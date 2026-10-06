# src/style_sampler.py
"""风格采样:在 planner 之前按 seed 抽出本次的曲风要素。

LLM 自己挑词会收敛到最常见的搭配(同一 preset 的 caption 几乎逐字相同);
这里用 seed 驱动的局部随机数抽取,保证可复现、遵守互斥、避开最近用过的。
"""
import logging
import random
from collections.abc import Sequence

from pydantic import BaseModel, Field, ValidationError

from src import llm
from src.presets import POOL_ORDER, PRESETS, UI_GENRES, Preset, get_preset

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


_DETECT_SYSTEM = "你是曲风分类器。只输出一个曲风 id,不要任何解释。"
_RECENT_AVOID = 3


def detect_by_keywords(text: str) -> str | None:
    """按命中关键词的字符长度之和打分:"city pop" 同时命中 pop 时,长词胜出。"""
    t = (text or "").lower()
    best, best_score = None, 0
    for pid in UI_GENRES:
        score = sum(len(k) for k in PRESETS[pid].keywords if k.lower() in t)
        if score > best_score:
            best, best_score = pid, score
    return best


def _detect_by_llm(text: str, llm_options: dict | None) -> str | None:
    menu = "\n".join(f"{pid}: {PRESETS[pid].label}" for pid in UI_GENRES)
    prompt = f"歌曲感觉描述:{text}\n可选曲风(id: 名称):\n{menu}\n只输出最合适的一个 id。"
    out = llm.complete(prompt, system=_DETECT_SYSTEM, **(llm_options or {})) or ""
    for pid in UI_GENRES:
        if pid in out:
            return pid
    return None


def _emit(events: list[dict] | None, ok: bool, source: str, reason: str | None = None):
    if events is None:
        return
    ev: dict = {"stage": "曲风识别", "ok": ok, "source": source}
    if not ok:
        ev["reason"] = reason
    events.append(ev)


def resolve_genre(preset_id: str | None, feeling: str, *, seed: int,
                  recent_ids: Sequence[str] = (), llm_options: dict | None = None,
                  status_events: list[dict] | None = None) -> Preset:
    """UI 选择 > 感觉关键词 > LLM 识别 > 随机(避开最近 3 首)。未知 UI id 抛 ValueError。"""
    if preset_id:
        preset = get_preset(preset_id)
        _emit(status_events, True, "ui")
        return preset

    pid = detect_by_keywords(feeling)
    if pid:
        _emit(status_events, True, "keyword")
        return PRESETS[pid]

    reason = None
    if (feeling or "").strip():
        try:
            pid = _detect_by_llm(feeling, llm_options)
        except Exception as e:  # noqa: BLE001 — 事件里不带异常原文(可能含 key)
            logging.warning("genre detection LLM failed, picking random: %s", type(e).__name__)
            reason = "llm_error"
        else:
            if pid:
                _emit(status_events, True, "llm")
                return PRESETS[pid]
            reason = "unknown_genre"

    avoid = set(list(recent_ids)[:_RECENT_AVOID])
    pool = [p for p in UI_GENRES if p not in avoid] or list(UI_GENRES)
    pid = random.Random(seed).choice(pool)
    _emit(status_events, reason is None, "random", reason)
    return PRESETS[pid]
