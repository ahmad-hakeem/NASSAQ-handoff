import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
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
  Sparkles,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Users,
  GraduationCap,
  Target,
  Lightbulb,
  Sun,
  Moon,
  Globe,
  RefreshCw,
  Loader2,
  Clock,
  BarChart3,
  Zap,
  Shield,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Star,
  Flame,
  Layers,
  Radar,
  HeartPulse,
  Cpu,
  BrainCircuit,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  Eye,
  MessageCircle,
  Info,
  BookOpen,
  Send,
  TrendingDown,
  AlertCircle,
  FileText,
  Percent,
  ArrowRight,
  CircleDot,
  LayoutGrid,
} from 'lucide-react';

const HAKIM_AVATAR = '/hakim-poses/detecting-patterns.png';

const NeuralBackground = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_30%,rgba(70,193,190,0.08),transparent_50%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_70%,rgba(97,80,144,0.06),transparent_50%)]" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(28,61,116,0.04),transparent_60%)]" />
    <svg className="absolute inset-0 w-full h-full opacity-[0.03] dark:opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="neural-grid" width="60" height="60" patternUnits="userSpaceOnUse">
          <circle cx="30" cy="30" r="1" fill="currentColor" className="text-brand-navy" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#neural-grid)" />
    </svg>
  </div>
);

const AnimatedGauge = ({ score, size = 200, label }) => {
  const [animatedScore, setAnimatedScore] = useState(0);
  const radius = (size - 30) / 2;
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
        <circle cx={center} cy={center} r={radius} fill="none" stroke="currentColor" className="text-white/10" strokeWidth="14" />
        <circle cx={center} cy={center} r={radius} fill="none" stroke="url(#gaugeGrad)" strokeWidth="14" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-1000 ease-out" style={{ filter: `drop-shadow(0 0 10px ${glowColor}50)` }} />
        <circle cx={center} cy={center} r={radius - 16} fill="none" stroke="currentColor" className="text-white/5" strokeWidth="2" strokeDasharray="4 8" />
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#46C1BE" />
            <stop offset="50%" stopColor="#615090" />
            <stop offset="100%" stopColor="#46C1BE" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <BrainCircuit className="h-8 w-8 text-brand-turquoise mb-1 ai-brain-pulse" />
        <span className="text-5xl font-bold font-cairo bg-gradient-to-br from-brand-turquoise via-white to-brand-purple bg-clip-text text-transparent">
          {animatedScore}
        </span>
        <span className="text-xs text-white/75 font-tajawal mt-0.5">{label}</span>
      </div>
    </div>
  );
};

const MetricOrb = ({ icon: Icon, value, label, color, delay = 0 }) => {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  const colorMap = {
    turquoise: 'from-brand-turquoise to-brand-turquoise-dark shadow-brand-turquoise/30',
    navy: 'from-brand-navy to-brand-navy-dark shadow-brand-navy/30',
    purple: 'from-brand-purple to-brand-purple-dark shadow-brand-purple/30',
    'navy-light': 'from-brand-navy-light to-brand-navy shadow-brand-navy/25',
    emerald: 'from-emerald-500 to-emerald-600 shadow-emerald-500/25',
    violet: 'from-brand-purple to-brand-purple-light shadow-brand-purple/25',
    amber: 'from-amber-500 to-amber-600 shadow-amber-500/25',
    cyan: 'from-brand-turquoise to-brand-turquoise-light shadow-brand-turquoise/25',
  };

  return (
    <div className={`flex flex-col items-center gap-2 transition-all duration-700 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
      <div className={`relative w-20 h-20 rounded-full bg-gradient-to-br ${colorMap[color] || colorMap.turquoise} shadow-lg flex items-center justify-center`}>
        <div className="absolute inset-0 rounded-full bg-white/10 backdrop-blur-sm" />
        <div className="relative z-10 text-center">
          <span className="text-xl font-bold text-white font-cairo block leading-none">{value}</span>
        </div>
        <div className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-white/15 border-2 border-white/20 backdrop-blur-sm flex items-center justify-center shadow-sm">
          <Icon className="h-3.5 w-3.5 text-white/80" />
        </div>
      </div>
      <span className="text-xs text-white/75 font-tajawal text-center max-w-[90px]">{label}</span>
    </div>
  );
};

const HakeemGuide = ({ activeSection, isRTL, insights, predictions, alerts, studentRisks, recommendations }) => {
  const { api, user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `hakim_insights_${Date.now()}`);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const contextSummary = isRTL
      ? `أنت الآن في صفحة رؤى الذكاء الاصطناعي. مؤشر الأداء العام: ${insights.overall_score}/100. التنبيهات: ${alerts.length}. التوقعات: ${predictions.length}. الطلاب المعرّضون للخطر: ${studentRisks.length}. التوصيات: ${recommendations.length}. القسم النشط: ${activeSection}.`
      : `You are on the AI Insights page. Overall score: ${insights.overall_score}/100. Alerts: ${alerts.length}. Predictions: ${predictions.length}. At-risk students: ${studentRisks.length}. Recommendations: ${recommendations.length}. Active section: ${activeSection}.`;

    setMessages([{
      role: 'assistant',
      content: isRTL
        ? `مرحباً! أنا حكيم، مساعدك الذكي. مؤشر أداء المدرسة ${insights.overall_score}/100 ${insights.trend === 'up' ? '📈' : '📉'}. اسألني أي سؤال عن البيانات أو اطلب تحليلاً أعمق!`
        : `Hello! I'm Hakim, your AI assistant. School performance score is ${insights.overall_score}/100 ${insights.trend === 'up' ? '📈' : '📉'}. Ask me anything about the data or request deeper analysis!`,
      context: contextSummary
    }]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const quickQuestions = useMemo(() => {
    if (isRTL) {
      return [
        'حلّل الحضور',
        'من الطلاب المعرضون؟',
        'أهم التوصيات',
        'ما التنبيهات؟'
      ];
    }
    return [
      'Analyze attendance',
      'At-risk students?',
      'Top recommendations',
      'What alerts?'
    ];
  }, [isRTL]);

  const sendMessage = async (text) => {
    if (!text.trim() || isLoading) return;
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const contextData = `القسم النشط: ${activeSection}. الأداء: ${insights.overall_score}/100. تنبيهات: ${alerts.length}. توقعات: ${predictions.length}. طلاب معرضون: ${studentRisks.length}. توصيات: ${recommendations.length}.`;

      const history = messages.slice(-10).map(m => ({ role: m.role, content: m.content }));

      const response = await api.post('/hakim/chat', {
        message: text,
        context: contextData,
        user_role: user?.role,
        tenant_id: user?.tenant_id,
        conversation_history: history,
        session_id: sessionId
      });

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.response,
        suggestions: response.data.suggestions || []
      }]);
    } catch (err) {
      console.error('Hakim chat error:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: isRTL ? 'عذراً، حدث خطأ. حاول مرة أخرى.' : 'Sorry, an error occurred. Please try again.'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="sticky top-24 space-y-4">
      <Card className="overflow-hidden border-brand-purple/20 shadow-lg shadow-brand-purple/5">
        <div className="bg-gradient-to-br from-brand-purple to-brand-navy p-4">
          <div className="flex items-center gap-3">
            <div className="w-16 h-16 rounded-xl bg-white/20 overflow-hidden flex-shrink-0 ring-2 ring-white/30 ai-float p-0.5">
              <img src={HAKIM_AVATAR} alt="حكيم" className="w-full h-full object-contain" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-cairo font-bold text-white text-sm">{isRTL ? 'حكيم — دردشة ذكية' : 'Hakim — AI Chat'}</h3>
                <Sparkles className="h-3.5 w-3.5 text-brand-gold" />
              </div>
              <p className="text-white/60 text-xs font-tajawal">{isRTL ? 'اسألني أي شيء عن بيانات المدرسة' : 'Ask me anything about school data'}</p>
            </div>
            {isLoading && (
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full bg-brand-gold animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="h-[280px] overflow-y-auto p-3 space-y-3">
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              {msg.role === 'assistant' && (
                <div className="w-9 h-9 rounded-lg bg-brand-purple/10 overflow-hidden flex-shrink-0">
                  <img src={HAKIM_AVATAR} alt="حكيم" className="w-full h-full object-contain" />
                </div>
              )}
              <div className={`max-w-[85%] rounded-2xl px-3 py-2 ${
                msg.role === 'user'
                  ? 'bg-brand-navy text-white'
                  : 'bg-muted'
              }`}>
                <p className="text-xs leading-relaxed font-tajawal whitespace-pre-wrap">{msg.content}</p>
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {msg.suggestions.map((s, si) => (
                      <button key={si} onClick={() => sendMessage(s)}
                        className="text-[10px] bg-brand-turquoise/10 text-brand-turquoise hover:bg-brand-turquoise/20 rounded-lg px-2 py-1 transition-colors font-tajawal">
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex gap-2">
              <div className="w-9 h-9 rounded-lg bg-brand-purple/10 overflow-hidden flex-shrink-0">
                <img src={HAKIM_AVATAR} alt="حكيم" className="w-full h-full object-contain" />
              </div>
              <div className="bg-muted rounded-2xl px-3 py-2">
                <div className="flex gap-1">
                  {[0, 1, 2].map(i => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full bg-brand-purple animate-bounce" style={{ animationDelay: `${i * 200}ms` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="px-3 pb-2">
          <div className="flex flex-wrap gap-1 mb-2">
            {quickQuestions.map((q, qi) => (
              <button key={qi} onClick={() => sendMessage(q)}
                className="text-[10px] bg-brand-purple/5 hover:bg-brand-purple/10 text-brand-purple border border-brand-purple/10 rounded-full px-2.5 py-1 transition-colors font-tajawal">
                {q}
              </button>
            ))}
          </div>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={isRTL ? 'اسأل حكيم...' : 'Ask Hakim...'}
              disabled={isLoading}
              className="flex-1 text-xs rounded-xl border border-border bg-background px-3 py-2 font-tajawal focus:outline-none focus:ring-1 focus:ring-brand-purple"
            />
            <button type="submit" disabled={isLoading || !input.trim()}
              className="bg-brand-purple hover:bg-brand-purple-light text-white rounded-xl px-3 py-2 disabled:opacity-50 transition-colors">
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>
      </Card>
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
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="currentColor" className="text-muted/15" strokeWidth="4" />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-700" />
      </svg>
      <span className="absolute text-[10px] font-bold font-cairo" style={{ color }}>{value}%</span>
    </div>
  );
};

const QuickStatCard = ({ icon: Icon, label, value, subLabel, gradient, onClick }) => (
  <button onClick={onClick}
    className="group relative overflow-hidden rounded-2xl border border-border/50 bg-card p-4 hover:shadow-lg hover:shadow-brand-turquoise/5 transition-all duration-300 text-start w-full">
    <div className="flex items-start justify-between">
      <div className="flex-1">
        <p className="text-xs text-muted-foreground font-tajawal mb-1">{label}</p>
        <p className="text-2xl font-bold font-cairo text-foreground">{value}</p>
        {subLabel && <p className="text-[10px] text-muted-foreground font-tajawal mt-1">{subLabel}</p>}
      </div>
      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-sm`}>
        <Icon className="h-5 w-5 text-white" />
      </div>
    </div>
  </button>
);

const AlertsTimeline = ({ alerts, isRTL, onNavigate }) => {
  const typeConfig = {
    warning: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-50 dark:bg-amber-950/30', line: 'bg-amber-300' },
    info: { icon: Lightbulb, color: 'text-sky-500', bg: 'bg-sky-50 dark:bg-sky-950/30', line: 'bg-sky-300' },
    success: { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-950/30', line: 'bg-emerald-300' },
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
    <Card className="card-nassaq overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-base">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-amber-500 to-yellow-500 flex items-center justify-center">
              <Zap className="h-4 w-4 text-white" />
            </div>
            {isRTL ? 'التنبيهات الذكية' : 'Smart Alerts'}
          </CardTitle>
          {alerts.length > 0 && (
            <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-0 font-cairo">{alerts.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-3">
              <CheckCircle className="h-6 w-6 text-emerald-500" />
            </div>
            <p className="text-sm font-cairo font-medium text-muted-foreground">{isRTL ? 'لا توجد تنبيهات حالياً' : 'No alerts right now'}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1">{isRTL ? 'سيقوم حكيم بإعلامك عند اكتشاف أنماط مهمة' : 'Hakim will notify you when important patterns are detected'}</p>
          </div>
        ) : (
          <div className="relative space-y-0">
            <div className="absolute start-[19px] top-4 bottom-4 w-[2px] bg-gradient-to-b from-amber-200 via-sky-200 to-emerald-200 dark:from-amber-800/40 dark:via-sky-800/40 dark:to-emerald-800/40" />
            {alerts.slice(0, 5).map((alert, i) => {
              const config = typeConfig[alert.type] || typeConfig.info;
              const AlertIcon = config.icon;
              const alertRoute = alert.route || alertRouteMap[alert.category] || null;

              return (
                <div key={alert.id || i} className="relative flex gap-4 pb-4 last:pb-0">
                  <div className={`relative z-10 w-10 h-10 rounded-xl ${config.bg} flex items-center justify-center shrink-0 border border-border/50`}>
                    <AlertIcon className={`h-4.5 w-4.5 ${config.color}`} />
                  </div>
                  <div className="flex-1 min-w-0 pt-1">
                    <p className="text-sm font-cairo font-semibold text-foreground leading-snug">
                      {isRTL ? alert.title?.ar : alert.title?.en}
                    </p>
                    <p className="text-xs text-muted-foreground font-tajawal mt-1 line-clamp-2">
                      {isRTL ? alert.description?.ar : alert.description?.en}
                    </p>
                    <div className="flex items-center gap-3 mt-2">
                      <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1 font-tajawal">
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
    <Card className="card-nassaq overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-base">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center">
              <Radar className="h-4 w-4 text-white" />
            </div>
            {isRTL ? 'التوقعات والتنبؤات' : 'Predictions & Forecasts'}
          </CardTitle>
          {predictions.length > 0 && (
            <Badge className="bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400 border-0 font-cairo">{predictions.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {predictions.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-muted/30 flex items-center justify-center mb-3">
              <TrendingUp className="h-6 w-6 text-muted-foreground/40" />
            </div>
            <p className="text-sm font-cairo font-medium text-muted-foreground">{isRTL ? 'لا توجد توقعات حالياً' : 'No predictions yet'}</p>
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
                <div key={pred.id || i} className={`p-4 rounded-xl border border-border/50 ${colors.bg} transition-all duration-300 hover:shadow-md`}>
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
    <Card className="card-nassaq overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-base">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
              <Target className="h-4 w-4 text-white" />
            </div>
            {isRTL ? 'توصيات ذكية' : 'Smart Recommendations'}
          </CardTitle>
          {recommendations.length > 0 && (
            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 font-cairo">{recommendations.length}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {recommendations.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-muted/30 flex items-center justify-center mb-3">
              <Lightbulb className="h-6 w-6 text-muted-foreground/40" />
            </div>
            <p className="text-sm font-cairo font-medium text-muted-foreground">{isRTL ? 'لا توجد توصيات حالياً' : 'No recommendations yet'}</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {recommendations.map((rec, i) => {
              const config = priorityConfig[rec.priority] || priorityConfig.medium;
              const PIcon = config.icon;
              return (
                <div key={rec.id || i} className="group relative flex items-start gap-3 p-3.5 rounded-xl border border-border/50 hover:border-brand-turquoise/30 bg-card hover:shadow-md transition-all duration-300">
                  <div className={`absolute top-0 ${isRTL ? 'right-0' : 'left-0'} w-1 h-full rounded-full ${config.accent}`} />
                  <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${config.color} flex items-center justify-center shrink-0 shadow-sm`}>
                    <PIcon className="h-4 w-4 text-white" />
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
                    <div className="flex items-center gap-2 mt-2">
                      <div className="flex-1 h-1.5 bg-muted/20 rounded-full overflow-hidden">
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
    <Card className="card-nassaq overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-base">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-rose-500 to-red-500 flex items-center justify-center">
              <HeartPulse className="h-4 w-4 text-white" />
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
      <CardContent>
        {students.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-3">
              <Shield className="h-6 w-6 text-emerald-500" />
            </div>
            <p className="text-sm font-cairo font-medium text-muted-foreground">{isRTL ? 'لا يوجد طلاب في خطر' : 'No at-risk students'}</p>
            <p className="text-xs text-muted-foreground/60 font-tajawal mt-1">{isRTL ? 'جميع الطلاب يسيرون بشكل جيد' : 'All students performing well'}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {students.sort((a, b) => b.risk_level - a.risk_level).map((student, i) => {
              const config = getRiskConfig(student.risk_level);
              return (
                <button key={student.id || i} onClick={() => onNavigate(student)}
                  className="w-full group flex items-center gap-3 p-3 rounded-xl border border-border/50 hover:border-red-200 hover:shadow-md transition-all duration-300 text-start">
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

  const totalIssues = alerts.length + studentRisks.filter(s => s.risk_level >= 70).length;
  const totalActions = recommendations.length + predictions.length;

  return (
    <Sidebar>
      <div className="min-h-screen bg-background relative" data-testid="ai-insights-page">
        <NeuralBackground />

        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-brand-turquoise to-brand-purple flex items-center justify-center ai-glow">
                <BrainCircuit className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
                  {isRTL ? 'رؤى الذكاء الاصطناعي' : 'AI Smart Insights'}
                  <Sparkles className="h-5 w-5 text-brand-gold" />
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? 'تحليلات عميقة وتوقعات ذكية مدعومة بالذكاء الاصطناعي' : 'Deep analytics and AI-powered smart predictions'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={handleRefresh} disabled={refreshing} className="rounded-xl gap-2">
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                <span className="hidden sm:inline">{isRTL ? 'تحديث' : 'Refresh'}</span>
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl" aria-label={isRTL ? 'تغيير اللغة' : 'Toggle language'}>
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl" aria-label={isRTL ? 'تبديل المظهر' : 'Toggle theme'}>
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="relative z-10 p-6 max-w-[1600px] mx-auto">

          {/* ══════ HERO CARD — PRESERVED AS-IS ══════ */}
          <div className="ai-slide-in mb-8">
            <Card className="card-nassaq overflow-hidden border-0 shadow-2xl">
              <div className="relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-brand-navy via-brand-navy-dark to-brand-purple/90" />
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_10%_90%,rgba(70,193,190,0.25),transparent_50%)]" />
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_90%_10%,rgba(97,80,144,0.25),transparent_50%)]" />
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(70,193,190,0.08),transparent_70%)]" />

                <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="absolute w-1.5 h-1.5 bg-white/15 rounded-full ai-float" style={{ left: `${10 + i * 12}%`, top: `${15 + (i % 4) * 20}%`, animationDelay: `${i * 0.5}s`, animationDuration: `${3 + i * 0.4}s` }} />
                  ))}
                  <div className="absolute top-4 right-4 w-32 h-32 rounded-full border border-white/5" />
                  <div className="absolute bottom-4 left-4 w-24 h-24 rounded-full border border-brand-turquoise/10" />
                </div>

                <div className="relative z-10 p-8 lg:p-10">
                  <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
                    <div className="flex-1 text-center lg:text-start">
                      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 backdrop-blur-md border border-white/15 mb-5 shadow-lg shadow-brand-turquoise/10">
                        <div className="w-8 h-8 rounded-full overflow-hidden flex-shrink-0">
                          <img src={HAKIM_AVATAR} alt="حكيم" className="w-full h-full object-contain" />
                        </div>
                        <span className="text-xs font-tajawal text-white/80 font-medium">
                          {isRTL ? 'تحليل مدعوم بحكيم AI' : 'Powered by Hakim AI'}
                        </span>
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      </div>
                      <h2 className="text-3xl lg:text-4xl font-bold font-cairo text-white mb-3 leading-tight">
                        {isRTL ? 'مؤشر الأداء الذكي' : 'Smart Performance Index'}
                      </h2>
                      <p className="text-sm text-white/70 font-tajawal max-w-lg leading-relaxed">
                        {isRTL
                          ? 'تقييم شامل لأداء المدرسة بناءً على تحليل الذكاء الاصطناعي للبيانات التعليمية والسلوكية'
                          : 'Comprehensive school performance assessment based on AI analysis of educational and behavioral data'}
                      </p>

                      <div className="flex items-center gap-4 mt-6 justify-center lg:justify-start">
                        <div className={`flex items-center gap-2.5 px-5 py-2.5 rounded-xl backdrop-blur-sm ${
                          insights.trend === 'up'
                            ? 'bg-emerald-500/15 border border-emerald-400/25 shadow-lg shadow-emerald-500/10'
                            : 'bg-red-500/15 border border-red-400/25 shadow-lg shadow-red-500/10'
                        }`}>
                          {insights.trend === 'up' ? (
                            <ArrowUpRight className="h-5 w-5 text-emerald-400" />
                          ) : (
                            <ArrowDownRight className="h-5 w-5 text-red-400" />
                          )}
                          <span className={`text-lg font-bold font-cairo ${insights.trend === 'up' ? 'text-emerald-400' : 'text-red-400'}`}>
                            {insights.trend_value}%
                          </span>
                          <span className="text-xs text-white/70 font-tajawal">
                            {isRTL ? 'مقارنة بالشهر الماضي' : 'vs last month'}
                          </span>
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-5 mt-8 justify-center lg:justify-start">
                        <MetricOrb icon={Users} value={metrics.total_students || 0} label={isRTL ? 'طالب' : 'Students'} color="turquoise" delay={200} />
                        <MetricOrb icon={GraduationCap} value={metrics.total_teachers || 0} label={isRTL ? 'معلم' : 'Teachers'} color="purple" delay={400} />
                        <MetricOrb icon={Activity} value={`${metrics.attendance_rate || 0}%`} label={isRTL ? 'نسبة الحضور' : 'Attendance'} color="navy-light" delay={600} />
                        <MetricOrb icon={BarChart3} value={`${metrics.student_teacher_ratio || 0}:1`} label={isRTL ? 'طالب/معلم' : 'Ratio'} color="navy" delay={800} />
                      </div>
                    </div>

                    <div className="ai-float">
                      <AnimatedGauge
                        score={insights.overall_score}
                        size={230}
                        label={isRTL ? 'من ١٠٠' : 'out of 100'}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
          {/* ══════ END HERO CARD ══════ */}

          {/* ══════ QUICK SUMMARY STRIP ══════ */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6 ai-fade-in">
            {[
              { id: 'alerts', icon: Zap, label: isRTL ? 'التنبيهات' : 'Alerts', value: alerts.length, gradient: 'from-brand-turquoise to-brand-turquoise-dark', sub: alerts.length > 0 ? (isRTL ? 'تحتاج مراجعة' : 'Need review') : (isRTL ? 'لا توجد' : 'Clear') },
              { id: 'predictions', icon: TrendingUp, label: isRTL ? 'التوقعات' : 'Predictions', value: predictions.length, gradient: 'from-brand-purple to-brand-purple-dark', sub: isRTL ? 'تنبؤات ذكية' : 'AI forecasts' },
              { id: 'recommendations', icon: Target, label: isRTL ? 'التوصيات' : 'Actions', value: recommendations.length, gradient: 'from-brand-navy-light to-brand-navy', sub: isRTL ? 'إجراءات مقترحة' : 'Suggested' },
              { id: 'risks', icon: HeartPulse, label: isRTL ? 'المخاطر' : 'Risks', value: studentRisks.length, gradient: 'from-brand-navy to-brand-navy-dark', sub: studentRisks.filter(s => s.risk_level >= 70).length > 0 ? `${studentRisks.filter(s => s.risk_level >= 70).length} ${isRTL ? 'مرتفع' : 'high'}` : (isRTL ? 'آمن' : 'Safe') },
            ].map(item => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button key={item.id} onClick={() => setActiveTab(item.id === activeTab ? 'overview' : item.id)}
                  className={`group relative overflow-hidden rounded-2xl border p-4 text-start transition-all duration-300 ${
                    isActive
                      ? 'border-brand-turquoise/40 bg-brand-turquoise/5 shadow-lg shadow-brand-turquoise/10 ring-1 ring-brand-turquoise/20'
                      : 'border-border/50 bg-card hover:shadow-md hover:shadow-brand-turquoise/5 hover:border-brand-turquoise/20'
                  }`}>
                  <div className="flex items-start justify-between mb-2">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${item.gradient} flex items-center justify-center shadow-sm`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    {item.value > 0 && (
                      <span className={`inline-flex items-center justify-center min-w-[24px] h-6 rounded-full text-xs font-bold px-1.5 ${
                        isActive ? 'bg-brand-turquoise text-white' : 'bg-muted text-muted-foreground'
                      }`}>{item.value}</span>
                    )}
                  </div>
                  <p className="text-2xl font-bold font-cairo text-foreground">{item.value}</p>
                  <p className="text-xs text-muted-foreground font-tajawal">{item.label}</p>
                  <p className="text-[10px] text-muted-foreground/60 font-tajawal mt-0.5">{item.sub}</p>
                </button>
              );
            })}
          </div>

          {/* ══════ NAVIGATION TABS ══════ */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-2 ai-fade-in scrollbar-none mb-6 border-b border-border/30 -mx-1 px-1">
            {tabs.map(tab => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative flex items-center gap-2 px-4 py-2.5 text-sm font-tajawal whitespace-nowrap transition-all duration-300 rounded-t-xl ${
                    isActive
                      ? 'text-brand-turquoise font-semibold'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                  {tab.count > 0 && (
                    <span className={`min-w-[20px] h-5 rounded-full text-[10px] flex items-center justify-center font-bold px-1 ${
                      isActive ? 'bg-brand-turquoise/10 text-brand-turquoise' : 'bg-muted text-muted-foreground'
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

          {/* ══════ CONTENT AREA ══════ */}
          <div className="flex gap-6">
            <div className="flex-1 min-w-0 space-y-6">

              {activeTab === 'overview' && (
                <div className="space-y-6 ai-slide-in">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <QuickStatCard
                      icon={Users}
                      label={isRTL ? 'إجمالي الطلاب' : 'Total Students'}
                      value={metrics.total_students || 0}
                      subLabel={isRTL ? 'مسجّل' : 'Enrolled'}
                      gradient="from-brand-turquoise to-brand-turquoise-dark"
                      onClick={() => navigate('/admin/users-management')}
                    />
                    <QuickStatCard
                      icon={GraduationCap}
                      label={isRTL ? 'إجمالي المعلمين' : 'Total Teachers'}
                      value={metrics.total_teachers || 0}
                      subLabel={`${metrics.student_teacher_ratio || 0}:1 ${isRTL ? 'طالب/معلم' : 'ratio'}`}
                      gradient="from-brand-purple to-brand-purple-dark"
                      onClick={() => navigate('/admin/users-management?filter=teachers')}
                    />
                    <QuickStatCard
                      icon={Activity}
                      label={isRTL ? 'نسبة الحضور' : 'Attendance Rate'}
                      value={`${metrics.attendance_rate || 0}%`}
                      subLabel={isRTL ? 'اليوم' : 'Today'}
                      gradient="from-brand-navy-light to-brand-navy"
                      onClick={() => navigate('/admin/attendance')}
                    />
                    <QuickStatCard
                      icon={Shield}
                      label={isRTL ? 'طلاب في خطر' : 'At-Risk Students'}
                      value={studentRisks.length}
                      subLabel={studentRisks.filter(s => s.risk_level < 40).length > 0 ? `${studentRisks.filter(s => s.risk_level < 40).length} ${isRTL ? 'خطر مرتفع' : 'critical'}` : (studentRisks.length > 0 ? (isRTL ? 'يحتاج متابعة' : 'Needs follow-up') : (isRTL ? 'آمن' : 'Safe'))}
                      gradient="from-brand-navy to-brand-navy-dark"
                      onClick={() => setActiveTab('risks')}
                    />
                  </div>

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
                <div className="ai-slide-in">
                  <AlertsTimeline alerts={alerts} isRTL={isRTL} onNavigate={handleAlertNavigate} />
                </div>
              )}

              {activeTab === 'predictions' && (
                <div className="ai-slide-in">
                  <PredictionsPanel predictions={predictions} isRTL={isRTL} />
                </div>
              )}

              {activeTab === 'recommendations' && (
                <div className="ai-slide-in">
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
                <div className="ai-slide-in">
                  <RiskStudentsPanel students={studentRisks} isRTL={isRTL} onNavigate={handleStudentNavigate} />
                </div>
              )}

              <div className="pb-4 ai-fade-in">
                <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground/50 font-tajawal">
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

            {/* ══════ SIDEBAR — Hakim Chat ══════ */}
            <div className={`hidden xl:block w-[340px] flex-shrink-0`}>
              <HakeemGuide
                activeSection={activeTab}
                isRTL={isRTL}
                insights={insights}
                predictions={predictions}
                alerts={alerts}
                studentRisks={studentRisks}
                recommendations={recommendations}
              />
            </div>
          </div>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};

export default AIInsightsPage;
