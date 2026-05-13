/**
 * WebSocket Real-time Notifications Context
 * سياق الإشعارات الفورية عبر WebSocket
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { toast } from 'sonner';
import { Bell, ShieldAlert, UserPlus, Megaphone, AlertTriangle, Lock, LogIn, Wrench } from 'lucide-react';
import {
  notifyWorkspaceNotMaterialised,
  hasShownBootstrapDialogThisSession,
  markBootstrapDialogShownThisSession,
  isPerimeterGateHandlerRegistered,
} from '../services/perimeterGateBridge';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const getWsUrl = () => {
  if (API_URL) {
    const wsUrl = API_URL.replace('https://', 'wss://').replace('http://', 'ws://');
    if (window.location.protocol === 'https:') {
      return wsUrl.replace('ws://', 'wss://');
    }
    return wsUrl;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}`;
};
const WS_URL = getWsUrl();

// Notification sound
const NOTIFICATION_SOUND_URL = 'https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3';

const WebSocketContext = createContext(null);

// Notification type icons
const notificationIcons = {
  teacher_request: UserPlus,
  security_alert: ShieldAlert,
  broadcast_message: Megaphone,
  system_alert: AlertTriangle,
  maintenance_mode: Wrench,
  login_attempt: LogIn,
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

export const WebSocketProvider = ({ children }) => {
  const { token, user } = useAuth();
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(1000);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 15;
  const isConnectingRef = useRef(false);
  const audioRef = useRef(null);
  
  const [isConnected, setIsConnected] = useState(false);
  const [onlineUsers, setOnlineUsers] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [browserNotificationsEnabled, setBrowserNotificationsEnabled] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  
  // Initialize audio
  useEffect(() => {
    audioRef.current = new Audio(NOTIFICATION_SOUND_URL);
    audioRef.current.volume = 0.5;
    
    // Check browser notification permission
    if ('Notification' in window) {
      setBrowserNotificationsEnabled(Notification.permission === 'granted');
    }
  }, []);
  
  // Play notification sound
  const playNotificationSound = useCallback(() => {
    if (soundEnabled && audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play().catch(() => {});
    }
  }, [soundEnabled]);
  
  // Request browser notification permission
  const requestBrowserNotificationPermission = useCallback(async () => {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      setBrowserNotificationsEnabled(permission === 'granted');
      return permission === 'granted';
    }
    return false;
  }, []);
  
  // Show browser notification
  const showBrowserNotification = useCallback((title, body, icon) => {
    if (browserNotificationsEnabled && 'Notification' in window) {
      try {
        new Notification(title, {
          body,
          icon: icon || '/logo192.png',
          badge: '/logo192.png',
          tag: 'nassaq-notification',
          renotify: true
        });
      } catch (err) {
        if (process.env.NODE_ENV === 'development') console.warn('Browser notification failed:', err);
      }
    }
  }, [browserNotificationsEnabled]);
  
  // Handle incoming notification
  const handleNotification = useCallback((notification) => {
    const isRTL = document.documentElement.dir === 'rtl';
    const message = isRTL ? notification.message_ar : notification.message_en;
    const title = isRTL ? notification.title_ar : notification.title_en;
    
    // Add to notifications list
    setNotifications(prev => [notification, ...prev.slice(0, 49)]);
    setUnreadCount(prev => prev + 1);
    
    // Play sound if enabled
    if (notification.sound) {
      playNotificationSound();
    }
    
    // Get icon component
    const IconComponent = notificationIcons[notification.notification_type] || notificationIcons.default;
    const priorityColor = priorityColors[notification.priority] || priorityColors.medium;
    
    // Show toast notification
    toast.custom((t) => (
      <div 
        className={`max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-xl pointer-events-auto flex ring-1 ring-black ring-opacity-5 ${
          notification.priority === 'critical' ? 'border-2 border-red-500' : ''
        }`}
        dir="rtl"
      >
        <div className="flex-1 w-0 p-4">
          <div className="flex items-start gap-3">
            <div className={`flex-shrink-0 w-10 h-10 rounded-full ${priorityColor} flex items-center justify-center`}>
              <IconComponent className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">
                {title}
              </p>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                {message}
              </p>
              <p className="mt-1 text-xs text-gray-400">
                {new Date().toLocaleTimeString('ar-SA')}
              </p>
            </div>
          </div>
        </div>
        <div className="flex border-s border-gray-200 dark:border-gray-700">
          <button
            onClick={() => toast.dismiss(t)}
            className="w-full border border-transparent rounded-none rounded-l-lg p-4 flex items-center justify-center text-sm font-medium text-brand-turquoise hover:text-brand-turquoise/80 focus:outline-none"
          >
            إغلاق
          </button>
        </div>
      </div>
    ), {
      duration: notification.priority === 'critical' ? 10000 : 5000,
      position: 'top-right'
    });
    
    // Show browser notification
    showBrowserNotification(title, message);
    
  }, [playNotificationSound, showBrowserNotification]);
  
  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!token || !WS_URL) return;
    if (isConnectingRef.current) return;
    isConnectingRef.current = true;
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      if (wsRef.current.pingInterval) {
        clearInterval(wsRef.current.pingInterval);
      }
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close(1000, 'Replacing connection');
      wsRef.current = null;
    }
    
    try {
      const ws = new WebSocket(`${WS_URL}/api/ws/notifications`);
      
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', token }));
        if (process.env.NODE_ENV === 'development') console.info('WebSocket connected');
        setIsConnected(true);
        reconnectDelayRef.current = 1000;
        reconnectAttemptsRef.current = 0;
        isConnectingRef.current = false;
        
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
        
        ws.pingInterval = pingInterval;
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'connection_established') {
            setOnlineUsers(data.online_users || 0);
          } else if (data.type === 'realtime_notification') {
            handleNotification(data);
            // Task #151 — realtime broadcasts may also carry per-student
            // change hints in their extra_data (e.g. tenant-scoped pushes
            // that include related_entity / related_entity_id). Bridge
            // those too so the parent portal cache stays consistent
            // regardless of which broadcast path the backend chose.
            try {
              const kind = data.notification_type;
              const childId = data.related_entity === 'student' ? data.related_entity_id : null;
              if (childId && (kind === 'attendance' || kind === 'assessment' || kind === 'behaviour' || kind === 'homework')) {
                window.dispatchEvent(new CustomEvent('nassaq:child_data_updated', {
                  detail: { childId: String(childId), kind },
                }));
              }
            } catch (_dispatchErr) { /* no-op */ }
          } else if (data.type === 'schedule_published') {
            // Task #145 — bridge tenant-wide schedule publish events to a
            // window CustomEvent so any open teacher screen can silently
            // refetch without prop-drilling through context. Detail
            // carries timetable_id / school_id / published_at; subscribers
            // can ignore the payload and just refetch.
            try {
              window.dispatchEvent(new CustomEvent('nassaq:schedule_published', { detail: data }));
            } catch (_dispatchErr) { /* no-op */ }
          } else if (data.type === 'new_notification') {
            // Task #151 — bridge per-student data-change notifications
            // (attendance flipped, grade posted, behaviour record added,
            // homework assigned/graded) to a window CustomEvent so the
            // parent portal's per-(childId, endpoint) cache can drop
            // stale entries without a manual reload. The notification
            // row itself is rendered by NotificationBell on its own
            // poll/refresh path; we only care about the cache hint here.
            const kind = data.notification_type;
            const childId = data.related_entity === 'student' ? data.related_entity_id : null;
            if (childId && (kind === 'attendance' || kind === 'assessment' || kind === 'behaviour' || kind === 'homework')) {
              try {
                window.dispatchEvent(new CustomEvent('nassaq:child_data_updated', {
                  detail: { childId: String(childId), kind },
                }));
              } catch (_dispatchErr) { /* no-op */ }
            }
          } else if (data.type === 'pong') {
            // Keep-alive response
          }
        } catch (err) {
          console.warn('WebSocket message parse error:', err);
        }
      };
      
      ws.onclose = (event) => {
        if (process.env.NODE_ENV === 'development') console.info('WebSocket disconnected:', event.code);
        setIsConnected(false);
        isConnectingRef.current = false;
        
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval);
        }
        
        if (event.code === 4001) {
          if (process.env.NODE_ENV === 'development') console.warn('WebSocket auth failed (4001), not reconnecting');
          return; // 4001 = invalid/expired token — do not reconnect
          // Note: 4002 = server ping timeout (network blip) — falls through to reconnect logic below
        }

        // Task #288 — IT perimeter "finish setup" parity for live updates.
        // Backend closes with code 4003 + reason "workspace not materialised"
        // when an Independent-Teacher token has no `tenant_id` claim yet
        // (signed up but never bootstrapped, or stale tab whose other tab
        // bootstrapped after this one opened). Mirror the HTTP interceptor
        // behaviour: trigger the same one-shot perimeter-gate dialog +
        // navigate('/teacher/onboarding'), and do NOT reconnect. Silent
        // recovery happens naturally via the AuthContext token-refresh
        // useEffect — once `token` updates with a tenant_id-bearing claim,
        // the connect() effect re-runs and the handshake succeeds.
        if (event.code === 4003) {
          if (process.env.NODE_ENV === 'development') console.warn('WebSocket workspace not materialised (4003), not reconnecting');
          if (!hasShownBootstrapDialogThisSession() && isPerimeterGateHandlerRegistered()) {
            markBootstrapDialogShownThisSession();
            notifyWorkspaceNotMaterialised();
          }
          return;
        }
        
        if (event.code !== 1000 && token && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          const delay = reconnectDelayRef.current;
          reconnectDelayRef.current = Math.min(delay * 2, 30000);
          reconnectTimeoutRef.current = setTimeout(() => {
            if (process.env.NODE_ENV === 'development') console.info(`WebSocket reconnecting (attempt=${reconnectAttemptsRef.current}, delay=${delay}ms)...`);
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          if (process.env.NODE_ENV === 'development') console.warn('WebSocket max reconnect attempts reached, giving up');
        }
      };
      
      ws.onerror = () => {
        isConnectingRef.current = false;
      };
      
      wsRef.current = ws;
      
    } catch (err) {
      isConnectingRef.current = false;
      console.error('WebSocket connection error:', err);
    }
  }, [token, handleNotification]);
  
  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'User logout');
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);
  
  // Connect when token changes
  useEffect(() => {
    if (token) {
      connect();
    } else {
      disconnect();
    }
    
    return () => disconnect();
  }, [token, connect, disconnect]);
  
  // Mark notification as read
  const markAsRead = useCallback((notificationId) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'mark_read',
        notification_id: notificationId
      }));
    }
    
    setNotifications(prev => 
      prev.map(n => n.id === notificationId ? { ...n, read_status: true } : n)
    );
    setUnreadCount(prev => Math.max(0, prev - 1));
  }, []);
  
  // Mark all as read
  const markAllAsRead = useCallback(() => {
    setNotifications(prev => prev.map(n => ({ ...n, read_status: true })));
    setUnreadCount(0);
  }, []);
  
  // Clear notifications
  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);
  
  // Toggle sound
  const toggleSound = useCallback(() => {
    setSoundEnabled(prev => !prev);
  }, []);
  
  const value = {
    isConnected,
    onlineUsers,
    notifications,
    unreadCount,
    soundEnabled,
    browserNotificationsEnabled,
    connect,
    disconnect,
    markAsRead,
    markAllAsRead,
    clearNotifications,
    toggleSound,
    requestBrowserNotificationPermission,
    playNotificationSound
  };
  
  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

export default WebSocketContext;
