# Role-Switch Audit — Scratch Notes (2026-05-25)

## Phase 1: Static map

### 1.1 Two parallel role-switch surfaces (DUAL-MODE STATE)
- **Legacy:** `POST /api/user-roles/switch` + `POST /api/user-roles/return-to-original` — mints new access token with `is_switched: True` claim, embeds `original_role` in JWT.
- **Hardened:** `POST /api/role-switch/switch` + `POST /api/role-switch/restore` — `is_impersonating: True` claim, server-side `impersonation_sessions` table holds `original_user_id`, requires `reason`.
- Both check `require_recent_mfa`; both revoke old JTI via `revoked_tokens` table on restore.
- WebSocket reconnects on token change (`WebSocketContext.jsx`).

### 1.2 FE entry point & state
- Entry: `SidebarContent.jsx:101-112` renders `RoleSwitcherDialog.jsx` for users with >1 role.
- AuthContext actions:
  - `switchRole` → legacy `POST /user-roles/switch`
  - `enterSchoolContext` → hardened `POST /role-switch/switch`; parks original token in `sessionStorage:nassaq_original_token`
  - `exitSchoolContext` → restores parked token from sessionStorage **WITHOUT SERVER ROUND-TRIP** (smell #1 — old impersonation token still valid on BE?)
  - `returnToOriginalRole` → legacy `POST /user-roles/return-to-original`; clears sessionStorage flags
- Persistence keys:
  - `localStorage:nassaq_token` (active JWT)
  - `sessionStorage:nassaq_school_context` (school_id + original_role + entered_at JSON)
  - `sessionStorage:nassaq_impersonating` = "true"
  - `sessionStorage:nassaq_original_token` (parked Platform Admin token)
- Banner: `PreviewModeBanner.jsx` visible when `isImpersonating` — Exit button calls `returnToOriginalRole`.

### 1.3 BE token & MFA helpers
- `dependencies.py:165` `create_access_token` embeds `mfa_recent_at`, `iat`.
- `dependencies.py:254` `create_refresh_token` — handles family on server side.
- MFA shim: `user_roles_routes.py:168` `_switch_mfa_dep` falls back to plain `get_current_user` if `require_recent_mfa` not importable (smell #2 — reachable in prod?).
- `X-School-Context`: `tenant_scope.py:412` rejects header unless `current_user.is_impersonating == True`.

### 1.4 Route + sidebar source-of-truth DIVERGENCE
- `ProtectedRoute` checks raw `user.role` from JWT.
- Sidebar uses `effectiveRole` (computed in `AuthContext:getEffectiveRole:925-930`).
- **Smell #3:** different predicates between guards and menu — menu may show or hide items inconsistent with actual route access during transitions.

### 1.5 Threat-model anchor confirmations
- "alternate self role-switch endpoints": `user_roles_routes.py:222-232` blocks PA cross-tenant legacy use, redirects to hardened.
- "legacy /return-to-original": still active at `user_roles_routes.py:375`; refuses restore if token has no JTI (line 419).
- "MFA session revocation / refresh family": handled in `dependencies.py:254` — needs live probe to confirm family really dies on switch.
- "X-School-Context raw header overrides": gated at `tenant_scope.py:412` — needs negative probe (non-impersonating caller).

## Phase 2: Role-switch matrix
(filled in next sub-task before live QA)

## Phase 3: Functional QA
## Phase 4: Security & permission probes
## Phase 5: Edge cases
## Phase 6: Code-quality observations
## Raw findings (promote to report in Phase 7)

## Phase 7 — Findings synthesis (2026-05-25)

### Confirmed live (with evidence)
- **H1**: 2× 500 in legacy switch routes — `linked_roles` shape mismatch (str vs dict). Files: auth_routes_mod.py:1141, 1579. Reproduced twice; stack traces in Backend_API_20260525_150846_842.log, _150940_540.log.
- **H2**: Impersonation JWT lives full 15-min TTL after FE `exitSchoolContext` (client-only). Direct curl after sessionStorage drop returns 200 on `/auth/me` with role=school_principal.
- **M1**: PA refresh-family produces parallel PA access token during impersonation (`/api/auth/refresh` returns role=platform_admin while SW token also alive).
- **M2**: Legacy `/user-roles/switch` audit row missing `severity` & `actor_role`. Confirmed via `GET /api/audit/logs?action=role_switch` (hardened row has both; legacy row is null on actor_role).

### Disconfirmed (initially flagged, withdrawn)
- L1 (audit-logs 404): wrong path — actual endpoint is `/api/audit/logs` (prefix `/audit`), works fine.

### Fixes applied this session
- H1: defensive `isinstance(x, dict)` filter in both alternate switch routes
- H2: `exitSchoolContext` now calls `/role-switch/restore` first; parked-token restore is fallback only
- M2: legacy audit row stamped with `severity: "high"` + `actor_role` + top-level `tenant_id`
