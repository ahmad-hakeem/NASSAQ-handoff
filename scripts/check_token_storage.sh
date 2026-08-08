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

# Known legitimate writers. AuthContext is the canonical chokepoint; the two
# additional entries are pre-existing flows that must migrate through
# AuthContext in the Phase 2.5 HttpOnly-cookie cutover — do NOT add new ones.
ALLOWED_FILES=(
  "frontend/src/contexts/AuthContext.js"
  "frontend/src/components/mfa/MfaStepUpDialog.jsx"      # §5.7 step-up replay stores rotated access token (Phase 2.5)
  "frontend/src/pages/ParentInvitationAcceptPage.jsx"    # invitation-accept auto-login (Phase 2.5)
)
PATTERN="localStorage\.setItem\(\s*['\"](nassaq_token|nassaq_refresh_token)['\"]"

# rg returns 1 when no matches; turn that into success here. Test files are
# excluded: jsdom localStorage writes in __tests__ are fixtures, not writers.
matches=$(rg -n --no-heading -g 'frontend/src/**' \
  -g '!frontend/src/**/__tests__/**' -g '!frontend/src/**/*.test.*' \
  --type-add 'fe:*.{js,jsx,ts,tsx}' -tfe \
  "$PATTERN" || true)

if [ -z "$matches" ]; then
  exit 0
fi

violations="$matches"
for f in "${ALLOWED_FILES[@]}"; do
  violations=$(printf "%s\n" "$violations" | grep -v "^${f}:" || true)
done

if [ -n "$violations" ]; then
  echo "ERROR: New localStorage writes of auth tokens outside the allowed chokepoint files:" >&2
  echo "$violations" >&2
  echo "" >&2
  echo "All auth-token writes must go through AuthContext (Phase 2.5 will" >&2
  echo "migrate the storage backend to HttpOnly cookies)." >&2
  exit 1
fi

exit 0
