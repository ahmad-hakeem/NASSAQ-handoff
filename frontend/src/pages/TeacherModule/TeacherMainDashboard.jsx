import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { formatFullDate } from '../../utils/hijriDate';
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
  Timer, CircleDot, School, Sparkles, Zap, TrendingUp, Star
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

const HAKIM_CHARACTER = '/hakim-poses/teacher-helper.png';

const TeacherDayProgress = ({ isRTL }) => {
  const { api } = useAuth();
  const [now, setNow] = useState(new Date());
  const [dayStatus, setDayStatus] = useState(null);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60000);
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

  const progress = dayStatus?.progress ?? 0;
  const isSchoolTime = dayStatus?.is_school_time ?? false;
  const currentPeriod = dayStatus?.current_period ?? 0;
  const totalPeriods = dayStatus?.total_periods ?? 7;
  const isBreak = dayStatus?.is_break ?? false;
  const dayStart = dayStatus?.day_start ?? '07:00';
  const dayEnd = dayStatus?.day_end ?? '13:15';

  const formatTimeLabel = (timeStr) => {
    const [h, m] = timeStr.split(':').map(Number);
    if (isRTL) return `${h}:${m.toString().padStart(2, '0')} ${h < 12 ? 'صباحاً' : 'مساءً'}`;
    const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
    return `${h12}:${m.toString().padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
  };

  const dateInfo = useMemo(() => {
    try {
      return formatFullDate(now, isRTL ? 'ar' : 'en');
    } catch (e) { console.error('Date format error:', e); return null; }
  }, [now, isRTL]);

  const periodLabel = isBreak
    ? (isRTL ? 'استراحة' : 'Break')
    : (isRTL ? `الحصة ${currentPeriod} من ${totalPeriods}` : `Period ${currentPeriod} of ${totalPeriods}`);

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800 via-slate-900 to-brand-navy p-3.5 sm:p-5 text-white border border-white/5">
      <div className="absolute inset-0 nassaq-pattern opacity-[0.04] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(56,189,248,0.05),transparent)]" />
      <div className="relative z-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-brand-turquoise/15 backdrop-blur flex items-center justify-center border border-brand-turquoise/20 flex-shrink-0">
              <Calendar className="h-5 w-5 sm:h-6 sm:w-6 text-brand-turquoise" />
            </div>
            <div className="min-w-0">
              <p className="text-base sm:text-xl font-bold font-cairo">
                {dateInfo?.weekday || now.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { weekday: 'long' })}
              </p>
              <p className="text-xs sm:text-sm text-white/50 font-tajawal truncate">
                {dateInfo?.full || ''}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-5">
            {isSchoolTime && (
              <div className="flex items-center gap-2 sm:gap-3 bg-white/5 backdrop-blur rounded-xl px-3 sm:px-4 py-2 sm:py-2.5 border border-white/10">
                <div className="relative flex-shrink-0">
                  {isBreak ? (
                    <Timer className="h-4 w-4 sm:h-5 sm:w-5 text-amber-400" />
                  ) : (
                    <>
                      <CircleDot className="h-4 w-4 sm:h-5 sm:w-5 text-emerald-400" />
                      <span className="absolute -top-0.5 -right-0.5 w-2 h-2 sm:w-2.5 sm:h-2.5 bg-emerald-400 rounded-full animate-ping" />
                    </>
                  )}
                </div>
                <div>
                  <p className="text-[10px] sm:text-xs text-white/40 font-tajawal">{isBreak ? (isRTL ? 'الوقت الحالي' : 'Current') : (isRTL ? 'الحصة الحالية' : 'Current Period')}</p>
                  <p className="text-sm sm:text-base font-bold font-cairo">{periodLabel}</p>
                </div>
              </div>
            )}
            <div className="text-center flex-shrink-0">
              <p className="text-xl sm:text-2xl font-bold font-cairo tabular-nums">
                {now.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
              </p>
              <p className="text-[9px] sm:text-[10px] text-white/40 font-tajawal">
                {isSchoolTime
                  ? (isRTL ? 'الدوام جارٍ' : 'School in session')
                  : (isRTL ? 'خارج وقت الدوام' : 'Outside school hours')}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between mb-1.5 font-tajawal">
            <span className="text-[10px] text-white/40">{formatTimeLabel(dayStart)}</span>
            <span className={`font-cairo font-bold ${progress > 0 && isSchoolTime ? 'text-sm text-emerald-400' : 'text-xs text-white/50'}`}>
              {isRTL ? `${progress}% من اليوم الدراسي` : `${progress}% of school day`}
            </span>
            <span className="text-[10px] text-white/40">{formatTimeLabel(dayEnd)}</span>
          </div>
          <div className="h-2 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-brand-turquoise to-emerald-400 rounded-full transition-all duration-1000 relative"
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
  );
};

export default function TeacherMainDashboard() {
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
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

  const teacherId = user?.teacher_id || user?.id;
  const teacherSubject = user?.primary_subject_name || user?.specialization || '';
  const schoolName = user?.school_name || user?.tenant_name || '';

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
            status: lesson.status || 'upcoming'
          })) || []
        });
        setClasses(data.classes || []);
        setRecentActivities(data.recent_activities?.map(a => ({
          type: a.type?.includes('attendance') ? 'attendance' :
                a.type?.includes('assessment') ? 'assessment' : 'notification',
          message: a.message,
          time: a.time ? new Date(a.time).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US') : (isRTL ? 'مؤخراً' : 'Recently')
        })) || []);
      }
    } catch (error) {
      console.error('Error fetching teacher data:', error);
    } finally {
      setLoading(false);
    }
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

  useEffect(() => { fetchTeacherData(); }, [fetchTeacherData]);
  useEffect(() => { fetchMetrics(); }, [fetchMetrics]);

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
    await Promise.all([fetchTeacherData(), fetchMetrics()]);
    setRefreshing(false);
    toast.success(isRTL ? 'تم تحديث البيانات' : 'Data refreshed');
  };

  const currentLesson = stats.upcomingLessons.length > 0 ? stats.upcomingLessons[0] : null;
  const NavArrow = isRTL ? ChevronLeft : ChevronRight;

  if (loading) {
    return (
      <Sidebar>
        <div className="flex flex-col items-center justify-center h-96 gap-4">
          <div className="relative">
            <div className="w-16 h-16 rounded-full border-4 border-brand-turquoise/20 border-t-brand-turquoise animate-spin" />
          </div>
          <p className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'جارٍ تحميل مركز القيادة...' : 'Loading Command Center...'}</p>
        </div>
      </Sidebar>
    );
  }

  const metricCards = [
    {
      title: isRTL ? 'حصص اليوم' : "Today's Lessons",
      value: stats.todayLessons,
      subtitle: isRTL ? 'المقرر لهذا اليوم' : 'Scheduled for today',
      icon: CalendarDays,
      gradient: 'from-violet-500 to-violet-600',
      onClick: () => navigate('/teacher/schedule'),
    },
    {
      title: isRTL ? 'فصولي' : 'My Classes',
      value: stats.myClasses,
      subtitle: isRTL ? 'الفصول المسندة' : 'Assigned classes',
      icon: BookOpen,
      gradient: 'from-blue-500 to-blue-600',
      onClick: () => navigate('/teacher/classes'),
    },
    {
      title: isRTL ? 'طلابي' : 'My Students',
      value: stats.myStudents,
      subtitle: isRTL ? 'إجمالي الطلاب' : 'Total students',
      icon: Users,
      gradient: 'from-emerald-500 to-emerald-600',
      onClick: () => navigate('/teacher/students'),
    },
    {
      title: isRTL ? 'المهام المفتوحة' : 'Open Tasks',
      value: stats.pendingAttendance,
      subtitle: isRTL ? 'بانتظار الإكمال' : 'Awaiting completion',
      icon: AlertCircle,
      gradient: stats.pendingAttendance > 0 ? 'from-orange-500 to-orange-600' : 'from-slate-500 to-slate-600',
      onClick: () => navigate('/teacher/tasks'),
    },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto">

          <div className="flex items-center justify-end">
            <Button size="sm" variant="outline" onClick={handleRefresh} disabled={refreshing}
              className="rounded-xl border-border/50 hover:bg-muted gap-2 font-tajawal text-xs">
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              {isRTL ? 'تحديث' : 'Refresh'}
            </Button>
          </div>

          {/* Hero Header */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy to-slate-900 p-4 sm:p-6 md:p-8 text-white border border-white/5">
            <div className="absolute inset-0 nassaq-pattern opacity-[0.05] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(56,189,248,0.08),transparent)]" />
            <div className="absolute top-0 end-0 w-48 md:w-64 h-48 md:h-64 rounded-full bg-brand-turquoise/5 blur-3xl" />
            <div className="absolute bottom-0 start-0 w-36 md:w-48 h-36 md:h-48 rounded-full bg-brand-purple/5 blur-3xl" />

            <div className="relative z-10">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 md:gap-6">
                <div className="flex items-center gap-3 sm:gap-5">
                  <div className="relative flex-shrink-0">
                    <Avatar className="h-14 w-14 sm:h-20 sm:w-20 border-[3px] border-brand-turquoise/40 shadow-2xl shadow-brand-turquoise/20 ring-4 ring-white/5">
                      <AvatarImage src={user?.avatar_url} alt={user?.full_name} />
                      <AvatarFallback className="bg-gradient-to-br from-brand-turquoise to-brand-purple text-white text-lg sm:text-2xl font-bold">
                        {user?.full_name?.charAt(0) || 'م'}
                      </AvatarFallback>
                    </Avatar>
                    <div className="absolute -bottom-1 -end-1 w-5 sm:w-7 h-5 sm:h-7 rounded-lg bg-emerald-500 flex items-center justify-center border-2 border-brand-navy shadow-lg">
                      <CheckCircle2 className="h-2.5 sm:h-3.5 w-2.5 sm:w-3.5 text-white" />
                    </div>
                  </div>
                  <div className="min-w-0">
                    <h1 className="font-cairo text-lg sm:text-2xl md:text-3xl font-bold truncate">
                      {isRTL ? `أهلاً أستاذ ${user?.full_name || 'المعلم'}` : `Welcome, ${user?.full_name || 'Teacher'}`}
                    </h1>
                    <p className="text-brand-turquoise font-bold font-cairo text-sm sm:text-lg mt-0.5 truncate">
                      {teacherSubject ? (isRTL ? `معلم ${teacherSubject}` : `${teacherSubject} Teacher`) : (isRTL ? 'معلم' : 'Teacher')}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5 sm:mt-2">
                      <div className="flex items-center gap-1.5 text-white/40 text-xs sm:text-sm font-tajawal bg-white/5 rounded-lg px-2 sm:px-2.5 py-0.5 sm:py-1">
                        <School className="h-3 sm:h-3.5 w-3 sm:w-3.5 flex-shrink-0" />
                        <span className="truncate max-w-[140px] sm:max-w-none">{schoolName || (isRTL ? 'المدرسة' : 'School')}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex gap-2 sm:gap-3">
                  <Button
                    className="flex-1 sm:flex-none bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise/90 hover:to-cyan-400 text-white rounded-xl h-10 sm:h-12 px-3 sm:px-6 font-cairo text-xs sm:text-base shadow-lg shadow-brand-turquoise/20 hover:shadow-xl transition-all hover:scale-[1.02]"
                    onClick={() => navigate('/teacher/schedule')}
                  >
                    <Calendar className="h-4 sm:h-5 w-4 sm:w-5 me-1.5 sm:me-2" />
                    {isRTL ? 'جدولي' : 'My Schedule'}
                  </Button>
                  <Button
                    variant="outline"
                    className="flex-1 sm:flex-none border-white/15 text-white hover:bg-white/10 rounded-xl h-10 sm:h-12 px-3 sm:px-6 font-cairo text-xs sm:text-base backdrop-blur-sm"
                    onClick={() => navigate('/teacher/achievements')}
                  >
                    <Award className="h-4 sm:h-5 w-4 sm:w-5 me-1.5 sm:me-2" />
                    {isRTL ? 'إنجازاتي' : 'Achievements'}
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <TeacherDayProgress isRTL={isRTL} />

          {/* Metric Cards */}
          <section>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3 md:gap-4">
              {metricCards.map((card, i) => (
                <button
                  key={i}
                  onClick={card.onClick}
                  className={`relative overflow-hidden rounded-xl sm:rounded-2xl bg-gradient-to-br ${card.gradient} p-3 sm:p-5 text-white cursor-pointer group shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-[1.02] border border-white/10 text-start w-full`}
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

          {/* Today's Schedule */}
          <Card className="border border-border/50 shadow-sm overflow-hidden">
            <CardHeader className="pb-3 bg-gradient-to-r from-brand-turquoise/5 to-transparent border-b border-border/30">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-3 text-xl font-cairo">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-turquoise to-cyan-600 flex items-center justify-center shadow-lg shadow-brand-turquoise/20">
                    <Clock className="h-5 w-5 text-white" />
                  </div>
                  {isRTL ? 'جدول اليوم' : "Today's Schedule"}
                </CardTitle>
                <Button variant="ghost" size="sm" className="rounded-xl font-cairo text-brand-turquoise hover:bg-brand-turquoise/10 gap-1" onClick={() => navigate('/teacher/schedule')}>
                  {isRTL ? 'الجدول الكامل' : 'Full Schedule'}
                  <NavArrow className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              {currentLesson && (
                <div className="rounded-2xl bg-gradient-to-r from-brand-turquoise/8 via-brand-turquoise/4 to-transparent border border-brand-turquoise/20 p-4 sm:p-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
                    <div className="flex items-center gap-3 sm:gap-4">
                      <div className="relative flex-shrink-0">
                        <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-gradient-to-br from-brand-turquoise to-brand-navy flex items-center justify-center shadow-lg shadow-brand-turquoise/20">
                          <Play className="h-5 w-5 sm:h-6 sm:w-6 text-white" />
                        </div>
                        <span className="absolute -top-1 -right-1 w-3 sm:w-4 h-3 sm:h-4 bg-emerald-500 rounded-full border-2 border-white dark:border-slate-900 animate-pulse" />
                      </div>
                      <div className="min-w-0">
                        <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-brand-turquoise/25 mb-1 sm:mb-1.5 font-cairo text-[10px] sm:text-xs">
                          {isRTL ? 'الحصة الحالية / القادمة' : 'Current / Next Class'}
                        </Badge>
                        <h3 className="text-base sm:text-lg font-bold font-cairo text-foreground truncate">{currentLesson.subject}</h3>
                        <p className="text-xs sm:text-sm text-muted-foreground font-tajawal flex items-center gap-1.5 sm:gap-2 mt-0.5">
                          <BookOpen className="h-3 w-3 sm:h-3.5 sm:w-3.5 flex-shrink-0" /> <span className="truncate">{currentLesson.class}</span>
                          <span className="text-border">•</span>
                          <Clock className="h-3 w-3 sm:h-3.5 sm:w-3.5 flex-shrink-0" /> {currentLesson.time}
                        </p>
                      </div>
                    </div>
                    <Button
                      className="w-full sm:w-auto bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise/90 hover:to-cyan-400 text-white rounded-xl h-10 sm:h-12 px-4 sm:px-6 font-cairo text-sm sm:text-base shadow-lg shadow-brand-turquoise/20 hover:shadow-xl transition-all hover:scale-[1.02]"
                      onClick={() => {
                        if (!currentLesson.class_id) return;
                        const lessonData = {
                          lesson: currentLesson,
                          schedule_session_id: currentLesson.schedule_session_id || currentLesson.id,
                          class_id: currentLesson.class_id,
                          subject_id: currentLesson.subject_id
                        };
                        sessionStorage.setItem('current_lesson', JSON.stringify(lessonData));
                        navigate('/teacher/session/start', { state: lessonData });
                      }}
                    >
                      <Play className="h-4 sm:h-5 w-4 sm:w-5 me-1.5 sm:me-2" />
                      {isRTL ? 'ابدأ الحصة' : 'Start Session'}
                    </Button>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                {stats.upcomingLessons.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Calendar className="h-14 w-14 mx-auto mb-3 opacity-15" />
                    <p className="font-cairo text-lg">{isRTL ? 'لا توجد حصص في هذا اليوم' : 'No lessons on this day'}</p>
                  </div>
                ) : (
                  stats.upcomingLessons.map((lesson, index) => (
                    <button
                      key={index}
                      className={`flex items-center justify-between p-3 sm:p-4 rounded-xl border transition-all cursor-pointer group w-full text-start ${
                        index === 0
                          ? 'bg-brand-turquoise/5 border-brand-turquoise/20'
                          : 'bg-muted/30 border-border/50 hover:border-brand-turquoise/20 hover:bg-muted/50'
                      }`}
                      onClick={() => lesson.class_id && navigate(`/teacher/class/${lesson.class_id}`)}
                    >
                      <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                        <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex flex-col items-center justify-center flex-shrink-0 ${
                          index === 0
                            ? 'bg-gradient-to-br from-brand-turquoise to-brand-navy text-white shadow-md'
                            : 'bg-muted text-muted-foreground'
                        }`}>
                          <span className="text-[8px] sm:text-[9px] font-tajawal leading-none">{isRTL ? 'الحصة' : 'P'}</span>
                          <span className="font-bold text-base sm:text-lg font-cairo leading-none">{lesson.period || (index + 1)}</span>
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold font-cairo text-sm sm:text-base text-foreground truncate">{lesson.subject}</p>
                          <div className="flex items-center gap-2 sm:gap-3 text-[11px] sm:text-xs text-muted-foreground font-tajawal mt-0.5">
                            <span className="flex items-center gap-1 truncate"><BookOpen className="h-3 w-3 flex-shrink-0" /> <span className="truncate">{lesson.class}</span></span>
                            <span className="flex items-center gap-1 flex-shrink-0"><Clock className="h-3 w-3" /> {lesson.time}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
                        {index === 0 && (
                          <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-brand-turquoise/25 font-cairo text-[10px] sm:text-xs hidden sm:inline-flex">
                            {isRTL ? 'القادمة' : 'Next'}
                          </Badge>
                        )}
                        <NavArrow className="h-4 w-4 text-muted-foreground/50 group-hover:text-brand-turquoise transition-colors" />
                      </div>
                    </button>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

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
                      <h3 className="font-cairo font-bold text-foreground text-lg">{isRTL ? 'أدائي التدريسي' : 'Teaching Performance'}</h3>
                      <p className="text-xs text-muted-foreground font-tajawal">{isRTL ? `بيانات من ${teachingMetrics.classCount} فصل` : `Data from ${teachingMetrics.classCount} classes`}</p>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-border/30">
                  {[
                    { label: isRTL ? 'معدل الحضور' : 'Attendance Rate', value: teachingMetrics.avgAttendance, icon: CheckCircle2, color: 'text-emerald-600', bgIcon: 'from-emerald-500 to-emerald-600' },
                    { label: isRTL ? 'معدل المشاركة' : 'Participation', value: teachingMetrics.avgParticipation, icon: Activity, color: 'text-blue-600', bgIcon: 'from-blue-500 to-blue-600' },
                    { label: isRTL ? 'الأداء' : 'Performance', value: teachingMetrics.avgPerformance, icon: Target, color: 'text-purple-600', bgIcon: 'from-purple-500 to-purple-600' },
                    { label: isRTL ? 'إجمالي الحصص' : 'Total Sessions', value: teachingMetrics.totalSessions, icon: Flame, color: 'text-amber-600', bgIcon: 'from-amber-500 to-amber-600', isCount: true },
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
                  {isRTL ? 'آخر النشاطات' : 'Recent Activities'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {recentActivities.length === 0 ? (
                  <div className="text-center py-10 text-muted-foreground">
                    <Bell className="h-12 w-12 mx-auto mb-3 opacity-15" />
                    <p className="font-tajawal">{isRTL ? 'لا توجد نشاطات حديثة' : 'No recent activities'}</p>
                  </div>
                ) : (
                  recentActivities.map((activity, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 rounded-xl bg-muted/30 border border-border/50 hover:border-brand-turquoise/20 transition-all group">
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
                  {isRTL ? 'عرض جميع الإشعارات' : 'View All Notifications'}
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
                    {isRTL ? 'إجراءات سريعة' : 'Quick Actions'}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { icon: ClipboardCheck, label: isRTL ? 'تسجيل الحضور' : 'Attendance', path: '/teacher/attendance', gradient: 'from-emerald-500 to-emerald-600' },
                      { icon: FileText, label: isRTL ? 'التقييمات' : 'Assessments', path: '/teacher/assessments', gradient: 'from-blue-500 to-blue-600' },
                      { icon: Star, label: isRTL ? 'السلوك' : 'Behavior', path: '/teacher/behavior', gradient: 'from-purple-500 to-purple-600' },
                      { icon: MessageSquare, label: isRTL ? 'التواصل' : 'Communication', path: '/teacher/communication', gradient: 'from-amber-500 to-orange-500' },
                    ].map((action, index) => (
                      <button
                        key={index}
                        className="flex flex-col items-center gap-2.5 p-4 rounded-xl border border-border/50 bg-background hover:border-brand-turquoise/30 hover:shadow-md transition-all group"
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
                    {isRTL ? 'المهام المعلقة' : 'Pending Tasks'}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-4 rounded-xl bg-orange-50 dark:bg-orange-950/20 border border-orange-200/50 dark:border-orange-800/30">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-orange-800 dark:text-orange-300 font-tajawal text-sm">{isRTL ? 'حضور غير مسجل' : 'Unrecorded Attendance'}</span>
                      <Badge className="bg-orange-500 text-white font-cairo">{stats.pendingAttendance}</Badge>
                    </div>
                    <Button size="sm" className="w-full bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white rounded-xl font-cairo shadow-md" onClick={() => navigate('/teacher/attendance')}>
                      {isRTL ? 'تسجيل الآن' : 'Record Now'}
                    </Button>
                  </div>
                  <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-950/20 border border-blue-200/50 dark:border-blue-800/30">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-medium text-blue-800 dark:text-blue-300 font-tajawal text-sm">{isRTL ? 'تقييمات معلقة' : 'Pending Assessments'}</span>
                      <Badge className="bg-blue-500 text-white font-cairo">{stats.pendingAssessments}</Badge>
                    </div>
                    <Button size="sm" variant="outline" className="w-full border-blue-300 text-blue-700 hover:bg-blue-50 rounded-xl font-cairo" onClick={() => navigate('/teacher/assessments')}>
                      {isRTL ? 'إكمال التقييم' : 'Complete Assessment'}
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
                      {isRTL ? 'رؤى حكيم الذكية' : 'Hakim AI Insights'}
                      <Sparkles className="h-4 w-4 text-brand-purple animate-pulse" />
                    </CardTitle>
                    <CardDescription className="font-tajawal text-xs">
                      {isRTL ? 'تحليل آلي لصحة فصولك وتنبيهات المخاطر' : 'Automated class health and risk alerts'}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-5">
                {hakimLoading ? (
                  <div className="flex items-center justify-center py-8 gap-3">
                    <div className="w-8 h-8 rounded-full border-2 border-brand-purple/20 border-t-brand-purple animate-spin" />
                    <span className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'جاري التحليل...' : 'Analyzing...'}</span>
                  </div>
                ) : (
                  <div className="space-y-5">
                    {classHealthData.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-muted-foreground mb-3 font-cairo flex items-center gap-2">
                          <Activity className="h-4 w-4 text-brand-turquoise" />
                          {isRTL ? 'صحة الفصول' : 'Class Health'}
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {classHealthData.map(cls => (
                            <div key={cls.class_id} className={`p-4 rounded-xl border transition-all hover:shadow-md ${
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
                                <span>{isRTL ? `${cls.total_students} طالب` : `${cls.total_students} students`}</span>
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
                          {isRTL ? 'تنبيهات المخاطر' : 'Risk Alerts'}
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
