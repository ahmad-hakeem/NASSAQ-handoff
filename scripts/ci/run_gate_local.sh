#!/usr/bin/env bash
# Workspace wrapper for scripts/ci_local.sh: derives a DISPOSABLE database
# URL (ci_e2e_seed on the same cluster) so no gate ever touches the real
# workspace database. CI does NOT use this wrapper — it provisions fresh
# Postgres service containers and calls scripts/ci/*.sh directly.
set -euo pipefail
GATE="${1:?usage: run_gate_local.sh [backend|frontend|e2e|security|all]}"
CI_LOCAL_DB_URL=$(echo "$DATABASE_URL" | sed -E 's#/[^/?]+(\?|$)#/ci_e2e_seed\1#') \
  bash "$(dirname "$0")/../ci_local.sh" "$GATE"
