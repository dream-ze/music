import json
import sqlite3
import uuid
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
              title TEXT, feeling TEXT, stage TEXT, progress REAL,
              started_at TEXT, finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS categories (
              id TEXT PRIMARY KEY, name TEXT, created_by TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS song_categories (
              song_id TEXT, category_id TEXT,
              PRIMARY KEY (song_id, category_id)
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
    # 真实进度:当前阶段、0–1 进度、起止时间(估算剩余时间用)
    for col, typ in (("stage", "TEXT"), ("progress", "REAL"),
                     ("started_at", "TEXT"), ("finished_at", "TEXT")):
        if col not in jcols:
            c.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ}")
    if "category_id" not in cols:
        # 老版本一首歌只能属于一个分类;这一列不再写入,只保留给下面的迁移读一次
        c.execute("ALTER TABLE songs ADD COLUMN category_id TEXT")
    else:
        # 上一版单分类模型已经上线过,把老数据搬进多对多关联表,避免真的丢了归类
        c.execute(
            "INSERT OR IGNORE INTO song_categories (song_id, category_id) "
            "SELECT id, category_id FROM songs WHERE category_id IS NOT NULL"
        )


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
        if not row:
            return None
        song = dict(row)
        song["category_ids"] = [
            r["category_id"] for r in
            c.execute("SELECT category_id FROM song_categories WHERE song_id=?", (song_id,))
        ]
    return song


def _attach_category_ids(c: sqlite3.Connection, songs: list[dict]) -> None:
    """给一批歌曲字典就地加上各自的 category_ids(一首歌可以同时属于多个分类)。"""
    if not songs:
        return
    ids = [s["id"] for s in songs]
    placeholders = ",".join("?" * len(ids))
    rows = c.execute(
        f"SELECT song_id, category_id FROM song_categories WHERE song_id IN ({placeholders})",
        ids,
    ).fetchall()
    by_song: dict[str, list[str]] = {sid: [] for sid in ids}
    for r in rows:
        by_song[r["song_id"]].append(r["category_id"])
    for s in songs:
        s["category_ids"] = by_song.get(s["id"], [])


def list_songs(*, q: str = "", favorite: bool = False, mine: str = "",
               category: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    where, args = [], []
    if q:
        where.append("(title LIKE ? OR feeling LIKE ? OR lyrics LIKE ?)")
        args += [f"%{q}%"] * 3
    if favorite:
        where.append("favorite=1")
    if mine:
        where.append("created_by=?")
        args.append(mine)
    if category == "__none__":
        where.append("NOT EXISTS (SELECT 1 FROM song_categories sc WHERE sc.song_id = songs.id)")
    elif category:
        where.append(
            "EXISTS (SELECT 1 FROM song_categories sc "
            "WHERE sc.song_id = songs.id AND sc.category_id = ?)"
        )
        args.append(category)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    args += [limit, offset]
    with _conn() as c:
        rows = c.execute(
            f"SELECT * FROM songs {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            args,
        ).fetchall()
        songs = [dict(r) for r in rows]
        _attach_category_ids(c, songs)
    return songs


def recent_style_draws(created_by: str, limit: int = 5) -> list[dict]:
    """同一用户最近几首的风格采样结果(新 → 旧),给采样器防重复。老歌没有 style_draw,跳过。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT spec_json FROM songs WHERE created_by=? ORDER BY created_at DESC LIMIT ?",
            (created_by, limit),
        ).fetchall()
    out: list[dict] = []
    for r in rows:
        try:
            draw = json.loads(r["spec_json"] or "{}").get("style_draw")
        except (ValueError, AttributeError):
            continue
        if isinstance(draw, dict):
            out.append(draw)
    return out


def delete_song(song_id: str) -> bool:
    """删数据库记录,返回是否真的删到了(歌不存在时 False)。"""
    with _conn() as c:
        cur = c.execute("DELETE FROM songs WHERE id=?", (song_id,))
        return cur.rowcount > 0


def rename_song(song_id: str, title: str) -> bool:
    """改歌名。原来只有生成那一刻能起名(还起得不好),这里补上事后改名。"""
    with _conn() as c:
        cur = c.execute("UPDATE songs SET title=? WHERE id=?", (title, song_id))
        return cur.rowcount > 0


def create_category(name: str, created_by: str) -> dict:
    cid = uuid.uuid4().hex
    with _conn() as c:
        c.execute(
            "INSERT INTO categories (id,name,created_by,created_at) VALUES (?,?,?,?)",
            (cid, name, created_by, _now()),
        )
    return {"id": cid, "name": name, "created_by": created_by}


def list_categories() -> list[dict]:
    """所有分类,附带各自的歌曲数。一首歌能同时在好几个分类里,
    所以这里的计数加总可能超过歌曲总数,这是符合预期的。
    (未分类不在这张表里,由前端固定一条"未分类"入口。)
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT c.id, c.name, c.created_by, c.created_at, "
            "COUNT(sc.song_id) AS song_count "
            "FROM categories c LEFT JOIN song_categories sc ON sc.category_id = c.id "
            "GROUP BY c.id ORDER BY c.created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def get_category(category_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
    return dict(row) if row else None


def delete_category(category_id: str) -> bool:
    """删分类本身;归在它下面的歌不删,只是从这个分类里移出(可能还在别的分类里)。"""
    with _conn() as c:
        c.execute("DELETE FROM song_categories WHERE category_id=?", (category_id,))
        cur = c.execute("DELETE FROM categories WHERE id=?", (category_id,))
        return cur.rowcount > 0


def add_song_to_category(song_id: str, category_id: str) -> None:
    """把歌加进一个分类;已经在里面就什么都不做(不会重复、不报错)。"""
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO song_categories (song_id, category_id) VALUES (?,?)",
            (song_id, category_id),
        )


def remove_song_from_category(song_id: str, category_id: str) -> None:
    """把歌从一个分类里移出;只影响这一个分类,歌在其他分类里的归属不变。"""
    with _conn() as c:
        c.execute(
            "DELETE FROM song_categories WHERE song_id=? AND category_id=?",
            (song_id, category_id),
        )


def get_song_category_ids(song_id: str) -> list[str]:
    with _conn() as c:
        return [
            r["category_id"] for r in
            c.execute("SELECT category_id FROM song_categories WHERE song_id=?", (song_id,))
        ]


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
            "SELECT job_id, status, title, feeling, created_by, created_at, "
            "stage, progress, started_at "
            "FROM jobs WHERE status IN ('queued','running') ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def recent_job_seconds(limit: int = 10) -> list[float]:
    """最近完成任务的耗时(秒),估算剩余时间用。失败或缺时间戳的不算。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT started_at, finished_at FROM jobs WHERE status='done' "
            "AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "ORDER BY finished_at DESC LIMIT ?", (limit,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            a = _dt.datetime.fromisoformat(r["started_at"])
            b = _dt.datetime.fromisoformat(r["finished_at"])
        except ValueError:
            continue
        out.append((b - a).total_seconds())
    return out


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
