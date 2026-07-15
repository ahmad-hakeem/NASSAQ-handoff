/**
 * Parent Portal — Hakim Chat Widget
 *
 * Visually unified with the Admin/School `HakimAssistant` (gradient header,
 * gradient FAB, gradient suggestion chips, identical Markdown renderer).
 * Parent-specific behavior is preserved:
 *   - Binds to selected `childId` and passes it to the backend so the AI
 *     scopes data to that specific student.
 *   - Parent-context suggestion chips.
 *   - Parent subtitle and disclaimer copy.
 *
 * Single source of truth for chat: `POST /api/hakim/chat` (same endpoint as
 * the admin assistant). The backend enforces parent → linked-student access
 * control and refuses cross-student data.
 */
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ScrollArea } from '../ui/scroll-area';
import { Card } from '../ui/card';
import { X, Send, Loader2, ChevronDown, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getPose } from '../hakim/hakimPoses';

const HakimState = {
  IDLE: 'idle',
  LISTENING: 'listening',
  THINKING: 'thinking',
  RESPONDING: 'responding',
};

const PARENT_DEFAULT_SUGGESTIONS = [
  'كيف أداء ابني الدراسي؟',
  'هل يوجد غياب هذا الأسبوع؟',
  'لخص لي إشعارات المدرسة',
];

const MarkdownMessage = ({ content }) => {
  const components = useMemo(() => ({
    h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-2 text-foreground font-cairo">{children}</h1>,
    h2: ({ children }) => <h2 className="text-base font-bold mt-2.5 mb-1.5 text-foreground font-cairo">{children}</h2>,
    h3: ({ children }) => <h3 className="text-[15px] font-semibold mt-2 mb-1 text-foreground/90 font-cairo">{children}</h3>,
    p: ({ children }) => <p className="text-[15px] leading-relaxed mb-2 last:mb-0 text-foreground dark:text-gray-200">{children}</p>,
    ul: ({ children }) => <ul className="text-[15px] list-disc list-inside space-y-1 mb-2 ms-1">{children}</ul>,
    ol: ({ children }) => <ol className="text-[15px] list-decimal list-inside space-y-1 mb-2 ms-1">{children}</ol>,
    li: ({ children }) => <li className="text-[15px] leading-relaxed text-foreground dark:text-muted-foreground/50">{children}</li>,
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
  }), []);

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
};

// `raised` lifts the launcher above PortalLayout's mobile bottom nav
// (lg:hidden fixed bottom-0) so the two never overlap on small screens.
const HakimChatWidget = ({ childId, childName, raised = false }) => {
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();

  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [hakimState, setHakimState] = useState(HakimState.IDLE);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const timeoutRefs = useRef([]);
  const revealTimerRef = useRef(null);
  // Bumped on every reveal stop/reset so an already-scheduled typewriter tick
  // can detect it belongs to a stale thread and bail instead of patching the
  // newly reset/switched conversation.
  const revealGenRef = useRef(0);

  const hakimAvatar = useMemo(() => getPose('friendly-greeting'), []);
  const hakimListeningAvatar = useMemo(() => getPose('listening'), []);
  const hakimThinkingAvatar = useMemo(() => getPose('ai-thinking'), []);
  const hakimRespondingAvatar = useMemo(() => getPose('explaining-concept'), []);

  const trackTimeout = useCallback((fn, ms) => {
    const id = setTimeout(fn, ms);
    timeoutRefs.current.push(id);
    return id;
  }, []);

  // Stop any in-flight typewriter reveal and invalidate stale ticks.
  const stopReveal = useCallback(() => {
    if (revealTimerRef.current) { clearInterval(revealTimerRef.current); revealTimerRef.current = null; }
    revealGenRef.current += 1;
  }, []);

  useEffect(() => {
    return () => {
      timeoutRefs.current.forEach(clearTimeout);
      if (revealTimerRef.current) clearInterval(revealTimerRef.current);
    };
  }, []);

  const welcomeMessage = useMemo(() => {
    const childPart = childName ? ` بخصوص **${childName}**` : '';
    return `مرحباً! أنا **حكيم**، مساعدك الذكي في منصة **نَسَّق** 🌟\n\nكيف يمكنني مساعدتك${childPart}؟`;
  }, [childName]);

  // Reset thread when the selected child changes so context never bleeds.
  useEffect(() => {
    stopReveal();
    setLoading(false);
    setHakimState(HakimState.IDLE);
    setMessages([{
      role: 'assistant',
      content: welcomeMessage,
      suggestions: PARENT_DEFAULT_SUGGESTIONS,
    }]);
  }, [childId, welcomeMessage, stopReveal]);

  useEffect(() => {
    trackTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }, [messages, trackTimeout]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      trackTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen, trackTimeout]);

  const sendMessage = async (text) => {
    const msg = (text || '').trim();
    if (!msg || loading) return;

    setMessages((prev) => [...prev, { role: 'user', content: msg }]);
    setInput('');
    setLoading(true);
    setHakimState(HakimState.THINKING);

    try {
      const res = await api.post('/hakim/chat', {
        message: msg,
        context: 'parent_portal',
        user_role: 'parent',
        tenant_id: user?.tenant_id,
        child_id: childId || null,
        conversation_history: messages.slice(-10).map((m) => ({
          role: m.role,
          content: m.content,
        })),
      });

      // The AI provider returns the whole reply at once, so reveal it with a
      // steady typewriter pace for a progressive, ChatGPT-style feel. Input
      // stays disabled (loading) until the reveal completes.
      setHakimState(HakimState.RESPONDING);
      const reply = res?.data?.response || res?.data?.message || 'لم أتمكن من الإجابة في الوقت الحالي. حاول مرة أخرى من فضلك.';
      const suggestions = res?.data?.suggestions || PARENT_DEFAULT_SUGGESTIONS;

      // Push an empty assistant bubble, then progressively fill it.
      setMessages((prev) => [...prev, { role: 'assistant', content: '', suggestions: [] }]);

      const updateLastAssistant = (patch) => {
        setMessages((prev) => {
          const next = [...prev];
          for (let k = next.length - 1; k >= 0; k--) {
            if (next[k].role === 'assistant') { next[k] = { ...next[k], ...patch }; break; }
          }
          return next;
        });
      };

      const step = Math.max(2, Math.ceil(reply.length / 280));
      let shown = 0;
      stopReveal();
      const myGen = revealGenRef.current;
      const timerId = setInterval(() => {
        // Bail if the thread was reset/closed/switched mid-reveal so a stale
        // tick never patches the wrong (new) assistant message.
        if (revealGenRef.current !== myGen) { clearInterval(timerId); return; }
        shown += step;
        if (shown >= reply.length) {
          clearInterval(timerId);
          if (revealTimerRef.current === timerId) revealTimerRef.current = null;
          updateLastAssistant({ content: reply, suggestions });
          trackTimeout(() => setHakimState(HakimState.IDLE), 1000);
          setLoading(false);
          return;
        }
        updateLastAssistant({ content: reply.slice(0, shown) });
      }, 18);
      revealTimerRef.current = timerId;
    } catch (err) {
      const status = err?.response?.status;
      let friendly;
      if (status === 403) {
        friendly = '⚠️ لا يمكنني الوصول إلى بيانات هذا الطالب. يُسمح لي فقط بمناقشة أبنائك المرتبطين بحسابك.';
      } else if (status === 503) {
        friendly = '⚠️ خدمة المساعد الذكي غير متوفرة حالياً. يرجى المحاولة لاحقاً.';
      } else {
        friendly = '⚠️ تعذّر الاتصال بحكيم الآن. تحقق من الاتصال وحاول مرة أخرى.';
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: friendly, suggestions: [] }]);
      setHakimState(HakimState.IDLE);
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  const clearChat = () => {
    stopReveal();
    setLoading(false);
    setHakimState(HakimState.IDLE);
    setMessages([{
      role: 'assistant',
      content: welcomeMessage,
      suggestions: PARENT_DEFAULT_SUGGESTIONS,
    }]);
  };

  const closeChat = useCallback(() => {
    stopReveal();
    setLoading(false);
    setHakimState(HakimState.IDLE);
    setIsOpen(false);
  }, [stopReveal]);

  const toggleOpen = () => {
    if (isOpen) { closeChat(); return; }
    setIsOpen(true);
    setHakimState(HakimState.IDLE);
  };

  const stateGlow = useMemo(() => {
    switch (hakimState) {
      case HakimState.THINKING: return 'shadow-[0_0_20px_rgba(124,58,237,0.5)]';
      case HakimState.RESPONDING: return 'shadow-[0_0_20px_rgba(27,147,164,0.5)]';
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
      {/* Floating Action Button — identical visual language to admin HakimAssistant */}
      <div className={`fixed ${raised ? 'bottom-24 lg:bottom-6' : 'bottom-6'} end-6 z-40`}>
        <button
          data-testid="hakim-toggle-btn"
          onClick={toggleOpen}
          className={`
            relative w-14 h-14 rounded-2xl overflow-hidden
            transition-all duration-500 hover:scale-110
            ring-2 ring-[#7C3AED]/30 ring-offset-2 ring-offset-white dark:ring-offset-gray-900
            ${stateGlow}
            ${hakimState === HakimState.IDLE && !isOpen ? 'animate-pulse-slow' : ''}
          `}
          style={{ animationDuration: '3s' }}
          aria-label="حكيم — المساعد الذكي"
        >
          {isOpen ? (
            <div className="w-full h-full bg-gradient-to-br from-[#7C3AED] to-[#1B93A4] flex items-center justify-center">
              <ChevronDown className="h-6 w-6 text-white" />
            </div>
          ) : (
            <img
              src={currentAvatar}
              alt=""
              aria-hidden="true"
              className="w-full h-full object-contain bg-gradient-to-br from-[#7C3AED]/10 to-[#1B93A4]/10"
            />
          )}
          {hakimState === HakimState.THINKING && (
            <div className="absolute inset-0 rounded-full border-2 border-[#7C3AED] border-t-transparent animate-spin" />
          )}
        </button>
      </div>

      {/* Chat Window */}
      {isOpen && (
        <Card
          data-testid="hakim-chat-window"
          className={`
            fixed ${raised ? 'bottom-40 lg:bottom-24' : 'bottom-24'} end-6 z-50 w-[440px] max-w-[calc(100vw-2rem)] h-[600px] max-h-[calc(100vh-8rem)]
            rounded-2xl shadow-2xl border-0 overflow-hidden flex flex-col
            animate-fade-up
          `}
          style={{ animationDuration: '0.25s' }}
          dir={isRTL ? 'rtl' : 'ltr'}
        >
          {/* Gradient Header — matches admin */}
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
                 'المساعد الذكي لولي الأمر'}
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
                onClick={closeChat}
                className="text-white/60 hover:text-white hover:bg-white/15 h-9 w-9"
              >
                <X className="h-[18px] w-[18px]" />
              </Button>
            </div>
          </div>

          {/* Messages */}
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
                        <MarkdownMessage content={message.content} />
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

              {loading && hakimState === HakimState.THINKING && (
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

          {/* Composer */}
          <form onSubmit={handleSubmit} className="p-4 border-t bg-background/80 backdrop-blur-sm shrink-0">
            <div className="flex gap-2.5">
              <Input
                ref={inputRef}
                data-testid="hakim-input"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setHakimState(e.target.value ? HakimState.LISTENING : HakimState.IDLE);
                }}
                placeholder={t('askHakim') || 'اسأل حكيم...'}
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
              حكيم مساعد ذكاء اصطناعي وقد يخطئ. يرجى التحقق من إجاباته.
            </p>
          </form>
        </Card>
      )}

      <style>{`
        @keyframes pulse-slow {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.04); }
        }
        .animate-pulse-slow { animation: pulse-slow 3s ease-in-out infinite; }
      `}</style>
    </>
  );
};

export default HakimChatWidget;
