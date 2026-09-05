from fastapi import APIRouter, Depends, HTTPException, Request

from server import db, models, inspirations
from server.auth import require_passcode

router = APIRouter(prefix="/api")


@router.post("/generate")
async def generate(req: models.GenerateRequest, request: Request,
                   who: str = Depends(require_passcode)):
    payload = req.model_dump()
    job_id = await request.app.state.queue.enqueue(payload, who)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, who: str = Depends(require_passcode)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    song = db.get_song(job["song_id"]) if job.get("song_id") else None
    return {"status": job["status"], "position": job.get("position"),
            "song": song, "error": job.get("error")}


@router.get("/songs")
def songs(q: str = "", favorite: bool = False, mine: str = "",
          limit: int = 50, offset: int = 0,
          who: str = Depends(require_passcode)):
    return {"songs": db.list_songs(q=q, favorite=favorite, mine=mine,
                                   limit=limit, offset=offset)}


@router.post("/songs/{song_id}/favorite")
def favorite(song_id: str, who: str = Depends(require_passcode)):
    if not db.get_song(song_id):
        raise HTTPException(404, "歌曲不存在")
    return {"favorite": db.toggle_favorite(song_id)}


@router.get("/inspirations")
def get_inspirations():
    return {"inspirations": inspirations.PRESETS}
