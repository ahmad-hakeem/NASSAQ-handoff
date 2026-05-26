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
  const scrollAreaRef = useRef(null);
  const viewportRef = useRef(null);
  const messageNodesRef = useRef(new Map());
  const followModeRef = useRef(true);
  const userScrollIntentRef = useRef(false);
  const streamAbortRef = useRef(null);
  const streamingIdRef = useRef(null);
  const [streamingId, setStreamingId] = useState(null);
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const { language } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const isPublic = !user;
  const locale = language === 'en' ? 'en' : 'ar';

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

  const defaultSuggestions = useMemo(() => {
    if (isPublic) {
      return [t('hakimPublicSuggestion1'), t('hakimPublicSuggestion2'), t('hakimPublicSuggestion3')];
    }
    return [t('hakimDefaultSuggestion1'), t('hakimDefaultSuggestion2'), t('hakimDefaultSuggestion3')];
  }, [t, isPublic]);

  const welcomeMessage = useMemo(() => {
    if (isPublic) {
      return t('hakimPublicWelcome');
    }
    const pageName = currentPageInfo?.name;
    const base = t('hakimWelcomeBase');
    const pageNote = pageName
      ? '\n\n' + t('hakimWelcomeOnPage', { page: pageName })
      : '\n\n' + t('hakimWelcomeGeneric');
    return base + pageNote;
  }, [currentPageInfo, t, isPublic]);

  useEffect(() => {
    setMessages((prev) => {
      // Initial mount, or only the welcome card is present (no user turns yet):
      // (re)hydrate the welcome + starter chips in the current locale so a
      // language toggle immediately swaps the visible starter content.
      if (prev.length === 0 || (prev.length === 1 && prev[0].role === 'assistant')) {
        return [{
          role: 'assistant',
          content: welcomeMessage,
          suggestions: currentPageInfo?.suggestions || defaultSuggestions,
        }];
      }
      return prev;
    });
  }, [welcomeMessage, currentPageInfo, defaultSuggestions]);

  useEffect(() => {
    const timeouts = timeoutRefs.current;
    const abortRef = streamAbortRef;
    return () => {
      timeouts.forEach(clearTimeout);
      if (abortRef.current) {
        try { abortRef.current.abort(); } catch (_) { /* noop */ }
        abortRef.current = null;
      }
    };
  }, []);

  const trackTimeout = useCallback((fn, ms) => {
    const id = setTimeout(fn, ms);
    timeoutRefs.current.push(id);
    return id;
  }, []);

  const getViewport = useCallback(() => {
    if (viewportRef.current) return viewportRef.current;
    const root = scrollAreaRef.current;
    if (!root) return null;
    const vp = root.querySelector('[data-radix-scroll-area-viewport]');
    viewportRef.current = vp;
    return vp;
  }, []);

  const isNearBottom = useCallback(() => {
    const vp = getViewport();
    if (!vp) return true;
    const threshold = 48;
    return vp.scrollHeight - vp.scrollTop - vp.clientHeight <= threshold;
  }, [getViewport]);

  const scrollToBottom = useCallback((behavior = 'auto') => {
    const vp = getViewport();
    if (!vp) return;
    vp.scrollTo({ top: vp.scrollHeight, behavior });
  }, [getViewport]);

  const scrollMessageToTop = useCallback((id) => {
    const vp = getViewport();
    const node = messageNodesRef.current.get(id);
    if (!vp || !node) return;
    const top = Math.max(0, node.offsetTop - 8);
    vp.scrollTo({ top, behavior: 'smooth' });
  }, [getViewport]);

  // Auto-follow the bottom edge of the in-flight assistant bubble only if it
  // would otherwise scroll past the viewport — preserves the top-anchor while
  // the bubble fits, and starts scrolling once the content outgrows it.
  const followInFlightIfNeeded = useCallback(() => {
    if (!followModeRef.current) return;
    const vp = getViewport();
    if (!vp) return;
    const id = streamingIdRef.current;
    const node = id ? messageNodesRef.current.get(id) : null;
    if (node) {
      const nodeBottom = node.offsetTop + node.offsetHeight;
      const viewportBottom = vp.scrollTop + vp.clientHeight;
      if (nodeBottom <= viewportBottom - 8) return;
    }
    vp.scrollTo({ top: vp.scrollHeight, behavior: 'auto' });
  }, [getViewport]);

  // Track whether the user is pinned to the bottom of the chat so we know
  // when to auto-follow streaming chunks vs. respect their scroll position.
  // We distinguish user-initiated scrolls from our own programmatic ones by
  // listening for the input events that precede a user scroll (wheel,
  // touchmove, keydown). Each such event sets a one-shot "intent" flag that
  // the next scroll event consumes — programmatic `scrollTo` calls don't
  // set this flag, so they never accidentally flip follow-mode off, but
  // even a single user wheel/swipe mid-stream is honored immediately.
  useEffect(() => {
    if (!isOpen) return undefined;
    const vp = getViewport();
    if (!vp) return undefined;
    const markIntent = () => { userScrollIntentRef.current = true; };
    const onScroll = () => {
      if (!userScrollIntentRef.current) return;
      userScrollIntentRef.current = false;
      followModeRef.current = isNearBottom();
    };
    vp.addEventListener('wheel', markIntent, { passive: true });
    vp.addEventListener('touchmove', markIntent, { passive: true });
    vp.addEventListener('keydown', markIntent);
    vp.addEventListener('scroll', onScroll, { passive: true });
    followModeRef.current = isNearBottom();
    return () => {
      vp.removeEventListener('wheel', markIntent);
      vp.removeEventListener('touchmove', markIntent);
      vp.removeEventListener('keydown', markIntent);
      vp.removeEventListener('scroll', onScroll);
    };
  }, [isOpen, getViewport, isNearBottom, messages.length]);

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
        const IDLE_GREETINGS = [
          t('hakimIdleGreeting1'),
          t('hakimIdleGreeting2'),
          t('hakimIdleGreeting3'),
          t('hakimIdleGreeting4'),
        ];
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
  }, [isOpen, dismissCount, trackTimeout, t]);

  const handleUserInteraction = useCallback(() => {
    lastInteractionRef.current = Date.now();
    setShowGreeting(false);
  }, []);

  const handleNavigate = useCallback((path) => {
    navigate(path);
    setIsOpen(false);
  }, [navigate]);

  const cancelInFlightStream = useCallback(() => {
    if (streamAbortRef.current) {
      try { streamAbortRef.current.abort(); } catch (_) { /* noop */ }
      streamAbortRef.current = null;
    }
  }, []);

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return;
    handleUserInteraction();
    cancelInFlightStream();

    const userMessage = { role: 'user', content: text };
    const historyForRequest = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setHakimState(HakimState.THINKING);
    // The user just sent a message — anchor them at the bottom so they see it
    // and so subsequent streaming auto-follows by default.
    followModeRef.current = true;
    trackTimeout(() => scrollToBottom('smooth'), 30);

    if (!isPublic) {
      // Authenticated flow is untouched — non-streaming.
      try {
        const response = await api.post('/hakim/chat', {
          message: text,
          context: null,
          user_role: user?.role,
          tenant_id: user?.tenant_id,
          current_page: location.pathname,
        });
        setHakimState(HakimState.RESPONDING);
        setMessages((prev) => [...prev, {
          role: 'assistant',
          content: response.data.response,
          suggestions: response.data.suggestions || [],
        }]);
        // Auth flow is non-streaming — keep the new assistant reply in view
        // by scrolling to bottom (matches the pre-streaming UX).
        trackTimeout(() => scrollToBottom('smooth'), 40);
        trackTimeout(() => setHakimState(HakimState.IDLE), 1000);
      } catch (error) {
        console.error('Hakim error:', error);
        setMessages((prev) => [...prev, {
          role: 'assistant', content: t('hakimError'), suggestions: [],
        }]);
        trackTimeout(() => scrollToBottom('smooth'), 40);
        setHakimState(HakimState.IDLE);
      } finally {
        setLoading(false);
      }
      return;
    }

    // Public/landing flow: stream chunks over fetch.
    const controller = new AbortController();
    streamAbortRef.current = controller;
    const assistantId = `a_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    let firstChunkSeen = false;

    const flipToStreaming = () => {
      if (firstChunkSeen) return;
      firstChunkSeen = true;
      streamingIdRef.current = assistantId;
      setStreamingId(assistantId);
      setHakimState(HakimState.RESPONDING);
      setMessages((prev) => [...prev, {
        id: assistantId, role: 'assistant', content: '', suggestions: [], streaming: true,
      }]);
      // Anchor the new bubble at the top of the viewport so the user reads
      // from the first line. We mark this as a programmatic scroll so the
      // scroll listener does NOT flip follow-mode off — if the user was
      // pinned to the bottom before sending, we keep auto-follow enabled
      // and `followInFlightIfNeeded` will start scrolling once the bubble
      // grows past the viewport.
      trackTimeout(() => scrollMessageToTop(assistantId), 40);
    };

    const appendChunk = (piece) => {
      if (!piece) return;
      flipToStreaming();
      setMessages((prev) => prev.map((m) => (
        m.id === assistantId ? { ...m, content: (m.content || '') + piece } : m
      )));
      trackTimeout(followInFlightIfNeeded, 0);
    };

    const cleanupStreamRefs = () => {
      streamingIdRef.current = null;
      setStreamingId(null);
      setLoading(false);
      setHakimState(HakimState.IDLE);
      if (streamAbortRef.current === controller) streamAbortRef.current = null;
    };

    const finalize = (suggestionList) => {
      setMessages((prev) => prev.map((m) => (
        m.id === assistantId
          ? { ...m, streaming: false, suggestions: suggestionList || [] }
          : m
      )));
      cleanupStreamRefs();
    };

    // Replace the in-flight bubble (if any) with the localized safe error.
    // Used for both stream errors / network drops and user-initiated aborts
    // so the user never sees a half-written, orphaned assistant message.
    const replaceWithSafeError = () => {
      if (firstChunkSeen) {
        setMessages((prev) => prev.map((m) => (
          m.id === assistantId
            ? { ...m, content: t('hakimError'), suggestions: [], streaming: false }
            : m
        )));
      } else {
        // No placeholder was ever added (no chunk arrived). For non-abort
        // failures, append a fresh error bubble so the user gets feedback;
        // for clean aborts (close/clear/new-send before any token) there
        // is nothing visible to replace, so the caller can skip this.
        setMessages((prev) => [...prev, {
          role: 'assistant', content: t('hakimError'), suggestions: [],
        }]);
      }
      cleanupStreamRefs();
    };

    try {
      const baseURL = api?.defaults?.baseURL || '';
      const res = await fetch(`${baseURL}/public/hakim/chat/stream`, {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
        body: JSON.stringify({
          message: text,
          locale,
          conversation_history: historyForRequest,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`stream HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let suggestionsOut = [];
      let done = false;

      // Parse Server-Sent Events: each event is separated by a blank line
      // ("\n\n"). Each event has one or more `data: <payload>` lines whose
      // payloads are joined with "\n". We use SSE because HTTP proxies
      // (Replit's outer proxy, nginx, Cloudflare) buffer arbitrary
      // streamed bodies but pass `text/event-stream` through unbuffered.
      const parseSseEvent = (rawEvent) => {
        const dataLines = [];
        for (const rawLine of rawEvent.split('\n')) {
          const line = rawLine.replace(/\r$/, '');
          if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).replace(/^ /, ''));
          }
          // Other SSE fields (event:, id:, retry:) are ignored.
        }
        if (!dataLines.length) return null;
        const payload = dataLines.join('\n');
        try { return JSON.parse(payload); } catch (_) { return null; }
      };

      while (!done) {
        // eslint-disable-next-line no-await-in-loop
        const { value, done: streamDone } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });
        let sep;
        // SSE events end at the first "\n\n" (also tolerate "\r\n\r\n").
        while (true) {
          const lf = buffer.indexOf('\n\n');
          const crlf = buffer.indexOf('\r\n\r\n');
          if (lf === -1 && crlf === -1) break;
          let sepLen = 2;
          if (lf === -1) { sep = crlf; sepLen = 4; }
          else if (crlf === -1) { sep = lf; sepLen = 2; }
          else if (crlf < lf) { sep = crlf; sepLen = 4; }
          else { sep = lf; sepLen = 2; }

          const rawEvent = buffer.slice(0, sep);
          buffer = buffer.slice(sep + sepLen);
          const evt = parseSseEvent(rawEvent);
          if (!evt) continue;
          if (evt.type === 'chunk' && typeof evt.text === 'string') {
            appendChunk(evt.text);
          } else if (evt.type === 'error') {
            // Terminal error from backend (e.g. provider failure
            // mid-stream): replace the in-flight bubble with the
            // localized safe error so the user never sees an
            // orphaned partial answer.
            replaceWithSafeError();
            return;
          } else if (evt.type === 'done') {
            suggestionsOut = Array.isArray(evt.suggestions) ? evt.suggestions : [];
            done = true;
            break;
          }
        }
      }
      // Flush any tail in buffer (server may close without a trailing blank line)
      const tail = buffer.trim();
      if (tail) {
        const evt = parseSseEvent(tail);
        if (evt) {
          if (evt.type === 'chunk' && typeof evt.text === 'string') appendChunk(evt.text);
          else if (evt.type === 'error') { replaceWithSafeError(); return; }
          else if (evt.type === 'done' && Array.isArray(evt.suggestions)) suggestionsOut = evt.suggestions;
        }
      }

      if (!firstChunkSeen) {
        // Stream closed without any content — show the safe error.
        replaceWithSafeError();
        return;
      }
      finalize(suggestionsOut);
    } catch (error) {
      if (error?.name === 'AbortError') {
        // User cancelled (close / clear / new send): if we already painted
        // any tokens, replace that half-written bubble with the localized
        // safe error so the user never sees an orphaned partial message.
        // If nothing was shown yet, just clean up silently.
        if (firstChunkSeen) {
          replaceWithSafeError();
        } else {
          cleanupStreamRefs();
        }
        return;
      }
      console.error('Hakim stream error:', error);
      replaceWithSafeError();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const clearChat = useCallback(() => {
    cancelInFlightStream();
    streamingIdRef.current = null;
    setStreamingId(null);
    setLoading(false);
    messageNodesRef.current.clear();
    setMessages([{
      role: 'assistant',
      content: welcomeMessage,
      suggestions: currentPageInfo?.suggestions || defaultSuggestions,
    }]);
  }, [welcomeMessage, currentPageInfo, defaultSuggestions, cancelInFlightStream]);

  const closeChat = useCallback(() => {
    // Single close path — every dismiss (launcher toggle, header X, etc.)
    // must cancel any in-flight stream so the user isn't billed for an
    // answer they won't see and so the next open isn't haunted by a stale
    // streaming bubble.
    cancelInFlightStream();
    setShowGreeting(false);
    setDismissCount(prev => prev + 1);
    setIsOpen(false);
  }, [cancelInFlightStream]);

  const toggleOpen = () => {
    handleUserInteraction();
    if (isOpen) {
      closeChat();
      return;
    }
    setShowGreeting(false);
    setDismissCount(0);
    setIsOpen(true);
    setHakimState(HakimState.IDLE);
    hakimEngine.fireEvent(SYSTEM_EVENTS.HELP_REQUESTED);
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
              alt={t("hakimAvatarAlt")}
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
                <img src={currentAvatar} alt={t("hakimAvatarAlt")} className="w-full h-full object-contain" />
              </div>
              <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-[#7C3AED] ${
                hakimState === HakimState.THINKING ? 'bg-amber-400 animate-pulse' :
                hakimState === HakimState.RESPONDING ? 'bg-[#1B93A4] animate-pulse' :
                'bg-emerald-400'
              }`} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-cairo font-bold text-white text-base leading-tight">{t('hakimName')}</h3>
              <p className="text-white/80 text-sm mt-0.5">
                {hakimState === HakimState.THINKING ? `⏳ ${t('hakimThinking')}` :
                 hakimState === HakimState.RESPONDING ? `💬 ${t('hakimResponding')}` :
                 `🟢 ${t('hakimSmartAssistant')}`}
              </p>
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                variant="ghost"
                size="icon"
                onClick={clearChat}
                className="text-white/60 hover:text-white hover:bg-white/15 h-9 w-9"
                title={t('hakimClearChat')}
              >
                <Trash2 className="h-[18px] w-[18px]" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={closeChat}
                className="text-white/60 hover:text-white hover:bg-white/15 h-9 w-9"
              >
                <X className="h-[18px] w-[18px]" />
              </Button>
            </div>
          </div>

          <ScrollArea ref={scrollAreaRef} className="flex-1 min-h-0">
            <div className="p-4 space-y-4">
              {messages.map((message, index) => (
                <div
                  key={message.id || index}
                  ref={(el) => {
                    if (!message.id) return;
                    if (el) messageNodesRef.current.set(message.id, el);
                    else messageNodesRef.current.delete(message.id);
                  }}
                  className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  {message.role === 'assistant' && (
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#7C3AED]/15 to-[#1B93A4]/15 overflow-hidden flex-shrink-0 mt-0.5">
                      <img src={hakimAvatar} alt={t("hakimAvatarAlt")} className="hakim-img w-full h-full object-contain" />
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

              {loading && !streamingId && (
                <div className="flex gap-3">
                  <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#7C3AED]/15 to-[#1B93A4]/15 overflow-hidden flex-shrink-0">
                    <img src={hakimThinkingAvatar} alt={t("hakimAvatarAlt")} className="hakim-img w-full h-full object-contain" />
                  </div>
                  <div className="bg-muted/60 dark:bg-muted/30 border border-border/40 rounded-2xl rounded-bl-md px-5 py-3.5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2.5 h-2.5 rounded-full bg-[#1B93A4] animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2.5 h-2.5 rounded-full bg-[#7C3AED] animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-sm text-muted-foreground font-cairo font-medium">{t('hakimThinkingDetailed')}</span>
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
            <p className="mt-2 text-[11px] leading-tight text-center text-muted-foreground/70 font-cairo select-none">
              {t('hakimDisclaimer')}
            </p>
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
