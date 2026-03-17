import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Building2, Users, GraduationCap, UserCheck, Activity, BarChart3, Brain,
  Zap, Shield, Clock, RefreshCw, Sparkles, Calendar, Settings,
  BookOpen, ChevronRight, Play, Server, Eye, CheckCircle,
  TrendingUp, TrendingDown, AlertTriangle, Bell, User, BookOpenCheck,
  School, Layers, ClipboardList, HeartPulse, Loader2, ArrowUpRight,
  Database, Wifi, CircleDot, MessagesSquare, UserCog, LayoutDashboard
} from 'lucide-react';
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, BarChart, Bar, Cell, PieChart, Pie
} from 'recharts';
import CreateSchoolWizard from '../components/wizards/CreateSchoolWizard';
import CreateUserWizard from '../components/wizards/CreateUserWizard';
import QuickAIOperationsPanel from '../components/ai/QuickAIOperationsPanel';

const HAKIM_AVATAR = '/hakim-poses/analyzing-data.png';

const KPICard = ({ icon: Icon, iconColor, title, value, subtitle, trend, trendValue, onClick, className = '' }) => (
  <Card
    className={`group relative overflow-hidden border-0 shadow-md hover:shadow-xl transition-all duration-300 cursor-pointer ${className}`}
    onClick={onClick}
  >
    <div className="absolute inset-0 bg-gradient-to-br from-white/80 to-white/40 dark:from-slate-800/80 dark:to-slate-800/40" />
    <CardContent className="relative p-4 sm:p-5">
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-xl ${iconColor} shadow-sm`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        {trend && (
          <div className={`flex items-center gap-1 text-xs font-semibold px-2 py-1 rounded-full ${
            trend === 'up' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
            trend === 'down' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
            'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
          }`}>
            {trend === 'up' ? <TrendingUp className="h-3 w-3" /> : trend === 'down' ? <TrendingDown className="h-3 w-3" /> : null}
            {trendValue}
          </div>
        )}
      </div>
      <div className="space-y-1">
        <p className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white font-cairo">{value}</p>
        <p className="text-sm font-medium text-slate-600 dark:text-slate-400 font-tajawal">{title}</p>
        {subtitle && <p className="text-xs text-slate-400 dark:text-slate-500">{subtitle}</p>}
      </div>
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r opacity-0 group-hover:opacity-100 transition-opacity" 
           style={{ backgroundImage: `linear-gradient(to right, var(--tw-gradient-from), var(--tw-gradient-to))` }} />
    </CardContent>
  </Card>
);

const HealthIndicator = ({ label, status, detail }) => (
  <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50">
    <div className="flex items-center gap-3">
      <div className={`w-2.5 h-2.5 rounded-full ${
        status === 'healthy' || status === 'active' ? 'bg-emerald-500 animate-pulse' :
        status === 'warning' ? 'bg-amber-500 animate-pulse' : 'bg-red-500 animate-pulse'
      }`} />
      <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
    </div>
    <Badge variant="outline" className={`text-xs ${
      status === 'healthy' || status === 'active' ? 'border-emerald-300 text-emerald-700 dark:text-emerald-400' :
      status === 'warning' ? 'border-amber-300 text-amber-700' : 'border-red-300 text-red-700'
    }`}>
      {detail || status}
    </Badge>
  </div>
);

export const AdminDashboard = () => {
  const navigate = useNavigate();
  const { api, user } = useAuth();
  const { isRTL, isDark } = useTheme();
  const { nassaqError } = useNassaqAlert();

  const [stats, setStats] = useState(null);
  const [schoolsOverview, setSchoolsOverview] = useState([]);
  const [systemHealth, setSystemHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAddSchoolWizard, setShowAddSchoolWizard] = useState(false);
  const [showCreateUserWizard, setShowCreateUserWizard] = useState(false);
  const [hakimInsights, setHakimInsights] = useState([]);

  const fetchAllData = useCallback(async (showToast = false) => {
    try {
      if (showToast) setRefreshing(true);
      const [ccRes, saRes, schoolsRes, healthRes] = await Promise.allSettled([
        api.get('/admin/command-center/stats'),
        api.get('/super-admin/dashboard-stats'),
        api.get('/admin/command-center/schools-overview'),
        api.get('/admin/command-center/system-health'),
      ]);

      const cc = ccRes.status === 'fulfilled' ? ccRes.value.data : {};
      const sa = saRes.status === 'fulfilled' ? saRes.value.data : {};

      setStats({ ...sa, ...cc });

      if (schoolsRes.status === 'fulfilled') {
        setSchoolsOverview(schoolsRes.value.data?.schools || []);
      }
      if (healthRes.status === 'fulfilled') {
        setSystemHealth(healthRes.value.data);
      }

      generateHakimInsights(cc, schoolsRes.status === 'fulfilled' ? schoolsRes.value.data?.schools : []);

      if (showToast) toast.success(isRTL ? 'تم تحديث البيانات' : 'Data refreshed');
    } catch (error) {
      console.error('Dashboard fetch error:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, isRTL]);

  const generateHakimInsights = (cc, schools) => {
    const insights = [];
    if (cc?.pending_requests > 0) {
      insights.push({ type: 'warning', text: isRTL ? `يوجد ${cc.pending_requests} طلب تسجيل معلق يحتاج مراجعة` : `${cc.pending_requests} pending registration requests need review` });
    }
    const incompleteSchools = (schools || []).filter(s => s.setup_score < 100);
    if (incompleteSchools.length > 0) {
      insights.push({ type: 'info', text: isRTL ? `${incompleteSchools.length} مدارس لم تكمل إعداداتها بعد` : `${incompleteSchools.length} schools haven't completed setup` });
    }
    if (cc?.student_attendance_rate > 0 && cc.student_attendance_rate < 85) {
      insights.push({ type: 'alert', text: isRTL ? `نسبة حضور الطلاب ${cc.student_attendance_rate}% أقل من المتوسط المطلوب` : `Student attendance ${cc.student_attendance_rate}% below target` });
    }
    if (cc?.active_sessions_now > 0) {
      insights.push({ type: 'success', text: isRTL ? `${cc.active_sessions_now} حصة جارية الآن على مستوى المنصة` : `${cc.active_sessions_now} sessions active now across platform` });
    }
    if (cc?.active_users_today > 0) {
      insights.push({ type: 'info', text: isRTL ? `${cc.active_users_today} مستخدم نشط اليوم` : `${cc.active_users_today} active users today` });
    }
    if (insights.length === 0) {
      insights.push({ type: 'success', text: isRTL ? 'النظام يعمل بشكل طبيعي. لا توجد تنبيهات حالياً' : 'System running normally. No alerts.' });
    }
    setHakimInsights(insights);
  };

  useEffect(() => { fetchAllData(); }, [fetchAllData]);

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
          <div className="text-center space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-brand-turquoise mx-auto" />
            <p className="text-lg font-cairo text-slate-600 dark:text-slate-400">
              {isRTL ? 'جاري تحميل مركز القيادة...' : 'Loading Command Center...'}
            </p>
          </div>
        </div>
      </Sidebar>
    );
  }

  const s = stats || {};

  const primaryKPIs = [
    { icon: School, iconColor: 'bg-brand-navy', title: isRTL ? 'المدارس المسجلة' : 'Schools', value: s.registered_schools || 0, subtitle: isRTL ? `${s.active_schools || 0} نشطة` : `${s.active_schools || 0} active`, onClick: () => navigate('/admin/schools') },
    { icon: GraduationCap, iconColor: 'bg-blue-600', title: isRTL ? 'إجمالي الطلاب' : 'Students', value: (s.registered_students || 0).toLocaleString(), subtitle: isRTL ? `${s.students_present_today || 0} حاضر اليوم` : `${s.students_present_today || 0} present today`, onClick: () => navigate('/admin/schools') },
    { icon: UserCheck, iconColor: 'bg-brand-purple', title: isRTL ? 'إجمالي المعلمين' : 'Teachers', value: s.teachers_in_schools || 0, subtitle: isRTL ? `${s.teachers_present_today || 0} حاضر اليوم` : `${s.teachers_present_today || 0} present today`, onClick: () => navigate('/admin/users') },
    { icon: Users, iconColor: 'bg-emerald-600', title: isRTL ? 'أولياء الأمور' : 'Parents', value: s.total_parents || 0, onClick: () => navigate('/admin/users') },
    { icon: Layers, iconColor: 'bg-indigo-600', title: isRTL ? 'الفصول الدراسية' : 'Classes', value: s.total_classes || 0, onClick: () => navigate('/admin/schools') },
    { icon: BookOpen, iconColor: 'bg-cyan-600', title: isRTL ? 'المواد الدراسية' : 'Subjects', value: s.total_subjects || 0, onClick: () => navigate('/admin/schools') },
  ];

  const operationalKPIs = [
    { icon: Play, iconColor: 'bg-emerald-600', title: isRTL ? 'الحصص اليوم' : 'Sessions Today', value: s.sessions_today || 0, subtitle: isRTL ? `${s.active_sessions_now || 0} جارية الآن` : `${s.active_sessions_now || 0} active now` },
    { icon: Activity, iconColor: 'bg-green-600', title: isRTL ? 'حضور الطلاب' : 'Student Attendance', value: `${s.student_attendance_rate || 0}%`, trend: s.student_attendance_rate > 85 ? 'up' : 'down', trendValue: s.student_attendance_rate > 85 ? (isRTL ? 'جيد' : 'Good') : (isRTL ? 'منخفض' : 'Low') },
    { icon: Activity, iconColor: 'bg-blue-600', title: isRTL ? 'حضور المعلمين' : 'Teacher Attendance', value: `${s.teacher_attendance_rate || 0}%`, trend: s.teacher_attendance_rate > 90 ? 'up' : 'down', trendValue: s.teacher_attendance_rate > 90 ? (isRTL ? 'ممتاز' : 'Excellent') : (isRTL ? 'منخفض' : 'Low') },
    { icon: Bell, iconColor: 'bg-amber-600', title: isRTL ? 'الإشعارات اليوم' : 'Notifications Today', value: s.notifications_sent_today || 0 },
    { icon: User, iconColor: 'bg-teal-600', title: isRTL ? 'المستخدمون النشطون' : 'Active Users', value: s.active_users_today || 0 },
    { icon: ClipboardList, iconColor: 'bg-orange-600', title: isRTL ? 'السلوكيات المسجلة' : 'Behaviour Records', value: s.behaviour_records_today || 0 },
  ];

  const adminKPIs = [
    { icon: Shield, iconColor: 'bg-violet-600', title: isRTL ? 'حسابات المنصة' : 'Platform Accounts', value: s.platform_accounts || 0, onClick: () => navigate('/admin/users') },
    { icon: UserCog, iconColor: 'bg-rose-600', title: isRTL ? 'مدراء المدارس' : 'School Admins', value: s.total_school_admins || 0 },
    { icon: Clock, iconColor: 'bg-amber-600', title: isRTL ? 'طلبات معلقة' : 'Pending Requests', value: s.pending_requests || 0, trend: s.pending_requests > 0 ? 'up' : null, trendValue: isRTL ? 'تحتاج مراجعة' : 'Needs review', onClick: () => navigate('/admin/users') },
    { icon: Calendar, iconColor: 'bg-sky-600', title: isRTL ? 'الجداول المنشورة' : 'Published Timetables', value: s.published_timetables || 0 },
    { icon: Sparkles, iconColor: 'bg-cyan-600', title: isRTL ? 'مدارس AI' : 'AI Schools', value: s.ai_enabled_schools || 0 },
    { icon: LayoutDashboard, iconColor: 'bg-slate-600', title: isRTL ? 'إجمالي المستخدمين' : 'Total Users', value: s.total_users || 0 },
  ];

  const schoolsPieData = [
    { name: isRTL ? 'نشطة' : 'Active', value: s.active_schools || 0, color: '#22c55e' },
    { name: isRTL ? 'معلقة' : 'Pending', value: s.pending_schools || 0, color: '#f59e0b' },
    { name: isRTL ? 'موقوفة' : 'Suspended', value: s.suspended_schools || 0, color: '#ef4444' },
  ].filter(d => d.value > 0);

  const attendanceBarData = [
    { name: isRTL ? 'حاضرون' : 'Present', students: s.students_present_today || 0, teachers: s.teachers_present_today || 0 },
    { name: isRTL ? 'غائبون' : 'Absent', students: s.students_absent_today || 0, teachers: s.teachers_absent_today || 0 },
  ];

  const schoolsBarData = schoolsOverview.slice(0, 6).map(sc => ({
    name: sc.name?.split(' ').slice(0, 2).join(' ') || '?',
    students: sc.student_count || 0,
    teachers: sc.teacher_count || 0,
  }));

  const quickActions = [
    { icon: Building2, label: isRTL ? 'إضافة مدرسة' : 'Add School', action: () => setShowAddSchoolWizard(true), color: 'bg-brand-navy hover:bg-brand-navy/90' },
    { icon: Users, label: isRTL ? 'إدارة المستخدمين' : 'Manage Users', action: () => navigate('/admin/users'), color: 'bg-brand-purple hover:bg-brand-purple/90' },
    { icon: BarChart3, label: isRTL ? 'التقارير' : 'Reports', action: () => navigate('/admin/reports'), color: 'bg-brand-turquoise hover:bg-brand-turquoise/90' },
    { icon: Settings, label: isRTL ? 'الإعدادات' : 'Settings', action: () => navigate('/settings'), color: 'bg-slate-700 hover:bg-slate-600' },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">

          {/* Hero Section */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple p-6 sm:p-8 text-white shadow-2xl">
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0zNiAxOGMwLTkuOTQtOC4wNi0xOC0xOC0xOFYwYzE5Ljg4IDAgMzYgMTYuMTIgMzYgMzZ6IiBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuMDMpIi8+PC9nPjwvc3ZnPg==')] opacity-30" />
            <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/10 rounded-xl backdrop-blur-sm">
                    <LayoutDashboard className="h-6 w-6" />
                  </div>
                  <div>
                    <h1 className="text-2xl sm:text-3xl font-bold font-cairo">
                      {isRTL ? 'مركز القيادة' : 'Command Center'}
                    </h1>
                    <p className="text-white/70 text-sm font-tajawal">
                      {isRTL ? 'نظرة شاملة على المنصة' : 'Platform Overview'}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm text-white/60">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="h-4 w-4" />
                    {s.hijri_date || ''}
                  </span>
                  <span className="text-white/30">|</span>
                  <span>{s.gregorian_date || new Date().toLocaleDateString('en-GB')}</span>
                  <span className="text-white/30">|</span>
                  <span className="flex items-center gap-1.5">
                    <CircleDot className="h-3 w-3 text-emerald-400 animate-pulse" />
                    {isRTL ? 'متصل' : 'Online'}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="border-white/20 text-white hover:bg-white/10"
                  onClick={() => fetchAllData(true)}
                  disabled={refreshing}
                >
                  <RefreshCw className={`h-4 w-4 me-1.5 ${refreshing ? 'animate-spin' : ''}`} />
                  {isRTL ? 'تحديث' : 'Refresh'}
                </Button>
                <NotificationBell />
              </div>
            </div>

            {/* Quick Stats Row */}
            <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: isRTL ? 'المدارس' : 'Schools', value: s.registered_schools || 0, icon: School },
                { label: isRTL ? 'الطلاب' : 'Students', value: (s.registered_students || 0).toLocaleString(), icon: GraduationCap },
                { label: isRTL ? 'المعلمين' : 'Teachers', value: s.teachers_in_schools || 0, icon: UserCheck },
                { label: isRTL ? 'الحصص اليوم' : 'Sessions', value: s.sessions_today || 0, icon: Play },
              ].map((item, i) => (
                <div key={i} className="bg-white/10 backdrop-blur-sm rounded-xl p-3 text-center">
                  <item.icon className="h-5 w-5 mx-auto mb-1 text-brand-turquoise" />
                  <p className="text-xl sm:text-2xl font-bold">{item.value}</p>
                  <p className="text-xs text-white/60">{item.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {quickActions.map((action, i) => (
              <Button
                key={i}
                className={`h-auto py-3 px-4 ${action.color} text-white rounded-xl shadow-md hover:shadow-lg transition-all font-cairo text-sm`}
                onClick={action.action}
              >
                <action.icon className="h-5 w-5 me-2" />
                {action.label}
              </Button>
            ))}
          </div>

          {/* Hakim AI Insights */}
          {hakimInsights.length > 0 && (
            <Card className="border-0 shadow-lg bg-gradient-to-r from-cyan-50 to-blue-50 dark:from-cyan-950/30 dark:to-blue-950/30 overflow-hidden">
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 flex flex-col items-center gap-1.5">
                    <div className="w-24 h-24 rounded-2xl overflow-hidden shadow-lg border-2 border-violet-200 dark:border-violet-700 bg-gradient-to-br from-violet-50 to-cyan-50 dark:from-violet-900/30 dark:to-cyan-900/30 p-1">
                      <img src={HAKIM_AVATAR} alt="Hakim" className="w-full h-full object-contain drop-shadow-md" style={{ animation: 'hakimRxFloat 4s ease-in-out infinite' }} />
                    </div>
                    <span className="text-[10px] font-cairo font-bold text-brand-purple/60">{isRTL ? 'حكيم AI' : 'Hakim AI'}</span>
                  </div>
                  <div className="flex-1 space-y-2 min-w-0">
                    <p className="text-base font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                      {isRTL ? 'ملاحظات حكيم' : 'Hakim Insights'}
                    </p>
                    <div className="space-y-2">
                      {hakimInsights.map((insight, i) => (
                        <div key={i} className="flex items-start gap-2 text-sm">
                          <span className={`mt-0.5 text-base ${
                            insight.type === 'warning' ? 'text-amber-500' :
                            insight.type === 'alert' ? 'text-red-500' :
                            insight.type === 'success' ? 'text-emerald-500' : 'text-blue-500'
                          }`}>
                            {insight.type === 'warning' ? '⚠' : insight.type === 'alert' ? '🔴' : insight.type === 'success' ? '✅' : 'ℹ️'}
                          </span>
                          <span className="text-slate-700 dark:text-slate-300 font-tajawal">{insight.text}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <style>{`@keyframes hakimRxFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }`}</style>
              </CardContent>
            </Card>
          )}

          {/* Section: Primary KPIs */}
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white font-cairo mb-3 flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-brand-turquoise" />
              {isRTL ? 'المؤشرات العامة' : 'General Metrics'}
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {primaryKPIs.map((kpi, i) => (
                <KPICard key={i} {...kpi} />
              ))}
            </div>
          </div>

          {/* Section: Operational KPIs */}
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white font-cairo mb-3 flex items-center gap-2">
              <Activity className="h-5 w-5 text-emerald-500" />
              {isRTL ? 'المؤشرات التشغيلية' : 'Operational Metrics'}
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {operationalKPIs.map((kpi, i) => (
                <KPICard key={i} {...kpi} />
              ))}
            </div>
          </div>

          {/* Section: Admin KPIs */}
          <div>
            <h2 className="text-lg font-bold text-slate-800 dark:text-white font-cairo mb-3 flex items-center gap-2">
              <Shield className="h-5 w-5 text-violet-500" />
              {isRTL ? 'المؤشرات الإدارية' : 'Administrative Metrics'}
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {adminKPIs.map((kpi, i) => (
                <KPICard key={i} {...kpi} />
              ))}
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Schools Distribution Pie */}
            <Card className="border-0 shadow-md">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-cairo flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-brand-navy" />
                  {isRTL ? 'توزيع المدارس' : 'Schools Distribution'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {schoolsPieData.length > 0 ? (
                  <div className="flex items-center justify-between">
                    <ResponsiveContainer width="50%" height={180}>
                      <PieChart>
                        <Pie
                          data={schoolsPieData}
                          cx="50%" cy="50%"
                          innerRadius={40} outerRadius={70}
                          paddingAngle={4}
                          dataKey="value"
                        >
                          {schoolsPieData.map((entry, i) => (
                            <Cell key={i} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="space-y-3">
                      {schoolsPieData.map((item, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                          <span className="text-sm text-slate-600 dark:text-slate-400">{item.name}</span>
                          <span className="font-bold text-sm">{item.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="h-[180px] flex items-center justify-center text-slate-400">
                    {isRTL ? 'لا توجد بيانات' : 'No data'}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Attendance Chart */}
            <Card className="border-0 shadow-md">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-cairo flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-emerald-500" />
                  {isRTL ? 'الحضور اليوم' : 'Today\'s Attendance'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={attendanceBarData}>
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="students" fill="#3b82f6" radius={[4, 4, 0, 0]} name={isRTL ? 'طلاب' : 'Students'} />
                    <Bar dataKey="teachers" fill="#8b5cf6" radius={[4, 4, 0, 0]} name={isRTL ? 'معلمين' : 'Teachers'} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Schools Comparison */}
            <Card className="border-0 shadow-md">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-cairo flex items-center gap-2">
                  <School className="h-4 w-4 text-brand-purple" />
                  {isRTL ? 'مقارنة المدارس' : 'Schools Comparison'}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {schoolsBarData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart data={schoolsBarData} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 11 }} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={80} />
                      <Tooltip />
                      <Bar dataKey="students" fill="#3b82f6" radius={[0, 4, 4, 0]} name={isRTL ? 'طلاب' : 'Students'} />
                      <Bar dataKey="teachers" fill="#22c55e" radius={[0, 4, 4, 0]} name={isRTL ? 'معلمين' : 'Teachers'} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[180px] flex items-center justify-center text-slate-400">
                    {isRTL ? 'لا توجد بيانات' : 'No data'}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Schools Overview + System Health */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Schools Table */}
            <Card className="border-0 shadow-md lg:col-span-2">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-base font-cairo flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-brand-navy" />
                  {isRTL ? 'نظرة سريعة على المدارس' : 'Schools Quick View'}
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => navigate('/admin/schools')} className="text-brand-turquoise hover:text-brand-turquoise/80">
                  {isRTL ? 'عرض الكل' : 'View All'}
                  <ChevronRight className="h-4 w-4 ms-1" />
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-slate-800">
                        <th className="text-start p-3 font-medium text-slate-500 dark:text-slate-400">{isRTL ? 'المدرسة' : 'School'}</th>
                        <th className="text-center p-3 font-medium text-slate-500 dark:text-slate-400">{isRTL ? 'الطلاب' : 'Students'}</th>
                        <th className="text-center p-3 font-medium text-slate-500 dark:text-slate-400">{isRTL ? 'المعلمين' : 'Teachers'}</th>
                        <th className="text-center p-3 font-medium text-slate-500 dark:text-slate-400">{isRTL ? 'الفصول' : 'Classes'}</th>
                        <th className="text-center p-3 font-medium text-slate-500 dark:text-slate-400">{isRTL ? 'الجاهزية' : 'Setup'}</th>
                        <th className="text-center p-3 font-medium text-slate-500 dark:text-slate-400">{isRTL ? 'الحالة' : 'Status'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schoolsOverview.map((school, i) => (
                        <tr key={i} className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30 cursor-pointer transition-colors" onClick={() => navigate('/admin/schools')}>
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-lg bg-brand-navy/10 flex items-center justify-center">
                                <School className="h-4 w-4 text-brand-navy" />
                              </div>
                              <div>
                                <p className="font-medium text-slate-800 dark:text-white text-sm">{school.name}</p>
                                <p className="text-xs text-slate-400">{school.city || ''}</p>
                              </div>
                            </div>
                          </td>
                          <td className="p-3 text-center font-semibold text-blue-600">{school.student_count}</td>
                          <td className="p-3 text-center font-semibold text-purple-600">{school.teacher_count}</td>
                          <td className="p-3 text-center font-semibold text-slate-600 dark:text-slate-400">{school.class_count}</td>
                          <td className="p-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <div className="w-16 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                <div className={`h-full rounded-full ${school.setup_score === 100 ? 'bg-emerald-500' : school.setup_score >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${school.setup_score}%` }} />
                              </div>
                              <span className="text-xs font-medium text-slate-500">{school.setup_score}%</span>
                            </div>
                          </td>
                          <td className="p-3 text-center">
                            <Badge className={`text-xs ${school.status === 'active' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-amber-100 text-amber-700'}`}>
                              {school.status === 'active' ? (isRTL ? 'نشطة' : 'Active') : (isRTL ? 'معلقة' : 'Pending')}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                      {schoolsOverview.length === 0 && (
                        <tr>
                          <td colSpan={6} className="p-8 text-center text-slate-400">
                            {isRTL ? 'لا توجد مدارس مسجلة' : 'No schools registered'}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* System Health Panel */}
            <Card className="border-0 shadow-md">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-cairo flex items-center gap-2">
                  <HeartPulse className="h-4 w-4 text-emerald-500" />
                  {isRTL ? 'صحة النظام' : 'System Health'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <HealthIndicator
                  label={isRTL ? 'قاعدة البيانات' : 'Database'}
                  status={systemHealth?.database?.status || 'healthy'}
                  detail={systemHealth?.database?.status === 'healthy' ? (isRTL ? 'يعمل' : 'Running') : (isRTL ? 'خطأ' : 'Error')}
                />
                <HealthIndicator
                  label={isRTL ? 'واجهات API' : 'API Services'}
                  status={systemHealth?.api?.status || 'healthy'}
                  detail={systemHealth?.api?.uptime || '99.9%'}
                />
                {systemHealth?.engines && Object.entries(systemHealth.engines).map(([key, val]) => (
                  <HealthIndicator
                    key={key}
                    label={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                    status={val}
                    detail={val === 'active' ? (isRTL ? 'نشط' : 'Active') : val}
                  />
                ))}
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                  <p className="text-xs text-slate-400 flex items-center gap-1.5">
                    <Clock className="h-3 w-3" />
                    {isRTL ? 'آخر تحديث:' : 'Last updated:'} {new Date(s.last_updated || Date.now()).toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US')}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* AI Operations Panel */}
          <QuickAIOperationsPanel />

        </div>
      </div>

      <CreateSchoolWizard
        open={showAddSchoolWizard}
        onOpenChange={setShowAddSchoolWizard}
        onSuccess={() => { setShowAddSchoolWizard(false); fetchAllData(true); }}
        api={api}
        isRTL={isRTL}
      />
      {showCreateUserWizard && (
        <CreateUserWizard
          onClose={() => setShowCreateUserWizard(false)}
          onSuccess={() => { setShowCreateUserWizard(false); fetchAllData(true); }}
        />
      )}
    </Sidebar>
  );
};

export default AdminDashboard;
