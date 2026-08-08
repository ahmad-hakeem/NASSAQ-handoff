#!/usr/bin/env bash
# Local mirror of the CI merge gate. Runs the SAME scripts/ci/* entry points
# the GitHub workflow runs. Usage: scripts/ci_local.sh [backend|frontend|e2e|security|all]
#
# CI_LOCAL_DB_URL must point at a DISPOSABLE postgres database created for
# the run (never the workspace/app DATABASE_URL — the workspace default is
# the real production database). See docs/ci.md for setup.
set -euo pipefail
GATE="${1:-all}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

: "${CI_LOCAL_DB_URL:?Set CI_LOCAL_DB_URL to a DISPOSABLE postgres database URL (never the app DB). See docs/ci.md}"

# ENVIRONMENT is pinned to development for CI parity — the workspace shell
# runs as production, and the gates must never inherit that.
run_backend()  { ENVIRONMENT=development DATABASE_URL="$CI_LOCAL_DB_URL" bash "$ROOT/scripts/ci/backend_tests.sh"; }
run_frontend() { bash "$ROOT/scripts/ci/frontend_tests.sh"; }
run_e2e()      { ENVIRONMENT=development DATABASE_URL="$CI_LOCAL_DB_URL" E2E_PORT="${E2E_PORT:-8100}" bash "$ROOT/scripts/ci/e2e_tests.sh"; }
run_security() { ENVIRONMENT=development DATABASE_URL="$CI_LOCAL_DB_URL" bash "$ROOT/scripts/ci_security_scan.sh"; }

case "$GATE" in
  backend)  run_backend ;;
  frontend) run_frontend ;;
  e2e)      run_e2e ;;
  security) run_security ;;
  all)
    FAILED=()
    run_backend  || FAILED+=(backend)
    run_frontend || FAILED+=(frontend)
    run_e2e      || FAILED+=(e2e)
    run_security || FAILED+=(security)
    if [ ${#FAILED[@]} -gt 0 ]; then
      echo "GATE VERDICT: RED — failed: ${FAILED[*]}"; exit 1
    fi
    echo "GATE VERDICT: GREEN — all gates passed" ;;
  *) echo "usage: $0 [backend|frontend|e2e|security|all]"; exit 2 ;;
esac
