# Independent Teacher Account — Architecture & Discovery Audit

**Date:** 2026-05-11
**Status:** Discovery / planning only. **No implementation in this task.**
**Author:** Replit Agent (audit pass)

---

## 0. Executive Summary

The platform already contains **partial, inconsistent scaffolding** for an `independent_teacher` role. It exists as:

- A first-class enum value (`UserRole.INDEPENDENT_TEACHER` in `backend/dependencies.py`, `backend/models/enums.py`, `backend/models/foundation.py`).
- A registration pathway (`backend/routes/teacher_registration_routes.py`, `backend/engines/teacher_registration_engine.py`) that flags `account_type = "independent_teacher"`.
- A synthetic per-user workspace id `itw_{user_id}` resolved through `backend/auth_scope.py::independent_workspace_id` and consumed by AI Insights, academics-student, and class-management routes.
- A *lazy* `School` row of type `independent_teacher_workspace` created on first class-management call (`backend/routes/class_management_routes.py::_resolve_tenant_id`).
- An RBAC permission slice in `backend/middleware/rbac.py` (a strict subset of `teacher`).
- A frontend role registration card, sidebar branch, login redirect, route guard entry pointing to `/teacher`, and a single user-visible *blocker* — the "create class" CTA on `TeacherClassesPage.jsx` shows `independentTeacherCreateClassComingSoon`.
- Security tests (`backend/tests/test_ai_insights_security.py`) that pin AI Insights cross-workspace isolation between two independent teachers.

**Critical finding:** the model is **half-built and inconsistent across modules**. Three different code paths create or assume an independent workspace id (`auth_scope.py`, `academics_student_routes.py`, `class_management_routes.py`), only one of which lazily *materializes* the `School` row. Most school-coupled features (schedule generation, bulk import, attendance reports, principal dashboard widgets, school settings) have not been audited or extended for the synthetic workspace, and silently assume a real `School` exists with `school_settings`, `academic_years`, `academic_terms`, etc. — none of which exist for an independent teacher.

**Recommended architecture (detail in §10):** Adopt the **synthetic self-tenant ("personal workspace school") model already in flight**, but harden it: (a) one canonical creation path, (b) created eagerly at registration (not lazily on first class call), (c) stamped with `school_type = 'independent_teacher_workspace'` so every existing school-scoped query stays correct *as-is*, (d) a deny-by-default capability gate (`requires_full_school_tenant`) that blocks principal-only school-wide features (timetable engine, bulk import, principal management, parent/student portals, school-wide reports) from running against synthetic tenants until each is explicitly adapted. This is lower-risk than introducing a parallel `Workspace` table and avoids a sweeping refactor of the ~30 tables that have `school_id NOT NULL`.

**Phase 1 launch surface (must-have):** authenticated session with materialized workspace, profile/account settings, manual class create, manual student create, manual schedule (light editor — not the smart engine), session-based attendance, teacher-scoped AI Insights, basic notifications, teacher portfolio, communication with the teacher's own students/parents.

**Hard blockers for v1 (resolve before any implementation PR):** B-1 through B-6 in §8.

---

## 1. Current-State Audit

### 1.1 Roles & RBAC

| Concern | File | Notes |
|---|---|---|
| Role enum (canonical) | `backend/models/enums.py`, `backend/models/foundation.py`, `backend/dependencies.py` (line 107) | `INDEPENDENT_TEACHER = "independent_teacher"` is duplicated in 3 enum files — already a code smell. |
| Permission map | `backend/middleware/rbac.py` lines 203–213 | Strict subset of `teacher`: SCHEDULE_VIEW, ATTENDANCE_VIEW/RECORD, ASSESSMENTS_VIEW/CREATE/GRADE, BEHAVIOUR_VIEW/RECORD, NOTIFICATIONS_VIEW. **Missing**: ASSESSMENTS_EDIT, NOTIFICATIONS_SEND, ACADEMIC_VIEW, plus all "create class / create student / publish schedule" verbs. |
| Frontend permission catalog | `frontend/src/components/wizards/CreateUserWizard.jsx` lines 385–391 (`INDEPENDENT_TEACHER_PERMISSIONS`) | **Diverges from backend.** Lists `view_schools, apply_to_schools, manage_profile, view_own_schedule, use_ai_assistant` — i.e. a "freelancer applying to schools" framing that does **not** match the synthetic-workspace design now in code. This is leftover from an older product spec. |
| Auth scope | `backend/auth_scope.py` | Single source of truth for `independent_workspace_id()` and `require_request_school_id()`. Fail-closed (returns 403 with safe Arabic message). |

**Authorization style.** Mixed: role-based (`require_roles`), permission-based (`require_permission`), and tenant-based (`TenantIsolation` middleware + manual `assert_school_access`). Independent teacher today bypasses tenant isolation only via the synthetic workspace id. There is **no attribute-level "this teacher owns this class" check** in most class/student routes — they trust `school_id == workspace_id`, which is safe because the workspace id is unique per user.

### 1.2 Existing `independent_teacher` traces

Backend (44 hits across the codebase):

- `backend/auth_scope.py` — canonical workspace id resolver.
- `backend/routes/ai_routes_mod.py` — full AI Insights pipeline already supports the workspace id (lines 912–991, 1347, 1493, 2181). Auto-materializes a `schools` row if missing.
- `backend/routes/academics_student_routes.py` — has its own deprecated copy of the resolver (lines 47–68). Allows independent teacher to create/list students in roles list at lines 176, 217, 242.
- `backend/routes/class_management_routes.py` — lazily materializes the workspace `School` row in `_resolve_tenant_id` (lines 22–73). Allows class create at line 105.
- `backend/engines/teacher_registration_engine.py` line 330 + `backend/routes/teacher_registration_routes.py` line 207 — registration sets `account_type="independent_teacher"`.
- `backend/engines/approval_handlers.py` line 140 — approval flow recognizes the account type.
- `backend/engines/school_notification_engine.py` line 231 — included in teacher-broadcast recipient lists.
- `backend/routes/communication_routes.py` lines 64, 325, 399, 464 — included in teacher cohorts (this is a **cross-tenant leak risk** — see B-3).
- `backend/routes/admin_dashboard_routes.py` + `dashboard_routes_mod.py` — counted in platform-admin stats.
- `backend/routes/user_roles_routes.py` lines 24, 271, 343, 403, 422 — role switcher knows the role and routes it to `/teacher`.
- `backend/routes/security_routes.py` line 300 — exposed in role catalog.
- `backend/tests/test_ai_insights_security.py`, `test_directory_attendance_scope.py`, `test_teacher_wizard_api.py`, `test_command_center_stats.py` — existing test coverage for isolation.

Frontend (16 hits):

- `frontend/src/routes/appRoutes.js` line 123 — `TEACHER_ROLES = ['teacher', 'independent_teacher']` shares all teacher routes.
- `frontend/src/components/guards/RouteGuards.js` line 11 — default landing `/teacher`.
- `frontend/src/components/layout/Sidebar.jsx` line 785 — role switcher entry.
- `frontend/src/pages/LoginPage.jsx` line 129, `RegisterPage.jsx` line 279 — login/registration redirect to `/teacher`.
- `frontend/src/pages/AIInsightsPage.jsx` line 336 — included in teacher cohort.
- `frontend/src/pages/TeacherModule/TeacherClassesPage.jsx` lines 96–100 — **explicit blocker UI** showing `independentTeacherCreateClassComingSoon`.
- `frontend/src/components/wizards/CreateUserWizard.jsx` — registration card + (mismatched) permission list.
- `frontend/src/components/users-management/constants.js` line 22 — admin user-list role chip.
- `frontend/src/locales/{ar,en}.json` — translated role label.

### 1.3 Tenancy / data ownership snapshot

From `backend/pg_models.py`:

| Table | Tenant column | Nullable | Notes |
|---|---|---|---|
| `users` | `tenant_id` | yes | platform users have NULL tenant. |
| `schools` | `id` (PK) | — | The tenant container itself. |
| `teachers` | `school_id` | yes | unique `(national_id, school_id)`. |
| `students` | `school_id` | **NO** | FK CASCADE. |
| `classes` | `school_id` | **NO** | FK CASCADE. |
| `subjects` | `school_id` | **NO** | |
| `teacher_assignments` | `school_id` | **NO** | |
| `time_slots`, `timetables`, `timetable_runs`, `schedule_sessions` | `school_id` | **NO** | |
| `attendance` | `school_id` | **NO** | |
| `assessments` | `school_id` | **NO** | |
| `school_settings` | `school_id` | **NO** | unique. Required by smart scheduling engine. |
| `academic_years`, `academic_terms` | `school_id` | **NO** | required by smart scheduling and academics list endpoints. |
| `notifications`, `audit_logs` | `tenant_id` / `school_id` | yes | platform-level entries allowed. |
| `parents` | `school_id` | yes | parent can be cross-school. |

**Implication.** Any model attempting an Independent Teacher *without* a `schools` row would require breaking ~14 NOT-NULL constraints and `ondelete=CASCADE` semantics. Synthetic workspace preserves these constraints unchanged.

### 1.4 Tenant resolution flow

Two parallel resolvers exist today:

1. **JWT path** — `dependencies.get_current_user` reads `tenant_id` from the user row; platform admins may override via `X-School-Context` header.
2. **Synthetic path** — `auth_scope.require_request_school_id` falls back to `itw_{user_id}` when `tenant_id` is null *and* the role/account_type is `independent_teacher`.

Beyond AI Insights, this fall-back is **not consistently applied**. `TenantIsolation.apply_tenant_filter` (`backend/middleware/tenant_isolation.py`) reads `user.tenant_id` directly and returns broad results when null — i.e. an independent teacher hitting a tenant-scoped endpoint that does *not* call `require_request_school_id` may either get a 4xx or, worse, a broad query.

### 1.5 Onboarding flow

`backend/routes/registration_routes_mod.py::_create_school_instant` (lines 130–354) creates `School + User(role=school_principal) + SchoolSettings` atomically. **There is no equivalent atomic flow** for independent teacher — the synthetic `School` row is created *lazily* the first time `class_management_routes._resolve_tenant_id` is called. AI Insights has its own materialization path. The registration engine itself does not create the workspace row.

### 1.6 Smart Scheduling Engine dependencies

`backend/engines/smart_scheduling_engine.py::validate_data_readiness` (lines 387–500) requires: `school`, active `academic_year`, `academic_term`, `academic_stages`, `grade_levels`, `classes`, `subjects`, `teachers` (with assignments and availability), and `school_settings.periods_per_day` + `working_days`. **None of these exist for an independent teacher today.** Running the smart engine on a synthetic workspace will fail readiness.

### 1.7 Bulk Import flow

`backend/routes/bulk_import_export_routes.py` requires `school_principal` or `school_admin`. Independent teacher is **not** in the allowed-role list. Headers/validation are designed for school-scale imports (Arabic templates, classroom assignment columns).

### 1.8 Frontend information architecture

Confirmed via `frontend/src/routes/appRoutes.js` and `Sidebar.jsx`:

- Independent teacher is routed to `/teacher` and inherits the **entire** Teacher Module.
- The Teacher Module assumes a school context: `TeacherClassesPage`, `TeacherSchedulePage`, `TeacherAttendanceManagePage`, `SessionTeachPage`, `TeacherAchievementsPage`, `TeacherCommunicationPage`, `AIInsightsPage`.
- The principal-only sidebar (Command Center, School Schedule editor, Users & Classes admin, School Settings, Communication Center, AI Insights principal view) is gated by `school_principal/school_admin` and is **not** reachable today.
- The single explicit independent-teacher branch in the UI is the "create class" coming-soon banner.

---

## 2. Capability Inheritance Matrix

Legend: ✅ inherit · ➕ inherit + adapt · 🔒 deny in v1 · 🆕 net-new for v1.

| # | Capability | Teacher today | Principal today | Proposed Indep. Teacher | Backend impact | Frontend impact | DB / tenancy impact | RBAC notes | Risk |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Login / session | ✅ | ✅ | ✅ | none | none | none | reuse JWT | low |
| 2 | Account & profile settings | ✅ | ✅ | ✅ | none | reuse `AccountSettingsPage` | none | reuse | low |
| 3 | Workspace bootstrap (synthetic `School` row) | n/a | n/a | 🆕 eager at registration | new code in registration engine | post-signup wizard | inserts 1 `schools` row + 1 `school_settings` row + 1 `academic_year` + 1 `academic_term` | safe — id is `itw_{user_id}` | medium |
| 4 | Create class | 🔒 | ✅ | ➕ unblock for indep. teacher only; remove "coming soon" banner | tighten `class_management_routes._resolve_tenant_id`; cap classes per workspace | replace banner with `CreateClassWizard` (reduced fields) | uses existing `classes` table | own-only invariant (already enforced via workspace id) | medium |
| 5 | Create / import students | 🔒 (teacher cannot create) | ✅ | ➕ allow manual create; **block** bulk Excel import in v1 | reuse `student_creation_routes`; deny bulk import for `independent_teacher_workspace` | reuse `AddStudentWizard` (drop "parent linkage") | uses `students` table | enforce parent FK as nullable for indep workspace | medium |
| 6 | Smart schedule generation | 🔒 | ✅ | 🔒 **block in v1** | gate `scheduling_smart_engine_routes` by `school_type != 'independent_teacher_workspace'` | hide from sidebar | none | engine assumes data they don't have | high — see §8 B-2 |
| 7 | Manual schedule editor | read-only ✅ | ✅ | 🆕 light single-teacher editor (drag-and-drop into `time_slots`) | new minimal endpoint over existing `time_slots` table | new lightweight page or fork of `MasterMatrix` | reuse tables | own-only writes | medium |
| 8 | View own schedule | ✅ | ✅ | ✅ | reuse `TeacherSchedulePage` | reuse | none | reuse | low |
| 9 | Attendance recording | ✅ session-based | ✅ daily | ✅ session-based only | reuse `attendance_routes_mod` | reuse `TeacherAttendanceManagePage` | reuse | own-class invariant | low |
| 10 | Attendance reports / approvals | view ✅ | approve excuses ✅ | view-only | reuse `ATTENDANCE_REPORTS` perm | reuse | none | no excuse approval (no principal) | low |
| 11 | Assessments / grading | ✅ | ✅ | ✅ + add ASSESSMENTS_EDIT to permission slice | reuse `assessment_routes_mod` | reuse | none | grant ASSESSMENTS_EDIT — currently missing | low |
| 12 | Behaviour records | ✅ | ✅ | ✅ | reuse | reuse `TeacherBehaviorPage` | none | reuse | low |
| 13 | Teacher portfolio | ✅ | n/a | ✅ | reuse `portfolio_routes_mod` | reuse `TeacherAchievementsPage` | none | reuse | low |
| 14 | AI Insights (teacher slice) | ✅ | ✅ school-wide | ✅ teacher slice only | already supported in `ai_routes_mod` | reuse `AIInsightsPage` | uses workspace id | already covered by tests | low |
| 15 | Hakeem Plans (principal scheduling AI) | n/a | ✅ | 🔒 block | gate route | hide | none | depends on smart engine | high |
| 16 | Interactive lesson / session teach | ✅ | n/a | ✅ | reuse `SessionTeachPage`, `SessionStartPage` | reuse | none | own-class invariant | low |
| 17 | Notifications — receive | ✅ | ✅ | ✅ | reuse | reuse `NotificationsPage` | reuse | reuse | low |
| 18 | Notifications — send school-wide | 🔒 | ✅ | 🔒 deny | gate by school_type | hide CTA | none | deny-by-default | low |
| 19 | Direct messaging to own students/parents | ✅ | ✅ | ✅ + add NOTIFICATIONS_SEND to permission slice | **fix `communication_routes.py`** (B-3) so independent_teacher cohorts are tenant-filtered | reuse `CommunicationCenterPage` | none | currently leaks across workspaces | **high** |
| 20 | Parent portal | n/a | n/a | n/a | parents log in separately | none | unchanged | unchanged | low |
| 21 | Student portal | n/a | n/a | optional v2 | unchanged | unchanged | unchanged | unchanged | n/a |
| 22 | School settings (academic year/term/grades) | 🔒 | ✅ | 🆕 minimal "workspace settings" subset | new endpoint or mock with sane defaults seeded at bootstrap | new page (or minimal subset of `SchoolSettingsPagePro`) | inserts default rows | own-only | medium |
| 23 | Bulk import (Excel/CSV) | 🔒 | ✅ | 🔒 v1; v2 nice-to-have | gate by school_type | hide | none | deny-by-default | medium |
| 24 | Reports / exports (school-wide) | partial | ✅ | personal scope only | reuse `reporting_routes_mod` with `school_id == workspace_id` | reuse | none | enforce scope | medium |
| 25 | Calendar / events | view | author | personal events only | reuse `calendar_routes_mod`; add own-author guard | reuse | none | own-author | low |
| 26 | Approvals (registration, excuses) | n/a | ✅ | 🔒 v1 | gate | hide | none | deny | low |
| 27 | Standby / substitution | n/a | ✅ | 🔒 v1 | gate | hide | none | irrelevant for solo teacher | low |
| 28 | Teacher attendance / staff attendance | n/a | ✅ | 🔒 | gate | hide | none | deny | low |
| 29 | Principal management / sub-admin creation | n/a | ✅ | 🔒 forever | gate | hide | none | deny | low |
| 30 | Subscription / plan gates | none today | none today | future v2 | requires new module | n/a | new tables | out of scope | n/a |

---

## 3. Authorization / RBAC Matrix (deny-by-default)

For role `independent_teacher` operating against scope `school_id == itw_{user_id}`:

| Resource | Read | Create | Update | Delete | Export | Notes |
|---|---|---|---|---|---|---|
| Self user / profile | ✓ | n/a | ✓ | ✗ | ✗ | password change & MFA allowed. |
| Workspace `School` row | ✓ | system at signup | name/avatar only | ✗ | ✗ | cannot change `school_type`, `tenant_type`, `id`. |
| `school_settings` (own) | ✓ | system | limited (working days, periods/day) | ✗ | ✗ | needed by schedule/attendance. |
| `academic_years` / `terms` (own) | ✓ | ✓ (≤2 active) | ✓ | only if no children | ✗ | seed one default at bootstrap. |
| `grade_levels`, `subjects` (own) | ✓ | ✓ | ✓ | own-only | ✗ | reuse academics CRUD. |
| `classes` (own) | ✓ | ✓ (cap N — see B-5) | ✓ | own-only & no enrolled students | ✗ | reuse class_management_routes. |
| `students` (own) | ✓ | ✓ (manual; bulk in v2) | ✓ | own-only | ✓ csv/pdf | parent linkage optional. |
| `parents` linked to own students | ✓ | optional | ✓ | own-only | ✓ | parent rows may be cross-tenant — handle dedupe by national_id. |
| `time_slots` / `timetables` (own) | ✓ | ✓ via light editor | ✓ | own-only | ✓ | smart engine blocked in v1. |
| `attendance` (own classes) | ✓ | ✓ session | ✓ same day | own-only same day | ✓ | reuse engine. |
| `assessments` (own) | ✓ | ✓ | ✓ | own-only | ✓ | grant ASSESSMENTS_EDIT. |
| `behaviour_records` (own students) | ✓ | ✓ | ✓ | own-only | ✓ | reuse. |
| `notifications` (received) | ✓ | n/a | ack | ✗ | ✗ | reuse. |
| `notifications` (broadcast school-wide) | ✗ | ✗ | ✗ | ✗ | ✗ | **deny.** |
| `notifications` (DM to own students/parents) | ✓ | ✓ | n/a | ✗ | ✗ | requires fix B-3. |
| Smart scheduling engine | ✗ | ✗ | ✗ | ✗ | ✗ | **deny in v1.** |
| Hakeem Plans | ✗ | ✗ | ✗ | ✗ | ✗ | deny. |
| Bulk import / export of students | ✗ | ✗ | ✗ | ✗ | ✗ | deny in v1. |
| Standby / substitution | ✗ | ✗ | ✗ | ✗ | ✗ | deny. |
| Staff/teacher attendance | ✗ | ✗ | ✗ | ✗ | ✗ | deny. |
| Approval workflows | ✗ | ✗ | ✗ | ✗ | ✗ | deny. |
| Other tenants' data (any table) | ✗ | ✗ | ✗ | ✗ | ✗ | enforced by `school_id == itw_{user_id}` filter at every layer. |
| Platform admin surfaces | ✗ | ✗ | ✗ | ✗ | ✗ | deny. |
| Parent / student portal data | only own students | n/a | n/a | n/a | n/a | reuse student-portal queries scoped by school. |

---

## 4. Architecture Findings by Layer

### 4.1 Database / tenancy

- **Keep** the `schools` table as the single tenancy anchor; the synthetic `School` row carries `school_type='independent_teacher_workspace'`. This avoids touching ~14 NOT-NULL `school_id` columns.
- **Add a discriminator helper** (e.g. `School.is_workspace -> bool`) so filters can branch deterministically.
- **Bootstrap row inventory** (must be inserted atomically at registration): `schools`, `school_settings`, `academic_years` (one), `academic_terms` (one), default `grade_levels` (or none — empty is fine if UI handles it), and the matching `users.tenant_id`/`teachers.school_id`.
- **No new tables required for v1.** A Phase-2 `workspace_quota` table is recommended for class/student caps and (eventually) plan gates.
- **CASCADE check.** Deleting a synthetic workspace would cascade to its students/classes/etc. Document this and require platform-admin confirmation.

### 4.2 Backend / API / Authorization

- **Consolidate the three workspace-id resolvers** into `auth_scope.py` only. Remove the deprecated copy in `academics_student_routes.py` (already marked DEPRECATED Task #155) and replace the lazy materializer in `class_management_routes.py` with a `require_workspace_or_school` dependency that errors if the bootstrap row is missing.
- **Introduce a single capability gate** dependency, e.g.

  ```py
  def require_full_school_tenant(current_user=Depends(get_current_user), db=Depends(get_db)) -> str:
      sid = require_request_school_id(current_user)
      school = ... fetch ...
      if school.school_type == "independent_teacher_workspace":
          raise HTTPException(403, "هذه الميزة غير متاحة لحساب المعلم المستقل")
      return sid
  ```

  Apply to: `scheduling_smart_engine_routes`, `bulk_import_export_routes`, `principal_management_routes`, `school_settings_routes` (write paths only), `standby_routes`, `teacher_attendance_routes`, `approval` write paths, broadcast paths in `communication_routes`.
- **Reusable as-is** (with workspace id flowing through `require_request_school_id`): `attendance_routes_mod`, `assessment_routes_mod`, `behaviour_routes_mod`, `portfolio_routes_mod`, `ai_routes_mod`, `participation_routes_mod`, `notification_routes_mod` (receive paths), `calendar_routes_mod` (read & own-author), `academics_student_routes`, `academics_class_routes`, `academics_subject_routes`, `academics_year_term_routes`, `academics_reference_routes`.
- **Needs adaptation**: `class_management_routes` (replace lazy bootstrap), `student_creation_routes` (parent linkage optional), `reporting_routes_mod` (force scope to caller), `communication_routes` (cohort filters — see B-3).
- **TenantIsolation middleware** must learn about the synthetic id, or every reuse path must explicitly call `require_request_school_id`.

### 4.3 Business logic

- **Smart Scheduling Engine** stays untouched and **blocked**. Even if data is seeded, the assumptions around multi-teacher conflicts, classroom rooms, and stage-level grade levels make the output meaningless for one teacher. v1 ships a manual editor; v2 considers a stripped engine.
- **Hakeem Plans** depends on the smart engine; block.
- **Approval engine** runs unchanged; independent teachers don't initiate principal-level requests, and they cannot approve anything, so no behavioural change.
- **AI Hakim Engine** already enforces explicit `school_id` filters on every call (`gd_find_one({"id": ..., "school_id": ...})`). It works as-is provided the workspace is materialized.
- **Notification engine**: cohort builders in `school_notification_engine.py` currently include `independent_teacher` in `["teacher","school_teacher","independent_teacher"]` recipient lists *without* `school_id` filter. This is a real cross-tenant leak and must be scoped — see B-3.

### 4.4 Frontend / navigation / UX

- **Reuse** the entire Teacher Module routes (`/teacher/*`) — already protected by `TEACHER_ROLES = ['teacher','independent_teacher']`.
- **Remove** the "coming soon" banner in `TeacherClassesPage.jsx` (lines 96–100).
- **Replace** the obsolete `INDEPENDENT_TEACHER_PERMISSIONS` array in `CreateUserWizard.jsx` (lines 385–391) with the canonical set sourced from backend `/auth/me/permissions`.
- **Add** an onboarding wizard (single page, 3 steps): workspace name → academic year window → optional first class. This calls a new `POST /independent-teacher/bootstrap` endpoint that wraps the atomic seed.
- **Add a minimal "Workspace Settings"** page (subset of `SchoolSettingsPagePro` — name, working days, periods/day, academic year/term).
- **Hide/guard** the principal-only menu items: nothing to do (already gated). Verify by adding a guard test.
- **AIInsightsPage**: already includes `'independent_teacher'` in `TEACHER_ROLES`. Keep.
- **Classroom session pages** (`SessionTeachPage`, `SessionStartPage`): smoke-test with a workspace that has 1 class & 1 subject — current code paths read schedule by `teacher_id` so they should work, but session creation may try to look up `academic_term` (verify in implementation).

---

## 5. Dependency Map

### 5.1 Affected modules

**Backend reuse-as-is** (after `require_request_school_id` is everywhere): `auth_routes_mod`, `attendance_routes_mod`, `assessment_routes_mod`, `behaviour_routes_mod`, `portfolio_routes_mod`, `ai_routes_mod`, `notification_routes_mod` (receive), `calendar_routes_mod`, `academics_*_routes`, `participation_routes_mod`, `search_directory_routes_mod`, `relationship_routes_mod`.

**Backend reuse-with-adaptation**: `class_management_routes`, `student_creation_routes`, `student_management_routes`, `communication_routes`, `reporting_routes_mod`, `school_settings_routes` (read).

**Backend gated/denied**: `scheduling_smart_engine_routes`, `scheduling_smart_session_routes` (write), `schedule_master_grid_routes` (write), `bulk_import_export_routes`, `bulk_teacher_routes`, `principal_management_routes`, `standby_routes`, `teacher_attendance_routes`, `school_settings_routes` (write), `hakeem_plan_routes_mod`, `event_workflow_routes_mod` (principal-only ops), `consent_privacy_routes_mod` (school-wide settings), `monitoring_routes`, `audit_routes`, `admin_*`, `platform_routes_mod`, `security_routes` (admin pieces).

**Frontend reuse-as-is**: `TeacherHomePage`, `TeacherSchedulePage` (read), `TeacherAttendanceManagePage`, `TeacherBehaviorPage`, `TeacherAchievementsPage`, `TeacherCommunicationPage` (after B-3 fix), `AIInsightsPage`, `NotificationsPage`, `AccountSettingsPage`, `SessionStartPage`, `SessionTeachPage`.

**Frontend new or forked**: `IndependentTeacherOnboardingWizard` (new), `WorkspaceSettingsPage` (new minimal), `TeacherClassesPage` (drop banner, enable create), `AddStudentWizard` (variant without parent-required), light schedule editor (new or simplified `MasterMatrix`).

### 5.2 Tables touched (new rows only — no schema changes)

`schools`, `school_settings`, `academic_years`, `academic_terms`, `users`, `teachers`, `classes`, `students`, `subjects`, `teacher_assignments`, `time_slots`, `timetables`, `schedule_sessions`, `attendance`, `assessments`, `behaviour_records`, `notifications`, `audit_logs`.

### 5.3 Tests to add

- Cross-workspace isolation for: `students`, `classes`, `attendance`, `assessments`, `notifications` (extend pattern from `test_ai_insights_security.py`).
- Capability-gate negative tests: smart engine, bulk import, standby, principal-management — all returning safe Arabic 403 for `independent_teacher`.
- Bootstrap idempotency: signing up the same identity twice, replaying `POST /independent-teacher/bootstrap`.
- Communication cohort scoping (B-3) — verify a broadcast by Independent Teacher A reaches **only** A's own students/parents.

---

## 6. Reusable vs Net-New Inventory

**Reusable as-is** (≈ 70% of surface): JWT/session, account settings, attendance recording, assessments, behaviour, portfolio, AI Insights, notifications-receive, calendar-read, classroom session pages, academics CRUD, AI Hakim engine.

**Reusable with guards/adaptation** (≈ 20%): class create, student create, communication center, reporting, schedule editor (light), school-settings read.

**Net-new for v1** (≈ 10%): atomic workspace bootstrap (backend + onboarding wizard frontend), `WorkspaceSettingsPage`, capability-gate dependency, light schedule editor, fixes to communication cohort scoping and tenant isolation middleware fall-back.

---

## 7. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Smart scheduling engine called against unseeded workspace → crash/garbage output | High if not gated | High | Hard capability gate + UI hide. |
| R-2 | Bulk import accepting Excel against workspace → unclear cap, parent linkage failure | Medium | Medium | Block in v1; revisit in v2 with workspace-aware template. |
| R-3 | Cross-workspace leak via communication recipient lists (`communication_routes.py`) | **High — present today** | **High** | Fix B-3 before launch. |
| R-4 | Lazy workspace materialization race when two endpoints first-touch concurrently | Medium | Medium | Move to atomic eager bootstrap at registration. |
| R-5 | TenantIsolation middleware ignoring `itw_*` ids → broad query fall-through | Medium | High | Either teach middleware about workspace ids or gate every reuse with `require_request_school_id`. |
| R-6 | Reporting/export endpoints aggregating across all schools when called by indep teacher | Medium | High | Force scope in reporting layer; add isolation tests. |
| R-7 | Frontend `INDEPENDENT_TEACHER_PERMISSIONS` divergence from backend → user sees CTAs that 403 | High | Low–Medium | Source UI permissions from backend `/auth/me`. |
| R-8 | Storage abuse: unlimited classes/students per free workspace | Medium | Medium | Caps + quota table (Phase 2). |
| R-9 | Cascade delete of workspace wiping student/parent data with no recovery | Low | High | Soft-delete + admin confirmation modal (`NassaqAlertDialog`). |
| R-10 | AI Insights returning empty/unstable values when workspace has 0 students | Medium | Low | Already covered by `test_independent_teacher_empty_workspace_schema_parity`. Keep. |
| R-11 | N+1 in class/student/schedule reads when teacher loads dashboard | Medium | Medium | Use bulk `gd_find` with `$in`; add explain plans on workspace queries. |
| R-12 | Payload bloat on AI Insights for workspace with many students | Low (small workspaces) | Low | Reuse existing pagination/limits. |

---

## 8. Blockers (must resolve before implementation)

- **B-1** *Multiple-source-of-truth for workspace id and lazy materialization.* Three modules each resolve/create the workspace differently. Pick one path — eager bootstrap at registration via `auth_scope`/registration engine — and delete the other two. Without this, B-3/B-4 cannot be reasoned about.
- **B-2** *Smart engine has no capability gate.* Today `scheduling_smart_engine_routes` would accept an `independent_teacher` request and crash on `validate_data_readiness`. Add a `require_full_school_tenant` dependency before any indep-teacher write paths ship.
- **B-3** *Cross-workspace leak in `communication_routes.py`.* Recipient lists at lines 64, 325, 399, 464 query `users` by role without `tenant_id` filter. An indep teacher broadcasting today (once NOTIFICATIONS_SEND is granted) would address every other indep teacher's audience. **Tiny critical guard** — add `tenant_id` filter to those four queries before granting send permission.
- **B-4** *`TenantIsolation` middleware ignores synthetic ids.* Either patch `apply_tenant_filter` to recognize `itw_*` and treat it as a tenant, or audit every reuse path to confirm it calls `require_request_school_id` instead of trusting the middleware.
- **B-5** *No quota / cap on workspace size.* Without a class/student cap a single user can grow a workspace unbounded; pick a v1 cap (e.g. 5 classes / 200 students) and enforce in `class_management_engine` + `student_creation_routes`.
- **B-6** *Frontend permission catalog diverges from backend.* `INDEPENDENT_TEACHER_PERMISSIONS` in `CreateUserWizard.jsx` advertises a "freelancer applying to schools" model that the backend no longer matches. Replace with backend-sourced permissions before any onboarding redesign ships.

(Per the audit constraints these are reported here, **not silently fixed**, except B-3 — which is a small required guard for safe investigation and is recommended to ship as a prerequisite hotfix task.)

---

## 9. Phased Implementation Recommendation

### Phase 1 — MVP launch (must-have)

1. Resolve B-1, B-2, B-4, B-6; ship B-3 as prerequisite hotfix.
2. Build atomic `POST /independent-teacher/bootstrap` (workspace + settings + academic year/term + teacher row).
3. Onboarding wizard frontend.
4. Drop "coming soon" banner; enable manual class create + manual student create (with caps from B-5).
5. Light per-teacher schedule editor over `time_slots`.
6. Reuse session-based attendance, assessments (grant ASSESSMENTS_EDIT), behaviour, portfolio, AI Insights teacher slice, notifications-receive, calendar-read, communication DM (post B-3).
7. Workspace Settings page (working days, periods/day, year/term rename).
8. Add cross-workspace isolation tests for students/classes/attendance/notifications.
9. Hard-deny smart engine, bulk import, standby, staff attendance, principal management, school-wide broadcasts, approvals.

### Phase 2 — Enhancements (nice-to-have)

- Workspace-aware bulk import (custom Arabic template, no classroom assignment column).
- Parent invite + parent portal access for an independent teacher's students.
- Personal calendar event authoring.
- Quota plan tiers (free / pro) groundwork.
- Light AI lesson-planning assistant scoped to workspace.

### Phase 3 — Optional parity

- Stripped-down smart scheduling for solo teacher (single-teacher constraint solver).
- Cross-workspace collaboration ("co-teacher" invite).
- Public profile / discovery surface (the "apply-to-schools" idea hinted in the legacy frontend permission list).
- Subscription/billing module.

---

## 10. Recommendation — safest architecture choice

**Adopt the synthetic self-tenant ("personal workspace school") model that already exists in code, and harden it. Do not introduce a parallel `Workspace` table.**

Why:

1. **Lowest blast radius.** ~14 tables enforce `school_id NOT NULL` + `ON DELETE CASCADE`. Reusing `schools` keeps every existing query, index, audit log, AI engine, and report correct without schema migration.
2. **Existing precedent.** Auth scope, AI Insights, class management, academics-student, registration engine, approval handlers, notification engine, dashboard counters, admin role catalog, frontend route guard, sidebar, login redirect, role switcher and tests all already speak `independent_teacher` + `itw_{user_id}`. The cost of *finishing* this model is much lower than the cost of replacing it.
3. **Discriminator gives clean deny-by-default.** A single `school_type == 'independent_teacher_workspace'` check produces a uniform capability gate for every principal-only feature (see B-2 / §4.2). Deny-by-default flows naturally from "is this a real school tenant?".
4. **Tests already pin the contract.** `test_ai_insights_security.py` proves cross-workspace isolation works under this model.

What must change to make it safe (recap of blockers): collapse the resolvers to one (B-1), make bootstrap eager and atomic, add `require_full_school_tenant` (B-2), close the communication leak (B-3), make `TenantIsolation` aware of workspace ids (B-4), enforce caps (B-5), and source frontend permissions from the backend (B-6).

The alternative — a separate `workspaces` table or a polymorphic owner column — would require schema migrations on at least 14 tables, parallel query paths in every engine, and a re-audit of every existing tenant-isolation test. That is a high-risk refactor with no product benefit over the discriminator approach.

---

## 11. Open Questions

1. Is the long-term product goal still "freelance teacher who *applies to schools*" (as the legacy frontend permission list suggests), or "self-managed mini-school" (as the current backend model implements)? The two are not mutually exclusive but Phase 2 work depends on the answer.
2. Should the synthetic workspace be visible to platform admins as a "school" in the schools list? Today it is (it's a row in `schools`). Recommend filtering it out by `school_type` in the admin UI.
3. Caps for v1 (B-5): pick numbers — proposal 5 classes / 200 students / 1 academic year.
4. Should an independent teacher be allowed to be *also* invited to a real school (dual-tenant)? Today the role switcher supports multiple roles; confirm whether this is in scope for v1.
5. Data export on account closure — required for compliance? If yes, Phase 2 must include a workspace-export endpoint before deletion is exposed.
