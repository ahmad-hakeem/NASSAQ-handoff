# Frontend E2E Suite — Post-Login Redirect

This is a tiny Playwright suite that locks the post-login redirect
contract against the **real** React app shell (real axios interceptor,
real `refreshUser()`, real `ProtectedRoute` guards, real
`NassaqAlertDialog`). It complements — and does not replace — the
existing jest unit tests under `frontend/src/__tests__`.

## Prerequisites

1. A running dev backend (`uvicorn backend.server:app --reload`) and a
   running dev frontend (`npm start`) reachable at `http://localhost:5000`
   (or whatever you set `E2E_BASE_URL` to).
2. The seeded test users from `TEST_CREDENTIALS.md` exist in the dev
   database. The suite never creates accounts.
3. Playwright's chromium binary installed:
   ```
   npx playwright install chromium
   ```

## Credentials

All credentials are loaded from environment variables at runtime —
**never** inline an email or password in a spec, helper, or commit
message. The canonical source of truth for the underlying accounts is
`TEST_CREDENTIALS.md` at the repo root; copy the relevant rows into a
gitignored `playwright.local.env` file alongside this README:

```
E2E_BASE_URL=http://localhost:5000

# Independent Teacher (workspace already bootstrapped)
E2E_IT_BOOTSTRAPPED_EMAIL=...
E2E_IT_BOOTSTRAPPED_PASSWORD=...

# Independent Teacher (registered, MFA enrolled, workspace NOT yet bootstrapped)
E2E_IT_PRE_BOOTSTRAP_EMAIL=...
E2E_IT_PRE_BOOTSTRAP_PASSWORD=...

# School Principal
E2E_PRINCIPAL_EMAIL=...
E2E_PRINCIPAL_PASSWORD=...

# Parent (any school parent — used by sign-out-other-devices.spec.ts
# AND parent-change-password.spec.ts).
# The account does NOT need to be MFA-enrolled; the spec drives two
# real browser contexts as the same parent and asserts the
# "End session" / "End all other sessions" buttons in
# Settings → Active Sessions actually bounce the other browser.
#
# IMPORTANT: parent-change-password.spec.ts ROTATES this account's
# password during the run and rotates it back at the end. If the
# spec aborts halfway the canonical seed password may not be
# restored — re-seed the account from TEST_CREDENTIALS.md before
# rerunning the rest of the suite.
E2E_PARENT_EMAIL=...
E2E_PARENT_PASSWORD=...

# MFA-enrolled user with a usable recovery code.
# IMPORTANT: this account MUST be an Independent Teacher whose
# workspace currently has an active `reactivation_banner` snapshot
# (i.e. has been reactivated since their last dismissal). Test #5
# asserts the IT-only same-paint banner, so a non-IT or non-banner-
# eligible MFA user will fail that test.
E2E_MFA_USER_EMAIL=...
E2E_MFA_USER_PASSWORD=...
E2E_MFA_USER_RECOVERY_CODE=...
```

Source the file before running the suite:

```
set -a && source playwright.local.env && set +a
```

If any credential is missing the suite throws a clear
`Missing E2E credentials: ...` error so it never silently skips.

## Running

```
npm run test:e2e          # headless, single chromium project
npm run test:e2e:ui       # Playwright UI mode for debugging
```

Set `E2E_AUTOSTART=1` to let Playwright boot `npm start` itself; by
default the suite assumes a dev server is already running so reruns
stay fast.

## Artifacts

Failures write traces, videos, and screenshots to
`frontend/playwright-report/` and `frontend/test-results/` (both
gitignored).

## What this suite covers

`e2e/auth/parent-change-password.spec.ts` (Task #474) — drives the
Parent Account Settings → Change Password dialog end-to-end against
the live FastAPI server. Two scenarios:

1. Valid change → rotates the password, signs out via the real
   Settings → Logout row, signs back in with the new password, and
   rotates the password BACK to the canonical seed so the shared
   parent account is reusable across runs.
2. Wrong current password → asserts exactly one
   `NassaqAlertDialog` appears (no stacked dialog, no stray sonner
   toast). Pins the regression Task #470 originally fixed.

`e2e/auth/sign-out-other-devices.spec.ts` (Task #378) — drives two
real browser contexts as the same parent and asserts that:

1. Clicking **End session** in Browser A on Browser B's row in
   Settings → Active Sessions bounces Browser B to `/login` on its
   next API call (real axios 401 interceptor in `AuthContext.js`).
2. Clicking **End all other sessions** in Browser A bounces every
   other browser to `/login`.

It complements — and does not duplicate — the API assertions in
`backend/tests/test_session_revocation_routes.py`.

`e2e/management/student-transfer-drag.spec.ts` (Task #804) — drives the
**real** Chromium HTML5 drag gesture for the student class-transfer grid
(`StudentClassGrid.jsx`) on the Users & Classes management page
(`/principal/users-management`). It complements — and does not replace —
the jest component test
(`frontend/src/components/management/__tests__/StudentClassGrid.transfer.test.jsx`),
which can only fake the gesture with synthetic events because jsdom has
no native drag or `DataTransfer`. Two scenarios:

1. Real drag of a student chip from one class column onto another →
   asserts the chip moved into the target column, is gone from the
   source, and both per-column counters changed by one. It then drags
   the student BACK so the shared test account is left exactly as it was
   found (same restore discipline as the parent password spec).
2. A transfer the backend rejects (the spec forces the
   `/students/transfer-class` endpoint to `409` via `page.route`, so the
   failure is deterministic and mutates nothing) → asserts the branded
   `NassaqAlertDialog` surfaces the backend message with no stray sonner
   toast, and the student stays put with intact counters.

The native gesture is fired by `e2e/lib/dragAndDrop.ts`, which dispatches
real bubbling `DragEvent`s with a shared `DataTransfer` inside the live
page — Playwright's mouse-based `dragTo()` cannot trigger HTML5 drag
events or carry a `DataTransfer` payload. Selectors use the
`student-chip-*` / `class-column-*` test hooks on `StudentClassGrid.jsx`.

> NOTE: scenario 1 performs a live backend transfer, so run it against a
> dev/staging database with the seeded test school — never a production
> database. It needs `E2E_PRINCIPAL_EMAIL` / `E2E_PRINCIPAL_PASSWORD` and
> at least two seeded classes where one has a student.

The six scenarios in `e2e/auth/post-login-redirect.spec.ts`:

1. Bootstrapped IT login → `/teacher` dashboard, no error surface.
2. Pre-bootstrap IT login → `/teacher/onboarding`.
3. Principal login → `/principal`.
4. Wrong password → stays on `/login` with the canonical Arabic error
   inside `NassaqAlertDialog` / inline banner, no sonner toast.
5. Login → MFA challenge → recovery code verify → role landing with
   the workspace lifecycle banner painted in the same paint as the
   dashboard (locks Task #231 + #236).
6. Already-logged-in user visits `/login` → bounced to their landing
   without a flicker of the login form.

## Out of scope (follow-ups)

- Cross-browser testing (Chromium only for v1).
- E2E coverage beyond the post-login redirect.
- Visual regression / screenshot diffing.
- CI integration — keep this locally runnable as the primary use case.
