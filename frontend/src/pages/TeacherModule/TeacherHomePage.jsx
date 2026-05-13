import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { toast } from 'sonner';
import {
  Users, BookOpen, Calendar, GraduationCap, Clock,
  Play, RefreshCw, Loader2,
  Target, Award, BarChart3,
  CheckCircle2, Activity, Flame, Building2, MapPin, Star, Briefcase,
  Bell, Check, CircleDot, Timer
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';
import { NotificationBell } from '../../components/notifications/NotificationBell';
import { formatHijriDate, formatFullDate } from '../../utils/hijriDate';
import ReactivationBanner from '../../components/teacher/ReactivationBanner';

import { useTranslation } from '../../contexts/ThemeContext';

const getTimeUntilLesson = (lessonTime) => {
  if (!lessonTime) return null;
  const now = new Date();
  const [hours, minutes] = lessonTime.split(':').map(Number);
  const lessonDate = new Date();
  lessonDate.setHours(hours, minutes, 0, 0);
  const lessonEndDate = new Date(lessonDate);
  lessonEndDate.setMinutes(lessonEndDate.getMinutes() + 45);
  const diff = lessonDate - now;
  const diffMinutes = Math.floor(diff / 60000);
  if (diff < 0 && now < lessonEndDate) return { status: 'ongoing', minutes: Math.abs(diffMinutes) };
  if (diff < 0) return { status: 'ended', minutes: Math.abs(diffMinutes) };
  if (diffMinutes <= 10) return { status: 'ready', minutes: diffMinutes };
  if (diffMinutes <= 30) return { status: 'soon', minutes: diffMinutes };
  return { status: 'upcoming', minutes: diffMinutes };
};

export default function TeacherHomePage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [now, setNow] = useState(new Date());
  const [teacherInfo, setTeacherInfo] = useState(null);
  const [todayLessons, setTodayLessons] = useState([]);
  const { nassaqError, nassaqConfirm } = useNassaqAlert();
  const [stats, setStats] = useState({
    classesCount: 0,
    studentsCount: 0,
    stage: ''
  });
  const [classMetrics, setClassMetrics] = useState(null);
  const [dayStatus, setDayStatus] = useState(null);
  const [portfolioProgress, setPortfolioProgress] = useState(0);

  const teacherId = user?.teacher_id || user?.id;

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);

  const fetchDayStatus = useCallback(async () => {
    try {
      const res = await api.get('/school/day-status');
      setDayStatus(res.data);
    } catch (err) { /* silent */ }
  }, [api]);

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

  const fetchTeacherData = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const dashboardRes = await api.get(`/teacher/dashboard/${teacherId}`).catch(() => null);
      if (dashboardRes?.data) {
        const data = dashboardRes.data;
        setTeacherInfo({
          name: data.teacher?.full_name || data.teacher?.name || user?.full_name || (t('teacher')),
          rank: data.teacher?.rank || '',
          qualification: data.teacher?.qualification || '',
          specialization: data.teacher?.specialization || '',
          school: data.school_name || (t('school')),
          schoolCity: data.school_city || '',
          schoolType: data.school_type || '',
          stage: data.school_stage || '',
          subjectNames: data.subject_names || [],
          weeklySessions: data.stats?.weekly_sessions || 0,
          subjectsCount: data.stats?.subjects_count || 0
        });
        setStats({
          classesCount: data.stats?.my_classes || 0,
          studentsCount: data.stats?.my_students || 0,
          stage: data.school_stage || ''
        });
        const lessons = (data.today_schedule || []).map((lesson, idx) => ({
          id: lesson.session_id || lesson.id || `lesson-${idx}`,
          schedule_session_id: lesson.schedule_session_id || lesson.id,
          subject: lesson.subject || lesson.subject_name || (isRTL ? 'مادة' : 'Subject'),
          className: lesson.class_name || (isRTL ? 'فصل' : 'Class'),
          classId: lesson.class_id,
          subjectId: lesson.subject_id,
          time: lesson.time || lesson.start_time || `${8 + idx}:00`,
          endTime: lesson.end_time || `${9 + idx}:00`,
          period: lesson.period || lesson.slot_number || idx + 1,
          lesson_topic: lesson.lesson_topic || lesson.lesson_name || ''
        }));
        setTodayLessons(lessons);
      } else {
        setTeacherInfo({
          name: user?.full_name || (t('teacher')),
          school: t('school'),
          stage: isRTL ? 'المرحلة' : 'Stage'
        });
      }
    } catch (error) {
      console.error('Error fetching teacher data:', error);
      nassaqError(t('errorLoadingData'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, teacherId, user, isRTL, nassaqError, t]);

  useEffect(() => {
    fetchTeacherData();
    fetchDayStatus();
    fetchPortfolioProgress();
    const interval = setInterval(() => {
      fetchTeacherData();
      fetchDayStatus();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchTeacherData, fetchDayStatus, fetchPortfolioProgress]);

  useEffect(() => {
    if (!teacherId) return;
    const fetchMetrics = async () => {
      try {
        const res = await api.get(`/teacher/${teacherId}/class-metrics`);
        if (res.data) {
          const classes = Object.values(res.data);
          if (classes.length > 0) {
            const avgAttendance = Math.round(classes.reduce((s, c) => s + (c.attendance_rate || 0), 0) / classes.length);
            const avgParticipation = Math.round(classes.reduce((s, c) => s + (c.participation_rate || 0), 0) / classes.length);
            const avgPerformance = Math.round(classes.reduce((s, c) => s + (c.avg_performance || 0), 0) / classes.length);
            const totalSessions = classes.reduce((s, c) => s + (c.total_sessions || 0), 0);
            setClassMetrics({ avgAttendance, avgParticipation, avgPerformance, totalSessions });
          }
        }
      } catch (e) { console.error('Error fetching class metrics:', e); }
    };
    fetchMetrics();
  }, [teacherId, api]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchTeacherData();
  };

  const handleStartClass = async (lesson) => {
    const lessonData = {
      lesson,
      schedule_session_id: lesson.schedule_session_id,
      class_id: lesson.classId,
      subject_id: lesson.subjectId
    };
    sessionStorage.setItem('current_lesson', JSON.stringify(lessonData));
    navigate('/teacher/session/start', { state: lessonData });
  };

  const dateInfo = useMemo(() => {
    try {
      return formatFullDate(now, isRTL ? 'ar' : 'en');
    } catch (e) { return null; }
  }, [now, isRTL]);

  const currentPeriod = dayStatus?.current_period ?? 0;
  const totalPeriods = dayStatus?.total_periods ?? 7;
  const isSchoolTime = dayStatus?.is_school_time ?? false;
  const schoolDayNumber = dayStatus?.school_day_number ?? dayStatus?.day_number ?? 0;

  const currentLesson = isSchoolTime
    ? (todayLessons.find(l => l.period === currentPeriod) || null)
    : (todayLessons[0] || null);
  const nextLesson = (() => {
    const next = todayLessons.find(l => l.period > (isSchoolTime ? currentPeriod : 0));
    if (next && currentLesson && next.period === currentLesson.period) return null;
    if (!isSchoolTime && next === currentLesson) return todayLessons[1] || null;
    return next || null;
  })();

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        {refreshing && (
          <div className="fixed top-0 inset-x-0 z-50 flex justify-center py-2 bg-brand-turquoise/10 backdrop-blur-sm">
            <Loader2 className="h-5 w-5 animate-spin text-brand-turquoise" />
          </div>
        )}

        <div className="p-4 space-y-4 max-w-lg mx-auto">

          {/* Task #222 — IT post-login reactivation banner */}
          <ReactivationBanner />

          {/* Top Action Bar (Mobile) */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Button
                size="icon"
                variant="ghost"
                className="rounded-xl h-9 w-9 hover:bg-brand-turquoise/10"
                onClick={() => navigate('/teacher/schedule')}
              >
                <Calendar className="h-4.5 w-4.5 text-brand-navy dark:text-brand-turquoise" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="rounded-xl h-9 px-2 gap-1 hover:bg-brand-purple/10"
                onClick={() => navigate('/teacher/achievements')}
              >
                <Award className="h-4 w-4 text-brand-navy dark:text-brand-turquoise" />
                <span className="text-[10px] font-cairo font-bold text-brand-purple">{portfolioProgress}%</span>
              </Button>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="relative">
                <NotificationBell />
              </div>
              <Button
                size="icon"
                variant="ghost"
                className="rounded-xl h-9 w-9 hover:bg-muted"
                onClick={handleRefresh}
                disabled={refreshing}
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {/* Teacher Info Card */}
          <Card className="overflow-hidden border-0 shadow-lg">
            <div className="relative bg-brand-navy text-white overflow-hidden">
              <div className="absolute inset-0 nassaq-pattern opacity-[0.05] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
              <CardContent className="p-5 relative">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(56,189,248,0.08),transparent)]" />
                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <Avatar className="h-14 w-14 border-2 border-brand-turquoise/40 shadow-xl">
                          <AvatarImage src={user?.avatar_url} />
                          <AvatarFallback className="bg-gradient-to-br from-brand-turquoise to-brand-purple text-white text-xl font-bold">
                            {teacherInfo?.name?.charAt(0) || 'م'}
                          </AvatarFallback>
                        </Avatar>
                        <div className="absolute -bottom-0.5 -end-0.5 w-5 h-5 rounded-md bg-emerald-500 flex items-center justify-center border-2 border-brand-navy">
                          <CheckCircle2 className="h-2.5 w-2.5 text-white" />
                        </div>
                      </div>
                      <div className="min-w-0">
                        <h1 className="font-cairo text-lg font-bold leading-tight">
                          {t('theTeacherName').replace('{0}', teacherInfo?.name)}
                        </h1>
                        {teacherInfo?.rank && (
                          <Badge className="mt-1 bg-brand-turquoise/20 text-brand-turquoise border-brand-turquoise/30 text-[11px] font-tajawal px-2 py-0">
                            <Star className="h-3 w-3 me-1" />
                            {teacherInfo.rank}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {/* School Day Number */}
                    {schoolDayNumber > 0 && (
                      <div className="flex flex-col items-center bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-xl px-3 py-1.5">
                        <span className="text-[9px] text-brand-turquoise/70 font-tajawal">{t('schoolDayNumber')}</span>
                        <span className="text-xl font-bold font-cairo text-brand-turquoise">{schoolDayNumber}</span>
                      </div>
                    )}
                  </div>

                  <div className="space-y-1.5 mb-3 ps-1">
                    <div className="flex items-center gap-2 text-white/60 text-sm">
                      <Building2 className="h-3.5 w-3.5 text-brand-turquoise/70 flex-shrink-0" />
                      <span className="font-tajawal truncate">{teacherInfo?.school}</span>
                      {teacherInfo?.schoolCity && (
                        <span className="flex items-center gap-1 text-white/40 text-xs">
                          <MapPin className="h-3 w-3" />{teacherInfo.schoolCity}
                        </span>
                      )}
                    </div>
                    {teacherInfo?.specialization && (
                      <div className="flex items-center gap-2 text-white/60 text-sm">
                        <BookOpen className="h-3.5 w-3.5 text-brand-turquoise/70 flex-shrink-0" />
                        <span className="font-tajawal truncate">{teacherInfo.specialization}</span>
                      </div>
                    )}
                  </div>

                  {/* Date + Time Row */}
                  <div className="flex items-center justify-between py-2 border-t border-white/10">
                    <p className="font-cairo text-white/70 text-sm truncate flex-1">
                      {dateInfo?.full || formatHijriDate()}
                    </p>
                    <p className="font-cairo font-bold text-lg tabular-nums text-brand-turquoise ms-3 flex-shrink-0">
                      {now.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-4 gap-2 mt-3">
                    {[
                      { icon: BookOpen, value: loading ? '-' : stats.classesCount, label: t('classes5') },
                      { icon: Users, value: loading ? '-' : stats.studentsCount, label: t('students2') },
                      { icon: Briefcase, value: loading ? '-' : (teacherInfo?.subjectsCount || 0), label: t('subjects5') },
                      { icon: Calendar, value: loading ? '-' : (teacherInfo?.weeklySessions || 0), label: t('weeklySessionsShort') },
                    ].map((item, i) => (
                      <div key={i} className="text-center p-2.5 rounded-xl bg-white/5 border border-white/5">
                        <item.icon className="h-4 w-4 mx-auto mb-1 text-brand-turquoise" />
                        <div className="font-bold text-lg leading-tight">{item.value}</div>
                        <div className="text-[9px] text-white/40 font-tajawal leading-tight">{item.label}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </div>
          </Card>

          {/* Period Timeline (Mobile) — visual schedule with end markers + counts */}
          {totalPeriods > 0 && (() => {
            const periodList = Array.from({ length: totalPeriods }, (_, i) => i + 1).map((num) => {
              let status = 'upcoming';
              if (isSchoolTime) {
                if (num < currentPeriod) status = 'done';
                else if (num === currentPeriod) status = 'active';
              }
              const lesson = todayLessons.find(l => l.period === num);
              return { num, status, lesson };
            });
            const completedCount = periodList.filter(p => p.status === 'done').length;
            const remainingCount = periodList.filter(p => p.status === 'upcoming' || p.status === 'active').length;
            return (
              <div className="bg-background border border-border/50 rounded-xl p-3 shadow-sm space-y-2.5">
                <div className="flex items-center justify-between">
                  <h3 className="font-cairo font-bold text-xs text-foreground flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-brand-turquoise" />
                    {t('schoolDayTimeline')}
                  </h3>
                  <div className="flex items-center gap-2 text-[10px] font-tajawal text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      <span className="tabular-nums">{completedCount}</span> {t('periodsCompleted')}
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-300 dark:bg-slate-600" />
                      <span className="tabular-nums">{remainingCount}</span> {t('periodsRemaining')}
                    </span>
                  </div>
                </div>
                <div className="flex items-stretch gap-1">
                  {periodList.map((p) => (
                    <div key={p.num} className="flex-1 flex flex-col items-stretch gap-0.5" title={p.lesson ? `${p.lesson.subject || ''} • ${p.lesson.className || ''} • ${p.lesson.time || ''}` : `${t('period') || 'الحصة'} ${p.num}`}>
                      <div className={`h-9 rounded-md flex items-center justify-center text-xs font-cairo font-bold transition-colors border ${
                        p.status === 'done'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                          : p.status === 'active'
                          ? 'bg-brand-turquoise/15 border-brand-turquoise/40 text-brand-turquoise ring-1 ring-brand-turquoise/30'
                          : 'bg-muted/50 border-border/50 text-muted-foreground'
                      }`}>
                        {p.status === 'done' ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : p.status === 'active' ? (
                          <span className="relative">
                            {p.num}
                            <span className="absolute -top-1 -end-1.5 w-1.5 h-1.5 bg-brand-turquoise rounded-full animate-ping" />
                          </span>
                        ) : (
                          p.num
                        )}
                      </div>
                      {p.lesson?.time && (
                        <span className="text-[8px] text-center text-muted-foreground/70 font-mono leading-none truncate">{p.lesson.time}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {classMetrics && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { label: t('attendance2'), value: `${classMetrics.avgAttendance}%`, icon: CheckCircle2, gradient: 'from-emerald-500 to-emerald-600' },
                { label: t('participationRate'), value: `${classMetrics.avgParticipation}%`, icon: Activity, gradient: 'from-blue-500 to-blue-600' },
                { label: t('performance3'), value: `${classMetrics.avgPerformance}%`, icon: Target, gradient: 'from-purple-500 to-purple-600' },
                { label: t('sessionsCount'), value: classMetrics.totalSessions, icon: Flame, gradient: 'from-amber-500 to-amber-600' },
              ].map(m => (
                <div key={m.label} className="bg-background rounded-xl p-3 text-center border border-border/50 shadow-sm">
                  <div className={`w-8 h-8 mx-auto rounded-lg bg-gradient-to-br ${m.gradient} flex items-center justify-center mb-1.5 shadow-md`}>
                    <m.icon className="h-3.5 w-3.5 text-white" />
                  </div>
                  <div className="text-base font-bold font-cairo text-foreground">{m.value}</div>
                  <div className="text-[10px] text-muted-foreground font-tajawal">{m.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Current Class Card */}
          {currentLesson && (
            <div>
              <h2 className="font-cairo font-bold text-lg text-foreground mb-3 flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-turquoise to-cyan-600 flex items-center justify-center shadow-md">
                  <Clock className="h-4 w-4 text-white" />
                </div>
                {t('currentClassNow')}
              </h2>

              <div
                className="rounded-2xl overflow-hidden shadow-lg border border-white/10"
                style={{ backgroundColor: '#0d9488' }}
              >
                <div className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <Badge className="bg-white/20 text-white border-0 animate-pulse font-cairo text-xs">
                      <CircleDot className="h-3 w-3 me-1" />
                      {t('currentPeriodLabel')}
                    </Badge>
                    <div className="flex items-center gap-1.5 text-white/80 text-sm">
                      <Clock className="h-3.5 w-3.5" />
                      <span className="font-mono font-bold">{currentLesson.time}</span>
                    </div>
                  </div>

                  <div className="mb-4">
                    <h3 className="font-cairo font-bold text-2xl text-white">{currentLesson.subject}</h3>
                    <p className="text-sm mt-0.5 text-white/60">
                      {currentLesson.className} • {t('periodNumber')} {currentLesson.period}
                    </p>
                    {currentLesson.lesson_topic && (
                      <p className="text-xs text-white/40 mt-1">{t('lessonTopic')}: {currentLesson.lesson_topic}</p>
                    )}
                  </div>

                  <Button
                    className="w-full h-13 text-lg font-bold rounded-xl font-cairo bg-white/95 text-brand-navy hover:bg-white shadow-lg transition-colors"
                    onClick={() => handleStartClass(currentLesson)}
                  >
                    <Play className="h-5 w-5 me-2" />
                    {t('startClass')}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Next Class Card */}
          {nextLesson && (
            <div>
              <h2 className="font-cairo font-bold text-base text-foreground mb-2 flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-sm">
                  <Clock className="h-3.5 w-3.5 text-white" />
                </div>
                {t('nextUpcomingClass')}
              </h2>

              <div className="rounded-xl border border-border/50 bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <h4 className="font-cairo font-bold text-base text-foreground">{nextLesson.subject}</h4>
                    <p className="text-xs text-muted-foreground font-tajawal mt-0.5">
                      {nextLesson.className} • {nextLesson.time} • {t('periodNumber')} {nextLesson.period}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="rounded-xl font-cairo border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/10 flex-shrink-0"
                    onClick={() => handleStartClass(nextLesson)}
                  >
                    <Play className="h-3.5 w-3.5 me-1" />
                    {t('startClass')}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Remaining Lessons */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : todayLessons.length === 0 ? (
            <Card className="border-dashed border-border/50">
              <CardContent className="text-center py-12">
                <Calendar className="h-12 w-12 mx-auto mb-3 text-muted-foreground/20" />
                <p className="text-muted-foreground font-tajawal">{t('noClassesScheduled')}</p>
                <p className="text-muted-foreground/60 font-tajawal text-sm mt-1">{t('enjoyYourDay')}</p>
              </CardContent>
            </Card>
          ) : todayLessons.length > 2 ? (
            <div>
              <h2 className="font-cairo font-bold text-base text-foreground mb-2">
                {t('otherClasses')}
              </h2>
              <div className="space-y-2">
                {todayLessons.slice(2).map((lesson) => {
                  const timeStatus = getTimeUntilLesson(lesson.time);
                  const isEnded = timeStatus?.status === 'ended';
                  return (
                    <div
                      key={lesson.id}
                      className={`rounded-xl border p-3 flex items-center justify-between ${
                        isEnded
                          ? 'border-border/30 bg-muted/30 opacity-60'
                          : 'border-border/50 bg-card shadow-sm'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-9 h-9 rounded-lg flex flex-col items-center justify-center flex-shrink-0 ${
                          isEnded ? 'bg-muted text-muted-foreground' : 'bg-brand-turquoise/10 text-brand-turquoise'
                        }`}>
                          {isEnded ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <span className="font-bold text-sm font-cairo">{lesson.period}</span>
                          )}
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold font-cairo text-sm text-foreground truncate">{lesson.subject}</p>
                          <p className="text-[11px] text-muted-foreground font-tajawal">
                            {lesson.className} • {lesson.time}
                          </p>
                        </div>
                      </div>
                      {!isEnded && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="rounded-lg font-cairo text-xs text-brand-turquoise hover:bg-brand-turquoise/10 flex-shrink-0"
                          onClick={() => handleStartClass(lesson)}
                        >
                          <Play className="h-3 w-3 me-1" />
                          {t('startNow')}
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {/* Quick Navigation */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
            {[
              { icon: BookOpen, label: t('myClasses2'), path: '/teacher/classes', gradient: 'from-blue-500 to-blue-600' },
              { icon: Users, label: t('myStudents2'), path: '/teacher/students', gradient: 'from-emerald-500 to-emerald-600' },
              { icon: BarChart3, label: t('aiInsights'), path: '/ai-insights', gradient: 'from-purple-500 to-purple-600' },
              { icon: Award, label: t('myAchievements'), path: '/teacher/achievements', gradient: 'from-amber-500 to-amber-600' },
            ].map(nav => (
              <button
                key={nav.path}
                className="flex flex-col items-center gap-2 p-4 rounded-xl border border-border/50 bg-background hover:border-brand-turquoise/30 hover:shadow-md transition-shadow group"
                onClick={() => navigate(nav.path)}
              >
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${nav.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
                  <nav.icon className="h-5 w-5 text-white" />
                </div>
                <span className="text-xs font-cairo font-medium text-foreground">{nav.label}</span>
              </button>
            ))}
          </div>

        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
