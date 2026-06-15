# NASSAQ (نَسَّق) — Engineering Handover Technical Report

> **Audience:** the next engineering team (engineers, tech leads, architects) taking over NASSAQ.
> **Purpose:** a source-of-truth transfer document derived from the real repository and its docs — not a summary. It explains what the system is, how it is built, where the dangerous areas are, and the rules that must never be broken.
> **Date of write-up:** 2026-06-15. Verified against the live codebase at this date.
> **How this was produced:** direct inspection of `replit.md`, `threat_model.md`, `.replit`, `build.sh`, backend/frontend source, migrations, tests, and the `docs/` corpus. Files inspected are listed at the end.

---

## 0. TL;DR for the incoming team

- **What it is:** a multi-tenant (multi-school) school-management SaaS for the Saudi market. Arabic-first / RTL. React (CRA + CRACO) frontend, FastAPI (async SQLAlchemy + PostgreSQL) backend, served same-origin in production. AI features ("Hakim") via an OpenAI-compatible gateway.
- **Scale:** ~200k lines of Python backend, ~152k lines of JS/JSX frontend, **89 route modules**, ~40 business engines, **75 Alembic migrations**, **214 backend test files**, **150 frontend pages**.
- **Two product shapes share one codebase:** full **Schools** (principal/admins/teachers/students/parents) and **Independent Teacher (IT) workspaces** (a single teacher running a lightweight workspace). They share primitives but have different tenancy, routing gates, lifecycle, and quotas. The IT surface is the newest and highest-churn area.
- **The non-negotiables:** strict tenant isolation, deny-by-default authz enforced **in the backend** (the frontend RBAC is UX only), Alembic-only schema changes, no destructive DB ops outside development, and Arabic-safe error messages.
- **The biggest operational trap:** the in-editor **`Backend API` dev workflow runs with `ENVIRONMENT=production` against the real production database** (see §13). Treat the dev backend as production.

---

## 1. Project Overview

### What the platform does
NASSAQ is a comprehensive school-management platform with AI-assisted administration, academics, and student-performance features. Core product capabilities (from `replit.md` / live routes):

- Smart timetable scheduling with drag-and-drop.
- Attendance tracking and management.
- Exam / assessment management and a grades ledger.
- Real-time notifications over WebSockets.
- Reporting & exports (PDF, CSV, XLSX) with filtering.
- Multi-tenant support for many schools, plus standalone **Independent Teacher** workspaces.
- AI-powered insights and an interactive **Hakim** assistant.
- Student & Parent portals.
- Teacher portfolio management.
- Role switching for administrators (and platform-admin impersonation/preview).
- Administrative calendar with event management.

### Primary user roles
Defined canonically in `backend/middleware/rbac.py` (`ROLE_PERMISSIONS`):

| Role | Scope | Notes |
|---|---|---|
| `platform_admin` | Cross-tenant | Platform operator. Can preview/impersonate schools. Credential-minting surfaces here are high-risk. |
| `school_principal` | One school tenant | Top of the school hierarchy. |
| `school_admin` | One school tenant | Lower-tier admin. Must **not** be able to take over higher-privileged same-tenant accounts (historical weak spot). |
| `teacher` | One school tenant | School-employed teacher. |
| `independent_teacher` | Synthetic IT workspace (`itw_{user_id}`) | Restricted permission set; gated out of full-school routes. |
| `student` | One school tenant | Student login is currently **disabled platform-wide** via a flag in `dependencies.py`. |
| `parent` | One school tenant | Parent/guardian portal access, scoped by guardian links. |

There is also a `school_sub_admin` concept (custom-permission only, no base permission set — see memory/`replit.md` discussion of `/users/create`).

### High-level product domains
Timetable/scheduling · Classes/Students/Subjects (academic structure) · Attendance · Assessments/Grades · Parent & Student portals · Notifications/Communication · Reports/Exports · AI/Hakim · School & Account settings · Independent-Teacher workspaces (parallel, lighter-weight tenancy).

---

## 2. Architecture Overview

### Shape
A classic **SPA + API** split that is deployed **same-origin**:

```
Browser (React SPA, RTL)
   │  HTTPS (Replit-managed TLS)
   ▼
FastAPI app  (single ASGI app, server.py::create_app)
   │  middleware onion → routers (/api/*) → engines (business logic)
   ▼
PostgreSQL (async SQLAlchemy)  +  GenericDocument JSONB store  +  OpenAI-compatible AI gateway
```

- **Frontend / backend boundary:** the SPA talks to `/api/*`. In production the FastAPI app **also serves the built frontend** (static `build/`), so the browser never needs a separate backend origin. This is why the frontend defaults `REACT_APP_BACKEND_URL` to an **empty string → relative URLs** (`process.env.REACT_APP_BACKEND_URL || ''`, used in `AuthContext.js`, `WebSocketContext.jsx`, etc.). If you ever bake an absolute/blank URL incorrectly you get `/undefined/api/...` 404/405s (see memory note `react-backend-url-relative`).
- **Where business logic lives:** in `backend/engines/*` (≈40 engines). Routers should stay thin — auth/validation/scoping then delegate to an engine. In practice some routes still hold logic (legacy factory routes), so this is aspirational in places.
- **Where shared contracts live:** Pydantic models in `backend/shared_models.py` are the **API request/response source of truth**. The SQLAlchemy ORM in `backend/pg_models.py` is the **database schema source of truth**. They are intentionally separate.
- **Tenant scoping is explicit, not automatic.** ⚠️ Data-access helpers (`gd_find`/`gd_find_one`) apply **only the caller-supplied filters** — they do **not** auto-inject `tenant_id`. Correct scoping depends on each route passing an explicit tenant predicate (resolved via `auth_scope.require_request_school_id`), the by-id helpers in `backend/utils/tenant_scope.py`, and `collab_access.py` for the co-teaching exception. `backend/middleware/tenant_isolation.py` provides helper utilities/decorators; it is **not** a global query-rewriting middleware. **A future engineer must never assume tenant filtering happens for them.**

### Request/response flow
1. Request enters the **middleware onion** (see §5.2). The DB-session middleware binds an `AsyncSession` to a `ContextVar` for the request.
2. Router-level **dependencies** (`backend/dependencies.py`) run: auth (`get_current_user`), capability gates (`require_full_school_tenant`), tenant resolution (`auth_scope.require_request_school_id`), and step-up MFA where needed.
3. The route delegates to an **engine**; data access goes through repositories / `gd_*` helpers, but the **tenant predicate must be passed explicitly** by the caller (see §8.5 — there is no automatic tenant rewriting).
4. Responses are wrapped in a canonical envelope `{success, error?, meta?}`; exceptions are converted to Arabic-safe envelopes by handlers in `server.py`.

---

## 3. Tech Stack

**Frontend**
- React 18 via **Create React App (`react-scripts` 5.0.1) + CRACO** (not Vite — deliberate, see §11).
- Tailwind CSS, Radix UI primitives, `@dnd-kit` (drag-and-drop scheduling), `react-router-dom`, `recharts`, `framer-motion`, `axios`.
- i18n via JSON locale files (`frontend/src/locales/ar.json`, `en.json`) with a custom `useTranslation` from `ThemeContext`.
- `webpack-dev-server` pinned to an **exact v5** version, adapted to CRA's v4 config via a shim in `frontend/craco.config.js`.

**Backend**
- **FastAPI** (app factory, version string `3.0.0`), **async SQLAlchemy 2.0** (`asyncpg`), **Pydantic**, **PyJWT**, **bcrypt**, **pandas**.
- Exports: `reportlab` + `Amiri` fonts + `arabic_reshaper` + `python-bidi` (PDF), `xlsxwriter`/`pandas` (XLSX/CSV).
- **Alembic** for migrations.

**Database:** PostgreSQL 16. ORM: SQLAlchemy 2.0 AsyncSession. Hybrid storage: relational tables **plus** a `generic_documents` JSONB collection store (§7.3).

**AI/ML:** OpenAI Python SDK pointed at a gateway (`AI_INTEGRATIONS_OPENAI_BASE_URL` / `_API_KEY`), model `gpt-5-mini`. Integration installed: `python_openai_ai_integrations`.

**Runtime / tooling** (from `.replit`): Python 3.12 base module, Node.js 22, PostgreSQL 16. Build via `build.sh`. Deploy target: **autoscale**. (`replit.md` says "Python 3.11+"; the actual Replit module is `python-base-3.12` — watch for site-packages skew across 3.11→3.12, see memory `branch-swap-env-resync`.)

---

## 4. Repository Structure

```
/backend/                  FastAPI app, business logic, models, routes, migrations, tests
  server.py                App factory (create_app) + global exception handlers   ← READ FIRST
  dependencies.py          Shared db proxy, auth gates, MFA step-up, engine singletons  ← READ FIRST
  shared_models.py         Pydantic models = API schema source of truth          ← READ FIRST
  pg_models.py             SQLAlchemy ORM = DB schema source of truth             ← READ FIRST
  auth_scope.py            Tenant/workspace resolution (require_request_school_id)
  config.py                Env detection, seed_allowed(), destructive_ops_allowed()
  db.py                    Engine/session, init_pg_tables() schema head-gate
  db_indexes.py            Index definitions
  app/
    middleware.py          register_middleware(); pg session, security headers, audit
    lifecycle.py           startup_tasks/shutdown_tasks; schema gate; deferred background loops
    routes.py              register_routes(); centralized router mounting + capability gates
    integrity_messages.py  PG constraint name → Arabic message map
  middleware/              ErrorHandler, RateLimiter, RequestTracing, TenantIsolation, rbac, audit...
  routes/                  89 route modules (*_mod.py consolidated, *.py legacy factory)
  engines/                 ~40 business engines (scheduling, attendance, assessment, hakim_ai, export, noor_import, ...)
  services/                hakim_llm_service.py, email_service, etc.
  repositories/            data-access layer
  utils/                   collab_access.py, tenant_scope.py, tokens.py, public_hakim_limiter.py, ...
  models/                  LEGACY modular Pydantic package (mostly superseded by shared_models.py)
  alembic/versions/        75 migrations
  tests/                   214 test files (schema drift, destructive guard, IT invariants, ...)
  ARCHITECTURE.md          Backend architecture guide (somewhat dated)
  DEPLOYMENT_SAFETY.md     The permanent deployment-safety policy

/frontend/
  src/
    App.js                 App shell + provider tree                              ← READ FIRST
    routes/appRoutes.js    Route table (lazy-loaded) with RBAC
    components/guards/RouteGuards.js   ProtectedRoute (UX-level RBAC, not security)
    contexts/AuthContext.js            Auth state, axios interceptors, MFA replay, X-School-Context  ← READ FIRST
    contexts/ThemeContext.js           i18n (useTranslation), theme
    contexts/WebSocketContext.jsx      realtime notifications
    services/apiClient.js              centralized API surface (api.students.list(), ...)
    components/ui/NassaqAlertDialog.jsx  mandated dialog primitive
    components/PerimeterGateBridge.jsx   IT "workspace materialized" gate
    locales/ar.json, en.json           translations
    pages/                              150 pages
  craco.config.js          CRA↔webpack-dev-server v5 shim (do not loosen the pin)

/docs/                     Specs, audits, QA, security, runbooks (rich — read the IT + security ones)
build.sh                   Deploy build: venv, deps, alembic upgrade head, frontend build, prune
.replit                    Modules, workflows, ports, deployment, userenv (ENVIRONMENT etc.)
replit.md                  Project README + guardrails + user preferences (authoritative)
threat_model.md            Security architecture, assets, trust boundaries, confirmed weak spots
```

> Note: there are **two** Pydantic locations — the single-file `backend/shared_models.py` (the operative source of truth, ~23 importers) and the older `backend/models/` package (~5 importers, legacy). Treat `shared_models.py` as canonical; `models/` is being phased out.

---

## 5. Backend Design

### 5.1 App bootstrapping
`backend/server.py::create_app()` (factory) builds the FastAPI app, registers four global exception handlers, then calls `register_middleware()`, mounts routers under an `/api` `APIRouter` via `register_routes()`, and wires `startup_tasks`/`shutdown_tasks`. Module-level `app = create_app()` is the ASGI target. Logging is **structured JSON** (one record per line, with `request_id`, `user_id`, `tenant_id`, `path`, `status_code`, `duration_ms`). API docs (`/docs`, `/redoc`, `/openapi.json`) are **disabled in production**.

### 5.2 Middleware stack
Registered in `backend/app/middleware.py` (`register_middleware`). **Starlette runs the *last-added* middleware *outermost* (first on the inbound path).** The components are:
- `ErrorHandlerMiddleware` — canonical JSON for unhandled errors (`middleware/error_handler.py`).
- `RateLimitMiddleware` — IP- and user-based limits (`middleware/rate_limiter.py`).
- `RequestTracingMiddleware` — request IDs (feeds the JSON logger).
- `pg_session_middleware` — binds the request `AsyncSession`; **commits on non-GET, rolls back on GET**. ⚠️ See the critical gotcha in §5.6.
- `add_security_headers` — HSTS, CSP, X-Frame-Options.
- `audit_log_middleware` — async business audit trail.
- `CORSMiddleware` and `TrustedHostMiddleware` (`ALLOWED_HOSTS` / `CORS_ORIGINS`).

Because of the last-added-outermost rule, the **actual inbound execution order** is roughly: `TrustedHost` (when enabled) → `CORS` → `audit_log` → `add_security_headers` → `pg_session` → `RequestTracing` → `RateLimit` → `ErrorHandler` → route. (The global exception handlers in `server.py` are the final safety net around all of it.) Read `register_middleware` directly before reasoning about ordering — the registration order in the file is the reverse of execution order.

### 5.3 Routing structure
- All app routes mount under `/api` (`register_routes` in `backend/app/routes.py`).
- Two coexisting styles: **consolidated** `*_mod.py` modules (the modern target) and **legacy factory** `*.py` modules (`create_*_router()`), still active. `server.py`'s own docstring documents this split.
- **Capability gates at mount/route level**: `require_full_school_tenant` blocks Independent-Teacher accounts from enterprise-only routes; IT routers (`independent_teacher_*`) are mounted **without** the global tenant dependency and instead self-resolve via `auth_scope`.

### 5.4 Service / business-logic organization
`backend/engines/*` holds the domain logic: `smart_scheduling_engine`, `attendance_engine`, `assessment_engine`, `behaviour_engine`, `approval_engine` (+ `approval_handlers`), `notification_engine`/`school_notification_engine`, `reporting_engine`, `export_engine`, `relationship_graph_engine`, `hakim_ai_engine`, `noor_import/*`, `tenant_engine`, `identity_engine`, `session_engine`, `audit_engine`, etc. The **Unified Approval Engine** is a generic state-machine for many request types (status lifecycle + transition validation + audit).

### 5.5 Models / schemas / validation
- **API contracts:** `shared_models.py` (Pydantic). Includes domain validators, e.g. Saudi national-ID format and real-name enforcement (`backend/name_validation.py` / `engines/name_validation.py`).
- **DB schema:** `pg_models.py` (SQLAlchemy ORM).
- **Validation approach:** Pydantic at the edge; engines add business validation; the DB enforces unique/foreign-key constraints whose violations are mapped to Arabic messages.

### 5.6 Error-handling conventions (important)
Defined in `server.py`:
- `StarletteHTTPException` → `{success:false, error:{code,message,detail}}`. **If `detail` is a dict** (e.g. the MFA step-up envelope `{code:"MFA_STEPUP_REQUIRED", challenge_endpoint, ...}`) its fields are spliced into the envelope so the **frontend interceptor can dispatch on the machine-readable code**. Explicit `headers` (e.g. `Retry-After`) are preserved.
- `IntegrityError` → **409** with a field-specific Arabic message via `app/integrity_messages.py` (maps PG constraint names like `uq_students_national_id_school`).
- `RequestValidationError` → **422** with field/message pairs in `meta.validation_errors` (logged for triage).
- Catch-all `Exception` → **500** with fixed `SAFE_ERROR_CODE` + `SAFE_ERROR_MESSAGE_AR` (never leaks `str(exc)`).

**Convention (from `replit.md`):** never return raw `str(e)`; all user-facing errors are safe Arabic messages. Replace bare `except:`/`except Exception: pass` with specific types and logging.

> ⚠️ **Middleware-commit gotcha (memory `middleware-commits-on-4xx`):** `pg_session_middleware` commits non-GET requests on **any** response status. An `HTTPException` raised *after* a write does **not** roll back — the write persists. **Order all authz/validation guards before any write.**

### 5.7 Startup / background concerns
`backend/app/lifecycle.py`:
- **Blocking (safety):** schema **head-gate** — `db.py::init_pg_tables()` checks `alembic_version == script head`; in production a mismatch raises `RuntimeError` and the app **refuses to boot**. Runtime sequences (e.g. `issue_number_seq`) are ensured.
- **Deferred (via `asyncio.create_task`, so the health check isn't blocked):** seeding (only if `config.seed_allowed()` and DB empty), revoked-token cleanup (6h), workspace reactivation reminders (24h), workspace auto-exports (1h). Deferring non-critical startup work is deliberate to avoid autoscale cold-start health-probe flakes (memory `autoscale-healthcheck-startup`).

---

## 6. Frontend Design

### 6.1 App shell & routing
`frontend/src/App.js` wraps the app in a provider tree: `AuthProvider`, `ThemeProvider`, `NassaqAlertProvider`, `WebSocketProvider`, plus `BrowserRouter` and global pieces (`PerimeterGateBridge`, beta banner, error boundaries). Routes live in `frontend/src/routes/appRoutes.js`, **code-split with `React.lazy`/`Suspense`**.

### 6.2 Role-based route guards (UX layer, NOT a security boundary)
`frontend/src/components/guards/RouteGuards.js` — `ProtectedRoute` enforces `allowedRoles` / `requiredPermission`, redirects to the role's default dashboard, and also gates **force-password-change** and **MFA-enrollment** flows. **This is presentation only.** Real enforcement is the FastAPI dependency + RBAC/tenant middleware validating JWT claims on every request. Do not describe these guards as a security boundary.

### 6.3 Auth context & token handling
`frontend/src/contexts/AuthContext.js` centralizes user state, token storage (local/session storage), and the **axios interceptors**:
- **401 → token refresh** (`attemptTokenRefresh`, rotates via refresh token).
- **403 MFA step-up** → interceptor pauses the request, opens the step-up modal (`MfaStepUpProvider` / `MfaStepUpDialog`), then **replays** the original request with the fresh token. This is why IT write/export surfaces must emit the step-up envelope as **HTTP 403** (a 401 is treated as a hard logout) — see §8 and `replit.md` IT §5.7.
- **Impersonation/preview:** injects the `X-School-Context` header when a school context is active in session storage. (Server-side, this header is treated as **equivalent to impersonation** and must carry the same MFA/audit/expiry guarantees — see `threat_model.md`.)

### 6.4 Centralized API client
`frontend/src/services/apiClient.js` exposes a structured surface (`api.auth`, `api.students.list(params)`, etc.) over the shared axios instance, so components don't hardcode URLs.

### 6.5 i18n / RTL
Locale JSON in `frontend/src/locales/`. `dir="rtl"` is applied app-wide. RTL is implemented via **logical Tailwind properties** (`ps-*/pe-*/ms-*/me-*`, `text-start/text-end`) — a hard rule on the landing page and in-app. Hijri dates use the `hijri-converter` utility (`frontend/src/utils/hijriDate.js`); `Intl.DateTimeFormat('ar-SA-u-ca-islamic')` is **forbidden**.

### 6.6 Enforced UX conventions (from `design_guidelines.json` + `replit.md`)
- All warnings/errors/confirms use **`NassaqAlertDialog`** (`useNassaqAlert` → `nassaqConfirm/nassaqError/nassaqWarning`). Native `alert()`/`confirm()`/`toast.error()` are **prohibited** for important interactions.
- No emoji as icons (use `lucide-react`, `strokeWidth={1.5}`, `aria-hidden` on decorative icons). No raw hex in JSX (use brand tokens). No text gradients. No `console.log` in pages/contexts.
- The public **LandingPage** intentionally overrides four design-spec rules for marketing conversion — documented in `replit.md` "Design guidelines & marketing-surface overrides"; **do not "fix" these back**.

---

## 7. Database & Data Model

### 7.1 Sources of truth
- **`backend/pg_models.py`** — SQLAlchemy ORM = the DB schema source of truth.
- **`backend/shared_models.py`** — Pydantic = the API contract source of truth.
- **`backend/alembic/versions/`** — the only sanctioned way to change schema (75 migrations).

### 7.2 Main entities & relationships
- `users` — central identity (login, role + `additional_roles`/`linked_roles` JSONB, tenant association, MFA state, `last_password_change`).
- `schools` — tenant root. Everything is scoped by `tenant_id`/`school_id`.
- `teachers` — authoritative professional profile, keyed by `school_id`. ⚠️ A school teacher exists in **both** `users` (login/tenant) **and** `teachers` (drives the Teachers page/academics); admin flows must reconcile both (memory `teacher-users-and-teachers-tables`).
- `students`, `parents`, `guardian_links` — family graph. Parent↔student linkage must use **canonical tenant-safe identifiers** (guardian links), not mutable contact fields. Relationship/email are canonical **only in `guardian_links`** for real schools (memory `real-school-guardian-linking`).
- `classes`, `subjects` — academic structure. Canonical **3-stage / 12-grade** system; `subjects` table is canonical for CRUD/assignment/generation (memory `canonical-grade-system`, `subject-source-of-truth`).
- `timetables`, `time_slots`, `schedule_sessions` — scheduling (see §9).
- `attendance`, `assessments`/grades, `notifications`, `impersonation_sessions`, `revoked_tokens`, `workspace_collaborators`, `ai_insights`, `generic_documents`.

### 7.3 Relational tables vs GenericDocument
There is a **`generic_documents`** table (`collection` string + `data` JSONB) with Mongo-like helpers `gd_find` / `gd_create` in `backend/engines/sql_utils.py`. **`gd_find` is "smart":** `_get_orm_model(collection)` maps known collection names to real ORM classes; if a match exists it transparently queries that **real table** with the same filter dict, otherwise it falls back to `generic_documents`. The historical pattern is: prototype in `generic_documents`, then **promote** to a real table once the schema stabilizes (e.g. `events`, `system_settings`). ⚠️ Consequence: a given "collection" may be a real table **or** a JSONB document set, and you cannot tell from the call site — always go through the helpers and check `_get_orm_model`'s mapping; never assume either backing exists (memory `schedule-storage-engine`). Concretely, `timetables` and `schedule_sessions` **are** real ORM tables (mapped in `_get_orm_model`), while `timetable_sessions` is **not** mapped and lives as a GenericDocument collection.

> N+1 caution (`replit.md`): use bulk `gd_find` with `$in` for related fetches.

### 7.4 Schema discipline (hard rules)
- **Alembic only.** No `Base.metadata.create_all()`/`drop_all()` outside dev.
- **Schema-drift test:** `backend/tests/test_schema_orm_drift.py` (Alembic `compare_metadata`) fails when ORM and live DB diverge (allowlist for intentional cases).
- **Destructive-migration guard:** `backend/tests/test_migration_destructive_ops_guard.py` fails on `drop_table`/`drop_column`/raw `DROP/TRUNCATE/DELETE` unless the revision id is added to `ALLOWED_DESTRUCTIVE` with a sign-off reason (take a `pg_dump` first — `docs/runbooks/database-backup-restore.md`).
- **Production data must never be lost/overwritten/replaced** during deploy (`DEPLOYMENT_SAFETY.md`, status: "PERMANENT & NON-NEGOTIABLE").

---

## 8. Authentication, Authorization & Tenancy

### 8.1 Login / session model
- **JWT bearer** access + refresh tokens. `get_current_user` (`backend/dependencies.py`) decodes, checks the `revoked_tokens` blacklist, and rejects tokens whose `iat < users.last_password_change` (a defense-in-depth "kill all old sessions on password change").
- **Refresh rotation with theft detection:** refresh tokens carry a **family id (`fid`)** + **JTI**. Rotation mints a new family member; **replaying a consumed JTI revokes the entire family** (`backend/routes/auth_routes_mod.py`, `backend/utils/tokens.py`).
- Passwords hashed with **bcrypt**.

### 8.2 MFA
- Enrollment is gated in `get_current_user` (users without MFA can be forced into enrollment). There is a platform kill-switch: `MFA_ENFORCEMENT_DISABLED` suppresses both the login gate and the FE enroll redirect via the `/auth/me` `mfa_enforcement_disabled` flag (memory `mfa-kill-switch-wiring`). **It is currently `true` in the shared userenv** (see §13).
- **Step-up:** `require_recent_mfa_403(max_age)` raises a **403** step-up envelope; the FE interceptor verifies a passkey and replays. On **shared** routes that IT can reach, use `require_recent_mfa_403_if_independent_teacher()`. Bare `require_recent_mfa` (401) on shared routes is **forbidden** — its 401 is treated as a hard logout by the FE (`replit.md` IT §5.7).
- MFA encryption uses a Fernet key in `MFA_ENCRYPTION_KEY`.

### 8.3 Role switching & impersonation
- Multi-role users switch among `additional_roles`; platform admins can **preview/impersonate** schools.
- Switched sessions are **capped at ~15 min TTL** and recorded in **`impersonation_sessions`** (`original_user_id`, `target_role`, `reason`, `ip_address`). `/return-to-original` restores the primary role and revokes the impersonation JTI.
- `X-School-Context` header overrides are treated as impersonation-equivalent (same MFA/audit/expiry requirements).

### 8.4 RBAC model
- **Source of truth:** `backend/middleware/rbac.py` `ROLE_PERMISSIONS: Dict[str, List[str]]` mapping each role to granular permissions (e.g. `users.view`, `schedule.publish`, `WORKSPACE_EXPORT`, `AUDIT_READ_OWN_WORKSPACE`).
- **Deny-by-default**: unauthenticated access is limited to `/public/*`, health, and specific registration options; `require_full_school_tenant` blocks IT from enterprise routes; `STUDENT_LOGIN_DISABLED` blocks the student role platform-wide.

### 8.5 Tenancy (the most critical correctness property)
- **Resolution source of truth:** `backend/auth_scope.py::require_request_school_id(current_user)`, resolving in order: `current_user["tenant_id"]` → `current_user["school_id"]` → synthetic **`itw_{user_id}`** for `independent_teacher`. **Fail-closed** (403) if none resolve.
- **Isolation enforcement is explicit, not automatic.** There is **no** global query-rewriting middleware. Each route is responsible for passing the resolved tenant predicate into its queries; the by-id read helpers in `backend/utils/tenant_scope.py` enforce the cross-workspace 404; `collab_access.py` is the only sanctioned widening. `backend/middleware/tenant_isolation.py` provides helper utilities (`TENANT_SCOPED_COLLECTIONS`, `warn_missing_tenant_filter`) to *detect* developer error — it does **not** silently inject filters into `gd_find`. Treat a missing tenant predicate as a latent cross-tenant disclosure bug.
- **Workspace materialization:** `require_workspace_materialised` — an IT user cannot hit non-allowlisted APIs until their workspace `tenant_id` is set (`PerimeterGateBridge` mirrors this on the FE).
- **IT discriminator:** real-vs-IT is `tenant_type`/`school_type == 'independent_teacher'` (NOT a column called `entity_kind`, which is computed) — memory `it-workspace-db-discriminator`.

### 8.6 High-risk areas where an isolation bug is critical
Per `threat_model.md` (confirmed weak spots — revisit these first on any security pass):
- Raw `X-School-Context` / request-param / body **tenant overrides**.
- Legacy academic-structure / teacher-management / subject routes that trust caller-supplied `school_id`.
- Unified reporting/export endpoints allowing teacher overreach.
- IT **public token-redemption** flows (parent-invitation accept rebinding to a foreign `parents` row via `national_id`; workspace export download accepting stale/reactivated bearer tokens).
- Cross-workspace roster serializers (accepted collaborator pulling full `StudentResponse` PII).
- CSV/XLSX export writers without formula neutralization.
- Parent/guardian authorization honoring stale `parents.student_ids` / inactive `guardian_links`; relationship-graph endpoints pivoting to siblings.
- Platform-admin & lower-tier admin **credential-minting / password-reset / unlock** paths that skip fresh-MFA or session revocation.

---

## 9. Scheduling / Timetable Architecture

This is the product's flagship and most intricate subsystem.

### 9.1 Storage (two models)
- **Real schools:** the `timetables` **ORM table** holds metadata (version, status `draft`/`published`); the actual class/teacher/subject/day/period tuples are read via the `timetable_sessions` **GenericDocument collection** (not a mapped table). Resolve through `_resolve_teacher_sessions` / engine helpers, never inline. Legacy `schedules` collection is empty (memory `schedule-storage-engine`).
- **Independent Teachers:** a **manual editor** writing directly to the `schedule_sessions` **ORM table** (which carries the `version` OCC column).

### 9.2 Generation pipeline (real schools)
`backend/engines/smart_scheduling_engine.py`:
1. **Data-readiness pre-validation** (`validate_data_readiness`, INF-01..INF-05).
2. **Context assembly** (`_assemble_hakim_context_payload`: timings, classes, assignments, constraints).
3. **Infeasibility report** (`build_infeasibility_report`) — blocks generation on critical gaps (e.g. no working days).
4. **Generation** — demand matrix → availability trimming → placement loop.
5. **Conflict detection** — `teacher_overlap`, `class_overlap`, etc.

The standby/substitution engine excludes teachers whose `teachers.weekly_periods` is null/≤0 **by design** (empty "حصص الانتظار" is a config issue, not a bug — memory `standby-weekly-periods-prereq`). Teacher class-membership is spread across **three overlapping tables** (`teacher_assignments` authoritative, `teacher_class_assignments` convenience, `schedule_sessions` grid) — reconcile additively (memory `teacher-class-membership-source`).

### 9.3 Optimistic concurrency (IT manual editor)
`schedule_sessions.version` is a monotonically increasing OCC token (migration `a2b3c4d5e6f7`). `PUT /independent-teacher/schedule/slot` must send `expected_version`; a mismatch returns **409** with the current row (`_conflict_response`). Concurrent inserts on the same natural key are serialized with `pg_advisory_xact_lock`. **Real-school write paths ignore `version`.**

### 9.4 Frontend
`frontend/src/pages/SchedulePageNew.jsx` is the master grid (workspace redesign 2026-05-06: sticky band, chip-collapsed alerts/insights, **no pagination**; window size `MASTER_GRID_TEACHER_WINDOW = 200` in `frontend/src/config/scheduleConfig.js`). Day colors in `components/schedule/grid-theme/dayPalette.js`. Teacher timetable period labels derive from the contiguous post-break-filter row index (not `slot_number`/`slot.name`) — memory `teacher-timetable-period-labels`.

> **Hard product rule (`replit.md`):** do **not** re-introduce the old scheduling system.

---

## 10. Independent-Teacher (IT) Workspace Model

A second, lighter tenancy model living alongside full schools. **Read `docs/it-phase2-reference.md` before touching any IT code** — it documents every IT route/table (§5.6, §5.7, §5.9, §6.1–§6.8, §8 inv. 3). Spec: `docs/specs/2026-05-12-independent-teacher-phased-spec.md`.

- **Identity:** synthetic `itw_{user_id}`; discriminator `tenant_type/school_type == 'independent_teacher'`.
- **Routers:** the `independent_teacher_*` family (bulk import, parent invitations, calendar, lesson plans, collab/co-teaching, notifications, reports, analytics, schedule, search, workspace lifecycle/settings/excel-export). Mounted **without** the global tenant dependency; they self-bind via `auth_scope`.
- **Lifecycle (§6.8):** export → soft-delete → reactivate (≤30d) → platform-admin **hard-delete** (out-of-band only; never reachable from the IT API). Soft-delete requires an export within 24h; export tokens are single-use. Purge: `backend/routes/platform_workspace_purge_routes.py`.
- **Quotas:** `workspace_quota` caps students/classes/daily imports/lesson plans.
- **Cross-workspace co-teaching (§6.7):** `workspace_collaborators` is the **only** sanctioned cross-tenant data path; widening happens at the call-site via `backend/utils/collab_access.py` (`caller_can_access_class`) for the named `class_id` only — **never broaden `TenantIsolation`** for this.
- **§8 by-id 404 invariant (inv. 3):** every IT-reachable by-id read must **404** (never 403/200) for cross-workspace lookups, so the API never confirms the existence of foreign-tenant rows (`backend/utils/tenant_scope.py::tenant_scoped_find_one`).
- **IT tab gating:** always-entitled IT tabs (lesson-planner/import) gate on **role**, not on a lazy `/auth/me/permissions` fetch (which can false-negative on slow/failed loads) — memory `it-tab-role-gating`.

---

## 11. Important Technical Decisions (do not revert without sign-off)

1. **Multi-tenancy enforced at the DB query level** (`tenant_id` aliased as `school_id`), deny-by-default. Tenant resolution is centralized in `auth_scope.py`.
2. **API schema as a contract:** `shared_models.py` (Pydantic) is the single source of truth for request/response shapes.
3. **Alembic-only schema management**; destructive ops blocked outside development; migrations applied **once per release** in `build.sh` build phase (not in the autoscale run command, to avoid multi-worker races), backed by a **startup head-gate**.
4. **Frontend stays on CRA + CRACO** with `webpack-dev-server` pinned to an exact v5 and a shim translating CRA's v4 config (`frontend/craco.config.js`). Rationale + safe-upgrade procedure: `docs/frontend-toolchain.md`. Covered by `frontend/src/__tests__/cracoDevServer.test.js`. **Do not loosen the exact pin; do not migrate to Vite without revisiting the documented tradeoffs.**
5. **Unified Approval Engine** — one generic state machine for many request types.
6. **Standardized alerting** — `NassaqAlertDialog` everywhere.
7. **MFA step-up is a 403 envelope on IT/shared surfaces** so the FE can replay (401 = hard logout). Use the IT-aware helpers.
8. **IT cross-tenant only via `workspace_collaborators`**, widened at the call-site, with the by-id 404 invariant.
9. **Export formula-injection neutralization** in every CSV/XLSX writer (shared `export_engine.py` and IT analytics route each have their own writer — keep them in sync): escape leading `= + - @ \t \r`; set `strings_to_formulas=False`, `strings_to_urls=False` (memory `export-formula-injection`).
10. **gpt-5-mini runtime contract:** it is a reasoning model — token budgets ≤1024 can return **empty**; open-ended calls need ≥2048; every OpenAI client must pass the gateway `base_url` or you get 401 (memory `gpt5-mini-runtime-contract`).
11. **Same-origin serving** → frontend uses relative API URLs (`|| ''`).

**Hard "do not break" list (`replit.md` user preferences):** don't reintroduce the old scheduler; new fixes must not break working flows; no changes to stable logic unless strictly necessary; no native `alert/confirm/toast.error` for important warnings; no `Intl` Hijri; no broad CSP `unsafe-eval`/wildcards without security review; safe Arabic API errors only; no `console.log` in pages/contexts; no hardcoded secrets.

---

## 12. Known Risks, Tech Debt & Caveats

**Security-sensitive (from `threat_model.md`, treat as the priority backlog):** see §8.6. The threat model explicitly tracks "confirmed weak spots" dated 2026-05-14 → 2026-05-20; these are the legacy/alternate paths most likely to harbor tenant/role bugs (alternate tenant-context paths, alternate role-switch paths, legacy factory routes, privacy-workflow endpoints, parent-linkage fallbacks, guardian-permission enforcement points, credential-minting surfaces, AI-backed parent/Hakim endpoints, legacy by-id school update routes, teacher self-linking fallbacks, password-reset/session-revocation joins).

**Architectural / structural debt**
- **Dual route styles** (`*_mod.py` vs legacy factory `*.py`) — 89 modules; legacy ones are the higher-risk authz surfaces.
- **Dual Pydantic locations** (`shared_models.py` vs `backend/models/`) — finish consolidating onto `shared_models.py`.
- **GenericDocument vs real tables** — "collections" may or may not be real tables; the smart `gd_find` indirection is powerful but easy to misuse (assume nothing; use helpers; bump cache keys when response shapes change).
- **Three overlapping teacher-class-membership tables** — reconcile additively; easy to under-count "My Classes".
- **Subjects "periods" field-name triple** — `default_periods_per_week` (column) / `weekly_periods` (response) / `weekly_hours` (generic-mutate wire); only update when a value is explicitly provided or edits clobber it (memory `subjects-periods-field-names`).
- `backend/ARCHITECTURE.md` is partly **dated** (describes the older `models/` + `services/` layout); trust live code + `replit.md` first.

**Performance hotspots** — N+1 risk in related-entity fetches (use bulk `$in`); the master schedule grid renders a 200-teacher window with no pagination; AI calls are latency-bound (cached where possible). See `docs/PERFORMANCE_AUDIT_REPORT.md`.

**AI abuse surface** — `/api/hakim/chat` and parent-portal insights make live LLM calls; rate limits exist (`rate_limiter.py`, `public_hakim_limiter.py`) and parent insights are cached per-child/day in `ai_insights`, but the threat model still flags broad authenticated AI endpoints as an abuse vector to keep watching.

**Operational caveat (highest-leverage to internalize)** — the dev backend runs as production against the prod DB (§13).

---

## 13. Operational / Environment Notes

### 13.1 Run / build / test
- **Run (dev workflows, `.replit`):** `Backend API` → `cd backend && uvicorn server:app --host 0.0.0.0 --port 8000`; `Frontend Dev` → `cd frontend && PORT=5000 BROWSER=none npx craco start`. The combined `Project` workflow runs both.
- **Build (deploy):** `build.sh` — create venv, `pip install`, **`alembic upgrade head` (once)**, `craco build`, then prune (`frontend/node_modules`, `frontend/src`, `attached_assets`, caches) to shrink the image. Fails the release if `build/index.html` is missing.
- **Deploy target:** **autoscale**; run command activates `.venv` and serves `uvicorn server:app` on `$PORT`.
- **Typecheck:** `mypy backend/`, `npm run typecheck` (frontend). **Migrations:** `alembic revision --autogenerate -m "..."`, `alembic upgrade head`. **Drift/destructive guards:** the two pytest files in §7.4.

### 13.2 Environment variables (required)
`DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `MFA_ENCRYPTION_KEY` (Fernet). AI: `AI_INTEGRATIONS_OPENAI_BASE_URL`, `AI_INTEGRATIONS_OPENAI_API_KEY`. Plus `ENVIRONMENT`, `CORS_ORIGINS`, `FRONTEND_URL`, `MFA_ENFORCEMENT_DISABLED`. **Manage all secrets via Replit secrets — never hardcode.**

### 13.3 ⚠️ The two biggest operational traps
1. **The dev `Backend API` workflow runs with `ENVIRONMENT=production` (set in `.replit` `[userenv.shared]`) and points at the real production database, with the startup schema head-gate active.** Practically: (a) treat the dev backend as production — destructive ops are blocked, seeds are skipped; (b) **any new Alembic head must be applied (dry-run first) or the backend refuses to boot**; (c) be careful with data. (memory `dev-workflow-runs-as-production`.)
2. **`MFA_ENFORCEMENT_DISABLED=true`** is currently set in the shared userenv — MFA looks optional because of this flag, not because the backend gate is gone. Flip with care (memory `mfa-kill-switch-wiring`).

> At the time of writing, the `Backend API` workflow shows as failed in the editor; the usual cause is a leftover stray `uvicorn ...:8000` from a previous session holding the port (the app itself boots in ~2s) — kill stray uvicorn procs before restarting (memory `backend-restart-stray-uvicorn`). A failed schema head-gate is the other candidate.

### 13.4 Deployment safety (permanent rules — `DEPLOYMENT_SAFETY.md`)
- Production data must never be lost/overwritten/replaced.
- Seeds **BLOCKED** in staging/production (and skipped if the DB already has data); destructive ops **BLOCKED** outside development (`config.seed_allowed()`, `config.destructive_ops_allowed()`, `config.deployment_checklist()`).
- Schema via Alembic only; no `create_all`/`drop_all`.

### 13.5 Post-merge reconciliation
`.replit` `[postMerge]` runs `scripts/post-merge.sh` (120s timeout) after task-agent merges — typically dependency install + migration apply. If a merge's reconciliation fails, fix it on the main app (see the `post_merge_setup` skill).

### 13.6 QA credentials
`TEST_CREDENTIALS.md` holds principal/teacher/parent test logins for QA only. **Reference by filename only** — never paste actual credentials into source, logs, commits, screenshots, or docs.

---

## 14. Testing & Quality

- **214 backend test files.** Strongest coverage is **structural/safety**: schema-drift (`test_schema_orm_drift.py`), destructive-migration guard (`test_migration_destructive_ops_guard.py`), and **Independent-Teacher invariants** (`test_independent_teacher_*` — `itw_{user_id}` pinning, cross-workspace 404, MFA step-up on write/export). IT Phase-1 exit criteria are documented in `docs/qa/2026-05-12-it-phase1-exit-criteria.md`.
- **Lightly covered:** full cross-role E2E flows (student → parent → teacher) and complex frontend application logic. Frontend tests center on the toolchain (`cracoDevServer.test.js`) plus some component tests.
- **Regression tests that matter most:** (1) tenant-isolation / by-id 404 invariants, (2) the two schema guards before any migration, (3) MFA step-up envelope status codes, (4) export formula-injection neutralization, (5) the CRACO dev-server shim before bumping `webpack-dev-server`.
- Note: the agent-driven `runTest` harness is disabled this session; verify manually using `TEST_CREDENTIALS.md` roles.

---

## 15. Recommended Reading Order for the Next Team

**Tier 1 — orientation & guardrails (read fully, first):**
1. `replit.md` — overview, run/build, architecture decisions, **user preferences/guardrails**.
2. `threat_model.md` — assets, trust boundaries, **confirmed weak spots**.
3. `backend/DEPLOYMENT_SAFETY.md` + `.replit` + `build.sh` — what runs where, and the prod-DB-in-dev trap.

**Tier 2 — backend spine:**
4. `backend/server.py` → `backend/app/middleware.py` → `backend/app/lifecycle.py` → `backend/app/routes.py`.
5. `backend/dependencies.py` (auth gates, MFA, engine singletons).
6. `backend/auth_scope.py` + `backend/middleware/tenant_isolation.py` + `backend/middleware/rbac.py` (tenancy + RBAC).
7. `backend/pg_models.py` + `backend/shared_models.py` + `backend/engines/sql_utils.py` (data model + GenericDocument).

**Tier 3 — frontend spine:**
8. `frontend/src/App.js` → `frontend/src/routes/appRoutes.js` → `frontend/src/components/guards/RouteGuards.js`.
9. `frontend/src/contexts/AuthContext.js` (interceptors, MFA replay, X-School-Context) + `frontend/src/services/apiClient.js`.

**Tier 4 — the deep/risky subsystems:**
10. `docs/it-phase2-reference.md` + `docs/specs/2026-05-12-independent-teacher-phased-spec.md` + the `independent_teacher_*` routers.
11. `backend/engines/smart_scheduling_engine.py` + `frontend/src/pages/SchedulePageNew.jsx`.
12. `backend/services/hakim_llm_service.py` + `backend/routes/ai_routes_mod.py`.
13. `backend/engines/export_engine.py` + `backend/engines/noor_import/`.

**Tier 5 — context/history:** `docs/audits/*`, `docs/security/*` (SECURITY_AUDIT_2026-05-11, PHASE1-3 reports, HAKIM_DPIA), `docs/qa/*`, `docs/superpowers/specs/*`, `docs/frontend-toolchain.md`, `docs/runbooks/database-backup-restore.md`.

---

## 16. Suggested First Priorities for the Incoming Team

**Verify first (smoke):**
1. Confirm dev vs prod posture — understand that the dev backend hits the prod DB; set up a safe way to test (and confirm seeds/destructive ops are blocked).
2. Boot the backend cleanly (resolve the failing `Backend API` workflow — likely stray uvicorn or an unapplied migration head). Confirm `alembic upgrade head` is clean and the schema-drift + destructive-guard tests pass.
3. Run the IT invariant tests and the CRACO dev-server test green.

**Stabilize first (risk reduction):**
4. Work the `threat_model.md` "confirmed weak spots" as a security backlog — especially alternate tenant-context paths (`X-School-Context`, caller-supplied `school_id`), IT public token-redemption flows, cross-workspace roster serializers, credential-minting/password-reset/session-revocation paths.
5. Audit legacy factory routes (`*.py`) for tenant binding and authz parity with the `*_mod.py` consolidations.
6. Verify export writers (shared + IT) both neutralize formula injection and stay in sync.

**Highest leverage (product/technical):**
7. Finish consolidations: legacy `models/` → `shared_models.py`; legacy factory routes → `*_mod.py`; promote stable `generic_documents` collections to real tables.
8. Add cross-role E2E coverage (student↔parent↔teacher↔principal) to backstop the lighter integration layer.
9. Treat the IT workspace surface as the highest-churn area — keep `docs/it-phase2-reference.md` authoritative and updated alongside code.

---

## 17. Constraints / Guardrails (non-negotiable)

- **Backend is the authority.** Frontend route guards and token claims are UX/requests, never the security boundary.
- **Tenant isolation is sacred** — deny-by-default, DB-level scoping, fail-closed resolution, by-id 404 for cross-workspace reads. Never widen `TenantIsolation` for co-teaching (widen at the call-site only).
- **Schema only via Alembic**; no `create_all`/`drop_all`; destructive ops blocked outside dev and gated by the destructive-migration guard + allowlist.
- **Production data is never lost/overwritten**; seeds/destructive ops blocked in staging/prod.
- **Arabic-safe errors only**; never leak `str(e)`.
- **`NassaqAlertDialog`** for all warnings/errors/confirms; no native `alert/confirm/toast.error`.
- **Do not reintroduce the old scheduler**; do not migrate off CRA/CRACO or loosen the `webpack-dev-server` pin without revisiting `docs/frontend-toolchain.md`.
- **MFA step-up = 403 envelope** on IT/shared routes (401 = hard logout).
- **Secrets via Replit secrets only**; `TEST_CREDENTIALS.md` referenced by filename only.
- **No `console.log`** in pages/contexts; no raw hex/text-gradients/emoji-icons in JSX; RTL via logical properties; Hijri via `hijri-converter` (never `Intl`).

---

## Appendix A — Files & documents inspected for this report

**Config / ops:** `replit.md`, `threat_model.md`, `.replit`, `build.sh`, `main.py`, `frontend/package.json`, `backend/DEPLOYMENT_SAFETY.md`, `backend/ARCHITECTURE.md`.
**Backend (read or grepped):** `backend/server.py`, `backend/dependencies.py`, `backend/shared_models.py`, `backend/pg_models.py`, `backend/auth_scope.py`, `backend/db.py`, `backend/app/{middleware,lifecycle,routes,integrity_messages}.py`, `backend/middleware/{rbac,tenant_isolation,rate_limiter,error_handler,request_tracing,audit_middleware}.py`, `backend/engines/*` (incl. `smart_scheduling_engine.py`, `sql_utils.py`, `export_engine.py`, `noor_import/*`, `hakim_ai_engine.py`, `session_engine.py`, `audit_engine.py`), `backend/services/hakim_llm_service.py`, `backend/routes/*` (89 modules — auth, user_roles, ai_routes_mod, parent_portal, independent_teacher_*, platform_workspace_purge, academics_*, attendance_*, reporting_*, etc.), `backend/utils/{collab_access,tenant_scope,tokens,public_hakim_limiter}.py`, `backend/tests/*` (schema drift, destructive guard, IT exit/invariants).
**Frontend:** `frontend/src/App.js`, `routes/appRoutes.js`, `components/guards/RouteGuards.js`, `contexts/{AuthContext.js,ThemeContext.js,WebSocketContext.jsx}`, `services/apiClient.js`, `components/ui/NassaqAlertDialog.jsx`, `components/PerimeterGateBridge.jsx`, `pages/SchedulePageNew.jsx`, `config/scheduleConfig.js`, `craco.config.js`, `src/__tests__/cracoDevServer.test.js`, `locales/{ar,en}.json`.
**Docs:** the full `docs/` tree was enumerated; key reads: `docs/it-phase2-reference.md`, `docs/specs/2026-05-12-independent-teacher-phased-spec.md`, `docs/security/*`, `docs/qa/*`, `docs/audits/*`, `docs/frontend-toolchain.md`, `docs/runbooks/database-backup-restore.md`, `docs/superpowers/specs/2026-05-03-hakeem-engine-audit-report.md`.

Counts verified live: 89 route modules, ~40 engines, 75 Alembic migrations, 214 backend test files, 150 frontend pages, ~200k LOC backend / ~152k LOC frontend.

## Appendix B — Source-of-truth quick map

| Concern | Source of truth |
|---|---|
| App entry / wiring | `backend/server.py` (`create_app`) |
| API schema contract | `backend/shared_models.py` (Pydantic) |
| DB schema | `backend/pg_models.py` (ORM) + `backend/alembic/versions/` |
| Tenant resolution | `backend/auth_scope.py::require_request_school_id` |
| Tenant isolation enforcement | **Explicit per-route** + `backend/utils/tenant_scope.py` (by-id 404) + `backend/utils/collab_access.py` (co-teaching widening). `backend/middleware/tenant_isolation.py` is a detection helper, not global enforcement. |
| Permissions / RBAC | `backend/middleware/rbac.py` (`ROLE_PERMISSIONS`) |
| Auth gates / MFA / engine DI | `backend/dependencies.py` |
| Token lifecycle | `backend/routes/auth_routes_mod.py` + `backend/utils/tokens.py` |
| Scheduling (schools) | `backend/engines/smart_scheduling_engine.py` |
| Scheduling (IT manual) | `schedule_sessions` table + `backend/routes/independent_teacher_schedule_routes.py` |
| GenericDocument access | `backend/engines/sql_utils.py` (`gd_find`/`gd_create`) |
| AI / Hakim | `backend/services/hakim_llm_service.py` + `backend/routes/ai_routes_mod.py` |
| Exports | `backend/engines/export_engine.py` (+ IT analytics writer) |
| Frontend routing/guards | `frontend/src/routes/appRoutes.js` + `components/guards/RouteGuards.js` |
| Frontend auth/interceptors | `frontend/src/contexts/AuthContext.js` |
| Deploy build / migrations | `build.sh` (+ startup head-gate in `backend/db.py`) |
| Operational config | `.replit` |

---

*End of handover report.*
