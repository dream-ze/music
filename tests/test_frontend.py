from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.frontend import mount_frontend


def _client(tmp_path):
    out = tmp_path / "out"
    (out / "_next" / "static").mkdir(parents=True)
    (out / "index.html").write_text("HOME")
    (out / "library.html").write_text("LIB")
    (out / "404.html").write_text("NF")
    (out / "_next" / "static" / "app.js").write_text("JS")
    (tmp_path / "secret.txt").write_text("SECRET")
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    assert mount_frontend(app, str(out)) is True
    return TestClient(app)


def test_serves_index_clean_urls_and_assets(tmp_path):
    c = _client(tmp_path)
    assert c.get("/").text == "HOME"
    assert c.get("/library").text == "LIB"            # 静态导出的 library.html,无扩展名访问
    assert c.get("/library.html").text == "LIB"
    assert c.get("/_next/static/app.js").text == "JS"


def test_api_routes_still_win(tmp_path):
    c = _client(tmp_path)
    assert c.get("/api/health").json() == {"status": "ok"}


def test_unknown_api_path_is_json_404_not_html(tmp_path):
    r = _client(tmp_path).get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_unknown_page_gets_404_html(tmp_path):
    r = _client(tmp_path).get("/no-such-page")
    assert r.status_code == 404 and r.text == "NF"


def test_path_traversal_blocked(tmp_path):
    c = _client(tmp_path)
    r = c.get("/..%2Fsecret.txt")
    assert r.status_code == 404 and "SECRET" not in r.text


def test_html_not_cached_assets_cached(tmp_path):
    c = _client(tmp_path)
    assert "no-cache" in c.get("/library").headers["cache-control"]
    assert "immutable" in c.get("/_next/static/app.js").headers["cache-control"]


def test_missing_dist_dir_mounts_nothing(tmp_path):
    app = FastAPI()
    assert mount_frontend(app, str(tmp_path / "nope")) is False
    assert TestClient(app).get("/").status_code == 404
