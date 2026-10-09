import pytest
from fastapi.testclient import TestClient

import config
from server import db, storage
from server.app import app


def test_local_save_stream_download_delete(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AUDIO_STORAGE", "local", raising=False)
    monkeypatch.setattr(config, "LOCAL_AUDIO_DIR", str(tmp_path / "audio"), raising=False)
    monkeypatch.setattr(config, "APP_PASSCODE", "test")
    db.init_db(str(tmp_path / "test.db"))
    source = tmp_path / "source.mp3"
    source.write_bytes(b"0123456789")
    key = "a" * 32 + ".mp3"
    url = storage.save_audio(str(source), key)
    assert url == f"/api/media/{key}"
    db.insert_song({"id": "local", "title": "本地歌曲", "mp3_url": url})
    client = TestClient(app)
    # Like public R2 URLs, opaque media URLs support audio tags and byte ranges.
    response = client.get(url, headers={"Range": "bytes=2-5"})
    assert response.status_code == 206
    assert response.content == b"2345"
    assert client.get("/api/songs/local/download").status_code == 401
    response = client.get("/api/songs/local/download", headers={"X-Passcode": "test"})
    assert response.status_code == 200 and response.content == source.read_bytes()
    assert client.get("/api/media/..%5Csecret.mp3").status_code in (400, 404)
    assert client.delete("/api/songs/local", headers={"X-Passcode": "test"}).status_code == 200
    assert client.get(url).status_code == 404
    assert source.exists()


def test_storage_auto_and_incomplete_r2(monkeypatch):
    monkeypatch.setattr(config, "AUDIO_STORAGE", "auto", raising=False)
    fields = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET", "R2_PUBLIC_BASE"]
    for field in fields:
        monkeypatch.setattr(config, field, "")
    assert storage.storage_backend() == "local"
    monkeypatch.setattr(config, "R2_BUCKET", "partial")
    with pytest.raises(ValueError, match="R2"):
        storage.storage_backend()
    for field in fields:
        monkeypatch.setattr(config, field, "configured")
    assert storage.storage_backend() == "r2"


def test_r2_save_still_uses_upload(monkeypatch):
    monkeypatch.setattr(config, "AUDIO_STORAGE", "r2", raising=False)
    for field in ["R2_ACCOUNT_ID", "R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_BUCKET", "R2_PUBLIC_BASE"]:
        monkeypatch.setattr(config, field, "configured")
    monkeypatch.setattr(storage, "upload_to_r2", lambda p, k: f"https://cdn/{k}")
    assert storage.save_audio("song.mp3", "a.mp3") == "https://cdn/a.mp3"
