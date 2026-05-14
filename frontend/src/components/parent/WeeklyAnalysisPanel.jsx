import React, { useEffect, useState, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Card, CardContent } from '../ui/card';
import { Skeleton } from '../ui/skeleton';
import {
  CalendarDays, CheckCircle, XCircle, Clock, AlertCircle,
  TrendingUp, TrendingDown, Minus, Sparkles, BookOpen, Heart, ClipboardList,
} from 'lucide-react';

const METRIC_ICONS = {
  attendance: CheckCircle,
  assessments: BookOpen,
  behaviour: Heart,
  homework: ClipboardList,
};

const METRIC_TONES = {
  attendance: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-100 dark:border-emerald-900/40',
  assessments: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/30 border-blue-100 dark:border-blue-900/40',
  behaviour: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/30 border-rose-100 dark:border-rose-900/40',
  homework: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 border-amber-100 dark:border-amber-900/40',
};

const DAY_STATUS_STYLES = {
  present: { cls: 'bg-emerald-500 text-white', Icon: CheckCircle, label: 'حاضر' },
  late:    { cls: 'bg-amber-500 text-white',   Icon: Clock,       label: 'متأخر' },
  absent:  { cls: 'bg-rose-500 text-white',    Icon: XCircle,     label: 'غائب' },
  excused: { cls: 'bg-blue-500 text-white',    Icon: AlertCircle, label: 'مستأذن' },
};

const formatWeekRange = (startIso, endIso, isRTL) => {
  if (!startIso || !endIso) return '';
  try {
    const start = new Date(startIso);
    const end = new Date(endIso);
    const fmt = new Intl.DateTimeFormat(isRTL ? 'ar-EG' : 'en-US', { day: 'numeric', month: 'short' });
    return `${fmt.format(start)} – ${fmt.format(end)}`;
  } catch {
    return `${startIso} – ${endIso}`;
  }
};

const TrendBadge = ({ trend }) => {
  if (trend === null || trend === undefined) return null;
  const Icon = trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus;
  const tone = trend > 0
    ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/40'
    : trend < 0
      ? 'text-rose-600 bg-rose-50 dark:bg-rose-950/40'
      : 'text-muted-foreground bg-muted/40';
  const sign = trend > 0 ? '+' : '';
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-md tabular-nums ${tone}`}>
      <Icon className="h-3 w-3" />
      {sign}{trend}%
    </span>
  );
};

const MetricCard = ({ metric, isRTL }) => {
  const Icon = METRIC_ICONS[metric.key] || Sparkles;
  const tone = METRIC_TONES[metric.key] || METRIC_TONES.attendance;
  const isAvailable = metric.available && metric.value !== null && metric.value !== undefined;

  let subtitle = '';
  if (metric.key === 'attendance' && metric.details) {
    const d = metric.details;
    subtitle = isRTL
      ? `${d.present} حاضر · ${d.absent} غياب · ${d.late} تأخر`
      : `${d.present} present · ${d.absent} absent · ${d.late} late`;
  } else if (metric.key === 'assessments' && metric.details) {
    subtitle = isRTL
      ? `${metric.details.items || 0} تقييم هذا الأسبوع`
      : `${metric.details.items || 0} assessments this week`;
  } else if (metric.key === 'behaviour' && metric.details) {
    subtitle = isRTL
      ? `${metric.details.positive} إيجابي · ${metric.details.negative} سلبي`
      : `${metric.details.positive} positive · ${metric.details.negative} negative`;
  } else if (metric.key === 'homework' && metric.details) {
    subtitle = isRTL
      ? `${metric.details.done} من ${metric.details.total}`
      : `${metric.details.done} of ${metric.details.total}`;
  }

  return (
    <div
      data-testid={`weekly-analysis-metric-${metric.key}`}
      className={`p-3 rounded-xl border ${isAvailable ? tone : 'bg-muted/30 border-border text-muted-foreground'}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${isAvailable ? 'bg-white/70 dark:bg-black/20' : 'bg-muted'}`}>
          <Icon className="h-4 w-4" />
        </span>
        <TrendBadge trend={metric.trend} />
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-xl font-bold tabular-nums">
          {isAvailable ? `${metric.value}${metric.unit || ''}` : '—'}
        </span>
      </div>
      <p className="text-[11px] font-tajawal mt-0.5 opacity-80">{metric.label_ar}</p>
      {isAvailable && subtitle && (
        <p className="text-[10px] text-muted-foreground mt-1 truncate" title={subtitle}>{subtitle}</p>
      )}
      {!isAvailable && (
        <p className="text-[10px] text-muted-foreground mt-1">
          {isRTL ? 'لا توجد بيانات هذا الأسبوع' : 'No data this week'}
        </p>
      )}
    </div>
  );
};

const DailyAttendanceStrip = ({ days, isRTL }) => {
  if (!Array.isArray(days) || days.length === 0) return null;
  const ordered = isRTL ? [...days].reverse() : days;
  return (
    <div className="grid grid-cols-6 gap-1.5">
      {ordered.map((d) => {
        const meta = d.status ? DAY_STATUS_STYLES[d.status] : null;
        const Icon = meta?.Icon;
        const baseCls = meta
          ? meta.cls
          : d.is_future
            ? 'bg-muted/40 text-muted-foreground/60 border border-dashed border-border'
            : 'bg-muted text-muted-foreground border border-border';
        return (
          <div
            key={d.date}
            className="flex flex-col items-center gap-1"
            title={meta ? `${d.day_ar} — ${meta.label}` : d.day_ar}
          >
            <span className={`w-full h-9 rounded-lg flex items-center justify-center ${baseCls} ${d.is_today ? 'ring-2 ring-brand-navy/40 dark:ring-brand-turquoise/50' : ''}`}>
              {Icon ? <Icon className="h-4 w-4" /> : <span className="text-[10px]">—</span>}
            </span>
            <span className="text-[10px] text-muted-foreground font-tajawal">{d.day_ar}</span>
          </div>
        );
      })}
    </div>
  );
};

const WeeklyAnalysisPanel = ({ childId }) => {
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const requestSeq = useRef(0);

  useEffect(() => {
    if (!childId) return;
    const seq = ++requestSeq.current;
    // Silent refetch when active student changes — keep the previous payload
    // visible (no spinner overlay) so the layout doesn't flash on switch.
    if (data == null) setLoading(true);
    setError(false);
    (async () => {
      try {
        const res = await api.get(`/parent-portal/child/${childId}/weekly-analysis`);
        if (seq !== requestSeq.current) return;
        setData(res.data);
      } catch {
        if (seq !== requestSeq.current) return;
        setError(true);
      } finally {
        if (seq === requestSeq.current) setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId, token]);

  if (loading && !data) {
    return (
      <Card className="rounded-2xl border border-border shadow-sm bg-card">
        <CardContent className="p-4 space-y-3">
          <Skeleton className="h-5 w-48 rounded" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-12 rounded-xl" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="rounded-2xl border border-border shadow-sm bg-card">
        <CardContent className="p-4 text-center text-sm text-muted-foreground font-tajawal">
          {isRTL ? 'تعذر تحميل التحليل الأسبوعي' : 'Unable to load weekly analysis'}
        </CardContent>
      </Card>
    );
  }

  const isInsufficient = data.status === 'insufficient_data';

  return (
    <Card
      data-testid="weekly-analysis-panel"
      className="rounded-2xl border border-border shadow-sm bg-card overflow-hidden"
    >
      <div className="bg-gradient-to-l from-brand-navy/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/15 px-4 py-3 border-b border-border">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-8 h-8 rounded-lg bg-brand-navy/10 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise flex items-center justify-center">
              <Sparkles className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h3 className="font-cairo font-bold text-sm text-foreground truncate">
                {isRTL ? 'التحليل الأكاديمي الأسبوعي' : 'Weekly Academic Analysis'}
              </h3>
              <p className="text-[11px] text-muted-foreground font-tajawal truncate">
                {data.headline_ar}
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground font-tajawal whitespace-nowrap">
            <CalendarDays className="h-3.5 w-3.5" />
            {formatWeekRange(data.week_start, data.week_end, isRTL)}
          </span>
        </div>
      </div>

      <CardContent className="p-4 space-y-4">
        {isInsufficient ? (
          <div className="py-6 text-center">
            <Sparkles className="h-10 w-10 mx-auto mb-2 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground font-tajawal">
              {data.empty_hint_ar || (isRTL ? 'لا توجد بيانات كافية للأسبوع الحالي' : 'Not enough data for this week')}
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {data.metrics.map((m) => (
                <MetricCard key={m.key} metric={m} isRTL={isRTL} />
              ))}
            </div>

            {Array.isArray(data.daily_attendance) && data.daily_attendance.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-muted-foreground font-tajawal">
                    {isRTL ? 'حضور الأسبوع يوماً بيوم' : 'Daily attendance'}
                  </span>
                </div>
                <DailyAttendanceStrip days={data.daily_attendance} isRTL={isRTL} />
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default WeeklyAnalysisPanel;
