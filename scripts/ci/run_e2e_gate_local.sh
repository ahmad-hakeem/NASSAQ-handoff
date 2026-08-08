#!/usr/bin/env bash
# Local wrapper: points the canonical E2E gate at the disposable ci_e2e_seed
# database on the same cluster and a non-conflicting port (dev backend owns
# :8000). CI calls scripts/ci/e2e_tests.sh directly instead.
set -euo pipefail
CI_DB_URL=$(echo "$DATABASE_URL" | sed -E 's#/[^/?]+(\?|$)#/ci_e2e_seed\1#')
DATABASE_URL="$CI_DB_URL" E2E_PORT="${E2E_PORT:-8100}" bash "$(dirname "$0")/e2e_tests.sh"
