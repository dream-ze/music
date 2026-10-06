# tests/test_caption_bank.py
import random
from src.caption_bank import detect_gender, load_bank, pick_examples, tag_caption
from src.presets import UI_GENRES, get_preset
from src.textcheck import has_cjk


def test_tag_caption_uses_caption_keywords():
    assert "pop.city_pop" in tag_caption("A dreamy 80s City Pop song with slap bass")
    assert "jazz.lounge" in tag_caption("A swing jazz tune")
    assert tag_caption("A song about nothing") == []


def test_detect_gender():
    assert detect_gender("a breathy female vocal") == "female"
    assert detect_gender("a raspy male vocal") == "male"           # 不能被 female 误伤
    assert detect_gender("a male and female duet") == "mixed"
    assert detect_gender("an instrumental piece") == "none"


BANK = [
    {"id": "a", "caption": "city pop female A", "genres": ["pop.city_pop"], "gender": "female"},
    {"id": "b", "caption": "city pop female B", "genres": ["pop.city_pop"], "gender": "female"},
    {"id": "c", "caption": "city pop male C", "genres": ["pop.city_pop"], "gender": "male"},
]


def test_pick_examples_prefers_same_gender_then_widens():
    got = pick_examples("pop.city_pop", "male", random.Random(1), k=2, bank=BANK)
    assert got[0] == "city pop male C" and len(got) == 2


def test_pick_examples_is_deterministic():
    a = pick_examples("pop.city_pop", "female", random.Random(3), k=2, bank=BANK)
    b = pick_examples("pop.city_pop", "female", random.Random(3), k=2, bank=BANK)
    assert a == b


def test_pick_examples_falls_back_to_preset_examples():
    got = pick_examples("cn.guofeng", "female", random.Random(1), k=2, bank=BANK)
    assert got == get_preset("cn.guofeng").examples


def test_real_bank_loads_and_is_english():
    bank = load_bank()
    assert len(bank) >= 150
    assert all(not has_cjk(e["caption"]) for e in bank)
    covered = {g for e in bank for g in e["genres"]}
    assert len(covered & set(UI_GENRES)) >= 8      # 其余曲风回退 preset.examples
