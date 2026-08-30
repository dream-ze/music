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
    assert events == ["歌词整理：已回退（模型调用失败）"]
    assert "super-secret" not in events[0]
