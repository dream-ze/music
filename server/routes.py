from fastapi import APIRouter, Depends, HTTPException, Request

from server import db, models, inspirations, storage
from server.auth import require_passcode

router = APIRouter(prefix="/api")


@router.post("/generate")
async def generate(req: models.GenerateRequest, request: Request,
                   who: str = Depends(require_passcode)):
    payload = req.model_dump()
    job_id = await request.app.state.queue.enqueue(payload, who)
    return {"job_id": job_id}


@router.get("/jobs/active")
def active_jobs(who: str = Depends(require_passcode)):
    # 必须排在 /jobs/{job_id} 前面,否则 "active" 会被当成 job_id
    return {"jobs": db.list_active_jobs()}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, who: str = Depends(require_passcode)):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    song = db.get_song(job["song_id"]) if job.get("song_id") else None
    return {"status": job["status"], "position": job.get("position"),
            "song": song, "error": job.get("error")}


@router.get("/songs")
def songs(q: str = "", favorite: bool = False, mine: str = "", category: str = "",
          limit: int = 50, offset: int = 0,
          who: str = Depends(require_passcode)):
    return {"songs": db.list_songs(q=q, favorite=favorite, mine=mine, category=category,
                                   limit=limit, offset=offset)}


@router.delete("/songs/{song_id}")
def delete_song(song_id: str, who: str = Depends(require_passcode)):
    song = db.get_song(song_id)
    if not song:
        raise HTTPException(404, "歌曲不存在")
    if song.get("mp3_url"):
        # R2 删失败只记日志、照样删记录:一个多余的文件代价很小,
        # 但"删不掉、一直挂在库里"的歌体验更差。
        key = song["mp3_url"].rsplit("/", 1)[-1]
        try:
            storage.delete_from_r2(key)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("R2 删除失败: %s", key, exc_info=True)
    db.delete_song(song_id)
    return {"deleted": True}


@router.post("/songs/{song_id}/favorite")
def favorite(song_id: str, who: str = Depends(require_passcode)):
    if not db.get_song(song_id):
        raise HTTPException(404, "歌曲不存在")
    return {"favorite": db.toggle_favorite(song_id)}


@router.put("/songs/{song_id}/categories/{category_id}")
def add_to_category(song_id: str, category_id: str, who: str = Depends(require_passcode)):
    """把歌加进一个分类;一首歌能同时在好几个分类里,这里只加不换。"""
    if not db.get_song(song_id):
        raise HTTPException(404, "歌曲不存在")
    if not db.get_category(category_id):
        raise HTTPException(404, "分类不存在")
    db.add_song_to_category(song_id, category_id)
    return {"category_ids": db.get_song_category_ids(song_id)}


@router.delete("/songs/{song_id}/categories/{category_id}")
def remove_from_category(song_id: str, category_id: str, who: str = Depends(require_passcode)):
    if not db.get_song(song_id):
        raise HTTPException(404, "歌曲不存在")
    db.remove_song_from_category(song_id, category_id)
    return {"category_ids": db.get_song_category_ids(song_id)}


@router.get("/categories")
def categories(who: str = Depends(require_passcode)):
    return {"categories": db.list_categories()}


@router.post("/categories")
def create_category(body: models.CategoryCreate, who: str = Depends(require_passcode)):
    return db.create_category(body.name, who)


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, who: str = Depends(require_passcode)):
    if not db.delete_category(category_id):
        raise HTTPException(404, "分类不存在")
    return {"deleted": True}


@router.get("/inspirations")
def get_inspirations():
    return {"inspirations": inspirations.PRESETS}
