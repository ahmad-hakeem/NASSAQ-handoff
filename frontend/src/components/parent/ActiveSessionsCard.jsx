import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { LoadingState } from '../ui/LoadingState';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { toast } from 'sonner';
import { History, Monitor, Loader2, LogOut } from 'lucide-react';
import { getApiErrorMessage } from '../../utils/apiError';

const formatDate = (ts, isRTL) => {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return String(ts);
  }
};

const ActiveSessionsCard = () => {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [endingAll, setEndingAll] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/settings/sessions');
      const list = Array.isArray(res?.data?.sessions) ? res.data.sessions : [];
      setSessions(list);
    } catch {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  const endOne = (s) => {
    nassaqConfirm(
      t('endSessionConfirm') || (isRTL ? 'هل تريد إنهاء هذه الجلسة؟' : 'End this session?'),
      async () => {
        setBusyId(s.id);
        try {
          // Task #374 — only mutate the list AFTER a confirmed 2xx. The
          // previous optimistic filter would hide the row even when the
          // backend revoke failed, making a failed request look like a
          // success and leaving the other device authenticated.
          await api.delete(`/settings/sessions/${s.id}`);
          await load();
          toast.success(t('sessionEnded') || (isRTL ? 'تم إنهاء الجلسة' : 'Session ended'));
        } catch (err) {
          nassaqError(
            getApiErrorMessage(err) ||
              t('errorEndingSession') ||
              (isRTL ? 'تعذر إنهاء الجلسة' : 'Could not end session'),
          );
        } finally {
          setBusyId(null);
        }
      },
      {
        title: t('endSession2') || (isRTL ? 'إنهاء الجلسة' : 'End session'),
        type: 'warning',
        confirmText: t('endSession2') || (isRTL ? 'إنهاء' : 'End'),
        cancelText: t('cancel') || 'Cancel',
      },
    );
  };

  const endAllOthers = () => {
    nassaqConfirm(
      t('endAllOtherSessionsConfirm') ||
        (isRTL ? 'هل تريد تسجيل الخروج من جميع الأجهزة الأخرى؟' : 'Sign out of all other devices?'),
      async () => {
        setEndingAll(true);
        try {
          await api.post('/settings/sessions/end-all', {});
          await load();
          toast.success(t('otherSessionsEnded') || (isRTL ? 'تم إنهاء الجلسات الأخرى' : 'Other sessions ended'));
        } catch (err) {
          nassaqError(getApiErrorMessage(err) || (t('errorEndingSession') || 'Could not end sessions'));
        } finally {
          setEndingAll(false);
        }
      },
      {
        title: t('endAllOtherSessions') || (isRTL ? 'إنهاء جميع الجلسات الأخرى' : 'End all other sessions'),
        type: 'warning',
        confirmText: t('endAll') || (isRTL ? 'إنهاء الكل' : 'End all'),
        cancelText: t('cancel') || 'Cancel',
      },
    );
  };

  const otherCount = sessions.filter((s) => !(s.current || s.is_current)).length;

  return (
    <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-brand-turquoise" />
            <span className="text-sm font-bold font-cairo text-foreground">
              {t('activeSessions') || 'Active sessions'}
            </span>
          </div>
          {otherCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={endAllOthers}
              disabled={endingAll}
              className="h-8 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
              data-testid="parent-end-all-sessions-btn"
            >
              {endingAll ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin me-1.5" />
              ) : (
                <LogOut className="h-3.5 w-3.5 me-1.5" />
              )}
              {t('endAllOtherSessions') || 'End all others'}
            </Button>
          )}
        </div>

        {loading ? (
          <LoadingState variant="section" />
        ) : sessions.length === 0 ? (
          <p className="text-xs text-muted-foreground font-cairo py-3 text-center">
            {t('noActiveSessions') || 'No active sessions'}
          </p>
        ) : (
          <div className="space-y-2" data-testid="parent-sessions-list">
            {sessions.map((s) => {
              const isCurrent = !!(s.current || s.is_current);
              return (
                <div
                  key={s.id}
                  className="flex items-center gap-3 p-3 rounded-xl border border-border/60"
                  data-testid="parent-session-row"
                  data-session-id={s.id}
                  data-session-current={isCurrent ? '1' : '0'}
                >
                  <span className="w-9 h-9 rounded-xl bg-muted/40 flex items-center justify-center shrink-0">
                    <Monitor className="h-4 w-4 text-muted-foreground" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium font-cairo text-foreground truncate">
                      {s.device || s.user_agent?.substring(0, 40) || (t('unknownDevice') || 'Unknown device')}
                    </p>
                    <p className="text-[11px] text-muted-foreground truncate" dir="ltr">
                      {(s.ip_address || '—')} • {formatDate(s.last_active || s.created_at, isRTL)}
                    </p>
                  </div>
                  {isCurrent ? (
                    <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-[10px] border-0">
                      {t('current3') || 'Current'}
                    </Badge>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => endOne(s)}
                      disabled={busyId === s.id}
                      className="h-8 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                      data-testid="parent-end-session-btn"
                    >
                      {busyId === s.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        t('endSession2') || 'End'
                      )}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ActiveSessionsCard;
