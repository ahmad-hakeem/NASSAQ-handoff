# CI Pipeline Design — Merge Gate for NASSAQ

**Date:** 2026-07-25
**Status:** Approved by user (design phase); spec pending user review
**Source task:** `attached_assets/Pasted-Objective-Design-and-implement-a-complete-continuous-in_1784989966934.txt` (starting point, not strict plan)

## Objective

Every proposed change is automatically validated before merge by running the full backend
test suite, the full frontend test suite, the existing E2E suite, and the existing security
scan. Any failure blocks the merge. Green means shippable; red is meaningful.

## Current state (audit findings)

Already runnable, but wired to nothing:

| Area | What exists | Entry point |
|---|---|---|
| Backend tests | 277 pytest files, transaction-isolated against real Postgres via `DATABASE_URL` | `pytest backend/tests` |
| Structural guards | Schema-drift test, destructive-migration guard | `backend/tests/test_schema_orm_drift.py`, `backend/tests/test_migration_destructive_ops_guard.py` |
| Frontend tests | ~46 jest test dirs incl. CRACO/webpack-dev-server shim test | `react-scripts test` via craco |
| E2E | 9 Playwright specs in `frontend/e2e/` (auth, management); `frontend/playwright.config.ts`, baseURL `http://localhost:5000` | `cd frontend && npm run test:e2e` |
| Security scan | `scripts/ci_security_scan.sh`: token-storage sentinel, tenant-isolation sentinel, 3 security pytest suites, pip-audit, safety, bandit | `bash scripts/ci_security_scan.sh` |

Gaps:

- No `.github/` directory, no CI workflows, no merge gate of any kind.
- Only local wiring is one pre-commit hook (tenant-lookup check) — skippable.
- `replit.md` documents `mypy backend/` and `npm run typecheck`, but neither command exists
  (no mypy config; no `typecheck` script in `frontend/package.json`). Documentation bug.
- 13 pre-existing failing backend tests (11 across two workspace-lifecycle suites —
  archived-workspace auth issue — plus 2 known-gap homework_mode tests).
- Backend tests need a real Postgres; CI must provision one.

Constraints:

- GitHub repo `ahmadzalat44/NASSAQ_Jul_26` (`origin`) is **private** and currently **empty**
  (no branches pushed).
- The Replit-connected GitHub credential is a different account (`ahmad-hakeem`) with no
  access to that repo. Agent can author everything in-repo; the one-time push and
  branch-protection setup must be executed with the owner's credentials.
- Required status checks on a private repo need GitHub Pro/Team (or a public repo). The
  workflow runs on the free plan regardless; only enforced blocking needs the plan.

## Decisions made with user

1. **Gate location: both.** GitHub Actions blocks PR merges; an identical one-command local
   gate runs inside Replit.
2. **Approach A** (chosen over Replit-only and staged/nightly variants): one workflow, four
   parallel required jobs, full coverage at the merge gate — no downgrading.
3. **Pre-existing red tests:** investigate first; fix cheap ones, quarantine only genuinely
   deep ones with a tracked list.
4. **§11 regression targets:**
   - Timetable grid rendering after AI generation (`SchedulePageNew.jsx`) — currently
     working; add a regression test to lock it.
   - Incomplete class-to-teacher drag-and-drop assignment refactor — validate the gate
     against it; if impractical to simulate, fall back to known regression classes from
     project history.

## Design

### 1. Architecture

- `.github/workflows/ci.yml`, triggered on every pull request and every push to `main`.
- Four parallel jobs, all configured as required status checks: `backend`, `frontend`,
  `e2e`, `security`.
- **Single source of truth for commands:** each gate lives in a script under `scripts/ci/`:
  - `scripts/ci/backend_tests.sh`
  - `scripts/ci/frontend_tests.sh`
  - `scripts/ci/e2e_tests.sh`
  - security gate: existing `scripts/ci_security_scan.sh`
  The workflow YAML and the local runner (`scripts/ci_local.sh`) both invoke these same
  scripts. Reproducing a CI failure locally = running the same file.
- Pinned runtimes in CI: Python 3.11, Node latest LTS, Postgres 16. Dependency caching
  (pip + npm) for speed; pins/lockfiles control versions, cache only accelerates.

### 2. Backend gate (`backend` job)

- Services: fresh Postgres 16 container per run. Never touches any real database.
- Steps: install backend deps → `alembic upgrade head` against the empty DB →
  `pytest backend/tests` (full suite; includes schema-drift test and destructive-migration
  guard by virtue of living in the suite).
- Side benefit: every PR proves migrations apply cleanly to a fresh database — the
  workspace (which runs against a long-lived prod DB) never exercises this path.
- Environment: CI-only dummy secrets (`SECRET_KEY`, `ALGORITHM`, generated
  `MFA_ENCRYPTION_KEY`, `DATABASE_URL` pointing at the service container),
  `ENVIRONMENT=development`. No production secrets in CI, ever.
- **Baseline triage (precondition for gate activation):** root-cause the 13 pre-existing
  failures per systematic-debugging discipline. Fix what is cheap; quarantine what is deep
  using `pytest.mark.skip(reason="quarantined: <link>")` and record each entry in
  `docs/ci/quarantine.md` (test id, failure mode, root-cause note, follow-up owner).
  The gate must start green and honest.

### 3. Frontend gate (`frontend` job)

- `CI=true npx react-scripts test --watchAll=false` via the canonical script (never raw
  jest — runner-specific transform config).
- Production build check: `CI=false npm run build` so build breakage cannot merge.
- New regression test: render `SchedulePageNew` with a realistic mocked AI-generation
  timetable payload; assert the grid renders sessions (session cells present, no empty-grid
  fallback). Locks in the §11 timetable-grid behavior.

### 4. E2E gate (`e2e` job)

- Steps: build frontend → start backend (uvicorn) against the CI Postgres →
  seed deterministic CI fixtures → serve the frontend on port 5000 → run all Playwright
  specs headless (`npm run test:e2e`).
- CI fixtures: a dedicated CI seed script creating the minimal tenant/users/classes the
  specs need, with credentials defined by the seed itself. `TEST_CREDENTIALS.md` is never
  used in CI. Existing seed-blocking rules are unaffected: CI runs as
  `ENVIRONMENT=development`.
- Stabilization: run the suite 3× consecutively during implementation; fix any flake with
  condition-based waiting (no arbitrary timeouts) before the gate activates. E2E is
  blocking, per the task file.
- Artifacts: Playwright traces/screenshots uploaded on failure.

### 5. Security gate (`security` job)

- Runs `scripts/ci_security_scan.sh` unchanged in behavior: token-storage chokepoint,
  tenant-scoped lookup chokepoint, security pytest suites (phase 1–3), `pip-audit`,
  `safety`, `bandit` (high severity).
- CI image installs pip-audit, safety, and bandit explicitly, so the script's
  "not installed = FAIL" contract holds.
- The security pytest suites need the same Postgres service the backend job uses; the job
  provisions its own service container.

### 6. Merge protection

- Branch protection on `main` in `NASSAQ_Jul_26`: the four job names required, strict
  up-to-date mode, no force pushes, applies to admins (no bypass for normal flow).
- Because the agent's connected GitHub credential cannot access the repo, deliverables are:
  1. Everything authored in-repo (workflow, scripts, docs) so it rides the next push.
  2. `scripts/ci/setup_branch_protection.sh` — one-time script the owner runs with their
     own token to enable protection exactly as specified.
  3. Equivalent click-path instructions in `docs/ci.md`.
- Open caveat (user decision, later): private repo requires GitHub Pro for enforced
  required checks; alternatives are making the repo public or accepting advisory-only
  checks until upgraded.

### 7. Local mirror & developer ergonomics

- `scripts/ci_local.sh [backend|frontend|e2e|security|all]` — runs the same `scripts/ci/`
  entry points. Documented as the canonical pre-push command.
- Registered as named validation steps in the Replit workspace so gates can be run and
  monitored from here.
- Each CI job emits a GitHub job summary (failed test names, scan findings) for at-a-glance
  PR feedback.
- `docs/ci.md`: canonical commands, local reproduction guide, quarantine policy,
  branch-protection setup.
- `replit.md` updates: CI section; correct the phantom `typecheck` commands (documented
  explicitly as a gap, not silently deleted).

### 8. §11 gate validation

- Timetable grid: the new regression test (section 3) plus existing E2E coverage.
- Drag-and-drop class-to-teacher assignment: trace the incomplete refactor; identify which
  gate catches a break in that flow; add a targeted test if coverage is missing. If
  simulation is impractical, demonstrate — with evidence, not claims — that the gate
  catches known regression classes (schema drift, tenant-isolation break, dependency CVE,
  security-test regression).

## Error handling

- Any gate script failure = job failure = merge blocked. No `continue-on-error` on required
  jobs.
- Missing tooling in CI fails loudly (security script contract; same principle applied to
  the new scripts).
- E2E boot failures (backend not up, seed failure) fail the job with the boot log attached,
  distinguishable from spec failures.
- Local runner exits non-zero on first failing gate with a clear per-gate verdict line.

## Testing the pipeline itself

- Workflow YAML validated locally (actionlint or equivalent syntax check) before delivery.
- Each `scripts/ci/*.sh` executed successfully in the Replit workspace as the local-mirror
  proof (backend script pointed at a disposable DB where applicable).
- E2E stability: 3 consecutive green runs locally.
- Evidence of red-path behavior: deliberately failing invocation (e.g. running a gate
  against a synthetic failing test) to show non-zero exit and correct verdict output.

## Out of scope

- mypy adoption / introducing a real backend typecheck gate.
- New E2E coverage beyond the specs that exist plus §11 targets.
- Fixing quarantined tests (tracked follow-up).
- GitHub plan changes / repo visibility decision.
- Nightly or scheduled pipelines.

## Acceptance criteria

| Area | Outcome |
|---|---|
| Backend | Full suite + structural guards run in CI on every PR; failures block merge. |
| Frontend | Full jest suite + build check run in CI; failures block merge. |
| E2E | All Playwright specs run in CI against a seeded, ephemeral environment; failures block merge. |
| Security | `ci_security_scan.sh` runs on every PR with all tools installed; failures block merge. |
| Merge safety | Branch protection config delivered (script + docs); once owner enables it, no unchecked merge path remains. |
| Determinism | Fresh DB per run, pinned runtimes, no reliance on workspace state or secrets. |
| Ergonomics | One local command reproduces any CI failure; PR job summaries; `docs/ci.md`. |
| Honesty | Pre-existing failures fixed or quarantined with a tracked list before activation; green baseline demonstrated. |
