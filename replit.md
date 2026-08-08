# NASSAQ - نَسَّق
A comprehensive, multi-tenant school management platform with AI-powered features for administration, academics, and student performance.

## Run & Operate
- **Run**: `uvicorn backend.server:app --reload` (backend), `npm start` (frontend)
- **Build**: `npm run build` (frontend)
- **Typecheck**: none yet — no mypy/tsc gate exists (documented gap in `docs/ci.md`)
- **CI gate (local)**: `scripts/ci_local.sh [backend|frontend|e2e|security|all]` — same scripts GitHub Actions runs; see `docs/ci.md`
- **Codegen**: `alembic revision --autogenerate -m "description"` (DB migrations), `python -m src.shared_models` (Pydantic models)
- **DB Push**: `alembic upgrade head`
- **Deploy migrations**: `build.sh` runs `alembic upgrade head` once per release (build phase — single run, no autoscale race). The app then refuses to boot in production if the live schema is not at head (startup gate in `backend/app/lifecycle.py`).
- **Schema drift check**: `cd backend && alembic upgrade head && pytest tests/test_schema_orm_drift.py -v` — fails when a column/table is in `pg_models.py` but not in Postgres (missing migration), or vice versa. Update the allowlist in the test only when a divergence is intentional.
- **Destructive-migration guard**: `cd backend && pytest tests/test_migration_destructive_ops_guard.py -v` — fails when a migration's `upgrade()` drops a table/column or runs raw DROP/TRUNCATE/DELETE SQL without an explicit entry in `ALLOWED_DESTRUCTIVE`. Add the revision id + reason to that allowlist as the review sign-off; take a `pg_dump` first (see `docs/runbooks/database-backup-restore.md`).
- **Health probes**: `GET /healthz` (liveness, process only) and `GET /readyz` (readiness, DB ping bounded by `READINESS_TIMEOUT_S`, 503 when down) are public and root-mounted for load balancers / orchestrators / uptime monitors. `/system/health|status|metrics` stay admin-only diagnostics — see `docs/runbooks/health-checks.md`.
- **Rate limiting**: all limits go through the shared, Postgres-backed `rate_store` (`backend/middleware/rate_limiter.py`, table `rate_limit_counters`) so one budget is enforced across every autoscale instance — never add a process-memory counter (the in-memory store is only the fail-degraded fallback). Tunables: `RATE_LIMIT_STORE`, `RATE_LIMIT_DB_TIMEOUT_MS`, `RATE_LIMIT_NAMESPACE`, `RATE_LIMIT_LOGIN`/`RATE_LIMIT_WINDOW` — see `docs/runbooks/rate-limiting.md`.
- **Query memory safety**: `gd_find` without a `limit` is capped at `GD_FIND_MAX_ROWS` (default 5000) and logs a WARNING when it truncates; explicit limits are always honoured. Stream with `gd_iter_rows` / `gd_iter_batches` (keyset-paged, `GD_BATCH_SIZE` default 500) when an operation really must touch every row, and give caller-supplied page sizes a server-side `le=` maximum — see `docs/runbooks/query-memory-safety.md`.
- **No CPU-bound work on the event loop**: the API is one asyncio process per instance, so any synchronous render (PDF/XLSX/CSV/zip, image or archive work) run inline in an `async def` freezes *every* other request for its full duration — measured 1.5 s for a 200-row Arabic PDF, 3.4 s at 500 rows. Await `services.cpu_offload.run_cpu_bound(fn, kind="pdf")` instead (bounded thread pool: `CPU_OFFLOAD_MAX_WORKERS`/`MAX_INFLIGHT`/`TIMEOUT_S`; saturation → 503 `RENDER_BUSY`, overrun → 504 `RENDER_TIMEOUT`; metrics under `render_pool` in `GET /system/metrics`). Gather DB data with `await` first — the worker thread must not touch the session. Guarded by `backend/tests/test_cpu_offload.py` — see `docs/runbooks/cpu-bound-work-off-the-loop.md`.
- **No heavy algorithms on the event loop, and no long solve as one request**: timetable generation / optimization / constraint solving must run in a sync core handed to `run_cpu_bound(..., pool=TIMETABLE_POOL)` — inline it froze the whole instance for 1.3 s (12 classes), 6.2 s (24) and 27 s (40 classes); offloaded, worst loop stall is 96–331 ms (`backend/scripts/evidence_event_loop_timetable.py`). The pools are **separate on purpose** (`render` for sub-second documents, `timetable` for the 1–27 s search) so one generation can't starve every export behind it. Anything that can exceed a few seconds is additionally exposed as a job: `POST /smart-scheduling/generate/{school_id}/job` → `job_id`, poll `GET /smart-scheduling/job/{job_id}`; state lives in the `timetable_runs` row so polls survive autoscale instance-hopping. Fail fast before queueing, one run per school, stale runs reaped after `TIMETABLE_JOB_STALE_AFTER_S`. Sync cores must never `await` or touch the session — return log intents for the async wrapper to flush. Guarded by `backend/tests/test_timetable_offload.py` — see `docs/runbooks/timetable-generation-as-a-job.md`.
- **`gd_*` silently drops unknown keys on real tables**: `dict_to_model` keeps only real columns unless the table has a `data` JSONB overflow column — no error, no warning. `timetable_runs` was discarding every progress field the scheduling engine wrote (`completion_percentage`, `started_at`, `timetable_id`, …) until migration `tj01runs02data` added `data`. Before depending on a written field, confirm the column exists or the table has `data`.
- **Required Env Vars**: `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `MFA_ENCRYPTION_KEY` (Fernet key — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`; rotate via Replit secrets), `APP_URL` (public site base URL for email links, e.g. `https://nassaqapp.com` — `FRONTEND_URL` is an accepted alias and outranks Replit-managed domain fallbacks, so set `APP_URL` explicitly on real deployments to avoid a dev-domain `FRONTEND_URL` secret leaking into production emails; resolver: `config.get_public_app_url()`, boot fails in production/staging if missing or non-public)

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
  - `backend/routes/`: All HTTP routers. The Independent-Teacher (IT) Phase-2 routers — bulk import, parent invitations, calendar, lesson plans, co-teaching, workspace lifecycle, platform purge — are documented per-route in `docs/it-phase2-reference.md`.
- `/frontend`: React application, UI components, pages, API clients.
  - `frontend/src/App.js`: Main React app and routing.
  - `frontend/src/appRoutes.js`: Frontend route definitions with RBAC.
  - `frontend/src/services/apiClient.js`: Centralized API service layer.
  - `frontend/src/components/`: Reusable UI components.
  - `frontend/src/context/AuthContext.js`: Authentication context.
  - `frontend/src/locales/`: Internationalization locale files (`ar.json`, `en.json`).
  - `frontend/src/utils/hijriDate.js`: Hijri/Gregorian date conversion utility.
  - `frontend/src/pages/SchedulePageNew.jsx`: Master schedule grid (workspace redesign 2026-05-06: sticky band, chip-collapsed alerts/insights, no pager UI).
  - `frontend/src/config/scheduleConfig.js`: `MASTER_GRID_TEACHER_WINDOW = 200` — single window size, no pagination.
  - `frontend/src/components/schedule/grid-theme/dayPalette.js`: Day color palette for schedules.
  - `schedule_sessions.version`: monotonically increasing integer used as the optimistic-concurrency token by the Independent Teacher manual schedule editor (spec 2026-05-12 §5.4); existing real-school schedule write paths ignore it.
- `/docs`: Project documentation and specifications.
  - `docs/it-phase2-reference.md`: Per-route / per-table reference for every IT Phase-2 surface (§5.6, §5.7, §5.9, §6.1–§6.8, §8 inv. 3). Read this before touching IT workspace code.

## Architecture decisions
- **Multi-tenancy Enforcement**: `tenant_id` (aliased as `school_id`) is enforced at the database query level for all sensitive data access, ensuring strict data isolation.
- **Unified Approval Engine**: A generic engine manages various request types with a defined status lifecycle, transition validation, and audit logging for consistency and traceability.
- **Standardized Alerting**: All critical user-facing warnings, errors, and confirmations must use `NassaqAlertDialog` to ensure a consistent and branded user experience.
- **API Schema as Source of Truth**: Pydantic models in `shared_models.py` define API request/response schemas, ensuring strict data contracts between frontend and backend.
- **Robust Deployment Safety**: Destructive database operations are strictly blocked in non-development environments, and schema changes are exclusively managed via Alembic to prevent data loss.
- **Frontend toolchain (CRA + webpack-dev-server v5)**: The frontend stays on `react-scripts` 5.0.1 (CRA) with `webpack-dev-server` pinned to an EXACT version. CRA emits a v4 dev-server config; a shim in `frontend/craco.config.js` translates it to the v5 API. Decision + tradeoffs (vs. migrating to Vite) and the safe-upgrade procedure are in `docs/frontend-toolchain.md`. The shim is covered by `frontend/src/__tests__/cracoDevServer.test.js` (validates against wds's own schema) — run it before bumping `webpack-dev-server`. Do not loosen the exact pin back to a caret range.
- **IT cross-workspace by-id 404 invariant (spec §8 inv. 3)**: Every IT-reachable by-id read MUST 404 (never 403/200) for cross-workspace lookups so the API does not confirm the existence of foreign-tenant rows. See `docs/it-phase2-reference.md` for the three enforcement points.
- **IT §6.7 cross-workspace co-teaching**: `workspace_collaborators` is the only sanctioned cross-tenant data path between two IT workspaces; the §8 invariant is intentionally relaxed only for the named `class_id`. At-callsite widening uses `backend/utils/collab_access.py` — never broaden `TenantIsolation` for this path. Full lifecycle/route detail in `docs/it-phase2-reference.md`.
- **IT §5.7 MFA step-up envelope**: All IT write/export surfaces emit the canonical step-up envelope as **HTTP 403** so the FE axios interceptor (`frontend/src/contexts/AuthContext.js`) replays the request after passkey assertion. Use `require_recent_mfa_403()` (IT-only routers) or `require_recent_mfa_403_if_independent_teacher()` (shared routes) from `backend/dependencies.py`. Bare `require_recent_mfa` on shared routes is forbidden — its 401 status is treated as a hard logout by the FE.
- **IT §6.8 workspace lifecycle**: Export → soft-delete → reactivate (≤30d) → platform-admin hard-delete. Soft-delete requires an export within the last 24h. Hard-delete is platform-admin out-of-band only — never reachable from the IT API surface. Single-use export tokens. Detail in `docs/it-phase2-reference.md`.
- **Hakim assistant is mounted ONCE globally** via `frontend/src/components/hakim/GlobalHakimMount.jsx` (rendered from `App.js`). Never add per-page `<HakimAssistant />` or `<HakimChatWidget />` mounts — and never add page-local floating/fixed Hakim widgets of any kind (the floating corner belongs to the global launcher alone; page-specific Hakim insights must render as in-content cards, e.g. the inline insights card pattern in `AdminDashboard.jsx` / `UsersClassesManagement.jsx`) — pages that need Hakim get it automatically. Route exclusions (auth/token/legal/onboarding) live in `HIDDEN_PREFIXES` there; parents on `/parent/*` get the child-aware `HakimChatWidget` with the `raised` prop (clears mobile bottom nav). The mount is keyed by effective role+tenant+user so chat never survives impersonation or role switches.

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

## Design guidelines & marketing-surface overrides
The product follows `design_guidelines.json` (in-app/admin surfaces). The public **landing page** (`frontend/src/pages/LandingPage.jsx`) intentionally overrides four rules from that spec to optimize for marketing-funnel conversion — do NOT "fix" these back to the in-app spec:
- **Turquoise is the unifying accent**, not "sparing". Used across eyebrows, headings, active states, and CTAs to enforce brand cohesion across the funnel. Purple is reserved for AI/Hakim and the pricing-offer eyebrow.
- **Navy + nassaq-texture sections alternate with light sections** (hero, how-it-works, AI capabilities, proof, pricing are navy; pain, journey, ecosystem, FAQ, final CTA are light). The dark/light alternation paces the funnel — it intentionally deviates from "backgrounds should be mostly #F8FAFC".
- **Heading scale is larger than the in-app `text-3xl/4xl` spec** (`lg:text-[3.5rem]`, `text-6xl`, `text-7xl` on hero/proof/CTA) — marketing display sizing.
- **Primary conversion CTAs use turquoise** rather than the in-app navy primary recipe: the hero CTA is solid `bg-brand-turquoise`, while the recommended pricing tier and final CTA use the `from-brand-turquoise to-cyan-500` gradient. Secondary/tertiary buttons remain navy or transparent-outline.

Strict rules from `design_guidelines.json` that DO apply on the landing page (do not violate):
- No emoji used as decorative icons — always use `lucide-react`.
- No raw hex literals in JSX — use Tailwind brand tokens (`bg-brand-navy`, `bg-brand-turquoise`, `bg-brand-purple`).
- No text gradients (`bg-clip-text`).
- RTL via logical properties (`ps-*`, `pe-*`, `ms-*`, `me-*`, `text-start`/`text-end`).
- Lucide icons with `strokeWidth={1.5}` and `aria-hidden="true"` on decorative ones.

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
- **IT Phase 2 Reference (per-route / per-table)**: `docs/it-phase2-reference.md`
