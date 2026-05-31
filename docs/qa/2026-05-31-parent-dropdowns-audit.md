# Parent Role — Dropdown / Select / Filter QA Audit

**Date:** 2026-05-31
**Scope:** Read-only end-to-end QA of every dropdown, select, combobox, child-switcher, and filter visible to the **Parent** role.
**Method:** Playwright (headless Chromium) UI walkthrough + direct read-only DB verification. No code or data was modified during the audit.
**Goal:** Confirm each control opens, loads real data, is correctly scoped to the parent's linked child/children, never exposes other families/students/teachers/schools, persists selections, and updates on child-switch/refresh.

---

## Executive summary

The parent portal's filters and notification controls are generally solid, and IDOR protection on by-id reads holds (foreign child → 403, no leak). **One high-severity defect** dominates: the **Communication Center teacher-recipient dropdown** resolves recipients from the class's scheduling sessions **without scoping to the current/published timetable**, and reads only the `timetable_sessions` document collection (not the `schedule_sessions` table that some tenants use). The result is simultaneously an **over-disclosure** bug (a parent sees every teacher ever associated with the child's class across all historical timetables, not just the current teachers) and a **broken-feature** bug (parents at tenants whose live schedule is materialized in `schedule_sessions` see an empty dropdown and cannot message any teacher).

A secondary, lower-severity issue is an aggressive per-IP rate limit on child-data endpoints that can surface `429`/blank-data during bursty browsing.

| # | Severity | Area | One-line |
|---|----------|------|----------|
| 1 | **High** | Communication — teacher dropdown | Recipient query lacks current-timetable scoping → unions all historical teachers (over-disclosure) / empty for `schedule_sessions`-only tenants |
| 2 | Low–Med | Children hub | `/api/parent-portal/child/` rate limit (20/60s per IP) trips during bursty navigation |
| 3 | Good | Notifications filters | Type / read-status / period / priority all work and scope correctly |
| 4 | Good | IDOR | Foreign child by-id → 403, no cross-family leak |
| 5 | Minor | i18n | Children tab mislabeled `واجب`; skip-link stays Arabic after EN toggle |
| — | Untested | Multi-child switcher | No test account with multiple children + default password (see Coverage) |

---

## Controls audited

- **Communication Center** (`/parent/communication`) — teacher recipient dropdown *"اختر المعلم المستلم"* (1 combobox).
- **Notifications** (`/notifications`) — filters: type, read/unread, period, priority.
- **Settings** (`/parent/settings`) — language toggle (AR / EN).
- **Children hub** (`/parent/children`) — sub-tabs (details / schedule / homework / behavior); child switcher.
- **Dashboard** (`/parent`) — child switcher.

---

## Findings

### FINDING 1 — HIGH — Teacher-recipient resolution is not scoped to the current timetable (and reads only one of two session stores)

**Where:** `GET /api/parent-portal/message-recipients/teachers`
→ `_resolve_parent_teacher_recipients` in `backend/routes/parent_portal_routes.py` (the session lookup is the `gd_find(db.session, "timetable_sessions", {"class_id": {"$in": class_ids}}, limit=2000)` call).

**Root cause (two compounding issues):**

1. **No current-timetable scoping (primary).** The recipient query filters sessions **only by `class_id`** — it does not constrain to the current/published timetable (`timetable_id` / published state) nor to active sessions. `timetable_sessions` accumulates a separate set of session docs per timetable run, so a class that has been scheduled many times retains every run's sessions. The query therefore unions **every teacher ever associated with the class across all historical timetables**, not the current roster. (Nearby parent *schedule* endpoints do scope by the active timetable; this recipient resolver does not.)

2. **Single-store read / store inconsistency (secondary).** `timetable_sessions` is **not** in the ORM registry (`backend/engines/sql_utils.py` `_ORM_REGISTRY`), so `gd_find` reads it from the `generic_documents` document store. The platform also has a live `schedule_sessions` ORM table; some tenants' current schedules are materialized **only** in `schedule_sessions` and have **zero** `timetable_sessions` docs. For those tenants this resolver finds nothing and the dropdown is empty. (Note: `timetable_sessions` is *not* a dead collection — it is actively written by the scheduling engine and read by many routes; the defect is the missing timetable scoping and this resolver's reliance on a single store, not the store being orphaned.)

**Observed behavior (two tenants):**

| Tenant | Current roster (live, for the class) | `timetable_sessions` docs for the class | Dropdown shows | Verdict |
|--------|--------------------------------------|------------------------------------------|----------------|---------|
| Al-Farabi (child class `ca2ce106…`) | **15 distinct teachers** (35 rows in `schedule_sessions`); 18 school-wide | **791 docs spanning 21 distinct timetables**, referencing **103** distinct teachers (all with `is_active` unset) | **103 teachers** (≈ the entire active teacher roster), every entry labeled with the single child *"رائد القحطاني"* | ❌ Over-disclosure + wrong labels |
| Ibn Sina (child class) | 18 teachers, **630 rows in `schedule_sessions`** | **0 docs** | **Empty** — combobox not even rendered | ❌ Broken: parent can message *no* teacher |

**Impact:**
1. **Information disclosure / least-privilege** — an Al-Farabi parent sees ~103 teachers (every teacher who has ever taught the class across 21 timetables) rather than the child's current ~15 teachers. The recipient-discovery scope is broken; all entries are falsely attributed to the one child.
2. **Data accuracy** — the list and its child labels are wrong (current vs. historical).
3. **Broken feature** — at tenants whose current schedule lives in `schedule_sessions` with no `timetable_sessions` docs (e.g. Ibn Sina), the dropdown is empty and the parent cannot contact any teacher, even though 630 live sessions / 18 teachers exist.

**Note on the teacher-row guards:** the downstream `teachers`/`users` lookups *do* filter `is_active=True` and tenant, so the over-broad set is bounded to currently-active in-tenant teachers — but it is still the historical union (103), not the current roster (15). Filtering `is_active` on the session docs would not help here because that field is unset on these docs; the correct fix is scoping to the current/published timetable (and reconciling the `timetable_sessions` vs `schedule_sessions` source). Fix is out of scope for this read-only audit.

**Compounding UX:** the dropdown has **no in-menu search input**, so 103 unsearchable options is also unusable even ignoring correctness.

---

### FINDING 2 — LOW–MEDIUM — Child-data rate limit trips during bursty navigation

**Where:** `RATE_LIMITS["/api/parent-portal/child/"] = {max: 20, window: 60}` in `backend/middleware/rate_limiter.py` (per-IP, per-process).

The children hub fires ~6 child requests per load (`analytics`, `attendance`, `grades`, `insights`, `schedule`, `weekly-analysis`). A single clean load stays well under the cap (verified: Al-Farabi clean load → no 429). However, 3–4 page loads / child-switches / refreshes within 60 s exceed 20 requests and return `429`, leaving analytics/insights panels blank with console errors (`Error fetching analytics: AxiosError … 429`). Reproduced when cumulative requests crossed the window during the audit.

**Notes:**
- The limit is **per-IP, not per-user**, so families behind shared NAT/school networks amplify the effect.
- Mostly automation-induced here, but realistic bursty browsing (switching between children, repeated refresh) can trip it. Recommend either raising the cap, scoping per-user, or batching the 6 child calls into one.

---

### FINDING 3 — GOOD — Notifications filters work and scope correctly

Type (11 options), read/unread (3), period (4), and priority (5) filters all open, load options, and filter the list. No cross-tenant or cross-family notifications observed. (Filters render under tabbed sections; confirmed working in the interactive pass.)

---

### FINDING 4 — GOOD — IDOR protection holds on by-id reads

Requesting a child that does not belong to the authenticated parent returns **403** (not 200/leak). Consistent with the platform's by-id authorization invariant. No cross-family data exposure observed on the audited surfaces.

---

### FINDING 5 — MINOR — Localization

- Children sub-tab labeled **`واجب`** (singular) — should be **`الواجبات`**.
- Language toggle (AR/EN) exists and switches portal content to English, but the skip-to-content link stays Arabic (`تخطى إلى المحتوى الرئيسي`) after toggling — incomplete i18n, cosmetic.

---

## Child-switch behavior

- Audited single-child parents render a **static child chip** (no dropdown), which is correct for one child — there is nothing to switch.
- Persistence/scoping on **child switch with multiple children could not be exercised** (see Coverage).

---

## Coverage — tested vs. untested

**Tested:** Communication teacher dropdown (two tenants), Notifications filters + refresh persistence, Settings language toggle, Children hub load + sub-tabs, Dashboard, IDOR by-id (foreign child), clean-load rate-limit behavior.

**Untested / blocked:**
- **Multi-child switcher.** The only parent with multiple (3) children, `walid.test@nassaq.sa`, does **not** use the default test password (401), and the audit forbids data mutation — so child-switch persistence and per-child scoping on the switcher are **unverified**.
- **In-menu search inside the teacher dropdown** — not present (no search input exists).
- Note: `TEST_CREDENTIALS.md` parent emails were **stale (401)**; DB-verified live parent accounts were used instead.

---

## Top recommended fixes (priority order)

1. **Finding 1 (High):** In `_resolve_parent_teacher_recipients`, scope the session lookup to the child's **current/published timetable** (`timetable_id` / published state), not by `class_id` alone — this collapses the historical 103-teacher union back to the current ~15. Also reconcile the session source so the resolver covers tenants whose live schedule is in `schedule_sessions` (today's `timetable_sessions`-only read returns empty for them). Both changes together fix the over-disclosure, the wrong labels, and the empty-dropdown-broken-feature.
2. **Finding 1 follow-up:** Add an in-menu search/typeahead to the teacher dropdown.
3. **Finding 2 (Low–Med):** Re-scope `/api/parent-portal/child/` limit per-user (not per-IP), raise the cap, or batch the 6 child calls.
4. **Finding 5 (Minor):** Fix `واجب` → `الواجبات`; complete EN i18n for the skip-link.
5. Refresh `TEST_CREDENTIALS.md` parent accounts; add a multi-child parent with the default test password to enable switcher QA.
