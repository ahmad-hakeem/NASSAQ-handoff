import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { MessageCircle, X, Send, Loader2, Bot, User } from 'lucide-react';

const formatMarkdown = (text) => {
  if (!text) return text;
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/^## (.+)$/gm, '<h4 class="font-bold text-sm mt-2 mb-1">$1</h4>');
  html = html.replace(/^### (.+)$/gm, '<h5 class="font-semibold text-xs mt-1.5 mb-0.5">$1</h5>');
  html = html.replace(/^- (.+)$/gm, '<li class="mr-3 text-sm">$1</li>');
  html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, (match) => `<ul class="list-disc mr-4 space-y-0.5">${match}</ul>`);
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="mr-3 text-sm list-decimal">$1</li>');
  html = html.replace(/\n{2,}/g, '<br/><br/>');
  html = html.replace(/\n/g, '<br/>');

  return html;
};

const HakimChatWidget = ({ childId, childName }) => {
  const { api } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: `مرحباً! أنا حكيم، المساعد الذكي. كيف يمكنني مساعدتك بخصوص ${childName || 'الطالب'}؟` }
  ]);
  const [suggestions, setSuggestions] = useState([
    'كيف أداء ابني الدراسي؟',
    'ما نقاط القوة والضعف؟',
    'نصائح للمتابعة المنزلية'
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const welcomeMessage = useMemo(() =>
    `مرحباً! أنا حكيم، المساعد الذكي. كيف يمكنني مساعدتك بخصوص ${childName || 'الطالب'}؟`,
    [childName]
  );

  useEffect(() => {
    setMessages([{ role: 'assistant', content: welcomeMessage }]);
    setSuggestions([
      'كيف أداء ابني الدراسي؟',
      'ما نقاط القوة والضعف؟',
      'نصائح للمتابعة المنزلية'
    ]);
  }, [childId, welcomeMessage]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const sendMessage = async (text) => {
    const msg = (text || input).trim();
    if (!msg || sending) return;

    setInput('');
    setSuggestions([]);
    setMessages(prev => [...prev, { role: 'user', content: msg }]);
    setSending(true);

    try {
      const res = await api.post('/hakim/chat', {
        message: msg,
        context: 'parent_portal',
        user_role: 'parent',
        child_id: childId,
        conversation_history: messages.slice(-10).map(m => ({
          role: m.role,
          content: m.content
        }))
      });
      const reply = res.data?.response || res.data?.message || 'عذراً، لم أتمكن من الإجابة حالياً.';
      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
      if (res.data?.suggestions?.length) {
        setSuggestions(res.data.suggestions);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'عذراً، حدث خطأ. يرجى المحاولة مرة أخرى.' }]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-20 left-4 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-brand-turquoise to-brand-navy text-white shadow-lg shadow-brand-turquoise/30 flex items-center justify-center hover:scale-105 transition-transform"
        aria-label="حكيم"
      >
        {isOpen ? <X className="w-6 h-6" /> : (
          <div className="relative">
            <MessageCircle className="w-6 h-6" />
            <span className="absolute -top-1 -right-1 text-[8px] font-bold">حكيم</span>
          </div>
        )}
      </button>

      {isOpen && (
        <div className="fixed bottom-36 left-4 z-50 w-80 sm:w-96 h-[32rem] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden" dir="rtl">
          <div className="bg-gradient-to-r from-brand-turquoise to-brand-navy p-4 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-sm">حكيم</h4>
                  <p className="text-xs opacity-80">المساعد الذكي لولي الأمر</p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded-lg hover:bg-white/20 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-gray-50">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                  msg.role === 'user' ? 'bg-brand-navy/15 text-brand-navy' : 'bg-brand-turquoise/15 text-brand-turquoise'
                }`}>
                  {msg.role === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                </div>
                {msg.role === 'user' ? (
                  <div className="max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed bg-brand-navy text-white rounded-br-sm">
                    {msg.content}
                  </div>
                ) : (
                  <div
                    className="max-w-[80%] px-3 py-2 rounded-2xl text-sm leading-relaxed bg-white text-gray-800 border border-gray-200 rounded-bl-sm hakim-msg"
                    dangerouslySetInnerHTML={{ __html: formatMarkdown(msg.content) }}
                  />
                )}
              </div>
            ))}
            {sending && (
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full bg-brand-turquoise/15 text-brand-turquoise flex items-center justify-center">
                  <Bot className="w-3.5 h-3.5" />
                </div>
                <div className="bg-white border border-gray-200 px-4 py-2 rounded-2xl rounded-bl-sm flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                  <span className="text-xs text-gray-400">حكيم يفكر...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {suggestions.length > 0 && !sending && (
            <div className="px-3 py-2 border-t border-gray-100 bg-gray-50 flex gap-1.5 overflow-x-auto">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(s)}
                  className="shrink-0 px-2.5 py-1 rounded-lg bg-brand-turquoise/10 text-brand-navy text-xs font-medium hover:bg-brand-turquoise/20 transition-colors border border-brand-turquoise/20"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="p-3 border-t border-gray-200 bg-white">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="اسأل حكيم عن أداء ابنك..."
                className="flex-1 px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-navy focus:border-transparent"
                disabled={sending}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || sending}
                className="w-9 h-9 rounded-xl bg-brand-navy text-white flex items-center justify-center hover:bg-brand-navy-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default HakimChatWidget;
