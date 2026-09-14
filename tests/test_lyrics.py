import json
from src import lyrics
from src.presets import get_preset
from src.spec import safe_spec

_TAGGED = """[Verse]
末班车掠过街角
City lights, sleepless nights

[Hook]
一拍一拍，把沉默拆开
Turn it up, feel the bass"""


def test_llm_output_accepted_when_only_line_breaks_moved(monkeypatch):
    raw = "末班车掠过街角，雨还挂在玻璃上，耳机鼓点替我壮胆"
    monkeypatch.setattr(lyrics.llm, "complete",
                        lambda *a, **k: "末班车掠过街角，\n雨还挂在玻璃上，\n耳机鼓点替我壮胆")
    events = []
    out = lyrics.structure_lyrics(raw, safe_spec(), status_events=events)
    assert out.splitlines()[1:] == ["末班车掠过街角，", "雨还挂在玻璃上，", "耳机鼓点替我壮胆"]
    assert out.startswith("[Verse]")           # 无标签 → 按结构补
    assert events == [{"stage": "歌词整理", "ok": True}]


def test_llm_output_rejected_when_text_changed(monkeypatch):
    raw = "末班车掠过街角，雨还挂在玻璃上"
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "末班车驶过街角，\n雨还挂在玻璃上")
    events = []
    out = lyrics.structure_lyrics(raw, safe_spec(), status_events=events)
    assert "驶过" not in out and "掠过" in out   # 丢弃 LLM 输出
    assert events == [{"stage": "歌词整理", "ok": False, "reason": "text_changed"}]


def test_empty_response_retries_once_then_falls_back(monkeypatch):
    calls = []
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: calls.append(1) or "   ")
    events = []
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec(), status_events=events)
    assert len(calls) == 2
    assert "第一句" in out and "[Verse]" in out
    assert events == [{"stage": "歌词整理", "ok": False, "reason": "empty"}]


def test_exception_falls_back_without_leaking_secret(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down, key=super-secret")
    monkeypatch.setattr(lyrics.llm, "complete", boom)
    events = []
    out = lyrics.structure_lyrics("歌词", safe_spec(),
                                  llm_options={"provider": "openai"}, status_events=events)
    assert "歌词" in out
    assert events == [{"stage": "歌词整理", "ok": False, "reason": "llm_error"}]
    assert "super-secret" not in json.dumps(events, ensure_ascii=False)


def test_fallback_splits_long_lines_deterministically(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    raw = "末班车掠过街角，雨还挂在玻璃上，耳机鼓点替我壮胆。"
    out = lyrics.structure_lyrics(raw, safe_spec())
    body = [l for l in out.splitlines() if l and not l.startswith("[")]
    assert body == ["末班车掠过街角，", "雨还挂在玻璃上，", "耳机鼓点替我壮胆。"]


def test_tagged_lyrics_keep_tags_and_never_duplicate(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    out = lyrics.structure_lyrics(_TAGGED, safe_spec())
    assert out.count("[Verse]") == 1 and out.count("[Hook]") == 1
    assert "[Chorus]" not in out
    assert out.count("末班车掠过街角") == 1


def test_untagged_lyrics_no_longer_duplicated_into_chorus(monkeypatch):
    """旧行为把整段复制成 [Chorus];新行为按结构补标签,不复制。"""
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec())
    assert out.count("第一句") == 1 and out.startswith("[Verse]")


def test_hiphop_preset_qualifies_verse_with_rap(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    spec = safe_spec()
    out = lyrics.structure_lyrics(_TAGGED, spec, preset=get_preset("hiphop.boom_bap"))
    assert "[Verse - rap]" in out and "[Hook]" in out


def test_prompt_contains_rules_and_forbids_edits(monkeypatch):
    seen = {}
    monkeypatch.setattr(lyrics.llm, "complete",
                        lambda prompt, **k: seen.update(prompt=prompt, system=k.get("system")) or "")
    lyrics.structure_lyrics("x", safe_spec(), preset=get_preset("hiphop.trap"))
    assert "6-10" in seen["prompt"] and "不改字" in seen["prompt"]
    assert "只能移动换行" in seen["system"]
