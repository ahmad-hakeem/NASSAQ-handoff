import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  MessageSquare, FileText, Inbox, Send, Upload, AlertCircle,
  CheckCircle, Clock, ChevronLeft, Lock
} from 'lucide-react';

const TABS = [
  { id: 'send', label: 'إرسال رسالة', icon: Send },
  { id: 'excuse', label: 'عذر طبي', icon: FileText },
  { id: 'inbox', label: 'صندوق الرسائل', icon: Inbox },
];

const MESSAGE_TYPES = [
  { id: 'note', label: 'ملاحظة' },
  { id: 'suggestion', label: 'اقتراح' },
  { id: 'inquiry', label: 'استفسار' },
];

const RECIPIENT_TYPES = [
  { id: 'teacher', label: 'المعلم' },
  { id: 'admin', label: 'الإدارة' },
];

const ParentCommunicationCenter = () => {
  const { t } = useTranslation();
  const { api, user } = useAuth();
  const { nassaqError } = useNassaqAlert();
  const [activeTab, setActiveTab] = useState('send');
  const [requestsCount, setRequestsCount] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  const [msgType, setMsgType] = useState('note');
  const [recipient, setRecipient] = useState('teacher');
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);

  const [excuseDesc, setExcuseDesc] = useState('');
  const [excuseFile, setExcuseFile] = useState('');
  const [excuseDate, setExcuseDate] = useState(new Date().toISOString().split('T')[0]);
  const [excuseChildId, setExcuseChildId] = useState('');
  const [sendingExcuse, setSendingExcuse] = useState(false);
  const [children, setChildren] = useState([]);

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
        nassaqError('خطأ في جلب البيانات');
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const canSubmit = requestsCount?.can_submit !== false;

  const handleSendMessage = async () => {
    if (!msgText.trim()) return;
    if (!canSubmit) {
      nassaqError('لقد وصلت للحد الأقصى من الطلبات المفتوحة (3). يرجى انتظار إغلاق أحدها.');
      return;
    }
    setSending(true);
    try {
      await api.post('/parent-portal/quick-message', {
        message_type: msgType,
        recipient_type: recipient,
        content: msgText.trim(),
      });
      toast.success('تم استلام رسالتكم، رضاكم محل اهتمامنا');
      setMsgText('');
      const countRes = await api.get('/parent-portal/open-requests-count');
      setRequestsCount(countRes.data);
    } catch {
      nassaqError('حدث خطأ أثناء الإرسال');
    } finally {
      setSending(false);
    }
  };

  const handleSendExcuse = async () => {
    if (!excuseDesc.trim() || !excuseChildId) return;
    if (!canSubmit) {
      nassaqError('لقد وصلت للحد الأقصى من الطلبات المفتوحة (3). يرجى انتظار إغلاق أحدها.');
      return;
    }
    setSendingExcuse(true);
    try {
      await api.post('/parent-portal/absence-excuse', {
        child_id: excuseChildId,
        reason: excuseDesc.trim(),
        absence_date: excuseDate || new Date().toISOString().split('T')[0],
        attachment_url: excuseFile || undefined,
      });
      toast.success('تم إرسال العذر الطبي بنجاح');
      setExcuseDesc('');
      setExcuseFile('');
      setExcuseDate(new Date().toISOString().split('T')[0]);
      const countRes = await api.get('/parent-portal/open-requests-count');
      setRequestsCount(countRes.data);
    } catch {
      nassaqError('حدث خطأ أثناء الإرسال');
    } finally {
      setSendingExcuse(false);
    }
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir="rtl">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-lg font-bold text-gray-800">مركز التواصل</h1>
        </div>

        {!canSubmit && (
          <div className="flex items-center gap-3 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
            <Lock className="w-5 h-5 shrink-0" />
            <p>لقد وصلت للحد الأقصى من الطلبات المفتوحة ({requestsCount?.total_open}/3). يرجى انتظار إغلاق أحدها قبل إرسال طلب جديد.</p>
          </div>
        )}

        <div className="flex gap-2 overflow-x-auto">
          {TABS.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all ${
                  activeTab === tab.id
                    ? 'bg-indigo-600 text-white shadow-md'
                    : 'bg-white text-gray-600 border border-gray-200 hover:border-indigo-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {activeTab === 'send' && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="p-4 space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">نوع الرسالة</p>
                <div className="flex gap-2">
                  {MESSAGE_TYPES.map(mt => (
                    <button
                      key={mt.id}
                      onClick={() => setMsgType(mt.id)}
                      className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                        msgType === mt.id
                          ? 'bg-indigo-100 text-indigo-700 border border-indigo-300'
                          : 'bg-gray-50 text-gray-600 border border-transparent hover:border-gray-200'
                      }`}
                    >
                      {mt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">الجهة</p>
                <div className="flex gap-2">
                  {RECIPIENT_TYPES.map(rt => (
                    <button
                      key={rt.id}
                      onClick={() => setRecipient(rt.id)}
                      className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                        recipient === rt.id
                          ? 'bg-indigo-100 text-indigo-700 border border-indigo-300'
                          : 'bg-gray-50 text-gray-600 border border-transparent hover:border-gray-200'
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
                placeholder="اكتب رسالتك هنا..."
                rows={4}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />

              <button
                onClick={handleSendMessage}
                disabled={!msgText.trim() || sending || !canSubmit}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                <Send className="w-4 h-4" />
                {sending ? 'جارٍ الإرسال...' : 'إرسال الرسالة'}
              </button>
            </CardContent>
          </Card>
        )}

        {activeTab === 'excuse' && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="p-4 space-y-4">
              {children.length > 1 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">الطالب</p>
                  <select
                    value={excuseChildId}
                    onChange={e => setExcuseChildId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  >
                    {children.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">تاريخ الغياب</p>
                <input
                  type="date"
                  value={excuseDate}
                  onChange={e => setExcuseDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <textarea
                value={excuseDesc}
                onChange={e => setExcuseDesc(e.target.value)}
                placeholder="وصف العذر الطبي..."
                rows={3}
                className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />

              <input
                type="text"
                value={excuseFile}
                onChange={e => setExcuseFile(e.target.value)}
                placeholder="رابط الملف المرفق (اختياري)"
                className="w-full px-3 py-2 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />

              <button
                onClick={handleSendExcuse}
                disabled={!excuseDesc.trim() || sendingExcuse || !canSubmit}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                <Upload className="w-4 h-4" />
                {sendingExcuse ? 'جارٍ الإرسال...' : 'إرسال العذر'}
              </button>
            </CardContent>
          </Card>
        )}

        {activeTab === 'inbox' && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="p-4">
              {messages.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <Inbox className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">لا توجد رسائل</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {messages.map((msg, i) => {
                    const isRead = msg.read_status || msg.status === 'read';
                    return (
                      <div key={msg.id || i} className={`p-3 rounded-xl border transition-colors ${isRead ? 'bg-white border-gray-100' : 'bg-indigo-50 border-indigo-100'}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800 truncate">
                              {msg.content || msg.message || msg.subject || 'رسالة'}
                            </p>
                            <p className="text-xs text-gray-500 mt-1">
                              {msg.created_at ? new Date(msg.created_at).toLocaleDateString('ar-SA') : ''}
                            </p>
                          </div>
                          <span className={`shrink-0 ml-2 px-2 py-0.5 rounded-full text-xs font-medium ${
                            msg.status === 'replied' ? 'bg-emerald-100 text-emerald-700' :
                            msg.status === 'pending' || msg.status === 'sent' ? 'bg-amber-100 text-amber-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {msg.status === 'replied' ? 'تم الرد' : msg.status === 'pending' || msg.status === 'sent' ? 'قيد المراجعة' : msg.status || 'مرسل'}
                          </span>
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
