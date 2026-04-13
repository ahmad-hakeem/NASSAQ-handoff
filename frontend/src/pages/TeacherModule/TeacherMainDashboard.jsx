import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
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
  FolderOpen, ArrowLeft, ArrowRight, Check
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
const HAKIM_CHARACTER = '/hakim-poses/teacher-helper.png';

const PeriodTimeline = ({ upcomingLessons, totalPeriods, currentPeriod, isSchoolTime, isRTL, t }) => {
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

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-cairo font-bold text-sm text-foreground flex items-center gap-2">
          <Clock className="h-4 w-4 text-brand-turquoise" />
          {t('schoolDayTimeline')}
        </h3>
        <div className="flex items-center gap-3 text-xs font-tajawal text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            {completed} {t('periodsCompleted')}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />
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
                ? 'bg-emerald-500/10 border-emerald-500/30 dark:bg-emerald-500/15'
                : period.status === 'active'
                ? 'bg-brand-turquoise/15 border-brand-turquoise/40 ring-2 ring-brand-turquoise/30 shadow-sm'
                : 'bg-muted/50 border-border/50'
            }`}>
              {period.status === 'done' ? (
                <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              ) : period.status === 'active' ? (
                <div className="relative">
                  <span className="font-cairo font-bold text-sm text-brand-turquoise">{period.number}</span>
                  <span className="absolute -top-0.5 -end-1 w-2 h-2 bg-brand-turquoise rounded-full animate-ping" />
                </div>
              ) : (
                <span className="font-cairo text-sm text-muted-foreground">{period.number}</span>
              )}
            </div>

            {period.lesson && (
              <div className="absolute bottom-full mb-2 start-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-20 w-36">
                <div className="bg-popover border border-border rounded-lg shadow-lg p-2 text-xs font-tajawal">
                  <p className="font-bold font-cairo text-foreground truncate">{period.lesson.subject}</p>
                  <p className="text-muted-foreground truncate">{period.lesson.class}</p>
                  <p className="text-muted-foreground">{period.lesson.time}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default function TeacherMainDashboard() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
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
  const [notificationCount, setNotificationCount] = useState(0);
  const [portfolioProgress, setPortfolioProgress] = useState(0);

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
    } catch (err) {
      console.error('Error fetching day status:', err);
    }
  }, [api]);

  useEffect(() => {
    fetchDayStatus();
    const interval = setInterval(fetchDayStatus, 60000);
    return () => clearInterval(interval);
  }, [fetchDayStatus]);

  const fetchTeacherData = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
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

  const fetchNotificationCount = useCallback(async () => {
    try {
      const res = await api.get('/notifications/unread-count').catch(() => null);
      if (res?.data) setNotificationCount(res.data.count || 0);
    } catch (e) { /* silent */ }
  }, [api]);

  const fetchPortfolioProgress = useCallback(async () => {
    if (!teacherId) return;
    try {
      const res = await api.get(`/teacher/achievements/${teacherId}`).catch(() => null);
      if (res?.data) {
        const earned = res.data.earned_badges || 0;
        const total = res.data.total_badges || 1;
        setPortfolioProgress(Math.round((earned / total) * 100));
      }
    } catch (e) { /* silent */ }
  }, [api, teacherId]);

  useEffect(() => { fetchTeacherData(); }, [fetchTeacherData]);
  useEffect(() => { fetchMetrics(); }, [fetchMetrics]);
  useEffect(() => { fetchNotificationCount(); }, [fetchNotificationCount]);
  useEffect(() => { fetchPortfolioProgress(); }, [fetchPortfolioProgress]);

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
    await Promise.all([fetchTeacherData(), fetchMetrics(), fetchDayStatus(), fetchNotificationCount(), fetchPortfolioProgress()]);
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

  const currentLesson = stats.upcomingLessons.find(l => l.period === currentPeriod) || stats.upcomingLessons[0] || null;
  const nextLesson = stats.upcomingLessons.find(l => l.period > currentPeriod) || (stats.upcomingLessons.length > 1 ? stats.upcomingLessons[1] : null);
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
    const [h, m] = timeStr.split(':').map(Number);
    const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
    const ampm = h < 12 ? t('am') : t('pm');
    return `${isRTL ? h : h12}:${m.toString().padStart(2, '0')} ${ampm}`;
  };

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

          {/* Top Action Bar */}
          <div className="flex items-center justify-between">
            <h1 className="font-cairo font-bold text-xl text-foreground">{t('teacherDashboardTitle')}</h1>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                className="rounded-xl gap-2 font-tajawal text-xs hover:bg-brand-turquoise/10 hover:text-brand-turquoise"
                onClick={() => navigate('/teacher/schedule')}
              >
                <Calendar className="h-4 w-4" />
                {t('mySchedule')}
              </Button>

              <div className="relative">
                <Button
                  size="sm"
                  variant="ghost"
                  className="rounded-xl gap-2 font-tajawal text-xs hover:bg-brand-purple/10 hover:text-brand-purple"
                  onClick={() => navigate('/teacher/achievements')}
                >
                  <Award className="h-4 w-4" />
                  {t('viewPortfolio')}
                  <Badge className="bg-brand-purple/15 text-brand-purple border-brand-purple/25 text-[10px] font-cairo px-1.5 py-0 ms-1">
                    {portfolioProgress}%
                  </Badge>
                </Button>
              </div>

              <div className="relative">
                <Button
                  size="icon"
                  variant="ghost"
                  className="rounded-xl hover:bg-muted relative"
                  onClick={() => navigate('/notifications')}
                >
                  <Bell className="h-4.5 w-4.5" />
                  {notificationCount > 0 && (
                    <span className="absolute -top-0.5 -end-0.5 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center px-1 border-2 border-background">
                      {notificationCount > 9 ? '9+' : notificationCount}
                    </span>
                  )}
                </Button>
              </div>

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
                    <div className="flex items-center gap-2 mt-1.5">
                      <div className="flex items-center gap-1.5 text-white/40 text-xs font-tajawal bg-white/5 rounded-lg px-2.5 py-1">
                        <School className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate max-w-[200px]">{schoolName || (t('school'))}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4 md:gap-6 flex-shrink-0">
                  {/* Current Date */}
                  <div className="hidden md:flex items-center gap-3 bg-white/5 backdrop-blur rounded-xl px-4 py-2.5 border border-white/10">
                    <CalendarDays className="h-5 w-5 text-brand-turquoise" />
                    <div>
                      <p className="text-sm font-bold font-cairo">{dateInfo?.weekday || ''}</p>
                      <p className="text-[11px] text-white/50 font-tajawal">{dateInfo?.full || ''}</p>
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
                    <div className="hidden lg:flex flex-col items-center bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-xl px-4 py-2">
                      <span className="text-[10px] text-brand-turquoise/70 font-tajawal">{t('schoolDayNumber')}</span>
                      <span className="text-2xl font-bold font-cairo text-brand-turquoise">{schoolDayNumber}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Day Progress Bar */}
              <div className="mt-5">
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
              </div>
            </div>
          </div>

          {/* Period Timeline */}
          <Card className="border border-border/50 shadow-sm p-4">
            <PeriodTimeline
              upcomingLessons={stats.upcomingLessons}
              totalPeriods={totalPeriods}
              currentPeriod={currentPeriod}
              isSchoolTime={isSchoolTime}
              isRTL={isRTL}
              t={t}
            />
          </Card>

          {/* School Day Section: Current + Next Class */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Current Class - Large Card */}
            <div className="lg:col-span-2">
              {currentLesson ? (
                <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-turquoise/8 via-brand-turquoise/4 to-transparent border-2 border-brand-turquoise/25 p-5 md:p-6 shadow-sm">
                  <div className="absolute top-0 end-0 w-32 h-32 rounded-full bg-brand-turquoise/5 blur-2xl" />
                  <div className="relative z-10">
                    <div className="flex items-center justify-between mb-4">
                      <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-brand-turquoise/25 font-cairo text-xs px-3 py-1">
                        <CircleDot className="h-3 w-3 me-1.5 animate-pulse" />
                        {t('currentClassNow')}
                      </Badge>
                      <div className="flex items-center gap-1.5 text-muted-foreground text-sm font-tajawal">
                        <Clock className="h-4 w-4" />
                        <span className="font-mono font-bold">{currentLesson.time}</span>
                        {currentLesson.end_time && (
                          <>
                            <span className="text-muted-foreground/50">—</span>
                            <span className="font-mono">{currentLesson.end_time}</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <h3 className="font-cairo font-bold text-2xl text-foreground mb-1">{currentLesson.subject}</h3>
                        <div className="flex items-center gap-3 text-sm text-muted-foreground font-tajawal mb-1">
                          <span className="flex items-center gap-1.5">
                            <BookOpen className="h-3.5 w-3.5 flex-shrink-0" />
                            {currentLesson.class}
                          </span>
                          <span className="text-border">•</span>
                          <span>{t('periodNumber')} {currentLesson.period}</span>
                        </div>
                        {currentLesson.lesson_topic && (
                          <p className="text-xs text-muted-foreground/70 font-tajawal mt-1">
                            {t('lessonTopic')}: {currentLesson.lesson_topic}
                          </p>
                        )}
                      </div>

                      <Button
                        size="lg"
                        className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-xl px-8 py-3 font-cairo font-bold text-base shadow-lg shadow-brand-navy/20 hover:shadow-xl transition-shadow flex-shrink-0"
                        onClick={() => handleStartClass(currentLesson)}
                      >
                        <Play className="h-5 w-5 me-2" />
                        {t('startClass')}
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border-2 border-dashed border-border/50 p-8 text-center">
                  <Calendar className="h-12 w-12 mx-auto mb-3 text-muted-foreground/20" />
                  <p className="text-muted-foreground font-tajawal text-lg font-medium">{t('noClassesScheduled')}</p>
                  <p className="text-muted-foreground/60 font-tajawal text-sm mt-1">{t('enjoyYourDay')}</p>
                </div>
              )}
            </div>

            {/* Next Class - Smaller Card */}
            <div>
              {nextLesson ? (
                <div className="rounded-2xl border border-border/50 bg-card p-5 shadow-sm hover:shadow-md transition-shadow h-full flex flex-col justify-between">
                  <div>
                    <Badge variant="outline" className="font-cairo text-xs mb-3 text-muted-foreground border-border">
                      {t('nextUpcomingClass')}
                    </Badge>
                    <h4 className="font-cairo font-bold text-lg text-foreground mb-1">{nextLesson.subject}</h4>
                    <div className="space-y-1.5 text-sm text-muted-foreground font-tajawal">
                      <p className="flex items-center gap-1.5">
                        <BookOpen className="h-3.5 w-3.5 flex-shrink-0" />
                        {nextLesson.class}
                      </p>
                      <p className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 flex-shrink-0" />
                        {nextLesson.time}
                        {nextLesson.end_time && ` — ${nextLesson.end_time}`}
                      </p>
                      <p className="flex items-center gap-1.5">
                        <Target className="h-3.5 w-3.5 flex-shrink-0" />
                        {t('periodNumber')} {nextLesson.period}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    className="w-full mt-4 rounded-xl font-cairo border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/10"
                    onClick={() => handleStartClass(nextLesson)}
                  >
                    <Play className="h-4 w-4 me-2" />
                    {t('startClass')}
                  </Button>
                </div>
              ) : (
                <div className="rounded-2xl border border-border/50 bg-card p-5 shadow-sm h-full flex flex-col items-center justify-center text-center">
                  <CheckCircle2 className="h-10 w-10 text-emerald-400/40 mb-2" />
                  <p className="text-sm text-muted-foreground font-tajawal">
                    {t('noUpcomingClasses')}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Metric Cards */}
          <section>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3 md:gap-4">
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

          {/* Teaching Performance */}
          {teachingMetrics && (
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

          {/* Two Column: Activities + Quick Actions */}
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
                <Button variant="ghost" className="w-full rounded-xl font-cairo text-brand-turquoise hover:bg-brand-turquoise/10 mt-2" onClick={() => navigate('/notifications')}>
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
                    <Button size="sm" variant="outline" className="w-full border-blue-300 text-blue-700 hover:bg-blue-50 rounded-xl font-cairo" onClick={() => navigate('/teacher/assessments')}>
                      {t('completeAssessment')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Hakim AI Insights */}
          {(classHealthData.length > 0 || riskAlerts.length > 0 || hakimLoading) && (
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
                                <span className="text-sm font-medium font-cairo">{cls.class_name || cls.class_id}</span>
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
                                  <span className="text-sm font-medium font-tajawal">{alert.student_name || alert.student_id}</span>
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
      <HakimAssistant />
    </Sidebar>
  );
}
