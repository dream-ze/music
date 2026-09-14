import json
from src import lyrics
from src.spec import safe_spec


def test_structure_lyrics_uses_llm(monkeypatch):
    monkeypatch.setattr(
        lyrics.llm, "complete",
        lambda *a, **k: "[Verse]\n我曾走过那条街\n[Chorus]\n后来啊",
    )
    out = lyrics.structure_lyrics("我曾走过那条街\n后来啊", safe_spec())
    assert "[Verse]" in out and "[Chorus]" in out


def test_structure_lyrics_fallback_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(lyrics.llm, "complete", boom)
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec())
    assert "[Verse]" in out and "[Chorus]" in out
    assert "第一句" in out  # 原歌词保留


def test_structure_lyrics_fallback_on_empty(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "   ")
    out = lyrics.structure_lyrics("只有一句", safe_spec())
    assert "[Verse]" in out and "[Chorus]" in out and "只有一句" in out


def test_structure_lyrics_reports_fallback_without_secret(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down, key=super-secret")

    events = []
    monkeypatch.setattr(lyrics.llm, "complete", boom)
    lyrics.structure_lyrics(
        "歌词", safe_spec(), llm_options={"provider": "openai"}, status_events=events
    )
    assert events == [{"stage": "歌词整理", "ok": False}]
    # 事件里不能夹带异常原文,那里面可能有 key
    assert "super-secret" not in json.dumps(events, ensure_ascii=False)


# ── 回退不得破坏已有结构 ────────────────────────────────────────────
#
# 用户手写的歌词常常自带 [Verse]/[Hook] 标记。旧的 _fallback 不看内容就套
# f"[Verse]\n{body}\n\n[Chorus]\n{body}",结果是标记重复、整段歌词被复制一遍、
# 还凭空多出一个跟 [Hook] 冲突的 [Chorus]。官方文档明确要求标记不要堆叠、
# Caption 与 Lyrics 不能互相矛盾。

_TAGGED = """[Verse]
末班车掠过街角
City lights, sleepless nights

[Hook]
一拍一拍，把沉默拆开
Turn it up, feel the bass"""


def test_fallback_passes_through_already_tagged_lyrics(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "   ")
    out = lyrics.structure_lyrics(_TAGGED, safe_spec())
    assert out == _TAGGED.strip()


def test_fallback_does_not_duplicate_tagged_lyrics(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "   ")
    out = lyrics.structure_lyrics(_TAGGED, safe_spec())
    assert out.count("[Verse]") == 1
    assert out.count("[Hook]") == 1
    assert "[Chorus]" not in out          # 不能塞进跟 [Hook] 打架的标记
    assert out.count("末班车掠过街角") == 1  # 不能把歌词复制一遍


def test_fallback_still_wraps_untagged_lyrics(monkeypatch):
    """没有标记的纯文本仍然要补上结构,否则模型没有分段依据。"""
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "   ")
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec())
    assert "[Verse]" in out and "[Chorus]" in out and "第一句" in out
