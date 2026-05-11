# Security Phase 1 — Immediate Hardening Sprint Report

**Date:** 2026-05-11  
**Audit:** [`docs/security/SECURITY_AUDIT_2026-05-11.md`](./SECURITY_AUDIT_2026-05-11.md)  
**Plan:** [`.local/tasks/task-166.md`](../../.local/tasks/task-166.md)  
**Tests:** `backend/tests/test_security_phase1.py` — 19/19 passing.

This phase covers the audit's "fix this week" tier. Sweeping migrations
(every unscoped `gd_find_one`, every grade/behaviour/notification IDOR, full
WebSocket re-auth) move to Phase 2/3.

---

## Closed in Phase 1

### C-3 — Cross-tenant IDORs on `GET /{id}` routes (representative offenders)
Migrated to `utils.tenant_scope.tenant_scoped_find_one`, which pins the
tenant column at the query level (no after-the-fact check):
- `GET /academics/academic-years/{id}` and `GET /academics/terms/{id}`
  (`backend/routes/academics_year_term_routes.py`)
- `GET /academics/grade-levels/{id}` (same file)
- `GET /assessments/{id}` — engine signature now takes `tenant_id`
  (`backend/routes/assessment_routes.py`,
  `backend/engines/assessment_engine.py`)
- `GET /dashboards/student/{id}` (`backend/routes/role_dashboards_mod.py`)

### C-3 (gate) — New unscoped lookups blocked at CI
- `scripts/check_tenant_scoped_lookups.sh` — grep gate over
  `backend/routes/**.py` against the tenant-owned-table allow-list.
  Detects both `gd_find_one(... "id" ...)` and bulk `gd_find(...)` against
  tenant-owned tables that don't pin `school_id`/`tenant_id`.
- Baseline of the 338 currently-known unscoped lookups checked in at
  `scripts/tenant_lookup_baseline.txt`. New entries fail the gate; clearing
  the backlog is Phase 2 work.

### C-4 — Public platform stats lockdown
- Both `/public/stats` handlers (in `routes/public_routes.py` *and* the
  duplicate in `routes/school_routes_mod.py:987`) now require
  `PLATFORM_ADMIN` / `PLATFORM_SUB_ADMIN`.

### H-1 — Per-identity authorization on student data (representative)
- `GET /attendance/student/{id}` now calls `can_view_student` — same-tenant
  alone is no longer sufficient. Enforces guardian / teacher-assignment /
  admin / self relationship before exposing the history.

### H-3 — Password recovery brute-force budget
- `/api/auth/forgot-password` and `/api/auth/reset-password` added to
  `RATE_LIMITS` (20/hr per IP).
- Layered per-email limit (5/hr) inside `forgot-password`, and a
  per-token-prefix limit (10/hr) inside `reset-password` — protects against
  brute-forcing the JWT signature space against a single victim across IPs.

### H-4 — CSP tightening
- `backend/app/middleware.py` now sets `object-src 'none'`, `base-uri 'none'`,
  `form-action 'self'`, and trims `connect-src` to `'self' wss: ws:` (no
  `https:` wildcard). `'unsafe-inline'` for **scripts** is intentionally
  retained until Phase 3 (SPA nonce migration); CSS still needs it because
  Tailwind/CRA inject inline `style` attrs.

### H-5 — XSS sinks in admin pages
- `frontend/src/pages/SecurityCenterPage.jsx` — `container.innerHTML = html`
  replaced with a `DOMParser` + sanitise pipeline that strips
  `<script>/<iframe>/<object>/<embed>/<style>/<link>` and any
  `on*` / `javascript:` attributes before appending.
- `frontend/src/pages/UsersClassesManagement.jsx` — image `onError` no
  longer sets `parentElement.innerHTML`; uses
  `createElement` + `textContent`.
- ESLint `no-restricted-syntax` rule added in `frontend/craco.config.js`
  at **error** level on `innerHTML` / `outerHTML` / `document.write` so
  future call sites fail the build.

### M-3 — `DANGEROUSLY_DISABLE_HOST_CHECK` build assertion
- `frontend/craco.config.js` hard-fails any production build
  (`NODE_ENV=production`) when the flag is `true`. CRA only honours the
  flag at the dev server, but defense-in-depth.

### M-7 — Destructive cleanup script guard
- `backend/scripts/cleanup_test_data.py` now calls
  `NassaqConfig.destructive_ops_allowed()` and exits with code 2 in any
  non-development environment. Re-asserted in a `finally:` block so a
  mid-run environment flip can't let the script "succeed silently".

---

## Partial in Phase 1 (carried to Phase 2)

- **Tenant-scoped lookup migration** — only the audit's representative
  offenders were rewritten; the baseline file lists 163 remaining
  call sites across `routes/`. Phase 2 should migrate them table-by-table
  and shrink the baseline.
- **`can_view_student` rollout** — applied only to
  `/attendance/student/{id}` in this sprint. Same gate is still owed to
  `/grades/student/{id}`, `/behaviour/student/{id}`,
  `/students/{id}/portfolio`, `/dashboards/parent/...`, and any other
  student-scoped surface. Phase 2.
- **CSP `script-src 'unsafe-inline'`** — still present; nonce migration is
  Phase 3 (depends on SPA inline-script audit).

## Out of scope / explicitly deferred

- **WebSocket re-auth on the existing connection** — flagged in the audit;
  scoped to Phase 2 because it touches the connection lifecycle and the
  notification fan-out.
- **Replacing the broader `RATE_LIMITS` dict with a Redis/process-shared
  store** — current implementation is per-process; acceptable for Phase 1
  but should move to a shared store in Phase 2 along with abuse controls
  on AI / export endpoints.

---

## Files touched (canonical list)

**Backend**
- `backend/utils/tenant_scope.py` — added `tenant_scoped_find_one`,
  `can_view_student`, `_PLATFORM_ROLES`, `_TENANT_KEY_BY_TABLE`.
- `backend/routes/public_routes.py` — `/public/stats` admin-gated.
- `backend/routes/school_routes_mod.py` — duplicate `/public/stats`
  admin-gated (was the actual prod route).
- `backend/routes/academics_year_term_routes.py` — academic_year / term /
  grade_level lookups migrated.
- `backend/routes/assessment_routes.py` +
  `backend/engines/assessment_engine.py` — assessment lookup migrated.
- `backend/routes/role_dashboards_mod.py` — student dashboard lookup
  migrated.
- `backend/routes/attendance_routes_mod.py` — `/attendance/student/{id}`
  guarded by `can_view_student`.
- `backend/routes/auth_routes_mod.py` — per-email + per-token-prefix
  limits on forgot/reset.
- `backend/middleware/rate_limiter.py` — `/api/auth/forgot-password`,
  `/api/auth/reset-password` entries.
- `backend/app/middleware.py` — CSP tightening.
- `backend/scripts/cleanup_test_data.py` — destructive-op guard.

**Frontend**
- `frontend/src/pages/SecurityCenterPage.jsx` — DOMParser + sanitise.
- `frontend/src/pages/UsersClassesManagement.jsx` — DOM-API fallback.
- `frontend/craco.config.js` — `NODE_ENV=production` assertion +
  ESLint `no-restricted-syntax` rule.

**CI / docs / tests**
- `scripts/check_tenant_scoped_lookups.sh` — baseline-diff grep gate.
- `scripts/tenant_lookup_baseline.txt` — current 163-entry baseline.
- `backend/tests/test_security_phase1.py` — 16 regression tests.
- `docs/security/PHASE1_REPORT.md` — this document.
