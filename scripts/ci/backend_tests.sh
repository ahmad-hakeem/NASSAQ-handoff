#!/usr/bin/env bash
# Canonical backend gate. Called by BOTH .github/workflows/ci.yml and
# scripts/ci_local.sh — never duplicate these commands elsewhere.
#
# Contract:
#   - DATABASE_URL must point at a DISPOSABLE Postgres database.
#   - Runs alembic upgrade head on it (fresh-DB migration proof), then the
#     full pytest suite (includes schema-drift + destructive-migration guards).
set -euo pipefail

: "${DATABASE_URL:?backend gate: DATABASE_URL must be set to a DISPOSABLE database}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
# The suite's baseline contract: the MFA kill-switch is ENGAGED. The vast
# majority of tests mint users without MFA enrollment and would otherwise be
# rejected by the Task #443 enrollment gate. The handful of tests that assert
# the *enforced* MFA contracts (step-up envelopes, enrollment gate, bootstrap
# MFA) opt back in per-test via the `enforce_mfa` fixture in conftest.py —
# mfa_policy reads the env fresh on every call, so a monkeypatch works.
# Pin it explicitly so the gate behaves identically on any runner.
export MFA_ENFORCEMENT_DISABLED=true
export SECRET_KEY="${SECRET_KEY:-ci-only-dummy-secret-key}"
export ALGORITHM="${ALGORITHM:-HS256}"
export TESTING=1
# Hermetic gate: legacy live-server integration scripts opt in via
# REACT_APP_BACKEND_URL (conftest pytest_collection_modifyitems). The
# workspace exports this var for the frontend dev server, so unset it here —
# the gate never has a running, seeded backend to point those scripts at.
unset REACT_APP_BACKEND_URL
if [ -z "${MFA_ENCRYPTION_KEY:-}" ]; then
  MFA_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  export MFA_ENCRYPTION_KEY
fi

cd "$(dirname "$0")/../../backend"

echo "==> [backend gate] alembic upgrade head (fresh DB)"
alembic upgrade head

echo "==> [backend gate] pytest (full suite)"
python -m pytest tests -q --maxfail=25 -rs

echo "==> [backend gate] PASS"
