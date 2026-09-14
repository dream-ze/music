import logging
import re

from src import llm
from src.spec import SongSpec

_SYSTEM = "你是作词编辑。把用户歌词按给定歌曲结构分段，用 [Verse]/[Chorus] 等标签标注，保留原词，不要新增大量歌词。"


# 单独成行的 [xxx] 才算结构标记;行内的方括号(如歌词里的括号和声)不算。
_TAG_LINE = re.compile(r"^\s*\[[^\]]+\]\s*$", re.MULTILINE)


def _fallback(raw_lyrics: str) -> str:
    """LLM 不可用时的兜底分段。

    已经带结构标记的歌词原样透传:再包一层会让标记重复、整段歌词被复制,
    还会塞进一个跟用户自己的 [Hook] 互相矛盾的 [Chorus]。官方文档要求
    标记不堆叠、Caption 与 Lyrics 不冲突。
    """
    body = raw_lyrics.strip() or "……"
    if _TAG_LINE.search(body):
        return body
    return f"[Verse]\n{body}\n\n[Chorus]\n{body}"


def structure_lyrics(
    raw_lyrics: str,
    spec: SongSpec,
    *,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> str:
    structure = " / ".join(spec.structure)
    prompt = (
        f"歌曲结构：{structure}\n"
        f"请按此结构给下面的歌词分段并加标签：\n{raw_lyrics}"
    )
    try:
        out = llm.complete(prompt, system=_SYSTEM, **(llm_options or {}))
        if out and "[" in out:
            if status_events is not None:
                status_events.append({"stage": "歌词整理", "ok": True})
            return out.strip()
        if status_events is not None:
            status_events.append({"stage": "歌词整理", "ok": False})
        return _fallback(raw_lyrics)
    except Exception as e:
        logging.warning("lyrics LLM failed, using fallback: %s", e)
        if status_events is not None:
            status_events.append({"stage": "歌词整理", "ok": False})
        return _fallback(raw_lyrics)
