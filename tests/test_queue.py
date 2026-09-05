import asyncio
from server import queue


class _FakeSpec:
    def model_dump_json(self):
        return "{}"


def test_run_generation_orchestrates(monkeypatch, tmp_path):
    monkeypatch.setattr(queue.pipeline, "make_song",
        lambda *a, **k: {"song": str(tmp_path / "song.wav"),
                          "spec": _FakeSpec(), "structured_lyrics": "[Verse]\nx"})
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
