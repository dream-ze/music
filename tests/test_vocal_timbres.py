# tests/test_vocal_timbres.py
import pytest
from src.textcheck import has_cjk
from src.vocal_timbres import TIMBRES, get_timbre

EXPECTED = ["clear", "breathy", "raspy", "deep", "powerful", "falsetto",
            "soft_whisper", "theatrical", "rap_rapid", "rap_laidback", "choir"]


def test_registry_order_and_ids():
    assert list(TIMBRES) == EXPECTED


@pytest.mark.parametrize("tid", EXPECTED)
def test_caption_is_english_and_hits_own_keywords(tid):
    t = TIMBRES[tid]
    assert has_cjk(t.label)
    assert not has_cjk(t.caption) and not any(has_cjk(k) for k in t.keywords)
    assert any(k in t.caption.lower() for k in t.keywords), t.caption


@pytest.mark.parametrize("tid", EXPECTED)
def test_section_tags_only_for_verse_or_chorus(tid):
    assert set(TIMBRES[tid].section_tags) <= {"Verse", "Chorus"}
    assert not any(has_cjk(v) for v in TIMBRES[tid].section_tags.values())


def test_get_timbre():
    assert get_timbre("") is None
    assert get_timbre("breathy").label == "气声"
    with pytest.raises(ValueError):
        get_timbre("robot")
