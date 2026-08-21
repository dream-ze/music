import json
import logging
import re
from src import llm
from src.spec import SongSpec, parse_spec, safe_spec

_SYSTEM = "你是音乐制作人。根据用户对歌曲感觉的描述，只输出一个 JSON 对象，不要多余文字。"

_TEMPLATE = """用户想要的感觉：{style}
{hint}
请输出 JSON，字段：
language(如 zh), vocal{{gender, style}}, genre(数组), mood(数组),
instrument(数组), bpm(40-200 整数), structure(数组, 如 Intro/Verse/Pre-Chorus/Chorus/Bridge/Outro)。
只输出 JSON。"""


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


def plan_song(style_desc: str, lyrics_hint: str = "") -> SongSpec:
    hint = f"歌词片段参考：{lyrics_hint}" if lyrics_hint else ""
    prompt = _TEMPLATE.format(style=style_desc, hint=hint)
    try:
        raw = llm.complete(prompt, system=_SYSTEM)
        return parse_spec(_extract_json(raw))
    except Exception as e:
        logging.warning("planner LLM failed, using safe default: %s", e)
        return safe_spec()
