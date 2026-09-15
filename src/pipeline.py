import os
import config
from src import planner, lyrics, song_gen
from src.presets import get_preset


def _apply_overrides(spec, overrides: dict):
    """用非空 override 字段覆盖 SongSpec;返回新的 SongSpec。"""
    data = spec.model_dump()
    if overrides.get("genre"):
        data["genre"] = overrides["genre"]
    if overrides.get("mood"):
        data["mood"] = overrides["mood"]
    if overrides.get("language"):
        data["language"] = overrides["language"]
    if overrides.get("vocal_gender"):
        data["vocal"]["gender"] = overrides["vocal_gender"]
    return spec.__class__(**data)


def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None,
              overrides: dict | None = None,
              llm_options: dict | None = None) -> dict:
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    overrides = overrides or {}

    # 风格预设只由 UI 选择;未选 → generic。未知 id 在 API 层已被 422 拦下,这里抛错兜底。
    preset = get_preset(overrides.get("preset"))

    # 调用方没指定供应商时用配置值(而不是 llm.complete 签名里的默认值)。
    llm_options = {"provider": config.LLM_PROVIDER, **(llm_options or {})}

    llm_status: list[dict] = []
    spec = planner.plan_song(
        style_desc, lyrics_hint=raw_lyrics[:80], preset=preset,
        llm_options=llm_options, status_events=llm_status,
    )
    if overrides:
        spec = _apply_overrides(spec, overrides)
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
        "llm_status": llm_status,
        # 任一阶段回退即为降级生成 —— 由事件的 ok 位判定,不靠文案匹配。
        "degraded": any(not e["ok"] for e in llm_status),
    }
