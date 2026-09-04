import os
import config
from src import planner, lyrics, song_gen


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

    llm_status: list[str] = []
    spec = planner.plan_song(
        style_desc, lyrics_hint=raw_lyrics[:80],
        llm_options=llm_options, status_events=llm_status,
    )
    if overrides:
        spec = _apply_overrides(spec, overrides)
    structured = lyrics.structure_lyrics(
        raw_lyrics, spec, llm_options=llm_options, status_events=llm_status
    )
    song_path = os.path.join(out_dir, "song.wav")
    song_path = song_gen.generate_song(
        structured, spec, length=length, seed=seed, out_path=song_path
    )
    return {
        "spec": spec,
        "structured_lyrics": structured,
        "song": song_path,
        "llm_status": llm_status,
    }
