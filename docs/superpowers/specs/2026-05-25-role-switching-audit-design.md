# Role-Switching Audit & Fix — Platform Admin

**Date:** 2026-05-25
**Status:** Design approved (brainstorming)
**Author:** Replit Agent
**Scope owner:** Project owner

## 1. Goal

Produce a trustworthy picture of whether role switching is safe and correct for the **Platform Admin** account, then fix every issue found, ordered by severity.

The audit is end-to-end: frontend entry points, frontend route guards, frontend state, backend role-switch endpoints, JWT/refresh handling, tenant scoping, WebSocket auth, refresh-persistence behavior, and security posture against the existing `threat_model.md`.

The terminal state of this work is:
1. A structured audit report (deliverable on its own).
2. Every Critical, High, Medium, and Low finding fixed, one commit per severity tier.
3. Live QA re-run on the highest-risk paths after fixes to confirm no regressions.

## 2. Non-Goals

- No changes to the smart-scheduling engine, Hakim AI, or IT workspace lifecycle unless a role-switch bug forces it.
- No re-introduction of the old scheduling system.
- No schema changes unless a finding requires it; if required, Alembic only.
- No changes to login, MFA enrollment, or password-reset flows except where they intersect role-switch behavior.

## 3. Approach

**Audit-first, fix-by-severity** (Approach B from the brainstorm):

1. Run the complete audit and produce the report.
2. Fix Critical → High → Medium → Low, one commit per tier.
3. Each fix references its finding ID in the report.
4. Re-run the highest-risk live QA paths after each tier.

Rationale: the report is a standalone deliverable; if work is interrupted, the most dangerous findings are already gone; severity-first matches the project's threat-model posture.

## 4. Audit Plan (Phases 1–6)

### Phase 1 — Static map
Read and diagram:
- **Frontend:** `contexts/AuthContext.js`, `components/layout/sidebar/RoleSwitcherDialog.jsx`, `components/layout/PreviewModeBanner.jsx`, `components/layout/Sidebar.jsx`, `components/layout/sidebar/SidebarContent.jsx`, `appRoutes.js`, `App.js`, `services/apiClient.js`, any RBAC gates / hooks.
- **Backend:** `routes/user_roles_routes.py`, `routes/auth_routes_mod.py`, `dependencies.py`, `auth_scope.py`, `middleware/`, MFA helpers (`require_recent_mfa_403*`), session/refresh engines (`engines/session_engine.py`, `utils/tokens.py`), WebSocket auth (`routes/websocket_routes.py`).

Output: switch-flow diagram + role-switch matrix (source role → target roles, expected route set, expected tenant scope, expected dashboard, expected sidebar items).

### Phase 2 — Role-switch matrix
For every target role Platform Admin can switch into, define expected behavior for routes, dashboard landing, sidebar, permissions, API scoping, tenant context, page titles, role badges, and switch-back behavior. This becomes the test matrix for Phase 3.

### Phase 3 — Functional QA (live)
Sign in as Platform Admin via `TEST_CREDENTIALS.md` (reference by filename only — never paste creds into report/code/screenshots).

For each target role:
- Switch in, verify shell updates (label, menu, sidebar, dashboard, header).
- Switch back to Platform Admin, verify clean restore.
- Repeat to detect stale state.
- Verify allowed routes accessible, disallowed routes blocked (direct URL navigation included).
- Browser back/forward across role changes.
- Inspect tenant/workspace context, list contents, dashboard widgets — no stale data, no cross-tenant leakage.
- Inspect network requests in DevTools: correct token, no stale role context, clean 401/403/404 handling, no raw backend strings surfaced.
- Refresh page, verify persistence behavior matches intent; watch for flashing wrong menu, brief Platform-Admin-link exposure, redirect loops.

### Phase 4 — Security & permission audit (highest priority)
Probe specifically:
- Permission leakage after switch (admin-only UI/API still reachable).
- Reverse leakage (admin caps missing after switching back).
- Route protection gaps (hidden but reachable; component renders before guard resolves).
- Tenant/workspace leakage (prior school context not reset).
- ID-based access (mutating IDs in URL after switch).
- Cached privileged data (in-memory or form state survives switch).
- Frontend-only restrictions not backed by API enforcement.
- Token/session mismatch (FE thinks role X, BE enforces Y).
- The `return-to-original` legacy path called out in `threat_model.md`.
- Alternate self-role-switch endpoints noted as bypassing hardened MFA/impersonation controls.
- `X-School-Context` header override attempts from lower-tier roles.
- WebSocket re-auth after switch — does the socket carry stale role claims?

### Phase 5 — Edge cases
Switch while on a deep nested route; with a modal open; mid-page-load; after a 401/403; after idle; with immediate browser back; with new tab; before a write/destructive action; during search/filter/pagination; on mobile viewport.

### Phase 6 — Code quality
Duplicate role logic, divergent guards (route vs menu), hardcoded role strings, missing central source of truth, hydration race conditions, missing loading guards before protected render, stale per-page state on switch (selected school/child/class/filters), fragile comparisons (raw strings, case sensitivity, untranslated vs translated labels).

## 5. Deliverable (Phase 7)

File: `docs/superpowers/specs/2026-05-25-role-switching-audit-report.md`

Sections:
1. **Role-switch map** — entry points, source of truth, FE files, BE files, route guard flow, API/session flow, diagram.
2. **Test matrix** — every source → target path, expected, actual, pass/fail.
3. **Findings list** — each finding has: ID (e.g. `F-001`), title, severity (Critical/High/Medium/Low), exact reproduction steps, expected behavior, actual behavior, likely root cause, affected files/components, category (UX / functional / RBAC / tenant-scope / security).
4. **Recommended fixes** — ordered, with notes on shared abstractions to centralize.
5. **QA evidence** — screenshots, console/network observations, layout shifts seen.

## 6. Fix Execution

Iterate severity tiers in order. For each tier:
1. Read the findings in that tier and the affected files.
2. Implement the fix(es). Multiple fixes in the same file batched into one diff.
3. Commit with message `audit(role-switch): fix <tier> findings F-XXX..F-YYY`.
4. Update the report: stamp each finding with `Fixed in <commit-sha>`.
5. Re-run the live QA path that originally reproduced the issue.
6. Move to the next tier.

Order: **Critical → High → Medium → Low.**

## 7. Guardrails (project rules that constrain this work)

- No native `alert()` / `window.confirm()` / `toast.error()` for any new dialog work — `NassaqAlertDialog` only.
- All API error messages must be safe Arabic; never expose raw `str(e)`.
- No credentials anywhere in the report, code, comments, logs, screenshots, or commit messages. Reference `TEST_CREDENTIALS.md` by filename only.
- No re-introduction of the old scheduling system.
- No `Base.metadata.create_all()` / `drop_all()`; schema changes only via Alembic if required.
- Step-up MFA on IT write/export surfaces must keep emitting HTTP 403 envelope (§5.7).
- Don't broaden `TenantIsolation` for cross-workspace co-teaching (§6.7).
- §8 invariant 3: cross-workspace by-id reads stay 404 (never 403/200).
- No `console.log` in frontend pages/contexts.
- No hardcoded secrets; use Replit secrets.
- RTL: logical properties (`ps-*`, `pe-*`, `ms-*`, `me-*`, `text-start`/`text-end`).
- Stable working flows must not regress.

## 8. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Fixes to auth/role guards break logged-in users mid-session | Each fix tier is its own commit; live QA after each tier; do not batch tiers |
| Audit surfaces a finding that requires schema change | Use Alembic; flag as a separate sub-task if non-trivial |
| Findings turn out to be in already-known weak spots from `threat_model.md` | Cross-reference each finding to threat-model anchors; avoid duplicating an existing tracked issue |
| Live QA hits a flaky failure mode | Re-run; if reproducible, file as finding; if not, note in evidence |
| Token budget exhausted mid-fix | Report itself is a deliverable; severity-first order means Critical/High land first |

## 9. Success Criteria

- Every Platform-Admin role-switch path is traced and tested.
- Route/menu/API behavior verified after each switch.
- Stale state and permission leaks investigated with documented evidence.
- Findings list is complete with severity and reproduction steps.
- All Critical/High/Medium/Low findings have a corresponding fix commit and a "Fixed in" stamp in the report.
- Highest-risk live QA paths re-run cleanly after fixes.
