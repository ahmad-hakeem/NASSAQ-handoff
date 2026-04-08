import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import SectionErrorBoundary from '../SectionErrorBoundary';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ScrollArea } from '../ui/scroll-area';
import { Card } from '../ui/card';
import { X, Send, Loader2, ChevronDown, Trash2, ExternalLink } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getPoseForPath, getPose } from './hakimPoses';
import hakimEngine, { SYSTEM_EVENTS } from './HakimContextEngine';

const PAGE_CONTEXT_MAP = {
  '/school/dashboard': { name: 'مركز القيادة', suggestions: ['ما حالة المدرسة اليوم؟', 'أعطني ملخص الحضور', 'ما أهم التنبيهات؟'] },
  '/school/schedule': { name: 'الجدول الدراسي', suggestions: ['كيف أنشئ جدول جديد؟', 'هل يوجد تعارضات؟', 'كيف أوزع الحصص؟'] },
  '/school/assessments': { name: 'الاختبارات والتقييمات', suggestions: ['كيف أضيف اختبار؟', 'كيف أسجل الدرجات؟', 'ما نتائج الطلاب؟'] },
  '/school/communication': { name: 'مركز التواصل', suggestions: ['كيف أرسل إشعار؟', 'كيف أتواصل مع أولياء الأمور؟'] },
  '/school/ai-insights': { name: 'رؤى الذكاء الاصطناعي', suggestions: ['ما أهم التنبؤات؟', 'من الطلاب المعرضون للخطر؟', 'ما التوصيات المتاحة؟'] },
  '/principal/ai-insights': { name: 'رؤى الذكاء الاصطناعي', suggestions: ['ما أهم التنبؤات؟', 'من الطلاب المعرضون للخطر؟', 'كيف أداء المدرسة؟'] },
  '/school/settings': { name: 'الإعدادات', suggestions: ['كيف أعدّل أيام الدراسة؟', 'كيف أضبط أوقات الحصص؟'] },
  '/principal/timetable': { name: 'الجدول المدرسي', suggestions: ['كيف أولّد الجدول؟', 'كيف أنقل حصة؟', 'ما حالة الجدول الحالي؟'] },
  '/principal/users-management': { name: 'إدارة المستخدمين والفصول', suggestions: ['كيف أضيف معلم؟', 'كيف أنشئ فصل؟'] },
  '/principal/communication': { name: 'مركز التواصل', suggestions: ['كيف أرسل إشعار لأولياء الأمور؟'] },
  '/admin/attendance': { name: 'إدارة الحضور', suggestions: ['ما نسبة الحضور اليوم؟', 'من الطلاب الأكثر غياباً؟', 'كيف أسجل الحضور؟'] },
  '/admin/students': { name: 'إدارة الطلاب', suggestions: ['كيف أضيف طالب جديد؟', 'كيف أبحث عن طالب؟'] },
  '/admin/teachers': { name: 'إدارة المعلمين', suggestions: ['كيف أضيف معلم؟', 'كيف أوزع الحصص على المعلمين؟'] },
  '/admin/classes': { name: 'إدارة الفصول', suggestions: ['كيف أنشئ فصل جديد؟', 'كم عدد الفصول؟'] },
  '/admin/users-management': { name: 'إدارة المستخدمين', suggestions: ['كيف أضيف مستخدم؟', 'ما الصلاحيات المتاحة؟'] },
  '/admin/dashboard': { name: 'لوحة تحكم المنصة', suggestions: ['ما إحصائيات المنصة؟', 'كم عدد المدارس المفعلة؟'] },
  '/teacher/home': { name: 'الصفحة الرئيسية', suggestions: ['ما حصصي اليوم؟', 'كيف أبدأ حصة؟'] },
  '/teacher/session/start': { name: 'بدء حصة', suggestions: ['كيف أبدأ الحصة؟', 'كيف أسجل الحضور؟'] },
  '/teacher/attendance': { name: 'الحضور والغياب', suggestions: ['كيف أسجل الحضور؟', 'ما نسبة حضور فصلي؟'] },
  '/teacher/assessments': { name: 'التقييمات', suggestions: ['كيف أنشئ اختبار؟', 'كيف أرصد الدرجات؟'] },
  '/teacher/students': { name: 'طلابي', suggestions: ['كيف أتابع طالب؟', 'من يحتاج متابعة؟'] },
};

const IDLE_GREETINGS = [
  'السلام عليكم 👋',
  'أهلاً! كيف أساعدك؟',
  'مرحباً! أنا هنا 🌟',
  'هل تحتاج مساعدة؟',
];

const HakimState = {
  IDLE: 'idle',
  LISTENING: 'listening',
  THINKING: 'thinking',
  RESPONDING: 'responding',
  GREETING: 'greeting',
};

const MarkdownMessage = ({ content, onNavigate }) => {
  const { t } = useTranslation();
  const components = useMemo(() => ({
    a: ({ href, children }) => {
      if (href && href.startsWith('/')) {
        return (
          <button
            onClick={() => onNavigate(href)}
            className="inline-flex items-center gap-1 text-[#1B93A4] hover:text-[#157a89] font-semibold underline underline-offset-2 decoration-[#1B93A4]/40 hover:decoration-[#1B93A4] transition-colors cursor-pointer"
          >
            {children}
            <ExternalLink className="h-3 w-3 inline-block" />
          </button>
        );
      }
      return <a href={href} target="_blank" rel="noopener noreferrer" className="text-[#1B93A4] underline">{children}</a>;
    },
    h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-2 text-foreground font-cairo">{children}</h1>,
    h2: ({ children }) => <h2 className="text-base font-bold mt-2.5 mb-1.5 text-foreground font-cairo">{children}</h2>,
    h3: ({ children }) => <h3 className="text-[15px] font-semibold mt-2 mb-1 text-foreground/90 font-cairo">{children}</h3>,
    p: ({ children }) => <p className="text-[15px] leading-relaxed mb-2 last:mb-0 text-gray-800 dark:text-gray-200">{children}</p>,
    ul: ({ children }) => <ul className="text-[15px] list-disc list-inside space-y-1 mb-2 ms-1">{children}</ul>,
    ol: ({ children }) => <ol className="text-[15px] list-decimal list-inside space-y-1 mb-2 ms-1">{children}</ol>,
    li: ({ children }) => <li className="text-[15px] leading-relaxed text-gray-700 dark:text-gray-300">{children}</li>,
    strong: ({ children }) => <strong className="font-bold text-foreground">{children}</strong>,
    code: ({ children }) => <code className="bg-muted/60 text-sm px-1.5 py-0.5 rounded font-mono">{children}</code>,
    blockquote: ({ children }) => (
      <blockquote className="border-s-3 border-[#1B93A4]/40 ps-3 my-1.5 text-sm text-muted-foreground italic">
        {children}
      </blockquote>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto my-2 rounded-lg border">
        <table className="w-full text-xs border-collapse">{children}</table>
      </div>
    ),
    th: ({ children }) => <th className="bg-muted/50 px-2 py-1.5 text-start font-semibold border-b text-xs">{children}</th>,
    td: ({ children }) => <td className="px-2 py-1 border-b text-xs">{children}</td>,
    hr: () => <hr className="my-2 border-border/50" />,
  }), [onNavigate]);

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
};

const HakimAssistantInner = () => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [hakimState, setHakimState] = useState(HakimState.IDLE);
  const [greetingText, setGreetingText] = useState('');
  const [showGreeting, setShowGreeting] = useState(false);
  const [breathe, setBreathe] = useState(true);
  const [dismissCount, setDismissCount] = useState(0);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const idleTimerRef = useRef(null);
  const greetingIndexRef = useRef(0);
  const lastInteractionRef = useRef(Date.now());
  const timeoutRefs = useRef([]);
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const userRole = user?.role || user?.user_role || 'school_principal';
    hakimEngine.detectContext(location.pathname, userRole);
  }, [location.pathname, user]);

  const currentPageInfo = useMemo(() => {
    for (const [path, info] of Object.entries(PAGE_CONTEXT_MAP)) {
      if (location.pathname === path || location.pathname.startsWith(path + '/')) {
        return info;
      }
    }
    return null;
  }, [location.pathname]);

  const hakimAvatar = useMemo(() => getPose('friendly-greeting'), []);
  const hakimListeningAvatar = useMemo(() => getPose('listening'), []);
  const hakimThinkingAvatar = useMemo(() => getPose('ai-thinking'), []);
  const hakimRespondingAvatar = useMemo(() => getPose('explaining-concept'), []);

  const welcomeMessage = useMemo(() => {
    const pageName = currentPageInfo?.name;
    const base = 'مرحباً! أنا **حكيم**، مساعدك الذكي في منصة **نَسَّق** 🌟';
    const pageNote = pageName ? `\n\nأنت حالياً في **${pageName}**. كيف يمكنني مساعدتك؟` : '\n\nكيف يمكنني مساعدتك اليوم؟';
    return base + pageNote;
  }, [currentPageInfo]);

  const hasInitialized = useRef(false);
  useEffect(() => {
    if (!hasInitialized.current) {
      hasInitialized.current = true;
      setMessages([{
        role: 'assistant',
        content: welcomeMessage,
        suggestions: currentPageInfo?.suggestions || ['ما هي إمكانيات النظام؟', 'ساعدني في البدء', 'أعطني ملخص سريع'],
      }]);
    }
  }, [welcomeMessage, currentPageInfo]);

  useEffect(() => {
    return () => { timeoutRefs.current.forEach(clearTimeout); };
  }, []);

  const trackTimeout = useCallback((fn, ms) => {
    const id = setTimeout(fn, ms);
    timeoutRefs.current.push(id);
    return id;
  }, []);

  const scrollToBottom = useCallback(() => {
    trackTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }, [trackTimeout]);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      trackTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen, trackTimeout]);

  useEffect(() => {
    const handleIdleGreeting = () => {
      if (isOpen || dismissCount >= 3) return;

      const now = Date.now();
      const elapsed = now - lastInteractionRef.current;
      const delay = Math.min(30000 + dismissCount * 20000, 120000);

      if (elapsed >= delay) {
        const greeting = IDLE_GREETINGS[greetingIndexRef.current % IDLE_GREETINGS.length];
        greetingIndexRef.current++;
        setGreetingText(greeting);
        setShowGreeting(true);
        setHakimState(HakimState.GREETING);

        trackTimeout(() => {
          setShowGreeting(false);
          setHakimState(HakimState.IDLE);
        }, 3000);

        lastInteractionRef.current = now;
      }
    };

    idleTimerRef.current = setInterval(handleIdleGreeting, 10000);
    return () => clearInterval(idleTimerRef.current);
  }, [isOpen, dismissCount, trackTimeout]);

  const handleUserInteraction = useCallback(() => {
    lastInteractionRef.current = Date.now();
    setShowGreeting(false);
  }, []);

  const handleNavigate = useCallback((path) => {
    navigate(path);
    setIsOpen(false);
  }, [navigate]);

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return;
    handleUserInteraction();

    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setHakimState(HakimState.THINKING);

    try {
      const response = await api.post('/hakim/chat', {
        message: text,
        context: null,
        user_role: user?.role,
        tenant_id: user?.tenant_id,
        current_page: location.pathname,
      });

      setHakimState(HakimState.RESPONDING);

      const assistantMessage = {
        role: 'assistant',
        content: response.data.response,
        suggestions: response.data.suggestions || [],
      };
      setMessages((prev) => [...prev, assistantMessage]);

      trackTimeout(() => setHakimState(HakimState.IDLE), 1000);
    } catch (error) {
      console.error('Hakim error:', error);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ عذراً، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.',
          suggestions: [],
        },
      ]);
      setHakimState(HakimState.IDLE);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const clearChat = useCallback(() => {
    setMessages([{
      role: 'assistant',
      content: welcomeMessage,
      suggestions: currentPageInfo?.suggestions || ['ما هي إمكانيات النظام؟', 'ساعدني في البدء', 'أعطني ملخص سريع'],
    }]);
  }, [welcomeMessage, currentPageInfo]);

  const toggleOpen = () => {
    handleUserInteraction();
    setShowGreeting(false);
    setDismissCount(prev => isOpen ? prev + 1 : 0);
    setIsOpen(!isOpen);
    if (!isOpen) {
      setHakimState(HakimState.IDLE);
      hakimEngine.fireEvent(SYSTEM_EVENTS.HELP_REQUESTED);
    }
  };

  const stateGlow = useMemo(() => {
    switch (hakimState) {
      case HakimState.THINKING: return 'shadow-[0_0_20px_rgba(124,58,237,0.5)]';
      case HakimState.RESPONDING: return 'shadow-[0_0_20px_rgba(27,147,164,0.5)]';
      case HakimState.GREETING: return 'shadow-[0_0_16px_rgba(27,147,164,0.4)]';
      default: return 'shadow-lg';
    }
  }, [hakimState]);

  const currentAvatar = useMemo(() => {
    switch (hakimState) {
      case HakimState.THINKING: return hakimThinkingAvatar;
      case HakimState.RESPONDING: return hakimRespondingAvatar;
      case HakimState.LISTENING: return hakimListeningAvatar;
      default: return hakimAvatar;
    }
  }, [hakimState, hakimAvatar, hakimThinkingAvatar, hakimRespondingAvatar, hakimListeningAvatar]);

  return (
    <>
      <div className={`fixed bottom-6 z-50 ${isRTL ? 'left-6' : 'right-6'}`}>
        {showGreeting && !isOpen && (
          <div
            className={`absolute bottom-24 ${isRTL ? 'left-0' : 'right-0'} animate-fade-up`}
            style={{ animationDuration: '0.3s' }}
          >
            <div className="bg-white dark:bg-gray-800 text-foreground rounded-2xl shadow-2xl px-5 py-3.5 text-base font-cairo font-bold border-2 border-[#1B93A4]/25 whitespace-nowrap">
              <div className="flex items-center gap-2.5">
                <span className="text-gray-800 dark:text-gray-100">{greetingText}</span>
              </div>
              <div className={`absolute bottom-[-7px] ${isRTL ? 'left-6' : 'right-6'} w-3.5 h-3.5 bg-white dark:bg-gray-800 border-b-2 border-r-2 border-[#1B93A4]/25 transform rotate-45`} />
            </div>
          </div>
        )}

        <button
          data-testid="hakim-toggle-btn"
          onClick={toggleOpen}
          className={`
            relative w-20 h-20 rounded-2xl overflow-hidden
            transition-all duration-500 hover:scale-110
            ring-2 ring-[#7C3AED]/30 ring-offset-2 ring-offset-white dark:ring-offset-gray-900
            ${stateGlow}
            ${breathe && hakimState === HakimState.IDLE && !isOpen ? 'animate-pulse-slow' : ''}
          `}
          style={{ animationDuration: '3s' }}
        >
          {isOpen ? (
            <div className="w-full h-full bg-gradient-to-br from-[#7C3AED] to-[#1B93A4] flex items-center justify-center">
              <ChevronDown className="h-7 w-7 text-white" />
            </div>
          ) : (
            <img
              src={currentAvatar}
              alt="حكيم"
              className="w-full h-full object-contain bg-gradient-to-br from-[#7C3AED]/10 to-[#1B93A4]/10"
            />
          )}
          {hakimState === HakimState.THINKING && (
            <div className="absolute inset-0 rounded-full border-2 border-[#7C3AED] border-t-transparent animate-spin" />
          )}
        </button>
      </div>

      {isOpen && (
        <Card
          data-testid="hakim-chat-window"
          className={`
            fixed bottom-28 z-50 w-[440px] max-w-[calc(100vw-2rem)] h-[600px] max-h-[calc(100vh-8rem)]
            rounded-2xl shadow-2xl border-0 overflow-hidden flex flex-col
            animate-fade-up
            ${isRTL ? 'left-6' : 'right-6'}
          `}
          style={{ animationDuration: '0.25s' }}
        >
          <div className="bg-gradient-to-r from-[#7C3AED] via-[#6D28D9] to-[#1B93A4] p-4 flex items-center gap-3.5 shrink-0">
            <div className="relative">
              <div className="w-16 h-16 rounded-xl bg-white/20 overflow-hidden flex-shrink-0 ring-2 ring-white/30 p-0.5">
                <img src={currentAvatar} alt="حكيم" className="w-full h-full object-contain" />
              </div>
              <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-[#7C3AED] ${
                hakimState === HakimState.THINKING ? 'bg-amber-400 animate-pulse' :
                hakimState === HakimState.RESPONDING ? 'bg-[#1B93A4] animate-pulse' :
                'bg-emerald-400'
              }`} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-cairo font-bold text-white text-base leading-tight">حكيم</h3>
              <p className="text-white/80 text-sm mt-0.5">
                {hakimState === HakimState.THINKING ? '⏳ يفكر...' :
                 hakimState === HakimState.RESPONDING ? '💬 يجيب...' :
                 '🟢 المساعد الذكي'}
              </p>
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="icon"
                onClick={clearChat}
                className="text-white/60 hover:text-white hover:bg-white/15 h-9 w-9"
                title="مسح المحادثة"
              >
                <Trash2 className="h-[18px] w-[18px]" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsOpen(false)}
                className="text-white/60 hover:text-white hover:bg-white/15 h-9 w-9"
              >
                <X className="h-[18px] w-[18px]" />
              </Button>
            </div>
          </div>

          <ScrollArea className="flex-1 min-h-0">
            <div className="p-4 space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#7C3AED]/15 to-[#1B93A4]/15 overflow-hidden flex-shrink-0 mt-0.5">
                      <img src={hakimAvatar} alt="حكيم" className="hakim-img w-full h-full object-contain" />
                    </div>
                  )}
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-gradient-to-br from-[#7C3AED] to-[#6D28D9] text-white rounded-br-md'
                        : 'bg-muted/60 dark:bg-muted/30 border border-border/40 rounded-bl-md'
                    }`}
                  >
                    {message.role === 'user' ? (
                      <p className="text-[15px] leading-relaxed">{message.content}</p>
                    ) : (
                      <div className="hakim-markdown text-foreground text-[15px] leading-relaxed">
                        <MarkdownMessage content={message.content} onNavigate={handleNavigate} />
                      </div>
                    )}

                    {message.suggestions && message.suggestions.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {message.suggestions.map((suggestion, idx) => (
                          <button
                            key={idx}
                            onClick={() => sendMessage(suggestion)}
                            disabled={loading}
                            className="text-sm bg-[#1B93A4]/10 text-[#1B93A4] hover:bg-[#1B93A4]/20 disabled:opacity-50 rounded-lg px-3 py-2 transition-all font-cairo font-medium border border-[#1B93A4]/15 hover:border-[#1B93A4]/30"
                          >
                            {suggestion}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex gap-3">
                  <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#7C3AED]/15 to-[#1B93A4]/15 overflow-hidden flex-shrink-0">
                    <img src={hakimThinkingAvatar} alt="حكيم" className="hakim-img w-full h-full object-contain" />
                  </div>
                  <div className="bg-muted/60 dark:bg-muted/30 border border-border/40 rounded-2xl rounded-bl-md px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2.5 h-2.5 rounded-full bg-[#1B93A4] animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2.5 h-2.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-sm text-muted-foreground font-cairo font-medium">حكيم يفكر...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          <form onSubmit={handleSubmit} className="p-4 border-t bg-background/80 backdrop-blur-sm shrink-0">
            <div className="flex gap-2.5">
              <Input
                ref={inputRef}
                data-testid="hakim-input"
                value={input}
                onChange={(e) => { setInput(e.target.value); setHakimState(e.target.value ? HakimState.LISTENING : HakimState.IDLE); }}
                onFocus={handleUserInteraction}
                placeholder={t('askHakim')}
                className="flex-1 rounded-xl text-[15px] h-12 border-border/50 focus:border-[#1B93A4] focus:ring-[#1B93A4]/20"
                disabled={loading}
              />
              <Button
                type="submit"
                size="icon"
                disabled={loading || !input.trim()}
                className="bg-gradient-to-r from-[#7C3AED] to-[#1B93A4] hover:from-[#6D28D9] hover:to-[#157a89] rounded-xl h-12 w-12 shrink-0 transition-all disabled:opacity-40"
                data-testid="hakim-send-btn"
              >
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <style>{`
        @keyframes pulse-slow {
          0%, 100% { transform: scale(1); box-shadow: 0 4px 15px rgba(124,58,237,0.3); }
          50% { transform: scale(1.03); box-shadow: 0 4px 20px rgba(27,147,164,0.4); }
        }
        .animate-pulse-slow { animation: pulse-slow 3s ease-in-out infinite; }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-up { animation: fade-up 0.25s ease-out; }
      `}</style>
    </>
  );
};

export const HakimAssistant = () => {
  const { isRTL } = useAuth();
  return (
    <SectionErrorBoundary name="HakimAssistant" isRTL={isRTL}>
      <HakimAssistantInner />
    </SectionErrorBoundary>
  );
};
