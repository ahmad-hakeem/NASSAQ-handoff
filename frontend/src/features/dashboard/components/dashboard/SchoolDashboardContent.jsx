import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { formatFullDate } from '@/shared/models/utils/hijriDate';
import SectionErrorBoundary from '@/shared/components/SectionErrorBoundary';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { 
  Users, 
  GraduationCap, 
  Calendar, 
  CalendarDays,
  Clock,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  School,
  ClipboardList,
  Eye,
  Activity,
  UserCheck,
  UserX,
  AlertCircle,
  CheckCircle2,
  Send,
  Loader2,
  RefreshCw,
  BarChart3,
  Target,
  Zap,
  Shield,
  ArrowRight,
  ArrowLeft,
  BookOpen,
  Megaphone,
  Settings,
  LayoutDashboard,
  CircleDot,
  Timer,
  ChevronRight,
  ChevronLeft,
  PieChart,
  Gauge,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { lazy, Suspense } from 'react';
import { AdminCalendar } from './AdminCalendar';
import { HakeemPlan } from './HakeemPlan';

const SendNotificationWizard = lazy(() => import('@/features/teachers/components/wizards/SendNotificationWizard').then(m => ({ default: m.SendNotificationWizard })));
const CreateScheduleWizard = lazy(() => import('@/features/teachers/components/wizards/CreateScheduleWizard').then(m => ({ default: m.CreateScheduleWizard })));
const LiveSessionsMonitor = lazy(() => import('@/features/teachers/components/wizards/LiveSessionsMonitor').then(m => ({ default: m.LiveSessionsMonitor })));

const SchoolDayProgress = ({ isRTL }) => {
  const { t } = useTranslation();
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
    } catch (err) { /* silent */ }
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
  const dayStart = dayStatus?.day_start;
  const dayEnd = dayStatus?.day_end;

  const formatTimeLabel = (timeStr) => {
    if (!timeStr || typeof timeStr !== 'string' || !timeStr.includes(':')) {
      return isRTL ? 'جاري التحميل...' : 'Loading...';
    }
    const [h, m] = timeStr.split(':').map(Number);
    if (Number.isNaN(h) || Number.isNaN(m)) {
      return isRTL ? 'جاري التحميل...' : 'Loading...';
    }
    if (isRTL) {
      return `${h}:${m.toString().padStart(2, '0')} ${h < 12 ? 'صباحاً' : 'مساءً'}`;
    }
    const h12 = h > 12 ? h - 12 : h === 0 ? 12 : h;
    return `${h12}:${m.toString().padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
  };

  const dateInfo = useMemo(() => {
    try {
      return formatFullDate(now, isRTL ? 'ar' : 'en');
    } catch (e) { console.error('Error formatting date:', e); return null; }
  }, [now, isRTL]);

  const periodLabel = isBreak
    ? (t('break'))
    : (isRTL ? `الحصة ${currentPeriod} من ${totalPeriods}` : `Period ${currentPeriod} of ${totalPeriods}`);

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-turquoise/80 p-6 text-white">
      <div className="absolute inset-0 nassaq-pattern opacity-[0.05]" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(255,255,255,0.05),transparent)]" />
      <div className="relative z-10">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/10">
              <Calendar className="h-7 w-7 text-white/90" />
            </div>
            <div>
              <p className="text-2xl font-bold font-cairo">
                {dateInfo?.weekday || now.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { weekday: 'long' })}
              </p>
              <p className="text-sm text-white/85 font-tajawal">
                {dateInfo?.full || ''}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6">
            {isSchoolTime && (
              <div className="flex items-center gap-3 bg-white/10 backdrop-blur rounded-xl px-4 py-2.5 border border-white/10">
                <div className="relative">
                  {isBreak ? (
                    <Timer className="h-5 w-5 text-amber-400" />
                  ) : (
                    <>
                      <CircleDot className="h-5 w-5 text-emerald-400" />
                      <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 rounded-full animate-ping" />
                    </>
                  )}
                </div>
                <div>
                  <p className="text-xs text-white/95 font-tajawal">{isBreak ? (t('current')) : (t('currentPeriod'))}</p>
                  <p className="text-lg font-bold font-cairo">{periodLabel}</p>
                </div>
              </div>
            )}

            <div className="text-center">
              <p className="text-3xl font-bold font-cairo tabular-nums">
                {now.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
              </p>
              <p className="text-xs text-white/90 font-tajawal">
                {isSchoolTime 
                  ? (t('schoolInSession')) 
                  : (t('outsideSchoolHours'))}
              </p>
            </div>
          </div>
        </div>

        <div className="mt-5">
          <div className="flex items-center justify-between mb-2 font-tajawal">
            <span className="text-xs text-white/90 font-medium">{formatTimeLabel(dayStart)}</span>
            <span className={`font-cairo font-bold ${progress > 0 && isSchoolTime ? 'text-lg text-emerald-300' : 'text-sm text-white/95'}`}>
              {isRTL ? `${progress}% من اليوم الدراسي` : `${progress}% of school day`}
            </span>
            <span className="text-xs text-white/90 font-medium">{formatTimeLabel(dayEnd)}</span>
          </div>
          <div className="h-3 bg-white/10 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-emerald-400 to-brand-turquoise rounded-full transition-all duration-1000 relative"
              style={{ width: `${progress}%` }}
            >
              {progress > 0 && (
                <span className="absolute end-0 top-1/2 -translate-y-1/2 w-4 h-4 bg-white rounded-full shadow-lg shadow-emerald-500/50" />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};


const DailyOpsPanel = ({ data, isRTL, onNavigate }) => {
  const { t } = useTranslation();
  const ops = data || {};
  const items = [
    {
      label: t('absentStudentsToday'),
      count: ops.absentStudentsToday || 0,
      icon: UserX,
      color: 'bg-red-500',
      textColor: 'text-red-500',
      bgLight: 'bg-red-50 dark:bg-red-950/30',
      ringColor: 'ring-red-500/20',
      path: '/principal/attendance',
      actionLabel: t('view'),
      priority: 'critical',
    },
    {
      label: t('unrecordedAttendance'),
      count: ops.unrecordedAttendance || 0,
      icon: ClipboardList,
      color: 'bg-amber-500',
      textColor: 'text-amber-500',
      bgLight: 'bg-amber-50 dark:bg-amber-950/30',
      ringColor: 'ring-amber-500/20',
      path: '/principal/attendance',
      actionLabel: t('followUp'),
      priority: 'high',
    },
    {
      label: t('unassignedSessions'),
      count: ops.classesWithoutTeacher || 0,
      icon: AlertTriangle,
      color: 'bg-orange-500',
      textColor: 'text-orange-500',
      bgLight: 'bg-orange-50 dark:bg-orange-950/30',
      ringColor: 'ring-orange-500/20',
      path: '/principal/schedule',
      actionLabel: t('assign'),
      priority: 'high',
    },
    {
      label: t('academicAlerts'),
      count: ops.academicAlerts || 0,
      icon: AlertCircle,
      color: 'bg-violet-500',
      textColor: 'text-violet-500',
      bgLight: 'bg-violet-50 dark:bg-violet-950/30',
      ringColor: 'ring-violet-500/20',
      path: '/principal/ai-insights',
      actionLabel: t('review'),
      priority: 'medium',
    },
    {
      label: t('newNotifications'),
      count: ops.newNotifications || 0,
      icon: Send,
      color: 'bg-blue-500',
      textColor: 'text-blue-500',
      bgLight: 'bg-blue-50 dark:bg-blue-950/30',
      ringColor: 'ring-blue-500/20',
      path: '/notifications',
      actionLabel: t('view2'),
      priority: 'low',
    },
    {
      label: t('frequentTeacherAbsence'),
      count: ops.teachersWithFrequentAbsence || 0,
      icon: UserCheck,
      color: 'bg-rose-500',
      textColor: 'text-rose-500',
      bgLight: 'bg-rose-50 dark:bg-rose-950/30',
      ringColor: 'ring-rose-500/20',
      path: '/principal/users-management',
      actionLabel: isRTL ? 'متابعة' : 'Review',
      priority: 'medium',
    },
  ];

  const activeItems = items.filter(i => i.count > 0);
  const total = activeItems.reduce((s, i) => s + i.count, 0);
  const criticalCount = activeItems.filter(i => i.priority === 'critical').reduce((s, i) => s + i.count, 0);

  const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const sorted = [...activeItems].sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

  return (
    <Card className={`card-nassaq overflow-hidden ${criticalCount > 0 ? 'ring-1 ring-red-300 dark:ring-red-700/50' : total > 0 ? 'ring-1 ring-blue-200 dark:ring-blue-800/50' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-lg">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center shadow-sm shadow-blue-500/20">
              <LayoutDashboard className="h-4.5 w-4.5 text-white" />
            </div>
            {t('dailyOperations')}
          </CardTitle>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 text-[10px] px-2 py-0.5 font-cairo border-0 animate-pulse">
                {criticalCount} {t('urgent')}
              </Badge>
            )}
            {total > 0 ? (
              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 text-xs px-2.5 py-0.5 font-cairo border-0">{total}</Badge>
            ) : (
              <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-xs px-2 py-0.5 font-cairo border-0">
                <CheckCircle2 className="h-3 w-3 mr-1" />{t('clear')}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {total === 0 ? (
          <div className="text-center py-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100 dark:from-emerald-900/30 dark:to-teal-900/30 flex items-center justify-center mx-auto mb-3 shadow-sm">
              <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            </div>
            <p className="font-tajawal text-sm font-semibold text-emerald-600 dark:text-emerald-400">{t('noPendingTasks')}</p>
            <p className="font-tajawal text-xs text-muted-foreground mt-1">{t('schoolDayRunningSmoothly')}</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {sorted.map((item) => {
              const ItemIcon = item.icon;
              const isCritical = item.priority === 'critical';
              return (
                <button key={item.path || item.label} onClick={() => onNavigate?.(item.path)}
                  className={`w-full flex items-center gap-3 p-2.5 rounded-xl transition-all duration-200 group text-start ${
                    isCritical
                      ? 'bg-red-50/80 dark:bg-red-950/20 hover:bg-red-100/80 dark:hover:bg-red-950/30 ring-1 ring-red-200/60 dark:ring-red-800/30'
                      : 'hover:bg-muted/70'
                  }`}>
                  <div className={`w-9 h-9 rounded-xl ${item.bgLight} flex items-center justify-center shrink-0 ring-1 ${item.ringColor}`}>
                    <ItemIcon className={`h-4 w-4 ${item.textColor}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-tajawal font-medium truncate">{item.label}</p>
                    <p className="text-[10px] text-muted-foreground font-tajawal">
                      {item.priority === 'critical' ? (t('immediateAttention')) :
                       item.priority === 'high' ? (t('highPriority')) :
                       item.priority === 'medium' ? (t('followupNeeded')) :
                       (t('informational'))}
                    </p>
                  </div>
                  <div className={`min-w-[40px] h-10 rounded-xl ${item.bgLight} flex items-center justify-center ring-1 ${item.ringColor}`}>
                    <span className={`text-lg font-bold font-cairo ${item.textColor}`}>{item.count}</span>
                  </div>
                  <div className={`flex items-center gap-1 text-[10px] font-tajawal font-semibold ${item.textColor} opacity-0 group-hover:opacity-100 transition-opacity shrink-0`}>
                    <span>{item.actionLabel}</span>
                    {isRTL ? <ChevronLeft className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const PerformanceSnapshot = ({ metrics, attendance, isRTL }) => {
  const { t } = useTranslation();
  const m = metrics || {};
  const totalStudents = m.totalStudents?.value || 0;
  const totalTeachers = m.totalTeachers?.value || 0;
  const totalClasses = m.totalClasses?.value || 0;
  const todaySessions = m.todaySessions?.value || 0;
  const attendanceRate = attendance ? Math.round(((attendance.students?.present || 0) / Math.max(attendance.students?.total || 1, 1)) * 100) : 0;

  const stats = [
    { 
      label: t('totalStudents'), 
      value: totalStudents, 
      icon: Users, 
      gradient: 'from-blue-500 to-blue-600',
      bgLight: 'bg-blue-50 dark:bg-blue-950/30',
      change: m.totalStudents?.change, 
      changeType: m.totalStudents?.changeType 
    },
    { 
      label: t('totalTeachers'), 
      value: totalTeachers, 
      icon: GraduationCap, 
      gradient: 'from-emerald-500 to-emerald-600',
      bgLight: 'bg-emerald-50 dark:bg-emerald-950/30',
      change: m.totalTeachers?.change, 
      changeType: m.totalTeachers?.changeType 
    },
    { 
      label: t('classes'), 
      value: totalClasses, 
      icon: School, 
      gradient: 'from-violet-500 to-violet-600',
      bgLight: 'bg-violet-50 dark:bg-violet-950/30',
      change: m.totalClasses?.change, 
      changeType: m.totalClasses?.changeType 
    },
    { 
      label: t('todaysSessions'), 
      value: todaySessions, 
      icon: BookOpen, 
      gradient: 'from-amber-500 to-amber-600',
      bgLight: 'bg-amber-50 dark:bg-amber-950/30',
      change: m.todaySessions?.change, 
      changeType: m.todaySessions?.changeType 
    },
  ];

  return (
    <Card className="card-nassaq">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-lg">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center">
              <BarChart3 className="h-4.5 w-4.5 text-white" />
            </div>
            {t('overviewSnapshot')}
          </CardTitle>
          <div className="flex items-center gap-1.5 text-[11px] font-tajawal text-muted-foreground">
            <CircleDot className="h-3 w-3 text-emerald-500 animate-pulse" />
            {t('live')}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {stats.map((stat, i) => (
            <div key={i} className={`relative p-3.5 rounded-xl ${stat.bgLight} border border-border/30 overflow-hidden group`}>
              <div className="absolute top-0 end-0 w-16 h-16 opacity-5">
                <stat.icon className="w-full h-full" />
              </div>
              <div className="relative">
                <div className="flex items-center gap-2 mb-2">
                  <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${stat.gradient} flex items-center justify-center`}>
                    <stat.icon className="h-3.5 w-3.5 text-white" />
                  </div>
                  <span className="text-[11px] font-tajawal text-muted-foreground leading-tight">{stat.label}</span>
                </div>
                <div className="flex items-end justify-between">
                  <span className="text-2xl font-bold font-cairo">{stat.value.toLocaleString()}</span>
                  {stat.change && stat.change !== '0' && (
                    <span className={`flex items-center gap-0.5 text-[10px] font-cairo font-medium ${
                      (stat.changeType === 'increase' || stat.changeType === 'up') ? 'text-emerald-600 dark:text-emerald-400' : 
                      (stat.changeType === 'decrease' || stat.changeType === 'down') ? 'text-red-600 dark:text-red-400' : 'text-muted-foreground'
                    }`}>
                      {(stat.changeType === 'increase' || stat.changeType === 'up') ? <TrendingUp className="h-3 w-3" /> : 
                       (stat.changeType === 'decrease' || stat.changeType === 'down') ? <TrendingDown className="h-3 w-3" /> : null}
                      {stat.change}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="p-3.5 rounded-xl bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5 dark:from-brand-navy/20 dark:to-brand-turquoise/20 border border-brand-turquoise/10">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-cairo font-semibold">{t('todaysAttendanceRate')}</span>
            <span className={`text-lg font-bold font-cairo ${attendanceRate >= 90 ? 'text-emerald-600 dark:text-emerald-400' : attendanceRate >= 75 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
              {attendanceRate}%
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-1000 ${attendanceRate >= 90 ? 'bg-emerald-500' : attendanceRate >= 75 ? 'bg-amber-500' : 'bg-red-500'}`} 
              style={{ width: `${attendanceRate}%` }} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};


const StrategicNav = ({ onAction, isRTL, onNavigate }) => {
  const { t } = useTranslation();
  const navItems = [
    { id: 'users', label: t('userManagement'), icon: Users, path: '/principal/users-management', color: 'from-blue-500 to-blue-600' },
    { id: 'schedule', label: t('timetable'), icon: CalendarDays, path: '/principal/schedule', color: 'from-emerald-500 to-emerald-600' },
    { id: 'attendance', label: t('attendance'), icon: ClipboardList, path: '/principal/attendance', color: 'from-violet-500 to-violet-600' },
    { id: 'insights', label: isRTL ? 'رؤى الذكاء' : 'AI Insights', icon: BarChart3, path: '/principal/ai-insights', color: 'from-amber-500 to-amber-600' },
    { id: 'communication', label: t('communication'), icon: Megaphone, path: '/principal/communication', color: 'from-pink-500 to-pink-600' },
    { id: 'settings', label: t('schoolSettings'), icon: Settings, path: '/principal/settings', color: 'from-slate-500 to-slate-600' },
  ];

  return (
    <Card className="card-nassaq">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 font-cairo text-lg">
          <LayoutDashboard className="h-5 w-5 text-brand-turquoise" />
          {t('quickNavigation')}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigate(item.path)}
              className={`relative flex flex-col items-center gap-2 p-4 rounded-xl bg-gradient-to-br ${item.color} text-white hover:shadow-lg hover:scale-[1.03] transition-all duration-200 group`}
            >
              <item.icon className="h-6 w-6 text-white/90" />
              <span className="text-[11px] font-tajawal text-center leading-tight text-white/90">{item.label}</span>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

const QuickAddBar = ({ onAction }) => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-1 flex-wrap items-center justify-end gap-2 max-md:flex-none max-md:justify-start">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onAction('send-notification')}
        className="rounded-xl text-xs h-8 px-3 border text-pink-600 dark:text-pink-400 hover:bg-pink-50 dark:hover:bg-pink-950/30 hover:text-pink-600 dark:hover:text-pink-400 focus-visible:text-pink-600 dark:focus-visible:text-pink-400 border-pink-200 dark:border-pink-800 transition-all"
      >
        <Send className="h-3.5 w-3.5 me-1.5" />
        {t('sendNotice')}
      </Button>
    </div>
  );
};

export const SchoolDashboardContent = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { api, schoolContext, isImpersonating } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const [showSendNotificationWizard, setShowSendNotificationWizard] = useState(false);
  const [showCreateScheduleWizard, setShowCreateScheduleWizard] = useState(false);
  const [showLiveSessionsMonitor, setShowLiveSessionsMonitor] = useState(false);

  const fetchDashboardData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    try {
      const response = await api.get('/school/dashboard');
      const data = response.data;
      const transformedData = {
        metrics: {
          totalStudents: data.metrics.totalStudents,
          totalTeachers: data.metrics.totalTeachers,
          totalClasses: data.metrics.totalClasses,
          todaySessions: data.metrics.todaySessions,
          activeUsers: data.metrics.attendanceRate || { value: 0, change: '0', changeType: 'same', status: 'normal' },
          waitingSubstitute: data.metrics.waitingSubstitute,
        },
        attendance: data.attendance,
        interventions: data.interventions,
        alerts: (data.alerts || []).map(alert => ({
          id: alert.id,
          type: alert.type,
          title: isRTL ? (alert.title_ar || alert.title) : (alert.title_en || alert.title),
          time: isRTL ? (alert.time_ar || alert.time) : (alert.time_en || alert.time),
        })),
      };
      setDashboardData(transformedData);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setDashboardData(prev => {
        if (prev) return prev;
        return {
          metrics: {
            totalStudents: { value: 0, change: '0', changeType: 'same', status: 'normal' },
            totalTeachers: { value: 0, change: '0', changeType: 'same', status: 'normal' },
            totalClasses: { value: 0, change: '0', changeType: 'same', status: 'normal' },
            todaySessions: { value: 0, change: '0', changeType: 'same', status: 'normal' },
            activeUsers: { value: 0, change: '0', changeType: 'same', status: 'normal' },
            waitingSubstitute: { value: 0, change: '0', changeType: 'same', status: 'normal' },
          },
          attendance: { students: { present: 0, absent: 0, excused: 0, total: 0 }, teachers: { present: 0, absent: 0, excused: 0, total: 0 } },
          interventions: { classesWithoutTeacher: 0, teachersWithFrequentAbsence: 0, classesLowAttendance: 0 },
          alerts: [],
        };
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isRTL, api, schoolContext, isImpersonating]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    const interval = setInterval(() => fetchDashboardData(false), 20000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleQuickAction = (actionId) => {
    switch (actionId) {
      case 'view-sessions': setShowLiveSessionsMonitor(true); break;
      case 'send-notification': setShowSendNotificationWizard(true); break;
      default: break;
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-full border-4 border-brand-turquoise/20 border-t-brand-turquoise animate-spin" />
        </div>
        <p className="text-sm text-muted-foreground font-tajawal">{t('loadingCommandCenter')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="school-dashboard-content">
      <div className="flex items-center gap-3 flex-wrap max-md:gap-2">
        <QuickAddBar onAction={handleQuickAction} />
        <div className="flex items-center gap-3 max-md:w-full max-md:justify-end">
          {lastUpdated && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="font-tajawal">
                {lastUpdated.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          )}
          <Button size="icon" variant="outline" onClick={() => fetchDashboardData(true)} disabled={refreshing}
            className="rounded-xl h-8 w-8 border-border/50 hover:bg-muted" title={t('refresh')}>
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <SectionErrorBoundary name="SchoolDayProgress" isRTL={isRTL} fallbackMessage={t('failedToLoadSchoolDayProgress')}>
        <SchoolDayProgress isRTL={isRTL} />
      </SectionErrorBoundary>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-md:gap-4" data-testid="dashboard-planning-section">
        <SectionErrorBoundary name="AdminCalendar" isRTL={isRTL} fallbackMessage={t('failedToLoadOperationsPanel')}>
          <AdminCalendar />
        </SectionErrorBoundary>
        <SectionErrorBoundary name="HakeemPlan" isRTL={isRTL} fallbackMessage={t('failedToLoadOperationsPanel')}>
          <HakeemPlan />
        </SectionErrorBoundary>
      </section>

      <Suspense fallback={null}>
        {showSendNotificationWizard && (
          <SendNotificationWizard open={showSendNotificationWizard} onOpenChange={setShowSendNotificationWizard} />
        )}
        {showCreateScheduleWizard && (
          <CreateScheduleWizard open={showCreateScheduleWizard} onOpenChange={setShowCreateScheduleWizard} />
        )}
        {showLiveSessionsMonitor && (
          <LiveSessionsMonitor open={showLiveSessionsMonitor} onOpenChange={setShowLiveSessionsMonitor} />
        )}
      </Suspense>
    </div>
  );
};

export default SchoolDashboardContent;
