import re
from urllib.parse import quote

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from server import db, models, inspirations, storage
from server.auth import require_passcode
from src.presets import PRESETS, UI_GENRES
from src.vocal_timbres import TIMBRES

router = APIRouter(prefix="/api")

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _content_disposition(title: str) -> str:
    """歌名基本都是中文,HTTP 头只能是 latin-1,原样塞进去会直接抛
    UnicodeEncodeError。按 RFC 5987 给一个 ASCII 兜底文件名 + UTF-8
    百分号编码的 filename*,新浏览器认 filename*,老的退回兜底名。"""
    name = _UNSAFE_FILENAME_CHARS.sub("_", (title or "未命名").strip())
    return f'attachment; filename="download.mp3"; filename*=UTF-8\'\'{quote(name)}.mp3'


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


@router.patch("/songs/{song_id}")
def rename_song(song_id: str, body: models.SongRename, who: str = Depends(require_passcode)):
    if not db.rename_song(song_id, body.title):
        raise HTTPException(404, "歌曲不存在")
    return {"title": body.title}


@router.get("/songs/{song_id}/download")
def download_song(song_id: str, who: str = Depends(require_passcode)):
    """下载这首歌的 mp3。走后端转一手,而不是前端直接 fetch R2 的公开地址:
    R2 桶没开 CORS,浏览器里的 fetch() 会被拦掉;我们自己的接口本来就对
    前端开着 CORS,顺便还能把 Content-Disposition 设成"强制下载",文件名
    也能用歌名,而不是一串 uuid.mp3。"""
    song = db.get_song(song_id)
    if not song or not song.get("mp3_url"):
        raise HTTPException(404, "歌曲不存在")
    r = requests.get(song["mp3_url"], timeout=30)
    r.raise_for_status()
    return Response(
        content=r.content,
        media_type="audio/mpeg",
        headers={"Content-Disposition": _content_disposition(song.get("title", ""))},
    )


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


_CREATIVITY_LABELS = [("pure", "纯正"), ("normal", "常规"), ("fusion", "融合")]


@router.get("/styles")
def get_styles():
    """曲风 / 音色 / 创意度的选项与中文名。前端据此渲染,避免两端数据不同步。"""
    return {
        "genres": [{"id": pid, "label": PRESETS[pid].label, "family": PRESETS[pid].family}
                   for pid in UI_GENRES],
        "timbres": [{"id": t.id, "label": t.label} for t in TIMBRES.values()],
        "creativity": [{"id": i, "label": l} for i, l in _CREATIVITY_LABELS],
    }
