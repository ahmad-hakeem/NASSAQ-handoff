import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Trash2,
  Filter,
  RefreshCw,
  Calendar,
  CalendarCheck,
  ClipboardList,
  AlertTriangle,
  Info,
  MessageSquare,
  Megaphone,
  Sun,
  Moon,
  Globe,
  Eye,
  Clock,
  Send,
  Users,
  Building2,
  GraduationCap,
  UserCheck,
  Inbox,
  Mail,
  Plus,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

const notificationTypeConfig = {
  system: { 
    icon: Info, 
    label: { ar: 'النظام', en: 'System' }, 
    color: 'bg-gray-500',
    iconColor: 'text-gray-500'
  },
  attendance: { 
    icon: CalendarCheck, 
    label: { ar: 'الحضور', en: 'Attendance' }, 
    color: 'bg-blue-500',
    iconColor: 'text-blue-500'
  },
  schedule: { 
    icon: Calendar, 
    label: { ar: 'الجدول', en: 'Schedule' }, 
    color: 'bg-purple-500',
    iconColor: 'text-purple-500'
  },
  assessment: { 
    icon: ClipboardList, 
    label: { ar: 'التقييمات', en: 'Assessments' }, 
    color: 'bg-green-500',
    iconColor: 'text-green-500'
  },
  behaviour: { 
    icon: AlertTriangle, 
    label: { ar: 'السلوك', en: 'Behaviour' }, 
    color: 'bg-yellow-500',
    iconColor: 'text-yellow-500'
  },
  communication: { 
    icon: MessageSquare, 
    label: { ar: 'التواصل', en: 'Communication' }, 
    color: 'bg-teal-500',
    iconColor: 'text-teal-500'
  },
  announcement: { 
    icon: Megaphone, 
    label: { ar: 'الإعلانات', en: 'Announcements' }, 
    color: 'bg-orange-500',
    iconColor: 'text-orange-500'
  },
};

const priorityConfig = {
  low: { label: { ar: 'منخفضة', en: 'Low' }, color: 'bg-gray-400' },
  medium: { label: { ar: 'متوسطة', en: 'Medium' }, color: 'bg-blue-400' },
  high: { label: { ar: 'مرتفعة', en: 'High' }, color: 'bg-orange-500' },
  critical: { label: { ar: 'حرجة', en: 'Critical' }, color: 'bg-red-600' },
};

export const CommunicationNotificationsPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const navigate = useNavigate();
  
  // Notifications State
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('all');
  const [filterRead, setFilterRead] = useState('all');
  const [analytics, setAnalytics] = useState(null);

  // Communication State
  const [newMessage, setNewMessage] = useState('');
  const [messageTitle, setMessageTitle] = useState('');
  const [selectedAudience, setSelectedAudience] = useState('all');
  const [activeTab, setActiveTab] = useState('notifications');
  
  // Communication Stats & Data
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [commStats, setCommStats] = useState({
    total_notifications: 0,
    unread_notifications: 0,
    sent_messages: 0,
    received_messages: 0,
    scheduled_messages: 0,
    failed_messages: 0,
  });
  const [scheduledMessages, setScheduledMessages] = useState([]);
  const [sentMessages, setSentMessages] = useState([]);
  const [audienceCounts, setAudienceCounts] = useState({
    all: 0, schools: 0, teachers: 0, students: 0, principals: 0, parents: 0
  });
  const [sendingMessage, setSendingMessage] = useState(false);

  const messageStats = {
    sent: commStats.sent_messages || 0,
    received: commStats.received_messages || 0,
    pending: commStats.scheduled_messages || 0,
  };

  const audienceGroups = [
    { id: 'all', name: t('everyone'), count: audienceCounts.all, icon: Users },
    { id: 'schools', name: t('schools2'), count: audienceCounts.schools, icon: Building2 },
    { id: 'teachers', name: t('teachers2'), count: audienceCounts.teachers, icon: UserCheck },
    { id: 'students', name: t('students'), count: audienceCounts.students, icon: GraduationCap },
  ];

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      let url = '/notifications?limit=100';
      if (filterType && filterType !== 'all') {
        url += `&notification_type=${filterType}`;
      }
      if (filterRead !== 'all') {
        url += `&read_status=${filterRead === 'read'}`;
      }
      
      const response = await api.get(url);
      setNotifications(response.data);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  }, [api, filterType, filterRead]);

  // Fetch communication stats
  const fetchCommunicationStats = useCallback(async () => {
    try {
      const response = await api.get('/communication/stats');
      setCommStats(response.data);
    } catch (error) {
      console.error('Failed to fetch communication stats:', error);
    }
  }, [api]);

  // Fetch scheduled messages
  const fetchScheduledMessages = useCallback(async () => {
    try {
      const response = await api.get('/communication/scheduled');
      setScheduledMessages(response.data.messages || []);
    } catch (error) {
      console.error('Failed to fetch scheduled messages:', error);
    }
  }, [api]);

  // Fetch sent messages
  const fetchSentMessages = useCallback(async () => {
    try {
      const response = await api.get('/communication/sent');
      setSentMessages(response.data.messages || []);
    } catch (error) {
      console.error('Failed to fetch sent messages:', error);
    }
  }, [api]);

  // Fetch audience counts
  const fetchAudienceCounts = useCallback(async () => {
    try {
      const response = await api.get('/communication/audience-counts');
      setAudienceCounts(response.data);
    } catch (error) {
      console.error('Failed to fetch audience counts:', error);
    }
  }, [api]);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get('/notifications/analytics');
      setAnalytics(response.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    }
  };

  useEffect(() => {
    fetchNotifications();
    if (user?.role === 'platform_admin' || user?.role === 'school_principal') {
      fetchAnalytics();
      fetchCommunicationStats();
      fetchScheduledMessages();
      fetchSentMessages();
      fetchAudienceCounts();
    }
  }, [fetchNotifications, user?.role, fetchCommunicationStats, fetchScheduledMessages, fetchSentMessages, fetchAudienceCounts]);

  const handleMarkAsRead = async (notificationId) => {
    try {
      await api.put(`/notifications/${notificationId}/read`);
      setNotifications(prev => 
        prev.map(n => n.id === notificationId ? { ...n, read_status: true } : n)
      );
      toast.success(t('markedAsRead'));
    } catch (error) {
      nassaqError(t('failedToMarkAsRead'));
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await api.put('/notifications/mark-all-read');
      setNotifications(prev => prev.map(n => ({ ...n, read_status: true })));
      toast.success(t('allMarkedAsRead'));
    } catch (error) {
      nassaqError(t('failedToMarkAllAsRead'));
    }
  };

  const handleDeleteNotification = async (notificationId) => {
    try {
      await api.delete(`/notifications/${notificationId}`);
      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      toast.success(t('notificationDeleted'));
    } catch (error) {
      nassaqError(t('failedToDeleteNotification'));
    }
  };

  const handleNotificationClick = (notification) => {
    if (!notification.read_status) {
      handleMarkAsRead(notification.id);
    }
    if (notification.action_url) {
      navigate(notification.action_url);
    }
  };

  const handleSendMessage = async () => {
    if (!messageTitle.trim() || !newMessage.trim()) {
      nassaqError(t('pleaseFillAllFields'));
      return;
    }
    
    setSendingMessage(true);
    try {
      const response = await api.post('/communication/broadcast', {
        title: messageTitle,
        content: newMessage,
        audience: selectedAudience,
        channels: ['in_app'],
        priority: 'medium'
      });
      
      if (response.data.success) {
        toast.success(
          isRTL 
            ? `تم إرسال الرسالة إلى ${response.data.recipients_count} مستخدم` 
            : `Message sent to ${response.data.recipients_count} users`
        );
        setMessageTitle('');
        setNewMessage('');
        // Refresh stats and messages
        fetchCommunicationStats();
        fetchSentMessages();
      }
    } catch (error) {
      console.error('Error sending message:', error);
      nassaqError(t('failedToSendMessage'));
    } finally {
      setSendingMessage(false);
    }
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return isRTL ? 'الآن' : 'Just now';
    if (minutes < 60) return isRTL ? `منذ ${minutes} دقيقة` : `${minutes}m ago`;
    if (hours < 24) return isRTL ? `منذ ${hours} ساعة` : `${hours}h ago`;
    if (days < 7) return isRTL ? `منذ ${days} يوم` : `${days}d ago`;
    return date.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US');
  };

  const unreadCount = notifications.filter(n => !n.read_status).length;

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="communication-notifications-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
                <MessageSquare className="h-7 w-7 text-brand-turquoise" />
                {t('communicationNotifications')}
                {unreadCount > 0 && (
                  <Badge className="bg-red-500 text-white">{unreadCount}</Badge>
                )}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('unifiedCenterForCommunicationAndNotifications')}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button 
                variant="outline"
                onClick={fetchNotifications}
                className="rounded-xl"
              >
                <RefreshCw className="h-4 w-4 me-2" />
                {t('refresh')}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Stats Overview */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                    <Bell className="h-5 w-5 text-brand-navy" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{analytics?.total_notifications || notifications.length}</p>
                    <p className="text-xs text-muted-foreground">{t('notifications')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <BellOff className="h-5 w-5 text-red-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{unreadCount}</p>
                    <p className="text-xs text-muted-foreground">{t('unread2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <Send className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{messageStats.sent}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'رسائل مرسلة' : 'Sent'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="card-nassaq cursor-pointer hover:shadow-lg transition-shadow" onClick={() => setActiveTab('notifications')}>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                    <Inbox className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{messageStats.received}</p>
                    <p className="text-xs text-muted-foreground">{t('received')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="card-nassaq cursor-pointer hover:shadow-lg transition-shadow" onClick={() => setActiveTab('communication')}>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{messageStats.pending}</p>
                    <p className="text-xs text-muted-foreground">{t('scheduled2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full max-w-md grid-cols-2 rounded-xl">
              <TabsTrigger value="notifications" className="rounded-xl flex items-center gap-2">
                <Bell className="h-4 w-4" />
                {t('notifications')}
                {unreadCount > 0 && (
                  <Badge className="bg-red-500 text-white text-xs h-5 w-5 flex items-center justify-center p-0 rounded-full">
                    {unreadCount}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="communication" className="rounded-xl flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                {isRTL ? 'التواصل' : 'Communication'}
              </TabsTrigger>
            </TabsList>

            {/* Notifications Tab */}
            <TabsContent value="notifications" className="space-y-6 mt-6">
              {/* Notifications Filters */}
              <Card className="card-nassaq">
                <CardContent className="p-4">
                  <div className="flex flex-wrap gap-4 items-center justify-between">
                    <div className="flex flex-wrap gap-4 items-center">
                      <div className="flex items-center gap-2">
                        <Filter className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">{t('filter')}</span>
                      </div>
                      
                      <Select value={filterType} onValueChange={setFilterType}>
                        <SelectTrigger className="w-40 rounded-xl">
                          <SelectValue placeholder={t('type4')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('allTypes')}</SelectItem>
                          {Object.entries(notificationTypeConfig).map(([key, config]) => (
                            <SelectItem key={key} value={key}>
                              {isRTL ? config.label.ar : config.label.en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      
                      <Select value={filterRead} onValueChange={setFilterRead}>
                        <SelectTrigger className="w-40 rounded-xl">
                          <SelectValue placeholder={t('status2')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('all')}</SelectItem>
                          <SelectItem value="unread">{t('unread2')}</SelectItem>
                          <SelectItem value="read">{t('read2')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {unreadCount > 0 && (
                      <Button 
                        onClick={handleMarkAllAsRead}
                        className="bg-brand-turquoise hover:bg-brand-turquoise/90 rounded-xl"
                        data-testid="mark-all-read-btn"
                      >
                        <CheckCheck className="h-4 w-4 me-2" />
                        {t('markAllRead2')}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Notifications List */}
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo">{t('notificationLog')}</CardTitle>
                  <CardDescription>
                    {isRTL ? `${notifications.length} إشعار` : `${notifications.length} notifications`}
                  </CardDescription>
                </CardHeader>
                
                <CardContent>
                  <ScrollArea className="h-[500px]">
                    {loading ? (
                      <div className="text-center py-8 text-muted-foreground">
                        {t('loading')}
                      </div>
                    ) : notifications.length === 0 ? (
                      <div className="text-center py-12">
                        <BellOff className="h-16 w-16 mx-auto text-muted-foreground/50 mb-4" />
                        <p className="text-muted-foreground">
                          {t('noNotifications')}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {notifications.map((notification) => {
                          const typeConfig = notificationTypeConfig[notification.notification_type] || notificationTypeConfig.system;
                          const priorityConf = priorityConfig[notification.priority] || priorityConfig.medium;
                          const IconComponent = typeConfig.icon;
                          
                          return (
                            <Card 
                              key={notification.id}
                              className={`cursor-pointer transition-all hover:shadow-md ${
                                !notification.read_status 
                                  ? 'bg-brand-turquoise/5 border-brand-turquoise/30' 
                                  : 'bg-background'
                              }`}
                              onClick={() => handleNotificationClick(notification)}
                            >
                              <CardContent className="p-4">
                                <div className="flex items-start gap-4">
                                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${typeConfig.color}/10`}>
                                    <IconComponent className={`h-5 w-5 ${typeConfig.iconColor}`} />
                                  </div>
                                  
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-start justify-between gap-2">
                                      <div>
                                        <h4 className={`font-medium ${!notification.read_status ? 'font-bold' : ''}`}>
                                          {isRTL ? notification.title : (notification.title_en || notification.title)}
                                        </h4>
                                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                                          {isRTL ? notification.message : (notification.message_en || notification.message)}
                                        </p>
                                      </div>
                                      
                                      <div className="flex flex-col items-end gap-1">
                                        <Badge className={`${typeConfig.color} text-white text-xs`}>
                                          {isRTL ? typeConfig.label.ar : typeConfig.label.en}
                                        </Badge>
                                        {notification.priority !== 'medium' && (
                                          <Badge className={`${priorityConf.color} text-white text-xs`}>
                                            {isRTL ? priorityConf.label.ar : priorityConf.label.en}
                                          </Badge>
                                        )}
                                      </div>
                                    </div>
                                    
                                    <div className="flex items-center justify-between mt-3">
                                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <Clock className="h-3 w-3" />
                                        {formatTimeAgo(notification.created_at)}
                                      </div>
                                      
                                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                                        {!notification.read_status && (
                                          <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => handleMarkAsRead(notification.id)}
                                            className="h-8 rounded-xl"
                                          >
                                            <Check className="h-4 w-4" />
                                          </Button>
                                        )}
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          onClick={() => handleDeleteNotification(notification.id)}
                                          className="h-8 rounded-xl text-red-500 hover:text-red-600"
                                        >
                                          <Trash2 className="h-4 w-4" />
                                        </Button>
                                      </div>
                                    </div>
                                  </div>
                                  
                                  {!notification.read_status && (
                                    <div className="w-2 h-2 rounded-full bg-brand-turquoise animate-pulse" />
                                  )}
                                </div>
                              </CardContent>
                            </Card>
                          );
                        })}
                      </div>
                    )}
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Communication Tab */}
            <TabsContent value="communication" className="space-y-6 mt-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Compose Message */}
                <Card className="card-nassaq lg:col-span-2">
                  <CardHeader>
                    <CardTitle className="font-cairo flex items-center gap-2">
                      <Send className="h-5 w-5 text-brand-turquoise" />
                      {t('composeNewMessage')}
                    </CardTitle>
                    <CardDescription>
                      {t('sendBroadcastMessagesToSchoolsAndUsers')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        {t('targetAudience')}
                      </label>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {audienceGroups.map((group) => (
                          <Button 
                            key={group.id} 
                            variant={selectedAudience === group.id ? 'default' : 'outline'}
                            className={`justify-start rounded-xl h-auto py-3 ${
                              selectedAudience === group.id ? 'bg-brand-navy' : ''
                            }`}
                            onClick={() => setSelectedAudience(group.id)}
                          >
                            <group.icon className="h-4 w-4 me-2" />
                            <div className="text-start">
                              <p className="text-sm">{group.name}</p>
                              <p className="text-xs opacity-70">{group.count.toLocaleString()}</p>
                            </div>
                          </Button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        {t('messageTitle')}
                      </label>
                      <Input 
                        placeholder={t('enterMessageTitle')} 
                        className="rounded-xl"
                        value={messageTitle}
                        onChange={(e) => setMessageTitle(e.target.value)}
                      />
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        {isRTL ? 'نص الرسالة' : 'Message Content'}
                      </label>
                      <Textarea 
                        placeholder={t('writeYourMessageHere')} 
                        className="rounded-xl min-h-[150px]"
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                      />
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                      <Button variant="outline" className="rounded-xl">
                        <Clock className="h-4 w-4 me-2" />
                        {t('schedule2')}
                      </Button>
                      <Button 
                        className="rounded-xl bg-brand-navy hover:bg-brand-navy/90"
                        onClick={handleSendMessage}
                        disabled={sendingMessage}
                      >
                        {sendingMessage ? (
                          <RefreshCw className="h-4 w-4 me-2 animate-spin" />
                        ) : (
                          <Send className="h-4 w-4 me-2" />
                        )}
                        {t('sendNow')}
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Recent Messages */}
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="font-cairo text-lg flex items-center gap-2">
                      <Mail className="h-5 w-5 text-brand-purple" />
                      {t('recentMessages2')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[400px]">
                      <div className="space-y-3">
                        {/* Scheduled Messages */}
                        {scheduledMessages.length > 0 && (
                          <div className="mb-4">
                            <p className="text-xs text-muted-foreground mb-2 font-semibold">
                              {t('scheduledMessages')}
                            </p>
                            {scheduledMessages.map((msg) => (
                              <div key={msg.id} className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl mb-2">
                                <div className="flex items-center justify-between mb-2">
                                  <p className="text-sm font-medium line-clamp-1">{msg.title}</p>
                                  <Badge variant="secondary" className="text-xs bg-amber-500/20 text-amber-600">
                                    <Clock className="h-3 w-3 me-1" />
                                    {t('scheduled2')}
                                  </Badge>
                                </div>
                                <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                                  {msg.message?.substring(0, 100)}...
                                </p>
                                <div className="flex items-center justify-between text-xs text-muted-foreground">
                                  <span>
                                    {msg.target_audience === 'all' ? (t('everyone')) :
                                     msg.target_audience === 'teachers' ? (t('teachers2')) :
                                     msg.target_audience === 'students' ? (t('students')) :
                                     msg.target_audience}
                                  </span>
                                  <span>{new Date(msg.scheduled_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US')}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* Sent Messages */}
                        {sentMessages.length > 0 ? (
                          sentMessages.map((msg) => (
                            <div key={msg.id} className="p-3 bg-muted/30 rounded-xl hover:bg-muted/50 transition-colors cursor-pointer">
                              <div className="flex items-center justify-between mb-2">
                                <p className="text-sm font-medium line-clamp-1">{msg.title}</p>
                                <Badge variant="default" className="text-xs bg-green-500/20 text-green-600">
                                  <Check className="h-3 w-3 me-1" />
                                  {t('sent2')}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{msg.message}</p>
                              <div className="flex items-center justify-between text-xs text-muted-foreground">
                                <span>
                                  {msg.target_audience === 'all' ? (t('everyone')) :
                                   msg.target_audience === 'teachers' ? (t('teachers2')) :
                                   msg.target_audience === 'students' ? (t('students')) :
                                   msg.target_audience}
                                </span>
                                <span>{msg.sent_at ? new Date(msg.sent_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US') : ''}</span>
                              </div>
                            </div>
                          ))
                        ) : (
                          <div className="text-center py-8 text-muted-foreground">
                            <Mail className="h-12 w-12 mx-auto mb-3 opacity-30" />
                            <p className="text-sm">{t('noSentMessages')}</p>
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
