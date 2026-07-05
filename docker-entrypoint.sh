#!/bin/sh
set -e

if [ -z "$DATABASE_URL" ]; then
  echo "FATAL: DATABASE_URL is not set" >&2
  exit 1
fi

echo "Applying database migrations (alembic upgrade head)..."
cd /app/backend
alembic upgrade head
echo "Migrations applied."

cd /app
exec uvicorn backend.server:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers
