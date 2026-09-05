import asyncio
import uuid

from src import pipeline
from server import db, storage


def run_generation(job_id: str, payload: dict, created_by: str) -> dict:
    """阻塞:成曲 → MP3 → R2 → 写库。返回 song dict。在线程池里跑。"""
    result = pipeline.make_song(
        payload["lyrics"], payload["feeling"],
        length=payload.get("length", "full"),
        seed=payload.get("seed"),
        overrides=payload.get("overrides") or {},
    )
    song_id = uuid.uuid4().hex
    wav = result["song"]
    mp3 = wav.rsplit(".", 1)[0] + ".mp3"
    storage.wav_to_mp3(wav, mp3)
    duration = storage.probe_duration(mp3)
    url = storage.upload_to_r2(mp3, f"{song_id}.mp3")

    title = (payload["feeling"] or payload["lyrics"] or "未命名").strip().splitlines()[0][:20]
    song = {
        "id": song_id, "title": title,
        "lyrics": payload["lyrics"], "feeling": payload["feeling"],
        "spec_json": result["spec"].model_dump_json(),
        "structured_lyrics": result["structured_lyrics"],
        "seed": payload.get("seed"), "mp3_url": url, "duration_sec": duration,
        "instrumental": 1 if payload.get("instrumental") else 0,
        "created_by": created_by,
    }
    db.insert_song(song)
    return song


class JobQueue:
    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, payload: dict, created_by: str) -> str:
        job_id = uuid.uuid4().hex
        position = self._queue.qsize() + 1
        db.create_job(job_id, status="queued", position=position, created_by=created_by)
        await self._queue.put((job_id, payload, created_by))
        return job_id

    async def _worker(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            job_id, payload, created_by = await self._queue.get()
            try:
                db.update_job(job_id, status="running", position=0)
                song = await loop.run_in_executor(
                    None, run_generation, job_id, payload, created_by
                )
                db.update_job(job_id, status="done", song_id=song["id"])
            except Exception as e:  # noqa: BLE001 — 失败要落库让前端可见
                db.update_job(job_id, status="error", error=str(e)[:500])
            finally:
                self._queue.task_done()
