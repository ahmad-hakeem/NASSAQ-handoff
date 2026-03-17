import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
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
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';

// Sample notifications removed - will be fetched from API
const sampleNotifications = [];

export const PlatformNotificationsPage = () => {
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
      system: { label: isRTL ? 'نظام' : 'System', color: 'bg-brand-navy' },
      alert: { label: isRTL ? 'تنبيه' : 'Alert', color: 'bg-red-500' },
      info: { label: isRTL ? 'معلومات' : 'Info', color: 'bg-blue-500' },
      reminder: { label: isRTL ? 'تذكير' : 'Reminder', color: 'bg-yellow-500' },
    };
    const typeInfo = types[type] || { label: type, color: 'bg-gray-500' };
    return <Badge className={`${typeInfo.color} text-white`}>{typeInfo.label}</Badge>;
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'sent':
        return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">{isRTL ? 'مرسل' : 'Sent'}</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">{isRTL ? 'قيد المعالجة' : 'Pending'}</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{isRTL ? 'فشل' : 'Failed'}</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getRecipientLabel = (recipient) => {
    const recipients = {
      all: isRTL ? 'الجميع' : 'Everyone',
      admins: isRTL ? 'المدراء' : 'Admins',
      platform_admin: isRTL ? 'مدير المنصة' : 'Platform Admin',
      schools: isRTL ? 'المدارس' : 'Schools',
      teachers: isRTL ? 'المعلمين' : 'Teachers',
      students: isRTL ? 'الطلاب' : 'Students',
      parents: isRTL ? 'أولياء الأمور' : 'Parents',
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
    toast.info(isRTL ? 'قريباً - إرسال إشعار جديد' : 'Coming soon - Send new notification');
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="platform-notifications-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'الإشعارات' : 'Notifications'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? 'إدارة إشعارات المنصة' : 'Manage platform notifications'}
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
                    <p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي الإشعارات' : 'Total'}</p>
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
                    <p className="text-xs text-muted-foreground">{isRTL ? 'مرسلة' : 'Sent'}</p>
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
                    <p className="text-xs text-muted-foreground">{isRTL ? 'قيد المعالجة' : 'Pending'}</p>
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
                    <p className="text-xs text-muted-foreground">{isRTL ? 'فشلت' : 'Failed'}</p>
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
                  <CardDescription>{isRTL ? 'جميع الإشعارات المرسلة من المنصة' : 'All notifications sent from the platform'}</CardDescription>
                </div>
                
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={isRTL ? 'بحث...' : 'Search...'}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-[180px] rounded-xl"
                    />
                  </div>
                  
                  <Select value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger className="w-[130px] rounded-xl">
                      <SelectValue placeholder={isRTL ? 'النوع' : 'Type'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'الكل' : 'All'}</SelectItem>
                      <SelectItem value="system">{isRTL ? 'نظام' : 'System'}</SelectItem>
                      <SelectItem value="alert">{isRTL ? 'تنبيه' : 'Alert'}</SelectItem>
                      <SelectItem value="info">{isRTL ? 'معلومات' : 'Info'}</SelectItem>
                      <SelectItem value="reminder">{isRTL ? 'تذكير' : 'Reminder'}</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[130px] rounded-xl">
                      <SelectValue placeholder={isRTL ? 'الحالة' : 'Status'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'الكل' : 'All'}</SelectItem>
                      <SelectItem value="sent">{isRTL ? 'مرسل' : 'Sent'}</SelectItem>
                      <SelectItem value="pending">{isRTL ? 'قيد المعالجة' : 'Pending'}</SelectItem>
                      <SelectItem value="failed">{isRTL ? 'فشل' : 'Failed'}</SelectItem>
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
                      <TableHead>{isRTL ? 'النوع' : 'Type'}</TableHead>
                      <TableHead>{isRTL ? 'العنوان' : 'Title'}</TableHead>
                      <TableHead>{isRTL ? 'المستلم' : 'Recipient'}</TableHead>
                      <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                      <TableHead>{isRTL ? 'التاريخ' : 'Date'}</TableHead>
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
                    {isRTL ? 'ملاحظة' : 'Note'}
                  </p>
                  <p className="text-sm text-blue-700 dark:text-blue-300">
                    {isRTL 
                      ? 'هذه الصفحة تعرض سجل الإشعارات المرسلة من المنصة. محرك الإشعارات الكامل سيتم تطويره في المرحلة القادمة.'
                      : 'This page displays the log of notifications sent from the platform. The full notification engine will be developed in the next phase.'
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
                {isRTL ? 'تفاصيل الإشعار' : 'Notification Details'}
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
                    <p className="text-sm text-muted-foreground">{isRTL ? 'المستلم' : 'Recipient'}</p>
                    <p className="font-medium">{getRecipientLabel(selectedNotification.recipient)}</p>
                  </div>
                  <div className="bg-muted rounded-xl p-3">
                    <p className="text-sm text-muted-foreground">{isRTL ? 'التاريخ' : 'Date'}</p>
                    <p className="font-medium">
                      {new Date(selectedNotification.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US')}
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setViewDialogOpen(false)} className="rounded-xl">
                {isRTL ? 'إغلاق' : 'Close'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
