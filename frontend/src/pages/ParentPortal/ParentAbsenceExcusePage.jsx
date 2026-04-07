import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Skeleton } from '../../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import {
  FileText, Send, Calendar, Clock, CheckCircle, XCircle,
  AlertCircle, Loader2, Upload, User, ChevronDown, History
} from 'lucide-react';


const STATUS_CONFIG = {
  pending: { label: 'قيد المراجعة', labelEn: 'Pending', color: 'bg-amber-100 text-amber-700 border-amber-200', icon: Clock },
  approved: { label: 'مقبول', labelEn: 'Approved', color: 'bg-green-100 text-green-700 border-green-200', icon: CheckCircle },
  rejected: { label: 'مرفوض', labelEn: 'Rejected', color: 'bg-red-100 text-red-700 border-red-200', icon: XCircle },
};

const ParentAbsenceExcusePage = () => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [children, setChildren] = useState([]);
  const [excuses, setExcuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(true);

  const [selectedChild, setSelectedChild] = useState('');
  const [absenceDate, setAbsenceDate] = useState('');
  const [reason, setReason] = useState('');
  const [attachmentName, setAttachmentName] = useState('');

  useEffect(() => {
    fetchData();
  }, [token]);

  const fetchData = async () => {
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
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedChild || !absenceDate || !reason.trim()) {
      toast.error(t('pleaseFillAllRequiredFields2'));
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/parent-portal/absence-excuse', {
        child_id: selectedChild,
        absence_date: absenceDate,
        reason: reason.trim(),
        attachment_name: attachmentName || null,
      });
      toast.success(t('excuseSubmittedSuccessfully'));
      setExcuses(prev => [res.data.excuse, ...prev]);
      setAbsenceDate('');
      setReason('');
      setAttachmentName('');
      setShowForm(false);
    } catch (err) {
      const msg = err.response?.data?.detail || (isRTL ? 'حدث خطأ' : 'An error occurred');
      toast.error(msg);
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
    } catch (e) { console.error('Error formatting date:', e); return dateStr; }
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 sm:p-6 space-y-6 max-w-3xl mx-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 font-cairo flex items-center gap-2">
              <FileText className="h-7 w-7 text-indigo-600" />
              {t('absenceExcuse2')}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
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
            <div className="h-1.5 bg-gradient-to-r from-indigo-500 to-purple-500" />
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-cairo">
                {t('absenceExcuseForm')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
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
                              <span className="text-xs text-gray-400">({child.class_name})</span>
                            )}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
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
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
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
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
                    {t('attachmentOptional')}
                  </label>
                  <Input
                    type="text"
                    value={attachmentName}
                    onChange={(e) => setAttachmentName(e.target.value)}
                    placeholder={t('documentNameOrAttachmentLink')}
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    {t('enterTheNameOfTheSupportingDocumentEgMedicalReport')}
                  </p>
                </div>

                <Button
                  type="submit"
                  disabled={submitting || !selectedChild || !absenceDate || !reason.trim()}
                  className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white h-11 font-cairo"
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
          <h2 className="text-lg font-bold font-cairo text-gray-800 dark:text-gray-200 flex items-center gap-2">
            <History className="h-5 w-5 text-indigo-500" />
            {t('excuseHistory')}
            {excuses.length > 0 && (
              <Badge variant="secondary" className="text-xs">{excuses.length}</Badge>
            )}
          </h2>

          {excuses.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="text-center py-10">
                <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
                <p className="text-gray-500 dark:text-gray-400 font-cairo">
                  {t('noExcusesSubmittedYet')}
                </p>
              </CardContent>
            </Card>
          ) : (
            excuses.map(excuse => {
              const status = STATUS_CONFIG[excuse.status] || STATUS_CONFIG.pending;
              const StatusIcon = status.icon;
              return (
                <Card key={excuse.id} className="border-0 shadow-sm hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                          <FileText className="h-5 w-5 text-indigo-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-sm text-gray-900 dark:text-gray-100">
                              {excuse.child_name}
                            </span>
                            <Badge className={`text-[10px] ${status.color}`}>
                              <StatusIcon className="h-3 w-3 me-1" />
                              {isRTL ? status.label : status.labelEn}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mb-1.5">
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {formatDate(excuse.absence_date)}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatDate(excuse.created_at)}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-2">{excuse.reason}</p>
                          {excuse.attachment_name && (
                            <div className="mt-1.5 flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-400">
                              <Upload className="h-3 w-3" />
                              {excuse.attachment_name}
                            </div>
                          )}
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
    </PortalLayout>
  );
};

export default ParentAbsenceExcusePage;
