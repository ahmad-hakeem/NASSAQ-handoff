import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import {
  Award, Star, TrendingUp, TrendingDown, BookOpen, Lightbulb,
  FileText, AlertCircle, RefreshCw, Calendar, Sparkles, GraduationCap,
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';
import { getPose } from '../../components/hakim/hakimPoses';

/* -------------------------------------------------------------------------- */
/* Hakim attribution primitives — reused across header, tip card, empty/error */
/* Uses the official Hakim character images from /hakim-poses/ to match the   */
/* same branded assistant identity used in the Teacher account.               */
/* -------------------------------------------------------------------------- */

// Branded avatar wrapper that frames the real Hakim character image.
// `size` is in px; `pose` is a registered key in hakimPoses.js.
const HakimAvatar = ({ pose = 'friendly-greeting', size = 44, ringed = true }) => (
  <div
    className={`relative shrink-0 rounded-2xl overflow-hidden bg-gradient-to-br from-brand-turquoise/15 to-brand-navy/10 ${
      ringed ? 'shadow-md shadow-brand-turquoise/25 ring-1 ring-brand-turquoise/25' : ''
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
  <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-turquoise/12 text-brand-turquoise ps-1 pe-2 py-0.5 text-[10px] font-bold border border-brand-turquoise/25 font-cairo">
    <span className="w-4 h-4 rounded-full overflow-hidden bg-white">
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
  <p className="text-[11px] text-brand-navy/70 leading-relaxed font-tajawal flex items-start gap-1.5">
    <Sparkles className="w-3 h-3 text-brand-turquoise mt-[2px] shrink-0" />
    <span>{children}</span>
  </p>
);

/* -------------------------------------------------------------------------- */

const WeeklyStory = ({ data, loading, error, onRetry }) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <HakimShell>
        {/* Real Hakim identity row — keeps attribution visible while data streams in */}
        <div className="bg-gradient-to-r from-brand-turquoise/[0.10] via-white/40 to-brand-navy/[0.08] px-5 pt-4 pb-4 border-b border-brand-turquoise/15">
          <div className="flex items-center gap-3">
            <HakimAvatar pose="ai-thinking" size={44} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-brand-navy font-cairo leading-tight">
                  {t('hakimWeeklyStoryTitle')}
                </h3>
                <HakimChip label={t('hakimAi')} />
              </div>
              <p className="text-[11px] text-brand-navy/60 mt-1 font-tajawal flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-brand-turquoise animate-pulse" />
                {t('hakimIsAnalyzingData')}
              </p>
            </div>
          </div>
          <div className="mt-3 ps-[3.6rem]">
            <HakimAttributionLine>{t('hakimWeeklyAttribution')}</HakimAttributionLine>
          </div>
        </div>
        <div className="p-5 space-y-4 bg-white animate-pulse">
          <div className="grid grid-cols-2 gap-3">
            <div className="h-20 bg-brand-navy/[0.04] border border-brand-navy/8 rounded-xl" />
            <div className="h-20 bg-brand-navy/[0.04] border border-brand-navy/8 rounded-xl" />
          </div>
          <div className="h-32 bg-brand-navy/[0.04] border border-brand-navy/8 rounded-xl" />
        </div>
      </HakimShell>
    );
  }

  if (error) {
    return (
      <HakimShell>
        <div className="text-center py-8 px-5">
          <div className="mx-auto mb-3 w-fit">
            <HakimAvatar pose="support" size={56} />
          </div>
          <p className="text-sm font-bold text-brand-navy mb-1 font-cairo">{t('hakimInsightsUnavailable')}</p>
          <p className="text-xs text-brand-navy/60 font-tajawal mb-4 max-w-sm mx-auto leading-relaxed">
            {t('checkConnectionAndRetry')}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-brand-turquoise/10 hover:bg-brand-turquoise/20 border border-brand-turquoise/30 text-xs font-bold text-brand-turquoise transition-colors font-cairo"
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
        <div className="text-center py-10 px-5">
          <div className="mx-auto mb-3 w-fit">
            <HakimAvatar pose="friendly-greeting" size={64} />
          </div>
          <p className="text-sm font-bold text-brand-navy mb-1.5 font-cairo">{t('hakimWeeklyStoryTitle')}</p>
          <p className="text-xs text-brand-navy/65 font-tajawal max-w-sm mx-auto leading-relaxed">
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

  return (
    <HakimShell>
      {/* Branded header — clearly identifies the card as a Hakim insight */}
      <div className="bg-gradient-to-r from-brand-turquoise/[0.10] via-white/40 to-brand-navy/[0.08] px-5 pt-4 pb-4 border-b border-brand-turquoise/15">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <HakimAvatar pose="explaining-concept" size={44} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-brand-navy font-cairo leading-tight">
                  {t('hakimWeeklyStoryTitle')}
                </h3>
                <HakimChip label={t('hakimAi')} />
              </div>
              {(week_start || week_end) && (
                <p className="text-[11px] text-brand-navy/55 mt-1 flex items-center gap-1 font-tajawal">
                  <Calendar className="w-3 h-3" />
                  {formatDateShort(week_start)} — {formatDateShort(week_end)}
                </p>
              )}
            </div>
          </div>
          <span className="hidden sm:inline-flex items-center gap-1 text-[10px] text-brand-navy/60 bg-white border border-brand-navy/10 px-2 py-1 rounded-full font-medium shrink-0">
            <RefreshCw className="w-2.5 h-2.5" />
            {t('weeklyRefresh')}
          </span>
        </div>
        <div className="mt-3 ps-[3.6rem]">
          <HakimAttributionLine>{t('hakimWeeklyAttribution')}</HakimAttributionLine>
        </div>
      </div>

      {/* Content body */}
      <div className="p-5 space-y-5 bg-white">
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
                  className="px-2.5 py-1 rounded-full bg-brand-turquoise/10 text-brand-turquoise text-xs font-semibold border border-brand-turquoise/25 font-tajawal"
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
                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-100">
                      <div className="flex items-center gap-1.5 text-emerald-700 text-xs font-semibold font-tajawal">
                        <GraduationCap className="w-3.5 h-3.5" />
                        {s.subject}
                      </div>
                      <span className="text-[11px] font-bold text-emerald-700 tabular-nums">{s.average}%</span>
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
                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-amber-50 border border-amber-100">
                      <div className="flex items-center gap-1.5 text-amber-700 text-xs font-semibold font-tajawal">
                        <Lightbulb className="w-3.5 h-3.5" />
                        {s.subject}
                      </div>
                      <span className="text-[11px] font-bold text-amber-700 tabular-nums">{s.average}%</span>
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
                <div key={plan.id || i} className="p-3 rounded-xl bg-orange-50 border border-orange-100">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="w-3.5 h-3.5 text-orange-600 shrink-0" />
                    <span className="text-xs font-bold text-orange-800 font-cairo">{plan.title}</span>
                  </div>
                  {plan.description && (
                    <p className="text-xs text-orange-700 ms-5 leading-relaxed font-tajawal">{plan.description}</p>
                  )}
                  {(plan.subject || plan.teacher_name) && (
                    <div className="flex items-center gap-3 ms-5 mt-1.5">
                      {plan.subject && (
                        <span className="text-[10px] text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full font-medium">
                          {plan.subject}
                        </span>
                      )}
                      {plan.teacher_name && (
                        <span className="text-[10px] text-orange-600">
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
            <div className="h-44 w-full mt-2 rounded-xl bg-gradient-to-b from-brand-navy/[0.03] to-transparent p-2" dir="ltr">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={daily_chart_data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e6ebf2" />
                  <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#1C3D74' }} />
                  <YAxis tick={{ fontSize: 11, fill: '#1C3D74' }} width={25} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      direction: 'rtl',
                      borderRadius: '12px',
                      border: '1px solid rgba(28,61,116,0.12)',
                      boxShadow: '0 4px 16px rgba(28,61,116,0.12)'
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, direction: 'rtl' }} />
                  <Bar dataKey="participation" name={t('classParticipation')} fill="#1C3D74" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="positive_behavior" name={t('positiveBehavior')} fill="#46C1BE" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center gap-4 justify-center mt-2">
              <ActivityDot color="bg-brand-navy" label={t('classParticipation')} />
              <ActivityDot color="bg-brand-turquoise" label={t('positiveBehavior')} />
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
          <div className="rounded-2xl bg-gradient-to-br from-brand-turquoise/10 via-white to-brand-turquoise/5 border border-brand-turquoise/25 overflow-hidden">
            <div className="px-4 py-3 bg-brand-turquoise/8 border-b border-brand-turquoise/15 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-7 h-7 rounded-lg bg-brand-turquoise text-white flex items-center justify-center shrink-0">
                  <BookOpen className="w-4 h-4" />
                </div>
                <span className="text-xs font-bold text-brand-navy font-cairo truncate">
                  {t('hakimWeeklyStorySection')}
                </span>
              </div>
              <HakimChip label={t('hakimAi')} />
            </div>
            <div className="p-4">
              <p className="text-sm text-brand-navy leading-relaxed font-tajawal whitespace-pre-line">
                {insightStory}
              </p>
              {insightGeneratedAt && (
                <p className="text-[10.5px] text-brand-navy/55 mt-3 font-tajawal flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5 text-brand-turquoise" />
                  {t('hakimGeneratedAt')} {formatGeneratedAt(insightGeneratedAt)}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Insufficient data — no fabrication, explicit message */}
        {insightStatus === 'insufficient_data' && (
          <div className="rounded-2xl bg-brand-navy/[0.04] border border-brand-navy/15 p-4 flex items-start gap-3">
            <HakimAvatar pose="ai-thinking-2" size={40} />
            <div className="min-w-0">
              <p className="text-sm font-bold text-brand-navy font-cairo">
                {t('hakimInsufficientData')}
              </p>
              <p className="text-xs text-brand-navy/65 mt-1 font-tajawal leading-relaxed">
                {t('hakimInsufficientDataHint')}
              </p>
            </div>
          </div>
        )}

        {/* Unavailable — service-side issue, not fabrication */}
        {insightStatus === 'unavailable' && (
          <div className="rounded-2xl bg-amber-50 border border-amber-200 p-4 flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center shrink-0 mt-0.5">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-amber-800 font-cairo">
                {t('hakimInsightsUnavailable')}
              </p>
              <p className="text-xs text-amber-700/80 mt-1 font-tajawal leading-relaxed">
                {t('checkConnectionAndRetry')}
              </p>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* Tip of the Week — only rendered when Hakim has a real tip      */}
        {/* ============================================================== */}
        {insightStatus === 'available' && insightTip && (
          <div className="rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy to-brand-purple text-white shadow-md shadow-brand-navy/20 overflow-hidden border border-brand-navy/20">
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
/* Shared brand-tinted shell so the card never reads as a generic white box.  */
/* -------------------------------------------------------------------------- */
const HakimShell = ({ children }) => (
  <div className="rounded-2xl shadow-sm border border-brand-turquoise/20 bg-gradient-to-br from-brand-turquoise/[0.05] via-white to-brand-navy/[0.04] overflow-hidden">
    {children}
  </div>
);

const SectionLabel = ({ icon: Icon, label, tone = 'navy' }) => {
  const toneMap = {
    navy: 'text-brand-navy',
    emerald: 'text-emerald-700',
    amber: 'text-amber-700',
    orange: 'text-orange-700',
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
    ? 'bg-emerald-50 border-emerald-200/70 text-emerald-800'
    : 'bg-brand-navy/[0.06] border-brand-navy/15 text-brand-navy';
  const iconWrap = tone === 'emerald'
    ? 'bg-emerald-100 text-emerald-700'
    : 'bg-brand-navy/15 text-brand-navy';

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
    <span className="text-[10px] text-brand-navy/70 font-tajawal">{label}</span>
  </div>
);

export default WeeklyStory;
