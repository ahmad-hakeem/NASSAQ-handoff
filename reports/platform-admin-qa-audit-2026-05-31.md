# NASSAQ — Platform Admin QA Audit

**Date:** 2026-05-31
**Role under test:** Platform Admin (`platform_admin`, "مدير المنصة")
**Method:** Live, interactive testing of the running app (Playwright automation against the running frontend + backend, plus authenticated API probing for network evidence). No code was modified.
**Account:** Platform Admin test account from `TEST_CREDENTIALS.md` (credentials not reproduced here).

---

## 1. Executive Summary

The Platform Admin account is, in the main, **functional and safe**: authentication, the route guard, logout, by-id error handling, the users module (pagination/search/filter/create wizard), the schools table, audit logs, and system monitoring all work and handle errors gracefully. No raw exception text, stack traces, or cross-tenant *leak* (in the negative sense) was observed — and platform admin is designed to see all tenants, so cross-tenant visibility here is expected.

The most important problems are **two sidebar links that the Platform Admin cannot actually use**: **Product Hub** (backend denies the account with a 403) and **AI Insights** (routes the platform admin into a school-scoped principal page that has no school context, producing a cascade of 400/403 errors). In both cases the page *renders anyway* with empty/placeholder data, so the failure is **silent and misleading** rather than a clear "not available" state. A secondary theme is a **duplicate Schools experience**: the navigation points to an old non-paginated page that renders all 326 schools at once, while a better paginated version exists but is not linked.

No Critical (data-loss / privilege-escalation) issues were found in this pass.

## 2. Total Issues Found

**9** distinct issues (plus several verified-working areas documented in §10).

## 3. Issue Count by Severity

| Severity | Count |
|---|---|
| Critical | 0 |
| High | 2 |
| Medium | 3 |
| Low | 4 |

## 4. Top Issues to Fix First

1. **PA-01 (High)** — "Product Hub" appears in the Platform Admin sidebar but the backend denies the account (403).
2. **PA-02 (High)** — "AI Insights" sidebar link sends the Platform Admin to a school-scoped page that fails with 400/403.
3. **PA-04 (Medium)** — Pages swallow 403/400 errors and show placeholder data instead of a clear "couldn't load / not available for your role" state.
4. **PA-03 (Medium)** — Sidebar "Schools" links to the old non-paginated page (renders all 326 schools); the paginated version isn't surfaced.
5. **PA-05 (Medium)** — Real-time notification WebSocket fails on every page.
6. **PA-06 (Low)** — Schools status summary cards don't sum to the total (a "setup" school isn't counted).
7. **PA-07 (Low)** — Monitoring charts log size(-1) warnings / brief layout flash on mount.
8. **PA-08 (Low)** — No quick language toggle in the authenticated app shell.
9. **PA-09 (Low/Info)** — Persistent "platform under development" banner on every admin page.

---

## Detailed Findings

### PA-01 — Product Hub is in the sidebar but the backend denies the Platform Admin
- **Severity:** High
- **Area / module:** Product Hub
- **Affected page:** `/admin/product-hub` ("مركز ذكاء المنتج")
- **Preconditions:** Signed in as Platform Admin.
- **Reproduction:**
  1. Sign in as Platform Admin.
  2. Click "مركز ذكاء المنتج" in the sidebar (or open `/admin/product-hub`).
  3. Observe the network tab.
- **Current result:** `GET /api/product-hub/dashboard` returns **403** with `{"message":"This action is restricted to the authorized super-admin accounts only."}` (fires twice). The page still renders cards and an "available opportunities" stat, so the user sees a seemingly-working page that is actually failing in the background; the console logs `AxiosError: Request failed with status code 403`.
- **Expected result:** Either Product Hub should be accessible to `platform_admin` (if it's meant for this role), or it should not appear in the Platform Admin sidebar at all. If access is genuinely restricted to a narrower super-admin identity, the page should show a clear, branded "not available for your role" state — not placeholder content.
- **Frequency:** Always
- **Screenshot:** Yes (`route_12_product_hub.png`)
- **Evidence:** `403 GET /api/product-hub/dashboard` (×2); page renders despite the failure.
- **Notes:** The denial wording ("authorized super-admin accounts only") implies the route gates on an allowlist narrower than the `platform_admin` role, while the sidebar gate (`roles: ['platform_admin']`) is broader. The two gates disagree.

### PA-02 — "AI Insights" sends the Platform Admin into a school-scoped page that fails
- **Severity:** High
- **Area / module:** Navigation / AI Insights
- **Affected page:** `/principal/ai-insights` ("رؤى الذكاء الاصطناعي")
- **Preconditions:** Signed in as Platform Admin.
- **Reproduction:**
  1. Sign in as Platform Admin.
  2. Click "رؤى الذكاء الاصطناعي" in the sidebar.
  3. Observe the network tab.
- **Current result:** The link targets the **principal** AI-insights page. Because the platform admin has no school context, it fires a cascade of failures:
  - `GET /api/school/dashboard` → **400** `"المستخدم غير مرتبط بمدرسة"` (user not linked to a school)
  - `GET /api/ai/insights/at-risk-students` → **403** `"Insufficient permissions"`
  - `GET /api/attendance/report/summary` → **403**
  - `GET /api/reports/school/grades` → **400**
  The page nonetheless renders an "AI score" of 74, 0% attendance, and other placeholder/zero values — implying real data that doesn't exist for this role.
- **Expected result:** The Platform Admin should land on a platform-wide AI view, or this item should not appear in the Platform Admin sidebar. It should never silently show fabricated/zero figures.
- **Frequency:** Always
- **Screenshot:** Yes (`route_13_ai_insights.png`)
- **Technical note:** Sidebar config maps the Platform Admin's AI Insights item to `href: '/principal/ai-insights'` (the same school-scoped page used by school roles), rather than a platform-scoped destination.

### PA-03 — Sidebar "Schools" points to the non-paginated page; a paginated version exists but isn't linked
- **Severity:** Medium
- **Area / module:** Schools administration
- **Affected pages:** `/admin/schools` (linked) vs. `/admin/schools-table` (not linked)
- **Reproduction:**
  1. Open `/admin/schools` from the sidebar → all schools render as cards in one long page (~10,000px tall); search is client-side; no pagination.
  2. Open `/admin/schools-table` directly → the same data with **server pagination** ("عرض 1 إلى 10 من 326", 33 pages), search, and status summary cards.
- **Current result:** The Platform Admin's primary Schools link is the heavier, non-paginated page. With 326 schools it renders the entire list at once.
- **Expected result:** Surface a single, paginated schools experience (the table page is the better one). Avoid shipping two divergent schools pages where the nav points at the weaker one.
- **Frequency:** Always
- **Screenshot:** Yes (`route_01_schools_mgmt.png`, `v_schools_table.png`)
- **Notes:** With realistic tenant counts this is a real load/scroll cost, and the inconsistency is confusing.

### PA-04 — Silent error swallowing: failed API calls show placeholder data instead of an error state
- **Severity:** Medium
- **Area / module:** Cross-cutting (Product Hub, AI Insights)
- **Affected pages:** `/admin/product-hub`, `/principal/ai-insights`
- **Reproduction:** Open either page as Platform Admin and watch the console/network.
- **Current result:** The pages render with zeros/placeholder content while the console fills with `AxiosError 403/400`. There is no user-visible indication that the data failed to load.
- **Expected result:** When a data call fails, show a clear, branded empty/error state ("تعذّر تحميل البيانات" with retry, or "غير متاح لهذا الدور"). Don't present placeholder numbers that look like real data.
- **Frequency:** Always
- **Screenshot:** Yes
- **Notes:** This is the mechanism that makes PA-01 and PA-02 feel "fine" at a glance — which is why both went unnoticed visually.

### PA-05 — Real-time notification WebSocket fails on every page
- **Severity:** Medium
- **Area / module:** Notifications / real-time
- **Affected page:** All admin pages
- **Reproduction:** Open any admin page and watch the console.
- **Current result:** `WebSocket connection to '…/api/ws/notifications' failed: WebSocket is closed before the connection is established` on every navigation.
- **Expected result:** A stable WebSocket connection (or a clean, non-erroring fallback to polling).
- **Frequency:** Always (in this environment)
- **Screenshot:** No (console only)
- **Notes:** The dev proxy is configured for WebSockets (`ws: true`), so this is likely an auth/handshake or lifecycle issue rather than missing proxying. Real-time notifications for the Platform Admin should be re-verified end-to-end on the deployed domain; as observed, they are not connecting.

### PA-06 — Schools status summary cards don't sum to the total
- **Severity:** Low
- **Area / module:** Schools table
- **Affected page:** `/admin/schools-table`
- **Current result:** Summary cards read 325 active + 0 suspended + 0 pending, but total = 326. At least one school is in a "setup" state that the summary cards don't account for.
- **Expected result:** The status breakdown should reconcile with the total (include "setup"/other states, or label the gap).
- **Frequency:** Always
- **Screenshot:** Yes (`v_schools_table.png`)

### PA-07 — Monitoring charts log size warnings / brief flash on mount
- **Severity:** Low
- **Area / module:** System Monitoring
- **Affected page:** `/admin/monitoring`
- **Current result:** Console warns `The width(-1) and height(-1) of chart should be greater than 0` on mount; the chart container is 0-sized until after mount, then renders correctly.
- **Expected result:** Reserve chart container dimensions so charts size correctly on first paint (no warning, no flash).
- **Frequency:** Always
- **Screenshot:** Yes (`route_06_monitoring.png`)
- **Note:** The page itself is healthy; the earlier "500" text seen during scanning was a false positive (the "8,500 operations" metric), not an HTTP 500.

### PA-08 — No quick language toggle in the authenticated shell
- **Severity:** Low
- **Area / module:** Localization / shell
- **Current result:** An EN/AR toggle exists on the login screen and under Account Settings → Preferences ("التفضيلات: اللغة والمظهر والوقت"), but there is no quick language switch in the main header/sidebar once signed in.
- **Expected result:** Optional — a quick language toggle in the shell would match the login experience. Low priority.
- **Frequency:** Always
- **Screenshot:** Yes (`v_account_settings.png`)

### PA-09 — Persistent "platform under development" banner on every page
- **Severity:** Low / Info
- **Area / module:** Global shell
- **Current result:** A yellow "المنصة قيد التطوير…" banner sits at the top of every admin page, consuming vertical space.
- **Expected result:** Confirm this is intended for production; if it's a dev-only notice, gate it to non-production environments.
- **Frequency:** Always
- **Screenshot:** Yes (present in all page screenshots)

---

## 5. Permission / Security Findings

- **No privilege escalation or cross-tenant *leak* found.** Platform Admin is intentionally cross-tenant; that visibility is by design.
- **Route guard verified:** unauthenticated access to `/admin` and `/admin/users` redirects to `/login`.
- **Logout verified:** uses a confirmation dialog, clears the `nassaq_token`, redirects to `/login`, and protected routes are blocked afterward.
- **By-id access is safe:** bogus school/user IDs return **404** and a branded error dialog with retry — no raw errors, no existence oracle beyond a generic "failed to load".
- **Permission/UX mismatch (the real issue):** the sidebar advertises two destinations the account cannot use (Product Hub → 403; AI Insights → 400/403). This is a *navigation/authorization consistency* problem, not a data exposure — but it should be fixed because it erodes trust and hides failures (see PA-01, PA-02, PA-04).

## 6. UX / UI Findings

- Duplicate/inconsistent Schools pages; nav points at the weaker one (PA-03).
- Silent failures presented as working pages with placeholder data (PA-04) — the most damaging UX pattern found.
- Monitoring chart mount warning/flash (PA-07).
- No in-shell language toggle (PA-08); persistent dev banner (PA-09).
- **Positives:** the create-user flow is a clean 5-step wizard that disables "Next" until a valid choice is made (no raw validation errors); users list has solid search + role/status/account-type filters and pagination; error dialogs are branded and consistent.

## 7. Data Integrity Findings

- Placeholder/zero figures rendered on pages whose data calls 403/400 (PA-01, PA-02, PA-04) — looks like real data but isn't.
- Schools status counts don't reconcile with the total (PA-06).
- **Positive:** edits/reads that succeed are consistent; bogus IDs fail cleanly; users/schools counts in the paginated views matched the API.

## 8. Localization Findings

- Arabic RTL renders correctly across all admin pages; headings, buttons, dialogs, and error messages are localized.
- Backend error messages surfaced to the UI are in Arabic and safe (e.g., "المستخدم غير مرتبط بمدرسة", "فشل تحميل بيانات المدرسة") — no raw `str(e)` observed.
- Minor: no quick language toggle in the shell (PA-08). No mixed-language or untranslated strings were observed on the audited pages.

## 9. Performance / Reliability Findings

- Non-paginated schools page renders all 326 records at once (~10,000px) (PA-03).
- WebSocket reconnect failures on every page (PA-05).
- Repeated duplicate API calls observed (React strict-mode double-invoke) — e.g., the Product Hub 403 and the AI-insights calls each fired twice; worth confirming this doesn't double real mutations.
- No infinite spinners, frozen buttons, or unrecoverable hangs were observed.

## 10. What Was Tested

- **Auth/session:** login, logout (with confirm dialog), token storage, route guard on protected routes while logged out.
- **Navigation:** every Platform Admin sidebar destination — Dashboard, Schools, Schools-table, Users, Rules, Monitoring, Integrations, Security Center, Workspace Purge, Audit Logs, Communication, Product Hub, AI Insights, Platform Settings, Account Settings.
- **By-id pages:** real and bogus school/user IDs (`/platform/schools/:id`, `/admin/users/:id`).
- **Users module:** list pagination (1–24 of 1960), search, filters, suspend/unlock controls, create-user wizard (open → step gating → cancel).
- **Schools module:** card list vs. paginated table, search, status summary cards.
- **Monitoring/Audit/Security/Settings:** page load, data render, charts.
- **Console + network** captured on every page; authenticated API probing for precise status codes.

## 11. What Could Not Be Tested

- **Destructive flows** (workspace hard-delete/purge, school deactivation, user suspension persistence) — intentionally not executed to protect shared environment data; dialogs were opened only.
- **Role-switch / impersonation** — `MFA_ENFORCEMENT_DISABLED=true` in this environment, so the hardened MFA step-up path could not be exercised realistically.
- **Email/SMS-dependent flows** (invites, password reset delivery).
- **WebSocket behavior on the deployed domain** — only the local dev proxy path was observable.
- **True cross-tenant negative tests** — N/A for Platform Admin (cross-tenant access is by design).

## 12. Recommended Next Priorities

1. **Reconcile sidebar gating with backend authorization** for Product Hub (PA-01) and AI Insights (PA-02): either grant the role, repoint to a platform-scoped page, or hide the items.
2. **Stop silent failures (PA-04):** add branded error/empty states for failed data loads platform-wide; treat a 403/400 as "show error", never "render zeros".
3. **Consolidate the Schools experience (PA-03):** point the sidebar at the paginated table and retire/redirect the non-paginated page.
4. **Investigate the notifications WebSocket (PA-05)** handshake/auth and verify on the deployed domain.
5. Clean up the smaller items: schools status reconciliation (PA-06), monitoring chart sizing (PA-07), shell language toggle (PA-08), and confirm the dev banner is environment-gated (PA-09).
