from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from server import db
from server.queue import JobQueue
from server.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.fail_orphaned_jobs()  # 清理上次重启残留的 queued/running 任务
    q = JobQueue()
    q.start()
    app.state.queue = q
    try:
        yield
    finally:
        await q.stop()


app = FastAPI(title="ze music API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(router)
