#!/usr/bin/env bash
set -e
# 载入本地 .env(不进 git),里面放 R2/LLM key/口令 等
if [ -f .env ]; then set -a; . ./.env; set +a; fi
exec .venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
