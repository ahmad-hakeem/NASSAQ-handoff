import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
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
  pending: { label: 'قيد الانتظار', labelEn: 'Pending', color: 'bg-amber-100 text-amber-700 border-amber-200', icon: Clock },
  confirmed: { label: 'مؤكد', labelEn: 'Confirmed', color: 'bg-green-100 text-green-700 border-green-200', icon: CheckCircle },
  cancelled: { label: 'ملغي', labelEn: 'Cancelled', color: 'bg-red-100 text-red-700 border-red-200', icon: XCircle },
};

const CONTACT_OPTIONS = [
  { value: 'in_person', label: 'حضوري', labelEn: 'In Person', icon: MapPin },
  { value: 'phone', label: 'هاتفي', labelEn: 'Phone Call', icon: Phone },
  { value: 'video', label: 'مرئي (عن بعد)', labelEn: 'Video Call', icon: MessageSquare },
];

const ParentMeetingRequestPage = () => {
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

  useEffect(() => {
    fetchMeetings();
  }, [token]);

  const fetchMeetings = async () => {
    try {
      const res = await api.get('/parent-portal/meeting-requests');
      setMeetings(res.data?.meetings || []);
    } catch (err) {
      console.error('Error fetching meetings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!preferredDate || !topic.trim()) {
      toast.error(isRTL ? 'يرجى تعبئة التاريخ والموضوع' : 'Please fill date and topic');
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
      toast.success(isRTL ? 'تم إرسال طلب الاجتماع بنجاح' : 'Meeting request submitted successfully');
      setMeetings(prev => [res.data.meeting, ...prev]);
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
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 font-cairo flex items-center gap-2">
              <CalendarCheck className="h-7 w-7 text-indigo-600" />
              {isRTL ? 'طلب اجتماع' : 'Meeting Request'}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
              {isRTL ? 'أرسل طلب اجتماع مع إدارة المدرسة' : 'Request a meeting with school administration'}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowForm(!showForm)}
            className="gap-1"
          >
            {showForm ? (
              <>{isRTL ? 'طلباتي' : 'My Requests'} <History className="h-4 w-4" /></>
            ) : (
              <>{isRTL ? 'طلب جديد' : 'New Request'} <CalendarCheck className="h-4 w-4" /></>
            )}
          </Button>
        </div>

        {showForm && (
          <Card className="border-0 shadow-lg overflow-hidden">
            <div className="h-1.5 bg-gradient-to-r from-indigo-500 to-purple-500" />
            <CardHeader className="pb-2">
              <CardTitle className="text-lg font-cairo">
                {isRTL ? 'نموذج طلب اجتماع' : 'Meeting Request Form'}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
                      {isRTL ? 'التاريخ المفضل *' : 'Preferred Date *'}
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
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
                      {isRTL ? 'الوقت المفضل' : 'Preferred Time'}
                    </label>
                    <Input
                      type="time"
                      value={preferredTime}
                      onChange={(e) => setPreferredTime(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
                    {isRTL ? 'موضوع الاجتماع *' : 'Meeting Topic *'}
                  </label>
                  <Input
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder={isRTL ? 'مثال: مناقشة المستوى الدراسي' : 'e.g., Discuss academic performance'}
                    required
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
                    {isRTL ? 'تفاصيل إضافية' : 'Additional Details'}
                  </label>
                  <textarea
                    value={details}
                    onChange={(e) => setDetails(e.target.value)}
                    placeholder={isRTL ? 'أي تفاصيل إضافية تودّ إضافتها...' : 'Any additional details you want to share...'}
                    className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5 block">
                    {isRTL ? 'طريقة التواصل المفضلة' : 'Contact Preference'}
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
                              ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                              : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 text-gray-600 dark:text-gray-400'
                          }`}
                        >
                          <Icon className={`h-5 w-5 ${isSelected ? 'text-indigo-600' : ''}`} />
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
                  className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white h-11 font-cairo"
                >
                  {submitting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-4 w-4 me-2" />
                      {isRTL ? 'إرسال الطلب' : 'Submit Request'}
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
            {isRTL ? 'طلباتي السابقة' : 'My Requests'}
            {meetings.length > 0 && (
              <Badge variant="secondary" className="text-xs">{meetings.length}</Badge>
            )}
          </h2>

          {meetings.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="text-center py-10">
                <CalendarCheck className="h-12 w-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
                <p className="text-gray-500 dark:text-gray-400 font-cairo">
                  {isRTL ? 'لا توجد طلبات اجتماع بعد' : 'No meeting requests yet'}
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
                      <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <CalendarCheck className="h-5 w-5 text-indigo-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <h3 className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">
                            {meeting.topic}
                          </h3>
                          <Badge className={`text-[10px] flex-shrink-0 ${status.color}`}>
                            <StatusIcon className="h-3 w-3 me-1" />
                            {isRTL ? status.label : status.labelEn}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400 mb-1.5 flex-wrap">
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
                          <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">{meeting.details}</p>
                        )}
                        {meeting.admin_notes && (
                          <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                            <p className="text-xs text-blue-700 dark:text-blue-300">
                              <span className="font-medium">{isRTL ? 'رد الإدارة: ' : 'Admin reply: '}</span>
                              {meeting.admin_notes}
                            </p>
                          </div>
                        )}
                        <p className="text-[10px] text-gray-400 mt-1.5">
                          {isRTL ? 'تاريخ الطلب: ' : 'Requested: '}{formatDate(meeting.created_at)}
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
