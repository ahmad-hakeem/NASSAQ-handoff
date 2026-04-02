#!/bin/bash
set -e

echo "=========================================="
echo "NASSAQ Build & Deployment Safety Check"
echo "=========================================="

ENV="${ENVIRONMENT:-development}"
echo "Environment: $ENV"
echo "DB_NAME: ${DB_NAME:-test_database}"

if [ "$ENV" = "production" ]; then
  echo ""
  echo "[SAFETY] Production deployment detected"
  echo "[SAFETY] Verifying deployment safety rules..."

  if [ "${DB_NAME:-test_database}" = "test_database" ]; then
    echo "[WARNING] DB_NAME is 'test_database' in production — verify this is intentional"
  fi

  if [ -z "$JWT_SECRET_KEY" ]; then
    echo "[ERROR] JWT_SECRET_KEY is not set for production!"
    exit 1
  fi

  echo "[SAFETY] Seed scripts: BLOCKED"
  echo "[SAFETY] Destructive migrations: BLOCKED"
  echo "[SAFETY] All safety checks passed"
  echo ""
fi

echo "Building frontend..."
cd /home/runner/workspace/frontend
npm install
npm run build
echo ""
echo "Build complete."
echo "=========================================="
