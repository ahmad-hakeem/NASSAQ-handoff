import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
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
  BookOpen, LayoutGrid,
} from 'lucide-react';

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

const AnimatedGauge = ({ score, size = 180, label }) => {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = (size - 24) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  useEffect(() => {
    let frame;
    const duration = 2000;
    const start = performance.now();
    const animate = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 4);
      setAnimatedScore(Math.round(score * eased));
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const glowColor = animatedScore >= 80 ? '#46C1BE' : animatedScore >= 60 ? '#615090' : '#1C3D74';
  const offset = circumference - (animatedScore / 100) * circumference;

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle cx={center} cy={center} r={radius} fill="none" stroke="currentColor" className="text-white/10" strokeWidth="12" />
        <circle cx={center} cy={center} r={radius} fill="none" stroke="url(#gaugeGradMain)" strokeWidth="12" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" style={{ filter: `drop-shadow(0 0 8px ${glowColor}50)` }} />
        <defs>
          <linearGradient id="gaugeGradMain" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#46C1BE" />
            <stop offset="50%" stopColor="#615090" />
            <stop offset="100%" stopColor="#46C1BE" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <BrainCircuit className="h-6 w-6 text-brand-turquoise mb-0.5 ai-brain-pulse" />
        <span className="text-4xl font-bold font-cairo bg-gradient-to-br from-brand-turquoise via-white to-brand-purple bg-clip-text text-transparent">
          {animatedScore}
        </span>
        <span className="text-[10px] text-white font-tajawal">{label}</span>
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
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
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

const AlertsTimeline = ({ alerts, isRTL, onNavigate }) => {
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

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-md shadow-amber-500/20">
              <Zap className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? 'التنبيهات الذكية' : 'Smart Alerts'}
          </CardTitle>
          {alerts.length > 0 && (
            <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-0 font-cairo text-xs px-2.5">{alerts.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100/80 dark:bg-emerald-900/30 flex items-center justify-center mb-4 shadow-sm">
              <CheckCircle className="h-8 w-8 text-emerald-500" />
            </div>
            <p className="text-sm font-cairo font-bold text-foreground">{isRTL ? 'كل شيء يسير بسلاسة' : 'Everything running smoothly'}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1 max-w-[200px]">{isRTL ? 'سيقوم حكيم بإعلامك عند اكتشاف أنماط مهمة' : 'Hakim will notify you when patterns are detected'}</p>
          </div>
        ) : (
          <div className="relative space-y-0">
            <div className="absolute start-[19px] top-4 bottom-4 w-[2px] bg-gradient-to-b from-amber-200 via-sky-200 to-emerald-200 dark:from-amber-800/40 dark:via-sky-800/40 dark:to-emerald-800/40 rounded-full" />
            {alerts.slice(0, 6).map((alert, i) => {
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
                          {isRTL ? 'انتقل' : 'Go'}
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
            {isRTL ? 'التوقعات والتنبؤات' : 'Predictions & Forecasts'}
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
            <p className="text-sm font-cairo font-bold text-foreground">{isRTL ? 'لا توجد توقعات حالياً' : 'No predictions yet'}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1">{isRTL ? 'يحتاج حكيم لمزيد من البيانات' : 'Hakim needs more data'}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {predictions.map((pred, i) => {
              const colors = impactColors[pred.impact] || impactColors.medium;
              const confidence = pred.confidence || 0;
              const reasonText = pred.reason
                ? (isRTL ? pred.reason.ar || pred.reason : pred.reason.en || pred.reason)
                : (isRTL ? 'بناءً على تحليل أنماط البيانات' : 'Based on data pattern analysis');

              return (
                <div key={pred.id || i} className={`p-4 rounded-xl border border-border/50 ${colors.bg} transition-all duration-300 hover:shadow-md hover:-translate-y-0.5`}>
                  <div className="flex items-start gap-3">
                    <MiniGauge value={confidence} color={colors.ring} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className={`text-[10px] ${colors.badge} border-0`}>
                          {pred.impact === 'positive' ? (isRTL ? 'إيجابي' : 'Positive') :
                            pred.impact === 'high' ? (isRTL ? 'يتطلب تدخل' : 'Needs Action') :
                              (isRTL ? 'متوسط' : 'Moderate')}
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

const RecommendationsPanel = ({ recommendations, isRTL }) => {
  const priorityConfig = {
    high: { color: 'from-red-500 to-rose-500', accent: 'bg-red-500', label: isRTL ? 'عالية' : 'High', icon: Flame },
    medium: { color: 'from-amber-500 to-yellow-500', accent: 'bg-amber-500', label: isRTL ? 'متوسطة' : 'Medium', icon: Star },
    low: { color: 'from-emerald-500 to-teal-500', accent: 'bg-emerald-500', label: isRTL ? 'منخفضة' : 'Low', icon: Lightbulb },
  };

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-500/20">
              <Target className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? 'توصيات ذكية' : 'Smart Recommendations'}
          </CardTitle>
          {recommendations.length > 0 && (
            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 font-cairo text-xs px-2.5">{recommendations.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {recommendations.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-100/60 dark:bg-emerald-900/20 flex items-center justify-center mb-4 shadow-sm">
              <Lightbulb className="h-8 w-8 text-emerald-400/60" />
            </div>
            <p className="text-sm font-cairo font-bold text-foreground">{isRTL ? 'لا توجد توصيات حالياً' : 'No recommendations yet'}</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {recommendations.map((rec, i) => {
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
  const getRiskConfig = (level) => {
    if (level >= 70) return { color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30', ring: '#EF4444', badge: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400', label: isRTL ? 'خطر مرتفع' : 'High Risk' };
    if (level >= 50) return { color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30', ring: '#F59E0B', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400', label: isRTL ? 'خطر متوسط' : 'Moderate' };
    return { color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30', ring: '#10B981', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400', label: isRTL ? 'خطر منخفض' : 'Low Risk' };
  };

  return (
    <Card className="card-nassaq overflow-hidden h-full">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2.5 font-cairo text-base">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-rose-500 to-red-500 flex items-center justify-center shadow-md shadow-red-500/20">
              <HeartPulse className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? 'رادار المخاطر الطلابية' : 'Student Risk Radar'}
          </CardTitle>
          {students.length > 0 && (
            <div className="flex items-center gap-1.5">
              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border-0 font-cairo text-[10px]">
                {students.filter(s => s.risk_level >= 70).length} {isRTL ? 'مرتفع' : 'high'}
              </Badge>
              <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-0 font-cairo text-[10px]">
                {students.filter(s => s.risk_level >= 50 && s.risk_level < 70).length} {isRTL ? 'متوسط' : 'mod'}
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
            <p className="text-sm font-cairo font-bold text-foreground">{isRTL ? 'لا يوجد طلاب في خطر' : 'No at-risk students'}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1">{isRTL ? 'جميع الطلاب يسيرون بشكل جيد' : 'All students performing well'}</p>
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
        <p className="text-lg font-bold font-cairo text-foreground">{value}%</p>
        <p className="text-[10px] text-muted-foreground font-tajawal">{label}</p>
      </div>
    </div>
  );
};

export const AIInsightsPage = () => {
  const { api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const navigate = useNavigate();

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
  const [activeTab, setActiveTab] = useState('overview');

  const [insights, setInsights] = useState({ overall_score: 0, trend: 'up', trend_value: 0, metrics: {} });
  const [predictions, setPredictions] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [studentRisks, setStudentRisks] = useState([]);

  const fetchData = useCallback(async () => {
    try {
      const [overviewRes, predictionsRes, recommendationsRes, alertsRes, risksRes] = await Promise.all([
        api.get('/ai/insights/overview').catch(() => ({ data: null })),
        api.get('/ai/insights/predictions').catch(() => ({ data: [] })),
        api.get('/ai/insights/recommendations').catch(() => ({ data: [] })),
        api.get('/ai/insights/alerts').catch(() => ({ data: [] })),
        api.get('/ai/insights/at-risk-students').catch(() => ({ data: [] })),
      ]);

      if (overviewRes.data) {
        setInsights({
          overall_score: overviewRes.data.overall_score || 0,
          trend: overviewRes.data.trend || 'stable',
          trend_value: overviewRes.data.trend_value || 0,
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
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    toast.success(isRTL ? 'تم تحديث رؤى الذكاء الاصطناعي' : 'AI insights refreshed');
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
            <p className="font-cairo font-bold text-foreground">{isRTL ? 'حكيم يحلل البيانات...' : 'Hakim is analyzing data...'}</p>
            <p className="text-xs text-muted-foreground font-tajawal mt-1">{isRTL ? 'جاري استخراج الأنماط والرؤى' : 'Extracting patterns and insights'}</p>
          </div>
        </div>
      </Sidebar>
    );
  }

  const tabs = [
    { id: 'overview', label: isRTL ? 'نظرة عامة' : 'Overview', icon: LayoutGrid, count: null },
    { id: 'alerts', label: isRTL ? 'التنبيهات' : 'Alerts', icon: Zap, count: alerts.length },
    { id: 'predictions', label: isRTL ? 'التوقعات' : 'Predictions', icon: TrendingUp, count: predictions.length },
    { id: 'recommendations', label: isRTL ? 'التوصيات' : 'Recommendations', icon: Target, count: recommendations.length },
    { id: 'risks', label: isRTL ? 'المخاطر' : 'Risks', icon: Shield, count: studentRisks.length },
  ];

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
                  {isRTL ? 'رؤى الذكاء الاصطناعي' : 'AI Smart Insights'}
                  <Sparkles className="h-4 w-4 text-brand-gold" />
                </h1>
                <p className="text-xs text-muted-foreground font-tajawal">
                  {isRTL ? 'تحليلات عميقة وتوقعات ذكية' : 'Deep analytics & AI predictions'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={handleRefresh} disabled={refreshing} className="rounded-xl gap-2 h-9">
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                <span className="hidden sm:inline text-xs">{isRTL ? 'تحديث' : 'Refresh'}</span>
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
                        {isRTL ? 'تحليل مدعوم بحكيم AI' : 'Powered by Hakim AI'}
                      </span>
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    </div>

                    <h2 className="text-2xl lg:text-3xl font-bold font-cairo text-white mb-2 leading-tight">
                      {isRTL ? 'مؤشر الأداء الذكي' : 'Smart Performance Index'}
                    </h2>
                    <p className="text-sm text-white font-tajawal max-w-md leading-relaxed">
                      {isRTL
                        ? 'تقييم شامل لأداء المدرسة بناءً على تحليل الذكاء الاصطناعي'
                        : 'Comprehensive school performance based on AI analysis'}
                    </p>

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
                          {isRTL ? 'مقارنة بالشهر الماضي' : 'vs last month'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="ai-float shrink-0">
                    <AnimatedGauge
                      score={insights.overall_score}
                      size={200}
                      label={isRTL ? 'من ١٠٠' : 'out of 100'}
                    />
                  </div>

                  <div className="hidden lg:flex flex-col gap-4">
                    <HealthRing label={isRTL ? 'الحضور' : 'Attendance'} value={metrics.attendance_rate || 0} color="#46C1BE" icon={Activity} isRTL={isRTL} />
                    <HealthRing label={isRTL ? 'المشاركة' : 'Engagement'} value={metrics.engagement_rate || metrics.attendance_rate || 0} color="#615090" icon={Users} isRTL={isRTL} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ══════ QUICK STATS ROW ══════ */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <VisualMetricCard
              icon={Users}
              label={isRTL ? 'إجمالي الطلاب' : 'Total Students'}
              value={metrics.total_students || 0}
              subLabel={isRTL ? 'مسجّل في النظام' : 'Enrolled'}
              gradient="from-brand-turquoise to-teal-600"
              onClick={() => navigate('/admin/users-management')}
              delay={100}
            />
            <VisualMetricCard
              icon={GraduationCap}
              label={isRTL ? 'إجمالي المعلمين' : 'Total Teachers'}
              value={metrics.total_teachers || 0}
              subLabel={`${metrics.student_teacher_ratio || 0}:1 ${isRTL ? 'طالب/معلم' : 'ratio'}`}
              gradient="from-brand-purple to-violet-600"
              onClick={() => navigate('/admin/users-management?filter=teachers')}
              delay={200}
            />
            <VisualMetricCard
              icon={Activity}
              label={isRTL ? 'نسبة الحضور' : 'Attendance Rate'}
              value={`${metrics.attendance_rate || 0}%`}
              subLabel={isRTL ? 'اليوم' : 'Today'}
              gradient="from-brand-navy-light to-brand-navy"
              onClick={() => navigate('/admin/attendance')}
              delay={300}
            />
            <VisualMetricCard
              icon={Shield}
              label={isRTL ? 'طلاب في خطر' : 'At-Risk Students'}
              value={studentRisks.length}
              subLabel={highRiskCount > 0 ? `${highRiskCount} ${isRTL ? 'خطر مرتفع' : 'critical'}` : (isRTL ? 'آمن' : 'Safe')}
              gradient="from-rose-500 to-red-600"
              onClick={() => setActiveTab('risks')}
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
                  <Button variant="outline" size="sm" onClick={() => setActiveTab('alerts')} className="rounded-lg text-xs border-amber-300 text-amber-700 hover:bg-amber-100">
                    {isRTL ? 'عرض التفاصيل' : 'View Details'}
                  </Button>
                </>
              ) : (
                <>
                  <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center">
                    <CheckCircle className="h-4 w-4 text-emerald-600" />
                  </div>
                  <p className="text-sm font-tajawal text-emerald-800 dark:text-emerald-300 flex-1">
                    {isRTL ? 'جميع المؤشرات طبيعية — لا توجد مشكلات تحتاج تدخل فوري' : 'All indicators normal — no issues need immediate attention'}
                  </p>
                </>
              )}
            </div>
          </div>

          {/* ══════ NAVIGATION TABS ══════ */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none border-b border-border/30">
            {tabs.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative flex items-center gap-2 px-4 py-2.5 text-sm font-tajawal whitespace-nowrap transition-all duration-300 rounded-t-xl ${
                    isActive
                      ? 'text-brand-turquoise font-bold'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                  {tab.count > 0 && (
                    <span className={`min-w-[20px] h-5 rounded-full text-[10px] flex items-center justify-center font-bold px-1.5 ${
                      isActive ? 'bg-brand-turquoise/15 text-brand-turquoise' : 'bg-muted text-muted-foreground'
                    }`}>
                      {tab.count}
                    </span>
                  )}
                  {isActive && (
                    <span className="absolute bottom-0 inset-x-2 h-0.5 rounded-full bg-gradient-to-r from-brand-turquoise to-brand-purple" />
                  )}
                </button>
              );
            })}
          </div>

          {/* ══════ CONTENT ══════ */}
          <div className="space-y-6">

            {activeTab === 'overview' && (
              <div className="space-y-6 ai-slide-in">
                <div className="grid lg:grid-cols-2 gap-6">
                  <AlertsTimeline alerts={alerts} isRTL={isRTL} onNavigate={handleAlertNavigate} />
                  <RiskStudentsPanel students={studentRisks} isRTL={isRTL} onNavigate={handleStudentNavigate} />
                </div>
                <div className="grid lg:grid-cols-2 gap-6">
                  <RecommendationsPanel recommendations={recommendations} isRTL={isRTL} />
                  <PredictionsPanel predictions={predictions} isRTL={isRTL} />
                </div>
              </div>
            )}

            {activeTab === 'alerts' && (
              <div className="ai-slide-in max-w-3xl mx-auto">
                <AlertsTimeline alerts={alerts} isRTL={isRTL} onNavigate={handleAlertNavigate} />
              </div>
            )}

            {activeTab === 'predictions' && (
              <div className="ai-slide-in max-w-3xl mx-auto">
                <PredictionsPanel predictions={predictions} isRTL={isRTL} />
              </div>
            )}

            {activeTab === 'recommendations' && (
              <div className="ai-slide-in max-w-3xl mx-auto">
                <svg width="0" height="0">
                  <defs>
                    <linearGradient id="impactGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="#46C1BE" />
                      <stop offset="100%" stopColor="#615090" />
                    </linearGradient>
                  </defs>
                </svg>
                <RecommendationsPanel recommendations={recommendations} isRTL={isRTL} />
              </div>
            )}

            {activeTab === 'risks' && (
              <div className="ai-slide-in max-w-3xl mx-auto">
                <RiskStudentsPanel students={studentRisks} isRTL={isRTL} onNavigate={handleStudentNavigate} />
              </div>
            )}

            <div className="pb-4 ai-fade-in">
              <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground/40 font-tajawal">
                <Cpu className="h-3 w-3" />
                <span>
                  {isRTL ? 'آخر تحديث: ' : 'Last updated: '}
                  {insights.last_updated
                    ? new Date(insights.last_updated).toLocaleString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' })
                    : (isRTL ? 'غير متاح' : 'N/A')}
                </span>
                <span className="text-brand-turquoise">•</span>
                <span>{isRTL ? 'مدعوم بمحرك حكيم' : 'Powered by Hakim Engine'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};

export default AIInsightsPage;
