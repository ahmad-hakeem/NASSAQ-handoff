const ARABIC_DIGITS = '٠١٢٣٤٥٦٧٨٩';
const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹';

export function normalizeLocalizedDigits(value) {
  return String(value ?? '').replace(/[٠-٩۰-۹]/g, digit => {
    const arabicIndex = ARABIC_DIGITS.indexOf(digit);
    return String(arabicIndex >= 0 ? arabicIndex : PERSIAN_DIGITS.indexOf(digit));
  });
}

export function parseLocalTime(value) {
  const normalized = normalizeLocalizedDigits(value);
  const match = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(normalized);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

const finiteNumber = value => {
  if (value === null || value === undefined || value === '') return 0;
  const number = Number(normalizeLocalizedDigits(value));
  return Number.isFinite(number) ? number : 0;
};

const strictInteger = value => {
  if (typeof value === 'boolean' || value === null || value === undefined) return null;
  const normalized = normalizeLocalizedDigits(value).trim();
  if (!/^[+-]?\d+$/.test(normalized)) return null;
  const number = Number(normalized);
  return Number.isSafeInteger(number) ? number : null;
};

const integerRangeError = (value, field, minimum, maximum) => {
  const parsed = strictInteger(value);
  if (parsed === null) return { reason: 'invalid_integer', field };
  if (parsed < minimum || parsed > maximum) {
    return { reason: 'out_of_range', field, minimum, maximum, actual: parsed };
  }
  return null;
};

export function calculateTimingSummary({ dayStart, dayEnd, periodsPerDay, periodDuration, breakDuration, breaks = [] }) {
  const start = parseLocalTime(dayStart);
  const end = parseLocalTime(dayEnd);
  const availableMinutes = start === null || end === null || end <= start ? 0 : end - start;
  const lessonMinutes = finiteNumber(periodsPerDay) * finiteNumber(periodDuration);
  const breakMinutes = (Array.isArray(breaks) ? breaks : [])
    .reduce((total, item) => total + finiteNumber(
      item?.duration == null ? breakDuration : item.duration,
    ), 0);
  const requiredMinutes = lessonMinutes + breakMinutes;
  const difference = availableMinutes - requiredMinutes;
  return {
    availableMinutes,
    lessonMinutes,
    breakMinutes,
    requiredMinutes,
    remainingMinutes: Math.max(0, difference),
    shortageMinutes: Math.max(0, -difference),
    isValid: start !== null && end !== null && end > start && difference >= 0,
  };
}

export function getTranslatedTimingSummary(summary, t) {
  return [
    { key: 'available', label: t('timingSummaryAvailable'), value: summary.availableMinutes },
    { key: 'lessons', label: t('timingSummaryLessons'), value: summary.lessonMinutes },
    { key: 'breaks', label: t('timingSummaryBreaks'), value: summary.breakMinutes },
    { key: 'required', label: t('timingSummaryRequired'), value: summary.requiredMinutes },
    summary.isValid
      ? { key: 'remaining', label: t('timingSummaryRemaining'), value: summary.remainingMinutes }
      : { key: 'shortage', label: t('timingSummaryShortage'), value: summary.shortageMinutes },
  ];
}

export function validateTimingDraft(draft) {
  const start = parseLocalTime(draft?.dayStart);
  const end = parseLocalTime(draft?.dayEnd);
  if (start === null) return { reason: 'invalid_time_format', field: 'dayStart' };
  if (end === null) return { reason: 'invalid_time_format', field: 'dayEnd' };
  if (start === 0) return { reason: 'midnight_not_allowed', field: 'dayStart' };
  if (end === 0) return { reason: 'midnight_not_allowed', field: 'dayEnd' };
  if (end <= start) return { reason: 'invalid_time_order', field: 'dayEnd' };
  const periodCountError = integerRangeError(draft?.periodsPerDay, 'periodsPerDay', 1, 12);
  if (periodCountError) return periodCountError;
  const lessonDurationError = integerRangeError(draft?.periodDuration, 'periodDuration', 20, 90);
  if (lessonDurationError) return lessonDurationError;
  const baseBreakError = integerRangeError(draft?.breakDuration, 'breakDuration', 0, 60);
  if (baseBreakError) return baseBreakError;
  if (!Object.values(draft?.workDays || {}).some(Boolean)) return { reason: 'working_days_required', field: 'workingDays' };
  const daySpecific = (draft?.breaks || []).find(item => item?.day && item.day !== 'all');
  if (daySpecific) return { reason: 'unsupported_break_day', field: 'breaks' };
  const positions = new Set();
  for (const item of draft?.breaks || []) {
    const positionError = integerRangeError(item?.afterPeriod, 'breaks', 1, strictInteger(draft.periodsPerDay));
    if (positionError) return positionError;
    if (item?.duration !== null) {
      const durationError = integerRangeError(item?.duration, 'breaks', 0, 180);
      if (durationError) return durationError;
    }
    const position = strictInteger(item.afterPeriod);
    if (positions.has(position)) return { reason: 'duplicate_break_position', field: 'breaks' };
    positions.add(position);
  }
  const summary = calculateTimingSummary(draft);
  if (!summary.isValid) return { reason: 'school_day_too_short', field: 'dayEnd', ...summary };
  return null;
}

const FIELD_KEYS = {
  dayStart: 'timingFieldDayStart',
  day_start: 'timingFieldDayStart',
  dayEnd: 'timingFieldDayEnd',
  day_end: 'timingFieldDayEnd',
  start_time: 'timingFieldDayStart',
  end_time: 'timingFieldDayEnd',
  periodsPerDay: 'timingFieldPeriodsPerDay',
  periods_per_day: 'timingFieldPeriodsPerDay',
  periodDuration: 'timingFieldPeriodDuration',
  period_duration: 'timingFieldPeriodDuration',
  breakDuration: 'timingFieldBreaks',
  break_duration: 'timingFieldBreaks',
  workingDays: 'timingFieldWorkingDays',
  working_days: 'timingFieldWorkingDays',
  breaks: 'timingFieldBreaks',
};

const REASON_KEYS = {
  invalid_time_format: 'timingValidationInvalidTime',
  midnight_not_allowed: 'timingValidationMidnight',
  day_end_not_after_start: 'timingValidationTimeOrder',
  invalid_time_order: 'timingValidationTimeOrder',
  school_day_too_short: 'timingValidationSchoolDayTooShort',
  must_be_integer: 'timingValidationInteger',
  invalid_integer: 'timingValidationInteger',
  out_of_range: 'timingValidationRange',
  working_days_required: 'timingValidationWorkingDays',
  invalid_working_days: 'timingValidationWorkingDays',
  invalid_weekday: 'timingValidationWorkingDays',
  invalid_weekday_value: 'timingValidationWorkingDays',
  no_working_days: 'timingValidationWorkingDays',
  duplicate_weekday: 'timingValidationDuplicateWeekday',
  invalid_breaks: 'timingValidationBreaks',
  invalid_break: 'timingValidationBreaks',
  invalid_break_position: 'timingValidationBreaks',
  missing_break_position: 'timingValidationMissingBreakPosition',
  duplicate_break_position: 'timingValidationDuplicateBreakPosition',
  occupied_draft_periods_removed: 'timingValidationOccupiedPeriods',
  removed_periods_occupied: 'timingValidationOccupiedPeriods',
  draft_sessions_use_removed_periods: 'timingValidationOccupiedPeriods',
  day_specific_breaks_unsupported: 'timingValidationDaySpecificBreaks',
  unsupported_break_day: 'timingValidationDaySpecificBreaks',
};

export function getTimingValidationTranslationKey(reason) {
  return REASON_KEYS[reason] || 'timingValidationGeneric';
}

export function localizeTimingValidationError(detail, t) {
  if (!detail || detail.code !== 'TIMING_VALIDATION_ERROR') return null;
  const metadata = detail.metadata || {};
  const fieldKey = FIELD_KEYS[detail.field]
    || (String(detail.field).startsWith('breaks[') ? 'timingFieldBreaks' : 'timingFieldSettings');
  const field = t(fieldKey);
  const reasonKey = getTimingValidationTranslationKey(detail.reason);
  return t(reasonKey, {
    field,
    min: detail.minimum ?? detail.min ?? metadata.minimum ?? metadata.min ?? '',
    max: detail.maximum ?? detail.max ?? metadata.maximum ?? metadata.max ?? '',
    available: detail.available_minutes ?? metadata.available_minutes ?? '',
    lessons: detail.lesson_minutes ?? metadata.lesson_minutes ?? '',
    breaks: detail.break_minutes ?? metadata.break_minutes ?? '',
    required: detail.required_minutes ?? metadata.required_minutes ?? '',
    shortage: detail.shortage_minutes ?? metadata.shortage_minutes ?? '',
  });
}