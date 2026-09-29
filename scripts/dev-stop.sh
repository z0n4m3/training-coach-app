#!/usr/bin/env bash

cd /workspaces/training-coach-app

echo "Stopping API..."

if [ -f .run/api.pid ]; then
  PID="$(cat .run/api.pid)"
  kill "$PID" 2>/dev/null || true
  rm -f .run/api.pid
fi

pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8000" 2>/dev/null || true

echo "Stopping PostgreSQL..."
docker compose stop db

echo "Development services stopped."
