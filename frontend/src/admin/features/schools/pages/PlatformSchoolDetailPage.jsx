import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { usePlatformAdminSchoolPreview } from '@/shared/hooks/usePlatformAdminSchoolPreview';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';
import {
  Building2, Users, BookOpen, Activity, CreditCard,
  ChevronRight, RefreshCw, AlertTriangle, Loader2
} from 'lucide-react';

// Sub-components
import SchoolDetailHeader from '../components/detail/SchoolDetailHeader';
import GeneralInfoTab from '../components/detail/GeneralInfoTab';
import SchoolUsersTab from '../components/detail/SchoolUsersTab';
import AcademicStructureTab from '../components/detail/AcademicStructureTab';
import BillingSubscriptionTab from '../components/detail/BillingSubscriptionTab';
import SchoolActivityTab from '../components/detail/SchoolActivityTab';
import SchoolCredentialsDialog from '../components/detail/SchoolCredentialsDialog';
import SchoolActionDialogs from '../components/SchoolActionDialogs';

export default function PlatformSchoolDetailPage() {
  const { schoolId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { api } = useAuth();
  const { openPrincipalDashboard, canOpenPrincipalDashboard } = usePlatformAdminSchoolPreview();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activeTab, setActiveTab] = useState('general');

  // Edit general info state
  const [editMode, setEditMode] = useState(false);
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);

  // Suspend & Activate state
  const [suspendDialog, setSuspendDialog] = useState(null);
  const [activateDialog, setActivateDialog] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Principal Credentials state
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
      nassaqError(t('failedToLoadSchoolData') || (isRTL ? 'فشل تحميل بيانات المدرسة' : 'Failed to load school data'));
    } finally {
      setLoading(false);
    }
  }, [api, schoolId, isRTL, nassaqError, t]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/schools/${schoolId}`, editData);
      toast.success(t('changesSaved') || (isRTL ? 'تم حفظ التعديلات بنجاح' : 'Changes saved'));
      setEditMode(false);
      fetchDetail();
    } catch (err) {
      nassaqError(t('failedToSaveChanges') || (isRTL ? 'فشل حفظ التعديلات' : 'Failed to save changes'));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveCredentials = async () => {
    if (!credForm.email.trim()) {
      nassaqError(t('emailIsRequired') || (isRTL ? 'البريد الإلكتروني مطلوب' : 'Email is required'));
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(credForm.email)) {
      nassaqError(t('invalidEmailFormat') || (isRTL ? 'صيغة البريد الإلكتروني غير صحيحة' : 'Invalid email format'));
      return;
    }
    if (credForm.password && credForm.password !== credForm.confirmPassword) {
      nassaqError(t('passwordsDoNotMatch2') || (isRTL ? 'كلمات المرور غير متطابقة' : 'Passwords do not match'));
      return;
    }
    if (credForm.password && credForm.password.length < 8) {
      nassaqError(t('passwordMustBeAtLeast8Characters') || (isRTL ? 'يجب أن تتكون كلمة المرور من 8 خانات على الأقل' : 'Password must be at least 8 characters'));
      return;
    }

    setCredLoading(true);
    try {
      const payload = { email: credForm.email, name: credForm.name || undefined };
      if (credForm.password) payload.password = credForm.password;
      const res = await api.post(`/schools/${schoolId}/credentials`, payload);
      setCredResult(res.data);
      toast.success(res.data.is_new
        ? (t('principalAccountCreatedSuccessfully') || (isRTL ? 'تم إنشاء حساب المدير بنجاح' : 'Principal account created'))
        : (t('credentialsUpdatedSuccessfully') || (isRTL ? 'تم تحديث بيانات الدخول بنجاح' : 'Credentials updated'))
      );
      setCredFormOpen(false);
      fetchDetail();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (t('failedToSaveCredentials') || (isRTL ? 'فشل حفظ بيانات الدخول' : 'Failed to save credentials')));
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
      nassaqError(t('reasonIsRequired') || (isRTL ? 'سبب الإيقاف مطلوب' : 'Reason is required'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${schoolId}/suspend`, { reason: actionReason });
      toast.success(t('schoolSuspendedSuccessfully') || (isRTL ? 'تم إيقاف المدرسة بنجاح' : 'School suspended'));
      setSuspendDialog(null);
      setActionReason('');
      fetchDetail();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (t('failedToSuspend') || (isRTL ? 'فشل إيقاف المدرسة' : 'Failed to suspend school')));
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivate = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired2') || (isRTL ? 'سبب التفعيل مطلوب' : 'Activation note is required'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${schoolId}/activate`, { reason: actionReason });
      toast.success(t('schoolActivatedSuccessfully') || (isRTL ? 'تم تفعيل المدرسة بنجاح' : 'School activated'));
      setActivateDialog(null);
      setActionReason('');
      fetchDetail();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (t('failedToActivate') || (isRTL ? 'فشل تفعيل المدرسة' : 'Failed to activate school')));
    } finally {
      setActionLoading(false);
    }
  };

  const handleEnterDashboard = () => {
    if (!detail?.school) return;
    openPrincipalDashboard(detail.school);
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center bg-slate-50/70 dark:bg-slate-950">
          <div className="text-center space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-[#46C1BE] mx-auto" />
            <p className="font-cairo font-bold text-slate-700 dark:text-slate-300">
              {t('loading') || (isRTL ? 'جاري تحميل تفاصيل المدرسة...' : 'Loading school details...')}
            </p>
          </div>
        </div>
      </Sidebar>
    );
  }

  if (error || !detail) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50/70 dark:bg-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
          <Card className="max-w-md w-full rounded-3xl border-slate-200 dark:border-slate-800 shadow-xl bg-white dark:bg-slate-900">
            <CardContent className="p-8 text-center space-y-5">
              <div className="w-14 h-14 rounded-2xl bg-rose-100 dark:bg-rose-950/60 flex items-center justify-center mx-auto text-rose-600">
                <AlertTriangle className="h-7 w-7" />
              </div>
              <p className="font-cairo text-lg font-black text-slate-900 dark:text-white">
                {t('failedToLoadSchoolData') || (isRTL ? 'تعذر تحميل بيانات المدرسة' : 'Failed to load school data')}
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                <Button onClick={() => fetchDetail()} className="w-full sm:w-auto rounded-xl font-bold bg-[#1C3D74] text-white">
                  <RefreshCw className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
                  <span>{t('retry') || (isRTL ? 'إعادة المحاولة' : 'Retry')}</span>
                </Button>
                <Button variant="outline" onClick={() => navigate('/admin/schools')} className="w-full sm:w-auto rounded-xl font-bold">
                  <span>{t('schoolsManagement') || (isRTL ? 'العودة للمدارس' : 'Back to Schools')}</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </Sidebar>
    );
  }

  const school = detail.school;

  const tabs = [
    { value: 'general', label: t('generalInfo') || (isRTL ? 'المعلومات العامة' : 'General Info'), icon: Building2 },
    { value: 'users', label: t('users') || (isRTL ? 'المستخدمون' : 'Users'), icon: Users },
    { value: 'academic', label: t('academicStructure') || (isRTL ? 'الهيكل الأكاديمي' : 'Academic Structure'), icon: BookOpen },
    { value: 'billing', label: t('billingSubscription') || (isRTL ? 'الاشتراك والسعة' : 'Billing & Tier'), icon: CreditCard },
    { value: 'activity', label: isRTL ? 'سجل النشاط' : 'Activity Logs', icon: Activity },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-slate-50/70 dark:bg-slate-950 font-tajawal" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">

          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <button
              onClick={() => navigate('/admin/schools')}
              className="hover:text-[#1C3D74] dark:hover:text-[#46C1BE] transition-colors"
            >
              {t('schoolsManagement') || (isRTL ? 'إدارة المدارس' : 'Schools Management')}
            </button>
            <ChevronRight className={`h-3.5 w-3.5 ${isRTL ? 'rotate-180' : ''}`} />
            <span className="text-slate-900 dark:text-white font-bold">{school?.name}</span>
          </div>

          {/* 1. Header Banner & Quick Stats */}
          <SchoolDetailHeader
            school={school}
            stats={detail.stats}
            onRefresh={() => fetchDetail()}
            onEnterDashboard={handleEnterDashboard}
            canEnterDashboard={canOpenPrincipalDashboard}
            onOpenSuspendDialog={() => setSuspendDialog(school)}
            onOpenActivateDialog={() => setActivateDialog(school)}
            isRTL={isRTL}
            t={t}
          />

          {/* 2. Structured Tabs Bar */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full justify-start bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-1 gap-1 overflow-x-auto shadow-2xs">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <TabsTrigger
                    key={tab.value}
                    value={tab.value}
                    className="flex items-center gap-2 rounded-xl text-xs font-bold py-2.5 px-4 data-[state=active]:bg-[#1C3D74] data-[state=active]:text-white dark:data-[state=active]:bg-[#1C3D74] whitespace-nowrap transition-all"
                  >
                    <Icon className="h-4 w-4" />
                    <span>{tab.label}</span>
                  </TabsTrigger>
                );
              })}
            </TabsList>

            {/* Tab 1: General Info */}
            <TabsContent value="general" className="mt-4">
              <GeneralInfoTab
                school={school}
                editMode={editMode}
                setEditMode={setEditMode}
                editData={editData}
                setEditData={setEditData}
                onSave={handleSave}
                saving={saving}
                principalAccount={detail.principal_account}
                hasCredentials={detail.has_credentials}
                onOpenCredForm={openCredForm}
                credResult={credResult}
                onCopy={copyToClipboard}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 2: Users List */}
            <TabsContent value="users" className="mt-4">
              <SchoolUsersTab
                users={detail.users || []}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 3: Academic Structure */}
            <TabsContent value="academic" className="mt-4">
              <AcademicStructureTab
                students={detail.students || []}
                classes={detail.classes || []}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 4: Billing & Tier */}
            <TabsContent value="billing" className="mt-4">
              <BillingSubscriptionTab
                school={school}
                stats={detail.stats}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 5: Activity Logs */}
            <TabsContent value="activity" className="mt-4">
              <SchoolActivityTab
                auditLogs={detail.audit_logs || []}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>
          </Tabs>

        </div>
      </div>

      {/* Credentials Dialog */}
      <SchoolCredentialsDialog
        open={credFormOpen}
        onOpenChange={setCredFormOpen}
        hasCredentials={detail.has_credentials}
        credForm={credForm}
        setCredForm={setCredForm}
        showPassword={showPassword}
        setShowPassword={setShowPassword}
        onGeneratePassword={generatePassword}
        onSaveCredentials={handleSaveCredentials}
        credLoading={credLoading}
        isRTL={isRTL}
        t={t}
      />

      {/* Suspend / Activate Dialogs */}
      <SchoolActionDialogs
        suspendDialogSchool={suspendDialog}
        onCloseSuspendDialog={() => setSuspendDialog(null)}
        onConfirmSuspend={handleSuspend}
        activateDialogSchool={activateDialog}
        onCloseActivateDialog={() => setActivateDialog(null)}
        onConfirmActivate={handleActivate}
        actionReason={actionReason}
        onChangeActionReason={setActionReason}
        actionLoading={actionLoading}
        isRTL={isRTL}
      />
    </Sidebar>
  );
}
