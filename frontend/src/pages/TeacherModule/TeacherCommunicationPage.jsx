import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
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
  Building2, Shield, Star,
  ScrollText, Presentation, ArrowLeft, ArrowRight,
  UserCog, HeartHandshake, Sparkles, Info
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';
import IndependentTeacherCommunicationPage from './IndependentTeacherCommunicationPage';
// 2026-05-18 — IT users now land on the unified inbox+composer hub
// instead of the bare composer page. The hub mounts the composer
// (IndependentTeacherCommunicationPanel) inside its "إرسال رسالة"
// tab so the IT composer code path is unchanged.
import UnifiedCommunicationsHub from './UnifiedCommunicationsHub';
import { getApiErrorMessage } from '../../utils/apiError';
import { NotificationDetailDialog } from '../../components/notifications/NotificationDetailDialog';
import { normalizeStandardNotification } from '../../components/notifications/notificationDisplay';

// Each template explicitly declares which recipient cohorts it can
// target. The "Choose Recipients" step (Step 2) renders only these
// cohorts for the selected template, and the same `id` is sent to the
// backend as `template_id` for fail-closed server-side validation in
// notification_routes_mod._enforce_template_recipient_rule.
//
// Default contract: a template that names cohorts here is restrictive
// (only those are allowed). Templates with no `allowedRecipients` key
// keep the legacy "all cohorts allowed" behaviour so existing flows do
// not regress.
const ALL_RECIPIENT_CATEGORY_IDS = ['parents', 'admin', 'staff'];
const TEMPLATES = [
  { id: 'homework', icon: BookOpen, color: 'bg-blue-500', titleKey: 'homeworkReminder', bodyKey: 'homeworkReminderBody', allowedRecipients: ['parents'] },
  { id: 'exam', icon: FileText, color: 'bg-amber-500', titleKey: 'examNotice', bodyKey: 'examNoticeBody', allowedRecipients: ALL_RECIPIENT_CATEGORY_IDS },
  { id: 'meeting', icon: UserCheck, color: 'bg-green-500', titleKey: 'meetingInvitation', bodyKey: 'meetingInvitationBody', allowedRecipients: ALL_RECIPIENT_CATEGORY_IDS },
  { id: 'behavior', icon: AlertTriangle, color: 'bg-rose-500', titleKey: 'behaviorNote', bodyKey: 'behaviorNoteBody', allowedRecipients: ALL_RECIPIENT_CATEGORY_IDS },
  { id: 'achievement', icon: CheckCircle2, color: 'bg-emerald-500', titleKey: 'achievementNotice', bodyKey: 'achievementNoticeBody', allowedRecipients: ALL_RECIPIENT_CATEGORY_IDS },
  { id: 'absence', icon: AlertCircle, color: 'bg-red-500', titleKey: 'absenceAlert', bodyKey: 'absenceAlertBody', allowedRecipients: ALL_RECIPIENT_CATEGORY_IDS },
];

// Recipient categories per spec: Parents / Administration / Staff.
// Administration auto-resolves to the General Admin Notice (the
// counselor sub-option was removed; see handleSelectCategory).
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

// Phase 1 §5.6 (Task #198) IT dispatcher wrapper — Independent-Teacher accounts get the
// reduced two-cohort communication surface. The full principal-style
// wizard below (TeacherCommunicationPageInner) stays untouched for
// regular teachers. Routing is done via a wrapper so the inner
// component never has hooks called conditionally.
export default function TeacherCommunicationPage() {
  const { user } = useAuth();
  if ((user?.role || '').toLowerCase() === 'independent_teacher') {
    // 2026-05-18 — render the unified hub (Inbox default + Composer
    // tab) instead of the standalone composer. The standalone
    // composer page is still exported so direct importers continue
    // to work; we just no longer wire it into the IT route.
    return <UnifiedCommunicationsHub />;
  }
  return <TeacherCommunicationPageInner />;
}

function TeacherCommunicationPageInner() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
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
  // `adminMode` historically gated a 2-card sub-flow under "Management"
  // (Student Counseling vs General Admin Notice). The counselor variant
  // was removed per spec — Management now auto-resolves to the general
  // admin notice. The state is retained as a passive marker so the
  // existing scroll/effect dependency arrays do not change shape.
  const [adminMode, setAdminMode] = useState(null);
  const [messageBody, setMessageBody] = useState('');
  const [messageSubject, setMessageSubject] = useState('');

  const [schoolNotifFilter, setSchoolNotifFilter] = useState('all');
  // Quick-preview dialog (parent pattern): clicking any notification
  // card opens the full content in place instead of only marking read.
  const [detailNotification, setDetailNotification] = useState(null);

  const step1Ref = useRef(null);
  const step2Ref = useRef(null);
  const step3Ref = useRef(null);
  const subPickerRef = useRef(null);

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

      // Forward the selected template id so the backend can fail-closed
      // on cohort mismatches (e.g. Homework Reminder → parents only).
      const templateId = selectedTemplate?.id || null;

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
          if (templateId) payload.template_id = templateId;
          await api.post('/notifications', payload);
        }
      }

      // Task #463 — for the parents cohort the FE now sends the
      // STUDENT id (tagged via related_entity/related_entity_id) and
      // lets the backend resolve the parent users.id canonically via
      // guardian_links. This avoids the broken path where the FE used
      // to push the mutable `students.parent_id` as recipient_id.
      const isParentFlow = selectedCategory === 'parents';

      for (const recipientId of userRecipients) {
        const payload = {
          title: messageSubject,
          message: messageBody,
          notification_type: 'communication',
          priority: 'medium',
        };
        if (isParentFlow) {
          payload.related_entity = 'student';
          payload.related_entity_id = recipientId;
        } else {
          payload.recipient_id = recipientId;
        }
        if (templateId) payload.template_id = templateId;
        await api.post('/notifications', payload);
      }

      toast.success(t('messageSentSuccessfully'));
      resetFlow();
      fetchData();
    } catch (error) {
      // Surface the backend's safe Arabic detail when present (e.g.
      // "لا يوجد ولي أمر مرتبط بهذا الطالب" or the cohort-mismatch
      // message). Falls back to the generic toast otherwise.
      const detail = getApiErrorMessage(error);
      if (typeof detail === 'string' && detail.trim()) {
        nassaqError(detail);
      } else {
        nassaqError(t('errorSendingMessage'));
      }
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
    setAdminMode(null);
    setMessageBody('');
    setMessageSubject('');
  };

  const applyTemplate = (template) => {
    setSelectedTemplate(template);
    setMessageSubject(t(template.titleKey));
    setMessageBody(t(template.bodyKey));
    setSelectedCategory(null);
    setSelectedRecipients([]);
    setParentMode(null);
    setAdminMode(null);
  };

  const handleSelectCategory = (catId) => {
    setSelectedCategory(catId);
    setParentMode(null);
    if (catId === 'admin') {
      // Management auto-resolves to the general admin notice — the
      // counselor sub-option was removed per spec, so there is no
      // remaining branching to surface. Set the canonical recipient up
      // front so the wizard's "next" affordance is enabled immediately.
      setSelectedRecipients(['admin_general']);
      setAdminMode('general');
    } else {
      setSelectedRecipients([]);
      setAdminMode(null);
    }
  };

  const handleParentModeSelect = (mode) => {
    setParentMode(mode);
    if (mode === 'all') {
      // Task #463 — collect STUDENT ids (deduped) instead of the
      // mutable `students.parent_id`. The backend now resolves the
      // canonical parent user via guardian_links for each student.
      const allStudentIds = students.filter(s => s.id).map(s => s.id);
      setSelectedRecipients([...new Set(allStudentIds)]);
    } else {
      setSelectedRecipients([]);
    }
  };

  const toggleRecipient = (id) => {
    setSelectedRecipients(prev =>
      prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]
    );
  };

  const handleStaffSelect = (roleId) => {
    setSelectedRecipients([roleId]);
  };

  const goToPreview = () => {
    if (selectedRecipients.length === 0) {
      nassaqError(t('noRecipientsSelected'));
      return;
    }
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

  // Opens the quick-preview dialog for ANY card (read or unread) and
  // marks unread ones as read — same contract as the parent pattern.
  const openNotification = (notif) => {
    if (!notif.read_status && !notif.is_read) markNotificationRead(notif.id);
    setDetailNotification(notif);
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
                  onOpen={openNotification}
                  t={t}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );

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
              setAdminMode(null);
              setSelectedClass('');
              setMessageSubject('');
              setMessageBody('');
              setActiveView('wizard');
            }}
          >
            <Send className="h-5 w-5 me-2" />
            {t('sendNotificationBtn')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const scrollIntoViewSoon = (ref) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (ref?.current) {
          ref.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });
  };

  // Auto-scroll on progressive disclosure
  useEffect(() => {
    if (activeView !== 'wizard') return;
    if (selectedTemplate && !selectedCategory) {
      scrollIntoViewSoon(step2Ref);
    }
  }, [activeView, selectedTemplate, selectedCategory]);

  useEffect(() => {
    if (activeView !== 'wizard') return;
    if (selectedCategory) {
      scrollIntoViewSoon(subPickerRef);
    }
  }, [activeView, selectedCategory, parentMode, adminMode]);

  useEffect(() => {
    if (activeView !== 'wizard') return;
    if (selectedRecipients.length > 0) {
      scrollIntoViewSoon(step3Ref);
    }
  }, [activeView, selectedRecipients.length]);

  const wizardCurrentStep = !selectedTemplate
    ? 1
    : selectedRecipients.length === 0
    ? 2
    : 3;

  const handleJumpToStep = (n) => {
    if (n === 1) {
      step1Ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (n === 2) {
      if (!selectedTemplate) return;
      step2Ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (n === 3) {
      if (selectedRecipients.length === 0) return;
      step3Ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const renderWizardStepBar = () => {
    const steps = [
      { n: 1, label: t('chooseTemplate') },
      { n: 2, label: t('selectRecipients') },
      { n: 3, label: t('messagePreview') },
    ];
    const reachable = (n) =>
      n === 1 ? true : n === 2 ? !!selectedTemplate : selectedRecipients.length > 0;
    return (
      <div className="sticky top-[72px] z-10 bg-slate-50/90 dark:bg-gray-900/90 backdrop-blur-sm py-3 -mx-1 px-1">
        <div className="flex items-center gap-2 flex-wrap">
          {steps.map((s, idx) => {
            const isActive = s.n === wizardCurrentStep;
            const isDone = s.n < wizardCurrentStep;
            const canJump = reachable(s.n);
            return (
              <React.Fragment key={s.n}>
                <button
                  type="button"
                  onClick={() => canJump && handleJumpToStep(s.n)}
                  disabled={!canJump}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-full border transition-colors duration-150 ${
                    isActive
                      ? 'bg-brand-turquoise/10 border-brand-turquoise text-brand-navy dark:text-white'
                      : isDone
                      ? 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-300 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/50'
                      : 'bg-muted/40 border-border/50 text-muted-foreground'
                  } ${canJump ? 'cursor-pointer' : 'cursor-not-allowed opacity-70'}`}
                >
                  <span
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                      isActive
                        ? 'bg-brand-turquoise text-white'
                        : isDone
                        ? 'bg-emerald-500 text-white'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {isDone ? '✓' : s.n}
                  </span>
                  <span className="text-xs font-cairo font-medium">{s.label}</span>
                </button>
                {idx < steps.length - 1 && (
                  <span className="h-px w-4 bg-border/70" aria-hidden="true" />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    );
  };

  const stepReveal = {
    initial: { opacity: 0, height: 0 },
    animate: { opacity: 1, height: 'auto' },
    exit: { opacity: 0, height: 0 },
    transition: { duration: 0.35, ease: [0.22, 0.61, 0.36, 1] },
  };

  const SelectedBadge = () => (
    <span className="absolute top-2 end-2 w-6 h-6 rounded-full bg-brand-turquoise text-white flex items-center justify-center shadow-md">
      <CheckCircle2 className="h-4 w-4" />
    </span>
  );

  const renderTemplatesGrid = () => (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {TEMPLATES.map(template => {
        const TIcon = template.icon;
        const isSelected = selectedTemplate?.id === template.id;
        return (
          <button
            key={template.id}
            onClick={() => applyTemplate(template)}
            className={`relative p-4 rounded-xl border-2 bg-card transition-all duration-200 text-center ${
              isSelected
                ? 'border-brand-turquoise ring-2 ring-brand-turquoise/30 shadow-md'
                : 'border-border/50 hover:border-brand-turquoise/40 hover:shadow-md'
            }`}
          >
            {isSelected && <SelectedBadge />}
            <div className={`w-11 h-11 mx-auto mb-2.5 rounded-xl ${template.color} flex items-center justify-center transition-transform duration-200 ${isSelected ? 'scale-110' : 'group-hover:scale-110'}`}>
              <TIcon className="h-5 w-5 text-white" />
            </div>
            <p className="text-sm font-cairo font-medium leading-tight">
              {t(template.titleKey)}
            </p>
          </button>
        );
      })}
    </div>
  );

  const renderRecipientCategoriesGrid = () => {
    // Filter the master cohort list against the selected template's
    // declared `allowedRecipients`. Templates without that key remain
    // unrestricted (legacy behaviour preserved).
    const allowed = selectedTemplate?.allowedRecipients;
    const visibleCategories = Array.isArray(allowed)
      ? RECIPIENT_CATEGORIES.filter(c => allowed.includes(c.id))
      : RECIPIENT_CATEGORIES;
    // Keep cards visually balanced when only 1–2 cohorts are visible
    // (e.g. Homework Reminder → Parents only). No placeholder cards.
    const colsClass =
      visibleCategories.length === 1
        ? 'grid-cols-1 sm:max-w-sm'
        : visibleCategories.length === 2
        ? 'grid-cols-1 sm:grid-cols-2'
        : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3';
    return (
    <div className={`grid ${colsClass} gap-4`}>
      {visibleCategories.map(cat => {
        const CIcon = cat.icon;
        const isSelected = selectedCategory === cat.id;
        return (
          <button
            key={cat.id}
            onClick={() => handleSelectCategory(cat.id)}
            className={`relative p-5 rounded-xl border-2 bg-card transition-all duration-200 text-center ${
              isSelected
                ? 'border-brand-turquoise ring-2 ring-brand-turquoise/30 shadow-md'
                : 'border-border/50 hover:border-brand-turquoise/40 hover:shadow-md'
            }`}
          >
            {isSelected && <SelectedBadge />}
            <div className={`w-12 h-12 mx-auto mb-3 rounded-xl ${cat.color} flex items-center justify-center transition-transform duration-200 ${isSelected ? 'scale-110' : ''}`}>
              <CIcon className="h-6 w-6 text-white" />
            </div>
            <p className="text-sm font-cairo font-semibold">{t(cat.i18nKey)}</p>
          </button>
        );
      })}
    </div>
    );
  };

  const renderParentSubFlow = () => (
    <div className="space-y-4">
      <div>
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
          className={`relative p-5 rounded-xl border-2 bg-card transition-all duration-200 text-start ${
            parentMode === 'individual'
              ? 'border-brand-turquoise ring-2 ring-brand-turquoise/30 shadow-md'
              : 'border-border/50 hover:border-blue-400/40 hover:shadow-md'
          }`}
        >
          {parentMode === 'individual' && <SelectedBadge />}
          <Users className="h-8 w-8 text-blue-500 mb-2" />
          <p className="font-cairo font-semibold text-sm">{t('individualParent')}</p>
          <p className="text-xs text-muted-foreground mt-1">{t('selectOneOrMoreStudents')}</p>
        </button>

        <button
          onClick={() => handleParentModeSelect('all')}
          className={`relative p-5 rounded-xl border-2 bg-card transition-all duration-200 text-start ${
            parentMode === 'all'
              ? 'border-brand-turquoise ring-2 ring-brand-turquoise/30 shadow-md'
              : 'border-border/50 hover:border-green-400/40 hover:shadow-md'
          } ${!selectedClass ? 'opacity-60' : ''}`}
          disabled={!selectedClass}
        >
          {parentMode === 'all' && <SelectedBadge />}
          <Megaphone className="h-8 w-8 text-green-500 mb-2" />
          <p className="font-cairo font-semibold text-sm">{t('allParentsInClass')}</p>
          <p className="text-xs text-muted-foreground mt-1">
            {selectedClass ? `${students.length} ${t('parentsCategory')}` : t('selectClass')}
          </p>
        </button>
      </div>

      <AnimatePresence initial={false}>
        {parentMode === 'individual' && (
          <motion.div key="parent-individual" {...stepReveal} className="overflow-hidden">
            <div className="space-y-3 pt-2">
              <div className="relative max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('search')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="ps-9 h-9"
                />
              </div>
              <Card>
                <CardContent className="p-3">
                  <div className="max-h-[340px] overflow-y-auto space-y-1.5">
                    {filteredStudents.length === 0 ? (
                      <div className="text-center py-8 text-sm text-muted-foreground">
                        {t('noStudentsFound')}
                      </div>
                    ) : (
                      filteredStudents.map(student => {
                        // Task #463 — push the STUDENT id; backend
                        // resolves the canonical parent user via
                        // guardian_links on submit.
                        const recId = student.id;
                        const isSel = selectedRecipients.includes(recId);
                        return (
                          <div
                            key={student.id}
                            className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors duration-150 ${
                              isSel ? 'bg-brand-turquoise/10 border-brand-turquoise/30' : 'hover:bg-muted/50 border-transparent'
                            }`}
                            onClick={() => toggleRecipient(recId)}
                          >
                            <Checkbox checked={isSel} onCheckedChange={() => toggleRecipient(recId)} />
                            <Avatar className="h-8 w-8">
                              <AvatarFallback className={`text-xs font-bold ${student.gender === 'male' ? 'bg-sky-100 text-sky-600' : 'bg-pink-100 text-pink-600'}`}>
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
                        );
                      })
                    )}
                  </div>
                </CardContent>
              </Card>
              <div className="flex items-center">
                <Badge variant="secondary" className="font-cairo">
                  {selectedRecipients.length} {t('selected2')}
                </Badge>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  const renderStaffSubFlow = () => (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {STAFF_ROLES.map(role => {
        const RIcon = role.icon;
        const isSel = selectedRecipients.includes(role.id);
        return (
          <button
            key={role.id}
            onClick={() => handleStaffSelect(role.id)}
            className={`relative p-4 rounded-xl border-2 bg-card transition-all duration-200 text-start flex items-center gap-4 ${
              isSel ? 'border-brand-turquoise ring-2 ring-brand-turquoise/30 shadow-md' : 'border-border/50 hover:border-brand-purple/40 hover:shadow-md'
            }`}
          >
            {isSel && <SelectedBadge />}
            <div className="w-10 h-10 rounded-lg bg-brand-purple/10 flex items-center justify-center">
              <RIcon className="h-5 w-5 text-brand-purple" />
            </div>
            <p className="text-sm font-cairo font-semibold">{t(role.i18nKey)}</p>
          </button>
        );
      })}
    </div>
  );

  const renderRecipientSubPicker = () => {
    if (!selectedCategory) return null;
    let content = null;
    if (selectedCategory === 'parents') content = renderParentSubFlow();
    else if (selectedCategory === 'staff') content = renderStaffSubFlow();
    // 'admin' (Management) intentionally has no sub-picker: it
    // auto-resolves to the general admin notice in handleSelectCategory.
    if (!content) return null;
    return (
      <div ref={subPickerRef} className="pt-4 mt-3 border-t border-border/40">
        {content}
      </div>
    );
  };

  const renderNotificationWizard = () => {
    const step1Locked = wizardCurrentStep > 1;
    const step2Locked = wizardCurrentStep > 2;
    return (
      <div className="space-y-5">
        <button
          onClick={() => setActiveView('communication-hub')}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-brand-navy dark:hover:text-brand-turquoise transition-colors duration-150"
        >
          <BackIcon className="h-4 w-4" />
          {t('backToSections')}
        </button>

        {renderWizardStepBar()}

        {/* Step 1: Choose Template */}
        <Card
          ref={step1Ref}
          className={`transition-opacity duration-300 ${step1Locked ? 'opacity-60 hover:opacity-100' : ''}`}
        >
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-full bg-brand-turquoise text-white flex items-center justify-center text-xs font-bold">1</span>
              <h2 className="text-lg font-bold font-cairo text-brand-navy dark:text-white">
                {t('chooseTemplate')}
              </h2>
              {selectedTemplate && (
                <Badge variant="secondary" className="ms-auto font-cairo">
                  {t(selectedTemplate.titleKey)}
                </Badge>
              )}
            </div>
            {renderTemplatesGrid()}
          </CardContent>
        </Card>

        {/* Step 2: Recipients */}
        <AnimatePresence initial={false}>
          {selectedTemplate && (
            <motion.div key="step-2" {...stepReveal} className="overflow-hidden">
              <Card
                ref={step2Ref}
                className={`transition-opacity duration-300 ${step2Locked ? 'opacity-60 hover:opacity-100' : ''}`}
              >
                <CardContent className="p-5 space-y-4">
                  <div className="flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-brand-turquoise text-white flex items-center justify-center text-xs font-bold">2</span>
                    <h2 className="text-lg font-bold font-cairo text-brand-navy dark:text-white">
                      {t('selectRecipients')}
                    </h2>
                    {selectedRecipients.length > 0 && (
                      <Badge variant="secondary" className="ms-auto font-cairo">
                        {selectedRecipients.length} {t('recipients3')}
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{t('recipientCategories')}</p>
                  {renderRecipientCategoriesGrid()}
                  {renderRecipientSubPicker()}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Step 3: Preview & Send */}
        <AnimatePresence initial={false}>
          {selectedRecipients.length > 0 && (
            <motion.div key="step-3" {...stepReveal} className="overflow-hidden">
              <Card ref={step3Ref}>
                <CardContent className="p-5 space-y-4">
                  <div className="flex items-center gap-2">
                    <span className="w-7 h-7 rounded-full bg-brand-turquoise text-white flex items-center justify-center text-xs font-bold">3</span>
                    <h2 className="text-lg font-bold font-cairo text-brand-navy dark:text-white">
                      {t('messagePreview')}
                    </h2>
                  </div>

                  <div>
                    <Label className="text-xs text-muted-foreground">{t('selectedRecipients')}</Label>
                    <div className="mt-1">
                      <Badge variant="secondary" className="font-cairo">
                        {selectedRecipients.length} {t('recipients3')}
                      </Badge>
                    </div>
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
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  };

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
              onOpen={openNotification}
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
              onOpen={openNotification}
              t={t}
              variant="system"
            />
          ))}
        </div>
      )}
    </div>
  );


  const renderActiveView = () => {
    switch (activeView) {
      case 'sections': return renderSections();
      case 'communication-hub': return renderCommunicationHub();
      case 'wizard': return renderNotificationWizard();
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

        <NotificationDetailDialog
          notification={normalizeStandardNotification(detailNotification)}
          isRTL={isRTL}
          onClose={() => setDetailNotification(null)}
          onNavigate={navigate}
        />
      </div>
    </Sidebar>
  );
}

function NotificationCard({ notif, isRTL, onOpen, t, variant }) {
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
      onClick={() => onOpen(notif)}
      data-testid={`notification-card-${notif.id}`}
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

