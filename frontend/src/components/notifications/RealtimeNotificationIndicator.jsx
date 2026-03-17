/**
 * Real-time Notification Indicator Component
 * مؤشر الإشعارات الفورية
 */

import React, { useState } from 'react';
import { useWebSocket } from '../../contexts/WebSocketContext';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { ScrollArea } from '../ui/scroll-area';
import { Switch } from '../ui/switch';
import {
  Bell,
  BellOff,
  Wifi,
  WifiOff,
  Volume2,
  VolumeX,
  Settings,
  Trash2,
  CheckCheck,
  Users,
  ShieldAlert,
  UserPlus,
  Megaphone,
  AlertTriangle,
  Lock,
} from 'lucide-react';

// Notification type icons
const notificationIcons = {
  teacher_request: UserPlus,
  security_alert: ShieldAlert,
  broadcast_message: Megaphone,
  system_alert: AlertTriangle,
  account_locked: Lock,
  default: Bell
};

// Priority colors
const priorityColors = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-blue-500',
  low: 'bg-gray-400'
};

export const RealtimeNotificationIndicator = ({ isRTL = true }) => {
  const {
    isConnected,
    onlineUsers,
    notifications,
    unreadCount,
    soundEnabled,
    browserNotificationsEnabled,
    markAsRead,
    markAllAsRead,
    clearNotifications,
    toggleSound,
    requestBrowserNotificationPermission
  } = useWebSocket();
  
  const [showSettings, setShowSettings] = useState(false);
  
  const formatTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    
    if (minutes < 1) return isRTL ? 'الآن' : 'Just now';
    if (minutes < 60) return isRTL ? `منذ ${minutes} دقيقة` : `${minutes}m ago`;
    if (hours < 24) return isRTL ? `منذ ${hours} ساعة` : `${hours}h ago`;
    return date.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US');
  };
  
  return (
    <DropdownMenu dir={isRTL ? 'rtl' : 'ltr'}>
      <DropdownMenuTrigger asChild>
        <Button 
          variant="ghost" 
          size="icon" 
          className="relative rounded-xl"
          data-testid="realtime-notifications-btn"
        >
          {isConnected ? (
            <Bell className="h-5 w-5" />
          ) : (
            <BellOff className="h-5 w-5 text-muted-foreground" />
          )}
          
          {/* Connection indicator */}
          <span className={`absolute top-1 ${isRTL ? 'left-1' : 'right-1'} w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-red-500'
          }`} />
          
          {/* Unread count badge */}
          {unreadCount > 0 && (
            <Badge 
              className="absolute -top-1 -end-1 h-5 w-5 p-0 flex items-center justify-center bg-red-500 text-[10px]"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      
      <DropdownMenuContent className="w-80" align={isRTL ? 'start' : 'end'}>
        {/* Header */}
        <DropdownMenuLabel className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4" />
            <span>{isRTL ? 'الإشعارات الفورية' : 'Real-time Notifications'}</span>
          </div>
          <div className="flex items-center gap-1">
            {/* Online users */}
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Users className="h-3 w-3" />
              <span>{onlineUsers}</span>
            </div>
            {/* Connection status */}
            {isConnected ? (
              <Wifi className="h-4 w-4 text-green-500" />
            ) : (
              <WifiOff className="h-4 w-4 text-red-500" />
            )}
          </div>
        </DropdownMenuLabel>
        
        <DropdownMenuSeparator />
        
        {/* Settings toggle */}
        {showSettings ? (
          <div className="p-3 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">{isRTL ? 'صوت الإشعارات' : 'Sound'}</span>
              <Switch 
                checked={soundEnabled} 
                onCheckedChange={toggleSound}
                data-testid="sound-toggle"
              />
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm">{isRTL ? 'إشعارات المتصفح' : 'Browser Notifications'}</span>
              {browserNotificationsEnabled ? (
                <Badge variant="outline" className="text-green-600 border-green-600">
                  {isRTL ? 'مفعّل' : 'Enabled'}
                </Badge>
              ) : (
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={requestBrowserNotificationPermission}
                >
                  {isRTL ? 'تفعيل' : 'Enable'}
                </Button>
              )}
            </div>
            
            <Button 
              variant="ghost" 
              size="sm" 
              className="w-full"
              onClick={() => setShowSettings(false)}
            >
              {isRTL ? 'إغلاق الإعدادات' : 'Close Settings'}
            </Button>
          </div>
        ) : (
          <>
            {/* Actions */}
            <div className="flex items-center justify-between px-2 py-1">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={markAllAsRead}
                disabled={unreadCount === 0}
                className="text-xs"
              >
                <CheckCheck className="h-3 w-3 me-1" />
                {isRTL ? 'قراءة الكل' : 'Mark all read'}
              </Button>
              
              <div className="flex items-center gap-1">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-7 w-7"
                  onClick={() => setShowSettings(true)}
                >
                  <Settings className="h-3.5 w-3.5" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-7 w-7 text-red-500"
                  onClick={clearNotifications}
                  disabled={notifications.length === 0}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
            
            <DropdownMenuSeparator />
            
            {/* Notifications list */}
            <ScrollArea className="h-[300px]">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <Bell className="h-8 w-8 mb-2 opacity-30" />
                  <p className="text-sm">{isRTL ? 'لا توجد إشعارات' : 'No notifications'}</p>
                </div>
              ) : (
                <div className="space-y-1 p-1">
                  {notifications.map((notification) => {
                    const IconComponent = notificationIcons[notification.notification_type] || notificationIcons.default;
                    const priorityColor = priorityColors[notification.priority] || priorityColors.medium;
                    
                    return (
                      <div
                        key={notification.id}
                        onClick={() => !notification.read_status && markAsRead(notification.id)}
                        className={`p-2 rounded-lg cursor-pointer transition-colors ${
                          notification.read_status 
                            ? 'bg-muted/30' 
                            : 'bg-muted/60 hover:bg-muted'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <div className={`flex-shrink-0 w-8 h-8 rounded-full ${priorityColor} flex items-center justify-center`}>
                            <IconComponent className="h-4 w-4 text-white" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm ${notification.read_status ? 'font-normal' : 'font-semibold'}`}>
                              {isRTL ? notification.title_ar : notification.title_en}
                            </p>
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {isRTL ? notification.message_ar : notification.message_en}
                            </p>
                            <p className="text-[10px] text-muted-foreground mt-1">
                              {formatTime(notification.created_at)}
                            </p>
                          </div>
                          {!notification.read_status && (
                            <span className="w-2 h-2 rounded-full bg-brand-turquoise flex-shrink-0 mt-2" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export default RealtimeNotificationIndicator;
