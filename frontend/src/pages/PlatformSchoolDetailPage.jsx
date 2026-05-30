import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Building2, ArrowRight, ArrowLeft, Users, GraduationCap, BookOpen,
  CreditCard, Activity, MapPin, Mail, Phone, Calendar, Hash,
  Edit, Save, X, Pause, Play, AlertTriangle, Loader2,
  UserCheck, CheckCircle2, XCircle, Clock, Shield, Eye, EyeOff,
  ChevronRight, School, LayoutDashboard, RefreshCw, Key, Copy,
  Lock, Unlock, Sparkles, UserPlus, RotateCcw,
} from 'lucide-react';

const STATUS_CONFIG = {
  active:    { label: 'نشطة',        label_en: 'Active',     color: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  suspended: { label: 'موقوفة',      label_en: 'Suspended',  color: 'bg-red-500',     badge: 'bg-red-100 text-red-700 border-red-200' },
  setup:     { label: 'قيد الإعداد', label_en: 'Setup',      color: 'bg-amber-500',   badge: 'bg-amber-100 text-amber-700 border-amber-200' },
  pending:   { label: 'معلقة',       label_en: 'Pending',    color: 'bg-slate-400',   badge: 'bg-slate-100 text-slate-700 border-slate-200' },
};

const ACTION_LABELS = {
  'tenant.suspended': { ar: 'تعليق المدرسة', icon: Pause, color: 'text-red-600' },
  'tenant.activated': { ar: 'تفعيل المدرسة', icon: Play, color: 'text-emerald-600' },
  'tenant.created':   { ar: 'إنشاء المدرسة', icon: Building2, color: 'text-blue-600' },
  'tenant.updated':   { ar: 'تعديل المدرسة', icon: Edit, color: 'text-amber-600' },
  'user.created':     { ar: 'إنشاء مستخدم',  icon: Users, color: 'text-purple-600' },
  'user.suspended':   { ar: 'تعليق مستخدم',  icon: XCircle, color: 'text-red-600' },
  'user.activated':   { ar: 'تفعيل مستخدم',  icon: CheckCircle2, color: 'text-emerald-600' },
};

const ROLE_LABELS = {
  school_principal: { ar: 'مدير المدرسة', color: 'bg-brand-navy/10 text-brand-navy' },
  school_admin:     { ar: 'مشرف', color: 'bg-brand-purple/10 text-brand-purple' },
  teacher:          { ar: 'معلم', color: 'bg-brand-turquoise/10 text-brand-turquoise' },
  student:          { ar: 'طالب', color: 'bg-blue-100 text-blue-700' },
  parent:           { ar: 'ولي أمر', color: 'bg-emerald-100 text-emerald-700' },
};

export default function PlatformSchoolDetailPage() {
  const { schoolId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { api, enterSchoolContext } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState('general');

  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);

  const [suspendDialog, setSuspendDialog] = useState(false);
  const [activateDialog, setActivateDialog] = useState(false);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const [credForm, setCredForm] = useState({ email: '', name: '', password: '', confirmPassword: '' });
  const [credFormOpen, setCredFormOpen] = useState(false);
  const [credLoading, setCredLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [credResult, setCredResult] = useState(null);

  const generatePassword = () => {
    const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$';
    const pwd = Array.from({ length: 14 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    setCredForm(f => ({ ...f, password: pwd, confirmPassword: pwd }));
  };

  const copyToClipboard = (text, label = '') => {
    navigator.clipboard.writeText(text);
    toast.success(isRTL ? `تم نسخ ${label}` : `${label} copied`);
  };

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const res = await api.get(`/schools/${schoolId}/detail`);
      setDetail(res.data);
      setEditData({
        name: res.data.school?.name || '',
        name_en: res.data.school?.name_en || '',
        email: res.data.school?.email || '',
        phone: res.data.school?.phone || '',
        city: res.data.school?.city || '',
        region: res.data.school?.region || '',
        address: res.data.school?.address || '',
      });
    } catch (err) {
      setError(true);
      nassaqError(t('failedToLoadSchoolData'));
    } finally {
      setLoading(false);
    }
  }, [api, schoolId, isRTL]);

  useEffect(() => { fetchDetail(); }, [fetchDetail]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/schools/${schoolId}`, editData);
      toast.success(t('changesSaved'));
      setEditMode(false);
      fetchDetail();
    } catch (err) {
      nassaqError(t('failedToSaveChanges'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCredentials = async () => {
    if (!credForm.email.trim()) {
      nassaqError(t('emailIsRequired'));
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(credForm.email)) {
      nassaqError(t('invalidEmailFormat'));
      return;
    }
    if (credForm.password && credForm.password !== credForm.confirmPassword) {
      nassaqError(t('passwordsDoNotMatch2'));
      return;
    }
    if (credForm.password && credForm.password.length < 8) {
      nassaqError(t('passwordMustBeAtLeast8Characters'));
      return;
    }
    setCredLoading(true);
    try {
      const payload = { email: credForm.email, name: credForm.name || undefined };
      if (credForm.password) payload.password = credForm.password;
      const res = await api.post(`/schools/${schoolId}/credentials`, payload);
      setCredResult(res.data);
      toast.success(res.data.is_new
        ? (t('principalAccountCreatedSuccessfully'))
        : (t('credentialsUpdatedSuccessfully'))
      );
      setCredFormOpen(false);
      fetchDetail();
    } catch (err) {
      nassaqError(err.response?.data?.detail || (t('failedToSaveCredentials')));
    } finally {
      setCredLoading(false);
    }
  };

  const openCredForm = (principal) => {
    setCredForm({
      email: principal?.email || detail?.school?.principal_email || detail?.school?.email || '',
      name: principal?.full_name || detail?.school?.principal_name || '',
      password: '',
      confirmPassword: '',
    });
    setCredResult(null);
    setCredFormOpen(true);
  };

  const handleSuspend = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${schoolId}/suspend`, { reason: actionReason });
      toast.success(t('schoolSuspendedSuccessfully'));
      setSuspendDialog(false);
      setActionReason('');
      fetchDetail();
    } catch (err) {
      nassaqError(err.response?.data?.detail || (t('failedToSuspend')));
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivate = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired2'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${schoolId}/activate`, { reason: actionReason });
      toast.success(t('schoolActivatedSuccessfully'));
      setActivateDialog(false);
      setActionReason('');
      fetchDetail();
    } catch (err) {
      nassaqError(err.response?.data?.detail || (t('failedToActivate')));
    } finally {
      setActionLoading(false);
    }
  };

  const handleEnterDashboard = async () => {
    if (!detail?.school) return;
    // Task #511: enterSchoolContext now mints an impersonation token
    // via /role-switch/switch (MFA step-up handled by the axios
    // interceptor). Only post-step-up failures surface here.
    try {
      await enterSchoolContext(detail.school);
    } catch (err) {
      const dt = err?.response?.data?.detail;
      nassaqError(typeof dt === 'string' ? dt : t('errorSwitchingRole'));
      return;
    }
    toast.success(isRTL ? `تم الدخول إلى ${detail.school.name}` : `Entered ${detail.school.name_en || detail.school.name}`);
    navigate('/principal');
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-brand-turquoise mx-auto" />
            <p className="font-cairo text-slate-500">{t('loading')}</p>
          </div>
        </div>
      </Sidebar>
    );
  }

  if (error || !detail) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center p-4" dir={isRTL ? 'rtl' : 'ltr'}>
          <Card className="max-w-md w-full">
            <CardContent className="p-8 text-center space-y-5">
              <div className="w-14 h-14 rounded-2xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto">
                <AlertTriangle className="h-7 w-7 text-red-600" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <p className="font-cairo text-lg font-semibold text-slate-800 dark:text-white">
                {t('failedToLoadSchoolData')}
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                <Button onClick={() => fetchDetail()} className="w-full sm:w-auto">
                  <RefreshCw className="h-4 w-4 me-1.5" strokeWidth={1.5} aria-hidden="true" />
                  {t('retry')}
                </Button>
                <Button variant="outline" onClick={() => navigate('/admin/schools')} className="w-full sm:w-auto">
                  <ChevronRight className="h-4 w-4 me-1.5 rtl:rotate-180" strokeWidth={1.5} aria-hidden="true" />
                  {t('schoolsManagement')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </Sidebar>
    );
  }

  const school = detail.school;
  const status = school?.status || 'active';
  const statusCfg = STATUS_CONFIG[status] || STATUS_CONFIG.active;
  const isSuspended = status === 'suspended';
  const BackIcon = isRTL ? ArrowLeft : ArrowRight;

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">

          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <button onClick={() => navigate('/admin/schools')} className="hover:text-brand-navy transition-colors">
              {t('schoolsManagement')}
            </button>
            <ChevronRight className="h-4 w-4" />
            <span className="text-slate-800 dark:text-white font-medium">{school?.name}</span>
          </div>

          {/* School Header Card */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple p-6 sm:p-8 text-white shadow-2xl">
            <div className="absolute inset-0 opacity-10 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-brand-turquoise to-transparent" />
            <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center flex-shrink-0 border border-white/20">
                  <span className="text-2xl font-bold">{school?.name?.charAt(0)}</span>
                </div>
                <div>
                  <h1 className="text-2xl sm:text-3xl font-bold font-cairo leading-tight">{school?.name}</h1>
                  {school?.name_en && <p className="text-white/60 text-sm mt-0.5">{school.name_en}</p>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-white/60">
                    <span className="flex items-center gap-1"><Hash className="h-3 w-3" />{school?.code || '—'}</span>
                    {school?.city && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{school.city}</span>}
                    <span className="flex items-center gap-1">
                      <div className={`w-2 h-2 rounded-full ${statusCfg.color} animate-pulse`} />
                      {isRTL ? statusCfg.label : statusCfg.label_en}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" className="border-white/20 text-white hover:bg-white/10" onClick={() => fetchDetail()}>
                  <RefreshCw className="h-4 w-4 me-1.5" />
                  {t('refresh')}
                </Button>
                <Button size="sm" className="bg-white/20 hover:bg-white/30 text-white border border-white/20" onClick={handleEnterDashboard}>
                  <LayoutDashboard className="h-4 w-4 me-1.5" />
                  {t('openDashboard')}
                </Button>
                {isSuspended ? (
                  <Button size="sm" className="bg-emerald-500 hover:bg-emerald-600 text-white" onClick={() => { setActivateDialog(true); setActionReason(''); }}>
                    <Play className="h-4 w-4 me-1.5" />
                    {t('activateSchool')}
                  </Button>
                ) : (
                  <Button size="sm" className="bg-red-500/80 hover:bg-red-500 text-white" onClick={() => { setSuspendDialog(true); setActionReason(''); }}>
                    <Pause className="h-4 w-4 me-1.5" />
                    {t('suspendSchool')}
                  </Button>
                )}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: t('users'), value: detail.stats?.total_users || 0, icon: Users },
                { label: t('students'), value: detail.stats?.total_students || 0, icon: GraduationCap },
                { label: t('teachers'), value: detail.stats?.total_teachers || 0, icon: UserCheck },
                { label: t('classes2'), value: detail.stats?.total_classes || 0, icon: BookOpen },
              ].map((s, i) => (
                <div key={i} className="bg-white/10 backdrop-blur-sm rounded-xl p-3 text-center">
                  <s.icon className="h-5 w-5 mx-auto mb-1 text-brand-turquoise" />
                  <p className="text-xl font-bold">{s.value}</p>
                  <p className="text-[10px] text-white/60">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Main Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full justify-start bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-1 gap-1 overflow-x-auto">
              {[
                { value: 'general', label: t('generalInfo'), icon: Building2 },
                { value: 'users', label: t('users'), icon: Users },
                { value: 'academic', label: t('academicStructure'), icon: BookOpen },
                { value: 'billing', label: t('billingSubscription'), icon: CreditCard },
                { value: 'activity', label: isRTL ? 'سجل النشاط' : 'Activity Logs', icon: Activity },
              ].map((tab) => (
                <TabsTrigger
                  key={tab.value}
                  value={tab.value}
                  className="flex items-center gap-1.5 rounded-lg text-sm data-[state=active]:bg-brand-navy data-[state=active]:text-white whitespace-nowrap"
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {/* ─── Tab: General Info ─── */}
            <TabsContent value="general" className="mt-4">
              <Card className="card-nassaq">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="font-cairo">{isRTL ? 'المعلومات العامة' : 'General Information'}</CardTitle>
                  {!editMode ? (
                    <Button size="sm" variant="outline" onClick={() => setEditMode(true)} className="rounded-xl">
                      <Edit className="h-4 w-4 me-1.5" />
                      {t('edit')}
                    </Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => setEditMode(false)} className="rounded-xl">
                        <X className="h-4 w-4 me-1.5" />
                        {t('cancel')}
                      </Button>
                      <Button size="sm" className="bg-brand-turquoise hover:bg-brand-turquoise/90 rounded-xl" onClick={handleSave} disabled={saving}>
                        {saving ? <Loader2 className="h-4 w-4 animate-spin me-1.5" /> : <Save className="h-4 w-4 me-1.5" />}
                        {t('save')}
                      </Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* School ID (non-editable) */}
                    <InfoField
                      label={t('schoolCode')}
                      value={school?.code}
                      icon={<Hash className="h-4 w-4 text-slate-400" />}
                    />
                    <InfoField
                      label={t('schoolId')}
                      value={school?.id}
                      icon={<Shield className="h-4 w-4 text-slate-400" />}
                      mono
                    />
                    <InfoField
                      label={t('createdAt')}
                      value={school?.created_at ? new Date(school.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-GB') : '—'}
                      icon={<Calendar className="h-4 w-4 text-slate-400" />}
                    />
                    <InfoField
                      label={t('status2')}
                      value={
                        <Badge className={`${statusCfg.badge} border text-xs`}>
                          <div className={`w-1.5 h-1.5 rounded-full ${statusCfg.color} me-1.5`} />
                          {isRTL ? statusCfg.label : statusCfg.label_en}
                        </Badge>
                      }
                    />

                    {/* Editable Fields */}
                    <EditableField
                      label={t('schoolNameArabic')}
                      value={editData.name}
                      displayValue={school?.name}
                      editMode={editMode}
                      onChange={(v) => setEditData(d => ({ ...d, name: v }))}
                    />
                    <EditableField
                      label={t('schoolNameEnglish2')}
                      value={editData.name_en}
                      displayValue={school?.name_en}
                      editMode={editMode}
                      onChange={(v) => setEditData(d => ({ ...d, name_en: v }))}
                    />
                    <EditableField
                      label={t('email2')}
                      value={editData.email}
                      displayValue={school?.email}
                      editMode={editMode}
                      onChange={(v) => setEditData(d => ({ ...d, email: v }))}
                      icon={<Mail className="h-4 w-4 text-slate-400" />}
                    />
                    <EditableField
                      label={t('phone2')}
                      value={editData.phone}
                      displayValue={school?.phone}
                      editMode={editMode}
                      onChange={(v) => setEditData(d => ({ ...d, phone: v }))}
                      icon={<Phone className="h-4 w-4 text-slate-400" />}
                    />
                    <EditableField
                      label={t('city')}
                      value={editData.city}
                      displayValue={school?.city}
                      editMode={editMode}
                      onChange={(v) => setEditData(d => ({ ...d, city: v }))}
                      icon={<MapPin className="h-4 w-4 text-slate-400" />}
                    />
                    <EditableField
                      label={t('region2')}
                      value={editData.region}
                      displayValue={school?.region}
                      editMode={editMode}
                      onChange={(v) => setEditData(d => ({ ...d, region: v }))}
                    />
                    {/* Suspension Info */}
                    {school?.suspension_reason && (
                      <div className="col-span-full p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded-xl space-y-1">
                        <p className="text-sm font-semibold text-red-700 dark:text-red-400 flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4" />
                          {t('suspensionReason')}
                        </p>
                        <p className="text-sm text-red-600 dark:text-red-400">{school.suspension_reason}</p>
                        {school.suspended_at && (
                          <p className="text-xs text-red-500">
                            {new Date(school.suspended_at).toLocaleString(isRTL ? 'ar-SA' : 'en-GB')}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* ─── Credentials Card ─── */}
              {(() => {
                const principal = detail.principal_account;
                const hasCreds = detail.has_credentials;
                return (
                  <Card className="card-nassaq border-2 border-dashed border-brand-navy/20 dark:border-brand-navy/30">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between gap-3">
                        <CardTitle className="font-cairo flex items-center gap-2 text-brand-navy dark:text-brand-turquoise">
                          <Key className="h-5 w-5" />
                          {t('systemLoginCredentials')}
                        </CardTitle>
                        <Button
                          size="sm"
                          onClick={() => openCredForm(principal)}
                          className={`gap-2 text-sm font-cairo ${hasCreds
                            ? 'bg-brand-navy/10 text-brand-navy hover:bg-brand-navy hover:text-white dark:bg-brand-navy/20 dark:text-brand-turquoise dark:hover:bg-brand-navy dark:hover:text-white'
                            : 'bg-brand-navy text-white hover:bg-brand-navy/90'
                          }`}
                          variant="ghost"
                        >
                          {hasCreds
                            ? <><RotateCcw className="h-4 w-4" />{t('updateCredentials')}</>
                            : <><UserPlus className="h-4 w-4" />{t('createPrincipalAccount')}</>
                          }
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {hasCreds && principal ? (
                        <div className="space-y-4">
                          <div className="flex items-center gap-3 p-3 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 rounded-xl">
                            <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-900/40 flex items-center justify-center flex-shrink-0">
                              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-300 font-cairo">
                                {t('accountActive')}
                              </p>
                              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                                {t('principalAccountExistsAndIsAccessible')}
                              </p>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-1">
                              <p className="text-xs text-slate-500 font-medium">{t('fullName')}</p>
                              <div className="flex items-center gap-2 p-2.5 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
                                <span className="text-sm font-medium text-slate-800 dark:text-white flex-1">{principal.full_name || '—'}</span>
                              </div>
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-slate-500 font-medium">{t('email2')}</p>
                              <div className="flex items-center gap-2 p-2.5 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
                                <span className="text-sm font-mono text-slate-800 dark:text-white flex-1 truncate">{principal.email}</span>
                                <button onClick={() => copyToClipboard(principal.email, isRTL ? 'البريد' : 'email')} className="flex-shrink-0 text-slate-400 hover:text-brand-navy transition-colors">
                                  <Copy className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-slate-500 font-medium">{t('accountStatus')}</p>
                              <div className="flex items-center gap-2 p-2.5 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
                                <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border ${principal.is_active !== false ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : 'bg-red-100 text-red-700 border-red-200'}`}>
                                  {principal.is_active !== false ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                                  {principal.is_active !== false ? (t('active')) : (t('suspended2'))}
                                </span>
                              </div>
                            </div>
                            <div className="space-y-1">
                              <p className="text-xs text-slate-500 font-medium">{isRTL ? 'تغيير كلمة المرور مطلوب' : 'Must Change Password'}</p>
                              <div className="flex items-center gap-2 p-2.5 bg-slate-50 dark:bg-slate-800/50 rounded-lg border border-slate-100 dark:border-slate-700">
                                <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border ${principal.must_change_password ? 'bg-amber-100 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                                  {principal.must_change_password ? <AlertTriangle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                                  {principal.must_change_password ? (t('yes')) : (t('no'))}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center py-8 text-center gap-3">
                          <div className="w-16 h-16 rounded-full bg-amber-50 dark:bg-amber-950/30 border-2 border-dashed border-amber-200 dark:border-amber-700 flex items-center justify-center">
                            <Lock className="h-7 w-7 text-amber-500" />
                          </div>
                          <div>
                            <p className="font-semibold text-slate-700 dark:text-white font-cairo">
                              {t('noLoginAccountConfigured')}
                            </p>
                            <p className="text-sm text-slate-500 mt-1">
                              {t('createAPrincipalAccountSoTheSchoolCanAccessTheSyst')}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Last result banner */}
                      {credResult && (
                        <div className="mt-4 p-4 bg-brand-navy/5 border border-brand-navy/20 rounded-xl space-y-3">
                          <p className="text-sm font-semibold text-brand-navy dark:text-brand-turquoise font-cairo flex items-center gap-2">
                            <Sparkles className="h-4 w-4" />
                            {credResult.is_new ? (t('accountCreatedSaveTheseCredentials')) : (isRTL ? 'تم تحديث بيانات الدخول' : 'Credentials Updated')}
                          </p>
                          <div className="space-y-2">
                            <div className="flex items-center gap-2 p-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                              <Mail className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                              <span className="text-sm font-mono flex-1">{credResult.email}</span>
                              <button onClick={() => copyToClipboard(credResult.email, 'email')} className="text-slate-400 hover:text-brand-navy"><Copy className="h-3.5 w-3.5" /></button>
                            </div>
                            {credResult.password_was_changed && credResult.temp_password && (
                              <div className="flex items-center gap-2 p-2 bg-white dark:bg-slate-800 rounded-lg border border-amber-200 dark:border-amber-700">
                                <Key className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
                                <span className="text-sm font-mono flex-1 tracking-wider">{credResult.temp_password}</span>
                                <button onClick={() => copyToClipboard(credResult.temp_password, isRTL ? 'كلمة المرور' : 'password')} className="text-slate-400 hover:text-amber-600"><Copy className="h-3.5 w-3.5" /></button>
                              </div>
                            )}
                          </div>
                          {credResult.password_was_changed && credResult.temp_password && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="w-full gap-2 mt-1 border-brand-navy/20 text-brand-navy hover:bg-brand-navy hover:text-white dark:text-brand-turquoise dark:border-brand-turquoise/30 dark:hover:bg-brand-turquoise dark:hover:text-white font-cairo"
                              onClick={() => {
                                const msg = `مرحباً،\n\nاليك بيانات حسابك على منصة نَسَّق | NASSAQ.\n\nالبريد الإلكتروني: ${credResult.email}\nكلمة المرور المؤقتة: ${credResult.temp_password}\n\nيرجى تسجيل الدخول عبر الرابط التالي:\n${window.location.origin}/login\n\nإذا واجهت أي مشكلة أثناء تسجيل الدخول أو احتجت إلى مساعدة، يرجى التواصل مع إدارة المنصة.\n\nنتمنى لك تجربة موفقة داخل منصة نَسَّق، ونسعد بمساهمتك في تطوير وتشغيل النظام.\n\nمع خالص التحية،\nإدارة منصة نَسَّق | NASSAQ`;
                                copyToClipboard(msg, isRTL ? 'رسالة الترحيب' : 'welcome message');
                              }}
                            >
                              <Copy className="h-4 w-4" />
                              {t('copyWelcomeMessageWithCredentials')}
                            </Button>
                          )}
                          <p className="text-xs text-slate-500">
                            {t('principalWillBePromptedToChangePasswordOnFirstLogi')}
                          </p>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })()}
            </TabsContent>

            {/* ─── Tab: Users ─── */}
            <TabsContent value="users" className="mt-4">
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo flex items-center gap-2">
                    <Users className="h-5 w-5 text-brand-navy" />
                    {isRTL ? `المستخدمون (${detail.users?.length || 0})` : `Users (${detail.users?.length || 0})`}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(!detail.users || detail.users.length === 0) ? (
                    <EmptyState icon={Users} message={t('noUsersFound')} />
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-slate-50 dark:bg-slate-800/50">
                            <th className="text-start p-3 font-medium text-slate-500">{t('name')}</th>
                            <th className="text-start p-3 font-medium text-slate-500">{t('email')}</th>
                            <th className="text-center p-3 font-medium text-slate-500">{t('role')}</th>
                            <th className="text-center p-3 font-medium text-slate-500">{t('status2')}</th>
                            <th className="text-center p-3 font-medium text-slate-500">{isRTL ? 'تاريخ الإنشاء' : 'Created'}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.users.map((user) => {
                            const roleCfg = ROLE_LABELS[user.role] || { ar: user.role, color: 'bg-slate-100 text-slate-700' };
                            return (
                              <tr key={user.id} className="border-t border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/20 transition-colors">
                                <td className="p-3">
                                  <div className="flex items-center gap-2">
                                    <div className="w-8 h-8 rounded-full bg-brand-navy/10 flex items-center justify-center flex-shrink-0">
                                      <span className="text-xs font-bold text-brand-navy">{user.full_name?.charAt(0) || '?'}</span>
                                    </div>
                                    <span className="font-medium text-slate-800 dark:text-white">{user.full_name || '—'}</span>
                                  </div>
                                </td>
                                <td className="p-3 text-slate-500 text-xs">{user.email}</td>
                                <td className="p-3 text-center">
                                  <Badge className={`text-[10px] ${roleCfg.color}`}>{roleCfg.ar}</Badge>
                                </td>
                                <td className="p-3 text-center">
                                  {user.is_active ? (
                                    <span className="inline-flex items-center gap-1 text-emerald-600 text-xs"><CheckCircle2 className="h-3.5 w-3.5" />{t('active')}</span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 text-red-500 text-xs"><XCircle className="h-3.5 w-3.5" />{isRTL ? 'موقوف' : 'Inactive'}</span>
                                  )}
                                </td>
                                <td className="p-3 text-center text-xs text-slate-400">
                                  {user.created_at ? new Date(user.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-GB') : '—'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* ─── Tab: Academic Structure ─── */}
            <TabsContent value="academic" className="mt-4">
              <div className="space-y-4">
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="font-cairo flex items-center gap-2">
                      <GraduationCap className="h-5 w-5 text-brand-turquoise" />
                      {isRTL ? `الطلاب (${detail.students?.length || 0})` : `Students (${detail.students?.length || 0})`}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(!detail.students || detail.students.length === 0) ? (
                      <EmptyState icon={GraduationCap} message={isRTL ? 'لا يوجد طلاب' : 'No students found'} />
                    ) : (
                      <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-800">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-slate-50 dark:bg-slate-800/50">
                              <th className="text-start p-3 font-medium text-slate-500">{t('name')}</th>
                              <th className="text-center p-3 font-medium text-slate-500">{t('grade')}</th>
                              <th className="text-center p-3 font-medium text-slate-500">{t('status2')}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.students.slice(0, 50).map((s) => (
                              <tr key={s.id} className="border-t border-slate-50 dark:border-slate-800/50">
                                <td className="p-3 font-medium text-slate-800 dark:text-white">{s.full_name || s.name || '—'}</td>
                                <td className="p-3 text-center text-slate-500">{s.grade_level || s.grade || '—'}</td>
                                <td className="p-3 text-center">
                                  {s.is_active !== false ? (
                                    <span className="text-emerald-600 text-xs">{t('active')}</span>
                                  ) : (
                                    <span className="text-red-500 text-xs">{t('inactive')}</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="font-cairo flex items-center gap-2">
                      <BookOpen className="h-5 w-5 text-brand-purple" />
                      {isRTL ? `الفصول (${detail.classes?.length || 0})` : `Classes (${detail.classes?.length || 0})`}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(!detail.classes || detail.classes.length === 0) ? (
                      <EmptyState icon={BookOpen} message={t('noClassesFound2')} />
                    ) : (
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                        {detail.classes.map((cls) => (
                          <div key={cls.id} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30 text-center">
                            <p className="font-semibold text-brand-navy dark:text-brand-turquoise text-sm">{cls.name || cls.class_name || '—'}</p>
                            <p className="text-xs text-slate-400 mt-0.5">{cls.grade_level || cls.grade || ''}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            {/* ─── Tab: Billing & Subscription ─── */}
            <TabsContent value="billing" className="mt-4">
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo flex items-center gap-2">
                    <CreditCard className="h-5 w-5 text-brand-purple" />
                    {t('billingSubscription')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-gradient-to-br from-brand-navy/5 to-brand-navy/10 border border-brand-navy/20 space-y-3">
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">{t('subscriptionPlan')}</p>
                      <p className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise">{isRTL ? 'غير محدد' : 'Not Set'}</p>
                      <p className="text-xs text-slate-400">{t('subscriptionNotConfiguredYet')}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-gradient-to-br from-brand-turquoise/5 to-brand-turquoise/10 border border-brand-turquoise/20 space-y-3">
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">{t('studentCapacity')}</p>
                      <p className="text-2xl font-bold text-brand-turquoise">{school?.student_capacity || '—'}</p>
                      <p className="text-xs text-slate-400">
                        {isRTL ? `مستخدم: ${detail.stats?.total_students || 0}` : `Used: ${detail.stats?.total_students || 0}`}
                      </p>
                    </div>
                    <div className="col-span-full p-4 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 text-center">
                      <CreditCard className="h-8 w-8 mx-auto text-amber-500 mb-2" />
                      <p className="text-sm text-amber-700 dark:text-amber-400 font-medium">
                        {t('billingSystemUnderDevelopment')}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ─── Tab: Activity Logs ─── */}
            <TabsContent value="activity" className="mt-4">
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo flex items-center gap-2">
                    <Activity className="h-5 w-5 text-brand-navy" />
                    {isRTL ? 'سجل النشاط' : 'Activity Logs'}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {(!detail.audit_logs || detail.audit_logs.length === 0) ? (
                    <EmptyState icon={Activity} message={isRTL ? 'لا يوجد سجل نشاط' : 'No activity logs found'} />
                  ) : (
                    <div className="space-y-2">
                      {detail.audit_logs.map((log, idx) => {
                        const actionCfg = ACTION_LABELS[log.action] || { ar: log.action, icon: Activity, color: 'text-slate-500' };
                        const ActionIcon = actionCfg.icon;
                        return (
                          <div key={idx} className="flex items-start gap-3 p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                            <div className={`mt-0.5 p-2 rounded-lg bg-slate-100 dark:bg-slate-800 ${actionCfg.color}`}>
                              <ActionIcon className="h-4 w-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2 flex-wrap">
                                <p className="text-sm font-medium text-slate-800 dark:text-white">{actionCfg.ar}</p>
                                <span className="text-xs text-slate-400 flex-shrink-0">
                                  {log.timestamp ? new Date(log.timestamp).toLocaleString(isRTL ? 'ar-SA' : 'en-GB') : ''}
                                </span>
                              </div>
                              {log.actor_email && (
                                <p className="text-xs text-slate-400 mt-0.5">{t('by')} {log.actor_email}</p>
                              )}
                              {log.new_values?.reason && (
                                <p className="text-xs text-slate-500 mt-1 bg-slate-100 dark:bg-slate-800 rounded p-1.5">
                                  {t('reason')} {log.new_values.reason}
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

        </div>
      </div>

      {/* Credentials Dialog */}
      <Dialog open={credFormOpen} onOpenChange={(o) => { setCredFormOpen(o); if (!o) { setShowPassword(false); } }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2 text-brand-navy dark:text-brand-turquoise">
              <Key className="h-5 w-5" />
              {detail?.has_credentials
                ? (t('updateSchoolLoginCredentials'))
                : (t('createSchoolPrincipalAccount'))
              }
            </DialogTitle>
            <DialogDescription>
              {detail?.has_credentials
                ? (t('updateTheEmailAndorPasswordForTheSchoolPrincipalAc'))
                : (t('createANewAccountForTheSchoolPrincipalToAccessTheS'))
              }
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Email */}
            <div className="space-y-1.5">
              <Label className="text-sm font-medium font-cairo">
                {isRTL ? 'البريد الإلكتروني' : 'Email Address'} <span className="text-red-500">*</span>
              </Label>
              <div className="relative">
                <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  type="email"
                  dir="ltr"
                  placeholder="principal@school.edu"
                  value={credForm.email}
                  onChange={(e) => setCredForm(f => ({ ...f, email: e.target.value }))}
                  className="ps-9 rounded-xl font-mono"
                />
              </div>
            </div>

            {/* Name */}
            <div className="space-y-1.5">
              <Label className="text-sm font-medium font-cairo">
                {t('fullName')}
              </Label>
              <Input
                placeholder={t('principalFullName')}
                value={credForm.name}
                onChange={(e) => setCredForm(f => ({ ...f, name: e.target.value }))}
                className="rounded-xl"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium font-cairo">
                  {detail?.has_credentials
                    ? (t('newPasswordLeaveBlankToKeepCurrent'))
                    : (t('password'))
                  }
                  {!detail?.has_credentials && <span className="text-slate-400 ms-1">({t('autogeneratedIfBlank')})</span>}
                </Label>
                <button
                  type="button"
                  onClick={generatePassword}
                  className="text-xs text-brand-turquoise hover:underline flex items-center gap-1 font-cairo"
                >
                  <Sparkles className="h-3 w-3" />
                  {t('generate')}
                </button>
              </div>
              <div className="relative">
                <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  type={showPassword ? 'text' : 'password'}
                  dir="ltr"
                  placeholder={isRTL ? '••••••••••••' : '••••••••••••'}
                  value={credForm.password}
                  onChange={(e) => setCredForm(f => ({ ...f, password: e.target.value }))}
                  className="ps-9 pe-10 rounded-xl font-mono tracking-wider"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute end-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Confirm Password — only if password has value */}
            {credForm.password && (
              <div className="space-y-1.5">
                <Label className="text-sm font-medium font-cairo">
                  {t('confirmPassword')} <span className="text-red-500">*</span>
                </Label>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  dir="ltr"
                  placeholder={t('reenterPassword')}
                  value={credForm.confirmPassword}
                  onChange={(e) => setCredForm(f => ({ ...f, confirmPassword: e.target.value }))}
                  className={`rounded-xl font-mono tracking-wider ${credForm.password && credForm.confirmPassword && credForm.password !== credForm.confirmPassword ? 'border-red-400 focus:ring-red-300' : ''}`}
                />
                {credForm.password && credForm.confirmPassword && credForm.password !== credForm.confirmPassword && (
                  <p className="text-xs text-red-500 font-cairo">{t('passwordsDoNotMatch')}</p>
                )}
              </div>
            )}
          </div>

          <DialogFooter className="flex-row-reverse gap-2">
            <Button variant="outline" onClick={() => setCredFormOpen(false)} disabled={credLoading}>
              {t('cancel')}
            </Button>
            <Button
              onClick={handleSaveCredentials}
              disabled={credLoading || !credForm.email || (credForm.password && credForm.password !== credForm.confirmPassword)}
              className="bg-brand-navy text-white hover:bg-brand-navy/90 gap-2"
            >
              {credLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {detail?.has_credentials ? (isRTL ? 'تحديث' : 'Update') : (t('createAccount'))}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suspend Dialog */}
      <Dialog open={suspendDialog} onOpenChange={(o) => { setSuspendDialog(o); if (!o) setActionReason(''); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              {t('suspendSchool')}
            </DialogTitle>
            <DialogDescription>
              {isRTL
                ? `هل أنت متأكد من تعليق مدرسة "${school?.name}"؟ سيتم تعطيل جميع الحسابات المرتبطة بها.`
                : `Are you sure you want to suspend "${school?.name_en || school?.name}"? All associated accounts will be disabled.`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Label className="text-sm font-medium">{t('reasonForSuspensionRequired')}</Label>
            <Textarea
              placeholder={t('enterReasonForSuspension')}
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              rows={3}
              className="rounded-xl"
            />
          </div>
          <DialogFooter className="flex-row-reverse gap-2">
            <Button variant="outline" onClick={() => setSuspendDialog(false)} disabled={actionLoading}>
              {t('cancel')}
            </Button>
            <Button variant="destructive" onClick={handleSuspend} disabled={actionLoading || !actionReason.trim()}>
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Pause className="h-4 w-4 me-2" />}
              {t('suspendSchool')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Activate Dialog */}
      <Dialog open={activateDialog} onOpenChange={(o) => { setActivateDialog(o); if (!o) setActionReason(''); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-600">
              <Play className="h-5 w-5" />
              {t('activateSchool')}
            </DialogTitle>
            <DialogDescription>
              {isRTL
                ? `تأكيد تفعيل مدرسة "${school?.name}" وإعادة جميع الحسابات للعمل.`
                : `Confirm activating "${school?.name_en || school?.name}" and restoring all accounts.`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Label className="text-sm font-medium">{t('reasonForActivationRequired')}</Label>
            <Textarea
              placeholder={t('enterReasonForActivation')}
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              rows={3}
              className="rounded-xl"
            />
          </div>
          <DialogFooter className="flex-row-reverse gap-2">
            <Button variant="outline" onClick={() => setActivateDialog(false)} disabled={actionLoading}>
              {t('cancel')}
            </Button>
            <Button className="bg-emerald-500 hover:bg-emerald-600" onClick={handleActivate} disabled={actionLoading || !actionReason.trim()}>
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Play className="h-4 w-4 me-2" />}
              {t('activateSchool')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Sidebar>
  );
}

function InfoField({ label, value, icon, mono }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-slate-500 flex items-center gap-1.5">
        {icon}{label}
      </label>
      <div className={`p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 text-sm ${mono ? 'font-mono text-xs' : ''}`}>
        {value || <span className="text-slate-400">—</span>}
      </div>
    </div>
  );
}

function EditableField({ label, value, displayValue, editMode, onChange, icon }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-slate-500 flex items-center gap-1.5">
        {icon}{label}
      </label>
      {editMode ? (
        <Input
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="rounded-xl h-9"
        />
      ) : (
        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 text-sm">
          {displayValue || <span className="text-slate-400">—</span>}
        </div>
      )}
    </div>
  );
}

function EmptyState({ icon: Icon, message }) {
  return (
    <div className="text-center py-12">
      <Icon className="h-12 w-12 mx-auto text-slate-200 dark:text-slate-700 mb-3" />
      <p className="text-slate-400 text-sm">{message}</p>
    </div>
  );
}
