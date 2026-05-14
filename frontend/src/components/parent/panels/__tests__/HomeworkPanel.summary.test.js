import { computeParentHomeworkSummary, isSubmittedStatus } from '../HomeworkPanel';

describe('computeParentHomeworkSummary', () => {
  test('collapses submitted/graded/corrected into سلم and pending/late/missing into لم يسلم', () => {
    const assignments = [
      { status: 'submitted' },
      { status: 'graded' },
      { status: 'corrected' },
      { status: 'pending' },
      { status: 'late' },
      { status: 'missing' },
      { status: 'not_submitted' },
    ];
    const result = computeParentHomeworkSummary(assignments);
    expect(result).toEqual({ submitted: 3, notSubmitted: 4 });
  });

  test('falls back to API statistics when assignment list is empty', () => {
    const result = computeParentHomeworkSummary([], {
      submitted: 2,
      graded: 1,
      corrected: 1,
      pending: 3,
      late: 2,
    });
    expect(result).toEqual({ submitted: 4, notSubmitted: 5 });
  });

  test('handles unknown/empty statuses as not submitted', () => {
    const result = computeParentHomeworkSummary([
      { status: 'submitted' },
      { status: undefined },
      { status: 'foo' },
    ]);
    expect(result).toEqual({ submitted: 1, notSubmitted: 2 });
  });

  test('isSubmittedStatus is case-insensitive', () => {
    expect(isSubmittedStatus('SUBMITTED')).toBe(true);
    expect(isSubmittedStatus('Graded')).toBe(true);
    expect(isSubmittedStatus('LATE')).toBe(false);
  });

  test('returns zeros for empty inputs', () => {
    expect(computeParentHomeworkSummary([], {})).toEqual({ submitted: 0, notSubmitted: 0 });
    expect(computeParentHomeworkSummary()).toEqual({ submitted: 0, notSubmitted: 0 });
  });
});
