# Threat Model

## Project Overview

NASSAQ is a multi-tenant school management platform with a React frontend and a FastAPI backend backed by PostgreSQL/SQLAlchemy. Production users include platform admins, school admins/principals, teachers, students, and parents. The main production risk is unauthorized cross-tenant or cross-role access to school data, student/parent PII, grades, attendance, schedules, notifications, and admin functions.

This threat model assumes production runs behind Replit-managed TLS, `NODE_ENV=production`, and that mockup/sandbox artifacts are not production-reachable unless proven otherwise.

## Assets

- **User accounts and session material** — bcrypt password hashes, JWT access tokens, refresh tokens, password-reset tokens, role-switch tokens. Compromise enables impersonation and privilege abuse.
- **School-scoped academic data** — student records, grades, attendance, schedules, behavior notes, parent communications, and teacher data. This is sensitive student/family information and must remain correctly scoped by tenant and role.
- **Parent/student relationship data** — `parents`, `students`, `guardian_links`, and derived portal/dashboard views. Incorrect linkage can expose one family’s data to another or cross school boundaries.
- **Administrative and platform data** — school metadata, monitoring/operational metrics, audit trails, and security settings. Exposure helps attackers enumerate tenants, users, or system state.
- **Application secrets and integrations** — database credentials, JWT signing key, email credentials, AI/API keys. Leakage would enable full compromise or secondary abuse.

## Trust Boundaries

- **Browser / API** — all frontend input is untrusted. Backend routes must enforce authn, authz, validation, and tenant scoping server-side.
- **API / Database** — the FastAPI backend has broad data access. Any broken authorization or unscoped query can expose cross-tenant data.
- **Public / Authenticated / Privileged API** — public/auth routes (`/auth/*`, public routes, WebSockets, monitoring endpoints) must be separated from authenticated school-role and platform-admin functionality.
- **School tenant / platform tenant** — platform users may traverse schools intentionally, but ordinary school-scoped roles must never widen tenant scope through request params, headers, or stale role-switch tokens.
- **HTTP / WebSocket** — WebSocket auth must uphold the same guarantees as HTTP APIs, including token validity, revocation, and user-state enforcement.
- **Production / dev-only code** — scripts, seeders, mockups, and tests are out of scope unless production reachability is shown.

## Scan Anchors

- **Production entry points:** `backend/server.py`, `backend/app/routes.py`, `backend/app/middleware.py`, `frontend/src/App.js`, `frontend/src/services/apiClient.js`.
- **Highest-risk code areas:** `backend/routes/auth_routes_mod.py`, `backend/dependencies.py`, `backend/routes/role_dashboards_mod.py`, `backend/routes/parent_portal_routes.py`, `backend/routes/websocket_routes.py`, `backend/routes/monitoring_routes.py`, tenant/auth helpers in `backend/middleware/` and `backend/auth_scope.py`.
- **Additional scan anchors from 2026-05-14:** `backend/routes/academics_student_routes.py`, `backend/routes/attendance_routes.py`, `backend/routes/reporting_routes_mod.py`, `backend/routes/independent_teacher_invite_parent_routes.py`, `backend/routes/independent_teacher_invitation_routes.py`, and `backend/engines/session_engine.py`.
- **Surface split:** public/auth routes, authenticated school-role routes, platform-admin routes, and WebSockets.
- **Usually ignore unless proven reachable:** `backend/scripts/`, test files, migrations, and mockup/sandbox artifacts.

## Threat Categories

### Spoofing

The application relies on JWT bearer tokens, refresh rotation, password-reset tokens, and role-switch/impersonation claims. The system must reject forged, expired, revoked, locked-account, and otherwise invalid tokens on every HTTP and WebSocket surface. Password-reset and login flows must resist brute force and account-state bypasses.

### Tampering

Clients can submit profile updates, attendance changes, grades, messages, uploads, and scheduling inputs. The backend must validate all user-controlled fields and must never trust client-supplied role, tenant, user, or relationship identifiers without server-side checks. Role-switching and school-context resolution must fail closed.

### Information Disclosure

This platform stores sensitive student and family data. All dashboard, portal, notification, reporting, and search endpoints must scope responses by both role and tenant. Parent-child linkage must be based on canonical, tenant-safe identifiers rather than mutable contact fields, and student-by-id read surfaces must verify the viewer's relationship to the target object instead of trusting same-tenant presence alone. Public monitoring, debug, or stats endpoints must not leak internal operational details that help attackers map the service or target high-value users.

### Denial of Service

Public and auth endpoints can be abused for brute force, scraping, or expensive operations. Production-facing login, reset, upload, export, AI, and WebSocket entry points must have effective abuse controls that still hold behind proxies and across worker/process boundaries.

### Elevation of Privilege

The largest project-specific risk is broken access control in multi-role and multi-tenant flows: IDORs in dashboards/portals, unscoped relationship lookups, cross-tenant context switching, and WebSocket/impersonation behavior that does not match HTTP authorization rules. The system must enforce least privilege on every route regardless of what the frontend shows or what token claims request.
