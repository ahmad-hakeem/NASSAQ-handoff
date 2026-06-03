import { expect, Locator, Page } from '@playwright/test';

/**
 * Page-object helpers for the Users & Classes management page
 * (`UsersClassesManagement.jsx`, route `/principal/users-management`).
 *
 * The student class-transfer grid (`StudentClassGrid.jsx`) exposes the
 * stable hooks these helpers rely on:
 *   - class column root:  [data-testid="class-column-<classId>"]
 *                         with data-class-id / data-student-count
 *   - draggable chip:     [data-testid="student-chip-<studentId>"]
 *                         with data-student-id / data-class-id
 */

export async function gotoUsersClassesManagement(page: Page) {
  await page.goto('/principal/users-management');
  await expect(page.getByTestId('users-classes-management')).toBeVisible({ timeout: 15_000 });
  // The students tab is the default; make sure we are on it so the grid renders.
  await page.getByTestId('filter-students').click();
  // The drag grid only renders for school-admin/principal/platform-admin
  // (canDrag). Wait for at least one class column to paint.
  await page.locator('[data-testid^="class-column-"]').first().waitFor({
    state: 'visible',
    timeout: 15_000,
  });
}

export type ColumnInfo = { classId: string; count: number; studentIds: string[] };

/** Snapshot every class column: its id, current student count, and chip ids. */
export async function readColumns(page: Page): Promise<ColumnInfo[]> {
  return page.$$eval('[data-testid^="class-column-"]', (cols) =>
    cols.map((col) => ({
      classId: col.getAttribute('data-class-id') || '',
      count: Number(col.getAttribute('data-student-count') || '0'),
      studentIds: Array.from(col.querySelectorAll('[data-testid^="student-chip-"]')).map(
        (chip) => chip.getAttribute('data-student-id') || '',
      ),
    })),
  );
}

export function columnLocator(page: Page, classId: string): Locator {
  return page.locator(`[data-testid="class-column-${classId}"]`);
}

export function chipLocator(page: Page, studentId: string): Locator {
  return page.locator(`[data-testid="student-chip-${studentId}"]`);
}

/** Read a single column's live student count from its data attribute. */
export async function columnCount(page: Page, classId: string): Promise<number> {
  const value = await columnLocator(page, classId).getAttribute('data-student-count');
  return Number(value || '0');
}
