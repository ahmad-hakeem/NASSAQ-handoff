# Role-Switching Audit & Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit the Platform-Admin role-switching surface end-to-end, produce a structured findings report, then fix every Critical → High → Medium → Low finding with one commit per severity tier and live-QA re-runs between tiers.

**Architecture:** Audit-first, fix-by-severity. Phases 1–6 of the audit produce raw findings into a scratch file. Phase 7 promotes them to a structured report under `docs/superpowers/specs/2026-05-25-role-switching-audit-report.md`. Fix tiers consume findings from that report; each tier is one commit and stamps the report with `Fixed in <sha>` per finding.

**Tech Stack:** FastAPI + SQLAlchemy (async) backend; React + react-router-dom + Tailwind frontend; JWT auth with refresh rotation; bcrypt hashes; passkey/MFA step-up via 403 envelope; Replit preview for live QA.

---

## File Structure

**Read-only during audit (highest signal):**
- Frontend: `frontend/src/contexts/AuthContext.js`, `frontend/src/components/layout/sidebar/RoleSwitcherDialog.jsx`, `frontend/src/components/layout/PreviewModeBanner.jsx`, `frontend/src/components/layout/Sidebar.jsx`, `frontend/src/components/layout/sidebar/SidebarContent.jsx`, `frontend/src/appRoutes.js`, `frontend/src/App.js`, `frontend/src/services/apiClient.js`, `frontend/src/contexts/MfaStepUpContext.jsx`, `frontend/src/contexts/WebSocketContext.jsx`.
- Backend: `backend/routes/user_roles_routes.py`, `backend/routes/auth_routes_mod.py`, `backend/dependencies.py`, `backend/auth_scope.py`, `backend/middleware/`, `backend/engines/session_engine.py`, `backend/engines/audit_engine.py`, `backend/utils/tokens.py`, `backend/routes/websocket_routes.py`, `backend/routes/platform_routes_mod.py`.

**Created by this plan:**
- `docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md` — running scratch pad during Phases 1–6.
- `docs/superpowers/specs/2026-05-25-role-switching-audit-report.md` — final deliverable (report + fix stamps).
- `screenshots/role-switch-audit/<finding-id>.jpg` — QA evidence per finding.

**Modified by fix tiers (set TBD until findings land):** any files identified by the audit. Fix-tier tasks below specify the workflow, not the line numbers.

---

## Phase 1 — Static Map

### Task 1: Set up scratch file and re-verify workflow health

**Files:**
- Create: `docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md`

- [ ] **Step 1: Create scratch file with section skeleton**

```bash
mkdir -p docs/superpowers/scratch screenshots/role-switch-audit
cat > docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md <<'EOF'
# Role-Switch Audit — Scratch Notes (2026-05-25)

## Phase 1: Static map
## Phase 2: Role-switch matrix
## Phase 3: Functional QA
## Phase 4: Security & permission probes
## Phase 5: Edge cases
## Phase 6: Code-quality observations
## Raw findings (promote to report in Phase 7)
EOF
```

- [ ] **Step 2: Confirm Backend API and Frontend Dev workflows are running**

Run: check workflow status via `refresh_all_logs`. If either is down, start it before continuing.
Expected: both workflows healthy, no startup exceptions in last 50 log lines.

- [ ] **Step 3: Note baseline auth/MFA posture in scratch file**

Document in scratch under `## Phase 1`: which env vars are present (`DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `MFA_ENCRYPTION_KEY`), JWT algorithm, refresh-token TTL, recent-MFA window. Read `backend/utils/tokens.py` and `backend/dependencies.py` to extract these values.

### Task 2: Map the frontend role-switch entry point

**Files:**
- Read: `frontend/src/components/layout/sidebar/RoleSwitcherDialog.jsx`
- Read: `frontend/src/components/layout/sidebar/SidebarContent.jsx`
- Read: `frontend/src/components/layout/PreviewModeBanner.jsx`
- Read: `frontend/src/contexts/AuthContext.js`

- [ ] **Step 1: Read all four files in parallel**

Capture in scratch under `## Phase 1`:
- Where the switcher renders (which roles see it).
- Which AuthContext action it calls (e.g. `switchRole`, `enterPreview`, `returnToOriginal`).
- What the dialog confirms before switching (MFA prompt? simple confirm? NassaqAlertDialog?).
- What PreviewModeBanner displays and what its "Exit" affordance calls (cross-reference task #528 which made exit obvious).

- [ ] **Step 2: Trace the AuthContext switch action to its API call**

Find the apiClient method invoked. Record the HTTP verb + path in scratch (expected: `POST /api/user-roles/switch` or similar; also note `return-to-original` legacy endpoint).

- [ ] **Step 3: Map what AuthContext mutates on success**

Record: which state slices reset, which persist (localStorage keys, in-memory caches, selected school/child), whether refresh token is rotated, whether WebSocket reconnects.

### Task 3: Map the backend role-switch surface

**Files:**
- Read: `backend/routes/user_roles_routes.py`
- Read: `backend/dependencies.py` (focus on role-switch / impersonation helpers)
- Read: `backend/auth_scope.py`
- Read: `backend/engines/session_engine.py`
- Read: `backend/utils/tokens.py`

- [ ] **Step 1: Read in parallel, capture every role-switch endpoint**

For each endpoint in `user_roles_routes.py` and any role-switch route in `auth_routes_mod.py`, record in scratch:
- Path, method, auth dependency, MFA requirement, body schema, response schema.
- Whether it mints a new access token, a new refresh token, or only rewrites server-side session state.
- Whether it logs to `audit_engine`.
- Whether it revokes prior refresh-token family.

- [ ] **Step 2: Identify the `return-to-original` legacy path**

Cross-reference `threat_model.md` callout. Record exact route, what it accepts, what guards it enforces, and how it differs from the canonical switch.

- [ ] **Step 3: Identify `X-School-Context` handling**

`rg -n "X-School-Context"` across backend. For each handler that reads it, record: who can use it, what scope it grants, whether it survives without re-MFA.

### Task 4: Map route guards and sidebar visibility

**Files:**
- Read: `frontend/src/appRoutes.js`
- Read: `frontend/src/App.js` (route wrapper / RBAC HOC)
- Read: `frontend/src/components/layout/Sidebar.jsx`

- [ ] **Step 1: Extract every route's role allowlist**

Produce a table in scratch: `path → component → allowed roles → fallback`. This is the input to Phase 2's matrix.

- [ ] **Step 2: Extract sidebar visibility rules**

For each sidebar group/item, record which role(s) see it and which selector/predicate determines visibility. Note whether the predicate is the same source-of-truth as the route guard.

- [ ] **Step 3: Commit the scratch file as-is**

```bash
git add docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md
git commit -m "audit(role-switch): phase 1 static map notes"
```

---

## Phase 2 — Role-Switch Matrix

### Task 5: Build the expected-behavior matrix

**Files:**
- Modify: `docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md` (Phase 2 section)

- [ ] **Step 1: Enumerate target roles available to Platform Admin**

From Task 2 + 3 notes, list every role Platform Admin can switch into. For each, record: display label (en + ar), is it tenant-bound, does it require a tenant/school selection, what dashboard route it lands on.

- [ ] **Step 2: For each target role, fill the matrix**

Columns: target role | landing route | allowed sidebar items | tenant scope after switch | expected role badge text | switch-back behavior | refresh-persistence expectation.

- [ ] **Step 3: Record any role that should NOT be switchable**

If the codebase exposes roles but the spec forbids switching into some (e.g. parent, student), document them as "negative cases" — direct-URL probes in Phase 4 will use these.

---

## Phase 3 — Functional QA (live)

### Task 6: Live sign-in as Platform Admin

**Files:** none modified; scratch updated.

- [ ] **Step 1: Open Replit preview, sign in**

Use the Platform Admin credential from `TEST_CREDENTIALS.md` (filename reference only — never paste into scratch, code, or commits). Confirm landing page is Platform Admin dashboard.

- [ ] **Step 2: Snapshot baseline state**

In scratch Phase 3: record landing URL, sidebar items visible, header/user-menu state. Take screenshot `screenshots/role-switch-audit/baseline-platform-admin.jpg`.

- [ ] **Step 3: Open DevTools, clear network log**

Note: every subsequent task in this phase requires Network tab open with "Preserve log" enabled.

### Task 7: Switch into each target role and verify shell

**Files:** scratch Phase 3.

For each target role from the Phase 2 matrix:

- [ ] **Step 1: Open RoleSwitcherDialog, switch into the target**

Record: any MFA prompt, dialog copy, time-to-update, network calls fired (exact URL + status), response payload shape (without secrets).

- [ ] **Step 2: Verify shell**

Compare against expected matrix row: role badge, sidebar items, landing route, header text, page title. Any mismatch → raw finding entry with category `UX` or `RBAC`.

- [ ] **Step 3: Screenshot post-switch state**

Save to `screenshots/role-switch-audit/switched-<role>.jpg`.

- [ ] **Step 4: Switch back to Platform Admin, verify clean restore**

Record any residual UI (stale selected school, stale filters, stale active nav item). Each residual = raw finding entry.

- [ ] **Step 5: Repeat switch-into-target twice more to detect stale state**

If second/third switch behaves differently from first → raw finding.

### Task 8: Route-access correctness per role

**Files:** scratch Phase 3.

For each target role:

- [ ] **Step 1: Switch in, navigate every allowed sidebar item**

Confirm page renders without 401/403/404 and shows scoped data only.

- [ ] **Step 2: Direct-URL probe disallowed routes**

Take a route allowed in another role but not this one. Paste URL in address bar. Expected: redirect to fallback (likely current dashboard) or guarded empty state — never blank page, never infinite redirect, never partial unauthorized render.

- [ ] **Step 3: Browser back/forward across the switch**

Switch role A → role B, then press Back. Expected: app handles the cross-role history entry without rendering A's protected page under B's token. Document actual behavior.

### Task 9: Tenant / workspace scope correctness

**Files:** scratch Phase 3.

- [ ] **Step 1: For each tenant-bound target role, verify tenant context**

Inspect a list endpoint (students, classes, schedules). Confirm IDs/tenant_id in payload match expected scope. Try mutating `?school_id=` in URL or sending `X-School-Context` header for a tenant the current role doesn't own → expect refusal.

- [ ] **Step 2: Verify no stale data from previous role**

After switch, inspect dashboard cards/lists. Each item belongs to the new scope. Each stale item = raw finding (severity Critical if cross-tenant data is visible).

### Task 10: API behavior after switching

**Files:** scratch Phase 3.

- [ ] **Step 1: Capture request headers before and after switch**

For one representative authenticated GET, copy `Authorization` header and any `X-School-Context`. After switch, repeat. Compare. Document changes (token rotated? school-context updated?).

- [ ] **Step 2: Replay an old token after switch**

Save the pre-switch access token in DevTools. After switch, fire a request via `curl` (or DevTools "copy as fetch") using the old token to a route only the old role could see. Expected: 401 (token revoked) or 403 (role mismatch). 200 = Critical finding.

- [ ] **Step 3: Inspect 401/403 handling**

Trigger one of each (call a disallowed endpoint while switched). Confirm FE renders a clean state (no raw Arabic-unsafe `str(e)`, no blank page). Failures = raw finding.

### Task 11: Refresh & persistence

**Files:** scratch Phase 3.

For each target role:

- [ ] **Step 1: Switch in, hard-refresh (Ctrl/Cmd+Shift+R)**

Record: which role is active after reload, time-to-stable-shell, whether Platform-Admin sidebar items flash before being hidden, whether dashboard briefly shows wrong data.

- [ ] **Step 2: Close tab, reopen app URL**

Record whether the previously-switched role persists or session resets to Platform Admin. Compare actual vs intended (intended = whatever the spec/AuthContext implements; if the code says "persist" but UX says "shouldn't," that's a finding).

- [ ] **Step 3: Commit scratch progress**

```bash
git add docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md screenshots/role-switch-audit/
git commit -m "audit(role-switch): phase 3 functional QA notes & evidence"
```

---

## Phase 4 — Security & Permission Probes

### Task 12: Permission leakage probes

**Files:** scratch Phase 4.

- [ ] **Step 1: For each target role, attempt admin-only API directly**

Pick a Platform-Admin-only endpoint (e.g. `POST /api/platform/schools`, `GET /api/admin/...`). While switched into a lower-tier role, call it via DevTools fetch using the current bearer. Expected: 403. 200 = Critical finding.

- [ ] **Step 2: Reverse leakage check**

After switching back to Platform Admin, confirm every admin-only route/widget is reachable again. Any missing = High finding.

- [ ] **Step 3: ID-based probe**

While switched into role B, take an ID seen during role A and request it directly (e.g. `/api/schools/<other-tenant-id>`). Expected: 404 (per §8 invariant 3) or 403. 200 = Critical.

### Task 13: Token & session mismatch probes

**Files:** scratch Phase 4.

- [ ] **Step 1: Decode JWT claims pre/post switch**

Use jwt.io or `python -c "import jwt,sys;print(jwt.decode(sys.argv[1],options={'verify_signature':False}))" "$TOKEN"`. Record claim diffs. Confirm `role`, `tenant_id`/`school_id`, `exp`, `jti` change as expected.

- [ ] **Step 2: Refresh-token family probe**

Trigger a refresh after switch. Confirm old refresh token is invalidated (subsequent use returns 401). Failure = Critical (matches `threat_model.md` callout on MFA session-revocation paths).

- [ ] **Step 3: WebSocket re-auth probe**

Open the WebSocket connection in DevTools. After role switch, confirm the socket either reconnects with new claims or is terminated. A socket carrying stale role claims that still receives messages = High.

### Task 14: Alternate-path probes (legacy & header overrides)

**Files:** scratch Phase 4.

- [ ] **Step 1: `return-to-original` legacy path**

If the route exists (mapped in Task 3 Step 2), invoke it directly via DevTools. Confirm it requires fresh MFA and audit-logs. Missing MFA = High; missing audit log = Medium.

- [ ] **Step 2: `X-School-Context` header from a non-platform role**

While switched into a school-role, fire any authenticated GET with `X-School-Context: <other-tenant-id>`. Expected: ignored or 403. Any tenant widening = Critical.

- [ ] **Step 3: Alternate self-role-switch endpoints**

`rg -n "role.switch|switch.role|impersonat" backend/routes` — for any endpoint beyond the canonical one, probe whether it enforces the same MFA + audit posture. Bypass = Critical.

---

## Phase 5 — Edge Cases

### Task 15: State-survival edge cases

**Files:** scratch Phase 5.

- [ ] **Step 1: Switch while on deep nested route**

Navigate to e.g. `/schedule/<schoolId>/class/<classId>/session/<sessionId>`. Open switcher, switch role. Confirm navigation lands on new role's dashboard (not nested route under new tenant), and no nested-route error toast fires.

- [ ] **Step 2: Switch while a modal is open**

Open any modal (e.g. NassaqAlertDialog confirmation). Switch. Confirm modal closes cleanly; no orphaned overlay or focus-trap.

- [ ] **Step 3: Switch mid-page-load**

Navigate, then immediately switch before XHRs settle. Confirm in-flight requests don't write to the new role's UI state.

- [ ] **Step 4: Switch after 401/403**

Force a 401 (let token expire or revoke it via another tab), see the error UI, then attempt switch. Confirm graceful path (forced re-login, not a hung switcher dialog).

- [ ] **Step 5: Switch with browser back immediately**

Switch role, press Back within 1s. Document outcome.

- [ ] **Step 6: Switch then open new tab**

Switch in tab A, open the app in tab B. Confirm tab B sees the switched role (or original — whichever the spec intends). Inconsistent tabs = at least Medium.

- [ ] **Step 7: Switch then perform a write action**

Switch into a role with write capability (e.g. school admin), perform one write. Confirm the write lands in correct tenant + audit log records correct actor.

- [ ] **Step 8: Switch during search/filter state**

Apply a filter on a list page, switch role. Confirm filter is cleared (not carried into other role's list).

- [ ] **Step 9: Mobile viewport**

DevTools mobile emulation. Confirm switcher reachable, dialog usable, banner readable.

---

## Phase 6 — Code-Quality Sweep

### Task 16: Search-and-document code smells

**Files:** scratch Phase 6.

- [ ] **Step 1: Hardcoded role strings**

```bash
rg -n '"(platform_admin|school_admin|principal|teacher|parent|student|independent_teacher)"' frontend/src backend
```
Document every site that compares raw strings instead of using a central enum.

- [ ] **Step 2: Duplicate guards**

```bash
rg -n 'role\s*===|role\s*==|user\.role|currentRole' frontend/src
```
Identify any page-level guard that duplicates `appRoutes.js` enforcement.

- [ ] **Step 3: console.log leftovers in role-switch code paths**

```bash
rg -n 'console\.(log|warn|error)' frontend/src/contexts frontend/src/components/layout/sidebar
```
Per project rule: any console.log in pages/contexts = Low finding.

- [ ] **Step 4: Stale per-page state on switch**

Inspect: ParentActiveStudentContext, any selected-school context, schedule grid teacher window, filters. Document whether each resets on AuthContext role-change.

- [ ] **Step 5: Untranslated role labels**

Confirm role-name display always goes through i18n (`t('roles.xxx')`), never raw English strings.

- [ ] **Step 6: Commit scratch**

```bash
git add docs/superpowers/scratch/2026-05-25-role-switch-audit-notes.md
git commit -m "audit(role-switch): phases 4-6 security, edge cases, code quality"
```

---

## Phase 7 — Promote Scratch to Report

### Task 17: Write the structured audit report

**Files:**
- Create: `docs/superpowers/specs/2026-05-25-role-switching-audit-report.md`

- [ ] **Step 1: Write the report skeleton**

```markdown
# Role-Switching Audit Report — Platform Admin

**Date:** 2026-05-25
**Scope:** Platform Admin role switching, end-to-end.
**Method:** Static code analysis + live QA via Replit preview using TEST_CREDENTIALS.md.

## 1. Role-Switch Map
### 1.1 Entry points
### 1.2 Source of truth
### 1.3 Frontend files
### 1.4 Backend files
### 1.5 Route guard flow
### 1.6 API / session flow
### 1.7 Diagram

## 2. Test Matrix
| Source role | Target role | Expected | Actual | Pass/Fail |
|---|---|---|---|---|

## 3. Findings
### F-001 — <title>
- **Severity:** Critical | High | Medium | Low
- **Category:** UX | functional | RBAC | tenant-scope | security
- **Reproduction:**
- **Expected:**
- **Actual:**
- **Likely root cause:**
- **Affected files:**
- **Status:** Open
<!-- After fix: append: **Fixed in:** <commit-sha> -->

## 4. Recommended Fixes (ordered)

## 5. QA Evidence
```

- [ ] **Step 2: Fill sections 1, 2, and 5 from scratch**

Copy mapped data + matrix + screenshot references.

- [ ] **Step 3: Promote every raw finding to a numbered F-### entry**

For each, fill all six fields. Assign severity using this rubric:
- **Critical:** cross-tenant data exposure; admin API reachable from lower role; token replay still works; `X-School-Context` widening from non-platform role.
- **High:** stale privileged UI; refresh-persistence inconsistency that leaks; alternate-path bypass of MFA/audit; reverse leakage hiding admin functions.
- **Medium:** stale per-page state; modal/overlay orphans; multi-tab inconsistency; missing audit-log entry on a non-privileged action.
- **Low:** UX clarity; untranslated label; hardcoded role string; `console.log` leftover; minor refresh flash.

- [ ] **Step 4: Write section 4 "Recommended Fixes (ordered)"**

Group fixes by severity tier; within tier, order by shared-abstraction wins first (e.g. "centralize role enum" before per-page rename).

- [ ] **Step 5: Commit the report**

```bash
git add docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
git commit -m "audit(role-switch): findings report (phase 7 deliverable)"
```

---

## Phase 8 — Fix Tier: Critical

### Task 18: Implement every Critical finding

**Files:** TBD — set per-finding from report section 3 "Affected files".

- [ ] **Step 1: List all Critical findings from the report**

In a scratch note, list F-IDs in the Critical tier and their affected files. If zero Critical findings, skip Task 18 entirely and proceed to Task 19.

- [ ] **Step 2: For each Critical finding, in order**

a. Read the affected files identified in the report.
b. Implement the minimal fix that closes the finding's reproduction.
c. If the fix touches an auth/guard surface, add a regression test under `backend/tests/` (for BE) or `frontend/src/**/__tests__/` (for FE) that mirrors the reproduction. If the failing reproduction is a live-only flow (no test harness practical), document the QA step instead.
d. Run `mypy backend/` and `npm run typecheck` and any test you added.
e. **Do NOT commit yet** — batch all Critical fixes into one commit.

- [ ] **Step 3: Re-run live QA for each Critical finding's reproduction**

For each F-ID, open the preview, follow the original reproduction steps. Expected: previously-failing assertion now passes.

- [ ] **Step 4: Single tier commit + report stamps**

```bash
git add -A
git commit -m "audit(role-switch): fix Critical findings F-XXX..F-YYY"
```

Then update the report: for each Critical finding, append `**Fixed in:** <commit-sha>` and flip `**Status:** Open` → `**Status:** Fixed`. Commit the report update:

```bash
git add docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
git commit -m "audit(role-switch): stamp Critical findings as fixed"
```

- [ ] **Step 5: Smoke re-run of the three highest-risk live QA paths**

(a) switch in, switch back, refresh; (b) direct-URL probe to a foreign-tenant route; (c) old-token replay after switch. All must remain green.

---

## Phase 9 — Fix Tier: High

### Task 19: Implement every High finding

**Files:** TBD per-finding.

- [ ] **Step 1: List all High findings**

If zero, skip to Task 20.

- [ ] **Step 2: For each High finding, in order**

Same workflow as Task 18 Step 2 (read → fix → test → typecheck → don't commit).

- [ ] **Step 3: Re-run live QA reproductions for High findings**

- [ ] **Step 4: Single tier commit + report stamps**

```bash
git add -A
git commit -m "audit(role-switch): fix High findings F-XXX..F-YYY"
git add docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
git commit -m "audit(role-switch): stamp High findings as fixed"
```

- [ ] **Step 5: Re-run Critical-tier smoke (3 paths from Task 18 Step 5)**

Confirm Critical fixes did not regress.

---

## Phase 10 — Fix Tier: Medium

### Task 20: Implement every Medium finding

**Files:** TBD per-finding.

- [ ] **Step 1: List all Medium findings**

If zero, skip to Task 21.

- [ ] **Step 2–4: Same workflow as Task 19 with `"Medium"` substituted for `"High"`**

```bash
git add -A
git commit -m "audit(role-switch): fix Medium findings F-XXX..F-YYY"
git add docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
git commit -m "audit(role-switch): stamp Medium findings as fixed"
```

- [ ] **Step 5: Smoke re-run (same 3 paths)**

---

## Phase 11 — Fix Tier: Low

### Task 21: Implement every Low finding

**Files:** TBD per-finding (typically console.log removals, hardcoded-string centralization, i18n cleanups).

- [ ] **Step 1: List all Low findings**

If zero, skip to Task 22.

- [ ] **Step 2: Batch implement**

Most Low findings are surface-level. Group by file. For each:
- Remove `console.log` per project rule.
- Replace raw role strings with the central enum (introduce `frontend/src/constants/roles.js` if it doesn't exist; export `ROLES.PLATFORM_ADMIN`, etc.).
- Route untranslated labels through `t('roles.<key>')` keys added to `frontend/src/locales/{en,ar}.json`.

- [ ] **Step 3: Run typecheck + lint**

```bash
npm run typecheck
mypy backend/
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "audit(role-switch): fix Low findings F-XXX..F-YYY"
git add docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
git commit -m "audit(role-switch): stamp Low findings as fixed"
```

---

## Phase 12 — Final Regression Sweep

### Task 22: End-to-end regression

**Files:** none modified.

- [ ] **Step 1: Re-walk the Phase 2 matrix end-to-end**

For each source→target row, perform: switch, verify shell, switch back, verify shell. Any new mismatch → reopen finding.

- [ ] **Step 2: Re-run all probes from Phase 4**

Permission leakage, token mismatch, alternate-path bypass.

- [ ] **Step 3: Verify report is fully stamped**

```bash
rg -c "Status:\*\* Open" docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
```
Expected output: 0. Any non-zero = unfinished work.

- [ ] **Step 4: Append "Regression sweep clean" stamp to report**

Add a final section:
```markdown
## 6. Closeout
- Regression sweep complete: <YYYY-MM-DD>.
- All findings stamped Fixed.
- Highest-risk QA paths green: switch/switch-back/refresh; foreign-tenant direct-URL; old-token replay.
```

Commit:
```bash
git add docs/superpowers/specs/2026-05-25-role-switching-audit-report.md
git commit -m "audit(role-switch): closeout — regression sweep clean"
```

- [ ] **Step 5: Code review handoff**

Call `architect` per the code_review skill with `task="Review role-switching audit fixes"`, `relevantFiles=` the files touched across Phases 8–11, `includeGitDiff=true`. Fix any severe issues raised immediately.

---

## Guardrails (apply to every task)

- `TEST_CREDENTIALS.md` referenced by filename only; never paste creds into scratch, report, code, commits, or screenshots.
- No native `alert()`/`window.confirm()`/`toast.error()` for new dialogs — `NassaqAlertDialog` only.
- API errors stay safe-Arabic; never expose raw `str(e)`.
- No `console.log` in frontend pages/contexts.
- No `Base.metadata.create_all()`; schema changes via Alembic only.
- Don't broaden `TenantIsolation` for cross-workspace co-teaching (§6.7).
- Step-up MFA on IT write/export surfaces stays HTTP 403 envelope (§5.7).
- RTL via logical properties (`ps-*`, `pe-*`, etc.).
- No re-introduction of the old scheduling system.
- Single commit per severity tier; report stamp commit follows tier commit.

## Self-Review

- **Spec coverage:** every section of the design spec (Phases 1–7 + Fix Execution + Guardrails) has at least one task. ✓
- **Placeholder scan:** "TBD" appears intentionally only in fix-tier task headers (file lists genuinely unknowable until findings land) and is explicitly explained. No vague "implement later" steps. ✓
- **Type consistency:** report file path is consistent across Tasks 17, 18, 19, 20, 21, 22. Severity rubric is defined once (Task 17 Step 3) and referenced by tiers. ✓
