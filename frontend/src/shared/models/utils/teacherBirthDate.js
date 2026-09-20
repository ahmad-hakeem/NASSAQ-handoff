import { toGregorian, toHijri } from 'hijri-converter';

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const SAUDI_TIME_ZONE = 'Asia/Riyadh';

const isLeapYear = (year) =>
  year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);

const daysInMonth = (year, month) => {
  if (month === 2) return isLeapYear(year) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
};

export const parseGregorianDateOnly = (value) => {
  if (typeof value !== 'string') return null;
  const match = ISO_DATE_PATTERN.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > daysInMonth(year, month)
  ) {
    return null;
  }
  return { year, month, day };
};

export const getSaudiDateOnly = (date = new Date()) => {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: SAUDI_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
};

export const convertGregorianToHijri = (value) => {
  const gregorian = parseGregorianDateOnly(value);
  if (!gregorian) return { status: 'invalid' };

  try {
    const converted = toHijri(gregorian.year, gregorian.month, gregorian.day);
    const hijriValues = [converted?.hy, converted?.hm, converted?.hd];
    if (!hijriValues.every(Number.isFinite)) return { status: 'unsupported' };

    const roundtrip = toGregorian(converted.hy, converted.hm, converted.hd);
    const roundtripValues = [roundtrip?.gy, roundtrip?.gm, roundtrip?.gd];
    if (
      !roundtripValues.every(Number.isFinite) ||
      roundtrip.gy !== gregorian.year ||
      roundtrip.gm !== gregorian.month ||
      roundtrip.gd !== gregorian.day
    ) {
      return { status: 'unsupported' };
    }

    return {
      status: 'converted',
      hijri: { year: converted.hy, month: converted.hm, day: converted.hd },
      iso: `${String(converted.hy).padStart(4, '0')}-${String(converted.hm).padStart(2, '0')}-${String(converted.hd).padStart(2, '0')}`,
    };
  } catch {
    return { status: 'unsupported' };
  }
};

export const validateTeacherBirthDate = (value, today = getSaudiDateOnly()) => {
  if (value === '' || value === null || value === undefined) {
    return { status: 'blank', value: null };
  }
  if (!parseGregorianDateOnly(value)) return { status: 'invalid' };
  if (value > today) return { status: 'future' };
  return {
    status: 'valid',
    value,
    conversion: convertGregorianToHijri(value),
  };
};