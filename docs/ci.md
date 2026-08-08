# CI Pipeline

## Overview

Four GitHub Actions jobs run on every pull request and every push to `main`
(`.github/workflows/ci.yml`). All four are required merge checks once branch
protection is enabled (see "One-time GitHub setup").

| Job | What it runs |
| --- | --- |
| `backend` | Fresh Postgres → `alembic upgrade head` → full backend pytest suite (`scripts/ci/backend_tests.sh`) |
| `frontend` | `npm ci` → CRA jest suite via `react-scripts test` (`scripts/ci/frontend_tests.sh`) |
| `e2e` | Fresh Postgres → migrate → seed (`backend/scripts/seed_ci_e2e.py`) → build FE → boot backend → Playwright specs (`scripts/ci/e2e_tests.sh`) |
| `security` | Token-storage + tenant-scoped-lookup chokepoints, security pytest phases 1–3, `pip-audit`, `safety`, `bandit` high-severity SAST (`scripts/ci_security_scan.sh`) |

## Canonical commands

Local runs use the SAME scripts CI runs, via one wrapper:

| Gate | Script | Local command |
| --- | --- | --- |
| backend | `scripts/ci/backend_tests.sh` | `scripts/ci_local.sh backend` |
| frontend | `scripts/ci/frontend_tests.sh` | `scripts/ci_local.sh frontend` |
| e2e | `scripts/ci/e2e_tests.sh` | `scripts/ci_local.sh e2e` |
| security | `scripts/ci_security_scan.sh` | `scripts/ci_local.sh security` |
| all | — | `scripts/ci_local.sh all` (prints `GATE VERDICT: GREEN/RED`) |

In the Replit workspace, the `ci-backend` / `ci-frontend` / `ci-e2e` /
`ci-security` workflows wrap the same wrapper via
`scripts/ci/run_gate_local.sh <gate>` (it provisions the disposable DB URL).

## Reproducing a CI failure locally

1. Create a DISPOSABLE database — never point the gates at the app
   `DATABASE_URL` (in this workspace that is the real production DB):

   ```bash
   psql "$DATABASE_URL" -c 'CREATE DATABASE ci_local_gate;'
   export CI_LOCAL_DB_URL="<same URL with dbname replaced by ci_local_gate>"
   ```

2. Run the failing gate: `scripts/ci_local.sh backend` (or
   `frontend|e2e|security|all`). The backend gate migrates the disposable DB
   from scratch, so schema drift and missing migrations reproduce exactly.

3. E2E: seeded credentials are written to `/tmp/ci_e2e.env` (outside the
   repo); the gate boots its own backend on `E2E_PORT` (default 8100).

## Quarantine policy

Known-red tests are skipped with a dated reason and tracked in
`docs/ci/quarantine.md`. A quarantine entry is a debt item, not a fix —
each entry names the product gap or contract conflict that must be resolved
before the skip is removed. Never quarantine a test to make an unrelated PR
green.

## One-time GitHub setup (repo owner)

1. Push the workspace to `main` of `ahmadzalat44/NASSAQ_Jul_26`.
2. Let the first CI run complete so the four job names exist as checks.
3. Enable protection: `export GITHUB_TOKEN=<PAT with repo admin>` then
   `bash scripts/ci/setup_branch_protection.sh` — or via the UI:
   Settings → Branches → Add branch protection rule → branch `main` →
   "Require status checks to pass" → select `backend`, `frontend`, `e2e`,
   `security` → "Require branches to be up to date" → "Include administrators".
4. Caveat: required status checks on a PRIVATE repo need GitHub Pro/Team
   (or make the repo public); otherwise the rule saves but is not enforced.

## Known gaps

- **No typecheck gate.** `mypy backend/` and `npm run typecheck` do not exist
  in this project; the `replit.md` lines that referenced them were removed.
  Adding mypy/tsc gates is future work.
- **E2E covers 5 spec files** (auth + core flows), not the whole product.
- Security gate hard-fails only on HIGH-severity bandit findings; the current
  Medium/Low findings (23/168) are visible in the log but non-blocking.

## §11 gate validation (red-path evidence, 2026-07-25)

Each gate was proven to actually catch its class of regression by
introducing a deliberate break, observing RED, then reverting to GREEN:

**Break 1 — grid regression (frontend gate RED):**
```
FAIL src/pages/__tests__/SchedulePageNew.gridRender.test.jsx
  Unable to find an element with the text: /رياضيات/.
Tests: 1 failed, 1 skipped, 590 passed, 592 total
```

**Break 2 — ORM column without migration (backend gate RED):**
```
UndefinedColumnError: column "ci_redpath_demo_column" of relation "audit_logs" does not exist
25 failed, 277 passed, 154 skipped (fail-fast)
```

**Break 3 — `requests.get(verify=False)` (security gate RED):**
```
>> Issue: [B501:request_with_no_cert_validation] ... Severity: High
   Location: backend/routes/monitoring_routes.py:775:11
Security gate FAILED — fix the issues above before merging.
```

All three breaks were reverted; all gates re-confirmed GREEN on the clean
tree (backend: 2121 passed / 915 skipped; security: PASSED).
