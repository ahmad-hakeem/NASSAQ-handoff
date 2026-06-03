
(async () => {
  try {
    const fs = require('fs');
const { chromium } = require('playwright');

const BASE = 'http://localhost:5000';
const creds = fs.readFileSync('/home/runner/workspace/TEST_CREDENTIALS.md', 'utf8');
const pw = (creds.match(/Default password for \*\*ALL\*\* accounts:\s*`([^`]+)`/) || [])[1];
const email = (creds.match(/School Admin \(Primary\)\s*\|\s*([^\s|]+@[^\s|]+)/) || [])[1];
if (!pw || !email) throw new Error('Could not parse credentials');

const STAMP = Date.now();
const FRESH_EMAIL = `qa.teacher.${STAMP}@faarabi.edu`;
const FRESH_NID = String(STAMP).slice(-10);
const DUP_EMAIL = 'amyra.alsaady@faarabi.edu';
const log = (...a) => console.log('[E2E]', ...a);

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
page.setDefaultTimeout(20000);
const results = {};

try {
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' });
  await page.fill('[data-testid="login-email-input"]', email);
  await page.fill('[data-testid="login-password-input"]', pw);
  await page.click('[data-testid="login-submit-btn"]');
  await page.waitForTimeout(3500);
  log('logged in, url=', page.url());

  await page.goto(BASE + '/principal/users-management', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="users-classes-management"]', { timeout: 25000 });
  log('on users-classes-management');

  async function openWizard() {
    await page.getByRole('button', { name: 'إضافة', exact: true }).first().click();
    await page.waitForTimeout(800);
    await page.getByRole('button').filter({ hasText: 'إضافة معلم جديد' }).first().click();
    await page.waitForSelector('[data-testid="add-teacher-wizard"]', { timeout: 15000 });
    await page.waitForTimeout(1500);
  }
  async function footerPrimary() {
    const wiz = page.locator('[data-testid="add-teacher-wizard"]');
    await wiz.locator('.border-t button').last().click();
    await page.waitForTimeout(1000);
  }
  async function pickFirstOption(testid) {
    await page.locator(`[data-testid="${testid}"]`).click();
    await page.waitForTimeout(500);
    await page.locator('[role="option"]').first().click();
    await page.waitForTimeout(400);
  }
  async function fillWizard(useEmail, useNid, usePhone) {
    await page.fill('[data-testid="teacher-name-ar"]', 'سعيد القحطاني');
    await page.fill('[data-testid="teacher-national-id"]', useNid);
    await page.click('button:has-text("ذكر")');
    await page.fill('[data-testid="teacher-phone"]', usePhone);
    await page.fill('[data-testid="teacher-email"]', useEmail);
    await footerPrimary();
    await pickFirstOption('teacher-degree');
    await page.fill('[data-testid="teacher-experience"]', '5');
    await pickFirstOption('teacher-rank');
    await footerPrimary();
    const wiz = page.locator('[data-testid="add-teacher-wizard"]');
    await wiz.locator('div.grid button').first().click();
    await page.waitForTimeout(300);
    await pickFirstOption('teacher-primary-subject');
    const gradeBtns = wiz.locator('div.grid.grid-cols-3 button, div.grid.grid-cols-6 button');
    if (await gradeBtns.count()) await gradeBtns.first().click();
    await page.waitForTimeout(300);
    await footerPrimary(); // -> step4
    await footerPrimary(); // -> step5
    await page.waitForTimeout(700);
  }

  // ===== ERROR PATH: duplicate email -> backend 400 -> alert must appear ON TOP =====
  await openWizard();
  await fillWizard(DUP_EMAIL, '1122334455', '0511'+String(STAMP).slice(-6));
  log('submitting duplicate-email teacher...');
  await footerPrimary();
  await page.waitForTimeout(2800);
  const alert = page.locator('[data-testid="nassaq-alert-dialog"]');
  results.alertAppears = await alert.isVisible().catch(() => false);
  log('alert visible:', results.alertAppears);

  if (results.alertAppears) {
    results.layering = await page.evaluate(() => {
      const z = (el) => el ? parseInt(getComputedStyle(el).zIndex || '0', 10) : null;
      const a = document.querySelector('[data-testid="nassaq-alert-dialog"]');
      const w = document.querySelector('[data-testid="add-teacher-wizard"]');
      const cx = Math.floor(window.innerWidth / 2), cy = Math.floor(window.innerHeight / 2);
      const top = document.elementFromPoint(cx, cy);
      return { alertZ: z(a), wizardZ: z(w), topIsAlert: !!(a && top && a.contains(top)), bodyPE: getComputedStyle(document.body).pointerEvents };
    });
    log('layering:', JSON.stringify(results.layering));
    await page.screenshot({ path: '/tmp/e2e-error-alert-on-top.png' });
    await alert.locator('button').first().click(); // dismiss
    await page.waitForTimeout(1200);
    results.alertDismissed = !(await alert.isVisible().catch(() => false));
    const wiz = page.locator('[data-testid="add-teacher-wizard"]');
    let interactive = false;
    try {
      await wiz.locator('.border-t button', { hasText: 'إلغاء' }).first().click({ timeout: 4000 });
      await page.waitForTimeout(1000);
      interactive = !(await wiz.isVisible().catch(() => false));
    } catch (e) {}
    results.wizardInteractiveAfterDismiss = interactive;
    results.bodyPEafter = await page.evaluate(() => getComputedStyle(document.body).pointerEvents);
    log('dismissed:', results.alertDismissed, 'interactive after:', interactive, 'bodyPE:', results.bodyPEafter);
  }

  // ===== SUCCESS PATH: fresh data -> teacher actually created =====
  await page.waitForTimeout(1000);
  await openWizard();
  await fillWizard(FRESH_EMAIL, FRESH_NID, '0522'+String(STAMP).slice(-6));
  log('submitting fresh teacher', FRESH_EMAIL, FRESH_NID);
  await footerPrimary();
  await page.waitForTimeout(4500);
  results.successScreen = await page.locator('[data-testid="add-teacher-wizard"] code').first().isVisible().catch(() => false)
    || await page.locator('text=تمت').first().isVisible().catch(() => false);
  await page.screenshot({ path: '/tmp/e2e-success.png' });
  log('success screen:', results.successScreen);

  console.log('\n[E2E_RESULTS]', JSON.stringify(results, null, 2));
} catch (err) {
  console.error('[E2E_FAIL]', err.message);
  await page.screenshot({ path: '/tmp/e2e-failure.png' }).catch(() => {});
  console.log('\n[E2E_RESULTS]', JSON.stringify(results, null, 2));
} finally {
  await browser.close();
}

  } catch (error) {
    console.error('❌ Automation error:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
    process.exit(1);
  }
})();
