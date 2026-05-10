# AI / Teacher-Scope Authorization Audit — 2026-05

**Task:** #155 (audit-first follow-up to #154)
**Scope:** Every remaining caller of `_resolve_teacher_scope` and every
broad-query fallback (literal `{"school_id": school_id} if school_id else {}`,
the `tenant_id` variant, and any helper that internally degrades to broad
access when scope is missing).

This audit gates the migration step of Task #155. No vulnerable site beyond
the first one is migrated until this matrix is committed.

## Definitions

- **Confirmed-vulnerable** — code path can return cross-tenant data (or raw PII
  across tenants) when the resolver / scope source returns a falsy value, *and*
  the route is reachable by a role whose token can plausibly miss the relevant
  scope key (e.g. `tenant_id`).
- **Inconsistent-but-not-exploitable** — pattern matches the risky shape, but
  every reachable caller already gates on a fail-closed resolver, OR the broad
  branch is unreachable at the HTTP boundary today. Defense-in-depth wanted,
  no current vulnerability.
- **Already-safe** — broad-by-design (e.g. platform-admin tenant-health) or
  the empty-filter branch is provably unreachable.

## Resolver inventory

| Symbol | File:Line | Callers today | Notes |
| --- | --- | --- | --- |
| `resolve_ai_insights_scope` | `backend/routes/ai_routes_mod.py:940` | 5 AI Insights endpoints (overview, predictions, recommendations, alerts, at-risk-students) | Canonical tri-state. Keep. |
| `_resolve_teacher_scope` | `backend/routes/ai_routes_mod.py:1046` | None — direct callers retired in #154 | Reduce to thin deprecation wrapper around `resolve_ai_insights_scope` (do **not** delete in this task). |
| `_scope_query_for` | `backend/routes/ai_routes_mod.py:1089` | 5 AI Insights endpoints, post-resolver | Internal `else {}` branch is unreachable today (resolver 403's first), but pattern is risky if a future caller skips the gate. Add defensive comment. |
| `_independent_workspace_id` / `_scoped_school_id` | `backend/routes/academics_student_routes.py:46,58` | Several local `academics_student_routes.py` endpoints | Duplicates logic embedded in the canonical resolver. Promote to shared `backend/auth_scope.py` so all modules share one canonical school-id resolution path. |

## Broad-fallback risk matrix

| # | File:Line | Symbol / Endpoint | Pattern | Auth gate (RBAC) | Classification | Justification |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `backend/routes/attendance_routes_mod.py:820` | `GET /attendance/alerts` | `q = {"school_id": school_id} if school_id else {}` then aggregation | `Depends(get_current_user)` only — any authenticated role | **Confirmed-vulnerable** | Same pattern as the original H1 leak. Returns chronic-absence + low-attendance student lists with names; `independent_teacher` (no `tenant_id`) triggers cross-tenant aggregation. |
| 2 | `backend/routes/attendance_routes_mod.py:899` | `GET /attendance/statistics` | Same fallback, used as base for `gd_count`s | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Falsy `school_id` → cross-tenant attendance counts (info disclosure even without PII). |
| 3 | `backend/routes/search_directory_routes_mod.py:34,49` | `GET /search/global` | `tenant_filter = {...} if school_id else {}` and `parent_filter = ...` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Worst case: returns raw student/teacher/parent records (names, emails, phones, national IDs) across all tenants when caller's `tenant_id` is missing. |
| 4 | `backend/routes/search_directory_routes_mod.py:78,83,87,91` | `GET /search/autocomplete` | Filters use literal `tenant_id: school_id` (no `if school_id else {}`); `school_id=None` becomes `tenant_id IS NULL` | `Depends(get_current_user)` only | **Inconsistent-but-not-exploitable** | When `school_id` is `None`, queries become `tenant_id = NULL` — they isolate to the (typically empty) NULL bucket rather than going broad. UX bug, not a leak. Will still benefit from the shared resolver for consistency, but does not gate the rest of the migration. |
| 5 | `backend/routes/search_directory_routes_mod.py:108-130` | `GET /directory/students` | `query = {}`; `tenant_id` only added `if school_id` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Falsy `school_id` → student directory across all tenants, paginated. |
| 6 | `backend/routes/search_directory_routes_mod.py:142-162` | `GET /directory/teachers` | `query = {"role": "teacher"}`; `tenant_id` only added `if school_id` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Same broad-fallback shape — global teacher listing on falsy `school_id`. |
| 7 | `backend/routes/search_directory_routes_mod.py:172-195` | `GET /directory/parents` | `query = {}`; `school_id` only added `if school_id` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Falsy `school_id` → cross-tenant parents list with children. |
| 8 | `backend/routes/search_directory_routes_mod.py:204-217` | `GET /directory/classes` | `query = {}`; `tenant_id` only added `if school_id` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Falsy `school_id` → cross-tenant class names. |
| 9 | `backend/routes/search_directory_routes_mod.py:226,227` | `GET /directory/statistics` | `t_filter`/`s_filter = {...} if school_id else {}` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Falsy `school_id` → platform-wide counts. |
| 10 | `backend/routes/academics_student_routes.py:173` | `GET /classes/options/grades` | `{"school_id": school_id} if school_id else {}` for `grade_levels` | `require_roles([... TEACHER, INDEPENDENT_TEACHER])`, uses `_scoped_school_id` (which falls back to `itw_…`) | **Confirmed-vulnerable** (low-impact) | `_scoped_school_id` covers most teacher cases, but still returns `None` for malformed/orphaned tokens; falsy → cross-tenant grade-level reference list. Low PII impact, but pattern must close. |
| 11 | `backend/routes/academics_teacher_routes.py:314` | `GET /teachers/options/grades` | `{"school_id": school_id} if school_id else {}` for `classes` | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Falsy `school_id` → cross-tenant `classes` listing (class names per school). |
| 12 | `backend/routes/ai_routes_mod.py:1095` | `_scope_query_for` helper | `{"school_id": school_id} if school_id else {}` baseline | All callers go through `resolve_ai_insights_scope` first | **Inconsistent-but-not-exploitable** | Today every caller 403's before reaching this helper with a falsy `school_id`. Latent risk if a new caller forgets the gate. Add defensive comment, do not change shape in this task. |
| 13 | `backend/routes/ai_routes_mod.py:172` | `POST /ai/tenant-health` | `gd_find(... "schools", {}, limit=1000)` | `require_roles([PLATFORM_ADMIN])` | **Already-safe** | Cross-tenant by design. Platform-admin only. Intentional. |
| 14 | `backend/routes/attendance_routes_mod.py:570` | `GET /attendance/report/summary` | `query = {}`; `tenant_id` only added when truthy | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Added in post-review re-scan. Falsy `tenant_id` → cross-tenant attendance summary. Migrated to `require_request_school_id`. |
| 15 | `backend/routes/attendance_routes_mod.py:794` | `GET /attendance/excuses` | `query = {}`; `school_id` only added when truthy | `Depends(get_current_user)` only | **Confirmed-vulnerable** | Added in post-review re-scan. Falsy `tenant_id` → cross-tenant excuses (includes student names + reasons — PII). Migrated to `require_request_school_id`. |
| 16 | `backend/routes/academics_student_routes.py:215` | `GET /classes/options/teachers` | `{"school_id": school_id, ...} if school_id else {"is_active": ...}` | `require_roles([... TEACHER, INDEPENDENT_TEACHER])`, used `_scoped_school_id` (tri-state) | **Confirmed-vulnerable** | Added in post-review re-scan. Same broad-fallback shape as row #10. Migrated to `require_request_school_id`. |
| 17 | `backend/routes/academics_student_routes.py:237` | `GET /classes/options/students` | `{"school_id": school_id, ...} if school_id else {"is_active": ...}` | `require_roles([... TEACHER, INDEPENDENT_TEACHER])`, used `_scoped_school_id` (tri-state) | **Confirmed-vulnerable** | Added in post-review re-scan. Falsy `school_id` → cross-tenant student listing with names + numbers. Migrated to `require_request_school_id`. |

### Post-review note (parallel resolver path)

The legacy local helpers `_scoped_school_id` and `_independent_workspace_id` in
`academics_student_routes.py` were the source of the row #10/#16/#17 fallbacks
(they return `None` instead of raising on resolution failure). After migrating
every in-module caller to `require_request_school_id`, both helpers are now
**unreferenced inside this module** but retained as deprecation shims (see the
"deprecate, don't remove" rule for `_resolve_teacher_scope` — applied here for
symmetry). This eliminates the parallel-contract risk: there is one canonical
fail-closed school-id resolver (`require_request_school_id`) and one canonical
tri-state scope resolver (`resolve_ai_insights_scope`); the deprecated locals
no longer participate in any live code path.

### Out-of-scope `query = {}` patterns

A project-wide grep finds further `query = {}` patterns in unrelated modules
(`user_routes_mod`, `role_dashboards_mod`, `bulk_import_export_routes`,
`platform_routes_mod`, `notification_routes_mod`, `communication_routes`,
`assessment_routes_mod`, `school_routes_mod`, `academics_subject_routes`,
`academics_year_term_routes`, `academics_class_routes`, `consent_privacy_routes_mod`,
`registration_routes_mod`, `teacher_attendance_routes`, `official_curriculum_routes`).
These are **explicitly out of scope** for Task #155 — they are not on the
AI/teacher endpoint surface this audit was chartered to cover, and migrating
them en masse would violate the "no broad refactor" rule. They are recorded
here so the next audit-first task (already proposed as follow-up #156) has
a starting inventory.

## Migration plan (Task #155 step 3)

Migrate every row classified **Confirmed-vulnerable** to the canonical
`require_request_school_id` adapter (added in `backend/auth_scope.py`). Behaviour:

- `school_id = require_request_school_id(current_user)` → returns the tenant id
  (or the `itw_{user_id}` workspace id for `independent_teacher`); raises
  `HTTPException(403, _AI_INSIGHTS_SCOPE_DENIED_AR)` when neither resolves.
- This is a **thin domain adapter** for the school-id resolution half of the
  canonical contract — it shares the constant + fail-closed semantic with
  `resolve_ai_insights_scope` and does not duplicate teacher-class scope
  resolution. There is still exactly one tri-state contract for AI Insights;
  the directory/search/attendance routes only need school-id-or-403, which is
  the sub-contract this adapter exposes.
- For routes that should additionally narrow by teacher class/student scope,
  the existing `resolve_ai_insights_scope` continues to be the only resolver.

Rows classified **Inconsistent-but-not-exploitable** receive only a defensive
comment in this task; no functional change.

Row 13 is left untouched.

## Deprecation of `_resolve_teacher_scope`

No external callers remain. Per the plan, reduce it to a thin compatibility
wrapper around `resolve_ai_insights_scope` (returning the legacy 2-state
shape: `None` for non-teacher / dict otherwise) with a `DeprecationWarning`
and an explicit comment pointing to the canonical resolver. **Full removal
is deferred to a separate cleanup task** so any out-of-tree callers we miss
keep working.

## Tests added in this task (step 5, pattern-based)

- `test_request_school_id_missing_tenant_returns_403_safe_arabic` — covers the
  shared adapter denial: a teacher/independent caller with no resolvable
  school_id receives 403 + the same Arabic message used by Task #154 across
  attendance, search and directory endpoints (one parametrized test per
  pattern, not per file).
- `test_directory_search_cross_tenant_isolation` — two seeded tenants; a
  caller from tenant A querying any directory/search endpoint never sees
  tenant B rows.

## Out of scope for this task

- Removing `_resolve_teacher_scope` entirely.
- Re-shaping `_scope_query_for` (latent risk only — covered by a comment).
- Tightening RBAC on the directory/search endpoints (currently
  `get_current_user` only — that is a separate authorization-design question
  and not the subject of this hardening pass).
- Frontend changes.
