# NASSAQ School Admin Platform — End-to-End Test Design

**Date:** 2026-04-16
**Owner:** Replit Agent (E2E task)
**Status:** Approved by user — execution in progress

## 1. Goal

Production-grade Playwright E2E test of the NASSAQ school admin platform.
The test exercises every primary CRUD entity, the timetable engine, the
communication center, parents linkage, academic structure, and tenant
isolation. Bugs found during execution are fixed in-place rather than only
reported.

## 2. Scope

**In scope (Al-Farabi tenant, account `mudeer@faarabi.edu`):**

| # | Section | Mode | Notes |
|---|---|---|---|
| 1 | Academic Structure | Read-only | Foundational; mutating risks cascade |
| 2 | Subjects | Full CRUD | Bilingual (ar/en) |
| 3 | Time Slots | Full CRUD | uses nassaqConfirm (audit fix) |
| 4 | Classes | Full CRUD | grade + capacity |
| 5 | Teachers | Full CRUD | activate/suspend toggle exercised |
| 6 | Students | Full CRUD | with parent stub |
| 7 | Parents | Read + Edit | parents are auto-linked through students |
| 8 | Teacher Assignments | Full CRUD | teacher×subject×class |
| 9 | School Timetable | Read-only | grid render verification |
| 10 | Timetable Generation | Dry-run only | NEVER click Publish |
| 11 | Communication Center | **Real send** | Recipient = test-created teacher in same run; channel = in_app only |
| 12 | Tenant Isolation | Read-only cross-check | Login as Ibn Sina admin, verify no leakage |
| 13 | Cleanup | Destructive | Reverse FK order |

**Out of scope:**
- Mobile responsive (separate task)
- Performance benchmarking
- Multi-browser (Chromium only)
- Sub-admin / principal role differences

## 3. Test Data Convention

All entities created during the run carry the marker
`E2ETEST-<runId>` where `<runId>` is the Unix-second timestamp at run
start. Examples:

- Subject name: `E2ETEST-1729123456-Math`
- Teacher email: `e2etest.1729123456@faarabi.edu`
- Class name: `E2ETEST-1729123456-Class`

Cleanup phase deletes any record whose name/email contains `E2ETEST-`,
regardless of which run created it. Cleanup runs even when earlier
phases fail.

## 4. Verification Strategy

Each CRUD step asserts THREE signals:

1. **UI affordance** — success toast (`sonner` or `NassaqAlertDialog`)
   appears within 5s of action.
2. **List update** — created item is visible in the list view; deleted
   item is absent. Verified by re-fetching the list page.
3. **Network response** — the underlying API request returns 2xx.
   Captured via Playwright's `page.on('response')` listener.

Any of the three failing → step is marked **FAIL** but the script
continues to the next step.

## 5. Safety Guardrails

| Risk | Guardrail |
|---|---|
| Live timetable replaced | Step 10 generates only; explicitly rejects/discards draft, never clicks Publish |
| Real students/teachers deleted | Cleanup matches `E2ETEST-` prefix only |
| Real parents notified | Step 11 sends to `audience: custom` with one test-created teacher's user_id |
| Cross-tenant pollution | Step 12 uses Ibn Sina admin account; only reads, never writes |
| Academic year/term mutated | Step 1 is read-only |

## 6. Outputs

All artifacts written to `/tmp/e2e-school-admin/`:

- `report.md` — per-step PASS/FAIL with timing, error message, and a
  link to the screenshot
- `screenshots/<NN>-<step>.png` — one per step
- `console.log` — captured browser console errors/warnings
- `network.log` — every API request with status code (filtered to non-2xx for failures)
- `bugs.md` — any bug discovered, with reproduction steps and the fix
  commit reference

## 7. Implementation Approach

- **One Playwright script** at `/tmp/playwright-test-school-admin-e2e.js`
- **Headed browser** (`headless: false`, `slowMo: 100`) for visibility
- **Reusable helpers** at top of script: `login()`, `goto()`,
  `assertToast()`, `expectInList()`, `recordStep()`
- **Phased execution** — each step wrapped in try/catch, failures
  recorded but not fatal
- **All UI-driven CRUD** — true E2E. API calls used only for read-side
  verification of list endpoints, with paths discovered from the
  network log captured during the UI flows themselves.

## 8. Bug-Fix Workflow

When a bug is encountered:

1. Capture screenshot + network log + console log into `bugs.md`
2. Identify root cause (frontend file, backend endpoint, or DB)
3. Apply the fix in the codebase
4. Restart affected workflow
5. Re-run only the failing step to verify
6. Continue with remaining steps

## 9. Acceptance

Run is considered successful when:

- Every step in §2 has a PASS entry in `report.md`, OR
- A FAIL entry exists with an accompanying fix in `bugs.md`
- Cleanup ran and `GET /api/.../subjects` etc. show zero `E2ETEST-`
  records remaining in Al-Farabi
- Tenant isolation step confirms no `E2ETEST-` record visible in Ibn Sina

## 10. Estimated Runtime

20–30 minutes for the full sweep, plus iteration time on any bugs.
