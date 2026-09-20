import { expect, test, type Page, type Route } from '@playwright/test';
import { gotoLogin, signInWith } from '../lib/loginPage';

const reviewName = 'مراجعة الاستيراد الخارجي';
const apiCalls = {
  previews: [] as string[],
  confirms: [] as Record<string, unknown>[],
  discards: [] as string[],
};
const hasPrincipalCredentials = Boolean(
  process.env.E2E_PRINCIPAL_EMAIL?.trim() && process.env.E2E_PRINCIPAL_PASSWORD?.trim(),
);

test.use({ launchOptions: { executablePath: '/repl/tools/bin/chromium' } });

const studentRows = Array.from({ length: 25 }, (_, index) => ({
  row: index + 2,
  name: index === 21 ? 'نورة المرشدي' : `طالب خارجي ${index + 1}`,
  action: index % 3 === 0 ? 'update' : 'create',
  national_id: `1100000${String(index).padStart(3, '0')}`,
  grade_name: index === 21 ? 'الصف الخامس' : 'الصف الرابع',
  class_name: index === 21 ? 'خامس ب' : 'رابع أ',
  parent_name: `ولي أمر ${index + 1}`,
  relationships: { parent: index % 3 === 0 ? 'reuse' : 'create', class: 'link' },
  errors: [],
  warnings: index === 0 ? ['سيُعاد استخدام ولي أمر موجود'] : [],
}));

const teacherRows = [
  {
    row: 2,
    name: 'سارة القحطاني',
    action: 'create',
    national_id: '2211111111',
    email: 'sara.external@example.test',
    phone: '0500000001',
    relationships: {},
    errors: [],
    warnings: [],
  },
  {
    row: 3,
    name: 'منى العتيبي',
    action: 'conflict',
    national_id: '2222222222',
    email: 'mona.external@example.test',
    phone: '0500000002',
    relationships: {},
    errors: ['البريد الإلكتروني مستخدم من حساب آخر'],
    warnings: [],
  },
];

function draft(importType: 'students' | 'teachers', rows = importType === 'students' ? studentRows : teacherRows) {
  const blocked = rows.some((row) => row.action === 'conflict' || row.errors.length > 0);
  return {
    draft_id: `task1169-${importType}-draft`,
    fingerprint: `task1169-${importType}-fingerprint`,
    preview_version: 1,
    expires_at: '2099-01-01T00:00:00Z',
    import_type: importType,
    rows,
    summary: {
      total_rows: rows.length,
      create: rows.filter((row) => row.action === 'create').length,
      update: rows.filter((row) => row.action === 'update').length,
      errors: rows.reduce((count, row) => count + row.errors.length, 0),
      warnings: rows.reduce((count, row) => count + row.warnings.length, 0),
    },
    errors: [],
    warnings: [],
    can_confirm: !blocked,
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installExternalImportFixtures(page: Page) {
  await page.route('**/api/bulk/preview/students', async (route) => {
    apiCalls.previews.push('students');
    await fulfillJson(route, draft('students'));
  });
  await page.route('**/api/bulk/preview/teachers', async (route) => {
    apiCalls.previews.push('teachers');
    await fulfillJson(route, draft('teachers'));
  });
  await page.route('**/api/bulk/confirm', async (route) => {
    apiCalls.confirms.push(route.request().postDataJSON());
    await fulfillJson(route, {
      success: true,
      total_rows: studentRows.length,
      imported: studentRows.length,
      created: 16,
      updated: 9,
      restored: 0,
      assigned: studentRows.length,
      classes_created: 0,
      classes_reused: 2,
      parents_created: 16,
      parents_reused: 9,
      students_linked_to_parents: studentRows.length,
      grades_created: 0,
      grades_reused: 2,
      skipped: 0,
      failed: 0,
      errors: [],
      warnings: [],
    });
  });
  await page.route('**/api/bulk/draft/*/discard', async (route) => {
    apiCalls.discards.push(new URL(route.request().url()).pathname);
    await fulfillJson(route, { discarded: true });
  });
}

async function installMockAuthenticatedShell(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('nassaq_token', 'task1169-browser-fixture-token');
    window.localStorage.setItem('nassaq_language', 'ar');
  });
  // Registered first: Playwright gives later, more-specific routes precedence.
  // This keeps unrelated directory/Noor reads deterministic when no reusable
  // principal credential is available in the execution environment.
  await page.route('**/api/**', async (route) => {
    if (route.request().method() === 'GET') {
      await fulfillJson(route, []);
      return;
    }
    await fulfillJson(route, {});
  });
  await page.route('**/api/auth/me', async (route) => {
    await fulfillJson(route, {
      id: 'task1169-principal',
      tenant_id: 'task1169-development-tenant',
      school_id: 'task1169-development-school',
      role: 'school_principal',
      full_name: 'مدير اختبار المتصفح',
      email: 'task1169-browser-fixture@example.test',
      is_active: true,
    });
  });
  await page.route('**/api/auth/me/permissions', async (route) => {
    await fulfillJson(route, { permissions: [] });
  });
}

async function openImportReview(page: Page) {
  if (hasPrincipalCredentials) {
    await gotoLogin(page);
    await signInWith(
      page,
      process.env.E2E_PRINCIPAL_EMAIL!.trim(),
      process.env.E2E_PRINCIPAL_PASSWORD!.trim(),
    );
    await page.waitForURL((url) => url.pathname.startsWith('/principal'), { timeout: 20_000 });
  }
  await page.goto('/principal/users-management?filter=import-export');
  await expect(page.getByTestId('users-classes-management')).toBeVisible();
  await expect(page.getByRole('region', { name: reviewName })).toBeVisible();
}

async function chooseFileAndPreview(page: Page, name: string) {
  const review = page.getByRole('region', { name: reviewName });
  await review.getByLabel('ملف Excel أو CSV').setInputFiles({
    name,
    mimeType: 'text/csv',
    buffer: Buffer.from('fixture bytes are intercepted before server parsing'),
  });
  await review.getByRole('button', { name: 'معاينة الملف' }).click();
  await expect(review.getByText('معاينة فقط — لم تُحفظ أي بيانات بعد')).toBeVisible();
  return review;
}

test.describe('task1169 external import browser verification', () => {
  test.describe.configure({ retries: 0 });

  test.beforeEach(async ({ page }) => {
    apiCalls.previews.length = 0;
    apiCalls.confirms.length = 0;
    apiCalls.discards.length = 0;
    if (!hasPrincipalCredentials) await installMockAuthenticatedShell(page);
    await installExternalImportFixtures(page);
    await openImportReview(page);
  });

  test('student review is RTL, responsive, searchable, pageable, cancellable, and confirms only an acknowledged draft', async ({ page }) => {
    const review = await chooseFileAndPreview(page, 'task1169-students.csv');

    await expect(review).toHaveAttribute('dir', 'rtl');
    await expect(review.getByText('إجمالي الصفوف: 25').first()).toBeVisible();
    await expect(review.getByText('صف 2: طالب خارجي 1 — تحديث')).toBeVisible();
    await expect(review.getByText('سيُعاد استخدام ولي أمر موجود')).toBeVisible();
    await expect(review.getByRole('button', { name: 'تأكيد الاستيراد' })).toBeDisabled();

    await review.getByRole('button', { name: 'التالي' }).click();
    await expect(review.getByText('2 / 2')).toBeVisible();
    await expect(review.getByText('نورة المرشدي')).toBeVisible();
    await review.getByLabel('البحث في صفوف المعاينة').fill('خامس ب');
    await expect(review.getByText('نتائج البحث: 1')).toBeVisible();
    await expect(review.getByText('نورة المرشدي')).toBeVisible();
    await expect(review.getByText('طالب خارجي 1')).toHaveCount(0);

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(review).toBeVisible();
    const overflow = await review.evaluate((element) => element.scrollWidth - element.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await page.screenshot({
      path: '../artifacts/task1169/students-mobile-search.png',
      fullPage: true,
    });

    await review.getByText('راجعت جميع التحذيرات وأوافق على المتابعة.').click();
    await review.getByText('راجعت المعاينة وأؤكد إنشاء أو تحديث السجلات والعلاقات المعروضة.').click();
    await expect(review.getByRole('button', { name: 'تأكيد الاستيراد' })).toBeEnabled();
    await review.getByRole('button', { name: 'تأكيد الاستيراد' }).click();

    await expect.poll(() => apiCalls.confirms.length).toBe(1);
    expect(apiCalls.confirms[0]).toEqual({
      draft_id: 'task1169-students-draft',
      fingerprint: 'task1169-students-fingerprint',
      preview_version: 1,
      acknowledged: true,
    });
    await expect(review.getByText('معاينة فقط — لم تُحفظ أي بيانات بعد')).toHaveCount(0);

    const secondReview = await chooseFileAndPreview(page, 'task1169-cancel.csv');
    await secondReview.getByRole('button', { name: 'إلغاء' }).click();
    await expect(secondReview.getByText('معاينة فقط — لم تُحفظ أي بيانات بعد')).toHaveCount(0);
    await expect.poll(() => apiCalls.discards.some((path) => path.includes('task1169-students-draft'))).toBe(true);
  });

  test('teacher conflicts block the whole import and Noor remains available', async ({ page }) => {
    await page.getByRole('button', { name: 'المعلمين', exact: true }).click();
    const review = await chooseFileAndPreview(page, 'task1169-teachers.csv');

    await expect(review.getByText('سارة القحطاني')).toBeVisible();
    await expect(review.getByText('منى العتيبي')).toBeVisible();
    await expect(review.getByText('البريد الإلكتروني مستخدم من حساب آخر')).toBeVisible();
    await expect(review.getByRole('alert')).toContainText('لا يمكن التأكيد');
    await expect(review.getByRole('button', { name: 'تأكيد الاستيراد' })).toBeDisabled();
    await expect(review.locator('input[type="checkbox"]')).toBeDisabled();
    await page.screenshot({
      path: '../artifacts/task1169/teachers-blocked-noor.png',
      fullPage: true,
    });

    await review.getByLabel('البحث في صفوف المعاينة').fill('سارة');
    await expect(review.getByText('نتائج البحث: 1')).toBeVisible();
    await expect(review.getByText('سارة القحطاني')).toBeVisible();
    await expect(review.getByText('منى العتيبي')).toHaveCount(0);
    expect(apiCalls.confirms).toHaveLength(0);

    await expect(page.getByText('استيراد من نظام نور')).toBeVisible();
    await expect(page.getByRole('button', { name: 'استيراد جديد' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'سجل الاستيرادات' })).toBeVisible();
  });
});