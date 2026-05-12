# IT Phase 1 — Reuse Smoke Pass

**Date:** 2026-05-12
**Spec:** `docs/specs/2026-05-12-independent-teacher-phased-spec.md` §5.5 + §7
**Ticket:** Task #194 — IT workspace: grant ASSESSMENTS_EDIT + Phase 1 smoke pass

## Permission grant — landed ✅

- `backend/middleware/rbac.py` `ROLE_PERMISSIONS["independent_teacher"]`
  now includes `Permission.ASSESSMENTS_EDIT.value` (one-line addition
  alongside `ASSESSMENTS_VIEW` / `CREATE` / `GRADE`).
- `GET /auth/me/permissions` for an IT caller returns `"assessments.edit"`
  in the `permissions` array. Verified in
  `backend/tests/test_independent_teacher_phase0.py`:
  - `test_auth_me_permissions_returns_independent_teacher_set` —
    extended with `assert "assessments.edit" in perms`. PASS.
  - `test_independent_teacher_slice_grants_assessments_edit` — new
    direct slice-membership check. PASS.

## Per-router IT fixes — landed ✅

The Phase 1 reuse pass surfaced narrow gaps in seven routers/engines.
Each is a small, scoped edit (role-list extension and/or IT-tenant
fallback via `auth_scope.independent_workspace_id`) so the IT caller
reaches the same code paths a school teacher does:

1. `routes/attendance_routes_mod.py` — `POST /attendance` and `POST /attendance/bulk` role lists
   include `independent_teacher`; new `_eff_tenant` derivation
   (`current_user.tenant_id or independent_workspace_id(current_user)`)
   propagated into `attendance.tenant_id`, `events.tenant_id`, and
   both audit-log calls so the IT's empty `users.tenant_id` cannot
   trip a NOT-NULL on the write.
2. `routes/assessment_routes_mod.py` — `POST /assessments`,
   `PUT /assessments/{id}`, and `POST /grades/bulk` role lists include
   `independent_teacher`; an IT-aware `effective_tenant` is used for
   the assessment row's `school_id`, the perimeter tenant check, and
   the engine call.
3. `engines/assessment_engine.py` — `record_bulk_grades` audit-log
   `tenant_id` falls back through
   `assessment.tenant_id → assessment.school_id → caller tenant_id`
   so the FK `audit_logs.school_id_fkey` is always satisfied.
4. `routes/behaviour_routes_mod.py` — `POST /behaviour-records`
   `require_roles` includes `UserRole.INDEPENDENT_TEACHER`; the new
   `record_doc["type"]` field mirrors `behaviour_type.category` (or
   `name_en`) so the schema's NOT-NULL `type` column is satisfied.
5. `routes/portfolio_routes_mod.py` — six role-list gates extended
   with `independent_teacher` so the portfolio surface is reachable
   from the IT workspace.
6. `routes/academics_class_routes.py` — `GET /classes` IT-tenant
   fallback (`current_user.tenant_id or independent_workspace_id(...)`)
   so the IT's own classes list returns the workspace rows.
7. `routes/reporting_routes_mod.py` — `GET /reports/school/attendance`
   IT-tenant fallback so the personal-scope report does not 400 with
   "المستخدم غير مرتبط بمدرسة"; `GET /export/report/{report_type}`
   adds `INDEPENDENT_TEACHER` to the `school_*` allow-list and the
   same IT-tenant fallback so XLSX/PDF/CSV exports stream correctly
   for an IT caller (deep row 11).
8. `routes/portfolio_routes_mod.py` — `POST /teacher/portfolio/cv-item`
   and `DELETE /teacher/portfolio/cv-item/{id}` role gates accept
   `independent_teacher` so the IT can persist achievements (deep
   row 7).

## How the smoke pass was executed

`TEST_CREDENTIALS.md` does **not** expose an Independent-Teacher
account, and per `replit.md` the agent must reference test
credentials by filename only — inventing or hardcoding an IT password
into the doc, source, or screenshots is prohibited. The smoke pass
was therefore run through the FastAPI in-process test client with an
IT-issued JWT and a fully-bootstrapped synthetic workspace
(`itw_{user_id}` school + class + student + subject + assessment) —
exactly the request shape the browser would send after a normal IT
sign-in.

The smoke harness lives in
`backend/tests/test_independent_teacher_phase1_smoke.py` (one test
per row).

Run:
```
backend $ python -m pytest tests/test_independent_teacher_phase1_smoke.py \
  tests/test_independent_teacher_phase0.py -v
```

## Smoke checklist — 11 / 11 ✅

> **Test account used (all rows):** synthetic in-process IT JWT minted
> from `auth.create_access_token` against a fresh, fully-bootstrapped
> `itw_{user_id}` workspace. `TEST_CREDENTIALS.md` does **not** publish
> an Independent-Teacher account, and per `replit.md` the agent is
> forbidden from inventing or hardcoding one. The same per-row
> account/workspace shape is reused for every row below — see "How the
> smoke pass was executed" above.

| #  | Capability (spec §7) | Status | Endpoint exercised | Test account used | Observed |
|----|----------------------|--------|--------------------|-------------------|----------|
| 1  | Attendance — record (row 11) | ✅ | `POST /attendance` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200 / 201; the row is written under `tenant_id = itw_{user_id}` and the audit log is emitted with the same workspace id. |
| 1b | Attendance — bulk record (row 11) — **regression for reviewer's blocking finding** | ✅ | `POST /attendance/bulk` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200 / 201; the engine's `Class.school_id == tenant_id` check now passes because the route resolves `tenant_id = current_user.tenant_id or independent_workspace_id(current_user)` before calling `create_bulk_class_attendance`. The persisted `attendance.school_id` equals the IT workspace id. |
| 2  | Attendance — listing / cross-tenant scoping (row 12) | ✅ | `GET /attendance/class/{id}` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200; the IT's own attendance row is returned and cross-IT isolation is backstopped by `test_independent_teachers_cannot_see_each_others_attendance` in the Phase 0 suite. |
| 3  | Assessments — create (row 13) | ✅ | `POST /assessments` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200 / 201; the new assessment is persisted under the IT workspace and counted in `gd_find` for the same class. |
| 4  | **Assessments — edit (Task #194 grant unlock)** | ✅ | `PUT /assessments/{id}` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200; `description` and `max_score` round-trip into the row. |
| 5  | Assessments — grade | ✅ | `POST /grades/bulk` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200 / 201; bulk grades land for the seeded student and the audit log carries the IT workspace id. |
| 6  | Behaviour records (row 14) | ✅ | `POST /behaviour-records` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200 / 201; the incident is written with the legacy `type` mirror so the NOT-NULL column is satisfied. |
| 7  | Portfolio (row 15) — `TeacherAchievementsPage` — **deep:** add CV item + verify save | ✅ | `GET /teacher/portfolio` → `POST /teacher/portfolio/cv-item` → `gd_find_one("teacher_portfolio_meta")` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | Portfolio envelope returns 200; `POST cv-item` returns `{success: true}` with a UUID; the saved row in `teacher_portfolio_meta.cv_items` contains the same `id`. Required extending the portfolio cv-item POST/DELETE role gate to include `independent_teacher`. |
| 8  | AI Insights (row 16) — `AIInsightsPage` | ✅ | `GET /ai/insights/overview` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200/503 envelope (per ticket spec, the canonical `AI_NOT_CONFIGURED_RESPONSE` 503 also counts as pass). |
| 9  | Session start / teach (row 18) — **deep:** schedule_session seeded → start → current | ✅ | `GET /classes` → `POST /session/start` → `GET /session/current?schedule_session_id=…` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | Classes list contains the IT's own class; `/session/start` returns a `session_record_id` and `/session/current` returns the same id with `session_status` in the active set. The seeded `schedule_sessions` row carries the IT teacher id, so the engine's owner-check passes without any role bypass. |
| 10 | Notifications — receive (row 19) | ✅ | `GET /notifications` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | 200; the IT's own notification row is returned. Cross-tenant cohort scoping for the IT recipient role landed under spec §4.3 B-3. |
| 11 | Personal-scope reports / exports (row 25) — **deep:** real XLSX export | ✅ | `GET /reports/school/attendance` → `GET /export/report/school_attendance?format=xlsx` | Synthetic IT JWT (no IT entry in `TEST_CREDENTIALS.md`) | Attendance report returns 200; XLSX export returns 200 with `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and a body whose first two bytes are the ZIP magic `PK`, proving a real XLSX (OOXML) was streamed — not a JSON fallback. Required extending `/export/report/{report_type}` to allow `INDEPENDENT_TEACHER` for `school_*` types and to fall back to `independent_workspace_id(...)` when `tenant_id` is null. |

**Result: 11 / 11 ✅ pass.**

## What got verified in this ticket

- ✅ Permission slice grant for `ASSESSMENTS_EDIT` is correct and is
  reflected on the wire by `/auth/me/permissions`.
- ✅ Phase 0 cross-IT isolation tests still pass (no regression):
  classes, students, assessments, attendance.
- ✅ All 11 smoke rows pass end-to-end against real backend routes
  via the in-process FastAPI test client.
- ✅ Row 4 (assessment edit) — the regression check the slice grant
  was meant to unlock — is green.

## What needs to happen next (user decision)

Independent of this ticket: provision a canonical Independent-Teacher
account in `TEST_CREDENTIALS.md` (workspace bootstrapped, MFA enrolled,
≥ 1 class, ≥ 1 student, ≥ 1 assessment) so future smoke passes can
add a UI sign-in pass on top of the in-process pass already done here.
