import {
  TEACHER_UMM_AL_QURA_GREGORIAN_RANGE,
  TEACHER_UMM_AL_QURA_HIJRI_OFFSET,
  TEACHER_UMM_AL_QURA_HIJRI_RANGE,
  TEACHER_UMM_AL_QURA_MONTH_STARTS,
} from './teacherUmmAlQuraData';

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const HIJRI_DATE_PATTERN = /^(\d{2})\/(\d{2})\/(\d{4})$/;
const SAUDI_TIME_ZONE = 'Asia/Riyadh';
const RJD_AT_UNIX_EPOCH = 40588;
const MILLISECONDS_PER_DAY = 86400000;

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

export const normalizeHijriDigits = (value) => String(value ?? '')
  .replace(/[٠-٩]/g, (digit) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit)))
  .replace(/[۰-۹]/g, (digit) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)));

export const parseHijriDate = (value) => {
  if (typeof value !== 'string') return null;
  const match = HIJRI_DATE_PATTERN.exec(normalizeHijriDigits(value));
  if (!match) return null;
  return {
    year: Number(match[3]),
    month: Number(match[2]),
    day: Number(match[1]),
  };
};

const gregorianToRjd = ({ year, month, day }) =>
  Math.floor(Date.UTC(year, month - 1, day) / MILLISECONDS_PER_DAY) + RJD_AT_UNIX_EPOCH;

const rjdToGregorian = (rjd) => {
  const date = new Date((rjd - RJD_AT_UNIX_EPOCH) * MILLISECONDS_PER_DAY);
  return {
    year: date.getUTCFullYear(),
    month: date.getUTCMonth() + 1,
    day: date.getUTCDate(),
  };
};

const formatGregorianIso = ({ year, month, day }) =>
  `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

const findHijriMonthIndex = (rjd) => {
  let low = 0;
  let high = TEACHER_UMM_AL_QURA_MONTH_STARTS.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (TEACHER_UMM_AL_QURA_MONTH_STARTS[middle] <= rjd) low = middle + 1;
    else high = middle;
  }
  return low - 1;
};

export const convertGregorianToHijri = (value) => {
  const gregorian = parseGregorianDateOnly(value);
  if (!gregorian) return { status: 'invalid' };

  const minimum = formatGregorianIso({
    year: TEACHER_UMM_AL_QURA_GREGORIAN_RANGE[0][0],
    month: TEACHER_UMM_AL_QURA_GREGORIAN_RANGE[0][1],
    day: TEACHER_UMM_AL_QURA_GREGORIAN_RANGE[0][2],
  });
  const maximum = formatGregorianIso({
    year: TEACHER_UMM_AL_QURA_GREGORIAN_RANGE[1][0],
    month: TEACHER_UMM_AL_QURA_GREGORIAN_RANGE[1][1],
    day: TEACHER_UMM_AL_QURA_GREGORIAN_RANGE[1][2],
  });
  if (value < minimum || value > maximum) return { status: 'unsupported' };

  const rjd = gregorianToRjd(gregorian);
  const index = findHijriMonthIndex(rjd);
  if (index < 0 || index >= TEACHER_UMM_AL_QURA_MONTH_STARTS.length - 1) {
    return { status: 'unsupported' };
  }
  const months = index + TEACHER_UMM_AL_QURA_HIJRI_OFFSET;
  const year = Math.floor(months / 12) + 1;
  const month = (months % 12) + 1;
  const day = rjd - TEACHER_UMM_AL_QURA_MONTH_STARTS[index] + 1;
  return {
    status: 'converted',
    hijri: { year, month, day },
    iso: `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
  };
};

export const convertHijriToGregorian = (value) => {
  const hijri = parseHijriDate(value);
  if (!hijri) return { status: 'invalid' };
  const [[minimumYear], [maximumYear]] = TEACHER_UMM_AL_QURA_HIJRI_RANGE;
  if (
    hijri.year < minimumYear ||
    hijri.year > maximumYear ||
    hijri.month < 1 ||
    hijri.month > 12
  ) {
    return { status: 'invalid' };
  }
  const index = ((hijri.year - 1) * 12 + hijri.month - 1) - TEACHER_UMM_AL_QURA_HIJRI_OFFSET;
  const start = TEACHER_UMM_AL_QURA_MONTH_STARTS[index];
  const next = TEACHER_UMM_AL_QURA_MONTH_STARTS[index + 1];
  if (!Number.isFinite(start) || !Number.isFinite(next)) return { status: 'invalid' };
  const monthLength = next - start;
  if (hijri.day < 1 || hijri.day > monthLength) return { status: 'invalid' };

  const gregorian = rjdToGregorian(start + hijri.day - 1);
  return {
    status: 'converted',
    gregorian,
    iso: formatGregorianIso(gregorian),
    hijri,
  };
};

export const validateTeacherHijriBirthDate = (value, today = getSaudiDateOnly()) => {
  if (value === '' || value === null || value === undefined) {
    return { status: 'blank', value: null };
  }
  const conversion = convertHijriToGregorian(value);
  if (conversion.status !== 'converted') return { status: 'invalid' };
  if (conversion.iso > today) return { status: 'future' };
  return { status: 'valid', value: conversion.iso, conversion };
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