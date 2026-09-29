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


def test_delete_from_r2_calls_delete_object(monkeypatch):
    deleted = {}
    class FakeClient:
        def delete_object(self, Bucket=None, Key=None):
            deleted.update(bucket=Bucket, key=Key)
    monkeypatch.setattr(storage, "_r2_client", lambda: FakeClient())
    monkeypatch.setattr(storage.config, "R2_BUCKET", "songs")
    storage.delete_from_r2("s1.mp3")
    assert deleted == {"bucket": "songs", "key": "s1.mp3"}


def test_r2_client_created_once_and_reused(monkeypatch):
    """每次删除/上传都新建连接的话,每次都要重新走一遍 TCP+TLS 握手,
    实测能让单次删除慢上 1~7 秒。客户端应该在进程里只建一次、之后复用。"""
    monkeypatch.setattr(storage, "_client", None)
    calls = []
    class FakeBoto3:
        @staticmethod
        def client(*a, **k):
            calls.append(1)
            return object()
    import sys
    monkeypatch.setitem(sys.modules, "boto3", FakeBoto3())
    monkeypatch.setattr(storage.config, "R2_ACCOUNT_ID", "acc")
    monkeypatch.setattr(storage.config, "R2_ACCESS_KEY", "key")
    monkeypatch.setattr(storage.config, "R2_SECRET_KEY", "secret")

    first = storage._r2_client()
    second = storage._r2_client()
    assert first is second
    assert len(calls) == 1
