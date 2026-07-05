#!/bin/sh
set -e

if [ -z "$DATABASE_URL" ]; then
  echo "FATAL: DATABASE_URL is not set" >&2
  exit 1
fi

# The app enforces a schema head-gate at startup: in production it refuses to
# serve traffic unless the database schema is at the latest migration.
# Migrations must therefore run BEFORE the server boots.
echo "Applying database migrations (alembic upgrade head)..."
cd /app/backend
alembic upgrade head
echo "Migrations applied."

# The backend uses top-level module imports (config, middleware, routes, ...),
# so the server must run with backend/ as the working directory.
exec uvicorn server:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --proxy-headers
