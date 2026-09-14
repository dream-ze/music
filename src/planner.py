import json
import logging
import re

from src import llm
from src.presets import Preset, get_preset
from src.spec import SongSpec, VocalSpec, parse_spec
from src.textcheck import normalize_language

_SYSTEM = (
    "你是音乐制作人。根据用户对歌曲感觉的描述和给定的风格预设,只输出一个 JSON 对象,不要多余文字。"
    "caption 与所有英文字段必须是英文,不得出现中文。"
)

_TEMPLATE = """用户想要的感觉:{style}
{hint}
风格预设:{label}
- caption 句式骨架(英文;可改写,但须保持自然语言整句):{skeleton}
- 可选乐器词:{instruments}
- 可选质感词:{textures}
- 可选年代/制作词:{eras}
- BPM 范围:{bpm_lo}-{bpm_hi}
- 调性倾向:{keyscale_hint}
- 结构模板:{structure}
- 官方风格 caption 示例(学习句式与维度,不要照抄):
{examples}

请输出 JSON,字段:
language(zh/en/yue/unknown), vocal{{gender, style}}, genre(英文数组), mood(英文数组),
instrument(英文数组), bpm(整数,在范围内), keyscale(如 "F minor"), timesignature(2/3/4/6),
structure(数组), caption(1-3 句英文,尽量覆盖 风格/情绪/乐器/质感/年代/制作/人声/速度/结构 九个维度,
不超过 400 字符)。所有字段不得出现中文。只输出 JSON。"""


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


def skeleton_spec(preset: Preset) -> SongSpec:
    """planner 降级时的 spec:用 preset 的英文骨架,而不是硬编码的 mandopop 模板。"""
    return SongSpec(
        language=preset.acestep.vocal_language_policy,
        vocal=VocalSpec(gender=preset.vocal_gender_default,
                        style=preset.vocal_qualifier or "soft"),
        genre=list(preset.genre_tags) or ["pop"],
        mood=["neutral"],
        instrument=list(preset.instrument_pool[:3]) or ["drums", "bass", "keys"],
        bpm=preset.bpm_default(),
        structure=list(preset.structure),
        caption=preset.render_skeleton(),
        caption_full=False,
        keyscale="",
        timesignature=preset.timesignature,
        preset_id=preset.id,
    )


def _build_prompt(style_desc: str, lyrics_hint: str, preset: Preset) -> str:
    hint = f"歌词片段参考:{lyrics_hint}" if lyrics_hint else ""
    return _TEMPLATE.format(
        style=style_desc, hint=hint, label=preset.label,
        skeleton=preset.caption_skeleton,
        instruments=", ".join(preset.instrument_pool) or "(不限)",
        textures=", ".join(preset.texture_pool) or "(不限)",
        eras=", ".join(preset.era_pool) or "(不限)",
        bpm_lo=preset.bpm_range[0], bpm_hi=preset.bpm_range[1],
        keyscale_hint=preset.keyscale_hint or "(不限)",
        structure=" / ".join(preset.structure),
        examples="\n".join(f"  - {e}" for e in preset.examples) or "  (无)",
    )


def plan_song(
    style_desc: str,
    lyrics_hint: str = "",
    *,
    preset: Preset | None = None,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> SongSpec:
    preset = preset or get_preset("")
    prompt = _build_prompt(style_desc, lyrics_hint, preset)
    reason: str | None
    try:
        raw = llm.complete(prompt, system=_SYSTEM, **(llm_options or {}))
    except Exception as e:  # noqa: BLE001 — 事件里不带异常原文
        logging.warning("planner LLM failed, using preset skeleton: %s", e)
        reason = "llm_error"
    else:
        try:
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            reason = "bad_json"
        else:
            data["language"] = normalize_language(
                str(data.get("language", "")), preset.acestep.vocal_language_policy
            )
            data["preset_id"] = preset.id
            data["caption_full"] = bool(str(data.get("caption", "")).strip())
            try:
                spec = parse_spec(data)
            except ValueError as e:
                reason = "non_english" if "CJK" in str(e) else "invalid_spec"
                logging.warning("planner output rejected (%s), using preset skeleton", reason)
            else:
                _emit(status_events, True, None)
                return spec
    _emit(status_events, False, reason)
    return skeleton_spec(preset)
