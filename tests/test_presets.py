import pytest
from src.presets import POOL_ORDER, PRESETS, Pool, Preset, get_preset
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


def _mini(**over):
    base = dict(id="x", label="x", family="x", caption_skeleton="{instruments}",
                structure=["Verse"])
    base.update(over)
    return Preset(**base)


def test_instrument_pool_flattens_role_pools_in_order():
    p = _mini(instrument_pools={"rhythm": Pool(items=["drums"]),
                                "harmonic": Pool(items=["piano", "rhodes"])})
    assert POOL_ORDER == ("harmonic", "color", "rhythm", "rare")
    assert p.instrument_pool == ["piano", "rhodes", "drums"]


def test_unknown_pool_role_rejected():
    with pytest.raises(ValueError):
        _mini(instrument_pools={"lead": Pool(items=["a"])})


def test_pool_pick_range_validated():
    with pytest.raises(ValueError):
        Pool(items=["a"], pick_min=2, pick_max=1)
    with pytest.raises(ValueError):
        Pool(items=["a"], pick_max=2)            # 比池子还大
    with pytest.raises(ValueError):
        Pool(items=["a"], chance=0)


def test_exclusions_must_reference_pool_items():
    with pytest.raises(ValueError):
        _mini(instrument_pools={"harmonic": Pool(items=["a"])}, exclusions=[("a", "zzz")])


def test_bpm_typical_must_be_in_range_and_wins_default():
    with pytest.raises(ValueError):
        _mini(bpm_range=(80, 90), bpm_typical=120)
    assert _mini(bpm_range=(80, 100), bpm_typical=84).bpm_default() == 84
    assert _mini(bpm_range=(80, 100)).bpm_default() == 90      # 未设 typical → 中点


def test_render_skeleton_accepts_drawn_elements():
    s = PRESETS["hiphop.trap"].render_skeleton(
        instruments=["808 sub-bass", "bell melody"], textures=["dark"], era="2020s",
        vocal="male rapid-fire rap flow")
    assert "808 sub-bass, bell melody" in s and "dark" in s and "2020s" in s
    assert "male rapid-fire rap flow" in s


def test_migrated_hiphop_presets_keep_behavior():
    assert PRESETS["hiphop.trap"].bpm_default() == 140
    assert PRESETS["hiphop.boom_bap"].bpm_default() == 90
    assert "808 sub-bass" in PRESETS["hiphop.trap"].instrument_pool
