# NASSAQ - نَسَّق
## Smart Multi-Tenant School Management System

A full-stack school management platform with React frontend and FastAPI backend.

## Scheduling System (Single Source of Truth — April 18, 2026)

The codebase previously had **two parallel scheduling systems**. The OLD system was fully removed. Only the NEW Smart Scheduling system remains.

**Active (NEW) system:**
- Engine: `backend/engines/smart_scheduling_engine.py`
- Routes: `backend/routes/scheduling_smart_engine_routes.py` (`/api/smart-scheduling/*`), `scheduling_smart_session_routes.py`, `schedule_candidates_routes.py`, `timetable_readiness_routes.py`
- Storage: `timetables` and `timetable_sessions` keys in the `generic_documents` collection (NOT real ORM tables)
- Frontend page: `frontend/src/pages/SchedulePageNew.jsx` — mounted at `/school/schedule` and `/admin/schedule`
- Frontend components: `frontend/src/components/schedule/` (CandidatesSidePanel, TeacherScheduleGrid, WaitingSessionsPanel)
- Back-compat: `/principal/timetable` redirects to `/school/schedule` in `appRoutes.js`

**Removed (OLD) system — DO NOT recreate:**
- Routes: `scheduling_core_routes.py`, `scheduling_generation_routes.py`, `scheduling_routes.py`, `schedule_management_routes.py`, `principal_timetable_routes.py`
- Engines: `scheduling_engine.py`, `schedule_management_engine.py`
- Service: `services/scheduling_service.py` (and its export from `services/__init__.py`)
- Frontend: entire `frontend/src/components/timetable/` folder (15 files incl. `PrincipalTimetablePage.jsx`, `TimetableModals.jsx`, `HakimCharacter.jsx`)
- Tables: `schedule_sessions` truncated (1260 stale rows); `schedules` table never existed
- Tests removed: `test_foundation_phase.py`, `test_timetable_tenant_isolation.py`, `test_scheduling_api.py`; `test_count_real_conflicts` removed from `test_detect_conflicts_via_registry.py`

**Kept but unrelated to scheduling:**
- `backend/engines/session_engine.py` — teacher session/attendance tracking (28 references, NOT old scheduling)

## Development Standards & Quality Checklist

Every task must follow these principles before delivery:

### Pre-Development Verification
- Verify actual DB roles (not assumed names) before any permission logic
- Compare backend required fields vs frontend form fields (Schema Alignment)
- Verify all imports and function dependencies in the code path
- Confirm dropdown/lookup sources are DB-driven (lookup_options collection first, hardcoded fallback only)

### Schema Alignment Rules
- No field required in backend but missing from frontend form
- No field in frontend that isn't wired to actual save/submit
- Field names must match exactly between frontend, API, and DB
- Pydantic models, API contracts, and UI forms stay in sync

### Permission & Role Rules
- Always check actual DB role names (school_admin, school_sub_admin, teacher, student, parent, platform_admin, platform_operations_manager)
- Never use hardcoded role assumptions — verify against DB
- Every create/update/delete flow must have roles reviewed before implementation

### Dropdown Standard
1. Read from DB (lookup_options collection) first
2. Fallback to hardcoded defaults only when DB returns empty
3. Must be manageable from settings later
4. No rigid frontend-only values except as last resort

### Pre-Delivery Checklist (every task)
- [ ] Roles verified against DB
- [ ] Required fields verified (backend ↔ frontend)
- [ ] All imports verified in code path
- [ ] API contract verified (request/response schema)
- [ ] DB schema verified (field names, types)
- [ ] UI form submission tested
- [ ] Success and error handling tested
- [ ] Regression check on related flows
- [ ] No silent errors (missing deps, imports, role mismatches caught early)

### Stability Rules
- No fix should break existing working flows
- No changes to stable logic unless strictly necessary
- Regression test on connected parts after any change
- Discover and fix issues before delivery, not after user encounters them

### Internationalization (i18n) System — Task #60
- **Architecture**: JSON locale files (`frontend/src/locales/ar.json`, `en.json`) with 2600+ translation keys
- **Hook**: `useTranslation()` from `contexts/ThemeContext.js` — returns `{ t, language, localizedValue }`
- **`t(key, params)`**: Static UI text translation. Supports parameter interpolation with `{param}` syntax — e.g., `t('sentToRecipients', { count: 5 })`
- **`localizedValue(item, field)`**: Dynamic data localization — returns `item.name_ar` or `item.name_en` based on current language, with fallback chain
- **Backend TranslationService**: `backend/services/translation_service.py` — OpenAI-powered ar↔en auto-translation on save. Integrated into school info and subject routes.
- **Functions**: `translate_text(text, source, target)`, `translate_fields(data, fields)`, `detect_language(text)`
- **Conversion**: 4300+ `isRTL ? 'عربي' : 'English'` ternaries converted to `t('key')` calls across 109 files
- **Remaining `isRTL` uses**: Legitimate CSS direction (`'rtl'`/`'ltr'`, `'left'`/`'right'`), icon swaps (`ArrowLeft`/`ArrowRight`), dynamic data display (`item.name_ar`/`item.name_en`), template literals with variables
- **Adding new translations**: Add key to both `ar.json` and `en.json`, use `t('key')` in JSX
- **Old `translations` export**: Still available from `ThemeContext.js` as `translations` (aliased to `locales`) for backward compatibility

### Cumulative Analytics (Task #76)
- **Component**: `frontend/src/components/parent/CumulativeAnalytics.jsx` — role-aware analytics section
- **Charts**: Uses existing `AnalyticsCharts.jsx` (GaugeChart, PerformanceLine, SubjectRadar from Recharts)
- **Parent view** (`ChildDetailsPage.jsx`): Analytics tab shows performance summary, gauge/line charts, radar chart, strengths/weaknesses, and home follow-up indicator
- **Student view** (`StudentProfilePage.jsx`): Shows same charts minus sensitive data (no follow-up indicator, no health/behavioral/social data)
- **Backend endpoints**: Parent uses existing `/parent-portal/child/{child_id}/analytics`, Student uses new `/student-portal/my-analytics`
- **Follow-up status**: Arabic labels — "مستقر" (stable), "يحتاج متابعة" (needs follow-up), "بحاجة دعم" (needs support)
- **Locale keys**: `cumulativeAnalytics`, `performanceSummary`, `overallLevel`, `classAverage`, `comparedToClass`, `performanceTrend`, `monthlyTrajectory`, `subjectDistribution`, `homeFollowUp`, `compositeScore`, `homeworkCompletion`, `noAnalyticsData`

### WebSocket Security
- **Auth method**: Token sent via message after connection (NOT in URL query string) to prevent token leakage in server access logs
- **Flow**: Client connects → sends `{type: "auth", token: "..."}` → server validates → registers connection
- **Backward compat**: Server still accepts `?token=` query param as fallback, but frontend no longer uses it
- **Files**: `frontend/src/contexts/WebSocketContext.jsx`, `backend/routes/websocket_routes.py`

### Content Security Policy
- **CSP header** set in `backend/app/middleware.py` with directives for script, style, font, img, media, connect sources
- **media-src**: `'self' https:` — allows notification sounds from external HTTPS sources
- **Do NOT** add `unsafe-eval` or broad wildcards without security review

### Alert & Warning System
- All warning/error/confirm dialogs use `NassaqAlertDialog` component (`frontend/src/components/ui/NassaqAlertDialog.jsx`)
- `NassaqAlertProvider` wraps the app in `App.js` — all components can use `useNassaqAlert()` hook
- Available methods: `nassaqWarning(msg)`, `nassaqError(msg)`, `nassaqSuccess(msg)`, `nassaqInfo(msg)`, `nassaqConfirm(msg, onConfirm, options)`
- RTL Arabic-first design with themed icons and colors per alert type
- **Do NOT use** `alert()`, `window.confirm()`, or `toast.error()` for important warnings — use the nassaq alert dialog instead
- **COMPLETED**: All `toast.error()` and `toast.warning()` calls across 76+ files converted to `nassaqError()`/`nassaqWarning()`. Only `toast.success()` remains for non-blocking success notifications.
- **Import paths**: From `pages/` use `'../components/ui/NassaqAlertDialog'`; from `pages/SubDir/` use `'../../components/ui/NassaqAlertDialog'`; from `components/*/` use `'../ui/NassaqAlertDialog'`

### Hijri/Gregorian Date System
- **Library**: `hijri-converter` (Python backend, Umm al-Qura calendar) + `hijri-converter` (npm frontend)
- **Centralized utility**: `frontend/src/utils/hijriDate.js` — `formatHijriDate()`, `formatHijriOnly()`, `formatGregorianArabic()`, `getHijriDate()`
- **Format**: `الاثنين ٢٧ رمضان ١٤٤٧ هـ  —  ١٦ مارس ٢٠٢٦` (with Eastern Arabic numerals)
- **Backend**: `get_hijri_date()` in `admin_dashboard_routes.py` uses `hijri_converter.Gregorian` for accurate Umm al-Qura conversion
- **Do NOT use** `Intl.DateTimeFormat('ar-SA-u-ca-islamic')` — it's browser-dependent and inaccurate by 1-2 days vs official Saudi calendar
- All dashboard pages (Teacher, Student, Parent, Admin, Portals) use the centralized utility

### Security Hardening (Bug Audit — April 2026)
- **Sensitive field filtering**: `security_routes.py` `/account-status/{user_id}` strips `password_hash`, `password`, `refresh_token`, `reset_token` before returning user data
- **Seed admin password**: No longer hardcoded in source code — requires `NASSAQ_SEED_ADMIN_PASSWORD` environment variable
- **SQL filter blocking**: `sql_utils.py` blocks filters on sensitive columns (`password_hash`, `password`, `refresh_token`, `reset_token`) in both ORM and JSONB query paths — logged as warnings
- **Regex sanitization**: All `$regex` filter operators in `sql_utils.py` are escaped via `re.escape()` and length-limited (200 chars) to prevent ReDoS attacks
- **Auth error logging**: `auth_service.py` now logs database lookup failures during JWT validation instead of silently swallowing them
- **Exception logging**: Swallowed exceptions in `notification_engine.py`, `websocket_routes.py`, and `identity_engine.py` now log with proper error context
- **Tenant isolation warnings**: `warn_missing_tenant_filter()` utility in `middleware/tenant_isolation.py` — logs warnings when tenant-scoped collections are queried without tenant filters
- **CSP cleanup**: Removed `cdn.tailwindcss.com` from Content-Security-Policy in both `backend/app/middleware.py` and `frontend/craco.config.js`; added `media-src 'self' https:` to frontend CSP
- **AuthContext stability**: `api` axios instance memoized with `useMemo`; interceptors properly set up and cleaned up via `useEffect`
- **React key fixes**: `SchoolDashboardContent.jsx` uses stable keys (`cat.label`, `item.path`) instead of array indices

### Security Hardening Phase 2 (Comprehensive Audit — April 9, 2026)
- **Token key mismatch fix**: `AccountSettingsPage.jsx` role-switch now uses `nassaq_token` key (was `token`), matching AuthContext; `PrincipalTimetablePage.jsx` removed fallback to old `token` key
- **Access token expiry**: `ACCESS_TOKEN_EXPIRE_MINUTES` reduced from 129600 (90 days) to 30 minutes in `backend/.env` — access tokens are short-lived; refresh tokens handle session persistence
- **Token refresh race condition**: `AuthContext.js` `attemptTokenRefresh()` now uses promise deduplication — concurrent 401s share a single refresh call instead of racing
- **Teacher password generation**: `academics_teacher_routes.py` `POST /teachers` now generates unique temp password (`Tch{random}!`) instead of hardcoded `Teacher@123`; sets `must_change_password: true`; returns `temp_password` in response
- **Security dashboard memory fix**: `security_routes.py` dashboard and AI report replaced `gd_find(limit=50000)` with `gd_count()` queries — no longer loads all users into memory
- **API key encryption**: `platform_routes_mod.py` integrations now encrypt `api_key` using Fernet symmetric encryption when `NASSAQ_ENCRYPTION_KEY` env var is set; graceful fallback to plaintext if key not configured
- **Error message sanitization**: Replaced `str(e)` in API responses with safe Arabic messages in `auth_routes_mod.py`, `teacher_registration_routes.py`, `audit_routes.py`, `user_routes_mod.py`
- **WebSocket token URL removed**: `websocket_routes.py` no longer accepts `?token=` query parameter — token must be sent via post-connection `{type: "auth", token: "..."}` message only

### Cross-Platform Integration Verification (April 2026)
- **Pydantic model fixes**: `UserResponse` fields (`has_generic_name`, `preferred_theme`, `created_at`) and `ClassResponse` fields (`capacity`, `is_active`, `current_students`, `student_count`) changed from required to `Optional` with defaults — DB records with NULL values were causing HTTP 500 on `/api/users` and `/api/classes`
- **Skills-types FK fix**: `role_dashboards_mod.py` auto-seed audit log insert changed from `performed_by="system"` to `performed_by=current_user.id` — the `audit_logs.performed_by` FK constraint requires a valid user ID
- **System proxy**: `setupProxy.js` now includes `/system` proxy rule alongside `/api` — health check endpoints route correctly through CRA dev proxy
- **WebSocket**: Uses `/api/ws/notifications` path, proxied through existing `/api` rule with `ws: true` — no separate WS proxy needed
- **Student user account**: Created student role user (`fares.student@nassaq-test.com`) linked to existing student record for full portal testing
- **Verified platforms**: Platform Admin, School Principal, School Admin, Teacher, Student, Parent — 53/53 endpoints passing across all 6 roles

### Scheduling & Academic Structure Audit (April 16, 2026)
- **Smart scheduling pre-validation fix**: `can_proceed` in `smart_scheduling_engine.py` was `len(critical_issues) <= 2` — allowed proceeding with missing teachers/settings/classes. Fixed to block on essential categories: `teachers`, `teacher_assignments`, `settings`, `classes`, `time_slots`, `academic_year`, `academic_term`, `grades`, `subjects`, `grade_subjects`
- **Time slot validation**: `create_time_slot` in `scheduling_engine.py` had no validation — could create slots with end_time before start_time or overlapping with existing slots. Added `_parse_time()` method with `datetime.time` parsing (not string comparison), overlap detection, and same validation in `update_time_slot`
- **Registration request IntegrityError**: Production 500 errors on `POST /registration-requests` — `type` column null despite validation. Root cause: `**submission_data` spread mixed Pydantic fields with ORM columns unpredictably via `dict_to_model`. Fixed by explicitly mapping ORM columns (`type`, `name`, `email`, `phone`, `school_name`) and storing remaining fields in `data` JSONB column. Ensured `account_type` and `full_name` preserved in `data` for downstream queries.
- **Files changed**: `backend/engines/smart_scheduling_engine.py`, `backend/engines/scheduling_engine.py`, `backend/routes/registration_routes_mod.py`

### Principal Platform Audit (April 16, 2026)
- **Scope**: Full audit of the School Principal platform (`school_principal`, `school_admin`, `school_sub_admin`) across all `/principal/*`, `/admin/*`, `/school/*` routes and their backend counterparts.
- **confirm() violations eliminated**: `TimeSlotsPage.jsx` (delete time slot) and `SubjectsPage.jsx` (delete subject) were using native `confirm()` — both refactored to `nassaqConfirm()` with async callback pattern. Grep across `frontend/src/**/*.{jsx,js}` now returns 0 native `confirm()`/`alert()` calls.
- **Hardcoded i18n strings fixed (first pass)**: `PrincipalDashboard.jsx`, `SchoolDashboard.jsx`, `TimeSlotsPage.jsx`, `SubjectsPage.jsx` — header, welcome/preview, add-slot, duration, period badge, category labels, subjects count.
- **Hardcoded i18n strings fixed (full principal-scope sweep, 99 replacements across 11 pages)**: `UsersClassesManagement.jsx` (39), `AIInsightsPage.jsx` (24), `TeacherAssignmentsPage.jsx` (6), `ClassDetailPage.jsx` (6), `StudentsPage.jsx` (5), `CommunicationCenterPage.jsx` (5), `AccountSettingsPage.jsx` (5), `ClassesPage.jsx` (3), `TeacherAttendancePage.jsx` (2), `AttendancePage.jsx` (2), `AssessmentPage.jsx` (2). After sweep, all `isRTL ? '…' : '…'` ternaries on these pages that contained user-visible text are eliminated; remaining 9 instances are all legitimate non-text uses (`ar-SA`/`en-US` for `Intl`, `rtl`/`ltr` for `dir`, `right-0`/`left-0` for Tailwind CSS, `ar`/`en` as field-name selector).
- **New i18n keys** (~60 total added to both `ar.json` and `en.json`, now 3508 keys each): first-pass 9 (`commandCenter`, `welcomeUser`, `welcomeUserWithTitle`, `previewingSchool`, `addTimeSlot`, `periodLabel`, `subjectsCount`, `categoryCore`, `categoryElective`) + second-pass batch (`suspendAccount`, `activateAccount`, `parentRole`, `sessionsPerWeek`, `operationFailed`, `addNew`, `newestFirst`, `oldestFirst`, `downloading`, `dailyTrend`, `quickTemplates`, `staffAttendanceMgmt`, `examsAssessmentsMgmt`, `aiSmartInsights`, `teacherMonitoringInsights`, `overallAttendanceRate`, `positiveBehaviorRate`, `liveData`, `critical`, `passRate`, `attendanceLabel`, `avgGrade`, `positiveBehavior`, `negativeBehavior`, `totalStudentsLabel`, `subjectsAssessed`, `participation`, `behaviorRecords`, `updatedLabel`, `usersClassesMgmt`, `editDetails`, `classLabel`, `gradeLabel`, `homeroomLabel`, `parentPhone`, `noStudentsFound`, `messageContent`, `studentLower`, `teacherLower`, `parentLower`, `classLower`, `studentsLower`, `yearsLabel`, `assignmentsCount`, `sessionsLabel`, `subjectsLabel`, `teachersLabel`, `realNameHint`, etc.). Parameter placeholders use single-brace `{name}` / `{count}` syntax to match `ThemeContext.t()` interpolation.
- **Settings route-guard bypass fixed** (found via architect review): Sidebar correctly hid School Settings from `school_sub_admin`, but `appRoutes.js` had `/principal/settings` and `/school/settings` gated on `SCHOOL_ROLES` (which includes sub_admin) — direct URL would load the page. Added `SCHOOL_PRINCIPAL_ROLES = ['school_principal','school_admin']` constant and applied to both routes. Backend `school_settings_routes.py`/`school_settings_mod.py` already enforced `require_roles([SCHOOL_PRINCIPAL, SCHOOL_ADMIN, PLATFORM_ADMIN])` so writes were never exploitable — this was a defense-in-depth UX fix.
- **Verified**: Sidebar role gating at `Sidebar.jsx:334` consistent with route guards. Backend tenant isolation confirmed — `principal_management_routes.py` uses `gd_*` helpers with `tenant_id` across 133 query sites.
- **Principal-scope i18n debt resolved**: previously-flagged debt in `AIInsightsPage`, `ClassesPage`, `StudentsPage`, `UsersClassesManagement`, and related pages was cleared in the second pass (see above). Remaining `isRTL` usages outside principal scope (teacher/platform-admin/parent modules) continue to be tracked separately.
- **Compile**: 0 new warnings introduced (1 pre-existing `react-hooks/exhaustive-deps` in `TimeSlotsPage`/`SubjectsPage` predates this audit).
- **Report**: `docs/PRINCIPAL_AUDIT_APRIL_2026.md`

### School Settings Persistence Bug Fix (April 18, 2026)
- **Symptom**: Saving timing settings (dayStart, periodDuration, breakDuration) appeared to succeed (toast shown, regen ran) but the values reverted to defaults on reload — only `periodsPerDay` survived. Hidden settings tabs (timings/unavailability/constraints) and POST `/api/teacher-assignments` 405 were also fixed in the same audit.
- **Root cause**: `SchoolSettings` ORM model in `pg_models.py` exposes legacy column names — `start_time`, `end_time`, `period_duration`, `break_duration`, `periods_per_day`, `working_days`, `custom_settings` (JSONB) — but every writer (PUT `/school/settings`, school create routes, approval handler) was passing new-style keys (`school_day_start`, `period_duration_minutes`, `break_duration_minutes`, `school_day_end`). `apply_updates()` in `engines/sql_utils.py` silently drops unknown keys when the ORM has no `data` column. Only `periods_per_day` happened to match an actual column name, which is why it was the single field that persisted.
- **Fix** (5 files):
  1. `routes/school_settings_mod.py` — PUT `/school/settings` now writes to actual ORM columns (`start_time`, `end_time`, `period_duration`, `break_duration`, `periods_per_day`) AND mirrors new-style names into `custom_settings` JSONB (read-modify-write merge to preserve unrelated keys). GET handler reads with priority `custom_settings` → nested `settings.*` → ORM columns.
  2. Added shared helper `normalize_school_settings_doc(raw)` (in same module) that maps new-style keys to ORM columns and bundles extras into `custom_settings`.
  3. `routes/school_routes_mod.py` (2 sites) and `engines/approval_handlers.py` — wrap school-creation default settings dicts with `normalize_school_settings_doc(...)` so new schools no longer silently lose 5 of 6 timing fields.
  4. `engines/smart_scheduling_engine.py` `load_school_settings()` — same fallback chain so the scheduler reads the freshly-saved values.
  5. `routes/timetable_readiness_routes.py` `_run_readiness_checks_impl()` — read `custom_settings.periods_per_day` / `period_duration_minutes` / `school_day_start` first.
- **Verified**: `PUT {dayStart:08:30, periodsPerDay:6, periodDuration:50, breakDuration:25, academicYear:1447, attendancePattern:summer}` → GET returns the same values; raw doc shows `start_time=08:30, period_duration=50, break_duration=25, periods_per_day=6` AND `custom_settings={school_day_start:08:30, period_duration_minutes:50, ...}`. Reset back to defaults also verified.
- **Sibling fixes shipped same day**: `SchoolSettingsPagePro.jsx` `dynamicTabs` array gained 3 missing entries (`timings`, `unavailability`, `constraints`) so all 6 `DynamicSettingsContent` tabs render. Added GET/POST/DELETE `/api/teacher-assignments` endpoints (writing to `teacher_assignments` collection shared with smart_scheduling) — tested create + idempotent-duplicate + delete.
- **Follow-up: missing `/api/time-slots` endpoint** — `SchedulePageNew.jsx` calls `GET /api/time-slots?school_id=...` to render the schedule, but no such endpoint existed (frontend swallowed the 404 with `.catch(() => ({ data: [] }))`, leaving `timeSlots` empty and showing the "لم يتم تحديد الفترات الزمنية" empty state even when slots existed in the DB). Added `GET /api/time-slots` in `school_settings_mod.py` — accepts `?school_id=...` (falls back to `X-School-Context`), enforces cross-school access guard, returns slots sorted by `period_number` (with `slot_number` fallback). Verified: returns 9 slots for the test school after a settings save.
- **Follow-up: scheduling distribution + read-limit bugs** — User reported coverage stuck at ~71% with Tuesday/Wednesday heavily under-filled. Two distinct bugs in `engines/smart_scheduling_engine.py`:
  1. **Day-order bias**: main placement loop (`_run_csp_placement`, ~line 1410) iterated `for day in working_days:` in fixed order for every demand, so subjects with `weekly_periods < len(working_days)` always landed on the first N days (Sun/Mon) and never reached the tail (Wed/Thu). Same bias in the gap-filler loop (~line 1584). Fix: rotate the day order per demand (`offset = demand_index % len(working_days)`, `rotated_days = working_days[offset:] + working_days[:offset]`) and similarly per class in the gap-filler. Also fixed the `days_left` calculation that previously used `working_days.index(day)` which misbehaves under rotation — now uses `enumerate(rotated_days)`.
  2. **Read-side truncation**: `get_timetable_sessions()` (line 2785) used `limit=500` while a fully-scheduled school has 5 days × 7 periods × 20 classes = 700 sessions. Because the query is `ORDER BY day_of_week ASC` (alphabetical: monday→sunday→thursday→tuesday→wednesday), the cutoff lopped off the tail — Wednesday returned **zero** rows even though 140 existed in the DB. Bumped to `limit=50000` (matches `validate_before_publish`).
- **Verified end-to-end**: post-fix regenerate → DB has 700 sessions evenly distributed (140/day including Wednesday); GET `/timetable/{id}/sessions` returns all 700; every class shows `{sun:7, mon:7, tue:7, wed:7, thu:7}`. UI "حصص غير مستوفية" panel should now be empty.

### Teacher Platform Bug Audit (April 16, 2026)
- **Sidebar layout bug**: `TeacherSessionsManagePage.jsx` used `<Sidebar />` as sibling with `<main>` instead of wrapper pattern — fixed to match all other teacher pages
- **confirm() violation**: `TeacherResourcesPage.jsx` used native `confirm()` for delete — replaced with `nassaqConfirm()` from `useNassaqAlert()`
- **Hardcoded i18n strings**: 10+ `isRTL ? 'Arabic' : 'English'` violations across `TeacherSettingsPage.jsx`, `TeacherSessionsManagePage.jsx`, `SessionsManageTab.jsx` — replaced with `t()` calls
- **Gender/RTL inversion**: `SessionStartPage.jsx` swapped male/female columns based on `isRTL` direction instead of actual gender — fixed to use gender data
- **useCallback stale closures**: Removed unnecessary `isRTL` from dependency arrays in 4 files (`TeacherClassesPage`, `TeacherAttendanceManagePage`, `TeacherSchedulePage`, `TeacherStudentsPage`); added missing `nassaqError` and `t` deps
- **New i18n keys**: Added 14 translation keys to both `ar.json` and `en.json` for previously hardcoded strings
- **Result**: Clean compile with 0 warnings, all teacher module pages verified

### Post-Fix Documentation
Each fix report must include: root cause, why it wasn't caught before, what changed, how recurrence is prevented, what was tested

### Deployment Safety Policy (PERMANENT & NON-NEGOTIABLE)
- **Core Rule**: Production data must NEVER be lost, overwritten, or replaced during deployment
- **Database**: Replit co-located PostgreSQL via `DATABASE_URL` — <1ms latency (migrated from Supabase EU ~291ms)
  - Pool: `pool_size=15, max_overflow=25, pool_recycle=300, pool_use_lifo=True, pool_pre_ping=True`
  - 99 FK constraints, 6 unique constraints, 259 indexes enforced at DB level (27 FK indexes added in migration i1j2k3l4m5n6)
  - **In-memory caching**: `/public/stats` (60s TTL in `school_routes_mod.py`), `/admin/command-center/stats` (30s TTL in `dashboard_routes_mod.py`)
- **Seed Scripts**: BLOCKED in production and staging (`config.seed_allowed()` returns `False`)
- **Double Guard**: Even if seeds allowed, they are SKIPPED when database already has data (user count > 0)
- **Replit DB Guard**: If DATABASE_URL points to Replit's managed DB (helium), seeds blocked unless ENVIRONMENT is explicitly "development"
- **Destructive Ops**: BLOCKED in non-development environments (`config.destructive_ops_allowed()`)
- **Safe Migrations Only**: Add fields, collections, indexes — NEVER drop, delete, rename, or truncate
- **No create_all**: Schema managed exclusively via Alembic — no `Base.metadata.create_all()` anywhere in codebase
- **No DROP TABLE**: No `drop_all()` or table drops in any startup path
- **Startup Data Snapshot**: Every startup logs `DEPLOYMENT SAFETY: Data snapshot — users=N, schools=N, students=N, teachers=N` for audit trail
- **Backup Script**: `python backend/scripts/backup_db.py` creates JSON snapshot; `python backend/scripts/backup_db.py verify <snapshot>` compares post-deploy
- **Build Script** (`build.sh`): Validates JWT_SECRET_KEY and DB_NAME before production builds
- **Startup Safety**: `server.py` logs environment, DB name, seed status; runs deployment checklist in production
- **Safety Endpoint**: `GET /system/deployment-safety` — full pre-flight checklist (admin only)
- **Environment Separation**: DEV (test data), STAGING (masked data), PROD (real data only) — each with separate DB/env vars
- **Pre-Deployment Checklist**: Environment set, DB production-safe, seeds blocked, destructive ops blocked, JWT configured, CORS configured
- **Documentation**: `backend/DEPLOYMENT_SAFETY.md` — complete policy reference

### Production Readiness (Applied)
- **JWT Security**: No hardcoded fallback — generates ephemeral secret if env var missing, logs warning
- **CORS**: Uses `CORS_ORIGINS` from config (env-based), not hardcoded `*`
- **Error Messages**: All API errors return safe Arabic messages — no `str(e)` exposure to users
- **Silent Failures**: All bare `except:` replaced with specific exception types (`ValueError`, `KeyError`, `TypeError`, etc.). All `except Exception: pass` in engines replaced with logged warnings/debug messages.
- **Structured Logging**: JSON-formatted logs via `StructuredJsonFormatter` with fields: ts, level, logger, msg, request_id, user_id, tenant_id, method, path, status_code, duration_ms
- **Request Tracing**: `RequestTracingMiddleware` generates UUID per request, propagated via ContextVar, emitted as `X-Request-Id` response header
- **Slow Query Detection**: SQLAlchemy event listeners log queries >500ms with SQL (truncated 500 chars) + params (truncated 300 chars)
- **Session Rollback Safety**: All database operations use `gd_*` helpers from `engines/sql_utils.py` which handle session management safely
- **Middleware Session Guard**: `pg_session_middleware` checks `session.is_active` before committing; rolls back failed sessions gracefully
- **Entity Creation Validation**: `create_class`, `create_student`, `create_teacher` all validate `school_id` is present before DB insert — returns 400 with bilingual error if missing
- **Tenant Isolation in Dashboards**: Teacher dashboard fallback query (email/name search) includes `school_id` filter; Student dashboard validates `school_id` matches user's `tenant_id`
- **Frontend Error Handling**: Axios interceptor handles 401 (auto-logout + redirect), 429 (rate limit toast), 500+ (server error toast), 502/503 (retry with backoff)
- **WebSocket Cleanup**: Both `WebSocketDisconnect` and generic `Exception` handlers clean up connection manager state (active_connections, role_connections, tenant_connections)
- **Pydantic Models**: `TeacherCreate`, `StudentCreate`, `ClassCreate` include all fields used by routes (school_id, full_name_en, gender, etc.) with `extra="ignore"` config
- **Pool Monitoring**: Background asyncio task logs pool stats every 60s; `/system/health` returns pool_size, checked_out, overflow, checked_in
- **Integration Tests**: `backend/tests/test_integration_phase5.py` — 17 tests covering health, auth, school CRUD, tenant isolation, monitoring
- **Tenant Isolation (BOLA)**: All cross-tenant data access paths fixed — assessment grades, student grade history, student portal assignments, and student messaging all enforce `tenant_id` checks. No user can access another school's data through any API endpoint.
- **Atomic DB Updates**: All database operations use `gd_*` helpers from `engines/sql_utils.py` — `gd_update_one`, `gd_update_many`, `gd_upsert`, `gd_insert`, `gd_find`, `gd_find_one`, `gd_count`, `gd_delete_one`, `gd_delete_many`, `gd_distinct`, `_gd_aggregate`. No MongoDB compatibility layer.
- **Dashboard Query Consolidation**: `GET /dashboard/stats` uses parallel `gd_count` calls. `GET /super-admin/dashboard-stats` reduced from ~20 to 7 parallel queries. `GET /admin/command-center/stats` reduced from ~18 to 8 parallel queries.
- **Reporting N+1 Elimination**: `GET /reports/school/attendance` fetches all attendance in 1 query then groups by class (was N queries). `GET /reports/school/grades` fetches all grades in 1 query then groups by subject. `GET /reports/school/top-classes` fetches all attendance + behavior in 2 queries instead of 2N. `GET /reports/school/behavior` batch-fetches student names in 1 query instead of per-record.
- **Engine Layer Consolidation (Phase 2)**:
  - **Bulk operations**: `record_bulk_attendance` and `record_bulk_grades` batch-fetch existing records in 1 query, use `insert_many` for new records. Route handlers (`/attendance/bulk`, `/grades/bulk`) also batch-fetch students/grades up front instead of N+1 per record.
  - **Memory patterns eliminated**: `get_daily_attendance_report`, `get_student_attendance_summary` use `batched_counts()` instead of fetching all records. `get_section_attendance_summary`, `get_tenant_attendance_overview`, `get_students_with_low_attendance` use aggregation pipelines with `$group` instead of `.to_list(100000)`.
  - **N+1 fix**: `calculate_student_average` batch-fetches all assessments in 1 query instead of calling `get_assessment_by_id()` per grade.
  - **Tenant isolation**: Assessment GET/PUT/DELETE routes enforce `tenant_id` check — non-platform-admin users cannot access other tenants' assessments.
  - **Configurable business rules**: `_percentage_to_letter` loads tenant-specific grade scale from `tenant_settings` collection (setting_key: `letter_grade_scale`), falls back to default. `SCORE_RULES` in session_engine.py has `load_tenant_score_rules(db, tenant_id)` that loads tenant overrides from `tenant_settings` (setting_key: `score_rules`). Both use `DEFAULT_*` constants as fallback.
- **Attendance Enrichment Batch**: `GET /attendance/class/{class_id}` collects all student/teacher/class/subject IDs, batch-fetches names in 4 parallel queries, then maps back (was 3-4 queries per record × N records).
- **Error Boundary**: `ErrorBoundary.jsx` wraps entire app — catches render crashes with Arabic fallback UI
- **Health Check**: `/system/health` returns DB status, latency, uptime, version
- **Logging**: All 34+ backend route files use `logging.getLogger("nassaq.*")` — zero `print()` statements in routes/engines
- **Mock Data Removed**: Student grades from real DB, Hakim chat from real API, AssessmentPage uses `fetchStudentsByClasses()` API call; IntegrationsPage `PREMIUM_INTEGRATIONS` mock array removed — shows empty state when API returns no data; ALL attendance metrics (student/teacher rates, present/absent counts, active users) now DB-only — zero fabricated fallbacks
- **Console Cleanup**: Zero `console.log` in frontend pages/contexts; WebSocket logs gated on `NODE_ENV === 'development'`
- **Env Vars**: `JWT_SECRET_KEY` set in dev+prod; `CORS_ORIGINS` set in prod (`https://nassaq.com,https://www.nassaq.com`); admin seed passwords via `ADMIN_SEED_PASSWORD_ZALAT` / `ADMIN_SEED_PASSWORD_HAKIM` env vars (no hardcoded passwords in code)
- **Secrets Cleaned**: `backend/.env` contains only non-sensitive config (algorithm, expiry); all secrets managed via Replit secrets system
- **Demo Scripts Removed**: 6 test/demo seed scripts deleted from `backend/scripts/` (seed_accounts, seed_demo_teacher_data, seed_exact_test_data, seed_test_data, seed_five_schools, verify_demo_teacher)

## Architecture

- **Frontend**: React (Create React App + CRACO), Tailwind CSS, Radix UI — port 5000
  - **App.js**: Thin composition file (~30 lines) — providers + BrowserRouter + AppRoutes
  - **routes/appRoutes.js**: All route definitions with role constants (SCHOOL_ROLES, SCHOOL_TEACHING_ROLES, ALL_AUTHENTICATED_ROLES, PRODUCT_HUB_ROLES)
  - **components/guards/RouteGuards.js**: ProtectedRoute + PublicRoute with ROLE_DASHBOARDS map
  - **services/apiClient.js**: API service layer factory `createApiService(api)` with 13 domain modules (auth, schools, students, teachers, classes, subjects, attendance, assessments, notifications, settings, platform, productHub, hakim)
  - **components/school-settings/DndComponents.jsx**: Extracted DnD components (DraggableClassItem, DroppableTeacherBox, DraggableSubjectItem, DroppableTeacherSubjectBox)
  - **components/student-profile/ProfileComponents.jsx**: Extracted profile helpers (TALENT_OPTIONS, PLAN_CONFIG, HakimPlanCard, StatCard, EmptyState, DataField)
  - **components/student-profile/StudentTabsContent.jsx**: Extracted 7 tab components (OverviewTab, AcademicTab, TalentsTab, BehaviourTab, ActivitiesTab, PlansTab, LongitudinalTab) — receive full hook object as single `hook` prop
  - **components/student-profile/StudentModals.jsx**: Extracted 6 modal components (EditProfileModal, BehaviourModal, ExportPlanModal, ActivityModal, CertificateModal, FullProfileExportModal)
  - **hooks/useStudentProfile.js**: Custom hook (685L) encapsulating all student profile state, API calls, handlers, and computed values
  - **AuthContext.js**: fetchUser uses AbortController with 10s timeout; 401 interceptor with silent refresh-token renewal; refresh tokens stored in localStorage (remember-me) or sessionStorage (session-only); logout clears all tokens and calls backend logout endpoint
- **Backend**: FastAPI (Python), JWT auth — port 8000
  - **server.py**: Thin orchestrator (~50 lines) — app creation only
  - **app/middleware.py**: HTTP middleware stack (PG session, security headers, audit, CORS, rate limit, error handler)
  - **app/lifecycle.py**: Startup/shutdown hooks (DB init, seed, approval engine, product hub integrity)
  - **app/routes.py**: Centralized router registration (all _mod and factory routes)
  - **shared_models.py**: All Pydantic request/response models (single source of truth)
  - **utils/api_response.py**: `ApiResponse[T]` envelope — `{success, data, error: {code, message, message_ar}, meta}` with `ok()`/`fail()` helpers
  - **Global error envelope**: All HTTPExceptions → `{success: false, error: {code: "HTTP_<status>", message}}`, validation errors → `{success: false, error: {code: "VALIDATION_ERROR", message}, meta: {validation_errors: [...]}}`
  - **Route files**: Each under ~1000 lines; `academics_routes_mod.py` (3848 lines) split into 7 sub-modules, `scheduling_routes_mod.py` (2875 lines) split into 4 sub-modules
- **Database**: PostgreSQL (async SQLAlchemy + asyncpg)
  - **PostgreSQL**: Replit built-in via `DATABASE_URL`, GenericDocument JSONB storage, Alembic migrations
  - **Repository layer**: `backend/repositories/__init__.py` — Simplified Repos class providing `session` property only. All data access via `gd_*` helpers from `engines/sql_utils.py`
  - **Session management**: Repos uses `contextvars.ContextVar` for per-request session isolation
  - **Core files**: `backend/db.py` (async engine), `backend/pg_models.py` (ORM models), `backend/alembic/` (migrations, head: h1i2j3k4l5m6)
  - **asyncpg SSL fix**: `sslmode` param stripped from DATABASE_URL (asyncpg uses `ssl=True` instead)
  - **Data access layer**: `backend/engines/sql_utils.py` — `gd_find`, `gd_find_one`, `gd_insert`, `gd_insert_many`, `gd_update_one`, `gd_update_many`, `gd_count`, `gd_delete_one`, `gd_delete_many`, `gd_distinct`, `gd_upsert`, `_gd_aggregate`. Supports filter operators, `order_by`/`desc_order`/`limit`/`offset` params, update operators (`$set`/`$push`/`$pull`/`$inc`/`$unset`), and `tenant_id`↔`school_id` aliasing

### Product Intelligence Hub (مركز ذكاء المنتج)
- **Database Models**: `backend/models/product_hub_models.py` — Production-ready Pydantic schemas: 12 enums (IssueType, IssueStatus, IssuePriority, Reproducible, TeamEnum, ImpactType, RelatedTo, AccountType, Platform, CommentType, AuditAction, AuditRole), structured sub-models (IssueContext, IssueDescription, IssueTechnical, IssueBusiness, IssueAssignment, IssueAI, SubmissionMetadata, IssueVisibility, IssueSystem), `IssueCreate.to_issue_document()` builder, backward-compatible `ISSUE_TYPE_COMPAT` map (performance→performance_issue, etc.), attachment validation (max 10 files, allowed extensions), field length limits
- **Audit Logging System**: `backend/engines/product_hub_audit.py` — Immutable audit trail with 12 AuditAction types (created, updated, status_changed, assigned, ai_analyzed, duplicate_detected, prompt_generated, comment_added, attachment_added, closed, reopened, feedback_confirmed). Specialized functions: `audit_issue_created()`, `audit_status_changed()` (auto-detects close/reopen), `audit_issue_assigned()`, `audit_ai_analyzed()`, `audit_duplicate_detected()`, `audit_prompt_generated()`, `audit_comment_added()`, `audit_attachment_added()`, `audit_feedback_confirmed()`. `get_full_timeline()` returns actors list + actions_summary. All entries immutable (insert-only, no edit/delete)
- **RBAC Engine**: `backend/engines/product_hub_rbac.py` — **Permanent Governance Rule**: Only `zalat@nassaqapp.com` and `hakim@nassaqapp.com` (MAIN_ADMIN_EMAILS) hold highest-level permissions across the entire system. This is identity-based (exact email match), NOT role-based. No other account—even platform_admin or any future admin role—may inherit these powers. HubAction permission matrix (26 actions including DELETE_ISSUE and REANALYZE_ISSUE), all high-privilege actions in MAIN_ADMIN_ONLY_ACTIONS set (delete, edit, status change, assign, prompt, hakim, analytics, duplicates, closure approval). Structured error responses with `FORBIDDEN_SUPER_ADMIN_ACTION` error code. Field redaction (generated_prompt + hakim_analysis hidden for non-main-admins). Frontend hides all restricted controls (not just disabled). Backend enforces on every request regardless of UI state.
- **Event Flow Engine**: `backend/engines/product_hub_events.py` — 16 HubEvent types, SLA calculation, progress% enrichment, strict status transitions, idempotent SLA warning
- **API Routes**: `backend/routes/product_hub_routes.py` — 20+ endpoints using models from product_hub_models.py, dual logging (event engine + audit system), structured document storage with nested objects (context, description, impact, technical, business, ai, assignment, submission_metadata, visibility, system). Enterprise comments: `PUT /issues/{id}/comments/{cid}` (edit own comment, main admin can edit any), `DELETE /issues/{id}/comments/{cid}` (delete own, admin can delete any), `GET /mentionable-users` (platform admins only). Comment type RBAC enforced server-side (non-admins forced to 'general'). Edit/delete enforce issue-level access via `can_access_comments`.
- **Enterprise Comments UX**: `frontend/src/components/product-hub/CommentInput.jsx` — `CommentInput` component with @mention popup (searches mentionable users), Ctrl+Enter submit, auto-resize textarea, comment type selector (admin only). `CommentBubble` component with inline edit/delete (hover actions), mention highlighting, "(تم التعديل)" edited indicator. Mentions stored as user IDs in `mentions[]` field.
- **Shared Component Library**: `frontend/src/components/product-hub/` — hubConstants.js (STATUS_CONFIG, PRIORITY_CONFIG, TYPE_CONFIG, EVENT_LABELS, COMMENT_TYPE_CONFIG, IMPACT_LABELS, KANBAN_COLUMNS), StatusChip, PriorityBadge, SLAIndicator, StatCard, EmptyState, HakimInsightCard, IssueKanbanCard, barrel index.js
- **Expandable Smart Panels**: `ProductHubPage.jsx` — Challenge Cards are now expandable smart panels (accordion, one at a time). Collapsed state shows compact preview (title, reporter, progress, status, ID, date, expand arrow). Expanded state reveals full-width 3-zone workspace: **Zone A (Details)** — reporter, status/priority badges, behaviors, impact, steps to reproduce, progress bar, open-full-page button; **Zone B (Comments)** — full comment thread with `CommentBubble` + `CommentInput`, @mentions, inline edit/delete; **Zone C (Hakim AI)** — `HakimMicroInsight` cards for priority/team/impact/technical notes, duplicate alerts, admin-only prompt generate/copy/preview. Data lazy-loaded on expand via `GET /issues/{id}` with error retry UI. `IssuesTableView` manages accordion state with "Collapse All" button.
- **Frontend Pages**: `ProductHubPage.jsx` (3-tab: Dashboard KPI cards + analytics charts, Expandable Smart Panels list, Kanban board with per-status columns), `ProductHubSubmitPage.jsx` (4-step guided form: Reporter → Details → Extra Info → Review, impact multi-select pills, reproducibility buttons, platform selection), `ProductHubIssuePage.jsx` (rich header with StatusChip/PriorityBadge/SLAIndicator + progress bar, HakimInsightCard sidebar, typed comments with admin_note/qa_note/general, activity timeline with colored event dots, admin action bar with status transitions + team assign, Developer Prompt panel with copy)
- **Routes**: `/admin/product-hub`, `/admin/product-hub/submit`, `/admin/product-hub/issues/:issueId`
- **Collections & Indexes**: `product_issues` (15 indexes: id unique, issue_number unique, status, priority, type, team, employee, created_by, created_at, compound is_deleted+status+date, compound is_deleted+creator+date, compound status+priority+date, compound status+team, section, compound created_by+date), `counters` (atomic sequence counter for issue_number — `_id: "product_issue_number"`, `seq: N`), `bulk_action_history` (3 indexes: id unique, user+date, date), `issue_activity_log` (5 indexes: id, issue_id+timestamp, action, performed_by, timestamp), `issue_comments` (3 indexes: id, issue_id+timestamp, created_by), `issue_duplicates_map` (4 indexes: id, issue_id, duplicate_of, compound pair)
- **Data Integrity System**: On startup: `_ensure_issue_counter()` syncs atomic counter with max issue_number in DB; `_ensure_data_integrity()` backfills missing `is_deleted` fields, assigns numbers to orphaned issues, resolves duplicate numbers. All dashboard queries filter `is_deleted != true`. Issue creation uses atomic counter increment on counters collection (no race conditions). `POST /issues/resequence` (main admin only) renumbers all active issues sequentially by creation date and resets counter.
- **Strict Status Lifecycle**: `new` → `under_review` → `in_progress` → `qa_validation` → `done` → `user_feedback_confirmed`. Reopen: `done/rejected` → `under_review`. Reject: only from `under_review`. No shortcuts.
- **Validation Rules**: employee_name ≥ 3 chars, impact enum array validation, reproducibility enum (yes/no/sometimes), related_to enum array (api/ui/database/permissions/upload/auth), platform enum (web/mobile/api/desktop), comment_type enum (admin_note/qa_note/general), issue_type backward compat mapping, max 10 attachments, 5000 char limit on text fields
- **SLA**: critical=24h, high=72h, medium=120h, low=None
- **Structured Errors**: `{success, error_code, message, details}` with INVALID_TRANSITION, FORBIDDEN_*, CONCURRENT_MODIFICATION, ASSIGNEE_NOT_FOUND, etc.
- **Hakim AI**: `AI_INTEGRATIONS_OPENAI_API_KEY`, model `gpt-4o-mini`, fallback `_fallback_analysis()`
- **Platform admin accounts**: `zalat@nassaqapp.com`, `hakim@nassaqapp.com` (seeded on startup)

### Real Personal Name Enforcement
- **Backend Validation Engine**: `backend/engines/name_validation.py` — `is_generic_name(name)` checks against GENERIC_NAMES_AR (50+ Arabic role/department names), GENERIC_NAMES_EN (40+ English generic names), GENERIC_PATTERNS regex (admin/manager/supervisor/coordinator/etc.), numbers-only, repeated chars, names < 3 chars. `validate_personal_name(name)` raises HTTPException 400 with Arabic message if invalid.
- **API Integration**: `has_generic_name` field added to `UserResponse` in `shared_models.py`, `models/user.py`, and `server.py`. Computed dynamically via `is_generic_name()` on `/auth/me` and `/auth/login` responses (not persisted to DB).
- **Backend Enforcement**: Name validation enforced on `PUT /settings/account`, `PUT /users/me/profile`, and extended profile update. Rejects saves with generic names (HTTP 400).
- **Frontend Guard**: `frontend/src/components/GenericNameGuard.jsx` — wraps `AppRoutes` in `App.js`. Shows persistent amber warning banner for users with `has_generic_name === true`. Auto-shows forced modal after 800ms delay (once per session) requiring name change. Exempt pages: `/login`, `/register`, `/change-password`, `/`, `/registration-confirmation`.
- **Name Update Modal**: Inline validation with `isGenericName()` (mirrors backend logic), saves via `PUT /api/settings/account`, calls `updateUser + refreshUser` from AuthContext on success.
- **Account Settings Integration**: `AccountSettingsPage.jsx` — inline amber warning under Arabic name input when generic name detected, blocks profile save if name is still generic.
- **Exported Utility**: `isGenericName(name)` exported from `GenericNameGuard.jsx` for reuse across frontend.

### Unified Approval Engine
- **Backend**: `backend/engines/approval_engine.py` — handler registry + transition validation + structured event logging
- **Handlers**: `backend/engines/approval_handlers.py` — Teacher + School handlers with `verify_after_approve()`
- **Routes**: `backend/routes/registration_routes_mod.py` — all approval API endpoints
- **Status Lifecycle**: `pending_review` → `under_review` → `approved`/`rejected` → `archived`. Also: `info_required` (from pending/under_review), `cancelled` (from pending states). Terminal: `{approved, rejected, cancelled, archived}`
- **Transition Validation**: `VALID_TRANSITIONS` matrix in engine; `validate_transition()` blocks all invalid status changes
- **Actions**: `approve`, `reject`, `mark_under_review`, `archive`, `cancel` — all with audit logging + lifecycle events
- **Event Logging**: `approval_events` collection — structured lifecycle events via `_emit_event()` for all state changes
- **Enriched Data Model**: Requests store `source`, `payload_snapshot`, `linked_entity_type/id`, `review_notes`, `priority`
- **Post-Approval Verification**: `verify_after_approve()` checks entity creation succeeded; handler errors caught to prevent false approvals
- **API Endpoints**: `POST /{id}/approve`, `POST /{id}/reject`, `POST /{id}/under-review`, `POST /{id}/archive`, `POST /{id}/cancel`, `GET /approval-queue`, `GET /approval-events/{id}`
- **Frontend**: `UsersManagement.jsx` — request details dialog with review history + lifecycle events, action buttons for under-review/archive, status badges for all statuses
- **Extensibility**: To add new type — create handler class, register in `server.py`, add config entry in `APPROVAL_TYPE_CONFIG`

### Form System Architecture
- **Location**: `frontend/src/components/forms/`
- **Components**: `FormContainer` (state + steps), `FormStep` (field rendering), `FormField` (unified input), `FormGrid` (responsive layout), `FormSection` (grouping), `StepIndicator` (progress), `StickyActionBar` (always-visible actions)
- **Rules**: Max 6-8 fields/step, no desktop scroll, auto-validation per step, data persists across steps
- **Usage**: Import from `components/forms`, define steps array with field configs, pass to `FormContainer`

## Platform Admin Pages (Redesigned)

### Command Center (`/admin` - AdminDashboard.jsx)
- Hero section with brand-navy/purple gradient, hijri/gregorian dates, online status
- 18 KPI cards in 3 sections: General Metrics, Operational Metrics, Administrative Metrics
- 3 charts: Schools Distribution (pie), Today's Attendance (bar), Schools Comparison (bar)
- Schools quick-view table with setup_score progress bars
- System Health panel (DB, API, engines status)
- Hakim AI Insights panel (auto-generated from real data)
- Quick Actions (Add School, Manage Users, Reports, Settings)
- Data source: `/admin/command-center/stats`, `/admin/command-center/schools-overview`, `/admin/command-center/system-health`, `/super-admin/dashboard-stats`

### Schools Management (`/admin/schools` - TenantsManagement.jsx)
- Hero section with 7 stat buttons (total, active, suspended, pending, students, teachers, classes)
- Clickable status filters in hero section
- Search + status/city filters
- Grid view: School cards with gradient headers, 4-column stats (students, teachers, classes, parents), setup_score progress, suspend toggle
- Table view: Full data table with all columns
- Data source: `/admin/command-center/schools-overview` (with fallback to `/schools`)
- Enter school context: Opens school as principal via `enterSchoolContext()`

### Backend: admin_dashboard_routes.py
- `GET /admin/command-center/stats` - 30+ fields: schools, students, teachers, parents, classes, subjects, timetables, sessions, attendance rates, notifications, behavior records, active users
- `GET /admin/command-center/schools-overview` - Per-school detail: counts, setup_score, has_timetable, sessions_today
- `GET /admin/command-center/system-health` - DB ping, API status, engine statuses
- `GET /admin/notifications/stats` - Notification counts
- `POST /admin/ai-operation/{type}` - AI operations (diagnosis, data_quality, etc.)

### Users & Classes Management (`/admin/users-management` - UsersClassesManagement.jsx)
- Tabs: Students, Parents, Teachers, Classes, Import/Export
- **Students Tab**: Class-grouped grid view (`StudentClassGrid.jsx`) — students organized by class in collapsible columns
- **Drag & Drop Transfer**: School admins (school_admin/school_principal/platform_admin) can drag students between class columns to transfer
- **Transfer API**: `POST /api/students/transfer-class` — updates student.class_id + class.student_ids arrays + student_count atomically
- Unassigned students (no class_id) shown in amber warning column at top
- Search filters within each class column
- StudentCard actions: View Profile, Edit, Reset Password, Delete
- Hakim AI insights panel: auto-detects students without class, without parent, suspended accounts, over-capacity classes

## Hakim AI Character — Dynamic Interactive System

Hakim is the AI intelligence layer of NASSAQ — a living, context-aware assistant that reacts dynamically to pages, events, and user actions. All images replaced with new chain-free versions.

### Dynamic Behavior
- **Context-based pose selection**: Pose changes based on current page, user role, and system events
- **Non-repeat random variation**: Same pose never shown twice in a row per context (tracked via `_lastUsed` map)
- **Smooth crossfade transitions**: 0.4-0.5s opacity transitions between pose changes
- **Idle breathing animation**: Subtle scale(1.012) + translateY(-5px) breathing cycle on idle
- **Landing hero rotation**: 4 poses cycle every 6s with crossfade (welcome, slight-bow, pointing-to-start, friendly-greeting)

### Pose Assets (`frontend/public/hakim-poses/`)
- **Welcome**: friendly-greeting, hand-wave-greeting, open-hands-welcoming, welcome, slight-bow-greeting
- **Teaching**: giving-instructions, explaining-concept, pointing-to-start
- **Analysis**: ai-thinking, ai-thinking-2, detecting-patterns
- **Alert**: attention-gesture
- **Listening**: listening, explaining-concept
- **Success**: positive-feedback, motivating, congratulating-student, clapping-celebration
- **Guidance**: explaining-concept, giving-instructions, inviting-to-begin

### Key Components
- `frontend/src/components/ui/ImageCropModal.jsx` — Reusable profile image crop modal (react-easy-crop + browser-image-compression). 1:1 aspect ratio, round crop, zoom slider, drag-to-reposition, client-side compression (0.5MB max, 512px), bilingual RTL/LTR support. Used in AccountSettingsPage and UserDetailsPage.
- `frontend/src/components/hakim/hakimPoses.js` — Pose registry with non-repeat selection, HERO_POSES export, context-to-category mapping
- `frontend/src/components/hakim/HakimReaction.jsx` — Reusable component with 3 animation levels (idle breathing, interaction bounce, celebration)
- `frontend/src/components/hakim/HakimAssistant.jsx` — Global floating chat widget (contextual pose per page, state-driven avatar: idle/listening/thinking/responding)
- `frontend/src/components/timetable/HakimCharacter.jsx` — Timetable-specific Hakim with dynamic state-to-category pose mapping and fade transitions

### Pose Context Mapping
- Landing/Login → welcome category (greeting poses, hero rotates 4 images)
- Dashboards/Analytics → analysis category (thinking, detecting patterns)
- Teaching/Sessions → teaching category (instructions, explaining, pointing)
- Management → guidance category (explaining, instructions, inviting)
- Success states → success/celebration category (feedback, clapping, motivating)

### Usage
```jsx
import HakimReaction, { ANIMATION_LEVEL } from '../components/hakim/HakimReaction';
import { getPose, getPoseForPath, getRandomPoseFromCategory, HERO_POSES } from '../components/hakim/hakimPoses';

<HakimReaction pose="ai-thinking" size="lg" message="أحلل البيانات..." animationLevel={ANIMATION_LEVEL.INTERACTION} />
<HakimReaction category="success" size="md" animationLevel={ANIMATION_LEVEL.CELEBRATION} rotatePoses />
```

## Project Structure

```
/frontend         React frontend (CRA + CRACO)
/backend          FastAPI backend
  server.py       Thin orchestrator (~754 lines, app init + router registration)
  config.py       Centralized production config with validation
  db.py           PostgreSQL async engine (SQLAlchemy + asyncpg), session factory, init_pg_tables()
  pg_models.py    47 SQLAlchemy ORM table models for PostgreSQL
  alembic/        Alembic async migration framework (env.py, versions/)
  alembic.ini     Alembic configuration
  # Alembic Migration Chain (latest → oldest):
  # a1b2c3d4e5f6 - Consolidate ProductIssue type/issue_type into single issue_type column
  # f3a4b5c6d7e8 - Drop extraneous columns added by earlier migration (issue_comments.created_at/updated_at, counters.updated_at, approval_events.created_at)
  # e2f3a4b5c6d7 - Migrate remaining string timestamps to TIMESTAMPTZ (approval_events, approval_requests, etc.)
  # d1e2f3a4b5c6 - Cleanup redundant schema fields (drop current_student_count/current_teacher_count, current_count, tenant_id on Subject/AuditLog)
  # c8d9e0f1a2b3 - Migrate string timestamps to DateTime(timezone=True) across all models + add subjects.updated_at, session_notes.updated_at
  # b7e52689a1ad - Add indexes and unique constraints
  # b9e08d69a15a - Add device_info, severity to audit_logs
  # 6ba4c4afaf24 - Initial schema with FK relationships
  dependencies.py Shared deps: db, auth, engines, helpers, enums
  shared_models.py Shared Pydantic models (UserResponse, TokenResponse, etc.)
  db_indexes.py   Database index management (auto-runs on startup)
  engines/        Core business engines (timetable, scheduling, hakim, reporting, export, session)
  routes/         API route handlers
    *_mod.py      17 consolidated route modules (extracted from server.py in Phase 8)
    *.py          Factory-pattern route modules (pre-existing)
    monitoring_routes.py  Health/status/metrics endpoints
  models/         Pydantic models
  middleware/     RBAC, tenant isolation, rate limiting, error handling
    rate_limiter.py  Token-bucket rate limiting on auth/export/AI endpoints
    error_handler.py Global error tracking with request IDs
  services/       Auth and audit services
  scripts/        Seed scripts
  seeds/          Database seed data
    timetable_hard_constraints.py  17 system-level hard constraints for timetable generation
```

## Timetable Hard Constraints

17 mandatory rules stored in `timetable_hard_constraints` collection (seeded on startup).
- **Collection**: `timetable_hard_constraints` (system-level, not per-school)
- **API**: `GET /api/school/settings/hard-constraints` (returns all 17 with categories)
- **Codes**: HC-01 through HC-17 (teacher conflict, class conflict, room conflict, day boundaries, non-teaching periods, daily limits, working days, teacher load, subject periods, consecutive subjects, teacher qualification, teacher-class assignment, double-booking, completeness, academic structure, entity integrity, publish block)
- **Categories**: resource_conflict, time_boundary, capacity, workload, curriculum, distribution, assignment, completeness, data_integrity, publishing
- **Enforcement**: Loaded by smart scheduling engine during generation; validated during publish

## Timetable Engine Bug Fixes & Capacity Diagnostics
- **weekly_hours fix**: Engine reads `weekly_periods` OR `weekly_hours` OR `weekly_sessions` from `grade_subjects` (was only checking `weekly_periods` which doesn't exist, causing all subjects to default to 4/week)
- **Teacher working_days fix**: Resource availability builder intersects school `working_days` with each teacher's individual `working_days` (47/48 teachers work Sun-Thu only; engine was ignoring this and scheduling on Saturday)
- **Capacity diagnostics**: `_analyze_capacity_issues()` detects grade over-capacity (demand > available slots) and per-subject teacher shortages; stored in `timetables.capacity_issues`; returned via `GenerationResult.capacity_issues`
- **Frontend capacity UI**: Result dialog shows severity-colored cards (red=critical, amber=warning) with Arabic messages and actionable fix guidance (e.g., "Go to Curriculum Settings > reduce weekly hours")
- **Data fields**: `grade_subjects` uses `weekly_hours` (NOT `weekly_periods`); teacher `working_days` is per-teacher array in teachers collection

## Timetable Drag & Drop (Move / Swap)
- **Frontend**: `SchedulePageNew.jsx` — native HTML5 drag & drop on the timetable grid
  - SessionCard is draggable when timetable status !== 'published' (draft mode)
  - Drop on empty cell → move session (POST `/smart-scheduling/sessions/move`)
  - Drop on occupied cell → swap sessions (POST `/smart-scheduling/sessions/swap`)
  - Optimistic state updates with rollback on API error
  - Visual feedback: turquoise highlight on empty drop targets, amber highlight on swap targets, grip dots icon on draggable cards
  - Badge "اسحب وأفلت لنقل الحصص ↔" shown in grid header when draft mode
- **Backend**: `scheduling_routes_mod.py` endpoints
  - `/smart-scheduling/sessions/move` — validates teacher/class conflicts (409), published guard (400), tenant ownership (403), resolves time slot by `period_number` with `is_break/is_prayer` exclusion
  - `/smart-scheduling/sessions/swap` — validates cross-timetable (400), teacher/class conflicts for both directions (409), published guard (400), tenant ownership (403), swaps all fields (day, period, time_slot_id, start/end times)
- **PrincipalTimetablePage.jsx** — also has D&D via TimetableGridSection (uses `/principal/timetable/sessions/swap` and `/sessions/move` endpoints)

## Unfilled Period Visual Warnings (SchedulePageNew)
- **periodGaps** (`useMemo`): Per-period gap analysis — counts filled/empty days for each period row, normalized with `Number()` for type safety
- **criticalGaps**: Periods with 3+ empty days (sorted by severity) → shown in amber warning card above the grid
- **EmptyCell `isGap` prop**: Empty cells in partially-filled periods show amber border + warning icon + "حصة فارغة" label instead of plain dash
- **Period label badge**: Rows with gaps show filled/total ratio (e.g., "2/5"); critical rows (≥3 empty) get amber styling on the period number badge
- **Coverage gaps warning panel**: Card with `AlertTriangle` icon listing critical periods, with red accent for ≥4 empty days, amber for 3; includes drag-and-drop hint
- **Guard**: Warnings only appear when `gridSessions.length > 0` (sessions exist but have gaps, not "nothing generated yet")

## Timetable Period Distribution
The scheduling engine uses contiguous-fill scoring to distribute sessions evenly across all periods:
- **No period bias**: Periods 3-5 no longer receive a fixed +10 bonus
- **Contiguous fill**: Sessions prefer filling the next sequential period on a given day (+8 bonus for period == last_filled + 1)
- **Gap penalty**: Large gaps between filled periods are penalized (-5 for period > last_filled + 2)
- **Gap-fill pass**: Fills remaining empty slots with proper teacher load and availability checks, prioritizing under-scheduled subjects (+25 bonus)
- **Optimizer**: Hill climbing rejects moves that violate teacher availability in addition to class/teacher conflicts
- **Seed file**: `backend/seeds/timetable_hard_constraints.py`

## Workflows

- **Start application** — Frontend dev server: `cd frontend && npm run start` (port 3000)
- **Backend API** — PostgreSQL + FastAPI: `cd backend && uvicorn server:app --host 0.0.0.0 --port 8000`

## Environment

### Frontend (`frontend/.env`)
- `REACT_APP_BACKEND_URL` — Points to the Replit backend URL on port 8000
- `PORT=3000`, `HOST=0.0.0.0` — Dev server binding
- `DANGEROUSLY_DISABLE_HOST_CHECK=true` — Required for Replit proxy

### Backend (`backend/.env`)
- `DATABASE_URL` — Replit co-located PostgreSQL connection string (managed by Replit)
- `JWT_SECRET_KEY` — JWT signing key
- `CORS_ORIGINS=*` — CORS allowed origins

## Key Features

- Multi-tenant school management (platform, school, teacher, student, parent roles)
- Smart AI timetable scheduling engine
- Attendance tracking with QR codes
- **Exam & Assessment Management page** (`/admin/assessments`) — "إدارة الاختبارات والتقييمات" with 3 tabs: Exam Schedule (periods with Arabic ordinal naming, subject CRUD with date/time/class/observer selection, inline period title editing), Committees (single + template creation, column-first seating grid, seat cancel/restore, stats/report/copy/import dialogs), Seating Cards (field configuration, dimension controls, print). All data is frontend state (no backend persistence yet).
- Audit logging system
- WebSocket real-time notifications
- **User & Class Management page** — fully redesigned with: unified "Add" picker dialog, 4-metric stats dashboard (students/parents/teachers/classes), Parents tab (fetches from `/parents` API, shows parent cards with children badges), Grid/List view toggle, unified THEME_COLORS system (student=navy, teacher=green, parent=amber, class=purple matching wizard themes), cartoon SVG avatars (male/female with face details, gender badges, teacher glasses), permanent floating Hakim widget (animated avatar with pulse indicator, expandable insights panel with action buttons), active filter banner, tab-based navigation (Students/Parents/Teachers/Classes/Import-Export), cards with dropdown menus, **Full Profile Dialogs** for all entity types:
  - `TeacherProfileDialog` — 5 tabs (Profile/Career/Login/Assignments/Activity), inline edit for basic+professional info, credential management with password generator, account status control (activate/suspend/close), assignment listing, activity log
  - `ParentProfileDialog` — 5 tabs (Profile/Children/Login/Contact/Activity), inline edit for contact info, linked children display with relationship badges, credential management, message sending with type categorization, account status control
  - `StudentProfileDialog` — 4 tabs (Info/Performance/Behavior/Actions), uses `/api/principal/student/` endpoints for status/credentials, risk analysis integration with Hakim
  - All dialogs use `/api/principal/` backend APIs with tenant-scoped security, explicit entity type routing (no heuristic detection)
- School Settings page as timetable configuration center (9 sections)
- Official Saudi curriculum reference data (read-only)
- **Interactive Teacher Session Console** (Phase 5) — live class sessions with attendance, random student picker, answer tracking, participation & behaviour logging
- **Phase 2 — Session Experience Improvements**: Gender-split student grids (attendance + teach pages), gender-based avatar fallback colors (sky-blue for boys, pink for girls), enhanced session summary with behaviour/skills cards + skills_recorded count from backend, parent notification button (sends positive reports to top participants' parents via `/notifications` API), enhanced celebration animations with multi-burst confetti
- **Attendance Screen Redesign (SessionStartPage)**: Dark/Light mode toggle, cartoon SVG avatars (male/female variants), two-column gender split (males right, females left in RTL — configurable toggle), all students default to "present", animated transition screen "ابدأ الشرح الآن" with progress bar after attendance approval, wider responsive layout (max-w-5xl), gradient progress bars, card-based student display with status glow effects
- **Phase 6 — Real DB Integration**: All Math.random() fallbacks eliminated. New batch endpoint `GET /api/classes/{class_id}/student-stats` returns aggregated attendance_rate, average_grade, behavior_points per student from real DB data. TeacherStudentsPage and TeacherClassDetailPage now fetch real stats.
- **Phase 7 — Student Analytics Enhancement**: New comprehensive endpoint `GET /api/students/{student_id}/analytics` returns attendance (rate, trend, recent), grades (average, records), participation (count, recent), behavior (points, records), and skills data. Student detail dialog enhanced with 4-metric overview, monthly attendance trend bars, session interactions, combined behavior records, and skills badges. ClassDetailPage statistics tab expanded with attendance distribution chart + best attendance leaderboard.
- **Student Portal (Complete)**: 9-item sidebar (Home, Schedule, Homework, Grades, Attendance, Profile, Progress, Achievements, Notifications). Dashboard has 4 panels: Today's Classes, My Score (gamification with points/rank/level), Today's Tasks (homework with "Start Now"), Hakim AI Panel. Backend APIs: `/student-portal/dashboard`, `/profile`, `/points`, `/progress`, `/achievements`, `/homework`, `/schedule`, `/grades`, `/attendance`. Gamification: 5 levels (مبتدئ→متميز), scoring from participation+grades+attendance+behaviour.
- **Parent Portal (Complete + Redesign)**: 6-item sidebar (Home, My Children, Reports, Messages, Notifications, Settings). Original pages: ParentChildrenPage, ChildBehaviorPage, ChildHomeworkPage, ParentReportsPage, ParentMessagesPage, ParentSettingsPage. **NEW Dashboard Redesign (April 2026)**: Student Switcher (multi-child pill tabs), SchoolDayProgress (visual timeline bar), CurrentClassCard (live class with countdown), UpcomingClasses, PerformanceIndicator (level + trend), WeeklyStory (daily chart + skills + tips), HakimChatWidget (AI chatbot floating button). **NEW Pages**: ParentCommunicationCenter (send messages/excuses with 3-open-request limit), StudentProfilePage (health/behavioral icons, emoji, family situation), StudentAnalyticsPage (gauge, line, radar charts + follow-up indicator). **NEW Backend APIs**: `/child/{id}/today-live`, `/child/{id}/weekly-story`, `/child/{id}/profile` (GET/PUT), `/child/{id}/achievements` (GET/POST), `/child/{id}/analytics`, `/open-requests-count`, `/quick-message`. Components in `frontend/src/components/parent/`, hook: `useParentDashboard.js`. Saudi timezone (UTC+3), school week Sat-Thu. Tenant isolation enforced via `_verify_parent_access()` and `school_id` constraints.
- **User Relationship Graph Engine (Complete)**: Full relationship data seeded and APIs working.

## Relationship Graph Engine

### Data Seeded
- **guardian_links**: 729 records (all students across 6 schools linked to parent users)
- **user_relationships**: 5,495 records covering 10 relationship types
- **user_identities**: 773 records (one per user)
- **user_roles**: 773 records
- **behaviour_records**: 75 records (noor-ahlia students)

### Relationship Types in `user_relationships` (migrated schema)
All records use the new schema: `from_entity_type`, `from_entity_id`, `to_entity_type`, `to_entity_id`, `status`.
| Type | Count | from_entity_type | to_entity_type |
|------|-------|------------------|----------------|
| parent_of | 728 | parent | student |
| sibling | 1,019 | student | student |
| teaches_class | 1,234 | teacher | class |
| teaches_subject | 169 | teacher | subject |
| enrolled_in_school | 728 | student | school |
| belongs_to_class | 727 | student | class |
| belongs_to_grade | 725 | student | grade |
| employed_at | 155 | teacher | school |
| manages_school | 10 | principal | school |

### Relationship Graph APIs
- `GET /api/relationships/graph/{entity_id}` — Returns connected graph for any entity type (student/teacher/parent). Resolves teacher_id mapping (user UUID → teacher record ID).
- `GET /api/relationships/siblings/{student_id}` — Returns siblings via guardian_links and user_relationships.
- Student graph includes: guardians, teachers (with real names/subjects), siblings, classmates count.
- Teacher graph includes: class assignments with subject names, total students, total classes.
- Parent graph includes: children with relationships and class info.

### Guardian Link Permissions (Full Spec)
`can_pickup`, `can_view_grades`, `can_view_attendance`, `can_communicate`, `can_view_financial_data`, `receive_notifications`, `pickup_authorization`

### RelationshipType Enum (`engines/relationship_graph_engine.py`)
`parent_of`, `child_of`, `guardian_of`, `teaches_class`, `teaches_subject`, `teaches_student`, `enrolled_in_school`, `belongs_to_grade`, `belongs_to_class`, `employed_at`, `manages_school`, `homeroom_for`, `linked_to_school`, `supervises_student`, `assigned_to`, `sibling`

### Seed & Migration Scripts
- `backend/scripts/seed_relationships.py` — Run once to populate all relationship data. Handles: guardian_links for all students, user_relationships (10 types), user_identities, user_roles, linked_roles detection, behaviour records.
- `backend/scripts/migrate_relationships.py` — Migrates user_relationships from old schema (user_id_1/user_id_2) to new schema (from_entity_type/from_entity_id/to_entity_type/to_entity_id/status). Maps old relationship_type names to new enum values.

## Session Engine (Phase 5 - Complete)

All 11 session routes wired in `server.py` calling `TeacherSessionEngine` methods:
- `POST /api/session/start` — creates session + draft attendance records
- `GET /api/session/current?schedule_session_id=...` — fetch in-progress session
- `GET /api/session/{id}` — session info + live stats
- `GET /api/session/{id}/students` — students with attendance + participation stats
- `PUT /api/session/{id}/attendance/{student_id}` — update single student status
- `POST /api/session/{id}/attendance/approve` — finalize attendance + score updates
- `POST /api/session/{id}/mode` — set interaction mode (review/homework/quiz)
- `POST /api/session/{id}/random-student` — fair weighted random selection
- `POST /api/session/{id}/answer` — record correct/wrong/no-answer + points
- `POST /api/session/{id}/participation` — record participation type + points
- `POST /api/session/{id}/behaviour` — record behaviour category + points
- `POST /api/session/{id}/end` — end session + full pipeline (owner verify → attendance check → stats → student profiles → analytics → AI insights → smart notifications → event log)
- `GET /api/session/{id}/export-report` — export session report as JSON (frontend converts to CSV download)
- `PUT /api/session/{id}/seating` — update seating order

### End Session Pipeline (end_session method)
1. **Owner verification** — session.teacher_id must match current_user
2. **Attendance guard** — requires attendance_approved or at least recorded attendance
3. **Stats computation** — attendance, interactions, behaviours, skills
4. **Session record update** — status=completed, summary saved
5. **Student profile update** — total_sessions_attended, participations, behavior counts, engagement_score
6. **Analytics trigger** — saves to `session_analytics` collection
7. **AI insights generation** — saves to `ai_session_insights` (attendance/engagement warnings, student highlights)
8. **Smart auto-notifications** — absence→parent, 3+ negative behaviors→parent+principal, outstanding performance→parent
9. **Event logging** — SESSION_ENDED + SESSION_SUMMARY_GENERATED events

### DB Collections Used by Session Engine
`class_sessions`, `session_attendance`, `session_interactions`, `student_daily_scores`, `student_score_ledger`, `timetable_sessions` (AI schedule), `schedule_sessions` (manual schedule), `session_analytics`, `ai_session_insights`

### Skills System (Phase 1 — Teacher Module)
- `skills_types` collection — 10 seed skills (leadership, cooperation, initiative, creativity, critical thinking, responsibility, communication, problem solving, time management, teamwork)
- `student_skills` collection — records of skills observed per student per session
- `GET /api/skills-types` — auto-seeds on first call if empty; returns all skill types
- `POST /api/skills-types` — admin-only: create new skill type
- `POST /api/session/{id}/skill` — record a skill for a student during a live session (stores in `student_skills` + `session_interactions`, updates score, audit logged)
- `GET /api/teacher/{id}/class-metrics` — real class metrics (attendance_rate, participation_rate, avg_performance, total_sessions) computed from `class_sessions` + `session_attendance` + `session_interactions`

### Key Data Fix
`validate_session_start` now checks `timetable_sessions` as fallback when `schedule_sessions` is empty. Teacher dashboard also falls back to `timetable_sessions` for today's lessons.

## All Engines (20 Engines — 200+ endpoints total)

### Core 6 Engines:
1. **Attendance Engine** (13 ep) — `attendance_routes_mod.py` — Single/bulk attendance, class/student history, daily reports, summaries, excuses, alerts, statistics.
2. **Behaviour Engine** (16 ep) — `behaviour_routes_mod.py` — Behaviour types/records, follow-ups, principal review, parent notification, disciplinary actions, school-wide stats.
3. **Participation Engine** (11 ep) — `participation_routes_mod.py` — Record/bulk, student/class stats, rankings, leaderboard.
4. **AI Planning Engine** (30 ep) — `ai_routes_mod.py` — Hakim LLM, diagnosis, predictions, recommendations, at-risk students, analytics, **auto-interventions** (auto-create intervention plans + notifications for at-risk students), **improvement plans** (per-student with strengths/weaknesses/goals/actions), **grade decline detection** (per-student trend + school-wide alerts), **schedule adjustment suggestions** (load balancing, substitute teacher recommendations, class intervention), **periodic scan** (full auto-analysis with auto-interventions + auto-notifications).
5. **Notification Engine** (13 ep) — `notification_routes_mod.py` — Notifications CRUD, scheduling, preferences, analytics.
6. **Student Score Engine** (20 ep) — `assessment_routes_mod.py` — Assessments CRUD, bulk grades, report cards, class rankings, **cross-section comparison** (compare class averages/pass rates/medians across sections), **student ranking** (ranked list with badges within class), **performance trend** (period-by-period trend analysis with subject breakdown), **grade decline alerts** (detect declining students with subject-level detail), **subject statistics** (school-wide subject stats with grade distribution + section comparison).

### 14 Additional Engines (all at 100%):
7. **User Identity Engine** (18 ep) — `auth_routes_mod.py` — Register, login, profile completion, session management, role switching, login history, password change.
8. **Role & Permission Engine** (24 ep) — `user_routes_mod.py` — User CRUD, permissions, suspension, activity, profile, preferences, notification settings.
9. **User Relationship Graph + Guardian Linking** (8 ep) — `relationship_routes_mod.py` — Guardian link/unlink/update, student guardians, parent children, custody transfer, relationship graph, siblings detection. Enhanced with `relationship_graph_engine.py` (temporal support, class transfers, stats).
9b. **Principal Management Engine** (20+ ep) — `principal_management_routes.py` — Full principal permissions over teacher/student/parent accounts: profile view/edit (basic, professional, contact), credential management (email/password), account status (active/suspended/closed with audit), teacher assignments, student class transfer, parent messaging, user search, password generation. All tenant-scoped with ADMIN_ROLES authorization.
10. **Student Profile Engine** (27 ep) — `student_portal_routes.py` + `student_management_routes.py` + `student_creation_routes.py` — Dashboard, grades, attendance, schedule, messages, assignments, student CRUD, drafts.
11. **Parent Portal Engine** (13 ep) — `parent_portal_routes.py` — Dashboard, child details/grades/attendance/schedule/teachers/behaviour, progress report, settings, notifications, messages.
12. **Student Enrollment Engine** (12+ ep) — `registration_routes_mod.py` — Teacher registration + **school registration** + student enrollment (create/list/approve/reject), additional info workflow. School approval endpoint `POST /registration-requests/{id}/approve-school` creates school entity + principal user + default settings in one flow. **UsersManagement.jsx has 4 tabs**: مستخدمين, مستخدمو المدارس, طلبات المعلمين المستقلين, طلبات المدارس. Both school and teacher requests fetched by `account_type` param from `/api/registration-requests`. School approval/rejection handled with dedicated confirmation dialogs and credentials display.
12b. **Direct Teacher Registration (Task #59)** — `teacher_registration_routes.py` adds `POST /api/teacher-registration/direct` endpoint for instant teacher account creation (no approval queue). Creates User + Teacher + QR code + Teacher ID directly. Returns `access_token` + `refresh_token` for immediate login. `TeacherSelfRegistration.jsx` updated with password + confirm password fields in Step 1; final submit calls `/direct` endpoint and auto-redirects to dashboard. Old approval-based flow (`/teacher-registration/request`) preserved for future use. `teachers.school_id` made nullable to support independent teachers.
13. **Account Lifecycle Engine** (10 ep) — `security_routes.py` — Lock/unlock, deactivate/reactivate, force password change, password reset, account status, session management.
14. **Notification & Communication** (28 ep) — `notification_routes_mod.py` + `communication_routes.py` — Full messaging, broadcasts, templates, scheduling, audience stats.
15. **Audit Log Engine** (7 ep) — `audit_routes.py` — Logs with filters/pagination, stats, export (JSON/CSV), user audit trail, cleanup.
16. **Search & Directory Engine** (7 ep) — `search_directory_routes_mod.py` — Global search, autocomplete, student/teacher/parent/class directories, statistics.
17. **Import / Bulk Registration** (5 ep) — `bulk_import_export_routes.py` — Templates, import (students/teachers), export (5 types), import/export history.
18. **Consent & Privacy Engine** (11 ep) — `consent_privacy_routes_mod.py` — Consent record/withdraw/check/pending, data deletion requests, data export, consent compliance report.
19. **Event / Workflow Engine** (11 ep) — `event_workflow_routes_mod.py` — System events CRUD, event statistics, workflow rules CRUD/toggle, executions, pre-built templates.
20. **Session Engine** (13 ep) — Teacher live class sessions with attendance, random picker, answers, participation/behaviour logging.

## Important Notes

### Database
- Active database: `test_database` (set via `DB_NAME` in `backend/.env`)
- Seed scripts: `backend/scripts/`

### ALL User Accounts (password: `NassaqAdmin2026!##$$HBJ`)

#### Original Demo School (school-demo-001 — مدرسة النور النموذجية — NEVER DELETE)
- `admin@nassaq.com` → platform_admin → `/admin`
- `ops@nassaq.com` → platform_operations_manager → `/admin`
- `admin@demo.nassaq.edu.sa` → school_admin → `/school`
- `subadmin@demo.nassaq.edu.sa` → school_sub_admin → `/school`
- `principal@demo.nassaq.edu.sa` → school_principal → `/school`
- `teacher@demo.nassaq.edu.sa` → teacher → `/teacher`
- `student@demo.nassaq.edu.sa` → student → `/student`
- `parent@demo.nassaq.edu.sa` → parent → `/parent`

#### New Schools (each: 25 classes, 25 teachers, 100 students)
| School | ID | Admin | Sub-Admin |
|--------|-----|-------|-----------|
| مدرسة النور الأهلية | school-noor-ahlia | admin@noor-ahlia.edu.sa | subadmin@noor-ahlia.edu.sa |
| ثانوية الملك فهد | school-fahad-secondary | admin@fahad-secondary.edu.sa | subadmin@fahad-secondary.edu.sa |
| متوسطة الأمل | school-amal-middle | admin@amal-middle.edu.sa | subadmin@amal-middle.edu.sa |
| ابتدائية الفلاح | school-falah-primary | admin@falah-primary.edu.sa | subadmin@falah-primary.edu.sa |
| مدارس التميز العالمية | school-tamayoz | admin@tamayoz.edu.sa | subadmin@tamayoz.edu.sa |

### Official Curriculum Collections (READ-ONLY, from وزارة التعليم)
- `official_curriculum_stages` — 3 stages (ابتدائي، متوسط، ثانوي)
- `official_curriculum_tracks` — 10 tracks (general, Quran, CS, health, business, sharia, etc.)
- `official_curriculum_grades` — 29 grades (all stage/track combinations)
- `official_curriculum_subjects` — 74 unique subjects
- `official_curriculum_grade_subjects` — 394 grade-subject mappings with annual sessions
- `official_teacher_rank_loads` — 7 teacher rank loads (weekly periods per rank)
- `official_optional_subject_pools` + `official_optional_subject_pool_items` — optional pool data

### School Settings Page (SchoolSettingsPagePro.jsx)
Routed at `/principal/settings` and `/school/settings`. Two sections:
- **Dynamic Section** (editable): **school-info** (NEW — Basic School Data), academic-year, workdays, timings, breaks, classes, teacher-assignments, unavailability, constraints (soft constraints persisted to DB)
- **Static Section** (read-only): official curriculum overview, stages/tracks, rank-loads, subject distribution accordion (stage → track → grade → subjects table)

### School Settings API Endpoints (T006 + T007 — fully implemented)
- `GET /api/school/info` — returns all school fields: name_ar, name_en, city, region, address, phone, email, type, stage, license_number (read-only), principal_name, is_active, updated_at + settings
- `PUT /api/school/info` — updates school basic data (NOT license_number), writes to `schools` collection, creates audit log. Roles: SCHOOL_PRINCIPAL, **SCHOOL_ADMIN**, PLATFORM_ADMIN
- `PUT /api/school/settings` — updates timetable settings (camelCase→snake_case) **+ audit log** (records changed_keys, old_data, new_data, soft_constraints_saved flag). **Auto-regenerates time_slots** when timing fields (dayStart, periodsPerDay, periodDuration, breaks) change. Roles: SCHOOL_PRINCIPAL, SCHOOL_ADMIN, PLATFORM_ADMIN
- `PUT /api/school/settings/timing` — updates school day start/end, auto-regenerates time_slots
- `PUT /api/school/settings/breaks` — updates break periods, auto-regenerates time_slots
- `PUT /api/school/settings/periods-per-day` — updates periods count, auto-regenerates time_slots
- `POST /api/school/settings/regenerate-time-slots` — explicit regeneration of time_slots from current settings
- **Time Slot Auto-Regeneration**: Helper `regenerate_time_slots_from_settings()` reads dayStart, periodsPerDay, periodDuration, breaks from `school_settings` and rebuilds `time_slots` collection with proper break/prayer insertion and 5-min passing time
- `GET /api/school/constraints` — returns constraints list. Open to all authenticated school users
- `POST/PUT/DELETE /api/school/constraints/{id}` — full CRUD. Roles: SCHOOL_PRINCIPAL, SCHOOL_ADMIN, PLATFORM_ADMIN
- All school-level endpoints now include `SCHOOL_ADMIN` role (bulk-updated ~95 endpoints)

### Teacher Assignment Audit Logging (T007)
- `POST /api/teacher-assignments` — **now writes CREATE audit log** (teacher_id, subject_id, class_id, performed_by_email, timestamp)
- `DELETE /api/teacher-assignments/{id}` — **now writes DELETE audit log** with old assignment data before soft-delete
- Audit logs queryable at `GET /api/audit/logs` (PLATFORM_ADMIN) and `GET /api/school/settings/audit-logs` (per-school)

### UX Improvements (T007)
- School day start time: replaced `<input type="time">` with hour + minute dual Select dropdowns (05–12h, 00–55 in 5-min steps)
- Teacher assignments: optimistic updates (instant UI, rollback on API error, `_optimistic` flag on pending), GripVertical drag handle, assignment-count badge per subject, green-glow drop zones
- Soft constraints: bulk enable/disable buttons, weight slider (10–100) with منخفض/متوسط/عالي presets, color-coded priority badges, unsaved-changes indicator, dedicated save function

### Hakim Context Engine
- **Core Engine**: `frontend/src/components/hakim/HakimContextEngine.js` — singleton engine with Context Detector, Pose Selector, Message Generator, Animation Controller
- **React Hook**: `frontend/src/components/hakim/useHakimContext.js` — `useHakimContext()` hook for any component to access Hakim's state
- **HakimPresence**: `frontend/src/components/hakim/HakimPresence.jsx` — drop-in component that auto-detects page context and displays Hakim with correct pose/message/animation
- **System Events**: `SYSTEM_EVENTS` enum (TASK_COMPLETED, SCHEDULE_CREATED, TIMETABLE_PUBLISHED, ATTENDANCE_RECORDED, AI_ANALYSIS_READY, SYSTEM_ALERT, ERROR_OCCURRED, SESSION_STARTED/ENDED, etc.)
- **Animation Levels**: IDLE (gentle floating), INTERACTION (bouncing), CELEBRATION (scale+rotate 3x)
- **Event-driven**: `hakimEngine.fireEvent(SYSTEM_EVENTS.TASK_COMPLETED, 'optional custom message')` triggers contextual pose+animation+message with auto-reset timer
- **Page Context**: Automatic pose/message selection based on URL path and user role (40+ path mappings)
- **Role Context**: Different default messages/categories per role (platform_admin, school_principal, teacher, student, parent)
- **Integrated into**: HakimAssistant (floating chat — fires HELP_REQUESTED on open), PrincipalTimetablePage (fires SCHEDULE_CREATED, TIMETABLE_PUBLISHED, TASK_COMPLETED, DATA_EXPORTED)
- **Index file**: `frontend/src/components/hakim/index.js` — clean re-exports for all Hakim modules

### Timetable Drag & Drop Session Rearrangement
- **Swap**: `POST /api/principal/timetable/sessions/swap` — swaps two sessions' positions (day/period/slot); validates same timetable version, teacher/class conflicts for both directions, rejects published timetables
- **Move**: `POST /api/principal/timetable/sessions/move` — moves session to empty slot; validates teacher/class conflicts, requires valid instructional slot (not break/prayer), rejects published timetables
- Frontend: HTML5 drag API in `TimetableGridSection.jsx`; drag sessions to swap or move to empty cells; visual feedback (violet highlight on drop targets, opacity on dragged session); banner hint in draft mode
- Locked sessions (`is_locked`) cannot be dragged

### Timetable API Endpoints
- Readiness: `GET /api/timetable-readiness/check` (sends `X-School-Context` header)
- Versions: `GET /api/smart-scheduling/timetable/versions?school_id=xxx`
- Generate: `POST /api/smart-scheduling/generate/{school_id}`
- Publish: `POST /api/principal/timetable/version/{id}/publish` — server-side validates (no sessions, teacher/class conflicts), auto-archives ALL previous published versions, records audit log
- Validate before publish: `GET /api/principal/timetable/version/{id}/validate-publish` — returns errors, warnings, sessions/classes/empty slots counts
- Previous timetables: `GET /api/principal/timetable/previous` — lists archived timetables with publish/archive dates
- Archive: `DELETE /api/smart-scheduling/timetable/{id}/archive`
- Grid: `GET /api/principal/timetable/grid?class_id=&teacher_id=&subject_id=&day=` (multi-filter AND logic)
- Filter options: `GET /api/principal/timetable/filter-options` (returns time_slots, timetable_settings.periods_per_day from DB)

### Timetable Engine (smart_scheduling_engine.py)
- `load_school_settings` reads time_slots from DB `time_slots` collection, computes `teaching_period_numbers` (excludes break/prayer slots)
- `generate_draft_timetable` only schedules into teaching periods (skips break/prayer slot numbers)
- Gap-fill phase runs after initial scheduling to fill remaining empty teaching slots
- `periods_per_day` in settings = raw DB value (7); `teaching_period_numbers` = actual teaching-only period numbers [1,2,3,5,6]
- DB time_slots for school-noor-ahlia: 10 slots (P1-P2=teaching, break, P4-P5=teaching, prayer, P7=teaching, break, P9-P10=teaching) = 7 teaching + 2 break + 1 prayer
- **CRITICAL**: `slot_number` is sequential (1-10 including breaks/prayers); `period_number` counts only teaching periods (1-7). Sessions use `period_number` (teaching-only). The filter-options API returns both fields on time_slots. Frontend matching in TimetableGridSection and SchedulePageNew uses `slot.period_number` to match `session.period_number`. The move endpoint resolves time slots by DB `period_number` field first, fallback to `slot_number`.
- **Data source mapping**: `grade_subjects` collection is typically empty; engine falls back to `teacher_assignments` ORM table for demand building. `academic_terms` table may be empty; engine also checks `terms` generic_documents collection.
- **Timetables ORM columns**: `id, school_id, name, name_en, academic_year, semester, effective_from, effective_to, working_days, status, total_sessions, version, created_at, updated_at` — no `data` column, so extra metadata is stored in `timetable_runs` (generic_documents).
- **ZeroDivisionError guard**: `generate_draft_timetable` safely skips all demands when `working_days` is empty, adding UnscheduledDemand records instead of crashing.
- **Query caching**: `build_academic_demand` pre-loads `teacher_assignments` (limit=5000) and `teachers` (limit=500) once, then filters in-memory per class/subject to avoid redundant DB queries.

### Official Curriculum API Endpoints
- Stats: `GET /api/official-curriculum/stats`
- Stages: `GET /api/official-curriculum/stages`
- Tracks: `GET /api/official-curriculum/tracks`
- Grades: `GET /api/official-curriculum/grades`
- Grade subjects: `GET /api/official-curriculum/grade-subjects/{grade_id}`
- Stage full: `GET /api/official-curriculum/stage/{stage_id}/full`
- Teacher rank loads: `GET /api/official-curriculum/teacher-rank-loads`

### Proxy
- Frontend calls all `/api/*` through CRA proxy in `frontend/src/setupProxy.js`
- `REACT_APP_BACKEND_URL` is intentionally empty

## Phase 3 System Stabilization (COMPLETED)

All 5 stabilization tasks are fixed and verified:

1. **JWT 90-day expiry** — `ACCESS_TOKEN_EXPIRE_MINUTES=129600` in `backend/.env` (overrides Python default). Tokens last 90 days.
2. **Parent Portal** — `parent_user_id` migration complete (501 students, 20 parents/school, i%20 distribution). `_parent_or_conditions()` helper guards against `parent_phone=None` matching all students. Uses `timetable_sessions` for schedule/teachers.
3. **Student Portal** — `/schedule` and `/teachers` query `timetable_sessions` by `class_id`, join with `subjects.name_ar` + `teachers.full_name`.
4. **Communication Center** — Routes persist to `db.messages`. Collection auto-creates on first insert. **Important (April 2026 fix, revision m1n2o3p4q5r6):** the `messages` and `notifications` ORM models in `pg_models.py` now expose a `data` JSONB column. Several routes (`communication_routes`, `parent_portal_routes`, `student_portal_routes`, `role_dashboards_mod`) write rich documents (audience, audience_ids, status, sent_count, sender_name, receiver_id, etc.) through `gd_insert`; without the `data` column, `dict_to_model` silently dropped every unmapped field and the entire pipeline (admin → teacher direct messages, fan-out notifications, inbox display) was non-functional. Also: `get_received_messages` now merges `audience IN (all/role)` with `audience='custom' AND user_id IN audience_ids`, otherwise direct messages were invisible to recipients.
5. **False completeness removed** — `/api/system/rules` returns real DB data (no fallback). `PREMIUM_INTEGRATIONS` all `is_active:false` used as catalog fallback. Empty-state UI for all 3 analytics charts.

### Parent Portal Bug Fixed (parent_phone=None)
The `_parent_or_conditions(parent_id, parent_phone)` helper in `parent_portal_routes.py` only appends the `parent_phone` condition when `parent_phone` is not None. Without this guard, `{"parent_phone": None}` matched every student (all have null phone), returning 20 unrelated children instead of the correct 5.

### Guardian Links & Tenant Isolation (March 2026)
- **guardian_links** collection stores parent-student relationships with `parent_ref`, `student_id`, `tenant_id`, `relationship_type`, `is_active`
- `_find_children(parent_id, phone, school_id)` checks both `students.parent_user_id` and `guardian_links.parent_ref` with tenant scoping
- `_verify_parent_access(parent_id, phone, child_id, school_id)` enforces tenant isolation on all child endpoints — prevents cross-tenant data leakage
- All child-detail endpoints now pass `current_user.get("tenant_id")` to `_verify_parent_access`
- Student dashboard properly resolves `school_name` from `db.schools` and `grade_level` from student record
- JWT tokens include `tenant_id` and `school_id` for all school-scoped users (student, parent, teacher, school_admin, etc.)

### Notification Schema Standardization (March 2026)
- **Standard fields**: `recipient_id` (not `user_id`), `notification_type`, `read_status`, `title`, `message`, `created_at`
- Fixed all portal routes to use `recipient_id` for notification queries and inserts (student_portal_routes.py, parent_portal_routes.py, registration_routes_mod.py, websocket_routes.py)
- `user_preferences` collection correctly uses `user_id` (different schema)

### Student & Parent Portal Data (March 2026)
- Noor-ahlia school: 234 grades, 203 attendance records, 103 guardian links across 10+ students and 10+ parents
- Published timetable provides 25 sessions/week per class across 5 school days
- Student points/gamification: calculates from participation + grades(>=80%) + attendance + behaviour
- 5 levels: مبتدئ (0-49), جيد (50-149), جيد جداً (150-299), متقدم (300-499), متميز (500+)

## Phase 6 — Hakim AI Engine, Reporting, Export, Role Switching, Platform Analytics

### Hakim AI Engine (`backend/engines/hakim_ai_engine.py`)
Real data-driven academic intelligence engine. No mock data — queries attendance, session_interactions, student_daily_scores, behaviour_records, student_grades.

- `GET /api/hakim/student/{student_id}/risk?days=30` — Student risk scoring (attendance 35%, participation 25%, behaviour 20%, academic 20%). Returns risk_score, risk_category (critical/high/medium/low), factors, breakdown
- `GET /api/hakim/class/{class_id}/participation?days=30` — Class participation analysis. Most active students, silent students, needs motivation list
- `GET /api/hakim/student/{student_id}/behaviour?days=60` — Behaviour pattern detection. Trend (improving/stable/declining), repeated patterns, type frequency
- `GET /api/hakim/teacher/{teacher_id}/analytics?days=30` — Teacher session analytics. Quality score, engagement rate, correct answer rate, class breakdown. Self-access or admin-only
- `GET /api/hakim/class/{class_id}/health?days=30` — Class health score (attendance 30%, participation 25%, behaviour 25%, academic 20%). Categories: excellent/good/average/needs_improvement
- `POST /api/hakim/school/analyze?days=30` — Full school analysis (admin only). Analyzes all students, classes, teachers. Stores insights in `ai_insights` collection
- `GET /api/hakim/insights?limit=20` — Retrieve stored insights

### Reporting Engine (`backend/engines/reporting_engine.py`)
Centralized report generation with 9 report types using PostgreSQL aggregation queries.

### Aggregation (`backend/engines/sql_utils.py` — `_gd_aggregate`)
- Aggregation via `_gd_aggregate` helper operates on GenericDocument JSONB data
- Supports `$match`, `$group` with accumulators (`$sum`, `$avg`, `$min`, `$max`), `$sort`, `$limit` stages
- All aggregation is performed in-memory on filtered GenericDocument rows

**Unified endpoint**: `GET /api/reports/generate/{report_type}` with query params:
- `start_date`, `end_date` (YYYY-MM-DD, defaults to last 30 days)
- `class_id`, `teacher_id`, `student_id` (filters)

**Report types** (`GET /api/reports/types` lists all):
- School: `school_attendance` (daily/weekly/monthly + class breakdown), `school_participation` (interactions by class, top students), `school_behaviour` (incidents, trends, type breakdown), `school_academic` (score distribution, class comparisons, top/bottom performers)
- Teacher: `teacher_activity` (sessions, interactions, classes taught), `teacher_session` (per-session metrics, class engagement comparison)
- Student: `student_progress` (attendance/grade/participation trends), `student_attendance` (calendar view, monthly summary), `student_performance` (risk score from Hakim AI, strengths, areas for improvement)

All return: `{ report_type, school_id, period, data, generated_at }`

**Legacy endpoints** (still supported):
- `GET /api/reports/student/{student_id}`, `GET /api/reports/class/{class_id}`
- `GET /api/reports/attendance?start_date=...&end_date=...&class_id=...`
- `GET /api/reports/teacher/{teacher_id}`, `GET /api/reports/school`

### Export Engine (`backend/engines/export_engine.py`)

**Unified export endpoint**: `GET /api/export/report/{report_type}?format=pdf|csv|xlsx`
- Accepts same filters as reporting engine: `start_date`, `end_date`, `class_id`, `teacher_id`, `student_id`
- PDF: Arabic RTL support via Amiri font (`backend/fonts/`), NASSAQ-branded tables, summary sections
- CSV: UTF-8 BOM for Arabic compatibility, multi-section output with section headers
- XLSX: Formatted headers (NASSAQ navy), auto-column-width, multi-sheet per data section
- All 9 report types supported: school_attendance, school_participation, school_behaviour, school_academic, teacher_activity, teacher_session, student_progress, student_attendance, student_performance
- Same role-based authorization as reporting engine
- Returns StreamingResponse with Content-Disposition attachment headers
- Dependencies: reportlab (PDF), xlsxwriter (Excel), pandas (CSV/data transformation)

**Legacy export endpoints** (preserved):
- `GET /api/export/students?fmt=csv|json&class_id=...`
- `GET /api/export/attendance?start_date=...&end_date=...&fmt=csv|json`
- `GET /api/export/grades?fmt=csv|json&class_id=...`
- `POST /api/export/report` — Export any report data to CSV/JSON

Frontend integration: PlatformAnalyticsPage, SchoolReportsPage, and TeacherReportsPage export buttons call the unified endpoint.

### Role Switching System
- `GET /api/role-switch/available-roles` — Get available roles for current user
- `POST /api/role-switch/switch` — Switch to target role (body: `{target_role, school_id}`)
- `POST /api/role-switch/restore` — Restore original role
- Allowed switches: platform_admin → principal/admin/teacher/student/parent; principal → admin/teacher; admin → teacher
- JWT claims carry `is_impersonating`, `original_role`, `original_user_id`
- All switches logged in audit_logs collection

### Platform Analytics (platform_admin only)
- `GET /api/platform/analytics` — Cross-school statistics (students, teachers, sessions, attendance per school, role distribution)
- `GET /api/platform/analytics/growth?months=6` — Monthly growth trends

### Hakim AI Floating Chat Assistant (System-Wide)
- **Component**: `frontend/src/components/hakim/HakimAssistant.jsx`
- **Backend**: `POST /api/hakim/chat` with `current_page` context field
- **Features**: Markdown-rendered responses (react-markdown + remark-gfm), clickable navigation links to system pages, page-aware context & suggestions, idle greeting animations with breathing pulse, visual states (idle/listening/thinking/responding/greeting), conversation history preserved across pages, clear chat button
- **System prompt** instructs LLM to format with markdown, include navigation links like `[الجدول الدراسي](/school/schedule)`, use emojis, and keep responses concise
- **Idle behavior**: Greeting bubble appears after 30s+ of inactivity with randomized Arabic greetings, respects dismiss count to reduce frequency
- **Dependencies**: react-markdown, remark-gfm

### Hakim AI Integration in Frontend (Task #6 — Platform Analytics)
All three dashboard pages now integrate with Hakim AI endpoints for live insights:

**PlatformAnalyticsPage** (`frontend/src/pages/PlatformAnalyticsPage.jsx`):
- AI Insights tab: school selector dropdown + "Analyze" button triggers `POST /api/hakim/analyze/{school_id}`
- Displays risk distribution cards (critical/high/medium/low), class health rankings with progress bars, Hakim alerts with severity badges
- Falls back to `GET /api/hakim/insights?school_id=...` if analysis POST fails
- Downloads AI summary as JSON
- Uses recharts (AreaChart, BarChart, PieChart, RadarChart) for trend visualizations

**SchoolReportsPage** (`frontend/src/pages/SchoolReportsPage.jsx`):
- Overview tab: "Hakim AI Insights" card auto-fetches via `POST /api/hakim/analyze/{tenant_id}`
- Shows risk summary grid, class health rankings, AI alert cards
- Falls back to stored insights from `ai_insights` collection

**TeacherMainDashboard** (`frontend/src/pages/TeacherModule/TeacherMainDashboard.jsx`):
- Hakim AI section fetches class health per teacher's assigned classes via `GET /api/hakim/class/{class_id}/health`
- Risk alerts: checks students in first 3 classes for critical/high risk via `GET /api/hakim/student/{student_id}/risk`
- Section only visible when data is available or loading

**TeacherReportsPage** (`frontend/src/pages/TeacherModule/TeacherReportsPage.jsx`):
- Export buttons wired to `GET /api/export/report/teacher_activity?format=pdf|csv|xlsx`

### DB Collections Added
- `ai_insights` — Stores Hakim AI analysis results (student_risk, class_health, full_school_analysis)
- `published_timetables` — Full snapshots of published timetables (classes, teachers, subjects, time_slots, sessions, working_days, break/prayer positions, academic year/term, publisher info). Created on each publish event. Used for viewing previous timetables without needing live data.

### Timetable Publish Flow
- On publish: validates (no conflicts, sessions exist), auto-archives ALL previous published versions, saves full snapshot to `published_timetables`, creates audit log entry
- Only one published timetable per school at any time
- Student/parent portals query published timetable first, fallback to latest draft
- Previous timetables viewable with full grid (from snapshot or live data fallback)

## Phase 8 — Production Readiness (COMPLETED)

### T001: Server Modularization
- server.py reduced from 17,735 → ~740 lines (thin orchestrator)
- 17 route modules in `backend/routes/*_mod.py`: auth, user, school, dashboard, ai, registration, academics, scheduling, attendance, assessment, behaviour, notification, platform, reporting, role_dashboards, admin, school_settings
- **Academic Year normalization**: Seeded DB documents use `name_ar`/`year` fields but API models expect `name`/`name_en`. `normalize_academic_year()` in `academics_routes_mod.py` handles legacy→current field mapping. The overview endpoint in `academic_structure_routes.py` also normalizes. Create/update write both `name` and `name_ar` for backwards compatibility.
- `dependencies.py` — all shared state (db, auth, engines, helpers)
- `shared_models.py` — all shared Pydantic models
- 1,019 routes registered successfully

### T002: Database Indexing & Performance
- `db_indexes.py` — 46 compound indexes across 22 collections
- Auto-runs on server startup via `@app.on_event("startup")`
- Key indexes: users (email, role+tenant), students (school+class), attendance (school+date), audit_logs (school+time)

### T003: Security Hardening
- Rate limiter middleware (`middleware/rate_limiter.py`): token-bucket limiting on login (10/min), register (5/min), export (10/2min), Hakim AI (5/min), password change (5/5min)
- Returns proper 429 with Arabic error message
- Global error handler middleware (`middleware/error_handler.py`): catches unhandled exceptions, assigns request IDs, logs tracebacks, returns safe error responses

### T004: Monitoring & Health Endpoints
- `GET /system/health` — Public: DB status, latency, uptime, version
- `GET /system/status` — Admin only: DB collections count, user/school stats, environment info
- `GET /system/metrics` — Admin only: process memory/CPU/threads, all collection counts
- Structured logging: timestamped with module names

### T005: Production Deployment Prep
- `config.py` — centralized config from env vars with validation
- Production validation checks (JWT secret length, CORS wildcard, debug mode)
- Middleware stack order: ErrorHandler → RateLimiter → CORS

### Monitoring Endpoints
- `GET /system/health` — Public, no auth required. Returns: status (healthy/degraded), DB connected, DB latency, uptime, version
- `GET /system/status` — platform_admin only. Returns: environment, python version, DB info, user/school counts, 24h active users
- `GET /system/metrics` — platform_admin only. Returns: process memory (RSS/VMS), CPU, threads, all collection document counts

## Phase 5 — Teacher Module Mobile-First Polish (COMPLETED)
All Teacher Module pages updated for mobile responsiveness:
- Grid breakpoints: All `grid-cols-N` classes now include `sm:` or `md:` breakpoints for proper collapsing on mobile (TeacherHomePage, AttendanceManagePage, StudentsPage, ResourcesPage, SettingsPage)
- Fixed-width controls: All `w-[Npx]` selects/inputs use `w-full sm:w-[Npx]` pattern across all pages
- Dialog mobile widths: Large dialogs include `w-[95vw]` for proper viewport sizing on mobile (Students, Assessments, Communication, Resources)
- Touch targets: Attendance status buttons use `min-h-[44px]` on mobile for proper touch interaction
- Schedule table: Reduced `min-w` on mobile for better horizontal scroll experience

## User & Class Management Fixes (COMPLETED)
Fixed teacher and student account creation from school admin (principal) dashboard:
- **Teacher creation fix**: Added `school_admin` to allowed roles (was only `school_principal`); fixed `bcrypt` NameError in `academics_routes_mod.py`; made `specialization` field optional; added specialization input to wizard form
- **Student creation fix**: Added `school_admin` and `school_sub_admin` to `require_roles` in all student-wizard endpoints; fixed `bcrypt.hashpw` → `hash_password()` calls
- **Dropdown lists (DB-driven)**: Nationality, Academic Degree, Teacher Rank, and Contract Type dropdowns now check `lookup_options` collection first, with fallback to hardcoded defaults
- **Teacher ranks updated**: معلم (Teacher), معلم أول (Senior Teacher), معلم خبير (Expert Teacher), رئيس قسم (Department Head)
- **Route priority note**: `academics_routes_mod.py` is registered FIRST in api_router (line 628) and handles `/teachers/create` and `/student-wizard/create` — the factory-pattern routes in `teacher_management_routes.py` and `student_creation_routes.py` are backup/secondary

## Phase 6 — Timetable System Completion (~90%+ COMPLETED)
Timetable system enhanced with soft constraints, sequential readiness, print/export, and parent schedule:

### Soft Constraints (SC-01..SC-12)
- **Seed**: `backend/seeds/timetable_soft_constraints.py` — 12 constraints in 4 categories: distribution, teacher_comfort, pedagogy, fairness
- **API**: GET/PUT at `/api/school/settings/soft-constraints` (via `school_settings_mod.py`)
- **Engine**: `_apply_soft_constraint_scoring()` in `smart_scheduling_engine.py` — scores all 12 keys during candidate evaluation
- **UI**: Redesigned constraints page uses two-panel horizontal layout (Hard | Soft), each with category tabs. Soft constraints auto-save individually via PUT. Weight scale is 1-10 (matching DB). Located in `SchoolSettingsPagePro.jsx` under `constraints` tab within `dynamic` section.

### 6-Phase Sequential Readiness
- **Backend**: `timetable_readiness_routes.py` — phases: time_structure → academic_entities → teaching_staff → teaching_relationships → constraints → generation_ready; each gates the next via `blocked_by`
- **Principal proxy**: `principal_timetable_routes.py` forwards `phases`, `current_phase`, `capacity`
- **Frontend**: `TimetableReadinessPanel.jsx` — phase-stepper UI with complete/partial/blocked/not_started states, expandable issue cards, capacity bar

### Print/Export
- Print via `window.print()` with RTL print stylesheet
- CSV export with proper BOM + CSV escaping from session data
- Both accessible from `TimetableActionBar.jsx`

### Parent Full Schedule View
- Route: `/parent/child/:childId/schedule` → `ChildSchedulePage.jsx`
- List and grid views with print support
- "View Full Schedule" button on ChildDetailsPage schedule tab

### Assignment Priority
- `AssignmentPriority` enum (primary/backup) + `priority` field on `TeacherAssignmentCreate`/`TeacherAssignmentResponse`

## Teacher Module (RESTRUCTURED — 10 Pages)
Sidebar reorganized to match Teacher Account Structure document:
1. **اللوحة الرئيسية (Dashboard)** → `/teacher` — TeacherResponsiveDashboard (auto-switches: mobile → TeacherHomePage, desktop → TeacherMainDashboard). **Teacher Greeting Card**: Enhanced with rank badge, school name + city, specialization, qualification, and 4-column stats grid (classes, students, subjects, weekly sessions). Backend `GET /api/teacher/dashboard/{teacher_id}` returns enriched data: `school_name`, `school_city`, `school_type`, `school_stage`, `subject_names`, and teacher fields (`rank`, `qualification`, `specialization`, `hire_date`, `phone`). Both primary (teachers collection) and fallback (users-only) paths return consistent response shape.
2. **جدولي (My Schedule)** → `/teacher/schedule` — TeacherSchedulePage (full redesign: weekly/daily/monthly views, current+next session cards with countdown, conflict detection banner, per-subject colors, room display, session detail dialog, CSV export, print, date picker, schedule change banner, Start Session navigates to /teacher/session/start with correct lesson contract)
3. **إدارة الحصص (Session Management)** → `/teacher/sessions` — TeacherSessionsManagePage (NEW)
4. **فصولي (My Classes)** → `/teacher/classes` — TeacherClassesPage
5. **طلابي (My Students)** → `/teacher/students` — TeacherStudentsPage
6. **ملف الإنجاز المهني (Professional Portfolio)** → `/teacher/achievements` — TeacherAchievementsPage (FULL REWRITE Task #83: Two tabs — Portfolio (default) + File Library. Portfolio tab: 9 collapsible sections (Teaching Plans, Applied Lessons, Assessment & Grading, Attendance, Behaviour & Guidance, Parent Communication, Professional Development, Participation & Activities, Administrative), each with evidence type badges, item cards with auto/manual tags, add/edit/delete manual evidence. File Library tab: grid view with search and type filter. Progress bar at top showing coverage % across 25 evidence types. Backend: `portfolio_evidence_engine.py` with capture_evidence() idempotent dedup, CRUD operations. Auto-evidence hooks in session_engine (lesson_plan on start, applied_lesson_report on end with ≥5 interactions, attendance_record), assessment_routes_mod (exam/quiz/performance_task on bulk grade), attendance_routes_mod (attendance_record on bulk), behaviour_routes_mod (behaviour_tracking on record), participation_routes_mod (participation_tracking on bulk), communication_routes (parent_communication_log on parent message). All hooks fire-and-forget. REST API: GET/POST/PUT/DELETE /teacher/portfolio/evidence, GET /teacher/portfolio, GET /teacher/portfolio/progress. 66 new i18n keys with portfolio* prefix.)
7. **التقارير والتحليلات (Reports & Analytics)** → `/teacher/reports` — TeacherReportsPage (FULL UPGRADE: 6 tabs — Overview, Attendance, Behavior, Grades, Needs Attention, Trends. Time period filter (today/week/month/semester/all). Grade distribution, top performers, most absent/present, behavior watch list, weekly attendance trend chart, students needing attention with issue badges. Export to PDF/CSV/XLSX. HakimPresence)
8. **التواصل والإشعارات (Communication & Notifications)** → `/teacher/communication` — TeacherCommunicationPage (FULL REWRITE Task #80: Three-section card layout — Communication Center, School Notifications, System Alerts. Communication Center: 6 notification templates (homework/exam/meeting/behavior/achievement/absence) → structured recipient selection (parents individual/all-in-class, admin guidance/general, students multi-select, school staff roles: vice principal, counselor, activity leader, gifted coordinator) → message preview and send. School Notifications: circulars/workshops dropdown filter, card layout. System Alerts: NASSAQ platform alerts card layout. Role-based recipient routing via `recipient_role`. All i18n. Sidebar merged to single "التواصل والإشعارات" item.)
10. **الملف الشخصي والإعدادات (Profile & Settings)** → `/teacher/settings` — TeacherSettingsPage (FULL REBUILD: 5 tabs — Profile, Security, Notifications, Preferences, Activity Log. Profile card with avatar upload/remove (base64), cover photo gradient, school/role/teacher ID display. Read-only fields: name, school, role, teacher ID. Editable: email, phone. Security: password change dialog with strength meter, account status, linked email. Notifications: method toggles + alert type toggles. Preferences: language picker (AR/EN) with flag cards, dark/light mode toggle. Activity Log: fetches from `GET /api/teacher/profile/{teacher_id}/activity` with tenant-scoped auth, grouped by date with timeline UI. HakimPresence)

### Hakim AI Context Bridge
- **Backend**: `POST /api/hakim/contextual-message` — receives page+role+context_data+language, calls OpenAI to generate short contextual message (max 20 words), returns AI message with graceful fallback
- **Frontend**: `useHakimContext.js` auto-fetches AI contextual messages on page navigation for teacher/school/student/parent pages. 2-min cache per page+role. `fetchContextualMessage(contextData)` function exposed for manual context-enriched requests

Sub-pages (accessible from within classes/sessions, not top-level sidebar):
- Attendance, Assessments, Behavior — routes still active at `/teacher/attendance`, `/teacher/assessments`, `/teacher/behavior`
- Resources — route still active at `/teacher/resources`
- Session engine: `/teacher/session/start`, `/teacher/session/teach`
- Class detail: `/teacher/class/:classId` — TeacherClassDetailPage (FULL REWRITE Task #82: Three tabs — Curriculum Plan (default), Student Records, Absence Log. Curriculum Plan: progress bar stats, weekly collapsible sections with lesson checkmarks, add/edit/delete lessons, inline editing. Student Records: grading table with configurable columns (coursework/exams), column settings dialog (add/remove/toggle visibility), locale-aware column names (name_en). Absence Log: visual absence circles per student with date labels, full attendance indicator. Backend: `_verify_class_access` tenant-scoped auth (teacher assignment check + school ownership), curriculum plan CRUD endpoints, grade columns config with Pydantic validation (Field constraints, enum column_type). i18n: 65 new keys including grade ordinals. NASSAQ design compliant: no gradients in dark mode, no transition-all, RTL-safe.)
- Mobile home: `/teacher/home`

- **Backend API**: `GET /teacher/sessions/{teacher_id}` — lists past sessions from `teacher_sessions` collection
- **Login**: teacher1@noor-ahlia.edu.sa redirects to `/teacher` main dashboard

## Dependencies

- Frontend: React 19, react-router-dom v7, Radix UI, Tailwind CSS, recharts, axios, @dnd-kit
- Backend: FastAPI, SQLAlchemy (async PostgreSQL), PyJWT, bcrypt, qrcode, pandas, google-generativeai, reportlab, xlsxwriter, psutil, python-docx

## Student Profile Page (Full Dedicated Page — Redesigned)
- **Route**: `/admin/students/:studentId` and `/principal/students/:studentId`
- **Component**: `StudentProfilePage.jsx` (imported as `AdminStudentProfilePage` in App.js)
- **Navigation**: Clicking any student name from ClassDetailPage or UsersClassesManagement navigates to this page. Both pass `classId`, `className`, `fromPath` in navigation state.
- **Hero Section** (dark navy-to-purple gradient, always visible):
  - Large circular avatar (initials, gradient bg, gold ring for gifted students)
  - Student name, grade/class subtitle, student ID (mono font)
  - Gifted badge (gold gradient), Active/Suspended status badge
  - Action buttons: Edit Profile (opens modal), Export Plan, Message Parent (WhatsApp), Account Actions dropdown (reset password, suspend/activate, delete — hidden for teachers)
  - Quick Stats Bar: 5 stat cards (Attendance %, Performance %, Talents count, Activities count, Positive Behavior count) with skeleton loaders
- **7 Tabs** (scrollable horizontally via ScrollArea):
  - `overview`: Student info summary, guardian info, attendance/performance/behavior cards, talents preview
  - `academic`: Attendance details (4-stat grid), grades with progress bar, AI risk analysis with breakdown & factors
  - `talents`: Current talents with remove buttons, predefined talent buttons, school talents, custom talent input
  - `behaviour`: Summary stats (4 cards), behavior log with color-coded records, add/edit/delete actions
  - `activities`: Involvement score bar, activities list with type badges (7 types: academic/sports/arts/community/scientific/cultural/other), certificates/awards visual cards, add/edit/delete modals (admin+teacher can add/edit, admin-only can delete)
  - `plans`: Hakim AI plans (remedial + enrichment) with generate, export, redo; plan history log showing previous generations
  - `longitudinal`: Full Longitudinal Record tab with year-by-year vertical timeline, skill growth line chart (Recharts), 4 readiness indicators (academic, social-emotional, leadership, career alignment), 3 career cluster cards with match percentages, vision statement banner
- **Full Profile Export**: "Export Full Profile" button in hero section opens modal with 7 section checkboxes (personal, academic, talents, behaviour, activities, plans, longitudinal) + PDF/Word format selection. Backend endpoints: `POST /hakim/export/student-profile/{id}` (DOCX) and `/pdf` (PDF)
- **Edit Profile Modal** (replaces old Info/Guardian tabs): Personal info fields + guardian info fields in a single dialog
- **Skeleton Loaders**: All data sections show skeleton placeholders while loading
- **EmptyState Component**: Consistent empty state with icon, message, and optional action button
- **DataField Component**: Consistent read-only field display with icon and empty fallback
- **overviewLoaded flag**: Prevents re-fetching overview data on tab switches (resets on studentId change)
- **Role-based**: `isTeacher` hides account actions dropdown and behavior delete buttons
- **Breadcrumbs**: User Management > Class Name > Student Name in sticky header
- **Back button**: Returns to fromPath > resolvedClassId class page > users-management fallback
- **Export Plan modal**: Plan type selection (Remedial/Enrichment/Both), format (PDF/Word)
- **Export Full Profile modal**: Section checkboxes (personal/academic/talents/behaviour/activities/plans/longitudinal), format (PDF/Word)
- **Tab values**: `overview` (default), `academic`, `talents`, `behaviour`, `activities`, `plans`, `longitudinal`
- **Backend endpoints**: Activities CRUD in `activities_routes_mod.py`, longitudinal + profile export in `ai_routes_mod.py`
- **Tenant scoping**: All backend queries enforce `school_id` from `current_user.tenant_id` for multi-tenant isolation

## School Admin Class Detail Page
- **Route**: `/admin/classes/:classId` and `/principal/classes/:classId`
- **Component**: `ClassDetailPage.jsx`
- **Navigation**: Clicking any class card in UsersClassesManagement navigates to this dedicated page (replaces old dialog)
- **Features**: Class header (name, grade, teacher, capacity bar, academic year), student list with grid/list toggle, gifted/other/all sub-tabs, search bar, add student button, export class list, StudentProfileDialog for viewing student details
- **Back navigation**: Button + breadcrumb trail (User Management > Class Name), browser back button works
- **API endpoints used**: `GET /classes/{class_id}`, `GET /classes/{class_id}/students`, `GET /classes`, `GET /reference/grades`

## Bug Audit & Security Fixes (April 2026)

### WebSocket Reconnect Loop Fix
- Added connection guard (`isConnectingRef`), max retry limit (15), proper cleanup of old connections, and stop-on-auth-failure (code 4001) in `WebSocketContext.jsx`

### Backend Auth Hardening
- Password complexity validation on `/auth/register`
- `is_active` and `is_locked` checks in `get_current_user` (dependencies.py) — revokes suspended/locked accounts mid-session
- `is_locked` check added to `/auth/refresh` — locked accounts cannot mint new tokens

### JSONB Race Condition Fix
- Added `with_for_update()` row locks to `gd_update_one` and `gd_update_many` in `sql_utils.py`

### `$options: "i"` Case-Insensitive Regex
- All three filter paths in `sql_utils.py` (`_build_orm_filter_conditions` direct columns, ORM `data` JSONB fallback, and `_build_filter_conditions` for GenericDocument) now use `~*` when `$options` contains `"i"`; `$options` key silently skipped

### ReDoS Protection
- `re.escape()` applied to all user-provided search inputs before `$regex` across 7 route files: `security_routes.py`, `user_routes_mod.py`, `admin_routes_mod.py`, `audit_routes.py`, `academics_student_routes.py`, `product_hub_routes.py`, `principal_management_routes.py`
- `search_directory_routes_mod.py` already had `re.escape()` — verified safe

### TeacherAchievementsPage Hooks Fix
- `useTranslation()` was called inside `renderBadgeCard()` helper function (non-component) — React hooks violation causing crash
- Fixed: Moved `const { t } = useTranslation()` to component top level, removed duplicate call from `renderBadgeCard`

### WebSocket `/ws` Health-Check Noise
- Replit proxy hits bare `/ws` endpoint every ~2 seconds for health checks
- Changed handler from `accept() + close(4000)` → `close(1000)` to suppress 3-line-per-hit log noise
- Real notification WebSocket remains at `/api/ws/notifications?token=...`

### ErrorBoundary Production Safety
- Stack traces in fallback UI are for debugging only — removed after crash diagnosis
- Errors still logged to `console.error` for DevTools inspection

### Task-71: Academic Structure & School Settings Restructure
- **AcademicStructurePage.jsx**: Added `other` holiday type with custom text input; Added `start_time`, `end_time`, `period_number` to exam period dialog; Added `openExamDialog()` helper that auto-fills current term; Removed "قواعد الترقية" tab from UI; Added AI calendar import button + dialog (file upload, Hakim instructions, preview)
- **academic_structure_routes.py**: Added `custom_type` to `HolidayCreate`; Added `start_time`, `end_time`, `period_number` to `ExamPeriodCreate`; Added `/academic-calendar/{year_id}/import` (AI parse) and `/import/apply` endpoints using OpenAI + openpyxl
- **SchoolSettingsPagePro.jsx**: Removed "المنهج الرسمي" section (static section) entirely; Changed from 3-column to 2-column section buttons; Removed timetable-specific tabs (timings, unavailability, constraints) from dynamic section; Dynamic section now shows only school-info, classes, teacher-assignments
- **PrincipalTimetablePage.jsx**: Added `pageView` state (timetable/settings); Added toggle buttons; When in settings view, renders `DynamicSettingsContent` with timetable-specific tabs (timings, unavailability, constraints) via `useSchoolSettings` hook
- **Dependencies**: Added `openpyxl` for Excel file parsing in calendar import

### End-to-End Bug Fix Sweep (Teacher Platform Testing)
- **Python operator precedence bug** (7 backend files): Fixed `a.get("x") or b.get("y") if obj else default` → `(a.get("x") or b.get("y")) if obj else default` in `role_dashboards_mod.py`, `ai_routes_mod.py`, `scheduling_smart_engine_routes.py`, `scheduling_generation_routes.py`, `scheduling_core_routes.py`, `student_portal_routes.py`, `parent_portal_routes.py`
- **ZeroDivisionError** (`assessment_routes_mod.py`): Added guard for `max_score=0` in grade percentage calculation
- **Missing role checks** (`role_dashboards_mod.py`): Added `require_roles` to grading endpoints that previously allowed any authenticated user
- **IDOR security fix** (`role_dashboards_mod.py`): Added resource-level tenant/school authorization on grading endpoints to prevent cross-school grade access
- **Role consistency** (`role_dashboards_mod.py`): Added `SCHOOL_SUB_ADMIN` to save grades endpoint to match read endpoint
- **Frontend null-safety** (`ParentDashboard.jsx`): Protected `child.name.charAt()` and `child.name.split()` with fallback
- **Frontend null-safety** (`TeacherMainDashboard.jsx`): Protected `timeStr.split()` with null check
- **Frontend null-safety** (`AssessmentPage.jsx`): Protected `student.name.split()` with fallback
- **JSON.parse crash protection** (`AuthContext.js`): Wrapped sessionStorage JSON.parse calls in try-catch to prevent app crash from malformed data

### Comprehensive Arabic-Language Test Data Seed
- **Script**: `backend/scripts/seed_test_data.py` — fully idempotent, re-runnable
- **Run**: `cd backend && python scripts/seed_test_data.py` (takes ~3–5 minutes)
- **Credentials file**: `TEST_CREDENTIALS.md` at project root (generated on each run)
- **Two isolated school tenants** (Gulf region, Arabic names):
  - **FARABI-001** — مدرسة الفارابي للتعليم الأساسي (domain: `faarabi.edu`, city: الرياض)
  - **IBNSINA-001** — Ibn Sina International Academy (domain: `ibnsina.edu`, city: جدة)
- **Per school**: 2 school admins, 18 teachers, 252 students (grades 1–12, 18 classes), 252 parents
- **Academic structure**: 14 subjects, 8 daily time slots, 279 teacher-subject-class assignments, 630 timetable sessions
- **Operational data per school**: ~1,000 behaviour records (4 weeks), 5,292 attendance records (Sun–Thu), 10 product hub issues
- **Default password for all accounts**: `Test@1234`
- **Platform admin**: `admin@nassaq.com` / `Test@1234`
- All seeding uses DB-direct ORM inserts (no API round-trips); structural data is upserted (safe to re-run)

## Critical Field Mapping Notes

### registration_requests table
- **ORM model** (`pg_models.py`): uses `type` (NOT NULL) and `name` columns
- **Pydantic model** (`shared_models.py`): uses `account_type` and `full_name` fields
- **Fix applied**: `registration_routes_mod.py` explicitly maps `type = account_type` and `name = full_name` before DB insert
- Extra Pydantic fields (`account_type`, `full_name`, `school_city`, etc.) are stored in the JSONB `data` column via `dict_to_model`
- The approval engine reads `account_type` from the merged dict (JSONB `data` → top-level via `model_to_dict`)
- The approval queue (`get_queue`) filters directly on `RegistrationRequest.type` column

### sql_utils.py TENANT_ALIAS
- Only `tenant_id` ↔ `school_id` is auto-aliased
- All other field name mismatches (like `account_type` vs `type`, `full_name` vs `name`) must be explicitly mapped before calling `gd_insert`

### ApprovalEvent FK (April 2026)
- `approval_events.request_id` FK now references `registration_requests.id` (was incorrectly pointing to `approval_requests.id`)
- Migration `l1m2n3o4p5q6` cleans orphaned rows and re-creates the FK
- `_emit_event()` in `approval_engine.py` uses `begin_nested()` savepoints so event failures don't corrupt the parent transaction
- Registration route validates `account_type` server-side against allowed set: school, teacher, parent, student
- Notification creation uses correct ORM field names: `user_id`, `type`, `is_read`

### Production Audit Fixes (April 2026 - Account Creation)
- **Password hashing**: `student_management_engine.py` was storing plaintext passwords for students and parents — now uses bcrypt
- **Sibling linking**: `_gd_addtoset` call in `student_creation_routes.py` had wrong signature (string instead of dict) — fixed
- **Role check**: `school_admin` was missing from allowed roles in `student_management_routes.py` — added
- **Class wizard auth**: `create_class_wizard` had no role check (any user could create classes) — now requires admin roles
- **Login safety**: `verify_password` could crash with ValueError on non-bcrypt hashes — now catches and returns False
- **School verification**: `SchoolApprovalHandler.verify_after_approve` used `principal.school_id` (non-existent attr) instead of `principal.tenant_id` — fixed
- **Student wizard field mapping**: `student_creation_routes.py` used `student_id` (dropped by ORM) instead of `student_number`, `grade_id` instead of `grade`, `student_count` instead of `current_students` — all corrected to match Student/Class ORM columns
- **QR code generation**: Updated to read `student_number` with fallback to `student_id`

### Smart Quick AI Operations Panel — Real Wiring (April 18, 2026)
- **Component**: `frontend/src/components/ai/QuickAIOperationsPanel.jsx`
- Replaced all mock state values with live data from real backend endpoints:
  - Status bar (operations today, AI-enabled schools, total schools): `/admin/command-center/stats` + `/admin/ai-operations/history`
  - Unread alerts: `/admin/notifications/stats`
  - Suggested actions: `/admin/ai-suggested-actions` (new endpoint)
  - Recent operations: `/admin/ai-operations/history` (new endpoint)
- 4 operation cards run real backend ops via `POST /admin/ai-operation/{type}` (diagnosis, data_quality, import_analysis, alerts_review)
- Each operation result is rendered with type-specific stats (health score, quality score, import file breakdown, unread alert list)
- New backend endpoints in `admin_dashboard_routes.py`:
  - `GET /admin/ai-operations/history?limit=10` — last AI ops with performer name + `operations_today` count
  - `GET /admin/ai-suggested-actions` — derives actions from real DB state (schools missing principal, teachers without rank, failed imports today, pending registrations, schools without AI)
- Improved `import_analysis` op to count today's import audit logs (filenames, imported/failed rows)
- Fix: replaced unsupported dotted-path JSONB filter on ORM `audit_logs` table with Python-side aggregation
