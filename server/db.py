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
