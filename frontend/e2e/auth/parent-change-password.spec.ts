import { test, expect, Browser, BrowserContext, Page } from '@playwright/test';
import { getParentCredentials } from '../lib/credentials';
import { gotoLogin, signInWith, resetSession } from '../lib/loginPage';

/**
 * Task #474 — End-to-end coverage for the Parent Account Settings →
 * Change Password flow.
 *
 * Task #470 fixed the original "NameError → 500 + double dialog"
 * regression and added unit-level coverage (backend route test,
 * dialog jest test, interceptor test) but there was no e2e that
 * drove the actual chain
 *   PasswordChangeDialog → AuthContext.api → /auth/change-password
 * end-to-end against the live FastAPI server. This spec locks that
 * chain so the next time something breaks the canonical path
 * (handler, interceptor envelope shape, dialog wiring, sonner/
 * NassaqAlertDialog stacking) it fails here instead of in front of
 * a parent.
 *
 * Spec contract:
 *   1. Sign in as a parent, open Settings → Change Password, submit
 *      a valid change, sign out, and sign back in with the new
 *      password. The spec then rotates the password BACK to the
 *      original value so the shared test account stays usable for
 *      reruns and for the other parent specs in this folder
 *      (`sign-out-other-devices.spec.ts`).
 *   2. Submit with a WRONG current password and assert exactly one
 *      NassaqAlertDialog error surface appears — never the double
 *      dialog regression Task #470 originally fixed and never a
 *      stray sonner toast.
 *
 * Credentials live in env vars (see `frontend/e2e/README.md` and
 * `TEST_CREDENTIALS.md`). The spec NEVER inlines an email or
 * password and NEVER writes the new password into a permanent file.
 */

const PARENT_SETTINGS_PATH = '/parent/settings';
const ROTATED_PASSWORD = 'Rotated@E2E-Task474!';

async function newSignedInParentContext(
  browser: Browser,
  email: string,
  password: string,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await gotoLogin(page);
  await signInWith(page, email, password);
  await page.waitForURL((u) => u.pathname.startsWith('/parent'), { timeout: 15_000 });
  return { context, page };
}

async function openChangePasswordDialog(page: Page) {
  await page.goto(PARENT_SETTINGS_PATH);
  await expect(page.getByTestId('parent-settings-page')).toBeVisible({ timeout: 15_000 });
  await page.getByTestId('settings-row-password').click();
  await expect(page.getByTestId('parent-password-dialog')).toBeVisible({ timeout: 10_000 });
}

async function fillPasswordForm(page: Page, current: string, next: string) {
  await page.getByTestId('parent-password-current-input').fill(current);
  await page.getByTestId('parent-password-new-input').fill(next);
  await page.getByTestId('parent-password-confirm-input').fill(next);
}

/**
 * Drives the dialog through a successful submit:
 * waits for the /auth/change-password 200 so we don't race the
 * dialog close, then asserts the dialog is gone.
 */
async function submitAndExpectSuccess(page: Page) {
  const responsePromise = page.waitForResponse(
    (r) => /\/auth\/change-password(\?|$)/.test(r.url()) && r.request().method() === 'POST',
    { timeout: 15_000 },
  );
  await page.getByTestId('parent-password-submit-btn').click();
  const resp = await responsePromise;
  expect(resp.status(), `change-password response body: ${await resp.text()}`).toBe(200);
  await expect(page.getByTestId('parent-password-dialog')).toBeHidden({ timeout: 10_000 });
}

/**
 * Signs the page out via the real Settings → Logout row (mirrors
 * what a real parent would do) and asserts the bounce to /login.
 */
async function signOutFromSettings(page: Page) {
  await page.goto(PARENT_SETTINGS_PATH);
  await expect(page.getByTestId('parent-settings-page')).toBeVisible({ timeout: 15_000 });
  await page.getByTestId('settings-row-logout').click();
  const dialog = page.getByTestId('nassaq-alert-dialog');
  await expect(dialog).toBeVisible({ timeout: 5_000 });
  // Confirm button is the first <button> in the NassaqAlertDialog footer.
  await dialog.getByRole('button').first().click();
  await page.waitForURL(/\/login(\?|$|#)/, { timeout: 15_000 });
  await expect(page.getByTestId('login-page')).toBeVisible({ timeout: 5_000 });
}

test.describe('parent change-password e2e (Task #474)', () => {
  test.afterEach(async ({ page }) => {
    await resetSession(page);
  });

  test('valid change: rotates, lets parent sign in with new password, then reverts', async ({ browser }) => {
    const { email, password } = getParentCredentials();
    // Hard guard: don't accidentally rotate to the same value if a
    // previous run aborted halfway and the operator re-seeded the
    // env to ROTATED_PASSWORD. The spec ALWAYS leaves the account
    // back on the canonical seed password.
    expect(password).not.toBe(ROTATED_PASSWORD);

    const a = await newSignedInParentContext(browser, email, password);
    try {
      // 1. Rotate seed → ROTATED_PASSWORD via the real dialog.
      await openChangePasswordDialog(a.page);
      await fillPasswordForm(a.page, password, ROTATED_PASSWORD);
      await submitAndExpectSuccess(a.page);

      // 2. Sign out via the real Settings → Logout row.
      await signOutFromSettings(a.page);

      // 3. Sign back in with the NEW password — proves the rotation
      //    actually landed on the server and the FE login path
      //    accepts it.
      await signInWith(a.page, email, ROTATED_PASSWORD);
      await a.page.waitForURL((u) => u.pathname.startsWith('/parent'), { timeout: 15_000 });

      // 4. Rotate ROTATED_PASSWORD → seed so the shared test
      //    account is reusable on the next run. This MUST succeed;
      //    if it doesn't the spec fails loudly rather than leaving
      //    the account in a broken state.
      await openChangePasswordDialog(a.page);
      await fillPasswordForm(a.page, ROTATED_PASSWORD, password);
      await submitAndExpectSuccess(a.page);
    } finally {
      await a.context.close();
    }
  });

  test('wrong current password surfaces exactly one NassaqAlertDialog (no double-dialog regression)', async ({ browser }) => {
    const { email, password } = getParentCredentials();
    const a = await newSignedInParentContext(browser, email, password);
    try {
      await openChangePasswordDialog(a.page);
      // Deliberately wrong current password; new password is valid
      // so the FE form-level guards don't short-circuit before the
      // API call.
      await fillPasswordForm(a.page, 'WrongCurrent@Pass1!', 'AnotherNew@Pass2!');

      const responsePromise = a.page.waitForResponse(
        (r) => /\/auth\/change-password(\?|$)/.test(r.url()) && r.request().method() === 'POST',
        { timeout: 15_000 },
      );
      await a.page.getByTestId('parent-password-submit-btn').click();
      const resp = await responsePromise;
      expect(resp.status()).toBe(400);

      // Exactly one NassaqAlertDialog (the dialog the catch handler
      // opens) — never two. Task #470's original bug stacked a
      // generic axios-interceptor toast on top of this dialog.
      const errorAlert = a.page.locator('[data-nassaq-alert="error"]');
      await expect(errorAlert).toHaveCount(1, { timeout: 5_000 });
      await expect(errorAlert).toBeVisible();
      // Safe Arabic message from the backend mentioning the
      // current password — pins the message-extraction logic.
      await expect(errorAlert).toContainText('كلمة المرور');

      // No stray sonner toast or non-Nassaq [role=alert] surface.
      await expect(
        a.page.locator('.toast, [data-sonner-toast], [role="alert"]:not([data-nassaq-alert])'),
      ).toHaveCount(0);

      // The change-password dialog itself must still be open so the
      // user can correct the mistake without re-navigating.
      await expect(a.page.getByTestId('parent-password-dialog')).toBeVisible();
    } finally {
      await a.context.close();
    }
  });
});
