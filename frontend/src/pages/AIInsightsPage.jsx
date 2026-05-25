import { useState, useEffect, useCallback, useMemo, useRef, lazy, Suspense } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
const StudentPerformanceDashboard = lazy(() =>
  import('../components/student-performance/StudentPerformanceDashboard'));
// 2026-05-19 — IT analytics panel merged in as the "التحليلات الرقمية"
// tab. Lazy so the recharts payload only loads when the tab is opened
// by an Independent Teacher. Self-contained fetching keeps the
// AI Insights and Analytics tabs from blocking each other's API calls.
const TeacherAnalyticsPanel = lazy(() =>
  import('./TeacherModule/TeacherAnalyticsPanel'));
const STUDENT_PERF_ROLES = ['school_admin', 'school_sub_admin', 'school_principal'];
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
  Sparkles, TrendingUp, AlertTriangle, CheckCircle,
  Users, GraduationCap, Target, Lightbulb, Sun, Moon, Globe,
  RefreshCw, Loader2, Clock, BarChart3, Zap, Shield,
  ArrowUpRight, ArrowDownRight, Activity, Star, Flame,
  Radar, HeartPulse, Cpu, BrainCircuit, ExternalLink,
  ChevronRight, ChevronLeft, Eye, TrendingDown, AlertCircle,
  BookOpen, ClipboardCheck, Award, UserCheck,
} from 'lucide-react';
import { Progress } from '../components/ui/progress';
import { AttendanceRadial } from '../components/dashboard/AttendancePanel';
import SectionErrorBoundary from '../components/SectionErrorBoundary';
import { CircularProgressRing } from '../components/ui/CircularProgressRing';
import { CalendarCheck, FileText, XCircle, Download, Filter } from 'lucide-react';
import { formatGregorianShort, formatGregorianFull } from '../utils/hijriDate';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
} from 'recharts';

const HAKIM_AVATAR = '/hakim-poses/detecting-patterns.png';

const NeuralBackground = () => (
  <div className="fixed inset-0 overflow-hidden pointer-events-none">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_30%,rgba(70,193,190,0.06),transparent_50%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_70%,rgba(97,80,144,0.05),transparent_50%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(28,61,116,0.03),transparent_60%)]" />
    <svg className="absolute inset-0 w-full h-full opacity-[0.025] dark:opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="neural-grid" width="60" height="60" patternUnits="userSpaceOnUse">
          <circle cx="30" cy="30" r="0.8" fill="currentColor" className="text-brand-navy" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#neural-grid)" />
    </svg>
  </div>
);

const AnimatedGauge = ({ score, size = 180, label, available = true }) => {
  const safeScore = available && Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = (size - 24) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  useEffect(() => {
    if (!available) {
      setAnimatedScore(0);
      return undefined;
    }
    let frame;
    const duration = 2000;
    const start = performance.now();
    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      setAnimatedScore(Math.round(safeScore * eased));
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [safeScore, available]);

  const glowColor = animatedScore >= 80 ? '#46C1BE' : animatedScore >= 60 ? '#615090' : '#1C3D74';
  const offset = available
    ? circumference - (animatedScore / 100) * circumference
    : circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={center} cy={center} r={radius} fill="none" stroke="currentColor" className="text-white/10" strokeWidth="12" />
        {available ? (
          <circle cx={center} cy={center} r={radius} fill="none" stroke="url(#gaugeGradMain)" strokeWidth="12" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" style={{ filter: `drop-shadow(0 0 8px ${glowColor}50)` }} />
        ) : (
          <circle cx={center} cy={center} r={radius} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="12" strokeLinecap="round" strokeDasharray="6 10" />
        )}
        <defs>
          <linearGradient id="gaugeGradMain" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#46C1BE" />
            <stop offset="50%" stopColor="#615090" />
            <stop offset="100%" stopColor="#46C1BE" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <BrainCircuit className={`h-6 w-6 mb-0.5 ${available ? 'text-brand-turquoise ai-brain-pulse' : 'text-white/40'}`} />
        {available ? (
          <span className="text-4xl font-bold font-cairo bg-gradient-to-br from-brand-turquoise via-white to-brand-purple bg-clip-text text-transparent">
            {animatedScore}
          </span>
        ) : (
          <span className="text-4xl font-bold font-cairo text-white/50" aria-label="insufficient-data">
            --
          </span>
        )}
        <span className={`text-[10px] font-tajawal ${available ? 'text-white' : 'text-white/40'}`}>{label}</span>
      </div>
    </div>
  );
};

const MiniGauge = ({ value, size = 44, color = '#1B93A4' }) => {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" className="text-muted/15" strokeWidth="4" />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-700" />
      </svg>
      <span className="absolute text-[10px] font-bold font-cairo" style={{ color }}>{value}%</span>
    </div>
  );
};

const VisualMetricCard = ({ icon: Icon, value, label, subLabel, gradient, accentColor, onClick, delay = 0 }) => {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  return (
    <button
      onClick={onClick}
      className={`group relative overflow-hidden rounded-2xl border border-border/40 bg-card p-5 hover:shadow-xl hover:shadow-brand-turquoise/8 hover:-translate-y-0.5 transition-all duration-500 text-start w-full ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      <div className={`absolute top-0 ${document.dir === 'rtl' ? 'right-0' : 'left-0'} w-1 h-full bg-gradient-to-b ${gradient} rounded-full opacity-60 group-hover:opacity-100 transition-opacity`} />
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-[11px] text-muted-foreground font-tajawal mb-1.5 uppercase tracking-wider">{label}</p>
          <p className="text-3xl font-bold font-cairo text-foreground leading-none">{value}</p>
          {subLabel && <p className="text-[10px] text-muted-foreground/70 font-tajawal mt-1.5">{subLabel}</p>}
        </div>
        <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-md group-hover:scale-110 transition-transform duration-300`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
    </button>
  );
};

const AlertsTimeline = ({ alerts, isRTL, onNavigate, isTeacher = false }) => {
  const { t } = useTranslation();
  const typeConfig = {
    warning: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50 dark:bg-amber-950/30', line: 'bg-amber-300', accent: 'border-amber-200' },
    info: { icon: Lightbulb, color: 'text-sky-500', bg: 'bg-sky-50 dark:bg-sky-950/30', line: 'bg-sky-300', accent: 'border-sky-200' },
    success: { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-950/30', line: 'bg-emerald-300', accent: 'border-emerald-200' },
  };

  const alertRouteMap = {
    attendance: '/admin/attendance',
    academic: '/admin/students',
    behavior: '/admin/students',
    teacher: '/admin/teacher-attendance',
    schedule: '/school/schedule',
    performance: '/principal/ai-insights',
  };

  // Strip admin-only alerts (e.g. "scheduling — assign teachers to
  // sessions") when the viewer is a teacher.
  const visibleAlerts = isTeacher
    ? alerts.filter(a => a?.category !== 'scheduling' && !isAdminOnlyItem(a))
    : alerts;

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-md shadow-amber-500/20">
              <Zap className="h-4.5 w-4.5 text-white" />
            </div>
            {t('smartAlerts')}
          </CardTitle>
          {visibleAlerts.length > 0 && (
            <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-0 font-cairo text-xs px-2.5">{visibleAlerts.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {visibleAlerts.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100/80 dark:bg-emerald-900/30 flex items-center justify-center mb-4 shadow-sm">
              <CheckCircle className="h-8 w-8 text-emerald-500" />
            </div>
            <p className="text-sm font-cairo font-bold text-foreground">
              {isTeacher ? t('teacherClassesRunningSmoothly') : t('everythingRunningSmoothly')}
            </p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1 max-w-[200px]">{t('hakimWillNotifyYouWhenPatternsAreDetected')}</p>
          </div>
        ) : (
          <div className="relative space-y-0">
            <div className="absolute start-[19px] top-4 bottom-4 w-[2px] bg-gradient-to-b from-amber-200 via-sky-200 to-emerald-200 dark:from-amber-800/40 dark:via-sky-800/40 dark:to-emerald-800/40 rounded-full" />
            {visibleAlerts.slice(0, 6).map((alert, i) => {
              const config = typeConfig[alert.type] || typeConfig.info;
              const AlertIcon = config.icon;
              const alertRoute = alert.route || alertRouteMap[alert.category] || null;

              return (
                <div key={alert.id || i} className="relative flex gap-4 pb-4 last:pb-0 group">
                  <div className={`relative z-10 w-10 h-10 rounded-xl ${config.bg} flex items-center justify-center shrink-0 border ${config.accent} group-hover:scale-105 transition-transform duration-200`}>
                    <AlertIcon className={`h-4.5 w-4.5 ${config.color}`} />
                  </div>
                  <div className="flex-1 min-w-0 pt-0.5">
                    <p className="text-sm font-cairo font-semibold text-foreground leading-snug">
                      {isRTL ? alert.title?.ar : alert.title?.en}
                    </p>
                    <p className="text-xs text-muted-foreground font-tajawal mt-1 line-clamp-2">
                      {isRTL ? alert.description?.ar : alert.description?.en}
                    </p>
                    <div className="flex items-center gap-3 mt-2">
                      <span className="text-[10px] text-muted-foreground/50 flex items-center gap-1 font-tajawal">
                        <Clock className="h-3 w-3" />
                        {new Date(alert.timestamp).toLocaleString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' })}
                      </span>
                      {alertRoute && (
                        <button onClick={() => onNavigate(alertRoute)}
                          className="flex items-center gap-1 text-[11px] font-cairo font-bold text-brand-turquoise hover:text-brand-purple transition-colors">
                          <ExternalLink className="h-3 w-3" />
                          {t('go')}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const PredictionsPanel = ({ predictions, isRTL }) => {
  const { t } = useTranslation();
  const impactColors = {
    positive: { ring: '#10B981', bg: 'bg-emerald-50 dark:bg-emerald-950/30', text: 'text-emerald-600', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400' },
    medium: { ring: '#F59E0B', bg: 'bg-amber-50 dark:bg-amber-950/30', text: 'text-amber-600', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400' },
    high: { ring: '#EF4444', bg: 'bg-red-50 dark:bg-red-950/30', text: 'text-red-600', badge: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400' },
  };

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md shadow-violet-500/20">
              <Radar className="h-4.5 w-4.5 text-white" />
            </div>
            {t('predictionsForecasts')}
          </CardTitle>
          {predictions.length > 0 && (
            <Badge className="bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400 border-0 font-cairo text-xs px-2.5">{predictions.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {predictions.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <div className="w-16 h-16 rounded-2xl bg-violet-100/60 dark:bg-violet-900/20 flex items-center justify-center mb-4 shadow-sm">
              <TrendingUp className="h-8 w-8 text-violet-400/60" />
            </div>
            <p className="text-sm font-cairo font-bold text-foreground">{t('noPredictionsYet')}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1">{t('hakimNeedsMoreData')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {predictions.map((pred, i) => {
              const colors = impactColors[pred.impact] || impactColors.medium;
              const confidence = pred.confidence || 0;
              const reasonText = pred.reason
                ? (isRTL ? pred.reason.ar || pred.reason : pred.reason.en || pred.reason)
                : (t('basedOnDataPatternAnalysis'));

              return (
                <div key={pred.id || i} className={`p-4 rounded-xl border border-border/50 ${colors.bg} transition-all duration-300 hover:shadow-md hover:-translate-y-0.5`}>
                  <div className="flex items-start gap-3">
                    <MiniGauge value={confidence} color={colors.ring} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className={`text-[10px] ${colors.badge} border-0`}>
                          {pred.impact === 'positive' ? (t('positive')) :
                            pred.impact === 'high' ? (t('needsAction')) :
                              (t('moderate'))}
                        </Badge>
                      </div>
                      <h4 className="font-cairo font-bold text-foreground text-sm leading-snug">
                        {isRTL ? pred.title?.ar : pred.title?.en}
                      </h4>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1 line-clamp-2">
                        {isRTL ? pred.description?.ar : pred.description?.en}
                      </p>
                      <div className="mt-2.5 flex items-start gap-1.5 p-2 rounded-lg bg-background/60 border border-border/30">
                        <BrainCircuit className="h-3 w-3 text-brand-purple flex-shrink-0 mt-0.5" />
                        <p className="text-[10px] text-muted-foreground font-tajawal leading-relaxed">{reasonText}</p>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Recommendations or alerts whose category is clearly an admin-level
// concern (HR, staffing, hiring, school-wide scheduling) must never be
// shown to a teacher — they can't act on them and the wording is wrong
// for their role. The backend now suppresses these for teachers, but we
// also filter on the client as defense-in-depth so a stale cache or a
// new admin-only category added server-side can't leak through.
const ADMIN_ONLY_CATEGORY_PATTERNS = [
  /human\s*resources?/i,
  /staffing/i,
  /hiring/i,
  /school[-\s]?wide/i,
  /الموارد\s*البشرية/,
  /الكادر/,
  /التوظيف/,
  /scheduling/i,
  /الجدول/,
];

const TEACHER_ROLES = ['teacher', 'independent_teacher'];

// An item is admin-only if either:
//   1. The backend explicitly marks it with an `audience` array that does
//      NOT include any teacher role (this is the authoritative signal — the
//      backend now ships role-aware wording variants per Task #155), OR
//   2. As a defence-in-depth fallback for items missing audience metadata,
//      the legacy category/title regex catches obvious admin-level cards.
const isAdminOnlyItem = (item) => {
  const audience = item?.audience;
  if (Array.isArray(audience) && audience.length > 0) {
    return !audience.some(r => TEACHER_ROLES.includes(r));
  }
  const cat = item?.category;
  const candidates = [
    typeof cat === 'string' ? cat : null,
    cat?.ar,
    cat?.en,
    item?.title?.ar,
    item?.title?.en,
  ].filter(Boolean);
  return candidates.some(text =>
    ADMIN_ONLY_CATEGORY_PATTERNS.some(rx => rx.test(text))
  );
};

const RecommendationsPanel = ({ recommendations, isRTL, isTeacher = false }) => {
  const { t } = useTranslation();
  const priorityConfig = {
    high: { color: 'from-red-500 to-rose-500', accent: 'bg-red-500', label: t('high2'), icon: Flame },
    medium: { color: 'from-amber-500 to-yellow-500', accent: 'bg-amber-500', label: t('medium2'), icon: Star },
    low: { color: 'from-emerald-500 to-teal-500', accent: 'bg-emerald-500', label: t('low2'), icon: Lightbulb },
  };

  // Strip admin-only entries when a teacher is viewing, so the UI only
  // surfaces pedagogical guidance the teacher can actually act on.
  const visibleRecommendations = isTeacher
    ? recommendations.filter(rec => !isAdminOnlyItem(rec))
    : recommendations;

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-500/20">
              <Target className="h-4.5 w-4.5 text-white" />
            </div>
            {t('smartRecommendations')}
          </CardTitle>
          {visibleRecommendations.length > 0 && (
            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 font-cairo text-xs px-2.5">{visibleRecommendations.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {visibleRecommendations.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100/60 dark:bg-emerald-900/20 flex items-center justify-center mb-4 shadow-sm">
              <Lightbulb className="h-8 w-8 text-emerald-400/60" />
            </div>
            <p className="text-sm font-cairo font-bold text-foreground">
              {isTeacher ? t('teacherClassesRunningSmoothly') : t('noRecommendationsYet')}
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {visibleRecommendations.map((rec, i) => {
              const config = priorityConfig[rec.priority] || priorityConfig.medium;
              const PIcon = config.icon;
              return (
                <div key={rec.id || i} className="group relative flex items-start gap-3 p-4 rounded-xl border border-border/50 hover:border-brand-turquoise/30 bg-card hover:shadow-md hover:-translate-y-0.5 transition-all duration-300">
                  <div className={`absolute top-0 ${isRTL ? 'right-0' : 'left-0'} w-1 h-full rounded-full ${config.accent}`} />
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${config.color} flex items-center justify-center shrink-0 shadow-md`}>
                    <PIcon className="h-4.5 w-4.5 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="secondary" className="text-[10px] font-tajawal">
                        {isRTL ? rec.category?.ar : rec.category?.en}
                      </Badge>
                      <Badge className={`text-[10px] bg-gradient-to-r ${config.color} text-white border-0`}>
                        {config.label}
                      </Badge>
                    </div>
                    <h4 className="font-cairo font-bold text-foreground text-sm leading-snug">
                      {isRTL ? rec.title?.ar : rec.title?.en}
                    </h4>
                    <p className="text-xs text-muted-foreground font-tajawal mt-1 line-clamp-2">
                      {isRTL ? rec.description?.ar : rec.description?.en}
                    </p>
                    <div className="flex items-center gap-2 mt-2.5">
                      <div className="flex-1 h-2 bg-muted/20 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-brand-turquoise to-brand-purple rounded-full transition-all duration-700" style={{ width: `${Math.min(100, rec.expected_impact * 4)}%` }} />
                      </div>
                      <span className="text-[10px] font-bold text-brand-turquoise font-cairo">+{rec.expected_impact}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const RiskStudentsPanel = ({ students, isRTL, onNavigate }) => {
  const { t } = useTranslation();
  const getRiskConfig = (level) => {
    if (level >= 70) return { color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30', ring: '#EF4444', badge: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400', label: t('highRisk') };
    if (level >= 50) return { color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30', ring: '#F59E0B', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400', label: t('moderate') };
    return { color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30', ring: '#10B981', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400', label: t('lowRisk') };
  };

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-rose-500 to-red-500 flex items-center justify-center shadow-md shadow-red-500/20">
              <HeartPulse className="h-4.5 w-4.5 text-white" />
            </div>
            {t('studentRiskRadar')}
          </CardTitle>
          {students.length > 0 && (
            <div className="flex items-center gap-1.5">
              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border-0 font-cairo text-[10px]">
                {students.filter(s => s.risk_level >= 70).length} {t('highRiskShort')}
              </Badge>
              <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-0 font-cairo text-[10px]">
                {students.filter(s => s.risk_level >= 50 && s.risk_level < 70).length} {t('modShort')}
              </Badge>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {students.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100/80 dark:bg-emerald-900/30 flex items-center justify-center mb-4 shadow-sm">
              <Shield className="h-8 w-8 text-emerald-500" />
            </div>
            <p className="text-sm font-cairo font-bold text-foreground">{t('noAtriskStudents')}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1">{t('allStudentsPerformingWell')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {students.sort((a, b) => b.risk_level - a.risk_level).map((student, i) => {
              const config = getRiskConfig(student.risk_level);
              return (
                <button key={student.id || i} onClick={() => onNavigate(student)}
                  className="w-full group flex items-center gap-3 p-3 rounded-xl border border-border/50 hover:border-red-200 hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 text-start">
                  <div className={`relative w-10 h-10 rounded-full ${config.bg} flex items-center justify-center shrink-0`}>
                    <GraduationCap className={`h-4 w-4 ${config.color}`} />
                    {student.risk_level >= 70 && (
                      <span className="absolute -top-0.5 -end-0.5 w-2.5 h-2.5 bg-red-500 rounded-full animate-ping" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="font-cairo font-bold text-sm truncate group-hover:text-brand-turquoise transition-colors">{student.name}</p>
                      <Badge variant="secondary" className="text-[10px] shrink-0">{student.grade}</Badge>
                    </div>
                    {student.factors && (
                      <div className="flex flex-wrap gap-1">
                        {student.factors.slice(0, 3).map((f, fi) => (
                          <span key={fi} className="text-[9px] px-1.5 py-0.5 rounded-full bg-muted/50 text-muted-foreground font-tajawal">{f}</span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <MiniGauge value={student.risk_level} size={40} color={config.ring} />
                    <div className="w-6 h-6 rounded-lg bg-muted/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      {isRTL ? <ChevronLeft className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    </div>
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

const HealthRing = ({ label, value, color, icon: Icon, isRTL }) => {
  const radius = 32;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative">
        <svg width="80" height="80" className="transform -rotate-90">
          <circle cx="40" cy="40" r={radius} fill="none" stroke="currentColor" className="text-muted/10" strokeWidth="6" />
          <circle cx="40" cy="40" r={radius} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <Icon className="h-5 w-5" style={{ color }} />
        </div>
      </div>
      <div className="text-center">
        <p className="text-lg font-bold font-cairo text-white">{value}%</p>
        <p className="text-[10px] text-white/70 font-tajawal">{label}</p>
      </div>
    </div>
  );
};

const TeacherMonitoringSection = ({ isRTL, api, isTeacher = false, userKey = '' }) => {
  const { t } = useTranslation();
  const [monitorData, setMonitorData] = useState(null);
  const [monitorLoading, setMonitorLoading] = useState(true);
  // Request-version guard: each userKey change bumps the active request id.
  // Async responses from a previous identity are dropped instead of
  // overwriting state for the current user (Task #154 / M1 race fix).
  const monitorReqIdRef = useRef(0);

  useEffect(() => {
    // Defense-in-depth: teachers have no access to admin-only report endpoints.
    // The primary guard is at the render site (!isTeacher), but we bail here too
    // in case the component is accidentally mounted for a teacher role in the future.
    if (isTeacher) return;

    // Reset on auth identity change so the previous user's numbers do not
    // flash before the new fetch resolves (Task #154 / M1).
    setMonitorData(null);
    monitorReqIdRef.current += 1;
    const myReqId = monitorReqIdRef.current;
    const fetchMonitorData = async () => {
      setMonitorLoading(true);
      try {
        const [overviewRes, behaviorRes, gradesRes] = await Promise.all([
          api.get('/reports/school/overview').catch(() => ({ data: null })),
          isTeacher ? Promise.resolve({ data: null }) : api.get('/reports/school/behavior').catch(() => ({ data: null })),
          api.get('/reports/school/grades').catch(() => ({ data: null })),
        ]);
        if (myReqId !== monitorReqIdRef.current) return;

        const overview = overviewRes.data || {};
        const behavior = isTeacher ? {} : (behaviorRes.data || {});
        const grades = Array.isArray(gradesRes.data) ? gradesRes.data : [];

        const totalSubjects = grades.length;
        const avgPassRate = totalSubjects > 0 ? Math.round(grades.reduce((sum, g) => sum + (g.pass_rate || 0), 0) / totalSubjects) : 0;
        const totalAttendance = (overview.attendance?.present || 0) + (overview.attendance?.absent || 0) + (overview.attendance?.late || 0);
        const participationRate = totalAttendance > 0 ? Math.round(((overview.attendance?.present || 0) / totalAttendance) * 100) : 0;

        setMonitorData({
          totalStudents: overview.total_students || 0,
          attendanceRate: overview.attendance_rate || 0,
          attendance: overview.attendance || { present: 0, absent: 0, late: 0 },
          avgGrade: overview.avg_grade || 0,
          positiveBehavior: behavior.stats?.positive || 0,
          negativeBehavior: behavior.stats?.negative || 0,
          warningBehavior: behavior.stats?.warning || 0,
          totalBehavior: behavior.stats?.total || 0,
          skillsAssessed: totalSubjects,
          avgSkillScore: avgPassRate,
          participationRate: participationRate,
        });
      } catch (err) {
        console.error('Teacher monitoring data error:', err);
      } finally {
        if (myReqId === monitorReqIdRef.current) setMonitorLoading(false);
      }
    };
    fetchMonitorData();
  }, [api, userKey]);

  if (monitorLoading) {
    return (
      <Card className="card-nassaq">
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" />
        </CardContent>
      </Card>
    );
  }

  if (!monitorData) return null;

  const d = monitorData;
  const behaviorPositiveRate = d.totalBehavior > 0 ? Math.round((d.positiveBehavior / d.totalBehavior) * 100) : 0;

  const monitorCards = [
    { label: t('attendanceLabel'), value: `${d.attendanceRate}%`, icon: ClipboardCheck, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30', detail: isRTL ? `${d.attendance.present} حاضر | ${d.attendance.absent} غائب` : `${d.attendance.present} present | ${d.attendance.absent} absent` },
    { label: t('avgGrade'), value: d.avgGrade || '-', icon: Award, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30', detail: t('avgCourseworkGrade') },
    { label: t('positiveBehavior'), value: d.positiveBehavior, icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30', detail: `${behaviorPositiveRate}% ${t('ofTotalBehavior')}` },
    { label: t('negativeBehavior'), value: d.negativeBehavior, icon: TrendingDown, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30', detail: `${d.warningBehavior} ${t('warnings')}` },
    { label: isTeacher ? t('myStudents') : t('totalStudentsLabel'), value: d.totalStudents, icon: Users, color: 'text-brand-navy', bg: 'bg-blue-50 dark:bg-blue-950/30', detail: isTeacher ? t('enrolledInYourClasses') : t('enrolledInSchool') },
    { label: t('subjectsAssessed'), value: d.skillsAssessed, icon: Star, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30', detail: `${t('passRate')}: ${d.avgSkillScore}%` },
    { label: t('participation'), value: `${d.participationRate}%`, icon: Activity, color: 'text-cyan-600', bg: 'bg-cyan-50 dark:bg-cyan-950/30', detail: t('studentEngagement') },
    { label: t('behaviorRecords'), value: d.totalBehavior, icon: Eye, color: 'text-violet-600', bg: 'bg-violet-50 dark:bg-violet-950/30', detail: t('totalBehaviorMonitoring') },
  ];

  return (
    <Card className="card-nassaq overflow-hidden">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-turquoise to-teal-600 flex items-center justify-center shadow-md shadow-brand-turquoise/20">
              <UserCheck className="h-4.5 w-4.5 text-white" />
            </div>
            {isTeacher ? t('myTeachingPerformanceSummary') : t('teacherMonitoringInsights')}
          </CardTitle>
          <Badge className="bg-brand-turquoise/10 text-brand-turquoise border-0 font-cairo text-xs px-2.5">
            {t('liveData')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {monitorCards.map((card, i) => {
            const CardIcon = card.icon;
            return (
              <div key={i} className={`p-4 rounded-xl ${card.bg} border border-border/30`}>
                <div className="flex items-center gap-2 mb-2">
                  <CardIcon className={`h-4 w-4 ${card.color}`} />
                  <span className="text-[11px] font-tajawal text-muted-foreground">{card.label}</span>
                </div>
                <p className={`text-2xl font-bold font-cairo ${card.color}`}>{card.value}</p>
                <p className="text-[10px] text-muted-foreground font-tajawal mt-1">{card.detail}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-4 space-y-3">
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-muted-foreground text-xs font-tajawal">{t('overallAttendanceRate')}</span>
              <span className="font-bold font-cairo text-xs">{d.attendanceRate}%</span>
            </div>
            <Progress value={d.attendanceRate} className="h-2" />
          </div>
          <div>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-muted-foreground text-xs font-tajawal">{t('positiveBehaviorRate')}</span>
              <span className="font-bold font-cairo text-xs">{behaviorPositiveRate}%</span>
            </div>
            <Progress value={behaviorPositiveRate} className="h-2" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

const StaffAttendanceKpis = ({ todayCounts, staffHeadcount, isRTL, t }) => {
  const present = todayCounts?.present || 0;
  const absent = todayCounts?.absent || 0;
  const excused = todayCounts?.excused || 0;
  const late = todayCounts?.late || 0;
  const recorded = present + absent + excused + late;
  const rate = recorded > 0 ? Math.round(((present + late) / recorded) * 100) : 0;

  const kpis = [
    {
      label: isRTL ? 'إجمالي الكوادر' : 'Total Staff',
      value: staffHeadcount,
      icon: Users,
      color: 'text-brand-navy',
      bg: 'bg-brand-navy/10',
    },
    {
      label: t('present') || (isRTL ? 'حاضر' : 'Present'),
      value: present,
      icon: CheckCircle,
      color: 'text-emerald-600',
      bg: 'bg-emerald-500/10',
    },
    {
      label: t('absent') || (isRTL ? 'غائب' : 'Absent'),
      value: absent,
      icon: XCircle,
      color: 'text-red-600',
      bg: 'bg-red-500/10',
    },
    {
      label: isRTL ? 'بعذر/متأخر' : 'Excused/Late',
      value: excused + late,
      icon: FileText,
      color: 'text-blue-600',
      bg: 'bg-blue-500/10',
    },
  ];

  return (
    <Card className="card-nassaq border-brand-turquoise/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center">
              <CalendarCheck className="h-5 w-5 text-brand-turquoise" />
            </div>
            <div>
              <CardTitle className="font-cairo text-base">
                {t('staffAttendance2') || (isRTL ? 'حضور الكوادر' : 'Staff Attendance')}
              </CardTitle>
              <p className="text-xs text-muted-foreground font-tajawal">
                {isRTL ? 'لمحة سريعة لحضور المعلمين والإداريين' : 'Quick overview of teacher & admin attendance'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <CircularProgressRing
              value={rate}
              size={72}
              stroke={7}
              color="#1B93A4"
            />
            <div>
              <p className="text-[11px] text-muted-foreground font-tajawal">
                {t('attendanceRate2') || (isRTL ? 'نسبة الحضور' : 'Attendance Rate')}
              </p>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {kpis.map((kpi) => {
            const Icon = kpi.icon;
            return (
              <div
                key={kpi.label}
                className="flex items-center gap-3 p-3 rounded-xl border border-border/50 bg-background/50"
                data-testid={`ai-attendance-kpi-${kpi.label}`}
              >
                <div className={`w-10 h-10 rounded-xl ${kpi.bg} flex items-center justify-center shrink-0`}>
                  <Icon className={`h-5 w-5 ${kpi.color}`} />
                </div>
                <div className="min-w-0">
                  <p className="text-lg font-bold font-cairo text-foreground leading-none">
                    {kpi.value}
                  </p>
                  <p className="text-[11px] text-muted-foreground font-tajawal mt-1 truncate">
                    {kpi.label}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

const REPORT_RANGE_OPTIONS = [
  { value: 7, ar: 'آخر ٧ أيام', en: 'Last 7 days' },
  { value: 14, ar: 'آخر ١٤ يوماً', en: 'Last 14 days' },
  { value: 30, ar: 'آخر ٣٠ يوماً', en: 'Last 30 days' },
  { value: 0, ar: 'الكل', en: 'All' },
];

const AttendanceReportsSection = ({
  report,
  isRTL,
  t,
  title,
  subjectLabel,
  exportFilenamePrefix = 'attendance-report',
  testIdPrefix = 'ai-attendance',
  iconBg = 'bg-brand-purple/10',
  iconColor = 'text-brand-purple',
}) => {
  const [rangeDays, setRangeDays] = useState(14);
  const locale = isRTL ? 'ar' : 'en';

  const parseDate = (value) => {
    if (!value) return null;
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? null : d;
  };

  const allDaily = useMemo(() => report?.daily || [], [report]);

  const filtered = useMemo(() => {
    if (!rangeDays) return allDaily;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - rangeDays);
    return allDaily.filter((row) => {
      const d = parseDate(row.date);
      return d ? d >= cutoff : true;
    });
  }, [allDaily, rangeDays]);

  const chartData = useMemo(
    () =>
      [...filtered]
        .sort((a, b) => (a.date > b.date ? 1 : -1))
        .map((row) => {
          const d = parseDate(row.date);
          return {
            date: row.date,
            dateShort: d ? formatGregorianShort(d, locale) : '—',
            dateFull: d ? formatGregorianFull(d, locale) : '—',
            present: row.present || 0,
            absent: row.absent || 0,
            excused: row.excused || 0,
            late: row.late || 0,
            rate: row.attendance_rate || 0,
          };
        }),
    [filtered, locale]
  );

  const windowTotals = useMemo(() => {
    const totals = filtered.reduce(
      (acc, row) => {
        acc.present += row.present || 0;
        acc.absent += row.absent || 0;
        acc.excused += row.excused || 0;
        acc.late += row.late || 0;
        acc.total += row.total || 0;
        return acc;
      },
      { present: 0, absent: 0, excused: 0, late: 0, total: 0 }
    );
    const denom = totals.total;
    totals.rate = denom > 0
      ? Math.round(((totals.present + totals.late) / denom) * 1000) / 10
      : 0;
    return totals;
  }, [filtered]);

  const handleExportCsv = () => {
    const headerLabels = isRTL
      ? ['التاريخ', 'اليوم', 'حاضر', 'غائب', 'بعذر', 'متأخر', 'الإجمالي', 'نسبة الحضور %']
      : ['Date', 'Day', 'Present', 'Absent', 'Excused', 'Late', 'Total', 'Attendance Rate %'];

    const escape = (val) => {
      const s = String(val ?? '');
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };

    const rows = [...filtered].sort((a, b) => (a.date > b.date ? 1 : -1));
    const csv = [
      headerLabels.map(escape).join(','),
      ...rows.map((r) => {
        const d = parseDate(r.date);
        const isoDay = d ? d.toISOString().slice(0, 10) : '—';
        const readable = d ? formatGregorianFull(d, locale) : '—';
        return [
          isoDay,
          readable,
          r.present || 0,
          r.absent || 0,
          r.excused || 0,
          r.late || 0,
          r.total || 0,
          r.attendance_rate || 0,
        ].map(escape).join(',');
      }),
    ].join('\r\n');

    const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const rangeTag = rangeDays ? `${rangeDays}d` : 'all';
    a.download = `${exportFilenamePrefix}-${rangeTag}-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const labelFor = (opt) => (isRTL ? opt.ar : opt.en);

  return (
    <Card className="card-nassaq" data-testid={`${testIdPrefix}-reports`}>
      <CardHeader>
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center`}>
              <BarChart3 className={`h-5 w-5 ${iconColor}`} />
            </div>
            <div>
              <CardTitle className="font-cairo text-base">
                {title}
              </CardTitle>
              <p className="text-xs text-muted-foreground font-tajawal">
                {isRTL
                  ? `${filtered.length} يوم • نسبة حضور ${subjectLabel || ''} ${windowTotals.rate}%`
                  : `${filtered.length} days • ${windowTotals.rate}% ${subjectLabel || ''} attendance rate`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1 p-1 bg-muted/40 rounded-xl">
              <Filter className="h-3.5 w-3.5 text-muted-foreground mx-1" />
              {REPORT_RANGE_OPTIONS.map((opt) => {
                const active = rangeDays === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setRangeDays(opt.value)}
                    className={`px-2.5 py-1 text-xs rounded-lg font-tajawal transition-colors ${
                      active
                        ? 'bg-white dark:bg-gray-800 text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                    data-testid={`${testIdPrefix}-range-${opt.value}`}
                  >
                    {labelFor(opt)}
                  </button>
                );
              })}
            </div>

            <Button
              variant="outline"
              size="sm"
              className="rounded-xl"
              onClick={handleExportCsv}
              disabled={filtered.length === 0}
              data-testid={`${testIdPrefix}-export-csv-btn`}
            >
              <Download className="h-3.5 w-3.5 me-1.5" />
              {isRTL ? 'تصدير CSV' : 'Export CSV'}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground font-tajawal">
            {isRTL ? 'لا توجد تقارير ضمن هذه الفترة' : 'No reports in this period'}
          </div>
        ) : (
          <>
            <div className="w-full" style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-muted/20" />
                  <XAxis
                    dataKey="dateShort"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                    minTickGap={16}
                    reversed={isRTL}
                  />
                  <YAxis yAxisId="left" tick={{ fontSize: 11 }} allowDecimals={false} orientation={isRTL ? 'right' : 'left'} />
                  <YAxis
                    yAxisId="right"
                    orientation={isRTL ? 'left' : 'right'}
                    tick={{ fontSize: 11 }}
                    domain={[0, 100]}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <RechartsTooltip
                    contentStyle={{ borderRadius: 12, fontSize: 12 }}
                    labelFormatter={(_, payload) => {
                      const item = payload && payload[0] && payload[0].payload;
                      return item?.dateFull || '—';
                    }}
                    formatter={(value, name) => {
                      if (name === 'rate') return [`${value}%`, isRTL ? 'نسبة الحضور' : 'Rate'];
                      const labels = {
                        present: isRTL ? 'حاضر' : 'Present',
                        absent: isRTL ? 'غائب' : 'Absent',
                        excused: isRTL ? 'بعذر' : 'Excused',
                        late: isRTL ? 'متأخر' : 'Late',
                      };
                      return [value, labels[name] || name];
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 12 }}
                    formatter={(name) => {
                      const labels = {
                        present: isRTL ? 'حاضر' : 'Present',
                        absent: isRTL ? 'غائب' : 'Absent',
                        excused: isRTL ? 'بعذر' : 'Excused',
                        late: isRTL ? 'متأخر' : 'Late',
                        rate: isRTL ? 'نسبة الحضور' : 'Attendance Rate',
                      };
                      return labels[name] || name;
                    }}
                  />
                  <Bar yAxisId="left" dataKey="present" stackId="a" fill="#10B981" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="left" dataKey="absent" stackId="a" fill="#EF4444" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="left" dataKey="excused" stackId="a" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                  <Bar yAxisId="left" dataKey="late" stackId="a" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="right" type="monotone" dataKey="rate" stroke="#1B93A4" strokeWidth={2} dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm" dir={isRTL ? 'rtl' : 'ltr'}>
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground font-tajawal">
                    <th className="text-start py-2 px-3 font-medium">
                      {isRTL ? 'التاريخ' : 'Date'}
                    </th>
                    <th className="text-center py-2 px-3 font-medium">
                      {t('present') || (isRTL ? 'حاضر' : 'Present')}
                    </th>
                    <th className="text-center py-2 px-3 font-medium">
                      {t('absent') || (isRTL ? 'غائب' : 'Absent')}
                    </th>
                    <th className="text-center py-2 px-3 font-medium">
                      {t('excused2') || (isRTL ? 'بعذر' : 'Excused')}
                    </th>
                    <th className="text-center py-2 px-3 font-medium">
                      {isRTL ? 'متأخر' : 'Late'}
                    </th>
                    <th className="text-end py-2 px-3 font-medium">
                      {t('attendanceRate2') || (isRTL ? 'نسبة الحضور' : 'Rate')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => (
                    <tr
                      key={row.date}
                      className="border-b border-border/40 hover:bg-muted/30 transition-colors"
                    >
                      <td className="py-2 px-3 font-tajawal whitespace-nowrap">
                        {(() => {
                          const d = parseDate(row.date);
                          return d ? formatGregorianFull(d, locale) : '—';
                        })()}
                      </td>
                      <td className="text-center py-2 px-3">
                        <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                          {row.present}
                        </Badge>
                      </td>
                      <td className="text-center py-2 px-3">
                        <Badge variant="secondary" className="bg-red-500/10 text-red-700 dark:text-red-400">
                          {row.absent}
                        </Badge>
                      </td>
                      <td className="text-center py-2 px-3">
                        <Badge variant="secondary" className="bg-blue-500/10 text-blue-700 dark:text-blue-400">
                          {row.excused}
                        </Badge>
                      </td>
                      <td className="text-center py-2 px-3">
                        <Badge variant="secondary" className="bg-amber-500/10 text-amber-700 dark:text-amber-400">
                          {row.late || 0}
                        </Badge>
                      </td>
                      <td className="text-end py-2 px-3">
                        <span className="font-semibold font-cairo text-brand-turquoise">
                          {row.attendance_rate}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export const AIInsightsPage = () => {
  const { t } = useTranslation();
  const { api, user } = useAuth();
  const canSeeStudentPerf = STUDENT_PERF_ROLES.includes(user?.role);
  // 2026-05-19 — IT users see the embedded analytics tab. Gated on
  // role only (the panel's own backend calls re-check the
  // `analytics.read_own_workspace` permission per request).
  const isIndependentTeacher = user?.role === 'independent_teacher';
  // 2026-05-19 — Treat Independent Teachers as teacher-scoped on this
  // page. Otherwise admitting them to /ai-insights would flip them
  // into the admin/principal branch, which fires `/teachers`,
  // `/teacher-attendance`, and `/attendance/report/summary` calls
  // they have no business making and renders staff-admin sections
  // that don't apply to a single-workspace teacher. The dedicated
  // analytics tab below remains the only IT-specific surface.
  const isTeacher = user?.role === 'teacher' || user?.role === 'independent_teacher';
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const navigate = useNavigate();
  // 2026-05-19 — Deep-link support: `?tab=analytics` (used by the
  // /teacher/analytics legacy redirect) opens the new analytics tab
  // directly so old bookmarks land in the right place.
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') === 'analytics' && isIndependentTeacher
    ? 'analytics'
    : 'insights';
  const [activeTab, setActiveTab] = useState(initialTab);
  const handleTabChange = useCallback((next) => {
    setActiveTab(next);
    const params = new URLSearchParams(searchParams);
    if (next === 'analytics') params.set('tab', 'analytics');
    else params.delete('tab');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      @keyframes aiBrainPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.08); }
      }
      @keyframes aiFloat {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-6px); }
      }
      @keyframes aiGlow {
        0% { box-shadow: 0 0 20px rgba(70,193,190,0.2), 0 0 40px rgba(97,80,144,0.1); }
        100% { box-shadow: 0 0 30px rgba(70,193,190,0.35), 0 0 60px rgba(97,80,144,0.2); }
      }
      @keyframes slideInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
      }
      @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
      }
      @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
      }
      .ai-brain-pulse { animation: aiBrainPulse 3s ease-in-out infinite; }
      .ai-float { animation: aiFloat 4s ease-in-out infinite; }
      .ai-glow { animation: aiGlow 3s ease-in-out infinite alternate; }
      .ai-slide-in { animation: slideInUp 0.6s ease-out forwards; }
      .ai-fade-in { animation: fadeIn 0.8s ease-out forwards; }
      @media (prefers-reduced-motion: reduce) {
        .ai-brain-pulse, .ai-float, .ai-glow, .ai-slide-in, .ai-fade-in { animation: none !important; }
      }
    `;
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, []);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [insights, setInsights] = useState({ overall_score: 0, trend: 'up', trend_value: 0, score_available: false, metrics: {} });
  const [predictions, setPredictions] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [studentRisks, setStudentRisks] = useState([]);
  const [attendanceData, setAttendanceData] = useState(null);
  const [attendanceReport, setAttendanceReport] = useState(null);
  const [studentAttendanceReport, setStudentAttendanceReport] = useState(null);
  const [staffHeadcount, setStaffHeadcount] = useState(0);
  const [todayAttendanceCounts, setTodayAttendanceCounts] = useState({ present: 0, absent: 0, excused: 0, late: 0 });

  // Auth identity key — when the signed-in user, role or tenant changes
  // (logout/login, role switch, impersonation), reset the data regions to
  // skeleton state so the previous user's analytics never flash on screen.
  // The page header, filters and surrounding shell stay mounted (Task #154 / M1).
  const userKey = `${user?.id || ''}|${user?.role || ''}|${user?.tenant_id || ''}`;

  // Request-version guard: incremented on every userKey change. Async
  // responses from a previous identity are dropped instead of overwriting
  // state for the current user (Task #154 / M1 race fix).
  const fetchReqIdRef = useRef(0);

  // First-mount marker: the full-screen splash is allowed ONLY for the
  // very first load of the page. On subsequent identity changes the page
  // shell, header and filters must remain mounted — only the data
  // regions reset to their empty/skeleton state (Task #154 / M1 spec).
  const firstLoadRef = useRef(true);

  const fetchData = useCallback(async () => {
    const myReqId = fetchReqIdRef.current;
    try {
      const todayDate = new Date().toISOString().split('T')[0];
      const [overviewRes, predictionsRes, recommendationsRes, alertsRes, risksRes, dashboardRes, attendanceReportRes, studentAttendanceReportRes, teachersRes, adminsRes, todayAttendanceRes] = await Promise.all([
        api.get('/ai/insights/overview').catch(() => ({ data: null })),
        api.get('/ai/insights/predictions').catch(() => ({ data: [] })),
        api.get('/ai/insights/recommendations').catch(() => ({ data: [] })),
        api.get('/ai/insights/alerts').catch(() => ({ data: [] })),
        api.get('/ai/insights/at-risk-students').catch(() => ({ data: [] })),
        api.get('/school/dashboard').catch(() => ({ data: null })),
        isTeacher ? Promise.resolve({ data: null }) : api.get('/teacher-attendance/report/summary').catch(() => ({ data: null })),
        isTeacher ? Promise.resolve({ data: null }) : api.get('/attendance/report/summary').catch(() => ({ data: null })),
        isTeacher ? Promise.resolve({ data: [] }) : api.get('/teachers').catch(() => ({ data: [] })),
        isTeacher ? Promise.resolve({ data: [] }) : api.get('/teacher-attendance/school-admins').catch(() => ({ data: [] })),
        isTeacher ? Promise.resolve({ data: [] }) : api.get(`/teacher-attendance?date=${todayDate}`).catch(() => ({ data: [] })),
      ]);

      if (myReqId !== fetchReqIdRef.current) return;

      setAttendanceData(dashboardRes?.data?.attendance || null);
      setAttendanceReport(attendanceReportRes?.data || null);
      setStudentAttendanceReport(studentAttendanceReportRes?.data || null);
      const teacherCount = Array.isArray(teachersRes?.data) ? teachersRes.data.length : 0;
      const adminCount = Array.isArray(adminsRes?.data) ? adminsRes.data.length : 0;
      setStaffHeadcount(teacherCount + adminCount);

      const todayRecords = Array.isArray(todayAttendanceRes?.data) ? todayAttendanceRes.data : [];
      setTodayAttendanceCounts({
        present: todayRecords.filter((r) => r.status === 'present').length,
        absent: todayRecords.filter((r) => r.status === 'absent').length,
        excused: todayRecords.filter((r) => r.status === 'excused').length,
        late: todayRecords.filter((r) => r.status === 'late').length,
      });

      if (overviewRes.data) {
        setInsights({
          overall_score: overviewRes.data.overall_score || 0,
          trend: overviewRes.data.trend || 'stable',
          trend_value: overviewRes.data.trend_value || 0,
          score_available: overviewRes.data.score_available === true,
          last_updated: overviewRes.data.last_updated || new Date().toISOString(),
          metrics: overviewRes.data.metrics || {},
        });
      }

      setPredictions(Array.isArray(predictionsRes.data) ? predictionsRes.data : []);
      setRecommendations(Array.isArray(recommendationsRes.data) ? recommendationsRes.data : []);
      setAlerts(Array.isArray(alertsRes.data) ? alertsRes.data : []);
      setStudentRisks(Array.isArray(risksRes.data) ? risksRes.data : []);
    } catch (error) {
      console.error('Failed to load AI insights:', error);
    } finally {
      if (myReqId === fetchReqIdRef.current) setLoading(false);
    }
  }, [api, isTeacher]);

  // Reset every data region back to its empty/skeleton state whenever the
  // signed-in user identity changes, BEFORE the next fetch runs. The page
  // header, filters and shell stay mounted (Task #154 / M1).
  useEffect(() => {
    fetchReqIdRef.current += 1;
    setInsights({ overall_score: 0, trend: 'up', trend_value: 0, score_available: false, metrics: {} });
    setPredictions([]);
    setRecommendations([]);
    setAlerts([]);
    setStudentRisks([]);
    setAttendanceData(null);
    setAttendanceReport(null);
    setStudentAttendanceReport(null);
    setStaffHeadcount(0);
    setTodayAttendanceCounts({ present: 0, absent: 0, excused: 0, late: 0 });
    if (firstLoadRef.current) {
      // First ever mount: full-screen splash is acceptable.
      setLoading(true);
      firstLoadRef.current = false;
    } else {
      // Identity switch: keep shell/header/filters mounted, render the
      // data regions in their (already-cleared) empty state until the
      // new fetch arrives. No full-page takeover.
      setLoading(false);
    }
    fetchData();
  }, [userKey, fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    toast.success(t('aiInsightsRefreshed'));
    setRefreshing(false);
  };

  const handleStudentNavigate = (student) => {
    navigate('/admin/users-management', { state: { openStudent: student.id, studentName: student.name } });
  };

  const handleAlertNavigate = (route) => {
    navigate(route);
  };

  const { metrics } = insights;

  const totalIssues = alerts.length + studentRisks.filter(s => s.risk_level >= 70).length;
  const highRiskCount = studentRisks.filter(s => s.risk_level >= 70).length;

  if (loading) {
    return (
      <Sidebar>
        <div className="flex flex-col items-center justify-center min-h-screen gap-6">
          <div className="relative">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-brand-turquoise/20 to-brand-purple/20 flex items-center justify-center ai-glow">
              <BrainCircuit className="h-12 w-12 text-brand-turquoise ai-brain-pulse" />
            </div>
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
              {[0, 1, 2].map(i => (
                <div key={i} className="w-2 h-2 rounded-full bg-brand-turquoise animate-bounce" style={{ animationDelay: `${i * 200}ms` }} />
              ))}
            </div>
          </div>
          <div className="text-center">
            <p className="font-cairo font-bold text-foreground">{t('hakimIsAnalyzingData')}</p>
            <p className="text-xs text-muted-foreground font-tajawal mt-1">{t('extractingPatternsAndInsights')}</p>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-background relative" data-testid="ai-insights-page">
        <NeuralBackground />

        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-3">
          <div className="flex items-center justify-between max-w-[1600px] mx-auto">
            <div className="flex items-center gap-3">
              <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-brand-turquoise to-brand-purple flex items-center justify-center ai-glow shadow-lg">
                <BrainCircuit className="h-5.5 w-5.5 text-white" />
              </div>
              <div>
                <h1 className="font-cairo text-xl font-bold text-foreground flex items-center gap-2">
                  {t('aiSmartInsights')}
                  <Sparkles className="h-4 w-4 text-brand-gold" />
                </h1>
                <p className="text-xs text-muted-foreground font-tajawal">
                  {t('deepAnalyticsAiPredictions')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={handleRefresh} disabled={refreshing} className="rounded-xl gap-2 h-9">
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                <span className="hidden sm:inline text-xs">{t('refresh')}</span>
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl h-9 w-9">
                <Globe className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl h-9 w-9">
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="relative z-10 p-6 max-w-[1600px] mx-auto space-y-6">
          <Tabs value={activeTab} onValueChange={handleTabChange} dir={isRTL ? 'rtl' : 'ltr'}>
            <TabsList>
              <TabsTrigger value="insights">{t('aiInsightsTabLabel')}</TabsTrigger>
              {/* 2026-05-19 — IT-only "التحليلات الرقمية" tab. Hosts the
                  analytics panel relocated from /teacher/analytics. */}
              {isIndependentTeacher && (
                <TabsTrigger value="analytics" data-testid="ai-insights-analytics-tab">
                  {t('digitalAnalyticsTabLabel')}
                </TabsTrigger>
              )}
              {canSeeStudentPerf && (
                <TabsTrigger value="student-performance">{t('studentPerformance')}</TabsTrigger>
              )}
            </TabsList>
            <TabsContent value="insights" className="space-y-6 mt-6">

          {/* ══════ HERO — PERFORMANCE SCORE ══════ */}
          <div className="ai-slide-in">
            <div className="relative overflow-hidden rounded-3xl shadow-2xl">
              <div className="absolute inset-0 bg-gradient-to-br from-brand-navy via-brand-navy-dark to-brand-purple/90" />
              <div className="absolute inset-0 nassaq-pattern opacity-[0.07]" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_10%_90%,rgba(70,193,190,0.2),transparent_50%)]" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_90%_10%,rgba(97,80,144,0.2),transparent_50%)]" />

              <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="absolute w-1 h-1 bg-white/15 rounded-full ai-float" style={{ left: `${12 + i * 15}%`, top: `${20 + (i % 3) * 25}%`, animationDelay: `${i * 0.6}s`, animationDuration: `${3 + i * 0.5}s` }} />
                ))}
              </div>

              <div className="relative z-10 p-8 lg:p-10">
                <div className="flex flex-col lg:flex-row items-center gap-8">

                  <div className="flex-1 text-center lg:text-start">
                    <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/10 backdrop-blur-md border border-white/15 mb-4">
                      <div className="w-7 h-7 rounded-full overflow-hidden flex-shrink-0">
                        <img src={HAKIM_AVATAR} alt="حكيم" className="hakim-img w-full h-full object-contain" />
                      </div>
                      <span className="text-[11px] font-tajawal text-white font-medium">
                        {t('poweredByHakimAi')}
                      </span>
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    </div>

                    <h2 className="text-2xl lg:text-3xl font-bold font-cairo text-white mb-2 leading-tight">
                      {t('smartPerformanceIndex')}
                    </h2>
                    <p className="text-sm text-white font-tajawal max-w-md leading-relaxed">
                      {insights.score_available
                        ? (isTeacher
                            ? t('comprehensiveTeachingPerformanceBasedOnAiAnalysis')
                            : t('comprehensiveSchoolPerformanceBasedOnAiAnalysis'))
                        : t('smartPerformanceIndexInsufficientData')}
                    </p>

                    {insights.score_available && (
                      <div className="flex items-center gap-3 mt-5 justify-center lg:justify-start">
                        <div className={`flex items-center gap-2 px-4 py-2 rounded-xl backdrop-blur-sm ${
                          insights.trend === 'up'
                            ? 'bg-emerald-500/15 border border-emerald-400/25'
                            : 'bg-red-500/15 border border-red-400/25'
                        }`}>
                          {insights.trend === 'up'
                            ? <ArrowUpRight className="h-4 w-4 text-emerald-400" />
                            : <ArrowDownRight className="h-4 w-4 text-red-400" />
                          }
                          <span className={`text-base font-bold font-cairo ${insights.trend === 'up' ? 'text-emerald-400' : 'text-red-400'}`}>
                            {insights.trend_value}%
                          </span>
                          <span className="text-[10px] text-white font-tajawal">
                            {t('vsLastMonth')}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="ai-float shrink-0">
                    <AnimatedGauge
                      score={insights.overall_score}
                      size={200}
                      label={t('outOf100')}
                      available={insights.score_available}
                    />
                  </div>

                  <div className="hidden lg:flex flex-col gap-4">
                    <HealthRing label={t('attendance2')} value={metrics.attendance_rate || 0} color="#46C1BE" icon={Activity} isRTL={isRTL} />
                    <HealthRing label={t('engagement')} value={metrics.engagement_rate || metrics.attendance_rate || 0} color="#615090" icon={Users} isRTL={isRTL} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ══════ QUICK STATS ROW ══════ */}
          <div className={`grid grid-cols-2 ${isTeacher ? 'lg:grid-cols-3' : 'lg:grid-cols-4'} gap-4`}>
            <VisualMetricCard
              icon={Users}
              label={isTeacher ? t('myStudents') : t('totalStudents')}
              value={metrics.total_students || 0}
              subLabel={isTeacher ? t('enrolledInYourClasses') : t('enrolled')}
              gradient="from-brand-turquoise to-teal-600"
              onClick={() => !isTeacher && navigate('/admin/users-management')}
              delay={100}
            />
            {!isTeacher && (
              <VisualMetricCard
                icon={GraduationCap}
                label={t('totalTeachers')}
                value={metrics.total_teachers || 0}
                subLabel={`${metrics.student_teacher_ratio || 0}:1 ${t('ratio')}`}
                gradient="from-brand-purple to-violet-600"
                onClick={() => navigate('/admin/users-management?filter=teachers')}
                delay={200}
              />
            )}
            <VisualMetricCard
              icon={Activity}
              label={t('attendanceRate')}
              value={`${metrics.attendance_rate || 0}%`}
              subLabel={t('today2')}
              gradient="from-brand-navy-light to-brand-navy"
              onClick={() => navigate('/admin/attendance')}
              delay={300}
            />
            <VisualMetricCard
              icon={Shield}
              label={t('atriskStudents')}
              value={studentRisks.length}
              subLabel={highRiskCount > 0 ? `${highRiskCount} ${t('critical')}` : (t('safe'))}
              gradient="from-rose-500 to-red-600"
              onClick={() => document.getElementById('risks-section')?.scrollIntoView({ behavior: 'smooth' })}
              delay={400}
            />
          </div>

          {/* ══════ STATUS BANNER ══════ */}
          <div className="ai-fade-in">
            <div className={`flex items-center gap-3 px-5 py-3 rounded-2xl border backdrop-blur-sm ${
              totalIssues > 0
                ? 'bg-amber-50/80 dark:bg-amber-950/20 border-amber-200/50 dark:border-amber-800/30'
                : 'bg-emerald-50/80 dark:bg-emerald-950/20 border-emerald-200/50 dark:border-emerald-800/30'
            }`}>
              {totalIssues > 0 ? (
                <>
                  <div className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                  </div>
                  <p className="text-sm font-tajawal text-amber-800 dark:text-amber-300 flex-1">
                    {isRTL
                      ? `يوجد ${totalIssues} عنصر يحتاج انتباهك — ${alerts.length} تنبيه و ${highRiskCount} طالب في خطر مرتفع`
                      : `${totalIssues} items need your attention — ${alerts.length} alerts and ${highRiskCount} high-risk students`}
                  </p>
                  <Button variant="outline" size="sm" onClick={() => document.getElementById('alerts-section')?.scrollIntoView({ behavior: 'smooth' })} className="rounded-lg text-xs border-amber-300 text-amber-700 hover:bg-amber-100 hover:text-amber-700 focus-visible:text-amber-700">
                    {t('viewDetails')}
                  </Button>
                </>
              ) : (
                <>
                  <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                  </div>
                  <p className="text-sm font-tajawal text-emerald-800 dark:text-emerald-300 flex-1">
                    {t('allIndicatorsNormalNoIssuesNeedImmediateAttention')}
                  </p>
                </>
              )}
            </div>
          </div>

          {/* ══════ ATTENDANCE PANEL (لوحة الحضور) ══════ */}
          {!isTeacher && (
            <div className="ai-slide-in">
              <SectionErrorBoundary name="AttendanceRadial" isRTL={isRTL} fallbackMessage={t('failedToLoadAttendanceData')}>
                <AttendanceRadial data={attendanceData} isRTL={isRTL} />
              </SectionErrorBoundary>
            </div>
          )}

          {!isTeacher && attendanceReport && (
            <div className="ai-slide-in space-y-6">
              <SectionErrorBoundary name="StaffAttendanceKPIs" isRTL={isRTL} fallbackMessage={t('failedToLoadAttendanceData')}>
                <StaffAttendanceKpis todayCounts={todayAttendanceCounts} staffHeadcount={staffHeadcount} isRTL={isRTL} t={t} />
              </SectionErrorBoundary>

              <SectionErrorBoundary name="StaffAttendanceReports" isRTL={isRTL} fallbackMessage={t('failedToLoadAttendanceData')}>
                <AttendanceReportsSection
                  report={attendanceReport}
                  isRTL={isRTL}
                  t={t}
                  title={isRTL ? 'تقارير حضور المعلمين والإداريين' : 'Teacher & Admin Attendance Reports'}
                  subjectLabel={isRTL ? 'الكوادر' : 'staff'}
                  exportFilenamePrefix="staff-attendance-report"
                  testIdPrefix="ai-staff-attendance"
                  iconBg="bg-brand-purple/10"
                  iconColor="text-brand-purple"
                />
              </SectionErrorBoundary>
            </div>
          )}

          {!isTeacher && studentAttendanceReport && (
            <div className="ai-slide-in space-y-6">
              <SectionErrorBoundary name="StudentAttendanceReports" isRTL={isRTL} fallbackMessage={t('failedToLoadAttendanceData')}>
                <AttendanceReportsSection
                  report={studentAttendanceReport}
                  isRTL={isRTL}
                  t={t}
                  title={isRTL ? 'تقارير حضور الطلاب' : 'Student Attendance Reports'}
                  subjectLabel={isRTL ? 'الطلاب' : 'student'}
                  exportFilenamePrefix="student-attendance-report"
                  testIdPrefix="ai-student-attendance"
                  iconBg="bg-brand-turquoise/10"
                  iconColor="text-brand-turquoise"
                />
              </SectionErrorBoundary>
            </div>
          )}

          {/* ══════ TEACHER MONITORING INSIGHTS ══════ */}
          {!isTeacher && (
            <div className="ai-slide-in">
              <TeacherMonitoringSection isRTL={isRTL} api={api} isTeacher={isTeacher} userKey={userKey} />
            </div>
          )}

          {/* ══════ ALL SECTIONS ══════ */}
          <div className="space-y-6">
            <div className="space-y-6 ai-slide-in">
              <div id="alerts-section" className="grid lg:grid-cols-2 gap-6">
                <AlertsTimeline alerts={alerts} isRTL={isRTL} onNavigate={handleAlertNavigate} isTeacher={isTeacher} />
                <div id="risks-section">
                  <RiskStudentsPanel students={studentRisks} isRTL={isRTL} onNavigate={handleStudentNavigate} />
                </div>
              </div>
              <div className="grid lg:grid-cols-2 gap-6">
                <RecommendationsPanel recommendations={recommendations} isRTL={isRTL} isTeacher={isTeacher} />
                <PredictionsPanel predictions={predictions} isRTL={isRTL} />
              </div>
            </div>

            <div className="pb-4 ai-fade-in">
              <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground/40 font-tajawal">
                <Cpu className="h-3 w-3" />
                <span>
                  {t('lastUpdated')}
                  {insights.last_updated
                    ? new Date(insights.last_updated).toLocaleString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' })
                    : (t('na'))}
                </span>
                <span className="text-brand-turquoise">•</span>
                <span>{t('poweredByHakimEngine')}</span>
              </div>
            </div>
          </div>
            </TabsContent>
            {/* 2026-05-19 — IT analytics tab. The panel owns its own
                state + fetch hooks, so opening this tab never blocks
                the AI insights tab's data and vice versa. */}
            {isIndependentTeacher && (
              <TabsContent value="analytics" className="mt-6" data-testid="ai-insights-analytics-content">
                <Suspense fallback={<div className="p-6 text-center">{t('loading')}</div>}>
                  <TeacherAnalyticsPanel />
                </Suspense>
              </TabsContent>
            )}
            {canSeeStudentPerf && (
              <TabsContent value="student-performance" className="mt-6">
                <Suspense fallback={<div className="p-6 text-center">{t('loading')}</div>}>
                  <StudentPerformanceDashboard />
                </Suspense>
              </TabsContent>
            )}
          </Tabs>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};

export default AIInsightsPage;
