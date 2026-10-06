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


def test_inspirations_include_hiphop_with_preset():
    items = client.get("/api/inspirations").json()["inspirations"]
    assert all("preset" in it for it in items)
    hip = [it for it in items if it["preset"] == "hiphop.boom_bap"]
    assert len(hip) == 1
    assert "[Hook]" in hip[0]["lyrics"] and "hip hop" in hip[0]["feeling"].lower()


def test_active_jobs_endpoint(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "active.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.create_job("j1", status="running", position=0, created_by="demo",
                  title="冬日甜心", feeling="女声 hip hop")
    db.create_job("j2", status="done", position=0, created_by="demo", title="旧歌")
    r = client.get("/api/jobs/active")
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert [j["job_id"] for j in jobs] == ["j1"]
    assert jobs[0]["title"] == "冬日甜心" and jobs[0]["status"] == "running"


def test_generate_defaults_length_to_auto_and_rejects_unknown(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "len.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    captured = {}

    class FakeQ:
        async def enqueue(self, payload, created_by):
            captured.update(payload)
            db.create_job("jL", status="queued", position=1, created_by=created_by)
            return "jL"
    appmod.app.state.queue = FakeQ()

    r = client.post("/api/generate", json={"lyrics": "词", "feeling": "女声"})
    assert r.status_code == 200
    assert captured["length"] == "auto"

    r2 = client.post("/api/generate", json={"lyrics": "词", "feeling": "女声", "length": "slow"})
    assert r2.status_code == 422


def test_delete_song_removes_record_and_r2_file(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "del.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "旧歌", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})
    deleted_keys = []
    from server import routes
    monkeypatch.setattr(routes.storage, "delete_from_r2", lambda key: deleted_keys.append(key))

    r = client.delete("/api/songs/s1")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert deleted_keys == ["s1.mp3"]
    assert db.get_song("s1") is None

    r2 = client.delete("/api/songs/s1")
    assert r2.status_code == 404


def test_rename_song(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "rename.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "旧歌", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})

    r = client.patch("/api/songs/s1", json={"title": "  新名字  "})
    assert r.status_code == 200
    assert r.json() == {"title": "新名字"}
    assert db.get_song("s1")["title"] == "新名字"


def test_rename_song_rejects_blank_title(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "rename2.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "旧歌", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})
    r = client.patch("/api/songs/s1", json={"title": "   "})
    assert r.status_code == 422


def test_rename_unknown_song_404(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "rename3.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    r = client.patch("/api/songs/nope", json={"title": "新名字"})
    assert r.status_code == 404


def test_delete_song_ok_even_if_r2_delete_fails(monkeypatch, tmp_path):
    """R2 删失败不应挡住删记录,否则前端会看到删不掉的歌。"""
    from server import db, routes
    db.init_db(str(tmp_path / "del2.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s2", "title": "旧歌", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s2.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})

    def _boom(key):
        raise RuntimeError("R2 挂了")
    monkeypatch.setattr(routes.storage, "delete_from_r2", _boom)

    r = client.delete("/api/songs/s2")
    assert r.status_code == 200
    assert db.get_song("s2") is None


def test_category_crud_and_multi_membership(monkeypatch, tmp_path):
    """一首歌能同时在好几个分类里,跟网易云歌单一样;删分类不删歌。"""
    from server import db
    db.init_db(str(tmp_path / "catapi.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "旧歌", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})

    r = client.post("/api/categories", json={"name": "  民谣  "})
    assert r.status_code == 200
    folk_id = r.json()["id"]
    assert r.json()["name"] == "民谣"
    night_id = client.post("/api/categories", json={"name": "深夜"}).json()["id"]

    r = client.get("/api/categories")
    counts = {c["id"]: c["song_count"] for c in r.json()["categories"]}
    assert counts[folk_id] == 0

    # 加进两个分类,互不影响
    r = client.put(f"/api/songs/s1/categories/{folk_id}")
    assert r.status_code == 200
    assert set(r.json()["category_ids"]) == {folk_id}
    r = client.put(f"/api/songs/s1/categories/{night_id}")
    assert set(r.json()["category_ids"]) == {folk_id, night_id}
    assert set(db.get_song("s1")["category_ids"]) == {folk_id, night_id}

    r = client.get("/api/songs", params={"category": folk_id})
    assert [s["id"] for s in r.json()["songs"]] == ["s1"]
    r = client.get("/api/songs", params={"category": night_id})
    assert [s["id"] for s in r.json()["songs"]] == ["s1"]

    # 从一个分类移出,另一个不受影响
    r = client.delete(f"/api/songs/s1/categories/{folk_id}")
    assert r.status_code == 200
    assert r.json()["category_ids"] == [night_id]

    # 删分类不删歌,只清那一个分类的归属
    r = client.delete(f"/api/categories/{night_id}")
    assert r.status_code == 200
    assert db.get_song("s1") is not None
    assert db.get_song("s1")["category_ids"] == []
    r = client.delete(f"/api/categories/{night_id}")
    assert r.status_code == 404


def test_category_rejects_blank_name(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "catblank.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    r = client.post("/api/categories", json={"name": "   "})
    assert r.status_code == 422


def test_add_song_to_unknown_category_404(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "catunk.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "旧歌", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})
    r = client.put("/api/songs/s1/categories/nope")
    assert r.status_code == 404


def test_add_unknown_song_to_category_404(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "catunk2.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    cat_id = client.post("/api/categories", json={"name": "民谣"}).json()["id"]
    r = client.put(f"/api/songs/nope/categories/{cat_id}")
    assert r.status_code == 404


def test_download_song_proxies_r2_with_content_disposition(monkeypatch, tmp_path):
    """前端不能直接 fetch R2 的公开地址(桶没开 CORS),下载走后端转一手;
    顺便把文件名换成歌名而不是一串 uuid,还要能扛住中文文件名不炸(latin-1)。"""
    from server import db, routes
    db.init_db(str(tmp_path / "dl.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    db.insert_song({"id": "s1", "title": "测试 歌名", "lyrics": "x", "feeling": "x",
                    "spec_json": "{}", "structured_lyrics": "x", "seed": None,
                    "mp3_url": "https://r2/s1.mp3", "duration_sec": 45.0,
                    "instrumental": 0, "created_by": "demo"})

    class FakeResp:
        content = b"fake mp3 bytes"
        def raise_for_status(self):
            pass
    captured = {}
    def fake_get(url, timeout=None):
        captured["url"] = url
        return FakeResp()
    monkeypatch.setattr(routes.requests, "get", fake_get)

    r = client.get("/api/songs/s1/download")
    assert r.status_code == 200
    assert r.content == b"fake mp3 bytes"
    assert r.headers["content-type"] == "audio/mpeg"
    assert captured["url"] == "https://r2/s1.mp3"
    disposition = r.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "filename*=UTF-8''" in disposition


def test_download_song_unknown_404(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "dlunk.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    r = client.get("/api/songs/nope/download")
    assert r.status_code == 404


def test_generate_accepts_timbre_and_creativity(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "t1.db")
    r = client.post("/api/generate", json=_body(overrides={
        "preset": "pop.city_pop", "vocal_timbre": "breathy", "creativity": "fusion"}))
    assert r.status_code == 200
    o = captured["overrides"]
    assert (o["preset"], o["vocal_timbre"], o["creativity"]) == \
        ("pop.city_pop", "breathy", "fusion")


def test_generate_defaults_creativity_to_normal(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "t2.db")
    client.post("/api/generate", json=_body())
    assert captured["overrides"]["creativity"] == "normal"
    assert captured["overrides"]["vocal_timbre"] == ""


def test_generate_rejects_unknown_timbre_or_creativity(monkeypatch, tmp_path):
    _with_fake_queue(monkeypatch, tmp_path, "t3.db")
    assert client.post("/api/generate",
                       json=_body(overrides={"vocal_timbre": "robot"})).status_code == 422
    assert client.post("/api/generate",
                       json=_body(overrides={"creativity": "wild"})).status_code == 422


def test_styles_endpoint():
    body = client.get("/api/styles").json()
    ids = [g["id"] for g in body["genres"]]
    assert len(ids) == 14 and ids[0] == "pop.ballad" and "generic" not in ids
    assert {"id", "label", "family"} <= set(body["genres"][0])
    assert [t["id"] for t in body["timbres"]][:2] == ["clear", "breathy"]
    assert [c["id"] for c in body["creativity"]] == ["pure", "normal", "fusion"]


def test_active_jobs_include_stage_progress_and_eta(monkeypatch, tmp_path):
    from server import db
    _with_fake_queue(monkeypatch, tmp_path, "eta.db")
    db.create_job("r1", status="running", position=0, created_by="ze")
    db.update_job("r1", stage="音频合成", progress=0.5, started_at=db._now())
    db.create_job("q1", status="queued", position=1, created_by="ze")
    jobs = {j["job_id"]: j for j in client.get("/api/jobs/active").json()["jobs"]}
    assert jobs["r1"]["stage"] == "音频合成" and jobs["r1"]["progress"] == 0.5
    assert jobs["r1"]["eta_seconds"] > 0 and jobs["q1"]["eta_seconds"] > jobs["r1"]["eta_seconds"]
    one = client.get("/api/jobs/q1").json()
    assert one["eta_seconds"] == jobs["q1"]["eta_seconds"] and "stage" in one


def test_generate_count_two_enqueues_a_and_b(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "c2.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    payloads = []

    class FakeQ:
        async def enqueue(self, payload, created_by):
            payloads.append(payload)
            return f"j{len(payloads)}"
    appmod.app.state.queue = FakeQ()
    r = client.post("/api/generate", json=_body(title="冬天的一首很长很长很长很长的歌名", count=2))
    assert r.status_code == 200
    assert r.json() == {"job_id": "j1", "job_ids": ["j1", "j2"]}
    titles = [p["title"] for p in payloads]
    assert titles[0].endswith(" · A") and titles[1].endswith(" · B")
    assert all(len(t) <= 20 for t in titles)


def test_generate_count_defaults_to_one_and_rejects_three(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "c1.db")
    r = client.post("/api/generate", json=_body())
    assert r.json()["job_ids"] == ["jP"] and captured["title"] == ""
    assert client.post("/api/generate", json=_body(count=3)).status_code == 422


def test_generate_count_two_with_fixed_seed_gets_distinct_seeds(monkeypatch, tmp_path):
    from server import db
    db.init_db(str(tmp_path / "c3.db"))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    seeds = []

    class FakeQ:
        async def enqueue(self, payload, created_by):
            seeds.append(payload["seed"])
            return "j"
    appmod.app.state.queue = FakeQ()
    client.post("/api/generate", json=_body(seed=7, count=2))
    assert seeds == [7, 8]
