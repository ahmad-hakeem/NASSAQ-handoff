import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Avatar, AvatarFallback } from '../../components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Checkbox } from '../../components/ui/checkbox';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  MessageSquare, Send, Plus, Users, Loader2, RefreshCw,
  Bell, Mail, Phone, Clock, CheckCircle2, AlertCircle, Search,
  MessageCircle, Megaphone, UserCheck, ChevronLeft, ChevronRight,
  BookOpen, FileText, AlertTriangle, Inbox, History, Eye, EyeOff,
  GraduationCap, Building2, Filter
} from 'lucide-react';

const MESSAGE_TYPES = [
  { value: 'general', label: 'عام', labelEn: 'General', icon: MessageSquare, color: 'bg-blue-500' },
  { value: 'urgent', label: 'عاجل', labelEn: 'Urgent', icon: AlertCircle, color: 'bg-red-500' },
  { value: 'announcement', label: 'إعلان', labelEn: 'Announcement', icon: Megaphone, color: 'bg-purple-500' },
  { value: 'meeting', label: 'اجتماع', labelEn: 'Meeting', icon: UserCheck, color: 'bg-green-500' },
  { value: 'follow_up', label: 'متابعة طالب', labelEn: 'Student Follow-up', icon: GraduationCap, color: 'bg-amber-500' },
];

const TEMPLATES = [
  { id: 'homework', icon: BookOpen, gradient: 'from-blue-500 to-indigo-500', titleAr: 'تذكير بالواجب', titleEn: 'Homework Reminder', bodyAr: 'نود تذكيركم بضرورة متابعة أداء الواجبات المنزلية لابنكم/ابنتكم. يرجى التأكد من إنجازها في الوقت المحدد.', bodyEn: 'Reminder to follow up on your child\'s homework.' },
  { id: 'exam', icon: FileText, gradient: 'from-amber-500 to-orange-500', titleAr: 'إشعار اختبار', titleEn: 'Exam Notice', bodyAr: 'نود إعلامكم بأنه سيكون هناك اختبار قريباً. يرجى مساعدة الطالب في الاستعداد والمراجعة.', bodyEn: 'There will be an upcoming exam. Please help your child prepare.' },
  { id: 'meeting', icon: UserCheck, gradient: 'from-green-500 to-emerald-500', titleAr: 'دعوة لاجتماع', titleEn: 'Meeting Invitation', bodyAr: 'يسرنا دعوتكم لحضور اجتماع أولياء الأمور لمناقشة تقدم الطلاب الأكاديمي.', bodyEn: 'You are invited to attend a parent-teacher meeting.' },
  { id: 'behavior', icon: AlertTriangle, gradient: 'from-rose-500 to-red-500', titleAr: 'ملاحظة سلوكية', titleEn: 'Behavior Note', bodyAr: 'نود إطلاعكم على سلوك الطالب في المدرسة ونأمل التعاون لتحسين الوضع.', bodyEn: 'We would like to inform you about your child\'s behavior.' },
  { id: 'achievement', icon: CheckCircle2, gradient: 'from-emerald-500 to-teal-500', titleAr: 'إنجاز متميز', titleEn: 'Achievement Notice', bodyAr: 'يسعدنا إبلاغكم بتفوق ابنكم/ابنتكم في الأنشطة الأكاديمية.', bodyEn: 'We are pleased to inform you about your child\'s achievement.' },
  { id: 'absence', icon: AlertCircle, gradient: 'from-red-500 to-rose-500', titleAr: 'تنبيه غياب', titleEn: 'Absence Alert', bodyAr: 'نود إعلامكم بتسجيل غياب لابنكم/ابنتكم اليوم. يرجى التواصل معنا.', bodyEn: 'Your child was marked absent today. Please contact us.' },
];

export default function TeacherCommunicationPage() {
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [sentMessages, setSentMessages] = useState([]);
  const [receivedMessages, setReceivedMessages] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [activeTab, setActiveTab] = useState('compose');
  const [showComposeDialog, setShowComposeDialog] = useState(false);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [msgSearchQuery, setMsgSearchQuery] = useState('');
  const [recipientFilter, setRecipientFilter] = useState('all_parties');

  const { nassaqError } = useNassaqAlert();
  const [newMessage, setNewMessage] = useState({
    type: 'general', subject: '', body: '', recipients: 'all',
    selectedStudents: [], selectedParents: []
  });

  const teacherId = user?.teacher_id || user?.id;

  const fetchData = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const [classesRes, sentRes, receivedRes, notifRes] = await Promise.all([
        api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] })),
        api.get(`/messages?sender_id=${teacherId}`).catch(() => ({ data: [] })),
        api.get(`/messages?recipient_id=${teacherId}`).catch(() => ({ data: [] })),
        api.get(`/notifications?recipient_id=${teacherId}&limit=20`).catch(() => ({ data: [] })),
      ]);
      setClasses(classesRes.data || []);
      setSentMessages(sentRes.data || []);
      setReceivedMessages(receivedRes.data || []);
      setNotifications(Array.isArray(notifRes.data) ? notifRes.data : []);
      if (classesRes.data?.length > 0 && !selectedClass) setSelectedClass(classesRes.data[0].id);
    } catch (error) { console.error('Error:', error); }
    finally { setLoading(false); }
  }, [api, teacherId, selectedClass]);

  const fetchStudents = useCallback(async () => {
    if (!selectedClass) return;
    try {
      const res = await api.get(`/classes/${selectedClass}/students`);
      setStudents(res.data || []);
    } catch (error) { console.error('Error:', error); }
  }, [api, selectedClass]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { if (selectedClass) fetchStudents(); }, [selectedClass, fetchStudents]);

  const handleSendMessage = async () => {
    if (!newMessage.subject || !newMessage.body) { nassaqError(isRTL ? 'يرجى ملء جميع الحقول' : 'Please fill all fields'); return; }
    setSending(true);
    try {
      let recipientIds = [];
      if (newMessage.recipients === 'all') recipientIds = students.map(s => s.parent_id || s.id);
      else if (newMessage.recipients === 'selected') recipientIds = newMessage.selectedParents;
      await api.post('/messages', { sender_id: teacherId, sender_type: 'teacher', recipient_ids: recipientIds, type: newMessage.type, subject: newMessage.subject, body: newMessage.body, class_id: selectedClass });
      toast.success(isRTL ? 'تم إرسال الرسالة بنجاح' : 'Message sent successfully');
      setShowComposeDialog(false);
      setNewMessage({ type: 'general', subject: '', body: '', recipients: 'all', selectedStudents: [], selectedParents: [] });
      fetchData();
    } catch (error) { nassaqError(isRTL ? 'خطأ في إرسال الرسالة' : 'Error sending message'); }
    finally { setSending(false); }
  };

  const toggleStudentSelection = (studentId, parentId) => {
    setNewMessage(prev => {
      const isSelected = prev.selectedStudents.includes(studentId);
      return { ...prev, selectedStudents: isSelected ? prev.selectedStudents.filter(id => id !== studentId) : [...prev.selectedStudents, studentId], selectedParents: isSelected ? prev.selectedParents.filter(id => id !== parentId) : [...prev.selectedParents, parentId] };
    });
  };

  const filteredStudents = students.filter(s => s.full_name?.toLowerCase().includes(searchQuery.toLowerCase()));

  const applyTemplate = (template) => {
    setNewMessage({ ...newMessage, subject: isRTL ? template.titleAr : template.titleEn, body: isRTL ? template.bodyAr : template.bodyEn });
    setShowComposeDialog(true);
  };

  const filteredSentMessages = sentMessages.filter(m =>
    !msgSearchQuery || m.subject?.toLowerCase().includes(msgSearchQuery.toLowerCase()) || m.body?.toLowerCase().includes(msgSearchQuery.toLowerCase())
  );

  const filteredReceivedMessages = receivedMessages.filter(m =>
    !msgSearchQuery || m.subject?.toLowerCase().includes(msgSearchQuery.toLowerCase()) || m.body?.toLowerCase().includes(msgSearchQuery.toLowerCase())
  );

  const unreadInbox = receivedMessages.filter(m => !m.is_read).length;

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {isRTL ? 'مركز التواصل' : 'Communication Center'}
              </h1>
              <p className="text-sm text-muted-foreground">{isRTL ? 'إرسال واستقبال الرسائل والإشعارات' : 'Send and receive messages and notifications'}</p>
            </div>
            <div className="flex items-center gap-2">
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-full sm:w-[160px]"><SelectValue placeholder={isRTL ? 'الفصل' : 'Class'} /></SelectTrigger>
                <SelectContent>{classes.map(cls => (<SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>))}</SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></Button>
              <Button className="bg-brand-turquoise hover:bg-brand-turquoise/90" onClick={() => setShowComposeDialog(true)}>
                <Plus className="h-4 w-4 me-1" /><span className="hidden sm:inline">{isRTL ? 'رسالة جديدة' : 'New Message'}</span><span className="sm:hidden">{isRTL ? 'جديدة' : 'New'}</span>
              </Button>
            </div>
          </div>
        </div>

        <div className="p-4 max-w-[1400px] mx-auto space-y-5">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4 bg-muted/50">
              <TabsTrigger value="compose" className="gap-1.5"><Send className="h-3.5 w-3.5" />{isRTL ? 'إرسال سريع' : 'Quick Send'}</TabsTrigger>
              <TabsTrigger value="inbox" className="gap-1.5">
                <Inbox className="h-3.5 w-3.5" />{isRTL ? 'الوارد' : 'Inbox'}
                {unreadInbox > 0 && <Badge className="bg-red-500 text-white text-[9px] px-1.5 h-4 border-0">{unreadInbox}</Badge>}
              </TabsTrigger>
              <TabsTrigger value="sent" className="gap-1.5">
                <History className="h-3.5 w-3.5" />{isRTL ? 'المرسلة' : 'Sent'}
                {sentMessages.length > 0 && <Badge variant="secondary" className="text-[9px] px-1.5 h-4 border-0">{sentMessages.length}</Badge>}
              </TabsTrigger>
              <TabsTrigger value="notifications" className="gap-1.5">
                <Bell className="h-3.5 w-3.5" />{isRTL ? 'الإشعارات' : 'Notifications'}
                {notifications.length > 0 && <Badge className="bg-brand-turquoise text-white text-[9px] px-1.5 h-4 border-0">{notifications.length}</Badge>}
              </TabsTrigger>
              <TabsTrigger value="contacts" className="gap-1.5"><Users className="h-3.5 w-3.5" />{isRTL ? 'جهات الاتصال' : 'Contacts'}</TabsTrigger>
            </TabsList>

            <TabsContent value="compose">
              {loading ? (<div className="flex items-center justify-center py-20"><Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" /></div>) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                    {TEMPLATES.map(template => {
                      const TIcon = template.icon;
                      return (<button key={template.id} onClick={() => applyTemplate(template)} className="group p-4 rounded-xl border-2 border-border/50 hover:border-brand-turquoise/40 bg-card hover:shadow-lg hover:shadow-brand-turquoise/5 transition-all duration-300 text-center">
                        <div className={`w-11 h-11 mx-auto mb-2.5 rounded-xl bg-gradient-to-br ${template.gradient} flex items-center justify-center shadow-sm group-hover:scale-110 transition-transform`}><TIcon className="h-5 w-5 text-white" /></div>
                        <p className="text-sm font-cairo font-medium leading-tight">{isRTL ? template.titleAr : template.titleEn}</p>
                      </button>);
                    })}
                  </div>
                  <div className="grid lg:grid-cols-3 gap-4">
                    <div className="lg:col-span-2">
                      <Card>
                        <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><MessageSquare className="h-4 w-4 text-brand-turquoise" />{isRTL ? 'آخر الرسائل المرسلة' : 'Recent Sent Messages'}</CardTitle></CardHeader>
                        <CardContent>
                          {sentMessages.length === 0 ? (<div className="text-center py-8"><MessageSquare className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" /><p className="text-sm text-muted-foreground font-cairo">{isRTL ? 'لم ترسل أي رسائل بعد' : 'No messages sent yet'}</p></div>) : (
                            <div className="space-y-2">{sentMessages.slice(0, 5).map((message, idx) => {
                              const typeConfig = MESSAGE_TYPES.find(t => t.value === message.type);
                              return (<div key={message.id || idx} className="p-3 rounded-lg border hover:bg-muted/30 transition-all">
                                <div className="flex items-start justify-between mb-1"><div className="flex items-center gap-2"><Badge className={`text-[10px] border-0 ${message.type === 'urgent' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'}`}>{typeConfig?.[isRTL ? 'label' : 'labelEn'] || message.type}</Badge><span className="font-medium text-sm">{message.subject}</span></div><span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0"><Clock className="h-3 w-3" />{message.created_at ? new Date(message.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US') : ''}</span></div>
                                <p className="text-xs text-muted-foreground line-clamp-1 ps-1">{message.body}</p>
                              </div>);
                            })}</div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                    <div className="space-y-3">
                      <Card className="bg-gradient-to-br from-brand-turquoise/5 to-brand-navy/5 border-brand-turquoise/20"><CardContent className="p-4 text-center"><Send className="h-7 w-7 mx-auto mb-2 text-brand-turquoise" /><div className="text-2xl font-bold font-cairo text-brand-navy dark:text-brand-turquoise">{sentMessages.length}</div><div className="text-xs text-muted-foreground">{isRTL ? 'رسالة مرسلة' : 'Sent'}</div></CardContent></Card>
                      <Card><CardContent className="p-4 text-center"><Inbox className="h-7 w-7 mx-auto mb-2 text-blue-600" /><div className="text-2xl font-bold font-cairo text-blue-600">{receivedMessages.length}</div><div className="text-xs text-muted-foreground">{isRTL ? 'رسالة واردة' : 'Received'}</div></CardContent></Card>
                      <Card><CardContent className="p-4 text-center"><Users className="h-7 w-7 mx-auto mb-2 text-green-600" /><div className="text-2xl font-bold font-cairo text-green-600">{students.length}</div><div className="text-xs text-muted-foreground">{isRTL ? 'ولي أمر' : 'Parents'}</div></CardContent></Card>
                    </div>
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="inbox">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <CardTitle className="text-base font-cairo flex items-center gap-2"><Inbox className="h-4 w-4 text-blue-500" />{isRTL ? 'الرسائل الواردة' : 'Inbox'}{unreadInbox > 0 && <Badge className="bg-red-500 text-white border-0">{unreadInbox} {isRTL ? 'جديدة' : 'new'}</Badge>}</CardTitle>
                    <div className="relative"><Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder={isRTL ? 'بحث في الرسائل...' : 'Search messages...'} value={msgSearchQuery} onChange={(e) => setMsgSearchQuery(e.target.value)} className="ps-9 w-full sm:w-[200px] h-9" /></div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredReceivedMessages.length === 0 ? (<div className="flex flex-col items-center py-10 text-center"><Inbox className="h-12 w-12 mb-3 text-muted-foreground/30" /><p className="text-muted-foreground font-cairo">{isRTL ? 'لا توجد رسائل واردة' : 'No received messages'}</p></div>) : (
                    <div className="space-y-2.5">{filteredReceivedMessages.map((message, idx) => {
                      const typeConfig = MESSAGE_TYPES.find(t => t.value === message.type);
                      const MIcon = typeConfig?.icon || MessageSquare;
                      return (<div key={message.id || idx} className={`p-4 rounded-xl border transition-all ${!message.is_read ? 'bg-brand-turquoise/5 border-brand-turquoise/20 hover:shadow-md' : 'hover:bg-muted/30'}`}>
                        <div className="flex items-start justify-between mb-2"><div className="flex items-center gap-2.5"><div className={`w-8 h-8 rounded-lg ${typeConfig?.color || 'bg-blue-500'} flex items-center justify-center shrink-0`}><MIcon className="h-4 w-4 text-white" /></div><div><div className="flex items-center gap-2"><span className="font-medium text-sm">{message.subject}</span>{!message.is_read && <span className="w-2 h-2 rounded-full bg-brand-turquoise" />}</div><div className="flex items-center gap-2 mt-0.5"><Badge variant="secondary" className="text-[10px]">{typeConfig?.[isRTL ? 'label' : 'labelEn'] || message.type}</Badge>{message.sender_name && <span className="text-[10px] text-muted-foreground">{isRTL ? 'من' : 'From'}: {message.sender_name}</span>}</div></div></div><span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0"><Clock className="h-3 w-3" />{message.created_at ? new Date(message.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium' }) : ''}</span></div>
                        <p className="text-xs text-muted-foreground line-clamp-2 ps-[42px]">{message.body}</p>
                      </div>);
                    })}</div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="sent">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <CardTitle className="text-base font-cairo flex items-center gap-2"><History className="h-4 w-4 text-brand-turquoise" />{isRTL ? 'سجل الرسائل المرسلة' : 'Sent Message History'}</CardTitle>
                    <div className="relative"><Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder={isRTL ? 'بحث...' : 'Search...'} value={msgSearchQuery} onChange={(e) => setMsgSearchQuery(e.target.value)} className="ps-9 w-full sm:w-[200px] h-9" /></div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredSentMessages.length === 0 ? (<div className="flex flex-col items-center py-10 text-center"><MessageSquare className="h-12 w-12 mb-3 text-muted-foreground/30" /><p className="text-muted-foreground font-cairo">{isRTL ? 'لا توجد رسائل مرسلة' : 'No sent messages'}</p></div>) : (
                    <div className="space-y-2.5">{filteredSentMessages.map((message, idx) => {
                      const typeConfig = MESSAGE_TYPES.find(t => t.value === message.type);
                      const MIcon = typeConfig?.icon || MessageSquare;
                      return (<div key={message.id || idx} className="p-4 rounded-xl border hover:border-brand-turquoise/30 hover:shadow-sm transition-all">
                        <div className="flex items-start justify-between mb-2"><div className="flex items-center gap-2.5"><div className={`w-8 h-8 rounded-lg ${typeConfig?.color || 'bg-blue-500'} flex items-center justify-center shrink-0`}><MIcon className="h-4 w-4 text-white" /></div><div><span className="font-medium text-sm">{message.subject}</span><div className="flex items-center gap-2 mt-0.5"><Badge variant="secondary" className="text-[10px]">{typeConfig?.[isRTL ? 'label' : 'labelEn'] || message.type}</Badge><span className="text-[10px] text-muted-foreground flex items-center gap-1"><Users className="h-2.5 w-2.5" />{message.recipient_ids?.length || 0} {isRTL ? 'مستلم' : 'recipients'}</span></div></div></div><span className="text-[10px] text-muted-foreground flex items-center gap-1 shrink-0"><Clock className="h-3 w-3" />{message.created_at ? new Date(message.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium' }) : ''}</span></div>
                        <p className="text-xs text-muted-foreground line-clamp-2 ps-[42px]">{message.body}</p>
                      </div>);
                    })}</div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="notifications">
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><Bell className="h-4 w-4 text-brand-turquoise" />{isRTL ? 'آخر الإشعارات' : 'Recent Notifications'}</CardTitle></CardHeader>
                <CardContent>
                  {notifications.length === 0 ? (<div className="flex flex-col items-center py-10 text-center"><Inbox className="h-12 w-12 mb-3 text-muted-foreground/30" /><p className="text-muted-foreground font-cairo">{isRTL ? 'لا توجد إشعارات' : 'No notifications'}</p><p className="text-xs text-muted-foreground/60 mt-1">{isRTL ? 'ستظهر الإشعارات هنا عندما تصلك' : 'Notifications will appear here'}</p></div>) : (
                    <div className="space-y-2">{notifications.map((notif, idx) => (
                      <div key={notif.id || idx} className={`p-3.5 rounded-xl border transition-all ${(notif.is_read || notif.read_status) ? 'bg-card' : 'bg-brand-turquoise/5 border-brand-turquoise/20'}`}>
                        <div className="flex items-start gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${notif.priority === 'high' ? 'bg-red-100 dark:bg-red-900/40 text-red-600' : 'bg-brand-turquoise/10 text-brand-turquoise'}`}>{notif.priority === 'high' ? <AlertCircle className="h-4 w-4" /> : <Bell className="h-4 w-4" />}</div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5"><p className="font-medium text-sm truncate">{notif.title}</p>{!(notif.is_read || notif.read_status) && <span className="w-2 h-2 rounded-full bg-brand-turquoise shrink-0" />}</div>
                            <p className="text-xs text-muted-foreground line-clamp-2">{notif.message}</p>
                            <span className="text-[10px] text-muted-foreground/60 flex items-center gap-1 mt-1.5"><Clock className="h-2.5 w-2.5" />{notif.created_at ? new Date(notif.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' }) : ''}</span>
                          </div>
                        </div>
                      </div>
                    ))}</div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="contacts">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <CardTitle className="text-base font-cairo flex items-center gap-2"><Users className="h-4 w-4 text-brand-turquoise" />{isRTL ? 'جهات الاتصال' : 'Contacts'}<Badge variant="secondary" className="font-cairo">{filteredStudents.length}</Badge></CardTitle>
                    <div className="relative"><Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" /><Input placeholder={isRTL ? 'بحث...' : 'Search...'} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="ps-9 w-full sm:w-[200px] h-9" /></div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredStudents.length === 0 ? (<div className="text-center py-10 text-muted-foreground font-cairo">{isRTL ? 'لا يوجد جهات اتصال' : 'No contacts found'}</div>) : (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">{filteredStudents.map(student => (
                      <div key={student.id} className="p-3.5 rounded-xl border hover:border-brand-turquoise/30 hover:shadow-sm transition-all">
                        <div className="flex items-center gap-3 mb-2.5"><Avatar className="h-9 w-9"><AvatarFallback className={`text-xs font-bold ${student.gender === 'male' ? 'bg-sky-100 text-sky-600' : 'bg-pink-100 text-pink-600'}`}>{student.full_name?.charAt(0) || '?'}</AvatarFallback></Avatar><div className="flex-1 min-w-0"><p className="font-medium text-sm truncate">{student.full_name}</p><p className="text-[10px] text-muted-foreground">{isRTL ? 'ولي الأمر' : 'Parent'}: {student.parent_name || '-'}</p></div></div>
                        {student.parent_phone && (<div className="flex items-center gap-2 text-xs text-muted-foreground mb-2"><Phone className="h-3 w-3" /><span dir="ltr">{student.parent_phone}</span></div>)}
                        <Button variant="outline" size="sm" className="w-full text-xs h-8 hover:border-brand-turquoise hover:text-brand-turquoise" onClick={() => { setNewMessage({ ...newMessage, recipients: 'selected', selectedStudents: [student.id], selectedParents: [student.parent_id] }); setShowComposeDialog(true); }}><Send className="h-3 w-3 me-1" />{isRTL ? 'إرسال رسالة' : 'Send Message'}</Button>
                      </div>
                    ))}</div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        <Dialog open={showComposeDialog} onOpenChange={setShowComposeDialog}>
          <DialogContent className="w-[95vw] max-w-lg">
            <DialogHeader><DialogTitle className="font-cairo flex items-center gap-2"><div className="w-8 h-8 rounded-lg bg-brand-turquoise flex items-center justify-center"><Send className="h-4 w-4 text-white" /></div>{isRTL ? 'إرسال رسالة' : 'Send Message'}</DialogTitle></DialogHeader>
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5"><Label className="text-xs">{isRTL ? 'نوع الرسالة' : 'Type'}</Label><Select value={newMessage.type} onValueChange={(v) => setNewMessage({...newMessage, type: v})}><SelectTrigger className="h-9"><SelectValue /></SelectTrigger><SelectContent>{MESSAGE_TYPES.map(t => (<SelectItem key={t.value} value={t.value}>{isRTL ? t.label : t.labelEn}</SelectItem>))}</SelectContent></Select></div>
                <div className="space-y-1.5"><Label className="text-xs">{isRTL ? 'المستلمين' : 'Recipients'}</Label><Select value={newMessage.recipients} onValueChange={(v) => setNewMessage({...newMessage, recipients: v})}><SelectTrigger className="h-9"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">{isRTL ? 'جميع أولياء الأمور' : 'All Parents'}</SelectItem><SelectItem value="selected">{isRTL ? 'محدد' : 'Selected'}</SelectItem></SelectContent></Select></div>
              </div>
              {newMessage.recipients === 'selected' && (<div className="space-y-1.5"><Label className="text-xs">{isRTL ? 'اختر الطلاب' : 'Select Students'} ({newMessage.selectedStudents.length})</Label><div className="max-h-28 overflow-y-auto border rounded-lg p-2 space-y-1">{students.map(student => (<div key={student.id} className="flex items-center gap-2 p-1 rounded hover:bg-muted/50"><Checkbox checked={newMessage.selectedStudents.includes(student.id)} onCheckedChange={() => toggleStudentSelection(student.id, student.parent_id)} /><span className="text-sm">{student.full_name}</span></div>))}</div></div>)}
              <div className="space-y-1.5"><Label className="text-xs">{isRTL ? 'عنوان الرسالة' : 'Subject'} *</Label><Input value={newMessage.subject} onChange={(e) => setNewMessage({...newMessage, subject: e.target.value})} placeholder={isRTL ? 'عنوان الرسالة...' : 'Message subject...'} className="h-9" /></div>
              <div className="space-y-1.5"><Label className="text-xs">{isRTL ? 'نص الرسالة' : 'Message'} *</Label><Textarea value={newMessage.body} onChange={(e) => setNewMessage({...newMessage, body: e.target.value})} placeholder={isRTL ? 'اكتب رسالتك هنا...' : 'Write your message...'} rows={4} /></div>
              {newMessage.recipients === 'all' && (<div className="p-2.5 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200/60"><p className="text-[11px] text-blue-600 dark:text-blue-400 flex items-center gap-1.5"><Users className="h-3 w-3 shrink-0" />{isRTL ? `سيتم إرسال الرسالة إلى ${students.length} ولي أمر` : `Message will be sent to ${students.length} parents`}</p></div>)}
            </div>
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setShowComposeDialog(false)} className="h-9">{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button className="bg-brand-turquoise hover:bg-brand-turquoise/90 h-9" onClick={handleSendMessage} disabled={sending || !newMessage.subject || !newMessage.body}>
                {sending && <Loader2 className="h-4 w-4 animate-spin me-2" />}<Send className="h-4 w-4 me-1" />{isRTL ? 'إرسال' : 'Send'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
