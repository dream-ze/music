"""歌词整理:只调整换行、不改字。LLM 负责断行,确定性校验兜底。"""
import logging

from src import llm
from src.lyric_text import apply_structure_tags, same_text, split_long_lines
from src.presets import Preset, get_preset
from src.spec import SongSpec

_SYSTEM = (
    "你是作词编辑。你的唯一任务是调整歌词的换行位置。"
    "绝对不可以增加、删除或修改任何一个字、标点或英文单词;只能移动换行。"
    "保留所有单独成行的 [标签] 行和段落之间的空行。只输出歌词文本,不要解释。"
)

_TEMPLATE = """断行规则:
- 每行 {min_s}-{max_s} 个音节(一个汉字算 1 个音节,英文按单词音节数)
- 同一段里位置相同的行音节数尽量接近(相差不超过 {tol})
- 不改字、不改标点、不改顺序;只移动换行
- 已有的 [标签] 行和段间空行原样保留

歌词:
{lyrics}"""


def _ask(text: str, preset: Preset, llm_options: dict | None) -> str:
    r = preset.lyric_rules
    prompt = _TEMPLATE.format(min_s=r.min_syllables, max_s=r.max_syllables,
                              tol=r.tolerance, lyrics=text)
    return llm.complete(prompt, system=_SYSTEM, **(llm_options or {})) or ""


def _emit(events: list[dict] | None, ok: bool, reason: str | None) -> None:
    if events is None:
        return
    ev: dict = {"stage": "歌词整理", "ok": ok}
    if not ok:
        ev["reason"] = reason
    events.append(ev)


def structure_lyrics(
    raw_lyrics: str,
    spec: SongSpec,
    *,
    preset: Preset | None = None,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> str:
    preset = preset or get_preset(spec.preset_id)
    rules = preset.lyric_rules
    base = raw_lyrics.strip() or "……"

    ok, reason, text = True, None, None
    try:
        out = _ask(base, preset, llm_options)
        if not out.strip():
            out = _ask(base, preset, llm_options)  # 空响应重试一次
        if not out.strip():
            ok, reason = False, "empty"
        elif not same_text(base, out):
            ok, reason = False, "text_changed"    # LLM 改了字:整份丢弃
        else:
            text = out.strip()
    except Exception as e:  # noqa: BLE001 — 事件里不带异常原文(可能含 key)
        logging.warning("lyrics LLM failed, using deterministic split: %s", e)
        ok, reason = False, "llm_error"

    if text is None:
        text = base
    # 无论 LLM 路径还是回退,都再做一次确定性切分:对合规文本是幂等的
    text = split_long_lines(text, rules.max_syllables, rules.tolerance)
    text = apply_structure_tags(text, spec.structure or preset.structure, preset.vocal_qualifier)
    _emit(status_events, ok, reason)
    return text
