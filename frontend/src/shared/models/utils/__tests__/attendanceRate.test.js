import { computeAttendanceRate } from '../attendanceRate';

describe('computeAttendanceRate', () => {
  test('returns null when there is no summary', () => {
    expect(computeAttendanceRate(null)).toBeNull();
    expect(computeAttendanceRate(undefined)).toBeNull();
  });

  test('defers to the backend-provided attendance_rate (rounded)', () => {
    // Real /attendance/summary/student/{id} body for the QA student.
    expect(
      computeAttendanceRate({
        total_days: 28, present_days: 26, absent_days: 2, late_days: 0, excused_days: 0, attendance_rate: 92.86,
      }),
    ).toBe(93);
  });

  test('mirrors the summary contract where late is NOT counted as attended', () => {
    // Backend summary rate = present / total; late is excluded from the numerator.
    expect(
      computeAttendanceRate({
        total_days: 10, present_days: 8, late_days: 2, absent_days: 0, excused_days: 0, attendance_rate: 80,
      }),
    ).toBe(80);
  });

  test('honours a backend rate of 0 instead of falling back', () => {
    expect(
      computeAttendanceRate({ total_days: 4, present_days: 0, absent_days: 4, attendance_rate: 0 }),
    ).toBe(0);
  });

  test('falls back to present/total when attendance_rate is absent (legacy shape)', () => {
    expect(computeAttendanceRate({ present_days: 9, absent_days: 1 })).toBe(90);
  });

  test('stays backward compatible with legacy present_count / total keys', () => {
    expect(computeAttendanceRate({ present_count: 5, total: 10 })).toBe(50);
  });

  test('returns 0 for a legacy shape with no recorded days', () => {
    expect(computeAttendanceRate({ present_days: 0, absent_days: 0, total_days: 0 })).toBe(0);
  });
});
