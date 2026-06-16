import { test, expect } from '@playwright/test';
import {
  getPlatformAdminCredentials,
  getPlatformOperationsManagerCredentials,
  getPlatformSubAdminCredentials,
} from './lib/credentials';
import {
  expectNassaqDialogContains,
  expectNoNassaqDialog,
  expectNoStrayErrorSurface,
  expectOnPath,
  gotoLogin,
  resetSession,
  signInWith,
} from './lib/loginPage';

/**
 * Task #939 — Platform-role login e2e coverage.
 *
 * The silent no-op bug for `platform_sub_admin` shipped because no
 * automated login test exercised the platform roles. This suite logs in
 * as each platform-level role and asserts the login orchestration
 * resolves the correct redirect target (`resolveRedirectTarget` in
 * `LoginPage.jsx`, mirrored by `ROLE_DASHBOARDS` in
 * `components/guards/RouteGuards.js`). All three platform roles —
 * `platform_admin`, `platform_operations_manager`, and
 * `platform_sub_admin` — must land on `/admin`.
 *
 * It runs against the *real* React app shell: the real axios
 * interceptor, the real `refreshUser()` call, the real `ProtectedRoute`
 * guards, and the production `NassaqAlertDialog`.
 */

const INVALID_CREDENTIALS_AR = 'بيانات الدخول غير صحيحة';

test.describe('platform-role login', () => {
  test.afterEach(async ({ page }) => {
    await resetSession(page);
  });

  test('1. platform_admin lands on /admin', async ({ page }) => {
    const { email, password } = getPlatformAdminCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/admin');
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });

  test('2. platform_operations_manager lands on /admin', async ({ page }) => {
    const { email, password } = getPlatformOperationsManagerCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/admin');
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });

  test('3. platform_sub_admin lands on /admin', async ({ page }) => {
    const { email, password } = getPlatformSubAdminCredentials();
    await gotoLogin(page);
    await signInWith(page, email, password);
    await expectOnPath(page, '/admin');
    await expectNoNassaqDialog(page);
    await expectNoStrayErrorSurface(page);
  });

  test('4. wrong password stays on /login with canonical Arabic error in NassaqAlertDialog and no toast', async ({ page }) => {
    const { email } = getPlatformAdminCredentials();
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
});
