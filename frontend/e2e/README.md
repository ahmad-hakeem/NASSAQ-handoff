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

# Parent (any school parent — used by sign-out-other-devices.spec.ts).
# The account does NOT need to be MFA-enrolled; the spec drives two
# real browser contexts as the same parent and asserts the
# "End session" / "End all other sessions" buttons in
# Settings → Active Sessions actually bounce the other browser.
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

`e2e/auth/sign-out-other-devices.spec.ts` (Task #378) — drives two
real browser contexts as the same parent and asserts that:

1. Clicking **End session** in Browser A on Browser B's row in
   Settings → Active Sessions bounces Browser B to `/login` on its
   next API call (real axios 401 interceptor in `AuthContext.js`).
2. Clicking **End all other sessions** in Browser A bounces every
   other browser to `/login`.

It complements — and does not duplicate — the API assertions in
`backend/tests/test_session_revocation_routes.py`.

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
