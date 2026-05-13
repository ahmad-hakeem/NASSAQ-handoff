import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { isGenericName } from '../components/GenericNameGuard';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { formatHijriDate } from '../utils/hijriDate';
import {
  User,
  Lock,
  Bell,
  Palette,
  Globe,
  Sun,
  Moon,
  Save,
  Camera,
  Mail,
  Phone,
  Shield,
  Eye,
  EyeOff,
  CheckCircle,
  AlertCircle,
  Loader2,
  Key,
  LogOut,
  Languages,
  Monitor,
  RefreshCw,
  Users,
  Building2,
  UserCog,
  Clock,
  Calendar,
  Fingerprint,
  History,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Check,
  X,
  AlertTriangle,
  Briefcase,
  MessageSquare,
  Download,
  ImageIcon,
} from 'lucide-react';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { ImageCropModal } from '../components/ui/ImageCropModal';
import MfaSecuritySection from '../components/mfa/MfaSecuritySection';

const PasswordStrength = ({ password, isRTL }) => {
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const checks = [
    { test: password.length >= 8, label: t('atLeast8Characters') },
    { test: /[A-Z]/.test(password), label: t('uppercaseLetter') },
    { test: /[a-z]/.test(password), label: t('lowercaseLetter') },
    { test: /[0-9]/.test(password), label: t('number') },
    { test: /[^A-Za-z0-9]/.test(password), label: t('specialCharacter') },
  ];
  const passed = checks.filter(c => c.test).length;
  const strength = passed === 0 ? 0 : passed <= 2 ? 1 : passed <= 3 ? 2 : passed <= 4 ? 3 : 4;
  const strengthLabels = isRTL
    ? ['', 'ضعيفة', 'مقبولة', 'جيدة', 'قوية جداً']
    : ['', 'Weak', 'Fair', 'Good', 'Very Strong'];
  const strengthColors = ['', 'bg-red-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500'];

  if (!password) return null;

  return (
    <div className="space-y-2 mt-3">
      <div className="flex gap-1.5">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className={`h-1.5 flex-1 rounded-full transition-all duration-500 ${i <= strength ? strengthColors[strength] : 'bg-muted/30'}`} />
        ))}
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-tajawal ${strength >= 3 ? 'text-emerald-600' : strength >= 2 ? 'text-amber-600' : 'text-red-600'}`}>
          {strengthLabels[strength]}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {checks.map((check, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {check.test ? <Check className="h-3 w-3 text-emerald-500" /> : <X className="h-3 w-3 text-muted-foreground/40" />}
            <span className={`text-[10px] font-tajawal ${check.test ? 'text-emerald-600' : 'text-muted-foreground/50'}`}>{check.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const SectionNav = ({ sections, active, onChange, isRTL }) => (
  <div className="flex flex-col gap-1.5">
    {sections.map(s => {
      const Icon = s.icon;
      const isActive = active === s.id;
      return (
        <button
          key={s.id}
          onClick={() => onChange(s.id)}
          className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-tajawal transition-all duration-300 text-start ${
            isActive
              ? 'bg-gradient-to-r from-brand-turquoise/10 to-brand-purple/5 text-brand-turquoise border border-brand-turquoise/20 shadow-sm'
              : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
          }`}
        >
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${
            isActive ? 'bg-brand-turquoise/15' : 'bg-muted/30'
          }`}>
            <Icon className={`h-4 w-4 ${isActive ? 'text-brand-turquoise' : ''}`} />
          </div>
          <div className="flex-1 min-w-0">
            <p className={`font-medium ${isActive ? 'text-foreground' : ''}`}>{s.label}</p>
            <p className="text-[10px] text-muted-foreground truncate">{s.desc}</p>
          </div>
          {isActive && (isRTL ? <ChevronLeft className="h-4 w-4 text-brand-turquoise flex-shrink-0" /> : <ChevronRight className="h-4 w-4 text-brand-turquoise flex-shrink-0" />)}
        </button>
      );
    })}
  </div>
);

const FieldGroup = ({ label, icon: Icon, children }) => (
  <div className="space-y-2">
    <Label className="flex items-center gap-2 text-sm font-tajawal">
      {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground" />}
      {label}
    </Label>
    {children}
  </div>
);

const NotificationRow = ({ title, desc, checked, onChange }) => (
  <div className="flex items-center justify-between p-4 rounded-xl border border-border/50 hover:bg-muted/20 transition-colors">
    <div>
      <p className="font-medium text-sm font-cairo">{title}</p>
      <p className="text-xs text-muted-foreground font-tajawal mt-0.5">{desc}</p>
    </div>
    <Switch checked={checked} onCheckedChange={onChange} />
  </div>
);

export const AccountSettingsPage = () => {
  const { t } = useTranslation();
  const { user, api, logout, refreshUser, updateToken } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark, language, setLanguage, theme, setTheme } = useTheme();
  const { nassaqError, nassaqInfo, nassaqSuccess } = useNassaqAlert();
  const { nassaqWarning } = useNassaqAlert();
  // §6.8 export + soft-delete local state. lastExportAt powers the
  // "exported X hours ago" chip (Hijri formatted) so the user can see
  // whether they still satisfy the 24h precondition before opening
  // the soft-delete dialog.
  const [lastExportAt, setLastExportAt] = useState(null);
  const [lastExportUrl, setLastExportUrl] = useState(null);
  const [lastExportExpiresAt, setLastExportExpiresAt] = useState(null);
  const [softDeleteOpen, setSoftDeleteOpen] = useState(false);
  const [softDeleteConfirmName, setSoftDeleteConfirmName] = useState('');
  // §6.8 — the soft-delete confirm step is gated by a fresh export
  // (within 24h) so the user always has a downloadable copy of their
  // data before the workspace is archived. Server re-validates the
  // same window and returns 412 if stale; the FE mirror keeps the
  // affordance honest (button greyed-out, reason inline).
  const softDeleteEligible = !!lastExportAt && (Date.now() - new Date(lastExportAt).getTime()) <= 24 * 60 * 60 * 1000;
  const nassaqErrorTop = nassaqError;

  // Task #200 §5.8 — Independent-Teacher (IT) gate for the three IT-only
  // sections (workspace, communication preferences, planned data export).
  const isIndependentTeacher = (user?.role || '').toLowerCase() === 'independent_teacher';

  const [saving, setSaving] = useState(false);
  // Task #172 P0 (review fix): honor a deep-link hash so other pages
  // (notably PlatformSettingsPage's MFA CTA → '/account/settings#security')
  // can land directly on the Security/MFA section. We read window.location
  // once on mount and validate against the known section ids below.
  const _initialSection = (() => {
    if (typeof window === 'undefined') return 'profile';
    const raw = (window.location.hash || '').replace(/^#/, '').toLowerCase();
    return ['profile', 'security', 'notifications', 'preferences', 'workspace', 'communication', 'export'].includes(raw)
      ? raw
      : 'profile';
  })();
  const [activeSection, setActiveSection] = useState(_initialSection);
  const [saveSuccess, setSaveSuccess] = useState(null);
  const [cropModalOpen, setCropModalOpen] = useState(false);

  // Task #172 P0 (review fix): also react to in-app hash changes so a user
  // already on /account/settings who clicks the deep-link is taken to the
  // requested section without a full reload.
  useEffect(() => {
    const onHash = () => {
      const raw = (window.location.hash || '').replace(/^#/, '').toLowerCase();
      if (['profile', 'security', 'notifications', 'preferences', 'workspace', 'communication', 'export'].includes(raw)) {
        setActiveSection(raw);
      }
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const [profile, setProfile] = useState({
    title: 'none', full_name: '', full_name_en: '', email: '', phone: '', avatar_url: '',
  });
  const [originalProfile, setOriginalProfile] = useState(null);

  const titleOptions = isRTL
    ? [
        { value: 'none', label: 'بدون لقب' }, { value: 'السيد', label: 'السيد' },
        { value: 'السيدة', label: 'السيدة' }, { value: 'الآنسة', label: 'الآنسة' },
        { value: 'الأستاذة', label: 'الأستاذة / السيدة' }, { value: 'دكتور', label: 'دكتور' },
        { value: 'أستاذ', label: 'أستاذ' }, { value: 'مهندس', label: 'مهندس' },
        { value: 'مستشار', label: 'مستشار' }, { value: 'معالي', label: 'معالي' },
        { value: 'سعادة', label: 'سعادة' }, { value: 'الشيخ', label: 'الشيخ' },
      ]
    : [
        { value: 'none', label: 'No Title' }, { value: 'Mr.', label: 'Mr.' },
        { value: 'Mrs.', label: 'Mrs.' }, { value: 'Miss', label: 'Miss' },
        { value: 'Ms.', label: 'Ms.' }, { value: 'Dr.', label: 'Dr.' },
        { value: 'Prof.', label: 'Prof.' }, { value: 'Eng.', label: 'Eng.' },
        { value: 'Consultant', label: 'Consultant' }, { value: 'His/Her Excellency', label: 'His/Her Excellency' },
        { value: 'Sheikh', label: 'Sheikh' },
      ];

  const [passwordData, setPasswordData] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [showPassword, setShowPassword] = useState({ current: false, new: false, confirm: false });

  const [notifications, setNotifications] = useState({
    email_notifications: true, sms_notifications: false, push_notifications: true,
    attendance_alerts: true, grade_alerts: true, behavior_alerts: true,
    announcement_alerts: true, weekly_digest: true,
  });

  const [preferences, setPreferences] = useState({
    language: 'ar', theme: 'light', time_format: '12h', date_format: 'dd/mm/yyyy', first_day_of_week: 'sunday',
  });

  // Task #200 §5.8 — IT workspace identity (mirrors WorkspaceSettingsPage,
  // same source of truth at /independent-teacher/workspace/settings).
  const [workspace, setWorkspace] = useState({ name_ar: '', name_en: '', logo_url: '' });
  const [workspaceLoaded, setWorkspaceLoaded] = useState(false);
  const [workspaceLogoCropOpen, setWorkspaceLogoCropOpen] = useState(false);

  // Task #200 §5.8 — IT communication preferences (default channel +
  // quiet hours). Persisted via the existing /users/me/preferences endpoint
  // under an `it_communication` blob.
  const [itCommunication, setItCommunication] = useState({
    default_channel: 'email',
    quiet_hours_start: '21:00',
    quiet_hours_end: '07:00',
  });

  const [showLogoutDialog, setShowLogoutDialog] = useState(false);
  const [showRoleSwitchDialog, setShowRoleSwitchDialog] = useState(false);
  const [userRoles, setUserRoles] = useState([]);
  const [switchingRole, setSwitchingRole] = useState(false);
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    if (user) {
      const p = {
        title: user.title || 'none',
        full_name: user.full_name || '',
        full_name_en: user.full_name_en || '',
        email: user.email || '',
        phone: user.phone || '',
        avatar_url: user.avatar_url || '',
      };
      setProfile(p);
      setOriginalProfile(p);
      setPreferences(prev => ({
        ...prev,
        language: user.preferred_language || 'ar',
        theme: user.preferred_theme || 'light',
      }));
    }
  }, [user]);

  useEffect(() => {
    const fetchExtras = async () => {
      try {
        const [rolesRes, notifRes, prefRes, sessRes] = await Promise.all([
          api.get('/user-roles/available').catch(() => ({ data: null })),
          api.get('/users/me/notifications').catch(() => ({ data: null })),
          api.get('/users/me/preferences').catch(() => ({ data: null })),
          api.get('/settings/sessions').catch(() => ({ data: [] })),
        ]);
        if (rolesRes.data?.roles) setUserRoles(rolesRes.data.roles);
        if (notifRes.data) setNotifications(prev => ({ ...prev, ...notifRes.data }));
        if (prefRes.data) {
          setPreferences(prev => ({ ...prev, ...prefRes.data }));
          // Task #200 §5.8 — IT communication blob lives under
          // `it_communication` on the same endpoint payload.
          if (prefRes.data.it_communication) {
            setItCommunication(prev => ({ ...prev, ...prefRes.data.it_communication }));
          }
        }
        const sessArray = Array.isArray(sessRes.data) ? sessRes.data : sessRes.data?.sessions || [];
        setSessions(sessArray.slice(0, 5));
      } catch (e) {
        console.error('Failed to fetch settings data:', e);
      }
    };
    fetchExtras();
  }, [api]);

  // Task #200 §5.8 — load workspace identity for IT users only. Re-uses the
  // existing /independent-teacher/workspace/settings endpoint so this section
  // and WorkspaceSettingsPage stay in sync without a second source of truth.
  useEffect(() => {
    if (!api || !isIndependentTeacher) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get('/independent-teacher/workspace/settings');
        if (cancelled || !data) return;
        setWorkspace({
          name_ar: data.name_ar || '',
          name_en: data.name_en || '',
          logo_url: data.logo_url || '',
        });
        setWorkspaceLoaded(true);
      } catch (err) {
        // Pre-bootstrap users won't have a workspace yet; leave defaults.
        setWorkspaceLoaded(true);
      }
      // §6.8 — pull the lifecycle view in parallel so the soft-delete
      // gating (24h export freshness) survives a page refresh. Failures
      // are non-fatal — the button just stays disabled with the
      // "export-required" hint.
      try {
        const { data: lc } = await api.get('/independent-teacher/workspace/lifecycle');
        if (cancelled || !lc) return;
        if (lc.last_export_at) setLastExportAt(lc.last_export_at);
      } catch (_e) {
        /* non-fatal */
      }
    })();
    return () => { cancelled = true; };
  }, [api, isIndependentTeacher]);

  const profileChanged = originalProfile && JSON.stringify(profile) !== JSON.stringify(originalProfile);

  const handleSaveProfile = async () => {
    if (isGenericName(profile.full_name)) {
      nassaqError(t('youMustUseYourRealPersonalName'));
      return;
    }
    setSaving(true);
    setSaveSuccess(null);
    try {
      const res = await api.put('/users/me/profile', {
        title: profile.title === 'none' ? '' : profile.title,
        full_name: profile.full_name,
        full_name_en: profile.full_name_en,
        email: profile.email,
        phone: profile.phone,
        preferred_language: preferences.language,
      });

      if (res.data?.user) {
        window.dispatchEvent(new CustomEvent('user-updated', { detail: res.data.user }));
      }
      await refreshUser();
      setOriginalProfile({ ...profile });
      setSaveSuccess('profile');
      toast.success(t('profileSavedSuccessfully'));
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('failedToSaveProfile')));
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarCropSave = async (base64Data) => {
    setSaving(true);
    try {
      const response = await api.post('/users/me/avatar', { image_data: base64Data });
      if (response.data?.success) {
        setProfile(prev => ({ ...prev, avatar_url: base64Data }));
        window.dispatchEvent(new CustomEvent('user-updated', { detail: { avatar_url: base64Data } }));
        await refreshUser();
        toast.success(t('avatarUpdated'));
      }
    } catch (err) {
      nassaqError(err.response?.data?.detail || (t('failedToUploadAvatar')));
      throw err;
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!passwordData.current_password) {
      nassaqError(t('enterCurrentPassword'));
      return;
    }
    if (passwordData.new_password !== passwordData.confirm_password) {
      nassaqError(t('passwordsDoNotMatch'));
      return;
    }
    if (passwordData.new_password.length < 8) {
      nassaqError(t('passwordMustBeAtLeast8Characters'));
      return;
    }
    setSaving(true);
    try {
      await api.post('/auth/change-password', {
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      });
      await refreshUser();
      setSaveSuccess('password');
      toast.success(t('passwordChangedSuccessfully'));
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('failedToChangePassword')));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotifications = async () => {
    setSaving(true);
    try {
      await api.put('/users/me/notifications', notifications);
      await refreshUser();
      setSaveSuccess('notifications');
      toast.success(t('notificationSettingsSaved'));
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      nassaqError(t('failedToSaveSettings'));
    } finally {
      setSaving(false);
    }
  };

  // Task #200 §5.8 — IT-only workspace identity save (name + logo). Mirrors
  // the same payload contract as WorkspaceSettingsPage so they stay aligned.
  // Per spec §5.8 + replit.md, success and recoverable errors must use
  // NassaqAlertDialog (never `toast.error()` / native browser dialogs).
  // 403/409 responses additionally re-fetch the workspace row so the form
  // recovers to server truth before surfacing the dialog.
  const handleSaveWorkspace = async () => {
    if (!workspace.name_ar?.trim()) {
      nassaqErrorTop(t('workspaceNameArRequired'));
      return;
    }
    setSaving(true);
    try {
      await api.put('/independent-teacher/workspace/settings', {
        name_ar: workspace.name_ar.trim(),
        name_en: workspace.name_en?.trim() || null,
        logo_url: workspace.logo_url || null,
      });
      setSaveSuccess('workspace');
      nassaqSuccess(t('workspaceSettingsSaved'));
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail;
      // 403/409: workspace state drifted (forbidden / conflict). Reload the
      // workspace row from the canonical endpoint so the form recovers to
      // server truth, then surface a NassaqAlertDialog instead of a toast.
      if (status === 403 || status === 409) {
        try {
          const { data } = await api.get('/independent-teacher/workspace/settings');
          if (data) {
            setWorkspace({
              name_ar: data.name_ar || '',
              name_en: data.name_en || '',
              logo_url: data.logo_url || '',
            });
          }
        } catch (_reloadErr) {
          // Ignore reload failures — we still surface the original error.
        }
        nassaqErrorTop(detail || t('failedToSaveWorkspaceSettings'));
      } else {
        nassaqErrorTop(detail || t('failedToSaveWorkspaceSettings'));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleWorkspaceLogoCropSave = async (base64Data) => {
    setWorkspace(prev => ({ ...prev, logo_url: base64Data }));
  };

  // Task #200 §5.8 — IT-only communication preferences save. Persisted
  // through the existing /users/me/preferences endpoint with an
  // `it_communication` blob (no new route, no new table). Success and
  // failure both surface through NassaqAlertDialog per spec.
  const handleSaveCommunication = async () => {
    setSaving(true);
    try {
      await api.put('/users/me/preferences', { it_communication: itCommunication });
      setSaveSuccess('communication');
      nassaqSuccess(t('communicationPreferencesSaved'));
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      nassaqErrorTop(t('failedToSaveCommunicationPreferences'));
    } finally {
      setSaving(false);
    }
  };

  // Task #211 §6.8 — Workspace export & soft-delete.
  // Right-to-export: POSTs to /independent-teacher/workspace/export
  // and surfaces the 24h signed download URL through nassaqSuccess
  // (no toast.error, no native window.confirm). The download URL is
  // bound to the caller's workspace + user id server-side; opening it
  // streams the zip bundle directly.
  const handleExportWorkspace = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/independent-teacher/workspace/export');
      const url = data?.download_url;
      const expiresAt = data?.expires_at;
      setLastExportAt(new Date().toISOString());
      setLastExportUrl(url || null);
      setLastExportExpiresAt(expiresAt || null);
      if (url) {
        // Open in a new tab so the settings page state survives the
        // download; the link itself is single-purpose (zip stream).
        try { window.open(url, '_blank', 'noopener,noreferrer'); } catch (_e) { /* popup blocked */ }
      }
      nassaqSuccess(t('itExportReadyMessage'), { title: t('itExportReadyTitle') });
    } catch (error) {
      nassaqError(error?.response?.data?.detail || t('itExportFailed'));
    } finally {
      setSaving(false);
    }
  };

  // Right-to-leave: opens the confirm dialog. The actual archive POST
  // happens in handleConfirmSoftDelete after the user types the
  // workspace name verbatim — server enforces the same equality check
  // so client-only typos cannot accidentally archive a workspace.
  const handleOpenSoftDelete = () => {
    setSoftDeleteConfirmName('');
    setSoftDeleteOpen(true);
  };

  const handleConfirmSoftDelete = async () => {
    setSaving(true);
    try {
      await api.post('/independent-teacher/workspace/soft-delete', {
        confirm_workspace_name: softDeleteConfirmName.trim(),
      });
      setSoftDeleteOpen(false);
      nassaqSuccess(t('itSoftDeleteSuccessMessage'), {
        title: t('itSoftDeleteSuccessTitle'),
        onConfirm: () => { try { logout(); } catch (_e) {} },
      });
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const status = error?.response?.status;
      if (status === 412) {
        nassaqWarning(detail || t('itSoftDeleteRequiresExport'));
      } else if (status === 422) {
        nassaqWarning(detail || t('itSoftDeleteNameMismatch'));
      } else {
        nassaqError(detail || t('itSoftDeleteFailed'));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleSavePreferences = async () => {
    setSaving(true);
    try {
      await api.put('/users/me/preferences', preferences);
      if (preferences.language !== language) setLanguage(preferences.language);
      if (preferences.theme !== theme) setTheme(preferences.theme);
      await refreshUser();
      setSaveSuccess('preferences');
      toast.success(t('preferencesSaved'));
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      nassaqError(t('failedToSavePreferences'));
    } finally {
      setSaving(false);
    }
  };

  const handleSwitchRole = async (roleId) => {
    setSwitchingRole(true);
    try {
      const response = await api.post(`/user-roles/switch/${roleId}`);
      // SECURITY (audit Phase 2): all auth-token writes must route through
      // AuthContext so the upcoming HttpOnly-cookie cutover has a single
      // chokepoint. Direct localStorage writes are blocked by
      // scripts/check_token_storage.sh.
      if (response.data?.access_token) await updateToken(response.data.access_token);
      toast.success(t('roleSwitchedSuccessfully'));
      setTimeout(() => window.location.reload(), 1000);
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('failedToSwitchRole')));
    } finally {
      setSwitchingRole(false);
      setShowRoleSwitchDialog(false);
    }
  };

  const getRoleLabel = (role) => {
    const roles = {
      platform_admin: { ar: 'مدير المنصة', en: 'Platform Admin' },
      school_principal: { ar: 'مدير المدرسة', en: 'School Principal' },
      school_sub_admin: { ar: 'مساعد المدير', en: 'Sub Admin' },
      school_admin: { ar: 'مشرف المدرسة', en: 'School Admin' },
      teacher: { ar: 'معلم', en: 'Teacher' },
      student: { ar: 'طالب', en: 'Student' },
      parent: { ar: 'ولي أمر', en: 'Parent' },
    };
    return roles[role]?.[isRTL ? 'ar' : 'en'] || role;
  };

  const getInitials = (name) => {
    if (!name) return 'U';
    return name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
  };

  const sections = [
    { id: 'profile', icon: User, label: t('profile3'), desc: t('nameTitleEmail') },
    { id: 'security', icon: Shield, label: t('security'), desc: t('passwordSessions') },
    { id: 'notifications', icon: Bell, label: t('notifications'), desc: t('emailSmsAlerts') },
    { id: 'preferences', icon: Palette, label: t('preferences'), desc: t('languageThemeTime') },
    // Task #200 §5.8 — IT-only sections appended at the end of the nav.
    ...(isIndependentTeacher ? [
      { id: 'workspace', icon: Briefcase, label: t('itWorkspaceSection'), desc: t('itWorkspaceSectionDesc') },
      { id: 'communication', icon: MessageSquare, label: t('itCommunicationSection'), desc: t('itCommunicationSectionDesc') },
      { id: 'export', icon: Download, label: t('itDataExportSection'), desc: t('itDataExportSectionDesc') },
    ] : []),
  ];

  const SaveButton = ({ onClick, sectionKey, label }) => (
    <Button onClick={onClick} disabled={saving} className="bg-brand-navy rounded-xl gap-2 min-w-[140px]" data-testid={`save-${sectionKey}`}>
      {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : saveSuccess === sectionKey ? <CheckCircle className="h-4 w-4 text-emerald-400" /> : <Save className="h-4 w-4" />}
      {saveSuccess === sectionKey ? (t('saved')) : label}
    </Button>
  );

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="account-settings-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center">
                <UserCog className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="font-cairo text-xl font-bold text-foreground">
                  {t('accountSettings')}
                </h1>
                <p className="text-xs text-muted-foreground font-tajawal">
                  {t('manageYourProfileAndPreferences')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl" aria-label={t('toggleLanguage')}>
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl" aria-label={t('toggleTheme')}>
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 max-w-[1200px] mx-auto">
          <Card className="card-nassaq overflow-hidden mb-6 border-0 shadow-lg">
            <div className="relative bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-turquoise/70 p-6 overflow-hidden">
              <div className="absolute inset-0 nassaq-pattern opacity-[0.05] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_80%,rgba(27,147,164,0.15),transparent_50%)]" />
              <div className="relative z-10 flex items-center gap-5">
                <div className="relative group">
                  <Avatar className="h-20 w-20 border-[3px] border-white/20 shadow-xl">
                    <AvatarImage src={profile.avatar_url} />
                    <AvatarFallback className="bg-white/10 backdrop-blur text-white text-xl font-cairo">
                      {getInitials(profile.full_name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="cursor-pointer" onClick={() => setCropModalOpen(true)}>
                    <div className="absolute inset-0 rounded-full bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      {saving ? <Loader2 className="h-5 w-5 text-white animate-spin" /> : <Camera className="h-5 w-5 text-white" />}
                    </div>
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-emerald-500 border-2 border-brand-navy flex items-center justify-center">
                    <Check className="h-3 w-3 text-white" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <h2 className="text-xl font-bold font-cairo text-white truncate">
                    {profile.title && profile.title !== 'none' ? `${profile.title} ` : ''}{profile.full_name}
                  </h2>
                  <p className="text-sm text-white/60 font-tajawal truncate">{profile.email}</p>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <Badge className="bg-white/15 text-white/90 border-white/10 backdrop-blur-sm text-xs">
                      {getRoleLabel(user?.role)}
                    </Badge>
                    {user?.tenant_name && (
                      <Badge className="bg-white/10 text-white/70 border-white/10 text-xs">
                        <Building2 className="h-3 w-3 me-1" />
                        {user.tenant_name}
                      </Badge>
                    )}
                    <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/20 text-xs">
                      <CheckCircle className="h-3 w-3 me-1" />
                      {t('verified')}
                    </Badge>
                  </div>
                </div>
                <div className="flex flex-col gap-2 flex-shrink-0">
                  {userRoles.length > 1 && (
                    <Button variant="secondary" size="sm" onClick={() => setShowRoleSwitchDialog(true)} className="rounded-xl bg-white/10 hover:bg-white/20 text-white border-0 text-xs">
                      <RefreshCw className="h-3.5 w-3.5 me-1.5" />
                      {t('switchRole2')}
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" onClick={() => setShowLogoutDialog(true)} className="rounded-xl bg-red-500/15 hover:bg-red-500/25 text-red-300 border-0 text-xs">
                    <LogOut className="h-3.5 w-3.5 me-1.5" />
                    {t('logout3')}
                  </Button>
                </div>
              </div>
            </div>
            <CardContent className="p-4 bg-muted/20 border-t border-border/30">
              <div className="flex items-center justify-between text-xs text-muted-foreground font-tajawal">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5" />
                    {t('created2')}
                    {user?.created_at ? new Date(user.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    {t('updatedLabel')}
                    {user?.updated_at ? new Date(user.updated_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '—'}
                  </span>
                </div>
                <span className="flex items-center gap-1.5 text-brand-turquoise">
                  <Sparkles className="h-3.5 w-3.5" />
                  ID: {user?.id?.slice(0, 8)}...
                </span>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
            <div className="lg:sticky lg:top-[80px] lg:self-start">
              <Card className="card-nassaq">
                <CardContent className="p-3">
                  <SectionNav sections={sections} active={activeSection} onChange={setActiveSection} isRTL={isRTL} />
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              {activeSection === 'profile' && (
                <>
                  <Card className="card-nassaq">
                    <CardHeader className="pb-4">
                      <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                        <User className="h-5 w-5 text-brand-turquoise" />
                        {t('personalInformation2')}
                        {profileChanged && (
                          <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 text-[10px] ms-2 border-0">
                            <AlertTriangle className="h-3 w-3 me-1" />
                            {t('unsavedChanges')}
                          </Badge>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <FieldGroup label={t('title')}>
                          <Select value={profile.title} onValueChange={(v) => setProfile({ ...profile, title: v })}>
                            <SelectTrigger className="rounded-xl" data-testid="profile-title"><SelectValue placeholder={t('selectTitle')} /></SelectTrigger>
                            <SelectContent>{titleOptions.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                          </Select>
                        </FieldGroup>
                        <FieldGroup label={t('fullNameArabic')} icon={User}>
                          <Input value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} className={`rounded-xl ${isGenericName(profile.full_name) ? 'border-amber-400 focus:border-amber-500' : ''}`} data-testid="profile-name-ar" dir="rtl" />
                          {isGenericName(profile.full_name) && (
                            <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                              <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                              {t('realNameHint')}
                            </p>
                          )}
                        </FieldGroup>
                        <FieldGroup label={t('fullNameEnglish')} icon={User}>
                          <Input value={profile.full_name_en} onChange={(e) => setProfile({ ...profile, full_name_en: e.target.value })} className="rounded-xl" data-testid="profile-name-en" dir="ltr" />
                        </FieldGroup>
                        <FieldGroup label={t('email2')} icon={Mail}>
                          <Input type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} className="rounded-xl" data-testid="profile-email" dir="ltr" />
                        </FieldGroup>
                        <FieldGroup label={t('phoneNumber')} icon={Phone}>
                          <Input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} className="rounded-xl" data-testid="profile-phone" dir="ltr" placeholder="+966 5xx xxx xxxx" />
                        </FieldGroup>
                      </div>
                      <div className="flex items-center justify-between pt-2 border-t border-border/30">
                        <p className="text-xs text-muted-foreground font-tajawal">
                          {t('changesWillBeSavedDirectlyToTheDatabase')}
                        </p>
                        <SaveButton onClick={handleSaveProfile} sectionKey="profile" label={t('saveChanges2')} />
                      </div>
                    </CardContent>
                  </Card>
                </>
              )}

              {activeSection === 'security' && (
                <>
                  <Card className="card-nassaq">
                    <CardHeader className="pb-4">
                      <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                        <Key className="h-5 w-5 text-brand-turquoise" />
                        {t('changePassword')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="max-w-md space-y-4">
                        <FieldGroup label={t('currentPassword')} icon={Lock}>
                          <div className="relative">
                            <Input
                              type={showPassword.current ? 'text' : 'password'}
                              value={passwordData.current_password}
                              onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                              className="rounded-xl pe-10" data-testid="current-password" dir="ltr"
                            />
                            <Button type="button" variant="ghost" size="icon" className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                              onClick={() => setShowPassword({ ...showPassword, current: !showPassword.current })}
                              aria-label={t('togglePasswordVisibility')}
                            >
                              {showPassword.current ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          </div>
                        </FieldGroup>
                        <FieldGroup label={t('newPassword')} icon={Key}>
                          <div className="relative">
                            <Input
                              type={showPassword.new ? 'text' : 'password'}
                              value={passwordData.new_password}
                              onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                              className="rounded-xl pe-10" data-testid="new-password" dir="ltr"
                            />
                            <Button type="button" variant="ghost" size="icon" className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                              onClick={() => setShowPassword({ ...showPassword, new: !showPassword.new })}
                              aria-label={t('togglePasswordVisibility')}
                            >
                              {showPassword.new ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          </div>
                          <PasswordStrength password={passwordData.new_password} isRTL={isRTL} />
                        </FieldGroup>
                        <FieldGroup label={t('confirmPassword')} icon={Lock}>
                          <div className="relative">
                            <Input
                              type={showPassword.confirm ? 'text' : 'password'}
                              value={passwordData.confirm_password}
                              onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                              className={`rounded-xl pe-10 ${passwordData.confirm_password && passwordData.confirm_password !== passwordData.new_password ? 'border-red-500 focus-visible:ring-red-500' : passwordData.confirm_password && passwordData.confirm_password === passwordData.new_password ? 'border-emerald-500 focus-visible:ring-emerald-500' : ''}`}
                              data-testid="confirm-password" dir="ltr"
                            />
                            <Button type="button" variant="ghost" size="icon" className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                              onClick={() => setShowPassword({ ...showPassword, confirm: !showPassword.confirm })}
                              aria-label={t('togglePasswordVisibility')}
                            >
                              {showPassword.confirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                          </div>
                          {passwordData.confirm_password && passwordData.confirm_password !== passwordData.new_password && (
                            <p className="text-xs text-red-500 font-tajawal flex items-center gap-1 mt-1">
                              <X className="h-3 w-3" />{t('passwordsDoNotMatch')}
                            </p>
                          )}
                          {passwordData.confirm_password && passwordData.confirm_password === passwordData.new_password && (
                            <p className="text-xs text-emerald-500 font-tajawal flex items-center gap-1 mt-1">
                              <Check className="h-3 w-3" />{t('passwordsMatch')}
                            </p>
                          )}
                        </FieldGroup>
                      </div>
                      <div className="flex items-center justify-between pt-2 border-t border-border/30">
                        <p className="text-xs text-muted-foreground font-tajawal">
                          {t('changeWillBeLoggedInTheSecurityAudit')}
                        </p>
                        <SaveButton onClick={handleChangePassword} sectionKey="password" label={t('changePassword')} />
                      </div>
                    </CardContent>
                  </Card>

                  {/* Task #169 Step 11 — Real MFA management surface (tier badge,
                      enrolled factors, TOTP enrolment, recovery-code generation
                      with password re-auth) replaces the previous decorative
                      "Enable" placeholder. */}
                  <MfaSecuritySection />

                  <Card className="card-nassaq">
                    <CardHeader className="pb-4">
                      <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                        <Fingerprint className="h-5 w-5 text-brand-turquoise" />
                        {t('securityStatus')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-center justify-between p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/50 dark:border-emerald-800/30">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                            <CheckCircle className="h-5 w-5 text-emerald-500" />
                          </div>
                          <div>
                            <p className="font-medium text-sm">{t('emailVerified')}</p>
                            <p className="text-xs text-muted-foreground">{profile.email}</p>
                          </div>
                        </div>
                        <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 text-xs">{t('verified')}</Badge>
                      </div>
                    </CardContent>
                  </Card>

                  {sessions.length > 0 && (
                    <Card className="card-nassaq">
                      <CardHeader className="pb-4">
                        <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                          <History className="h-5 w-5 text-brand-turquoise" />
                          {t('activeSessions2')}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {sessions.map((session, i) => (
                          <div key={session.id || i} className="flex items-center justify-between p-3 rounded-xl border border-border/50">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-lg bg-muted/50 flex items-center justify-center">
                                <Monitor className="h-4 w-4 text-muted-foreground" />
                              </div>
                              <div>
                                <p className="text-sm font-medium">{session.device || session.user_agent?.substring(0, 30) || (t('unknownDevice'))}</p>
                                <p className="text-[10px] text-muted-foreground">{session.ip_address || '—'} • {session.created_at ? new Date(session.created_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US') : '—'}</p>
                              </div>
                            </div>
                            {i === 0 && (
                              <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-[10px] border-0">
                                {t('current3')}
                              </Badge>
                            )}
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}
                </>
              )}

              {activeSection === 'notifications' && (
                <Card className="card-nassaq">
                  <CardHeader className="pb-4">
                    <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                      <Bell className="h-5 w-5 text-brand-turquoise" />
                      {t('notificationSettings')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div>
                      <p className="text-sm font-cairo font-medium mb-3">{t('alertChannels')}</p>
                      <div className="space-y-2">
                        <NotificationRow title={t('emailNotifications')} desc={t('receiveNotificationsViaEmail')} checked={notifications.email_notifications} onChange={(v) => setNotifications({ ...notifications, email_notifications: v })} />
                        <NotificationRow title={t('smsNotifications')} desc={t('receiveNotificationsViaSms')} checked={notifications.sms_notifications} onChange={(v) => setNotifications({ ...notifications, sms_notifications: v })} />
                        <NotificationRow title={t('pushNotifications')} desc={t('instantBrowserPushNotifications')} checked={notifications.push_notifications} onChange={(v) => setNotifications({ ...notifications, push_notifications: v })} />
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-cairo font-medium mb-3">{t('alertTypes')}</p>
                      <div className="space-y-2">
                        <NotificationRow title={t('attendanceAlerts')} desc={t('alertsAboutAbsencesAndTardiness')} checked={notifications.attendance_alerts} onChange={(v) => setNotifications({ ...notifications, attendance_alerts: v })} />
                        <NotificationRow title={t('gradeAlerts')} desc={t('alertsAboutGradesAndResults')} checked={notifications.grade_alerts} onChange={(v) => setNotifications({ ...notifications, grade_alerts: v })} />
                        <NotificationRow title={t('behaviorAlerts')} desc={t('alertsAboutBehaviorAndDiscipline')} checked={notifications.behavior_alerts} onChange={(v) => setNotifications({ ...notifications, behavior_alerts: v })} />
                        <NotificationRow title={t('announcements')} desc={t('announcementsAndUpdates')} checked={notifications.announcement_alerts} onChange={(v) => setNotifications({ ...notifications, announcement_alerts: v })} />
                        <NotificationRow title={t('weeklyDigest')} desc={t('comprehensiveWeeklySummary')} checked={notifications.weekly_digest} onChange={(v) => setNotifications({ ...notifications, weekly_digest: v })} />
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-border/30">
                      <p className="text-xs text-muted-foreground font-tajawal">
                        {t('changesAreSavedDirectlyToYourAccount')}
                      </p>
                      <SaveButton onClick={handleSaveNotifications} sectionKey="notifications" label={t('saveSettings')} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {activeSection === 'preferences' && (
                <Card className="card-nassaq">
                  <CardHeader className="pb-4">
                    <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                      <Palette className="h-5 w-5 text-brand-turquoise" />
                      {t('preferencesAppearance')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <FieldGroup label={t('language')} icon={Languages}>
                        <Select value={preferences.language} onValueChange={(v) => setPreferences({ ...preferences, language: v })}>
                          <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ar">العربية</SelectItem>
                            <SelectItem value="en">English</SelectItem>
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <FieldGroup label={t('theme')} icon={Monitor}>
                        <Select value={preferences.theme} onValueChange={(v) => setPreferences({ ...preferences, theme: v })}>
                          <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="light">{t('light')}</SelectItem>
                            <SelectItem value="dark">{t('dark')}</SelectItem>
                            <SelectItem value="system">{t('system')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <FieldGroup label={t('timeFormat')} icon={Clock}>
                        <Select value={preferences.time_format} onValueChange={(v) => setPreferences({ ...preferences, time_format: v })}>
                          <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="12h">{t('12HourAmpm')}</SelectItem>
                            <SelectItem value="24h">{t('24Hour')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <FieldGroup label={t('dateFormat')} icon={Calendar}>
                        <Select value={preferences.date_format} onValueChange={(v) => setPreferences({ ...preferences, date_format: v })}>
                          <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="dd/mm/yyyy">DD/MM/YYYY</SelectItem>
                            <SelectItem value="mm/dd/yyyy">MM/DD/YYYY</SelectItem>
                            <SelectItem value="yyyy-mm-dd">YYYY-MM-DD</SelectItem>
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                      <FieldGroup label={t('firstDayOfWeek')}>
                        <Select value={preferences.first_day_of_week} onValueChange={(v) => setPreferences({ ...preferences, first_day_of_week: v })}>
                          <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="sunday">{t('sunday')}</SelectItem>
                            <SelectItem value="monday">{t('monday')}</SelectItem>
                            <SelectItem value="saturday">{t('saturday')}</SelectItem>
                          </SelectContent>
                        </Select>
                      </FieldGroup>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-border/30">
                      <p className="text-xs text-muted-foreground font-tajawal">
                        {t('changesWillBeAppliedImmediatelyAndSavedToYourAccou')}
                      </p>
                      <SaveButton onClick={handleSavePreferences} sectionKey="preferences" label={t('savePreferences')} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Task #200 §5.8 — IT-only: Workspace identity (name + logo). */}
              {activeSection === 'workspace' && isIndependentTeacher && (
                <Card className="card-nassaq border-workspace-accent-border" data-testid="it-workspace-section">
                  <CardHeader className="pb-4 border-b border-workspace-accent-border bg-workspace-accent-light/40">
                    <CardTitle className="font-cairo flex items-center gap-2 text-lg text-workspace-accent-fg">
                      <Briefcase className="h-5 w-5 text-workspace-accent" />
                      {t('itWorkspaceSection')}
                    </CardTitle>
                    <p className="text-xs text-workspace-accent-fg/70 font-tajawal mt-1">
                      {t('itWorkspaceSectionHint')}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-5 pt-5">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 rounded-2xl overflow-hidden border-2 border-workspace-accent-border bg-workspace-accent-light flex items-center justify-center flex-shrink-0">
                        {workspace.logo_url ? (
                          <img src={workspace.logo_url} alt="workspace logo" className="w-full h-full object-cover" />
                        ) : (
                          <ImageIcon className="h-7 w-7 text-workspace-accent" />
                        )}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => setWorkspaceLogoCropOpen(true)}
                        className="rounded-xl border-workspace-accent-border text-workspace-accent-fg hover:bg-workspace-accent-light"
                        data-testid="it-workspace-logo-upload-btn"
                      >
                        <Camera className="h-4 w-4 me-2" />
                        {workspace.logo_url ? t('changeImage') : t('uploadWorkspaceLogo')}
                      </Button>
                      {workspace.logo_url && (
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => setWorkspace(prev => ({ ...prev, logo_url: '' }))}
                          className="text-muted-foreground"
                        >
                          <X className="h-4 w-4 me-1" />
                          {t('removeLogo')}
                        </Button>
                      )}
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <FieldGroup label={t('workspaceNameAr')} icon={Building2}>
                        <Input
                          value={workspace.name_ar}
                          onChange={(e) => setWorkspace({ ...workspace, name_ar: e.target.value })}
                          className="rounded-xl"
                          dir="rtl"
                          data-testid="it-workspace-name-ar"
                          disabled={!workspaceLoaded}
                        />
                      </FieldGroup>
                      <FieldGroup label={t('workspaceNameEn')} icon={Building2}>
                        <Input
                          value={workspace.name_en}
                          onChange={(e) => setWorkspace({ ...workspace, name_en: e.target.value })}
                          className="rounded-xl"
                          dir="ltr"
                          data-testid="it-workspace-name-en"
                          disabled={!workspaceLoaded}
                        />
                      </FieldGroup>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-border/30">
                      <p className="text-xs text-muted-foreground font-tajawal">
                        {t('itWorkspaceSyncHint')}
                      </p>
                      {/* Task #200 §5.8 — workspace primary action uses the
                          sub-brand workspace-accent token instead of the
                          generic brand-navy SaveButton, matching the §5.8
                          visual identity for IT-only surfaces. */}
                      <Button
                        onClick={handleSaveWorkspace}
                        disabled={saving}
                        className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 min-w-[140px]"
                        data-testid="save-workspace"
                      >
                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : saveSuccess === 'workspace' ? <CheckCircle className="h-4 w-4 text-emerald-200" /> : <Save className="h-4 w-4" />}
                        {saveSuccess === 'workspace' ? (t('saved')) : (t('saveChanges2'))}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Task #200 §5.8 — IT-only: Communication preferences (default channel + quiet hours). */}
              {activeSection === 'communication' && isIndependentTeacher && (
                <Card className="card-nassaq border-workspace-accent-border" data-testid="it-communication-section">
                  <CardHeader className="pb-4 border-b border-workspace-accent-border bg-workspace-accent-light/40">
                    <CardTitle className="font-cairo flex items-center gap-2 text-lg text-workspace-accent-fg">
                      <MessageSquare className="h-5 w-5 text-workspace-accent" />
                      {t('itCommunicationSection')}
                    </CardTitle>
                    <p className="text-xs text-workspace-accent-fg/70 font-tajawal mt-1">
                      {t('itCommunicationSectionHint')}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-5 pt-5">
                    <FieldGroup label={t('itDefaultChannel')} icon={MessageSquare}>
                      <Select
                        value={itCommunication.default_channel}
                        onValueChange={(v) => setItCommunication({ ...itCommunication, default_channel: v })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="it-default-channel"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="email">{t('emailChannel')}</SelectItem>
                          <SelectItem value="sms">{t('smsChannel')}</SelectItem>
                          <SelectItem value="in_app">{t('inAppChannel')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </FieldGroup>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <FieldGroup label={t('quietHoursStart')} icon={Clock}>
                        <Input
                          type="time"
                          value={itCommunication.quiet_hours_start}
                          onChange={(e) => setItCommunication({ ...itCommunication, quiet_hours_start: e.target.value })}
                          className="rounded-xl"
                          dir="ltr"
                          data-testid="it-quiet-start"
                        />
                      </FieldGroup>
                      <FieldGroup label={t('quietHoursEnd')} icon={Clock}>
                        <Input
                          type="time"
                          value={itCommunication.quiet_hours_end}
                          onChange={(e) => setItCommunication({ ...itCommunication, quiet_hours_end: e.target.value })}
                          className="rounded-xl"
                          dir="ltr"
                          data-testid="it-quiet-end"
                        />
                      </FieldGroup>
                    </div>
                    <div className="flex items-center justify-between pt-2 border-t border-border/30">
                      <p className="text-xs text-muted-foreground font-tajawal">
                        {t('itCommunicationFutureHint')}
                      </p>
                      <SaveButton onClick={handleSaveCommunication} sectionKey="communication" label={t('saveSettings')} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Task #211 §6.8 — IT-only: Data export + soft-delete.
                  Two cards per spec: a primary export card (right-to-export)
                  and a destructive soft-delete card (right-to-leave). All
                  warnings/errors/confirms route through NassaqAlertDialog;
                  any inline date is formatted via the hijriDate utility,
                  never Intl.DateTimeFormat. */}
              {activeSection === 'export' && isIndependentTeacher && (
                <div className="space-y-6" data-testid="it-export-section">
                  <Card className="card-nassaq border-brand-turquoise/20">
                    <CardHeader className="pb-4 border-b border-border/40 bg-brand-turquoise/5">
                      <CardTitle className="font-cairo flex items-center gap-2 text-lg text-brand-navy">
                        <Download className="h-5 w-5 text-brand-turquoise" />
                        {t('itDataExportSection')}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('itDataExportSectionHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-5">
                      <div className="rounded-xl bg-muted/30 border border-border/40 p-5 flex items-start gap-3">
                        <div className="w-10 h-10 rounded-xl bg-brand-turquoise/15 flex items-center justify-center flex-shrink-0">
                          <Download className="h-5 w-5 text-brand-turquoise" />
                        </div>
                        <div className="flex-1">
                          <p className="font-cairo font-semibold text-foreground">
                            {t('itExportCardTitle')}
                          </p>
                          <p className="text-sm text-muted-foreground font-tajawal mt-1">
                            {t('itExportCardHint')}
                          </p>
                          {lastExportAt && (
                            <p
                              className="text-xs text-brand-turquoise font-tajawal mt-2"
                              data-testid="it-export-last-at"
                            >
                              {t('itExportLastAt')}: {formatHijriDate(new Date(lastExportAt))}
                            </p>
                          )}
                          {lastExportUrl && (
                            <a
                              href={lastExportUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-brand-navy underline font-tajawal mt-1 inline-block"
                              data-testid="it-export-download-link"
                            >
                              {t('itExportDownloadAgain')}
                            </a>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center justify-end pt-2 border-t border-border/30">
                        <Button
                          type="button"
                          onClick={handleExportWorkspace}
                          disabled={saving}
                          className="bg-brand-navy rounded-xl gap-2"
                          data-testid="it-export-run-btn"
                        >
                          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                          {t('itExportRun')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="card-nassaq border-red-200 dark:border-red-900/40" data-testid="it-soft-delete-section">
                    <CardHeader className="pb-4 border-b border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20">
                      <CardTitle className="font-cairo flex items-center gap-2 text-lg text-red-700 dark:text-red-300">
                        <AlertTriangle className="h-5 w-5 text-red-500" />
                        {t('itSoftDeleteSection')}
                      </CardTitle>
                      <p className="text-xs text-red-600/80 dark:text-red-300/70 font-tajawal mt-1">
                        {t('itSoftDeleteSectionHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="space-y-4 pt-5">
                      <ul className="text-sm text-muted-foreground font-tajawal space-y-1 list-disc ps-5">
                        <li>{t('itSoftDeleteBullet1')}</li>
                        <li>{t('itSoftDeleteBullet2')}</li>
                        <li>{t('itSoftDeleteBullet3')}</li>
                      </ul>
                      {!softDeleteEligible && (
                        <p
                          className="text-xs text-red-600/80 dark:text-red-300/80 font-tajawal rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/40 p-3"
                          data-testid="it-soft-delete-export-required"
                        >
                          {t('itSoftDeleteExportRequired')}
                        </p>
                      )}
                      <div className="flex items-center justify-end pt-2 border-t border-border/30">
                        <Button
                          type="button"
                          onClick={handleOpenSoftDelete}
                          variant="outline"
                          disabled={!softDeleteEligible || saving}
                          className="rounded-xl border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20 gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                          data-testid="it-soft-delete-open-btn"
                        >
                          <AlertTriangle className="h-4 w-4" />
                          {t('itSoftDeleteOpen')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* §6.8 soft-delete confirm dialog. Native confirm() and
            window.prompt() are forbidden — this is the only place the
            workspace-name verbatim check is collected; the server
            re-validates the same string so a client-only bypass cannot
            archive a workspace. */}
        <AlertDialog open={softDeleteOpen} onOpenChange={setSoftDeleteOpen}>
          <AlertDialogContent dir="rtl" data-testid="it-soft-delete-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-cairo text-red-700">
                {t('itSoftDeleteDialogTitle')}
              </AlertDialogTitle>
              <AlertDialogDescription className="font-tajawal text-sm whitespace-pre-wrap">
                {t('itSoftDeleteDialogBody')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="space-y-2 py-2">
              <Label htmlFor="it-soft-delete-confirm-input" className="font-tajawal text-xs">
                {t('itSoftDeleteConfirmLabel')}
              </Label>
              <Input
                id="it-soft-delete-confirm-input"
                value={softDeleteConfirmName}
                onChange={(e) => setSoftDeleteConfirmName(e.target.value)}
                placeholder={t('itSoftDeleteConfirmPlaceholder')}
                data-testid="it-soft-delete-confirm-input"
              />
            </div>
            <AlertDialogFooter className="gap-2 flex-row-reverse">
              <Button
                type="button"
                onClick={handleConfirmSoftDelete}
                disabled={saving || !softDeleteConfirmName.trim()}
                className="bg-red-600 hover:bg-red-700 text-white rounded-xl"
                data-testid="it-soft-delete-confirm-btn"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {t('itSoftDeleteConfirm')}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setSoftDeleteOpen(false)}
                className="rounded-xl"
                data-testid="it-soft-delete-cancel-btn"
              >
                {t('cancel')}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <AlertDialog open={showLogoutDialog} onOpenChange={setShowLogoutDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="font-cairo">{t('logout')}</AlertDialogTitle>
              <AlertDialogDescription>{t('areYouSureYouWantToLogout')}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className="rounded-xl">{t('cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={() => { logout(); toast.success(t('loggedOut')); }} className="bg-red-500 rounded-xl">
                <LogOut className="h-4 w-4 me-2" />{t('logout3')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <Dialog open={showRoleSwitchDialog} onOpenChange={setShowRoleSwitchDialog}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <RefreshCw className="h-5 w-5 text-brand-turquoise" />
                {t('switchRole2')}
              </DialogTitle>
              <DialogDescription>{t('selectTheRoleToSwitchTo')}</DialogDescription>
            </DialogHeader>
            <div className="space-y-2.5 mt-4">
              {userRoles.length === 0 ? (
                <div className="text-center py-8">
                  <Users className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
                  <p className="text-sm text-muted-foreground">{t('noOtherRolesAvailable')}</p>
                </div>
              ) : (
                userRoles.map((role) => (
                  <Card
                    key={role.id}
                    className={`cursor-pointer transition-all hover:ring-2 hover:ring-brand-turquoise/50 ${role.is_active ? 'ring-2 ring-brand-turquoise bg-brand-turquoise/5' : ''}`}
                    onClick={() => !role.is_active && handleSwitchRole(role.id)}
                  >
                    <CardContent className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                          role.role_type === 'school_principal' ? 'bg-purple-100 text-purple-600 dark:bg-purple-900/30' :
                          role.role_type === 'teacher' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30' :
                          'bg-gray-100 text-gray-600 dark:bg-gray-800'
                        }`}>
                          {role.role_type === 'school_principal' ? <Building2 className="h-4 w-4" /> :
                           role.role_type === 'teacher' ? <Users className="h-4 w-4" /> :
                           <User className="h-4 w-4" />}
                        </div>
                        <div>
                          <p className="font-medium text-sm">{role.role_name_ar || role.role_name}</p>
                          {role.school_name && <p className="text-xs text-muted-foreground">{role.school_name}</p>}
                        </div>
                      </div>
                      {role.is_active ? (
                        <Badge className="bg-brand-turquoise text-white text-xs"><CheckCircle className="h-3 w-3 me-1" />{t('active')}</Badge>
                      ) : switchingRole ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
      <ImageCropModal
        open={cropModalOpen}
        onOpenChange={setCropModalOpen}
        onSave={handleAvatarCropSave}
        isRTL={isRTL}
      />
      {/* Task #200 §5.8 — IT-only workspace logo cropper. Reuses the same
          ImageCropModal as the personal avatar so the UX matches. */}
      {isIndependentTeacher && (
        <ImageCropModal
          open={workspaceLogoCropOpen}
          onOpenChange={setWorkspaceLogoCropOpen}
          onSave={handleWorkspaceLogoCropSave}
          isRTL={isRTL}
        />
      )}
    </Sidebar>
  );
};

export default AccountSettingsPage;
