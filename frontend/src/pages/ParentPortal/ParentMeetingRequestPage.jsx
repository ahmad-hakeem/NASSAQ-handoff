import React, { useState, useEffect, useCallback } from 'react';
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
  CalendarCheck, Send, Calendar, Clock, CheckCircle, XCircle,
  AlertCircle, Loader2, Phone, Mail, MapPin, History,
  MessageSquare, User
} from 'lucide-react';


const STATUS_CONFIG = {
  pending: { label: 'قيد الانتظار', labelEn: 'Pending', color: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900/40', icon: Clock },
  confirmed: { label: 'مؤكد', labelEn: 'Confirmed', color: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-green-200 dark:border-green-900/40', icon: CheckCircle },
  cancelled: { label: 'ملغي', labelEn: 'Cancelled', color: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900/40', icon: XCircle },
};

const CONTACT_OPTIONS = [
  { value: 'in_person', label: 'حضوري', labelEn: 'In Person', icon: MapPin },
  { value: 'phone', label: 'هاتفي', labelEn: 'Phone Call', icon: Phone },
  { value: 'video', label: 'مرئي (عن بعد)', labelEn: 'Video Call', icon: MessageSquare },
];

const ParentMeetingRequestPage = () => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showForm, setShowForm] = useState(true);

  const [preferredDate, setPreferredDate] = useState('');
  const [preferredTime, setPreferredTime] = useState('');
  const [topic, setTopic] = useState('');
  const [details, setDetails] = useState('');
  const [contactPreference, setContactPreference] = useState('in_person');

  const fetchMeetings = useCallback(async () => {
    try {
      const res = await api.get('/parent-portal/meeting-requests');
      setMeetings(res.data?.meetings || []);
    } catch (err) {
      console.error('Error fetching meetings:', err);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!preferredDate || !topic.trim()) {
      toast.error(t('pleaseFillDateAndTopic'));
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/parent-portal/meeting-request', {
        preferred_date: preferredDate,
        preferred_time: preferredTime,
        topic: topic.trim(),
        details: details.trim(),
        contact_preference: contactPreference,
      });
      toast.success(t('meetingRequestSubmittedSuccessfully'));
      fetchMeetings();
      setPreferredDate('');
      setPreferredTime('');
      setTopic('');
      setDetails('');
      setContactPreference('in_person');
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

  const getContactLabel = (pref) => {
    const opt = CONTACT_OPTIONS.find(o => o.value === pref);
    if (!opt) return pref;
    return isRTL ? opt.label : opt.labelEn;
  };

  const getContactIcon = (pref) => {
    const opt = CONTACT_OPTIONS.find(o => o.value === pref);
    return opt?.icon || MapPin;
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
            <h1 className="text-2xl font-bold text-foreground dark:text-gray-100 font-cairo flex items-center gap-2">
              <CalendarCheck className="h-7 w-7 text-brand-navy" />
              {t('meetingRequest')}
            </h1>
            <p className="text-sm text-muted-foreground dark:text-muted-foreground mt-1">
              {t('requestAMeetingWithSchoolAdministration')}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowForm(!showForm)}
            className="gap-1"
          >
            {showForm ? (
              <>{t('myRequests')} <History className="h-4 w-4" /></>
            ) : (
              <>{t('newRequest')} <CalendarCheck className="h-4 w-4" /></>
            )}
          </Button>
        </div>

        {showForm && (
          <Card className="border-0 shadow-lg overflow-hidden">
            <div className="h-1.5 bg-gradient-to-r from-brand-navy to-brand-purple" />
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-cairo">
                {t('meetingRequestForm')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                      {t('preferredDate')}
                    </label>
                    <Input
                      type="date"
                      value={preferredDate}
                      onChange={(e) => setPreferredDate(e.target.value)}
                      min={new Date().toISOString().split('T')[0]}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                      {t('preferredTime')}
                    </label>
                    <Input
                      type="time"
                      value={preferredTime}
                      onChange={(e) => setPreferredTime(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('meetingTopic')}
                  </label>
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder={t('egDiscussAcademicPerformance')}
                    required
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('additionalDetails2')}
                  </label>
                  <textarea
                    value={details}
                    onChange={(e) => setDetails(e.target.value)}
                    placeholder={t('anyAdditionalDetailsYouWantToShare')}
                    className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-foreground dark:text-muted-foreground/50 mb-1.5 block">
                    {t('contactPreference')}
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {CONTACT_OPTIONS.map(opt => {
                      const Icon = opt.icon;
                      const isSelected = contactPreference === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setContactPreference(opt.value)}
                          className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border-2 transition-all text-sm ${
                            isSelected
                              ? 'border-brand-navy bg-brand-navy/5 dark:bg-brand-navy/20 text-brand-navy dark:text-brand-navy/80'
                              : 'border-border dark:border-gray-700 hover:border-border text-muted-foreground dark:text-muted-foreground'
                          }`}
                        >
                          <Icon className={`h-5 w-5 ${isSelected ? 'text-brand-navy' : ''}`} />
                          <span className="font-medium text-xs">
                            {isRTL ? opt.label : opt.labelEn}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <Button
                  type="submit"
                  disabled={submitting || !preferredDate || !topic.trim()}
                  className="w-full bg-gradient-to-r from-brand-navy to-brand-purple hover:from-brand-navy-dark hover:to-brand-purple text-white h-11 font-cairo"
                >
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-4 w-4 me-2" />
                      {t('submitRequest')}
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
            {t('myRequests2')}
            {meetings.length > 0 && (
              <Badge variant="secondary" className="text-xs">{meetings.length}</Badge>
            )}
          </h2>

          {meetings.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="text-center py-10">
                <CalendarCheck className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50 dark:text-muted-foreground" />
                <p className="text-muted-foreground dark:text-muted-foreground font-cairo">
                  {t('noMeetingRequestsYet')}
                </p>
              </CardContent>
            </Card>
          ) : (
            meetings.map(meeting => {
              const status = STATUS_CONFIG[meeting.status] || STATUS_CONFIG.pending;
              const StatusIcon = status.icon;
              const ContactIcon = getContactIcon(meeting.contact_preference);
              return (
                <Card key={meeting.id} className="border-0 shadow-sm hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-xl bg-brand-navy/15 dark:bg-brand-navy/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <CalendarCheck className="h-5 w-5 text-brand-navy" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <h3 className="font-semibold text-sm text-foreground dark:text-gray-100 truncate font-cairo">
                            {meeting.topic}
                          </h3>
                          <Badge className={`text-[10px] flex-shrink-0 ${status.color}`}>
                            <StatusIcon className="h-3 w-3 me-1" />
                            {isRTL ? status.label : status.labelEn}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground dark:text-muted-foreground mb-1.5 flex-wrap">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {formatDate(meeting.preferred_date)}
                          </span>
                          {meeting.preferred_time && (
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {meeting.preferred_time}
                            </span>
                          )}
                          <span className="flex items-center gap-1">
                            <ContactIcon className="h-3 w-3" />
                            {getContactLabel(meeting.contact_preference)}
                          </span>
                        </div>
                        {meeting.details && (
                          <p className="text-xs text-muted-foreground dark:text-muted-foreground line-clamp-2">{meeting.details}</p>
                        )}
                        {meeting.admin_notes && (
                          <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                            <p className="text-xs text-blue-700 dark:text-blue-300">
                              <span className="font-medium">{t('adminReply')}</span>
                              {meeting.admin_notes}
                            </p>
                          </div>
                        )}
                        <p className="text-[10px] text-muted-foreground mt-1.5">
                          {t('requested')}{formatDate(meeting.created_at)}
                        </p>
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

export default ParentMeetingRequestPage;
