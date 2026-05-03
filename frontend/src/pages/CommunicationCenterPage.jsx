import { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { NotificationsPage } from './NotificationsPage';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import {
  MessageSquare,
  Send,
  Users,
  Bell,
  Mail,
  Plus,
  RefreshCw,
  Inbox,
  CheckCircle,
  Clock,
  GraduationCap,
  UserCheck,
  Loader2,
  Edit,
  Eye,
  Calendar,
  Megaphone,
  Trash2,
  AlertTriangle,
  X,
  MailOpen,
  ChevronDown,
  ChevronUp,
  AlertOctagon,
  CheckCircle2,
  XCircle,
  Users2,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import { UserMultiSelect } from '../components/ui/UserMultiSelect';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';

const iconMap = {
  users: Users,
  'user-check': UserCheck,
  'graduation-cap': GraduationCap,
  bell: Bell,
  clock: Clock,
  refresh: RefreshCw,
  mail: Mail,
  calendar: Calendar,
  megaphone: Megaphone,
};

export const CommunicationCenterPage = () => {
  const { t } = useTranslation();
  const { isRTL, isDark } = useTheme();
  const { api } = useAuth();
  const { nassaqWarning, nassaqError } = useNassaqAlert();
  
  const location = useLocation();
  const navigate = useNavigate();
  const isNotificationsRoute = location.pathname.endsWith('/notifications');
  const [activeTab, setActiveTab] = useState(isNotificationsRoute ? 'notifications' : 'compose');

  useEffect(() => {
    if (isNotificationsRoute && activeTab !== 'notifications') {
      setActiveTab('notifications');
    } else if (!isNotificationsRoute && activeTab === 'notifications') {
      setActiveTab('compose');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isNotificationsRoute]);

  const [notificationsUnread, setNotificationsUnread] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const loadNotifUnread = async () => {
      try {
        const res = await api.get('/notifications/unread-count');
        if (!cancelled) setNotificationsUnread(res.data?.count ?? res.data?.unread_count ?? 0);
      } catch (_) { /* non-fatal */ }
    };
    loadNotifUnread();
    const id = setInterval(loadNotifUnread, 60000);
    return () => { cancelled = true; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTabChange = (tabId) => {
    if (tabId === 'notifications' && !isNotificationsRoute) {
      navigate('/principal/communication/notifications');
    } else if (tabId !== 'notifications' && isNotificationsRoute) {
      navigate('/principal/communication');
    }
    setActiveTab(tabId);
  };

  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [stats, setStats] = useState({ sent: 0, received: 0, scheduled: 0 });
  const [sentMessages, setSentMessages] = useState([]);
  const [receivedMessages, setReceivedMessages] = useState([]);
  const [scheduledMessages, setScheduledMessages] = useState([]);
  const [audienceGroups, setAudienceGroups] = useState([]);

  const [editScheduledOpen, setEditScheduledOpen] = useState(false);
  const [viewMessageOpen, setViewMessageOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [messageToDelete, setMessageToDelete] = useState(null);
  const [expandedInboxMsg, setExpandedInboxMsg] = useState(null);
  const [inboxFilter, setInboxFilter] = useState('all');

  // Sent circulars + acknowledgment tracking
  const [sentCirculars, setSentCirculars] = useState([]);
  const [ackModalOpen, setAckModalOpen] = useState(false);
  const [ackModalLoading, setAckModalLoading] = useState(false);
  const [ackModalData, setAckModalData] = useState(null);
  
  // New message form (mirrors SendNotificationWizard fields + scheduling)
  const [newMessage, setNewMessage] = useState({
    title_ar: '',
    title_en: '',
    message_ar: '',
    message_en: '',
    recipient_type: 'all_students',
    recipient_filter: null,
    notification_type: 'announcement',
    priority: 'normal',
    send_push: true,
    send_sms: false,
    send_email: false,
    send_whatsapp: false,
    scheduled_at: '',
  });

  const [notifOptions, setNotifOptions] = useState({
    recipientTypes: [],
    notificationTypes: [],
    priorities: [],
    grades: [],
    classes: [],
  });

  const resetNewMessage = () => setNewMessage({
    title_ar: '',
    title_en: '',
    message_ar: '',
    message_en: '',
    recipient_type: 'all_students',
    recipient_filter: null,
    notification_type: 'announcement',
    priority: 'normal',
    send_push: true,
    send_sms: false,
    send_email: false,
    send_whatsapp: false,
    scheduled_at: '',
  });

  const needsRecipientFilter = ['grade_students', 'grade_parents', 'class_students', 'class_parents'].includes(newMessage.recipient_type);
  const isSpecificUsers = newMessage.recipient_type === 'specific_users';

  const openAckModal = async (circular) => {
    setAckModalData({ circular, recipients: [], acknowledged_count: 0, total: 0, acknowledged_rate: 0 });
    setAckModalOpen(true);
    setAckModalLoading(true);
    try {
      const res = await api.get(`/notifications/circular/${circular.broadcast_id}/acknowledgements`);
      setAckModalData({ ...res.data, circular });
    } catch (e) {
      console.error('Failed to load acknowledgements:', e);
      nassaqError(isRTL ? 'تعذر تحميل حالة الاستلام' : 'Failed to load acknowledgment status');
    } finally {
      setAckModalLoading(false);
    }
  };

  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      
      // Fetch stats
      const statsRes = await api.get('/communication/stats');
      
      // Fetch all messages (sent)
      const messagesRes = await api.get('/communication?limit=100');
      const allMessages = messagesRes.data.messages || [];
      
      // Filter sent and scheduled
      const sent = allMessages.filter(m => m.status === 'sent');
      const scheduled = allMessages.filter(m => m.status === 'scheduled');
      
      setSentMessages(sent);
      setScheduledMessages(scheduled);
      
      try {
        const circRes = await api.get('/notifications/sent-circulars?limit=50');
        setSentCirculars(circRes.data?.circulars || []);
      } catch (_e) {
        setSentCirculars([]);
      }

      let received = [];
      try {
        const receivedRes = await api.get('/communication/received');
        received = receivedRes.data.messages || [];
      } catch (e) {
        received = [];
      }
      setReceivedMessages(received);
      
      const audienceRes = await api.get('/communication/audience');
      setAudienceGroups(audienceRes.data || []);

      // Notification form options (same as SendNotificationWizard)
      const [recipientRes, notifTypeRes, priorityRes, gradesRes, classesRes] = await Promise.all([
        api.get('/notifications/options/recipient-types').catch(() => ({ data: { types: [] } })),
        api.get('/notifications/options/notification-types').catch(() => ({ data: { types: [] } })),
        api.get('/notifications/options/priorities').catch(() => ({ data: { priorities: [] } })),
        api.get('/classes/options/grades').catch(() => ({ data: { grades: [] } })),
        api.get('/classes/').catch(() => ({ data: { classes: [] } })),
      ]);
      setNotifOptions({
        recipientTypes: recipientRes.data.types || [
          { code: 'all_students', name_ar: 'جميع الطلاب', name_en: 'All Students' },
          { code: 'all_teachers', name_ar: 'جميع المعلمين', name_en: 'All Teachers' },
          { code: 'all_parents', name_ar: 'جميع أولياء الأمور', name_en: 'All Parents' },
          { code: 'grade_students', name_ar: 'طلاب صف معين', name_en: 'Grade Students' },
          { code: 'class_students', name_ar: 'طلاب فصل معين', name_en: 'Class Students' },
        ],
        notificationTypes: notifTypeRes.data.types || [
          { code: 'announcement', name_ar: 'إعلان', name_en: 'Announcement' },
          { code: 'reminder', name_ar: 'تذكير', name_en: 'Reminder' },
          { code: 'alert', name_ar: 'تنبيه', name_en: 'Alert' },
          { code: 'event', name_ar: 'حدث', name_en: 'Event' },
          { code: 'emergency', name_ar: 'طوارئ', name_en: 'Emergency' },
          { code: 'circular', name_ar: 'تعميم', name_en: 'Circular' },
          { code: 'other', name_ar: 'أخرى', name_en: 'Other' },
        ],
        priorities: priorityRes.data.priorities || [
          { code: 'low', name_ar: 'منخفضة', name_en: 'Low' },
          { code: 'normal', name_ar: 'عادية', name_en: 'Normal' },
          { code: 'high', name_ar: 'عالية', name_en: 'High' },
          { code: 'urgent', name_ar: 'عاجلة', name_en: 'Urgent' },
        ],
        grades: gradesRes.data.grades || [],
        classes: classesRes.data.classes || [],
      });
      
      setStats({
        sent: sent.length,
        received: received.length || statsRes.data?.received || 0,
        scheduled: scheduled.length,
      });
      
    } catch (error) {
      console.error('Failed to fetch communication data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Map the wizard recipient_type onto the legacy /communication audience codes
  // so Sent/Scheduled/Inbox tabs keep working without regressions.
  const mapRecipientToAudience = (recipientType) => {
    if (!recipientType) return 'all';
    if (recipientType === 'specific_users') return 'custom';
    if (recipientType.startsWith('all_')) {
      const seg = recipientType.replace('all_', '');
      if (seg === 'students') return 'students';
      if (seg === 'teachers') return 'teachers';
      if (seg === 'parents') return 'parents';
      return 'all';
    }
    if (recipientType.includes('student')) return 'students';
    if (recipientType.includes('teacher')) return 'teachers';
    if (recipientType.includes('parent')) return 'parents';
    return 'all';
  };

  // Send or schedule message — uses the same form fields as SendNotificationWizard,
  // mapped onto the existing /communication payload (so Sent/Scheduled tabs keep working),
  // combined with the optional scheduled_at from this page.
  const handleSendMessage = async (schedule = false) => {
    if (!newMessage.title_ar?.trim() || !newMessage.message_ar?.trim()) {
      nassaqWarning(t('titleAndMessageRequired'));
      return;
    }

    if (isSpecificUsers && (!newMessage.recipient_filter?.user_ids || newMessage.recipient_filter.user_ids.length === 0)) {
      nassaqWarning(isRTL ? 'يرجى اختيار مستخدم واحد على الأقل' : 'Please select at least one user');
      return;
    }

    try {
      setSending(true);

      const channels = ['in_app'];
      if (newMessage.send_push) channels.push('push');
      if (newMessage.send_whatsapp) channels.push('whatsapp');
      if (newMessage.send_sms) channels.push('sms');
      if (newMessage.send_email) channels.push('email');

      const userIds = isSpecificUsers ? (newMessage.recipient_filter?.user_ids || []) : [];

      const payload = {
        title: newMessage.title_ar,
        content: newMessage.message_ar,
        audience: mapRecipientToAudience(newMessage.recipient_type),
        audience_ids: userIds,
        channels,
        scheduled_at: schedule && newMessage.scheduled_at ? newMessage.scheduled_at : null,
        // Extra wizard metadata — backend may ignore unknown keys
        notification_type: newMessage.notification_type,
        priority: newMessage.priority,
        recipient_type: newMessage.recipient_type,
        recipient_filter: needsRecipientFilter
          ? newMessage.recipient_filter
          : isSpecificUsers
            ? { user_ids: userIds }
            : null,
      };

      const response = await api.post('/communication', payload);

      if (response.data?.status === 'sent' || !schedule) {
        toast.success(t('messageSentSuccessfully'));
      } else {
        toast.success(t('messageScheduledSuccessfully'));
      }

      resetNewMessage();
      await fetchData();
    } catch (error) {
      console.error('Failed to send message:', error);
      nassaqError(error.response?.data?.detail || t('failedToSendMessage'));
    } finally {
      setSending(false);
    }
  };

  // Send scheduled message now
  const handleSendScheduledNow = async (messageId) => {
    try {
      setSending(true);
      await api.post(`/communication/${messageId}/send-now`);
      toast.success(t('messageSentSuccessfully'));
      await fetchData();
    } catch (error) {
      console.error('Failed to send message:', error);
      nassaqError(t('failedToSendMessage'));
    } finally {
      setSending(false);
    }
  };

  // Update scheduled message
  const handleUpdateScheduledMessage = async () => {
    if (!selectedMessage) return;
    
    try {
      setSending(true);
      await api.put(`/communication/${selectedMessage.id}`, {
        title: selectedMessage.title,
        content: selectedMessage.content,
        audience: selectedMessage.audience,
        scheduled_at: selectedMessage.scheduled_at
      });
      toast.success(t('scheduledMessageUpdated'));
      setEditScheduledOpen(false);
      setSelectedMessage(null);
      await fetchData();
    } catch (error) {
      console.error('Failed to update message:', error);
      nassaqError(t('failedToUpdateMessage'));
    } finally {
      setSending(false);
    }
  };

  // Delete message
  const handleDeleteMessage = async () => {
    if (!messageToDelete) return;
    
    try {
      await api.delete(`/communication/${messageToDelete.id}`);
      toast.success(t('messageDeleted'));
      setDeleteConfirmOpen(false);
      setMessageToDelete(null);
      await fetchData();
    } catch (error) {
      console.error('Failed to delete message:', error);
      nassaqError(t('failedToDeleteMessage'));
    }
  };

  // Mark message as read
  const handleMarkAsRead = async (messageId) => {
    try {
      await api.put(`/communication/${messageId}/read`);
      setReceivedMessages(prev => 
        prev.map(m => m.id === messageId ? { ...m, is_read: true } : m)
      );
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  };

  // Get audience label
  const getAudienceLabel = (audience) => {
    const labels = {
      all: t('everyone'),
      teachers: t('teachers2'),
      students: t('students'),
      parents: t('parents')
    };
    return labels[audience] || audience;
  };

  const getAudienceIcon = (iconName) => {
    return iconMap[iconName] || Users;
  };

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="flex items-center justify-center min-h-screen">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      </Sidebar>
    );
  }

  const unreadCount = receivedMessages.filter(m => !m.is_read).length;

  const filteredInboxMessages = inboxFilter === 'all' 
    ? receivedMessages 
    : inboxFilter === 'unread' 
      ? receivedMessages.filter(m => !m.is_read)
      : receivedMessages.filter(m => m.is_read);

  const tabs = [
    { id: 'inbox', label: t('inbox'), icon: Inbox, badge: unreadCount },
    { id: 'compose', label: t('compose'), icon: MessageSquare },
    { id: 'sent', label: t('sent'), icon: Send, badge: sentMessages.length },
    { id: 'scheduled', label: t('scheduled'), icon: Clock, badge: scheduledMessages.length },
    { id: 'notifications', label: isRTL ? 'الإشعارات' : 'Notifications', icon: Bell, badge: notificationsUnread },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="communication-center-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {t('communicationCenter')}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('sendAndReceiveMessagesAndNotifications')}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button 
                variant="outline" 
                className="rounded-xl" 
                onClick={fetchData} 
                disabled={loading}
                data-testid="refresh-btn"
              >
                <RefreshCw className={`h-4 w-4 me-2 ${loading ? 'animate-spin' : ''}`} />
                {t('refresh')}
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-1 mt-4 bg-muted/50 rounded-xl p-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                data-testid={`tab-${tab.id}`}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-tajawal font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-background shadow-sm text-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
                {tab.badge > 0 && (
                  <Badge variant={tab.id === 'inbox' && unreadCount > 0 ? 'destructive' : 'secondary'} className="text-[10px] h-5 px-1.5 font-cairo">
                    {tab.badge}
                  </Badge>
                )}
              </button>
            ))}
          </div>
        </header>

        <div className="p-4 sm:p-6 space-y-6">

          {activeTab === 'inbox' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="font-cairo text-lg font-semibold">{t('inbox')}</h2>
                  {unreadCount > 0 && (
                    <Badge variant="destructive" className="font-cairo">{unreadCount} {t('new3')}</Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {['all', 'unread', 'read'].map((f) => (
                    <Button key={f} variant={inboxFilter === f ? 'default' : 'outline'} size="sm" className="rounded-lg text-xs"
                      onClick={() => setInboxFilter(f)}>
                      {f === 'all' ? (t('all')) : f === 'unread' ? (t('unread')) : (t('read'))}
                    </Button>
                  ))}
                </div>
              </div>

              {filteredInboxMessages.length === 0 ? (
                <Card className="card-nassaq">
                  <CardContent className="py-16 text-center">
                    <div className="w-20 h-20 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
                      <Inbox className="h-10 w-10 text-muted-foreground/30" />
                    </div>
                    <p className="text-lg font-cairo font-semibold text-muted-foreground">
                      {inboxFilter === 'unread' 
                        ? (t('noUnreadMessages'))
                        : (t('yourInboxIsEmpty'))}
                    </p>
                    <p className="text-sm text-muted-foreground/60 font-tajawal mt-1">
                      {t('newMessagesWillAppearHere')}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-2">
                  {filteredInboxMessages.map((msg) => {
                    const isExpanded = expandedInboxMsg === msg.id;
                    return (
                      <Card key={msg.id} className={`card-nassaq overflow-hidden transition-all ${!msg.is_read ? 'ring-1 ring-blue-300 dark:ring-blue-700' : ''}`}>
                        <button
                          className="w-full text-start p-4 hover:bg-muted/30 transition-colors"
                          onClick={() => {
                            setExpandedInboxMsg(isExpanded ? null : msg.id);
                            if (!msg.is_read) handleMarkAsRead(msg.id);
                          }}
                        >
                          <div className="flex items-start gap-3">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
                              msg.is_read 
                                ? 'bg-muted/50' 
                                : 'bg-blue-100 dark:bg-blue-900/40'
                            }`}>
                              {msg.is_read 
                                ? <MailOpen className="h-5 w-5 text-muted-foreground" /> 
                                : <Mail className="h-5 w-5 text-blue-600 dark:text-blue-400" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <p className={`text-sm truncate ${!msg.is_read ? 'font-bold text-foreground' : 'font-medium'}`}>
                                  {msg.title}
                                </p>
                                <div className="flex items-center gap-2 shrink-0">
                                  {!msg.is_read && (
                                    <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
                                  )}
                                  <span className="text-[11px] text-muted-foreground font-tajawal whitespace-nowrap">
                                    {formatDate(msg.sent_at || msg.created_at)}
                                  </span>
                                  {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                                </div>
                              </div>
                              {!isExpanded && (
                                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{msg.content}</p>
                              )}
                              {msg.sender_name && (
                                <p className="text-[11px] text-muted-foreground/70 mt-0.5 font-tajawal">
                                  {t('from')} {msg.sender_name}
                                </p>
                              )}
                            </div>
                          </div>
                        </button>
                        {isExpanded && (
                          <div className="px-4 pb-4 border-t border-border/50 pt-3">
                            <div className="ms-13 space-y-3">
                              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                              <div className="flex items-center gap-3 pt-2">
                                <Badge variant="secondary" className="text-[10px]">
                                  {getAudienceLabel(msg.audience)}
                                </Badge>
                                {msg.sender_name && (
                                  <span className="text-[11px] text-muted-foreground font-tajawal">
                                    {t('sender')} {msg.sender_name}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activeTab === 'compose' && (
            <>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="card-nassaq cursor-pointer hover:ring-2 hover:ring-brand-navy/50 transition-all"
                  onClick={() => setActiveTab('sent')} data-testid="sent-messages-card">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                      <Send className="h-6 w-6 text-brand-navy" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{sentMessages.length}</p>
                      <p className="text-sm text-muted-foreground">{t('sentMessages')}</p>
                    </div>
                  </CardContent>
                </Card>
                <Card className="card-nassaq cursor-pointer hover:ring-2 hover:ring-green-500/50 transition-all"
                  onClick={() => setActiveTab('inbox')} data-testid="received-messages-card">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-green-500/10 flex items-center justify-center">
                      <Inbox className="h-6 w-6 text-green-600" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{receivedMessages.length}</p>
                      <p className="text-sm text-muted-foreground">{t('inbox')}</p>
                    </div>
                  </CardContent>
                </Card>
                <Card className="card-nassaq cursor-pointer hover:ring-2 hover:ring-yellow-500/50 transition-all"
                  onClick={() => setActiveTab('scheduled')} data-testid="scheduled-messages-card">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                      <Clock className="h-6 w-6 text-yellow-600" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{scheduledMessages.length}</p>
                      <p className="text-sm text-muted-foreground">{t('scheduled2')}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo flex items-center gap-2">
                    <MessageSquare className="h-5 w-5 text-brand-turquoise" />
                    {t('composeNewMessage')}
                  </CardTitle>
                  <CardDescription>
                    {t('sendAMessageToUsersInYourSchool')}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Recipient Type + optional grade/class filter */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('recipients')} <span className="text-red-500">*</span></Label>
                      <Select
                        value={newMessage.recipient_type}
                        onValueChange={(val) => setNewMessage(prev => ({ ...prev, recipient_type: val, recipient_filter: null }))}
                      >
                        <SelectTrigger data-testid="notif-recipient" className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {notifOptions.recipientTypes.map((rt) => (
                            <SelectItem key={rt.code} value={rt.code}>{isRTL ? rt.name_ar : rt.name_en}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {needsRecipientFilter && (
                      <div className="space-y-2">
                        <Label>{newMessage.recipient_type.includes('grade') ? t('grade') : t('class')}</Label>
                        <Select
                          value={newMessage.recipient_filter?.grade_id || newMessage.recipient_filter?.class_id || ''}
                          onValueChange={(val) => setNewMessage(prev => ({
                            ...prev,
                            recipient_filter: prev.recipient_type.includes('grade') ? { grade_id: val } : { class_id: val },
                          }))}
                        >
                          <SelectTrigger className="rounded-xl">
                            <SelectValue placeholder={t('select2')} />
                          </SelectTrigger>
                          <SelectContent>
                            {newMessage.recipient_type.includes('grade')
                              ? notifOptions.grades.map((g) => <SelectItem key={g.id} value={g.id}>{isRTL ? g.name_ar : g.name_en}</SelectItem>)
                              : notifOptions.classes.map((c) => <SelectItem key={c.class_id} value={c.class_id}>{c.name_ar}</SelectItem>)
                            }
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                  </div>

                  {isSpecificUsers && (
                    <div className="space-y-2">
                      <Label>
                        {isRTL ? 'المستخدمون' : 'Users'} <span className="text-red-500">*</span>
                      </Label>
                      <UserMultiSelect
                        value={newMessage.recipient_filter?.user_ids || []}
                        onChange={(ids) => setNewMessage(prev => ({ ...prev, recipient_filter: { user_ids: ids } }))}
                        placeholder={isRTL ? 'ابحث عن مستخدمين...' : 'Search for users...'}
                        dataTestId="cc-specific-users"
                      />
                    </div>
                  )}

                  {/* Type & Priority */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('type3')}</Label>
                      <Select
                        value={newMessage.notification_type}
                        onValueChange={(val) => setNewMessage(prev => ({ ...prev, notification_type: val }))}
                      >
                        <SelectTrigger data-testid="notif-type" className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {notifOptions.notificationTypes.map((nt) => (
                            <SelectItem key={nt.code} value={nt.code}>{isRTL ? nt.name_ar : nt.name_en}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label>{t('priority')}</Label>
                      <Select
                        value={newMessage.priority}
                        onValueChange={(val) => setNewMessage(prev => ({ ...prev, priority: val }))}
                      >
                        <SelectTrigger data-testid="notif-priority" className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {notifOptions.priorities.map((p) => (
                            <SelectItem key={p.code} value={p.code}>{isRTL ? p.name_ar : p.name_en}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {/* Title (Arabic) */}
                  <div className="space-y-2">
                    <Label>{t('titleArabic')} <span className="text-red-500">*</span></Label>
                    <Input
                      value={newMessage.title_ar}
                      onChange={(e) => setNewMessage(prev => ({ ...prev, title_ar: e.target.value }))}
                      placeholder={t('notificationTitle')}
                      className="rounded-xl"
                      data-testid="notif-title-ar"
                    />
                  </div>

                  {/* Message (Arabic) */}
                  <div className="space-y-2">
                    <Label>{t('messageArabic')} <span className="text-red-500">*</span></Label>
                    <Textarea
                      value={newMessage.message_ar}
                      onChange={(e) => setNewMessage(prev => ({ ...prev, message_ar: e.target.value }))}
                      placeholder={t('notificationContent')}
                      className="rounded-xl min-h-[150px]"
                      rows={4}
                      data-testid="notif-message-ar"
                    />
                  </div>

                  {/* Delivery Methods */}
                  <Card className="bg-muted/30 border-none shadow-none">
                    <CardContent className="p-4">
                      <Label className="mb-3 block">{t('deliveryMethod')}</Label>
                      <div className="flex flex-wrap gap-4">
                        <div className="flex items-center gap-2">
                          <Checkbox
                            id="cc_send_push"
                            checked={newMessage.send_push}
                            onCheckedChange={(checked) => setNewMessage(prev => ({ ...prev, send_push: !!checked }))}
                          />
                          <Label htmlFor="cc_send_push" className="cursor-pointer">{t('push')}</Label>
                        </div>
                        <div className="flex items-center gap-2">
                          <Checkbox
                            id="cc_send_whatsapp"
                            checked={newMessage.send_whatsapp}
                            onCheckedChange={(checked) => setNewMessage(prev => ({ ...prev, send_whatsapp: !!checked }))}
                          />
                          <Label htmlFor="cc_send_whatsapp" className="cursor-pointer">
                            {isRTL ? 'إرسال عبر الواتساب' : 'WhatsApp'}
                          </Label>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Schedule (kept from original) */}
                  <div>
                    <Label className="text-sm font-medium mb-2 block">
                      {t('scheduleSendOptional')}
                    </Label>
                    <Input
                      type="datetime-local"
                      value={newMessage.scheduled_at}
                      onChange={(e) => setNewMessage(prev => ({ ...prev, scheduled_at: e.target.value }))}
                      className="rounded-xl"
                      data-testid="schedule-input"
                    />
                  </div>

                  {/* Actions (kept from original) */}
                  <div className="flex justify-end gap-3 pt-4">
                    <Button variant="outline" className="rounded-xl" onClick={resetNewMessage}>
                      {t('clear3')}
                    </Button>
                    {newMessage.scheduled_at && (
                      <Button
                        variant="secondary"
                        className="rounded-xl"
                        onClick={() => handleSendMessage(true)}
                        disabled={sending || !newMessage.title_ar || !newMessage.message_ar}
                        data-testid="schedule-btn"
                      >
                        {sending ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <Clock className="h-4 w-4 me-2" />}
                        {t('schedule2')}
                      </Button>
                    )}
                    <Button
                      className="rounded-xl bg-brand-navy hover:bg-brand-navy/90"
                      onClick={() => handleSendMessage(false)}
                      disabled={sending || !newMessage.title_ar || !newMessage.message_ar}
                      data-testid="send-now-btn"
                    >
                      {sending ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <Send className="h-4 w-4 me-2" />}
                      {t('sendNow')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {activeTab === 'sent' && (
            <div className="space-y-6">
              {/* Sent Circulars (تعميمات) — high-priority, with ack tracking */}
              {sentCirculars.length > 0 && (
                <div className="space-y-3">
                  <h2 className="font-cairo text-lg font-semibold flex items-center gap-2">
                    <AlertOctagon className="h-5 w-5 text-red-600" />
                    {isRTL ? 'التعميمات المرسلة' : 'Sent Circulars'}
                    <Badge variant="secondary" className="font-cairo">{sentCirculars.length}</Badge>
                  </h2>
                  <div className="space-y-3">
                    {sentCirculars.map((c) => {
                      const ackPct = c.acknowledged_rate || 0;
                      const allAcked = c.recipient_count > 0 && c.acknowledged_count >= c.recipient_count;
                      return (
                        <Card
                          key={c.broadcast_id}
                          className="card-nassaq border-s-4 border-red-500"
                        >
                          <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-2 gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                <AlertOctagon className="h-4 w-4 text-red-600 shrink-0" />
                                <p className="font-medium font-cairo truncate">
                                  {isRTL ? c.title : (c.title_en || c.title)}
                                </p>
                              </div>
                              <Badge
                                variant="outline"
                                className={`font-cairo shrink-0 ${
                                  allAcked
                                    ? 'border-green-500 text-green-700 bg-green-50 dark:bg-green-950/30'
                                    : 'border-red-500 text-red-700 bg-red-50 dark:bg-red-950/30'
                                }`}
                              >
                                {isRTL ? 'تعميم' : 'Circular'}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground line-clamp-2">
                              {isRTL ? c.message : (c.message_en || c.message)}
                            </p>
                            <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-muted-foreground font-tajawal">
                              <span className="inline-flex items-center gap-1">
                                <Users2 className="h-3.5 w-3.5" />
                                {isRTL ? `${c.recipient_count} مستلم` : `${c.recipient_count} recipients`}
                              </span>
                              <span className="inline-flex items-center gap-1 text-green-700 dark:text-green-500">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                {isRTL ? 'تم الاستلام:' : 'Acknowledged:'} {c.acknowledged_count}
                              </span>
                              <span className="inline-flex items-center gap-1 text-red-700 dark:text-red-500">
                                <XCircle className="h-3.5 w-3.5" />
                                {isRTL ? 'لم يتم:' : 'Pending:'} {Math.max(0, (c.recipient_count || 0) - (c.acknowledged_count || 0))}
                              </span>
                              <span>{formatDate(c.sent_at || c.created_at)}</span>
                            </div>

                            {/* Progress bar */}
                            <div className="mt-3">
                              <div className="flex items-center justify-between text-xs font-cairo mb-1">
                                <span className={allAcked ? 'text-green-700 dark:text-green-500' : 'text-muted-foreground'}>
                                  {isRTL ? 'حالة الاستلام' : 'Acknowledgment Status'}
                                </span>
                                <span className={allAcked ? 'text-green-700 dark:text-green-500 font-semibold' : 'text-muted-foreground'}>
                                  {ackPct}%
                                </span>
                              </div>
                              <div className="h-2 bg-muted rounded-full overflow-hidden">
                                <div
                                  className={`h-full transition-all ${allAcked ? 'bg-green-500' : 'bg-red-500'}`}
                                  style={{ width: `${Math.min(100, ackPct)}%` }}
                                />
                              </div>
                            </div>

                            <div className="mt-3 flex justify-end">
                              <Button
                                size="sm"
                                variant="outline"
                                className="font-cairo"
                                onClick={() => openAckModal(c)}
                                data-testid={`view-acks-${c.broadcast_id}`}
                              >
                                <Eye className="h-3.5 w-3.5 me-1" />
                                {isRTL ? 'عرض حالة الاستلام' : 'View Acknowledgment Status'}
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              )}

              <h2 className="font-cairo text-lg font-semibold flex items-center gap-2">
                <Send className="h-5 w-5 text-brand-navy" />
                {t('sentMessages2')}
                <Badge variant="secondary" className="font-cairo">{sentMessages.length}</Badge>
              </h2>
              {sentMessages.length === 0 ? (
                <Card className="card-nassaq">
                  <CardContent className="py-16 text-center">
                    <Send className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                    <p className="text-muted-foreground font-cairo">{t('noSentMessages')}</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {sentMessages.map((msg) => (
                    <Card key={msg.id} className="card-nassaq cursor-pointer hover:ring-1 hover:ring-brand-navy/30 transition-all"
                      onClick={() => { setSelectedMessage(msg); setViewMessageOpen(true); }}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-2">
                          <p className="font-medium font-cairo">{msg.title}</p>
                          <Badge variant="default" className="bg-green-500">{t('sent2')}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">{msg.content}</p>
                        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground font-tajawal">
                          <span>{t('audience')} {getAudienceLabel(msg.audience)}</span>
                          <span>{t('recipients2')} {msg.recipient_count || msg.sent_count || 0}</span>
                          <span>{formatDate(msg.sent_at || msg.created_at)}</span>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'notifications' && (
            <div data-testid="notifications-tab-content">
              <NotificationsPage embedded />
            </div>
          )}

          {activeTab === 'scheduled' && (
            <div className="space-y-4">
              <h2 className="font-cairo text-lg font-semibold flex items-center gap-2">
                <Clock className="h-5 w-5 text-yellow-600" />
                {t('scheduledMessages')}
                <Badge variant="secondary" className="font-cairo">{scheduledMessages.length}</Badge>
              </h2>
              {scheduledMessages.length === 0 ? (
                <Card className="card-nassaq">
                  <CardContent className="py-16 text-center">
                    <Clock className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                    <p className="text-muted-foreground font-cairo">{t('noScheduledMessages')}</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {scheduledMessages.map((msg) => (
                    <Card key={msg.id} className="card-nassaq border-yellow-200 dark:border-yellow-800/50">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-2">
                          <p className="font-medium font-cairo">{msg.title}</p>
                          <Badge variant="outline" className="text-yellow-700 border-yellow-500">
                            <Clock className="h-3 w-3 me-1" />
                            {t('scheduled2')}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">{msg.content}</p>
                        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground font-tajawal">
                          <span>{t('audience')} {getAudienceLabel(msg.audience)}</span>
                          <span>•</span>
                          <span>{t('sendAt')} {formatDate(msg.scheduled_at)}</span>
                        </div>
                        <div className="flex gap-2 mt-4">
                          <Button size="sm" variant="outline" className="flex-1"
                            onClick={() => { setSelectedMessage({...msg}); setEditScheduledOpen(true); }}
                            data-testid={`edit-scheduled-${msg.id}`}>
                            <Edit className="h-4 w-4 me-1" />
                            {t('edit')}
                          </Button>
                          <Button size="sm" className="flex-1 bg-green-600 hover:bg-green-700"
                            onClick={() => handleSendScheduledNow(msg.id)} disabled={sending}
                            data-testid={`send-now-scheduled-${msg.id}`}>
                            {sending ? <Loader2 className="h-4 w-4 me-1 animate-spin" /> : <Send className="h-4 w-4 me-1" />}
                            {t('sendNow')}
                          </Button>
                          <Button size="sm" variant="destructive"
                            onClick={() => { setMessageToDelete(msg); setDeleteConfirmOpen(true); }}
                            data-testid={`delete-scheduled-${msg.id}`}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>

        {/* ===== Dialogs ===== */}

        {/* Edit Scheduled Message Dialog */}
        <Dialog open={editScheduledOpen} onOpenChange={setEditScheduledOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo">
                {t('editScheduledMessage')}
              </DialogTitle>
            </DialogHeader>
            {selectedMessage && (
              <div className="space-y-4 mt-4">
                <div>
                  <Label>{t('targetAudience')}</Label>
                  <Select 
                    value={selectedMessage.audience}
                    onValueChange={(v) => setSelectedMessage({...selectedMessage, audience: v})}
                  >
                    <SelectTrigger className="rounded-xl mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {audienceGroups.map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {isRTL ? group.name : group.name_en}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>{t('messageTitle')}</Label>
                  <Input
                    value={selectedMessage.title}
                    onChange={(e) => setSelectedMessage({...selectedMessage, title: e.target.value})}
                    className="rounded-xl mt-1"
                  />
                </div>
                <div>
                  <Label>{t('messageContent')}</Label>
                  <Textarea
                    value={selectedMessage.content}
                    onChange={(e) => setSelectedMessage({...selectedMessage, content: e.target.value})}
                    className="rounded-xl mt-1"
                    rows={4}
                  />
                </div>
                <div>
                  <Label>{t('scheduledTime')}</Label>
                  <Input
                    type="datetime-local"
                    value={selectedMessage.scheduled_at?.slice(0, 16) || ''}
                    onChange={(e) => setSelectedMessage({...selectedMessage, scheduled_at: e.target.value})}
                    className="rounded-xl mt-1"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button variant="outline" onClick={() => setEditScheduledOpen(false)}>
                    {t('cancel')}
                  </Button>
                  <Button onClick={handleUpdateScheduledMessage} disabled={sending}>
                    {sending ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <CheckCircle className="h-4 w-4 me-2" />}
                    {t('saveChanges2')}
                  </Button>
                </DialogFooter>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* View Message Dialog */}
        <Dialog open={viewMessageOpen} onOpenChange={setViewMessageOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo">
                {selectedMessage?.title}
              </DialogTitle>
            </DialogHeader>
            {selectedMessage && (
              <div className="space-y-4 mt-4">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{getAudienceLabel(selectedMessage.audience)}</Badge>
                  <Badge variant="outline">{selectedMessage.recipient_count || 0} {t('recipients3')}</Badge>
                </div>
                <p className="text-sm whitespace-pre-wrap">{selectedMessage.content}</p>
                <p className="text-xs text-muted-foreground">
                  {t('sentAt')} {formatDate(selectedMessage.sent_at || selectedMessage.created_at)}
                </p>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Circular Acknowledgment Status Dialog */}
        <Dialog open={ackModalOpen} onOpenChange={setAckModalOpen}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <AlertOctagon className="h-5 w-5 text-red-600" />
                {isRTL ? 'حالة الاستلام' : 'Acknowledgment Status'}
              </DialogTitle>
              {ackModalData?.circular && (
                <DialogDescription className="font-tajawal">
                  {isRTL ? ackModalData.circular.title : (ackModalData.circular.title_en || ackModalData.circular.title)}
                </DialogDescription>
              )}
            </DialogHeader>

            {ackModalLoading ? (
              <div className="py-12 text-center">
                <Loader2 className="h-8 w-8 mx-auto animate-spin text-muted-foreground" />
              </div>
            ) : ackModalData ? (
              <div className="space-y-4 overflow-y-auto">
                {/* Summary metrics */}
                <div className="grid grid-cols-3 gap-3">
                  <Card className="bg-muted/30">
                    <CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold font-cairo">{ackModalData.total || 0}</p>
                      <p className="text-xs text-muted-foreground font-cairo">
                        {isRTL ? 'الإجمالي' : 'Total'}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="bg-green-50 dark:bg-green-950/20">
                    <CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold font-cairo text-green-700 dark:text-green-400">
                        {ackModalData.acknowledged_count || 0}
                      </p>
                      <p className="text-xs text-green-700 dark:text-green-400 font-cairo">
                        {isRTL ? 'تم الاستلام' : 'Acknowledged'}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="bg-red-50 dark:bg-red-950/20">
                    <CardContent className="p-3 text-center">
                      <p className="text-2xl font-bold font-cairo text-red-700 dark:text-red-400">
                        {Math.max(0, (ackModalData.total || 0) - (ackModalData.acknowledged_count || 0))}
                      </p>
                      <p className="text-xs text-red-700 dark:text-red-400 font-cairo">
                        {isRTL ? 'لم يتم الاستلام' : 'Pending'}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs font-cairo mb-1">
                    <span className="text-muted-foreground">{isRTL ? 'نسبة الاستلام' : 'Acknowledgment rate'}</span>
                    <span className="font-semibold">{ackModalData.acknowledged_rate || 0}%</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 transition-all"
                      style={{ width: `${Math.min(100, ackModalData.acknowledged_rate || 0)}%` }}
                    />
                  </div>
                </div>

                {/* Recipients list */}
                <div className="border rounded-lg divide-y max-h-[40vh] overflow-y-auto">
                  {(ackModalData.recipients || []).length === 0 ? (
                    <div className="p-6 text-center text-sm text-muted-foreground font-cairo">
                      {isRTL ? 'لا يوجد مستلمون' : 'No recipients'}
                    </div>
                  ) : (
                    ackModalData.recipients.map((r) => (
                      <div
                        key={r.user_id}
                        className="flex items-center justify-between p-3 gap-3"
                        data-testid={`ack-row-${r.user_id}`}
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium font-cairo truncate">{r.name || '—'}</p>
                          {r.email && (
                            <p className="text-xs text-muted-foreground truncate font-tajawal">{r.email}</p>
                          )}
                        </div>
                        {r.acknowledged ? (
                          <div className="text-right shrink-0">
                            <Badge className="bg-green-500 hover:bg-green-600 font-cairo">
                              <CheckCircle2 className="h-3 w-3 me-1" />
                              {isRTL ? 'تم الاستلام' : 'Acknowledged'}
                            </Badge>
                            {r.acknowledged_at && (
                              <p className="text-[10px] text-muted-foreground mt-1 font-tajawal">
                                {formatDate(r.acknowledged_at)}
                              </p>
                            )}
                          </div>
                        ) : (
                          <Badge variant="outline" className="border-red-500 text-red-700 dark:text-red-400 font-cairo shrink-0">
                            <XCircle className="h-3 w-3 me-1" />
                            {isRTL ? 'لم يتم الاستلام' : 'Pending'}
                          </Badge>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                {t('confirmDelete')}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {isRTL 
                  ? `هل أنت متأكد من حذف الرسالة "${messageToDelete?.title}"؟ لا يمكن التراجع عن هذا الإجراء.`
                  : `Are you sure you want to delete "${messageToDelete?.title}"? This action cannot be undone.`
                }
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
              <AlertDialogAction 
                onClick={handleDeleteMessage}
                className="bg-red-500 hover:bg-red-600"
              >
                {t('delete')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </Sidebar>
  );
};

export default CommunicationCenterPage;
