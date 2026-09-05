#!/usr/bin/env bash
set -e
export APP_PASSCODE="${APP_PASSCODE:-}"
exec .venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
