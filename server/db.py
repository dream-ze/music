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
              created_by TEXT, favorite INTEGER DEFAULT 0, created_at TEXT,
              llm_status TEXT
            );
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY, status TEXT, position INTEGER,
              song_id TEXT, error TEXT, created_by TEXT, created_at TEXT,
              title TEXT, feeling TEXT
            );
            """
        )
        _migrate(c)


def _migrate(c: sqlite3.Connection) -> None:
    """给已存在的老表补新列。CREATE TABLE IF NOT EXISTS 不会改已有表结构。"""
    cols = {r["name"] for r in c.execute("PRAGMA table_info(songs)")}
    if "llm_status" not in cols:
        c.execute("ALTER TABLE songs ADD COLUMN llm_status TEXT")
    jcols = {r["name"] for r in c.execute("PRAGMA table_info(jobs)")}
    # 作品库要在歌生成完之前就显示歌名/感觉,所以提交时存进 jobs
    for col in ("title", "feeling"):
        if col not in jcols:
            c.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def insert_song(song: dict) -> None:
    cols = ["id", "title", "lyrics", "feeling", "spec_json", "structured_lyrics",
            "seed", "mp3_url", "duration_sec", "instrumental", "created_by",
            "llm_status"]
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


def delete_song(song_id: str) -> bool:
    """删数据库记录,返回是否真的删到了(歌不存在时 False)。"""
    with _conn() as c:
        cur = c.execute("DELETE FROM songs WHERE id=?", (song_id,))
        return cur.rowcount > 0


def toggle_favorite(song_id: str) -> bool:
    with _conn() as c:
        c.execute("UPDATE songs SET favorite = 1 - favorite WHERE id=?", (song_id,))
        row = c.execute("SELECT favorite FROM songs WHERE id=?", (song_id,)).fetchone()
    return bool(row["favorite"]) if row else False


def create_job(job_id: str, *, status: str, position: int, created_by: str,
               title: str = "", feeling: str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs (job_id,status,position,created_by,created_at,title,feeling) "
            "VALUES (?,?,?,?,?,?,?)",
            (job_id, status, position, created_by, _now(), title, feeling),
        )


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE job_id=?",
                  [*fields.values(), job_id])


def list_active_jobs() -> list[dict]:
    """排队中/生成中的任务,按提交先后。作品库用它显示"生成中"卡片。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT job_id, status, title, feeling, created_by, created_at "
            "FROM jobs WHERE status IN ('queued','running') ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_job(job_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else None


def fail_orphaned_jobs() -> int:
    """把重启前残留的 queued/running 任务标记为 error。

    进程内队列不持久化,服务重启后这些任务不会再被处理,需在启动时清理,
    否则前端会一直看到"排队中/生成中"卡死。返回被清理的任务数。
    """
    with _conn() as c:
        cur = c.execute(
            "UPDATE jobs SET status='error', position=0, "
            "error='服务重启,任务已中断,请重新生成' "
            "WHERE status IN ('queued','running')"
        )
        return cur.rowcount
