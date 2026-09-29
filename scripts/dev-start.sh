#!/usr/bin/env bash
set -e

cd /workspaces/training-coach-app

echo "1/5 Starting PostgreSQL..."

if ! docker compose up -d db; then
  echo "Old Docker container looks broken - recreating it..."
  CONTAINER_ID="$(docker compose ps -aq db 2>/dev/null || true)"
  if [ -n "$CONTAINER_ID" ]; then
    docker rm -f "$CONTAINER_ID" || true
  fi
  docker compose up -d db
fi

echo "2/5 Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U training -d training >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker compose exec -T db pg_isready -U training -d training >/dev/null 2>&1; then
  echo "ERROR: PostgreSQL did not become ready."
  exit 1
fi

echo "3/5 Checking Python dependencies..."
if ! python -c "import fastapi, sqlalchemy, psycopg, alembic" >/dev/null 2>&1; then
  python -m pip install -e "./apps/api[dev]"
fi

export DATABASE_URL="postgresql+psycopg://training:training@127.0.0.1:5432/training"

echo "4/5 Running migrations..."
(
  cd apps/api
  alembic upgrade head
)

if [ -z "${INTERVALS_API_KEY:-}" ]; then
  echo "WARNING: INTERVALS_API_KEY is not loaded."
else
  echo "Intervals API key: loaded."
fi

echo "5/5 Starting API..."

if [ -f .run/api.pid ] && kill -0 "$(cat .run/api.pid)" 2>/dev/null; then
  echo "API is already running."
else
  rm -f .run/api.pid
  (
    cd apps/api
    nohup python -m uvicorn app.main:app \
      --host 0.0.0.0 \
      --port 8000 \
      > ../../.run/api.log 2>&1 &
    echo $! > ../../.run/api.pid
  )
fi

for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo
    echo "READY"
    curl -s http://127.0.0.1:8000/health
    echo
    exit 0
  fi
  sleep 1
done

echo "ERROR: API did not start."
echo "Check: tail -50 .run/api.log"
exit 1
