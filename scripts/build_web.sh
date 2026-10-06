#!/usr/bin/env bash
# 构建前端静态页面到 web/out,由后端在同一地址提供(见 server/frontend.py)。
# 前端改动后执行一次即可,后端无需重启(每次请求都从磁盘读文件)。
set -e
cd "$(dirname "$0")/../web"
# 网页与 API 同源,API 地址就是公网 Funnel 地址;可用环境变量覆盖
export NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-https://192.tail3eff52.ts.net}"
npx next build
echo "built web/out (API base: $NEXT_PUBLIC_API_BASE)"
