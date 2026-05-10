import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import {
  Award, Star, TrendingUp, TrendingDown, BookOpen, Lightbulb,
  FileText, AlertCircle, RefreshCw, Calendar, Sparkles, GraduationCap,
} from 'lucide-react';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { getPose } from '../../components/hakim/hakimPoses';

/* -------------------------------------------------------------------------- */
/* Hakim attribution primitives — reused across header, tip card, empty/error */
/* Uses the official Hakim character images from /hakim-poses/ to match the   */
/* same branded assistant identity used in the Teacher account.               */
/* All surfaces are theme-aware so dark mode reads as a premium NASSAQ panel. */
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

/* -------------------------------------------------------------------------- */

const WeeklyStory = ({ data, loading, error, onRetry }) => {
  const { t } = useTranslation();
  const { isDark } = useTheme();

  if (loading) {
    return (
      <HakimShell>
        <HakimHeader subtitle={t('hakimIsAnalyzingData')} subtitleAnimated pose="ai-thinking" />
        <div className="p-5 space-y-4 bg-card animate-pulse">
          <div className="grid grid-cols-2 gap-3">
            <div className="h-20 bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border rounded-xl" />
            <div className="h-20 bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border rounded-xl" />
          </div>
          <div className="h-32 bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.06] border border-border rounded-xl" />
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

  const {
    participation_count,
    positive_behaviors,
    acquired_skills,
    strong_subjects,
    weak_subjects,
    remedial_plans,
    daily_chart_data,
    weekly_tip,
    weekly_insight,
    week_start,
    week_end,
  } = data;

  // Hakim insight envelope (new structured payload)
  const insightStatus = weekly_insight?.status || (weekly_tip ? 'available' : 'insufficient_data');
  const insightStory = weekly_insight?.story || null;
  const insightTip = weekly_insight?.tip || weekly_tip || null;
  const insightGeneratedAt = weekly_insight?.generated_at || null;

  const formatGeneratedAt = (iso) => {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleString('ar-SA', { dateStyle: 'medium', timeStyle: 'short' });
    } catch {
      return '';
    }
  };

  const formatDateShort = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('ar-SA', { month: 'short', day: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const hasActivityData = participation_count > 0 || positive_behaviors > 0;
  const hasSubjectData = (strong_subjects?.length > 0) || (weak_subjects?.length > 0);

  // Theme-aware recharts palette so the chart never reads as a light island.
  const chartGrid = isDark ? '#1e293b' : '#e6ebf2';
  const chartTick = isDark ? '#cbd5e1' : '#1C3D74';
  const tooltipBg = isDark ? '#0f172a' : '#ffffff';
  const tooltipBorder = isDark ? '#1e293b' : 'rgba(28,61,116,0.12)';
  const tooltipShadow = isDark ? '0 4px 16px rgba(0,0,0,0.45)' : '0 4px 16px rgba(28,61,116,0.12)';
  // In dark mode the participation bar is shifted to brand-turquoise so it
  // (a) matches its legend dot and (b) reads against the dark card surface.
  // The positive-behavior bar uses brand-purple in dark to stay distinct from
  // the now-turquoise participation bar.
  const participationBarFill = isDark ? '#46C1BE' : '#1C3D74';
  const positiveBarFill = isDark ? '#9b6dff' : '#46C1BE';

  return (
    <HakimShell>
      {/* Branded header — clearly identifies the card as a Hakim insight */}
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

      {/* Content body */}
      <div className="p-5 space-y-5 bg-card">
        {/* Summary metrics */}
        <div className="grid grid-cols-2 gap-3">
          <StatBadge
            icon={Star}
            label={t('classParticipation')}
            value={participation_count}
            tone="navy"
          />
          <StatBadge
            icon={Award}
            label={t('positiveBehavior')}
            value={positive_behaviors}
            tone="emerald"
          />
        </div>

        {acquired_skills?.length > 0 && (
          <div>
            <SectionLabel icon={Sparkles} label={t('acquiredSkills')} tone="turquoise" />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {acquired_skills.map((skill, i) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-full bg-brand-turquoise/10 dark:bg-brand-turquoise/20 text-brand-turquoise text-xs font-semibold border border-brand-turquoise/25 dark:border-brand-turquoise/40 font-tajawal"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {hasSubjectData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {strong_subjects?.length > 0 && (
              <div>
                <SectionLabel icon={TrendingUp} label={t('excelledIn')} tone="emerald" />
                <div className="space-y-1.5 mt-2">
                  {strong_subjects.map((s, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40">
                      <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-300 text-xs font-semibold font-tajawal">
                        <GraduationCap className="w-3.5 h-3.5" />
                        {s.subject}
                      </div>
                      <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-300 tabular-nums">{s.average}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {weak_subjects?.length > 0 && (
              <div>
                <SectionLabel icon={TrendingDown} label={t('needsImprovement')} tone="amber" />
                <div className="space-y-1.5 mt-2">
                  {weak_subjects.map((s, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40">
                      <div className="flex items-center gap-1.5 text-amber-700 dark:text-amber-300 text-xs font-semibold font-tajawal">
                        <Lightbulb className="w-3.5 h-3.5" />
                        {s.subject}
                      </div>
                      <span className="text-[11px] font-bold text-amber-700 dark:text-amber-300 tabular-nums">{s.average}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {remedial_plans?.length > 0 && (
          <div>
            <SectionLabel icon={FileText} label={t('teacherRemedialPlans')} tone="orange" />
            <div className="space-y-2 mt-2">
              {remedial_plans.map((plan, i) => (
                <div key={plan.id || i} className="p-3 rounded-xl bg-orange-50 dark:bg-orange-950/30 border border-orange-100 dark:border-orange-900/40">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="w-3.5 h-3.5 text-orange-600 dark:text-orange-300 shrink-0" />
                    <span className="text-xs font-bold text-orange-800 dark:text-orange-200 font-cairo">{plan.title}</span>
                  </div>
                  {plan.description && (
                    <p className="text-xs text-orange-700 dark:text-orange-200/85 ms-5 leading-relaxed font-tajawal">{plan.description}</p>
                  )}
                  {(plan.subject || plan.teacher_name) && (
                    <div className="flex items-center gap-3 ms-5 mt-1.5">
                      {plan.subject && (
                        <span className="text-[10px] text-orange-600 dark:text-orange-300 bg-orange-100 dark:bg-orange-900/40 px-2 py-0.5 rounded-full font-medium">
                          {plan.subject}
                        </span>
                      )}
                      {plan.teacher_name && (
                        <span className="text-[10px] text-orange-600 dark:text-orange-300">
                          {t('theTeacher')}: {plan.teacher_name}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {daily_chart_data?.length > 0 && hasActivityData && (
          <div>
            <SectionLabel icon={Star} label={t('dailyActivity')} tone="navy" />
            <div className="h-44 w-full mt-2 rounded-xl bg-gradient-to-b from-brand-navy/[0.03] dark:from-brand-turquoise/[0.06] to-transparent p-2" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily_chart_data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: chartTick }} />
                  <YAxis tick={{ fontSize: 11, fill: chartTick }} width={25} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      direction: 'rtl',
                      borderRadius: '12px',
                      border: `1px solid ${tooltipBorder}`,
                      backgroundColor: tooltipBg,
                      color: chartTick,
                      boxShadow: tooltipShadow,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, direction: 'rtl', color: chartTick }} />
                  <Bar dataKey="participation" name={t('classParticipation')} fill={participationBarFill} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="positive_behavior" name={t('positiveBehavior')} fill={positiveBarFill} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center gap-4 justify-center mt-2">
              <ActivityDot color="bg-brand-navy dark:bg-brand-turquoise" label={t('classParticipation')} />
              <ActivityDot color="bg-brand-turquoise dark:bg-brand-purple" label={t('positiveBehavior')} />
              {daily_chart_data.some(d => d.participation > 3) && (
                <ActivityDot color="bg-brand-purple" label={t('highActivity')} />
              )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* Story of the Week — Hakim-generated narrative (real LLM output) */}
        {/* ============================================================== */}
        {insightStatus === 'available' && insightStory && (
          <div className="rounded-2xl bg-gradient-to-br from-brand-turquoise/10 via-card to-brand-turquoise/5 dark:from-brand-turquoise/15 dark:via-card dark:to-brand-turquoise/10 border border-brand-turquoise/25 dark:border-brand-turquoise/40 overflow-hidden">
            <div className="px-4 py-3 bg-brand-turquoise/8 dark:bg-brand-turquoise/15 border-b border-brand-turquoise/15 dark:border-brand-turquoise/30 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-brand-turquoise text-white dark:text-brand-navy flex items-center justify-center shrink-0">
                  <BookOpen className="w-4 h-4" />
                </div>
                <span className="text-xs font-bold text-foreground font-cairo truncate">
                  {t('hakimWeeklyStorySection')}
                </span>
              </div>
              <HakimChip label={t('hakimAi')} />
            </div>
            <div className="p-4">
              <p className="text-sm text-foreground leading-relaxed font-tajawal whitespace-pre-line">
                {insightStory}
              </p>
              {insightGeneratedAt && (
                <p className="text-[10.5px] text-muted-foreground mt-3 font-tajawal flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5 text-brand-turquoise" />
                  {t('hakimGeneratedAt')} {formatGeneratedAt(insightGeneratedAt)}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Insufficient data — no fabrication, explicit message */}
        {insightStatus === 'insufficient_data' && (
          <div className="rounded-2xl bg-brand-navy/[0.04] dark:bg-brand-turquoise/[0.08] border border-brand-navy/15 dark:border-brand-turquoise/30 p-4 flex items-start gap-3">
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

        {/* Unavailable — service-side issue, not fabrication */}
        {insightStatus === 'unavailable' && (
          <div className="rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 p-4 flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 flex items-center justify-center shrink-0 mt-0.5">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-amber-800 dark:text-amber-200 font-cairo">
                {t('hakimInsightsUnavailable')}
              </p>
              <p className="text-xs text-amber-700/80 dark:text-amber-200/80 mt-1 font-tajawal leading-relaxed">
                {t('checkConnectionAndRetry')}
              </p>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* Tip of the Week — only rendered when Hakim has a real tip      */}
        {/* Branded dark gradient — looks intentional in BOTH themes        */}
        {/* ============================================================== */}
        {insightStatus === 'available' && insightTip && (
          <div className="rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy to-brand-purple text-white shadow-md shadow-brand-navy/20 overflow-hidden border border-brand-navy/20 dark:border-brand-turquoise/30">
            <div className="px-4 py-3 bg-white/[0.06] border-b border-white/10 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-7 h-7 rounded-lg overflow-hidden bg-white/15 ring-1 ring-white/25 shrink-0">
                  <img
                    src={getPose('motivating')}
                    alt=""
                    aria-hidden="true"
                    loading="lazy"
                    className="w-full h-full object-cover object-top"
                    draggable={false}
                  />
                </div>
                <span className="text-xs font-bold text-white font-cairo truncate">
                  {t('hakimWeeklyTipTitle')}
                </span>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-turquoise/25 text-white px-2 py-0.5 text-[10px] font-bold border border-brand-turquoise/40 shrink-0">
                <Sparkles className="w-2.5 h-2.5" />
                {t('hakimAi')}
              </span>
            </div>
            <div className="p-4 flex items-start gap-3">
              <div className="w-9 h-9 rounded-xl bg-white/15 text-white flex items-center justify-center shrink-0 mt-0.5">
                <Lightbulb className="w-4.5 h-4.5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm text-white leading-relaxed font-tajawal">{insightTip}</p>
                <p className="text-[10.5px] text-white/65 mt-2 font-tajawal flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5" />
                  {t('hakimWeeklyAttribution')}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </HakimShell>
  );
};

/* -------------------------------------------------------------------------- */
/* Shared brand-tinted shell. Uses `via-card` so the gradient picks up the    */
/* current theme surface (white in light, near-black in dark) instead of      */
/* hard-coding white. Border is the semantic `border` token in dark for a     */
/* softer, NASSAQ-branded edge.                                               */
/* -------------------------------------------------------------------------- */
const HakimShell = ({ children }) => (
  <div className="rounded-2xl shadow-sm border border-brand-turquoise/20 dark:border-brand-turquoise/25 bg-gradient-to-br from-brand-turquoise/[0.05] via-card to-brand-navy/[0.04] dark:from-brand-turquoise/[0.08] dark:via-card dark:to-brand-navy/30 overflow-hidden">
    {children}
  </div>
);

/* Shared header so loading + main render share identical visual language. */
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

const SectionLabel = ({ icon: Icon, label, tone = 'navy' }) => {
  const toneMap = {
    navy:      'text-brand-navy dark:text-brand-turquoise',
    emerald:   'text-emerald-700 dark:text-emerald-300',
    amber:     'text-amber-700 dark:text-amber-300',
    orange:    'text-orange-700 dark:text-orange-300',
    turquoise: 'text-brand-turquoise',
  };
  return (
    <div className={`flex items-center gap-1.5 text-xs font-bold font-cairo ${toneMap[tone] || toneMap.navy}`}>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
};

const StatBadge = ({ icon: Icon, label, value, tone }) => {
  const surface = tone === 'emerald'
    ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200/70 dark:border-emerald-900/50 text-emerald-800 dark:text-emerald-200'
    : 'bg-brand-navy/[0.06] dark:bg-brand-turquoise/[0.10] border-brand-navy/15 dark:border-brand-turquoise/30 text-brand-navy dark:text-foreground';
  const iconWrap = tone === 'emerald'
    ? 'bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300'
    : 'bg-brand-navy/15 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise';

  return (
    <div className={`flex items-center gap-3 p-3.5 rounded-xl border ${surface}`}>
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${iconWrap}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold leading-none font-cairo tabular-nums">{value || 0}</p>
        <p className="text-[11px] opacity-80 mt-1 font-tajawal">{label}</p>
      </div>
    </div>
  );
};

const ActivityDot = ({ color, label }) => (
  <div className="flex items-center gap-1.5">
    <div className={`w-2 h-2 rounded-full ${color}`} />
    <span className="text-[10px] text-muted-foreground font-tajawal">{label}</span>
  </div>
);

export default WeeklyStory;
