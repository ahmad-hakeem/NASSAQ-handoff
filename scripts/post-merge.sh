#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Reconcile dependencies only. Never run Alembic, schema pushes, seeds,
# application startup jobs, or the destructive deployment build script here.
# Keep Replit's existing Python environment and its auxiliary tools.
UV_PROJECT_ENVIRONMENT="$PWD/.pythonlibs" uv sync --frozen --inexact
npm ci --no-audit --no-fund
npm --prefix frontend ci --legacy-peer-deps --no-audit --no-fund

echo "Post-merge dependencies ready. No database migrations were run."
# The platform reconciles/restarts configured workflows after this hook.