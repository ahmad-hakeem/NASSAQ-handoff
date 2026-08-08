import {
  resolveInsightKind,
  getKindPresentation,
  getInsightGauge,
  formatInsightWindow,
  getInsightBasis,
  getRecommendationContext,
} from '../insightSemantics';

describe('insight semantics', () => {
  it('classifies a data-gap card as a data gap, never a risk level', () => {
    const card = {
      insight_kind: 'data_gap',
      impact: 'info',
      confidence: null,
      title: { ar: 'بيانات حضور غير كافية' },
    };
    expect(resolveInsightKind(card)).toBe('data_gap');
    expect(getKindPresentation(card).labelKey).toBe('insightKindDataGap');
    // The old UI showed a 0% gauge here, which reads as "0% likely".
    expect(getInsightGauge(card, true)).toBeNull();
  });

  it('never invents a classification for an unclassified card', () => {
    const legacy = { impact: 'medium', confidence: 70, title: { ar: 'x' } };
    expect(resolveInsightKind(legacy)).toBeNull();
    expect(getKindPresentation(legacy)).toBeNull();
    expect(resolveInsightKind(undefined)).toBeNull();
    expect(getInsightGauge(undefined, true)).toBeNull();
  });

  it('shows confidence for a trend card', () => {
    const card = { insight_kind: 'trend', confidence: 78 };
    expect(getKindPresentation(card).labelKey).toBe('insightKindTrend');
    expect(getInsightGauge(card, true)).toEqual({
      type: 'confidence', value: 78, label: null,
    });
  });

  it('prefers a real measurement over a confidence number', () => {
    const card = {
      insight_kind: 'current_state',
      confidence: null,
      measure: { value: 91.6, unit: 'percent', label: { ar: 'نسبة الحضور', en: 'Attendance rate' } },
    };
    const gauge = getInsightGauge(card, true);
    expect(gauge.type).toBe('measure');
    expect(gauge.value).toBe(92);
    expect(gauge.label).toBe('نسبة الحضور');
    expect(getInsightGauge(card, false).label).toBe('Attendance rate');
  });

  it('ignores a non-percent measure unit', () => {
    const card = { insight_kind: 'risk_signal', measure: { value: 3, unit: 'students' } };
    expect(getInsightGauge(card, true)).toBeNull();
  });

  it('exposes the time window and evidence of a card', () => {
    const card = {
      insight_kind: 'trend',
      time_window: { direction: 'past', days: 7, label: { ar: 'آخر 7 أيام', en: 'Last 7 days' } },
      basis: { ar: 'مقارنة 40 سجل حضور', en: 'Comparing 40 attendance records' },
    };
    expect(formatInsightWindow(card, true)).toBe('آخر 7 أيام');
    expect(formatInsightWindow(card, false)).toBe('Last 7 days');
    expect(getInsightBasis(card, true)).toBe('مقارنة 40 سجل حضور');
    expect(formatInsightWindow({}, true)).toBeNull();
    expect(getInsightBasis({}, true)).toBeNull();
  });

  it('surfaces which classes a recommendation applies to', () => {
    const rec = {
      context: {
        scope_level: 'classroom',
        scope_label: { ar: 'فصولك: 8أ، 8ب', en: 'your classes 8A, 8B' },
        class_names: ['8أ', '8ب'],
        student_count: 42,
        time_window: { direction: 'past', days: 30, label: { ar: 'آخر 30 يوماً', en: 'Last 30 days' } },
        evidence: { ar: '0 تقييم مسجّل', en: '0 assessments recorded' },
      },
    };
    const ctx = getRecommendationContext(rec, true);
    expect(ctx.scopeLabel).toBe('فصولك: 8أ، 8ب');
    expect(ctx.windowLabel).toBe('آخر 30 يوماً');
    expect(ctx.evidence).toBe('0 تقييم مسجّل');
    expect(ctx.classNames).toEqual(['8أ', '8ب']);
    expect(ctx.studentCount).toBe(42);
    expect(getRecommendationContext({}, true)).toBeNull();
  });
});
