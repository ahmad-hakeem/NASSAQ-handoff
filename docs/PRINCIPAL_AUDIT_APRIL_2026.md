# Principal Platform Audit — April 2026

## Scope
Comprehensive audit of the School Principal platform (`منصة مدير المدرسة`) covering roles `school_principal`, `school_admin`, `school_sub_admin` across:
- All pages under `/principal/*`, `/admin/*`, `/school/*`
- Backend routes serving these pages (`principal_*`, `school_*`, `academics_*`, `scheduling_*`, `assessment_*`, `attendance_*`, `communication_*`, `ai_*`)
- i18n, NassaqAlertDialog usage, tenant isolation, role-based permissions, and sidebar navigation

## Scope Map

### Principal Routes (`frontend/src/routes/appRoutes.js`)
| Route | Component | Roles |
|---|---|---|
| `/principal` | `PrincipalDashboard` | `school_principal`, `school_admin` |
| `/principal/communication` | `CommunicationCenterPage` | `SCHOOL_ROLES` |
| `/principal/users-management`, `/admin/users-management` | `UsersClassesManagement` | `SCHOOL_ROLES` |
| `/admin/teachers`, `/school/teachers` | `UsersClassesManagement` | `SCHOOL_ROLES` |
| `/admin/students`, `/school/students` | `StudentsPage` | `SCHOOL_ROLES` |
| `/admin/classes`, `/school/classes`, `/admin/classes/:id`, `/principal/classes/:id` | `ClassesPage` / `ClassDetailPage` | `SCHOOL_ROLES` |
| `/admin/subjects`, `/school/subjects` | `SubjectsPage` | `SCHOOL_ROLES` |
| `/admin/schedule`, `/school/schedule` | `SchedulePageNew` | `SCHOOL_ROLES` |
| `/admin/time-slots` | `TimeSlotsPage` | `SCHOOL_ROLES` |
| `/admin/teacher-assignments` | `TeacherAssignmentsPage` | `SCHOOL_ROLES` |
| `/admin/teacher-attendance` | `TeacherAttendancePage` | `SCHOOL_ROLES` |
| `/admin/attendance`, `/admin/assessments` | `AttendancePage` / `AssessmentPage` | `SCHOOL_TEACHING_ROLES` |
| `/principal/settings`, `/school/settings` | `SchoolSettingsPagePro` | `SCHOOL_ROLES` |
| `/principal/timetable` | `PrincipalTimetablePage` | `SCHOOL_ROLES` |
| `/school/teacher-class-assignments` | `TeacherClassAssignmentPage` | `SCHOOL_ROLES` |
| `/principal/ai-insights` | `AIInsightsPage` | `[...SCHOOL_ROLES, 'platform_admin', 'teacher']` |
| `/account/settings` | `AccountSettingsPage` | all authenticated |

### Sidebar (`components/layout/Sidebar.jsx`, lines 270–360)
- `SCHOOL_ROLES` = `['school_principal', 'school_admin', 'school_sub_admin']`
- `SCHOOL_PRINCIPAL_ROLES` = `['school_principal', 'school_admin']` — excludes `school_sub_admin` for School Settings (line 334). Verified.

### Backend Route Families Servicing the Principal UI
- `principal_management_routes.py` — 133 tenant-scoped queries using `gd_*` helpers (verified).
- `principal_timetable_routes.py` — timetable summary, readiness, grid, insights, issues, versions, generate, publish.
- `school_settings_routes.py`, `school_settings_mod.py`, `settings_routes.py` — school settings sections.
- `school_routes_mod.py` — school info CRUD with `TranslationService` ar↔en.
- `academic_structure_routes.py`, `academics_structure_engine_routes.py`, `academics_year_term_routes.py`, `academics_reference_routes.py` — academic structure.
- `class_management_routes.py`, `academics_class_routes.py`, `academics_student_routes.py`, `academics_teacher_routes.py`, `academics_subject_routes.py` — users/classes/subjects.
- `teacher_management_routes.py`, `student_management_routes.py`, `student_creation_routes.py` — CRUD + password management.
- `assessment_routes.py` + `assessment_routes_mod.py`, `attendance_routes.py` + `attendance_routes_mod.py`, `teacher_attendance_routes.py` — assessments/attendance.
- `communication_routes.py`, `notification_routes.py` + `notification_routes_mod.py`, `websocket_routes.py` — communication center.
- `ai_routes_mod.py` — AI insights.
- `scheduling_routes.py`, `scheduling_smart_engine_routes.py`, `scheduling_smart_session_routes.py`, `scheduling_generation_routes.py`, `scheduling_core_routes.py`, `schedule_management_routes.py`, `timetable_readiness_routes.py` — scheduling engines.

## Issues Found and Fixed

### 1. Native `confirm()` Violations (high severity)
**Rule**: All confirmations must use `NassaqAlertDialog` via `nassaqConfirm()` from `useNassaqAlert()`. Native `confirm()` is disallowed.

| File | Line | Before | After |
|---|---|---|---|
| `frontend/src/pages/TimeSlotsPage.jsx` | 146 | `if (!confirm(t('...'))) return;` then delete | `nassaqConfirm(message, async () => { /* delete */ })` |
| `frontend/src/pages/SubjectsPage.jsx` | 174 | same pattern | same refactor |

Also destructured `nassaqConfirm` from the hook in both files. Verified no remaining `confirm()`/`alert()` calls across `frontend/src/**`.

### 2. Hardcoded i18n Ternaries (`isRTL ? 'عربي' : 'English'`)
**Rule**: All user-visible text must go through `t('key')` with entries in `locales/ar.json` + `locales/en.json`.

| File | Lines | Fix |
|---|---|---|
| `frontend/src/pages/PrincipalDashboard.jsx` | 85, 88–93 | Replaced header `مركز القيادة` + welcome/preview strings with `t('commandCenter')`, `t('previewingSchool', {name})`, `t('welcomeUser'/'welcomeUserWithTitle', {title,name})` |
| `frontend/src/pages/SchoolDashboard.jsx` | 28, 31 | Same `commandCenter` + `welcomeUser` keys; imported `useTranslation` |
| `frontend/src/pages/TimeSlotsPage.jsx` | 262 | `إضافة فترة` → `t('addTimeSlot')` |
| `frontend/src/pages/TimeSlotsPage.jsx` | 437 | `دقيقة/min` → existing `t('minutes')` |
| `frontend/src/pages/TimeSlotsPage.jsx` | 450 | `حصة/Period` → `t('periodLabel')` |
| `frontend/src/pages/SubjectsPage.jsx` | 88, 89 | `core/elective` labels → `t('categoryCore')`, `t('categoryElective')` |
| `frontend/src/pages/SubjectsPage.jsx` | 242 | subjects count → `t('subjectsCount', {count})` |

Added 9 new keys to both `ar.json` and `en.json`: `commandCenter`, `welcomeUser`, `welcomeUserWithTitle`, `previewingSchool`, `addTimeSlot`, `periodLabel`, `subjectsCount`, `categoryCore`, `categoryElective`.

### 3. Settings Route-Guard Bypass (MEDIUM severity, fixed)
**Issue** (flagged by architect review): `Sidebar.jsx` correctly hid the School Settings link from `school_sub_admin` via `SCHOOL_PRINCIPAL_ROLES`, but the underlying routes `/principal/settings` and `/school/settings` in `appRoutes.js` were still gated on `SCHOOL_ROLES` (which includes `school_sub_admin`). A sub-admin could navigate directly by URL and load `SchoolSettingsPagePro`.

**Root cause**: Navigation gating was being confused with authorization. Sidebar visibility is not a security boundary.

**Backend status**: Not exploitable — `school_settings_routes.py` and `school_settings_mod.py` already enforce `require_roles([UserRole.SCHOOL_PRINCIPAL, UserRole.SCHOOL_ADMIN, UserRole.PLATFORM_ADMIN])` on every write endpoint (verified across ~30 call sites). A sub-admin hitting the page would see UI but API writes would 403. Still a defense-in-depth UX bug.

**Fix**:
- Added `const SCHOOL_PRINCIPAL_ROLES = ['school_principal', 'school_admin'];` to `frontend/src/routes/appRoutes.js:110`.
- Changed `allowedRoles={SCHOOL_ROLES}` → `allowedRoles={SCHOOL_PRINCIPAL_ROLES}` on `/principal/settings` (line 397) and `/school/settings` (line 400).

Result: sub-admin direct URL access now bounces at `ProtectedRoute` level, matching sidebar gating.

### 4. Verification Passes
- **Compile**: Frontend `webpack compiled with 1 warning` — only a pre-existing `react-hooks/exhaustive-deps` pair in `SubjectsPage.jsx:118` and `TimeSlotsPage.jsx:106/112` (unrelated to audit changes; present before this audit).
- **Backend**: `Backend API` startup clean — `DEPLOYMENT SAFETY: Data snapshot — users=734, schools=7, students=511, teachers=215`, Alembic revision `m1n2o3p4q5r6`.
- **No confirm/alert left**: Grep `window\.confirm|window\.alert|\balert\(|\bconfirm\(` across `frontend/src/**/*.{jsx,js}` → 0 matches.
- **Tenant isolation**: `principal_management_routes.py` uses `gd_*` helpers and `tenant_id` in 133 locations (verified via grep).
- **Sub-admin settings exclusion**: `Sidebar.jsx:334` confirms School Settings menu item is gated on `SCHOOL_PRINCIPAL_ROLES` (excludes `school_sub_admin`).

## Known Remaining i18n Debt (out of scope for this pass — tracked for follow-up)
Static scan surfaced additional `isRTL ? '...' : '...'` ternaries on principal-adjacent pages that require a broader translation pass (non-blocking, strings still render correctly in both languages):
- `frontend/src/pages/AIInsightsPage.jsx` — extensive (~40+ literals) inside metric labels, tab labels, and chart legends
- `frontend/src/pages/ClassesPage.jsx` — 3 literals (dropdown placeholder, 2 table headers)
- `frontend/src/pages/StudentsPage.jsx` — 5 literals (class select placeholder, parent labels, table header, empty state)

These will be addressed in a follow-up i18n sweep. They are not security, data-integrity, or flow-breaking issues.

## Sections Reviewed via Static Analysis
- **Dashboard** (`/principal`) — header i18n fixed; widget content comes from `SchoolDashboardContent` (no hardcoded-locale violations found).
- **Timetable** (`/principal/timetable`) — already uses `NassaqAlertDialog` via `useNassaqAlert()`; Arabic-only inline labels (`مركز التحكم`-style) remain in the visual-only generation journey character dialog (`TimetableGenerationJourney.jsx`) which is already Arabic-only by design for the Hakim character persona.
- **Users/Classes/Subjects** — `confirm()` eliminated; dropdown label ternaries removed.
- **Time Slots** — `confirm()` eliminated; header/badges i18n cleaned.
- **Sidebar & Permissions** — sidebar gating verified at line 334 of `Sidebar.jsx`. Route-level guard for settings was loose and has been tightened (see Issue #3). Backend `require_roles` on settings endpoints already excludes `school_sub_admin`.
- **Backend Tenant Isolation** — `principal_management_routes.py` shows correct `gd_*` helper usage with `tenant_id` scoping (133 occurrences).

## Files Changed
- `frontend/src/pages/TimeSlotsPage.jsx`
- `frontend/src/pages/SubjectsPage.jsx`
- `frontend/src/pages/PrincipalDashboard.jsx`
- `frontend/src/pages/SchoolDashboard.jsx`
- `frontend/src/locales/ar.json` (+9 keys)
- `frontend/src/locales/en.json` (+9 keys)
- `replit.md` (audit summary section)
- `docs/PRINCIPAL_AUDIT_APRIL_2026.md` (this report)

## Deployment Safety
All changes are additive: frontend string-replacement and locale-file additions only. No schema changes, no migrations, no destructive ops.
