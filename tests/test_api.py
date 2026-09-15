from fastapi.testclient import TestClient
from server.app import app
import server.app as appmod

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_generate_enqueues_and_job_status(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "api.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")

    # 用假队列替换,避免真跑 worker
    class FakeQ:
        async def enqueue(self, payload, created_by):
            db.create_job("jX", status="queued", position=1, created_by=created_by)
            return "jX"
    appmod.app.state.queue = FakeQ()

    r = client.post("/api/generate", json={
        "lyrics": "词", "feeling": "女声 R&B", "length": "full",
        "seed": None, "instrumental": False, "overrides": {},
    })
    assert r.status_code == 200
    jid = r.json()["job_id"]
    assert jid == "jX"

    s = client.get(f"/api/jobs/{jid}")
    assert s.status_code == 200
    assert s.json()["status"] == "queued"


def test_songs_list_and_favorite(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "api2.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "夏夜", "lyrics": "", "feeling": "",
                    "spec_json": "{}", "structured_lyrics": "", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 200.0,
                    "instrumental": 0, "created_by": "ze"})
    r = client.get("/api/songs")
    assert [s["id"] for s in r.json()["songs"]] == ["s1"]
    f = client.post("/api/songs/s1/favorite")
    assert f.json()["favorite"] is True


def test_generate_requires_passcode(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "api3.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "sesame")
    r = client.post("/api/generate", json={
        "lyrics": "词", "feeling": "x", "length": "full",
        "seed": None, "instrumental": False, "overrides": {}})
    assert r.status_code == 401


def test_inspirations():
    r = client.get("/api/inspirations")
    assert len(r.json()["inspirations"]) >= 3


def _with_fake_queue(monkeypatch, tmp_path, name):
    from server import db
    db.init_db(str(tmp_path / name))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    captured = {}

    class FakeQ:
        async def enqueue(self, payload, created_by):
            captured.update(payload)
            db.create_job("jP", status="queued", position=1, created_by=created_by)
            return "jP"
    appmod.app.state.queue = FakeQ()
    return captured


def _body(**over):
    base = {"lyrics": "词", "feeling": "说唱", "length": "short", "seed": None,
            "instrumental": False, "overrides": {}}
    base.update(over)
    return base


def test_generate_accepts_known_preset_and_forwards_it(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "p1.db")
    r = client.post("/api/generate", json=_body(overrides={"preset": "hiphop.trap"}))
    assert r.status_code == 200
    assert captured["overrides"]["preset"] == "hiphop.trap"


def test_generate_rejects_unknown_preset_with_422(monkeypatch, tmp_path):
    _with_fake_queue(monkeypatch, tmp_path, "p2.db")
    r = client.post("/api/generate", json=_body(overrides={"preset": "hiphop.nope"}))
    assert r.status_code == 422


def test_generate_rejects_cjk_genre_or_mood_with_422(monkeypatch, tmp_path):
    _with_fake_queue(monkeypatch, tmp_path, "p3.db")
    assert client.post("/api/generate", json=_body(overrides={"genre": ["流行"]})).status_code == 422
    assert client.post("/api/generate", json=_body(overrides={"mood": ["温柔"]})).status_code == 422
    assert client.post("/api/generate", json=_body(overrides={"genre": ["pop"], "mood": ["gentle"]})).status_code == 200
