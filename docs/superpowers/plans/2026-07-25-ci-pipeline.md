# CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub Actions merge gate (4 required parallel jobs: backend, frontend, e2e, security) plus an identical one-command local gate, with a green-and-honest baseline.

**Architecture:** Canonical gate scripts live in `scripts/ci/`; both `.github/workflows/ci.yml` and `scripts/ci_local.sh` call the same scripts. Backend/E2E/security jobs each provision a fresh Postgres 16, run `alembic upgrade head`, then their suite. E2E serves the production frontend build from the backend itself (same-origin, the prod path — `backend/app/routes.py` mounts `frontend/build`), so one uvicorn on :8000 is the whole E2E environment.

**Tech Stack:** GitHub Actions, Postgres 16 service containers, pytest, react-scripts/craco (jest), Playwright (chromium), bandit/pip-audit/safety, bash.

**Spec:** `docs/superpowers/specs/2026-07-25-ci-pipeline-design.md`

**Environment facts the engineer must know (verified during design):**
- Backend tests need a real Postgres via `DATABASE_URL`; `backend/tests/conftest.py` wraps every test in a rollback (`_db_session` fixture) and sets `TESTING=1`. Tests run from `backend/` (`cd backend && pytest tests`).
- `_get_async_url()` in `backend/db.py` converts the URL for asyncpg; give CI a plain `postgresql://` URL.
- The workspace `Backend API` workflow runs `ENVIRONMENT=production` against the **real prod DB**. NEVER point any gate script at the workspace `DATABASE_URL` default. Local verification uses a disposable database created for the run.
- Frontend tests MUST run via `craco test` / `react-scripts test` — never raw `npx jest` (transform config lives in the runner).
- E2E specs (5 files under `frontend/e2e/`) read credentials ONLY from `E2E_*` env vars via `frontend/e2e/lib/credentials.ts`; missing vars throw. CI credentials come from the new CI seed — `TEST_CREDENTIALS.md` is never read in CI.
- `frontend/playwright.config.ts`: baseURL from `E2E_BASE_URL` (default `http://localhost:5000`), 1 worker, retries=1, traces retained on failure.
- Known-red baseline (13 tests): 11 across `backend/tests/test_independent_teacher_phase2_workspace_lifecycle.py` + `backend/tests/test_post_login_workspace_lifecycle.py` (archived-workspace 401 class), 2 in `backend/tests/test_session_homework_grade_sync_task969.py` (`homework_mode=didnt_submit` engine gap — documented pre-existing, see memory topic homework-mode-gate-gap).
- GitHub: repo `ahmadzalat44/NASSAQ_Jul_26` is private + empty; connected credential is a different account. Everything is authored in-repo; push + protection are a user handoff (Task 12).

---

### Task 1: Baseline triage — workspace-lifecycle failures (11 tests)

**Files:**
- Investigate: `backend/tests/test_independent_teacher_phase2_workspace_lifecycle.py`, `backend/tests/test_post_login_workspace_lifecycle.py`, `backend/routes/independent_teacher_workspace_lifecycle_routes.py`
- Maybe modify: whichever of the above the root cause implicates
- Create: `docs/ci/quarantine.md` (only if quarantining)

- [ ] **Step 1: Reproduce and capture the exact failures**

```bash
cd backend && python -m pytest tests/test_independent_teacher_phase2_workspace_lifecycle.py tests/test_post_login_workspace_lifecycle.py -x -q 2>&1 | tail -40
```

Expected: FAIL. Record each failing test id and the assertion (expected vs actual status; prior evidence says tests expect 401 for archived workspaces and get something else, or vice versa).

- [ ] **Step 2: Root-cause per systematic-debugging (no fix before understanding)**

Read the failing assertions, then the route/dependency code they exercise. Determine: did product behavior change intentionally (test is stale) or did a regression land (code is wrong)? Check `git log --oneline -15 -- backend/routes/independent_teacher_workspace_lifecycle_routes.py backend/dependencies.py` for the change that flipped the behavior. Cross-check the contract in `docs/it-phase2-reference.md` (§6.8 lifecycle) — that doc is the spec of record for archived-workspace auth behavior.

- [ ] **Step 3: Decide fix vs quarantine (decision rule)**

- If the tests are stale against an intentionally-changed contract: update the assertions to the documented contract. That is the cheap fix — do it.
- If the code regressed: fixing the route is in scope ONLY if the fix is localized (single guard/status-code correction). A multi-file behavioral repair is out of scope → quarantine.

- [ ] **Step 4: Apply the decision**

If fixing: edit the tests (or the localized guard), then re-run Step 1's command. Expected: PASS.

If quarantining, add at module level (adjust reason to the actual root cause):

```python
import pytest

pytestmark = pytest.mark.skip(
    reason="quarantined 2026-07-25: archived-workspace auth contract drift — see docs/ci/quarantine.md"
)
```

- [ ] **Step 5: Record quarantined entries**

Create `docs/ci/quarantine.md`:

```markdown
# CI Quarantine List

Tests excluded from the merge gate. Every entry needs: test id(s), failure mode,
root-cause note, and a follow-up owner. Removing an entry = deleting its skip
marker and proving the test green. Adding an entry requires the same rigor as
this list's existing entries — no drive-by skips.

| Test(s) | Quarantined | Failure mode | Root cause | Follow-up |
|---|---|---|---|---|
| (fill from Step 4) | 2026-07-25 | ... | ... | user decision on contract |
```

- [ ] **Step 6: Verify both files' final state**

```bash
cd backend && python -m pytest tests/test_independent_teacher_phase2_workspace_lifecycle.py tests/test_post_login_workspace_lifecycle.py -q
```

Expected: PASS (or all-skipped with the quarantine reason shown under `-rs`).

### Task 2: Baseline triage — homework_mode failures (2 tests)

**Files:**
- Modify: `backend/tests/test_session_homework_grade_sync_task969.py`
- Modify: `docs/ci/quarantine.md`

- [ ] **Step 1: Reproduce**

```bash
cd backend && python -m pytest tests/test_session_homework_grade_sync_task969.py -q 2>&1 | tail -20
```

Expected: exactly 2 failures, both `didnt_submit`-mode tests.

- [ ] **Step 2: Quarantine (root cause already established)**

Prior investigation established this is a product gap, not a test bug: the route stores `homework_mode` but the grade-sync engine only reads `homework_enabled` (memory topic homework-mode-gate-gap). Fixing the engine is a behavior change requiring user sign-off → quarantine the two tests only (NOT the module). Decorate each failing test function:

```python
@pytest.mark.skip(reason="quarantined 2026-07-25: engine ignores homework_mode=didnt_submit (product gap) — docs/ci/quarantine.md")
```

- [ ] **Step 3: Verify + record**

```bash
cd backend && python -m pytest tests/test_session_homework_grade_sync_task969.py -q -rs
```

Expected: PASS with 2 skips showing the reason. Add both test ids to the `docs/ci/quarantine.md` table.

### Task 3: Canonical backend gate script

**Files:**
- Create: `scripts/ci/backend_tests.sh`

- [ ] **Step 1: Write the script**

```bash
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
export SECRET_KEY="${SECRET_KEY:-ci-only-dummy-secret-key}"
export ALGORITHM="${ALGORITHM:-HS256}"
export TESTING=1
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
```

- [ ] **Step 2: Make executable, verify against a disposable DB**

Create a throwaway database on the workspace Postgres (NOT the app database), point the script at it, run:

```bash
chmod +x scripts/ci/backend_tests.sh
psql "$DATABASE_URL" -c 'CREATE DATABASE nassaq_ci_check;' 2>/dev/null || true
CI_DB_URL=$(python -c "import os,urllib.parse as u; p=u.urlsplit(os.environ['DATABASE_URL']); print(u.urlunsplit((p.scheme,p.netloc,'/nassaq_ci_check',p.query,'')))")
DATABASE_URL="$CI_DB_URL" bash scripts/ci/backend_tests.sh 2>&1 | tail -15
```

Expected: `alembic upgrade head` completes on the empty DB, pytest ends green (with the Task 1/2 skips listed), script prints `PASS`. If `CREATE DATABASE` is not permitted on the managed instance, fall back to a local throwaway cluster (`pg_ctl initdb` under `/tmp`) — the point is: never the app DB.

- [ ] **Step 3: Drop the throwaway DB**

```bash
psql "$DATABASE_URL" -c 'DROP DATABASE IF EXISTS nassaq_ci_check;'
```

### Task 4: Canonical frontend gate script

**Files:**
- Create: `scripts/ci/frontend_tests.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Canonical frontend gate: full jest suite (via react-scripts — NEVER raw jest)
# then a production build check.
set -euo pipefail

cd "$(dirname "$0")/../../frontend"

echo "==> [frontend gate] jest suite"
CI=true npx craco test --watchAll=false

echo "==> [frontend gate] production build"
CI=false npm run build

echo "==> [frontend gate] PASS"
```

Note: `CI=false` on the build is deliberate (matches the existing `fe-build` workflow — CRA treats warnings as errors under `CI=true`, and the warning baseline is not clean; tightening it is out of scope).

- [ ] **Step 2: Verify**

```bash
chmod +x scripts/ci/frontend_tests.sh
bash scripts/ci/frontend_tests.sh 2>&1 | tail -10
```

Expected: full jest suite green, build completes, `PASS` printed. (Slow — several minutes; run via the validation skill, not a foreground bash timeout.)

### Task 5: Timetable-grid regression test (§11 target 1)

**Files:**
- Create: `frontend/src/pages/__tests__/SchedulePageNew.gridRender.test.jsx`
- Read first: `frontend/src/pages/SchedulePageNew.jsx`, `frontend/src/components/schedule/__tests__/MasterMatrix.test.jsx` (existing harness patterns for the schedule grid), `frontend/src/config/scheduleConfig.js`

- [ ] **Step 1: Extract the real data contract**

`SchedulePageNew` is large; do NOT guess the payload. Identify:

```bash
grep -n "api.get\|apiClient\|fetch" frontend/src/pages/SchedulePageNew.jsx | head -20
grep -n "sessions\|timetable" frontend/src/components/schedule/__tests__/MasterMatrix.test.jsx | head -20
```

Record: which endpoint(s) deliver the published/draft timetable sessions, and the minimal session-object fields the grid needs (class/teacher/subject/day/period). `MasterMatrix.test.jsx` already mocks this shape — reuse its fixture style verbatim.

- [ ] **Step 2: Write the failing test**

Harness rules (from the existing FE test conventions): mock `useAuth` with module-level stable `user`/`api` objects (fresh objects per call loop fetch effects); mock `useTranslation` with a stable module-level `t`; jest `resetMocks: true` is on, so install mock implementations in `beforeEach`. Structure:

```jsx
// SchedulePageNew.gridRender.test.jsx
// §11 regression: after an AI generation payload is loaded, the master grid
// must render session cells — not the empty-grid fallback.
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SchedulePageNew from '../SchedulePageNew';

// mocks per Step 1 findings: stable useAuth api mock whose .get() resolves the
// recorded endpoints with a fixture of >= 2 sessions across 2 classes.

test('renders session cells from a generation payload', async () => {
  render(<MemoryRouter><SchedulePageNew /></MemoryRouter>);
  await waitFor(() => {
    // assert on the subject/teacher text of the fixture sessions, and that
    // the empty-state marker is absent. Use the exact testids/text the page
    // renders (recorded in Step 1) — getAllBy* because desktop+mobile branches
    // may both mount.
    expect(screen.getAllByText('رياضيات').length).toBeGreaterThan(0);
  });
});
```

Fill the mock payloads with the exact fields from Step 1 — the test must pass against the real page, no approximations.

- [ ] **Step 3: Run to verify it fails for the right reason first**

Temporarily point the mock at an empty-sessions payload and confirm the assertion fails (proves the test detects a blank grid), then restore the real fixture:

```bash
cd frontend && CI=true npx craco test --watchAll=false --testPathPattern='SchedulePageNew.gridRender'
```

Expected: FAIL with empty fixture, PASS with real fixture.

- [ ] **Step 4: Commit-worthy checkpoint** — full frontend gate still green: `bash scripts/ci/frontend_tests.sh`.

### Task 6: CI E2E seed script

**Files:**
- Create: `backend/scripts/seed_ci_e2e.py`
- Read first: `backend/scripts/seed_test_data.py` + `backend/scripts/seed_db_helper.py` (existing account-creation patterns — REUSE their helpers instead of reinventing), `frontend/e2e/lib/credentials.ts` (the required env-var names), `frontend/e2e/README.md` (per-account state requirements), `backend/routes/mfa_routes.py` (MFA enrollment + recovery-code storage contract), `backend/routes/independent_teacher_workspace_lifecycle_routes.py` (reactivation-banner snapshot state), `docs/it-phase2-reference.md`

**Required accounts (from `credentials.ts` + README, all with seed-generated random passwords):**

| Env vars emitted | Account state |
|---|---|
| `E2E_IT_BOOTSTRAPPED_*` | independent_teacher, MFA-enrolled, workspace bootstrapped |
| `E2E_IT_PRE_BOOTSTRAP_*` | independent_teacher, MFA-enrolled, workspace NOT bootstrapped |
| `E2E_PRINCIPAL_*` | school_admin of a seeded real school with ≥2 classes, one holding ≥1 student (student-transfer drag spec) |
| `E2E_PARENT_*` | real-school parent linked to a student; password rotated by a spec then restored — plain seeded account is fine |
| `E2E_PLATFORM_ADMIN_*`, `E2E_PLATFORM_OPS_MANAGER_*`, `E2E_PLATFORM_SUB_ADMIN_*` | the three platform roles (BE role names: `platform_admin`, `platform_operations_manager`, `platform_sub_admin`) |
| `E2E_MFA_USER_*` incl. `E2E_MFA_USER_RECOVERY_CODE` | independent_teacher, MFA-enrolled with a usable recovery code, workspace has an ACTIVE `reactivation_banner` snapshot (soft-delete → reactivate via the lifecycle engine, banner not dismissed) |

- [ ] **Step 1: Write the script skeleton**

```python
"""CI-only E2E seed. Creates the accounts frontend/e2e expects and writes
their credentials to an env file consumed by the e2e gate script.

SAFETY: refuses to run unless ENVIRONMENT=development AND CI_E2E_SEED=1.
Never run against a real database.
"""
import asyncio, os, secrets, sys

def main() -> None:
    if os.environ.get("ENVIRONMENT") != "development" or os.environ.get("CI_E2E_SEED") != "1":
        sys.exit("seed_ci_e2e: refusing to run (need ENVIRONMENT=development and CI_E2E_SEED=1)")
    out_path = os.environ.get("CI_E2E_ENV_FILE", "/tmp/ci_e2e.env")
    creds = asyncio.run(seed())          # returns {"E2E_...": "value", ...}
    with open(out_path, "w") as f:
        for k, v in creds.items():
            f.write(f"{k}={v}\n")
    print(f"seed_ci_e2e: wrote {len(creds)} vars to {out_path}")

if __name__ == "__main__":
    main()
```

`seed()` builds each account through the SAME engine/helper functions the app uses (bcrypt hash via the auth helpers in `backend/dependencies.py`; school/class/student creation mirroring `seed_test_data.py`; MFA enrollment via the functions `mfa_routes.py` calls so the encrypted TOTP secret + hashed recovery codes land in the real storage shape; IT workspace bootstrap + soft-delete/reactivate via the lifecycle engine so the banner snapshot is genuine). Passwords: `secrets.token_urlsafe(16)` each. The recovery code must be captured in plaintext at generation time (the enrollment helper returns it before hashing).

- [ ] **Step 2: Iterate account-by-account with spec-level verification**

Order: platform roles → principal school (+classes/+student) → parent → IT accounts → MFA/banner account. After each account, verify with a direct login round-trip:

```bash
cd backend && ENVIRONMENT=development CI_E2E_SEED=1 DATABASE_URL="$CI_DB_URL" python scripts/seed_ci_e2e.py
curl -s -X POST localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"<seeded>","password":"<seeded>"}' | head -c 200
```

Expected: 200 + token payload per account (MFA accounts: MFA-challenge response instead).

- [ ] **Step 3: Idempotency check** — run the seed twice against the same DB; second run must not crash (skip-or-recreate, either is fine, but deterministic).

### Task 7: Canonical E2E gate script

**Files:**
- Create: `scripts/ci/e2e_tests.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Canonical E2E gate. Production-shaped: builds the frontend, lets the backend
# serve it same-origin (backend/app/routes.py mounts frontend/build), seeds CI
# fixtures, runs the full Playwright suite against http://localhost:8000.
#
# Contract: DATABASE_URL = DISPOSABLE database, already migrated OR empty
# (script migrates). Node deps + playwright chromium must be installed.
set -euo pipefail

: "${DATABASE_URL:?e2e gate: DATABASE_URL must be set to a DISPOSABLE database}"
export ENVIRONMENT=development
export SECRET_KEY="${SECRET_KEY:-ci-only-dummy-secret-key}"
export ALGORITHM="${ALGORITHM:-HS256}"
export APP_URL="http://localhost:8000"
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
( cd "$ROOT/backend" && uvicorn server:app --host 0.0.0.0 --port 8000 ) &
BACKEND_PID=$!
for i in $(seq 1 60); do
  curl -sf http://localhost:8000/api/health >/dev/null 2>&1 && break
  curl -sf http://localhost:8000/ >/dev/null 2>&1 && break
  [ "$i" = 60 ] && { echo "e2e gate: backend failed to boot"; exit 1; }
  sleep 1
done

echo "==> [e2e gate] seed CI fixtures"
CI_E2E_ENV_FILE=/tmp/ci_e2e.env
( cd "$ROOT/backend" && CI_E2E_SEED=1 CI_E2E_ENV_FILE="$CI_E2E_ENV_FILE" python scripts/seed_ci_e2e.py )
set -a; source "$CI_E2E_ENV_FILE"; set +a

echo "==> [e2e gate] playwright"
( cd "$ROOT/frontend" && E2E_BASE_URL="http://localhost:8000" npx playwright test )

echo "==> [e2e gate] PASS"
```

- [ ] **Step 2: Verify the health endpoint used in the wait loop actually exists** (`grep -rn "health" backend/app/routes.py backend/routes/monitoring_routes.py | head`) and adjust the curl path to a real, unauthenticated 200 route.

- [ ] **Step 3: Run locally end-to-end** against the disposable DB from Task 3's pattern. Expected: all 5 spec files pass. Debug failures spec-by-spec (`npx playwright test e2e/auth/post-login-redirect.spec.ts`) — traces land in `frontend/test-results/`.

### Task 8: E2E stabilization (3× green)

- [ ] **Step 1: Run the full E2E gate 3 times consecutively** (fresh DB each run — drop/recreate between runs to prove seed+suite determinism):

```bash
for run in 1 2 3; do
  psql "$ADMIN_URL" -c 'DROP DATABASE IF EXISTS nassaq_ci_e2e;' -c 'CREATE DATABASE nassaq_ci_e2e;'
  DATABASE_URL="$CI_E2E_DB_URL" bash scripts/ci/e2e_tests.sh || echo "RUN $run FAILED"
done
```

Expected: 3× PASS. Any flake → root-cause and fix with condition-based waiting (Playwright `expect` polling / `waitFor` on real conditions), never `waitForTimeout`. Re-run 3× after each fix.

### Task 9: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

env:
  ENVIRONMENT: development
  SECRET_KEY: ci-only-dummy-secret-key
  ALGORITHM: HS256

jobs:
  backend:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: nassaq_ci }
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s
          --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/nassaq_ci
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11', cache: pip, cache-dependency-path: backend/requirements.txt }
      - run: pip install -r backend/requirements.txt
      - run: bash scripts/ci/backend_tests.sh
      - name: Job summary
        if: always()
        run: echo "### Backend gate — see step log for failures" >> "$GITHUB_STEP_SUMMARY"

  frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 'lts/*', cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: cd frontend && npm ci
      - run: bash scripts/ci/frontend_tests.sh

  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: nassaq_e2e }
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s
          --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/nassaq_e2e
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11', cache: pip, cache-dependency-path: backend/requirements.txt }
      - uses: actions/setup-node@v4
        with: { node-version: 'lts/*', cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: pip install -r backend/requirements.txt
      - run: cd frontend && npm ci
      - run: cd frontend && npx playwright install --with-deps chromium
      - run: bash scripts/ci/e2e_tests.sh
      - uses: actions/upload-artifact@v4
        if: failure()
        with: { name: playwright-artifacts, path: |
                frontend/test-results/
                frontend/playwright-report/ }

  security:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: nassaq_sec }
        ports: ['5432:5432']
        options: >-
          --health-cmd "pg_isready -U postgres" --health-interval 5s
          --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5432/nassaq_sec
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11', cache: pip, cache-dependency-path: backend/requirements.txt }
      - run: pip install -r backend/requirements.txt
      - run: pip install pip-audit safety bandit
      - run: cd backend && alembic upgrade head
      - run: bash scripts/ci_security_scan.sh
```

Adjust to reality during implementation: (a) if `scripts/ci_security_scan.sh` expects to run from repo root vs backend, match its cwd contract (read the script header); (b) confirm the security pytest suites need a migrated DB (they do — keep the alembic step); (c) `MFA_ENCRYPTION_KEY` is generated inside the gate scripts, no workflow secret needed.

- [ ] **Step 2: Validate the YAML**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"
npx --yes @action-validator/cli .github/workflows/ci.yml || true   # best-effort schema check
```

Expected: `yaml ok`; action-validator clean or tool-unavailable (note which).

### Task 10: One-command local gate

**Files:**
- Create: `scripts/ci_local.sh`

- [ ] **Step 1: Write the runner**

```bash
#!/usr/bin/env bash
# Local mirror of the CI merge gate. Runs the SAME scripts/ci/* entry points
# the GitHub workflow runs. Usage: scripts/ci_local.sh [backend|frontend|e2e|security|all]
set -euo pipefail
GATE="${1:-all}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

: "${CI_LOCAL_DB_URL:?Set CI_LOCAL_DB_URL to a DISPOSABLE postgres database URL (never the app DB). See docs/ci.md}"

run_backend()  { DATABASE_URL="$CI_LOCAL_DB_URL" bash "$ROOT/scripts/ci/backend_tests.sh"; }
run_frontend() { bash "$ROOT/scripts/ci/frontend_tests.sh"; }
run_e2e()      { DATABASE_URL="$CI_LOCAL_DB_URL" bash "$ROOT/scripts/ci/e2e_tests.sh"; }
run_security() { DATABASE_URL="$CI_LOCAL_DB_URL" bash "$ROOT/scripts/ci_security_scan.sh"; }

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
```

(Note: `all` runs every gate and reports the full verdict rather than stopping at the first failure — one run tells you everything that's red; single-gate mode exits non-zero immediately.)

- [ ] **Step 2: Register validation steps** via the validation skill: `ci-backend`, `ci-frontend`, `ci-e2e`, `ci-security` mapping to `scripts/ci_local.sh <gate>` with `CI_LOCAL_DB_URL` documented as a prerequisite.

- [ ] **Step 3: Verify** `bash scripts/ci_local.sh frontend` runs the frontend gate end-to-end.

### Task 11: §11 gate validation — drag-and-drop + red-path evidence

**Files:**
- Read: `frontend/src/pages/TeacherClassAssignmentPage.jsx` (the class-to-teacher drag-and-drop surface), its tests if any
- Maybe create: `frontend/src/pages/__tests__/TeacherClassAssignmentPage.regression.test.jsx`

- [ ] **Step 1: Trace the incomplete refactor**

```bash
git log --oneline -10 -- frontend/src/pages/TeacherClassAssignmentPage.jsx
grep -rln "TeacherClassAssignment" frontend/src --include="*.test.*"
```

Determine what "incomplete" means concretely (unfinished handler? dead code path? missing persistence?) and whether any existing jest/E2E test exercises the flow.

- [ ] **Step 2: Close the coverage gap if one exists** — if no test covers the drag-assignment happy path, add a component test in the same harness style as Task 5 (stable mocks, `@dnd-kit` interaction via keyboard-activation or direct handler invocation like `StudentClassGrid.transfer.test.jsx` does). If the flow is genuinely broken mid-refactor, do NOT fix the feature (out of scope) — document in the validation report which gate WILL catch it when the refactor lands with tests.

- [ ] **Step 3: Red-path demonstration (evidence, not claims)** — three deliberate breaks, each: introduce → run the relevant gate → confirm RED → revert → confirm GREEN:
  1. Grid regression: flip the Task 5 fixture assertion target (or comment out the session-render branch) → frontend gate red.
  2. Schema drift: add a throwaway column to a model in `backend/pg_models.py` without a migration → backend gate red (drift test).
  3. Security: add a temporary `verify=False`-style bandit trigger or an unscoped tenant lookup in a route file → security gate red.

  Capture each red output snippet into the validation report section of `docs/ci.md`. `git diff` must be empty after this step.

### Task 12: Branch protection handoff + docs

**Files:**
- Create: `scripts/ci/setup_branch_protection.sh`
- Create: `docs/ci.md`
- Modify: `replit.md`

- [ ] **Step 1: Write the protection script (runs with the OWNER's token, not in CI)**

```bash
#!/usr/bin/env bash
# One-time setup, run by the repo owner: enables branch protection on main
# requiring the 4 CI jobs. Needs: GITHUB_TOKEN with repo admin on
# ahmadzalat44/NASSAQ_Jul_26. NOTE: required checks on a PRIVATE repo need
# GitHub Pro/Team (or make the repo public).
set -euo pipefail
: "${GITHUB_TOKEN:?export GITHUB_TOKEN=<personal access token with repo admin>}"
REPO="${1:-ahmadzalat44/NASSAQ_Jul_26}"

curl -sf -X PUT \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$REPO/branches/main/protection" \
  -d '{
    "required_status_checks": {"strict": true, "contexts": ["backend", "frontend", "e2e", "security"]},
    "enforce_admins": true,
    "required_pull_request_reviews": null,
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false
  }'
echo "Branch protection enabled on $REPO main"
```

- [ ] **Step 2: Write `docs/ci.md`** — sections: pipeline overview (4 jobs, what each runs); canonical commands table (gate → script → local command); reproducing a CI failure locally (incl. creating a disposable DB and `CI_LOCAL_DB_URL`); quarantine policy (link `docs/ci/quarantine.md`); one-time GitHub setup (push `main`, run the protection script, click-path alternative, the Pro-plan caveat); known gaps (no typecheck gate — `mypy`/`npm run typecheck` do not exist; E2E covers 5 spec files, not the whole product); §11 validation report (evidence from Task 11 Step 3).

- [ ] **Step 3: Update `replit.md`** — in Run & Operate add: `**CI gate (local)**: scripts/ci_local.sh [backend|frontend|e2e|security|all] — same scripts GitHub Actions runs; see docs/ci.md`. Remove/replace the phantom `mypy backend/` and `npm run typecheck` lines with a note that no typecheck gate exists yet (documented gap in docs/ci.md).

### Task 13: Final verification sweep

- [ ] **Step 1:** Full local gate: `bash scripts/ci_local.sh all` (via validation skill; long-running). Expected: `GATE VERDICT: GREEN`.
- [ ] **Step 2:** Confirm no credential material leaked into the repo: `git grep -l "token_urlsafe\|E2E_.*=" -- ':!docs' ':!frontend/e2e' ':!scripts' ':!backend/scripts/seed_ci_e2e.py'` returns nothing unexpected; `/tmp/ci_e2e.env` is outside the repo; `.gitignore` covers `frontend/test-results/`, `frontend/playwright-report/`.
- [ ] **Step 3:** Architect code review of the whole change set (`includeGitDiff: true`), fix severe findings.
- [ ] **Step 4:** Hand the user the one-time GitHub checklist (push, protection script, Pro caveat).

---

## Self-review notes (writing-plans checklist)

- **Spec coverage:** backend gate (T3), frontend gate (T4+T5), e2e gate (T6–T8), security gate (T9 security job), merge protection (T12), local mirror + ergonomics (T10, T12), baseline honesty (T1–T2), §11 validation (T5, T11), acceptance evidence (T11, T13). Typecheck gap handled in T12 docs. No spec section uncovered.
- **Placeholder scan:** T1 root-cause outcome and T6 seed internals are investigation-dependent by nature; both specify exact commands, exact files to read, decision rules, and verification criteria rather than "TBD".
- **Consistency:** job names in workflow (`backend/frontend/e2e/security`) match the protection-script contexts; `CI_E2E_ENV_FILE`/`CI_E2E_SEED` names match between seed script and e2e gate; `CI_LOCAL_DB_URL` consistent across T10/T12.
