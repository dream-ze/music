import subprocess
from server import storage


def test_wav_to_mp3_calls_ffmpeg(monkeypatch):
    called = {}
    def fake_run(cmd, **kw):
        called["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(storage.subprocess, "run", fake_run)
    out = storage.wav_to_mp3("in.wav", "out.mp3")
    assert out == "out.mp3"
    assert "ffmpeg" in called["cmd"][0]
    assert "in.wav" in called["cmd"] and "out.mp3" in called["cmd"]


def test_wav_to_mp3_raises_on_failure(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stderr=b"boom")
    monkeypatch.setattr(storage.subprocess, "run", fake_run)
    try:
        storage.wav_to_mp3("in.wav", "out.mp3")
        assert False, "应抛异常"
    except RuntimeError as e:
        assert "ffmpeg" in str(e)


def test_upload_to_r2_returns_public_url(monkeypatch):
    uploaded = {}
    class FakeClient:
        def upload_file(self, local, bucket, key, ExtraArgs=None):
            uploaded.update(local=local, bucket=bucket, key=key)
    monkeypatch.setattr(storage, "_r2_client", lambda: FakeClient())
    monkeypatch.setattr(storage.config, "R2_BUCKET", "songs")
    monkeypatch.setattr(storage.config, "R2_PUBLIC_BASE", "https://cdn.example")
    url = storage.upload_to_r2("out.mp3", "s1.mp3")
    assert url == "https://cdn.example/s1.mp3"
    assert uploaded["key"] == "s1.mp3" and uploaded["bucket"] == "songs"
