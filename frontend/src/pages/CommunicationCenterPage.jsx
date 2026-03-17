import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { useTheme } from '../contexts/ThemeContext';
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
  FileText,
  Trash2,
  AlertTriangle,
  X,
  MailOpen,
  ChevronDown,
  ChevronUp,
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
  const { isRTL, isDark } = useTheme();
  const { api } = useAuth();
  const { nassaqWarning, nassaqError } = useNassaqAlert();
  
  const [activeTab, setActiveTab] = useState('compose');

  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [stats, setStats] = useState({ sent: 0, received: 0, scheduled: 0, templates: 0 });
  const [sentMessages, setSentMessages] = useState([]);
  const [receivedMessages, setReceivedMessages] = useState([]);
  const [scheduledMessages, setScheduledMessages] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [audienceGroups, setAudienceGroups] = useState([]);
  
  const [editScheduledOpen, setEditScheduledOpen] = useState(false);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [viewMessageOpen, setViewMessageOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [messageToDelete, setMessageToDelete] = useState(null);
  const [expandedInboxMsg, setExpandedInboxMsg] = useState(null);
  const [inboxFilter, setInboxFilter] = useState('all');
  
  // New message form
  const [newMessage, setNewMessage] = useState({
    title: '',
    content: '',
    audience: '',
    scheduled_at: ''
  });

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
      
      let received = [];
      try {
        const receivedRes = await api.get('/communication/received');
        received = receivedRes.data.messages || [];
      } catch (e) {
        received = [];
      }
      setReceivedMessages(received);
      
      const templatesRes = await api.get('/communication/templates');
      const fetchedTemplates = templatesRes.data || [];
      setTemplates(fetchedTemplates);
      
      const audienceRes = await api.get('/communication/audience');
      setAudienceGroups(audienceRes.data || []);
      
      setStats({
        sent: sent.length,
        received: received.length || statsRes.data?.received || 0,
        scheduled: scheduled.length,
        templates: fetchedTemplates.length || statsRes.data?.templates || 0
      });
      
    } catch (error) {
      console.error('Failed to fetch communication data:', error);
      nassaqError(isRTL ? 'فشل تحميل البيانات' : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [api, isRTL]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Send or schedule message
  const handleSendMessage = async (schedule = false) => {
    if (!newMessage.title || !newMessage.content || !newMessage.audience) {
      nassaqWarning(isRTL ? 'يرجى تعبئة جميع الحقول المطلوبة' : 'Please fill all required fields');
      return;
    }
    
    try {
      setSending(true);
      
      const payload = {
        title: newMessage.title,
        content: newMessage.content,
        audience: newMessage.audience,
        channels: ['in_app'],
        scheduled_at: schedule && newMessage.scheduled_at ? newMessage.scheduled_at : null
      };
      
      const response = await api.post('/communication', payload);
      
      if (response.data.status === 'sent' || !schedule) {
        toast.success(isRTL ? 'تم إرسال الرسالة بنجاح ✓' : 'Message sent successfully ✓');
      } else {
        toast.success(isRTL ? 'تمت جدولة الرسالة بنجاح ✓' : 'Message scheduled successfully ✓');
      }
      
      // Reset form
      setNewMessage({ title: '', content: '', audience: '', scheduled_at: '' });
      
      // Refresh data
      await fetchData();
      
    } catch (error) {
      console.error('Failed to send message:', error);
      nassaqError(isRTL ? 'فشل إرسال الرسالة' : 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  // Send scheduled message now
  const handleSendScheduledNow = async (messageId) => {
    try {
      setSending(true);
      await api.post(`/communication/${messageId}/send-now`);
      toast.success(isRTL ? 'تم إرسال الرسالة بنجاح ✓' : 'Message sent successfully ✓');
      await fetchData();
    } catch (error) {
      console.error('Failed to send message:', error);
      nassaqError(isRTL ? 'فشل إرسال الرسالة' : 'Failed to send message');
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
      toast.success(isRTL ? 'تم تحديث الرسالة المجدولة ✓' : 'Scheduled message updated ✓');
      setEditScheduledOpen(false);
      setSelectedMessage(null);
      await fetchData();
    } catch (error) {
      console.error('Failed to update message:', error);
      nassaqError(isRTL ? 'فشل تحديث الرسالة' : 'Failed to update message');
    } finally {
      setSending(false);
    }
  };

  // Delete message
  const handleDeleteMessage = async () => {
    if (!messageToDelete) return;
    
    try {
      await api.delete(`/communication/${messageToDelete.id}`);
      toast.success(isRTL ? 'تم حذف الرسالة ✓' : 'Message deleted ✓');
      setDeleteConfirmOpen(false);
      setMessageToDelete(null);
      await fetchData();
    } catch (error) {
      console.error('Failed to delete message:', error);
      nassaqError(isRTL ? 'فشل حذف الرسالة' : 'Failed to delete message');
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

  // Apply template
  const handleTemplateSelect = (template) => {
    setNewMessage(prev => ({
      ...prev,
      title: template.name || template.name_en,
      content: template.content_template || ''
    }));
    setTemplatesOpen(false);
    toast.success(isRTL ? 'تم تطبيق القالب' : 'Template applied');
  };

  // Get audience label
  const getAudienceLabel = (audience) => {
    const labels = {
      all: isRTL ? 'الجميع' : 'Everyone',
      teachers: isRTL ? 'المعلمين' : 'Teachers',
      students: isRTL ? 'الطلاب' : 'Students',
      parents: isRTL ? 'أولياء الأمور' : 'Parents'
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
    { id: 'inbox', label: isRTL ? 'صندوق الوارد' : 'Inbox', icon: Inbox, badge: unreadCount },
    { id: 'compose', label: isRTL ? 'إنشاء رسالة' : 'Compose', icon: MessageSquare },
    { id: 'sent', label: isRTL ? 'المرسلة' : 'Sent', icon: Send, badge: sentMessages.length },
    { id: 'scheduled', label: isRTL ? 'المجدولة' : 'Scheduled', icon: Clock, badge: scheduledMessages.length },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="communication-center-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'مركز التواصل والإشعارات' : 'Communication & Notifications Center'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? 'إرسال واستقبال الرسائل والإشعارات' : 'Send and receive messages and notifications'}
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
                {isRTL ? 'تحديث' : 'Refresh'}
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-1 mt-4 bg-muted/50 rounded-xl p-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
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
                  <h2 className="font-cairo text-lg font-semibold">{isRTL ? 'صندوق الوارد' : 'Inbox'}</h2>
                  {unreadCount > 0 && (
                    <Badge variant="destructive" className="font-cairo">{unreadCount} {isRTL ? 'جديدة' : 'new'}</Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {['all', 'unread', 'read'].map((f) => (
                    <Button key={f} variant={inboxFilter === f ? 'default' : 'outline'} size="sm" className="rounded-lg text-xs"
                      onClick={() => setInboxFilter(f)}>
                      {f === 'all' ? (isRTL ? 'الكل' : 'All') : f === 'unread' ? (isRTL ? 'غير مقروءة' : 'Unread') : (isRTL ? 'مقروءة' : 'Read')}
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
                        ? (isRTL ? 'لا توجد رسائل غير مقروءة' : 'No unread messages')
                        : (isRTL ? 'صندوق الوارد فارغ' : 'Your inbox is empty')}
                    </p>
                    <p className="text-sm text-muted-foreground/60 font-tajawal mt-1">
                      {isRTL ? 'ستظهر الرسائل الجديدة هنا' : 'New messages will appear here'}
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
                                  {isRTL ? 'من:' : 'From:'} {msg.sender_name}
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
                                    {isRTL ? 'المرسل:' : 'Sender:'} {msg.sender_name}
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
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="card-nassaq cursor-pointer hover:ring-2 hover:ring-brand-navy/50 transition-all"
                  onClick={() => setActiveTab('sent')} data-testid="sent-messages-card">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                      <Send className="h-6 w-6 text-brand-navy" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{sentMessages.length}</p>
                      <p className="text-sm text-muted-foreground">{isRTL ? 'رسائل مرسلة' : 'Sent Messages'}</p>
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
                      <p className="text-sm text-muted-foreground">{isRTL ? 'صندوق الوارد' : 'Inbox'}</p>
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
                      <p className="text-sm text-muted-foreground">{isRTL ? 'مجدولة' : 'Scheduled'}</p>
                    </div>
                  </CardContent>
                </Card>
                <Card className="card-nassaq cursor-pointer hover:ring-2 hover:ring-brand-purple/50 transition-all"
                  onClick={() => setTemplatesOpen(true)} data-testid="templates-card">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-brand-purple/10 flex items-center justify-center">
                      <FileText className="h-6 w-6 text-brand-purple" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{templates.length}</p>
                      <p className="text-sm text-muted-foreground">{isRTL ? 'قوالب جاهزة' : 'Templates'}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="card-nassaq lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="font-cairo flex items-center gap-2">
                      <MessageSquare className="h-5 w-5 text-brand-turquoise" />
                      {isRTL ? 'إنشاء رسالة جديدة' : 'Compose New Message'}
                    </CardTitle>
                    <CardDescription>
                      {isRTL ? 'أرسل رسالة للمستخدمين في مدرستك' : 'Send a message to users in your school'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <Label className="text-sm font-medium mb-2 block">
                        {isRTL ? 'الجمهور المستهدف' : 'Target Audience'} *
                      </Label>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {audienceGroups.map((group) => {
                          const Icon = getAudienceIcon(group.icon);
                          const isSelected = newMessage.audience === group.id;
                          return (
                            <Button key={group.id} variant={isSelected ? 'default' : 'outline'}
                              className={`justify-start rounded-xl h-auto py-3 ${isSelected ? 'bg-brand-navy' : ''}`}
                              onClick={() => setNewMessage(prev => ({ ...prev, audience: group.id }))}
                              data-testid={`audience-btn-${group.id}`}>
                              <Icon className="h-4 w-4 me-2" />
                              <div className="text-start">
                                <p className="text-sm">{isRTL ? group.name : group.name_en}</p>
                                <p className="text-xs text-muted-foreground">{group.count.toLocaleString()}</p>
                              </div>
                            </Button>
                          );
                        })}
                      </div>
                    </div>
                    <div>
                      <Label className="text-sm font-medium mb-2 block">
                        {isRTL ? 'عنوان الرسالة' : 'Message Title'} *
                      </Label>
                      <Input value={newMessage.title}
                        onChange={(e) => setNewMessage(prev => ({ ...prev, title: e.target.value }))}
                        placeholder={isRTL ? 'أدخل عنوان الرسالة...' : 'Enter message title...'}
                        className="rounded-xl" data-testid="message-title-input" />
                    </div>
                    <div>
                      <Label className="text-sm font-medium mb-2 block">
                        {isRTL ? 'نص الرسالة' : 'Message Content'} *
                      </Label>
                      <Textarea value={newMessage.content}
                        onChange={(e) => setNewMessage(prev => ({ ...prev, content: e.target.value }))}
                        placeholder={isRTL ? 'اكتب رسالتك هنا...' : 'Write your message here...'}
                        className="rounded-xl min-h-[150px]" data-testid="message-content-input" />
                    </div>
                    <div>
                      <Label className="text-sm font-medium mb-2 block">
                        {isRTL ? 'جدولة الإرسال (اختياري)' : 'Schedule Send (Optional)'}
                      </Label>
                      <Input type="datetime-local" value={newMessage.scheduled_at}
                        onChange={(e) => setNewMessage(prev => ({ ...prev, scheduled_at: e.target.value }))}
                        className="rounded-xl" data-testid="schedule-input" />
                    </div>
                    <div className="flex justify-end gap-3 pt-4">
                      <Button variant="outline" className="rounded-xl"
                        onClick={() => setNewMessage({ title: '', content: '', audience: '', scheduled_at: '' })}>
                        {isRTL ? 'مسح' : 'Clear'}
                      </Button>
                      {newMessage.scheduled_at && (
                        <Button variant="secondary" className="rounded-xl"
                          onClick={() => handleSendMessage(true)}
                          disabled={sending || !newMessage.title || !newMessage.content || !newMessage.audience}
                          data-testid="schedule-btn">
                          {sending ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <Clock className="h-4 w-4 me-2" />}
                          {isRTL ? 'جدولة' : 'Schedule'}
                        </Button>
                      )}
                      <Button className="rounded-xl bg-brand-navy hover:bg-brand-navy/90"
                        onClick={() => handleSendMessage(false)}
                        disabled={sending || !newMessage.title || !newMessage.content || !newMessage.audience}
                        data-testid="send-now-btn">
                        {sending ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <Send className="h-4 w-4 me-2" />}
                        {isRTL ? 'إرسال الآن' : 'Send Now'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                <div className="space-y-6">
                  <Card className="card-nassaq">
                    <CardHeader>
                      <CardTitle className="font-cairo text-lg flex items-center gap-2">
                        <FileText className="h-5 w-5 text-brand-purple" />
                        {isRTL ? 'قوالب جاهزة' : 'Quick Templates'}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {templates.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                          {isRTL ? 'لا توجد قوالب' : 'No templates'}
                        </p>
                      ) : (
                        templates.slice(0, 5).map((template) => {
                          const Icon = iconMap[template.icon] || Bell;
                          return (
                            <Button key={template.id} variant="ghost" className="w-full justify-start rounded-xl"
                              onClick={() => handleTemplateSelect(template)} data-testid={`template-btn-${template.id}`}>
                              <Icon className="h-4 w-4 me-2" />
                              {isRTL ? template.name : template.name_en}
                            </Button>
                          );
                        })
                      )}
                    </CardContent>
                  </Card>

                  <Card className="card-nassaq">
                    <CardHeader>
                      <CardTitle className="font-cairo text-lg">{isRTL ? 'آخر الرسائل' : 'Recent Messages'}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {sentMessages.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                          {isRTL ? 'لا توجد رسائل مرسلة' : 'No sent messages'}
                        </p>
                      ) : (
                        sentMessages.slice(0, 3).map((msg) => (
                          <div key={msg.id} className="p-3 bg-muted/30 rounded-xl cursor-pointer hover:bg-muted/50 transition-colors"
                            onClick={() => { setSelectedMessage(msg); setViewMessageOpen(true); }}>
                            <p className="text-sm font-medium line-clamp-1">{msg.title}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="secondary" className="text-xs">{getAudienceLabel(msg.audience)}</Badge>
                              <span className="text-xs text-muted-foreground">{formatDate(msg.sent_at || msg.created_at)}</span>
                            </div>
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </>
          )}

          {activeTab === 'sent' && (
            <div className="space-y-4">
              <h2 className="font-cairo text-lg font-semibold flex items-center gap-2">
                <Send className="h-5 w-5 text-brand-navy" />
                {isRTL ? 'الرسائل المرسلة' : 'Sent Messages'}
                <Badge variant="secondary" className="font-cairo">{sentMessages.length}</Badge>
              </h2>
              {sentMessages.length === 0 ? (
                <Card className="card-nassaq">
                  <CardContent className="py-16 text-center">
                    <Send className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                    <p className="text-muted-foreground font-cairo">{isRTL ? 'لا توجد رسائل مرسلة' : 'No sent messages'}</p>
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
                          <Badge variant="default" className="bg-green-500">{isRTL ? 'مرسلة' : 'Sent'}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">{msg.content}</p>
                        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground font-tajawal">
                          <span>{isRTL ? 'الجمهور:' : 'Audience:'} {getAudienceLabel(msg.audience)}</span>
                          <span>{isRTL ? 'المستلمون:' : 'Recipients:'} {msg.recipient_count || msg.sent_count || 0}</span>
                          <span>{formatDate(msg.sent_at || msg.created_at)}</span>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'scheduled' && (
            <div className="space-y-4">
              <h2 className="font-cairo text-lg font-semibold flex items-center gap-2">
                <Clock className="h-5 w-5 text-yellow-600" />
                {isRTL ? 'الرسائل المجدولة' : 'Scheduled Messages'}
                <Badge variant="secondary" className="font-cairo">{scheduledMessages.length}</Badge>
              </h2>
              {scheduledMessages.length === 0 ? (
                <Card className="card-nassaq">
                  <CardContent className="py-16 text-center">
                    <Clock className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                    <p className="text-muted-foreground font-cairo">{isRTL ? 'لا توجد رسائل مجدولة' : 'No scheduled messages'}</p>
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
                            {isRTL ? 'مجدولة' : 'Scheduled'}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2">{msg.content}</p>
                        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground font-tajawal">
                          <span>{isRTL ? 'الجمهور:' : 'Audience:'} {getAudienceLabel(msg.audience)}</span>
                          <span>•</span>
                          <span>{isRTL ? 'موعد الإرسال:' : 'Send at:'} {formatDate(msg.scheduled_at)}</span>
                        </div>
                        <div className="flex gap-2 mt-4">
                          <Button size="sm" variant="outline" className="flex-1"
                            onClick={() => { setSelectedMessage({...msg}); setEditScheduledOpen(true); }}
                            data-testid={`edit-scheduled-${msg.id}`}>
                            <Edit className="h-4 w-4 me-1" />
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                          <Button size="sm" className="flex-1 bg-green-600 hover:bg-green-700"
                            onClick={() => handleSendScheduledNow(msg.id)} disabled={sending}
                            data-testid={`send-now-scheduled-${msg.id}`}>
                            {sending ? <Loader2 className="h-4 w-4 me-1 animate-spin" /> : <Send className="h-4 w-4 me-1" />}
                            {isRTL ? 'إرسال الآن' : 'Send Now'}
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
                {isRTL ? 'تعديل الرسالة المجدولة' : 'Edit Scheduled Message'}
              </DialogTitle>
            </DialogHeader>
            {selectedMessage && (
              <div className="space-y-4 mt-4">
                <div>
                  <Label>{isRTL ? 'الجمهور المستهدف' : 'Target Audience'}</Label>
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
                  <Label>{isRTL ? 'عنوان الرسالة' : 'Message Title'}</Label>
                  <Input
                    value={selectedMessage.title}
                    onChange={(e) => setSelectedMessage({...selectedMessage, title: e.target.value})}
                    className="rounded-xl mt-1"
                  />
                </div>
                <div>
                  <Label>{isRTL ? 'نص الرسالة' : 'Message Content'}</Label>
                  <Textarea
                    value={selectedMessage.content}
                    onChange={(e) => setSelectedMessage({...selectedMessage, content: e.target.value})}
                    className="rounded-xl mt-1"
                    rows={4}
                  />
                </div>
                <div>
                  <Label>{isRTL ? 'موعد الإرسال' : 'Scheduled Time'}</Label>
                  <Input
                    type="datetime-local"
                    value={selectedMessage.scheduled_at?.slice(0, 16) || ''}
                    onChange={(e) => setSelectedMessage({...selectedMessage, scheduled_at: e.target.value})}
                    className="rounded-xl mt-1"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button variant="outline" onClick={() => setEditScheduledOpen(false)}>
                    {isRTL ? 'إلغاء' : 'Cancel'}
                  </Button>
                  <Button onClick={handleUpdateScheduledMessage} disabled={sending}>
                    {sending ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <CheckCircle className="h-4 w-4 me-2" />}
                    {isRTL ? 'حفظ التغييرات' : 'Save Changes'}
                  </Button>
                </DialogFooter>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Templates Dialog */}
        <Dialog open={templatesOpen} onOpenChange={setTemplatesOpen}>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <FileText className="h-5 w-5 text-brand-purple" />
                {isRTL ? 'القوالب الجاهزة' : 'Message Templates'}
              </DialogTitle>
              <DialogDescription>
                {isRTL ? 'اختر قالباً لتعبئة نموذج الرسالة تلقائياً' : 'Choose a template to auto-fill the message form'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 mt-4">
              {templates.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                  <p className="text-muted-foreground">{isRTL ? 'لا توجد قوالب' : 'No templates available'}</p>
                </div>
              ) : (
                templates.map((template) => {
                  const Icon = iconMap[template.icon] || Bell;
                  return (
                    <div 
                      key={template.id}
                      className="p-4 bg-muted/30 rounded-xl cursor-pointer hover:bg-muted/50 transition-colors border border-transparent hover:border-brand-purple/30"
                      onClick={() => handleTemplateSelect(template)}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 rounded-lg bg-brand-purple/10 flex items-center justify-center">
                          <Icon className="h-5 w-5 text-brand-purple" />
                        </div>
                        <div>
                          <p className="font-medium">{template.name}</p>
                          <p className="text-xs text-muted-foreground">{template.name_en}</p>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {template.content_template?.slice(0, 100)}...
                      </p>
                    </div>
                  );
                })
              )}
            </div>
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
                  <Badge variant="outline">{selectedMessage.recipient_count || 0} {isRTL ? 'مستلم' : 'recipients'}</Badge>
                </div>
                <p className="text-sm whitespace-pre-wrap">{selectedMessage.content}</p>
                <p className="text-xs text-muted-foreground">
                  {isRTL ? 'تاريخ الإرسال:' : 'Sent at:'} {formatDate(selectedMessage.sent_at || selectedMessage.created_at)}
                </p>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-500" />
                {isRTL ? 'تأكيد الحذف' : 'Confirm Delete'}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {isRTL 
                  ? `هل أنت متأكد من حذف الرسالة "${messageToDelete?.title}"؟ لا يمكن التراجع عن هذا الإجراء.`
                  : `Are you sure you want to delete "${messageToDelete?.title}"? This action cannot be undone.`
                }
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{isRTL ? 'إلغاء' : 'Cancel'}</AlertDialogCancel>
              <AlertDialogAction 
                onClick={handleDeleteMessage}
                className="bg-red-500 hover:bg-red-600"
              >
                {isRTL ? 'حذف' : 'Delete'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </Sidebar>
  );
};

export default CommunicationCenterPage;
