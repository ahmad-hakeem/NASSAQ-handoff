# NASSAQ - نَسَّق
## Smart Multi-Tenant School Management System

A full-stack school management platform with React frontend and FastAPI backend.

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

### Post-Fix Documentation
Each fix report must include: root cause, why it wasn't caught before, what changed, how recurrence is prevented, what was tested

### Deployment Safety Policy (PERMANENT & NON-NEGOTIABLE)
- **Core Rule**: Production data must NEVER be lost, overwritten, or replaced during deployment
- **Seed Scripts**: BLOCKED in production and staging (`config.seed_allowed()` returns `False`)
- **Destructive Ops**: BLOCKED in non-development environments (`config.destructive_ops_allowed()`)
- **Safe Migrations Only**: Add fields, collections, indexes — NEVER drop, delete, rename, or truncate
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
- **Silent Failures**: All bare `except:` replaced with specific exception types (`ValueError`, `KeyError`, etc.)
- **Error Boundary**: `ErrorBoundary.jsx` wraps entire app — catches render crashes with Arabic fallback UI
- **Health Check**: `/system/health` returns DB status, latency, uptime, version
- **Logging**: All 34+ backend route files use `logging.getLogger("nassaq.*")` — zero `print()` statements in routes/engines
- **Mock Data Removed**: Student grades from real DB, Hakim chat from real API, AssessmentPage uses `fetchStudentsByClasses()` API call
- **Console Cleanup**: Zero `console.log` in frontend pages/contexts; WebSocket logs gated on `NODE_ENV === 'development'`
- **Env Vars**: `JWT_SECRET_KEY` set in dev+prod; `CORS_ORIGINS` set in prod (`https://nassaq.com,https://www.nassaq.com`)

## Architecture

- **Frontend**: React (Create React App + CRACO), Tailwind CSS, Radix UI — port 5000
- **Backend**: FastAPI (Python), JWT auth — port 8000
- **Database**: PostgreSQL (async SQLAlchemy + asyncpg) — MongoDB fully replaced via adapter layer
  - **PostgreSQL**: Replit built-in via `DATABASE_URL`, 47+ ORM tables + GenericDocument fallback, Alembic migrations
  - **Adapter layer**: `backend/pg_adapter.py` — MongoDB-compatible API (find_one, find, update_one, aggregate, etc.) over SQLAlchemy; all routes/engines use adapter transparently
  - **Compatibility stubs**: `backend/bson_compat.py` — ObjectId + UpdateOne stubs for code that imported from bson/pymongo
  - **Migration files**: `backend/db.py` (async engine), `backend/pg_models.py` (47+ ORM models + GenericDocument), `backend/pg_helpers.py` (utilities), `backend/alembic/` (migrations, head: e052f4eb5993)
  - **asyncpg SSL fix**: `sslmode` param stripped from DATABASE_URL (asyncpg uses `ssl=True` instead)
  - **MongoDB**: Still installed (mongod binary) but NO code imports motor/pymongo/bson — will be fully removed in Task #12

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
- **Data Integrity System**: On startup: `_ensure_issue_counter()` syncs atomic counter with max issue_number in DB; `_ensure_data_integrity()` backfills missing `is_deleted` fields, assigns numbers to orphaned issues, resolves duplicate numbers. All dashboard aggregation pipelines filter `is_deleted: {$ne: true}`. Issue creation uses atomic `find_one_and_update` with `$inc` on counters collection (no race conditions). `POST /issues/resequence` (main admin only) renumbers all active issues sequentially by creation date and resets counter.
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
  pg_helpers.py   PostgreSQL helper utilities (generate_id, serialize, issue sequence)
  alembic/        Alembic async migration framework (env.py, versions/)
  alembic.ini     Alembic configuration
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
- **Backend API** — MongoDB + FastAPI: mongod start + `cd backend && uvicorn server:app --host 0.0.0.0 --port 8000`

## Environment

### Frontend (`frontend/.env`)
- `REACT_APP_BACKEND_URL` — Points to the Replit backend URL on port 8000
- `PORT=3000`, `HOST=0.0.0.0` — Dev server binding
- `DANGEROUSLY_DISABLE_HOST_CHECK=true` — Required for Replit proxy

### Backend (`backend/.env`)
- `MONGO_URL` — MongoDB connection string
- `DB_NAME` — Database name (`test_database`)
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
- **Parent Portal (Complete)**: 6-item sidebar (Home, My Children, Reports, Messages, Notifications, Settings). Pages: ParentChildrenPage (list all children with quick links to details/schedule/homework/behaviour), ChildBehaviorPage, ChildHomeworkPage, ParentReportsPage (aggregated progress), ParentMessagesPage, ParentSettingsPage (notification preferences). Backend APIs: `/parent-portal/dashboard`, `/children`, `/reports`, `/child/{id}`, `/child/{id}/grades`, `/child/{id}/attendance`, `/child/{id}/schedule`, `/child/{id}/behaviour`, `/child/{id}/homework`, `/child/{id}/progress-report`, `/child/{id}/teachers`, `/messages`, `/settings`, `/notifications`.
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
4. **Communication Center** — Routes persist to `db.messages`. Collection auto-creates on first insert.
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
Centralized report generation with 9 report types using MongoDB aggregation pipelines.

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
6. **إنجازاتي (My Achievements)** → `/teacher/achievements` — TeacherAchievementsPage (FULL REBUILD: Backend API `GET /api/teacher/achievements/{teacher_id}` computes metrics from sessions/attendance/grades/behavior, 11 badge definitions with earned/in-progress, monthly timeline, school comparison. Frontend: level system, badge cards with gradient icons, stats tab with progress bars, monthly bar chart, HakimPresence)
7. **التقارير والتحليلات (Reports & Analytics)** → `/teacher/reports` — TeacherReportsPage (FULL UPGRADE: 6 tabs — Overview, Attendance, Behavior, Grades, Needs Attention, Trends. Time period filter (today/week/month/semester/all). Grade distribution, top performers, most absent/present, behavior watch list, weekly attendance trend chart, students needing attention with issue badges. Export to PDF/CSV/XLSX. HakimPresence)
8. **مركز التواصل (Communication Center)** → `/teacher/communication` — TeacherCommunicationPage (FULL EXPANSION: 5 tabs — Quick Send, Inbox, Sent, Notifications, Contacts. 6 message templates (homework/exam/meeting/behavior/achievement/absence). Compose dialog with type/recipients/student selection. Message search. Contact directory with per-student send. HakimPresence)
9. **مركز الإشعارات (Notifications Center)** → `/notifications` — NotificationsPage (ENHANCED: 4 tabs — All, Unread, By Type, Preferences. Search, time period filter, priority filter. Group by date. Notification preferences UI with toggle switches. Stats cards. HakimPresence)
10. **الملف الشخصي والإعدادات (Profile & Settings)** → `/teacher/settings` — TeacherSettingsPage (FULL REBUILD: 5 tabs — Profile, Security, Notifications, Preferences, Activity Log. Profile card with avatar upload/remove (base64), cover photo gradient, school/role/teacher ID display. Read-only fields: name, school, role, teacher ID. Editable: email, phone. Security: password change dialog with strength meter, account status, linked email. Notifications: method toggles + alert type toggles. Preferences: language picker (AR/EN) with flag cards, dark/light mode toggle. Activity Log: fetches from `GET /api/teacher/profile/{teacher_id}/activity` with tenant-scoped auth, grouped by date with timeline UI. HakimPresence)

### Hakim AI Context Bridge
- **Backend**: `POST /api/hakim/contextual-message` — receives page+role+context_data+language, calls OpenAI to generate short contextual message (max 20 words), returns AI message with graceful fallback
- **Frontend**: `useHakimContext.js` auto-fetches AI contextual messages on page navigation for teacher/school/student/parent pages. 2-min cache per page+role. `fetchContextualMessage(contextData)` function exposed for manual context-enriched requests

Sub-pages (accessible from within classes/sessions, not top-level sidebar):
- Attendance, Assessments, Behavior — routes still active at `/teacher/attendance`, `/teacher/assessments`, `/teacher/behavior`
- Resources — route still active at `/teacher/resources`
- Session engine: `/teacher/session/start`, `/teacher/session/teach`
- Class detail: `/teacher/class/:classId`
- Mobile home: `/teacher/home`

- **Backend API**: `GET /teacher/sessions/{teacher_id}` — lists past sessions from `teacher_sessions` collection
- **Login**: teacher1@noor-ahlia.edu.sa redirects to `/teacher` main dashboard

## Dependencies

- Frontend: React 19, react-router-dom v7, Radix UI, Tailwind CSS, recharts, axios, @dnd-kit
- Backend: FastAPI, motor (MongoDB async), PyJWT, bcrypt, qrcode, pandas, google-generativeai, reportlab, xlsxwriter, psutil, python-docx

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
