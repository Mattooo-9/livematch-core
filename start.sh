#!/bin/bash
set -e
echo "[start] Running migrations..."
alembic upgrade head
echo "[start] Starting bot polling in background..."
python scripts/run_bot.py &
echo "[start] Starting API..."
exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
