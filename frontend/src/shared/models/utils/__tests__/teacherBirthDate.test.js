import {
  convertGregorianToHijri,
  getSaudiDateOnly,
  validateTeacherBirthDate,
} from '../teacherBirthDate';

describe('teacher birth-date calendar utilities', () => {
  test('converts Gregorian dates with the installed Umm al-Qura table', () => {
    expect(convertGregorianToHijri('2024-03-11')).toEqual({
      status: 'converted',
      hijri: { year: 1445, month: 9, day: 1 },
      iso: '1445-09-01',
    });
  });

  test('derives today from the Saudi civil day instead of the browser timezone', () => {
    expect(getSaudiDateOnly(new Date('2026-01-01T21:30:00.000Z'))).toBe('2026-01-02');
  });

  test.each(['2024-2-01', '2024-02-30', 'not-a-date'])(
    'strictly rejects malformed or impossible Gregorian value %s',
    (value) => {
      expect(validateTeacherBirthDate(value, '2026-01-02')).toEqual({ status: 'invalid' });
    }
  );

  test('allows blank as null and rejects a date after the Saudi day', () => {
    expect(validateTeacherBirthDate('', '2026-01-02')).toEqual({ status: 'blank', value: null });
    expect(validateTeacherBirthDate('2026-01-03', '2026-01-02')).toEqual({ status: 'future' });
  });

  test('reports the conversion table boundaries by finite Gregorian roundtrip', () => {
    expect(convertGregorianToHijri('1937-03-13')).toEqual({ status: 'unsupported' });
    expect(convertGregorianToHijri('1937-03-14')).toMatchObject({
      status: 'converted',
      iso: '1356-01-01',
    });
    expect(convertGregorianToHijri('2077-11-16')).toMatchObject({
      status: 'converted',
      iso: '1500-12-30',
    });
    expect(convertGregorianToHijri('2077-11-17')).toEqual({ status: 'unsupported' });
  });

  test('permits a valid old Gregorian date even when Hijri conversion is unsupported', () => {
    expect(validateTeacherBirthDate('1900-01-01', '2026-01-02')).toEqual({
      status: 'valid',
      value: '1900-01-01',
      conversion: { status: 'unsupported' },
    });
  });
});