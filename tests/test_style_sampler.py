# tests/test_style_sampler.py
import pytest
from src.presets import UI_GENRES, get_preset
from src.style_sampler import Locks, StyleDraw, parse_recent, sample_style


@pytest.mark.parametrize("pid", UI_GENRES)
def test_same_seed_same_draw(pid):
    p = get_preset(pid)
    assert sample_style(p, seed=7) == sample_style(p, seed=7)


@pytest.mark.parametrize("pid", UI_GENRES)
def test_different_seeds_vary(pid):
    p = get_preset(pid)
    draws = {sample_style(p, seed=s).model_dump_json(exclude={"seed"}) for s in range(20)}
    assert len(draws) > 1


@pytest.mark.parametrize("pid", UI_GENRES)
def test_invariants_hold_for_every_level(pid):
    p = get_preset(pid)
    lo, hi = p.bpm_range
    for s in range(40):
        for level in ("pure", "normal", "fusion"):
            d = sample_style(p, seed=s, creativity=level)
            assert d.preset_id == pid and d.seed == s
            assert 1 <= len(d.instruments) <= 5
            assert len(set(d.instruments)) == len(d.instruments)
            for a, b in p.exclusions:
                assert not (a in d.instruments and b in d.instruments), (a, b)
            assert lo <= d.bpm <= hi
            assert d.vocal_timbre in p.vocal_timbres
            assert d.vocal_gender == p.vocal_gender_default
            assert d.era in p.era_pool and set(d.textures) <= set(p.texture_pool)


def test_locks_are_kept_verbatim():
    d = sample_style(get_preset("folk.acoustic"), seed=1,
                     locks=Locks(moods=["sad"], vocal_gender="female", vocal_timbre="choir"))
    assert d.moods == ["sad"] and d.vocal_gender == "female" and d.vocal_timbre == "choir"


def test_pure_uses_typical_bpm_and_only_harmonic_rhythm():
    p = get_preset("jazz.lounge")
    allowed = set(p.instrument_pools["harmonic"].items) | set(p.instrument_pools["rhythm"].items)
    for s in range(30):
        d = sample_style(p, seed=s, creativity="pure")
        assert d.bpm == p.bpm_default() and d.fusion_id is None
        assert set(d.instruments) <= allowed
        assert d.era == p.era_pool[0] and len(d.textures) == 1


def test_fusion_adds_partner_and_one_partner_color():
    p = get_preset("pop.city_pop")
    for s in range(30):
        d = sample_style(p, seed=s, creativity="fusion")
        assert d.fusion_id in p.fusion_partners
        partner_color = set(get_preset(d.fusion_id).instrument_pools["color"].items)
        assert set(d.instruments) & partner_color


def test_unknown_creativity_raises():
    with pytest.raises(ValueError):
        sample_style(get_preset("rock.band"), seed=1, creativity="wild")


def _draw(**over):
    base = dict(preset_id="hiphop.boom_bap", instruments=["jazzy piano sample"],
                textures=["warm"], era="90s", moods=["confident"], vocal_timbre="deep",
                vocal_gender="male", bpm=90, seed=0)
    base.update(over)
    return StyleDraw(**base)


def test_recent_instruments_are_down_weighted():
    p = get_preset("hiphop.boom_bap")
    target = "jazzy piano sample"
    recent = [_draw(instruments=[target])]
    base = sum(target in sample_style(p, seed=s).instruments for s in range(300))
    down = sum(target in sample_style(p, seed=s, recent=recent).instruments
               for s in range(300))
    assert down < base * 0.7


def test_recent_timbres_are_down_weighted():
    p = get_preset("hiphop.boom_bap")
    recent = [_draw(vocal_timbre="rap_laidback")]
    base = sum(sample_style(p, seed=s).vocal_timbre == "rap_laidback" for s in range(300))
    down = sum(sample_style(p, seed=s, recent=recent).vocal_timbre == "rap_laidback"
               for s in range(300))
    assert down < base * 0.7


def test_parse_recent_skips_invalid_items():
    good = _draw().model_dump()
    assert parse_recent([{"bad": 1}, good, None, "x"]) == [_draw()]


from src import style_sampler
from src.style_sampler import detect_by_keywords, resolve_genre


@pytest.mark.parametrize("text,expected", [
    ("想要 City Pop 的感觉", "pop.city_pop"),       # 不能被 "pop" 抢走
    ("pop punk 青春", "rock.pop_punk"),
    ("民谣吉他，女声", "folk.acoustic"),
    ("女声 R&B 深夜", "rnb.soul"),
    ("夏天的海边", None),
    ("", None),
])
def test_detect_by_keywords(text, expected):
    assert detect_by_keywords(text) == expected


def test_resolve_ui_choice_wins_and_skips_llm(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete",
                        lambda *a, **k: pytest.fail("不该调用 LLM"))
    events = []
    p = resolve_genre("jazz.lounge", "摇滚", seed=1, status_events=events)
    assert p.id == "jazz.lounge"
    assert events == [{"stage": "曲风识别", "ok": True, "source": "ui"}]


def test_resolve_unknown_ui_id_raises():
    with pytest.raises(ValueError):
        resolve_genre("nope", "", seed=1)


def test_resolve_keyword_before_llm(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete",
                        lambda *a, **k: pytest.fail("不该调用 LLM"))
    events = []
    assert resolve_genre("", "来点 synthwave", seed=1, status_events=events).id == \
        "electronic.synthwave"
    assert events[0]["source"] == "keyword"


def test_resolve_llm_when_keywords_miss(monkeypatch):
    seen = {}

    def fake(prompt, **k):
        seen.update(prompt=prompt, **k)
        return "我觉得是 jazz.lounge"
    monkeypatch.setattr(style_sampler.llm, "complete", fake)
    events = []
    p = resolve_genre("", "夜里的小酒馆", seed=1, llm_options={"provider": "deepseek"},
                      status_events=events)
    assert p.id == "jazz.lounge" and seen["provider"] == "deepseek"
    assert "rock.anime" in seen["prompt"] and "夜里的小酒馆" in seen["prompt"]
    assert events == [{"stage": "曲风识别", "ok": True, "source": "llm"}]


def test_resolve_llm_garbage_falls_back_to_random(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete", lambda *a, **k: "不知道")
    events = []
    p = resolve_genre("", "夜里的小酒馆", seed=1, status_events=events)
    assert p.id in UI_GENRES
    assert events == [{"stage": "曲风识别", "ok": False, "source": "random",
                       "reason": "unknown_genre"}]


def test_resolve_llm_error_does_not_leak(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bad key sk-SECRET")
    monkeypatch.setattr(style_sampler.llm, "complete", boom)
    events = []
    resolve_genre("", "夜里的小酒馆", seed=1, status_events=events)
    assert events[0]["reason"] == "llm_error"
    assert "SECRET" not in str(events)


def test_resolve_empty_feeling_is_random_without_llm(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete",
                        lambda *a, **k: pytest.fail("不该调用 LLM"))
    events = []
    a = resolve_genre("", "  ", seed=5, status_events=events)
    assert a.id == resolve_genre("", "", seed=5).id          # 同 seed 同结果
    assert events == [{"stage": "曲风识别", "ok": True, "source": "random"}]


def test_resolve_random_avoids_three_most_recent():
    recent = ["pop.ballad", "rock.band", "lofi.chill", "jazz.lounge"]
    picked = {resolve_genre("", "", seed=s, recent_ids=recent).id for s in range(200)}
    assert not picked & {"pop.ballad", "rock.band", "lofi.chill"}
    assert "jazz.lounge" in picked                           # 第 4 个不避
