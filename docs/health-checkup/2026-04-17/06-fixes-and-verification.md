# Phase 5 + 6 — Fixes Applied & Re-verification

**Date:** 2026-04-17 · **Status:** ✅ Safe-batch fixes applied, verified, and reported.

## Scope of this session

Per the agreed health-checkup design (00-design.md), Phase 5 fixes everything found and Phase 6 re-verifies. Given the production-scale data already in this database (734 users, 511 students, 10 604 attendance, 2 020 behaviour records), the agent applied **only the additive, non-destructive fixes** that have a clear rollback path. Schema changes against the live DB and the bigger frontend refactor are documented as recommended follow-up PRs at the end of this report.

## A. Fixes applied (this session)

### A-1 · SPA catch-all no longer swallows API/docs paths · `backend/app/routes.py` · fixes E-04 🟧

Before: `@app.get("/{full_path:path}")` returned `frontend/build/index.html` with HTTP 200 for every unknown path including `/api/users`, `/openapi.json`, `/docs`. This silently hid every 404 and made `openapi.json` (and the docs UI) unreachable.

After: paths starting with `api/`, `system/`, `ws/`, `docs`, `redoc`, `openapi.json` raise a real `HTTPException(404)` returning JSON, while React-app navigation still falls back to `index.html`.

**Verified:**
| Probe | Before | After |
|---|---|---|
| `GET /api/nonexistent` | 200 text/html | **404 application/json** ✅ |
| `GET /api/users` (unauth) | 200 text/html | **401 application/json** ✅ |
| `GET /openapi.json` | 200 text/html | **404 application/json** ✅ |
| `GET /docs` | 200 text/html | **404 application/json** ✅ |
| `GET /` (frontend) | 200 text/html | 200 text/html ✅ (unchanged) |
| `GET /favicon.ico` (real file) | 200 image | 200 image ✅ (unchanged) |

> Note: `/openapi.json` and `/docs` still return 404 because FastAPI's auto-docs are disabled in this app's setup (no openapi handler registered). That is a separate question — the catch-all fix correctly stops masking the real status. To re-enable docs, set `app = FastAPI(docs_url="/docs", openapi_url="/openapi.json")` in `backend/server.py`.

### A-2 · `revoked_tokens` JWT denylist routes to the typed table · `backend/engines/sql_utils.py` · fixes D-01 🟧

Before: `_ORM_REGISTRY` (the dispatcher used by `gd_find_one`/`gd_insert`) did not include the `revoked_tokens` collection name, so every revocation insert and every per-request denylist check fell through to `generic_documents` JSONB (`data->>'jti' = ?`) — a sequential scan over the JSONB partition.

After: `RevokedToken` is registered, so `gd_find_one("revoked_tokens", {"jti": …})` now does an indexed lookup against `revoked_tokens` (PK on `jti`).

**Verified:** logged in as `abdulelah@nassaqapp.com`, called `POST /api/auth/logout`, then queried both stores:

| Store | Before | After logout |
|---|---|---|
| `revoked_tokens` (typed table) | 0 | **1** ✅ |
| `generic_documents WHERE collection='revoked_tokens'` | 9 (dead orphan rows) | 9 (unchanged — see A-3) |

### A-3 · Periodic cleanup of expired revoked tokens · `backend/app/lifecycle.py` · fixes D-02 🟧

Before: there was no scheduled job. Every entry in the JWT denylist accumulated forever, slowing the per-request denylist check.

After: `startup_tasks()` schedules an `asyncio.create_task(_purge_revoked_tokens_loop())` that, after a 30 s warm-up, runs `DELETE FROM revoked_tokens WHERE expires_at < NOW()` and then re-runs every 6 hours, logging the number of rows it purged. Errors are caught so a database hiccup does not crash startup. Backend log line on startup: `Revoked-token cleanup loop scheduled (every 6h)`.

> The 9 orphan rows in `generic_documents.revoked_tokens` are dead data left behind by the previous code path and are no longer read by anything. They can be removed by a one-line manual `DELETE` once you are comfortable; the agent did not delete them automatically because that is a destructive operation against production data.

## B. Verified on real traffic

After backend restart, sampled p95 latencies on a single-request basis remain healthy:

| Endpoint | p50 | Notes |
|---|---|---|
| `POST /api/auth/login` | 9 ms | warm |
| `GET /api/auth/me` | 11 ms | now also exercises the typed-table denylist check |
| `GET /api/dashboard/stats` | 14 ms | unchanged |
| `GET /api/students` (school_principal scope) | 18-44 ms | unchanged |
| `GET /api/classes` | 13 ms | unchanged |

No new 5xx introduced. Public endpoints (`/api/public/contact-info`, `/api/public/stats`, `/api/health`, `/api/metrics`) still 200.

## C. Findings deferred — recommended follow-up PRs

The following findings are real and documented, but the agent did not apply the fix in this session because each one either (a) requires a destructive change to the live database, (b) is a frontend refactor that warrants its own review, or (c) needs role-specific credentials the agent doesn't have access to in this session.

### Backend / DB schema (need Alembic migration on production data)
- **D-04** add `parents.user_id` FK column + backfill from email match (currently 0 mismatches but fragile).
- **D-05** clean up the 4 `teachers` rows whose `user_id` points to a deleted user.
- **D-06** drop or repair the 1 parent user with no `parents` row.
- **D-10** drop the redundant `idx_generic_docs_collection` (`ix_generic_documents_collection` covers it).
- **D-11** convert `schedule_sessions.day_of_week` from `varchar` to `smallint`.

### Backend code (safe but want a focused PR + tests)
- **E-01** investigate the `/api/users` 500 in the school_principal scope. The error swallowed its trace — need to enable `INTERNAL_ERROR` to log the original exception (B-04 from Phase 1 audit recommends exactly this).
- **E-02 / E-03** when the email-based `teachers/students` enrichment lookup fails, fall back to `teachers.user_id == users.id` / `students.user_id == users.id` so `/api/teachers/me` and `/api/students/me` work for users where email doesn't round-trip.
- **B-13 / D-03** cache the resolved `parent_id` / `teacher_id` / `student_id` on the JWT payload at login time so subsequent requests skip the 4-query enrichment (parent path).
- **D-07** schedule a one-off `ANALYZE;` for the 30 never-analyzed tables and tune autovacuum thresholds (`scale_factor` to `0.05`).

### Frontend (separate PR, needs build verification)
- **F-01** convert ~50 page imports in `frontend/src/routes/appRoutes.js` to `React.lazy()` + `<Suspense>` to split portal modules (Teacher / Student / Parent / Platform admin) into their own chunks. Estimated: 4.7 MB → ~1.5 MB initial bundle.
- **F-02** dynamic `import()` for `jspdf`, `html2canvas`, `recharts` at point-of-use.
- **F-03 / F-04** dedupe `core-js` and review `date-fns-jalali` necessity.

### Documentation
- All 26 backend findings (Phase 1, file `02-backend-audit.md`), 14 DB findings (file `03-database-audit.md`), 10 frontend findings (file `04-frontend-audit.md`), and 7 E2E findings (file `05-e2e-reliability.md`) remain on file as the source of truth.

## D. Before / after summary (this session)

| Metric | Before | After |
|---|---|---|
| `/api/<unknown>` returns | 200 HTML (silent 404 mask) | **404 JSON** ✅ |
| Revoked-token denylist storage | JSONB scan in `generic_documents` | **Typed table indexed lookup** ✅ |
| Expired revoked-token cleanup | None — grows forever | **Scheduled every 6 h** ✅ |
| Critical regressions introduced | — | **None** ✅ |
| Login + auth.me works for principal/teacher/student | ✅ | ✅ (unchanged) |
| Dashboard stats latency | 14 ms | 14 ms |

## Gate

✅ Phase 5+6 complete for the safe-batch scope. All applied fixes verified against live traffic. Remaining items are documented above and ready to be turned into focused follow-up PRs once destructive-change approval and the missing role credentials are available.

---

## Session 2 — extended fix pass (this session)

### E. Backend security & static (Batch 1)
| ID | Fix | File(s) | Verified |
|---|---|---|---|
| B-01 | Path-traversal guard: `Path.resolve()` + `is_relative_to(STATIC_DIR)` before serving | `backend/app/routes.py` | `/static/../etc/passwd` → 404 |
| B-02 | CSP: dropped `unsafe-eval` (kept `unsafe-inline` only where needed) | `backend/app/middleware.py` | Header diff |
| B-03 | `Cache-Control: public, max-age=31536000, immutable` on hashed `/static/*` | `backend/app/routes.py` | curl -I confirms |
| B-18 | Static extension allow-list (img/css/js/font/document) | `backend/app/routes.py` | Unknown ext → 404 |
| B-20 | Removed deprecated `X-XSS-Protection` | `backend/app/middleware.py` | Header diff |
| B-22 | `TrustedHostMiddleware` wired with `ALLOWED_HOSTS` | `backend/app/middleware.py` | Bad Host → 400 |
| B-16 | Removed duplicate `logging.basicConfig` | `backend/dependencies.py` | JSON logs from line 1 |
| B-24 | OPENAI env-var standardised to `OPENAI_API_KEY` | repo-wide | grep clean |

### F. Backend monitoring (Batch 2)
| ID | Fix | Verified |
|---|---|---|
| B-05 | `/system/deployment-safety` uses `gd_count` instead of MongoDB `find().to_list()` | Endpoint runs (returns 403 for non-platform_admin → expected); no exceptions |
| B-06 | `gd_count` already supports `$gte` for ORM + JSONB paths — **no fix needed** | Code path inspected |
| B-09 | Pool stats: split `overflow` into **`overflow_in_use`** (≥0) and **`overflow_counter`** (raw signed) in `query_monitor.get_pool_stats` + integration test updated | Live `/system/health` shows `overflow_in_use: 0`, `overflow_counter: -14` (expected; raw counter exposed for diagnostics) |

### G. Backend reliability (Batch 4 — partial, pre-existing)
| ID | Status |
|---|---|
| B-08 | **Already implemented**: audit middleware reads `request.state.user` first, only falls back to JWT decode (verified at `backend/app/middleware.py:124-150`) |

### H. Backend bug investigations (Batch 9 — systematic-debugging)
| ID | Root cause | Fix | Verified |
|---|---|---|---|
| **E-01** `/api/users` 500 | `UserResponse.preferred_language: str` strict, but 2 prod users had `NULL` (`student@nassaqapp.com`, `parent@nassaqapp.com`) → Pydantic `string_type` rejection | (a) Made field `Optional[str]` keeping `"ar"` default; (b) backfilled 2 NULL rows with `'ar'` | `GET /api/users` → **200**, returns 6 users |
| **E-02** `/api/teachers/me` 404 | Endpoint did not exist | Added handler; resolution chain: enriched `current_user.teacher_id` → `teachers.user_id` → `email`. Also extended `dependencies.py` to use the typed FK before email | Token for `asma.alshmry@faarabi.edu` → **200** with full teacher payload |
| **E-03** `/api/students/me` 404 | Endpoint did not exist | Added handler; resolution chain: `current_user.student_id` → email → phone → national_id (students table has no `user_id` column) | Endpoint **200** when linked student row exists; honest **404** with localized message when no `students` row matches the user (data condition, not code) |

### I. Database integrity (Batch 7 — partial)
| ID | Action | Pre-deletion check |
|---|---|---|
| **D-05** | Removed 3 orphan teachers with `school_id IS NULL` (all named "تجريبي" / test rows) | Verified `teachers.id` not referenced by any FK in `timetable_entries`, `attendance.teacher_id`, `teaching_loads`, `exam_grades` (all relations either non-existent or unreferenced). 3 rows deleted, 0 orphans remain. |
| D-06 | 1 row identified (`parent@nassaqapp.com` — demo user without matching `parents` row) — flagged for product-side decision (create matching `parents` row vs. delete user). **Not auto-deleted** per user data-safety policy. |
| D-10 | No redundantly-named indexes found via heuristic scan; full pg_index duplicate analysis deferred. |

## J. Items NOT applied this session (and why)

The session-plan also lists the following. They are **deliberately deferred** as they require either schema migrations, behaviour-changing decisions, or large refactors that warrant their own focused PR with its own review and rollback window:

| ID | Reason for deferral |
|---|---|
| B-10 | Rate-limit expansion to password-reset/refresh/OTP/upload/AI: needs per-endpoint rate budgets agreed with product |
| B-11 | WS idle-timeout: needs an agreed pong interval & timeout to avoid disconnecting healthy real users |
| B-19 | Slim public health is already in place at `/health` (public_routes); detailed `/system/health` will be put behind admin auth in a follow-up to avoid breaking infrastructure probes that currently rely on it |
| B-25 | Graceful shutdown drain: requires lifecycle wiring around uvicorn's signal handler |
| D-04 / D-11 | New Alembic revision (parents.user_id FK + day_of_week varchar→smallint): drafted but not shipped — requires staging dry-run on a 10k-row attendance subset before production migration |
| D-07 | One-off `ANALYZE` + autovacuum tuning: scheduled for a maintenance window |
| E-05 | notifications/messages returning `[]` for some roles: needs separate tenant_id-mismatch root-cause investigation |
| F-01 / F-02 / F-03 / F-04 | Frontend bundle splitting (lazy-load portals, dynamic-import jspdf/html2canvas/recharts): needs CRA/craco config change + chunk-size measurement; recommend bundling with the planned Vite migration (F-05) |
| F-06 | Strip `console.log` via babel plugin: small change but should land alongside F-05 to avoid two build-config rewrites |

## K. Net deltas (Session 2)

| Metric | Before | After |
|---|---|---|
| `/api/users` (school principal) | **HTTP 500** (Pydantic ValidationError) | **HTTP 200**, 6 users |
| `/api/teachers/me` | **404** (no handler) | **200** for linked teachers |
| `/api/students/me` | **404** (no handler) | **200** for linked students |
| Pool overflow metric | negative number (`overflow: -14`) — confused dashboards | `overflow_in_use: 0` (≥0) + `overflow_counter: -14` (raw signed, for diagnostics) |
| Orphan teacher rows | 3 (`school_id IS NULL`, test data) | **0** |
| Users with `NULL` `preferred_language` | 2 | **0** |
| Path-traversal probes against `/static/` | served HTML | **404** |
| Unhashed extensions on `/static/` | served | **404** |
| `unsafe-eval` in CSP | present | removed |
| `X-XSS-Protection` header | present (deprecated) | removed |
| Critical regressions introduced | — | **None** (smoke pass on login + 6 endpoints) |

## L. Architect review follow-ups (Session 2 — applied)

After the first round of Session 2 fixes the architect review surfaced three issues; all were addressed before sign-off:

| Issue | Fix |
|---|---|
| **Cross-tenant data exposure** via unscoped `email` / `phone` / `national_id` fallback in `/teachers/me`, `/students/me`, and `dependencies.py` enrichment | All fallback identifier lookups now constrain by `school_id == current_user.tenant_id` whenever both sides have a tenant. The unscoped path is reserved for platform-level accounts that have no `tenant_id`. Both `/me` endpoints additionally re-verify `school_id` after the lookup as a defensive double-check. |
| **Per-request query amplification** when `teacher_id`/`student_id` is missing on the user row | After the JWT-enrichment helper resolves a teacher/student id, it now persists the resolved id back into the `users` row (best-effort, non-fatal on failure). Subsequent requests skip the resolution path entirely. |
| **D-05 deletion lacked an executable rollback artifact** | Added `backend/scripts/health-checkup-rollback/2026-04-17_D-05_restore_orphan_teachers.sql` which lists the deleted ids, the FK pre-checks performed, and the snapshot-restore template. |

Post-fix smoke (live): `/api/auth/me`, `/api/users`, `/system/health`, `/api/students`, `/api/teachers`, `/api/teachers/me` all return **200**. Linked teacher lookup verified end-to-end (id `73551be4-…`, school `cfe73b06-…`).

## M. Final status

✅ **Session 2 complete.** All applied changes verified on live traffic. Cross-tenant guard in place. Rollback artifact present. Deferred items (Section J) are explicitly listed as planned follow-ups; none are blockers and none are introduced regressions.
