import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Switch } from '@/shared/components/ui/switch';
import { Label } from '@/shared/components/ui/label';
import {
  Bell, BellOff, Check, CheckCheck, Trash2, Filter, RefreshCw,
  Calendar, CalendarCheck, ClipboardList, AlertTriangle,
  MessageSquare, Eye, Clock, Search, Settings,
  Inbox, AlertCircle, Loader2, FileText, User, ExternalLink
} from 'lucide-react';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '@/shared/components/ui/dialog';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';
// Display metadata + canonical normalizers shared with the bell/preview
// dialog. The normalizers are the single source of truth for the effective
// type/priority of a row — display AND filtering must both go through them
// so a row labeled "النظام" is always matched by the النظام filter.
import {
  notificationTypeConfig,
  priorityConfig,
  normalizeNotificationType,
  normalizeNotificationPriority,
  prettifyText,
} from '@/features/communication/components/notifications/notificationDisplay';

// Task #1049 — attendance status → localized label + tone for the
// per-child lesson report card surfaced on IT lesson-end summaries.
const ATTENDANCE_STATUS_CONFIG = {
  present: { ar: 'حاضر', en: 'Present', tone: 'text-green-600 dark:text-green-400' },
  absent: { ar: 'غائب', en: 'Absent', tone: 'text-red-600 dark:text-red-400' },
  late: { ar: 'متأخر', en: 'Late', tone: 'text-orange-600 dark:text-orange-400' },
  excused: { ar: 'مستأذن', en: 'Excused', tone: 'text-blue-600 dark:text-blue-400' },
};

// Renders the structured per-child lesson report (attendance,
// participation, homework, teacher note) attached to an IT lesson-end
// summary notification. Returns null when the notification carries no
// report so non-summary rows are unaffected.
const LessonReportCard = ({ report, isRTL }) => {
  if (!report || typeof report !== 'object') return null;
  const att = ATTENDANCE_STATUS_CONFIG[report.attendance_status]
    || { ar: report.attendance_status || '—', en: report.attendance_status || '—', tone: 'text-muted-foreground' };
  const participations = Number(report.participations || 0);
  const correct = Number(report.correct_answers || 0);
  const wrong = Number(report.wrong_answers || 0);
  const positive = Number(report.positive_behaviours || 0);
  const negative = Number(report.negative_behaviours || 0);
  const hwStatus = report.homework_status;
  const hwDone = hwStatus === 'done' || hwStatus === 'submitted';
  const hasHomework = hwStatus !== null && hwStatus !== undefined && hwStatus !== '';
  const note = typeof report.teacher_note === 'string' ? report.teacher_note.trim() : '';

  const Row = ({ icon: Icon, label, children }) => (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-brand-navy/5 dark:border-white/5 last:border-0">
      <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" strokeWidth={1.5} />
        {label}
      </span>
      <span className="text-[11px] font-semibold text-end">{children}</span>
    </div>
  );

  return (
    <div
      className="mt-2.5 rounded-lg border border-brand-turquoise/20 bg-brand-turquoise/5 dark:bg-brand-turquoise/10 p-3"
      data-testid="lesson-report-card"
    >
      <Row icon={CalendarCheck} label={isRTL ? 'الحضور' : 'Attendance'}>
        <span className={att.tone}>{isRTL ? att.ar : att.en}</span>
      </Row>
      <Row icon={MessageSquare} label={isRTL ? 'المشاركة' : 'Participation'}>
        <span className="text-brand-navy dark:text-brand-turquoise">
          {participations}
          {(correct > 0 || wrong > 0) && (
            <span className="ms-1.5 font-normal text-muted-foreground">
              ({isRTL ? 'صحيح' : 'correct'} {correct} · {isRTL ? 'خطأ' : 'wrong'} {wrong})
            </span>
          )}
        </span>
      </Row>
      {(positive > 0 || negative > 0) && (
        <Row icon={AlertTriangle} label={isRTL ? 'السلوك' : 'Behaviour'}>
          <span>
            {positive > 0 && <span className="text-green-600 dark:text-green-400">+{positive}</span>}
            {positive > 0 && negative > 0 && <span className="mx-1 text-muted-foreground">·</span>}
            {negative > 0 && <span className="text-red-600 dark:text-red-400">-{negative}</span>}
          </span>
        </Row>
      )}
      {hasHomework && (
        <Row icon={ClipboardList} label={isRTL ? 'الواجب' : 'Homework'}>
          <span className={hwDone ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'}>
            {hwDone ? (isRTL ? 'تم التسليم' : 'Submitted') : (isRTL ? 'لم يُسلَّم' : 'Not submitted')}
          </span>
        </Row>
      )}
      {note && (
        <div className="flex items-start gap-1.5 pt-2 mt-1.5 border-t border-brand-navy/5 dark:border-white/5">
          <FileText className="h-3.5 w-3.5 shrink-0 mt-0.5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
          <p className="text-[11px] text-foreground/80 leading-relaxed">
            <span className="font-semibold">{isRTL ? 'ملاحظة المعلم: ' : 'Teacher note: '}</span>
            {note}
          </p>
        </div>
      )}
    </div>
  );
};

export const NotificationsPage = ({ embedded = false }) => {
  const { t } = useTranslation();
  const { user, api, isPlatformAdmin, isSchoolPrincipal } = useAuth();
  const { isRTL } = useTheme();
  const navigate = useNavigate();
  const { nassaqError } = useNassaqAlert();

  const isManagerView = isPlatformAdmin || isSchoolPrincipal;
  const isReceiverView = !isManagerView;
  const isParent = user?.role === 'parent';

  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterType, setFilterType] = useState('all');
  const [filterRead, setFilterRead] = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [timePeriod, setTimePeriod] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [analytics, setAnalytics] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [prefSettings, setPrefSettings] = useState(null);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [acknowledgedIds, setAcknowledgedIds] = useState(() => new Set());
  // Tracks notification IDs whose underlying relocation alert has been
  // acknowledged in this session — separate from the circular set so the
  // two flows can evolve independently. Server also persists the state on
  // the unavailability doc, but this gives us instant UI feedback.
  const [acknowledgedRelocationIds, setAcknowledgedRelocationIds] = useState(() => new Set());
  // Task #1006 — per-child filter for parent inbox
  const [linkedChildren, setLinkedChildren] = useState([]);
  const [selectedChildId, setSelectedChildId] = useState('all');
  // Full-message detail view: clicking a card opens the complete body in a
  // dialog (long teacher→parent messages were only readable as a 2-line
  // clamp before). Null = closed.
  const [detailNotification, setDetailNotification] = useState(null);

  // Fetch the FULL inbox once (no notification_type / read_status params).
  // Type, read, priority, period and search are all applied client-side
  // against the same normalized values the cards display — server-side
  // type filtering matched raw stored values (e.g. `warning`, `message`)
  // and returned empty for rows visibly labeled "النظام". Fetching
  // unfiltered also keeps the top counter cards stable while filtering.
  // Only the parent per-child filter stays server-side (it is validated
  // against the guardian linkage on the backend).
  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      let url = '/notifications?limit=200';
      if (isParent && selectedChildId && selectedChildId !== 'all') url += `&student_id=${encodeURIComponent(selectedChildId)}`;
      const response = await api.get(url);
      setNotifications(response.data);
    } catch (error) {
      // intentionally silent — parent inbox failure is handled by empty state
    } finally {
      setLoading(false);
    }
  }, [api, isParent, selectedChildId]);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get('/notifications/analytics');
      setAnalytics(response.data);
    } catch (error) { console.error('Failed to fetch analytics:', error); }
  };

  const fetchPreferences = async () => {
    try {
      const res = await api.get(`/users/${user?.id}/notifications/settings`);
      setPrefSettings(res.data || {});
    } catch (error) { console.error('Failed to fetch prefs:', error); }
  };

  useEffect(() => {
    if (!isParent || !embedded) return;
    api.get('/parent-portal/children')
      .then(res => {
        const raw = res.data;
        const list = Array.isArray(raw) ? raw
          : Array.isArray(raw?.children) ? raw.children
          : [];
        setLinkedChildren(list);
      })
      .catch(() => {});
  }, [api, isParent, embedded]);

  useEffect(() => {
    fetchNotifications();
    if (user?.role === 'platform_admin' || user?.role === 'school_principal') fetchAnalytics();
    fetchPreferences();
  }, [fetchNotifications, user?.role]);

  const handleMarkAsRead = async (notificationId) => {
    try {
      await api.put(`/notifications/${notificationId}/read`);
      setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, read_status: true } : n));
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
    if (!notification.read_status) handleMarkAsRead(notification.id);
    // Open the full-message detail dialog instead of navigating away —
    // when the notification carries an action_url the dialog surfaces it
    // as an explicit button so deep-link navigation is still one tap away.
    setDetailNotification(notification);
  };

  // Acknowledge a class-relocation alert. Mirrors the circular ack flow:
  // optimistic UI update, server call to /school/settings/unavailability/
  // {id}/acknowledge, rollback on failure. Also flips the notification's
  // read state locally so the unread badge updates without a refetch.
  const handleAcknowledgeRelocation = async (notification) => {
    if (!notification?.unavailability_id) return;
    if (acknowledgedRelocationIds.has(notification.id) || notification.is_acknowledged) return;
    setAcknowledgedRelocationIds(prev => {
      const next = new Set(prev);
      next.add(notification.id);
      return next;
    });
    setNotifications(prev => prev.map(n => n.id === notification.id
      ? { ...n, read_status: true, is_acknowledged: true }
      : n));
    try {
      await api.post(`/school/settings/unavailability/${notification.unavailability_id}/acknowledge`);
      // Tell other notification UIs (sidebar bell) to re-sync their badge.
      window.dispatchEvent(new CustomEvent('notifications:refresh'));
    } catch (error) {
      setAcknowledgedRelocationIds(prev => {
        const next = new Set(prev);
        next.delete(notification.id);
        return next;
      });
      setNotifications(prev => prev.map(n => n.id === notification.id
        ? { ...n, read_status: notification.read_status, is_acknowledged: notification.is_acknowledged }
        : n));
      const detail = getApiErrorMessage(error);
      nassaqError(detail || (isRTL ? 'تعذر تسجيل اطلاعك على نقل الفصل' : 'Failed to acknowledge relocation'));
    }
  };

  const handleAcknowledgeCircular = async (notification) => {
    if (acknowledgedIds.has(notification.id)) return;
    setAcknowledgedIds(prev => {
      const next = new Set(prev);
      next.add(notification.id);
      return next;
    });
    try {
      await api.post(`/notifications/${notification.id}/acknowledge`, {
        circularId: notification.id,
        userId: user?.id,
      });
      if (!notification.read_status) {
        setNotifications(prev => prev.map(n => n.id === notification.id ? { ...n, read_status: true } : n));
      }
    } catch (error) {
      setAcknowledgedIds(prev => {
        const next = new Set(prev);
        next.delete(notification.id);
        return next;
      });
      nassaqError(isRTL ? 'تعذر تسجيل تأكيد الاستلام' : 'Failed to acknowledge circular');
    }
  };

  const handleSavePreferences = async () => {
    if (!prefSettings) return;
    setSavingPrefs(true);
    try {
      await api.put(`/users/${user?.id}/notifications/settings`, prefSettings);
      toast.success(t('preferencesSaved'));
    } catch (error) {
      nassaqError(t('failedToSavePreferences'));
    } finally { setSavingPrefs(false); }
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

  const getDateLabel = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
    const notifDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    if (notifDate.getTime() === today.getTime()) return t('today2');
    if (notifDate.getTime() === yesterday.getTime()) return t('yesterday');
    return date.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { weekday: 'long', day: 'numeric', month: 'long' });
  };

  const filteredNotifications = useMemo(() => {
    let result = [...notifications];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(n => n.title?.toLowerCase().includes(q) || n.message?.toLowerCase().includes(q) || n.title_en?.toLowerCase().includes(q) || n.message_en?.toLowerCase().includes(q));
    }
    if (filterType !== 'all') result = result.filter(n => normalizeNotificationType(n.notification_type) === filterType);
    if (filterRead !== 'all') result = result.filter(n => (filterRead === 'read' ? n.read_status : !n.read_status));
    if (filterPriority !== 'all') result = result.filter(n => normalizeNotificationPriority(n.priority) === filterPriority);
    if (timePeriod !== 'all') {
      const now = new Date();
      const cutoff = new Date();
      if (timePeriod === 'today') cutoff.setHours(0, 0, 0, 0);
      else if (timePeriod === 'week') cutoff.setDate(now.getDate() - 7);
      else if (timePeriod === 'month') cutoff.setMonth(now.getMonth() - 1);
      result = result.filter(n => n.created_at && new Date(n.created_at) >= cutoff);
    }
    return result;
  }, [notifications, searchQuery, filterType, filterRead, filterPriority, timePeriod]);

  const groupedByDate = useMemo(() => {
    const groups = {};
    filteredNotifications.forEach(n => {
      const label = n.created_at ? getDateLabel(n.created_at) : (t('unknown'));
      if (!groups[label]) groups[label] = [];
      groups[label].push(n);
    });
    return groups;
  }, [filteredNotifications, isRTL]);

  const unreadCount = notifications.filter(n => !n.read_status).length;
  const typeBreakdown = useMemo(() => {
    const counts = {};
    notifications.forEach(n => { const nType = normalizeNotificationType(n.notification_type); counts[nType] = (counts[nType] || 0) + 1; });
    return counts;
  }, [notifications]);

  const renderNotificationCard = (notification) => {
    const effectivePriority = normalizeNotificationPriority(notification.priority);
    const typeConf = notificationTypeConfig[normalizeNotificationType(notification.notification_type)];
    const priorityConf = priorityConfig[effectivePriority];
    const IconComponent = typeConf.icon;
    const isCircular = notification.notification_type === 'circular';
    const isCircularAck = notification.notification_type === 'circular_ack';
    const showAcknowledgeButton = isCircular && isReceiverView;
    const showCircularAckCard = isCircularAck && isManagerView;
    const isAcknowledged = acknowledgedIds.has(notification.id);
    // Relocation ack metadata: surfaced when the backend tagged the
    // notification with an unavailability_id (i.e. it stems from a class
    // relocation). The button appears for any recipient — only the user
    // it was sent to receives this notification, so an extra role check is
    // unnecessary.
    const isRelocation = !!notification.unavailability_id;
    const isRelocationAcked = !!notification.is_acknowledged
      || acknowledgedRelocationIds.has(notification.id);

    if (showCircularAckCard) {
      return (
        <div
          key={notification.id}
          className={`p-4 rounded-xl border cursor-pointer transition-all hover:shadow-md bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-900/40 ${!notification.read_status ? 'ring-1 ring-green-300/60' : ''}`}
          onClick={() => handleNotificationClick(notification)}
          data-testid={`notif-circular-ack-${notification.id}`}
        >
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 bg-green-100 dark:bg-green-900/40">
              <CheckCheck className="h-4 w-4 text-green-600 dark:text-green-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <h4 className={`font-medium text-sm text-green-800 dark:text-green-200 truncate ${!notification.read_status ? 'font-bold' : ''}`}>
                      {isRTL ? 'تأكيد استلام تعميم' : 'Circular Acknowledged'}
                    </h4>
                    {!notification.read_status && <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />}
                  </div>
                  <p className="text-xs text-green-900/80 dark:text-green-100/80 line-clamp-2">
                    {prettifyText(isRTL ? notification.message : (notification.message_en || notification.message), isRTL)}
                  </p>
                </div>
                <Badge className="bg-green-600 text-white text-[10px] border-0">
                  {isRTL ? 'تم الاستلام' : 'Acknowledged'}
                </Badge>
              </div>
              <div className="flex items-center justify-between mt-2.5">
                <div className="flex items-center gap-2 text-[10px] text-green-800/70 dark:text-green-200/70">
                  <Clock className="h-3 w-3" />
                  {formatTimeAgo(notification.created_at)}
                  {notification.sender_name && (<><span>•</span><span>{notification.sender_name}</span></>)}
                </div>
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  {!notification.read_status && (
                    <Button size="sm" variant="ghost" onClick={() => handleMarkAsRead(notification.id)} className="h-7 w-7 p-0 rounded-lg text-green-700 hover:text-green-800"><Check className="h-3.5 w-3.5" /></Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => handleDeleteNotification(notification.id)} className="h-7 w-7 p-0 rounded-lg text-red-500 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div
        key={notification.id}
        className={`p-4 rounded-xl border cursor-pointer transition-all hover:shadow-md ${!notification.read_status ? 'bg-brand-turquoise/5 border-brand-turquoise/30' : 'bg-card hover:bg-muted/30'}`}
        onClick={() => handleNotificationClick(notification)}
      >
        <div className="flex items-start gap-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${effectivePriority === 'critical' || effectivePriority === 'high' ? 'bg-red-100 dark:bg-red-900/30' : `${typeConf.color}/10`}`}>
            <IconComponent className={`h-4 w-4 ${effectivePriority === 'critical' ? 'text-red-500' : typeConf.iconColor}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <h4 className={`font-medium text-sm truncate ${!notification.read_status ? 'font-bold' : ''}`}>
                    {prettifyText(isRTL ? notification.title : (notification.title_en || notification.title), isRTL)}
                  </h4>
                  {!notification.read_status && <span className="w-2 h-2 rounded-full bg-brand-turquoise shrink-0" />}
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {prettifyText(isRTL ? notification.message : (notification.message_en || notification.message), isRTL)}
                </p>
                {notification.student && (notification.student.name_ar || notification.student.code) && (
                  <span className="inline-flex items-center gap-1 mt-1 text-[10px] font-medium text-brand-navy/70 dark:text-brand-turquoise/70 bg-brand-navy/5 dark:bg-brand-turquoise/10 rounded-full px-2 py-0.5 w-fit">
                    <User className="h-2.5 w-2.5 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                    {notification.student.name_ar || notification.student.code}
                  </span>
                )}
                {notification.lesson_report && (
                  <LessonReportCard report={notification.lesson_report} isRTL={isRTL} />
                )}
              </div>
              <div className="flex flex-col items-end gap-1 shrink-0">
                <Badge className={`${typeConf.color} text-white text-[10px] border-0`}>
                  {isRTL ? typeConf.label.ar : typeConf.label.en}
                </Badge>
                {effectivePriority !== 'medium' && (
                  <Badge className={`${priorityConf.color} text-white text-[10px] border-0`}>
                    {isRTL ? priorityConf.label.ar : priorityConf.label.en}
                  </Badge>
                )}
              </div>
            </div>
            {showAcknowledgeButton && (
              <div className="mt-3" onClick={(e) => e.stopPropagation()}>
                <Button
                  size="sm"
                  onClick={() => handleAcknowledgeCircular(notification)}
                  disabled={isAcknowledged}
                  className={`h-8 gap-1.5 ${isAcknowledged ? 'bg-green-600 hover:bg-green-600 text-white' : 'bg-brand-turquoise hover:bg-brand-turquoise/90 text-white'}`}
                  data-testid={`notif-ack-btn-${notification.id}`}
                >
                  {isAcknowledged ? (
                    <>
                      <CheckCheck className="h-3.5 w-3.5" />
                      {isRTL ? 'تم الاستلام' : 'Acknowledged'}
                    </>
                  ) : (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      {isRTL ? 'تلقيت التعميم' : 'Acknowledge Receipt'}
                    </>
                  )}
                </Button>
              </div>
            )}
            {isRelocation && (
              <div className="mt-3 flex items-center gap-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
                <Button
                  size="sm"
                  onClick={() => handleAcknowledgeRelocation(notification)}
                  disabled={isRelocationAcked}
                  className={`h-8 gap-1.5 ${isRelocationAcked
                    ? 'bg-emerald-600 hover:bg-emerald-600 text-white'
                    : 'bg-orange-600 hover:bg-orange-700 text-white'}`}
                  data-testid={`notif-relocation-ack-btn-${notification.id}`}
                >
                  {isRelocationAcked ? (
                    <>
                      <CheckCheck className="h-3.5 w-3.5" />
                      {isRTL ? 'تم الاطلاع' : 'Acknowledged'}
                    </>
                  ) : (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      {isRTL ? 'تم الاطلاع' : 'Acknowledge'}
                    </>
                  )}
                </Button>
                {notification.action_url && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => navigate(notification.action_url)}
                    className="h-8 gap-1.5 border-orange-300 text-orange-700 hover:bg-orange-50 hover:text-orange-700 focus-visible:text-orange-700"
                    data-testid={`notif-relocation-open-btn-${notification.id}`}
                  >
                    {isRTL ? 'فتح الجدول' : 'Open Schedule'}
                  </Button>
                )}
                {notification.alternative_location && (
                  <span className="text-[11px] text-orange-700 font-semibold">
                    {isRTL ? 'الموقع البديل: ' : 'Relocated to: '}
                    {notification.alternative_location}
                  </span>
                )}
              </div>
            )}
            <div className="flex items-center justify-between mt-2.5">
              <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatTimeAgo(notification.created_at)}
                {notification.sender_name && (<><span>•</span><span>{notification.sender_name}</span></>)}
              </div>
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                {!notification.read_status && (
                  <Button size="sm" variant="ghost" onClick={() => handleMarkAsRead(notification.id)} className="h-7 w-7 p-0 rounded-lg"><Check className="h-3.5 w-3.5" /></Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => handleDeleteNotification(notification.id)} className="h-7 w-7 p-0 rounded-lg text-red-500 hover:text-red-600"><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const content = (
      <div className={embedded ? '' : 'min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800'} dir={isRTL ? 'rtl' : 'ltr'}>
        {!embedded && (
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo flex items-center gap-2">
                <Bell className="h-6 w-6" />
                {t('notificationsCenter')}
                {unreadCount > 0 && <Badge className="bg-red-500 text-white border-0">{unreadCount}</Badge>}
              </h1>
              <p className="text-sm text-muted-foreground">{t('allYourNotificationsInOnePlace')}</p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input placeholder={t('searchNotifications')} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="ps-9 w-full sm:w-[200px] h-9" />
              </div>
              <Button variant="outline" size="sm" onClick={fetchNotifications} disabled={loading}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></Button>
              {unreadCount > 0 && (
                <Button onClick={handleMarkAllAsRead} className="bg-brand-turquoise hover:bg-brand-turquoise/90" size="sm">
                  <CheckCheck className="h-4 w-4 me-1" /><span className="hidden sm:inline">{t('markAllRead2')}</span>
                </Button>
              )}
            </div>
          </div>
        </div>
        )}

        <div className={embedded ? 'space-y-5' : 'p-4 max-w-[1400px] mx-auto space-y-5'}>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card className="overflow-hidden"><CardContent className="p-3 text-center bg-blue-50 dark:bg-blue-950/30"><Bell className="h-5 w-5 mx-auto mb-1.5 text-blue-600" /><div className="text-xl font-bold font-cairo text-blue-600">{notifications.length}</div><div className="text-[10px] text-muted-foreground">{t('total2')}</div></CardContent></Card>
            <Card className="overflow-hidden"><CardContent className="p-3 text-center bg-red-50 dark:bg-red-950/30"><AlertCircle className="h-5 w-5 mx-auto mb-1.5 text-red-600" /><div className="text-xl font-bold font-cairo text-red-600">{unreadCount}</div><div className="text-[10px] text-muted-foreground">{t('unread')}</div></CardContent></Card>
            <Card className="overflow-hidden"><CardContent className="p-3 text-center bg-green-50 dark:bg-green-950/30"><Check className="h-5 w-5 mx-auto mb-1.5 text-green-600" /><div className="text-xl font-bold font-cairo text-green-600">{notifications.length - unreadCount}</div><div className="text-[10px] text-muted-foreground">{t('read')}</div></CardContent></Card>
            <Card className="overflow-hidden"><CardContent className="p-3 text-center bg-purple-50 dark:bg-purple-950/30"><Eye className="h-5 w-5 mx-auto mb-1.5 text-purple-600" /><div className="text-xl font-bold font-cairo text-purple-600">{notifications.length > 0 ? Math.round(((notifications.length - unreadCount) / notifications.length) * 100) : 0}%</div><div className="text-[10px] text-muted-foreground">{t('readRate')}</div></CardContent></Card>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4 bg-muted/50 flex-wrap">
              <TabsTrigger value="all" className="gap-1.5"><Inbox className="h-3.5 w-3.5" />{t('all2')}<Badge variant="secondary" className="text-[9px] h-4 border-0">{filteredNotifications.length}</Badge></TabsTrigger>
              <TabsTrigger value="unread" className="gap-1.5"><BellOff className="h-3.5 w-3.5" />{t('unread')}{unreadCount > 0 && <Badge className="bg-red-500 text-white text-[9px] h-4 border-0">{unreadCount}</Badge>}</TabsTrigger>
              <TabsTrigger value="types" className="gap-1.5"><Filter className="h-3.5 w-3.5" />{t('byType')}</TabsTrigger>
              <TabsTrigger value="preferences" className="gap-1.5"><Settings className="h-3.5 w-3.5" />{t('preferences')}</TabsTrigger>
            </TabsList>

            <TabsContent value="all">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <CardTitle className="text-base font-cairo">{isRTL ? 'جميع الإشعارات' : 'All Notifications'}</CardTitle>
                    <div className="flex gap-2 flex-wrap">
                      {isParent && embedded && linkedChildren.length > 0 && (
                        <Select value={selectedChildId} onValueChange={val => { setSelectedChildId(val); }}>
                          <SelectTrigger className="w-[140px] h-9">
                            <User className="h-3.5 w-3.5 me-1.5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
                            <SelectValue placeholder={isRTL ? 'كل الأبناء' : 'All Children'} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">{isRTL ? 'كل الأبناء' : 'All Children'}</SelectItem>
                            {linkedChildren.map(child => (
                              <SelectItem key={child.id} value={child.id}>
                                {child.full_name || child.name || child.id}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                      <Select value={filterType} onValueChange={setFilterType}>
                        <SelectTrigger className="w-[130px] h-9"><SelectValue placeholder={t('type4')} /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('allTypes2')}</SelectItem>
                          {Object.entries(notificationTypeConfig).map(([key, config]) => (
                            <SelectItem key={key} value={key}>{isRTL ? config.label.ar : config.label.en}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Select value={filterRead} onValueChange={setFilterRead}>
                        <SelectTrigger className="w-[110px] h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('all')}</SelectItem>
                          <SelectItem value="unread">{t('unread2')}</SelectItem>
                          <SelectItem value="read">{t('read2')}</SelectItem>
                        </SelectContent>
                      </Select>
                      <Select value={timePeriod} onValueChange={setTimePeriod}>
                        <SelectTrigger className="w-[110px] h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('allTime')}</SelectItem>
                          <SelectItem value="today">{t('today2')}</SelectItem>
                          <SelectItem value="week">{t('thisWeek')}</SelectItem>
                          <SelectItem value="month">{t('thisMonth')}</SelectItem>
                        </SelectContent>
                      </Select>
                      <Select value={filterPriority} onValueChange={setFilterPriority}>
                        <SelectTrigger className="w-[110px] h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">{t('allPriority')}</SelectItem>
                          {Object.entries(priorityConfig).map(([key, config]) => (
                            <SelectItem key={key} value={key}>{isRTL ? config.label.ar : config.label.en}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-4 sm:p-6">
                  <div className="max-h-[600px] overflow-y-auto pe-1 sm:pe-2 custom-scrollbar space-y-5">
                    {loading ? (
                      <div className="flex items-center justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" /></div>
                    ) : filteredNotifications.length === 0 ? (
                      <div className="flex flex-col items-center py-16 text-center"><BellOff className="h-14 w-14 mb-4 text-muted-foreground/30" /><p className="text-muted-foreground font-cairo">{t('noNotifications2')}</p></div>
                    ) : (
                      <div className="space-y-5">
                        {Object.entries(groupedByDate).map(([dateLabel, notifs]) => (
                          <div key={dateLabel}>
                            <div className="flex items-center gap-3 mb-3">
                              <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide font-cairo">{dateLabel}</h3>
                              <div className="flex-1 h-px bg-border" />
                              <Badge variant="secondary" className="text-[10px]">{notifs.length}</Badge>
                            </div>
                            <div className="space-y-2.5">{notifs.map(renderNotificationCard)}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="unread">
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><AlertCircle className="h-4 w-4 text-red-500" />{t('unreadNotifications')}<Badge className="bg-red-500 text-white border-0">{unreadCount}</Badge></CardTitle></CardHeader>
                <CardContent className="p-4 sm:p-6">
                  {unreadCount === 0 ? (
                    <div className="flex flex-col items-center py-16 text-center"><Check className="h-14 w-14 mb-4 text-green-400" /><p className="text-muted-foreground font-cairo font-medium">{t('noUnreadNotifications')}</p><p className="text-xs text-muted-foreground/60 mt-1">{t('youreAllCaughtUp')}</p></div>
                  ) : (
                    <div className="max-h-[600px] overflow-y-auto pe-1 sm:pe-2 custom-scrollbar space-y-2.5">
                      {notifications.filter(n => !n.read_status).map(renderNotificationCard)}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="types">
              <div className="grid md:grid-cols-2 gap-4">
                {Object.entries(notificationTypeConfig).map(([typeKey, typeConf]) => {
                  const typeNotifs = notifications.filter(n => normalizeNotificationType(n.notification_type) === typeKey);
                  const TypeIcon = typeConf.icon;
                  return (
                    <Card key={typeKey}>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-cairo flex items-center gap-2">
                          <div className={`w-7 h-7 rounded-lg ${typeConf.color} flex items-center justify-center`}><TypeIcon className="h-3.5 w-3.5 text-white" /></div>
                          {isRTL ? typeConf.label.ar : typeConf.label.en}
                          <Badge variant="secondary" className="text-[10px] ms-auto">{typeNotifs.length}</Badge>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        {typeNotifs.length === 0 ? (<p className="text-xs text-muted-foreground text-center py-4">{t('noNotifications2')}</p>) : (
                          <div className="space-y-2">{typeNotifs.slice(0, 3).map(n => (
                            <div key={n.id} className={`p-2.5 rounded-lg border cursor-pointer transition-all hover:bg-muted/30 ${!n.read_status ? 'bg-brand-turquoise/5 border-brand-turquoise/20' : ''}`} onClick={() => handleNotificationClick(n)}>
                              <div className="flex items-center gap-2 mb-0.5"><h4 className="text-xs font-medium truncate">{isRTL ? n.title : (n.title_en || n.title)}</h4>{!n.read_status && <span className="w-1.5 h-1.5 rounded-full bg-brand-turquoise shrink-0" />}</div>
                              <p className="text-[10px] text-muted-foreground line-clamp-1">{isRTL ? n.message : (n.message_en || n.message)}</p>
                              <span className="text-[9px] text-muted-foreground/60 flex items-center gap-1 mt-1"><Clock className="h-2.5 w-2.5" />{formatTimeAgo(n.created_at)}</span>
                            </div>
                          ))}</div>
                        )}
                        {typeNotifs.length > 3 && (<p className="text-center text-[10px] text-brand-turquoise mt-2 cursor-pointer hover:underline" onClick={() => { setFilterType(typeKey); setActiveTab('all'); }}>{isRTL ? `عرض ${typeNotifs.length - 3} أخرى` : `View ${typeNotifs.length - 3} more`}</p>)}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </TabsContent>

            <TabsContent value="preferences">
              <Card dir={isRTL ? 'rtl' : 'ltr'} className="rounded-2xl border border-border/60 shadow-sm overflow-hidden">
                <CardHeader className="pb-4 border-b border-border/40 bg-muted/10">
                  <CardTitle className="text-base font-cairo font-bold flex items-center gap-2.5 text-foreground">
                    <Settings className="h-4.5 w-4.5 text-brand-turquoise shrink-0" />
                    <span>{isRTL ? 'إعدادات الإشعارات' : 'Notification Preferences'}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-6 space-y-5">
                  {!prefSettings ? (<div className="flex items-center justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" /></div>) : (
                    <>
                      <div className="space-y-3">
                        {[
                          { key: 'email_notifications', label: t('emailNotifications'), desc: t('receiveNotificationsViaEmail2') },
                          { key: 'push_notifications', label: t('pushNotifications'), desc: t('browserPushNotifications') },
                          { key: 'attendance_alerts', label: t('attendanceAlerts'), desc: t('alertsOnAttendanceChanges') },
                          { key: 'grade_notifications', label: t('gradeNotifications'), desc: t('alertsOnGradeUpdates') },
                          { key: 'behavior_alerts', label: t('behaviorAlerts'), desc: t('alertsOnBehaviorRecords') },
                          { key: 'announcement_notifications', label: t('announcements2'), desc: t('schoolAnnouncements') },
                        ].map(pref => (
                          <div key={pref.key} className="flex items-center justify-between p-3.5 sm:p-4 rounded-2xl border border-border/50 bg-background/50 hover:bg-muted/30 transition-colors">
                            <div className="min-w-0 flex-1 pe-4 text-start">
                              <p className="text-sm font-semibold font-cairo text-foreground">{pref.label}</p>
                              <p className="text-xs text-muted-foreground font-tajawal mt-0.5">{pref.desc}</p>
                            </div>
                            <div className="shrink-0 flex items-center">
                              <Switch checked={prefSettings[pref.key] !== false} onCheckedChange={(checked) => setPrefSettings(prev => ({ ...prev, [pref.key]: checked }))} />
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="pt-2 flex justify-start">
                        <Button className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white rounded-xl px-6 h-10 font-cairo shadow-sm" onClick={handleSavePreferences} disabled={savingPrefs}>
                          {savingPrefs && <Loader2 className="h-4 w-4 animate-spin me-2" />}{t('savePreferences')}
                        </Button>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Full-message detail view. The card body is clamped to two lines,
            so this dialog is the only place long teacher→parent messages can
            be read in full. dir is set explicitly because the Radix portal
            renders outside the page's dir container. */}
        <Dialog open={!!detailNotification} onOpenChange={(open) => { if (!open) setDetailNotification(null); }}>
          <DialogContent dir={isRTL ? 'rtl' : 'ltr'} className="max-w-lg max-h-[85vh] flex flex-col" data-testid="notification-detail-dialog">
            {detailNotification && (() => {
              const dTypeConf = notificationTypeConfig[normalizeNotificationType(detailNotification.notification_type)];
              const dPriority = normalizeNotificationPriority(detailNotification.priority);
              const dPriorityConf = priorityConfig[dPriority];
              const DetailIcon = dTypeConf.icon;
              return (
                <>
                  <DialogHeader className="text-start space-y-0">
                    <div className="flex items-start gap-3 pe-6">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${dPriority === 'critical' || dPriority === 'high' ? 'bg-red-100 dark:bg-red-900/30' : `${dTypeConf.color}/10`}`}>
                        <DetailIcon className={`h-5 w-5 ${dPriority === 'critical' ? 'text-red-500' : dTypeConf.iconColor}`} aria-hidden="true" strokeWidth={1.5} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <DialogTitle className="font-cairo text-base leading-snug break-words text-start">
                          {prettifyText(isRTL ? detailNotification.title : (detailNotification.title_en || detailNotification.title), isRTL)}
                        </DialogTitle>
                        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                          <Badge className={`${dTypeConf.color} text-white text-[10px] border-0`}>
                            {isRTL ? dTypeConf.label.ar : dTypeConf.label.en}
                          </Badge>
                          {dPriority !== 'medium' && (
                            <Badge className={`${dPriorityConf.color} text-white text-[10px] border-0`}>
                              {isRTL ? dPriorityConf.label.ar : dPriorityConf.label.en}
                            </Badge>
                          )}
                          {detailNotification.student && (detailNotification.student.name_ar || detailNotification.student.code) && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-brand-navy/80 dark:text-brand-turquoise/80 bg-brand-navy/5 dark:bg-brand-turquoise/10 rounded-full px-2 py-0.5" data-testid="detail-student-chip">
                              <User className="h-3 w-3 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                              {isRTL ? 'بخصوص الطالب: ' : 'Regarding: '}
                              {detailNotification.student.name_ar || detailNotification.student.code}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <DialogDescription className="sr-only">
                      {isRTL ? 'تفاصيل الإشعار الكاملة' : 'Full notification details'}
                    </DialogDescription>
                  </DialogHeader>
                  <div className="overflow-y-auto flex-1 min-h-0 mt-1">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground/90" data-testid="detail-message-body">
                      {prettifyText(isRTL ? detailNotification.message : (detailNotification.message_en || detailNotification.message), isRTL)}
                    </p>
                    {detailNotification.lesson_report && (
                      <LessonReportCard report={detailNotification.lesson_report} isRTL={isRTL} />
                    )}
                    {detailNotification.alternative_location && (
                      <p className="mt-3 text-xs text-orange-700 font-semibold">
                        {isRTL ? 'الموقع البديل: ' : 'Relocated to: '}
                        {detailNotification.alternative_location}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-2 pt-3 border-t flex-wrap">
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground min-w-0">
                      <Clock className="h-3 w-3 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                      <span className="truncate">
                        {detailNotification.created_at
                          ? new Date(detailNotification.created_at).toLocaleString(isRTL ? 'ar' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' })
                          : formatTimeAgo(detailNotification.created_at)}
                      </span>
                      {detailNotification.sender_name && (
                        <>
                          <span>•</span>
                          <span className="truncate">{detailNotification.sender_name}</span>
                        </>
                      )}
                    </div>
                    {detailNotification.action_url && (
                      <Button
                        size="sm"
                        className="h-8 gap-1.5 bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
                        onClick={() => { const url = detailNotification.action_url; setDetailNotification(null); navigate(url); }}
                        data-testid="detail-action-btn"
                      >
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" strokeWidth={1.5} />
                        {isRTL ? 'الانتقال إلى الصفحة' : 'Open page'}
                      </Button>
                    )}
                  </div>
                </>
              );
            })()}
          </DialogContent>
        </Dialog>
      </div>
  );

  if (embedded) return content;
  return <Sidebar>{content}</Sidebar>;
};
