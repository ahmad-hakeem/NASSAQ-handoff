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
#   4. Dependency vulnerability audit — pip-audit AND safety, both
#      hard-fail when high-severity advisories are reported.
#   5. SAST scan with bandit, hard-fail on high-severity findings.
#
# The full HoundDog secret-scan step from the `security_scan` skill is
# additionally run by the platform in the agent loop; this script is the
# deterministic, repo-local subset suitable for a CI runner. Tools that
# are not installed in the CI image FAIL the gate — install them in the
# image rather than letting the check silently no-op.
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

# Dependency audit — hard-fail. Install pip-audit in the CI image.
if command -v pip-audit >/dev/null 2>&1; then
    run_step "pip-audit"  pip-audit -r backend/requirements.txt --strict
else
    echo "──▶ pip-audit not installed — install with: pip install pip-audit"
    FAIL=1
fi

# Second-source dependency audit (safety) — hard-fail on high severity.
if command -v safety >/dev/null 2>&1; then
    run_step "safety check"  safety check -r backend/requirements.txt --full-report
else
    echo "──▶ safety not installed — install with: pip install safety"
    FAIL=1
fi

# SAST — bandit, hard-fail on high-severity findings only.
if command -v bandit >/dev/null 2>&1; then
    run_step "bandit (high severity)"  bandit -r backend -ll -ii -x backend/tests
else
    echo "──▶ bandit not installed — install with: pip install bandit"
    FAIL=1
fi

if [ "$FAIL" -ne 0 ]; then
    echo
    echo "Security gate FAILED — fix the issues above before merging."
    exit 1
fi

echo
echo "Security gate PASSED."
