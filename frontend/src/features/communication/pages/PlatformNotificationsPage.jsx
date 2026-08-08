import { useState, useEffect } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { toast } from 'sonner';
import {
  Bell,
  BellRing,
  CheckCircle,
  XCircle,
  Sun,
  Moon,
  Globe,
  RefreshCw,
  Send,
  Clock,
  AlertTriangle,
  Info,
  MessageSquare,
  Users,
  Building2,
  Filter,
  Search,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Eye,
  Mail,
} from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { ScrollArea } from '@/shared/components/ui/scroll-area';

// Sample notifications removed - will be fetched from API
const sampleNotifications = [];

export const PlatformNotificationsPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedNotification, setSelectedNotification] = useState(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Fetch notifications from API
  useEffect(() => {
    const fetchNotifications = async () => {
      try {
        setLoading(true);
        const response = await api.get('/notifications');
        if (response.data && Array.isArray(response.data)) {
          setNotifications(response.data);
        }
      } catch (error) {
        console.error('Error fetching notifications:', error);
        setNotifications([]);
      } finally {
        setLoading(false);
      }
    };
    fetchNotifications();
  }, [api]);

  const getTypeIcon = (type) => {
    switch (type) {
      case 'system':
        return <Bell className="h-4 w-4 text-brand-navy" />;
      case 'alert':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'info':
        return <Info className="h-4 w-4 text-blue-500" />;
      case 'reminder':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      default:
        return <MessageSquare className="h-4 w-4 text-gray-500" />;
    }
  };

  const getTypeBadge = (type) => {
    const types = {
      system: { label: t('system2'), color: 'bg-brand-navy' },
      alert: { label: t('alert'), color: 'bg-red-500' },
      info: { label: t('info2'), color: 'bg-blue-500' },
      reminder: { label: t('reminder'), color: 'bg-yellow-500' },
    };
    const typeInfo = types[type] || { label: type, color: 'bg-gray-500' };
    return <Badge className={`${typeInfo.color} text-white`}>{typeInfo.label}</Badge>;
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'sent':
        return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">{t('sent3')}</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">{t('pending3')}</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{t('failed')}</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getRecipientLabel = (recipient) => {
    const recipients = {
      all: t('everyone'),
      admins: t('admins'),
      platform_admin: t('platformAdmin'),
      schools: t('schools2'),
      teachers: t('teachers2'),
      students: t('students'),
      parents: t('parents'),
    };
    return recipients[recipient] || recipient;
  };

  const filteredNotifications = notifications.filter(n => {
    const matchesSearch = 
      (isRTL ? n.title : n.title_en)?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (isRTL ? n.message : n.message_en)?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesType = typeFilter === 'all' || n.type === typeFilter;
    const matchesStatus = statusFilter === 'all' || n.status === statusFilter;
    
    return matchesSearch && matchesType && matchesStatus;
  });

  const paginatedNotifications = filteredNotifications.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPages = Math.ceil(filteredNotifications.length / itemsPerPage);

  const stats = {
    total: notifications.length,
    sent: notifications.filter(n => n.status === 'sent').length,
    pending: notifications.filter(n => n.status === 'pending').length,
    failed: notifications.filter(n => n.status === 'failed').length,
  };

  const handleSendNotification = () => {
    toast.info(t('comingSoonSendNewNotification'));
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="platform-notifications-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {t('notifications')}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('managePlatformNotifications')}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setLoading(true)} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-4 sm:p-6 space-y-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                    <Bell className="h-5 w-5 text-brand-navy" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.total}</p>
                    <p className="text-xs text-muted-foreground">{t('total3')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.sent}</p>
                    <p className="text-xs text-muted-foreground">{t('sent2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-yellow-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.pending}</p>
                    <p className="text-xs text-muted-foreground">{t('pending3')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <XCircle className="h-5 w-5 text-red-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.failed}</p>
                    <p className="text-xs text-muted-foreground">{t('failed2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Notifications Table */}
          <Card className="card-nassaq">
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <CardTitle className="font-cairo">{isRTL ? 'سجل الإشعارات' : 'Notifications Log'}</CardTitle>
                  <CardDescription>{t('allNotificationsSentFromThePlatform')}</CardDescription>
                </div>
                
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('search')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-[180px] rounded-xl"
                    />
                  </div>
                  
                  <Select value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger className="w-[130px] rounded-xl">
                      <SelectValue placeholder={t('type4')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('all')}</SelectItem>
                      <SelectItem value="system">{t('system2')}</SelectItem>
                      <SelectItem value="alert">{t('alert')}</SelectItem>
                      <SelectItem value="info">{t('info2')}</SelectItem>
                      <SelectItem value="reminder">{t('reminder')}</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[130px] rounded-xl">
                      <SelectValue placeholder={t('status2')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('all')}</SelectItem>
                      <SelectItem value="sent">{t('sent3')}</SelectItem>
                      <SelectItem value="pending">{t('pending3')}</SelectItem>
                      <SelectItem value="failed">{t('failed')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            
            <CardContent>
              <div className="rounded-xl border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('type4')}</TableHead>
                      <TableHead>{isRTL ? 'العنوان' : 'Title'}</TableHead>
                      <TableHead>{t('recipient')}</TableHead>
                      <TableHead>{t('status2')}</TableHead>
                      <TableHead>{t('date')}</TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedNotifications.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          {isRTL ? 'لا توجد إشعارات' : 'No notifications found'}
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedNotifications.map((notification) => (
                        <TableRow key={notification.id}>
                          <TableCell>{getTypeBadge(notification.type)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {getTypeIcon(notification.type)}
                              <span className="font-medium">{isRTL ? notification.title : notification.title_en}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <Users className="h-4 w-4 text-muted-foreground" />
                              {getRecipientLabel(notification.recipient)}
                            </div>
                          </TableCell>
                          <TableCell>{getStatusBadge(notification.status)}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {new Date(notification.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })}
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => {
                                setSelectedNotification(notification);
                                setViewDialogOpen(true);
                              }}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
              
              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    {isRTL 
                      ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, filteredNotifications.length)} من ${filteredNotifications.length}`
                      : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, filteredNotifications.length)} of ${filteredNotifications.length}`
                    }
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                      className="rounded-xl"
                    >
                      {isRTL ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                    </Button>
                    <span className="text-sm">{currentPage} / {totalPages}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                      className="rounded-xl"
                    >
                      {isRTL ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Note about notification engine */}
          <Card className="card-nassaq bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-800 dark:text-blue-200">
                    {t('note')}
                  </p>
                  <p className="text-sm text-blue-700 dark:text-blue-300">
                    {t('thisPageDisplaysTheLogOfNotificationsSentFromThePl')
                    }
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* View Notification Dialog */}
        <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                {selectedNotification && getTypeIcon(selectedNotification.type)}
                {t('notificationDetails')}
              </DialogTitle>
            </DialogHeader>
            
            {selectedNotification && (
              <div className="space-y-4 py-4">
                <div className="flex items-center gap-2">
                  {getTypeBadge(selectedNotification.type)}
                  {getStatusBadge(selectedNotification.status)}
                </div>
                
                <div>
                  <h3 className="font-bold text-lg">
                    {isRTL ? selectedNotification.title : selectedNotification.title_en}
                  </h3>
                  <p className="text-sm text-muted-foreground mt-2">
                    {isRTL ? selectedNotification.message : selectedNotification.message_en}
                  </p>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-muted rounded-xl p-3">
                    <p className="text-sm text-muted-foreground">{t('recipient')}</p>
                    <p className="font-medium">{getRecipientLabel(selectedNotification.recipient)}</p>
                  </div>
                  <div className="bg-muted rounded-xl p-3">
                    <p className="text-sm text-muted-foreground">{t('date')}</p>
                    <p className="font-medium">
                      {new Date(selectedNotification.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US')}
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setViewDialogOpen(false)} className="rounded-xl">
                {t('close')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};
