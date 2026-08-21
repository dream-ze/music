from src.song_gen import build_acestep_params
from src.spec import safe_spec


def test_length_short_maps_to_short_duration():
    p = build_acestep_params(safe_spec(), length="short")
    assert p["duration"] == 45


def test_length_full_maps_to_full_duration():
    p = build_acestep_params(safe_spec(), length="full")
    assert p["duration"] == 210


def test_prompt_contains_genre_and_instrument():
    spec = safe_spec()  # genre=[mandopop], instrument=[piano, soft drums]
    p = build_acestep_params(spec)
    assert "mandopop" in p["prompt"]
    assert "piano" in p["prompt"]


def test_seed_passthrough():
    p = build_acestep_params(safe_spec(), seed=123)
    assert p["seed"] == 123
