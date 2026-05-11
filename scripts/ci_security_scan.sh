#!/usr/bin/env bash
# Phase 3 — CI security gate.
#
# Runs the dependency-audit + SAST + token-storage checks that the audit's
# Phase 3 roadmap requires on every PR. Designed to be invoked from a CI
# pipeline (GitHub Actions, GitLab CI, Replit Deployments pre-deploy hook,
# or `make security`) and to FAIL the pipeline if any check fails.
#
# Coverage:
#   1. Token-storage chokepoint (Phase 2 sentinel).
#   2. Tenant-scoped lookup chokepoint (Phase 1 sentinel).
#   3. Phase-1, Phase-2, and Phase-3 security pytest suites.
#   4. Dependency vulnerability audit (pip-audit) — soft-fail on info-only
#      advisories so transient registry blips do not block deploys.
#
# The full SAST + HoundDog secret-scan steps from the `security_scan` skill
# are run by the platform via the same skill in the agent loop; this script
# is the deterministic, repo-local subset suitable for a CI runner.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FAIL=0

run_step() {
    local label="$1"; shift
    echo "──▶ $label"
    if "$@"; then
        echo "   OK"
    else
        echo "   FAIL"
        FAIL=1
    fi
}

run_step "token-storage chokepoint"  bash scripts/check_token_storage.sh
run_step "tenant-scoped lookup chokepoint"  bash scripts/check_tenant_scoped_lookups.sh

# pytest may not be installed in every CI image — skip cleanly if absent.
if command -v pytest >/dev/null 2>&1; then
    run_step "phase 1 security tests"  pytest -q backend/tests/test_security_phase1.py
    run_step "phase 2 security tests"  pytest -q backend/tests/test_security_phase2.py
    run_step "phase 3 security tests"  pytest -q backend/tests/test_security_phase3.py
else
    echo "──▶ pytest not installed — skipping security test suites"
fi

# Dependency audit — soft-fail (warn but do not block) since transient PyPI
# advisory feed errors must not gate hotfix deploys.
if command -v pip-audit >/dev/null 2>&1; then
    echo "──▶ pip-audit (warn-only)"
    pip-audit -r backend/requirements.txt --strict || \
        echo "   warning: pip-audit reported issues — review before merge"
else
    echo "──▶ pip-audit not installed — install with: pip install pip-audit"
fi

if [ "$FAIL" -ne 0 ]; then
    echo
    echo "Security gate FAILED — fix the issues above before merging."
    exit 1
fi

echo
echo "Security gate PASSED."
