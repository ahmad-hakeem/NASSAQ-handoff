# Independent Teacher Account — Phased Architecture & Product Spec

**Date:** 2026-05-12
**Status:** Spec only. **No code is changed by this document.**
**Baseline audit:** `docs/audits/2026-05-11-independent-teacher-architecture-audit.md`
**Related constraints:** `replit.md`, `threat_model.md`
**Assumes:** Principal Grid Matrix work and platform-wide MFA work have stabilised before any ticket cut from this spec begins.

---

## Table of Contents

1. Product Framing & Architectural Decision
2. Glossary & Naming
3. Cross-Cutting Conventions (Arabic-first, NassaqAlertDialog, Alembic, secrets, errors)
4. Phase 0 — Pre-Conditions (gating B-1..B-6 + quotas)
5. Phase 1 — MVP Surface
   - 5.1 Registration & Atomic Bootstrap
   - 5.2 Workspace Settings
   - 5.3 Classes & Students
   - 5.4 Manual Schedule Editor
   - 5.5 Attendance, Assessments, Behaviour, Portfolio, AI Insights
   - 5.6 Communication & Parent Linking
   - 5.7 Security & MFA (Tier A)
   - 5.8 Account Settings, Branding & Visual Identity
6. Phase 2 — Enhancements
7. Per-Capability Verdict Table (reuse / adapt / deny / net-new)
8. Cross-Workspace Isolation Invariants
9. Implementation Ticket Map (Appendix A)
10. Open Questions Carried From Audit (Appendix B)

---

## 1. Product Framing & Architectural Decision

The Independent Teacher (IT) is modelled as a **self-managed mini-school**. Every IT user owns a synthetic single-tenant `schools` row tagged `school_type = 'independent_teacher_workspace'` with a deterministic id `itw_{user_id}`. Class/student/schedule/attendance/assessment data lives in the same physical tables that real schools use, scoped to that synthetic id. There is **no parallel `workspaces` table**.

The decision is taken from the audit (§4.1, §10) and is final for v1:

- ~14 tables enforce `school_id NOT NULL` + `ON DELETE CASCADE`. Reusing `schools` keeps every existing query, index, audit log, AI engine, and report correct without a schema migration.
- Existing precedent across `auth_scope`, `ai_routes_mod`, `class_management_routes`, `academics_student_routes`, `teacher_registration_engine`, `school_notification_engine`, dashboards, role switcher, frontend route guards, sidebar and tests already speak `independent_teacher` + `itw_{user_id}`.
- A single discriminator (`school_type == 'independent_teacher_workspace'`) gives clean deny-by-default for principal-only features.

The model is **half-built today** (audit §0). This spec freezes the work needed to finish it.

---

## 2. Glossary & Naming

| Term | Meaning |
|---|---|
| **Workspace** | The synthetic `schools` row owned by exactly one IT user. Id = `itw_{user_id}`. |
| **Workspace school_id** | The string `itw_{user_id}` resolved by `auth_scope.require_request_school_id`. |
| **Real school tenant** | Any `schools` row with `school_type != 'independent_teacher_workspace'`. |
| **`require_full_school_tenant`** | Capability gate that raises 403 with a safe Arabic message when the resolved tenant is a workspace. |
| **Tier A MFA** | The MFA tier that requires WebAuthn passkey or TOTP, with recovery codes presented at enrolment. Already implemented for the platform; this spec extends its usage to IT-sensitive routes. |
| **Sub-brand** | The visual accent ("مساحتك التعليمية الخاصة") applied to IT-only UI surfaces. |

---

## 3. Cross-Cutting Conventions

These apply to every Phase 0/1/2 ticket cut from this spec. They are **not optional**.

- **Schema changes are Alembic-only.** No `Base.metadata.create_all()`, no `drop_all()`, no manual SQL in production. Any new column or table proposed in this spec ships through a new revision in `backend/alembic/versions/`.
- **Destructive ops blocked outside dev.** Drop/delete/rename/truncate stay blocked by the existing deployment safety guard. The "delete workspace" path (Phase 2) is a soft-delete with platform-admin re-confirmation only.
- **Seed scripts are blocked in production/staging.** The atomic bootstrap endpoint described in §5.1 is the only legitimate workspace creation path in any environment.
- **Arabic-first UX.** All user-visible copy is authored in `frontend/src/locales/ar.json` first, with the English mirror in `en.json`. Sub-brand label: **"مساحتك التعليمية الخاصة"**.
- **NassaqAlertDialog** for every warning/error/confirm. No `alert()`, `window.confirm()`, or `toast.error()` for important interactions. (Toast is allowed only for non-critical "saved" type acknowledgements.)
- **API errors are safe Arabic strings.** No raw `str(e)` in HTTP responses. Server logs may contain detail; HTTP body must not. Pattern reused: `HTTPException(403, "هذه الميزة غير متاحة لحساب المعلم المستقل")`.
- **No hardcoded secrets.** All keys read from Replit secrets / env. No `console.log` in pages or contexts. No bare `except:`.
- **Cross-workspace isolation is a hard invariant** (§8). Every reuse path either consults `auth_scope.require_request_school_id` directly or runs through the consolidated `TenantIsolation` middleware that has been taught about workspace ids (B-4).
- **No regression of stable principal/teacher flows.** Every gating change in this spec is **deny-by-default for IT**, not a behavioural change for existing roles.

---

## 4. Phase 0 — Pre-Conditions

Phase 0 contains the work that **must land before any Phase 1 implementation ticket starts**. These are the audit's blockers B-1..B-6 plus the v1 quota policy. Phase 0 ships no user-visible IT functionality; it makes Phase 1 safe to build.

### 4.1 B-1 — Single canonical workspace-id resolver

- **Goal.** Exactly one function in `backend/auth_scope.py` returns the workspace id and gates access to it.
- **Keep:** `auth_scope.independent_workspace_id(user)` and `auth_scope.require_request_school_id(user, request)`.
- **Remove / re-route:**
  - `backend/routes/academics_student_routes.py` — local resolver lines ~47–68 (already marked DEPRECATED, Task #155). Replace every call with `require_request_school_id`.
  - `backend/routes/class_management_routes.py::_resolve_tenant_id` — drop the lazy materialiser. Replace with a `Depends(require_workspace_or_school)` that calls `require_request_school_id` and returns 409 if the workspace row is missing (the eager bootstrap in §5.1 makes this case unreachable for legitimate IT users).
  - `backend/routes/ai_routes_mod.py` — drop the inline auto-materialise paths (the audit notes lines 912–991, 1347, 1493, 2181). Read-only resolution only.
- **Acceptance:** ripgrep across `backend/` finds zero non-`auth_scope.py` references that *create* a workspace `schools` row, and the only resolver imported by routes is `auth_scope.require_request_school_id`.

### 4.2 B-2 — `require_full_school_tenant` capability gate

- **Goal.** A single FastAPI dependency that raises 403 when the caller resolves to a workspace.
- **Signature** (illustrative, not normative):
  ```py
  async def require_full_school_tenant(
      current_user: dict = Depends(get_current_user),
      session: AsyncSession = Depends(get_db),
  ) -> str:
      sid = require_request_school_id(current_user)
      school = await gd_find_one(session, "schools", {"id": sid})
      if not school or school.get("school_type") == "independent_teacher_workspace":
          raise HTTPException(403, detail="هذه الميزة غير متاحة لحساب المعلم المستقل")
      return sid
  ```
- **Apply to (write paths and full-school reads only):**
  - `backend/routes/scheduling_smart_engine_routes.py` (all routes)
  - `backend/routes/scheduling_smart_session_routes.py` (write paths)
  - `backend/routes/schedule_master_grid_routes.py` (write paths)
  - `backend/routes/bulk_import_export_routes.py`, `backend/routes/bulk_teacher_routes.py`
  - `backend/routes/principal_management_routes.py`
  - `backend/routes/standby_routes.py`
  - `backend/routes/teacher_attendance_routes.py` (staff attendance)
  - `backend/routes/school_settings_routes.py` (write paths only — IT keeps read access via §5.2)
  - `backend/routes/communication_routes.py` school-wide broadcast paths only (DM paths stay open after B-3)
  - `backend/routes/hakeem_plan_routes_mod.py`
  - Approval *write* paths in `event_workflow_routes_mod.py` and `consent_privacy_routes_mod.py`
- **Acceptance:** negative tests for each gated route assert 403 with the Arabic message for an IT caller; positive tests confirm school principals are unaffected.

### 4.3 B-3 — Communication cross-tenant leak fix (PREREQUISITE HOTFIX)

- **Goal.** Recipient cohort builders never include users from other tenants.
- **Touch:**
  - `backend/routes/communication_routes.py` lines ~64, 325, 399, 464 — every `users` query that filters by role must also filter by `tenant_id == caller_workspace_school_id` (or by the `$in` of accessible tenants if the caller is a platform user).
  - `backend/engines/school_notification_engine.py` line ~231 — the `["teacher","school_teacher","independent_teacher"]` recipient lookup must be scoped by `school_id`.
- **Acceptance:** isolation test "IT-A broadcasts → only IT-A's own students/parents receive" passes; existing principal broadcast behaviour unchanged.
- **Sequencing.** This is the only Phase 0 fix the audit allows to ship as an independent hotfix before the rest of Phase 0 is complete, because granting `NOTIFICATIONS_SEND` to IT (Phase 1, §5.6) without B-3 would actively leak data.

### 4.4 B-4 — Teach `TenantIsolation` about synthetic ids

- **Goal.** No reuse path silently broadens results because middleware did not recognise `itw_*`.
- **Touch:** `backend/middleware/tenant_isolation.py` — `TenantIsolation.get_user_tenant_id`, `get_accessible_tenant_ids`, `apply_tenant_filter`, and `TenantAwareQuery.build_query` must treat an IT user with `tenant_id == None` and a derivable workspace id as having `accessible_tenants == [itw_{user_id}]`.
- **Equivalent fallback (acceptable):** every reuse path explicitly calls `require_request_school_id` and never depends on middleware-only filtering. Pick one and apply it consistently.
- **Add:** `'student_grades', 'student_daily_scores', 'portfolio_*', 'assessments', 'behaviour_records', 'communication_*'` to `TENANT_SCOPED_COLLECTIONS` if they are not already covered, so the `warn_missing_tenant_filter` heuristic flags new regressions.
- **Acceptance:** an IT user calling each reuse-path endpoint returns only `school_id == itw_{user_id}` rows in dev fixtures with two co-existing IT workspaces.

### 4.5 B-5 — v1 quotas

- **Policy (frozen for v1):**
  - **Max active classes per workspace:** 5
  - **Max students per workspace:** 200
  - **Max active academic years per workspace:** 1
  - **Max active academic terms per workspace:** 2
- **Enforcement points:**
  - `backend/routes/class_management_routes.py` create endpoint
  - `backend/routes/student_creation_routes.py` create endpoint
  - `backend/routes/academics_year_term_routes.py` create endpoints
- **Source of truth.** A small constants module `backend/quotas/independent_teacher.py` (new) holds the numeric caps so they are not duplicated across routes. No new DB table for v1; a `workspace_quota` table is deferred to Phase 2 (§6).
- **Error contract.** Quota-exceeded responses return `409` with safe Arabic messages, e.g. `"وصلت إلى الحد الأقصى للفصول في مساحتك (5). يمكنك حذف فصل غير نشط للإضافة."`. The frontend renders these via `NassaqAlertDialog`.

### 4.6 B-6 — Backend-sourced `INDEPENDENT_TEACHER_PERMISSIONS`

- **Goal.** Frontend does not advertise CTAs that the backend will 403.
- **Touch:**
  - `backend/middleware/rbac.py` — confirm the canonical IT slice (after Phase 1 grants of `ASSESSMENTS_EDIT` and `NOTIFICATIONS_SEND`, see §5.5/§5.6).
  - Add or reuse a `GET /auth/me/permissions` endpoint that returns the resolved permission list for the current user.
  - `frontend/src/components/wizards/CreateUserWizard.jsx` lines ~385–391 — delete the hardcoded `INDEPENDENT_TEACHER_PERMISSIONS` array. Replace with the backend-sourced list (cached on `AuthContext`).
- **Acceptance:** searching the frontend for `INDEPENDENT_TEACHER_PERMISSIONS` returns zero literal arrays; every CTA gating decision reads from the backend-sourced set.

### 4.7 Phase 0 exit criteria

Phase 1 cannot start until **all** of the following are true:
1. B-1..B-6 land in the codebase with green isolation + capability tests.
2. Principal Grid Matrix work is stable (no in-flight refactor of `schedule_master_grid_routes.py` or `MasterMatrix`).
3. Tier A MFA infrastructure (`mfa_required`, `mfa_must_restore_factor`, `require_recent_mfa`) is fully deployed and observable.

---

## 5. Phase 1 — MVP Surface

Phase 1 ships the user-visible Independent Teacher account. Every item below assumes Phase 0 is complete.

### 5.1 Registration & Atomic Bootstrap

**Net-new.** This is the only legitimate workspace creation path.

- **Endpoint:** `POST /independent-teacher/bootstrap` — owned by `backend/routes/teacher_registration_routes.py` (or a new `independent_teacher_routes.py`; the spec is neutral on file placement).
- **Auth:** authenticated IT user whose workspace row does not yet exist. Idempotent — replaying the call against an already-bootstrapped workspace returns the existing workspace summary, never duplicates rows.
- **Atomic transaction inserts:**
  1. `schools` — `id = itw_{user_id}`, `school_type = 'independent_teacher_workspace'`, `tenant_type = 'production'`, `name` = wizard input, `language='ar'`, `country='SA'`, `status='active'`, `setup_completed=True`.
  2. `school_settings` — defaults derived from wizard step 2 (`working_days`, `periods_per_day`, optional `period_minutes`).
  3. `academic_years` — single row covering wizard year-window dates. `is_active=True`.
  4. `academic_terms` — single row inside that year. `is_active=True`.
  5. `users.tenant_id` — set to `itw_{user_id}` for the IT user.
  6. `teachers` — one row keyed to the user (`user_id`, `school_id = itw_{user_id}`, `is_active=True`).
  7. (Optional, only if wizard step 3 is filled) `classes` — one row, `homeroom_teacher_id` = the row from step 6, `school_id = itw_{user_id}`. Counts against B-5 quota.
- **Failure semantics.** The transaction is all-or-nothing. On failure, return `500` with the safe Arabic message `"تعذر إنشاء مساحتك الآن. حاول مرة أخرى أو تواصل مع الدعم."` and log the underlying error server-side only.
- **Audit log.** Emits one `audit_logs` entry of action `INDEPENDENT_TEACHER_BOOTSTRAP` tagged with the workspace id.

**Frontend — `IndependentTeacherOnboardingWizard` (new).**

- **Trigger.** First successful login when `current_user.role == 'independent_teacher'` and `tenant_id` is null. `LoginPage` and `RegisterPage` redirect to `/teacher/onboarding` (new route under `appRoutes.js`) instead of `/teacher`.
- **Three steps, each `NassaqAlertDialog` for confirm-and-continue:**
  1. **Workspace identity.** Workspace name (Arabic, required), optional avatar upload (reuses existing avatar uploader). Sub-brand header reads "مساحتك التعليمية الخاصة".
  2. **Schedule baseline.** School year window (Hijri picker via `frontend/src/utils/hijriDate.js` — never `Intl.DateTimeFormat('ar-SA-u-ca-islamic')`), working days (multi-select), periods per day (numeric).
  3. **Optional first class.** Class name, grade (free-text in v1; reuse `grade_levels` table as empty), subject (reuses `subjects`). May be skipped.
- **Submit.** Single call to `POST /independent-teacher/bootstrap`. On success, redirect to `/teacher`. The wizard is only shown once per workspace; the post-bootstrap state is detected by the presence of `users.tenant_id`.

### 5.2 Workspace Settings Page

**Adapt.** A reduced view of `frontend/src/pages/SchoolSettingsPagePro.jsx` — same components, narrower data.

- **Route:** `/teacher/workspace-settings` (new, IT-only via guard).
- **Backend.** Read endpoints in `backend/routes/school_settings_routes.py` reused as-is (workspace school_id flows through `require_request_school_id`). Write endpoints reused **for the explicit allow-list below**; everything else stays denied by `require_full_school_tenant`.
- **IT may edit:**
  - Workspace `name`, `name_en` (optional), `logo_url` (avatar).
  - `school_settings.working_days`, `school_settings.periods_per_day`, `school_settings.period_minutes` (if present).
  - Active `academic_year` + `academic_term` rename (no creating additional active years/terms in v1; capped by §4.5).
  - Locale / timezone if the existing settings row exposes them.
- **IT may NOT edit (deny-by-default via `require_full_school_tenant` in the write handler):**
  - `school_type`, `tenant_type`, `id` — system-controlled, frozen.
  - `principal_*` fields, ministry id, license number — irrelevant for a workspace.
  - Stages, sections, classroom rooms, multi-teacher assignment policies, school-wide notification settings.
- **UX.** Sub-brand accent at the page header. Every save action confirms via `NassaqAlertDialog`. Errors render as Arabic strings.

### 5.3 Classes & Students

**Adapt.** Drop the blocker, enable the existing wizards under quota.

- **Frontend — `frontend/src/pages/TeacherModule/TeacherClassesPage.jsx`:**
  - Remove the `independentTeacherCreateClassComingSoon` block (lines ~96–100).
  - Wire the existing "create class" CTA to a simplified `CreateClassWizard` variant with these fields only: name (Arabic), grade label (free text), subject (`subjects` dropdown — auto-create from existing subjects in workspace), capacity (default 30, ≤ §4.5 limit).
  - Display the current `classes used / max` chip sourced from backend (the create endpoint returns 409 with quota copy on overflow).
- **Backend — `backend/routes/class_management_routes.py`:**
  - Replace `_resolve_tenant_id` with `Depends(require_request_school_id)` (Phase 0 outcome).
  - Add quota check before insert; return `409` with the Arabic message from §4.5 when exceeded.
- **Manual student create.**
  - Frontend: existing `AddStudentWizard` reused with a flag `mode='workspace'` that hides the "select parent from school directory" step. Fields: full name (real-name validated by `backend/name_validation.py`), national id (optional), grade, optional date of birth, optional parent name + phone + email captured inline.
  - Backend: `backend/routes/student_creation_routes.py` reused; parent FK stays nullable; quota check applied.
- **Cross-workspace invariants (§8).** Every read in the classes/students pages must scope by `school_id == itw_{user_id}`; every detail page must 404 if the student/class belongs to another workspace. This is verified by isolation tests added in this phase.

### 5.4 Manual Schedule Editor

**Adapt + small net-new UI.** Reuses existing data tables (`time_slots`, `timetables`, `schedule_sessions`); no schema change.

- **Frontend.** A light editor — either a forked simplified `MasterMatrix` (preferred, smaller diff) or a new `WorkspaceScheduleEditor.jsx` if forking introduces more risk than it removes. Final placement is a Phase 1 ticket-time decision; the spec only requires:
  - Grid of `working_days × periods_per_day` from §5.2.
  - Drag-and-drop or click-to-assign of `(class, subject)` pairs into a slot. Single teacher implicit (the IT themselves).
  - Inline "clear slot" action confirmed via `NassaqAlertDialog`.
  - Read-only print/export to PDF reuses `export_engine`.
- **Backend.** A small endpoint surface that wraps `time_slots` + `schedule_sessions` writes scoped by `require_request_school_id`. Per-slot uniqueness invariant: at most one assignment per `(school_id, day_of_week, slot_number)` and that assignment's `teacher_id` must equal the IT's teacher row.
- **Explicit denial.** Smart engine routes (`scheduling_smart_engine_routes`, `scheduling_smart_session_routes` write paths, Hakeem Plans) stay 403 via `require_full_school_tenant` (Phase 0). The sidebar entries for those features are not rendered for IT — confirmed by a guard test.
- **Constraint.** Per `replit.md`, "do not re-introduce the old scheduling system" — the manual editor is not a scheduling engine. It writes literal user choices into `schedule_sessions` and runs no solver.

### 5.5 Attendance, Assessments, Behaviour, Portfolio, AI Insights

**Reuse.** All existing teacher-slice routes work as soon as the workspace school_id is materialised.

- **Attendance.** `frontend/src/pages/TeacherModule/TeacherAttendanceManagePage.jsx`, `SessionStartPage.jsx`, `SessionTeachPage.jsx` reused unchanged. Backend `attendance_routes_mod` and `session_engine` already query by `school_id` and `teacher_id`. Verify in implementation that `SessionStartPage` does not require an `academic_term` lookup that 404s (the bootstrap seeded one — should be fine).
- **Assessments.** Reuse `assessment_routes_mod`. **Permission grant:** add `Permission.ASSESSMENTS_EDIT.value` to the IT slice in `backend/middleware/rbac.py` lines 203–213. Without this grant the existing teacher pages cannot edit a previously created assessment.
- **Behaviour.** Reuse `behaviour_routes_mod` and `TeacherBehaviorPage`. No grants needed — existing slice covers `BEHAVIOUR_VIEW` + `BEHAVIOUR_RECORD`.
- **Portfolio.** Reuse `portfolio_routes_mod` and `TeacherAchievementsPage`. No changes.
- **AI Insights (teacher slice).** Already supported — `frontend/src/pages/AIInsightsPage.jsx` line ~336 includes `'independent_teacher'` in `TEACHER_ROLES`, and `backend/routes/ai_routes_mod.py` resolves the workspace id end-to-end. Phase 0 strips the auto-materialisation paths; AI Insights becomes read-only with respect to workspace creation.
- **Hakeem Plans / scheduling AI / executive summaries.** Stay 403 via `require_full_school_tenant`.

All endpoints in this section are scoped by `school_id == itw_{user_id}` and the teacher id resolved from `users.id → teachers.user_id`. Cross-workspace isolation tests are added in §5.5's ticket per the audit's Phase 1 plan (audit §9 step 8).

### 5.6 Communication & Parent Linking

**Adapt.** This is the most security-sensitive area — it must not ship before Phase 0 B-3.

- **Permission grant.** Add `Permission.NOTIFICATIONS_SEND.value` to the IT slice in `backend/middleware/rbac.py` **only after B-3 is in main**.
- **Cohorts.**
  - "My students" — students whose `school_id == itw_{user_id}` AND who appear in the IT's classes (via `classes.homeroom_teacher_id` or `teacher_assignments`).
  - "Parents of my students" — parents linked to those students via `students.parent_id` and `guardian_links` (`parent_ref`, active, `tenant_id == itw_{user_id}`).
- **Forbidden cohorts.** No "all teachers", no "all students", no "all parents", no school-wide broadcast. The principal-only cohort builders in `school_notification_engine.py` are gated by `require_full_school_tenant`.
- **Frontend.** `frontend/src/pages/TeacherModule/TeacherCommunicationPage.jsx` — variant of the existing Communication Center where the cohort selector is restricted to the two allowed cohorts above and the broadcast option is hidden.
- **Parent capture.** During student create (§5.3) the IT may capture parent name/phone/email inline. The spec does not auto-create a `parents` row in v1 — it stores the contact strings on the `students` row and defers true `parents` row creation + linking to the optional **"Invite Parent"** action in §5.6 below.
- **Invite Parent (Phase 1, behind `require_recent_mfa`).** Authenticated IT clicks "Invite Parent" from a student detail. Backend dedupes by national id (preferred) or by phone+email pair, creating or updating a `parents` row whose `school_id` is set to the workspace if no other school owns the parent yet (parents are intentionally cross-school nullable). A `guardian_links` row is created with `parent_ref`, `student_id`, `tenant_id = itw_{user_id}`, `is_active=True`. The audit notes `_resolve_parent_linked_children` already enforces the `tenant_id` filter (`backend/routes/ai_routes_mod.py` lines 404–436) — that pattern is the reference implementation for the link enforcement.
- **Parent portal scoping invariant.** When a parent's children include both a workspace-owned and a real-school-owned student, every parent-portal query is scoped by `(student_id IN allow_list) AND (school_id == student.school_id)`. The existing `_build_parent_child_context` (`ai_routes_mod.py` lines 439–473) already pins to `school_id`; reuse that pattern everywhere.

### 5.7 Security & MFA (Tier A)

The audit mentions MFA implicitly (via `replit.md` and `backend/pg_models.py` columns); this spec makes it explicit.

- **Enrolment.** IT users are enrolled in Tier A on first login: WebAuthn passkey OR TOTP, with recovery codes presented once and `mfa_recovery_codes_acknowledged` recorded. `mfa_required` is true by default for `role == 'independent_teacher'`.
- **Lockout / restore.** Existing `mfa_must_restore_factor` flag continues to work — a successful recovery-code use forces restore on the next sensitive action.
- **`require_recent_mfa` step-up routes (apply to IT users specifically):**
  - `POST /independent-teacher/bootstrap` (idempotent re-bootstrap or "reset workspace" Phase 2)
  - Any account-settings change that touches email, phone, password, MFA factors.
  - Any contact change on `students` or `parents`.
  - Any data export endpoint (`reporting_routes_mod` exports, student-list CSV/PDF).
  - The "Invite Parent" action (§5.6).
  - Workspace deletion / soft-delete (Phase 2).
- **Login policy hardening.** IT users keep the standard rate limiting + account-lockout path (`failed_login_attempts`, `locked_until`). No relaxation. The login redirect must not skip MFA enrolment for an IT user with `mfa_required=True` and `mfa_enrolled_at IS NULL`.
- **Audit log.** Every Tier A step-up issuance and consumption emits `audit_logs` entries already produced by the auth module — no new code, but isolation tests in this phase verify the IT user's audit trail is scoped to their workspace.

### 5.8 Account Settings, Branding & Visual Identity

- **Reuse `AccountSettingsPage`** for personal info (full_name with `name_validation`, email, phone, avatar, password change, MFA panel, language/theme).
- **Add three IT-only sections:**
  - **Workspace.** Name + avatar (mirrors §5.2; same source of truth).
  - **Communication preferences.** Default channel for parent messaging, quiet hours.
  - **Data export (planned).** Visible card pointing to the Phase 2 workspace-export endpoint; in Phase 1 it shows a "متاح قريبًا" hint via `NassaqAlertDialog` info variant — never a native alert.
- **Sub-brand accent.** The token-driven accent applied to:
  - Sidebar role badge for `independent_teacher`.
  - Onboarding wizard header.
  - Workspace Settings page header.
  - Empty-state illustrations on TeacherClassesPage / WorkspaceScheduleEditor.
- **Tone.** Arabic copy uses "مساحتك التعليمية الخاصة" as the canonical label and "حساب المعلم المستقل" as the formal identifier in admin lists.
- **Design tokens.** Reuse existing Tailwind tokens from the Teacher Module palette; no new colour primitives. The accent is a single semantic token (`workspace-accent`) added to the design system in one place.

### 5.9 Phase 1 exit criteria

1. Every B-1..B-6 fix is in main with passing tests.
2. Cross-workspace isolation tests pass for: `students`, `classes`, `attendance`, `assessments`, `behaviour_records`, `notifications` — pattern from `backend/tests/test_ai_insights_security.py`.
3. Capability-gate negative tests pass for: smart engine, bulk import, standby, principal-management, school-wide broadcasts, Hakeem Plans.
4. Bootstrap idempotency test passes (replay returns the existing workspace, never duplicates).
5. Communication cohort-scoping test passes (IT-A → only IT-A's students/parents).
6. MFA Tier A is enforced on every route in §5.7.
7. The `independentTeacherCreateClassComingSoon` block is gone; the IT can complete the end-to-end loop: bootstrap → create class → create student → assign schedule slot → record attendance → grade an assessment → message a parent.

---

## 6. Phase 2 — Enhancements

Each item is captured at spec depth so a Phase 2 ticket can be cut without re-discovery. Nothing here is required for Phase 1 launch. Every subsection follows the same five-axis structure: **Data model · RBAC · Tenancy · UX · MFA.**

> **Delta from audit baseline.** Two intentional phase shifts vs. the audit's matrix: (a) calendar event authoring (audit row 25) is deferred from Phase 1 to Phase 2 (§6.3) — Phase 1 keeps calendar read-only. (b) `workspace_quota` is introduced as a new Phase 2 table (audit only mentioned it as a recommendation in §4.1); Phase 1 ships the constants in code per §4.5.

### 6.1 Workspace-aware bulk student import

- **Data model.** No new student schema. Add `workspace_quota` table (Phase 2 net-new) keyed by `school_id` storing `(max_classes, max_students, max_imports_per_day)` so quotas vary per plan tier (§6.5) without code changes. Alembic revision required.
- **RBAC.** Add a new `students.bulk_import_workspace` permission to the IT slice in `rbac.py`. Existing `bulk_import_export_routes` stays gated by `require_full_school_tenant`; a parallel workspace-only endpoint accepts the new permission.
- **Tenancy.** Force `school_id = itw_{user_id}` on every imported row; reject (422 with safe Arabic message) any row whose CSV explicitly sets a different school id. Quota check before commit; partial-import never leaves the workspace over cap.
- **UX.** New page `/teacher/import-students`. Two-step flow: (1) upload + parse preview shows row counts, validation errors, and projected post-import quota usage; (2) commit confirmed via `NassaqAlertDialog`. Arabic-only template with no classroom-assignment column.
- **MFA.** `require_recent_mfa` on the commit endpoint. Preview/parse endpoint stays normal-auth.

### 6.2 Parent invitations + portal deep-linking

- **Data model.** New `parent_invitations` table — `(id, workspace_school_id, parent_email, parent_phone, student_id, token_hash, sent_at, accepted_at, expires_at, status, created_by)`. Token is one-shot, hashed with the same scheme as `users.reset_token_hash`, signed with `SECRET_KEY`, expires in 7 days. Alembic revision required.
- **RBAC.** Reuses Phase 1 `NOTIFICATIONS_SEND` for create/cancel; parent acceptance is a public-but-token-protected route bound to the parent role on success.
- **Tenancy.** IT may create/cancel invitations only for students whose `school_id == itw_{user_id}`. Acceptance creates / activates a `guardian_links` row with `tenant_id = itw_{user_id}` (same dedupe pattern as §5.6 Invite Parent). Subsequent parent-portal queries follow the §8 invariant of pinning by `student.school_id`.
- **UX.** Email and SMS content Arabic-first, carries the workspace sub-brand. Acceptance lands on the parent portal deep-linked to the linked student. IT student-detail page shows pending/accepted/expired chips; cancel action confirmed via `NassaqAlertDialog`.
- **MFA.** `require_recent_mfa` on create and cancel. Acceptance route is unauthenticated by design (token-protected) and is rate-limited per IP.

### 6.3 Personal calendar event authoring

- **Data model.** Reuse `events` table with `created_by = IT user id`, `school_id = itw_{user_id}`, and a new boolean column `is_personal=True` for IT-authored rows (Alembic revision; nullable, defaults false to keep existing principals untouched).
- **RBAC.** Add `events.author_own` to the IT permission slice in `rbac.py`. School-wide event creation paths in `calendar_routes_mod` stay gated by `require_full_school_tenant`; the personal-event endpoint is a separate path.
- **Tenancy.** Read filter for IT users: `school_id == itw_{user_id} AND (is_personal=True OR created_by == user.id)`. Writes always set `school_id` and `created_by` server-side. No cross-workspace event visibility.
- **UX.** Reuse the administrative calendar component in personal-mode — no school-wide overlays, no academic-stage filters. Sub-brand accent on the empty state. Delete confirmed via `NassaqAlertDialog`.
- **MFA.** Normal auth for create/edit/delete; `require_recent_mfa` only when an event carries an attachment containing student PII (defer to a per-event flag if attachments are added; otherwise no step-up).

### 6.4 Light AI lesson-planning assistant

- **Data model.** New `lesson_plans` table — `(id, school_id, teacher_id, subject_id, grade, period_count, prompt_payload, generated_payload, created_at)`. Alembic revision required. Daily request counter stored in `workspace_quota` (§6.5).
- **RBAC.** Add `ai.lesson_plans` to the IT slice. New endpoint in `ai_routes_mod` scoped by workspace school_id and `teacher_id`. School principals/teachers can opt in later via the same permission.
- **Tenancy.** Strict workspace pin: every read/write filters by `school_id == itw_{user_id}` and the resolved `teacher_id`. Generated content never references rows outside the workspace.
- **UX.** New tab in the `AIInsightsPage` (or a dedicated `LessonPlannerPage`) — Arabic-first prompt form (subject, grade, period count, optional past-assessment context), generation progress, save-to-class action. Generation failures surfaced via `NassaqAlertDialog`. AI-not-configured returns the existing 503 response shape (`AI_NOT_CONFIGURED_RESPONSE` in `ai_routes_mod`).
- **MFA.** Standard auth; no step-up. Treat lesson plans as low-sensitivity content.

### 6.5 Free vs Pro plan/quotas

- **Data model.** `workspace_plans` table — `(school_id, plan='free'|'pro', activated_at, expires_at, source, updated_by)`. The `workspace_quota` table from §6.1 is read in conjunction with the plan to derive effective caps via a new helper `get_effective_quotas(workspace_school_id)`. Alembic revision required.
- **RBAC.** Plan reads exposed to the IT via `GET /independent-teacher/plan`. Plan writes are platform-only (`platform_admin`, `platform_operations_manager`); IT cannot self-upgrade in this spec — billing integration is a separate ticket.
- **Tenancy.** `workspace_plans` and `workspace_quota` are 1:1 with the workspace `schools.id`. All reads scoped by caller's workspace school_id; platform users can read across tenants.
- **UX.** Account Settings gains a **"خطتي"** card showing current plan, effective caps, and current usage. When a write hits a quota, the existing 409 path from §4.5 renders the Arabic message in `NassaqAlertDialog`; the dialog includes a CTA "اعرف المزيد عن خطة Pro" that links to a static info page (no purchase flow yet).
- **MFA.** Plan downgrade or workspace deactivation triggered by an IT user (when self-service appears) requires `require_recent_mfa`. Read endpoints are normal auth.
- **Out of scope.** Payment/billing integration; pricing model; promo/coupon mechanics.

### 6.6 Optional public profile

- **Data model.** New `public_profiles` table — `(school_id, slug UNIQUE, visibility='public'|'unlisted'|'off', bio, subjects JSONB, region, accepts_inquiries, updated_at)`. Alembic revision required.
- **RBAC.** New permission `profile.public_manage` granted to IT. Public read route `GET /teachers/{slug}` is unauthenticated and serves only `visibility='public'` rows.
- **Tenancy.** Profile rows are 1:1 with the workspace; no student/parent/class data is ever joined into the public response — only the IT's own self-disclosed fields. Slug uniqueness is platform-wide.
- **UX.** New page `/teacher/public-profile` in the IT account area. Toggle to enable visibility confirmed via `NassaqAlertDialog` (with the threat-model note that the slug is publicly enumerable). Sub-brand accent on the live preview.
- **MFA.** `require_recent_mfa` on visibility transitions to/from `public` and on slug changes; field edits within `public` are normal auth.
- **Threat model addendum.** Per `threat_model.md` "Public / Authenticated / Privileged API" boundary, the public route is rate-limited per IP, returns 404 for `off`/`unlisted`, never echoes back the IT's email/phone unless they explicitly opted-in, and is excluded from monitoring endpoints' enumeration responses.

### 6.7 Cross-workspace co-teaching

- **Data model.** New `workspace_collaborators` table — `(id, host_school_id, collaborator_school_id, class_id, scope JSONB, status, invited_by, accepted_at, revoked_at)`. The `class_id` pins the collaboration to a single class. Alembic revision required.
- **RBAC.** New permission `workspace.collab_manage` for the host IT; collaborator IT inherits a read-only or write-restricted scope per the row's `scope` field.
- **Tenancy.** Cross-tenant by design. The `TenantIsolation` middleware extension from B-4 is widened so accessible tenants for the collaborator includes the host's `school_id` **only for the explicitly listed `class_id`** — every query that touches that class joins the collaborator allow-list. Every other table access remains single-tenant. No collaborator can ever see data outside the named class.
- **UX.** New "Collaborators" tab on a class detail page. Invite flow asks for collaborator email; acceptance is via signed token email link. Revocation confirmed via `NassaqAlertDialog`.
- **MFA.** `require_recent_mfa` on invite, accept, and revoke.

### 6.8 Workspace export & soft-delete

- **Data model.** No new tables. New `audit_logs` action `INDEPENDENT_TEACHER_EXPORT` and `INDEPENDENT_TEACHER_SOFT_DELETE`. Soft-delete sets `schools.status='archived'` (no row deletion).
- **RBAC.** New permissions `workspace.export` and `workspace.soft_delete` granted to IT. Hard-delete remains a platform-admin operation only and is performed out-of-band; the existing destructive-op guard from `replit.md` continues to block it in production.
- **Tenancy.** Export reads only the IT's workspace tables (whitelist enforced server-side). Soft-delete archives only the workspace row plus a flag on owned children — never reaches across tenants.
- **UX.** New section in Account Settings → "بيانات مساحتي". Export generates a signed zip download (token expires in 24h). Soft-delete requires (1) successful export within the last 24h, (2) a typed confirmation of the workspace name, (3) `NassaqAlertDialog` final confirmation. Reactivation within 30 days is one click; after 30 days the workspace is queued for platform-admin hard-delete.
- **MFA.** `require_recent_mfa` mandatory on both export and soft-delete. The audit log entries are correlated with the recent-MFA assertion id.

---

## 7. Per-Capability Verdict Table

Legend: ✅ reuse · ➕ adapt · 🔒 deny in v1 · 🆕 net-new for v1.

| # | Capability | Verdict | Backend touchpoints | Frontend touchpoints | Tenancy / RBAC | MFA |
|---|---|---|---|---|---|---|
| 1 | Login / session | ✅ | `auth_routes_mod`, `dependencies.get_current_user` | `LoginPage` redirect to `/teacher/onboarding` if not bootstrapped | JWT only; no tenant override | Tier A enrolment enforced |
| 2 | Account & profile settings | ✅ | reuse | `AccountSettingsPage` + IT sections (§5.8) | self-only | step-up on email/phone/password |
| 3 | Workspace bootstrap | 🆕 | `POST /independent-teacher/bootstrap` (atomic) | `IndependentTeacherOnboardingWizard` | inserts §5.1 rows with workspace school_id | step-up on re-bootstrap |
| 4 | Workspace settings | ➕ | `school_settings_routes` (read + narrow write allow-list) | `WorkspaceSettingsPage` (subset of `SchoolSettingsPagePro`) | `require_request_school_id`; deny others via `require_full_school_tenant` | step-up on identity changes |
| 5 | Create class | ➕ | `class_management_routes` create + quota | drop banner in `TeacherClassesPage`, simplified `CreateClassWizard` | own-only via workspace school_id | normal auth |
| 6 | Create student (manual) | ➕ | `student_creation_routes` (parent optional) + quota | `AddStudentWizard` mode `workspace` | own-only | step-up on contact-field edits |
| 7 | Bulk import students | 🔒 | `bulk_import_export_routes` gated by `require_full_school_tenant` | hidden | n/a | n/a (deferred to §6.1) |
| 8 | Smart schedule generation | 🔒 | `scheduling_smart_engine_routes` gated | hidden | n/a | n/a |
| 9 | Manual schedule editor | 🆕 (small) | thin endpoint over `time_slots`/`schedule_sessions` | light editor (fork or new) | own-only writes; per-slot uniqueness | normal auth |
| 10 | View own schedule | ✅ | reuse | `TeacherSchedulePage` | own-only | normal auth |
| 11 | Attendance recording | ✅ | `attendance_routes_mod` | `TeacherAttendanceManagePage`, `SessionStartPage`, `SessionTeachPage` | own-class invariant | normal auth |
| 12 | Attendance reports | ✅ | reuse with caller scope | reuse | view-only; no excuse approval | normal auth |
| 13 | Assessments / grading | ✅ + permission grant | `assessment_routes_mod`; grant `ASSESSMENTS_EDIT` | reuse | own-only | normal auth |
| 14 | Behaviour records | ✅ | reuse | `TeacherBehaviorPage` | own-students | normal auth |
| 15 | Portfolio | ✅ | `portfolio_routes_mod` | `TeacherAchievementsPage` | own | normal auth |
| 16 | AI Insights (teacher slice) | ✅ | `ai_routes_mod` | `AIInsightsPage` | workspace school_id | normal auth |
| 17 | Hakeem Plans / scheduling AI | 🔒 | gated | hidden | n/a | n/a |
| 18 | Session teach / start | ✅ | `session_engine` | `SessionTeachPage`, `SessionStartPage` | own-class | normal auth |
| 19 | Notifications — receive | ✅ | `notification_routes_mod` | `NotificationsPage` | own | normal auth |
| 20 | Notifications — broadcast school-wide | 🔒 | gated by `require_full_school_tenant` | hidden | n/a | n/a |
| 21 | DM to own students/parents | ➕ + permission grant (post B-3) | `communication_routes`; grant `NOTIFICATIONS_SEND` after B-3 | restricted Communication Center variant | cohort scoped to workspace | normal auth |
| 22 | Parent invite | 🆕 | dedupe + `guardian_links` insert | new action on student detail | tenant-pinned link | step-up |
| 23 | Parent portal access | ✅ | reuse with strict `_resolve_parent_linked_children` pattern | none (parents log in separately) | child-scoped allow-list | parents follow their own MFA policy |
| 24 | School-wide reports / exports | 🔒 | gated | hidden | n/a | n/a |
| 25 | Personal scope reports / exports | ➕ | `reporting_routes_mod` forced to caller scope | reuse | workspace school_id | step-up on export |
| 26 | Calendar — read | ✅ | `calendar_routes_mod` | reuse | own | normal auth |
| 27 | Calendar — author | 🔒 v1 / 🆕 v2 (§6.3) | n/a in v1 | n/a | n/a | n/a |
| 28 | Approvals | 🔒 | gated | hidden | n/a | n/a |
| 29 | Standby / substitution | 🔒 | gated | hidden | n/a | n/a |
| 30 | Staff/teacher attendance | 🔒 | gated | hidden | n/a | n/a |
| 31 | Principal management | 🔒 forever | gated | hidden | n/a | n/a |
| 32 | Subscription / plan gates | 🔒 v1 / 🆕 v2 (§6.5) | n/a | n/a | n/a | n/a |

---

## 8. Cross-Workspace Isolation Invariants

These are non-negotiable for every Phase 1 ticket and every Phase 2 extension:

1. **Every read** of a tenant-scoped table by an IT user is filtered by `school_id == itw_{user_id}` (or by the equivalent tenant column on that table). `TenantIsolation` middleware (post B-4) enforces this for collections in `TENANT_SCOPED_COLLECTIONS`; manual call-sites use `require_request_school_id`.
2. **Every write** by an IT user sets `school_id = itw_{user_id}` server-side; any client-supplied `school_id` is overridden.
3. **Every detail / by-id endpoint** returns 404 (not 403) when the resource's `school_id` does not match the caller's workspace — to avoid leaking existence.
4. **Communication cohorts** never include users from other tenants, full stop. Test pattern: two coexisting IT workspaces in fixtures, IT-A broadcasts, only IT-A's students/parents receive.
5. **Parent linkage** is hydrated through the `_resolve_parent_linked_children` (audit + `ai_routes_mod.py` 404–436) pattern — `tenant_id` is always re-asserted on the lookup, even when the link table claims otherwise.
6. **Reports / exports / AI insights** use the caller's resolved workspace school_id; they never accept a `school_id` query parameter from IT users.
7. **Capability-gated routes** return `403` with the safe Arabic message; they never silently downgrade or swap to a personal-scope variant.
8. **Audit logs** inserted by IT actions carry `tenant_id = itw_{user_id}` so the audit trail is itself isolated.

---

## Appendix A — Implementation Ticket Map

Suggested ticket breakdown so this spec can be lifted into the project task queue once Phase 0 entry criteria (§4.7) are met. Each ticket maps to a numbered section above.

**Phase 0 (must land before Phase 1 starts):**
- IT-P0-1 — B-1: Consolidate workspace-id resolver in `auth_scope.py`; remove deprecated copies.
- IT-P0-2 — B-2: Introduce `require_full_school_tenant` and apply to the route allow-list in §4.2.
- IT-P0-3 — B-3 (PREREQUISITE HOTFIX, may ship independently): Communication cohort tenant scoping in `communication_routes.py` + `school_notification_engine.py`.
- IT-P0-4 — B-4: Teach `TenantIsolation` middleware about `itw_*` ids; extend `TENANT_SCOPED_COLLECTIONS`.
- IT-P0-5 — B-5: v1 quotas constants module + enforcement in class/student/year-term create endpoints.
- IT-P0-6 — B-6: Backend `/auth/me/permissions` source; remove `INDEPENDENT_TEACHER_PERMISSIONS` literal in `CreateUserWizard.jsx`.

**Phase 1 (after Phase 0 + principal Grid Matrix + MFA stable):**
- IT-P1-1 — Atomic `POST /independent-teacher/bootstrap` endpoint (§5.1 backend).
- IT-P1-2 — `IndependentTeacherOnboardingWizard` frontend + first-login routing (§5.1 frontend).
- IT-P1-3 — Workspace Settings page (§5.2).
- IT-P1-4 — Drop "coming soon" banner; enable simplified class create wizard with quota (§5.3 classes).
- IT-P1-5 — Manual student create wizard variant (§5.3 students).
- IT-P1-6 — Light manual schedule editor (§5.4).
- IT-P1-7 — Grant `ASSESSMENTS_EDIT`, smoke-test attendance/assessment/behaviour/portfolio/AI Insights end-to-end (§5.5).
- IT-P1-8 — Grant `NOTIFICATIONS_SEND` (only after IT-P0-3); restrict cohorts in Communication Center (§5.6 communication).
- IT-P1-9 — Parent invite action + `guardian_links` insert with dedupe (§5.6 invite).
- IT-P1-10 — MFA Tier A enrolment + `require_recent_mfa` on §5.7 routes.
- IT-P1-11 — Account Settings IT sections + sub-brand visual identity (§5.8).
- IT-P1-12 — Cross-workspace isolation + capability-gate test suites (§5.9 exit criteria).

**Phase 2 (no fixed order):**
- IT-P2-1 — Workspace-aware bulk import (§6.1).
- IT-P2-2 — Parent invitations + portal deep-link (§6.2).
- IT-P2-3 — Personal calendar authoring (§6.3).
- IT-P2-4 — Light AI lesson planner (§6.4).
- IT-P2-5 — `workspace_plans` + effective quotas (§6.5).
- IT-P2-6 — Public profile (§6.6).
- IT-P2-7 — Cross-workspace co-teaching (§6.7).
- IT-P2-8 — Workspace export & soft-delete (§6.8).

---

## Appendix B — Open Questions Carried From Audit

Inherited verbatim from the 2026-05-11 audit §11 — answers are required before the matching Phase 2 ticket can start, but do not block Phase 0/1.

1. Long-term framing: "freelance teacher who applies to schools" vs "self-managed mini-school"? Phase 2 §6.6 (public profile / apply-to-schools) depends on the answer.
2. Should the synthetic workspace appear in the platform-admin schools list? Recommend filtering by `school_type` in admin UI.
3. Confirm v1 caps: proposal frozen as 5 classes / 200 students / 1 active year (§4.5).
4. May an IT also be invited to a real school as a regular teacher (dual-tenant)? The role-switcher already supports multi-role users; in-scope decision deferred.
5. Workspace data export on closure for compliance — required before "delete workspace" surfaces (Phase 2 §6.6 covers).
