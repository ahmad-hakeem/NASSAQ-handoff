#!/usr/bin/env bash
# Canonical frontend gate. Called by BOTH .github/workflows/ci.yml and
# scripts/ci_local.sh — never duplicate these commands elsewhere.
#
# Full jest suite (via react-scripts/craco — NEVER raw jest) then a
# production build check.
set -euo pipefail

cd "$(dirname "$0")/../../frontend"

echo "==> [frontend gate] jest suite"
CI=true npx craco test --watchAll=false

echo "==> [frontend gate] production build"
# CI=false is deliberate (matches the fe-build workflow): CRA treats warnings
# as errors under CI=true and the warning baseline is not clean; tightening
# it is out of scope for the gate.
CI=false npm run build

echo "==> [frontend gate] PASS"
