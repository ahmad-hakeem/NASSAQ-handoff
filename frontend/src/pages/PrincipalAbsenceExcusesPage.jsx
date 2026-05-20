import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import {
  FileText,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  RefreshCw,
  Paperclip,
  User,
  GraduationCap,
  Inbox,
} from 'lucide-react';

const FILTERS = ['pending', 'approved', 'rejected', 'all'];

const STATUS_CONFIG = {
  pending: { labelAr: 'قيد المراجعة', labelEn: 'Pending', color: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900/40', icon: Clock },
  approved: { labelAr: 'مقبول', labelEn: 'Approved', color: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-200 dark:border-green-900/40', icon: CheckCircle },
  rejected: { labelAr: 'مرفوض', labelEn: 'Rejected', color: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900/40', icon: XCircle },
};

const PrincipalAbsenceExcusesPage = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { api, user } = useAuth();
  const { nassaqWarning, nassaqError } = useNassaqAlert();

  const role = user?.role;
  const canReview = ['platform_admin', 'school_admin', 'school_principal', 'school_sub_admin'].includes(role);

  const [filter, setFilter] = useState('pending');
  const [excuses, setExcuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReason, setRejectReason] = useState('');

  const fetchExcuses = useCallback(async (which = filter) => {
    setLoading(true);
    try {
      const params = which && which !== 'all' ? { status_filter: which } : {};
      const res = await api.get('/attendance/excuses', { params });
      setExcuses(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      setExcuses([]);
      const msg = err.response?.data?.detail || (isRTL ? 'تعذّر تحميل الأعذار' : 'Failed to load excuses');
      nassaqError(msg);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, filter, isRTL]);

  useEffect(() => {
    fetchExcuses(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const formatDate = (s) => {
    if (!s) return '';
    try {
      return new Date(s).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
      });
    } catch { return s; }
  };

  const formatDateTime = (s) => {
    if (!s) return '';
    try {
      return new Date(s).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return s; }
  };

  const handleApprove = (excuse) => {
    if (!canReview) return;
    nassaqWarning(
      isRTL
        ? `سيتم قبول العذر وتحديث سجل الحضور لـ ${excuse.child_name || excuse.student_name || ''}. هل تريد المتابعة؟`
        : `This will approve the excuse and update the attendance record for ${excuse.child_name || excuse.student_name || ''}. Continue?`,
      {
        title: isRTL ? 'تأكيد القبول' : 'Confirm approve',
        confirmText: t('approve'),
        cancelText: t('cancel'),
        showCancel: true,
        onConfirm: async () => {
          setActionId(excuse.id);
          try {
            await api.put(`/attendance/excuse/${excuse.id}/approve`);
            toast.success(isRTL ? 'تمت الموافقة على العذر' : 'Excuse approved');
            window.dispatchEvent(new CustomEvent('excuses:refresh'));
            fetchExcuses(filter);
          } catch (err) {
            const msg = err.response?.data?.detail || (isRTL ? 'تعذّر إكمال العملية' : 'Action failed');
            nassaqError(msg);
          } finally {
            setActionId(null);
          }
        },
      }
    );
  };

  const submitReject = async (excuse) => {
    setActionId(excuse.id);
    try {
      await api.put(`/attendance/excuse/${excuse.id}/reject`, {
        reason: rejectReason.trim() || null,
      });
      toast.success(isRTL ? 'تم رفض العذر' : 'Excuse rejected');
      setRejectingId(null);
      setRejectReason('');
      window.dispatchEvent(new CustomEvent('excuses:refresh'));
      fetchExcuses(filter);
    } catch (err) {
      const msg = err.response?.data?.detail || (isRTL ? 'تعذّر إكمال العملية' : 'Action failed');
      nassaqError(msg);
    } finally {
      setActionId(null);
    }
  };

  const filterLabel = (key) => {
    if (key === 'pending') return isRTL ? 'قيد المراجعة' : 'Pending';
    if (key === 'approved') return isRTL ? 'مقبول' : 'Approved';
    if (key === 'rejected') return isRTL ? 'مرفوض' : 'Rejected';
    return isRTL ? 'الكل' : 'All';
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="principal-absence-excuses-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between" dir={isRTL ? 'rtl' : 'ltr'}>
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
                <FileText className="h-6 w-6 text-brand-navy" aria-hidden="true" strokeWidth={1.5} />
                {isRTL ? 'أعذار الغياب' : 'Absence Excuses'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal mt-1">
                {isRTL
                  ? 'مراجعة وقبول/رفض أعذار الغياب المُرسلة من أولياء الأمور'
                  : 'Review and approve or reject absence excuses submitted by parents'}
              </p>
            </div>
            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => fetchExcuses(filter)}
              disabled={loading}
              data-testid="excuses-refresh-btn"
            >
              <RefreshCw className={`h-4 w-4 me-2 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
              {t('refresh')}
            </Button>
          </div>

          <div className="flex items-center gap-1 mt-4 bg-muted/50 rounded-xl p-1" dir={isRTL ? 'rtl' : 'ltr'}>
            {FILTERS.map((key) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                data-testid={`excuses-filter-${key}`}
                className={`px-4 py-2 rounded-lg text-sm font-tajawal font-medium transition-all ${
                  filter === key
                    ? 'bg-background shadow-sm text-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
                }`}
              >
                {filterLabel(key)}
              </button>
            ))}
          </div>
        </header>

        <div className="p-4 sm:p-6 space-y-4" dir={isRTL ? 'rtl' : 'ltr'}>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
            </div>
          ) : excuses.length === 0 ? (
            <Card className="card-nassaq">
              <CardContent className="py-16 text-center">
                <div className="w-20 h-20 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
                  <Inbox className="h-10 w-10 text-muted-foreground/30" aria-hidden="true" strokeWidth={1.5} />
                </div>
                <p className="font-cairo text-lg text-muted-foreground">
                  {isRTL ? 'لا توجد أعذار في هذه الحالة' : 'No excuses match this filter'}
                </p>
              </CardContent>
            </Card>
          ) : (
            excuses.map((excuse) => {
              const status = STATUS_CONFIG[excuse.status] || STATUS_CONFIG.pending;
              const StatusIcon = status.icon;
              const isRejecting = rejectingId === excuse.id;
              const isBusy = actionId === excuse.id;
              const hasUploadedFile = excuse.attachment_url && /^(https?:|data:)/i.test(excuse.attachment_url);

              return (
                <Card key={excuse.id} className="border-0 shadow-sm hover:shadow-md transition-shadow"
                  data-testid={`excuse-card-${excuse.id}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <div className="w-10 h-10 rounded-xl bg-brand-navy/15 flex items-center justify-center flex-shrink-0">
                          <FileText className="h-5 w-5 text-brand-navy" aria-hidden="true" strokeWidth={1.5} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center flex-wrap gap-2 mb-1.5">
                            <span className="inline-flex items-center gap-1 font-semibold text-sm text-foreground">
                              <GraduationCap className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
                              {excuse.child_name || excuse.student_name || excuse.child_id}
                            </span>
                            {excuse.parent_name && (
                              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                                <User className="h-3 w-3" aria-hidden="true" strokeWidth={1.5} />
                                {excuse.parent_name}
                              </span>
                            )}
                            <Badge className={`text-[10px] ${status.color}`}>
                              <StatusIcon className="h-3 w-3 me-1" aria-hidden="true" strokeWidth={1.5} />
                              {isRTL ? status.labelAr : status.labelEn}
                            </Badge>
                          </div>
                          <div className="flex items-center flex-wrap gap-3 text-xs text-muted-foreground mb-1.5">
                            <span className="inline-flex items-center gap-1">
                              <Calendar className="h-3 w-3" aria-hidden="true" strokeWidth={1.5} />
                              {isRTL ? 'تاريخ الغياب: ' : 'Absence date: '}
                              {formatDate(excuse.absence_date)}
                            </span>
                            <span className="inline-flex items-center gap-1">
                              <Clock className="h-3 w-3" aria-hidden="true" strokeWidth={1.5} />
                              {isRTL ? 'أُرسل: ' : 'Submitted: '}
                              {formatDateTime(excuse.created_at)}
                            </span>
                          </div>
                          {excuse.reason && (
                            <p className="text-sm text-foreground whitespace-pre-wrap" data-testid="excuse-reason">
                              {excuse.reason}
                            </p>
                          )}
                          {hasUploadedFile ? (
                            <a
                              href={excuse.attachment_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              download={excuse.attachment_name || undefined}
                              className="mt-2 inline-flex items-center gap-1 text-xs text-brand-navy hover:underline"
                            >
                              <Paperclip className="h-3 w-3" aria-hidden="true" strokeWidth={1.5} />
                              {excuse.attachment_name || (isRTL ? 'فتح المرفق' : 'Open attachment')}
                            </a>
                          ) : excuse.attachment_name ? (
                            <div className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
                              <Paperclip className="h-3 w-3" aria-hidden="true" strokeWidth={1.5} />
                              {excuse.attachment_name}
                            </div>
                          ) : null}
                          {excuse.status === 'rejected' && excuse.rejection_reason && (
                            <div className="mt-2 rounded-lg border border-red-200 bg-red-50 dark:bg-red-900/20 px-3 py-2 text-xs text-red-700 dark:text-red-300">
                              <span className="font-semibold">{isRTL ? 'سبب الرفض: ' : 'Rejection reason: '}</span>
                              {excuse.rejection_reason}
                            </div>
                          )}
                          {excuse.reviewed_at && (
                            <div className="mt-1 text-[11px] text-muted-foreground">
                              {isRTL ? 'تمت المراجعة: ' : 'Reviewed: '}{formatDateTime(excuse.reviewed_at)}
                            </div>
                          )}
                        </div>
                      </div>

                      {canReview && excuse.status === 'pending' && !isRejecting && (
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <Button
                            size="sm"
                            className="rounded-xl bg-green-600 hover:bg-green-700 text-white"
                            onClick={() => handleApprove(excuse)}
                            disabled={isBusy}
                            data-testid={`excuse-approve-${excuse.id}`}
                          >
                            {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : (
                              <>
                                <CheckCircle className="h-4 w-4 me-1" aria-hidden="true" strokeWidth={1.5} />
                                {t('approve')}
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-xl border-red-300 text-red-700 hover:bg-red-50"
                            onClick={() => { setRejectingId(excuse.id); setRejectReason(''); }}
                            disabled={isBusy}
                            data-testid={`excuse-reject-open-${excuse.id}`}
                          >
                            <XCircle className="h-4 w-4 me-1" aria-hidden="true" strokeWidth={1.5} />
                            {t('reject')}
                          </Button>
                        </div>
                      )}
                    </div>

                    {canReview && isRejecting && (
                      <div className="mt-3 rounded-xl border border-border bg-muted/30 p-3 space-y-2">
                        <label className="text-xs font-semibold text-foreground">
                          {isRTL ? 'سبب الرفض (اختياري)' : 'Rejection reason (optional)'}
                        </label>
                        <textarea
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          rows={3}
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          placeholder={isRTL ? 'اكتب سبب الرفض ليطّلع عليه ولي الأمر' : 'Explain why this excuse is rejected'}
                          data-testid={`excuse-reject-reason-${excuse.id}`}
                        />
                        <div className="flex items-center gap-2 justify-end">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => { setRejectingId(null); setRejectReason(''); }}
                            disabled={isBusy}
                          >
                            {t('cancel')}
                          </Button>
                          <Button
                            size="sm"
                            className="rounded-xl bg-red-600 hover:bg-red-700 text-white"
                            onClick={() => submitReject(excuse)}
                            disabled={isBusy}
                            data-testid={`excuse-reject-confirm-${excuse.id}`}
                          >
                            {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : (
                              isRTL ? 'تأكيد الرفض' : 'Confirm reject'
                            )}
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </div>
    </Sidebar>
  );
};

export default PrincipalAbsenceExcusesPage;
