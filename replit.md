# NASSAQ - نَسَّق
## Smart Multi-Tenant School Management System

## Overview
NASSAQ is a comprehensive, full-stack school management platform designed for multi-tenant environments. It features a React frontend and a FastAPI backend. The system aims to provide a smart, AI-powered solution for educational institutions, covering various aspects of school administration from academic management to student performance analytics. Key capabilities include smart timetable scheduling, attendance tracking, exam and assessment management, real-time notifications, and extensive reporting features. The project's vision is to enhance educational workflows, improve student outcomes through data-driven insights, and provide a secure, scalable platform for schools in the MENA region.

## User Preferences
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

## System Architecture
The platform utilizes a modern full-stack architecture.

### Hakeem Auto-Generation Engine — Constraint Audit & Generation Summary (2026-05-03)
- Audited the placement loop in `backend/engines/smart_scheduling_engine.py` against all hard constraints (A double-booking, B unavailability, C boundary, D weekly quota, E max consecutive, F max periods/day) and best-effort fairness (G). Audit report: `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md` — no gaps found, all constraints A–F enforced.
- Added a persisted `generation_summary` JSONB column on `timetable_runs` (Alembic revision `u1v2w3x4y5z6`) and a matching `Optional[Dict[str, Any]]` field on the SQLAlchemy `TimetableRun` model.
- New helper module `backend/engines/scheduling_summary.py` (`RejectionCounters`, `TeacherPlacementRecord`, `build_generation_summary`) builds the rich summary; covered by `backend/tests/test_scheduling_summary.py`.
- The placement loop now aggregates per-demand rejection counters into a run-wide `_last_rejection_counts` dict; `generate_timetable` builds the summary, persists it on the run row, and returns it on `GenerationResult.generation_summary` so the route response includes it automatically.

**Frontend**:
- Built with React (Create React App + CRACO), styled with Tailwind CSS and Radix UI.
- `App.js` serves as a thin composition layer for providers and routing.
- Routes are managed in `appRoutes.js` with role-based access control.
- API service layer is centralized in `services/apiClient.js` with domain-specific modules.
- Reusable UI components are organized within `components/`.
- Custom hooks (e.g., `useStudentProfile`) encapsulate complex state and logic.
- Authentication context (`AuthContext.js`) handles JWT, refresh tokens, and session management, including an `AbortController` with a 10s timeout for `fetchUser`.
- `NassaqAlertDialog` is the standardized component for all system alerts, warnings, and confirmations.
- Internationalization (i18n) uses JSON locale files (`ar.json`, `en.json`) and a `useTranslation()` hook for both static UI text and dynamic data localization.
- Hijri/Gregorian date conversion is handled by a centralized utility (`hijriDate.js`) using `hijri-converter` libraries and Eastern Arabic numerals.
- Hakim AI character is a dynamic, context-aware interactive system with various poses and animations, integrated system-wide.

**Backend**:
- Developed with FastAPI (Python), utilizing JWT for authentication.
- `server.py` acts as a thin orchestrator for app creation and router registration.
- Middleware stack (`app/middleware.py`) handles PostgreSQL sessions, security headers, audit logging, CORS, rate limiting, and global error handling.
- Lifecycle hooks (`app/lifecycle.py`) manage DB initialization, seeding, and approval engine setup.
- Pydantic models (`shared_models.py`) serve as the single source of truth for API request/response schemas.
- API responses adhere to a global error envelope for consistency.
- Routes are modularized into `*_mod.py` files, each under ~1000 lines, for better organization.
- Core business logic is encapsulated in `engines/` (e.g., `smart_scheduling_engine.py`, `hakeem_plan_service.py`).
- Security hardening includes sensitive field filtering, SQL injection blocking, ReDoS protection, and robust error logging.
- Content Security Policy (CSP) headers are set in `middleware.py`.
- WebSocket security ensures tokens are sent via message after connection, not in the URL.
- Production readiness includes structured logging, request tracing, slow query detection, session rollback safety, and tenant isolation enforcement.
- Real Personal Name Enforcement: `name_validation.py` validates user names against generic terms and patterns, rejecting non-personal names.

**Database**:
- PostgreSQL is used as the primary database, co-located with Replit via `DATABASE_URL`.
- Asynchronous SQLAlchemy with `asyncpg` provides the ORM layer.
- `GenericDocument` JSONB storage is used for flexible schema data.
- Alembic manages database migrations.
- A repository layer (`backend/repositories/`) provides simplified data access using `gd_*` helpers from `engines/sql_utils.py`, which handle session management and tenant isolation.
- `db_indexes.py` defines compound indexes to optimize query performance, applied on startup.
- Deployment safety policies include blocking destructive operations, seed scripts in production, and requiring Alembic for schema management.

**Key Features and Design Patterns**:
- **Multi-tenancy**: Implemented with `tenant_id` (aliased as `school_id`) filters enforced at the database query level for all sensitive data access.
- **Smart Scheduling System**: Uses `smart_scheduling_engine.py` to generate timetables, incorporating teacher preferences, constraints, and capacity diagnostics. Supports drag-and-drop session rearrangement.
- **Unified Approval Engine**: Manages various request types (e.g., school/teacher registration) with a defined status lifecycle, transition validation, and audit logging.
- **Form System Architecture**: Standardized components for multi-step forms with responsive layouts, auto-validation, and data persistence.
- **Hakim AI Character**: A dynamic, interactive AI assistant integrated system-wide, offering contextual messages, insights, and guiding users.
- **Product Intelligence Hub**: A robust system for tracking, managing, and analyzing product issues, featuring granular RBAC, audit logging, and an event flow engine.
- **Administrative Calendar**: Manages school events with CRUD operations and CSV import functionality.
- **Teacher Portfolio**: A comprehensive system for teachers to document professional achievements and evidence, with auto-generated and manual entry options.
- **Reporting & Export Engine**: Centralized generation of 9 report types (PDF, CSV, XLSX) with extensive filtering and role-based authorization.
- **Role Switching System**: Allows platform administrators to impersonate other roles for testing and support, with audit logging.
- **WebSocket Real-time Notifications**: Securely delivers notifications using a token-based authentication mechanism.
- **Student & Parent Portals**: Dedicated interfaces providing personalized information, schedules, grades, attendance, and communication features.
- **Relationship Graph Engine**: Maps and manages complex relationships between users (students, parents, teachers) and entities (schools, classes, subjects).
- **Session Engine**: Manages live class sessions, including attendance, participation tracking, behavior logging, and post-session analytics with AI insights and notifications.
- **Academic Structure & School Settings**: Comprehensive configuration of school academic parameters and timetable settings, with auto-regeneration of time slots.
- **Class Detail Page**: Provides a dedicated view for managing class details, student records, and curriculum plans.
- **Real Personal Name Enforcement**: Backend validation and frontend guards prevent generic names for user accounts.
- **Comprehensive Test Data Seeding**: An idempotent script creates two isolated school tenants with full academic and operational data for thorough testing.

## External Dependencies

- **PostgreSQL**: Primary database.
- **FastAPI**: Backend web framework.
- **React**: Frontend library.
- **Radix UI**: Frontend component library.
- **Tailwind CSS**: CSS framework.
- **Axios**: HTTP client for API requests.
- **Recharts**: Charting library for data visualization.
- **PyJWT**: JSON Web Token implementation for Python.
- **bcrypt**: Password hashing library.
- **qrcode**: QR code generation library.
- **pandas**: Data manipulation and analysis library for Python.
- **Google Generative AI (OpenAI API)**: For Hakim AI engine, translation service, and AI-powered operations.
- **reportlab**: PDF generation library for Python.
- **xlsxwriter**: Excel file generation library for Python.
- **psutil**: System monitoring (process and system utilities).
- **python-docx**: Library for creating and updating Microsoft Word files.
- **hijri-converter (Python & npm)**: For Hijri/Gregorian date conversions.
- **@dnd-kit**: Drag-and-drop library for React.
- **react-router-dom**: Routing for React applications.
- **react-markdown, remark-gfm**: Markdown rendering in React.
- **framer-motion**: Animation library for React.
- **openpyxl**: Excel file parsing library for Python.