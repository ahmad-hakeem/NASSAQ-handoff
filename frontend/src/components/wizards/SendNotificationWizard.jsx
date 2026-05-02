import { useState, useEffect } from 'react';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import { Checkbox } from '../../components/ui/checkbox';
import { UserMultiSelect } from '../../components/ui/UserMultiSelect';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  Loader2,
  CheckCircle2,
  Send,
  Bell,
  Users,
  AlertTriangle,
  Calendar,
  Megaphone,
} from 'lucide-react';


export const SendNotificationWizard = ({ open, onClose, onOpenChange }) => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { token, api } = useAuth();
  const { nassaqWarning, nassaqError } = useNassaqAlert();
  
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [result, setResult] = useState(null);
  
  const [data, setData] = useState({
    title_ar: '',
    title_en: '',
    message_ar: '',
    message_en: '',
    recipient_type: 'all_students',
    recipient_filter: null,
    notification_type: 'announcement',
    priority: 'normal',
    send_push: true,
    send_sms: false,
    send_email: false,
    send_whatsapp: false,
  });
  
  const [options, setOptions] = useState({
    recipientTypes: [],
    notificationTypes: [],
    priorities: [],
    grades: [],
    classes: [],
  });

  useEffect(() => {
    if (open) fetchOptions();
  }, [open]);

  const fetchOptions = async () => {
    setLoading(true);
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    try {
      const [recipientRes, notifTypeRes, priorityRes, gradesRes, classesRes] = await Promise.all([
        api.get('/notifications/options/recipient-types').catch(() => ({ data: { types: [] } })),
        api.get('/notifications/options/notification-types').catch(() => ({ data: { types: [] } })),
        api.get('/notifications/options/priorities').catch(() => ({ data: { priorities: [] } })),
        api.get('/classes/options/grades').catch(() => ({ data: { grades: [] } })),
        api.get('/classes/').catch(() => ({ data: { classes: [] } })),
      ]);

      setOptions({
        recipientTypes: recipientRes.data.types || [
          { code: 'all_students', name_ar: 'جميع الطلاب', name_en: 'All Students' },
          { code: 'all_teachers', name_ar: 'جميع المعلمين', name_en: 'All Teachers' },
          { code: 'all_parents', name_ar: 'جميع أولياء الأمور', name_en: 'All Parents' },
          { code: 'grade_students', name_ar: 'طلاب صف معين', name_en: 'Grade Students' },
          { code: 'class_students', name_ar: 'طلاب فصل معين', name_en: 'Class Students' },
        ],
        notificationTypes: notifTypeRes.data.types || [
          { code: 'announcement', name_ar: 'إعلان', name_en: 'Announcement' },
          { code: 'reminder', name_ar: 'تذكير', name_en: 'Reminder' },
          { code: 'alert', name_ar: 'تنبيه', name_en: 'Alert' },
          { code: 'event', name_ar: 'حدث', name_en: 'Event' },
          { code: 'emergency', name_ar: 'طوارئ', name_en: 'Emergency' },
          { code: 'circular', name_ar: 'تعميم', name_en: 'Circular' },
          { code: 'other', name_ar: 'أخرى', name_en: 'Other' },
        ],
        priorities: priorityRes.data.priorities || [
          { code: 'low', name_ar: 'منخفضة', name_en: 'Low' },
          { code: 'normal', name_ar: 'عادية', name_en: 'Normal' },
          { code: 'high', name_ar: 'عالية', name_en: 'High' },
          { code: 'urgent', name_ar: 'عاجلة', name_en: 'Urgent' },
        ],
        grades: gradesRes.data.grades || [],
        classes: classesRes.data.classes || [],
      });
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const onChange = (key, value) => setData(prev => ({ ...prev, [key]: value }));

  const needsFilter = ['grade_students', 'grade_parents', 'class_students', 'class_parents'].includes(data.recipient_type);
  const isSpecificUsers = data.recipient_type === 'specific_users';

  const handleSubmit = async () => {
    if (!data.title_ar?.trim() || !data.message_ar?.trim()) {
      nassaqWarning(t('titleAndMessageRequired'));
      return;
    }

    setSubmitting(true);
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    
    try {
      const { send_whatsapp, ...apiData } = data;
      const payload = {
        ...apiData,
        recipient_filter: needsFilter
          ? data.recipient_filter
          : isSpecificUsers
            ? { user_ids: data.recipient_filter?.user_ids || [] }
            : null,
      };

      if (isSpecificUsers && (!data.recipient_filter?.user_ids || data.recipient_filter.user_ids.length === 0)) {
        nassaqWarning(isRTL ? 'يرجى اختيار مستخدم واحد على الأقل' : 'Please select at least one user');
        setSubmitting(false);
        return;
      }

      const response = await api.post('/notifications/send', payload);
      
      if (response.data.success) {
        setResult(response.data);
        setSuccess(true);
        toast.success(t('notificationSent'));
      } else {
        nassaqError(response.data.error);
      }
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('errorSendingNotification')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setData({
      title_ar: '',
      title_en: '',
      message_ar: '',
      message_en: '',
      recipient_type: 'all_students',
      recipient_filter: null,
      notification_type: 'announcement',
      priority: 'normal',
      send_push: true,
      send_sms: false,
      send_email: false,
      send_whatsapp: false,
    });
    setSuccess(false);
    setResult(null);
  };

  const handleClose = () => { 
    handleReset(); 
    if (onOpenChange) onOpenChange(false);
    else if (onClose) onClose();
  };

  const getPriorityColor = (p) => {
    const colors = { low: 'bg-gray-100 text-gray-700', normal: 'bg-blue-100 text-blue-700', high: 'bg-amber-100 text-amber-700', urgent: 'bg-red-100 text-red-700' };
    return colors[p] || colors.normal;
  };

  const getTypeIcon = (t) => {
    const icons = { announcement: Megaphone, reminder: Calendar, alert: AlertTriangle, event: Calendar, emergency: AlertTriangle };
    return icons[t] || Bell;
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="send-notification-wizard">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 font-cairo text-xl">
            <div className="w-10 h-10 bg-pink-100 rounded-xl flex items-center justify-center">
              <Send className="h-5 w-5 text-pink-600" />
            </div>
            {isRTL ? 'إرسال إشعار' : 'Send Notification'}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-pink-600" />
          </div>
        ) : success && result ? (
          <div className="text-center space-y-6 py-8">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="h-10 w-10 text-green-600" />
            </div>
            <div>
              <h3 className="text-2xl font-bold font-cairo text-green-700">
                {t('notificationSent2')}
              </h3>
              <p className="text-lg mt-2 text-muted-foreground">
                {isRTL ? `تم إرسال الإشعار إلى ${result.recipient_count} مستلم` : `Sent to ${result.recipient_count} recipients`}
              </p>
            </div>
            <div className="flex justify-center gap-3">
              <Button variant="outline" onClick={handleClose}>{t('close')}</Button>
              <Button onClick={handleReset} className="bg-pink-600 hover:bg-pink-700">
                {t('sendAnother')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-6 py-4">
            {/* Recipient Type */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('recipients')} <span className="text-red-500">*</span></Label>
                <Select value={data.recipient_type} onValueChange={(val) => onChange('recipient_type', val)}>
                  <SelectTrigger data-testid="notif-recipient">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {options.recipientTypes.map((rt) => (
                      <SelectItem key={rt.code} value={rt.code}>{isRTL ? rt.name_ar : rt.name_en}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {needsFilter && (
                <div className="space-y-2">
                  <Label>
                    {data.recipient_type.includes('grade') ? (t('grade')) : (t('class'))}
                  </Label>
                  <Select 
                    value={data.recipient_filter?.grade_id || data.recipient_filter?.class_id || ''} 
                    onValueChange={(val) => onChange('recipient_filter', 
                      data.recipient_type.includes('grade') ? { grade_id: val } : { class_id: val }
                    )}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('select2')} />
                    </SelectTrigger>
                    <SelectContent>
                      {data.recipient_type.includes('grade') 
                        ? options.grades.map((g) => <SelectItem key={g.id} value={g.id}>{isRTL ? g.name_ar : g.name_en}</SelectItem>)
                        : options.classes.map((c) => <SelectItem key={c.class_id} value={c.class_id}>{c.name_ar}</SelectItem>)
                      }
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>

            {isSpecificUsers && (
              <div className="space-y-2">
                <Label>
                  {isRTL ? 'المستخدمون' : 'Users'} <span className="text-red-500">*</span>
                </Label>
                <UserMultiSelect
                  value={data.recipient_filter?.user_ids || []}
                  onChange={(ids) => onChange('recipient_filter', { user_ids: ids })}
                  placeholder={isRTL ? 'ابحث عن مستخدمين...' : 'Search for users...'}
                  dataTestId="notif-specific-users"
                />
              </div>
            )}

            {/* Notification Type & Priority */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t('type3')}</Label>
                <Select value={data.notification_type} onValueChange={(val) => onChange('notification_type', val)}>
                  <SelectTrigger data-testid="notif-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {options.notificationTypes.map((nt) => (
                      <SelectItem key={nt.code} value={nt.code}>{isRTL ? nt.name_ar : nt.name_en}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t('priority')}</Label>
                <Select value={data.priority} onValueChange={(val) => onChange('priority', val)}>
                  <SelectTrigger data-testid="notif-priority">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {options.priorities.map((p) => (
                      <SelectItem key={p.code} value={p.code}>{isRTL ? p.name_ar : p.name_en}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Title */}
            <div className="space-y-2">
              <Label>{t('titleArabic')} <span className="text-red-500">*</span></Label>
              <Input
                value={data.title_ar}
                onChange={(e) => onChange('title_ar', e.target.value)}
                placeholder={t('notificationTitle')}
                data-testid="notif-title-ar"
              />
            </div>

            <div className="space-y-2 hidden">
              <Label>{t('titleEnglish')}</Label>
              <Input
                value={data.title_en}
                onChange={(e) => onChange('title_en', e.target.value)}
                dir="ltr"
                data-testid="notif-title-en"
              />
            </div>

            {/* Message */}
            <div className="space-y-2">
              <Label>{t('messageArabic')} <span className="text-red-500">*</span></Label>
              <Textarea
                value={data.message_ar}
                onChange={(e) => onChange('message_ar', e.target.value)}
                placeholder={t('notificationContent')}
                rows={4}
                data-testid="notif-message-ar"
              />
            </div>

            <div className="space-y-2 hidden">
              <Label>{t('messageEnglish')}</Label>
              <Textarea
                value={data.message_en}
                onChange={(e) => onChange('message_en', e.target.value)}
                dir="ltr"
                rows={3}
                data-testid="notif-message-en"
              />
            </div>

            {/* Delivery Options */}
            <Card className="bg-muted/30">
              <CardContent className="p-4">
                <Label className="mb-3 block">{t('deliveryMethod')}</Label>
                <div className="flex flex-wrap gap-4">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="send_push"
                      checked={data.send_push}
                      onCheckedChange={(checked) => onChange('send_push', checked)}
                    />
                    <Label htmlFor="send_push" className="cursor-pointer">{t('push')}</Label>
                  </div>
                  <div className="flex items-center gap-2 hidden">
                    <Checkbox
                      id="send_sms"
                      checked={data.send_sms}
                      onCheckedChange={(checked) => onChange('send_sms', checked)}
                    />
                    <Label htmlFor="send_sms" className="cursor-pointer">{t('sms')}</Label>
                  </div>
                  <div className="flex items-center gap-2 hidden">
                    <Checkbox
                      id="send_email"
                      checked={data.send_email}
                      onCheckedChange={(checked) => onChange('send_email', checked)}
                    />
                    <Label htmlFor="send_email" className="cursor-pointer">{t('email5')}</Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="send_whatsapp"
                      checked={data.send_whatsapp}
                      onCheckedChange={(checked) => onChange('send_whatsapp', checked)}
                    />
                    <Label htmlFor="send_whatsapp" className="cursor-pointer">
                      {isRTL ? 'إرسال عبر الواتساب' : 'WhatsApp'}
                    </Label>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {!loading && !success && (
          <DialogFooter className="flex justify-between gap-3 mt-4">
            <Button variant="ghost" onClick={handleClose}>{t('cancel')}</Button>
            <Button 
              onClick={handleSubmit} 
              disabled={submitting || !data.title_ar || !data.message_ar}
              className="bg-pink-600 hover:bg-pink-700"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Send className="h-4 w-4 me-2" />}
              {t('sendNotification')}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default SendNotificationWizard;
