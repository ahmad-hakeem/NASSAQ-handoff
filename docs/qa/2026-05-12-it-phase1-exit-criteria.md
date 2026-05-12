# IT Phase 1 §5.9 Exit-Criteria Coverage

**Spec:** [`docs/specs/2026-05-12-independent-teacher-phased-spec.md`](../specs/2026-05-12-independent-teacher-phased-spec.md) §5.9 + §8
**Test file:** [`backend/tests/test_independent_teacher_phase1_exit.py`](../../backend/tests/test_independent_teacher_phase1_exit.py)
**Shared fixtures:** [`backend/tests/_it_fixtures.py`](../../backend/tests/_it_fixtures.py)
**Ticket:** Task #202 (tests-only)

This document maps each Phase 1 exit criterion from §5.9 to the test
that verifies it. Every test in the file carries an inline `# §5.9 #N`
marker so the mapping below stays mechanically searchable
(`rg "§5\.9 #"`).

| §5.9 | Criterion | Test(s) | Notes |
|---|---|---|---|
| 1 | B-1..B-6 fixes are in main with passing tests | `test_5_9_1_phase0_b_marker_symbols_present` | Sanity import of the canonical RBAC slice, quota constants, perimeter helpers, and MFA dependency factories. The deeper B-N coverage lives in `test_independent_teacher_phase0.py` (B-2/B-4/B-5/B-6), `test_independent_teacher_bootstrap.py` (B-3 perimeter), and `test_independent_teacher_communication.py` (B-1 NOTIFICATIONS_SEND grant). |
| 2 | Cross-workspace isolation for `students`, `classes`, `attendance`, `assessments`, `behaviour_records`, `notifications` | `test_5_9_2_cross_workspace_isolation_list_and_by_id` (parametrized over the six collections, covering BOTH list and by-id surfaces in one test) | Pattern from `test_ai_insights_security.py`. List surfaces are asserted absent of A's row id and A's `school_id`. ALL by-id surfaces (students, classes, attendance, assessments, behaviour_records) now strictly assert §8 invariant 3 `404` after Task #203 closed the prod gaps. |
| 3 | Capability-gate negatives — every §4.2 deny-list router class | `test_5_9_3_capability_gate_denies_independent_teacher` (IT → 403 IT-deny envelope) **and** `test_5_9_3_capability_gate_does_not_block_school_principal` (principal MUST NOT see the IT-deny envelope) | Both tests parametrize over the same matrix. The matrix now spans the full §4.2 deny-list backbone — read surfaces (smart-scheduling versions, standby candidates, teacher-attendance, bulk students template/export, Hakeem tasks, principal user search) **and** representative WRITE surfaces from each gated router: `POST /timetable/generate-smart` (smart engine), `POST /smart-scheduling/sessions/swap` + `POST /smart-scheduling/session/add` (smart-session writes incl. master-grid mutation paths), `POST /substitutions` + `POST /standby/roster/regenerate` (standby writes), `PUT /principal/teacher/{id}/basic-info` + `POST /principal/generate-password` (principal-management writes), `POST /teachers/bulk/parse` (bulk-teacher), `POST /v1/hakeem-plan/tasks` (hakeem-plan write), `PUT /school/settings` + `POST /school/settings/holidays` (school_settings_mod gated writes), and `POST /communication/broadcast` (school-wide broadcast). The principal-positive companion catches over-broad blocks that would silently break real schools — a fail there means the capability gate widened past the IT slice. |
| 4 | Bootstrap idempotency (replay returns existing workspace, never duplicates) | `test_5_9_4_bootstrap_replay_is_idempotent` | Asserts second call returns `already_materialised=True` and that `schools` / `academic_years` / `teachers` row counts are unchanged. |
| 5 | Communication cohort-scoping (IT-A → only IT-A's students/parents) | `test_5_9_5_cohorts_scope_to_caller_workspace_only` | Two IT workspaces, A queries `my_students` + `my_parents`, B's user ids must not appear. Also pins the response shape: every `my_students` item carries `user_id` + `student_id`; every `my_parents` item additionally carries `parent_id` per `independent_teacher_communication_routes.py:_resolve_my_parents_recipients`. |
| 6 | MFA Tier A enforced on every §5.7 route | `test_5_9_6_mfa_required_routes_emit_stepup_envelope` (parametrized over 8 surfaces: bootstrap, `PUT /users/me/profile`, `GET /export/report/...`, `GET /export/attendance`, `GET /independent-teacher/schedule/export.pdf`, **`PUT /students/{id}`**, **`DELETE /parents/{id}`**, `POST /independent-teacher/students/{id}/invite-parent`) | Every surface emits the canonical step-up envelope (`MFA_STEPUP_REQUIRED` / `MFA_PASSKEY_REQUIRED` / `MFA_RESTORE_REQUIRED`). Bootstrap is the only documented 401 (per `replit.md` IT §5.7); all other IT-facing surfaces are 403 so the FE axios interceptor replays. The §5.7 backfilled paths (Task #201) for any contact change on `students`/`parents` are now part of this consolidated suite, in addition to their dedicated coverage in `test_it_mfa_stepup_backfill.py`. |
| 7 | The `independentTeacherCreateClassComingSoon` block is gone; the IT can complete the end-to-end loop bootstrap → create class → create student → assign schedule slot → record attendance → grade an assessment → message a parent | `test_5_9_7_end_to_end_independent_teacher_loop` | Single test that drives the full happy path through real backend routes: `POST /independent-teacher/bootstrap`, `POST /classes/create` (homeroom_teacher_id pinned in the request body), `POST /student-wizard/create`, `PUT /independent-teacher/schedule/slot`, `POST /attendance`, `POST /grades/bulk`, `POST /independent-teacher/students/{id}/invite-parent`, `POST /notifications/bulk`. Every persisted row is asserted to carry `school_id == itw_{user_id}`; the final notification is asserted to be tenant-pinned to the IT workspace. The `subjects` row is the only direct-DB seed (no IT public subject-create endpoint exists in v1) — flagged as an unavoidable fixture prerequisite. After Task #203, invite-parent now materialises a workspace-scoped `users` row on the new-parent dedupe path, so the §5.9 #7 loop is fully real-route end-to-end with no test-side `xfail`. |

## Shared fixtures

`backend/tests/_it_fixtures.py` promotes the workspace-bootstrap and
header-mint helpers that were duplicated across
`test_independent_teacher_communication.py`,
`_invite_parent.py`, `_phase1_smoke.py`, and
`_it_mfa_stepup_backfill.py`. The exit suite imports them so the
"what does an IT workspace look like?" definition lives in exactly
one place. The per-feature suites can adopt the shared module
incrementally; nothing in this task changes their behaviour.

## Deviations from the spec invariants

**Resolved in Task #203 (2026-05-12).** All four xfail rows that
shipped with #202 have been closed by minimal production fixes; the
suite now passes 56/56 with zero `xfail` and the §8 by-id 404
invariant is enforced uniformly across the six §5.9 #2 collections.

Closed gaps:

- **`/attendance/student/{id}`** — `attendance_routes_mod.py:459`
  now resolves the workspace via
  `auth_scope.require_request_school_id` and tenant-pins the
  student lookup BEFORE the `can_view_student` relationship check,
  so cross-workspace returns 404 (spec §8 invariant 3). The H-1
  audit guarantee (relationship still required for same-tenant
  access) is preserved.
- **`/assessments/{id}`** — `utils/tenant_scope.py:tenant_scoped_find_one`
  now falls back to `auth_scope.independent_workspace_id`
  (`itw_{user_id}`) when the caller has neither `tenant_id` nor
  `school_id` set, so IT callers tenant-pin into their own
  workspace and cross-workspace lookups return None → 404.
- **`/behaviour-records/{id}`** — `behaviour_routes_mod.py:427` (GET)
  and `:447` (PUT) now both pin `tenant_id` via
  `require_request_school_id`, closing the IT-only HTTP-200
  cross-tenant leak that shipped in v1.
- **`/independent-teacher/students/{id}/invite-parent` portal user
  materialisation** — `independent_teacher_invite_parent_routes.py:311`
  now inserts a workspace-scoped `users` row (role=`parent`,
  `tenant_id=workspace_id`, `password_hash="!invite-pending"`
  sentinel that cannot verify) on the **new-parent** dedupe path
  inside the same SAVEPOINT as the `parents` / `guardian_links`
  inserts, and points `guardian_links.parent_ref` at the new
  user id. The §5.9 #7 loop is now fully real-route end-to-end.
  Dedupe paths (national_id / phone+email / phone / email) deliberately
  skip user materialisation because `users.email` is globally unique
  and a cross-workspace email collision would fail the insert and
  roll back the entire link — Phase-2 will introduce a proper
  portal-onboarding flow for those paths.

## Running the suite

```
pytest backend/tests/test_independent_teacher_phase1_exit.py -v
```

The suite is hermetic: it uses the standard `conftest.py`
`_db_session` autouse fixture and rolls back at the end of each
test. No production data is touched. Expected result after
Task #203: **57 passed, 0 xfailed** (56 baseline + 1 new focused
behaviour-record owner-vs-intruder by-id test added in review) —
all four prod gaps from #202 closed.

The companion `test_independent_teacher_invite_parent.py` suite
gained three regression tests (a.1 phone-only, a.2 national-id-only,
a.3 email-collision fallback) and now reports **15 passed**.

Across the full IT test surface
(`pytest backend/tests/test_independent_teacher_*.py
backend/tests/test_it_*.py -q`) the expected result is
**183 passed, 0 xfailed**. Two legacy tests
(`test_smoke_row11_personal_scope_attendance_export_xlsx` in
`test_independent_teacher_phase1_smoke.py` and
`test_export_pdf_returns_pdf_bytes` in
`test_independent_teacher_schedule.py`) were updated in this task
to seed an active passkey and mint a passkey-backed header for the
§5.7 step-up-protected export calls (added by Task #201) — without
this, the legacy tests still expected 200 from
`/export/report/...` and `/independent-teacher/schedule/export.pdf`
and were failing with `MFA_PASSKEY_REQUIRED`. The non-export
assertions of those tests are unchanged.

## Why these tests live in one file

§5.9 is the single Phase 1 launch gate. Splitting its verification
across multiple files makes "is Phase 1 ready?" a multi-search
question. Consolidation here means the launch decision is one
command and one test report.

## Relationship to existing IT test files

This file does **not** duplicate the focused per-feature tests; it
verifies the §5.9 launch contract by exercising representative
behaviour for each criterion. The deeper feature suites continue to
own the long tail:

- `test_independent_teacher_phase0.py` — B-2/B-4/B-5/B-6 deep coverage.
- `test_independent_teacher_bootstrap.py` — bootstrap atomicity, MFA
  enrolment gates, mid-transaction rollback.
- `test_independent_teacher_classes.py` / `_students.py` /
  `_schedule.py` / `_workspace_settings.py` — feature CRUD scoping.
- `test_independent_teacher_communication.py` — full cohort + send
  hardening matrix.
- `test_independent_teacher_invite_parent.py` — all four dedupe paths
  + rollback + edit-conflict.
- `test_it_mfa_stepup_backfill.py` — the six §5.7 routes' 401→403
  envelope conversion.
- `test_independent_teacher_phase1_smoke.py` — Phase 1 reuse smoke
  pass across the §7 capability table.

## Phase 2 §6.2b addendum (Task #205)

- `test_independent_teacher_phase2_invitations.py` covers the new
  three-route envelope: create (happy / idempotent / cross-workspace
  404 / 422 / step-up envelope), cancel (happy / 409 illegal-state /
  cross-workspace 404), public accept (new-parent + each of the four
  §5.6 dedupe paths + global-email collision `.invalid` fallback +
  tampered/expired/replay token rejection + per-IP rate-limit trip),
  and §5.6 feature-flag delegation (`IT_PARENT_INVITATIONS_ENABLED=1`).
- The accept-handler `.invalid` placeholder fallback closes the
  Task #203 carryover for the four §5.6 dedupe paths
  (national_id / phone+email / phone / email).
