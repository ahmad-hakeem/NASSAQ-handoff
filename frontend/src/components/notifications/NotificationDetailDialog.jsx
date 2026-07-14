// Cross-role notification quick-preview dialog — mirrors the parent
// pattern in pages/NotificationsPage.jsx (full message readable in
// place, deep link surfaced as an explicit button instead of implicit
// navigation). Purely presentational: it makes NO API calls — each
// surface owns its own mark-read endpoint and passes a pre-normalized
// notification via the adapters in ./notificationDisplay.
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../ui/dialog';
import { Clock, ExternalLink, User } from 'lucide-react';
import { priorityConfig, prettifyText, normalizeNotificationPriority } from './notificationDisplay';

export function NotificationDetailDialog({ notification, isRTL, onClose, onNavigate }) {
  // Render nothing when closed so host pages (and their viewport
  // snapshot tests) get zero extra DOM in the default state.
  if (!notification) return null;

  const typeMeta = notification.typeMeta || {};
  const TypeIcon = typeMeta.icon;
  const dPriority = normalizeNotificationPriority(notification.priority);
  const dPriorityConf = priorityConfig[dPriority];
  const isUrgent = dPriority === 'critical' || dPriority === 'high';

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose?.(); }}>
      {/* dir is set explicitly because the Radix portal renders outside
          the page's dir container. */}
      <DialogContent
        dir={isRTL ? 'rtl' : 'ltr'}
        className="max-w-lg max-h-[85vh] flex flex-col"
        data-testid="notification-detail-dialog"
      >
        <DialogHeader className="text-start space-y-0">
          <div className="flex items-start gap-3 pe-6">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${isUrgent ? 'bg-red-100 dark:bg-red-900/30' : `${typeMeta.color || 'bg-gray-500'}/10`}`}>
              {TypeIcon && (
                <TypeIcon
                  className={`h-5 w-5 ${dPriority === 'critical' ? 'text-red-500' : (typeMeta.iconColor || 'text-gray-500')}`}
                  aria-hidden="true"
                  strokeWidth={1.5}
                />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <DialogTitle className="font-cairo text-base leading-snug break-words text-start">
                {prettifyText(isRTL ? notification.title : (notification.titleEn || notification.title), isRTL)}
              </DialogTitle>
              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                {typeMeta.label && (
                  <Badge className={`${typeMeta.color} text-white text-[10px] border-0`}>
                    {isRTL ? typeMeta.label.ar : typeMeta.label.en}
                  </Badge>
                )}
                {dPriority !== 'medium' && (
                  <Badge className={`${dPriorityConf.color} text-white text-[10px] border-0`}>
                    {isRTL ? dPriorityConf.label.ar : dPriorityConf.label.en}
                  </Badge>
                )}
                {notification.student && (notification.student.name_ar || notification.student.code) && (
                  <span
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-brand-navy/80 dark:text-brand-turquoise/80 bg-brand-navy/5 dark:bg-brand-turquoise/10 rounded-full px-2 py-0.5"
                    data-testid="detail-student-chip"
                  >
                    <User className="h-3 w-3 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                    {isRTL ? 'بخصوص الطالب: ' : 'Regarding: '}
                    {notification.student.name_ar || notification.student.code}
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
          <p
            className="text-sm leading-relaxed whitespace-pre-wrap break-words text-foreground/90"
            data-testid="detail-message-body"
          >
            {prettifyText(isRTL ? notification.message : (notification.messageEn || notification.message), isRTL)}
          </p>
          {notification.alternativeLocation && (
            <p className="mt-3 text-xs text-orange-700 font-semibold">
              {isRTL ? 'الموقع البديل: ' : 'Relocated to: '}
              {notification.alternativeLocation}
            </p>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 pt-3 border-t flex-wrap">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground min-w-0">
            <Clock className="h-3 w-3 shrink-0" aria-hidden="true" strokeWidth={1.5} />
            <span className="truncate">
              {notification.createdAt
                ? new Date(notification.createdAt).toLocaleString(isRTL ? 'ar' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' })
                : ''}
            </span>
            {notification.senderName && (
              <>
                <span>•</span>
                <span className="truncate">{notification.senderName}</span>
              </>
            )}
          </div>
          {notification.actionUrl && onNavigate && (
            <Button
              size="sm"
              className="h-8 gap-1.5 bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
              onClick={() => { const url = notification.actionUrl; onClose?.(); onNavigate(url); }}
              data-testid="detail-action-btn"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" strokeWidth={1.5} />
              {isRTL ? 'الانتقال إلى الصفحة' : 'Open page'}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
