import { useState, useEffect, useCallback, useMemo } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { formatFullDate } from '../../utils/hijriDate';
import SectionErrorBoundary from '../SectionErrorBoundary';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { 
  Users, 
  GraduationCap, 
  Calendar, 
  CalendarDays,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  UserPlus,
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
import { useAuth } from '../../contexts/AuthContext';
import AddStudentWizard from '../wizards/AddStudentWizard';
import { AddTeacherWizard } from '../wizards/AddTeacherWizard';
import { CreateClassWizard } from '../wizards/CreateClassWizard';
import { SendNotificationWizard } from '../wizards/SendNotificationWizard';
import { CreateScheduleWizard } from '../wizards/CreateScheduleWizard';
import { LiveSessionsMonitor } from '../wizards/LiveSessionsMonitor';

const SchoolDayProgress = ({ isRTL }) => {
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
    ? (isRTL ? 'استراحة' : 'Break')
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
                  <p className="text-xs text-white/95 font-tajawal">{isBreak ? (isRTL ? 'الوقت الحالي' : 'Current') : (isRTL ? 'الحصة الحالية' : 'Current Period')}</p>
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
                  ? (isRTL ? 'الدوام جارٍ' : 'School in session') 
                  : (isRTL ? 'خارج وقت الدوام' : 'Outside school hours')}
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

const HeroMetric = ({ title, value, subtitle, icon: Icon, gradient, onClick, isRTL, change, changeType }) => {
  const NavArrow = isRTL ? ChevronLeft : ChevronRight;
  return (
    <Card 
      className={`relative overflow-hidden border-0 shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer group ${gradient}`}
      onClick={onClick}
    >
      <CardContent className="p-5 relative z-10">
        <div className="flex items-start justify-between">
          <div className="space-y-3">
            <p className="text-sm font-tajawal text-white/85">{title}</p>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold font-cairo text-white">{value}</span>
              {change && (
                <span className={`text-sm font-tajawal flex items-center gap-0.5 ${
                  changeType === 'up' ? 'text-emerald-300' : changeType === 'down' ? 'text-red-300' : 'text-white/90'
                }`}>
                  {changeType === 'up' ? <TrendingUp className="h-3.5 w-3.5" /> : changeType === 'down' ? <TrendingDown className="h-3.5 w-3.5" /> : <Minus className="h-3.5 w-3.5" />}
                  {change}
                </span>
              )}
            </div>
            {subtitle && <p className="text-xs text-white/90 font-tajawal">{subtitle}</p>}
          </div>
          <div className="w-14 h-14 rounded-2xl bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-colors">
            <Icon className="h-7 w-7 text-white/90" />
          </div>
        </div>
        <div className="absolute bottom-3 end-4 opacity-0 group-hover:opacity-100 transition-opacity">
          <NavArrow className="h-5 w-5 text-white/80" />
        </div>
      </CardContent>
    </Card>
  );
};

const AttendanceRadial = ({ data, isRTL }) => {
  const studentTotalRaw = data?.students?.total || 0;
  const studentPresent = data?.students?.present || 0;
  const studentAbsent = data?.students?.absent || 0;
  const studentExcused = data?.students?.excused || 0;
  const studentLate = data?.students?.late || 0;
  const studentPercent = Math.round((studentPresent / Math.max(studentTotalRaw, 1)) * 100);
  const teacherTotalRaw = data?.teachers?.total || 0;
  const teacherPresent = data?.teachers?.present || 0;
  const teacherAbsent = data?.teachers?.absent || 0;
  const teacherExcused = data?.teachers?.excused || 0;
  const teacherLate = data?.teachers?.late || 0;
  const teacherPercent = Math.round((teacherPresent / Math.max(teacherTotalRaw, 1)) * 100);

  const overallTotal = studentTotalRaw + teacherTotalRaw;
  const overallPresent = studentPresent + teacherPresent;
  const overallPercent = Math.round((overallPresent / Math.max(overallTotal, 1)) * 100);

  const getColor = (pct) => {
    if (pct >= 90) return { ring: '#10b981', bg: 'rgba(16,185,129,0.15)', label: isRTL ? 'ممتاز' : 'Excellent', labelColor: 'text-emerald-600 dark:text-emerald-400' };
    if (pct >= 75) return { ring: '#f59e0b', bg: 'rgba(245,158,11,0.15)', label: isRTL ? 'جيد' : 'Good', labelColor: 'text-amber-600 dark:text-amber-400' };
    return { ring: '#ef4444', bg: 'rgba(239,68,68,0.15)', label: isRTL ? 'يحتاج متابعة' : 'Needs Attention', labelColor: 'text-red-600 dark:text-red-400' };
  };

  const RadialRing = ({ percent, size = 130, strokeWidth = 12, color }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percent / 100) * circumference;
    return (
      <svg width={size} height={size} className="transform -rotate-90 drop-shadow-sm">
        <circle cx={size/2} cy={size/2} r={radius} stroke={color.bg} strokeWidth={strokeWidth} fill="none" />
        <circle cx={size/2} cy={size/2} r={radius} stroke={color.ring} strokeWidth={strokeWidth} fill="none"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-in-out', filter: `drop-shadow(0 0 6px ${color.ring}40)` }}
        />
      </svg>
    );
  };

  const StatBar = ({ label, value, total, color, icon: Icon }) => {
    const pct = total > 0 ? Math.round((value / total) * 100) : 0;
    return (
      <div className="flex items-center gap-2.5">
        <div className={`w-7 h-7 rounded-lg ${color} flex items-center justify-center shrink-0`}>
          <Icon className="h-3.5 w-3.5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[11px] font-tajawal text-muted-foreground">{label}</span>
            <span className="text-[11px] font-cairo font-bold">{value}<span className="text-muted-foreground font-normal">/{total}</span></span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
    );
  };

  const categories = [
    { 
      label: isRTL ? 'الطلاب' : 'Students', 
      percent: studentPercent, present: studentPresent, absent: studentAbsent, 
      excused: studentExcused, late: studentLate, total: studentTotalRaw, icon: Users 
    },
    { 
      label: isRTL ? 'المعلمون' : 'Teachers', 
      percent: teacherPercent, present: teacherPresent, absent: teacherAbsent, 
      excused: teacherExcused, late: teacherLate, total: teacherTotalRaw, icon: GraduationCap 
    },
  ];

  const overallColor = getColor(overallPercent);

  return (
    <Card className="card-nassaq">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-lg">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-turquoise to-brand-turquoise/70 flex items-center justify-center">
              <UserCheck className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? 'لوحة الحضور' : 'Attendance Dashboard'}
          </CardTitle>
          <div className={`px-2.5 py-1 rounded-lg text-[11px] font-tajawal font-medium ${overallColor.labelColor} bg-current/5`}
            style={{ backgroundColor: `${overallColor.ring}15` }}>
            {overallColor.label}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          {categories.map((cat, i) => {
            const color = getColor(cat.percent);
            return (
              <div key={i} className="relative p-4 rounded-2xl bg-muted/30 border border-border/50">
                <div className="flex flex-col items-center text-center mb-4">
                  <div className="relative mb-2">
                    <RadialRing percent={cat.percent} color={color} />
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold font-cairo" style={{ color: color.ring }}>{cat.percent}%</span>
                      <span className={`text-[10px] font-tajawal font-medium ${color.labelColor}`}>{color.label}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <cat.icon className="h-4 w-4 text-muted-foreground" />
                    <span className="font-tajawal text-sm font-semibold">{cat.label}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-cairo">{cat.total}</Badge>
                  </div>
                </div>

                <div className="space-y-2.5">
                  <StatBar label={isRTL ? 'حاضر' : 'Present'} value={cat.present} total={cat.total} color="bg-emerald-500" icon={UserCheck} />
                  <StatBar label={isRTL ? 'غائب' : 'Absent'} value={cat.absent} total={cat.total} color="bg-red-500" icon={UserX} />
                  <StatBar label={isRTL ? 'مستأذن' : 'Excused'} value={cat.excused} total={cat.total} color="bg-amber-500" icon={Clock} />
                  {cat.late > 0 && (
                    <StatBar label={isRTL ? 'متأخر' : 'Late'} value={cat.late} total={cat.total} color="bg-orange-500" icon={Timer} />
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5 dark:from-brand-navy/20 dark:to-brand-turquoise/20 border border-brand-turquoise/10">
          <div className="relative shrink-0">
            <RadialRing percent={overallPercent} size={56} strokeWidth={6} color={overallColor} />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-sm font-bold font-cairo" style={{ color: overallColor.ring }}>{overallPercent}%</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-cairo font-semibold">{isRTL ? 'الحضور الإجمالي' : 'Overall Attendance'}</p>
            <p className="text-[11px] text-muted-foreground font-tajawal">
              {isRTL ? `${overallPresent} من ${overallTotal} حاضرون اليوم` : `${overallPresent} of ${overallTotal} present today`}
            </p>
          </div>
          <div className="text-end shrink-0">
            <p className="text-lg font-bold font-cairo" style={{ color: overallColor.ring }}>{overallPresent}</p>
            <p className="text-[10px] text-muted-foreground font-tajawal">{isRTL ? 'حاضر' : 'present'}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const DailyOpsPanel = ({ data, isRTL, onNavigate }) => {
  const ops = data || {};
  const items = [
    {
      label: isRTL ? 'الطلاب المتغيبون اليوم' : 'Absent Students Today',
      count: ops.absentStudentsToday || 0,
      icon: UserX,
      color: 'bg-red-500',
      textColor: 'text-red-500',
      bgLight: 'bg-red-50 dark:bg-red-950/30',
      ringColor: 'ring-red-500/20',
      path: '/admin/attendance',
      actionLabel: isRTL ? 'عرض الغياب' : 'View',
      priority: 'critical',
    },
    {
      label: isRTL ? 'حصص لم يُسجَّل حضورها' : 'Unrecorded Attendance',
      count: ops.unrecordedAttendance || 0,
      icon: ClipboardList,
      color: 'bg-amber-500',
      textColor: 'text-amber-500',
      bgLight: 'bg-amber-50 dark:bg-amber-950/30',
      ringColor: 'ring-amber-500/20',
      path: '/admin/attendance',
      actionLabel: isRTL ? 'متابعة' : 'Follow Up',
      priority: 'high',
    },
    {
      label: isRTL ? 'حصص بلا معلم' : 'Unassigned Sessions',
      count: ops.classesWithoutTeacher || 0,
      icon: AlertTriangle,
      color: 'bg-orange-500',
      textColor: 'text-orange-500',
      bgLight: 'bg-orange-50 dark:bg-orange-950/30',
      ringColor: 'ring-orange-500/20',
      path: '/school/schedule',
      actionLabel: isRTL ? 'تعيين' : 'Assign',
      priority: 'high',
    },
    {
      label: isRTL ? 'تنبيهات أكاديمية' : 'Academic Alerts',
      count: ops.academicAlerts || 0,
      icon: AlertCircle,
      color: 'bg-violet-500',
      textColor: 'text-violet-500',
      bgLight: 'bg-violet-50 dark:bg-violet-950/30',
      ringColor: 'ring-violet-500/20',
      path: '/principal/ai-insights',
      actionLabel: isRTL ? 'مراجعة' : 'Review',
      priority: 'medium',
    },
    {
      label: isRTL ? 'إشعارات جديدة' : 'New Notifications',
      count: ops.newNotifications || 0,
      icon: Send,
      color: 'bg-blue-500',
      textColor: 'text-blue-500',
      bgLight: 'bg-blue-50 dark:bg-blue-950/30',
      ringColor: 'ring-blue-500/20',
      path: '/notifications',
      actionLabel: isRTL ? 'عرض' : 'View',
      priority: 'low',
    },
    {
      label: isRTL ? 'معلمون بغياب متكرر' : 'Frequent Teacher Absence',
      count: ops.teachersWithFrequentAbsence || 0,
      icon: UserCheck,
      color: 'bg-rose-500',
      textColor: 'text-rose-500',
      bgLight: 'bg-rose-50 dark:bg-rose-950/30',
      ringColor: 'ring-rose-500/20',
      path: '/admin/users-management',
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
            {isRTL ? 'العمليات اليومية' : 'Daily Operations'}
          </CardTitle>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 text-[10px] px-2 py-0.5 font-cairo border-0 animate-pulse">
                {criticalCount} {isRTL ? 'عاجل' : 'urgent'}
              </Badge>
            )}
            {total > 0 ? (
              <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 text-xs px-2.5 py-0.5 font-cairo border-0">{total}</Badge>
            ) : (
              <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-xs px-2 py-0.5 font-cairo border-0">
                <CheckCircle2 className="h-3 w-3 mr-1" />{isRTL ? 'مكتمل' : 'Clear'}
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
            <p className="font-tajawal text-sm font-semibold text-emerald-600 dark:text-emerald-400">{isRTL ? 'لا توجد مهام معلّقة' : 'No pending tasks'}</p>
            <p className="font-tajawal text-xs text-muted-foreground mt-1">{isRTL ? 'اليوم الدراسي يسير بسلاسة' : 'School day running smoothly'}</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {sorted.map((item, idx) => {
              const ItemIcon = item.icon;
              const isCritical = item.priority === 'critical';
              return (
                <button key={idx} onClick={() => onNavigate?.(item.path)}
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
                      {item.priority === 'critical' ? (isRTL ? 'يتطلب اهتمام فوري' : 'Immediate attention') :
                       item.priority === 'high' ? (isRTL ? 'أولوية عالية' : 'High priority') :
                       item.priority === 'medium' ? (isRTL ? 'متابعة مطلوبة' : 'Follow-up needed') :
                       (isRTL ? 'إعلامي' : 'Informational')}
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
  const m = metrics || {};
  const totalStudents = m.totalStudents?.value || 0;
  const totalTeachers = m.totalTeachers?.value || 0;
  const totalClasses = m.totalClasses?.value || 0;
  const todaySessions = m.todaySessions?.value || 0;
  const attendanceRate = attendance ? Math.round(((attendance.students?.present || 0) / Math.max(attendance.students?.total || 1, 1)) * 100) : 0;

  const stats = [
    { 
      label: isRTL ? 'إجمالي الطلاب' : 'Total Students', 
      value: totalStudents, 
      icon: Users, 
      gradient: 'from-blue-500 to-blue-600',
      bgLight: 'bg-blue-50 dark:bg-blue-950/30',
      change: m.totalStudents?.change, 
      changeType: m.totalStudents?.changeType 
    },
    { 
      label: isRTL ? 'إجمالي المعلمين' : 'Total Teachers', 
      value: totalTeachers, 
      icon: GraduationCap, 
      gradient: 'from-emerald-500 to-emerald-600',
      bgLight: 'bg-emerald-50 dark:bg-emerald-950/30',
      change: m.totalTeachers?.change, 
      changeType: m.totalTeachers?.changeType 
    },
    { 
      label: isRTL ? 'الفصول الدراسية' : 'Classes', 
      value: totalClasses, 
      icon: School, 
      gradient: 'from-violet-500 to-violet-600',
      bgLight: 'bg-violet-50 dark:bg-violet-950/30',
      change: m.totalClasses?.change, 
      changeType: m.totalClasses?.changeType 
    },
    { 
      label: isRTL ? 'حصص اليوم' : "Today's Sessions", 
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
            {isRTL ? 'لمحة عامة' : 'Overview Snapshot'}
          </CardTitle>
          <div className="flex items-center gap-1.5 text-[11px] font-tajawal text-muted-foreground">
            <CircleDot className="h-3 w-3 text-emerald-500 animate-pulse" />
            {isRTL ? 'مباشر' : 'Live'}
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
            <span className="text-sm font-cairo font-semibold">{isRTL ? 'معدل الحضور اليوم' : "Today's Attendance Rate"}</span>
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
  const navItems = [
    { id: 'users', label: isRTL ? 'إدارة المستخدمين' : 'User Management', icon: Users, path: '/admin/users-management', color: 'from-blue-500 to-blue-600' },
    { id: 'schedule', label: isRTL ? 'الجدول الدراسي' : 'Timetable', icon: CalendarDays, path: '/school/schedule', color: 'from-emerald-500 to-emerald-600' },
    { id: 'attendance', label: isRTL ? 'الحضور والغياب' : 'Attendance', icon: ClipboardList, path: '/admin/attendance', color: 'from-violet-500 to-violet-600' },
    { id: 'reports', label: isRTL ? 'التقارير' : 'Reports', icon: BarChart3, path: '/principal/reports', color: 'from-amber-500 to-amber-600' },
    { id: 'communication', label: isRTL ? 'مركز التواصل والإشعارات' : 'Communication', icon: Megaphone, path: '/principal/communication', color: 'from-pink-500 to-pink-600' },
    { id: 'settings', label: isRTL ? 'إعدادات المدرسة' : 'School Settings', icon: Settings, path: '/school/settings', color: 'from-slate-500 to-slate-600' },
  ];

  return (
    <Card className="card-nassaq">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 font-cairo text-lg">
          <LayoutDashboard className="h-5 w-5 text-brand-turquoise" />
          {isRTL ? 'التنقل السريع' : 'Quick Navigation'}
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

const QuickAddBar = ({ onAction, isRTL }) => {
  const actions = [
    { id: 'add-student', label: isRTL ? 'إضافة طالب' : 'Add Student', icon: UserPlus, color: 'text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/30 border-blue-200 dark:border-blue-800' },
    { id: 'add-teacher', label: isRTL ? 'إضافة معلم' : 'Add Teacher', icon: GraduationCap, color: 'text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800' },
    { id: 'create-class', label: isRTL ? 'إنشاء فصل' : 'Create Class', icon: School, color: 'text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/30 border-purple-200 dark:border-purple-800' },
    { id: 'send-notification', label: isRTL ? 'إرسال إشعار' : 'Send Notice', icon: Send, color: 'text-pink-600 dark:text-pink-400 hover:bg-pink-50 dark:hover:bg-pink-950/30 border-pink-200 dark:border-pink-800' },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      {actions.map((a) => (
        <Button key={a.id} variant="outline" size="sm" onClick={() => onAction(a.id)}
          className={`rounded-xl text-xs h-8 px-3 border ${a.color} transition-all`}>
          <a.icon className="h-3.5 w-3.5 me-1.5" />
          {a.label}
        </Button>
      ))}
    </div>
  );
};

export const SchoolDashboardContent = () => {
  const { isRTL } = useTheme();
  const { api, schoolContext, isImpersonating } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboardData, setDashboardData] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [grades, setGrades] = useState([]);
  const [classes, setClasses] = useState([]);

  const [showAddStudentWizard, setShowAddStudentWizard] = useState(false);
  const [showAddTeacherWizard, setShowAddTeacherWizard] = useState(false);
  const [showCreateClassWizard, setShowCreateClassWizard] = useState(false);
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
    const fetchWizardData = async () => {
      try {
        const [gradesRes, classesRes] = await Promise.all([
          api.get('/reference/grades').catch(() => ({ data: [] })),
          api.get('/classes').catch(() => ({ data: [] })),
        ]);
        setGrades(gradesRes.data || []);
        setClasses(classesRes.data || []);
      } catch (err) {
        console.error('Error fetching wizard data:', err);
      }
    };
    fetchWizardData();
  }, [api, fetchDashboardData]);

  useEffect(() => {
    const interval = setInterval(() => fetchDashboardData(false), 20000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  const handleQuickAction = (actionId) => {
    switch (actionId) {
      case 'add-student': setShowAddStudentWizard(true); break;
      case 'add-teacher': setShowAddTeacherWizard(true); break;
      case 'create-class': setShowCreateClassWizard(true); break;
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
        <p className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'جارٍ تحميل مركز القيادة...' : 'Loading Command Center...'}</p>
      </div>
    );
  }

  const m = dashboardData?.metrics;

  return (
    <div className="space-y-5" data-testid="school-dashboard-content">
      <div className="flex items-center justify-between">
        <QuickAddBar onAction={handleQuickAction} isRTL={isRTL} />
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
              <span className="font-tajawal">
                {lastUpdated.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          )}
          <Button size="icon" variant="outline" onClick={() => fetchDashboardData(true)} disabled={refreshing}
            className="rounded-xl h-8 w-8 border-border/50 hover:bg-muted" title={isRTL ? 'تحديث' : 'Refresh'}>
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <SectionErrorBoundary name="SchoolDayProgress" isRTL={isRTL} fallbackMessage={isRTL ? 'تعذّر تحميل تقدّم اليوم الدراسي' : 'Failed to load school day progress'}>
        <SchoolDayProgress isRTL={isRTL} />
      </SectionErrorBoundary>

      <section data-testid="key-metrics-section">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <HeroMetric
            title={isRTL ? 'إجمالي الطلاب' : 'Total Students'}
            value={m?.totalStudents?.value || 0}
            change={m?.totalStudents?.change}
            changeType={m?.totalStudents?.changeType}
            subtitle={isRTL ? 'المسجلين في المدرسة' : 'Enrolled students'}
            icon={Users}
            gradient="bg-gradient-to-br from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700"
            onClick={() => navigate('/admin/users-management')}
            isRTL={isRTL}
          />
          <HeroMetric
            title={isRTL ? 'إجمالي المعلمين' : 'Total Teachers'}
            value={m?.totalTeachers?.value || 0}
            change={m?.totalTeachers?.change}
            changeType={m?.totalTeachers?.changeType}
            subtitle={isRTL ? 'الكادر التعليمي' : 'Teaching staff'}
            icon={GraduationCap}
            gradient="bg-gradient-to-br from-emerald-500 to-emerald-600 dark:from-emerald-600 dark:to-emerald-700"
            onClick={() => navigate('/admin/users-management')}
            isRTL={isRTL}
          />
          <HeroMetric
            title={isRTL ? 'حصص اليوم' : "Today's Sessions"}
            value={m?.todaySessions?.value || 0}
            change={m?.todaySessions?.change}
            changeType={m?.todaySessions?.changeType}
            subtitle={isRTL ? 'الحصص المجدولة' : 'Scheduled sessions'}
            icon={Clock}
            gradient="bg-gradient-to-br from-violet-500 to-violet-600 dark:from-violet-600 dark:to-violet-700"
            onClick={() => navigate('/school/schedule')}
            isRTL={isRTL}
          />
          <HeroMetric
            title={isRTL ? 'حصص الانتظار' : 'Substitute Queue'}
            value={m?.waitingSubstitute?.value || 0}
            change={m?.waitingSubstitute?.change}
            changeType={m?.waitingSubstitute?.changeType}
            subtitle={isRTL ? 'بانتظار بديل' : 'Awaiting substitute'}
            icon={Timer}
            gradient={`bg-gradient-to-br ${(m?.waitingSubstitute?.value || 0) > 0 ? 'from-red-500 to-red-600 dark:from-red-600 dark:to-red-700' : 'from-slate-500 to-slate-600 dark:from-slate-600 dark:to-slate-700'}`}
            onClick={() => setShowLiveSessionsMonitor(true)}
            isRTL={isRTL}
          />
        </div>
      </section>

      <section className="grid lg:grid-cols-2 gap-5" data-testid="dashboard-kpi-section">
        <SectionErrorBoundary name="AttendanceRadial" isRTL={isRTL} fallbackMessage={isRTL ? 'تعذّر تحميل بيانات الحضور' : 'Failed to load attendance data'}>
          <AttendanceRadial data={dashboardData?.attendance} isRTL={isRTL} />
        </SectionErrorBoundary>
        <SectionErrorBoundary name="DailyOpsPanel" isRTL={isRTL} fallbackMessage={isRTL ? 'تعذّر تحميل لوحة العمليات' : 'Failed to load operations panel'}>
          <DailyOpsPanel data={dashboardData?.interventions} isRTL={isRTL} onNavigate={(path) => navigate(path)} />
        </SectionErrorBoundary>
      </section>

      <SectionErrorBoundary name="StrategicNav" isRTL={isRTL}>
        <StrategicNav onAction={handleQuickAction} isRTL={isRTL} onNavigate={(path) => navigate(path)} />
      </SectionErrorBoundary>

      <section>
        <SectionErrorBoundary name="PerformanceSnapshot" isRTL={isRTL}>
          <PerformanceSnapshot metrics={dashboardData?.metrics} attendance={dashboardData?.attendance} isRTL={isRTL} />
        </SectionErrorBoundary>
      </section>

      <AddStudentWizard 
        open={showAddStudentWizard} 
        onOpenChange={setShowAddStudentWizard}
        isRTL={isRTL}
        api={api}
        grades={grades}
        classes={classes}
        onSuccess={() => fetchDashboardData(true)}
      />
      <AddTeacherWizard open={showAddTeacherWizard} onOpenChange={setShowAddTeacherWizard} />
      <CreateClassWizard open={showCreateClassWizard} onOpenChange={setShowCreateClassWizard} />
      <SendNotificationWizard open={showSendNotificationWizard} onOpenChange={setShowSendNotificationWizard} />
      <CreateScheduleWizard open={showCreateScheduleWizard} onOpenChange={setShowCreateScheduleWizard} />
      <LiveSessionsMonitor open={showLiveSessionsMonitor} onOpenChange={setShowLiveSessionsMonitor} />
    </div>
  );
};

export default SchoolDashboardContent;
