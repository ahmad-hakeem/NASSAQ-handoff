/**
 * Task #138 — pure logic tests for the Master Schedule grid helpers.
 *
 * يحرس هذا الملف منطق وضع العرض (يومي/أسبوعي) ومنطق الترقيم على صفوف
 * المعلمين. الاختبارات نقيّة لا تعتمد على الـproviders، فتظلّ سريعة
 * وموثوقة وتتجنب مشاكل ThemeContext/Translation التي تعطل اختبارات
 * المكوّنات الأكبر.
 */
import {
  computeDisplayDays,
  clampPage,
  paginateRows,
} from '../grid-helpers';

const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

describe('computeDisplayDays', () => {
  it('returns the full week in weekly mode', () => {
    expect(computeDisplayDays('weekly', 'monday', DAYS)).toEqual(DAYS);
  });

  it('returns only the selected day in daily mode', () => {
    expect(computeDisplayDays('daily', 'tuesday', DAYS)).toEqual(['tuesday']);
  });

  it('falls back to the first available day when selectedDay is invalid', () => {
    expect(computeDisplayDays('daily', 'friday', DAYS)).toEqual(['sunday']);
    expect(computeDisplayDays('daily', null, DAYS)).toEqual(['sunday']);
    expect(computeDisplayDays('daily', undefined, DAYS)).toEqual(['sunday']);
  });

  it('returns an empty array when there are no days at all', () => {
    expect(computeDisplayDays('daily', 'monday', [])).toEqual([]);
    expect(computeDisplayDays('weekly', 'monday', [])).toEqual([]);
  });

  it('treats unknown view modes as weekly (full week)', () => {
    expect(computeDisplayDays('something-else', 'monday', DAYS)).toEqual(DAYS);
  });

  it('does not mutate the input days array', () => {
    const input = [...DAYS];
    computeDisplayDays('weekly', 'monday', input);
    expect(input).toEqual(DAYS);
  });
});

describe('clampPage', () => {
  it('keeps a valid page index unchanged', () => {
    expect(clampPage(2, 5)).toBe(2);
  });

  it('clamps negative indices to 0', () => {
    expect(clampPage(-3, 5)).toBe(0);
  });

  it('clamps overflow indices to the last page', () => {
    expect(clampPage(99, 5)).toBe(4);
  });

  it('returns 0 when there are no pages', () => {
    expect(clampPage(2, 0)).toBe(0);
  });
});

describe('paginateRows', () => {
  const rows = Array.from({ length: 23 }, (_, i) => ({ id: i + 1 }));

  it('slices the first page correctly', () => {
    const page = paginateRows(rows, 10, 0);
    expect(page).toHaveLength(10);
    expect(page[0].id).toBe(1);
    expect(page[9].id).toBe(10);
  });

  it('advances to the next page', () => {
    const page = paginateRows(rows, 10, 1);
    expect(page).toHaveLength(10);
    expect(page[0].id).toBe(11);
    expect(page[9].id).toBe(20);
  });

  it('returns the trailing partial page', () => {
    const page = paginateRows(rows, 10, 2);
    expect(page).toHaveLength(3);
    expect(page[0].id).toBe(21);
    expect(page[2].id).toBe(23);
  });

  it('clamps an out-of-range page to the last available page', () => {
    const page = paginateRows(rows, 10, 99);
    expect(page).toHaveLength(3);
    expect(page[0].id).toBe(21);
  });

  it('respects different page sizes', () => {
    expect(paginateRows(rows, 15, 0)).toHaveLength(15);
    expect(paginateRows(rows, 15, 1)).toHaveLength(8);
    expect(paginateRows(rows, 25, 0)).toHaveLength(23);
  });

  it('returns an empty array on bad inputs', () => {
    expect(paginateRows(null, 10, 0)).toEqual([]);
    expect(paginateRows(rows, 0, 0)).toEqual([]);
    expect(paginateRows(rows, -5, 0)).toEqual([]);
  });

  it('does not mutate the input rows', () => {
    const snapshot = rows.map((r) => r.id);
    paginateRows(rows, 10, 0);
    expect(rows.map((r) => r.id)).toEqual(snapshot);
  });
});
