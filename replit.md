# NASSAQ - نَسَّق
A comprehensive, multi-tenant school management platform with AI-powered features for administration, academics, and student performance.

## Run & Operate
- **Run**: `uvicorn backend.server:app --reload` (backend), `npm start` (frontend)
- **Build**: `npm run build` (frontend)
- **Typecheck**: `mypy backend/` (backend), `npm run typecheck` (frontend)
- **Codegen**: `alembic revision --autogenerate -m "description"` (DB migrations), `python -m src.shared_models` (Pydantic models)
- **DB Push**: `alembic upgrade head`
- **Required Env Vars**: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`

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
- `/docs`: Project documentation and specifications.

## Architecture decisions
- **Multi-tenancy Enforcement**: `tenant_id` (aliased as `school_id`) is enforced at the database query level for all sensitive data access, ensuring strict data isolation.
- **Unified Approval Engine**: A generic engine manages various request types with a defined status lifecycle, transition validation, and audit logging for consistency and traceability.
- **Standardized Alerting**: All critical user-facing warnings, errors, and confirmations must use `NassaqAlertDialog` to ensure a consistent and branded user experience.
- **API Schema as Source of Truth**: Pydantic models in `shared_models.py` define API request/response schemas, ensuring strict data contracts between frontend and backend.
- **Robust Deployment Safety**: Destructive database operations are strictly blocked in non-development environments, and schema changes are exclusively managed via Alembic to prevent data loss.

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