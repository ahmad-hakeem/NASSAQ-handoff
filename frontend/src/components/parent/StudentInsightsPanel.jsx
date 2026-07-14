import React, { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Card, CardContent } from '../ui/card';
import { LoadingState } from '../ui/LoadingState';
import {
  Sparkles, Zap, Target, ChevronDown, TrendingUp, TrendingDown,
  Minus, Lightbulb, Heart, BookOpen, GraduationCap,
} from 'lucide-react';

const TREND_META = {
  improving:    { Icon: TrendingUp,   label_ar: 'تحسّن',  cls: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40 dark:text-emerald-400' },
  declining:    { Icon: TrendingDown, label_ar: 'تراجع',  cls: 'text-rose-600    bg-rose-50    dark:bg-rose-950/40    dark:text-rose-400' },
  stable:       { Icon: Minus,        label_ar: 'مستقر',  cls: 'text-muted-foreground bg-muted/50' },
  insufficient: { Icon: Minus,        label_ar: '—',      cls: 'text-muted-foreground bg-muted/40' },
};

const LEVEL_META = {
  advanced:     { label_ar: 'متقدم',          cls: 'text-emerald-700 bg-emerald-50 border-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900/40' },
  intermediate: { label_ar: 'متوسط',          cls: 'text-blue-700    bg-blue-50    border-blue-100    dark:bg-blue-950/30    dark:text-blue-300    dark:border-blue-900/40' },
  needs_focus:  { label_ar: 'يحتاج تركيز',    cls: 'text-amber-700   bg-amber-50   border-amber-100   dark:bg-amber-950/30   dark:text-amber-300   dark:border-amber-900/40' },
  insufficient: { label_ar: 'لم يُقيَّم بعد', cls: 'text-muted-foreground bg-muted/40 border-border' },
};

const SCORE_RING = (score) => {
  if (score === null || score === undefined) {
    return 'text-muted-foreground bg-muted/40 border-border';
  }
  if (score >= 85) return 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900/50';
  if (score >= 70) return 'text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900/50';
  if (score >= 60) return 'text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900/50';
  return 'text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-900/50';
};

const TagPill = ({ children, tone = 'neutral' }) => {
  const tones = {
    positive: 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900/40',
    concern:  'bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900/40',
    neutral:  'bg-muted/50 text-muted-foreground border-border',
  };
  return (
    <span className={`inline-flex items-center text-[11px] font-tajawal px-2 py-0.5 rounded-full border ${tones[tone]}`}>
      {children}
    </span>
  );
};

const StrengthsCard = ({ items, isRTL }) => {
  if (!items || items.length === 0) return null;
  return (
    <Card className="rounded-2xl border border-emerald-100 dark:border-emerald-900/40 shadow-sm bg-card overflow-hidden">
      <div className="border-r-4 border-emerald-500 dark:border-emerald-400">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-300 flex items-center justify-center">
              <Zap className="h-4 w-4" />
            </span>
            <h4 className="font-cairo font-bold text-sm text-emerald-700 dark:text-emerald-300">
              {isRTL ? 'نقاط القوة العامة' : 'General strengths'}
            </h4>
          </div>
          <ul className="space-y-1.5">
            {items.map((it, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground font-tajawal">
                <TrendingUp className="h-3.5 w-3.5 mt-0.5 text-emerald-500 dark:text-emerald-400 shrink-0" />
                <span>{it}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </div>
    </Card>
  );
};

const WeaknessesCard = ({ items, isRTL }) => {
  if (!items || items.length === 0) return null;
  return (
    <Card className="rounded-2xl border border-amber-100 dark:border-amber-900/40 shadow-sm bg-card overflow-hidden">
      <div className="border-r-4 border-amber-500 dark:border-amber-400">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-300 flex items-center justify-center">
              <Target className="h-4 w-4" />
            </span>
            <h4 className="font-cairo font-bold text-sm text-amber-700 dark:text-amber-300">
              {isRTL ? 'نقاط تحتاج تحسين' : 'Improvement areas'}
            </h4>
          </div>
          <ul className="space-y-1.5">
            {items.map((it, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground font-tajawal">
                <TrendingDown className="h-3.5 w-3.5 mt-0.5 text-amber-500 dark:text-amber-400 shrink-0" />
                <span>{it}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </div>
    </Card>
  );
};

const HakimNarrative = ({ summary, tips, isRTL }) => {
  if (!summary || summary.status !== 'available' || !summary.text) return null;
  return (
    <Card className="rounded-2xl border border-border shadow-sm bg-card overflow-hidden">
      <div className="bg-gradient-to-l from-brand-navy/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/15 px-4 py-2.5 border-b border-border flex items-center gap-2">
        <span className="w-7 h-7 rounded-lg bg-brand-navy/10 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise flex items-center justify-center">
          <Sparkles className="h-3.5 w-3.5" />
        </span>
        <h4 className="font-cairo font-bold text-sm text-foreground">
          {isRTL ? 'ملخص حكيم' : 'Hakim summary'}
        </h4>
      </div>
      <CardContent className="p-4 space-y-3">
        <p className="text-sm leading-relaxed font-tajawal text-foreground whitespace-pre-line">
          {summary.text}
        </p>
        {Array.isArray(tips) && tips.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-border">
            {tips.map((tip, i) => (
              <div key={i} className="flex items-start gap-2 text-sm bg-muted/30 rounded-xl p-3">
                <Lightbulb className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  {tip.subject && (
                    <p className="text-[11px] text-muted-foreground font-tajawal mb-0.5">
                      {isRTL ? `نصيحة لمادة ${tip.subject}` : `Tip for ${tip.subject}`}
                    </p>
                  )}
                  <p className="text-foreground font-tajawal leading-relaxed">{tip.text}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const SubjectRow = ({ subject, isOpen, onToggle, isRTL }) => {
  const trend = TREND_META[subject.trend_status] || TREND_META.insufficient;
  const TrendIcon = trend.Icon;
  const level = LEVEL_META[subject.level] || LEVEL_META.insufficient;
  const scoreCls = SCORE_RING(subject.score);
  const hasScore = subject.score !== null && subject.score !== undefined;

  return (
    <div className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="w-full flex items-center gap-3 p-3 hover:bg-muted/30 transition-colors"
      >
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
        <div className="flex-1 min-w-0 flex flex-col items-end gap-1">
          <span className="font-cairo font-bold text-sm text-foreground truncate">
            {subject.name}
          </span>
          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            <span className={`inline-flex items-center text-[10px] font-tajawal px-2 py-0.5 rounded-full border ${level.cls}`}>
              {level.label_ar}
            </span>
            {subject.trend_status !== 'insufficient' && (
              <span className={`inline-flex items-center gap-0.5 text-[10px] font-tajawal px-2 py-0.5 rounded-full ${trend.cls}`}>
                <TrendIcon className="h-3 w-3" />
                {trend.label_ar}
              </span>
            )}
          </div>
        </div>
        <span className={`shrink-0 w-12 h-12 rounded-full border-2 flex items-center justify-center font-bold text-sm tabular-nums ${scoreCls}`}>
          {hasScore ? Math.round(subject.score) : '—'}
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-border p-3 space-y-3 bg-muted/10">
          {/* Trend line + teacher */}
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground font-tajawal">
            {subject.teacher_name ? (
              <span className="truncate">
                {isRTL ? `أ. ${subject.teacher_name}` : `Teacher: ${subject.teacher_name}`}
              </span>
            ) : <span />}
            {subject.previous_score !== null && subject.previous_score !== undefined && hasScore && (
              <span className="tabular-nums whitespace-nowrap">
                {Math.round(subject.previous_score)}% {isRTL ? '←' : '→'} {Math.round(subject.score)}%
              </span>
            )}
          </div>

          {!hasScore ? (
            <p className="text-sm text-muted-foreground font-tajawal text-center py-3">
              {isRTL ? 'لم يتم تقييم المادة بعد' : 'Subject not yet evaluated'}
            </p>
          ) : (
            <>
              {subject.strengths?.length > 0 && (
                <div className="rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/40 p-3">
                  <div className="flex items-center gap-1.5 mb-2 text-emerald-700 dark:text-emerald-300">
                    <Zap className="h-3.5 w-3.5" />
                    <span className="text-xs font-cairo font-bold">
                      {isRTL ? `نقاط القوة في ${subject.name}` : `Strengths in ${subject.name}`}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {subject.strengths.map((s, i) => <TagPill key={i} tone="positive">{s}</TagPill>)}
                  </div>
                </div>
              )}

              {subject.weaknesses?.length > 0 && (
                <div className="rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40 p-3">
                  <div className="flex items-center gap-1.5 mb-2 text-amber-700 dark:text-amber-300">
                    <Target className="h-3.5 w-3.5" />
                    <span className="text-xs font-cairo font-bold">
                      {isRTL ? `نقاط تحتاج تحسين في ${subject.name}` : `Improvement areas in ${subject.name}`}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {subject.weaknesses.map((s, i) => <TagPill key={i} tone="concern">{s}</TagPill>)}
                  </div>
                </div>
              )}

              {subject.action_plan && (
                <div className={`rounded-xl border p-3 ${
                  subject.action_plan.type === 'enrichment'
                    ? 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-100 dark:border-emerald-900/40'
                    : 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-100 dark:border-amber-900/40'
                }`}>
                  <div className={`flex items-center gap-1.5 mb-1 ${
                    subject.action_plan.type === 'enrichment'
                      ? 'text-emerald-700 dark:text-emerald-300'
                      : 'text-amber-700 dark:text-amber-300'
                  }`}>
                    {subject.action_plan.type === 'enrichment'
                      ? <Sparkles className="h-3.5 w-3.5" />
                      : <Heart className="h-3.5 w-3.5" />}
                    <span className="text-xs font-cairo font-bold">{subject.action_plan.title}</span>
                  </div>
                  <p className="text-sm font-tajawal text-foreground leading-relaxed">
                    {subject.action_plan.description}
                  </p>
                  {subject.action_plan.hint && (
                    <p className="text-[11px] mt-1.5 text-muted-foreground font-tajawal">
                      ← {subject.action_plan.hint}
                    </p>
                  )}
                </div>
              )}

              {/* Empty cleanly when there are no tags / plan */}
              {!subject.strengths?.length && !subject.weaknesses?.length && !subject.action_plan && (
                <p className="text-xs text-muted-foreground font-tajawal text-center py-2">
                  {isRTL ? 'لا توجد ملاحظات إضافية لهذه المادة بعد' : 'No additional notes yet'}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

const StudentInsightsPanel = ({ childId }) => {
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [data, setData] = useState(null);
  const [openIdx, setOpenIdx] = useState(null);
  const reqSeq = useRef(0);

  useEffect(() => {
    if (!childId) return;
    const seq = ++reqSeq.current;
    if (data == null) setLoading(true);
    setError(false);
    (async () => {
      try {
        const res = await api.get(`/parent-portal/child/${childId}/insights`);
        if (seq !== reqSeq.current) return;
        setData(res.data);
        setOpenIdx(null);
      } catch {
        if (seq !== reqSeq.current) return;
        setError(true);
      } finally {
        if (seq === reqSeq.current) setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId, token]);

  if (loading && !data) {
    return (
      <LoadingState variant="section" />
    );
  }

  if (error || !data) {
    return (
      <Card className="rounded-2xl border border-border shadow-sm bg-card">
        <CardContent className="p-4 text-center text-sm text-muted-foreground font-tajawal">
          {isRTL ? 'تعذر تحميل الرؤى' : 'Unable to load insights'}
        </CardContent>
      </Card>
    );
  }

  const { general_insights, subjects, hakim_summary, parent_tips, status, empty_hint_ar } = data;
  const hasGeneral = (general_insights?.strengths?.length || 0) + (general_insights?.weaknesses?.length || 0) > 0;
  const hasSubjects = Array.isArray(subjects) && subjects.length > 0;

  if (status === 'insufficient_data') {
    return (
      <Card className="rounded-2xl border border-border shadow-sm bg-card">
        <CardContent className="p-6 text-center">
          <Sparkles className="h-10 w-10 mx-auto mb-2 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground font-tajawal">
            {empty_hint_ar || (isRTL ? 'لا توجد بيانات كافية لعرض الرؤى بعد' : 'Not enough data for insights yet')}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div data-testid="student-insights-panel" className="space-y-3">
      {hasGeneral && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <StrengthsCard items={general_insights.strengths} isRTL={isRTL} />
          <WeaknessesCard items={general_insights.weaknesses} isRTL={isRTL} />
        </div>
      )}

      <HakimNarrative summary={hakim_summary} tips={parent_tips} isRTL={isRTL} />

      {hasSubjects && (
        <Card className="rounded-2xl border border-border shadow-sm bg-card overflow-hidden">
          <div className="bg-gradient-to-l from-brand-navy/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/15 px-4 py-2.5 border-b border-border flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-brand-navy/10 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise flex items-center justify-center">
              <BookOpen className="h-3.5 w-3.5" />
            </span>
            <h4 className="font-cairo font-bold text-sm text-foreground">
              {isRTL ? 'تفاصيل الأداء حسب المادة' : 'Performance by subject'}
            </h4>
          </div>
          <CardContent className="p-3 space-y-2">
            {subjects.map((s, idx) => (
              <SubjectRow
                key={s.id || s.name}
                subject={s}
                isOpen={openIdx === idx}
                onToggle={() => setOpenIdx(openIdx === idx ? null : idx)}
                isRTL={isRTL}
              />
            ))}
          </CardContent>
        </Card>
      )}

      {!hasGeneral && !hasSubjects && hakim_summary?.status !== 'available' && (
        <Card className="rounded-2xl border border-border shadow-sm bg-card">
          <CardContent className="p-6 text-center">
            <GraduationCap className="h-10 w-10 mx-auto mb-2 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground font-tajawal">
              {isRTL ? 'سنُظهر الرؤى هنا فور توفر بيانات كافية للطالب' : 'Insights will appear once enough data is available'}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default StudentInsightsPanel;
