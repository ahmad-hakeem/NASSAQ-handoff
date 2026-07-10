import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { NotificationsPage } from '../NotificationsPage';
import ParentAbsenceExcusePage from './ParentAbsenceExcusePage';
import {
  MessageSquare, FileText, Inbox, Send, AlertCircle,
  CheckCircle, Clock, ArrowUpRight, ArrowDownLeft, Loader2,
  Bell
} from 'lucide-react';

const OUTER_TABS = ['messages', 'notifications', 'excuses'];

const ParentCommunicationCenter = () => {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const outerTab = OUTER_TABS.includes(tabParam) ? tabParam : 'messages';
  const setOuterTab = (id) => {
    const next = new URLSearchParams(searchParams);
    if (id === 'messages') next.delete('tab');
    else next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  const [activeTab, setActiveTab] = useState('send');
  const [requestsCount, setRequestsCount] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  const [msgType, setMsgType] = useState('note');
  const [recipient, setRecipient] = useState('teacher');
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [teacherRecipients, setTeacherRecipients] = useState([]);
  const [selectedTeacherUserId, setSelectedTeacherUserId] = useState('');
  const [children, setChildren] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState('');

  const TABS = [
    { id: 'send', label: t('sendMessage'), icon: Send },
    { id: 'inbox', label: t('conversationInbox'), icon: Inbox },
  ];

  const OUTER_TAB_CONFIG = useMemo(() => ([
    { id: 'messages', label: t('messages') || (isRTL ? 'الرسائل' : 'Messages'), icon: MessageSquare },
    { id: 'notifications', label: t('notifications') || (isRTL ? 'الإشعارات' : 'Notifications'), icon: Bell },
    { id: 'excuses', label: t('absenceExcuse') || (isRTL ? 'عذر غياب' : 'Absence Excuse'), icon: FileText },
  ]), [t, isRTL]);

  const MESSAGE_TYPES = [
    { id: 'note', label: t('messageTypeNote') },
    { id: 'suggestion', label: t('messageTypeSuggestion') },
    { id: 'inquiry', label: t('messageTypeInquiry') },
  ];

  const RECIPIENT_TYPES = [
    { id: 'teacher', label: t('recipientTeacher') },
    { id: 'admin', label: t('recipientAdmin') },
  ];

  useEffect(() => {
    const init = async () => {
      try {
        const [countRes, msgRes, teachersRes] = await Promise.all([
          api.get('/parent-portal/open-requests-count'),
          api.get('/parent-portal/messages'),
          api.get('/parent-portal/message-recipients/teachers').catch(() => ({ data: { teachers: [], children: [] } })),
        ]);
        setRequestsCount(countRes.data);
        setMessages(msgRes.data?.messages || []);
        setTeacherRecipients(teachersRes.data?.teachers || []);
        const kids = teachersRes.data?.children || [];
        setChildren(kids);
        if (kids.length === 1) {
          setSelectedStudentId(kids[0].student_id);
        }
      } catch {
        nassaqError(t('errorFetchingData'));
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [api, nassaqError, t]);

  useEffect(() => {
    if (recipient !== 'teacher') {
      setSelectedTeacherUserId('');
    }
  }, [recipient]);

  // The teacher list is child-specific: changing the child invalidates the
  // previously selected teacher.
  useEffect(() => {
    setSelectedTeacherUserId('');
  }, [selectedStudentId]);

  const childTeachers = useMemo(
    () => teacherRecipients.filter(
      tr => (tr.child_ids || []).includes(selectedStudentId)
    ),
    [teacherRecipients, selectedStudentId]
  );

  const refreshRequestCount = async () => {
    try {
      const countRes = await api.get('/parent-portal/open-requests-count');
      setRequestsCount(countRes.data);
    } catch {}
  };

  const refreshInbox = async () => {
    try {
      const msgRes = await api.get('/parent-portal/messages');
      setMessages(msgRes.data?.messages || []);
    } catch {}
  };

  const handleSendMessage = async () => {
    if (!msgText.trim()) return;
    if (!selectedStudentId) {
      nassaqError(t('selectChildLabel'));
      return;
    }
    if (recipient === 'teacher' && !selectedTeacherUserId) {
      nassaqError(t('selectTeacherRecipient'));
      return;
    }
    setSending(true);
    try {
      const body = {
        message_type: msgType,
        recipient_type: recipient,
        content: msgText.trim(),
        student_id: selectedStudentId,
      };
      if (recipient === 'teacher') {
        body.recipient_user_id = selectedTeacherUserId;
      }
      await api.post('/parent-portal/quick-message', body);
      setMsgText('');
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 5000);
      await Promise.all([refreshRequestCount(), refreshInbox()]);
    } catch (err) {
      nassaqError(t('errorSendingMessage'));
    } finally {
      setSending(false);
    }
  };

  const getStatusBadge = (msg) => {
    if (msg.status === 'replied') {
      return { label: t('replied'), className: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' };
    }
    if (msg.status === 'pending' || msg.status === 'sent' || msg.status === 'open') {
      return { label: t('underReview'), className: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300' };
    }
    if (msg.status === 'closed') {
      return { label: t('closed'), className: 'bg-muted/40 text-muted-foreground' };
    }
    return { label: msg.status || t('sentStatus'), className: 'bg-muted/40 text-muted-foreground' };
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4 max-w-lg mx-auto">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const messagesUnread = messages.filter(m => !m.read_status && !m.is_sent).length;

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-5xl mx-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-navy to-brand-purple flex items-center justify-center">
            <MessageSquare className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground dark:text-gray-100 font-cairo">
              {t('communicationCenter')}
            </h1>
            <p className="text-xs text-muted-foreground dark:text-muted-foreground">
              {t('communicationCenterDesc')}
            </p>
          </div>
        </div>

        <div
          role="tablist"
          aria-label={t('communicationCenter')}
          className="flex gap-2 overflow-x-auto pb-1 border-b border-border dark:border-gray-700"
        >
          {OUTER_TAB_CONFIG.map(tab => {
            const Icon = tab.icon;
            const isActive = outerTab === tab.id;
            const badge = tab.id === 'messages' && messagesUnread > 0 ? messagesUnread : 0;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setOuterTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-t-xl text-sm font-medium whitespace-nowrap transition-all border-b-2 ${
                  isActive
                    ? 'border-brand-navy text-brand-navy dark:text-brand-turquoise bg-brand-navy/5 dark:bg-brand-navy/20'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {badge > 0 && (
                  <span className="min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold bg-red-500 text-white flex items-center justify-center">
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {outerTab === 'messages' && (
        <div className="space-y-4 max-w-lg mx-auto">
        {requestsCount && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-navy/5 dark:bg-brand-navy/20 border border-brand-navy/10 dark:border-brand-navy/30">
            <AlertCircle className="w-4 h-4 text-brand-navy shrink-0" />
            <p className="text-xs text-brand-navy dark:text-brand-navy/80">
              {t('openRequestsCount').replace('{count}', requestsCount.total_open)}
            </p>
          </div>
        )}

        <div className="flex gap-2 overflow-x-auto pb-1">
          {TABS.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            const unreadCount = tab.id === 'inbox' ? messages.filter(m => !m.read_status && !m.is_sent).length : 0;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium whitespace-nowrap transition-all ${
                  isActive
                    ? 'bg-brand-navy text-white shadow-md shadow-brand-navy/15 dark:shadow-brand-navy/30'
                    : 'bg-white dark:bg-gray-800 text-muted-foreground dark:text-muted-foreground/50 border border-border dark:border-gray-700 hover:border-brand-navy/30 dark:hover:border-brand-navy/40'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {unreadCount > 0 && (
                  <span className={`w-5 h-5 rounded-full text-[10px] flex items-center justify-center font-bold ${
                    isActive ? 'bg-white dark:bg-card text-brand-navy' : 'bg-red-500 text-white'
                  }`}>
                    {unreadCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {activeTab === 'send' && (
          <>
            {showSuccess && (
              <div className="flex items-center gap-3 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 text-sm animate-in fade-in slide-in-from-top-2">
                <CheckCircle className="w-5 h-5 shrink-0" />
                <p className="font-cairo font-medium">{t('messageReceivedConfirmation')}</p>
              </div>
            )}

            <Card className="rounded-2xl border-0 shadow-sm">
              <div className="h-1 bg-gradient-to-r from-brand-navy to-brand-purple rounded-t-2xl" />
              <CardContent className="p-4 space-y-4">
                <div>
                  <p className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-2 font-cairo">
                    {t('selectChildLabel')}
                  </p>
                  {children.length === 0 ? (
                    <p className="text-xs text-muted-foreground font-cairo px-1">
                      {t('noChildrenLinked')}
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {children.map(child => (
                        <button
                          key={child.student_id}
                          onClick={() => setSelectedStudentId(child.student_id)}
                          className={`px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                            selectedStudentId === child.student_id
                              ? 'bg-brand-navy/15 dark:bg-brand-navy/20 text-brand-navy dark:text-brand-navy/80 border border-brand-navy/30 dark:border-brand-navy/40 shadow-sm'
                              : 'bg-muted/40 dark:bg-gray-800 text-muted-foreground dark:text-muted-foreground border border-transparent hover:border-border dark:hover:border-gray-600'
                          }`}
                        >
                          {child.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <p className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-2 font-cairo">
                    {t('messageTypeLabel')}
                  </p>
                  <div className="flex gap-2">
                    {MESSAGE_TYPES.map(mt => (
                      <button
                        key={mt.id}
                        onClick={() => setMsgType(mt.id)}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all ${
                          msgType === mt.id
                            ? 'bg-brand-navy/15 dark:bg-brand-navy/20 text-brand-navy dark:text-brand-navy/80 border border-brand-navy/30 dark:border-brand-navy/40 shadow-sm'
                            : 'bg-muted/40 dark:bg-gray-800 text-muted-foreground dark:text-muted-foreground border border-transparent hover:border-border dark:hover:border-gray-600'
                        }`}
                      >
                        {mt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-2 font-cairo">
                    {t('recipientLabel')}
                  </p>
                  <div className="flex gap-2">
                    {RECIPIENT_TYPES.map(rt => (
                      <button
                        key={rt.id}
                        onClick={() => setRecipient(rt.id)}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all ${
                          recipient === rt.id
                            ? 'bg-brand-navy/15 dark:bg-brand-navy/20 text-brand-navy dark:text-brand-navy/80 border border-brand-navy/30 dark:border-brand-navy/40 shadow-sm'
                            : 'bg-muted/40 dark:bg-gray-800 text-muted-foreground dark:text-muted-foreground border border-transparent hover:border-border dark:hover:border-gray-600'
                        }`}
                      >
                        {rt.label}
                      </button>
                    ))}
                  </div>
                  {recipient === 'teacher' && (
                    !selectedStudentId ? (
                      <p className="mt-2 text-xs text-muted-foreground font-cairo px-1">
                        {t('selectChildFirstHint')}
                      </p>
                    ) : childTeachers.length === 0 ? (
                      <p className="mt-2 text-xs text-muted-foreground font-cairo px-1">
                        {t('noTeacherRecipientsAvailable')}
                      </p>
                    ) : (
                      <div className="mt-2">
                        <Select
                          value={selectedTeacherUserId}
                          onValueChange={setSelectedTeacherUserId}
                          dir={isRTL ? 'rtl' : 'ltr'}
                        >
                          <SelectTrigger className="w-full rounded-xl border border-border dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-brand-navy text-start">
                            <SelectValue placeholder={t('selectTeacherRecipient')} />
                          </SelectTrigger>
                          <SelectContent>
                            {childTeachers.map(tr => (
                              <SelectItem key={tr.recipient_user_id} value={tr.recipient_user_id}>
                                <span className="font-medium">{tr.teacher_name}</span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )
                  )}
                </div>

                <textarea
                  value={msgText}
                  onChange={e => setMsgText(e.target.value)}
                  placeholder={t('writeYourMessageHere')}
                  rows={4}
                  className="w-full px-3 py-2.5 rounded-xl border border-border dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-foreground dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand-navy resize-none placeholder:text-muted-foreground"
                />

                <button
                  onClick={handleSendMessage}
                  disabled={
                    !msgText.trim() || sending || !selectedStudentId ||
                    (recipient === 'teacher' && (childTeachers.length === 0 || !selectedTeacherUserId))
                  }
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-brand-navy to-brand-purple hover:from-brand-navy-dark hover:to-brand-purple text-white text-sm font-medium font-cairo disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-brand-navy/15 dark:shadow-brand-navy/30"
                >
                  {sending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                  {sending ? t('sendingMessage') : t('sendMessage')}
                </button>
              </CardContent>
            </Card>
          </>
        )}

        {activeTab === 'inbox' && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <div className="h-1 bg-gradient-to-r from-brand-navy to-brand-purple rounded-t-2xl" />
            <CardContent className="p-4">
              {messages.length === 0 ? (
                <div className="text-center py-10">
                  <Inbox className="w-12 h-12 mx-auto mb-3 text-muted-foreground/50 dark:text-muted-foreground" />
                  <p className="text-sm text-muted-foreground dark:text-muted-foreground font-cairo">
                    {t('noConversations')}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {messages.map((msg, i) => {
                    const isRead = msg.read_status || msg.is_sent;
                    const statusBadge = getStatusBadge(msg);
                    return (
                      <div
                        key={msg.id || i}
                        className={`p-3.5 rounded-xl border transition-all ${
                          isRead
                            ? 'bg-white dark:bg-gray-800 border-border dark:border-gray-700'
                            : 'bg-brand-navy/5 dark:bg-brand-navy/20 border-brand-navy/20 dark:border-brand-navy/30'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                            msg.is_sent
                              ? 'bg-blue-100 dark:bg-blue-900/30'
                              : 'bg-green-100 dark:bg-green-900/30'
                          }`}>
                            {msg.is_sent ? (
                              <ArrowUpRight className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                            ) : (
                              <ArrowDownLeft className="h-4 w-4 text-green-600 dark:text-green-400" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-sm font-medium text-foreground dark:text-gray-200 truncate">
                                {msg.is_sent
                                  ? t('toRecipient').replace('{name}', msg.receiver_name || t('recipientAdmin'))
                                  : t('fromSender').replace('{name}', msg.sender_name || '')}
                              </p>
                              <div className="flex items-center gap-1.5 shrink-0">
                                {!isRead && (
                                  <Badge className="bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400 border-0 text-[10px] px-1.5">
                                    {t('newMessage')}
                                  </Badge>
                                )}
                              </div>
                            </div>
                            {msg.student_name && (
                              <Badge className="mb-1 bg-brand-navy/10 dark:bg-brand-navy/25 text-brand-navy dark:text-brand-turquoise border-0 text-[10px] px-1.5">
                                {t('regardingStudent').replace('{name}', msg.student_name)}
                              </Badge>
                            )}
                            <p className="text-sm text-foreground dark:text-muted-foreground/50 line-clamp-2 mb-1.5">
                              {msg.content || msg.message || msg.subject}
                            </p>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Clock className="h-3 w-3" />
                                <span>
                                  {msg.created_at
                                    ? new Date(msg.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', {
                                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                      })
                                    : ''}
                                </span>
                              </div>
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${statusBadge.className}`}>
                                {statusBadge.label}
                              </span>
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
        )}
        </div>
        )}

        {outerTab === 'notifications' && (
          <div className="-mx-1">
            <NotificationsPage embedded />
          </div>
        )}

        {outerTab === 'excuses' && (
          <ParentAbsenceExcusePage embedded />
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentCommunicationCenter;
