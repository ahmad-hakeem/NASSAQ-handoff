import React, { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
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
import { Checkbox } from '../../components/ui/checkbox';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  MessageSquare, Send, Users, Loader2, RefreshCw,
  Bell, Phone, Clock, CheckCircle2, AlertCircle, Search,
  Megaphone, UserCheck, ChevronLeft,
  BookOpen, FileText, AlertTriangle, Eye,
  GraduationCap, Building2, Shield, Star,
  ScrollText, Presentation, ArrowLeft, ArrowRight,
  UserCog, HeartHandshake, Sparkles, Info
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const TEMPLATES = [
  { id: 'homework', icon: BookOpen, color: 'bg-blue-500', titleKey: 'homeworkReminder', bodyKey: 'homeworkReminderBody' },
  { id: 'exam', icon: FileText, color: 'bg-amber-500', titleKey: 'examNotice', bodyKey: 'examNoticeBody' },
  { id: 'meeting', icon: UserCheck, color: 'bg-green-500', titleKey: 'meetingInvitation', bodyKey: 'meetingInvitationBody' },
  { id: 'behavior', icon: AlertTriangle, color: 'bg-rose-500', titleKey: 'behaviorNote', bodyKey: 'behaviorNoteBody' },
  { id: 'achievement', icon: CheckCircle2, color: 'bg-emerald-500', titleKey: 'achievementNotice', bodyKey: 'achievementNoticeBody' },
  { id: 'absence', icon: AlertCircle, color: 'bg-red-500', titleKey: 'absenceAlert', bodyKey: 'absenceAlertBody' },
];

// Recipient categories per spec: Parents / Administration / Staff.
// Direct student selection is reachable via Administration → Student Guidance.
const RECIPIENT_CATEGORIES = [
  { id: 'parents', icon: Users, color: 'bg-blue-500', i18nKey: 'parentsCategory' },
  { id: 'admin', icon: Building2, color: 'bg-brand-navy', i18nKey: 'adminCategory' },
  { id: 'staff', icon: Shield, color: 'bg-brand-purple', i18nKey: 'schoolStaffCategory' },
];

const STAFF_ROLES = [
  { id: 'vice_principal', icon: UserCog, i18nKey: 'vicePrincipal' },
  { id: 'counselor', icon: HeartHandshake, i18nKey: 'studentCounselor' },
  { id: 'activity_leader', icon: Star, i18nKey: 'activityLeader' },
  { id: 'gifted_coordinator', icon: Sparkles, i18nKey: 'giftedCoordinator' },
];

export default function TeacherCommunicationPage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [schoolNotifications, setSchoolNotifications] = useState([]);
  const [systemAlerts, setSystemAlerts] = useState([]);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const [activeView, setActiveView] = useState('sections');
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedRecipients, setSelectedRecipients] = useState([]);
  const [parentMode, setParentMode] = useState(null);
  const [messageBody, setMessageBody] = useState('');
  const [messageSubject, setMessageSubject] = useState('');

  const [schoolNotifFilter, setSchoolNotifFilter] = useState('all');
  const [guidanceStudentIds, setGuidanceStudentIds] = useState([]);

  // Sync `?tab=bulletin|workshop` from sidebar deep links into the right view + filter
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tab = params.get('tab');
    if (tab === 'bulletin') {
      setActiveView('school-notifications');
      setSchoolNotifFilter('circulars');
    } else if (tab === 'workshop') {
      setActiveView('school-notifications');
      setSchoolNotifFilter('workshops');
    }
  }, [location.search]);

  const { nassaqError } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  const fetchData = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const [classesRes, notifRes] = await Promise.all([
        api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] })),
        api.get(`/notifications?limit=50`).catch(() => ({ data: [] })),
      ]);
      // Note: backend GET /notifications enforces auth-scoped filtering
      // (recipient_id=current_user OR recipient_role=current_user.role)
      setClasses(classesRes.data || []);

      const allNotifs = Array.isArray(notifRes.data) ? notifRes.data : [];
      setNotifications(allNotifs);

      const school = allNotifs.filter(n =>
        n.notification_type === 'announcement' ||
        n.notification_type === 'schedule'
      );
      setSchoolNotifications(school);

      const system = allNotifs.filter(n =>
        n.notification_type === 'system'
      );
      setSystemAlerts(system);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId]);

  const fetchStudents = useCallback(async () => {
    if (!selectedClass) return;
    try {
      const res = await api.get(`/classes/${selectedClass}/students`);
      setStudents(res.data || []);
    } catch (error) {
      console.error('Error:', error);
    }
  }, [api, selectedClass]);

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { if (selectedClass) fetchStudents(); }, [selectedClass, fetchStudents]);

  const handleSendMessage = async () => {
    if (!messageSubject || !messageBody) {
      nassaqError(t('pleaseFillAllFields'));
      return;
    }
    if (selectedRecipients.length === 0) {
      nassaqError(t('noRecipientsSelected'));
      return;
    }
    setSending(true);
    try {
      const isRoleBasedRecipient = (id) =>
        ['vice_principal', 'counselor', 'activity_leader', 'gifted_coordinator', 'admin_general',
         'school_sub_admin', 'school_principal', 'school_admin'].includes(id);

      const roleRecipients = selectedRecipients.filter(isRoleBasedRecipient);
      const userRecipients = selectedRecipients.filter(id => !isRoleBasedRecipient(id));

      if (roleRecipients.length > 0) {
        const roleMap = {
          'vice_principal': 'school_sub_admin',
          'counselor': 'school_sub_admin',
          'activity_leader': 'school_sub_admin',
          'gifted_coordinator': 'school_sub_admin',
          'admin_general': 'school_principal',
        };
        const roles = [...new Set(roleRecipients.map(r => roleMap[r] || r))];
        for (const role of roles) {
          const payload = {
            title: messageSubject,
            message: messageBody,
            notification_type: 'communication',
            priority: 'medium',
            recipient_role: role,
          };
          if (guidanceStudentIds.length > 0) {
            payload.related_entity = 'student';
            payload.related_entity_id = guidanceStudentIds.join(',');
          }
          await api.post('/notifications', payload);
        }
      }

      for (const recipientId of userRecipients) {
        await api.post('/notifications', {
          title: messageSubject,
          message: messageBody,
          notification_type: 'communication',
          priority: 'medium',
          recipient_id: recipientId,
        });
      }

      toast.success(t('messageSentSuccessfully'));
      resetFlow();
      fetchData();
    } catch (error) {
      nassaqError(t('errorSendingMessage'));
    } finally {
      setSending(false);
    }
  };

  const resetFlow = () => {
    setActiveView('sections');
    setSelectedTemplate(null);
    setSelectedCategory(null);
    setSelectedClass('');
    setSelectedRecipients([]);
    setParentMode(null);
    setMessageBody('');
    setMessageSubject('');
    setGuidanceStudentIds([]);
  };

  const applyTemplate = (template) => {
    setSelectedTemplate(template);
    setMessageSubject(t(template.titleKey));
    setMessageBody(t(template.bodyKey));
    setActiveView('recipients');
  };

  const handleSelectCategory = (catId) => {
    setSelectedCategory(catId);
    setSelectedRecipients([]);
    setGuidanceStudentIds([]);
    if (catId === 'parents') {
      setActiveView('parent-mode');
    } else if (catId === 'students') {
      setActiveView('student-select');
    } else if (catId === 'staff') {
      setActiveView('staff-select');
    } else if (catId === 'admin') {
      setActiveView('admin-select');
    }
  };

  const handleParentModeSelect = (mode) => {
    setParentMode(mode);
    if (mode === 'all') {
      const allParentIds = students.filter(s => s.parent_id).map(s => s.parent_id);
      setSelectedRecipients([...new Set(allParentIds)]);
      setActiveView('preview');
    } else {
      setActiveView('parent-individual');
    }
  };

  const toggleRecipient = (id) => {
    setSelectedRecipients(prev =>
      prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]
    );
  };

  const handleSelectAllStudents = () => {
    const allIds = filteredStudents.map(s => s.id);
    const allSelected = allIds.every(id => selectedRecipients.includes(id));
    if (allSelected) {
      setSelectedRecipients(prev => prev.filter(id => !allIds.includes(id)));
    } else {
      setSelectedRecipients(prev => [...new Set([...prev, ...allIds])]);
    }
  };

  const handleStaffSelect = (roleId) => {
    setSelectedRecipients([roleId]);
    setActiveView('preview');
  };

  const handleAdminSelect = (type) => {
    if (type === 'guidance') {
      setSelectedRecipients(['counselor']);
      setActiveView('guidance-student-context');
    } else {
      setSelectedRecipients(['admin_general']);
      setActiveView('preview');
    }
  };

  const goToPreview = () => {
    if (selectedRecipients.length === 0) {
      nassaqError(t('noRecipientsSelected'));
      return;
    }
    setActiveView('preview');
  };

  const markNotificationRead = async (notifId) => {
    try {
      await api.put(`/notifications/${notifId}/read`);
      setNotifications(prev => prev.map(n => n.id === notifId ? { ...n, read_status: true } : n));
      setSchoolNotifications(prev => prev.map(n => n.id === notifId ? { ...n, read_status: true } : n));
      setSystemAlerts(prev => prev.map(n => n.id === notifId ? { ...n, read_status: true } : n));
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const filteredStudents = students.filter(s =>
    s.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredSchoolNotifs = schoolNotifFilter === 'all'
    ? schoolNotifications
    : schoolNotifications.filter(n => {
        if (schoolNotifFilter === 'circulars') return n.notification_type === 'announcement';
        if (schoolNotifFilter === 'workshops') return n.notification_type === 'schedule';
        return true;
      });

  const unreadCount = notifications.filter(n => !n.read_status && !n.is_read).length;
  const BackIcon = isRTL ? ChevronLeft : ArrowLeft;

  const renderSections = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          onClick={() => setActiveView('communication-hub')}
          className="group text-start"
        >
          <Card className="h-full border-2 border-transparent hover:border-brand-turquoise/40 hover:shadow-md transition-shadow duration-200">
            <CardContent className="p-6">
              <div className="w-12 h-12 rounded-xl bg-brand-turquoise/10 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform duration-200">
                <MessageSquare className="h-6 w-6 text-brand-turquoise" />
              </div>
              <h3 className="text-lg font-bold font-cairo text-brand-navy dark:text-white mb-1">
                {t('communicationCenterSection')}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t('communicationCenterSectionDesc')}
              </p>
            </CardContent>
          </Card>
        </button>

        <button
          onClick={() => setActiveView('school-notifications')}
          className="group text-start"
        >
          <Card className="h-full border-2 border-transparent hover:border-brand-navy/40 hover:shadow-md transition-shadow duration-200">
            <CardContent className="p-6">
              <div className="w-12 h-12 rounded-xl bg-brand-navy/10 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform duration-200">
                <Megaphone className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
              </div>
              <h3 className="text-lg font-bold font-cairo text-brand-navy dark:text-white mb-1">
                {t('schoolNotifications')}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t('schoolNotificationsDesc')}
              </p>
              {schoolNotifications.filter(n => !n.read_status).length > 0 && (
                <Badge className="mt-2 bg-red-500 text-white border-0">
                  {schoolNotifications.filter(n => !n.read_status).length} {t('new3')}
                </Badge>
              )}
            </CardContent>
          </Card>
        </button>

        <button
          onClick={() => setActiveView('system-alerts')}
          className="group text-start"
        >
          <Card className="h-full border-2 border-transparent hover:border-brand-purple/40 hover:shadow-md transition-shadow duration-200">
            <CardContent className="p-6">
              <div className="w-12 h-12 rounded-xl bg-brand-purple/10 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform duration-200">
                <Bell className="h-6 w-6 text-brand-purple" />
              </div>
              <h3 className="text-lg font-bold font-cairo text-brand-navy dark:text-white mb-1">
                {t('systemAlerts')}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t('systemAlertsDesc')}
              </p>
              {systemAlerts.filter(n => !n.read_status).length > 0 && (
                <Badge className="mt-2 bg-brand-purple text-white border-0">
                  {systemAlerts.filter(n => !n.read_status).length} {t('new3')}
                </Badge>
              )}
            </CardContent>
          </Card>
        </button>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-cairo flex items-center gap-2">
            <Bell className="h-4 w-4 text-brand-turquoise" />
            {t('recentNotifications2')}
            {unreadCount > 0 && (
              <Badge className="bg-red-500 text-white border-0 text-[10px]">{unreadCount}</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center py-10 text-center">
              <Bell className="h-10 w-10 mb-3 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground font-cairo">{t('noNotifications2')}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {notifications.slice(0, 5).map((notif) => (
                <NotificationCard
                  key={notif.id}
                  notif={notif}
                  isRTL={isRTL}
                  onRead={markNotificationRead}
                  t={t}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

  const renderStepIndicator = (currentStep) => {
    const steps = [
      { n: 1, label: t('chooseTemplate') },
      { n: 2, label: t('selectRecipients') },
      { n: 3, label: t('messagePreview') },
    ];
    return (
      <div className="flex items-center gap-2 flex-wrap">
        {steps.map((s, idx) => {
          const isActive = s.n === currentStep;
          const isDone = s.n < currentStep;
          return (
            <React.Fragment key={s.n}>
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
                isActive
                  ? 'bg-brand-turquoise/10 border-brand-turquoise text-brand-navy dark:text-white'
                  : isDone
                  ? 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-300 text-emerald-700 dark:text-emerald-300'
                  : 'bg-muted/40 border-border/50 text-muted-foreground'
              }`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  isActive ? 'bg-brand-turquoise text-white' : isDone ? 'bg-emerald-500 text-white' : 'bg-muted text-muted-foreground'
                }`}>
                  {isDone ? '✓' : s.n}
                </span>
                <span className="text-xs font-cairo font-medium">{s.label}</span>
              </div>
              {idx < steps.length - 1 && (
                <span className="h-px w-4 bg-border/70" aria-hidden="true" />
              )}
            </React.Fragment>
          );
        })}
      </div>
    );
  };

  const renderCommunicationHub = () => (
    <div className="space-y-6">
      <button
        onClick={() => setActiveView('sections')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToSections')}
      </button>

      <div className="flex items-start gap-4 flex-wrap">
        <div className="w-14 h-14 rounded-2xl bg-brand-turquoise/10 flex items-center justify-center shrink-0">
          <MessageSquare className="h-7 w-7 text-brand-turquoise" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
            {t('communicationCenterSection')}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t('communicationCenterSectionDesc')}
          </p>
        </div>
      </div>

      <Card className="border-2 border-brand-turquoise/30 bg-gradient-to-br from-brand-turquoise/5 to-transparent">
        <CardContent className="p-6 flex items-center justify-between flex-wrap gap-4">
          <div className="flex-1 min-w-[220px]">
            <h3 className="text-lg font-bold font-cairo text-brand-navy dark:text-white mb-1">
              {t('sendNotificationBtn')}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t('chooseTemplate')} → {t('selectRecipients')}
            </p>
          </div>
          <Button
            size="lg"
            className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white font-cairo px-6"
            onClick={() => {
              setSelectedTemplate(null);
              setSelectedCategory(null);
              setSelectedRecipients([]);
              setParentMode(null);
              setSelectedClass('');
              setMessageSubject('');
              setMessageBody('');
              setGuidanceStudentIds([]);
              setActiveView('templates');
            }}
          >
            <Send className="h-5 w-5 me-2" />
            {t('sendNotificationBtn')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const renderTemplates = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('communication-hub')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToSections')}
      </button>

      {renderStepIndicator(1)}

      <div>
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
          {t('chooseTemplate')}
        </h2>
        <p className="text-sm text-muted-foreground mb-4">{t('communicationCenterSectionDesc')}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {TEMPLATES.map(template => {
          const TIcon = template.icon;
          return (
            <button
              key={template.id}
              onClick={() => applyTemplate(template)}
              className="group p-4 rounded-xl border-2 border-border/50 hover:border-brand-turquoise/40 bg-card hover:shadow-md transition-shadow duration-200 text-center"
            >
              <div className={`w-11 h-11 mx-auto mb-2.5 rounded-xl ${template.color} flex items-center justify-center group-hover:scale-110 transition-transform duration-200`}>
                <TIcon className="h-5 w-5 text-white" />
              </div>
              <p className="text-sm font-cairo font-medium leading-tight">
                {t(template.titleKey)}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderRecipients = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('templates')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToTemplates')}
      </button>

      {renderStepIndicator(2)}

      <div>
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
          {t('selectRecipients')}
        </h2>
        <p className="text-sm text-muted-foreground mb-4">{t('recipientCategories')}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {RECIPIENT_CATEGORIES.map(cat => {
          const CIcon = cat.icon;
          return (
            <button
              key={cat.id}
              onClick={() => handleSelectCategory(cat.id)}
              className="group p-5 rounded-xl border-2 border-border/50 hover:border-brand-turquoise/40 bg-card hover:shadow-md transition-shadow duration-200 text-center"
            >
              <div className={`w-12 h-12 mx-auto mb-3 rounded-xl ${cat.color} flex items-center justify-center group-hover:scale-110 transition-transform duration-200`}>
                <CIcon className="h-6 w-6 text-white" />
              </div>
              <p className="text-sm font-cairo font-semibold">{t(cat.i18nKey)}</p>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderParentMode = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('recipients')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      <div>
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
          {t('parentsCategory')}
        </h2>
      </div>

      <div className="mb-4">
        <Label className="text-sm font-medium mb-2 block">{t('selectClass')}</Label>
        <Select value={selectedClass} onValueChange={setSelectedClass}>
          <SelectTrigger className="w-full sm:w-[240px]">
            <SelectValue placeholder={t('selectClass')} />
          </SelectTrigger>
          <SelectContent>
            {classes.map(cls => (
              <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button
          onClick={() => handleParentModeSelect('individual')}
          className="p-5 rounded-xl border-2 border-border/50 hover:border-blue-400/40 bg-card hover:shadow-md transition-shadow duration-200 text-start"
        >
          <Users className="h-8 w-8 text-blue-500 mb-2" />
          <p className="font-cairo font-semibold text-sm">{t('individualParent')}</p>
          <p className="text-xs text-muted-foreground mt-1">{t('selectOneOrMoreStudents')}</p>
        </button>

        <button
          onClick={() => handleParentModeSelect('all')}
          className="p-5 rounded-xl border-2 border-border/50 hover:border-green-400/40 bg-card hover:shadow-md transition-shadow duration-200 text-start"
          disabled={!selectedClass}
        >
          <Megaphone className="h-8 w-8 text-green-500 mb-2" />
          <p className="font-cairo font-semibold text-sm">{t('allParentsInClass')}</p>
          <p className="text-xs text-muted-foreground mt-1">
            {selectedClass ? `${students.length} ${t('parentsCategory')}` : t('selectClass')}
          </p>
        </button>
      </div>
    </div>
  );

  const renderParentIndividual = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('parent-mode')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white">
          {t('individualParent')}
        </h2>
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="ps-9 w-full sm:w-[200px] h-9"
          />
        </div>
      </div>

      <div className="mb-3">
        <Select value={selectedClass} onValueChange={setSelectedClass}>
          <SelectTrigger className="w-full sm:w-[240px]">
            <SelectValue placeholder={t('selectClass')} />
          </SelectTrigger>
          <SelectContent>
            {classes.map(cls => (
              <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-3">
          <div className="max-h-[340px] overflow-y-auto space-y-1.5">
            {filteredStudents.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                {t('noStudentsFound')}
              </div>
            ) : (
              filteredStudents.map(student => (
                <div
                  key={student.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors duration-150 ${
                    selectedRecipients.includes(student.parent_id || student.id)
                      ? 'bg-brand-turquoise/10 border-brand-turquoise/30'
                      : 'hover:bg-muted/50 border-transparent'
                  }`}
                  onClick={() => toggleRecipient(student.parent_id || student.id)}
                >
                  <Checkbox
                    checked={selectedRecipients.includes(student.parent_id || student.id)}
                    onCheckedChange={() => toggleRecipient(student.parent_id || student.id)}
                  />
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className={`text-xs font-bold ${
                      student.gender === 'male' ? 'bg-sky-100 text-sky-600' : 'bg-pink-100 text-pink-600'
                    }`}>
                      {student.full_name?.charAt(0) || '?'}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{student.full_name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {t('parent')}: {student.parent_name || '-'}
                    </p>
                  </div>
                  {student.parent_phone && (
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1" dir="ltr">
                      <Phone className="h-3 w-3" />{student.parent_phone}
                    </span>
                  )}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Badge variant="secondary" className="font-cairo">
          {selectedRecipients.length} {t('selected2')}
        </Badge>
        <Button
          className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
          disabled={selectedRecipients.length === 0}
          onClick={goToPreview}
        >
          {t('confirmAndSend')}
          {isRTL ? <ArrowLeft className="h-4 w-4 ms-2" /> : <ArrowRight className="h-4 w-4 ms-2" />}
        </Button>
      </div>
    </div>
  );

  const renderStudentSelect = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('recipients')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white">
          {t('studentsCategory')}
        </h2>
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="ps-9 w-full sm:w-[200px] h-9"
          />
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <Select value={selectedClass} onValueChange={setSelectedClass}>
          <SelectTrigger className="w-full sm:w-[240px]">
            <SelectValue placeholder={t('selectClass')} />
          </SelectTrigger>
          <SelectContent>
            {classes.map(cls => (
              <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={handleSelectAllStudents}>
          {filteredStudents.length > 0 && filteredStudents.every(s => selectedRecipients.includes(s.id))
            ? t('deselectAll')
            : t('selectAll')}
        </Button>
      </div>

      <Card>
        <CardContent className="p-3">
          <div className="max-h-[340px] overflow-y-auto space-y-1.5">
            {filteredStudents.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                {t('noStudentsFound')}
              </div>
            ) : (
              filteredStudents.map(student => (
                <div
                  key={student.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors duration-150 ${
                    selectedRecipients.includes(student.id)
                      ? 'bg-brand-turquoise/10 border-brand-turquoise/30'
                      : 'hover:bg-muted/50 border-transparent'
                  }`}
                  onClick={() => toggleRecipient(student.id)}
                >
                  <Checkbox
                    checked={selectedRecipients.includes(student.id)}
                    onCheckedChange={() => toggleRecipient(student.id)}
                  />
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className={`text-xs font-bold ${
                      student.gender === 'male' ? 'bg-sky-100 text-sky-600' : 'bg-pink-100 text-pink-600'
                    }`}>
                      {student.full_name?.charAt(0) || '?'}
                    </AvatarFallback>
                  </Avatar>
                  <p className="text-sm font-medium truncate flex-1">{student.full_name}</p>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Badge variant="secondary" className="font-cairo">
          {selectedRecipients.length} {t('selected2')}
        </Badge>
        <Button
          className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
          disabled={selectedRecipients.length === 0}
          onClick={goToPreview}
        >
          {t('confirmAndSend')}
          {isRTL ? <ArrowLeft className="h-4 w-4 ms-2" /> : <ArrowRight className="h-4 w-4 ms-2" />}
        </Button>
      </div>
    </div>
  );

  const renderStaffSelect = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('recipients')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      <div>
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
          {t('schoolStaffCategory')}
        </h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {STAFF_ROLES.map(role => {
          const RIcon = role.icon;
          return (
            <button
              key={role.id}
              onClick={() => handleStaffSelect(role.id)}
              className="group p-4 rounded-xl border-2 border-border/50 hover:border-brand-purple/40 bg-card hover:shadow-md transition-shadow duration-200 text-start flex items-center gap-4"
            >
              <div className="w-10 h-10 rounded-lg bg-brand-purple/10 flex items-center justify-center group-hover:scale-110 transition-transform duration-200">
                <RIcon className="h-5 w-5 text-brand-purple" />
              </div>
              <p className="text-sm font-cairo font-semibold">{t(role.i18nKey)}</p>
            </button>
          );
        })}
      </div>
    </div>
  );

  const renderAdminSelect = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('recipients')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      <div>
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
          {t('adminCategory')}
        </h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          onClick={() => handleAdminSelect('guidance')}
          className="group p-5 rounded-xl border-2 border-border/50 hover:border-brand-navy/40 bg-card hover:shadow-md transition-shadow duration-200 text-start"
        >
          <GraduationCap className="h-8 w-8 text-brand-navy dark:text-brand-turquoise mb-2" />
          <p className="font-cairo font-semibold text-sm">{t('studentGuidance')}</p>
          <p className="text-xs text-muted-foreground mt-1">{t('selectOneOrMoreStudents')}</p>
        </button>

        <button
          onClick={() => handleAdminSelect('general')}
          className="group p-5 rounded-xl border-2 border-border/50 hover:border-brand-navy/40 bg-card hover:shadow-md transition-shadow duration-200 text-start"
        >
          <Building2 className="h-8 w-8 text-brand-navy dark:text-brand-turquoise mb-2" />
          <p className="font-cairo font-semibold text-sm">{t('generalAdminNotification')}</p>
        </button>
      </div>
    </div>
  );

  const renderPreview = () => (
    <div className="space-y-4">
      <button
        onClick={() => {
          if (parentMode === 'individual') setActiveView('parent-individual');
          else if (selectedCategory === 'students' || selectedCategory === 'guidance') setActiveView('student-select');
          else setActiveView('recipients');
        }}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      {renderStepIndicator(3)}

      <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white">
        {t('messagePreview')}
      </h2>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div>
            <Label className="text-xs text-muted-foreground">{t('selectedRecipients')}</Label>
            <Badge variant="secondary" className="mt-1 font-cairo">
              {selectedRecipients.length} {t('recipients3')}
            </Badge>
          </div>

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs">{t('messageSubject')} *</Label>
              <Input
                value={messageSubject}
                onChange={(e) => setMessageSubject(e.target.value)}
                placeholder={t('messageSubject')}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t('message')} *</Label>
              <Textarea
                value={messageBody}
                onChange={(e) => setMessageBody(e.target.value)}
                placeholder={t('writeYourMessageHere')}
                rows={5}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-end gap-3">
        <Button variant="outline" onClick={resetFlow}>{t('cancel')}</Button>
        <Button
          className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
          onClick={handleSendMessage}
          disabled={sending || !messageSubject || !messageBody}
        >
          {sending && <Loader2 className="h-4 w-4 animate-spin me-2" />}
          <Send className="h-4 w-4 me-1" />
          {t('send')}
        </Button>
      </div>
    </div>
  );

  const renderSchoolNotifications = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('sections')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToSections')}
      </button>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
            {t('schoolNotifications')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('fromSchoolAdmin')}</p>
        </div>
        <Select value={schoolNotifFilter} onValueChange={setSchoolNotifFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('allNotifications')}</SelectItem>
            <SelectItem value="circulars">
              <span className="flex items-center gap-2">
                <ScrollText className="h-3.5 w-3.5" />{t('viewCirculars')}
              </span>
            </SelectItem>
            <SelectItem value="workshops">
              <span className="flex items-center gap-2">
                <Presentation className="h-3.5 w-3.5" />{t('attendWorkshops')}
              </span>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {filteredSchoolNotifs.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Megaphone className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground font-cairo">
              {schoolNotifFilter === 'circulars' ? t('noCircularsYet')
                : schoolNotifFilter === 'workshops' ? t('noWorkshopsYet')
                : t('noNotifications2')}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredSchoolNotifs.map(notif => (
            <NotificationCard
              key={notif.id}
              notif={notif}
              isRTL={isRTL}
              onRead={markNotificationRead}
              t={t}
              variant="school"
            />
          ))}
        </div>
      )}
    </div>
  );

  const renderSystemAlerts = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('sections')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToSections')}
      </button>

      <div>
        <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white mb-1">
          {t('systemAlerts')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('fromNassaq')}</p>
      </div>

      {systemAlerts.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Bell className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground font-cairo">{t('noSystemAlertsYet')}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {systemAlerts.map(notif => (
            <NotificationCard
              key={notif.id}
              notif={notif}
              isRTL={isRTL}
              onRead={markNotificationRead}
              t={t}
              variant="system"
            />
          ))}
        </div>
      )}
    </div>
  );

  const renderGuidanceStudentContext = () => (
    <div className="space-y-4">
      <button
        onClick={() => setActiveView('admin-select')}
        className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
      >
        <BackIcon className="h-4 w-4" />
        {t('backToCategories')}
      </button>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold font-cairo text-brand-navy dark:text-white">
            {t('studentGuidance')}
          </h2>
          <p className="text-sm text-muted-foreground">{t('selectOneOrMoreStudents')}</p>
        </div>
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="ps-9 w-full sm:w-[200px] h-9"
          />
        </div>
      </div>

      <Select value={selectedClass} onValueChange={setSelectedClass}>
        <SelectTrigger className="w-full sm:w-[240px]">
          <SelectValue placeholder={t('selectClass')} />
        </SelectTrigger>
        <SelectContent>
          {classes.map(cls => (
            <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Card>
        <CardContent className="p-3">
          <div className="max-h-[340px] overflow-y-auto space-y-1.5">
            {filteredStudents.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                {t('noStudentsFound')}
              </div>
            ) : (
              filteredStudents.map(student => (
                <div
                  key={student.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors duration-150 ${
                    guidanceStudentIds.includes(student.id)
                      ? 'bg-brand-turquoise/10 border-brand-turquoise/30'
                      : 'hover:bg-muted/50 border-transparent'
                  }`}
                  onClick={() => {
                    setGuidanceStudentIds(prev =>
                      prev.includes(student.id) ? prev.filter(id => id !== student.id) : [...prev, student.id]
                    );
                  }}
                >
                  <Checkbox
                    checked={guidanceStudentIds.includes(student.id)}
                    onCheckedChange={() => {
                      setGuidanceStudentIds(prev =>
                        prev.includes(student.id) ? prev.filter(id => id !== student.id) : [...prev, student.id]
                      );
                    }}
                  />
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className={`text-xs font-bold ${
                      student.gender === 'male' ? 'bg-sky-100 text-sky-600' : 'bg-pink-100 text-pink-600'
                    }`}>
                      {student.full_name?.charAt(0) || '?'}
                    </AvatarFallback>
                  </Avatar>
                  <p className="text-sm font-medium truncate flex-1">{student.full_name}</p>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Badge variant="secondary" className="font-cairo">
          {guidanceStudentIds.length} {t('selected2')}
        </Badge>
        <Button
          className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
          onClick={() => setActiveView('preview')}
        >
          {t('confirmAndSend')}
          {isRTL ? <ArrowLeft className="h-4 w-4 ms-2" /> : <ArrowRight className="h-4 w-4 ms-2" />}
        </Button>
      </div>
    </div>
  );

  const renderActiveView = () => {
    switch (activeView) {
      case 'sections': return renderSections();
      case 'communication-hub': return renderCommunicationHub();
      case 'templates': return renderTemplates();
      case 'recipients': return renderRecipients();
      case 'parent-mode': return renderParentMode();
      case 'parent-individual': return renderParentIndividual();
      case 'student-select': return renderStudentSelect();
      case 'staff-select': return renderStaffSelect();
      case 'admin-select': return renderAdminSelect();
      case 'guidance-student-context': return renderGuidanceStudentContext();
      case 'preview': return renderPreview();
      case 'school-notifications': return renderSchoolNotifications();
      case 'system-alerts': return renderSystemAlerts();
      default: return renderSections();
    }
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-slate-50 dark:bg-gray-900" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b border-slate-200 dark:border-slate-800 p-4">
          <div className="flex items-center justify-between flex-wrap gap-4 max-w-[1400px] mx-auto">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('communicationNotifications')}
              </h1>
              <p className="text-sm text-muted-foreground">{t('communicationCenterSectionDesc')}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => { resetFlow(); fetchData(); }}
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              {unreadCount > 0 && (
                <Badge className="bg-red-500 text-white border-0">
                  {unreadCount} {t('new3')}
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="p-4 md:p-6 lg:p-8 max-w-[1400px] mx-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : (
            renderActiveView()
          )}
        </div>
      </div>
    </Sidebar>
  );
}

function NotificationCard({ notif, isRTL, onRead, t, variant }) {
  const isUnread = !notif.read_status && !notif.is_read;
  const priorityColors = {
    critical: 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-300',
    high: 'bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-300',
    medium: 'bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300',
    low: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300',
  };

  const typeIcons = {
    system: Info,
    announcement: Megaphone,
    schedule: Presentation,
    communication: MessageSquare,
    attendance: Eye,
    assessment: FileText,
    behaviour: AlertTriangle,
  };

  const TypeIcon = typeIcons[notif.notification_type] || Bell;
  const iconBg = variant === 'system'
    ? 'bg-brand-purple/10 text-brand-purple'
    : variant === 'school'
    ? 'bg-brand-navy/10 text-brand-navy dark:text-brand-turquoise'
    : notif.priority === 'high' || notif.priority === 'critical'
    ? 'bg-red-100 dark:bg-red-900/40 text-red-600'
    : 'bg-brand-turquoise/10 text-brand-turquoise';

  return (
    <div
      className={`p-4 rounded-xl border transition-colors duration-150 cursor-pointer ${
        isUnread
          ? 'bg-brand-turquoise/5 border-brand-turquoise/20 hover:shadow-sm'
          : 'bg-card hover:bg-muted/30'
      }`}
      onClick={() => isUnread && onRead(notif.id)}
    >
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${iconBg}`}>
          <TypeIcon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <p className="font-medium text-sm truncate">{isRTL ? notif.title : (notif.title_en || notif.title)}</p>
            {isUnread && <span className="w-2 h-2 rounded-full bg-brand-turquoise shrink-0" />}
          </div>
          <p className="text-xs text-muted-foreground line-clamp-2">
            {isRTL ? notif.message : (notif.message_en || notif.message)}
          </p>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {notif.priority && (
              <Badge className={`text-[10px] border-0 ${priorityColors[notif.priority] || priorityColors.medium}`}>
                {t(`priority${notif.priority.charAt(0).toUpperCase()}${notif.priority.slice(1)}`)}
              </Badge>
            )}
            {notif.sender_name && (
              <span className="text-[10px] text-muted-foreground">
                {t('from')}: {notif.sender_name}
              </span>
            )}
            <span className="text-[10px] text-muted-foreground flex items-center gap-1">
              <Clock className="h-2.5 w-2.5" />
              {notif.created_at
                ? new Date(notif.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                  })
                : ''}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
