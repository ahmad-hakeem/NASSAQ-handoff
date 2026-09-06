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
  ChevronRight, RefreshCw, AlertTriangle, Loader2, ArrowRight, ArrowLeft
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
import { schoolsService } from '../services';

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
    const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%';
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
      const data = await schoolsService.fetchSchoolDetail(api, schoolId);
      setDetail(data);
      setEditData({
        name: data.school?.name || '',
        name_en: data.school?.name_en || '',
        email: data.school?.email || '',
        phone: data.school?.phone || '',
        city: data.school?.city || '',
        region: data.school?.region || '',
        address: data.school?.address || '',
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
      await schoolsService.updateSchool(api, schoolId, editData);
      toast.success(t('changesSaved') || (isRTL ? 'تم حفظ التعديلات بنجاح' : 'Changes saved successfully'));
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
      const resData = await schoolsService.saveSchoolCredentials(api, schoolId, payload);
      setCredResult(resData);
      toast.success(resData.is_new
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
    const reason = actionReason.trim() || (isRTL ? 'إيقاف إداري مؤقت' : 'Temporary administrative suspension');
    setActionLoading(true);
    try {
      await schoolsService.suspendSchool(api, schoolId, reason);
      setDetail(prev => prev ? { ...prev, school: { ...prev.school, status: 'suspended' } } : prev);
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
    const reason = actionReason.trim() || (isRTL ? 'إعادة تفعيل المدرسة' : 'Reactivate school');
    setActionLoading(true);
    try {
      await schoolsService.activateSchool(api, schoolId, reason);
      setDetail(prev => prev ? { ...prev, school: { ...prev.school, status: 'active' } } : prev);
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
        <div className="min-h-screen flex items-center justify-center bg-slate-50/70 dark:bg-slate-950 font-tajawal">
          <div className="text-center space-y-3 p-8">
            <div className="w-12 h-12 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-center mx-auto text-[#1C3D74] dark:text-[#46C1BE]">
              <Loader2 className="h-6 w-6 animate-spin text-[#1C3D74] dark:text-[#46C1BE]" />
            </div>
            <p className="font-cairo font-bold text-xs text-slate-600 dark:text-slate-300">
              {t('loading') || (isRTL ? 'جاري تحميل بيانات المدرسة...' : 'Loading school profile...')}
            </p>
          </div>
        </div>
      </Sidebar>
    );
  }

  if (error || !detail) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50/70 dark:bg-slate-950 font-tajawal" dir={isRTL ? 'rtl' : 'ltr'}>
          <Card className="max-w-md w-full rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
            <CardContent className="p-8 text-center space-y-5">
              <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-950/60 flex items-center justify-center mx-auto text-rose-600 border border-rose-100 dark:border-rose-900/60">
                <AlertTriangle className="h-7 w-7" />
              </div>
              <div className="space-y-1">
                <p className="font-cairo text-base font-extrabold text-slate-900 dark:text-white">
                  {t('failedToLoadSchoolData') || (isRTL ? 'تعذر تحميل بيانات المدرسة' : 'Failed to load school data')}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {isRTL ? 'يرجى التحقق من اتصالك بالإنترنت أو إعادة المحاولة.' : 'Please check your connection and try again.'}
                </p>
              </div>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-2.5 pt-2">
                <Button onClick={() => fetchDetail()} className="w-full sm:w-auto rounded-xl font-bold bg-[#1C3D74] hover:bg-[#152e57] text-white text-xs h-10 px-4 gap-2">
                  <RefreshCw className="h-3.5 w-3.5" />
                  <span>{t('retry') || (isRTL ? 'إعادة المحاولة' : 'Retry')}</span>
                </Button>
                <Button variant="outline" onClick={() => navigate('/admin/schools')} className="w-full sm:w-auto rounded-xl font-bold border-slate-200 dark:border-slate-700 text-xs h-10">
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
    { value: 'users', label: t('users') || (isRTL ? 'المستخدمون' : 'Users'), icon: Users, count: detail.stats?.total_users },
    { value: 'academic', label: t('academicStructure') || (isRTL ? 'الهيكل الأكاديمي' : 'Academic Structure'), icon: BookOpen, count: detail.stats?.total_classes },
    { value: 'billing', label: t('billingSubscription') || (isRTL ? 'الاشتراك والفواتير' : 'Billing & Tier'), icon: CreditCard },
    { value: 'activity', label: isRTL ? 'سجل النشاط' : 'Activity Logs', icon: Activity, count: detail.audit_logs?.length },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-slate-50/70 dark:bg-slate-950 font-tajawal text-slate-900 dark:text-slate-100" dir={isRTL ? 'rtl' : 'ltr'} style={{ direction: isRTL ? 'rtl' : 'ltr' }}>
        <div className="max-w-7xl mx-auto p-5 sm:p-7 lg:p-9 space-y-7">

          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <button
              onClick={() => navigate('/admin/schools')}
              className="hover:text-[#1C3D74] dark:hover:text-[#46C1BE] transition-colors flex items-center gap-1 font-bold"
            >
              <span>{t('schoolsManagement') || (isRTL ? 'إدارة المدارس' : 'Schools')}</span>
            </button>
            <ChevronRight className={`h-3.5 w-3.5 text-slate-400 ${isRTL ? 'rotate-180' : ''}`} />
            <span className="text-slate-800 dark:text-slate-200 font-bold truncate max-w-[200px] sm:max-w-md">{school?.name}</span>
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

          {/* 2. Structured Tabs Bar - Refined Segmented Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <div className="overflow-x-auto pb-1">
              <TabsList className="bg-slate-100/90 dark:bg-slate-800/60 p-1.5 rounded-2xl border border-slate-200/70 dark:border-slate-700/60 inline-flex gap-1 h-auto min-w-max">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <TabsTrigger
                      key={tab.value}
                      value={tab.value}
                      className="flex items-center gap-2 rounded-xl text-xs font-bold py-2.5 px-4 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-[#1C3D74] dark:data-[state=active]:text-[#46C1BE] data-[state=active]:shadow-xs transition-all"
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span>{tab.label}</span>
                      {typeof tab.count === 'number' && (
                        <span className="ms-1 px-2 py-0.5 rounded-md text-[10px] font-mono bg-slate-200/80 dark:bg-slate-700 text-slate-700 dark:text-slate-300 data-[state=active]:bg-[#1C3D74]/10 data-[state=active]:text-[#1C3D74] dark:data-[state=active]:bg-[#46C1BE]/20 dark:data-[state=active]:text-[#46C1BE]">
                          {tab.count}
                        </span>
                      )}
                    </TabsTrigger>
                  );
                })}
              </TabsList>
            </div>

            {/* Tab 1: General Info */}
            <TabsContent value="general" className="mt-0 focus-visible:outline-none">
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
            <TabsContent value="users" className="mt-0 focus-visible:outline-none">
              <SchoolUsersTab
                users={detail.users || []}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 3: Academic Structure */}
            <TabsContent value="academic" className="mt-0 focus-visible:outline-none">
              <AcademicStructureTab
                students={detail.students || []}
                classes={detail.classes || []}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 4: Billing & Tier */}
            <TabsContent value="billing" className="mt-0 focus-visible:outline-none">
              <BillingSubscriptionTab
                school={school}
                stats={detail.stats}
                isRTL={isRTL}
                t={t}
              />
            </TabsContent>

            {/* Tab 5: Activity Logs */}
            <TabsContent value="activity" className="mt-0 focus-visible:outline-none">
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
