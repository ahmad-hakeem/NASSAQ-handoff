import React, { useEffect, useRef } from 'react';
import {
  Award, Star, TrendingDown, BookOpen, Lightbulb,
  FileText, AlertCircle, RefreshCw, Calendar, Sparkles, GraduationCap,
  Clock, CheckCircle2,
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';
import { getPose } from '../../components/hakim/hakimPoses';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';

/* -------------------------------------------------------------------------- */
/* Task #324 — Parent home Weekly Story redesign                              */
/*                                                                            */
/* The old layout (two empty KPI tiles + recharts bar + generic banner)       */
/* is replaced by a small ranked grid of compact event cards plus a separate  */
/* "نصيحة الأسبوع" advice card. Cards are populated from the new backend     */
/* `cards: [{kind, tone, icon, title_ar, value, metric}]` payload; the        */
/* advice card reads `advice.text_ar` (omitted gracefully when Hakim is       */
/* unavailable). Partial weeks render whatever cards exist; only a truly     */
/* empty week falls back to the "insufficient data" message.                  */
/* -------------------------------------------------------------------------- */

const HakimAvatar = ({ pose = 'friendly-greeting', size = 44, ringed = true }) => (
  <div
    className={`relative shrink-0 rounded-2xl overflow-hidden bg-gradient-to-br from-brand-turquoise/15 to-brand-navy/10 dark:from-brand-turquoise/20 dark:to-brand-navy/30 ${
      ringed ? 'shadow-md shadow-brand-turquoise/25 ring-1 ring-brand-turquoise/25 dark:ring-brand-turquoise/40' : ''
    }`}
    style={{ width: size, height: size }}
  >
    <img
      src={getPose(pose)}
      alt=""
      aria-hidden="true"
      loading="lazy"
      className="w-full h-full object-cover object-top select-none pointer-events-none"
      draggable={false}
    />
  </div>
);

const HakimChip = ({ label }) => (
  <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-turquoise/12 dark:bg-brand-turquoise/20 text-brand-turquoise ps-1 pe-2 py-0.5 text-[10px] font-bold border border-brand-turquoise/25 dark:border-brand-turquoise/40 font-cairo">
    <span className="w-4 h-4 rounded-full overflow-hidden bg-card">
      <img
        src={getPose('friendly-greeting')}
        alt=""
        aria-hidden="true"
        loading="lazy"
        className="w-full h-full object-cover object-top"
        draggable={false}
      />
    </span>
    {label}
    <Sparkles className="w-2.5 h-2.5 opacity-70" />
  </span>
);

const HakimAttributionLine = ({ children }) => (
  <p className="text-[11px] text-brand-navy/70 dark:text-muted-foreground leading-relaxed font-tajawal flex items-start gap-1.5">
    <Sparkles className="w-3 h-3 text-brand-turquoise mt-[2px] shrink-0" />
    <span>{children}</span>
  </p>
);

/* Stable lucide icon registry — backend ships icon names as strings so the  */
/* FE can swap them without coupling the API to lucide internals.            */
const ICONS = {
  Star, Award, Sparkles, GraduationCap, BookOpen, FileText,
  Clock, AlertCircle, TrendingDown, CheckCircle2,
};

const TONE_STYLES = {
  positive: {
    iconWrap:  'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300',
    valueText: 'text-emerald-700 dark:text-emerald-300',
  },
  concern: {
    iconWrap:  'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300',
    valueText: 'text-amber-700 dark:text-amber-300',
  },
  academic: {
    iconWrap:  'bg-brand-turquoise/15 dark:bg-brand-turquoise/25 text-brand-turquoise',
    valueText: 'text-brand-turquoise',
  },
};

const HighlightCard = ({ card }) => {
  const Icon = ICONS[card.icon] || Star;
  const tone = TONE_STYLES[card.tone] || TONE_STYLES.positive;
  return (
    <div
      className="relative rounded-2xl bg-card border border-border/70 dark:border-border p-3.5 flex items-start gap-3 shadow-sm hover:shadow-md transition-shadow"
      data-testid="weekly-story-card"
      data-card-kind={card.kind}
      data-card-tone={card.tone}
    >
      <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${tone.iconWrap}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-cairo font-bold text-foreground leading-snug">
          {card.title_ar}
        </p>
        {card.value && (
          <p className={`text-[11px] font-tajawal mt-0.5 tabular-nums ${tone.valueText}`}>
            {card.value}
          </p>
        )}
      </div>
    </div>
  );
};

const AdviceCard = ({ text }) => {
  const { t } = useTranslation();
  return (
    <div
      className="rounded-2xl bg-brand-purple/8 dark:bg-brand-purple/15 border border-brand-purple/25 dark:border-brand-purple/40 p-4 flex items-start gap-3"
      data-testid="weekly-story-advice"
    >
      <div className="w-10 h-10 rounded-xl bg-brand-purple/20 dark:bg-brand-purple/30 text-brand-purple dark:text-white flex items-center justify-center shrink-0">
        <Lightbulb className="w-5 h-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-cairo font-bold text-brand-purple dark:text-white/90 mb-1">
          {t('hakimWeeklyAdviceTitle')}
        </p>
        <p className="text-sm text-foreground font-tajawal leading-relaxed">
          {text}
        </p>
      </div>
    </div>
  );
};

const SectionLabel = ({ icon: Icon, label }) => (
  <div className="flex items-center gap-1.5 text-[11px] font-bold font-cairo text-muted-foreground uppercase tracking-wide">
    <Icon className="w-3.5 h-3.5" />
    {label}
  </div>
);

const WeeklyStory = ({ data, loading, error, onRetry }) => {
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const lastErrorShownRef = useRef(null);

  // Surface load errors through NassaqAlertDialog (per spec + project preference
  // to avoid native alert/toast.error). Fire only on the rising edge so a single
  // failure shows exactly one dialog, and reset when the error clears.
  useEffect(() => {
    if (error) {
      const sig = String(error?.message || error || 'weekly-story-error');
      if (lastErrorShownRef.current !== sig) {
        lastErrorShownRef.current = sig;
        nassaqError(t('hakimInsightsUnavailable'), {
          description: t('checkConnectionAndRetry'),
        });
      }
    } else {
      lastErrorShownRef.current = null;
    }
  }, [error, nassaqError, t]);

  if (loading) {
    return (
      <HakimShell>
        <HakimHeader subtitle={t('hakimIsAnalyzingData')} subtitleAnimated pose="ai-thinking" />
        <div className="p-5 space-y-4 bg-card animate-pulse" data-testid="weekly-story-skeleton">
          <div className="grid grid-cols-2 gap-3">
            <div className="h-20 rounded-2xl bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border" />
            <div className="h-20 rounded-2xl bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border" />
            <div className="h-20 rounded-2xl bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border" />
            <div className="h-20 rounded-2xl bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border" />
          </div>
          <div className="h-20 rounded-2xl bg-brand-purple/[0.06] dark:bg-brand-purple/[0.10] border border-brand-purple/20" />
        </div>
      </HakimShell>
    );
  }

  if (error) {
    return (
      <HakimShell>
        <div className="text-center py-8 px-5 bg-card">
          <div className="mx-auto mb-3 w-fit">
            <HakimAvatar pose="support" size={56} />
          </div>
          <p className="text-sm font-bold text-foreground mb-1 font-cairo">{t('hakimInsightsUnavailable')}</p>
          <p className="text-xs text-muted-foreground font-tajawal mb-4 max-w-sm mx-auto leading-relaxed">
            {t('checkConnectionAndRetry')}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-brand-turquoise/10 hover:bg-brand-turquoise/20 dark:bg-brand-turquoise/20 dark:hover:bg-brand-turquoise/30 border border-brand-turquoise/30 dark:border-brand-turquoise/40 text-xs font-bold text-brand-turquoise transition-colors font-cairo"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              {t('retry')}
            </button>
          )}
        </div>
      </HakimShell>
    );
  }

  if (!data) {
    return (
      <HakimShell>
        <div className="text-center py-10 px-5 bg-card">
          <div className="mx-auto mb-3 w-fit">
            <HakimAvatar pose="friendly-greeting" size={64} />
          </div>
          <p className="text-sm font-bold text-foreground mb-1.5 font-cairo">{t('hakimWeeklyStoryTitle')}</p>
          <p className="text-xs text-muted-foreground font-tajawal max-w-sm mx-auto leading-relaxed">
            {t('hakimInsightsEmpty')}
          </p>
        </div>
      </HakimShell>
    );
  }

  const cards = Array.isArray(data.cards) ? data.cards : [];
  const adviceText = data.advice?.text_ar || null;
  const status = data.status || (cards.length > 0 ? 'available' : 'insufficient_data');
  const { week_start, week_end } = data;

  const formatDateShort = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ar-SA', { month: 'short', day: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  return (
    <HakimShell>
      <HakimHeader
        pose="explaining-concept"
        meta={(week_start || week_end) ? (
          <p className="text-[11px] text-brand-navy/55 dark:text-muted-foreground mt-1 flex items-center gap-1 font-tajawal">
            <Calendar className="w-3 h-3" />
            {formatDateShort(week_start)} — {formatDateShort(week_end)}
          </p>
        ) : null}
        right={(
          <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-brand-navy/60 dark:text-muted-foreground bg-card border border-border px-2 py-1 rounded-full font-medium shrink-0">
            <RefreshCw className="w-2.5 h-2.5" />
            {t('weeklyRefresh')}
          </span>
        )}
      />

      <div className="p-5 space-y-4 bg-card">
        {status === 'insufficient_data' && (
          <div
            className="rounded-2xl bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.08] border border-brand-navy/15 dark:border-brand-turquoise/30 p-4 flex items-start gap-3"
            data-testid="weekly-story-empty"
          >
            <HakimAvatar pose="ai-thinking-2" size={40} />
            <div className="min-w-0">
              <p className="text-sm font-bold text-foreground font-cairo">
                {t('hakimInsufficientData')}
              </p>
              <p className="text-xs text-muted-foreground mt-1 font-tajawal leading-relaxed">
                {t('hakimInsufficientDataHint')}
              </p>
            </div>
          </div>
        )}

        {cards.length > 0 && (
          <>
            <SectionLabel icon={Sparkles} label={t('hakimWeeklyHighlights')} />
            <div
              className="grid grid-cols-2 gap-2.5 sm:gap-3 lg:grid-cols-4"
              data-testid="weekly-story-cards"
            >
              {cards.map((c, i) => (
                <HighlightCard key={`${c.kind}-${i}`} card={c} />
              ))}
            </div>
          </>
        )}

        {adviceText && <AdviceCard text={adviceText} />}
      </div>
    </HakimShell>
  );
};

const HakimShell = ({ children }) => (
  <div className="rounded-2xl shadow-sm border border-brand-turquoise/20 dark:border-brand-turquoise/25 bg-gradient-to-br from-brand-turquoise/[0.05] via-card to-brand-navy/[0.04] dark:from-brand-turquoise/[0.08] dark:via-card dark:to-brand-navy/30 overflow-hidden">
    {children}
  </div>
);

const HakimHeader = ({ pose, subtitle, subtitleAnimated, meta, right }) => {
  const { t } = useTranslation();
  return (
    <div className="bg-gradient-to-r from-brand-turquoise/[0.10] via-card/60 to-brand-navy/[0.08] dark:from-brand-turquoise/[0.12] dark:via-card/40 dark:to-brand-navy/30 px-5 pt-4 pb-4 border-b border-brand-turquoise/15 dark:border-brand-turquoise/25">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <HakimAvatar pose={pose} size={44} />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-bold text-foreground font-cairo leading-tight">
                {t('hakimWeeklyStoryTitle')}
              </h3>
              <HakimChip label={t('hakimAi')} />
            </div>
            {subtitle && (
              <p className="text-[11px] text-muted-foreground mt-1 font-tajawal flex items-center gap-1">
                <Sparkles className={`w-3 h-3 text-brand-turquoise ${subtitleAnimated ? 'animate-pulse' : ''}`} />
                {subtitle}
              </p>
            )}
            {meta}
          </div>
        </div>
        {right}
      </div>
      <div className="mt-3 ps-[3.6rem]">
        <HakimAttributionLine>{t('hakimWeeklyAttribution')}</HakimAttributionLine>
      </div>
    </div>
  );
};

export default WeeklyStory;
