import os
import secrets

import config
from src import planner, lyrics, song_gen
from src.style_sampler import Locks, parse_recent, resolve_genre, sample_style


def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None,
              overrides: dict | None = None,
              llm_options: dict | None = None,
              recent: list[dict] | None = None,
              instrumental: bool = False) -> dict:
    """识别曲风 → 采样要素 → 规划 caption → 整理歌词 → 出歌。

    recent:同一用户最近几首的 style_draw(新 → 旧),用于避开刚用过的曲风/乐器/音色。
    """
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    overrides = overrides or {}

    # 采样器与 DiT 共用同一个 seed;调用方没给就在这里生成,随结果返回以便落库复现。
    if seed is None:
        seed = secrets.randbelow(2**31)

    # 调用方没指定供应商时用配置值(而不是 llm.complete 签名里的默认值)。
    llm_options = {"provider": config.LLM_PROVIDER, **(llm_options or {})}
    recent_draws = parse_recent(recent or [])

    llm_status: list[dict] = []
    # 旧客户端可能仍发 genre tag:并入识别文本。用户选择一律在采样前作为锁定项进入,
    # 不再在 planner 之后覆盖 spec —— caption 写好后再改 genre 对 DiT 无效。
    feeling_text = " ".join([style_desc or "", *(overrides.get("genre") or [])]).strip()
    preset = resolve_genre(
        overrides.get("preset"), feeling_text, seed=seed,
        recent_ids=[d.preset_id for d in recent_draws],
        llm_options=llm_options, status_events=llm_status,
    )
    draw = sample_style(
        preset, seed=seed,
        locks=Locks(moods=overrides.get("mood") or [],
                    vocal_gender=overrides.get("vocal_gender") or "",
                    vocal_timbre=overrides.get("vocal_timbre") or ""),
        creativity=overrides.get("creativity") or "normal",
        recent=recent_draws,
    )
    if instrumental:
        # 纯音乐:人声相关的锁定与采样都不适用,换成伪音色让 planner 写 no vocals
        draw = draw.model_copy(update={"vocal_timbre": "instrumental", "vocal_gender": ""})
    spec = planner.plan_song(
        style_desc, lyrics_hint=raw_lyrics[:80], preset=preset, draw=draw,
        llm_options=llm_options, status_events=llm_status,
    )
    if overrides.get("language"):
        spec = spec.__class__(**{**spec.model_dump(), "language": overrides["language"]})
    if instrumental:
        spec = spec.model_copy(update={"instrumental": True})
        structured = "[Instrumental]"          # 不调断行:没有要唱的词
    else:
        structured = lyrics.structure_lyrics(
            raw_lyrics, spec, preset=preset, llm_options=llm_options, status_events=llm_status
        )
    song_path = os.path.join(out_dir, "song.wav")
    song_path = song_gen.generate_song(
        structured, spec, length=length, seed=seed, out_path=song_path
    )
    return {
        "spec": spec,
        "structured_lyrics": structured,
        "song": song_path,
        "preset_id": preset.id,
        "seed": seed,
        "style_draw": draw,
        "llm_status": llm_status,
        # 任一阶段回退即为降级生成 —— 由事件的 ok 位判定,不靠文案匹配。
        "degraded": any(not e["ok"] for e in llm_status),
    }
