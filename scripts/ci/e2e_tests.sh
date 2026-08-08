#!/usr/bin/env bash
# Canonical E2E gate. Called by BOTH .github/workflows/ci.yml and
# scripts/ci_local.sh — never duplicate these commands elsewhere.
#
# Production-shaped: builds the frontend, lets the backend serve it
# same-origin (backend/app/routes.py mounts frontend/build), seeds CI
# fixtures, runs the full Playwright suite against http://localhost:8000.
#
# The suite includes frontend/e2e/double-fetch.spec.ts, the double-fetch
# guard: it loads representative pages per role against this production
# build and fails when a page requests the same URL twice on one load.
#
# Contract:
#   - DATABASE_URL = DISPOSABLE database, already migrated OR empty
#     (script migrates).
#   - Node deps + playwright chromium must be installed.
set -euo pipefail

: "${DATABASE_URL:?e2e gate: DATABASE_URL must be set to a DISPOSABLE database}"
export ENVIRONMENT=development
export SECRET_KEY="${SECRET_KEY:-ci-only-dummy-secret-key}"
export ALGORITHM="${ALGORITHM:-HS256}"
# Port 8000 in CI; overridable locally where the dev backend already owns it.
E2E_PORT="${E2E_PORT:-8000}"
export APP_URL="http://localhost:${E2E_PORT}"
# The E2E suite exercises the REAL MFA challenge flow (post-login-redirect
# spec 5 signs in with a recovery code). The workspace/dev environment may
# have the demo kill switch engaged — the gate must run with enforcement ON.
unset MFA_ENFORCEMENT_DISABLED
# The suite performs dozens of logins from one IP within a minute; the
# production default (10/60s) rate-limits the gate itself into 429s.
export RATE_LIMIT_LOGIN="${RATE_LIMIT_LOGIN:-1000}"
# Production build must use relative API URLs (same-origin serving); a
# workspace-exported dev-domain value would bake absolute URLs into the
# bundle and break the localhost:8000 round-trip.
unset REACT_APP_BACKEND_URL
if [ -z "${MFA_ENCRYPTION_KEY:-}" ]; then
  MFA_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  export MFA_ENCRYPTION_KEY
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_PID=""
cleanup() { [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true; }
trap cleanup EXIT

echo "==> [e2e gate] frontend production build"
( cd "$ROOT/frontend" && CI=false REACT_APP_BACKEND_URL='' npm run build )

echo "==> [e2e gate] migrate DB"
( cd "$ROOT/backend" && alembic upgrade head )

echo "==> [e2e gate] boot backend on :8000"
( cd "$ROOT/backend" && uvicorn server:app --host 0.0.0.0 --port "${E2E_PORT}" ) &
BACKEND_PID=$!
BOOTED=0
for i in $(seq 1 60); do
  if curl -sf http://localhost:${E2E_PORT}/system/health >/dev/null 2>&1; then BOOTED=1; break; fi
  sleep 1
done
if [ "$BOOTED" != 1 ]; then echo "e2e gate: backend failed to boot"; exit 1; fi

echo "==> [e2e gate] seed CI fixtures"
CI_E2E_ENV_FILE="${CI_E2E_ENV_FILE:-/tmp/ci_e2e.env}"
( cd "$ROOT/backend" && CI_E2E_SEED=1 CI_E2E_ENV_FILE="$CI_E2E_ENV_FILE" python scripts/seed_ci_e2e.py )
set -a
# shellcheck disable=SC1090
source "$CI_E2E_ENV_FILE"
set +a

echo "==> [e2e gate] playwright"
( cd "$ROOT/frontend" && E2E_BASE_URL="http://localhost:${E2E_PORT}" npx playwright test )

echo "==> [e2e gate] PASS"
