# Independent-Teacher (IT) Phase-2 Reference

Detailed reference for the IT Phase-2 surfaces. `replit.md` summarises the
trust boundaries; this file holds the per-route, per-table specifics.

## §6.1 — Bulk student import

**Tables**
- `workspace_quota` (Alembic `b4c5d6e7f8a9`, Task #207). One row per IT
  workspace. PK column is **`workspace_school_id`** (not `school_id`) to
  make it explicit that it always points at the synthetic
  `itw_{user_id}` schools row and never at a real-school tenant — §6.5
  must use this canonical name.
  - Columns: `max_students` (default 200, mirrors
    `quotas.independent_teacher.MAX_STUDENTS`), `max_classes` (5),
    `max_imports_per_day` (5), `max_rows_per_import` (200),
    `imports_today` + `imports_today_date` (UTC-day reset in app code;
    `_quota_view` parses date / datetime / ISO-string).
  - Migration backfills existing IT workspaces.
  - Bootstrap (`independent_teacher_bootstrap_routes.py` step 6.g.bis)
    seeds the row inside the all-or-nothing materialisation
    transaction, sourcing constants from `quotas.independent_teacher`
    so a future cap change carries through.

**Routes** (`backend/routes/independent_teacher_bulk_import_routes.py`,
Task #207)
- `POST /independent-teacher/students/bulk/parse` — Arabic-only CSV
  upload, returns per-row diagnostics, NO writes.
- `POST /independent-teacher/students/bulk/commit` — gated by
  `require_recent_mfa_403` so the FE axios interceptor replays after
  passkey assertion; all-or-nothing insert pinned to `itw_{user_id}`;
  bumps daily import counter.
- CSV headers: `الاسم الكامل` (required), `رقم الهوية`, `الجنس`
  (`ذكر`/`أنثى`), `تاريخ الميلاد` (yyyy-mm-dd), `الصف` — **no
  classroom column** per spec.
- Cross-tenant payload columns (`school_id` / `tenant_id` / `class_id`
  / etc.) are rejected with the safe Arabic message.
- Names are re-validated server-side via
  `engines.name_validation.validate_personal_name` so a tampered
  preview cannot smuggle past parse.
- RBAC permission `students.bulk_import_workspace` is granted to
  `independent_teacher` only.

**FE**: `/teacher/import-students`
(`frontend/src/pages/TeacherModule/ImportStudentsPage.jsx`) — IT-only
`ProtectedRoute`, sidebar entry under workspace-schedule (Upload icon,
label `استيراد الطلاب`), uses `NassaqAlertDialog`'s `nassaqConfirm` /
`nassaqError` / `nassaqInfo` (signature is `(message, [callback,]
options)`); ships an Arabic CSV template download.

## §6.2 / §6.2b / §6.2c — Parent invitations

**Tables**
- `parent_invitations` (Alembic `a3b4c5d6e7f8`).
- Token contract in `backend/utils/tokens.py`
  (`mint_invitation_token` / `verify_invitation_token`, shared
  `token_hash`): JWT signed with `JWT_SECRET`, 7-day TTL, bound to
  `(workspace_school_id, student_id)` to block cross-row replay. Same
  sha256 hash scheme as `users.reset_token_hash`.

**Routes** (`backend/routes/independent_teacher_invitation_routes.py`,
Task #205)
- `POST /independent-teacher/students/{id}/invite-parent-invitation`
  — IT-only, Tier-A MFA, idempotent on the
  `(workspace_school_id, student_id)` pending slot, raw token returned
  exactly once.
- `POST /independent-teacher/parent-invitations/{id}/cancel` — 409 on
  non-pending.
- `POST /public/parent-invitations/accept` — unauth, IP-rate-limited
  10/5min via `rate_store`; atomically flips status, dedupes parent,
  materialises workspace `users` row, activates `guardian_links`,
  returns one-shot parent bearer.
- All three return **404** for cross-workspace ids per §8 inv. 3.
- Accept handler falls back to the
  `invite+{parent_id}@invite.nassaq.invalid` placeholder when a real
  `parent_email` collides with the global `users.email` unique index —
  closes Task #203 carryover for the four §5.6 dedupe paths
  (national_id / phone+email / phone / email).

**Feature flag**: `IT_PARENT_INVITATIONS_ENABLED` (default off). When
truthy at request time, the legacy §5.6
`POST /independent-teacher/students/{id}/invite-parent` route delegates
to the §6.2b create endpoint instead of performing the immediate
Pending → Linked transition. Read with `os.getenv` so tests can flip
per-call without re-import.
- Rollout: kept **off in dev/test/staging** while the FE rolls out
  behind the new chip + accept-landing surfaces; flipped **on in
  production** only after the §6.2c FE has shipped.
- Tests must set the env var explicitly (e.g.
  `monkeypatch.setenv("IT_PARENT_INVITATIONS_ENABLED", "1")`).

**FE wiring (#206 §6.2c)**: when the flag is on, `TeacherStudentsPage`
chip pulls invitation status from
`GET /independent-teacher/students/{id}/parent-invitation` (returns
`parent_name` on the `accepted` row so the tooltip reads
"Linked to <name>"). Chip dates are formatted via
`frontend/src/utils/hijriDate.js::formatHijriDate`, never
`Intl.DateTimeFormat`. Cancel goes to
`/independent-teacher/parent-invitations/{id}/cancel` via
`NassaqAlertDialog` confirm. The public landing
`/parent-invitations/accept?token=...`
(`frontend/src/pages/ParentInvitationAcceptPage.jsx`) posts to
`/public/parent-invitations/accept`, surfaces every failure variant
through `NassaqAlertDialog` (`info` / `warning` / `error`) with
locale-keyed copy, stores the returned bearer in
`localStorage.nassaq_token`, and hard-navigates to
`/parent?student_id=<id>` (alias for the existing `?child=`
deep-link, honoured by
`ParentActiveStudentContext.readChildIdFromLocation`).

**Invariant — invite-parent portal user materialisation**: the legacy
`POST /independent-teacher/students/{id}/invite-parent` materialises a
workspace-scoped `users` row (`role=parent`, `tenant_id=itw_{user_id}`,
sentinel `password_hash="!invite-pending"` that cannot verify) on the
**new-parent** dedupe path only, inside the same SAVEPOINT as the
`parents` / `guardian_links` inserts. `guardian_links.parent_ref` is
set to the new user id so `/notifications/bulk`'s cohort resolver finds
the recipient. Dedupe paths (national_id / phone+email / phone / email)
deliberately skip user materialisation because `users.email` is
globally unique — the new §6.2b accept path is the portal-onboarding
flow for those cases.

## §6.3 — Personal calendar

**Routes** (`backend/routes/independent_teacher_calendar_routes.py`,
Task #208) — IT-only personal calendar CRUD.
- `GET / POST / PUT / DELETE /independent-teacher/calendar/events[/{id}]`.
- Every read/write pins `tenant_id == itw_{user_id}` +
  `created_by == current_user.id` + `is_personal=True` (Alembic
  `b1c2d3e4f5a6` adds the column on `calendar_events`).
- Cross-workspace ids return **404** per §8 inv. 3 — never 200/403.
- New RBAC permission `Permission.EVENTS_AUTHOR_OWN = "events.author_own"`
  is added to `independent_teacher` only; principals do not inherit it.
- The legacy `/v1/calendar/*` surface in `calendar_routes_mod.py` is
  deliberately untouched (principal events stay
  `is_personal IS NULL/false` so the IT read filter ignores them).

**FE**: `frontend/src/pages/TeacherModule/TeacherPersonalCalendarPage.jsx`
reuses `AdminCalendar` via new `basePath` / `importEnabled` /
`titleAr` / `titleEn` props (defaults preserve the legacy school-wide
behaviour byte-identically); sidebar entry "تقويمي الشخصي" →
`/teacher/calendar` (IT-only).

## §6.4 — Lesson-plan AI assistant

**Tables**
- `lesson_plans` (Alembic merge `c1d2e3f4a5b6`, ORM `LessonPlan`).
- Same migration adds `lesson_plans_today` + `lesson_plans_today_date`
  columns to `workspace_quota` (UTC-day reset in app code, mirrors
  `imports_today`).

**Routes** (`backend/routes/independent_teacher_lesson_plans_routes.py`,
Task #209) — IT-only light AI lesson-planning assistant.
- `POST /independent-teacher/lesson-plans/generate`
- `GET /independent-teacher/lesson-plans`
- `POST /independent-teacher/lesson-plans/{id}/save-to-class`
- NO MFA step-up (low-sensitivity content generation per spec).
- Every read/write pins `workspace_school_id == itw_{user_id}` +
  `created_by == current_user.id`; cross-workspace `plan_id` OR
  `class_id` → **404** per §8 inv. 3.
- Daily cap = `quotas.independent_teacher.MAX_LESSON_PLANS_PER_DAY`
  (20) → 429 when exhausted.
- The LLM JSON payload is recursively scrubbed of forbidden id-like
  keys (`student_id`, `class_id`, `parent_id`, `tenant_id`,
  `school_id`, `workspace_school_id`, `user_id`, `teacher_id`,
  `created_by`, plus their `*_ids` / plural variants) before
  persistence so a tampered prompt can't smuggle foreign-tenant ids
  back into the FE; non-JSON model responses fall back to
  `{"summary": <text>}` so the row still persists.
- AI client comes from `routes.ai_routes_mod.get_openai_client`;
  absent → returns the canonical `AI_NOT_CONFIGURED_RESPONSE` (503).
- New RBAC permission `Permission.AI_LESSON_PLANS = "ai.lesson_plans"`
  granted to `independent_teacher` only.
- Default model `os.getenv("AI_LESSON_PLAN_MODEL", "gpt-4o-mini")`.

**FE**: `/teacher/lesson-planner`
(`frontend/src/pages/TeacherModule/LessonPlannerPage.jsx`) — IT-only
`ProtectedRoute` gated on `ai.lesson_plans`, sidebar entry
"مساعد خطط الدروس" (Sparkles icon), prompt form + structured Arabic
preview + optional save-to-class via existing `/classes` listing; all
errors surface through `NassaqAlertDialog` (`nassaqError` /
`nassaqInfo`).

## §6.7 — Cross-workspace co-teaching (Task #210)

`workspace_collaborators` (Alembic `b1c2d3e4f5a6`) is the **only**
sanctioned cross-tenant data path between two Independent-Teacher
workspaces; the §8 single-tenant invariant is intentionally relaxed
**only** for the named `class_id`, never the wider workspace.

- Lifecycle: `pending → accepted → revoked` (or `cancelled` /
  `expired`).
- Partial unique index `ux_workspace_collab_accepted` enforces
  "at most one active link per host+collaborator+class" and
  `ux_workspace_collab_pending` keeps invites idempotent on
  `(host, class, email)`.
- Tokens: JWTs minted via
  `utils/tokens.py::mint_collab_invitation_token` bound to
  `(host_school_id, class_id, collaborator_email.lower())`, purpose
  `workspace_collab_invitation`, 7-day TTL, sha256 stored as
  `token_hash` (same scheme as parent invitations).
- Routes: `backend/routes/independent_teacher_collab_routes.py`,
  mounted **without** the global tenant dep — IT role + Tier-A MFA
  (`require_recent_mfa_403`) are enforced per route. Host-side writes
  additionally need `Permission.WORKSPACE_COLLAB_MANAGE`
  (`workspace.collab_manage`, granted to `independent_teacher`).
- Cross-workspace by-id reads return **404** (§8 inv. 3).
- At-callsite widening uses
  `backend/utils/collab_access.py::caller_can_access_class` /
  `caller_collab_mode_for_class` — never broaden `TenantIsolation`
  for this path.
- Audit actions:
  `INDEPENDENT_TEACHER_COLLAB_{INVITED,CANCELLED,ACCEPTED,REVOKED}`.

**FE**: `frontend/src/components/teacher/CollaboratorsTab.jsx` rendered
as the "المتعاونون" tab inside `TeacherClassDetailPage` (URL
`?tab=collaborators`); the one-shot raw token is shown exactly once in
a NassaqAlertDialog-driven modal. Accept landing
`frontend/src/pages/CollabInvitationAcceptPage.jsx` is mounted on
`/teacher/collab-accept` and `/workspace-collaborators/accept`,
requires the collaborator to sign in first, posts to
`/independent-teacher/workspace-collaborators/accept`, and lets the
AuthContext interceptor handle any returned MFA step-up envelope.

## §6.8 — Workspace lifecycle (export, soft-delete, reactivate, hard-delete)

**Tables**
- `schools.archived_at` / `schools.pending_hard_delete` /
  `schools.last_export_at` (Alembic `b4c5d6e7f8a9`).
- `schools.last_export_token_hash` /
  `schools.last_export_consumed_at` (Alembic `c5d6e7f8a9b0`,
  single-use export-token state).

**Routes**
(`backend/routes/independent_teacher_workspace_lifecycle_routes.py`,
Task #211) — four-route workspace lifecycle envelope.
- `POST /independent-teacher/workspace/export` — IT-only, Tier-A MFA;
  stamps `last_export_at`; returns a 24h signed `download_url` bound
  to `(ws, uid)`.
- `GET /public/workspace-export/{token}` — unauth, IP-rate-limited
  30/5min; streams a zip of the §6.8 whitelisted tables (`schools`,
  `school_settings`, `academic_{years,terms}`, `teachers`, `classes`,
  `subjects`, `students`, `parents`, `guardian_links`,
  `schedule_sessions`, `attendance`, `assessments`,
  `behaviour_records`, `parent_invitations`) with `_REDACTED_COLUMNS`
  (`password_hash`, MFA secrets, reset/token hashes) stripped.
- `POST /independent-teacher/workspace/soft-delete` — IT-only, Tier-A
  MFA; requires `last_export_at` within 24h → 412 + verbatim
  `confirm_workspace_name` match → 422; flips `status=archived` +
  `archived_at`; 409 once already archived.
- `POST /independent-teacher/workspace/reactivate` — IT-only, allowed
  within 30-day window → 410 once `pending_hard_delete=TRUE`.
- Lazy on-login sweep `maybe_flip_pending_hard_delete()` is invoked
  from `auth_routes_mod.login` and BLOCKS login for archived /
  pending-hard-delete workspaces with a safe Arabic message.
- Hard-delete remains platform-admin out-of-band — never exposed by
  this router.
- The download endpoint is **single-use**: the mint persists
  `last_export_token_hash` and clears `last_export_consumed_at`; the
  public GET atomically flips `last_export_consumed_at` BEFORE
  building the bundle, so replays (and any older outstanding URL
  whose hash no longer matches the most-recent mint) 404.
- Soft-delete is gated server-side by RBAC
  `Permission.WORKSPACE_SOFT_DELETE` (export by
  `Permission.WORKSPACE_EXPORT`).
- `GET /independent-teacher/workspace/lifecycle` powers the FE's
  "export within 24h" gating affordance on `AccountSettingsPage`.

**Platform-admin hard-delete**
(`backend/routes/platform_workspace_purge_routes.py`, Task #217) —
platform-admin-only hard-delete tooling for IT workspaces past their
30-day reactivation window.
- `GET /platform/workspaces/pending-hard-delete` — lists rows where
  `schools.pending_hard_delete=TRUE AND status='archived'`.
- `POST /platform/workspaces/{workspace_id}/hard-delete` — body
  `confirm_workspace_id` must equal the path param verbatim → 422
  otherwise; 409 when row is not `pending_hard_delete`; 404 if
  missing. Cascade-deletes every workspace-scoped child row in
  child→parent order via the `_PURGE_TABLES` whitelist (mirrors
  `_EXPORT_TABLES` plus `workspace_collaborators` on both FK sides,
  `workspace_quota`, `school_settings`, `academic_{years,terms}`,
  `calendar_events`, `users` (`tenant_id=itw_*`), and the `schools`
  row last) wrapped in a single SAVEPOINT, then writes one
  `INDEPENDENT_TEACHER_HARD_DELETED` audit row carrying per-table
  delete counts and a snapshot of the school name/status for
  forensics. Missing tables/columns are logged + recorded under
  `skipped_tables` so a stale whitelist entry never wedges the
  purge.
- Lives behind `require_roles([UserRole.PLATFORM_ADMIN])` — never
  reachable from the IT API surface, preserving the §6.8 trust
  boundary.

## §5.6 — IT inline parent-create

`students.pending_parent_{name,phone,email}` (Alembic `z1a2b3c4d5e6`)
is the canonical pre-link parent contact for the IT inline-create
flow. Trigger `students_clear_pending_parent_on_link_trg` clears them
when `parent_id` transitions NULL → non-NULL.

## §8 inv. 3 — Cross-workspace by-id 404

Every IT-reachable by-id read MUST 404 (never 403/200) for
cross-workspace lookups so the API does not confirm the existence of
foreign-tenant rows. Enforced by:
1. `utils/tenant_scope.py:tenant_scoped_find_one` falling back to
   `auth_scope.independent_workspace_id` when `tenant_id` /
   `school_id` are unset (covers `/assessments/{id}` and other shared
   routes).
2. Explicit `require_request_school_id`-pinned `gd_find_one` on
   `behaviour_routes_mod.py` GET/PUT `/behaviour-records/{id}`.
3. Tenant-pinned student lookup BEFORE `can_view_student` on
   `attendance_routes_mod.py` `GET /attendance/student/{id}`.

The §5.9 exit suite
(`test_independent_teacher_phase1_exit.py::test_5_9_2_*`) asserts
strict 404 for all six §5.9 #2 collections.

## §5.7 — MFA step-up envelope

All Independent-Teacher write/export surfaces emit the canonical
step-up envelope as **HTTP 403** (`code` ∈ `{MFA_STEPUP_REQUIRED,
MFA_PASSKEY_REQUIRED, MFA_RESTORE_REQUIRED}`) so the frontend axios
interceptor (`frontend/src/contexts/AuthContext.js`) replays the
request after passkey assertion.

- Use `require_recent_mfa_403()` (unconditional, IT-only routers) or
  `require_recent_mfa_403_if_independent_teacher()` (shared routes;
  no-op for non-IT) from `backend/dependencies.py`.
- Do not call bare `require_recent_mfa` on shared routes — its 401
  status is treated as a hard logout by the FE.
