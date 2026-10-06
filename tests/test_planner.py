import json
import pytest
from src import planner
from src.presets import UI_GENRES, get_preset
from src.spec import SongSpec
from src.style_sampler import Locks, StyleDraw, sample_style
from src.vocal_timbres import get_timbre

DRAW = StyleDraw(
    preset_id="hiphop.boom_bap",
    instruments=["jazzy piano sample", "dusty drum break", "upright bass"],
    textures=["warm"], era="90s", moods=["nocturnal"],
    vocal_timbre="rap_laidback", vocal_gender="male", bpm=88, seed=1,
)
BOOM = get_preset("hiphop.boom_bap")
CAPTION = ("A warm 90s boom bap hip-hop track with a laid-back, relaxed male rap flow over "
           "jazzy piano samples, a dusty drum break and upright bass.")
GOOD = {
    "language": "zh",
    "vocal": {"gender": "female", "style": "whatever"},     # 会被 draw 覆盖
    "genre": ["jazz"], "mood": ["happy"], "instrument": ["kazoo"], "bpm": 150,
    "keyscale": "F minor", "timesignature": 4,
    "structure": ["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    "caption": CAPTION,
}


def _llm(monkeypatch, *outputs):
    """按顺序返回 outputs,记录每次调用的 prompt 与 kwargs。"""
    calls = []
    seq = list(outputs)

    def fake(prompt, **k):
        calls.append({"prompt": prompt, **k})
        out = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(out, Exception):
            raise out
        return out
    monkeypatch.setattr(planner.llm, "complete", fake)
    return calls


def _plan(**kw):
    return planner.plan_song("说唱", preset=BOOM, draw=DRAW, **kw)


def test_draw_overrides_llm_choices(monkeypatch):
    _llm(monkeypatch, json.dumps(GOOD))
    events = []
    spec = _plan(status_events=events)
    assert isinstance(spec, SongSpec)
    assert events == [{"stage": "歌曲规划", "ok": True}]
    assert spec.caption == CAPTION and spec.caption_full is True
    assert spec.instrument == DRAW.instruments and spec.mood == ["nocturnal"]
    assert spec.bpm == 88 and spec.genre == ["hip hop", "boom bap"]
    assert spec.vocal.gender == "male" and spec.vocal.timbre == "rap_laidback"
    assert spec.vocal.style == "laid-back, relaxed rap flow"
    assert spec.keyscale == "F minor" and spec.preset_id == "hiphop.boom_bap"
    assert spec.style_draw == DRAW.model_dump()


def test_json_in_code_fence(monkeypatch):
    fence = "`" * 3      # 不在源码里直接写三个反引号,免得破坏 markdown 代码块
    _llm(monkeypatch, f"{fence}json\n{json.dumps(GOOD)}\n{fence}")
    assert _plan().caption_full is True


def test_mixed_language_normalized_to_policy(monkeypatch):
    _llm(monkeypatch, json.dumps(dict(GOOD, language="zh-en")))
    assert _plan().language == "zh"


def test_prompt_carries_hard_constraints_and_examples(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(GOOD))
    _plan()
    p = calls[0]["prompt"]
    for s in ["jazzy piano sample", "dusty drum break", "upright bass", "warm", "90s",
              "nocturnal", "male laid-back, relaxed rap flow", "88 BPM", "boom bap",
              "supersaw", "硬性要求", "不得出现中文"]:
        assert s in p, s
    assert "官方风格 caption 示例" in p and "\n  - " in p


def test_empty_feeling_is_marked_in_prompt(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(GOOD))
    planner.plan_song("", preset=BOOM, draw=DRAW)
    assert "未填写" in calls[0]["prompt"]


def test_missing_genre_retries_once_with_hint_then_succeeds(monkeypatch):
    bad = dict(GOOD, caption="A warm track with a laid-back, relaxed male rap flow.")
    calls = _llm(monkeypatch, json.dumps(bad), json.dumps(GOOD))
    events = []
    spec = _plan(status_events=events)
    assert len(calls) == 2 and "上一次输出不合格" in calls[1]["prompt"]
    assert "boom bap" in calls[1]["prompt"]
    assert spec.caption == CAPTION and events == [{"stage": "歌曲规划", "ok": True}]


@pytest.mark.parametrize("caption,reason", [
    ("A warm 90s boom bap track with a male rap verse.", "missing_timbre"),
    ("A boom bap track, laid-back rap flow, supersaw leads.", "conflict"),
    ("A smooth track with a laid-back rap flow.", "missing_genre"),
])
def test_two_bad_captions_fall_back_to_skeleton(monkeypatch, caption, reason):
    calls = _llm(monkeypatch, json.dumps(dict(GOOD, caption=caption)))
    events = []
    spec = _plan(status_events=events)
    assert len(calls) == 2
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": reason}]
    assert spec.caption_full is False and "jazzy piano sample" in spec.caption
    assert spec.bpm == 88 and spec.style_draw == DRAW.model_dump()


def test_cjk_falls_back_without_retry(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(dict(GOOD, caption="中文 caption")))
    events = []
    spec = _plan(status_events=events)
    assert len(calls) == 1
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "non_english"}]
    assert "Hook" in spec.structure and spec.vocal.gender == "male"


def test_bad_json_falls_back(monkeypatch):
    _llm(monkeypatch, "抱歉我不会")
    events = []
    _plan(status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "bad_json"}]


def test_exception_falls_back_without_leaking(monkeypatch):
    _llm(monkeypatch, RuntimeError("bad key sk-SECRET"))
    events = []
    spec = _plan(status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "llm_error"}]
    assert spec.language == "zh"


def test_invalid_spec_reason(monkeypatch):
    _llm(monkeypatch, json.dumps(dict(GOOD, timesignature=5)))
    events = []
    _plan(status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "invalid_spec"}]


def test_passes_llm_options(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(GOOD))
    _plan(llm_options={"provider": "deepseek", "model": "custom", "api_key": "k"})
    assert calls[0]["provider"] == "deepseek" and calls[0]["model"] == "custom"


def test_fusion_line_and_partner_genre(monkeypatch):
    draw = DRAW.model_copy(update={"fusion_id": "jazz.lounge",
                                   "instruments": [*DRAW.instruments, "muted trumpet"]})
    calls = _llm(monkeypatch, json.dumps(GOOD))
    spec = planner.plan_song("说唱", preset=BOOM, draw=draw)
    assert "编曲演进" in calls[0]["prompt"] and "爵士" in calls[0]["prompt"]
    assert "muted trumpet" in calls[0]["prompt"]
    assert spec.genre == ["hip hop", "boom bap", "jazz"]


def test_draw_defaults_to_seed_zero_sample(monkeypatch):
    calls = _llm(monkeypatch, "not json")
    spec = planner.plan_song("说唱", preset=BOOM)
    assert spec.style_draw == sample_style(BOOM, seed=0).model_dump()
    assert len(calls) == 1


def test_check_caption_reasons():
    t = get_timbre("rap_laidback")
    assert planner.check_caption(CAPTION, BOOM, t) is None
    assert planner.check_caption("中文", BOOM, t) == "non_english"
    assert planner.check_caption("laid-back rap", BOOM, t) == "missing_genre"
    assert planner.check_caption("Boom Bap rap", BOOM, t) == "missing_timbre"   # 大小写不敏感
    assert planner.check_caption("boom bap laid-back supersaw", BOOM, t) == "conflict"
    assert planner.check_caption("anything", get_preset("generic"), None) is None


@pytest.mark.parametrize("pid", UI_GENRES)
def test_skeleton_passes_its_own_check_for_every_timbre(pid):
    p = get_preset(pid)
    for tid in p.vocal_timbres:
        d = sample_style(p, seed=3, locks=Locks(vocal_timbre=tid))
        spec = planner.skeleton_spec(p, d)
        assert spec.caption_full is False and spec.bpm == d.bpm
        assert planner.check_caption(spec.caption, p, get_timbre(tid)) is None, spec.caption


INSTR_DRAW = DRAW.model_copy(update={"vocal_timbre": "instrumental", "vocal_gender": ""})
INSTR_CAPTION = ("A warm 90s boom bap instrumental hip-hop beat with jazzy piano samples, "
                 "a dusty drum break and upright bass, no vocals.")


def test_instrumental_prompt_and_check(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(dict(GOOD, caption=INSTR_CAPTION)))
    events = []
    spec = planner.plan_song("说唱", preset=BOOM, draw=INSTR_DRAW, status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": True}]
    assert "纯音乐" in calls[0]["prompt"] and "laid-back" not in calls[0]["prompt"]
    assert spec.vocal.timbre == "instrumental" and spec.vocal.gender == ""


def test_instrumental_skeleton_passes_check():
    spec = planner.skeleton_spec(BOOM, INSTR_DRAW)
    assert planner.check_caption(spec.caption, BOOM, get_timbre("instrumental")) is None
