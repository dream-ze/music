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


def test_rename_song(tmp_path):
    """生成时只有一次起名机会,还起得不一定好;这里补上事后改名。"""
    p = str(tmp_path / "t.db")
    db.init_db(p)
    db.insert_song(_song())
    assert db.rename_song("s1", "新名字") is True
    assert db.get_song("s1")["title"] == "新名字"


def test_rename_unknown_song_returns_false(tmp_path):
    db.init_db(str(tmp_path / "t.db"))
    assert db.rename_song("nope", "新名字") is False


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


def test_fail_orphaned_jobs(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    db.create_job("q1", status="queued", position=1, created_by="ze")
    db.create_job("r1", status="running", position=0, created_by="ze")
    db.create_job("d1", status="done", position=0, created_by="ze")
    n = db.fail_orphaned_jobs()
    assert n == 2  # q1 + r1
    assert db.get_job("q1")["status"] == "error"
    assert db.get_job("r1")["status"] == "error"
    assert db.get_job("d1")["status"] == "done"  # 已完成的不动


# ── llm_status:把"降级生成"落库,让前端能把它跟正常出的歌区分开 ────────

_OLD_SONGS_SCHEMA = """
CREATE TABLE songs (
  id TEXT PRIMARY KEY, title TEXT, lyrics TEXT, feeling TEXT,
  spec_json TEXT, structured_lyrics TEXT, seed INTEGER,
  mp3_url TEXT, duration_sec REAL, instrumental INTEGER DEFAULT 0,
  created_by TEXT, favorite INTEGER DEFAULT 0, created_at TEXT
);
"""


def test_insert_and_get_song_keeps_llm_status(tmp_path):
    p = str(tmp_path / "t.db")
    db.init_db(p)
    status = '[{"stage": "歌词整理", "ok": false}]'
    db.insert_song(_song(llm_status=status))
    assert db.get_song("s1")["llm_status"] == status


def test_init_db_migrates_existing_table_without_llm_status(tmp_path):
    """老库里 songs 表已存在且没有 llm_status 列,启动时必须补列而不是崩掉。"""
    import sqlite3

    p = str(tmp_path / "old.db")
    with sqlite3.connect(p) as c:
        c.executescript(_OLD_SONGS_SCHEMA)

    db.init_db(p)

    with sqlite3.connect(p) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(songs)")}
    assert "llm_status" in cols


def test_jobs_table_migrates_title_and_feeling(tmp_path):
    """老库的 jobs 表没有 title/feeling 列,启动时要自动补上。"""
    import sqlite3
    p = str(tmp_path / "old.db")
    with sqlite3.connect(p) as c:
        c.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, status TEXT, position INTEGER, "
                  "song_id TEXT, error TEXT, created_by TEXT, created_at TEXT)")
    db.init_db(p)
    db.create_job("j1", status="queued", position=1, created_by="ze",
                  title="冬日甜心", feeling="女声 hip hop")
    got = db.get_job("j1")
    assert got["title"] == "冬日甜心" and got["feeling"] == "女声 hip hop"


def test_list_active_jobs_only_queued_running_in_order(tmp_path):
    db.init_db(str(tmp_path / "t.db"))
    db.create_job("j1", status="running", position=0, created_by="ze", title="A")
    db.create_job("j2", status="queued", position=1, created_by="ze", title="B")
    db.create_job("j3", status="done", position=0, created_by="ze", title="C")
    db.create_job("j4", status="error", position=0, created_by="ze", title="D")
    active = db.list_active_jobs()
    assert [j["job_id"] for j in active] == ["j1", "j2"]
    assert set(active[0]) == {"job_id", "status", "title", "feeling", "created_by", "created_at"}


# ── 自定义分类(多对多:一首歌能同时属于好几个分类,跟网易云歌单一样)────

def test_create_and_list_categories(tmp_path):
    db.init_db(str(tmp_path / "cat.db"))
    cat = db.create_category("民谣", "ze")
    assert cat["name"] == "民谣"
    cats = db.list_categories()
    assert len(cats) == 1
    assert cats[0]["id"] == cat["id"]
    assert cats[0]["song_count"] == 0


def test_add_song_to_multiple_categories_and_filter(tmp_path):
    db.init_db(str(tmp_path / "cat2.db"))
    folk = db.create_category("民谣", "ze")
    night = db.create_category("深夜", "ze")
    db.insert_song(_song(id="s1"))
    db.insert_song(_song(id="s2"))

    db.add_song_to_category("s1", folk["id"])
    db.add_song_to_category("s1", night["id"])  # s1 同时属于两个分类
    assert set(db.get_song("s1")["category_ids"]) == {folk["id"], night["id"]}
    assert set(db.get_song_category_ids("s1")) == {folk["id"], night["id"]}

    in_folk = db.list_songs(category=folk["id"])
    assert [s["id"] for s in in_folk] == ["s1"]
    assert in_folk[0]["category_ids"] and set(in_folk[0]["category_ids"]) == {folk["id"], night["id"]}

    uncategorized = db.list_songs(category="__none__")
    assert [s["id"] for s in uncategorized] == ["s2"]
    assert uncategorized[0]["category_ids"] == []

    cats = {c["id"]: c["song_count"] for c in db.list_categories()}
    assert cats[folk["id"]] == 1 and cats[night["id"]] == 1


def test_remove_song_from_one_category_keeps_the_other(tmp_path):
    db.init_db(str(tmp_path / "cat3.db"))
    folk = db.create_category("民谣", "ze")
    night = db.create_category("深夜", "ze")
    db.insert_song(_song(id="s1"))
    db.add_song_to_category("s1", folk["id"])
    db.add_song_to_category("s1", night["id"])

    db.remove_song_from_category("s1", folk["id"])
    assert db.get_song_category_ids("s1") == [night["id"]]


def test_add_song_to_category_twice_is_a_no_op(tmp_path):
    """重复加进同一个分类不报错、不重复计数。"""
    db.init_db(str(tmp_path / "cat4.db"))
    cat = db.create_category("民谣", "ze")
    db.insert_song(_song(id="s1"))
    db.add_song_to_category("s1", cat["id"])
    db.add_song_to_category("s1", cat["id"])
    assert db.get_song_category_ids("s1") == [cat["id"]]
    assert db.list_categories()[0]["song_count"] == 1


def test_delete_category_removes_membership_but_keeps_song_and_other_memberships(tmp_path):
    db.init_db(str(tmp_path / "cat5.db"))
    folk = db.create_category("民谣", "ze")
    night = db.create_category("深夜", "ze")
    db.insert_song(_song(id="s1"))
    db.add_song_to_category("s1", folk["id"])
    db.add_song_to_category("s1", night["id"])

    assert db.delete_category(folk["id"]) is True
    assert db.get_song_category_ids("s1") == [night["id"]]
    assert db.get_song("s1") is not None
    assert {c["id"] for c in db.list_categories()} == {night["id"]}


def test_delete_category_unknown_returns_false(tmp_path):
    db.init_db(str(tmp_path / "cat6.db"))
    assert db.delete_category("nope") is False


def test_songs_table_migrates_category_id_column(tmp_path):
    """老库的 songs 表没有 category_id 列,启动时要自动补上(即使不再写它)。"""
    import sqlite3
    p = str(tmp_path / "oldsongs.db")
    with sqlite3.connect(p) as c:
        c.execute("CREATE TABLE songs (id TEXT PRIMARY KEY, title TEXT, lyrics TEXT, "
                  "feeling TEXT, spec_json TEXT, structured_lyrics TEXT, seed INTEGER, "
                  "mp3_url TEXT, duration_sec REAL, instrumental INTEGER DEFAULT 0, "
                  "created_by TEXT, favorite INTEGER DEFAULT 0, created_at TEXT)")
    db.init_db(p)
    db.insert_song(_song(id="s1"))
    assert db.get_song("s1")["category_ids"] == []


def test_old_single_category_data_gets_backfilled_into_song_categories(tmp_path):
    """上一版单分类模型已经上线过;老数据(songs.category_id)不能凭空消失,
    启动时要一次性搬进新的多对多关联表。"""
    import sqlite3
    p = str(tmp_path / "legacy.db")
    with sqlite3.connect(p) as c:
        c.execute("CREATE TABLE songs (id TEXT PRIMARY KEY, title TEXT, lyrics TEXT, "
                  "feeling TEXT, spec_json TEXT, structured_lyrics TEXT, seed INTEGER, "
                  "mp3_url TEXT, duration_sec REAL, instrumental INTEGER DEFAULT 0, "
                  "created_by TEXT, favorite INTEGER DEFAULT 0, created_at TEXT, "
                  "category_id TEXT)")
        c.execute("CREATE TABLE categories (id TEXT PRIMARY KEY, name TEXT, "
                  "created_by TEXT, created_at TEXT)")
        c.execute("INSERT INTO categories VALUES ('c1','民谣','ze','t')")
        c.execute("INSERT INTO songs (id, category_id) VALUES ('s1','c1')")
    db.init_db(p)
    assert db.get_song_category_ids("s1") == ["c1"]


def test_recent_style_draws_filters_user_and_skips_old_songs(tmp_path):
    import json
    import time
    from server import db
    db.init_db(str(tmp_path / "r.db"))
    rows = [("a", "ze", {"style_draw": {"preset_id": "rock.band"}}),
            ("b", "ze", {"language": "zh"}),                              # 老歌:没有 style_draw
            ("c", "other", {"style_draw": {"preset_id": "jazz.lounge"}}),
            ("d", "ze", {"style_draw": {"preset_id": "lofi.chill"}})]
    for sid, who, spec in rows:
        db.insert_song({"id": sid, "title": sid, "lyrics": "", "feeling": "",
                        "spec_json": json.dumps(spec), "structured_lyrics": "",
                        "seed": 1, "mp3_url": "", "duration_sec": 1.0,
                        "instrumental": 0, "created_by": who, "llm_status": "[]"})
        time.sleep(0.002)          # created_at 精确到微秒,留出间隔保证排序稳定
    got = db.recent_style_draws("ze", limit=5)
    assert [d["preset_id"] for d in got] == ["lofi.chill", "rock.band"]   # 新 → 旧
    assert db.recent_style_draws("ze", limit=1) == [{"preset_id": "lofi.chill"}]
