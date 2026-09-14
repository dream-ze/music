import json
from src import pipeline
from src.spec import SAFE_DEFAULT_SPEC, SongSpec


def test_make_song_orchestrates(monkeypatch, tmp_path):
    def fake_complete(*args, **kwargs):
        if "音乐制作人" in kwargs.get("system", ""):
            return json.dumps(SAFE_DEFAULT_SPEC)
        return "[Verse]\nx\n[Chorus]\ny"

    monkeypatch.setattr(pipeline.planner.llm, "complete", fake_complete)

    captured = {}
    def fake_gen(structured_lyrics, spec, *, length, seed, out_path):
        captured["lyrics"] = structured_lyrics
        captured["spec"] = spec
        captured["length"] = length
        with open(out_path, "wb") as f:
            f.write(b"RIFF")
        return out_path
    monkeypatch.setattr(pipeline.song_gen, "generate_song", fake_gen)

    result = pipeline.make_song(
        "我的歌词", "女声 R&B", length="short", work_dir=str(tmp_path)
    )
    assert isinstance(result["spec"], SongSpec)
    assert "[Verse]" in result["structured_lyrics"]
    assert result["song"].endswith(".wav")
    assert captured["length"] == "short"
    assert "[Verse]" in captured["lyrics"]
    assert isinstance(captured["spec"], SongSpec)
    assert result["llm_status"] == [
        {"stage": "歌曲规划", "ok": True}, {"stage": "歌词整理", "ok": True}
    ]
    assert result["degraded"] is False


def test_make_song_propagates_llm_options_and_keeps_generating_on_fallback(
    monkeypatch, tmp_path
):
    calls = []

    def fail(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("offline")

    monkeypatch.setattr(pipeline.planner.llm, "complete", fail)
    monkeypatch.setattr(
        pipeline.song_gen, "generate_song",
        lambda lyrics, spec, **kwargs: kwargs["out_path"],
    )
    options = {"provider": "gemini", "model": "gemini-test", "api_key": "k"}
    result = pipeline.make_song(
        "词", "感觉", length="short", work_dir=str(tmp_path), llm_options=options
    )
    assert len(calls) == 2
    assert all(call["provider"] == "gemini" for call in calls)
    assert result["llm_status"] == [
        {"stage": "歌曲规划", "ok": False}, {"stage": "歌词整理", "ok": False}
    ]
    assert result["degraded"] is True


def test_make_song_applies_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline.planner.llm, "complete", lambda *a, **k: json.dumps(SAFE_DEFAULT_SPEC)
    )
    monkeypatch.setattr(
        pipeline.lyrics.llm, "complete", lambda *a, **k: "[Verse]\nx"
    )
    seen = {}
    monkeypatch.setattr(
        pipeline.song_gen, "generate_song",
        lambda structured, spec, **k: seen.setdefault("spec", spec) or k["out_path"],
    )

    pipeline.make_song(
        "词", "随便", work_dir=str(tmp_path),
        overrides={"genre": ["R&B"], "vocal_gender": "male", "language": "en"},
    )
    spec = seen["spec"]
    assert spec.genre == ["R&B"]
    assert spec.vocal.gender == "male"
    assert spec.language == "en"
    # 未覆盖字段保持 planner 结果
    assert spec.mood == SAFE_DEFAULT_SPEC["mood"]


def test_make_song_uses_configured_provider_by_default(monkeypatch, tmp_path):
    """调用方没指定供应商时,走 config.LLM_PROVIDER —— 否则 provider 写死在
    llm.complete 的默认参数里,API 链路上没有任何入口能换掉它。"""
    monkeypatch.setattr(pipeline.config, "LLM_PROVIDER", "deepseek")
    seen = []
    monkeypatch.setattr(pipeline.planner.llm, "complete",
                        lambda *a, **k: seen.append(k) or json.dumps(SAFE_DEFAULT_SPEC))
    monkeypatch.setattr(pipeline.lyrics.llm, "complete",
                        lambda *a, **k: seen.append(k) or "[Verse]\nx")
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])

    pipeline.make_song("词", "感觉", work_dir=str(tmp_path))

    assert [k.get("provider") for k in seen] == ["deepseek", "deepseek"]


def test_explicit_llm_options_override_configured_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.config, "LLM_PROVIDER", "deepseek")
    seen = []
    monkeypatch.setattr(pipeline.planner.llm, "complete",
                        lambda *a, **k: seen.append(k) or json.dumps(SAFE_DEFAULT_SPEC))
    monkeypatch.setattr(pipeline.lyrics.llm, "complete",
                        lambda *a, **k: seen.append(k) or "[Verse]\nx")
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])

    pipeline.make_song("词", "感觉", work_dir=str(tmp_path),
                       llm_options={"provider": "gemini"})

    assert [k.get("provider") for k in seen] == ["gemini", "gemini"]
