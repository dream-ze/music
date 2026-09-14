import pytest
from src.spec import SongSpec, parse_spec, safe_spec, SAFE_DEFAULT_SPEC


def test_safe_default_is_valid():
    spec = safe_spec()
    assert spec.language == "zh"
    assert 40 <= spec.bpm <= 200
    assert spec.structure  # 非空


def test_parse_valid_dict():
    data = {
        "language": "zh",
        "vocal": {"gender": "male", "style": "powerful"},
        "genre": ["rock"],
        "mood": ["angry"],
        "instrument": ["electric guitar"],
        "bpm": 140,
        "structure": ["Intro", "Verse", "Chorus"],
    }
    spec = parse_spec(data)
    assert spec.vocal.gender == "male"
    assert spec.bpm == 140


def test_parse_out_of_range_bpm_raises():
    data = dict(SAFE_DEFAULT_SPEC)
    data["bpm"] = 9999
    with pytest.raises(ValueError):
        parse_spec(data)


def test_parse_missing_field_uses_model_default():
    # 缺 vocal 时用默认 VocalSpec
    data = {k: v for k, v in SAFE_DEFAULT_SPEC.items() if k != "vocal"}
    spec = parse_spec(data)
    assert spec.vocal.gender == "female"


def test_songspec_default_instrument_matches_safe_default():
    assert SongSpec().instrument == SAFE_DEFAULT_SPEC["instrument"]


# ── 新字段与校验 ────────────────────────────────────────────────────

def test_new_fields_have_defaults_for_old_spec_json():
    """旧 spec_json 没有新字段也要能解析。"""
    spec = parse_spec(dict(SAFE_DEFAULT_SPEC))
    assert spec.caption == "" and spec.caption_full is False
    assert spec.keyscale == "" and spec.timesignature is None
    assert spec.preset_id == "generic"


def test_caption_with_cjk_rejected():
    data = dict(SAFE_DEFAULT_SPEC, caption="A hip hop track 中文说唱")
    with pytest.raises(ValueError, match="CJK"):
        parse_spec(data)


def test_genre_mood_instrument_with_cjk_rejected():
    for field in ("genre", "mood", "instrument"):
        data = dict(SAFE_DEFAULT_SPEC)
        data[field] = ["hip hop", "夜晚"]
        with pytest.raises(ValueError, match="CJK"):
            parse_spec(data)


def test_language_must_be_valid():
    with pytest.raises(ValueError):
        parse_spec(dict(SAFE_DEFAULT_SPEC, language="zh-en"))
    assert parse_spec(dict(SAFE_DEFAULT_SPEC, language="unknown")).language == "unknown"


def test_caption_max_512_chars():
    with pytest.raises(ValueError):
        parse_spec(dict(SAFE_DEFAULT_SPEC, caption="a" * 513))
    assert len(parse_spec(dict(SAFE_DEFAULT_SPEC, caption="a" * 512)).caption) == 512


def test_timesignature_enum():
    assert parse_spec(dict(SAFE_DEFAULT_SPEC, timesignature=4)).timesignature == 4
    with pytest.raises(ValueError):
        parse_spec(dict(SAFE_DEFAULT_SPEC, timesignature=5))
