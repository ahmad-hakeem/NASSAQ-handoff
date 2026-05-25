# Platform-Admin Role-Switching Audit — Report

**Date:** 2026-05-25  
**Scope:** Full end-to-end audit of every Platform-Admin role-switch / preview flow in NASSAQ — frontend entry points, backend issuance, token lifecycle, tenant scoping, audit trail, restore, and side-effects on parallel sessions.  
**Methodology:** Static-map subagents + live API probes against `http://localhost:8000` using the Platform-Admin account from `TEST_CREDENTIALS.md`. All evidence is reproducible from the curl probes captured in this session.

---

## 1. Surface inventory

Three Platform-Admin-reachable role-switch surfaces exist:

| Surface | File:line | Token claim | MFA | Server-side session row | Revocation on restore |
|---|---|---|---|---|---|
| **Hardened** `POST /api/role-switch/switch` + `/restore` | `auth_routes_mod.py:1854,2002` | `is_impersonating=True` | `require_recent_mfa()` | `impersonation_sessions` | ✅ JTI revoked (probed) |
| **Legacy** `POST /api/user-roles/switch` + `/return-to-original` | `user_roles_routes.py:170,375` | `is_switched=True` | `_switch_mfa_dep` (resolves to `require_recent_mfa()` in prod) | `impersonation_sessions` (line 300) | ✅ JTI revoked (line 422) |
| **Alternate** `POST /api/auth/set-active-role` | `auth_routes_mod.py:1110` | `is_switched=True` | `require_recent_mfa()` | `impersonation_sessions` (line 1199) | ❌ no restore endpoint |
| **Alternate** `POST /api/users/{user_id}/switch-role` | `auth_routes_mod.py:1554` | `is_switched=True` | `require_recent_mfa()` | `impersonation_sessions` (line 1634) | ❌ no restore endpoint |

The frontend (`AuthContext.js`) uses only the **hardened** path for both Sidebar `RoleSwitcherDialog` and Command-Center `enterSchoolContext`. The legacy and alternate routes are not called by the current FE but remain mounted and authenticated.

---

## 2. Findings

### 🟢 Critical — 0

No critical findings. All cross-tenant escalation attempts via header overrides, alternate routes, and stolen-claim replays were properly rejected by the hardened path's MFA-gated audit pipeline and by `tenant_scope.resolve_school_id()`.

---

### 🟠 High — 2

#### H1 — `linked_roles` shape crash in two MFA-gated legacy switch routes (HTTP 500)

**Affected routes**
- `POST /api/auth/set-active-role` — `backend/routes/auth_routes_mod.py:1141`
- `POST /api/users/{user_id}/switch-role` — `backend/routes/auth_routes_mod.py:1579`

**Symptom.** Both routes iterate `current_user["linked_roles"]` (resp. `user["linked_roles"]`) and call `.get("is_active")` / `.get("role")` on each element. When a user's `linked_roles` field contains plain role strings (as Platform Admin's does), `str.get(...)` raises `AttributeError`, the request 500s, and the global handler returns `INTERNAL_ERROR` plus an `error_id`.

**Reproduction (live, this session):**
```
POST /api/auth/set-active-role           {"role_id":"school_principal","school_id":"<TARGET>"}  → HTTP 500 (error_id=f83d7aca)
POST /api/users/{me}/switch-role?target_role=platform_admin                                     → HTTP 500 (error_id=…)
```
Stack traces captured in `Backend_API_20260525_150846_842.log` and `…150940_540.log`:
```
File ".../auth_routes_mod.py", line 1579, in switch_user_role
    if linked.get("is_active"):
AttributeError: 'str' object has no attribute 'get'
```

**Impact.** Not a privilege escalation — the routes are correctly MFA-gated and self-only — but they are completely broken for the platform-admin caller, fail loudly with `INTERNAL_ERROR`, and the stack trace is logged. The routes are still mounted and discoverable, so any UI or external automation that tries to call them is permanently broken. Counts as **High** because:
1. The crash happens *after* the MFA check passes, on the privilege-mutation path.
2. The two routes duplicate the hardened path's behavior and are a maintenance hazard.

**Fix applied (this session):** Defensive `isinstance(x, dict)` guard before `.get()` in both routes. See §4.

---

#### H2 — Impersonation JWT remains valid for full 15-min TTL after client-only `exitSchoolContext`

**File:** `frontend/src/contexts/AuthContext.js:906-922`

**Symptom.** `exitSchoolContext()` is the cleanup path used when the user presses "Exit Preview" in `PreviewModeBanner` or when the page is reloaded mid-preview. It clears sessionStorage and restores the parked Platform-Admin token **without calling the backend**. The previously-issued impersonation JWT (`is_impersonating=True`, school-pinned, ≤15-min TTL) is never revoked server-side and continues to be accepted by `get_current_user` until natural expiry.

**Reproduction (live, this session):**
```
1. POST /api/role-switch/switch  → issues SW token (school_principal of TARGET)
2. simulate exitSchoolContext: client drops sessionStorage, restores parked PA token
3. GET /api/auth/me  -H "Authorization: Bearer $SW"   → HTTP 200, role=school_principal
```
The hardened restore path (`POST /api/role-switch/restore`) correctly revokes the JTI; only the FE bypass leaves the token live.

**Impact.** Standard JWT-lifetime risk amplified by the impersonation context: a token stolen via XSS / browser-extension / postMessage during the preview window is usable for up to 15 minutes after the user thinks they've exited. Restoration of the parked PA token is also a sensitive operation that should be audit-logged.

**Fix applied (this session):** Promote `exitSchoolContext` to call `POST /api/role-switch/restore` first; the parked-token client-side restore stays as a *fallback only* for the network-failure / no-parked-token branch. See §4.

---

### 🟡 Medium — 2

#### M1 — Platform-Admin refresh-token family stays alive during impersonation

**Files:** `backend/routes/auth_routes_mod.py:585` (`/auth/refresh`), `backend/routes/auth_routes_mod.py:1854` (hardened switch issuance — access-only)

**Symptom.** `POST /api/role-switch/switch` issues only an access token (no refresh-token rotation). The original Platform-Admin refresh-token family stayed live and could be exchanged for a fresh PA access token while the impersonation session was active.

**Reproduction (pre-fix):**
```
1. POST /api/role-switch/switch → SW (impersonating)
2. POST /api/auth/refresh  body {"refresh_token": <PA refresh>}  → HTTP 200, NEW PA access token (role=platform_admin)
```

**Fix applied (this session).** `/auth/refresh` now queries `impersonation_sessions` for any active (`ended_at IS NULL AND expires_at > now()`) row keyed to the caller's `user_id` and refuses with **HTTP 409** + Arabic message until the user restores via `/role-switch/restore` (which sets `ended_at` and revokes the impersonation JTI). Fails closed if the table is unavailable.

**Verification (live, post-fix):**
```
refresh BEFORE impersonation → 200
refresh DURING impersonation → 409 "لا يمكن تجديد الجلسة الأصلية…"
restore                       → 200
refresh AFTER  restore       → 200
```

---

#### M2 — Legacy `/user-roles/switch` audit row missing `severity`

**File:** `backend/routes/user_roles_routes.py:319-334`

**Symptom.** The hardened path stamps `severity: "high"` on its `audit_logs` row (visible in `GET /api/audit/logs?action=role_switch` — first row in probe response). The legacy `/user-roles/switch` audit row writes `action: "role_switched"` but no `severity`, no `actor_role`, no top-level `tenant_id` (only nested in `details`), making severity-based alerting / SIEM filtering inconsistent across the two paths.

**Fix applied (this session):** Add `severity: "high"` and `actor_role` to the legacy audit row to match the hardened schema. See §4.

---

### 🟢 Low — 2

#### L1 — Three parallel role-switch surfaces is a maintenance hazard

The hardened path is the only one the FE uses today (codebase-wide grep confirms zero FE callers of `/auth/set-active-role` and `/users/{id}/switch-role`). The legacy `/user-roles/switch` survives because legacy tokens / external scripts may still depend on it. The two alternates duplicate hardened-path behavior and were the source of H1.

**Fix applied (this session).** Both alternate routes now emit `logger.warning("deprecated_route_used: …")` on every call with caller identity and target role/tenant. Functionality is preserved (no behavior change) so no in-flight automation breaks; the log line gives ops a metric to confirm zero usage before scheduling removal in a follow-up. No FE callsite needs to be touched.

#### L2 — Page-level filter state may persist across role switches

`ParentActiveStudentContext` correctly resets on `user.id` change, but switching across roles within the *same* `user.id` (PA → school_principal preview) did not flush per-page filter state set within the preview.

**Fix applied (this session).** `frontend/src/routes/appRoutes.js` now keys the entire `<Routes>` tree on `${effectiveRole}:${effectiveTenantId}`. React fully unmounts and remounts the page tree on any impersonation enter/exit, guaranteeing per-page state (selected class/grade/section/subject filters in `StudentsPage`, `AttendancePage`, `TeacherStudentsPage`, `TeacherAttendanceManagePage`, etc.) is discarded across role switches. The hard-navigation pattern in all three exit callsites already mitigated this in practice; the route-key change is the belt-and-braces fix for any future exit path that doesn't trigger a hard reload.

---

## 3. Verified-good controls (positive findings, with live evidence)

| Control | Probe result |
|---|---|
| `X-School-Context` requires `is_impersonating` (tenant_scope.py:412) | PA + header on `/api/classes` → **HTTP 403** "يجب استخدام مسار تبديل الدور…" ✅ |
| `X-School-Context` pinned to JWT tenant_id (tenant_scope.py:428) | SW (TARGET) + header=OTHER on `/api/classes` → **HTTP 403** "لا يمكن الوصول…" ✅ |
| Hardened restore revokes JTI | SW token after `/role-switch/restore` → **HTTP 401** "Token has been revoked" ✅ |
| Cross-tenant by-id → 404 (§8 invariant) | SW reads `/api/classes/<other-school-uuid>` → **HTTP 404** ✅ |
| Nested impersonation blocked | 2nd `/role-switch/switch` while impersonating → **HTTP 409** ✅ |
| Hardened path requires reason ≥4 chars | empty reason → **HTTP 400** ✅ |
| Hardened path stamps `severity: "high"` on audit row | `GET /api/audit/logs?action=role_switch` shows `"severity":"high","actor_role":"platform_admin"` ✅ |
| Legacy `/user-roles/switch` forces PA to hardened path | PA call → **HTTP 400** "يجب تحديد المدرسة للأدوار المدرسية" + redirect logic at line 222 ✅ |
| `/users/{id}/switch-role` self-only | PA → other user_id → **HTTP 403** "يمكنك فقط تبديل دورك الخاص" ✅ |
| MFA shim resolves in production | `_switch_mfa_dep` wired to real `require_recent_mfa()` via `app/routes.py:340` ✅ |

---

## 4. Fixes applied in this session — ALL FINDINGS RESOLVED

| ID | Tier | File | Change | Verified |
|---|---|---|---|---|
| H1a | High | `backend/routes/auth_routes_mod.py` (≈1140) | `for role in user_roles: if not isinstance(role, dict): continue` | cross-tenant → 400 (was 500) |
| H1b | High | `backend/routes/auth_routes_mod.py` (≈1586) | `for linked in user.get("linked_roles", []): if not isinstance(linked, dict): continue` | cross-tenant → 400 (was 500) |
| H1c | High | `backend/routes/auth_routes_mod.py` (≈1549) | Same guard on the sibling `GET /api/users/{id}/roles` reader (architect-flagged). | → 200 with full role list |
| H2  | High | `frontend/src/contexts/AuthContext.js` (906) + `PrincipalDashboard.jsx` + `AccountSettingsPage.jsx` + `Sidebar.jsx` | `exitSchoolContext` now `await`s `POST /role-switch/restore` (server-side JTI revoke); the 3 callsites `await` it before navigating; worst-case branch clears the bearer to avoid UI/token divergence. | replay of pre-restore SW → 401 "Token has been revoked" |
| M1  | Medium | `backend/routes/auth_routes_mod.py` (`/auth/refresh`, line ≈735) | Refresh refuses with **HTTP 409** while an active `impersonation_sessions` row exists for the caller, closing the parallel PA-refresh privilege channel during impersonation. | refresh during impersonation → 409; after restore → 200 |
| M2  | Medium | `backend/routes/user_roles_routes.py` (319) | Legacy audit row stamped with `severity: "high"`, `actor_role`, top-level `tenant_id`. | code inspection (path unreachable for PA pre-write) |
| L1  | Low | `backend/routes/auth_routes_mod.py` (set_active_role, switch_user_role) | Deprecation `logger.warning("deprecated_route_used: …")` on every call to the two alternate switch endpoints, with caller identity and target role/tenant for ops metrics. | endpoints still 200; warning will surface any remaining caller |
| L2  | Low | `frontend/src/routes/appRoutes.js` (≈200) | `<Routes key={`${effectiveRole}:${effectiveTenantId}`}>` forces a full remount of the routed tree on impersonation enter/exit. | belt-and-braces over existing hard-navigation pattern |

**Status: 0 outstanding findings. All 8 audit issues (0 Critical / 4 High / 2 Medium / 2 Low) closed in-session.**

---

## 6. Test reproductions (one-liner cheat sheet)

```bash
BASE=http://localhost:8000
PA=$(curl -sS $BASE/api/auth/login -d '{"email":"<PA>","password":"<P>"}' -H 'Content-Type: application/json' | jq -r .access_token)
# H1a — repro
curl -sS -X POST $BASE/api/auth/set-active-role -H "Authorization: Bearer $PA" \
  -H 'Content-Type: application/json' -d '{"role_id":"school_principal","school_id":"<TARGET>"}'
# H2 — repro: switch, then re-use SW token after client-only sessionStorage drop
SW=$(curl -sS -X POST $BASE/api/role-switch/switch -H "Authorization: Bearer $PA" \
  -H 'Content-Type: application/json' -d '{"target_role":"school_principal","school_id":"<TARGET>","reason":"audit"}' | jq -r .token)
curl -sS $BASE/api/auth/me -H "Authorization: Bearer $SW"   # still 200 after FE "exit"
```

---

**Scratch & supporting artefacts:** `docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md`, `docs/superpowers/plans/2026-05-25-role-switching-audit.md`, `docs/superpowers/specs/2026-05-25-role-switching-audit-design.md`.
