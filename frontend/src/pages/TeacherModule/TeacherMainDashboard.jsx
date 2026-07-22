import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useCanViewInternalIds } from '../../hooks/useCanViewInternalIds';
import { maskInternalId } from '../../utils/internalId';
import { formatFullDate, formatHijriDate } from '../../utils/hijriDate';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Progress } from '../../components/ui/progress';
import { toast } from 'sonner';
import {
  BookOpen, Users, Calendar, ClipboardCheck, Bell,
  Clock, CheckCircle2, AlertCircle, ChevronLeft,
  ChevronRight, FileText, CalendarDays,
  RefreshCw, MessageSquare, Play, Target, Activity, Flame, Award,
  Timer, CircleDot, School, Sparkles, Zap, TrendingUp, Star,
  FolderOpen, ArrowLeft, ArrowRight, Check, Plus, Loader2
} from 'lucide-react';
import ReactivationBanner from '../../components/teacher/ReactivationBanner';
import OnboardingTrigger from '../../components/teacher/OnboardingTour/OnboardingTrigger';

import { useTranslation } from '../../contexts/ThemeContext';
const HAKIM_CHARACTER = '/hakim-poses/teacher-helper.png';

const PeriodTimeline = ({ upcomingLessons, totalPeriods, currentPeriod, isSchoolTime, isRTL, t, onDark = false }) => {
  const periods = [];
  for (let i = 1; i <= totalPeriods; i++) {
    const lesson = upcomingLessons.find(l => l.period === i);
    let status = 'upcoming';
    if (isSchoolTime) {
      if (i < currentPeriod) status = 'done';
      else if (i === currentPeriod) status = 'active';
    }
    periods.push({ number: i, status, lesson });
  }

  const completed = periods.filter(p => p.status === 'done').length;
  const remaining = periods.filter(p => p.status === 'upcoming').length;

  // Theme-aware classes — when embedded inside the dark Welcome Card we use
  // light/translucent surfaces and white text so contrast is preserved.
  const titleCls = onDark ? 'text-white' : 'text-foreground';
  const titleIconCls = onDark ? 'text-brand-turquoise' : 'text-brand-turquoise';
  const countersCls = onDark ? 'text-white/70' : 'text-muted-foreground';
  const remainingDotCls = onDark ? 'bg-white/30' : 'bg-slate-300 dark:bg-slate-600';
  const completedDotCls = onDark ? 'bg-emerald-400' : 'bg-emerald-500';

  const doneCellCls = onDark
    ? 'bg-emerald-400/15 border-emerald-300/40'
    : 'bg-emerald-500/10 border-emerald-500/30 dark:bg-emerald-500/15';
  const activeCellCls = onDark
    ? 'bg-brand-turquoise/25 border-brand-turquoise/60 ring-2 ring-brand-turquoise/40 shadow-sm'
    : 'bg-brand-turquoise/15 border-brand-turquoise/40 ring-2 ring-brand-turquoise/30 shadow-sm';
  const upcomingCellCls = onDark
    ? 'bg-white/5 border-white/15'
    : 'bg-muted/50 border-border/50';

  const doneIconCls = onDark ? 'text-emerald-300' : 'text-emerald-600 dark:text-emerald-400';
  const activeNumCls = onDark ? 'text-white' : 'text-brand-turquoise';
  const upcomingNumCls = onDark ? 'text-white/80' : 'text-muted-foreground';

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className={`font-cairo font-bold text-sm flex items-center gap-2 ${titleCls}`}>
          <Clock className={`h-4 w-4 ${titleIconCls}`} />
          {t('schoolDayTimeline')}
        </h3>
        <div className={`flex items-center gap-3 text-xs font-tajawal ${countersCls}`}>
          <span className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${completedDotCls}`} />
            {completed} {t('periodsCompleted')}
          </span>
          <span className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${remainingDotCls}`} />
            {remaining} {t('periodsRemaining')}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        {periods.map((period) => (
          <div
            key={period.number}
            className={`flex-1 relative group cursor-default`}
          >
            <div className={`h-10 rounded-lg flex items-center justify-center transition-colors duration-300 border ${
              period.status === 'done'
                ? doneCellCls
                : period.status === 'active'
                ? activeCellCls
                : upcomingCellCls
            }`}>
              {period.status === 'done' ? (
                <Check className={`h-4 w-4 ${doneIconCls}`} />
              ) : period.status === 'active' ? (
                <div className="relative">
                  <span className={`font-cairo font-bold text-sm ${activeNumCls}`}>{period.number}</span>
                  <span className="absolute -top-0.5 -end-1 w-2 h-2 bg-brand-turquoise rounded-full animate-ping" />
                </div>
              ) : (
                <span className={`font-cairo text-sm ${upcomingNumCls}`}>{period.number}</span>
              )}
            </div>

            {period.lesson && (() => {
              const isFirst = period.number === 1;
              const isLast = period.number === totalPeriods;
              // Horizontal anchoring. Default: physically centered over the cell.
              // We deliberately pair the PHYSICAL `left-1/2` anchor with the
              // PHYSICAL `-translate-x-1/2` shift — CSS transforms are not
              // RTL-flipped, so the old logical `start-1/2` anchor pushed the
              // tooltip off to the side in RTL. Centering is direction-symmetric,
              // so physical centering is correct in both LTR and RTL.
              // First / last period: clamp to the cell's leading / trailing edge
              // so the 144px (w-36) tooltip never overflows the card.
              const posCls = isFirst
                ? 'start-0'
                : isLast
                ? 'end-0'
                : 'left-1/2 -translate-x-1/2';
              // Caret tracks the anchoring so it always points back at the cell.
              const caretCls = isFirst
                ? 'start-5'
                : isLast
                ? 'end-5'
                : 'left-1/2 -translate-x-1/2';
              return (
                <div
                  role="tooltip"
                  className={`absolute bottom-full mb-2 ${posCls} w-36 z-30 opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0 pointer-events-none transition-all duration-200 ease-out motion-reduce:transition-none`}
                >
                  <div className="relative bg-popover border border-border rounded-lg shadow-lg p-2 text-xs font-tajawal text-start">
                    <p className="font-bold font-cairo text-foreground truncate">{period.lesson.subject}</p>
                    <p className="text-muted-foreground truncate">{period.lesson.class}</p>
                    <p className="text-muted-foreground">{period.lesson.time}</p>
                    <span className={`absolute top-full ${caretCls} -mt-1 w-2 h-2 rotate-45 bg-popover border-b border-r border-border`} aria-hidden="true" />
                  </div>
                </div>
              );
            })()}
          </div>
        ))}
      </div>
    </div>
  );
};

// Personal-calendar event-type meta for the IT home widget. Mirrors the
// EVENT_TYPES map in components/dashboard/AdminCalendar.jsx (the تقويمي
// الشخصي tab) so the two surfaces label/color events identically.
const IT_EVENT_TYPE_META = {
  trip:    { label_ar: 'رحلة',         label_en: 'Trip',    dot: 'bg-violet-500' },
  parents: { label_ar: 'أولياء الأمور', label_en: 'Parents', dot: 'bg-pink-500' },
  report:  { label_ar: 'تقرير',        label_en: 'Report',  dot: 'bg-amber-500' },
  exam:    { label_ar: 'اختبار',       label_en: 'Exam',    dot: 'bg-emerald-500' },
  holiday: { label_ar: 'إجازة',        label_en: 'Holiday', dot: 'bg-sky-500' },
  meeting: { label_ar: 'اجتماع',       label_en: 'Meeting', dot: 'bg-blue-500' },
};

const IT_CAL_SHORT_MONTHS_AR = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
const IT_CAL_SHORT_MONTHS_EN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

// Date-only formatting: parse the Y-M-D string manually — never
// `new Date(iso)` on a date-only value (UTC-midnight off-by-one).
const formatItEventDate = (isoDate, isRTL) => {
  if (!isoDate || typeof isoDate !== 'string') return '';
  const [, m, d] = isoDate.split('-').map(Number);
  if (!m || !d) return isoDate;
  const months = isRTL ? IT_CAL_SHORT_MONTHS_AR : IT_CAL_SHORT_MONTHS_EN;
  return `${d} ${months[m - 1] || ''}`;
};

const localTodayISODate = () => {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
};

export default function TeacherMainDashboard() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const canViewInternalIds = useCanViewInternalIds();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [now, setNow] = useState(new Date());
  const [stats, setStats] = useState({
    myClasses: 0,
    myStudents: 0,
    todayLessons: 0,
    pendingAttendance: 0,
    pendingAssessments: 0,
    upcomingLessons: [],
    totalSessions: 0,
    subjectsCount: 0
  });
  const [recentActivities, setRecentActivities] = useState([]);
  const [classes, setClasses] = useState([]);
  const [teachingMetrics, setTeachingMetrics] = useState(null);
  const [classHealthData, setClassHealthData] = useState([]);
  const [riskAlerts, setRiskAlerts] = useState([]);
  const [hakimLoading, setHakimLoading] = useState(false);
  const [dayStatus, setDayStatus] = useState(null);
  const [dayStatusError, setDayStatusError] = useState(false);
  const [portfolioProgress, setPortfolioProgress] = useState(0);
  // Task #310 — IT brand-new-workspace empty state. We only fetch the IT
  // personal-calendar event count when the signed-in user is an Independent
  // Teacher; principals/teachers in real schools never see this card and
  // never hit the IT-only endpoint.
  const isIndependentTeacher = user?.role === 'independent_teacher';
  const [itEventsCount, setItEventsCount] = useState(null);
  // Personal-calendar home widget shares the SAME fetch as the empty-state
  // count above (single source of truth = /independent-teacher/calendar
  // /events, the exact endpoint the تقويمي الشخصي tab reads), so the home
  // page and the Schedule & Calendar tab can never disagree.
  const [itEvents, setItEvents] = useState(null);
  const todayISODate = localTodayISODate();
  // Today's + future events, soonest first, capped for the compact card.
  const itUpcomingEvents = useMemo(() => {
    if (!Array.isArray(itEvents)) return [];
    return itEvents
      .filter((e) => typeof e?.date === 'string' && e.date >= todayISODate)
      .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
      .slice(0, 5);
  }, [itEvents, todayISODate]);

  const teacherId = user?.teacher_id || user?.id;
  const teacherSubject = user?.primary_subject_name || user?.specialization || '';
  const schoolName = user?.school_name || user?.tenant_name || '';

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);

  const fetchDayStatus = useCallback(async () => {
    try {
      const res = await api.get('/school/day-status');
      setDayStatus(res.data);
      setDayStatusError(false);
    } catch (err) {
      setDayStatusError(true);
    }
  }, [api]);

  useEffect(() => {
    fetchDayStatus();
    const interval = setInterval(fetchDayStatus, 60000);
    return () => clearInterval(interval);
  }, [fetchDayStatus]);

  const hasDataRef = useRef(false);
  const fetchTeacherData = useCallback(async ({ silent = false } = {}) => {
    if (!teacherId) return;
    // Task #145 — when refreshing in the background (WS publish or 5-min
    // poll), don't toggle the global loading skeleton if the dashboard
    // already has data on screen. Keeps the update truly silent for the
    // teacher: cards stay rendered and only the underlying numbers/lists
    // change when the new payload arrives. We track "has data" via a ref
    // so the callback identity doesn't change on every state update.
    if (!silent || !hasDataRef.current) setLoading(true);
    try {
      const dashboardRes = await api.get(`/teacher/dashboard/${teacherId}`).catch(() => null);
      if (dashboardRes?.data) {
        const data = dashboardRes.data;
        setStats({
          myClasses: data.stats.my_classes || 0,
          myStudents: data.stats.my_students || 0,
          todayLessons: data.stats.today_lessons || 0,
          pendingAttendance: data.stats.pending_attendance || 0,
          pendingAssessments: 0,
          totalSessions: data.stats.weekly_sessions || 0,
          subjectsCount: data.stats.subjects_count || 0,
          upcomingLessons: data.today_schedule?.map(lesson => ({
            id: lesson.id,
            schedule_session_id: lesson.schedule_session_id || lesson.id,
            time: lesson.time || lesson.start_time,
            end_time: lesson.end_time,
            period: lesson.period || lesson.slot_number,
            subject: lesson.subject || lesson.subject_name,
            class: lesson.class_name,
            class_id: lesson.class_id,
            subject_id: lesson.subject_id,
            lesson_topic: lesson.lesson_topic || lesson.lesson_name || '',
            status: lesson.status || 'upcoming'
          })) || []
        });
        setClasses(data.classes || []);
        setRecentActivities(data.recent_activities?.map(a => ({
          type: a.type?.includes('attendance') ? 'attendance' :
                a.type?.includes('assessment') ? 'assessment' : 'notification',
          message: a.message,
          time: a.time ? new Date(a.time).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US') : (t('recently'))
        })) || []);
        hasDataRef.current = true;
      }
    } catch (error) {
      console.error('Error fetching teacher data:', error);
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, teacherId, isRTL]);

  const fetchMetrics = useCallback(async () => {
    if (!teacherId) return;
    try {
      const res = await api.get(`/teacher/${teacherId}/class-metrics`);
      if (res.data) {
        const cls = Object.values(res.data);
        if (cls.length > 0) {
          const avgAttendance = Math.round(cls.reduce((s, c) => s + (c.attendance_rate || 0), 0) / cls.length);
          const avgParticipation = Math.round(cls.reduce((s, c) => s + (c.participation_rate || 0), 0) / cls.length);
          const avgPerformance = Math.round(cls.reduce((s, c) => s + (c.avg_performance || 0), 0) / cls.length);
          const totalSessions = cls.reduce((s, c) => s + (c.total_sessions || 0), 0);
          setTeachingMetrics({ avgAttendance, avgParticipation, avgPerformance, totalSessions, classCount: cls.length });
        }
      }
    } catch (e) { console.error('Error fetching teacher metrics:', e); }
  }, [teacherId, api]);

  const fetchPortfolioProgress = useCallback(async () => {
    if (!teacherId) return;
    try {
      const res = await api.get(`/teacher/achievements/${teacherId}`).catch(() => null);
      if (res?.data) {
        const earned = Number(res.data.total_earned) || 0;
        const total = Number(res.data.total_badges) || 0;
        const pct = total > 0 ? Math.round((earned / total) * 100) : 0;
        setPortfolioProgress(Number.isFinite(pct) ? pct : 0);
      }
    } catch (e) { /* silent */ }
  }, [api, teacherId]);

  useEffect(() => { fetchTeacherData(); }, [fetchTeacherData]);
  useEffect(() => { fetchMetrics(); }, [fetchMetrics]);
  useEffect(() => { fetchPortfolioProgress(); }, [fetchPortfolioProgress]);

  // Task #310 — count personal-calendar events for IT only, so we can show
  // the brand-new-workspace empty state when classes/students/events are
  // all zero. We keep `itEventsCount` as a tri-state (null = unknown) and
  // only flip the empty-state on a *confirmed* zero so a transient API
  // failure can't falsely hide a workspace that actually has events.
  useEffect(() => {
    if (!isIndependentTeacher) { setItEventsCount(0); setItEvents([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/independent-teacher/calendar/events');
        const data = Array.isArray(res?.data) ? res.data : (res?.data?.events || []);
        if (!cancelled) { setItEventsCount(data.length); setItEvents(data); }
      } catch (e) {
        // Count stays null — the Task #310 empty-state stays suppressed on
        // transient errors. The widget, however, must not spin forever:
        // resolve it to an empty list so it shows the calm empty state.
        if (!cancelled) setItEvents([]);
      }
    })();
    return () => { cancelled = true; };
  }, [api, isIndependentTeacher]);

  // Task #145 — silently refresh today's lessons block when the school
  // admin publishes a new schedule. WebSocketContext bridges the tenant
  // ``schedule_published`` WS frame to a window CustomEvent. We pass
  // ``silent: true`` so the dashboard cards stay on screen — only the
  // numbers/lists update once the new payload arrives.
  useEffect(() => {
    const onPublished = () => { fetchTeacherData({ silent: true }); };
    window.addEventListener('nassaq:schedule_published', onPublished);
    return () => window.removeEventListener('nassaq:schedule_published', onPublished);
  }, [fetchTeacherData]);

  useEffect(() => {
    const fetchHakimData = async () => {
      if (!classes || classes.length === 0 || !user?.tenant_id) return;
      setHakimLoading(true);
      try {
        const healthPromises = classes.map(cls =>
          api.get(`/hakim/class/${cls.id}/health?school_id=${user.tenant_id}`).catch(() => null)
        );
        const healthResults = await Promise.all(healthPromises);
        const healthData = healthResults.filter(r => r?.data).map(r => r.data).sort((a, b) => b.health_score - a.health_score);
        setClassHealthData(healthData);

        const riskPromises = classes.map(cls =>
          api.get(`/classes/${cls.id}/students`).catch(() => ({ data: [] }))
        );
        const studentsResults = await Promise.all(riskPromises);
        const allStudents = studentsResults.flatMap(r => r?.data || []);
        const riskChecks = allStudents.map(s =>
          api.get(`/hakim/student/${s.id}/risk?school_id=${user.tenant_id}`).catch(() => null)
        );
        const riskResults = await Promise.all(riskChecks);
        const alerts = riskResults.filter(r => r?.data && (r.data.risk_category === 'critical' || r.data.risk_category === 'high')).map(r => r.data);
        setRiskAlerts(alerts);
      } catch (e) { console.error('Error fetching Hakim data:', e); } finally { setHakimLoading(false); }
    };
    fetchHakimData();
  }, [classes, user, api]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchTeacherData(), fetchMetrics(), fetchDayStatus(), fetchPortfolioProgress()]);
    setRefreshing(false);
    toast.success(t('dataRefreshed'));
  };

  const dateInfo = useMemo(() => {
    try {
      return formatFullDate(now, isRTL ? 'ar' : 'en');
    } catch (e) { return null; }
  }, [now, isRTL]);

  const progress = dayStatus?.progress ?? 0;
  const isSchoolTime = dayStatus?.is_school_time ?? false;
  const currentPeriod = dayStatus?.current_period ?? 0;
  const totalPeriods = dayStatus?.total_periods ?? 7;
  const isBreak = dayStatus?.is_break ?? false;
  const schoolDayNumber = dayStatus?.school_day_number ?? dayStatus?.day_number ?? 0;
  const dayStart = dayStatus?.day_start ?? '07:00';
  const dayEnd = dayStatus?.day_end ?? '13:15';

  const currentLesson = isSchoolTime
    ? (stats.upcomingLessons.find(l => l.period === currentPeriod) || null)
    : (stats.upcomingLessons[0] || null);
  const nextLesson = (() => {
    const next = stats.upcomingLessons.find(l => l.period > (isSchoolTime ? currentPeriod : 0));
    if (next && currentLesson && next.period === currentLesson.period) return null;
    if (!isSchoolTime && next === currentLesson) return stats.upcomingLessons[1] || null;
    return next || null;
  })();
  const NavArrow = isRTL ? ChevronLeft : ChevronRight;

  const handleStartClass = (lesson) => {
    const lessonData = {
      lesson,
      schedule_session_id: lesson.schedule_session_id,
      class_id: lesson.class_id,
      subject_id: lesson.subject_id
    };
    sessionStorage.setItem('current_lesson', JSON.stringify(lessonData));
    navigate('/teacher/session/start', { state: lessonData });
  };

  const formatTimeLabel = (timeStr) => {
    if (!timeStr) return '';
    const [h, m] = timeStr.split(':').map(Number);
    const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
    const ampm = h < 12 ? t('am') : t('pm');
    return `${isRTL ? h : h12}:${m.toString().padStart(2, '0')} ${ampm}`;
  };

  // Task #310 — Brand-new IT workspace: show a single centered welcome
  // empty-state card matching the dashed workspace-accent style used by
  // the rest of the IT onboarding triad (classes / students / schedule)
  // and the lesson planner / personal calendar pages. Reverts to the
  // normal dashboard the moment the workspace has at least one class.
  // Non-IT roles' dashboards are unchanged.
  const itDashboardIsEmpty =
    isIndependentTeacher
    && !loading
    && itEventsCount !== null
    && (stats.myClasses || 0) === 0
    && (stats.myStudents || 0) === 0
    && itEventsCount === 0;

  if (itDashboardIsEmpty) {
    return (
      <Sidebar>
        <div
          className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950"
          dir={isRTL ? 'rtl' : 'ltr'}
        >
          <div className="p-4 md:p-6 max-w-[1400px] mx-auto space-y-5">
            <ReactivationBanner />
            <OnboardingTrigger />
            <div className="flex items-center justify-center min-h-[60vh]">
              <Card
                className="border-dashed border-workspace-accent-border bg-workspace-accent-light/30 w-full max-w-xl"
                data-testid="teacher-dashboard-empty-state-it"
              >
                <CardContent className="text-center py-16 px-6">
                  <Sparkles className="h-16 w-16 mx-auto mb-4 text-workspace-accent" />
                  <h3 className="font-bold text-lg mb-2 font-cairo text-workspace-accent-fg">
                    {t('itEmptyDashboardTitle')}
                  </h3>
                  <p className="text-muted-foreground text-sm font-tajawal mb-5 max-w-md mx-auto leading-relaxed">
                    {t('itEmptyDashboardDescription')}
                  </p>
                  <Button
                    onClick={() => navigate('/teacher/classes')}
                    className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 px-5"
                    data-testid="teacher-dashboard-empty-state-cta"
                  >
                    <Plus className="h-4 w-4" />
                    {t('itEmptyDashboardCta')}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  if (loading) {
    return (
      <Sidebar>
        <div className="flex flex-col items-center justify-center h-96 gap-4">
          <div className="relative">
            <div className="w-16 h-16 rounded-full border-4 border-brand-turquoise/20 border-t-brand-turquoise animate-spin" />
          </div>
          <p className="text-sm text-muted-foreground font-tajawal">{t('loadingCommandCenter')}</p>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto">

          {/* Task #222 — IT post-login reactivation banner */}
          <ReactivationBanner />

          {/* Task #250 — IT first-login guided tour (welcome card + coach-marks). */}
          <OnboardingTrigger />

          {/* Top Action Bar */}
          <div className="flex items-center justify-between">
            <h1 className="font-cairo font-bold text-xl text-foreground">{t('teacherDashboardTitle')}</h1>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                className="rounded-xl gap-2 font-tajawal text-xs hover:bg-brand-turquoise/10 hover:text-brand-turquoise"
                /* 2026-05-19 — IA refactor: the IT "جدولي" surface moved
                   into the unified Schedule & Calendar hub at
                   /teacher/planning, where "schedule" is the default
                   tab (TimeManagementHubPage maps an empty ?tab= to
                   the schedule view, so no query string is needed).
                   Regular teachers keep the legacy /teacher/schedule
                   route — /teacher/planning is gated to
                   `independent_teacher` only and would 403 them. */
                onClick={() => navigate(isIndependentTeacher ? '/teacher/planning' : '/teacher/schedule')}
              >
                <Calendar className="h-4 w-4" />
                {t('mySchedule')}
              </Button>

              <button
                className="flex flex-col items-center gap-0.5 px-3 py-1 rounded-xl hover:bg-brand-purple/10 transition-colors group"
                onClick={() => navigate('/teacher/achievements')}
              >
                <div className="flex items-center gap-1.5">
                  <Award className="h-4 w-4 text-brand-purple group-hover:text-brand-purple" />
                  <span className="font-tajawal text-xs text-muted-foreground group-hover:text-brand-purple">{t('viewPortfolio')}</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-12 h-1.5 bg-brand-purple/10 rounded-full overflow-hidden">
                    <div className="h-full bg-brand-purple rounded-full" style={{ width: `${portfolioProgress}%` }} />
                  </div>
                  <span className="text-[10px] font-cairo font-bold text-brand-purple">{portfolioProgress}%</span>
                </div>
              </button>

              <Button size="sm" variant="outline" onClick={handleRefresh} disabled={refreshing}
                className="rounded-xl border-border/50 hover:bg-muted gap-2 font-tajawal text-xs">
                <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                {t('refresh')}
              </Button>
            </div>
          </div>

          {/* Teacher Info Rectangle */}
          <div className="relative overflow-hidden rounded-2xl bg-brand-navy p-5 md:p-6 text-white border border-white/5">
            <div className="absolute inset-0 nassaq-pattern opacity-[0.05] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(56,189,248,0.08),transparent)]" />
            <div className="absolute top-0 end-0 w-48 md:w-64 h-48 md:h-64 rounded-full bg-brand-turquoise/5 blur-3xl" />

            <div className="relative z-10">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="relative flex-shrink-0">
                    <Avatar className="h-16 w-16 border-[3px] border-brand-turquoise/40 shadow-2xl shadow-brand-turquoise/20 ring-4 ring-white/5">
                      <AvatarImage src={user?.avatar_url} alt={user?.full_name} />
                      <AvatarFallback className="bg-gradient-to-br from-brand-turquoise to-brand-purple text-white text-xl font-bold">
                        {user?.full_name?.charAt(0) || 'م'}
                      </AvatarFallback>
                    </Avatar>
                    <div className="absolute -bottom-1 -end-1 w-6 h-6 rounded-lg bg-emerald-500 flex items-center justify-center border-2 border-brand-navy shadow-lg">
                      <CheckCircle2 className="h-3 w-3 text-white" />
                    </div>
                  </div>
                  <div className="min-w-0">
                    <h2 className="font-cairo text-xl md:text-2xl font-bold truncate">
                      {t('welcomeTeacher').replace('{0}', user?.full_name || t('teacher'))}
                    </h2>
                    <p className="text-brand-turquoise font-bold font-cairo text-sm mt-0.5 truncate">
                      {teacherSubject ? t('teacherOf').replace('{0}', teacherSubject) : t('teacher')}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      <div className="flex items-center gap-1.5 text-white/40 text-xs font-tajawal bg-white/5 rounded-lg px-2.5 py-1">
                        <School className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate max-w-[200px]">{schoolName || (t('school'))}</span>
                      </div>
                      {currentLesson && (
                        <div className="flex items-center gap-1.5 text-brand-turquoise/80 text-xs font-tajawal bg-brand-turquoise/10 rounded-lg px-2.5 py-1">
                          <BookOpen className="h-3.5 w-3.5 flex-shrink-0" />
                          <span className="truncate max-w-[160px]">{currentLesson.subject}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 md:gap-6 flex-shrink-0">
                  {/* Current Date */}
                  <div className="flex items-center gap-2 md:gap-3 bg-white/5 backdrop-blur rounded-xl px-2.5 md:px-4 py-2 md:py-2.5 border border-white/10">
                    <CalendarDays className="h-4 w-4 md:h-5 md:w-5 text-brand-turquoise flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs md:text-sm font-bold font-cairo truncate">{dateInfo?.weekday || ''}</p>
                      <p className="text-[10px] md:text-[11px] text-white/50 font-tajawal truncate">{dateInfo?.full || ''}</p>
                    </div>
                  </div>

                  {/* Current Time */}
                  <div className="text-center">
                    <p className="text-2xl md:text-3xl font-bold font-cairo tabular-nums">
                      {now.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                    <p className="text-[10px] text-white/40 font-tajawal">
                      {isSchoolTime ? t('schoolInSession') : t('outsideSchoolHours')}
                    </p>
                  </div>

                  {/* School Day Number */}
                  {schoolDayNumber > 0 && (
                    <div className="flex flex-col items-center bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-xl px-2.5 md:px-4 py-1.5 md:py-2">
                      <span className="text-[9px] md:text-[10px] text-brand-turquoise/70 font-tajawal">{t('schoolDayNumber')}</span>
                      <span className="text-xl md:text-2xl font-bold font-cairo text-brand-turquoise">{schoolDayNumber}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Day Progress Bar */}
              <div className="mt-5">
                {dayStatusError && !dayStatus ? (
                <div className="flex items-center justify-between gap-3 rounded-lg bg-white/5 border border-white/10 px-3 py-2">
                  <span className="text-xs text-white/60 font-tajawal flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-white/40" aria-hidden="true" />
                    {t('dayStatusUnavailable')}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={fetchDayStatus}
                    className="h-7 px-2 text-xs text-brand-turquoise hover:bg-white/10 gap-1 font-tajawal"
                  >
                    <RefreshCw className="h-3 w-3" aria-hidden="true" />
                    {t('retry')}
                  </Button>
                </div>
                ) : (
                <>
                <div className="flex items-center justify-between mb-1.5 font-tajawal">
                  <span className="text-[10px] text-white/40">{formatTimeLabel(dayStart)}</span>
                  <div className="flex items-center gap-3">
                    {isSchoolTime && !isBreak && (
                      <span className="text-xs text-white/60 flex items-center gap-1.5">
                        <CircleDot className="h-3.5 w-3.5 text-emerald-400" />
                        {t('periodOf').replace('{0}', currentPeriod).replace('{1}', totalPeriods)}
                      </span>
                    )}
                    {isBreak && (
                      <span className="text-xs text-amber-400 flex items-center gap-1.5">
                        <Timer className="h-3.5 w-3.5" />
                        {t('break')}
                      </span>
                    )}
                    <span className={`font-cairo font-bold text-sm ${progress > 0 && isSchoolTime ? 'text-emerald-400' : 'text-white/50'}`}>
                      {progress}%
                    </span>
                  </div>
                  <span className="text-[10px] text-white/40">{formatTimeLabel(dayEnd)}</span>
                </div>
                <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-turquoise rounded-full transition-[width] duration-1000 relative"
                    style={{ width: `${progress}%` }}
                  >
                    {progress > 0 && (
                      <span className="absolute end-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg shadow-brand-turquoise/50" />
                    )}
                  </div>
                </div>
                </>
                )}
              </div>

              {/* School Day Path — integrated at the bottom of the welcome card */}
              {(!dayStatusError || dayStatus) && (
              <div className="mt-5 pt-4 border-t border-white/10">
                <PeriodTimeline
                  upcomingLessons={stats.upcomingLessons}
                  totalPeriods={totalPeriods}
                  currentPeriod={currentPeriod}
                  isSchoolTime={isSchoolTime}
                  isRTL={isRTL}
                  t={t}
                  onDark
                />
              </div>
              )}
            </div>
          </div>

          {/* School Day Section: Section title + Current Card + Upcoming Card + Timeline */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-cairo font-bold text-lg text-foreground flex items-center gap-2">
                <CalendarDays className="h-5 w-5 text-brand-turquoise" />
                {t('schoolDay')}
              </h2>
              {isSchoolTime && (
                <span className="text-xs font-tajawal text-muted-foreground flex items-center gap-1.5">
                  <CircleDot className="h-3.5 w-3.5 text-emerald-500" />
                  {t('periodOf').replace('{0}', currentPeriod).replace('{1}', totalPeriods)}
                </span>
              )}
            </div>

            {/* A) Current Session Card — primary, full width */}
            {currentLesson ? (
              <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-turquoise/10 via-brand-turquoise/5 to-transparent border-2 border-brand-turquoise/30 p-5 md:p-6 shadow-md">
                <div className="absolute top-0 end-0 w-40 h-40 rounded-full bg-brand-turquoise/10 blur-3xl pointer-events-none" />
                <div className="relative z-10 flex flex-col md:flex-row md:items-center gap-5 md:gap-6">
                  {/* Left: Time block (visual anchor on the start side in RTL = right) */}
                  <div className="flex md:flex-col items-center md:items-start gap-3 md:gap-1 md:min-w-[140px] md:order-last md:ms-auto md:text-end">
                    <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-brand-turquoise/25 font-cairo text-[11px] px-2.5 py-0.5 self-start md:self-end">
                      <CircleDot className="h-3 w-3 me-1 animate-pulse" />
                      {t('currentClassNow')}
                    </Badge>
                    <div className="flex md:flex-col items-baseline md:items-end gap-2 md:gap-0">
                      <span className="font-mono font-bold text-2xl md:text-3xl text-brand-turquoise tabular-nums leading-none">
                        {currentLesson.time}
                      </span>
                      {currentLesson.end_time && (
                        <span className="font-mono text-xs text-muted-foreground tabular-nums">
                          — {currentLesson.end_time}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Center: Title + meta */}
                  <div className="min-w-0 flex-1">
                    <h3 className="font-cairo font-bold text-2xl md:text-3xl text-foreground mb-1.5 truncate">
                      {currentLesson.subject}
                    </h3>
                    {currentLesson.lesson_topic && (
                      <p className="text-sm text-foreground/70 font-tajawal mb-2 line-clamp-1">
                        <span className="text-muted-foreground">{t('lessonTopic')}:</span>{' '}
                        <span className="font-medium">{currentLesson.lesson_topic}</span>
                      </p>
                    )}
                    <div className="flex items-center gap-3 text-sm text-muted-foreground font-tajawal flex-wrap">
                      <span className="flex items-center gap-1.5">
                        <BookOpen className="h-4 w-4 flex-shrink-0 text-brand-turquoise/70" />
                        {currentLesson.class}
                      </span>
                      <span className="text-border">•</span>
                      <span>{t('periodNumber')} {currentLesson.period}</span>
                    </div>
                  </div>

                  {/* Center action: Start session */}
                  <Button
                    size="lg"
                    className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-xl px-6 md:px-8 py-6 font-cairo font-bold text-base shadow-lg shadow-brand-navy/20 hover:shadow-xl transition-shadow flex-shrink-0 self-stretch md:self-center"
                    onClick={() => handleStartClass(currentLesson)}
                  >
                    <Play className="h-5 w-5 me-2" />
                    {t('startClass')}
                  </Button>
                </div>
              </div>
            ) : (
              (() => {
                const hasAnyToday = stats.upcomingLessons.length > 0;
                const hasFutureToday = hasAnyToday && stats.upcomingLessons.some(
                  l => l.period > (isSchoolTime ? currentPeriod : 0)
                );
                let title, hint;
                if (!hasAnyToday) {
                  title = t('noClassesScheduled');
                  hint = t('enjoyYourDay');
                } else if (hasFutureToday) {
                  title = t('noClassRightNow');
                  hint = t('noClassRightNowHint');
                } else {
                  title = t('allClassesDoneToday');
                  hint = t('allClassesDoneTodayHint');
                }
                return (
                  <div className="rounded-2xl border-2 border-dashed border-border/50 p-8 text-center bg-card/40">
                    <Calendar className="h-12 w-12 mx-auto mb-3 text-muted-foreground/20" />
                    <p className="text-muted-foreground font-tajawal text-lg font-medium">{title}</p>
                    <p className="text-muted-foreground/60 font-tajawal text-sm mt-1">{hint}</p>
                  </div>
                );
              })()
            )}

            {/* B) Upcoming Session Card — secondary, directly below current */}
            {nextLesson ? (
              <div className="rounded-2xl border border-border/60 bg-card p-4 md:p-5 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                  <Badge variant="outline" className="font-cairo text-[11px] text-muted-foreground border-border self-start sm:self-center px-2.5 py-0.5">
                    {t('nextUpcomingClass')}
                  </Badge>

                  <div className="min-w-0 flex-1">
                    <h4 className="font-cairo font-bold text-base md:text-lg text-foreground truncate">
                      {nextLesson.subject}
                    </h4>
                    <div className="flex items-center gap-3 text-xs md:text-sm text-muted-foreground font-tajawal mt-0.5 flex-wrap">
                      <span className="flex items-center gap-1.5">
                        <BookOpen className="h-3.5 w-3.5 flex-shrink-0" />
                        {nextLesson.class}
                      </span>
                      <span className="text-border">•</span>
                      <span>{t('periodNumber')} {nextLesson.period}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 sm:gap-4">
                    <div className="flex items-center gap-1.5 text-sm font-tajawal text-foreground/80">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="font-mono font-semibold tabular-nums">{nextLesson.time}</span>
                      {nextLesson.end_time && (
                        <span className="font-mono text-xs text-muted-foreground tabular-nums">— {nextLesson.end_time}</span>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-xl font-cairo border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/10 hover:text-brand-turquoise focus-visible:text-brand-turquoise"
                      onClick={() => handleStartClass(nextLesson)}
                    >
                      <Play className="h-3.5 w-3.5 me-1.5" />
                      {t('startClass')}
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-border/50 bg-card/60 p-4 flex items-center justify-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-500/60" />
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('noUpcomingClasses')}
                </p>
              </div>
            )}

            {/* C) School Day Timeline moved into the Welcome Card above */}
          </section>

          {/* IT-only: personal calendar widget — same data source as the
              تقويمي الشخصي tab in /teacher/planning (Schedule & Calendar). */}
          {isIndependentTeacher && (
            <section data-testid="it-home-personal-calendar">
              <Card className="border border-border/50 shadow-sm overflow-hidden">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <CardTitle className="flex items-center gap-3 text-lg font-cairo">
                      <div className="w-9 h-9 rounded-xl bg-workspace-accent flex items-center justify-center shadow-md">
                        <CalendarDays className="h-4 w-4 text-white" aria-hidden="true" />
                      </div>
                      <span>
                        {t('itHomeCalendarTitle')}
                        <span className="block text-xs font-tajawal font-normal text-muted-foreground mt-0.5">
                          {t('itHomeCalendarSubtitle')}
                        </span>
                      </span>
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="rounded-xl font-cairo text-workspace-accent hover:bg-workspace-accent-light/40 hover:text-workspace-accent-fg"
                      onClick={() => navigate('/teacher/planning?tab=calendar')}
                      data-testid="it-home-calendar-view-all"
                    >
                      {t('itHomeCalendarViewAll')}
                      <NavArrow className="h-4 w-4 ms-1" aria-hidden="true" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {itEvents === null ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-workspace-accent" aria-hidden="true" />
                    </div>
                  ) : itUpcomingEvents.length === 0 ? (
                    <div
                      className="text-center py-8 rounded-xl border border-dashed border-workspace-accent-border bg-workspace-accent-light/20"
                      data-testid="it-home-calendar-empty"
                    >
                      <CalendarDays className="h-10 w-10 mx-auto mb-3 text-workspace-accent opacity-40" aria-hidden="true" />
                      <p className="text-sm text-muted-foreground font-tajawal mb-4">{t('itHomeCalendarEmpty')}</p>
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl font-cairo border-workspace-accent-border text-workspace-accent hover:bg-workspace-accent-light/40"
                        onClick={() => navigate('/teacher/planning?tab=calendar')}
                        data-testid="it-home-calendar-empty-cta"
                      >
                        <Plus className="h-4 w-4 me-1" aria-hidden="true" />
                        {t('itHomeCalendarEmptyCta')}
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {itUpcomingEvents.map((event) => {
                        const meta = IT_EVENT_TYPE_META[event.type] || IT_EVENT_TYPE_META.meeting;
                        const isToday = event.date === todayISODate;
                        return (
                          <div
                            key={event.id}
                            className={`flex items-center gap-3 p-3 rounded-xl border transition-colors ${
                              isToday
                                ? 'border-workspace-accent-border bg-workspace-accent-light/30'
                                : 'border-border/50 bg-muted/20 hover:border-workspace-accent-border/60'
                            }`}
                            data-testid={`it-home-calendar-event-${event.id}`}
                          >
                            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${meta.dot}`} aria-hidden="true" />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium font-tajawal truncate">
                                {isRTL ? (event.title_ar || event.title_en) : (event.title_en || event.title_ar)}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {isRTL ? meta.label_ar : meta.label_en}
                              </p>
                            </div>
                            <div className="text-end flex-shrink-0">
                              {isToday ? (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-cairo bg-workspace-accent text-white">
                                  {t('itHomeCalendarToday')}
                                </span>
                              ) : (
                                <span className="text-xs text-muted-foreground font-tajawal whitespace-nowrap">
                                  {formatItEventDate(event.date, isRTL)}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>
          )}

          {/* Metric Cards — HIDDEN per request (logic kept intact) */}
          {false && (
          <section>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 sm:gap-3 md:gap-4">
              {[
                {
                  title: t('todaysLessons'),
                  value: stats.todayLessons,
                  subtitle: t('scheduledForToday'),
                  icon: CalendarDays,
                  gradient: 'from-violet-500 to-violet-600',
                  onClick: () => navigate('/teacher/schedule'),
                },
                {
                  title: t('myClasses'),
                  value: stats.myClasses,
                  subtitle: t('assignedClasses'),
                  icon: BookOpen,
                  gradient: 'from-blue-500 to-blue-600',
                  onClick: () => navigate('/teacher/classes'),
                },
                {
                  title: t('myStudents'),
                  value: stats.myStudents,
                  subtitle: t('totalStudents'),
                  icon: Users,
                  gradient: 'from-emerald-500 to-emerald-600',
                  onClick: () => navigate('/teacher/students'),
                },
                {
                  title: t('openTasks'),
                  value: stats.pendingAttendance,
                  subtitle: t('awaitingCompletion'),
                  icon: AlertCircle,
                  gradient: stats.pendingAttendance > 0 ? 'from-orange-500 to-orange-600' : 'from-slate-500 to-slate-600',
                  onClick: () => navigate('/teacher/tasks'),
                },
                {
                  title: t('weeklySessions'),
                  value: stats.totalSessions,
                  subtitle: t('thisWeek'),
                  icon: Activity,
                  gradient: 'from-teal-500 to-teal-600',
                  onClick: () => navigate('/teacher/schedule'),
                },
              ].map((card, i) => (
                <button
                  key={i}
                  onClick={card.onClick}
                  className={`relative overflow-hidden rounded-xl sm:rounded-2xl bg-gradient-to-br ${card.gradient} p-3 sm:p-5 text-white cursor-pointer group shadow-lg hover:shadow-xl transition-shadow duration-300 border border-white/10 text-start w-full`}
                >
                  <div className="absolute top-0 end-0 w-20 sm:w-24 h-20 sm:h-24 rounded-full bg-white/5 -translate-y-1/2 translate-x-1/2" />
                  <div className="relative z-10 flex items-start justify-between">
                    <div className="space-y-1 sm:space-y-2 min-w-0">
                      <p className="text-[11px] sm:text-sm font-tajawal text-white/70 truncate">{card.title}</p>
                      <p className="text-2xl sm:text-3xl md:text-4xl font-bold font-cairo">{card.value}</p>
                      <p className="text-[10px] sm:text-xs font-tajawal text-white/50 truncate">{card.subtitle}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1 sm:gap-2 flex-shrink-0">
                      <div className="w-8 h-8 sm:w-11 sm:h-11 rounded-lg sm:rounded-xl bg-white/15 backdrop-blur-sm flex items-center justify-center group-hover:scale-110 transition-transform">
                        <card.icon className="h-3.5 w-3.5 sm:h-5 sm:w-5 text-white" />
                      </div>
                      <NavArrow className="h-3 w-3 sm:h-4 sm:w-4 text-white/30 group-hover:text-white/70 transition-colors" />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </section>
          )}

          {/* Teaching Performance — HIDDEN per request (logic kept intact) */}
          {false && teachingMetrics && (
            <Card className="border border-border/50 shadow-sm overflow-hidden">
              <CardContent className="p-0">
                <div className="bg-gradient-to-r from-brand-turquoise/5 to-brand-navy/5 px-6 py-4 border-b border-border/30">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-turquoise to-brand-navy flex items-center justify-center shadow-lg shadow-brand-turquoise/20">
                      <TrendingUp className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <h3 className="font-cairo font-bold text-foreground text-lg">{t('teachingPerformance')}</h3>
                      <p className="text-xs text-muted-foreground font-tajawal">{t('dataFrom').replace('{0}', teachingMetrics.classCount)}</p>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border/30">
                  {[
                    { label: t('attendanceRate2'), value: teachingMetrics.avgAttendance, icon: CheckCircle2, color: 'text-emerald-600', bgIcon: 'from-emerald-500 to-emerald-600' },
                    { label: t('participation'), value: teachingMetrics.avgParticipation, icon: Activity, color: 'text-blue-600', bgIcon: 'from-blue-500 to-blue-600' },
                    { label: t('performance3'), value: teachingMetrics.avgPerformance, icon: Target, color: 'text-purple-600', bgIcon: 'from-purple-500 to-purple-600' },
                    { label: t('totalSessions'), value: teachingMetrics.totalSessions, icon: Flame, color: 'text-amber-600', bgIcon: 'from-amber-500 to-amber-600', isCount: true },
                  ].map(metric => (
                    <div key={metric.label} className="text-center p-3 sm:p-5 bg-background">
                      <div className={`w-9 h-9 sm:w-11 sm:h-11 mx-auto rounded-lg sm:rounded-xl bg-gradient-to-br ${metric.bgIcon} flex items-center justify-center mb-2 sm:mb-3 shadow-md`}>
                        <metric.icon className="h-4 w-4 sm:h-5 sm:w-5 text-white" />
                      </div>
                      <div className={`text-xl sm:text-2xl font-bold ${metric.color} font-cairo`}>
                        {metric.value}{metric.isCount ? '' : '%'}
                      </div>
                      <div className="text-[10px] sm:text-xs text-muted-foreground mt-1 font-tajawal">{metric.label}</div>
                      {!metric.isCount && <Progress value={metric.value} className="h-1 sm:h-1.5 mt-2 sm:mt-3" />}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Two Column: Recent Activities + Quick Actions + Pending Tasks — HIDDEN per request (logic kept intact) */}
          {false && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <Card className="border border-border/50 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-3 text-lg font-cairo">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-purple to-violet-600 flex items-center justify-center shadow-md">
                    <Bell className="h-4 w-4 text-white" />
                  </div>
                  {t('recentActivities')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {recentActivities.length === 0 ? (
                  <div className="text-center py-10 text-muted-foreground">
                    <Bell className="h-12 w-12 mx-auto mb-3 opacity-15" />
                    <p className="font-tajawal">{t('noRecentActivities')}</p>
                  </div>
                ) : (
                  recentActivities.map((activity, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 rounded-xl bg-muted/30 border border-border/50 hover:border-brand-turquoise/20 transition-colors group">
                      <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        activity.type === 'attendance' ? 'bg-emerald-100 dark:bg-emerald-900/30' :
                        activity.type === 'assessment' ? 'bg-blue-100 dark:bg-blue-900/30' : 'bg-orange-100 dark:bg-orange-900/30'
                      }`}>
                        {activity.type === 'attendance' ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : activity.type === 'assessment' ? (
                          <FileText className="h-4 w-4 text-blue-600" />
                        ) : (
                          <Bell className="h-4 w-4 text-orange-600" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium font-tajawal truncate">{activity.message}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">{activity.time}</p>
                      </div>
                    </div>
                  ))
                )}
                <Button variant="ghost" className="w-full rounded-xl font-cairo text-brand-turquoise hover:bg-brand-turquoise/10 hover:text-brand-turquoise focus-visible:text-brand-turquoise mt-2" onClick={() => navigate('/notifications')}>
                  {t('viewAllNotifications')}
                </Button>
              </CardContent>
            </Card>

            <div className="space-y-5">
              <Card className="border border-border/50 shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-3 text-lg font-cairo">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-turquoise to-cyan-600 flex items-center justify-center shadow-md">
                      <Zap className="h-4 w-4 text-white" />
                    </div>
                    {t('quickActions')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { icon: ClipboardCheck, label: t('attendance3'), path: '/teacher/attendance', gradient: 'from-emerald-500 to-emerald-600' },
                      { icon: FileText, label: t('assessments'), path: '/teacher/assessments', gradient: 'from-blue-500 to-blue-600' },
                      { icon: Star, label: t('behavior'), path: '/teacher/behavior', gradient: 'from-purple-500 to-purple-600' },
                      { icon: MessageSquare, label: t('communication'), path: '/teacher/communication', gradient: 'from-amber-500 to-orange-500' },
                    ].map((action, index) => (
                      <button
                        key={index}
                        className="flex flex-col items-center gap-2.5 p-4 rounded-xl border border-border/50 bg-background hover:border-brand-turquoise/30 hover:shadow-md transition-shadow group"
                        onClick={() => navigate(action.path)}
                      >
                        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${action.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
                          <action.icon className="h-5 w-5 text-white" />
                        </div>
                        <span className="font-cairo text-sm font-medium text-foreground">{action.label}</span>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="border border-border/50 shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-3 text-lg font-cairo">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center shadow-md">
                      <AlertCircle className="h-4 w-4 text-white" />
                    </div>
                    {t('pendingTasks')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-4 rounded-xl bg-orange-50 dark:bg-orange-950/20 border border-orange-200/50 dark:border-orange-800/30">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-orange-800 dark:text-orange-300 font-tajawal text-sm">{t('unrecordedAttendance2')}</span>
                      <Badge className="bg-orange-500 text-white font-cairo">{stats.pendingAttendance}</Badge>
                    </div>
                    <Button size="sm" className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white rounded-xl font-cairo shadow-md" onClick={() => navigate('/teacher/attendance')}>
                      {t('recordNow')}
                    </Button>
                  </div>
                  <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-950/20 border border-blue-200/50 dark:border-blue-800/30">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-blue-800 dark:text-blue-300 font-tajawal text-sm">{t('pendingAssessments')}</span>
                      <Badge className="bg-blue-500 text-white font-cairo">{stats.pendingAssessments}</Badge>
                    </div>
                    <Button size="sm" variant="outline" className="w-full border-blue-300 text-blue-700 hover:bg-blue-50 hover:text-blue-700 focus-visible:text-blue-700 rounded-xl font-cairo" onClick={() => navigate('/teacher/assessments')}>
                      {t('completeAssessment')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
          )}

          {/* Hakim AI Insights — HIDDEN per request (logic kept intact) */}
          {false && (classHealthData.length > 0 || riskAlerts.length > 0 || hakimLoading) && (
            <Card className="border border-brand-purple/20 shadow-sm overflow-hidden">
              <CardHeader className="pb-3 bg-gradient-to-r from-brand-purple/5 to-transparent border-b border-brand-purple/10">
                <div className="flex items-center gap-3">
                  <img src={HAKIM_CHARACTER} alt="حكيم" className="hakim-img w-20 h-20 rounded-2xl object-contain border-2 border-brand-purple/30 shadow-lg bg-gradient-to-br from-violet-50 to-cyan-50 p-1" style={{ animation: 'hakimRxFloat 4s ease-in-out infinite' }} />
                  <style>{`@keyframes hakimRxFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }`}</style>
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg font-cairo">
                      {t('hakimAiInsights')}
                      <Sparkles className="h-4 w-4 text-brand-purple animate-pulse" />
                    </CardTitle>
                    <CardDescription className="font-tajawal text-xs">
                      {t('automatedClassHealthAndRiskAlerts')}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-5">
                {hakimLoading ? (
                  <div className="flex items-center justify-center py-8 gap-3">
                    <div className="w-8 h-8 rounded-full border-2 border-brand-purple/20 border-t-brand-purple animate-spin" />
                    <span className="text-sm text-muted-foreground font-tajawal">{t('analyzing')}</span>
                  </div>
                ) : (
                  <div className="space-y-5">
                    {classHealthData.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-muted-foreground mb-3 font-cairo flex items-center gap-2">
                          <Activity className="h-4 w-4 text-brand-turquoise" />
                          {t('classHealth')}
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {classHealthData.map(cls => (
                            <div key={cls.class_id} className={`p-4 rounded-xl border transition-shadow hover:shadow-md ${
                              cls.health_score >= 80 ? 'border-emerald-200/50 bg-emerald-50/50 dark:bg-emerald-950/20' :
                              cls.health_score >= 65 ? 'border-blue-200/50 bg-blue-50/50 dark:bg-blue-950/20' :
                              cls.health_score >= 50 ? 'border-yellow-200/50 bg-yellow-50/50 dark:bg-yellow-950/20' :
                              'border-red-200/50 bg-red-50/50 dark:bg-red-950/20'
                            }`}>
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium font-cairo">{cls.class_name || maskInternalId(cls.class_id, canViewInternalIds)}</span>
                                <Badge className={`text-xs font-cairo ${
                                  cls.health_score >= 80 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
                                  cls.health_score >= 65 ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                                  cls.health_score >= 50 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                                  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                }`}>{cls.health_score}%</Badge>
                              </div>
                              <Progress value={cls.health_score} className="h-1.5" />
                              <div className="flex justify-between mt-2 text-xs text-muted-foreground font-tajawal">
                                <span>{cls.total_students} {t('studentsCount2')}</span>
                                <span>{cls.health_label_ar || cls.health_category}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {riskAlerts.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-muted-foreground mb-3 flex items-center gap-2 font-cairo">
                          <AlertCircle className="h-4 w-4 text-red-500" />
                          {t('riskAlerts')}
                        </h4>
                        <div className="space-y-2">
                          {riskAlerts.map((alert, idx) => (
                            <div key={idx} className={`p-3 rounded-xl border ${
                              alert.risk_category === 'critical' ? 'border-red-200/50 bg-red-50/50 dark:bg-red-950/20' :
                              'border-orange-200/50 bg-orange-50/50 dark:bg-orange-950/20'
                            }`}>
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <AlertCircle className={`h-4 w-4 ${alert.risk_category === 'critical' ? 'text-red-500' : 'text-orange-500'}`} />
                                  <span className="text-sm font-medium font-tajawal">{alert.student_name || maskInternalId(alert.student_id, canViewInternalIds)}</span>
                                </div>
                                <Badge variant="outline" className={`text-xs ${
                                  alert.risk_category === 'critical' ? 'border-red-400 text-red-600' : 'border-orange-400 text-orange-600'
                                }`}>{alert.risk_label_ar || alert.risk_category}</Badge>
                              </div>
                              {alert.factors?.length > 0 && (
                                <p className="text-xs text-muted-foreground mt-1.5 font-tajawal">{alert.factors.join(' • ')}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

        </div>
      </div>
    </Sidebar>
  );
}
