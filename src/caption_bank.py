# src/caption_bank.py
"""官方 caption 示例库:按曲风检索 2–3 条,给 planner 当句式与维度参考。

数据由 scripts/build_caption_bank.py 从 ACE-Step-1.5 的 examples/text2music(MIT)
生成并入库,运行时不依赖 ACE-Step 目录。
"""
import json
import os
import random
import re
from functools import lru_cache

from src.presets import PRESETS, UI_GENRES, get_preset

BANK_PATH = os.path.join(os.path.dirname(__file__), "data", "caption_bank.json")

_FEMALE = re.compile(r"\b(female|woman|women|girl)\b")
_MALE = re.compile(r"\b(male|man|men|boy)\b")


def tag_caption(caption: str) -> list[str]:
    c = caption.lower()
    return [pid for pid in UI_GENRES
            if any(k in c for k in PRESETS[pid].caption_keywords)]


def detect_gender(caption: str) -> str:
    c = caption.lower()
    f, m = bool(_FEMALE.search(c)), bool(_MALE.search(c))
    if f and m:
        return "mixed"
    return "female" if f else "male" if m else "none"


@lru_cache(maxsize=4)
def load_bank(path: str = BANK_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["entries"]


def pick_examples(preset_id: str, gender: str, rng: random.Random, k: int = 2,
                  bank: list[dict] | None = None) -> list[str]:
    bank = load_bank() if bank is None else bank
    same = [e for e in bank if preset_id in e["genres"]]
    exact = [e for e in same if e["gender"] == gender]
    chosen = rng.sample(exact, min(k, len(exact)))
    rest = [e for e in same if e not in chosen]
    if len(chosen) < k and rest:
        chosen += rng.sample(rest, min(k - len(chosen), len(rest)))
    return [e["caption"] for e in chosen] or list(get_preset(preset_id).examples)
