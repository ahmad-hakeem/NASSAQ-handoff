# NASSAQ - نَسَّق
A comprehensive, multi-tenant school management platform with AI-powered features for administration, academics, and student performance.

## Run & Operate
- **Run**: `uvicorn backend.server:app --reload` (backend), `npm start` (frontend)
- **Build**: `npm run build` (frontend)
- **Typecheck**: `mypy backend/` (backend), `npm run typecheck` (frontend)
- **Codegen**: `alembic revision --autogenerate -m "description"` (DB migrations), `python -m src.shared_models` (Pydantic models)
- **DB Push**: `alembic upgrade head`
- **Required Env Vars**: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `MFA_ENCRYPTION_KEY` (Fernet key — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`; rotate via Replit secrets)

## Stack
- **Frontend**: React (CRACO), Tailwind CSS, Radix UI, `@dnd-kit`, `react-router-dom`, `recharts`, `framer-motion`
- **Backend**: FastAPI (Python), PostgreSQL, SQLAlchemy (asyncpg), Pydantic, PyJWT, bcrypt, pandas
- **AI/ML**: Google Generative AI (OpenAI API)
- **Runtime**: Node.js (latest LTS), Python 3.11+
- **ORM**: SQLAlchemy 2.0 with AsyncSession
- **Validation**: Pydantic
- **Build Tool**: CRACO, Alembic

## Where things live
- `/backend`: FastAPI application, business logic, database models, API routes.
  - `backend/server.py`: Main FastAPI app instantiation.
  - `backend/shared_models.py`: Pydantic models (source of truth for API schemas).
  - `backend/alembic/versions/`: Database migration scripts.
  - `backend/engines/smart_scheduling_engine.py`: Core scheduling logic.
  - `backend/name_validation.py`: Real personal name enforcement.
  - `students.pending_parent_{name,phone,email}` (Alembic `z1a2b3c4d5e6`): canonical pre-link parent contact for the IT inline-create flow per spec §5.6; trigger `students_clear_pending_parent_on_link_trg` clears them when `parent_id` transitions NULL → non-NULL.
  - `parent_invitations` table (Alembic `a3b4c5d6e7f8`) + `backend/utils/tokens.py` (`mint_invitation_token` / `verify_invitation_token`, shared `token_hash`): IT Phase-2 §6.2 parent-invitation token contract — JWT signed with `JWT_SECRET`, 7-day TTL, bound to `(workspace_school_id, student_id)` to block cross-row replay. Same sha256 hash scheme as `users.reset_token_hash`.
  - `workspace_quota` table (Alembic `b4c5d6e7f8a9`, IT Phase-2 §6.1, Task #207): one row per IT workspace. PK column is **`workspace_school_id`** (not `school_id`) to make it explicit that it always points at the synthetic `itw_{user_id}` schools row and never at a real-school tenant — §6.5 must use this canonical name. Columns: `max_students` (default 200, mirrors `quotas.independent_teacher.MAX_STUDENTS`), `max_classes` (5, mirrors `MAX_CLASSES`), `max_imports_per_day` (5), `max_rows_per_import` (200), `imports_today` + `imports_today_date` (UTC-day reset in app code; `_quota_view` parses date/datetime/ISO-string). Migration backfills existing IT workspaces. Bootstrap (`independent_teacher_bootstrap_routes.py` step 6.g.bis) seeds the row inside the all-or-nothing materialisation transaction, sourcing constants from `quotas.independent_teacher` so a future cap change carries through.
  - `backend/routes/independent_teacher_bulk_import_routes.py` (#207, IT Phase-2 §6.1): two endpoints — `POST /independent-teacher/students/bulk/parse` (Arabic-only CSV upload, returns per-row diagnostics, NO writes) and `POST /independent-teacher/students/bulk/commit` (gated by `require_recent_mfa_403` so the FE axios interceptor replays after passkey assertion; all-or-nothing insert pinned to `itw_{user_id}`; bumps daily import counter). CSV headers: `الاسم الكامل` (required), `رقم الهوية`, `الجنس` (`ذكر`/`أنثى`), `تاريخ الميلاد` (yyyy-mm-dd), `الصف` — **no classroom column** per spec. Cross-tenant payload columns (`school_id`/`tenant_id`/`class_id`/etc.) are rejected with the safe Arabic message. Names are re-validated server-side via `engines.name_validation.validate_personal_name` so a tampered preview cannot smuggle past parse. RBAC permission `students.bulk_import_workspace` is granted to `independent_teacher` only. **FE**: `/teacher/import-students` (`frontend/src/pages/TeacherModule/ImportStudentsPage.jsx`) — IT-only `ProtectedRoute`, sidebar entry under workspace-schedule (Upload icon, label `استيراد الطلاب`), uses `NassaqAlertDialog`'s `nassaqConfirm`/`nassaqError`/`nassaqInfo` (signature is `(message, [callback,] options)`); ships an Arabic CSV template download.
  - `backend/routes/independent_teacher_invitation_routes.py` (#205, IT Phase-2 §6.2b): three-route invitation envelope — `POST /independent-teacher/students/{id}/invite-parent-invitation` (IT-only, Tier-A MFA, idempotent on the `(workspace_school_id, student_id)` pending slot, raw token returned exactly once); `POST /independent-teacher/parent-invitations/{id}/cancel` (409 on non-pending); `POST /public/parent-invitations/accept` (unauth, IP-rate-limited at 10/5min via `rate_store`, atomically flips status + dedupes parent + materialises workspace `users` row + activates `guardian_links`, returns one-shot parent bearer). All three return **404** for cross-workspace ids per §8 inv. 3. The accept handler ALSO falls back to the `invite+{parent_id}@invite.nassaq.invalid` placeholder when a real `parent_email` collides with the global `users.email` unique index — closing the Task #203 carryover for the four §5.6 dedupe paths (national_id / phone+email / phone / email).
  - `backend/routes/independent_teacher_calendar_routes.py` (#208, IT Phase-2 §6.3): IT-only personal calendar CRUD — `GET/POST/PUT/DELETE /independent-teacher/calendar/events[/{id}]`. Every read/write pins `tenant_id == itw_{user_id}` + `created_by == current_user.id` + `is_personal=True` (Alembic `b1c2d3e4f5a6` adds the column on `calendar_events`). Cross-workspace ids return **404** per spec §8 inv. 3 — never 200/403. New RBAC permission `Permission.EVENTS_AUTHOR_OWN = "events.author_own"` is added to the `independent_teacher` role only; principals do not inherit it. The legacy `/v1/calendar/*` surface in `calendar_routes_mod.py` is deliberately untouched (principal events stay `is_personal IS NULL/false` so the IT read filter ignores them). FE: `frontend/src/pages/TeacherModule/TeacherPersonalCalendarPage.jsx` reuses `AdminCalendar` via new `basePath` / `importEnabled` / `titleAr` / `titleEn` props (defaults preserve the legacy school-wide behaviour byte-identically); sidebar entry "تقويمي الشخصي" → `/teacher/calendar` (IT-only).
  - Feature flag `IT_PARENT_INVITATIONS_ENABLED` (default off): when truthy at request time, the legacy §5.6 `POST /independent-teacher/students/{id}/invite-parent` route delegates to the §6.2b create endpoint instead of performing the immediate Pending → Linked transition. Read with `os.getenv` so tests can flip per-call without re-import. **Rollout**: kept **off in dev/test/staging** while the FE is rolled out behind the new chip + accept-landing surfaces; flipped **on in production** only after the §6.2c FE has shipped, since the legacy callsite delegates to the new envelope when truthy. Tests must set the env var explicitly (e.g. `monkeypatch.setenv("IT_PARENT_INVITATIONS_ENABLED", "1")`) to exercise the delegation path. **FE wiring (#206 §6.2c)**: when the flag is on, `TeacherStudentsPage` chip pulls invitation status from the §6.2c read endpoint `GET /independent-teacher/students/{id}/parent-invitation` (returns `parent_name` on the `accepted` row so the tooltip reads "Linked to <name>"); chip dates are formatted via `frontend/src/utils/hijriDate.js::formatHijriDate`, never `Intl.DateTimeFormat`. Cancel goes to `/independent-teacher/parent-invitations/{id}/cancel` via `NassaqAlertDialog` confirm. The public landing `/parent-invitations/accept?token=...` (`frontend/src/pages/ParentInvitationAcceptPage.jsx`) posts to `/public/parent-invitations/accept`, surfaces every failure variant through `NassaqAlertDialog` (`info`/`warning`/`error`) with locale-keyed copy, stores the returned bearer in `localStorage.nassaq_token`, and hard-navigates to `/parent?student_id=<id>` (alias for the existing `?child=` deep-link, honoured by `ParentActiveStudentContext.readChildIdFromLocation`).
- `/frontend`: React application, UI components, pages, API clients.
  - `frontend/src/App.js`: Main React app and routing.
  - `frontend/src/appRoutes.js`: Frontend route definitions with RBAC.
  - `frontend/src/services/apiClient.js`: Centralized API service layer.
  - `frontend/src/components/`: Reusable UI components.
  - `frontend/src/context/AuthContext.js`: Authentication context.
  - `frontend/src/i18n/`: Internationalization locale files (`ar.json`, `en.json`).
  - `frontend/src/utils/hijriDate.js`: Hijri/Gregorian date conversion utility.
  - `frontend/src/pages/SchedulePageNew.jsx`: Master schedule grid (workspace redesign 2026-05-06: sticky band, chip-collapsed alerts/insights, no pager UI).
  - `frontend/src/config/scheduleConfig.js`: `MASTER_GRID_TEACHER_WINDOW = 200` — single window size, no pagination.
  - `frontend/src/components/schedule/grid-theme/dayPalette.js`: Day color palette for schedules.
  - `schedule_sessions.version`: monotonically increasing integer used as the optimistic-concurrency token by the Independent Teacher manual schedule editor (spec 2026-05-12 §5.4); existing real-school schedule write paths ignore it.
- `/docs`: Project documentation and specifications.

## Architecture decisions
- **Multi-tenancy Enforcement**: `tenant_id` (aliased as `school_id`) is enforced at the database query level for all sensitive data access, ensuring strict data isolation.
- **Unified Approval Engine**: A generic engine manages various request types with a defined status lifecycle, transition validation, and audit logging for consistency and traceability.
- **Standardized Alerting**: All critical user-facing warnings, errors, and confirmations must use `NassaqAlertDialog` to ensure a consistent and branded user experience.
- **API Schema as Source of Truth**: Pydantic models in `shared_models.py` define API request/response schemas, ensuring strict data contracts between frontend and backend.
- **Robust Deployment Safety**: Destructive database operations are strictly blocked in non-development environments, and schema changes are exclusively managed via Alembic to prevent data loss.
- **IT cross-workspace by-id 404 invariant (spec §8 inv. 3)**: Every IT-reachable by-id read MUST 404 (never 403/200) for cross-workspace lookups so the API does not confirm the existence of foreign-tenant rows. Enforced by: (1) `utils/tenant_scope.py:tenant_scoped_find_one` falling back to `auth_scope.independent_workspace_id` when `tenant_id`/`school_id` are unset (covers `/assessments/{id}` and other shared routes); (2) explicit `require_request_school_id`-pinned `gd_find_one` on `behaviour_routes_mod.py` GET/PUT `/behaviour-records/{id}`; (3) tenant-pinned student lookup BEFORE `can_view_student` on `attendance_routes_mod.py` `GET /attendance/student/{id}`. The §5.9 exit suite (`test_independent_teacher_phase1_exit.py::test_5_9_2_*`) asserts strict 404 for all six §5.9 #2 collections.
- **IT invite-parent portal user materialisation**: `POST /independent-teacher/students/{id}/invite-parent` materialises a workspace-scoped `users` row (`role=parent`, `tenant_id=itw_{user_id}`, sentinel `password_hash="!invite-pending"` that cannot verify) on the **new-parent** dedupe path only, inside the same SAVEPOINT as the `parents`/`guardian_links` inserts; `guardian_links.parent_ref` is set to the new user id so `/notifications/bulk`'s cohort resolver finds the recipient. Dedupe paths (national_id / phone+email / phone / email) deliberately skip user materialisation because `users.email` is globally unique — Phase-2 will add a portal-onboarding flow for those paths.
- **IT §6.7 cross-workspace co-teaching (Task #210)**: `workspace_collaborators` (Alembic `b1c2d3e4f5a6`) is the **only** sanctioned cross-tenant data path between two Independent-Teacher workspaces; the §8 single-tenant invariant is intentionally relaxed **only** for the named `class_id`, never the wider workspace. Lifecycle `pending → accepted → revoked` (or `cancelled` / `expired`); partial unique idx `ux_workspace_collab_accepted` enforces "at most one active link per host+collaborator+class" and `ux_workspace_collab_pending` keeps invites idempotent on `(host, class, email)`. Tokens are JWTs minted via `utils/tokens.py::mint_collab_invitation_token` bound to `(host_school_id, class_id, collaborator_email.lower())`, purpose `workspace_collab_invitation`, 7-day TTL, sha256 stored as `token_hash` (same scheme as parent invitations). Routes live in `backend/routes/independent_teacher_collab_routes.py` and are mounted **without** the global tenant dep — IT role + Tier-A MFA (`require_recent_mfa_403`) are enforced per route, host-side writes additionally need `Permission.WORKSPACE_COLLAB_MANAGE` (`workspace.collab_manage`, granted to `independent_teacher`). Cross-workspace by-id reads return **404** (§8 inv. 3). At-callsite widening uses `backend/utils/collab_access.py::caller_can_access_class` / `caller_collab_mode_for_class` — never broaden `TenantIsolation` for this path. Audit actions: `INDEPENDENT_TEACHER_COLLAB_{INVITED,CANCELLED,ACCEPTED,REVOKED}`. **FE**: `frontend/src/components/teacher/CollaboratorsTab.jsx` rendered as the "المتعاونون" tab inside `TeacherClassDetailPage` (URL `?tab=collaborators`); the one-shot raw token is shown exactly once in a NassaqAlertDialog-driven modal. Accept landing `frontend/src/pages/CollabInvitationAcceptPage.jsx` is mounted on `/teacher/collab-accept` and `/workspace-collaborators/accept`, requires the collaborator to sign in first, posts to `/independent-teacher/workspace-collaborators/accept`, and lets the AuthContext interceptor handle any returned MFA step-up envelope.
- **IT §5.7 MFA step-up envelope**: All Independent-Teacher write/export surfaces emit the canonical step-up envelope as **HTTP 403** (`code` ∈ `{MFA_STEPUP_REQUIRED, MFA_PASSKEY_REQUIRED, MFA_RESTORE_REQUIRED}`) so the frontend axios interceptor (`frontend/src/contexts/AuthContext.js`) replays the request after passkey assertion. Use `require_recent_mfa_403()` (unconditional, IT-only routers) or `require_recent_mfa_403_if_independent_teacher()` (shared routes; no-op for non-IT) from `backend/dependencies.py`. Do not call bare `require_recent_mfa` on shared routes — its 401 status is treated as a hard logout by the FE.

## Product
- Smart timetable scheduling with drag-and-drop.
- Comprehensive attendance tracking and management.
- Exam and assessment management.
- Real-time notifications via WebSockets.
- Extensive reporting (PDF, CSV, XLSX) with filtering.
- Multi-tenant support for multiple schools.
- AI-powered insights and an interactive Hakim AI assistant.
- Student & Parent portals with personalized information.
- Teacher portfolio management.
- Role switching for administrators.
- Administrative calendar with event management.

## User preferences
- **Communication Style**: I prefer simple and direct language.
- **Workflow**: I want iterative development with clear milestones.
- **Interaction**: Ask for confirmation before making major changes or architectural decisions.
- **Explanations**: Provide detailed explanations for complex features or changes.
- **Codebase Changes**:
    - Do not re-introduce the old scheduling system.
    - Any new fix should not break existing working flows.
    - No changes to stable logic unless strictly necessary.
    - Do not use native browser `alert()`, `window.confirm()`, or `toast.error()` for important warnings; use `NassaqAlertDialog` instead.
    - Do not use `Intl.DateTimeFormat('ar-SA-u-ca-islamic')` for Hijri date conversion.
    - Do not hardcode `unsafe-eval` or broad wildcards in CSP without security review.
    - All warning/error/confirm dialogs must use `NassaqAlertDialog`.
    - Production data must NEVER be lost, overwritten, or replaced during deployment.
    - Seed scripts are BLOCKED in production and staging environments and SKIPPED if the database already has data.
    - Destructive database operations (drop, delete, rename, truncate) are BLOCKED in non-development environments.
    - Schema is managed exclusively via Alembic; no `Base.metadata.create_all()` or `drop_all()`.
    - All API errors should return safe Arabic messages; avoid exposing raw `str(e)`.
    - Replace bare `except:` with specific exception types and `except Exception: pass` with logged warnings/debug messages.
    - No `console.log` statements in frontend pages/contexts.
    - Do not use hardcoded passwords or sensitive information in source code; use environment variables or Replit secrets.

## QA verification with test credentials
- For QA verification, the coding agent may use test account credentials from `TEST_CREDENTIALS.md` to sign in as principal, teacher, or parent after implementing a feature or fix. The agent should verify the affected flow end-to-end, take screenshots when useful, and confirm there are no visible runtime errors or blockers. These credentials are for testing only and must never be hardcoded, copied into source files, logs, commit messages, comments, generated docs, screenshots, frontend constants, backend defaults, or any permanent configuration. Reference the file by filename only — never paste actual usernames, emails, or passwords elsewhere. Treat them as QA-only test data, not production secrets or deploy-time config.
- Preferred QA workflow: (1) implement the change, (2) sign in using the relevant test role from `TEST_CREDENTIALS.md`, (3) verify the affected flow end-to-end, (4) capture a screenshot if useful, (5) report results clearly.

## Gotchas
- Hijri date conversion requires `hijri-converter` libraries; `Intl.DateTimeFormat('ar-SA-u-ca-islamic')` is forbidden.
- Ensure `NassaqAlertDialog` is used for all user-facing warnings/errors/confirms; native browser alerts or `toast.error()` are prohibited for critical interactions.
- All database schema changes must be managed via Alembic; direct ORM schema creation/deletion is blocked in non-development environments.
- Production and staging environments explicitly block seed scripts and destructive database operations.
- Remember to use Replit secrets or environment variables for sensitive information instead of hardcoding.
- All API errors must return safe Arabic messages, avoiding raw exception strings.
- Be mindful of N+1 query issues; use bulk `gd_find` with `$in` for related data fetching.

## Pointers
- **FastAPI Docs**: `https://fastapi.tiangolo.com/`
- **React Docs**: `https://react.dev/`
- **Tailwind CSS Docs**: `https://tailwindcss.com/docs`
- **Radix UI Docs**: `https://www.radix-ui.com/docs`
- **SQLAlchemy Docs**: `https://docs.sqlalchemy.org/`
- **Alembic Docs**: `https://alembic.sqlalchemy.org/en/latest/`
- **Replit Secrets**: `https://docs.replit.com/misc/secrets`
- **Hakeem Engine Audit Report**: `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md`
- **IT Phase 1 §5.9 Exit-Criteria Coverage**: `docs/qa/2026-05-12-it-phase1-exit-criteria.md`