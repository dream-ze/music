"""由后端直接提供前端静态页面(web/out,Next.js 静态导出)。

*.vercel.app 在部分国内网络被 SNI 拦截,前端改为与 API 同源,经 Tailscale Funnel
的同一个地址访问。API 路由先注册、优先匹配;这里只兜底处理其余 GET 请求。
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_NO_CACHE = {"Cache-Control": "no-cache"}
# Next 构建产物带内容哈希,可以长期缓存
_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _resolve(dist: str, path: str) -> str | None:
    """把 URL 路径映射到 dist 下的文件:原样 → 加 .html → 目录下 index.html。越界返回 None。"""
    rel = path.strip("/")
    for cand in (rel, f"{rel}.html", os.path.join(rel, "index.html")):
        full = os.path.realpath(os.path.join(dist, cand))
        if not full.startswith(dist + os.sep):
            continue                      # 防 ../ 越出 dist
        if os.path.isfile(full):
            return full
    return None


def mount_frontend(app: FastAPI, dist_dir: str) -> bool:
    """dist_dir 不存在(如测试环境、尚未构建)时不挂载,返回 False。"""
    if not os.path.isdir(dist_dir):
        return False
    dist = os.path.realpath(dist_dir)

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not Found")      # 未知 API 保持 JSON 404,不返回网页
        full = _resolve(dist, path)
        if full:
            headers = _IMMUTABLE if path.startswith("_next/static/") else _NO_CACHE
            return FileResponse(full, headers=headers)
        not_found = os.path.join(dist, "404.html")
        if os.path.isfile(not_found):
            return FileResponse(not_found, status_code=404, headers=_NO_CACHE)
        raise HTTPException(404, "Not Found")

    return True
