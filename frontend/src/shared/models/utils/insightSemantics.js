/**
 * Semantic classification for AI Insights cards.
 *
 * The insights endpoints return a heterogeneous list of cards: some describe
 * what the data already shows, some compare two past windows, one is a plain
 * "not enough data" notice. Rendering them all under a "Predictions &
 * Forecasts" heading — and badging them by `impact` alone — made a data-gap
 * notice read as a medium *risk* forecast with a 0% confidence gauge.
 *
 * The backend now declares `insight_kind` on every card. This module is the
 * single place that turns that machine value into UI semantics (label,
 * colour, whether a gauge is meaningful at all) so the panels can never
 * drift apart or invent a classification of their own.
 *
 * IMPORTANT: an unclassified card (no `insight_kind`, e.g. a stale cached
 * payload) resolves to `null` — we show no kind badge rather than guess.
 */

export const INSIGHT_KINDS = {
  FORECAST: 'forecast',
  TREND: 'trend',
  CURRENT_STATE: 'current_state',
  RISK_SIGNAL: 'risk_signal',
  DATA_GAP: 'data_gap',
};

const KIND_PRESENTATION = {
  forecast: {
    kind: 'forecast',
    labelKey: 'insightKindForecast',
    hintKey: 'insightKindForecastHint',
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
    ring: '#8B5CF6',
    surface: 'bg-violet-50/70 dark:bg-violet-950/20',
  },
  trend: {
    kind: 'trend',
    labelKey: 'insightKindTrend',
    hintKey: 'insightKindTrendHint',
    badge: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
    ring: '#0EA5E9',
    surface: 'bg-sky-50/70 dark:bg-sky-950/20',
  },
  current_state: {
    kind: 'current_state',
    labelKey: 'insightKindCurrentState',
    hintKey: 'insightKindCurrentStateHint',
    badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800/60 dark:text-slate-300',
    ring: '#64748B',
    surface: 'bg-slate-50/70 dark:bg-slate-900/30',
  },
  risk_signal: {
    kind: 'risk_signal',
    labelKey: 'insightKindRiskSignal',
    hintKey: 'insightKindRiskSignalHint',
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    ring: '#EF4444',
    surface: 'bg-red-50/70 dark:bg-red-950/20',
  },
  data_gap: {
    kind: 'data_gap',
    labelKey: 'insightKindDataGap',
    hintKey: 'insightKindDataGapHint',
    badge: 'bg-muted text-muted-foreground',
    ring: '#94A3B8',
    surface: 'bg-muted/30',
  },
};

const VALID_KINDS = new Set(Object.values(INSIGHT_KINDS));

/** Machine kind of a card, or null when the backend did not classify it. */
export const resolveInsightKind = (card) => {
  const kind = card?.insight_kind;
  return VALID_KINDS.has(kind) ? kind : null;
};

/** Label/colour recipe for a kind. Returns null for unclassified cards. */
export const getKindPresentation = (card) => {
  const kind = resolveInsightKind(card);
  return kind ? KIND_PRESENTATION[kind] : null;
};

const localized = (blob, isRTL) => {
  if (!blob) return null;
  if (typeof blob === 'string') return blob;
  const value = isRTL ? (blob.ar || blob.en) : (blob.en || blob.ar);
  return value || null;
};

/**
 * What (if anything) the circular gauge should show.
 *
 * - a descriptive card carries a real `measure` (e.g. attendance 92%) — show
 *   the measurement;
 * - a trend/forecast card carries a `confidence` — show it, labelled as
 *   reading reliability, not as a risk level;
 * - a data gap or a counted fact carries neither — show nothing, because a
 *   0% gauge reads as "0% likely".
 */
export const getInsightGauge = (card, isRTL) => {
  const measure = card?.measure;
  const measureValue = Number(measure?.value);
  if (measure && Number.isFinite(measureValue) && measure.unit === 'percent') {
    return {
      type: 'measure',
      value: Math.max(0, Math.min(100, Math.round(measureValue))),
      label: localized(measure.label, isRTL),
    };
  }
  const confidence = Number(card?.confidence);
  if (card?.confidence !== null && card?.confidence !== undefined
      && Number.isFinite(confidence) && confidence > 0) {
    return {
      type: 'confidence',
      value: Math.max(0, Math.min(100, Math.round(confidence))),
      label: null,
    };
  }
  return null;
};

/** "آخر 7 أيام" / "Last 7 days" — null when the card has no window. */
export const formatInsightWindow = (card, isRTL) =>
  localized(card?.time_window?.label, isRTL);

/** The records the number was computed from. */
export const getInsightBasis = (card, isRTL) => localized(card?.basis, isRTL);

/**
 * Contextual metadata of a recommendation: which classes/scope it applies
 * to, over which window, and the numeric evidence behind it.
 */
export const getRecommendationContext = (rec, isRTL) => {
  const ctx = rec?.context;
  if (!ctx) return null;
  const scopeLabel = localized(ctx.scope_label, isRTL);
  const windowLabel = localized(ctx.time_window?.label, isRTL);
  const evidence = localized(ctx.evidence, isRTL);
  if (!scopeLabel && !windowLabel && !evidence) return null;
  return {
    scopeLabel,
    windowLabel,
    evidence,
    classNames: Array.isArray(ctx.class_names) ? ctx.class_names : [],
    studentCount: Number.isFinite(Number(ctx.student_count))
      ? Number(ctx.student_count)
      : null,
  };
};
