import json
import logging
import random
import re

from src import llm
from src.caption_bank import pick_examples
from src.presets import Preset, get_preset
from src.spec import SongSpec, VocalSpec, parse_spec
from src.style_sampler import StyleDraw, sample_style
from src.textcheck import has_cjk, normalize_language
from src.vocal_timbres import VocalTimbre, get_timbre

_SYSTEM = (
    "你是音乐制作人。根据用户对歌曲感觉的描述和给定的硬性要求,只输出一个 JSON 对象,不要多余文字。"
    "caption 与所有英文字段必须是英文,不得出现中文。"
)

_TEMPLATE = """用户想要的感觉:{style}
{hint}
硬性要求(必须全部体现在 caption 中,不得替换或遗漏):
- 曲风:{label}(caption 必须包含以下词之一:{genre_words})
- 乐器:{instruments}
- 质感:{textures};年代/制作:{era}
- 情绪:{moods}
- 人声:{gender} {vocal}
- 速度:{bpm} BPM
{fusion}- 禁止出现的词:{avoid}
参考:
- caption 句式骨架(可改写,须保持自然语言整句):{skeleton}
- 调性倾向:{keyscale_hint}
- 结构模板:{structure}
- 官方风格 caption 示例(学习句式与维度,不要照抄):
{examples}

请输出 JSON,字段:
language(zh/en/yue/unknown), keyscale(如 "F minor"), timesignature(2/3/4/6),
structure(数组), caption(1-3 句英文,覆盖上面全部硬性要求,并尽量覆盖
风格/情绪/乐器/质感/年代/制作/人声/速度/结构 九个维度,不超过 400 字符)。
所有字段不得出现中文。只输出 JSON。"""

_FUSION_LINE = "- 编曲演进:以{label}开始,后段逐渐融入{partner}的元素({instruments})\n"

_HINTS = {
    "missing_genre": "caption 缺少曲风词,必须包含其中之一:{genre_words}",
    "missing_timbre": "caption 缺少人声音色描述,必须包含其中之一:{timbre_words}",
    "conflict": "caption 出现了禁止的词:{avoid}",
}


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no json object in llm output")
    return json.loads(m.group(0))


def _emit(events: list[dict] | None, ok: bool, reason: str | None) -> None:
    if events is None:
        return
    ev: dict = {"stage": "歌曲规划", "ok": ok}
    if not ok:
        ev["reason"] = reason
    events.append(ev)


def check_caption(caption: str, preset: Preset, timbre: VocalTimbre | None) -> str | None:
    """返回不合格原因;合格返回 None。匹配不区分大小写。"""
    if has_cjk(caption):
        return "non_english"
    c = caption.lower()
    if preset.caption_keywords and not any(k in c for k in preset.caption_keywords):
        return "missing_genre"
    if timbre and not any(k in c for k in timbre.keywords):
        return "missing_timbre"
    if any(a.lower() in c for a in preset.avoid):
        return "conflict"
    return None


def _genres(preset: Preset, draw: StyleDraw) -> list[str]:
    tags = list(preset.genre_tags)
    if draw.fusion_id:
        tags += [t for t in get_preset(draw.fusion_id).genre_tags if t not in tags]
    return tags or ["pop"]


def _vocal_phrase(draw: StyleDraw, timbre: VocalTimbre | None) -> str:
    return f"{draw.vocal_gender} {timbre.caption if timbre else 'vocal'}"


def skeleton_spec(preset: Preset, draw: StyleDraw | None = None) -> SongSpec:
    """planner 降级时的 spec:用采样结果渲染 preset 骨架,降级也保留多样性。"""
    draw = draw or sample_style(preset, seed=0)
    timbre = get_timbre(draw.vocal_timbre)
    return SongSpec(
        language=preset.acestep.vocal_language_policy,
        vocal=VocalSpec(gender=draw.vocal_gender,
                        style=timbre.caption if timbre else "soft",
                        timbre=draw.vocal_timbre),
        genre=_genres(preset, draw),
        mood=draw.moods or ["neutral"],
        instrument=draw.instruments or ["drums", "bass", "keys"],
        bpm=draw.bpm,
        structure=list(preset.structure),
        caption=preset.render_skeleton(
            instruments=draw.instruments or None, textures=draw.textures or None,
            era=draw.era, vocal=_vocal_phrase(draw, timbre)),
        caption_full=False,
        keyscale="",
        timesignature=preset.timesignature,
        preset_id=preset.id,
        style_draw=draw.model_dump(),
    )


def _build_prompt(style_desc: str, lyrics_hint: str, preset: Preset, draw: StyleDraw,
                  timbre: VocalTimbre | None) -> str:
    rng = random.Random(draw.seed)
    examples = pick_examples(preset.id, draw.vocal_gender, rng, k=2)
    fusion = ""
    if draw.fusion_id:
        partner = get_preset(draw.fusion_id)
        own = set(preset.instrument_pool)
        borrowed = [i for i in draw.instruments if i not in own]
        fusion = _FUSION_LINE.format(label=preset.label, partner=partner.label,
                                     instruments=", ".join(borrowed) or "signature sounds")
        examples += pick_examples(partner.id, draw.vocal_gender, rng, k=1)
    return _TEMPLATE.format(
        style=style_desc.strip() or "(未填写,按硬性要求发挥)",
        hint=f"歌词片段参考:{lyrics_hint}" if lyrics_hint else "",
        label=preset.label,
        genre_words=", ".join(preset.caption_keywords[:2]) or "(不限)",
        instruments=", ".join(draw.instruments) or "(不限)",
        textures=", ".join(draw.textures) or "(不限)",
        era=draw.era,
        moods=", ".join(draw.moods) or "(不限)",
        gender=draw.vocal_gender,
        vocal=timbre.caption if timbre else "vocal",
        bpm=draw.bpm,
        fusion=fusion,
        avoid=", ".join(preset.avoid) or "(无)",
        skeleton=preset.caption_skeleton,
        keyscale_hint=preset.keyscale_hint or "(不限)",
        structure=" / ".join(preset.structure),
        examples="\n".join(f"  - {e}" for e in examples) or "  (无)",
    )


def _hint(reason: str, preset: Preset, timbre: VocalTimbre | None) -> str:
    return _HINTS[reason].format(
        genre_words=", ".join(preset.caption_keywords),
        timbre_words=", ".join(timbre.keywords) if timbre else "",
        avoid=", ".join(preset.avoid),
    )


def _apply_draw(data: dict, preset: Preset, draw: StyleDraw,
                timbre: VocalTimbre | None) -> None:
    """采样器是要素的唯一来源:LLM 给的 genre/mood/instrument/bpm/vocal 一律覆盖。"""
    data["genre"] = _genres(preset, draw)
    if draw.moods:
        data["mood"] = list(draw.moods)
    if draw.instruments:
        data["instrument"] = list(draw.instruments)
    data["bpm"] = draw.bpm
    data["vocal"] = {"gender": draw.vocal_gender,
                     "style": timbre.caption if timbre else "soft",
                     "timbre": draw.vocal_timbre}
    data["style_draw"] = draw.model_dump()


def plan_song(
    style_desc: str,
    lyrics_hint: str = "",
    *,
    preset: Preset | None = None,
    draw: StyleDraw | None = None,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> SongSpec:
    preset = preset or get_preset("")
    draw = draw or sample_style(preset, seed=0)
    timbre = get_timbre(draw.vocal_timbre)
    prompt = _build_prompt(style_desc, lyrics_hint, preset, draw, timbre)
    reason: str | None = None
    for _attempt in range(2):        # 只有 caption 校验失败才会进入第二轮
        try:
            raw = llm.complete(prompt, system=_SYSTEM, **(llm_options or {}))
        except Exception as e:  # noqa: BLE001 — 事件里不带异常原文
            logging.warning("planner LLM failed, using preset skeleton: %s", type(e).__name__)
            reason = "llm_error"
            break
        try:
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            reason = "bad_json"
            break
        data["language"] = normalize_language(
            str(data.get("language", "")), preset.acestep.vocal_language_policy)
        data["preset_id"] = preset.id
        data["caption_full"] = bool(str(data.get("caption", "")).strip())
        _apply_draw(data, preset, draw, timbre)
        try:
            spec = parse_spec(data)
        except ValueError as e:
            reason = "non_english" if "CJK" in str(e) else "invalid_spec"
            logging.warning("planner output rejected (%s), using preset skeleton", reason)
            break
        reason = check_caption(spec.caption, preset, timbre)
        if reason is None:
            _emit(status_events, True, None)
            return spec
        prompt += f"\n\n上一次输出不合格:{_hint(reason, preset, timbre)}。请重新输出完整 JSON。"
    _emit(status_events, False, reason)
    return skeleton_spec(preset, draw)
