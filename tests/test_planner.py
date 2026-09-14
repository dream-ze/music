import json
from src import planner
from src.presets import get_preset
from src.spec import SongSpec

GOOD = {
    "language": "zh",
    "vocal": {"gender": "male", "style": "laid-back rap"},
    "genre": ["hip hop", "boom bap"],
    "mood": ["nocturnal", "introspective"],
    "instrument": ["dusty drum break", "upright bass", "vinyl crackle"],
    "bpm": 90,
    "keyscale": "F minor",
    "timesignature": 4,
    "structure": ["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    "caption": "A warm 90s boom bap hip-hop track with a confident male rap over a dusty "
               "drum break, upright bass and vinyl crackle.",
}


def test_plan_song_parses_llm_json_and_marks_caption_full(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(GOOD))
    events = []
    spec = planner.plan_song("hip hop 说唱", preset=get_preset("hiphop.boom_bap"),
                             status_events=events)
    assert isinstance(spec, SongSpec)
    assert spec.bpm == 90 and spec.keyscale == "F minor" and spec.timesignature == 4
    assert spec.caption_full is True and spec.preset_id == "hiphop.boom_bap"
    assert events == [{"stage": "歌曲规划", "ok": True}]


def test_plan_song_json_in_code_fence(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: f"```json\n{json.dumps(GOOD)}\n```")
    assert planner.plan_song("随便").bpm == 90


def test_plan_song_normalizes_mixed_language_to_policy(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete",
                        lambda *a, **k: json.dumps(dict(GOOD, language="zh-en")))
    spec = planner.plan_song("中英混合", preset=get_preset("hiphop.trap"))
    assert spec.language == "zh"


def test_plan_song_cjk_in_output_falls_back_to_skeleton(monkeypatch):
    bad = dict(GOOD, genre=["hip hop", "中文说唱"], instrument=["鼓机", "贝斯"])
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(bad))
    events = []
    spec = planner.plan_song("说唱", preset=get_preset("hiphop.boom_bap"), status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "non_english"}]
    assert spec.preset_id == "hiphop.boom_bap" and spec.caption_full is False
    assert "boom bap" in spec.caption and spec.bpm == 90       # 骨架:区间中点
    assert spec.vocal.gender == "male" and "Hook" in spec.structure


def test_plan_song_garbage_falls_back_with_bad_json(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: "抱歉我不会")
    events = []
    spec = planner.plan_song("女声", status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "bad_json"}]
    assert spec.preset_id == "generic" and spec.caption          # generic 骨架也有英文 caption


def test_plan_song_exception_falls_back_with_llm_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(planner.llm, "complete", boom)
    events = []
    spec = planner.plan_song("女声", status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "llm_error"}]
    assert spec.language == "zh"


def test_plan_song_invalid_spec_reason(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(dict(GOOD, bpm=999)))
    events = []
    planner.plan_song("随便", status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "invalid_spec"}]


def test_plan_song_passes_llm_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(planner.llm, "complete",
                        lambda *a, **k: captured.update(k) or json.dumps(GOOD))
    planner.plan_song("温柔", llm_options={"provider": "deepseek", "model": "custom", "api_key": "k"})
    assert captured["provider"] == "deepseek" and captured["model"] == "custom"


def test_prompt_injects_preset_skeleton_examples_and_bpm_range(monkeypatch):
    seen = {}
    monkeypatch.setattr(planner.llm, "complete",
                        lambda prompt, **k: seen.update(prompt=prompt) or json.dumps(GOOD))
    planner.plan_song("说唱", preset=get_preset("hiphop.trap"))
    p = seen["prompt"]
    assert "130-150" in p and "808 sub-bass" in p and "Trap" in p
    assert "Chinese trap song" in p            # 官方示例句
    assert "不得出现中文" in p


def test_skeleton_spec_is_valid_and_english():
    spec = planner.skeleton_spec(get_preset("hiphop.trap"))
    assert spec.bpm == 140 and spec.timesignature == 4 and spec.genre == ["hip hop", "trap"]
    assert spec.caption and spec.caption_full is False
