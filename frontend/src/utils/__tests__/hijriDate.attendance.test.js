import { formatAttendanceDate } from '../hijriDate';

describe('formatAttendanceDate', () => {
  it('returns an em-dash for empty / invalid values', () => {
    expect(formatAttendanceDate(null)).toBe('—');
    expect(formatAttendanceDate(undefined)).toBe('—');
    expect(formatAttendanceDate('')).toBe('—');
    expect(formatAttendanceDate('not-a-date')).toBe('—');
  });

  it('never renders a raw ISO / server timestamp (Arabic)', () => {
    const out = formatAttendanceDate('2026-06-30T00:00:00+00:00', 'ar');
    expect(out).not.toMatch(/T00:00:00/);
    expect(out).not.toMatch(/\+00:00/);
    expect(out).not.toContain('2026-06-30');
  });

  it('shows the Gregorian date in Arabic with the Hijri marker', () => {
    const out = formatAttendanceDate('2026-06-30T00:00:00+00:00', 'ar');
    // Gregorian part is deterministic: 30 يونيو 2026 in Eastern-Arabic digits.
    expect(out).toContain('٣٠');
    expect(out).toContain('يونيو');
    expect(out).toContain('٢٠٢٦');
    // Hijri marker present (shared formatHijriDate output).
    expect(out).toContain('هـ');
  });

  it('shows the Gregorian date in English with the AH marker', () => {
    const out = formatAttendanceDate('2026-06-30T00:00:00+00:00', 'en');
    expect(out).toContain('30');
    expect(out).toContain('Jun');
    expect(out).toContain('2026');
    expect(out).toContain('AH');
    expect(out).not.toMatch(/T00:00:00/);
  });

  it('treats a date-only string the same as the full timestamp (no timezone shift)', () => {
    const fromDateOnly = formatAttendanceDate('2026-06-30', 'ar');
    const fromTimestamp = formatAttendanceDate('2026-06-30T00:00:00+00:00', 'ar');
    expect(fromDateOnly).toBe(fromTimestamp);
    // Calendar day must stay 30, never roll back to the 29th.
    expect(fromDateOnly).toContain('٣٠');
  });

  it('accepts a Date instance', () => {
    const out = formatAttendanceDate(new Date(2026, 5, 30), 'ar');
    expect(out).toContain('٣٠');
    expect(out).toContain('يونيو');
  });
});
