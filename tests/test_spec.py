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
