import {
  convertGregorianToHijri,
  convertHijriToGregorian,
  getSaudiDateOnly,
  parseHijriDate,
  validateTeacherBirthDate,
  validateTeacherHijriBirthDate,
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
    expect(convertGregorianToHijri('1924-07-31')).toEqual({ status: 'unsupported' });
    expect(convertGregorianToHijri('1924-08-01')).toMatchObject({
      status: 'converted',
      iso: '1343-01-01',
    });
    expect(convertGregorianToHijri('2077-11-16')).toMatchObject({
      status: 'converted',
      iso: '1500-12-30',
    });
    expect(convertGregorianToHijri('2077-11-17')).toEqual({ status: 'unsupported' });
  });

  test('matches authoritative Python table dates where the installed JS package differs', () => {
    expect(convertHijriToGregorian('01/06/1427')).toMatchObject({
      status: 'converted',
      iso: '2006-06-27',
    });
    expect(convertHijriToGregorian('01/06/1446')).toMatchObject({
      status: 'converted',
      iso: '2024-12-02',
    });
    expect(convertGregorianToHijri('2024-12-02')).toMatchObject({
      status: 'converted',
      iso: '1446-06-01',
    });
  });

  test('permits a valid old Gregorian date even when Hijri conversion is unsupported', () => {
    expect(validateTeacherBirthDate('1900-01-01', '2026-01-02')).toEqual({
      status: 'valid',
      value: '1900-01-01',
      conversion: { status: 'unsupported' },
    });
  });

  test('parses DD/MM/YYYY Hijri input including Arabic digits', () => {
    expect(parseHijriDate('01/09/1445')).toEqual({ year: 1445, month: 9, day: 1 });
    expect(parseHijriDate('٠١/٠٩/١٤٤٥')).toEqual({ year: 1445, month: 9, day: 1 });
    expect(parseHijriDate('1445-09-01')).toBeNull();
  });

  test('converts a valid Umm al-Qura Hijri date to canonical Gregorian', () => {
    expect(convertHijriToGregorian('01/09/1445')).toEqual({
      status: 'converted',
      gregorian: { year: 2024, month: 3, day: 11 },
      iso: '2024-03-11',
      hijri: { year: 1445, month: 9, day: 1 },
    });
  });

  test.each(['31/09/1445', '01/13/1445', '1/09/1445', 'xx/09/1445', '01/01/1342'])(
    'rejects impossible, malformed, or unsupported Hijri input %s',
    (value) => {
      expect(validateTeacherHijriBirthDate(value, '2026-01-02').status).toBe('invalid');
    }
  );

  test('allows blank Hijri input and rejects a Hijri date converting after the Saudi day', () => {
    expect(validateTeacherHijriBirthDate('', '2026-01-02')).toEqual({
      status: 'blank',
      value: null,
    });
    expect(validateTeacherHijriBirthDate('14/07/1447', '2026-01-02')).toEqual({
      status: 'future',
    });
  });
});