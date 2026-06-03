import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Skeleton } from '../../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { getApiErrorMessage } from '../../utils/apiError';
import {
  FileText, Send, Calendar, Clock, CheckCircle, XCircle,
  Loader2, Upload, User, History, Paperclip, X
} from 'lucide-react';


const STATUS_CONFIG = {
  pending: { label: 'قيد المراجعة', labelEn: 'Pending', color: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900/40', icon: Clock },
  approved: { label: 'مقبول', labelEn: 'Approved', color: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-200 dark:border-green-900/40', icon: CheckCircle },
  rejected: { label: 'مرفوض', labelEn: 'Rejected', color: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900/40', icon: XCircle },
};

const ALLOWED_MIME = ['image/jpeg', 'image/png', 'application/pdf'];
const MAX_FILE_BYTES = 5 * 1024 * 1024;

const formatFileSize = (bytes) => {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const ParentAbsenceExcusePage = ({ embedded = false }) => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();
  const fileInputRef = useRef(null);
  const [children, setChildren] = useState([]);
  const [excuses, setExcuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(true);

  const [selectedChild, setSelectedChild] = useState('');
  const [absenceDate, setAbsenceDate] = useState('');
  const [reason, setReason] = useState('');
  const [attachmentFile, setAttachmentFile] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [childrenRes, excusesRes] = await Promise.all([
        api.get('/parent-portal/children'),
        api.get('/parent-portal/absence-excuses')
      ]);
      const childList = childrenRes.data?.children || [];
      setChildren(childList);
      if (childList.length === 1) setSelectedChild(childList[0].id);
      setExcuses(excusesRes.data?.excuses || []);
    } catch (err) {
      // swallow; UI stays empty
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleFilePicked = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!ALLOWED_MIME.includes(f.type)) {
      nassaqError(t('attachmentTypeNotAllowed'));
      e.target.value = '';
      return;
    }
    if (f.size > MAX_FILE_BYTES) {
      nassaqError(t('attachmentTooLarge'));
      e.target.value = '';
      return;
    }
    setAttachmentFile(f);
  };

  const clearAttachment = () => {
    setAttachmentFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedChild || !absenceDate || !reason.trim()) {
      nassaqError(t('pleaseFillAllRequiredFields2'));
      return;
    }
    setSubmitting(true);
    try {
      let attachment_url = null;
      let attachment_name = null;

      if (attachmentFile) {
        const fd = new FormData();
        fd.append('file', attachmentFile);
        try {
          const up = await api.post('/parent-portal/upload-attachment', fd, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          attachment_url = up.data?.attachment_url || null;
          attachment_name = up.data?.attachment_name || attachmentFile.name;
        } catch (uerr) {
          const msg = getApiErrorMessage(uerr) || t('attachmentUploadFailed');
          nassaqError(msg);
          setSubmitting(false);
          return;
        }
      }

      await api.post('/parent-portal/absence-excuse', {
        child_id: selectedChild,
        absence_date: absenceDate,
        reason: reason.trim(),
        attachment_url,
        attachment_name,
      });
      toast.success(t('excuseSubmittedSuccessfully'));
      fetchData();
      setAbsenceDate('');
      setReason('');
      clearAttachment();
      setShowForm(false);
    } catch (err) {
      const msg = getApiErrorMessage(err) || (isRTL ? 'حدث خطأ' : 'An error occurred');
      nassaqError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric'
      });
    } catch (e) { return dateStr; }
  };

  if (loading) {
    const skeleton = (
      <div className="p-4 space-y-4">
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-2xl" />)}
      </div>
    );
    if (embedded) return skeleton;
    return <PortalLayout portalType="parent">{skeleton}</PortalLayout>;
  }

  const body = (
    <div
      className={`${embedded ? 'space-y-6' : 'p-4 sm:p-6 space-y-6 max-w-3xl mx-auto'}`}
      dir={isRTL ? 'rtl' : 'ltr'}
    >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground dark:text-gray-100 font-cairo flex items-center gap-2">
              <FileText className="h-7 w-7 text-brand-navy" />
              {t('absenceExcuse2')}
            </h1>
            <p className="text-sm text-muted-foreground dark:text-muted-foreground mt-1">
              {t('submitAnAbsenceExcuseForYourChild')}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowForm(!showForm)}
            className="gap-1"
          >
            {showForm ? (
              <>{t('history')} <History className="h-4 w-4" /></>
            ) : (
              <>{t('newExcuse')} <FileText className="h-4 w-4" /></>
            )}
          </Button>
        </div>

        {showForm && (
          <Card className="border-0 shadow-lg overflow-hidden">
            <div className="h-1.5 bg-gradient-to-r from-brand-navy to-brand-purple" />
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-cairo">
                {t('absenceExcuseForm')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('child')}
                  </label>
                  <Select value={selectedChild} onValueChange={setSelectedChild}>
                    <SelectTrigger>
                      <SelectValue placeholder={t('selectChild')} />
                    </SelectTrigger>
                    <SelectContent>
                      {children.map(child => (
                        <SelectItem key={child.id} value={child.id}>
                          <span className="flex items-center gap-2">
                            <User className="h-3.5 w-3.5" />
                            {child.full_name || child.name}
                            {child.class_name && (
                              <span className="text-xs text-muted-foreground">({child.class_name})</span>
                            )}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('dateOfAbsence')}
                  </label>
                  <Input
                    type="date"
                    value={absenceDate}
                    onChange={(e) => setAbsenceDate(e.target.value)}
                    className="w-full"
                    required
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('reasonForAbsence')}
                  </label>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={t('describeTheReasonForAbsence')}
                    className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                    required
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('attachmentOptional')}
                  </label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,application/pdf"
                    onChange={handleFilePicked}
                    className="hidden"
                    data-testid="excuse-attachment-input"
                  />
                  {!attachmentFile ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                      className="w-full justify-center gap-2"
                    >
                      <Paperclip className="h-4 w-4" />
                      {t('attachmentChooseFile')}
                    </Button>
                  ) : (
                    <div className="flex items-center justify-between gap-2 rounded-md border border-input bg-muted/40 px-3 py-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <Paperclip className="h-4 w-4 text-brand-navy shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm truncate" data-testid="excuse-attachment-name">
                            {attachmentFile.name}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {formatFileSize(attachmentFile.size)}
                          </p>
                        </div>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={clearAttachment}
                        aria-label={t('attachmentRemove')}
                        className="h-8 w-8 shrink-0"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    {t('attachmentFileHelp')}
                  </p>
                </div>

                <Button
                  type="submit"
                  disabled={submitting || !selectedChild || !absenceDate || !reason.trim()}
                  className="w-full bg-gradient-to-r from-brand-navy to-brand-purple hover:from-brand-navy-dark hover:to-brand-purple text-white h-11 font-cairo"
                >
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-4 w-4 me-2" />
                      {t('submitExcuse')}
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        <div className="space-y-3">
          <h2 className="text-lg font-bold font-cairo text-foreground dark:text-gray-200 flex items-center gap-2">
            <History className="h-5 w-5 text-brand-navy" />
            {t('excuseHistory')}
            {excuses.length > 0 && (
              <Badge variant="secondary" className="text-xs">{excuses.length}</Badge>
            )}
          </h2>

          {excuses.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="text-center py-10">
                <FileText className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50 dark:text-muted-foreground" />
                <p className="text-muted-foreground dark:text-muted-foreground font-cairo">
                  {t('noExcusesSubmittedYet')}
                </p>
              </CardContent>
            </Card>
          ) : (
            excuses.map(excuse => {
              const status = STATUS_CONFIG[excuse.status] || STATUS_CONFIG.pending;
              const StatusIcon = status.icon;
              const hasUploadedFile = excuse.attachment_url && /^(https?:|data:)/i.test(excuse.attachment_url);
              return (
                <Card key={excuse.id} className="border-0 shadow-sm hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="w-10 h-10 rounded-xl bg-brand-navy/15 dark:bg-brand-navy/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <FileText className="h-5 w-5 text-brand-navy" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-sm text-foreground dark:text-gray-100">
                              {excuse.child_name}
                            </span>
                            <Badge className={`text-[10px] ${status.color}`}>
                              <StatusIcon className="h-3 w-3 me-1" />
                              {isRTL ? status.label : status.labelEn}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-muted-foreground dark:text-muted-foreground mb-1.5">
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {formatDate(excuse.absence_date)}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatDate(excuse.created_at)}
                            </span>
                          </div>
                          <p className="text-sm text-foreground dark:text-muted-foreground/50 line-clamp-2">{excuse.reason}</p>
                          {hasUploadedFile ? (
                            <a
                              href={excuse.attachment_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              download={excuse.attachment_name || undefined}
                              className="mt-1.5 inline-flex items-center gap-1 text-xs text-brand-navy hover:underline dark:text-brand-navy/80"
                            >
                              <Upload className="h-3 w-3" />
                              {excuse.attachment_name || t('attachmentOpen')}
                            </a>
                          ) : excuse.attachment_name ? (
                            <div className="mt-1.5 flex items-center gap-1 text-xs text-brand-navy dark:text-brand-navy/70">
                              <Upload className="h-3 w-3" />
                              {excuse.attachment_name}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </div>
  );

  if (embedded) return body;
  return <PortalLayout portalType="parent">{body}</PortalLayout>;
};

export default ParentAbsenceExcusePage;
