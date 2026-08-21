import os
import config
from src import planner, lyrics, song_gen


def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None) -> dict:
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    spec = planner.plan_song(style_desc, lyrics_hint=raw_lyrics[:80])
    structured = lyrics.structure_lyrics(raw_lyrics, spec)
    song_path = os.path.join(out_dir, "song.wav")
    song_path = song_gen.generate_song(
        structured, spec, length=length, seed=seed, out_path=song_path
    )
    return {"spec": spec, "structured_lyrics": structured, "song": song_path}
