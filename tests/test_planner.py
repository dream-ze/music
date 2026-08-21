import json
from src import planner
from src.spec import SongSpec, SAFE_DEFAULT_SPEC


def test_plan_song_parses_llm_json(monkeypatch):
    fake = {
        "language": "zh",
        "vocal": {"gender": "female", "style": "soft"},
        "genre": ["r&b"],
        "mood": ["nostalgic"],
        "instrument": ["piano"],
        "bpm": 82,
        "structure": ["Intro", "Verse", "Chorus"],
    }
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(fake))
    spec = planner.plan_song("女声，R&B，深夜，温柔")
    assert isinstance(spec, SongSpec)
    assert spec.bpm == 82
    assert "r&b" in spec.genre


def test_plan_song_json_in_code_fence(monkeypatch):
    fake = json.dumps(SAFE_DEFAULT_SPEC)
    monkeypatch.setattr(
        planner.llm, "complete", lambda *a, **k: f"```json\n{fake}\n```"
    )
    spec = planner.plan_song("随便")
    assert spec.language == "zh"


def test_plan_song_falls_back_on_garbage(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: "抱歉我不会")
    spec = planner.plan_song("女声")
    assert spec.bpm == SAFE_DEFAULT_SPEC["bpm"]  # 回退默认


def test_plan_song_falls_back_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(planner.llm, "complete", boom)
    spec = planner.plan_song("女声")
    assert spec.language == "zh"  # 未抛异常，回退成功
