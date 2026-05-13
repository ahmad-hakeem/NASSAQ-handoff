import { expect, Page } from '@playwright/test';

/**
 * Minimal page-object helpers for the login flow.
 *
 * Selectors prefer the existing `data-testid` hooks on
 * `LoginPage.jsx`, and the branded NassaqAlertDialog surface is
 * identified by the `data-nassaq-alert` attribute set in
 * `NassaqAlertDialog.jsx`.
 */

export async function gotoLogin(page: Page) {
  await page.goto('/login');
  await expect(page.getByTestId('login-page')).toBeVisible();
}

export async function signInWith(page: Page, email: string, password: string) {
  await page.getByTestId('login-email-input').fill(email);
  await page.getByTestId('login-password-input').fill(password);
  await page.getByTestId('login-submit-btn').click();
}

export async function expectOnPath(page: Page, path: string, timeout = 15_000) {
  await page.waitForURL((url) => url.pathname.startsWith(path), { timeout });
}

/** Asserts the branded NassaqAlertDialog is open and contains the expected text. */
export async function expectNassaqDialogContains(page: Page, text: string) {
  const dialog = page.locator('[data-nassaq-alert]');
  await expect(dialog).toBeVisible({ timeout: 5_000 });
  await expect(dialog).toContainText(text);
}

/**
 * Asserts that no stray toast or non-NassaqAlertDialog
 * `[role=alert]` surface is visible. Matches the spec selector
 * contract: `.toast, [role=alert]:not([data-nassaq-alert])`.
 */
export async function expectNoStrayErrorSurface(page: Page) {
  const stray = page.locator(
    '.toast, [data-sonner-toast], [role="alert"]:not([data-nassaq-alert])',
  );
  await expect(stray).toHaveCount(0);
}

/** Asserts the branded NassaqAlertDialog is closed (no `data-nassaq-alert` element rendered). */
export async function expectNoNassaqDialog(page: Page) {
  await expect(page.locator('[data-nassaq-alert]')).toHaveCount(0);
}

/** Best-effort session reset between tests. */
export async function resetSession(page: Page) {
  await page.request.post('/api/auth/logout').catch(() => {});
  await page.context().clearCookies();
  await page.goto('/login');
  await page.evaluate(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
}
