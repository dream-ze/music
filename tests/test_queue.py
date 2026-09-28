import json
import asyncio
from server import queue


class _FakeSpec:
    def model_dump_json(self):
        return "{}"


def test_run_generation_orchestrates(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.pipeline, "make_song",
        lambda *a, **k: {"song": str(tmp_path / "song.wav"),
                          "spec": _FakeSpec(), "structured_lyrics": "[Verse]\nx",
                          "llm_status": [], "degraded": False})
    monkeypatch.setattr(queue.storage, "wav_to_mp3", lambda w, m: m)
    monkeypatch.setattr(queue.storage, "probe_duration", lambda p: 200.0)
    monkeypatch.setattr(queue.storage, "upload_to_r2", lambda p, key: f"https://r2/{key}")
    saved = {}
    monkeypatch.setattr(queue.db, "insert_song", lambda s: saved.update(s))

    song = queue.run_generation("j1", {
        "lyrics": "词", "feeling": "女声", "length": "full",
        "seed": None, "instrumental": False, "overrides": {},
    }, "ze")
    assert song["mp3_url"] == f"https://r2/{song['id']}.mp3"
    assert song["duration_sec"] == 200.0
    assert saved["id"] == song["id"] and saved["created_by"] == "ze"


def test_enqueue_creates_queued_job(monkeypatch):
    jobs = {}
    monkeypatch.setattr(queue.db, "create_job",
        lambda job_id, **k: jobs.__setitem__(job_id, k))

    async def go():
        q = queue.JobQueue()
        jid = await q.enqueue({"lyrics": "x"}, "ze")
        return jid
    jid = asyncio.run(go())
    assert jobs[jid]["status"] == "queued"
    assert jobs[jid]["created_by"] == "ze"


def test_worker_marks_done(monkeypatch):
    monkeypatch.setattr(queue.db, "create_job", lambda *a, **k: None)
    updates = []
    monkeypatch.setattr(queue.db, "update_job",
        lambda job_id, **f: updates.append((job_id, f)))
    monkeypatch.setattr(queue, "run_generation",
        lambda job_id, payload, created_by: {"id": "s1"})

    async def go():
        q = queue.JobQueue()
        q.start()
        jid = await q.enqueue({"lyrics": "x"}, "ze")
        await asyncio.sleep(0.05)
        await q.stop()
        return jid
    jid = asyncio.run(go())
    statuses = [f.get("status") for _, f in updates]
    assert "running" in statuses and "done" in statuses


def test_run_generation_persists_llm_status(monkeypatch, tmp_path):
    """降级生成必须在库里留痕,否则前端无法把它跟正常出的歌区分开。"""
    events = [{"stage": "歌曲规划", "ok": False}, {"stage": "歌词整理", "ok": True}]
    monkeypatch.setattr(queue.pipeline, "make_song",
        lambda *a, **k: {"song": str(tmp_path / "song.wav"),
                          "spec": _FakeSpec(), "structured_lyrics": "[Verse]\nx",
                          "llm_status": events, "degraded": True})
    monkeypatch.setattr(queue.storage, "wav_to_mp3", lambda w, m: m)
    monkeypatch.setattr(queue.storage, "probe_duration", lambda p: 200.0)
    monkeypatch.setattr(queue.storage, "upload_to_r2", lambda p, key: f"https://r2/{key}")
    saved = {}
    monkeypatch.setattr(queue.db, "insert_song", lambda s: saved.update(s))

    song = queue.run_generation("j1", {
        "lyrics": "词", "feeling": "女声", "length": "full",
        "seed": None, "instrumental": False, "overrides": {},
    }, "ze")

    assert json.loads(saved["llm_status"]) == events
    assert json.loads(song["llm_status"]) == events


def _stub_io(monkeypatch, tmp_path, saved):
    monkeypatch.setattr(queue.pipeline, "make_song",
        lambda *a, **k: {"song": str(tmp_path / "song.wav"),
                          "spec": _FakeSpec(), "structured_lyrics": "[Verse]\nx",
                          "llm_status": [], "degraded": False})
    monkeypatch.setattr(queue.storage, "wav_to_mp3", lambda w, m: m)
    monkeypatch.setattr(queue.storage, "probe_duration", lambda p: 200.0)
    monkeypatch.setattr(queue.storage, "upload_to_r2", lambda p, key: f"https://r2/{key}")
    monkeypatch.setattr(queue.db, "insert_song", lambda s: saved.update(s))


def test_run_generation_uses_custom_title(monkeypatch, tmp_path):
    saved = {}
    _stub_io(monkeypatch, tmp_path, saved)
    song = queue.run_generation("j1", {
        "lyrics": "词", "feeling": "女声", "title": "  毕业的青春回忆 ",
    }, "ze")
    assert song["title"] == saved["title"] == "毕业的青春回忆"


def test_run_generation_blank_title_falls_back(monkeypatch, tmp_path):
    saved = {}
    _stub_io(monkeypatch, tmp_path, saved)
    song = queue.run_generation("j1", {
        "lyrics": "词", "feeling": "女声，R&B", "title": "   ",
    }, "ze")
    assert song["title"] == "女声，R&B"


def test_generate_request_trims_and_truncates_title():
    from server.models import GenerateRequest
    assert GenerateRequest(lyrics="x", title="  名字 ").title == "名字"
    assert GenerateRequest(lyrics="x", title="字" * 30).title == "字" * 20
    assert GenerateRequest(lyrics="x").title == ""


def test_enqueue_stores_title_and_feeling(monkeypatch):
    """作品库要在生成完之前就能显示歌名,所以提交时就得算好存进 jobs。"""
    jobs = {}
    monkeypatch.setattr(queue.db, "create_job",
        lambda job_id, **k: jobs.__setitem__(job_id, k))

    async def go():
        q = queue.JobQueue()
        a = await q.enqueue({"lyrics": "词", "feeling": "女声 hip hop", "title": " 冬日甜心 "}, "ze")
        b = await q.enqueue({"lyrics": "第一行\n第二行", "feeling": ""}, "ze")
        return a, b
    a, b = asyncio.run(go())
    assert jobs[a]["title"] == "冬日甜心" and jobs[a]["feeling"] == "女声 hip hop"
    assert jobs[b]["title"] == "第一行" and jobs[b]["feeling"] == ""
