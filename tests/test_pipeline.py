import json
from src import pipeline
from src.spec import SAFE_DEFAULT_SPEC, SongSpec


def test_make_song_orchestrates(monkeypatch, tmp_path):
    def fake_complete(*args, **kwargs):
        if "音乐制作人" in kwargs.get("system", ""):
            return json.dumps(SAFE_DEFAULT_SPEC)
        return "我的歌词"   # 断行器只接受"不改字"的输出;无标签 → 自动补 [Verse]

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
        {"stage": "歌曲规划", "ok": False, "reason": "llm_error"},
        {"stage": "歌词整理", "ok": False, "reason": "llm_error"},
    ]
    assert result["degraded"] is True


def test_make_song_applies_overrides(monkeypatch, tmp_path):
    # planner 与 lyrics 共用同一个 src.llm 模块,不能分别 patch(后者会覆盖前者);按 system 分流
    def fake_complete(prompt, *a, **kwargs):
        if "音乐制作人" in kwargs.get("system", ""):
            return json.dumps(SAFE_DEFAULT_SPEC)
        return "词"
    monkeypatch.setattr(pipeline.planner.llm, "complete", fake_complete)
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


def test_make_song_threads_preset_to_planner_and_lyrics(monkeypatch, tmp_path):
    seen = {}

    def fake_plan(style, lyrics_hint="", *, preset=None, llm_options=None, status_events=None):
        seen["plan_preset"] = preset.id
        status_events.append({"stage": "歌曲规划", "ok": True})
        return pipeline.planner.skeleton_spec(preset)

    def fake_lyrics(raw, spec, *, preset=None, llm_options=None, status_events=None):
        seen["lyrics_preset"] = preset.id
        status_events.append({"stage": "歌词整理", "ok": True})
        return "[Verse - rap]\n" + raw

    monkeypatch.setattr(pipeline.planner, "plan_song", fake_plan)
    monkeypatch.setattr(pipeline.lyrics, "structure_lyrics", fake_lyrics)
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])

    result = pipeline.make_song("词", "说唱", work_dir=str(tmp_path),
                                overrides={"preset": "hiphop.trap"})
    assert seen == {"plan_preset": "hiphop.trap", "lyrics_preset": "hiphop.trap"}
    assert result["preset_id"] == "hiphop.trap"
    assert result["spec"].preset_id == "hiphop.trap"
    assert result["degraded"] is False


def test_make_song_unknown_preset_raises(monkeypatch, tmp_path):
    import pytest
    # 必须 patch 掉出歌:否则 RED 阶段会一路跑到真 generate_song 去加载 ACE-Step 模型
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    monkeypatch.setattr(pipeline.planner.llm, "complete", lambda *a, **k: "{}")
    with pytest.raises(ValueError):
        pipeline.make_song("词", "x", work_dir=str(tmp_path), overrides={"preset": "nope"})
