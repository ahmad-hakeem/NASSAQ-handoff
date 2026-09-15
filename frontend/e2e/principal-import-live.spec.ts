/**
 * Disposable, real-browser principal import QA.
 *
 * The Python fixture creates one random development school/account and an
 * all-synthetic workbook.  Every write in this spec goes through Chromium,
 * the React UI, and the live FastAPI routes; there are no route mocks.  The
 * afterAll cleanup is deliberately in the same Playwright lifecycle as the
 * fixture seed so failed assertions still remove only this generated tenant.
 */
import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ROOT = resolve(__dirname, '../..');
const FIXTURE = resolve(ROOT, 'backend/scripts/live_principal_import_qa_fixture.py');
const STATE_PATH = process.env.LIVE_IMPORT_QA_STATE || '/tmp/nassaq_live_principal_import_qa.json';
const CHROMIUM = '/repl/tools/bin/chromium';

test.use({
  launchOptions: {
    executablePath: CHROMIUM,
  },
});

type FixtureState = {
  principal_email: string;
  principal_password: string;
  workbook: string;
  student_names: string[];
  class_names: string[];
  expected_rows: number;
};

let fixture: FixtureState;

test.describe.configure({ retries: 0 });

function runFixture(mode: '--seed' | '--cleanup') {
  // Do not inherit stdout/stderr: the generated password must never reach
  // test output or CI artifacts.
  execFileSync('python', [FIXTURE, mode], {
    cwd: ROOT,
    env: { ...process.env, LIVE_IMPORT_QA_STATE: STATE_PATH },
    stdio: 'ignore',
  });
}

async function login(page: Page) {
  await page.goto('/login');
  await expect(page.getByTestId('login-page')).toBeVisible();
  await page.getByTestId('login-email-input').fill(fixture.principal_email);
  await page.getByTestId('login-password-input').fill(fixture.principal_password);
  await page.getByTestId('login-submit-btn').click();
  await page.waitForURL((url) => url.pathname.startsWith('/principal'), { timeout: 20_000 });
}

async function importWorkbook(page: Page, expected: { created: string; parents: string; classes: string }) {
  await page.goto('/principal/users-management?filter=import-export');
  await expect(page.getByTestId('users-classes-management')).toBeVisible();
  const upload = page.locator('#file-upload');
  await upload.setInputFiles(fixture.workbook);
  await expect(page.getByText(fixture.workbook.split('/').pop() || '', { exact: true })).toBeVisible();

  const responsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/bulk/import/students')
      && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: /بدء الاستيراد|Start Import/ }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const result = await response.json();
  const metrics = result?.data?.metrics || result?.metrics || result;
  console.log('LIVE_IMPORT_METRICS', JSON.stringify({
    imported: metrics.imported,
    created: metrics.created,
    updated: metrics.updated,
    restored: metrics.restored,
    assigned: metrics.assigned,
    classes_created: metrics.classes_created ?? metrics.classesCreated,
    classes_reused: metrics.classes_reused ?? metrics.classesReused,
    parents_created: metrics.parents_created ?? metrics.parentsCreated,
    parents_reused: metrics.parents_reused ?? metrics.parentsReused,
    failed: metrics.failed,
  }));

  await expect(page.getByTestId('import-status-badge-success')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId('import-metric-imported')).toContainText(String(fixture.expected_rows));
  await expect(page.getByTestId('import-metric-created')).toContainText(expected.created);
  await expect(page.getByTestId('import-metric-assigned')).toContainText(String(fixture.expected_rows));
  await expect(page.getByTestId('import-metric-parents_created')).toContainText(expected.parents);
  await expect(page.getByTestId('import-metric-classes_created')).toContainText(expected.classes);
}

async function confirmLogout(page: Page) {
  await page.getByTestId('logout-btn').click();
  const alert = page.locator('[data-nassaq-alert]');
  await expect(alert).toBeVisible();
  await alert.getByRole('button', { name: 'تسجيل الخروج' }).click();
  await page.waitForURL((url) => url.pathname.startsWith('/login'), { timeout: 15_000 });
}

test.beforeAll(() => {
  if (existsSync(STATE_PATH)) {
    throw new Error('refusing to run with an existing live import QA state file');
  }
  runFixture('--seed');
  fixture = JSON.parse(readFileSync(STATE_PATH, 'utf8')) as FixtureState;
});

test.afterAll(() => {
  // This is the only cleanup entry point.  The Python helper refuses any
  // state outside its generated namespace and verifies school/user absence
  // before deleting the generated workbook/state marker.
  if (existsSync(STATE_PATH)) runFixture('--cleanup');
});

test('imports the synthetic ten-row workbook through the principal UI and survives refresh/logout/reimport', async ({ page }) => {
  test.setTimeout(120_000);
  await login(page);

  // First import is a genuine browser multipart upload to the live backend.
  await importWorkbook(page, { created: '10', parents: '10', classes: '10' });

  // Refresh must retain the committed directory structure and all ten rows.
  await page.reload();
  await expect(page.getByTestId('users-classes-management')).toBeVisible();
  await page.getByTestId('filter-parents').click();
  await expect(page.getByTestId('filter-parents')).toContainText('10');
  await expect(page.locator('h3').filter({ hasText: /^ولي اختبار حي/ })).toHaveCount(10);

  // The UI logout confirmation and the next password login are both real.
  await confirmLogout(page);
  await login(page);

  // The second upload proves idempotent reimport after a new authenticated
  // browser session: no duplicate parents/classes should be created.
  await importWorkbook(page, { created: '0', parents: '0', classes: '0' });

  // Parents tab: ten generated parent cards, each with one registered child.
  await page.getByTestId('filter-parents').click();
  await expect(page.getByTestId('filter-parents')).toContainText('10');
  await expect(page.locator('h3').filter({ hasText: /^ولي اختبار حي/ })).toHaveCount(10);
  await expect(page.getByText(/1\s+الأبناء المسجلون/)).toHaveCount(10);

  // Classes tab: all ten generated grade/section cards are visible and their
  // roster counters each show one imported student.
  await page.getByTestId('filter-classes').click();
  await expect(page.locator('h3').filter({ hasText: /^الصف/ })).toHaveCount(10);
  await expect(page.getByText(/1 \/ 30/)).toHaveCount(10);

  // Student profile deep-link is reached through the rendered student card,
  // not by calling its API.  The profile header must show the imported
  // student's canonical class.
  await page.getByTestId('filter-students').click();
  const firstStudent = page
    .getByText(fixture.student_names[0], { exact: true })
    .first()
    .locator('xpath=ancestor::*[starts-with(@data-testid, "student-chip-")]')
    .first();
  await expect(firstStudent).toBeVisible();
  await firstStudent.getByRole('button').click();
  await page.getByRole('menuitem', { name: /عرض الملف|View Profile/ }).click();
  await expect(page).toHaveURL(/\/principal\/students\//, { timeout: 15_000 });
  await expect(page.locator('h1').filter({ hasText: fixture.student_names[0] })).toBeVisible();
  await expect(page.locator('nav').getByText(fixture.class_names[0], { exact: true })).toBeVisible();
  await expect(page.locator('p').filter({ hasText: fixture.class_names[0] }).first()).toBeVisible();
  await page.screenshot({
    path: '/tmp/nassaq-live-principal-import-final.png',
    fullPage: true,
  });
});