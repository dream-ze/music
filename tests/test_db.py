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
