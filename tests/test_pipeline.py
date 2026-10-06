import json
import pytest
from src import pipeline
from src.presets import get_preset
from src.spec import SAFE_DEFAULT_SPEC, SongSpec


@pytest.fixture
def capture(monkeypatch):
    """替换 planner / lyrics / 出歌,记录各阶段收到的参数。"""
    seen: dict = {}

    def fake_plan(style, lyrics_hint="", *, preset=None, draw=None, llm_options=None,
                  status_events=None):
        seen.update(plan_preset=preset.id, draw=draw, plan_options=llm_options)
        status_events.append({"stage": "歌曲规划", "ok": True})
        return pipeline.planner.skeleton_spec(preset, draw)

    def fake_lyrics(raw, spec, *, preset=None, llm_options=None, status_events=None):
        seen["lyrics_preset"] = preset.id
        status_events.append({"stage": "歌词整理", "ok": True})
        return "[Verse]\n" + raw

    def fake_gen(structured, spec, *, length, seed, out_path):
        seen.update(gen_spec=spec, gen_seed=seed, length=length)
        return out_path

    monkeypatch.setattr(pipeline.planner, "plan_song", fake_plan)
    monkeypatch.setattr(pipeline.lyrics, "structure_lyrics", fake_lyrics)
    monkeypatch.setattr(pipeline.song_gen, "generate_song", fake_gen)
    return seen


def test_orchestrates_resolve_sample_plan_lyrics_gen(capture, tmp_path):
    result = pipeline.make_song("我的歌词", "女声 R&B", length="short", seed=42,
                                work_dir=str(tmp_path))
    assert capture["plan_preset"] == capture["lyrics_preset"] == "rnb.soul"
    assert capture["draw"].preset_id == "rnb.soul" and capture["draw"].seed == 42
    assert capture["gen_seed"] == 42 and result["seed"] == 42
    assert capture["length"] == "short"
    assert result["style_draw"] == capture["draw"]
    assert isinstance(result["spec"], SongSpec) and result["preset_id"] == "rnb.soul"
    assert result["llm_status"] == [
        {"stage": "曲风识别", "ok": True, "source": "keyword"},
        {"stage": "歌曲规划", "ok": True},
        {"stage": "歌词整理", "ok": True},
    ]
    assert result["degraded"] is False


def test_seed_generated_when_missing_and_shared(capture, tmp_path):
    result = pipeline.make_song("词", "摇滚", work_dir=str(tmp_path))
    assert isinstance(result["seed"], int) and 0 <= result["seed"] < 2**31
    assert capture["gen_seed"] == result["seed"] == capture["draw"].seed


def test_overrides_become_locks(capture, tmp_path):
    result = pipeline.make_song(
        "词", "随便", seed=3, work_dir=str(tmp_path),
        overrides={"preset": "rock.band", "mood": ["sad"], "vocal_gender": "female",
                   "vocal_timbre": "choir", "creativity": "pure", "language": "en"})
    d = capture["draw"]
    assert d.preset_id == "rock.band" and d.moods == ["sad"]
    assert d.vocal_gender == "female" and d.vocal_timbre == "choir"
    assert d.bpm == get_preset("rock.band").bpm_default()         # pure → typical
    assert result["spec"].language == "en"
    assert result["spec"].mood == ["sad"]                         # 不再事后覆盖,由 draw 带入


def test_legacy_genre_tag_feeds_detection(capture, tmp_path):
    pipeline.make_song("词", "", seed=1, work_dir=str(tmp_path),
                       overrides={"genre": ["jazz"]})
    assert capture["plan_preset"] == "jazz.lounge"


def test_recent_draws_steer_random_genre(capture, tmp_path):
    recent = [{"preset_id": pid, "instruments": ["x"], "textures": [], "era": "modern",
               "moods": [], "vocal_timbre": "clear", "vocal_gender": "female", "bpm": 100,
               "seed": 0} for pid in ("pop.ballad", "rock.band", "lofi.chill")]
    for s in range(30):
        pipeline.make_song("词", "", seed=s, work_dir=str(tmp_path),
                           recent=[*recent, {"garbage": True}])
        assert capture["plan_preset"] not in {"pop.ballad", "rock.band", "lofi.chill"}


def test_unknown_preset_raises(capture, tmp_path):
    with pytest.raises(ValueError):
        pipeline.make_song("词", "x", work_dir=str(tmp_path), overrides={"preset": "nope"})


def test_all_llm_failures_still_generate(monkeypatch, tmp_path):
    calls = []

    def fail(*a, **k):
        calls.append(k)
        raise RuntimeError("offline")
    monkeypatch.setattr(pipeline.planner.llm, "complete", fail)
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    options = {"provider": "gemini", "model": "gemini-test", "api_key": "k"}
    result = pipeline.make_song("词", "夏天的海边", length="short", work_dir=str(tmp_path),
                                llm_options=options)
    assert len(calls) == 3                         # 识别 / 规划 / 断行各一次
    assert all(c["provider"] == "gemini" for c in calls)
    assert result["llm_status"] == [
        {"stage": "曲风识别", "ok": False, "source": "random", "reason": "llm_error"},
        {"stage": "歌曲规划", "ok": False, "reason": "llm_error"},
        {"stage": "歌词整理", "ok": False, "reason": "llm_error"},
    ]
    assert result["degraded"] is True


def test_uses_configured_provider_by_default(monkeypatch, tmp_path):
    """调用方没指定供应商时,走 config.LLM_PROVIDER。"""
    monkeypatch.setattr(pipeline.config, "LLM_PROVIDER", "deepseek")
    seen = []
    monkeypatch.setattr(pipeline.planner.llm, "complete",
                        lambda *a, **k: seen.append(k) or json.dumps(SAFE_DEFAULT_SPEC))
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    pipeline.make_song("词", "女声 R&B", work_dir=str(tmp_path))
    assert seen and {k.get("provider") for k in seen} == {"deepseek"}


def test_explicit_llm_options_override_configured_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.config, "LLM_PROVIDER", "deepseek")
    seen = []
    monkeypatch.setattr(pipeline.planner.llm, "complete",
                        lambda *a, **k: seen.append(k) or json.dumps(SAFE_DEFAULT_SPEC))
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    pipeline.make_song("词", "女声 R&B", work_dir=str(tmp_path),
                       llm_options={"provider": "gemini"})
    assert seen and {k.get("provider") for k in seen} == {"gemini"}


def test_instrumental_skips_lyrics_and_marks_spec(capture, tmp_path):
    result = pipeline.make_song("这些词会被忽略", "lo-fi", seed=2, work_dir=str(tmp_path),
                                instrumental=True, overrides={"vocal_timbre": "breathy"})
    assert "lyrics_preset" not in capture                       # 不调断行
    assert result["structured_lyrics"] == "[Instrumental]"
    assert capture["draw"].vocal_timbre == "instrumental" and capture["draw"].vocal_gender == ""
    assert capture["gen_spec"].instrumental is True
    assert [e["stage"] for e in result["llm_status"]] == ["曲风识别", "歌曲规划"]
