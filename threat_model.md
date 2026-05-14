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
- **Public / Authenticated / Privileged API** — public/auth routes (`/auth/*`, registration helpers, WebSockets, monitoring endpoints) must be separated from authenticated school-role and platform-admin functionality.
- **School tenant / platform tenant** — platform users may traverse schools intentionally, but ordinary school-scoped roles must never widen tenant scope through request params, headers, or stale role-switch tokens.
- **HTTP / WebSocket** — WebSocket auth must uphold the same guarantees as HTTP APIs, including token validity, revocation, and user-state enforcement.
- **Production / dev-only code** — scripts, seeders, mockups, and tests are out of scope unless production reachability is shown.

## Scan Anchors

- **Production entry points:** `backend/server.py`, `backend/app/routes.py`, `backend/app/middleware.py`, `frontend/src/App.js`, `frontend/src/services/apiClient.js`.
- **Highest-risk code areas:** `backend/routes/auth_routes_mod.py`, `backend/dependencies.py`, `backend/routes/user_roles_routes.py`, `backend/routes/role_dashboards_mod.py`, `backend/routes/parent_portal_routes.py`, `backend/routes/websocket_routes.py`, `backend/routes/monitoring_routes.py`, `backend/routes/school_settings_mod.py`, tenant/auth helpers in `backend/middleware/` and `backend/auth_scope.py`.
- **Additional scan anchors from 2026-05-14 and 2026-05-14 follow-up:** `backend/routes/academics_student_routes.py`, `backend/routes/search_directory_routes_mod.py`, `backend/routes/attendance_routes.py`, `backend/routes/attendance_routes_mod.py`, `backend/routes/reporting_routes_mod.py`, `backend/routes/relationship_routes_mod.py`, `backend/routes/participation_routes_mod.py`, `backend/routes/consent_privacy_routes_mod.py`, `backend/routes/activities_routes_mod.py`, `backend/routes/registration_routes_mod.py`, `backend/routes/independent_teacher_invite_parent_routes.py`, `backend/routes/independent_teacher_invitation_routes.py`, `backend/routes/independent_teacher_workspace_lifecycle_routes.py`, `backend/routes/user_routes_mod.py`, `backend/routes/admin_routes_mod.py`, `backend/routes/audit_routes.py`, `backend/routes/communication_routes.py`, `backend/routes/academics_structure_engine_routes.py`, `backend/routes/academics_year_term_routes.py`, `backend/engines/audit_engine.py`, `backend/engines/session_engine.py`, and `backend/utils/tokens.py`.
- **Surface split:** public/auth routes, authenticated school-role routes, platform-admin routes, and WebSockets.
- **Usually ignore unless proven reachable:** `backend/scripts/`, test files, migrations, and mockup/sandbox artifacts.
- **Confirmed weak spots from 2026-05-14 full scan:** raw `X-School-Context` and request-parameter tenant overrides, legacy academic-structure routes that trust caller-supplied `school_id`, legacy reporting/export endpoints, `_mod` attendance routes, teacher-reachable directory/relationship/reporting/privacy surfaces, legacy communication read APIs, audit/admin telemetry routes, and switched/MFA session invalidation paths. Revisit these first on future scans and treat alternate tenant-context paths as privileged impersonation surfaces.

## Threat Categories

### Spoofing

The application relies on JWT bearer tokens, refresh rotation, password-reset tokens, and role-switch/impersonation claims. The system must reject forged, expired, revoked, locked-account, and otherwise invalid tokens on every HTTP and WebSocket surface. Password-reset and login flows must resist brute force and account-state bypasses. Any mechanism that rewrites tenant context for a privileged caller, including header-driven overrides such as `X-School-Context`, must be treated as equivalent to impersonation and carry the same MFA, audit, expiry, and server-side session guarantees as `/role-switch/switch`. Session revocation must invalidate both the access token and its refresh-token family, and switched/impersonation tokens must stop working immediately after the underlying role or tenant entitlement changes.

### Tampering

Clients can submit profile updates, attendance changes, grades, messages, uploads, and scheduling inputs. The backend must validate all user-controlled fields and must never trust client-supplied role, tenant, user, or relationship identifiers without server-side checks. Role-switching and school-context resolution must fail closed. Security telemetry is also integrity-sensitive: authenticated users must not be able to append arbitrary audit entries or security/MFA events into trusted logs or tamper-evident audit chains.

### Information Disclosure

This platform stores sensitive student and family data. All dashboard, portal, directory, relationship, consent, participation, reporting, search, attendance, and communication endpoints must scope responses by both role and tenant. Parent-child linkage must be based on canonical, tenant-safe identifiers rather than mutable contact fields, and student-by-id read surfaces must verify the viewer's relationship to the target object instead of trusting same-tenant presence alone. Relationship graph endpoints must re-authorize every adjacent student they disclose instead of pivoting from one allowed child to siblings or other family members. Privacy-export endpoints must never return raw account records or security secrets such as password hashes, reset-token material, lockout state, or MFA state fields. Public monitoring, debug, registration-helper, message-stats, or admin-telemetry endpoints must not leak internal operational details, tenant inventory, onboarding pipeline data, platform telemetry, or bearer-style export artifacts that help attackers map the service or exfiltrate another tenant's data.

### Denial of Service

Public and auth endpoints can be abused for brute force, scraping, or expensive operations. Production-facing login, reset, upload, export, AI, and WebSocket entry points must have effective abuse controls that still hold behind proxies and across worker/process boundaries.

### Elevation of Privilege

The largest project-specific risk is broken access control in multi-role and multi-tenant flows: IDORs in dashboards/portals, unscoped relationship lookups, arbitrary linked-role assignment, cross-tenant context switching, caller-supplied `school_id` parameters, legacy report/directory/attendance/communication endpoints that trust tenant membership alone, and WebSocket/impersonation behavior that does not match HTTP authorization rules. The system must enforce least privilege on every route regardless of what the frontend shows or what token claims request, and authorization-changing admin workflows must invalidate stale real-time and switched-session access promptly.
