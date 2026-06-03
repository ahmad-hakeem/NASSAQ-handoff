import { expect, test } from '@playwright/test';
import { getPrincipalCredentials } from '../lib/credentials';
import { html5DragAndDrop } from '../lib/dragAndDrop';
import {
  chipLocator,
  columnCount,
  columnLocator,
  gotoUsersClassesManagement,
  readColumns,
} from '../lib/managementPage';
import { gotoLogin, resetSession, signInWith } from '../lib/loginPage';

/**
 * Task #804 — real-browser drag gesture for the student class-transfer.
 *
 * The jest component test (`StudentClassGrid.transfer.test.jsx`) fakes
 * the gesture with synthetic React Testing Library events and a hand-
 * rolled DataTransfer because jsdom cannot perform a native HTML5 drag.
 * This suite drives the *real* Chromium HTML5 drag pipeline (native
 * DragEvents + a real DataTransfer threaded across dragstart→drop) against
 * the live React shell, the real `handleTransferStudent` /
 * `applyTransferSuccess` wiring, the real backend, and the production
 * `NassaqAlertDialog`.
 *
 * Test 1 performs a real cross-column transfer against the live backend,
 * asserts the student moved and both per-column counters changed, then
 * drags the student BACK so the shared test account is left exactly as it
 * was found (mirrors the restore discipline in
 * `parent-change-password.spec.ts`).
 *
 * Test 2 forces the transfer endpoint to 409 so the failure path is
 * deterministic, then asserts the branded NassaqAlertDialog surfaces the
 * backend message (never a generic toast) and the student stays put.
 */

const CLASS_FULL_AR = 'الفصل ممتلئ';

async function signInAsPrincipal(page: import('@playwright/test').Page) {
  const { email, password } = getPrincipalCredentials();
  await gotoLogin(page);
  await signInWith(page, email, password);
  await page.waitForURL((url) => url.pathname.startsWith('/principal'), { timeout: 15_000 });
}

/**
 * Pick a source column that has at least one student and a different
 * target column, from the live grid. Throws a clear error if the seeded
 * data does not have two usable class columns.
 */
async function pickTransferPair(page: import('@playwright/test').Page) {
  const columns = await readColumns(page);
  const source = columns.find((c) => c.classId && c.studentIds.length > 0);
  if (!source) {
    throw new Error(
      'No class column with a draggable student was found — seed the test school (TEST_CREDENTIALS.md) so at least one class has a student.',
    );
  }
  const target = columns.find((c) => c.classId && c.classId !== source.classId);
  if (!target) {
    throw new Error(
      'Need at least two distinct class columns to test a transfer — seed a second class for the test school.',
    );
  }
  return { studentId: source.studentIds[0], sourceId: source.classId, targetId: target.classId };
}

test.describe('student class-transfer — real HTML5 drag gesture (Task #804)', () => {
  test.afterEach(async ({ page }) => {
    await resetSession(page);
  });

  test('1. a real drag moves the student to another class and updates both counters (then restores)', async ({
    page,
  }) => {
    await signInAsPrincipal(page);
    await gotoUsersClassesManagement(page);

    const { studentId, sourceId, targetId } = await pickTransferPair(page);

    const sourceBefore = await columnCount(page, sourceId);
    const targetBefore = await columnCount(page, targetId);

    // Sanity: the chip starts inside the source column.
    await expect(columnLocator(page, sourceId).locator(chipLocator(page, studentId))).toHaveCount(1);

    // The real native HTML5 drag (DragEvents + shared DataTransfer).
    await html5DragAndDrop(page, chipLocator(page, studentId), columnLocator(page, targetId));

    // The chip now lives under the target column, and is gone from the source.
    await expect(columnLocator(page, targetId).locator(chipLocator(page, studentId))).toHaveCount(1, {
      timeout: 10_000,
    });
    await expect(columnLocator(page, sourceId).locator(chipLocator(page, studentId))).toHaveCount(0);

    // Both per-column counters moved by exactly one (re-derived from the server).
    await expect
      .poll(() => columnCount(page, sourceId), { timeout: 10_000 })
      .toBe(sourceBefore - 1);
    await expect
      .poll(() => columnCount(page, targetId), { timeout: 10_000 })
      .toBe(targetBefore + 1);

    // No error surface on a clean success.
    await expect(page.getByTestId('nassaq-alert-dialog')).toHaveCount(0);

    // --- Restore: drag the student back so the shared account is untouched. ---
    await html5DragAndDrop(page, chipLocator(page, studentId), columnLocator(page, sourceId));

    await expect(columnLocator(page, sourceId).locator(chipLocator(page, studentId))).toHaveCount(1, {
      timeout: 10_000,
    });
    await expect
      .poll(() => columnCount(page, sourceId), { timeout: 10_000 })
      .toBe(sourceBefore);
    await expect
      .poll(() => columnCount(page, targetId), { timeout: 10_000 })
      .toBe(targetBefore);
  });

  test('2. a failing transfer surfaces NassaqAlertDialog and the student stays put', async ({
    page,
  }) => {
    await signInAsPrincipal(page);
    await gotoUsersClassesManagement(page);

    const { studentId, sourceId, targetId } = await pickTransferPair(page);
    const sourceBefore = await columnCount(page, sourceId);
    const targetBefore = await columnCount(page, targetId);

    // Force the transfer endpoint to fail with a real backend message so
    // the error path is deterministic (no reliance on a class being full).
    await page.route('**/students/transfer-class', (route) =>
      route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ success: false, error: { message: CLASS_FULL_AR } }),
      }),
    );

    await html5DragAndDrop(page, chipLocator(page, studentId), columnLocator(page, targetId));

    // The branded NassaqAlertDialog shows the backend's own message —
    // never a generic sonner toast or unbranded alert.
    const dialog = page.getByTestId('nassaq-alert-dialog');
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await expect(dialog).toContainText(CLASS_FULL_AR);
    await expect(
      page.locator('.toast, [data-sonner-toast], [role="alert"]:not([data-nassaq-alert])'),
    ).toHaveCount(0);

    // The student never moved and the counters are intact.
    await expect(columnLocator(page, sourceId).locator(chipLocator(page, studentId))).toHaveCount(1);
    await expect(columnLocator(page, targetId).locator(chipLocator(page, studentId))).toHaveCount(0);
    expect(await columnCount(page, sourceId)).toBe(sourceBefore);
    expect(await columnCount(page, targetId)).toBe(targetBefore);
  });
});
