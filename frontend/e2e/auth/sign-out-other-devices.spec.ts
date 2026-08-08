import { test, expect, Browser, BrowserContext, Page } from '@playwright/test';
import { getParentCredentials } from '../lib/credentials';
import { gotoLogin, signInWith, resetSession } from '../lib/loginPage';

/**
 * Task #378 — UI-layer regression coverage for the
 * "End session" / "End all other sessions" buttons in the parent
 * Settings → Active Sessions card.
 *
 * Task #375 already locked the backend behaviour (the API rejects an
 * ended session's refresh+access tokens). This suite drives two real
 * browser contexts as the same parent and asserts that clicking the
 * button in Browser A causes Browser B to be bounced to /login —
 * i.e. that the axios 401 interceptor in
 * `frontend/src/contexts/AuthContext.js` actually fires the redirect
 * the backend test guarantees is possible.
 *
 * The test deliberately does NOT manipulate cookies, localStorage, or
 * tokens directly: the whole point is to catch UI-layer regressions
 * (interceptor swallowing the 401, button mis-wired, optimistic UI
 * hiding the row before the server call returns, etc.).
 *
 * Robustness note: parent test accounts are shared and may carry
 * leftover sessions from previous runs, so we never assume a row
 * count. Browser B's exact session id is captured from its own
 * `/settings/sessions` response (the row marked `is_current` in B's
 * own list), and Browser A targets that specific row by
 * `data-session-id` — see the `data-session-id` / `data-session-current`
 * hooks on `ActiveSessionsCard.jsx`.
 */

const PARENT_SETTINGS_PATH = '/parent/settings';

async function newSignedInParentContext(
  browser: Browser,
  email: string,
  password: string,
  totpSecret: string,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await gotoLogin(page);
  await signInWith(page, email, password, totpSecret);
  // Parents land somewhere under /parent (dashboard, settings, etc.).
  await page.waitForURL((u) => u.pathname.startsWith('/parent'), { timeout: 15_000 });
  return { context, page };
}

/**
 * Navigates to the parent Settings page, waits for the Active
 * Sessions card to render, and returns the id of the *current*
 * session for that browser context (read out of the
 * `/settings/sessions` response so we don't depend on row order).
 */
async function openSessionsAndGetOwnSessionId(page: Page): Promise<string> {
  const sessionsResponse = page.waitForResponse(
    (r) => /\/settings\/sessions(\?|$)/.test(r.url()) && r.request().method() === 'GET',
    { timeout: 15_000 },
  );
  await page.goto(PARENT_SETTINGS_PATH);
  await expect(page.getByTestId('parent-settings-page')).toBeVisible({ timeout: 15_000 });
  const resp = await sessionsResponse;
  const body = await resp.json();
  const list: Array<{ id: string; current?: boolean; is_current?: boolean }> =
    Array.isArray(body?.sessions) ? body.sessions : [];
  const own = list.find((s) => s.current || s.is_current);
  expect(own, 'session list did not include a current-session row').toBeTruthy();
  await expect(page.getByTestId('parent-sessions-list')).toBeVisible({ timeout: 15_000 });
  await expect(
    page.locator(`[data-testid="parent-session-row"][data-session-id="${own!.id}"][data-session-current="1"]`),
  ).toBeVisible({ timeout: 15_000 });
  return own!.id;
}

async function confirmNassaqDialog(page: Page) {
  const dialog = page.getByTestId('nassaq-alert-dialog');
  await expect(dialog).toBeVisible({ timeout: 5_000 });
  // The confirm button is the first <button> in the dialog footer
  // (cancel renders second; see NassaqAlertDialog.jsx).
  await dialog.getByRole('button').first().click();
  await expect(dialog).toBeHidden({ timeout: 10_000 });
}

/**
 * After Browser A revokes Browser B's session, Browser B will only
 * notice on its next API call (the axios response interceptor lives
 * outside React's render tree). A real user almost always reloads or
 * clicks something within a few seconds; we simulate that by issuing
 * a single page.reload() and then asserting the bounce. This is the
 * regression the task asks for: the 401 from re-bootstrap must not be
 * swallowed by the interceptor.
 */
async function expectBouncedToLoginAfterReload(page: Page) {
  await page.reload();
  await page.waitForURL(/\/login(\?|$|#)/, { timeout: 15_000 });
  await expect(page.getByTestId('login-page')).toBeVisible({ timeout: 5_000 });
}

test.describe('sign out other devices', () => {
  test.afterEach(async ({ page }) => {
    await resetSession(page);
  });

  test('clicking "End session" on Browser B\'s row bounces Browser B to /login', async ({ browser }) => {
    const { email, password, totpSecret } = getParentCredentials();

    const a = await newSignedInParentContext(browser, email, password, totpSecret);
    const b = await newSignedInParentContext(browser, email, password, totpSecret);

    try {
      // Capture B's own session id from B's view of the list.
      const bSessionId = await openSessionsAndGetOwnSessionId(b.page);

      // Open the same card in A and confirm A actually sees B's row.
      await openSessionsAndGetOwnSessionId(a.page);
      const bRowInA = a.page.locator(
        `[data-testid="parent-session-row"][data-session-id="${bSessionId}"]`,
      );
      await expect(bRowInA).toBeVisible({ timeout: 15_000 });
      await expect(bRowInA).toHaveAttribute('data-session-current', '0');

      // Click END on B's specific row (not "any other row" — we want
      // to prove A→B revocation, not just A→someone).
      await bRowInA.getByTestId('parent-end-session-btn').click();
      await confirmNassaqDialog(a.page);

      // A's list should no longer contain B's row.
      await expect(bRowInA).toHaveCount(0, { timeout: 10_000 });

      // Browser B is the device that was signed out.
      await expectBouncedToLoginAfterReload(b.page);
    } finally {
      await b.context.close();
      await a.context.close();
    }
  });

  test('clicking "End all other sessions" bounces every other browser to /login', async ({ browser }) => {
    const { email, password, totpSecret } = getParentCredentials();

    const a = await newSignedInParentContext(browser, email, password, totpSecret);
    const b = await newSignedInParentContext(browser, email, password, totpSecret);

    try {
      const aSessionId = await openSessionsAndGetOwnSessionId(a.page);

      const endAllBtn = a.page.getByTestId('parent-end-all-sessions-btn');
      await expect(endAllBtn).toBeVisible({ timeout: 15_000 });
      await endAllBtn.click();
      await confirmNassaqDialog(a.page);

      // Only A's own current-session row should remain. The end-all
      // button itself disappears once otherCount === 0.
      await expect(
        a.page.locator(`[data-testid="parent-session-row"][data-session-id="${aSessionId}"]`),
      ).toBeVisible({ timeout: 10_000 });
      await expect(
        a.page.locator('[data-testid="parent-session-row"][data-session-current="0"]'),
      ).toHaveCount(0, { timeout: 10_000 });
      await expect(a.page.getByTestId('parent-end-all-sessions-btn')).toHaveCount(0);

      await expectBouncedToLoginAfterReload(b.page);
    } finally {
      await b.context.close();
      await a.context.close();
    }
  });
});
