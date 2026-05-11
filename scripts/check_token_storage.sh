#!/usr/bin/env bash
# SECURITY (audit Phase 2 / H-1 sentinel): block new localStorage writes of
# the auth tokens (`nassaq_token`, `nassaq_refresh_token`) outside the single
# legitimate writer at `frontend/src/contexts/AuthContext.js`.
#
# The full migration off localStorage to HttpOnly cookies is a Phase 2.5
# follow-up. Until then, this gate keeps the chokepoint property: any code
# that wants to mutate the token has to go through AuthContext, where the
# cookie cutover will live.
#
# Usage:
#   bash scripts/check_token_storage.sh
#
# Exits 0 on no violations, 1 on any new localStorage.setItem('nassaq_token'…
# in any frontend file other than AuthContext.js.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ALLOWED="frontend/src/contexts/AuthContext.js"
PATTERN="localStorage\.setItem\(\s*['\"](nassaq_token|nassaq_refresh_token)['\"]"

# rg returns 1 when no matches; turn that into success here.
matches=$(rg -n --no-heading -g 'frontend/src/**' \
  --type-add 'fe:*.{js,jsx,ts,tsx}' -tfe \
  "$PATTERN" || true)

if [ -z "$matches" ]; then
  exit 0
fi

violations=$(printf "%s\n" "$matches" | grep -v "^${ALLOWED}:" || true)

if [ -n "$violations" ]; then
  echo "ERROR: New localStorage writes of auth tokens outside ${ALLOWED}:" >&2
  echo "$violations" >&2
  echo "" >&2
  echo "All auth-token writes must go through AuthContext (Phase 2.5 will" >&2
  echo "migrate the storage backend to HttpOnly cookies)." >&2
  exit 1
fi

exit 0
