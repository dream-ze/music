import logging

from src import llm
from src.spec import SongSpec

_SYSTEM = "你是作词编辑。把用户歌词按给定歌曲结构分段，用 [Verse]/[Chorus] 等标签标注，保留原词，不要新增大量歌词。"


def _fallback(raw_lyrics: str) -> str:
    body = raw_lyrics.strip() or "……"
    return f"[Verse]\n{body}\n\n[Chorus]\n{body}"


def structure_lyrics(raw_lyrics: str, spec: SongSpec) -> str:
    structure = " / ".join(spec.structure)
    prompt = (
        f"歌曲结构：{structure}\n"
        f"请按此结构给下面的歌词分段并加标签：\n{raw_lyrics}"
    )
    try:
        out = llm.complete(prompt, system=_SYSTEM)
        if out and "[" in out:
            return out.strip()
        return _fallback(raw_lyrics)
    except Exception as e:
        logging.warning("lyrics LLM failed, using fallback: %s", e)
        return _fallback(raw_lyrics)
