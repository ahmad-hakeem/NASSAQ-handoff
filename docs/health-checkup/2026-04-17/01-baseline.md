# Phase 0 — Stabilize & Baseline

**Date:** 2026-04-17
**Status:** ✅ Complete

## Inventory

| Item | Count / Size |
|---|---|
| Backend route modules (`backend/routes/`) | 66 |
| Frontend pages (`frontend/src/pages/`) | 55 |
| Frontend top-level components | 22 |
| Alembic migrations | 18 |
| `backend/server.py` LOC | 145 |
| `frontend/node_modules` | 2.3 GB |
| Root `node_modules` | 4.1 MB |

## Live data snapshot (from startup log)

- Users: **734**
- Schools: **7**
- Students: **511**
- Teachers: **215**

## Runtime baseline

- Backend startup: ~1 s (PostgreSQL, Alembic revision `m1n2o3p4q5r6` verified)
- Sample request times: `/` 15.5 ms · `/api/public/contact-info` 34.8 ms · `/api/public/stats` 82.6 ms · static images 8–18 ms
- Approval engine: 2 handlers registered (`teacher`, `school`)
- Connection-pool monitor running (60 s interval)

## Findings (Phase 0)

| ID | Severity | Finding |
|---|---|---|
| P0-01 | **High (reliability)** | Both workflows started in a broken state because **stale processes from previous sessions held ports 8000 and 5000**. Required manual kill + restart. No automated port-cleanup or “prestart” safety in workflow commands. |
| P0-02 | **Medium (docs drift)** | `replit.md` describes the system as MongoDB-based, but the running backend is **PostgreSQL with Alembic** (`backend/db.py`, `pg_models.py`, `alembic/`). All future doc edits and audit assumptions must use PostgreSQL. |
| P0-03 | **Info** | Backend serves static frontend assets and images itself (`/static/...`, `/hakim-poses/...`, `/images/...`). Acceptable in dev, but Phase 1 will assess production caching headers and consider offloading. |
| P0-04 | **Info** | Production-scale data (734 users, 511 students) is present in the dev database — good for realistic perf testing, but means destructive operations are extra risky. Stop-condition rule applies. |

## Action items carried into later phases

- P0-01 → fix in **Phase 5** (workflow command + a small `scripts/free_ports.sh`)
- P0-02 → fix in **Phase 5** (rewrite the DB section of `replit.md`)
- P0-03 → assess in **Phase 1**, decide in Phase 5
- P0-04 → no action; reinforces the stop-condition

## Gate

✅ Phase 0 complete. Ready for **Phase 1 — Backend Audit** on user approval.
