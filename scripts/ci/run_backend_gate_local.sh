#!/usr/bin/env bash
# Local-only helper: points the canonical backend gate at the throwaway
# nassaq_ci_check database on the workspace Postgres. CI does NOT use this —
# it calls scripts/ci/backend_tests.sh directly with its own service DB.
set -euo pipefail
# The workspace shell runs with ENVIRONMENT=production (real app DB); the gate
# must run in development mode against the throwaway DB only.
export ENVIRONMENT=development
CI_DB_URL=$(python -c "import os,urllib.parse as u; p=u.urlsplit(os.environ['DATABASE_URL']); print(u.urlunsplit((p.scheme,p.netloc,'/nassaq_ci_check',p.query,'')))")
# Recreate from scratch every run: the whole point of this gate is proving a
# clean `alembic upgrade head` schema, so never reuse a stale throwaway DB.
psql "$DATABASE_URL" -c 'DROP DATABASE IF EXISTS nassaq_ci_check;'
psql "$DATABASE_URL" -c 'CREATE DATABASE nassaq_ci_check;'
DATABASE_URL="$CI_DB_URL" exec bash "$(dirname "$0")/backend_tests.sh"
