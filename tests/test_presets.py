import pytest
from src.presets import PRESETS, Preset, get_preset
from src.textcheck import has_cjk


def test_registry_has_generic_and_two_hiphop_presets():
    assert set(PRESETS) == {"generic", "hiphop.boom_bap", "hiphop.trap"}


def test_get_preset_empty_returns_generic_and_unknown_raises():
    assert get_preset("").id == "generic"
    assert get_preset(None).id == "generic"
    with pytest.raises(ValueError):
        get_preset("hiphop.nope")


@pytest.mark.parametrize("pid", list(PRESETS))
def test_preset_english_fields_have_no_cjk(pid):
    p = PRESETS[pid]
    for text in [p.caption_skeleton, *p.genre_tags, *p.instrument_pool,
                 *p.texture_pool, *p.era_pool, *p.examples, p.keyscale_hint,
                 p.vocal_qualifier, p.render_skeleton()]:
        assert not has_cjk(text), text


@pytest.mark.parametrize("pid", list(PRESETS))
def test_preset_bpm_range_valid(pid):
    lo, hi = PRESETS[pid].bpm_range
    assert 40 <= lo < hi <= 200
    assert lo <= PRESETS[pid].bpm_default() <= hi


def test_hiphop_presets_use_hook_and_rap_qualifier():
    for pid in ("hiphop.boom_bap", "hiphop.trap"):
        p = PRESETS[pid]
        assert "Hook" in p.structure and "Chorus" not in p.structure
        assert p.vocal_qualifier == "rap"
        assert p.vocal_gender_default == "male"


def test_boom_bap_and_trap_bpm_ranges():
    assert PRESETS["hiphop.boom_bap"].bpm_range == (85, 95)
    assert PRESETS["hiphop.trap"].bpm_range == (130, 150)


def test_render_skeleton_fills_placeholders():
    s = PRESETS["hiphop.boom_bap"].render_skeleton()
    assert "{" not in s and "}" not in s
    assert "male rap" in s
    assert "dusty drum break" in s
