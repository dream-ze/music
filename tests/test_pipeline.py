import json
from src import pipeline
from src.spec import SAFE_DEFAULT_SPEC, SongSpec


def test_make_song_orchestrates(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline.planner.llm, "complete", lambda *a, **k: json.dumps(SAFE_DEFAULT_SPEC)
    )
    monkeypatch.setattr(
        pipeline.lyrics.llm, "complete", lambda *a, **k: "[Verse]\nx\n[Chorus]\ny"
    )

    captured = {}
    def fake_gen(structured_lyrics, spec, *, length, seed, out_path):
        captured["lyrics"] = structured_lyrics
        captured["length"] = length
        with open(out_path, "wb") as f:
            f.write(b"RIFF")
        return out_path
    monkeypatch.setattr(pipeline.song_gen, "generate_song", fake_gen)

    result = pipeline.make_song(
        "我的歌词", "女声 R&B", length="short", work_dir=str(tmp_path)
    )
    assert isinstance(result["spec"], SongSpec)
    assert "[Verse]" in result["structured_lyrics"]
    assert result["song"].endswith(".wav")
    assert captured["length"] == "short"
    assert "[Verse]" in captured["lyrics"]
