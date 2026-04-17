# NASSAQ Full-Stack Health, Performance, Speed & Reliability Checkup — Design

**Date:** 2026-04-17
**Owner:** Main agent + user checkpoints
**Cycle type:** Full cycle — audit → fix → verify
**Severity bar:** Fix everything (Critical → High → Medium → Low → Polish)
**Mode of operation:** Phased with user checkpoints between phases

---

## Phases

| # | Phase | Deliverable |
|---|---|---|
| 0 | Stabilize & Baseline | `01-baseline.md` |
| 1 | Backend Audit (FastAPI, auth, WebSockets, jobs, security headers, secrets, integrations) | `02-backend-audit.md` |
| 2 | Database Audit (PostgreSQL: schema vs models, indexes, slow queries, orphans, migrations) | `03-db-audit.md` |
| 3 | Frontend Audit (bundle, render perf, console errors, i18n parity, RTL, a11y, network) | `04-frontend-audit.md` |
| 4 | E2E Reliability per role (platform_admin, school_admin, school_sub_admin, teacher, student, parent, platform_operations_manager) covering login, attendance, grading, assignments, parent portal, notifications, file uploads, analytics, settings | `05-e2e-report.md` |
| 5 | Fix everything found, in safe batches | `06-fix-log.md` |
| 6 | Re-verify (re-run Phases 1–4) and produce before/after report | `07-final-health-report.md` |

## Stop conditions (escalate to user)

- Destructive change required (data migration, schema rename)
- Missing third-party secret/integration credential
- Fix risks breaking a stable flow with no clear rollback

## Reports location

`docs/health-checkup/2026-04-17/`
