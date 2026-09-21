import {
  calculateTimingSummary,
  getTimingValidationTranslationKey,
  getTranslatedTimingSummary,
  localizeTimingValidationError,
  validateTimingDraft,
} from '../timingValidation';
import ar from '@/locales/ar.json';
import en from '@/locales/en.json';
import fs from 'fs';
import path from 'path';

const t = (key, values = {}) => {
  const messages = {
    timingValidationSchoolDayTooShort: `Short by ${values.shortage} minutes`,
    timingValidationInvalidTime: `Invalid ${values.field}`,
    timingFieldDayStart: 'start time',
    timingFieldBreaks: 'breaks',
  };
  return messages[key] || key;
};

describe('timing validation helpers', () => {
  it('calculates valid, exact, and short lesson-and-break totals without passing time', () => {
    expect(calculateTimingSummary({
      dayStart: '07:00', dayEnd: '13:00', periodsPerDay: 7, periodDuration: 45,
      breaks: [{ duration: 20 }, { duration: 10 }],
    })).toEqual({
      availableMinutes: 360, lessonMinutes: 315, breakMinutes: 30,
      requiredMinutes: 345, remainingMinutes: 15, shortageMinutes: 0, isValid: true,
    });
    expect(calculateTimingSummary({
      dayStart: '07:00', dayEnd: '08:00', periodsPerDay: 1, periodDuration: 45,
      breaks: [{ duration: 15 }],
    }).isValid).toBe(true);
    expect(calculateTimingSummary({
      dayStart: '07:00', dayEnd: '08:00', periodsPerDay: 1, periodDuration: 50,
      breaks: [{ duration: 15 }],
    })).toEqual(expect.objectContaining({ remainingMinutes: 0, shortageMinutes: 5, isValid: false }));
  });

  it('normalizes Arabic and Persian digits and rejects malformed or overnight times', () => {
    expect(calculateTimingSummary({
      dayStart: '٠٧:٣٠', dayEnd: '۱۳:۰۰', periodsPerDay: 1, periodDuration: 30, breaks: [],
    }).availableMinutes).toBe(330);
    expect(validateTimingDraft({ dayStart: '13:00', dayEnd: '07:00', periodsPerDay: 1, periodDuration: 30, breaks: [] }).reason)
      .toBe('invalid_time_order');
    expect(validateTimingDraft({ dayStart: '7.00', dayEnd: '13:00', periodsPerDay: 1, periodDuration: 30, breaks: [] }).reason)
      .toBe('invalid_time_format');
  });

  it.each([
    [{ periodsPerDay: 0 }, 'out_of_range', 'periodsPerDay'],
    [{ periodsPerDay: 13 }, 'out_of_range', 'periodsPerDay'],
    [{ periodDuration: 19 }, 'out_of_range', 'periodDuration'],
    [{ periodDuration: 91 }, 'out_of_range', 'periodDuration'],
    [{ breakDuration: -1 }, 'out_of_range', 'breakDuration'],
    [{ breakDuration: 61 }, 'out_of_range', 'breakDuration'],
    [{ periodsPerDay: 7, breaks: [{ afterPeriod: 0, duration: 5 }] }, 'out_of_range', 'breaks'],
    [{ periodsPerDay: 7, breaks: [{ afterPeriod: 8, duration: 5 }] }, 'out_of_range', 'breaks'],
    [{ breaks: [{ afterPeriod: 2, duration: -1 }] }, 'out_of_range', 'breaks'],
    [{ breaks: [{ afterPeriod: 2, duration: 181 }] }, 'out_of_range', 'breaks'],
  ])('matches backend numeric ranges for %o', (overrides, reason, field) => {
    const draft = {
      dayStart: '07:00', dayEnd: '14:00', periodsPerDay: 7, periodDuration: 45,
      breakDuration: 20, workDays: { sunday: true }, breaks: [], ...overrides,
    };
    expect(validateTimingDraft(draft)).toEqual(expect.objectContaining({ reason, field }));
  });

  it('treats null break duration as inherited while validating explicit zero', () => {
    const base = {
      dayStart: '07:00', dayEnd: '14:00', periodsPerDay: 7, periodDuration: 45,
      breakDuration: 20, workDays: { sunday: true },
    };
    expect(validateTimingDraft({ ...base, breaks: [{ afterPeriod: 2, duration: null }] })).toBeNull();
    expect(validateTimingDraft({ ...base, breaks: [{ afterPeriod: 2, duration: 0 }] })).toBeNull();
  });

  it('counts multiple edited breaks once, inheriting null while preserving explicit zero', () => {
    const base = { dayStart: '07:00', dayEnd: '08:00', periodsPerDay: 1, periodDuration: 30, breakDuration: 20 };
    expect(calculateTimingSummary({ ...base, breaks: [{ duration: null }, { duration: 0 }, { duration: 12 }] }).breakMinutes).toBe(32);
    expect(calculateTimingSummary({ ...base, breaks: [{ duration: 5 }] }).breakMinutes).toBe(5);
    expect(calculateTimingSummary({ ...base, breaks: [] }).breakMinutes).toBe(0);
  });

  it('localizes structured backend details rather than leaking the fallback English message', () => {
    expect(localizeTimingValidationError({
      code: 'TIMING_VALIDATION_ERROR',
      reason: 'school_day_too_short',
      field: 'breaks',
      shortage_minutes: 25,
      message: 'School day is too short',
    }, t)).toBe('Short by 25 minutes');
    expect(localizeTimingValidationError({
      code: 'TIMING_VALIDATION_ERROR', reason: 'invalid_time_format', field: 'dayStart',
      message: 'Invalid time',
    }, t)).toBe('Invalid start time');
  });

  it('builds the same live summary with Arabic and English labels', () => {
    const summary = calculateTimingSummary({
      dayStart: '07:00', dayEnd: '08:00', periodsPerDay: 1, periodDuration: 45, breaks: [],
    });
    const translate = locale => key => locale[key];
    expect(getTranslatedTimingSummary(summary, translate(en)).map(item => item.label))
      .toEqual(['Available', 'Lesson minutes', 'Break minutes', 'Required', 'Remaining']);
    expect(getTranslatedTimingSummary(summary, translate(ar)).map(item => item.label))
      .toEqual(['الوقت المتاح', 'دقائق الحصص', 'دقائق الاستراحات', 'الوقت المطلوب', 'الوقت المتبقي']);
  });

  it('has an explicit Arabic and English localization for every backend timing reason', () => {
    const servicePaths = [
      '../backend/src/modules/schools/services/school_settings_service.py',
      '../backend/src/modules/schools/services/time_slots_service.py',
    ];
    const sources = servicePaths.map(file => fs.readFileSync(path.resolve(process.cwd(), file), 'utf8'));
    const reasons = new Set();
    for (const match of sources[0].matchAll(/_timing_error\(\s*["']([^"']+)["']/g)) reasons.add(match[1]);
    for (const match of sources[1].matchAll(/["']reason["']\s*:\s*["']([^"']+)["']/g)) {
      if (sources[1].slice(Math.max(0, match.index - 300), match.index).includes('TIMING_VALIDATION_ERROR')) reasons.add(match[1]);
    }

    expect([...reasons].sort()).toEqual(expect.arrayContaining([
      'unsupported_break_day',
      'draft_sessions_use_removed_periods',
    ]));
    for (const reason of reasons) {
      const key = getTimingValidationTranslationKey(reason);
      expect(key).not.toBe('timingValidationGeneric');
      expect(ar[key]).toEqual(expect.any(String));
      expect(en[key]).toEqual(expect.any(String));
      expect(ar[key]).not.toBe(en[key]);
    }
  });
});