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
| 2 | Cross-workspace isolation for `students`, `classes`, `attendance`, `assessments`, `behaviour_records`, `notifications` | `test_5_9_2_cross_workspace_isolation_list_and_by_id` (parametrized over the six collections, covering BOTH list and by-id surfaces in one test) | Pattern from `test_ai_insights_security.py`. List surfaces are asserted absent of A's row id and A's `school_id`. BY-ID surfaces split into two modes: strict `404` (students, classes — §8 invariant 3) and `no_leak` (attendance, assessments — prod returns 403 for tenant violations, also a no-leak signal). See **Deviations** below for the `behaviour_records` xfail. |
| 3 | Capability-gate negatives — every §4.2 deny-list router class | `test_5_9_3_capability_gate_denies_independent_teacher` (IT → 403 IT-deny envelope) **and** `test_5_9_3_capability_gate_does_not_block_school_principal` (principal MUST NOT see the IT-deny envelope) | Both tests parametrize over the same matrix. The matrix now spans the full §4.2 deny-list backbone — read surfaces (smart-scheduling versions, standby candidates, teacher-attendance, bulk students template/export, Hakeem tasks, principal user search) **and** representative WRITE surfaces from each gated router: `POST /timetable/generate-smart` (smart engine), `POST /smart-scheduling/sessions/swap` + `POST /smart-scheduling/session/add` (smart-session writes incl. master-grid mutation paths), `POST /substitutions` + `POST /standby/roster/regenerate` (standby writes), `PUT /principal/teacher/{id}/basic-info` + `POST /principal/generate-password` (principal-management writes), `POST /teachers/bulk/parse` (bulk-teacher), `POST /v1/hakeem-plan/tasks` (hakeem-plan write), `PUT /school/settings` + `POST /school/settings/holidays` (school_settings_mod gated writes), and `POST /communication/broadcast` (school-wide broadcast). The principal-positive companion catches over-broad blocks that would silently break real schools — a fail there means the capability gate widened past the IT slice. |
| 4 | Bootstrap idempotency (replay returns existing workspace, never duplicates) | `test_5_9_4_bootstrap_replay_is_idempotent` | Asserts second call returns `already_materialised=True` and that `schools` / `academic_years` / `teachers` row counts are unchanged. |
| 5 | Communication cohort-scoping (IT-A → only IT-A's students/parents) | `test_5_9_5_cohorts_scope_to_caller_workspace_only` | Two IT workspaces, A queries `my_students` + `my_parents`, B's user ids must not appear. Also pins the response shape: every `my_students` item carries `user_id` + `student_id`; every `my_parents` item additionally carries `parent_id` per `independent_teacher_communication_routes.py:_resolve_my_parents_recipients`. |
| 6 | MFA Tier A enforced on every §5.7 route | `test_5_9_6_mfa_required_routes_emit_stepup_envelope` (parametrized over 8 surfaces: bootstrap, `PUT /users/me/profile`, `GET /export/report/...`, `GET /export/attendance`, `GET /independent-teacher/schedule/export.pdf`, **`PUT /students/{id}`**, **`DELETE /parents/{id}`**, `POST /independent-teacher/students/{id}/invite-parent`) | Every surface emits the canonical step-up envelope (`MFA_STEPUP_REQUIRED` / `MFA_PASSKEY_REQUIRED` / `MFA_RESTORE_REQUIRED`). Bootstrap is the only documented 401 (per `replit.md` IT §5.7); all other IT-facing surfaces are 403 so the FE axios interceptor replays. The §5.7 backfilled paths (Task #201) for any contact change on `students`/`parents` are now part of this consolidated suite, in addition to their dedicated coverage in `test_it_mfa_stepup_backfill.py`. |
| 7 | The `independentTeacherCreateClassComingSoon` block is gone; the IT can complete the end-to-end loop bootstrap → create class → create student → assign schedule slot → record attendance → grade an assessment → message a parent | `test_5_9_7_end_to_end_independent_teacher_loop` | Single test that drives the full happy path through real backend routes: `POST /independent-teacher/bootstrap`, `POST /classes/create` (homeroom_teacher_id pinned in the request body), `POST /student-wizard/create`, `PUT /independent-teacher/schedule/slot`, `POST /attendance`, `POST /grades/bulk`, `POST /independent-teacher/students/{id}/invite-parent`, `POST /notifications/bulk`. Every persisted row is asserted to carry `school_id == itw_{user_id}`; the final notification is asserted to be tenant-pinned to the IT workspace. The `subjects` row is the only direct-DB seed (no IT public subject-create endpoint exists in v1) — flagged as an unavoidable fixture prerequisite. **Deviation:** if invite-parent does not materialise a workspace-scoped `users` row for the new parent (a Phase-1 portal-access gap, not a security bug), the test calls `pytest.xfail(...)` instead of synthesising a parent user via direct DB writes — the launch-gate signal must flip on real product behaviour, not on test fixtures. |

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

Three §8 by-id invariants are not yet met by v1 production code.
Per the tests-only scope of Task #202, the deviating routes are
pinned as `pytest.xfail(strict=True)` with the exact prod gap and
file/line so the suite flips to xpass the day the fix lands and the
contract auto-tightens. There is **no** "permissive pass" mode in
the suite — every BY-ID assertion is the strict §8 404 invariant:

- **`/attendance/student/{id}`** — the cross-workspace lookup
  routes through `tenant_scoped_find_one`, which returns the
  wrapped 403 envelope, not the §8 invariant 3 404. Marked
  `xfail(strict=True)`.
- **`/assessments/{id}`** — `assessment_routes_mod.py:297` resolves
  cross-tenant lookups through `tenant_scoped_find_one`, which
  returns the wrapped 403 envelope, not the §8 invariant 3 404.
  Marked `xfail(strict=True)`.
- **`/behaviour-records/{id}`** — `behaviour_routes_mod.py:424`
  performs an unscoped `gd_find_one` and returns A's row to IT-B
  with HTTP 200. This is a real cross-tenant gap on a single
  by-id surface; the cohort-driving paths
  (`/behaviour-records/student/{id}`, `/behaviour-records/class/{id}`,
  list filters) are tenant-scoped, so the IT FE flow does not
  exercise the leaky path. The test is `xfail(strict=True)` so the
  day a tenant pin is added the suite flips to xpass and we tighten
  the contract back to the strict 404. Tracking: follow-up.
- **`/independent-teacher/students/{id}/invite-parent` portal user
  materialisation** — §5.9 #7 expects the invite path to create a
  workspace-scoped `users` row for the new parent so the cohort
  resolver in `/notifications/bulk` accepts the recipient. v1 leaves
  portal-account creation to a Phase-2 follow-up. Rather than
  rewriting `guardian_links.parent_ref` or inserting a synthetic
  `users` row from the test (which would fake a green light), the
  e2e loop calls `pytest.xfail(...)` if no workspace user is found
  for the freshly-linked parent. The day the invite path
  materialises the user, the test flips to xpass and the §5.9 #7
  signal becomes fully real-route end-to-end. Tracking: follow-up.

## Running the suite

```
pytest backend/tests/test_independent_teacher_phase1_exit.py -v
```

The suite is hermetic: it uses the standard `conftest.py`
`_db_session` autouse fixture and rolls back at the end of each
test. No production data is touched. Expected result: **52 passed,
4 xfailed** (the three documented BY-ID prod gaps —
`/attendance/student/{id}`, `/assessments/{id}`,
`/behaviour-records/{id}` — and the invite-parent portal-user
materialisation gap above).

Across the full IT test surface
(`pytest backend/tests/test_independent_teacher_*.py
backend/tests/test_it_*.py -q`) the expected result is
**175 passed, 4 xfailed**. Two legacy tests
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
