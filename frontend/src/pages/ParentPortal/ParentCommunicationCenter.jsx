import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  MessageSquare, FileText, Inbox, Send, Upload, AlertCircle,
  CheckCircle, Clock, Lock, ArrowUpRight, ArrowDownLeft, Loader2
} from 'lucide-react';

const ParentCommunicationCenter = () => {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();
  const [activeTab, setActiveTab] = useState('send');
  const [requestsCount, setRequestsCount] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  const [msgType, setMsgType] = useState('note');
  const [recipient, setRecipient] = useState('teacher');
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const [excuseDesc, setExcuseDesc] = useState('');
  const [excuseFile, setExcuseFile] = useState(null);
  const [excuseFileName, setExcuseFileName] = useState('');
  const [excuseDate, setExcuseDate] = useState(new Date().toISOString().split('T')[0]);
  const [excuseChildId, setExcuseChildId] = useState('');
  const [sendingExcuse, setSendingExcuse] = useState(false);
  const [children, setChildren] = useState([]);
  const fileInputRef = React.useRef(null);

  const TABS = [
    { id: 'send', label: t('sendMessage'), icon: Send },
    { id: 'excuse', label: t('medicalExcuse'), icon: FileText },
    { id: 'inbox', label: t('conversationInbox'), icon: Inbox },
  ];

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
        const [countRes, msgRes, childRes] = await Promise.all([
          api.get('/parent-portal/open-requests-count'),
          api.get('/parent-portal/messages'),
          api.get('/parent-portal/children'),
        ]);
        setRequestsCount(countRes.data);
        setMessages(msgRes.data?.messages || []);
        const childList = childRes.data?.children || [];
        setChildren(childList);
        if (childList.length > 0) setExcuseChildId(childList[0].id);
      } catch {
        nassaqError(t('errorFetchingData'));
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [api, nassaqError, t]);

  const canSubmit = requestsCount?.can_submit !== false;

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
    if (!canSubmit) {
      nassaqError(t('maxOpenRequestsError'));
      return;
    }
    setSending(true);
    try {
      await api.post('/parent-portal/quick-message', {
        message_type: msgType,
        recipient_type: recipient,
        content: msgText.trim(),
      });
      setMsgText('');
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 5000);
      await Promise.all([refreshRequestCount(), refreshInbox()]);
    } catch (err) {
      if (err.response?.status === 429) {
        nassaqError(t('maxOpenRequestsError'));
        await refreshRequestCount();
      } else {
        nassaqError(t('errorSendingMessage'));
      }
    } finally {
      setSending(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setExcuseFile(file);
      setExcuseFileName(file.name);
    }
  };

  const clearFile = () => {
    setExcuseFile(null);
    setExcuseFileName('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSendExcuse = async () => {
    if (!excuseDesc.trim() || !excuseChildId) return;
    if (!canSubmit) {
      nassaqError(t('maxOpenRequestsError'));
      return;
    }
    setSendingExcuse(true);
    try {
      let attachmentUrl = undefined;
      let attachmentName = undefined;

      if (excuseFile) {
        const formData = new FormData();
        formData.append('file', excuseFile);
        const uploadRes = await api.post('/parent-portal/upload-attachment', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        attachmentUrl = uploadRes.data?.attachment_url;
        attachmentName = uploadRes.data?.attachment_name || excuseFileName;
      }

      await api.post('/parent-portal/absence-excuse', {
        child_id: excuseChildId,
        reason: excuseDesc.trim(),
        absence_date: excuseDate || new Date().toISOString().split('T')[0],
        attachment_url: attachmentUrl,
        attachment_name: attachmentName,
      });
      toast.success(t('excuseSentSuccess'));
      setExcuseDesc('');
      clearFile();
      setExcuseDate(new Date().toISOString().split('T')[0]);
      await refreshRequestCount();
    } catch (err) {
      if (err.response?.status === 429) {
        nassaqError(t('maxOpenRequestsError'));
        await refreshRequestCount();
      } else {
        nassaqError(t('errorSendingMessage'));
      }
    } finally {
      setSendingExcuse(false);
    }
  };

  const getStatusBadge = (msg) => {
    if (msg.status === 'replied') {
      return { label: t('replied'), className: 'bg-emerald-100 text-emerald-700' };
    }
    if (msg.status === 'pending' || msg.status === 'sent' || msg.status === 'open') {
      return { label: t('underReview'), className: 'bg-amber-100 text-amber-700' };
    }
    if (msg.status === 'closed') {
      return { label: t('closed'), className: 'bg-gray-100 text-gray-600' };
    }
    return { label: msg.status || t('sentStatus'), className: 'bg-gray-100 text-gray-600' };
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

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="flex items-center gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
            <MessageSquare className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-800 dark:text-gray-100 font-cairo">
              {t('communicationCenter')}
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {t('communicationCenterDesc')}
            </p>
          </div>
        </div>

        {!canSubmit && (
          <div className="flex items-start gap-3 p-3.5 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
            <Lock className="w-5 h-5 shrink-0 mt-0.5" />
            <p className="font-cairo leading-relaxed">
              {t('maxOpenRequestsReached').replace('{count}', requestsCount?.total_open || 3)}
            </p>
          </div>
        )}

        {requestsCount && canSubmit && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-100 dark:border-indigo-800">
            <AlertCircle className="w-4 h-4 text-indigo-500 shrink-0" />
            <p className="text-xs text-indigo-700 dark:text-indigo-300">
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
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200 dark:shadow-indigo-900/30'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-600'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
                {unreadCount > 0 && (
                  <span className={`w-5 h-5 rounded-full text-[10px] flex items-center justify-center font-bold ${
                    isActive ? 'bg-white text-indigo-600' : 'bg-red-500 text-white'
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
              <div className="h-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-t-2xl" />
              <CardContent className="p-4 space-y-4">
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 font-cairo">
                    {t('messageTypeLabel')}
                  </p>
                  <div className="flex gap-2">
                    {MESSAGE_TYPES.map(mt => (
                      <button
                        key={mt.id}
                        onClick={() => setMsgType(mt.id)}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all ${
                          msgType === mt.id
                            ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-700 shadow-sm'
                            : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-transparent hover:border-gray-200 dark:hover:border-gray-600'
                        }`}
                      >
                        {mt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 font-cairo">
                    {t('recipientLabel')}
                  </p>
                  <div className="flex gap-2">
                    {RECIPIENT_TYPES.map(rt => (
                      <button
                        key={rt.id}
                        onClick={() => setRecipient(rt.id)}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all ${
                          recipient === rt.id
                            ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-700 shadow-sm'
                            : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-transparent hover:border-gray-200 dark:hover:border-gray-600'
                        }`}
                      >
                        {rt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <textarea
                  value={msgText}
                  onChange={e => setMsgText(e.target.value)}
                  placeholder={t('writeYourMessageHere')}
                  rows={4}
                  className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none placeholder:text-gray-400"
                />

                <button
                  onClick={handleSendMessage}
                  disabled={!msgText.trim() || sending || !canSubmit}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-sm font-medium font-cairo disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-indigo-200 dark:shadow-indigo-900/30"
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

        {activeTab === 'excuse' && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <div className="h-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-t-2xl" />
            <CardContent className="p-4 space-y-4">
              {children.length > 1 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 font-cairo">
                    {t('selectStudent')}
                  </p>
                  <select
                    value={excuseChildId}
                    onChange={e => setExcuseChildId(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {children.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.full_name || c.name}
                        {c.class_name ? ` (${c.class_name})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 font-cairo">
                  {t('absenceDateLabel')}
                </p>
                <input
                  type="date"
                  value={excuseDate}
                  onChange={e => setExcuseDate(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 font-cairo">
                  {t('medicalExcuse')}
                </p>
                <textarea
                  value={excuseDesc}
                  onChange={e => setExcuseDesc(e.target.value)}
                  placeholder={t('medicalExcuseDesc')}
                  rows={3}
                  className="w-full px-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none placeholder:text-gray-400"
                />
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 font-cairo flex items-center gap-1.5">
                  <Upload className="w-3.5 h-3.5" />
                  {t('attachmentOptional')}
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                  onChange={handleFileChange}
                  className="hidden"
                  id="excuse-file-input"
                />
                {excuseFileName ? (
                  <div className="flex items-center gap-2 p-3 rounded-xl border border-indigo-200 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/20">
                    <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                    <span className="text-sm text-indigo-700 dark:text-indigo-300 truncate flex-1">{excuseFileName}</span>
                    <button
                      type="button"
                      onClick={clearFile}
                      className="text-gray-400 hover:text-red-500 transition-colors shrink-0"
                    >
                      <AlertCircle className="w-4 h-4" />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full flex items-center justify-center gap-2 p-3 rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-600 text-gray-500 dark:text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-all"
                  >
                    <Upload className="w-4 h-4" />
                    <span className="text-sm">{t('attachmentLink')}</span>
                  </button>
                )}
              </div>

              <button
                onClick={handleSendExcuse}
                disabled={!excuseDesc.trim() || !excuseChildId || sendingExcuse || !canSubmit}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white text-sm font-medium font-cairo disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-indigo-200 dark:shadow-indigo-900/30"
              >
                {sendingExcuse ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                {sendingExcuse ? t('sendingExcuse') : t('sendExcuse')}
              </button>
            </CardContent>
          </Card>
        )}

        {activeTab === 'inbox' && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <div className="h-1 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-t-2xl" />
            <CardContent className="p-4">
              {messages.length === 0 ? (
                <div className="text-center py-10">
                  <Inbox className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
                  <p className="text-sm text-gray-500 dark:text-gray-400 font-cairo">
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
                            ? 'bg-white dark:bg-gray-800 border-gray-100 dark:border-gray-700'
                            : 'bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800'
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
                              <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
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
                            <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2 mb-1.5">
                              {msg.content || msg.message || msg.subject}
                            </p>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1 text-xs text-gray-400">
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
    </PortalLayout>
  );
};

export default ParentCommunicationCenter;
