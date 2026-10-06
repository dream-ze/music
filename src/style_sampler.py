# src/style_sampler.py
"""风格采样:在 planner 之前按 seed 抽出本次的曲风要素。

LLM 自己挑词会收敛到最常见的搭配(同一 preset 的 caption 几乎逐字相同);
这里用 seed 驱动的局部随机数抽取,保证可复现、遵守互斥、避开最近用过的。
"""
import random
from collections.abc import Sequence

from pydantic import BaseModel, Field, ValidationError

from src.presets import POOL_ORDER, Preset, get_preset

CREATIVITY_LEVELS = ("pure", "normal", "fusion")
MAX_INSTRUMENTS = 5
RECENT_WEIGHT = 0.3     # 最近用过的乐器/音色降权到这个比例
DEFAULT_TIMBRE = "clear"


class Locks(BaseModel):
    """用户在界面上锁定的维度:锁定即原样使用,不参与采样。"""
    moods: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    vocal_timbre: str = ""


class StyleDraw(BaseModel):
    preset_id: str
    instruments: list[str]
    textures: list[str]
    era: str
    moods: list[str]
    vocal_timbre: str
    vocal_gender: str
    bpm: int
    fusion_id: str | None = None
    seed: int


def parse_recent(items: list) -> list[StyleDraw]:
    """从库里读出的 style_draw 字典 → StyleDraw;老数据或坏数据直接跳过。"""
    out: list[StyleDraw] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        try:
            out.append(StyleDraw.model_validate(it))
        except ValidationError:
            continue
    return out


def _conflicts(item: str, chosen: list[str], exclusions) -> bool:
    return any((item == a and b in chosen) or (item == b and a in chosen)
               for a, b in exclusions)


def _pick(rng: random.Random, items: list[str], avoid: set[str]) -> str:
    weights = [RECENT_WEIGHT if i in avoid else 1.0 for i in items]
    return rng.choices(items, weights=weights, k=1)[0]


def _sample(rng: random.Random, pool: list[str], k: int) -> list[str]:
    return rng.sample(pool, min(k, len(pool)))


def _draw_instruments(rng, preset: Preset, creativity: str, avoid: set[str],
                      cap: int) -> list[str]:
    chosen: list[str] = []
    roles = ("harmonic", "rhythm") if creativity == "pure" else POOL_ORDER
    for role in roles:
        pool = preset.instrument_pools.get(role)
        if not pool:
            continue
        if creativity != "pure" and pool.chance < 1 and rng.random() >= pool.chance:
            continue
        k = max(pool.pick_min, 1) if creativity == "pure" else rng.randint(pool.pick_min,
                                                                           pool.pick_max)
        for _ in range(k):
            if len(chosen) >= cap:
                return chosen
            cands = [i for i in pool.items
                     if i not in chosen and not _conflicts(i, chosen, preset.exclusions)]
            if not cands:
                break
            chosen.append(_pick(rng, cands, avoid))
    return chosen


def sample_style(preset: Preset, *, seed: int, locks: Locks | None = None,
                 creativity: str = "normal",
                 recent: Sequence[StyleDraw] = ()) -> StyleDraw:
    if creativity not in CREATIVITY_LEVELS:
        raise ValueError(f"未知创意度: {creativity}")
    locks = locks or Locks()
    rng = random.Random(seed)
    pure = creativity == "pure"
    used_instruments = {i for d in recent for i in d.instruments}
    used_timbres = {d.vocal_timbre for d in recent}

    # 融合档给伙伴曲风留一个位置
    cap = MAX_INSTRUMENTS - (1 if creativity == "fusion" else 0)
    instruments = _draw_instruments(rng, preset, creativity, used_instruments, cap)

    fusion_id = None
    if creativity == "fusion" and preset.fusion_partners:
        fusion_id = rng.choice(preset.fusion_partners)
        color = get_preset(fusion_id).instrument_pools.get("color")
        # 伙伴的乐器也要过本曲风的互斥表(如 lofi 的 muted trumpet 与 jazz 的 flugelhorn)
        cands = [i for i in (color.items if color else [])
                 if i not in instruments and not _conflicts(i, instruments, preset.exclusions)]
        if cands:
            instruments.append(_pick(rng, cands, used_instruments))

    textures = _sample(rng, preset.texture_pool, 1 if pure else rng.randint(1, 2))
    if preset.era_pool:
        era = preset.era_pool[0] if pure else rng.choice(preset.era_pool)
    else:
        era = "modern"
    moods = (list(locks.moods) if locks.moods
             else _sample(rng, preset.mood_pool, 1 if pure else rng.randint(1, 2)))
    if locks.vocal_timbre:
        timbre = locks.vocal_timbre
    elif preset.vocal_timbres:
        timbre = _pick(rng, preset.vocal_timbres, used_timbres)
    else:
        timbre = DEFAULT_TIMBRE

    typical = preset.bpm_default()
    lo, hi = preset.bpm_range
    bpm = typical if pure else rng.randint(max(lo, typical - 8), min(hi, typical + 8))

    return StyleDraw(
        preset_id=preset.id, instruments=instruments, textures=textures, era=era,
        moods=moods, vocal_timbre=timbre,
        vocal_gender=locks.vocal_gender or preset.vocal_gender_default,
        bpm=bpm, fusion_id=fusion_id, seed=seed,
    )
