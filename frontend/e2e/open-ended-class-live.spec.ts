/**
 * Disposable real-browser QA for an open-ended class roster.
 *
 * The shared Python fixture creates the disposable principal/school marker and
 * a synthetic workbook.  This spec replaces that workbook's synthetic ten-row
 * payload with 300 synthetic rows in one grade/section, then exercises the
 * real principal upload and class-detail UI.  No application route is mocked.
 */
import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const ROOT = resolve(__dirname, '../..');
const FIXTURE = resolve(ROOT, 'backend/scripts/live_principal_import_qa_fixture.py');
const STATE_PATH = process.env.OPEN_ENDED_CLASS_LIVE_STATE || '/tmp/nassaq_open_ended_class_live.json';
const WORKBOOK_PATH = process.env.OPEN_ENDED_CLASS_LIVE_WORKBOOK || '/tmp/nassaq_open_ended_class_live.xlsx';
const CHROMIUM = '/repl/tools/bin/chromium';
const CLASS_NAME = 'الصف الأول الابتدائي - أ';
const ROW_COUNT = 300;

test.use({
  launchOptions: {
    executablePath: CHROMIUM,
  },
});

test.describe.configure({ retries: 0 });

type FixtureState = {
  school_id: string;
  principal_id: string;
  principal_email: string;
  principal_password: string;
  workbook: string;
};

let fixture: FixtureState | undefined;

function fixtureEnv() {
  return {
    ...process.env,
    LIVE_IMPORT_QA_STATE: STATE_PATH,
    LIVE_IMPORT_QA_WORKBOOK: WORKBOOK_PATH,
  };
}

function runFixture(mode: '--seed' | '--cleanup') {
  // The generated password is never sent to stdout/stderr or test artifacts.
  execFileSync('python', [FIXTURE, mode], {
    cwd: ROOT,
    env: fixtureEnv(),
    stdio: 'ignore',
  });
}

function replaceWithThreeHundredSyntheticRows(state: FixtureState) {
  // This starts from the fixture's already-synthetic workbook and only writes
  // new example.com identities.  It never reads or copies source-workbook
  // values into the generated rows.
  const script = String.raw`
from pathlib import Path
import sys

from openpyxl import load_workbook

workbook_path = Path(sys.argv[1])
school_id = sys.argv[2]
token = school_id.rsplit("-", 1)[-1][:8]
numeric_token = int(token, 16) % 1000000

workbook = load_workbook(workbook_path)
sheet = workbook["البيانات"]
if sheet.max_row > 1:
    sheet.delete_rows(2, sheet.max_row - 1)

grade = "الصف الأول الابتدائي"
section = "أ"
for index in range(1, 301):
    first_name = f"اختبار سعة {token} {index:03d}"
    parent_name = f"ولي سعة {token} {index:03d}"
    # Ten digits, unique for every generated row, and not copied from any
    # uploaded artifact.
    national_id = f"8{numeric_token:06d}{index:03d}"
    parent_phone = f"050{numeric_token:06d}{index:03d}"
    values = [
        first_name,
        "أب",
        "جد",
        "عائلة",
        national_id,
        f"{2000 + (index % 20):04d}-01-{((index - 1) % 28) + 1:02d}",
        "ذكر" if index % 2 else "أنثى",
        grade,
        section,
        parent_name,
        parent_phone,
        f"live-import-qa-parent-{token}-{index:03d}@example.com",
        "لا توجد",
        "بيانات اصطناعية لاختبار صف مفتوح",
    ]
    for column, value in enumerate(values, start=1):
        sheet.cell(row=index + 1, column=column).value = value

workbook.save(workbook_path)
try:
    workbook_path.chmod(0o600)
except OSError:
    pass
`;

  execFileSync('python', ['-c', script, state.workbook, state.school_id], {
    cwd: ROOT,
    env: { ...process.env },
    stdio: 'ignore',
  });
}

async function login(page: Page) {
  await page.goto('/login');
  await expect(page.getByTestId('login-page')).toBeVisible();
  await page.getByTestId('login-email-input').fill(fixture!.principal_email);
  await page.getByTestId('login-password-input').fill(fixture!.principal_password);
  await page.getByTestId('login-submit-btn').click();
  await page.waitForURL((url) => url.pathname.startsWith('/principal'), { timeout: 20_000 });
}

async function importThreeHundredRows(page: Page) {
  await page.goto('/principal/users-management?filter=import-export');
  await expect(page.getByTestId('users-classes-management')).toBeVisible();
  const upload = page.locator('#file-upload');
  await upload.setInputFiles(fixture!.workbook);
  await expect(page.getByText(fixture!.workbook.split('/').pop() || '', { exact: true })).toBeVisible();

  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/bulk/import/students')
      && response.request().method() === 'POST',
    { timeout: 120_000 },
  );
  const importStartedAt = Date.now();
  await page.getByRole('button', { name: /بدء الاستيراد|Start Import/ }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const result = await response.json();
  const metrics = result?.data?.metrics || result?.metrics || result;
  const importResponseMs = Date.now() - importStartedAt;
  console.log('OPEN_ENDED_IMPORT_METRICS', JSON.stringify({
    imported: metrics.imported,
    created: metrics.created,
    updated: metrics.updated,
    restored: metrics.restored,
    assigned: metrics.assigned,
    students_linked_to_parents: metrics.students_linked_to_parents,
    classes_created: metrics.classes_created ?? metrics.classesCreated,
    classes_reused: metrics.classes_reused ?? metrics.classesReused,
    parents_created: metrics.parents_created ?? metrics.parentsCreated,
    parents_reused: metrics.parents_reused ?? metrics.parentsReused,
    failed: metrics.failed,
    import_response_ms: importResponseMs,
  }));

  expect(metrics.imported).toBe(ROW_COUNT);
  expect(metrics.created).toBe(ROW_COUNT);
  expect(metrics.updated).toBe(0);
  expect(metrics.assigned).toBe(ROW_COUNT);
  expect(metrics.classes_created ?? metrics.classesCreated).toBe(1);
  expect(metrics.parents_created ?? metrics.parentsCreated).toBe(ROW_COUNT);
  expect(metrics.failed).toBe(0);

  await expect(page.getByTestId('import-status-badge-success')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('import-metric-imported')).toContainText(String(ROW_COUNT));
  await expect(page.getByTestId('import-metric-created')).toContainText(String(ROW_COUNT));
  await expect(page.getByTestId('import-metric-assigned')).toContainText(String(ROW_COUNT));
  await expect(page.getByTestId('import-metric-parents_created')).toContainText(String(ROW_COUNT));
  await expect(page.getByTestId('import-metric-classes_created')).toContainText('1');

  return importResponseMs;
}

async function verifyAllNamespaceRowsAreGone(state: FixtureState) {
  const script = String.raw`
import asyncio
import sys

from sqlalchemy import text

from db import async_session_factory


def ident(value):
    return '"' + value.replace('"', '""') + '"'


async def main():
    school_id = sys.argv[1]
    principal_id = sys.argv[2]
    principal_email = sys.argv[3]
    async with async_session_factory() as session:
        table_rows = await session.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                """
            )
        )
        tables = [str(value) for value in table_rows.scalars().all()]
        leftovers = {}
        for table in tables:
            column_rows = await session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = :table
                    """
                ),
                {"table": table},
            )
            columns = {str(value) for value in column_rows.scalars().all()}
            clauses = []
            params = {
                "school_id": school_id,
                "principal_id": principal_id,
                "principal_email": principal_email,
                "marker": "%" + school_id + "%",
                "principal_marker": "%" + principal_id + "%",
            }
            for column in ("school_id", "tenant_id", "primary_tenant_id"):
                if column in columns:
                    clauses.append(f"CAST({ident(column)} AS text) = :school_id")
            if "id" in columns:
                clauses.extend([
                    f"CAST({ident('id')} AS text) = :school_id",
                    f"CAST({ident('id')} AS text) = :principal_id",
                ])
            if "email" in columns:
                clauses.append(f"CAST({ident('email')} AS text) = :principal_email")
            # GenericDocument-backed collections (including guardian_links)
            # may not expose school_id as a relational column.
            if "data" in columns:
                clauses.extend([
                    f"CAST({ident('data')} AS text) LIKE :marker",
                    f"CAST({ident('data')} AS text) LIKE :principal_marker",
                ])
            if not clauses:
                continue
            count = await session.execute(
                text(
                    f"SELECT count(*) FROM {ident(table)} "
                    f"WHERE {' OR '.join(clauses)}"
                ),
                params,
            )
            value = int(count.scalar_one())
            if value:
                leftovers[table] = value
    print("OPEN_ENDED_CLEANUP_COUNTS", leftovers)
    if leftovers:
        raise SystemExit(1)


asyncio.run(main())
`;

  const output = execFileSync(
    'python',
    ['-c', script, state.school_id, state.principal_id, state.principal_email],
    {
      cwd: resolve(ROOT, 'backend'),
      env: { ...process.env, TESTING: '1' },
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    },
  );
  console.log(output.trim());
}

test.beforeAll(() => {
  if (existsSync(STATE_PATH) || existsSync(WORKBOOK_PATH)) {
    throw new Error('refusing to run with an existing open-ended class QA artifact');
  }
  runFixture('--seed');
  fixture = JSON.parse(readFileSync(STATE_PATH, 'utf8')) as FixtureState;
  replaceWithThreeHundredSyntheticRows(fixture);
});

test.afterAll(async () => {
  if (!existsSync(STATE_PATH)) return;

  // Keep fixture cleanup as the ownership boundary; it validates the marker
  // namespace before removing the generated school/account and workbook.
  if (!fixture) fixture = JSON.parse(readFileSync(STATE_PATH, 'utf8')) as FixtureState;
  const stateForVerification = fixture;
  runFixture('--cleanup');
  await verifyAllNamespaceRowsAreGone(stateForVerification);
  if (existsSync(STATE_PATH) || existsSync(WORKBOOK_PATH)) {
    throw new Error('open-ended class QA cleanup left a state/workbook artifact');
  }
});

test('imports an open-ended 300-student class and renders its full roster in 50-row batches', async ({ page }) => {
  test.setTimeout(300_000);
  await login(page);

  const importResponseMs = await importThreeHundredRows(page);

  // The class directory must show the real imported count, not a hard-coded
  // capacity such as 30 or a full-capacity warning.
  await page.goto('/principal/users-management?filter=classes');
  await expect(page.getByTestId('users-classes-management')).toBeVisible();
  const classHeading = page.locator('h3').filter({ hasText: CLASS_NAME }).first();
  await expect(classHeading).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('300 طالب', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('30 طالب', { exact: true })).toHaveCount(0);
  await expect(page.locator('input[name="capacity"], input[placeholder*="السعة"], input[aria-label*="السعة"]')).toHaveCount(0);
  await expect(page.getByText(/ممتلئ|full capacity/i)).toHaveCount(0);

  // Open the class through the rendered class card, then perform a real
  // document navigation so browser navigation/DOM timing is measured rather
  // than treating the import response as a render metric.
  await classHeading.click();
  await page.waitForURL(/\/principal\/classes\//, { timeout: 20_000 });
  const classDetailUrl = page.url();
  const classNavigationStartedAt = Date.now();
  await page.goto(classDetailUrl);
  await expect(page.getByTestId('class-detail-page')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('class-detail-page').getByText(CLASS_NAME, { exact: true }).first()).toBeVisible();
  const classRenderMs = Date.now() - classNavigationStartedAt;

  const classDetail = page.getByTestId('class-detail-page');
  await expect(classDetail.getByText('300 طالب', { exact: true })).toBeVisible();
  await expect(classDetail.getByText('30 طالب', { exact: true })).toHaveCount(0);
  await expect(classDetail.locator('main h3')).toHaveCount(50);

  const navigationMetrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
    const firstContentfulPaint = performance.getEntriesByName('first-contentful-paint')[0];
    return {
      dom_content_loaded_ms: navigation ? Math.round(navigation.domContentLoadedEventEnd - navigation.startTime) : null,
      load_event_ms: navigation ? Math.round(navigation.loadEventEnd - navigation.startTime) : null,
      first_contentful_paint_ms: firstContentfulPaint ? Math.round(firstContentfulPaint.startTime) : null,
    };
  });
  console.log('OPEN_ENDED_CLASS_PERFORMANCE', JSON.stringify({
    import_ms: importResponseMs,
    class_navigation_render_ms: classRenderMs,
    ...navigationMetrics,
    initial_student_nodes: await classDetail.locator('main h3').count(),
  }));

  // The open-ended class has no capacity gate.  Each click reveals exactly
  // one more 50-student batch until all 300 rendered student cards are present.
  const showMore = page.getByTestId('show-more-class-students');
  for (const expectedVisible of [100, 150, 200, 250, 300]) {
    await expect(showMore).toBeVisible();
    await showMore.click();
    await expect(classDetail.locator('main h3')).toHaveCount(expectedVisible);
  }
  await expect(showMore).toHaveCount(0);
  await expect(classDetail.getByText('300 طالب', { exact: true })).toBeVisible();

  await page.screenshot({
    path: '/tmp/open-ended-class-live.png',
    fullPage: true,
  });

  // A browser refresh must retain the 300-row class and its true counter.
  await page.reload();
  await expect(page.getByTestId('class-detail-page')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('class-detail-page').getByText('300 طالب', { exact: true })).toBeVisible();
  await expect(page.getByTestId('class-detail-page').locator('main h3')).toHaveCount(50);
});