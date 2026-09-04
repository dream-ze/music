# ze music 后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有 ACE-Step 成曲引擎(`src/`)包成一个 FastAPI 服务:异步任务队列(单 GPU 串行)、WAV→MP3、R2 上传、SQLite 元数据、共享口令认证,给 Next.js 前端提供 API。

**Architecture:** FastAPI app + 进程内单 worker 的 `asyncio` 队列保护单 GPU;阻塞的 `make_song()` 丢到线程池执行;任务与歌曲元数据落 SQLite;音频转 MP3 后传 Cloudflare R2,返回公网 URL。现有 `src/` 只改一处(`pipeline.make_song` 增加 `overrides`)。

**Tech Stack:** Python 3.11、FastAPI、uvicorn、sqlite3(stdlib)、boto3(R2/S3 兼容)、ffmpeg(系统二进制,subprocess 调用)、pytest。

**Spec:** `docs/superpowers/specs/2026-09-04-ze-music-web-app-design.md`

## Global Constraints

- 现有 `src/` 引擎核心逻辑不改,唯一例外:`src/pipeline.py` 的 `make_song` 增加可选 `overrides` 参数。
- 现有测试(35 passed / 1 skipped)必须保持通过。
- 所有外部依赖(R2、ffmpeg、GPU 成曲)在测试中必须 mock;不得在单测里真连 R2 或跑 GPU。
- 新代码放 `server/` 包;配置项一律走环境变量,在 `config.py` 声明并给安全默认。
- SQLite 采用「每次操作开一个新连接」,以保证 API 事件循环线程与队列 worker 线程池线程都能安全访问。
- LLM key 由服务器环境变量提供(`src/llm.py` 已支持 env fallback),API 不接收用户 key。

---

## 文件结构

```
server/
  __init__.py        # 空
  app.py             # FastAPI app、lifespan(启停队列)、CORS、路由挂载
  models.py          # Pydantic 请求/响应模型
  db.py              # SQLite: 建表 + songs/jobs 读写(每次开新连接)
  storage.py         # wav_to_mp3(ffmpeg) + upload_to_r2(boto3)
  queue.py           # JobQueue: asyncio 队列 + 单 worker + 生成编排
  auth.py            # require_passcode 依赖(X-Passcode header)
  routes.py          # 各 API 端点处理函数
  inspirations.py    # 静态灵感示例数据
config.py            # 修改: 加 R2 / 口令 / CORS / DB_PATH 配置
src/pipeline.py      # 修改: make_song 加 overrides
requirements.txt     # 加 fastapi / uvicorn[standard] / boto3
requirements-dev.txt # 加 httpx(TestClient 依赖)
tests/
  test_config.py         # 现有,扩展
  test_pipeline.py       # 现有,扩展 overrides
  test_db.py             # 新
  test_storage.py        # 新
  test_queue.py          # 新
  test_auth.py           # 新
  test_api.py            # 新(集成)
```

---

## Task 1: 配置项 + FastAPI 骨架 + 健康检查 + CORS

**Files:**
- Modify: `config.py`
- Modify: `requirements.txt`、`requirements-dev.txt`
- Create: `server/__init__.py`(空文件)、`server/app.py`
- Test: `tests/test_api.py`(本任务先建健康检查用例)

**Interfaces:**
- Produces:
  - `config.R2_ACCOUNT_ID/R2_ACCESS_KEY/R2_SECRET_KEY/R2_BUCKET/R2_PUBLIC_BASE: str`
  - `config.APP_PASSCODE: str`、`config.CORS_ORIGINS: list[str]`、`config.DB_PATH: str`
  - `server.app.app`(FastAPI 实例);`GET /api/health` → `{"status": "ok"}`

- [ ] **Step 1: 加依赖声明**

`requirements.txt` 末尾追加:
```
fastapi
uvicorn[standard]
boto3
```
`requirements-dev.txt` 末尾追加:
```
httpx
```
安装:`.venv/bin/pip install fastapi "uvicorn[standard]" boto3 httpx`

- [ ] **Step 2: 写失败测试(健康检查)**

`tests/test_api.py`:
```python
from fastapi.testclient import TestClient
from server.app import app

client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: FAIL(`ModuleNotFoundError: server.app`)

- [ ] **Step 4: 在 config.py 增加配置项**

在 `config.py` 末尾(`ensure_dirs` 之前或之后)加:
```python
# Web 后端配置
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "ze_music.db"))
APP_PASSCODE = os.environ.get("APP_PASSCODE", "")
CORS_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()
]

# Cloudflare R2(S3 兼容)
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
R2_PUBLIC_BASE = os.environ.get("R2_PUBLIC_BASE", "")  # 如 https://xxx.r2.dev
```

- [ ] **Step 5: 写 server/app.py 骨架**

`server/__init__.py`:空文件。

`server/app.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config

app = FastAPI(title="ze music API")

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
```

- [ ] **Step 6: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add requirements.txt requirements-dev.txt config.py server/__init__.py server/app.py tests/test_api.py
git commit -m "feat: FastAPI 骨架 + 健康检查 + CORS + 后端配置项"
```

---

## Task 2: SQLite 元数据层(songs / jobs)

**Files:**
- Create: `server/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `config.DB_PATH`
- Produces:
  - `db.init_db(path: str | None = None) -> None`
  - `db.insert_song(song: dict) -> None`(song 含 id,见下)
  - `db.get_song(song_id: str) -> dict | None`
  - `db.list_songs(*, q: str = "", favorite: bool = False, mine: str = "", limit: int = 50, offset: int = 0) -> list[dict]`
  - `db.toggle_favorite(song_id: str) -> bool`(返回切换后的收藏状态)
  - `db.create_job(job_id: str, *, status: str, position: int, created_by: str) -> None`
  - `db.update_job(job_id: str, **fields) -> None`
  - `db.get_job(job_id: str) -> dict | None`
  - song 字段:`id,title,lyrics,feeling,spec_json,structured_lyrics,seed,mp3_url,duration_sec,instrumental,created_by,favorite,created_at`
  - job 字段:`job_id,status,position,song_id,error,created_by,created_at`

- [ ] **Step 1: 写失败测试**

`tests/test_db.py`:
```python
from server import db


def _song(**over):
    base = dict(
        id="s1", title="夏夜的微风", lyrics="歌词", feeling="女声 R&B",
        spec_json="{}", structured_lyrics="[Verse]\nx", seed=None,
        mp3_url="https://r2/s1.mp3", duration_sec=201.0, instrumental=0,
        created_by="ze",
    )
    base.update(over)
    return base


def test_insert_and_get_song(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    db.insert_song(_song())
    got = db.get_song("s1")
    assert got["title"] == "夏夜的微风"
    assert got["favorite"] == 0
    assert got["created_at"]  # 自动填充


def test_list_songs_filters(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    db.insert_song(_song(id="s1", title="夏夜", created_by="ze"))
    db.insert_song(_song(id="s2", title="冬夜", created_by="lin"))
    assert {s["id"] for s in db.list_songs()} == {"s1", "s2"}
    assert [s["id"] for s in db.list_songs(q="夏")] == ["s1"]
    assert [s["id"] for s in db.list_songs(mine="lin")] == ["s2"]


def test_toggle_favorite(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    db.insert_song(_song())
    assert db.toggle_favorite("s1") is True
    assert db.get_song("s1")["favorite"] == 1
    assert db.toggle_favorite("s1") is False
    assert [s["id"] for s in db.list_songs(favorite=True)] == []


def test_job_lifecycle(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    db.create_job("j1", status="queued", position=1, created_by="ze")
    assert db.get_job("j1")["status"] == "queued"
    db.update_job("j1", status="done", song_id="s1", position=0)
    j = db.get_job("j1")
    assert j["status"] == "done" and j["song_id"] == "s1"
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_db.py -q`
Expected: FAIL(`ModuleNotFoundError: server.db`)

- [ ] **Step 3: 实现 server/db.py**

```python
import sqlite3
import datetime as _dt

import config

_PATH = config.DB_PATH


def _conn(path: str | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(path or _PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db(path: str | None = None) -> None:
    global _PATH
    if path:
        _PATH = path
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS songs (
              id TEXT PRIMARY KEY, title TEXT, lyrics TEXT, feeling TEXT,
              spec_json TEXT, structured_lyrics TEXT, seed INTEGER,
              mp3_url TEXT, duration_sec REAL, instrumental INTEGER DEFAULT 0,
              created_by TEXT, favorite INTEGER DEFAULT 0, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY, status TEXT, position INTEGER,
              song_id TEXT, error TEXT, created_by TEXT, created_at TEXT
            );
            """
        )


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def insert_song(song: dict) -> None:
    cols = ["id", "title", "lyrics", "feeling", "spec_json", "structured_lyrics",
            "seed", "mp3_url", "duration_sec", "instrumental", "created_by"]
    vals = [song.get(k) for k in cols]
    with _conn() as c:
        c.execute(
            f"INSERT INTO songs ({','.join(cols)}, favorite, created_at) "
            f"VALUES ({','.join('?' * len(cols))}, 0, ?)",
            [*vals, _now()],
        )


def get_song(song_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
    return dict(row) if row else None


def list_songs(*, q: str = "", favorite: bool = False, mine: str = "",
               limit: int = 50, offset: int = 0) -> list[dict]:
    where, args = [], []
    if q:
        where.append("(title LIKE ? OR feeling LIKE ? OR lyrics LIKE ?)")
        args += [f"%{q}%"] * 3
    if favorite:
        where.append("favorite=1")
    if mine:
        where.append("created_by=?")
        args.append(mine)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    args += [limit, offset]
    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM songs {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            args,
        ).fetchall()
    return [dict(r) for r in rows]


def toggle_favorite(song_id: str) -> bool:
    with _conn() as c:
        c.execute("UPDATE songs SET favorite = 1 - favorite WHERE id=?", (song_id,))
        row = c.execute("SELECT favorite FROM songs WHERE id=?", (song_id,)).fetchone()
    return bool(row["favorite"]) if row else False


def create_job(job_id: str, *, status: str, position: int, created_by: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs (job_id,status,position,created_by,created_at) "
            "VALUES (?,?,?,?,?)",
            (job_id, status, position, created_by, _now()),
        )


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE job_id=?",
                  [*fields.values(), job_id])


def get_job(job_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_db.py -q`
Expected: PASS(4 passed)

- [ ] **Step 5: 提交**

```bash
git add server/db.py tests/test_db.py
git commit -m "feat: SQLite 元数据层(songs/jobs 读写 + 收藏/筛选)"
```

---

## Task 3: pipeline 支持手动 overrides

**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline.py`(扩展)

**Interfaces:**
- Consumes: 现有 `planner.plan_song`、`lyrics.structure_lyrics`、`song_gen.generate_song`
- Produces:`pipeline.make_song(..., overrides: dict | None = None)`;overrides 非空字段覆盖 SongSpec 的 `genre/mood/language` 与 `vocal.gender`

- [ ] **Step 1: 写失败测试**

在 `tests/test_pipeline.py` 追加:
```python
def test_make_song_applies_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline.planner.llm, "complete", lambda *a, **k: json.dumps(SAFE_DEFAULT_SPEC)
    )
    monkeypatch.setattr(
        pipeline.lyrics.llm, "complete", lambda *a, **k: "[Verse]\nx"
    )
    seen = {}
    monkeypatch.setattr(
        pipeline.song_gen, "generate_song",
        lambda structured, spec, **k: seen.setdefault("spec", spec) or k["out_path"],
    )

    pipeline.make_song(
        "词", "随便", work_dir=str(tmp_path),
        overrides={"genre": ["R&B"], "vocal_gender": "male", "language": "en"},
    )
    spec = seen["spec"]
    assert spec.genre == ["R&B"]
    assert spec.vocal.gender == "male"
    assert spec.language == "en"
    # 未覆盖字段保持 planner 结果
    assert spec.mood == SAFE_DEFAULT_SPEC["mood"]
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py::test_make_song_applies_overrides -q`
Expected: FAIL(`make_song() got an unexpected keyword argument 'overrides'`)

- [ ] **Step 3: 修改 make_song**

`src/pipeline.py` 改为:
```python
import os
import config
from src import llm, planner, lyrics, song_gen


def _apply_overrides(spec, overrides: dict):
    """用非空 override 字段覆盖 SongSpec;返回新的 SongSpec。"""
    data = spec.model_dump()
    if overrides.get("genre"):
        data["genre"] = overrides["genre"]
    if overrides.get("mood"):
        data["mood"] = overrides["mood"]
    if overrides.get("language"):
        data["language"] = overrides["language"]
    if overrides.get("vocal_gender"):
        data["vocal"]["gender"] = overrides["vocal_gender"]
    return spec.__class__(**data)


def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None,
              overrides: dict | None = None,
              llm_settings: llm.LLMSettings | None = None) -> dict:
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    spec = planner.plan_song(
        style_desc, lyrics_hint=raw_lyrics[:80], llm_settings=llm_settings
    )
    if overrides:
        spec = _apply_overrides(spec, overrides)
    structured = lyrics.structure_lyrics(
        raw_lyrics, spec, llm_settings=llm_settings
    )
    song_path = os.path.join(out_dir, "song.wav")
    song_path = song_gen.generate_song(
        structured, spec, length=length, seed=seed, out_path=song_path
    )
    return {"spec": spec, "structured_lyrics": structured, "song": song_path}
```

- [ ] **Step 4: 运行全部 pipeline 测试**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -q`
Expected: PASS(含新用例与原有用例)

- [ ] **Step 5: 提交**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline make_song 支持手动 overrides 覆盖 SongSpec"
```

---

## Task 4: 存储层(WAV→MP3 + R2 上传)

**Files:**
- Create: `server/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `config.R2_*`;系统 `ffmpeg`
- Produces:
  - `storage.wav_to_mp3(wav_path: str, mp3_path: str) -> str`(返回 mp3_path)
  - `storage.upload_to_r2(local_path: str, key: str) -> str`(返回公网 URL)
  - `storage.probe_duration(path: str) -> float`(ffprobe 读时长,失败返回 0.0)

- [ ] **Step 1: 写失败测试(mock subprocess 与 boto3)**

`tests/test_storage.py`:
```python
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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_storage.py -q`
Expected: FAIL(`ModuleNotFoundError: server.storage`)

- [ ] **Step 3: 实现 server/storage.py**

```python
import subprocess

import config


def wav_to_mp3(wav_path: str, mp3_path: str) -> str:
    """用 ffmpeg 把 WAV 转 128k MP3。失败抛 RuntimeError。"""
    cmd = ["ffmpeg", "-y", "-i", wav_path, "-b:a", "128k", mp3_path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 转码失败: {proc.stderr.decode(errors='ignore')[:300]}")
    return mp3_path


def probe_duration(path: str) -> float:
    """ffprobe 读音频时长(秒);失败返回 0.0。"""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        return 0.0
    try:
        return float(proc.stdout.decode().strip())
    except ValueError:
        return 0.0


def _r2_client():
    import boto3
    endpoint = f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=config.R2_ACCESS_KEY,
        aws_secret_access_key=config.R2_SECRET_KEY,
        region_name="auto",
    )


def upload_to_r2(local_path: str, key: str) -> str:
    """上传到 R2,返回公网 URL。"""
    client = _r2_client()
    client.upload_file(
        local_path, config.R2_BUCKET, key,
        ExtraArgs={"ContentType": "audio/mpeg"},
    )
    return f"{config.R2_PUBLIC_BASE.rstrip('/')}/{key}"
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_storage.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add server/storage.py tests/test_storage.py
git commit -m "feat: 存储层 WAV→MP3(ffmpeg) + R2 上传(boto3)"
```

---

## Task 5: 任务队列 + worker(单 GPU 串行编排)

**Files:**
- Create: `server/queue.py`
- Test: `tests/test_queue.py`

**Interfaces:**
- Consumes: `pipeline.make_song`、`storage.wav_to_mp3/upload_to_r2/probe_duration`、`db.*`
- Produces:
  - `queue.run_generation(job_id: str, payload: dict, created_by: str) -> dict`(阻塞:成曲→MP3→R2→写库,返回 song dict)
  - `queue.JobQueue`,方法:`start()`、`async stop()`、`async enqueue(payload: dict, created_by: str) -> str`
  - payload 键:`lyrics,feeling,length,seed,instrumental,overrides`

- [ ] **Step 1: 写失败测试**

`tests/test_queue.py`:
```python
import asyncio
from server import queue


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


class _FakeSpec:
    def model_dump_json(self):
        return "{}"


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
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_queue.py -q`
Expected: FAIL(`ModuleNotFoundError: server.queue`)

- [ ] **Step 3: 实现 server/queue.py**

```python
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
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_queue.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add server/queue.py tests/test_queue.py
git commit -m "feat: 异步任务队列 + 单 worker 编排(成曲→MP3→R2→落库)"
```

---

## Task 6: 共享口令认证

**Files:**
- Create: `server/auth.py`
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `config.APP_PASSCODE`
- Produces:`auth.require_passcode(x_passcode: str = Header(default="")) -> str`;校验通过返回口令,失败抛 401。`APP_PASSCODE` 为空时放行(本地开发)。

- [ ] **Step 1: 写失败测试**

`tests/test_auth.py`:
```python
import pytest
from fastapi import HTTPException
from server import auth


def test_passcode_ok(monkeypatch):
    monkeypatch.setattr(auth.config, "APP_PASSCODE", "sesame")
    assert auth.require_passcode("sesame") == "sesame"


def test_passcode_wrong(monkeypatch):
    monkeypatch.setattr(auth.config, "APP_PASSCODE", "sesame")
    with pytest.raises(HTTPException) as ei:
        auth.require_passcode("nope")
    assert ei.value.status_code == 401


def test_passcode_disabled_when_empty(monkeypatch):
    monkeypatch.setattr(auth.config, "APP_PASSCODE", "")
    assert auth.require_passcode("") == "anonymous"
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
Expected: FAIL(`ModuleNotFoundError: server.auth`)

- [ ] **Step 3: 实现 server/auth.py**

```python
from fastapi import Header, HTTPException

import config


def require_passcode(x_passcode: str = Header(default="")) -> str:
    """校验 X-Passcode。APP_PASSCODE 为空时放行(本地开发)。"""
    if not config.APP_PASSCODE:
        return "anonymous"
    if x_passcode != config.APP_PASSCODE:
        raise HTTPException(status_code=401, detail="口令错误")
    return x_passcode
```

- [ ] **Step 4: 运行,确认通过**

Run: `.venv/bin/python -m pytest tests/test_auth.py -q`
Expected: PASS(3 passed)

- [ ] **Step 5: 提交**

```bash
git add server/auth.py tests/test_auth.py
git commit -m "feat: 共享口令认证依赖(X-Passcode)"
```

---

## Task 7: 请求模型 + 全部路由 + 队列接入 lifespan

**Files:**
- Create: `server/models.py`、`server/routes.py`、`server/inspirations.py`
- Modify: `server/app.py`(挂路由 + lifespan 启停队列 + init_db)
- Test: `tests/test_api.py`(扩展)

**Interfaces:**
- Consumes: `queue.JobQueue`、`db.*`、`auth.require_passcode`、`models.*`、`inspirations.PRESETS`
- Produces(HTTP):
  - `POST /api/generate` → `{"job_id": str}`
  - `GET /api/jobs/{job_id}` → `{status, position, song, error}`
  - `GET /api/songs?q=&favorite=&mine=&limit=&offset=` → `{"songs": [...]}`
  - `POST /api/songs/{id}/favorite` → `{"favorite": bool}`
  - `GET /api/inspirations` → `{"inspirations": [...]}`

- [ ] **Step 1: 写失败测试(集成流:mock 队列不真跑 GPU)**

在 `tests/test_api.py` 追加:
```python
import server.app as appmod


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


def test_inspirations(monkeypatch):
    r = client.get("/api/inspirations")
    assert len(r.json()["inspirations"]) >= 3
```

- [ ] **Step 2: 运行,确认失败**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: FAIL(新用例:404 / 无 `app.state.queue` 等)

- [ ] **Step 3: 写 server/models.py**

```python
from pydantic import BaseModel, Field


class Overrides(BaseModel):
    genre: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    language: str = ""


class GenerateRequest(BaseModel):
    lyrics: str
    feeling: str = ""
    length: str = "full"      # full | short
    seed: int | None = None
    instrumental: bool = False
    overrides: Overrides = Field(default_factory=Overrides)
```

- [ ] **Step 4: 写 server/inspirations.py**

```python
PRESETS = [
    {"title": "毕业的青春回忆", "feeling": "流行，温柔，女声",
     "lyrics": "[Verse]\n那年夏天 微风吹过海边\n[Chorus]\n如果还能再遇见你"},
    {"title": "夜晚城市的孤独", "feeling": "R&B，悲伤，男声",
     "lyrics": "[Verse]\n最后一班地铁 载着疲惫的人"},
    {"title": "恋爱的心动瞬间", "feeling": "流行，浪漫，女声",
     "lyrics": "[Verse]\n你的一个微笑 让整个世界都亮了"},
    {"title": "海边的治愈旋律", "feeling": "民谣，治愈，纯音乐",
     "lyrics": ""},
]
```

- [ ] **Step 5: 写 server/routes.py**

```python
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
```

- [ ] **Step 6: 改 server/app.py 挂路由 + lifespan**

```python
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
```

注:测试里用 `TestClient(app)` 且直接给 `appmod.app.state.queue` 赋假队列;`GET` 端点不经过队列,可正常测。集成测试中 `POST /api/generate` 用假队列,不触发真 worker/GPU。

- [ ] **Step 7: 运行全部后端测试**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS(原有 + 新增全部通过;真实 GPU 那条仍为 skipped)

- [ ] **Step 8: 提交**

```bash
git add server/models.py server/inspirations.py server/routes.py server/app.py tests/test_api.py
git commit -m "feat: API 路由(generate/jobs/songs/favorite/inspirations)+ 队列接入 lifespan"
```

---

## Task 8: 本地启动脚本 + 真实 E2E 冒烟(手动)

**Files:**
- Create: `run_api.sh`
- Modify: `docs/superpowers/specs/2026-09-04-ze-music-web-app-design.md`(记录冒烟结果,可选)

**Interfaces:** 无新代码接口;交付一个可运行的本地服务与一次真实全链路验证。

- [ ] **Step 1: 写启动脚本**

`run_api.sh`:
```bash
#!/usr/bin/env bash
set -e
export APP_PASSCODE="${APP_PASSCODE:-}"
exec .venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
```
`chmod +x run_api.sh`

- [ ] **Step 2: 起服务,验证健康检查**

Run:
```bash
./run_api.sh &
sleep 2
curl -s http://127.0.0.1:8000/api/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 3: 真实 E2E 冒烟(需 GPU + R2 配好)**

前置:设好 `R2_*` 与 LLM key 环境变量,ACE-Step 权重就位。
```bash
curl -s -X POST http://127.0.0.1:8000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"lyrics":"[Verse]\n测试歌词","feeling":"女声 温柔","length":"short","overrides":{}}'
# 拿到 job_id 后轮询:
curl -s http://127.0.0.1:8000/api/jobs/<job_id>
```
Expected: 状态从 `queued`→`running`→`done`,`song.mp3_url` 是可访问的 R2 链接;`GET /api/songs` 能看到它。

- [ ] **Step 4: 提交**

```bash
git add run_api.sh
git commit -m "chore: 本地 API 启动脚本 + E2E 冒烟流程"
```

注:Step 3 是手动验收(依赖真实 GPU/R2),不进 CI;若本机无 GPU,在目标机器上执行,把结果记进 spec 的测试表。

---

## Self-Review

**Spec coverage:**
- FastAPI + 6 接口 → Task 1(health)、Task 7(generate/jobs/songs/favorite/inspirations)✅
- 单 worker 队列保护 GPU → Task 5 ✅
- WAV→MP3 + R2 → Task 4 ✅
- SQLite songs/jobs → Task 2 ✅
- pipeline overrides → Task 3 ✅
- 服务器持有 LLM key → 不接收用户 key,靠 `src/llm.py` env fallback,Task 7 请求模型无 key 字段 ✅
- 共享口令 → Task 6 ✅
- 唯一 job 目录避免覆盖:当前单 worker 已串行,song_id 作为 R2 key 唯一;`outputs/song.wav` 本地临时文件被单 worker 串行复用可接受(后续多 worker 才需唯一目录)—— 记为已知取舍,未单列任务。
- 错误处理(job=error + 消息)→ Task 5 worker except 分支 ✅
- CORS → Task 1 ✅
- Tailscale Funnel / Vercel 部署 → 属"部署运行手册",不在本后端计划,列入后续前端计划后的部署步骤 ✅

**Placeholder scan:** 无 TBD/TODO;每个 code step 均含完整代码。✅

**Type consistency:** `enqueue(payload, created_by)`、`run_generation(job_id, payload, created_by)`、song dict 字段(`id/title/mp3_url/duration_sec/...`)、job 字段(`status/position/song_id/error`)在 db/queue/routes/tests 间一致。✅

**已知取舍 / 后续:**
- 进程重启时 `queued/running` 的残留任务未自动清理(spec 未决项),后续加启动时把非 done 标 error。
- 标题用 feeling/歌词首句截断,后续可换 LLM 起名。
