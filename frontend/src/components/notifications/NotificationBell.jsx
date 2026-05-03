import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Card, CardContent } from '../ui/card';
import { ScrollArea } from '../ui/scroll-area';
import {
  Bell,
  Calendar,
  CalendarCheck,
  ClipboardList,
  AlertTriangle,
  AlertOctagon,
  Info,
  MessageSquare,
  Megaphone,
  Check,
  CheckCircle2,
  Clock,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../ui/popover';

const notificationTypeConfig = {
  system: { icon: Info, color: 'text-gray-500' },
  attendance: { icon: CalendarCheck, color: 'text-blue-500' },
  schedule: { icon: Calendar, color: 'text-purple-500' },
  assessment: { icon: ClipboardList, color: 'text-green-500' },
  behaviour: { icon: AlertTriangle, color: 'text-yellow-500' },
  communication: { icon: MessageSquare, color: 'text-teal-500' },
  announcement: { icon: Megaphone, color: 'text-orange-500' },
  circular: { icon: AlertOctagon, color: 'text-red-600' },
  circular_ack: { icon: CheckCircle2, color: 'text-green-600' },
  emergency: { icon: AlertOctagon, color: 'text-red-600' },
};

export const NotificationBell = () => {
  const { t } = useTranslation();
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const navigate = useNavigate();
  
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [ackingId, setAckingId] = useState(null);

  const fetchUnreadCount = useCallback(async () => {
    if (!user) return;
    try {
      const response = await api.get('/notifications/unread-count');
      setUnreadCount(response.data.unread_count);
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
    }
  }, [api, user]);

  const fetchRecentNotifications = useCallback(async () => {
    if (!user) return;
    try {
      setLoading(true);
      const response = await api.get('/notifications?limit=5');
      setNotifications(response.data);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  }, [api, user]);

  // Fetch on mount and poll every 30 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Fetch notifications when dropdown opens
  useEffect(() => {
    if (open) {
      fetchRecentNotifications();
    }
  }, [open, fetchRecentNotifications]);

  const handleMarkAsRead = async (notificationId, e) => {
    e.stopPropagation();
    try {
      await api.put(`/notifications/${notificationId}/read`);
      setNotifications(prev => 
        prev.map(n => n.id === notificationId ? { ...n, read_status: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark as read:', error);
    }
  };

  const handleAcknowledge = async (notification, e) => {
    e.stopPropagation();
    if (notification.is_acknowledged || ackingId === notification.id) return;
    try {
      setAckingId(notification.id);
      await api.post(`/notifications/${notification.id}/acknowledge`, {
        circularId: notification.id,
        userId: user?.id,
      });
      setNotifications((prev) =>
        prev.map((n) =>
          n.id === notification.id
            ? { ...n, is_acknowledged: true, acknowledged_at: new Date().toISOString(), read_status: true }
            : n,
        ),
      );
      if (!notification.read_status) {
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
      toast.success(isRTL ? 'تم تأكيد استلام التعميم' : 'Circular acknowledged');
    } catch (error) {
      console.error('Failed to acknowledge circular:', error);
      toast.error(isRTL ? 'تعذر تأكيد الاستلام' : 'Failed to acknowledge');
    } finally {
      setAckingId(null);
    }
  };

  const handleNotificationClick = async (notification) => {
    if (!notification.read_status) {
      try {
        await api.put(`/notifications/${notification.id}/read`);
        setUnreadCount(prev => Math.max(0, prev - 1));
      } catch (error) {
        console.error('Failed to mark as read:', error);
      }
    }
    setOpen(false);
    
    if (notification.action_url) {
      navigate(notification.action_url);
    } else {
      const schoolRoles = ['school_principal', 'school_admin', 'school_sub_admin'];
      navigate(schoolRoles.includes(user?.role) ? '/principal/communication/notifications' : '/notifications');
    }
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return t('now');
    if (minutes < 60) return isRTL ? `${minutes}د` : `${minutes}m`;
    if (hours < 24) return isRTL ? `${hours}س` : `${hours}h`;
    return isRTL ? `${days}ي` : `${days}d`;
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button 
          variant="ghost" 
          size="icon" 
          className="relative rounded-xl"
          data-testid="notification-bell"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge 
              className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center bg-red-500 text-white text-xs animate-pulse"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      
      <PopoverContent 
        className="w-80 p-0" 
        align={isRTL ? 'start' : 'end'}
        sideOffset={8}
      >
        <div className="p-3 border-b border-border">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold font-cairo">
              {t('notifications')}
            </h4>
            {unreadCount > 0 && (
              <Badge variant="secondary" className="text-xs">
                {unreadCount} {t('new')}
              </Badge>
            )}
          </div>
        </div>
        
        <ScrollArea className="h-[300px]">
          {loading ? (
            <div className="p-4 text-center text-sm text-muted-foreground">
              {t('loading')}
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-8 text-center">
              <Bell className="h-10 w-10 mx-auto text-muted-foreground/50 mb-2" />
              <p className="text-sm text-muted-foreground">
                {t('noNotifications')}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {notifications.map((notification) => {
                const typeConfig = notificationTypeConfig[notification.notification_type] || notificationTypeConfig.system;
                const IconComponent = typeConfig.icon;
                const isCircular = notification.notification_type === 'circular';
                const needsAck = isCircular && !notification.is_acknowledged;

                return (
                  <div
                    key={notification.id}
                    className={`p-3 cursor-pointer hover:bg-muted/50 transition-colors ${
                      needsAck
                        ? 'bg-red-50 dark:bg-red-950/20 border-s-4 border-red-500'
                        : !notification.read_status
                        ? 'bg-brand-turquoise/5'
                        : ''
                    }`}
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 ${typeConfig.color}`}>
                        <IconComponent className="h-4 w-4" />
                      </div>

                      <div className="flex-1 min-w-0">
                        {isCircular && (
                          <Badge
                            variant="outline"
                            className="mb-1 text-[10px] font-cairo border-red-500 text-red-600 bg-red-50 dark:bg-red-950/30"
                          >
                            <AlertOctagon className="h-3 w-3 me-1" />
                            {isRTL ? 'تعميم — يتطلب التأكيد' : 'Circular — Acknowledgment Required'}
                          </Badge>
                        )}
                        <p className={`text-sm line-clamp-2 ${!notification.read_status ? 'font-medium' : ''}`}>
                          {isRTL ? notification.title : (notification.title_en || notification.title)}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">
                            {formatTimeAgo(notification.created_at)}
                          </span>
                          {isCircular && notification.is_acknowledged && (
                            <span className="inline-flex items-center gap-1 text-[11px] text-green-600 font-cairo">
                              <CheckCircle2 className="h-3 w-3" />
                              {isRTL ? 'تم الاستلام' : 'Acknowledged'}
                            </span>
                          )}
                        </div>

                        {needsAck && (
                          <Button
                            size="sm"
                            className="mt-2 w-full h-8 bg-red-600 hover:bg-red-700 text-white font-cairo"
                            disabled={ackingId === notification.id}
                            onClick={(e) => handleAcknowledge(notification, e)}
                            data-testid={`ack-circular-${notification.id}`}
                          >
                            {ackingId === notification.id ? (
                              <Loader2 className="h-3 w-3 me-1 animate-spin" />
                            ) : (
                              <CheckCircle2 className="h-3 w-3 me-1" />
                            )}
                            {isRTL ? 'تأكيد الاستلام والقراءة' : 'Acknowledge Receipt'}
                          </Button>
                        )}
                      </div>

                      {!notification.read_status && !needsAck && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={(e) => handleMarkAsRead(notification.id, e)}
                        >
                          <Check className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
        
        <div className="p-2 border-t border-border">
          <Button 
            variant="ghost" 
            className="w-full justify-center text-brand-turquoise hover:text-brand-turquoise-dark text-sm"
            onClick={() => {
              setOpen(false);
              const schoolRoles = ['school_principal', 'school_admin', 'school_sub_admin'];
              navigate(schoolRoles.includes(user?.role) ? '/principal/communication/notifications' : '/notifications');
            }}
          >
            {t('viewAllNotifications')}
            <ChevronRight className={`h-4 w-4 ms-1 ${isRTL ? 'rotate-180' : ''}`} />
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
};
