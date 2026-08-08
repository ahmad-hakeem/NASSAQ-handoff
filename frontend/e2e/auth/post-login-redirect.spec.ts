import { test, expect } from '@playwright/test';
import {
  getItBootstrappedCredentials,
  getItPreBootstrapCredentials,
  getMfaUserCredentials,
  getPrincipalCredentials,
} from '../lib/credentials';
import {
  expectNassaqDialogContains,
  expectNoNassaqDialog,
  expectNoStrayErrorSurface,
  expectOnPath,
  gotoLogin,
  resetSession,
  signInWith,
} from '../lib/loginPage';

/**
 * Task #197 — Post-login redirect e2e coverage.
 *
 * Exercises the *real* axios interceptor, the real `refreshUser()`
 * call, the real `ProtectedRoute` guards, and the production
 * `NassaqAlertDialog` against the live React app shell.
 */

const INVALID_CREDENTIALS_AR = 'بيانات الدخول غير صحيحة';

test.describe('post-login redirect', () => {
  test.afterEach(async ({ page }) => {
    await resetSession(page);
  });

  test('1. bootstrapped IT lands on /teacher with no error surface', async ({ page }) => {
    const { email, password } = getItBootstrappedCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/teacher');
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });

  test('2. pre-bootstrap IT lands on /teacher/onboarding', async ({ page }) => {
    const { email, password } = getItPreBootstrapCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/teacher/onboarding');
    // The WebSocket handshake for a pre-bootstrap IT token deterministically
    // closes with code 4003 ("workspace not materialised"), which pops the
    // SANCTIONED one-shot "finish setup" info dialog (Task #288 parity with
    // the HTTP perimeter gate). Whether it lands before or after this
    // assertion is a WS race — so tolerate exactly that info dialog (and
    // dismiss it), but fail on any other alert type.
    const alert = page.locator('[data-nassaq-alert]');
    const appeared = await alert
      .waitFor({ state: 'visible', timeout: 3_000 })
      .then(() => true)
      .catch(() => false);
    if (appeared) {
      await expect(alert).toHaveAttribute('data-nassaq-alert', 'info');
      await expect(alert).toContainText('أكمل إعداد مساحتك');
      // Dismiss via the primary CTA (متابعة الإعداد) — it navigates to the
      // onboarding route we are already on.
      await alert.getByRole('button').first().click();
      await expect(alert).toHaveCount(0);
      await expectOnPath(page, '/teacher/onboarding');
    }
    await expectNoStrayErrorSurface(page);
  });

  test('3. principal lands on /principal', async ({ page }) => {
    const { email, password } = getPrincipalCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/principal');
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });

  test('4. wrong password stays on /login with canonical Arabic error in NassaqAlertDialog and no toast', async ({ page }) => {
    const { email } = getItBootstrappedCredentials();
    await gotoLogin(page);
    await signInWith(page, email, 'definitely-not-the-right-password');

    // Stays on /login.
    await expect(page).toHaveURL(/\/login(\?|$|#)/);

    // The canonical Arabic error must surface inside the branded
    // NassaqAlertDialog (selected by `data-nassaq-alert` set in
    // NassaqAlertDialog.jsx). No sonner toast or unbranded
    // `[role=alert]` may fire alongside it.
    await expectNassaqDialogContains(page, INVALID_CREDENTIALS_AR);
    await expectNoStrayErrorSurface(page);
  });

  test('5. MFA recovery-code verify lands on dashboard with reactivation banner painted in same paint', async ({ page }, testInfo) => {
    const { email, password, recoveryCodes } = getMfaUserCredentials();
    // Recovery codes are single-use — a retry must burn the NEXT code
    // from the seeded pool, not replay the consumed one.
    const recoveryCode = recoveryCodes[Math.min(testInfo.retry, recoveryCodes.length - 1)];
    await gotoLogin(page);
    await signInWith(page, email, password);

    // MFA challenge replaces the password form (see MfaLoginChallengePanel.jsx).
    await page
      .getByTestId('mfa-challenge-panel')
      .waitFor({ state: 'visible', timeout: 10_000 });

    // Switch to the recovery-code factor when the multi-factor
    // picker is shown; if the panel already defaulted to
    // recovery_code the pick button won't be present and we just
    // fill the code.
    const pickRecovery = page.getByTestId('mfa-pick-recovery_code');
    if (await pickRecovery.count()) {
      await pickRecovery.click();
    }

    // Same-paint contract (Task #231/#236): the banner must be seeded from
    // the lifecycle snapshot EMBEDDED in the /auth/mfa/verify response —
    // never hydrated by a follow-up GET. Track any lifecycle GET from here
    // on; the dismiss POST is allowed, a GET is a contract breach.
    const lifecycleGets: string[] = [];
    page.on('request', (r) => {
      if (r.method() === 'GET' && r.url().includes('/independent-teacher/workspace/lifecycle')) {
        lifecycleGets.push(r.url());
      }
    });

    await page.getByTestId('mfa-code-input').fill(recoveryCode);
    await page.getByTestId('mfa-verify-btn').click();

    // The MFA test user MUST be an Independent Teacher with an
    // active reactivation-banner snapshot — see README. We assert
    // the IT landing specifically so the same-paint banner check
    // below is meaningful (the banner is IT-only).
    await expectOnPath(page, '/teacher');

    // Task #231 / #236 — the workspace lifecycle banner must be
    // painted in the SAME paint as the dashboard, not after a
    // follow-up GET. In the production build the dashboard chunk is
    // lazy-loaded, so a wall-clock window after the URL transition is
    // racy; the real contract is "banner visible AND zero lifecycle
    // GETs" — the only data source left is the embedded snapshot.
    const banner = page.getByTestId('it-reactivation-banner');
    await banner.waitFor({ state: 'visible', timeout: 10_000 });
    expect(lifecycleGets, 'banner must hydrate from the embedded login snapshot, not a follow-up GET').toEqual([]);
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });

  test('6. already-logged-in user visiting /login is bounced without a flicker of the login form', async ({ page }) => {
    const { email, password } = getItBootstrappedCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/teacher');

    // Instrument a MutationObserver before the /login revisit so
    // we can detect any transient mount of the login card —
    // catches a regression class where the login form briefly
    // renders before the auth-bounce fires.
    await page.addInitScript(() => {
      const w = window as unknown as { __loginCardMounted?: boolean };
      w.__loginCardMounted = false;
      const obs = new MutationObserver(() => {
        if (document.querySelector('[data-testid="login-card"]')) {
          w.__loginCardMounted = true;
        }
      });
      obs.observe(document.documentElement, { childList: true, subtree: true });
    });

    await page.goto('/login');
    await page.waitForURL((url) => url.pathname.startsWith('/teacher'), {
      timeout: 5_000,
    });

    const flickered = await page.evaluate(() => {
      const w = window as unknown as { __loginCardMounted?: boolean };
      return w.__loginCardMounted === true;
    });
    expect(flickered, 'login card flickered on /login revisit').toBe(false);

    await expect(page.getByTestId('login-card')).toHaveCount(0);
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });
});
