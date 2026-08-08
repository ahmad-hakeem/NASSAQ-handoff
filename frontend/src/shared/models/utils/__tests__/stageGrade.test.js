import {
  EDUCATION_STAGES,
  normalizeStage,
  gradeBelongsToStage,
  filterGradesByStage,
  availableStagesFromGrades,
} from '../stageGrade';

describe('stageGrade helper', () => {
  describe('normalizeStage', () => {
    it.each([
      ['primary', 'primary'],
      ['Middle', 'middle'],
      ['HIGH', 'high'],
      ['ابتدائي', 'primary'],
      ['المرحلة المتوسطة', 'middle'],
      ['ثانوي', 'high'],
      [3, 'primary'],
      ['8', 'middle'],
      [11, 'high'],
      [null, null],
      ['', null],
      ['kindergarten', null],
    ])('coerces %p → %p', (input, expected) => {
      expect(normalizeStage(input)).toBe(expected);
    });

    it('derives stage from a grade row object', () => {
      expect(normalizeStage({ stage: 'ابتدائي' })).toBe('primary');
      expect(normalizeStage({ stage: null, grade: 8 })).toBe('middle');
      expect(normalizeStage({ order: 11 })).toBe('high');
      expect(normalizeStage({})).toBeNull();
    });
  });

  describe('gradeBelongsToStage', () => {
    it('matches when stage and grade buckets agree', () => {
      expect(gradeBelongsToStage({ stage: 'primary', grade: 3 }, 'primary')).toBe(true);
      expect(gradeBelongsToStage({ stage: 'middle', grade: 8 }, 'middle')).toBe(true);
    });
    it('rejects when buckets disagree', () => {
      expect(gradeBelongsToStage({ stage: 'middle', grade: 8 }, 'primary')).toBe(false);
      expect(gradeBelongsToStage({ grade: 11 }, 'middle')).toBe(false);
    });
    it('passes through when no stage filter supplied', () => {
      expect(gradeBelongsToStage({ grade: 8 }, null)).toBe(true);
    });
  });

  describe('filterGradesByStage', () => {
    const grades = [
      { id: 'g1', name_ar: 'الأول الابتدائي', stage: 'ابتدائي', grade: 1 },
      { id: 'g6', name_ar: 'السادس الابتدائي', stage: 'ابتدائي', grade: 6 },
      { id: 'g7', name_ar: 'الأول المتوسط', stage: 'متوسط', grade: 7 },
      { id: 'g10', name_ar: 'الأول الثانوي', stage: 'ثانوي', grade: 10 },
    ];

    it('filters to only the chosen stage', () => {
      expect(filterGradesByStage(grades, 'primary').map(g => g.id)).toEqual(['g1', 'g6']);
      expect(filterGradesByStage(grades, 'middle').map(g => g.id)).toEqual(['g7']);
      expect(filterGradesByStage(grades, 'high').map(g => g.id)).toEqual(['g10']);
    });

    it('returns empty when no stage selected', () => {
      expect(filterGradesByStage(grades, null)).toEqual([]);
      expect(filterGradesByStage(grades, '')).toEqual([]);
    });

    it('handles missing/empty input safely', () => {
      expect(filterGradesByStage(null, 'primary')).toEqual([]);
      expect(filterGradesByStage(undefined, 'primary')).toEqual([]);
    });
  });

  describe('availableStagesFromGrades', () => {
    it('returns only stages with at least one grade row', () => {
      const grades = [
        { id: 'g1', stage: 'ابتدائي', grade: 1 },
        { id: 'g8', stage: 'متوسط', grade: 8 },
      ];
      const ids = availableStagesFromGrades(grades).map(s => s.id);
      expect(ids).toEqual(['primary', 'middle']);
    });

    it('returns [] for empty input', () => {
      expect(availableStagesFromGrades([])).toEqual([]);
    });
  });

  it('exposes the three canonical stages in order', () => {
    expect(EDUCATION_STAGES.map(s => s.id)).toEqual(['primary', 'middle', 'high']);
  });
});
