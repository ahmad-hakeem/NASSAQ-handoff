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
import { useWorkspaceHubData } from '../hooks/useWorkspaceHubData';
import { ResponsiveTable } from '../components/ui/ResponsiveTable';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
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
  ShieldAlert,
  Database,
  RotateCcw,
  Users2,
  Trash2,
  FileText,
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

// Task #252 — small inline helper for the workspace-hub quota card.
// Renders "<used> of <max>" + a clamped progress bar; turns amber at 80%
// and red at 100% so the user gets a visual hint before they hit the cap.
// Task #253 — small spark-line under each QuotaBar to show usage trend.
// Renders only when at least 2 history points exist AND any point is
// non-zero (a flat-zero series would just be visual noise). Tone matches
// the bar's own threshold colour so the user sees the same "approaching
// the cap" signal in both glyphs at once.
const QuotaSparkline = ({ history, max, tone, testid }) => {
  if (!Array.isArray(history) || history.length < 2) return null;
  if (!history.some((v) => Number(v) > 0)) return null;
  const data = history.map((v, i) => ({ i, v: Math.max(0, Number(v) || 0) }));
  const safeMax = Math.max(0, Number(max) || 0);
  const dataMax = Math.max(...data.map((d) => d.v));
  // Domain top: at least the cap (so the trend is read against the cap),
  // but if the user already overshot we let the chart grow.
  const yTop = Math.max(safeMax || dataMax || 1, dataMax || 1);
  const stroke = tone === 'red' ? '#ef4444' : tone === 'amber' ? '#f59e0b' : '#14b8a6';
  return (
    <div className="h-8 w-full -mt-0.5" data-testid={testid}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={[0, yTop]} />
          <Line
            type="monotone"
            dataKey="v"
            stroke={stroke}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

const QuotaBar = ({ label, used, max, t, testid, history }) => {
  const safeMax = Math.max(0, Number(max) || 0);
  const safeUsed = Math.max(0, Number(used) || 0);
  const pct = safeMax > 0 ? Math.min(100, Math.round((safeUsed / safeMax) * 100)) : 0;
  const toneKey = pct >= 100 ? 'red' : pct >= 80 ? 'amber' : 'turquoise';
  const tone = toneKey === 'red' ? 'bg-red-500' : toneKey === 'amber' ? 'bg-amber-500' : 'bg-brand-turquoise';
  return (
    <div className="space-y-1.5" data-testid={testid}>
      <div className="flex items-center justify-between text-xs font-tajawal">
        <span className="text-foreground">{label}</span>
        <span className="text-muted-foreground">
          {(t('itHubQuotaUsageOf') || '{0} of {1}').replace('{0}', String(safeUsed)).replace('{1}', String(safeMax))}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted/40 overflow-hidden">
        <div className={`h-full ${tone} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <QuotaSparkline history={history} max={safeMax} tone={toneKey} testid={testid ? `${testid}-spark` : undefined} />
    </div>
  );
};

const NotificationRow = ({ title, desc, checked, onChange }) => (
  <div className="flex items-center justify-between p-4 rounded-xl border border-border/50 hover:bg-muted/20 transition-colors">
    <div>
      <p className="font-medium text-sm font-cairo">{title}</p>
      <p className="text-xs text-muted-foreground font-tajawal mt-0.5">{desc}</p>
    </div>
    <Switch checked={checked} onCheckedChange={onChange} />
  </div>
);

// Task #275 — small toggle row used by the IT auto-export card. Same
// visual + a11y shape as NotificationRow; kept separate so future
// auto-export rows (e.g. inline schedule preview) can extend without
// touching the broader notifications block. Originally referenced by
// the auto-export sub-card without ever being defined — Task #254's
// workspace-hub integration render surfaced this as "ToggleRow is not
// defined" the moment an IT user opened the hub. Aliasing keeps both
// call-sites identical and is the smallest possible patch.
const ToggleRow = NotificationRow;

export const AccountSettingsPage = () => {
  const { t } = useTranslation();
  const { user, api, logout, refreshUser, updateToken } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark, language, setLanguage, theme, setTheme } = useTheme();
  const { nassaqError, nassaqInfo, nassaqSuccess, nassaqConfirm, showAlert } = useNassaqAlert();
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
  // Task #276 — IT account erasure (GDPR right-to-be-forgotten).
  // Multi-step flow: 'consequences' → 'confirm' (verbatim name +
  // checkbox). Tier-A MFA is collected by the AuthContext axios
  // interceptor when the POST returns the 403 step-up envelope, so
  // there is no separate MFA step in the dialog.
  const [erasureOpen, setErasureOpen] = useState(false);
  const [erasureStep, setErasureStep] = useState('consequences');
  const [erasureConfirmName, setErasureConfirmName] = useState('');
  const [erasureAcknowledged, setErasureAcknowledged] = useState(false);
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
    return ['profile', 'security', 'notifications', 'preferences', 'workspace', 'communication', 'inbox_prefs', 'export', 'workspace-hub'].includes(raw)
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
      if (['profile', 'security', 'notifications', 'preferences', 'workspace', 'communication', 'inbox_prefs', 'export', 'workspace-hub'].includes(raw)) {
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

  // Task #249 — IT inbox channel preferences (per category × channel).
  // in_app is non-suppressible server-side; we still store it as `true`
  // for round-trip clarity and disable the toggle in the UI.
  const IT_INBOX_CATEGORIES = [
    'collab_invite', 'parent_accept', 'workspace_lifecycle', 'quota', 'lesson_plan',
  ];
  const _defaultInboxPref = () => ({
    in_app: true, email: true,
  });
  const [itInboxPrefs, setItInboxPrefs] = useState(() => {
    const out = {};
    IT_INBOX_CATEGORIES.forEach((c) => { out[c] = _defaultInboxPref(); });
    return out;
  });
  const [itInboxPrefsLoaded, setItInboxPrefsLoaded] = useState(false);

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

  // Task #249 — load IT inbox channel preferences. The endpoint pins
  // user_id + tenant_id == itw_{user_id} server-side; failures are
  // soft so the section still renders with sensible defaults.
  useEffect(() => {
    if (!api || !isIndependentTeacher) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get('/independent-teacher/notifications/preferences');
        if (cancelled || !data) return;
        const cats = data.categories || {};
        setItInboxPrefs((prev) => {
          const next = { ...prev };
          IT_INBOX_CATEGORIES.forEach((c) => {
            const incoming = cats[c] || {};
            next[c] = {
              in_app: incoming.in_app !== false, // server forces true
              email: incoming.email !== false,
            };
          });
          return next;
        });
      } catch (_e) { /* soft-fail */ }
      finally { if (!cancelled) setItInboxPrefsLoaded(true); }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, isIndependentTeacher]);

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
      // Task #338: a transient refreshUser() failure (e.g. network blip)
      // must NOT undo the success path or surface as a change-password
      // error — the password update has already been committed server-side.
      try {
        await refreshUser();
      } catch (_refreshErr) {
        // swallow — success state below is still the correct outcome.
      }
      setSaveSuccess('password');
      toast.success(t('passwordChangedSuccessfully'));
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      // Task #338: the axios interceptor handles MFA step-up envelopes
      // (HTTP 403 + canonical code) by opening the step-up modal and
      // replaying the request. If the user cancels or the replay fails,
      // the error reaches us here — surface a clear Arabic message in
      // the form instead of bouncing to /login. The interceptor's
      // defense-in-depth branch guarantees no logout for step-up codes.
      // Task #351 — accept BOTH envelope shapes the backend can emit:
      //   1. Canonical wrapped: `{ success:false, error:{ code, message } }`
      //      from `http_exception_handler` in backend/server.py.
      //   2. Raw FastAPI: `{ detail: { code, message } }` (defense in depth
      //      for any router that bypasses the global wrapper).
      const data = error.response?.data || {};
      const errEnv = (data.error && typeof data.error === 'object') ? data.error : null;
      const detail = data.detail;
      const code = errEnv?.code
        || (detail && typeof detail === 'object' ? detail.code : null);
      const envelopeMessage = errEnv?.message
        || (errEnv?.detail && typeof errEnv.detail === 'object' ? errEnv.detail.message : null)
        || (detail && typeof detail === 'object' ? detail.message : null)
        || (typeof detail === 'string' ? detail : null);
      // Task #351: MFA_RESTORE_REQUIRED means the user signed in with a
      // recovery code and must re-enroll a real second factor before
      // sensitive writes are allowed. The step-up modal cannot satisfy
      // this state — only the MFA Security section can. Show a focused
      // dialog that scrolls the user there instead of dumping the raw
      // backend message into a generic error alert.
      if (code === 'MFA_RESTORE_REQUIRED') {
        showAlert({
          type: 'warning',
          title: 'يلزم إعادة تسجيل عامل تحقق',
          message:
            'لقد سجّلت الدخول باستخدام رمز استرداد. لتغيير كلمة المرور، يجب أولاً إعادة تسجيل عامل تحقق (مفتاح أمان أو تطبيق مصادقة) من قسم "التحقق بخطوتين" أدناه، ثم أعد المحاولة.',
          confirmText: 'الذهاب إلى إعدادات التحقق',
          cancelText: 'إلغاء',
          showCancel: true,
          onConfirm: () => {
            try {
              const el = document.querySelector('[data-testid="mfa-security-section"]');
              if (el && typeof el.scrollIntoView === 'function') {
                el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                el.classList.add('ring-2', 'ring-amber-400');
                setTimeout(() => {
                  el.classList.remove('ring-2', 'ring-amber-400');
                }, 2400);
              }
            } catch (_e) { /* scroll best-effort */ }
          },
        });
        return;
      }
      nassaqError(envelopeMessage || t('failedToChangePassword'));
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

  // Task #249 — IT inbox preferences save. Round-trips through the new
  // /independent-teacher/notifications/preferences endpoint which
  // forces in_app=true server-side regardless of the client payload.
  const handleSaveInboxPrefs = async () => {
    setSaving(true);
    try {
      await api.put('/independent-teacher/notifications/preferences', {
        categories: itInboxPrefs,
      });
      setSaveSuccess('inbox_prefs');
      nassaqSuccess(t('itInboxPrefsSaved'));
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (error) {
      nassaqErrorTop(t('itInboxPrefsSaveFailed'));
    } finally {
      setSaving(false);
    }
  };

  // §369 security fix — authenticated blob download helper.
  // All workspace export downloads MUST carry the user's Bearer token so
  // the server can verify the downloader is the same user who minted the
  // export token.  window.open() / raw anchor hrefs cannot carry auth
  // headers and are no longer accepted by the download endpoint.
  const _downloadWorkspaceBlob = async (apiPath, filename = 'nassaq-workspace-export.zip') => {
    const path = apiPath.replace(/^\/api/, '');
    const response = await api.get(path, { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'application/zip' });
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(objectUrl);
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
      const downloadUrl = data?.download_url;
      const expiresAt = data?.expires_at;
      setLastExportAt(new Date().toISOString());
      setLastExportUrl(downloadUrl || null);
      setLastExportExpiresAt(expiresAt || null);
      if (downloadUrl) {
        await _downloadWorkspaceBlob(downloadUrl);
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
      const { data } = await api.post('/independent-teacher/workspace/soft-delete', {
        confirm_workspace_name: softDeleteConfirmName.trim(),
      });
      setSoftDeleteOpen(false);
      // Trigger the exit-artefact download while the user's access token is still
      // valid. The download endpoint requires authentication and verifies the
      // caller is the same user who minted the token (§369 security fix).
      const exitDownloadUrl = data?.download_url;
      if (exitDownloadUrl) {
        try {
          await _downloadWorkspaceBlob(exitDownloadUrl);
        } catch (_dlErr) { /* non-fatal: user was already shown the export earlier */ }
      }
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

  // Task #276 — IT account erasure handlers.
  //
  // Step 1 (consequences) is surfaced through NassaqAlertDialog
  // (`nassaqConfirm`) per repo policy — never `window.confirm` /
  // `toast.error` for important warnings. Step 2 collects the
  // verbatim workspace name + acknowledge checkbox, which still
  // requires an inline AlertDialog (the NassaqAlert primitive does
  // not accept embedded inputs); the inline dialog uses the same
  // visual styling as the existing soft-delete confirm and routes
  // every error variant back through `nassaqWarning` / `nassaqError`.
  const handleOpenErasure = () => {
    setErasureConfirmName('');
    setErasureAcknowledged(false);
    setErasureStep('confirm');
    nassaqConfirm(
      t('itErasureDialogConsequences'),
      () => { setErasureOpen(true); },
      {
        title: t('itErasureDialogTitle'),
        confirmText: t('itErasureContinue'),
        cancelText: t('cancel'),
      },
    );
  };

  const handleConfirmErasure = async () => {
    setSaving(true);
    try {
      const { data } = await api.post(
        '/independent-teacher/workspace/request-erasure',
        {
          confirm_workspace_name: erasureConfirmName.trim(),
          acknowledged: true,
        },
      );
      setErasureOpen(false);
      // Trigger the final exit-artefact download while the user's access token
      // is still valid. The download endpoint requires authentication and
      // verifies the caller is the same user who minted the token (§369).
      const exitDownloadUrl = data?.download_url;
      if (exitDownloadUrl) {
        try {
          await _downloadWorkspaceBlob(exitDownloadUrl);
        } catch (_dlErr) { /* non-fatal */ }
      }
      const deadline = data?.erasure_deadline
        ? formatHijriDate(new Date(data.erasure_deadline))
        : '';
      const msg = (t('itErasureSuccessMessage') || '').replace('{0}', deadline);
      nassaqInfo(msg, {
        title: t('itErasureSuccessTitle'),
        onConfirm: () => {
          try { logout(); } catch (_e) {}
          try { window.location.assign('/account-erased'); } catch (_e) {}
        },
      });
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const status = error?.response?.status;
      if (status === 409) {
        nassaqWarning(detail || t('itErasureAlreadyRequested'));
      } else if (status === 422) {
        nassaqWarning(detail || t('itErasureNameMismatch'));
      } else {
        nassaqError(detail || t('itErasureFailed'));
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
      independent_teacher: { ar: 'معلم مستقل', en: 'Independent Teacher' },
      student: { ar: 'طالب', en: 'Student' },
      parent: { ar: 'ولي أمر', en: 'Parent' },
    };
    // Fall back to the i18n dictionary (e.g. `independent_teacher` →
    // "معلم مستقل") before the raw role key, so the header badge never
    // leaks a snake_case identifier into the UI.
    return roles[role]?.[isRTL ? 'ar' : 'en'] || t(role) || role;
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
    { id: 'legal', icon: Shield, label: t('legalDocuments') || 'الوثائق القانونية', desc: t('privacyPolicyAndLegal') || 'سياسة الخصوصية والشروط والأحكام' },
    // Task #200 §5.8 — IT-only sections appended at the end of the nav.
    ...(isIndependentTeacher ? [
      { id: 'workspace', icon: Briefcase, label: t('itWorkspaceSection'), desc: t('itWorkspaceSectionDesc') },
      { id: 'communication', icon: MessageSquare, label: t('itCommunicationSection'), desc: t('itCommunicationSectionDesc') },
      { id: 'inbox_prefs', icon: Bell, label: t('itInboxPrefsSection'), desc: t('itInboxPrefsSectionDesc') },
      { id: 'export', icon: Download, label: t('itDataExportSection'), desc: t('itDataExportSectionDesc') },
      // Task #252 — at-a-glance hub: quota + export + collaborators + lifecycle.
      { id: 'workspace-hub', icon: ShieldAlert, label: t('itHubSection'), desc: t('itHubSectionDesc') },
    ] : []),
  ];

  // Task #252 — aggregator hook lazily loads only when the IT user is on
  // the hub section, so non-IT users + IT users on other sections pay no
  // network cost. The hook fans out to lifecycle + classes + per-class
  // collaborators in parallel.
  const hubEnabled = isIndependentTeacher && activeSection === 'workspace-hub';
  const hub = useWorkspaceHubData(api, hubEnabled);

  // Task #275 — opt-in weekly auto-export. Local state mirrors the
  // GET /workspace/auto-export/settings response; PUT optimistically
  // applies the change and rolls back on error via NassaqAlertDialog.
  const [autoExport, setAutoExport] = useState({
    enabled: false,
    day_of_week: 0,
    hour: 2,
    last_run_at: null,
    last_status: null,
    next_run_at: null,
  });
  const [autoExportSaving, setAutoExportSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!api || !hubEnabled) return;
      try {
        const { data } = await api.get('/independent-teacher/workspace/auto-export/settings');
        if (!cancelled && data) setAutoExport(data);
      } catch (_e) { /* hub-card silent — error surfaces on save */ }
    };
    load();
    return () => { cancelled = true; };
  }, [api, hubEnabled]);

  const _saveAutoExport = async (next) => {
    setAutoExportSaving(true);
    const prev = autoExport;
    setAutoExport((s) => ({ ...s, ...next }));
    try {
      const { data } = await api.put('/independent-teacher/workspace/auto-export/settings', {
        enabled: next.enabled !== undefined ? next.enabled : autoExport.enabled,
        day_of_week: next.day_of_week !== undefined ? next.day_of_week : autoExport.day_of_week,
        hour: next.hour !== undefined ? next.hour : autoExport.hour,
      });
      if (data) setAutoExport(data);
    } catch (error) {
      setAutoExport(prev);
      nassaqError(error?.response?.data?.detail || t('itHubAutoExportSaveFailed'));
    } finally {
      setAutoExportSaving(false);
    }
  };

  const handleAutoExportToggle = (v) => _saveAutoExport({ enabled: !!v });
  const handleAutoExportField = (patch) => _saveAutoExport(patch);

  // Task #252 — hub-specific export. Unlike handleExportWorkspace (which
  // also auto-opens the download in a new tab for the dedicated Export
  // section's UX), this one surfaces the one-shot signed URL exactly
  // once via NassaqAlertDialog so the IT user can copy it. The URL is
  // single-use server-side; we deliberately do NOT persist it in page
  // state.
  const handleHubExport = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/independent-teacher/workspace/export');
      const downloadUrl = data?.download_url || '';
      // Sync the page-level lastExportAt state so the legacy
      // `softDeleteEligible` derived flag (used to gate the archive CTA
      // in this same hub session) flips to true immediately, without
      // waiting for the hub.refresh() round-trip.
      const nowIso = new Date().toISOString();
      setLastExportAt(nowIso);
      setLastExportExpiresAt(data?.expires_at || null);
      await hub.refresh();
      if (downloadUrl) {
        await _downloadWorkspaceBlob(downloadUrl);
      }
      nassaqSuccess(t('itExportReadyMessage'), { title: t('itExportReadyTitle') });
    } catch (error) {
      nassaqError(error?.response?.data?.detail || t('itExportFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleHubReactivate = async () => {
    nassaqConfirm(
      t('itHubLifecycleReactivateConfirm'),
      async () => {
        try {
          await api.post('/independent-teacher/workspace/reactivate');
          nassaqSuccess(t('itHubLifecycleReactivateDone'));
          await hub.refresh();
        } catch (err) {
          const status = err?.response?.status;
          if (status === 410) {
            nassaqWarning(t('itHubLifecycleReactivateExpired'));
          } else {
            nassaqError(
              err?.response?.data?.detail || t('itHubLifecycleReactivateFailed'),
            );
          }
        }
      },
    );
  };

  const handleHubCollabAction = (item) => {
    const isPending = (item.status || '').toLowerCase() === 'pending';
    const message = isPending
      ? t('collabCancelConfirmBody').replace('{0}', item.collaborator_email || '')
      : t('collabRevokeConfirmBody').replace('{0}', item.collaborator_email || '');
    nassaqConfirm(message, async () => {
      try {
        if (isPending) {
          await api.post(
            `/independent-teacher/workspace-collaborators/${item.id}/cancel`,
          );
          nassaqSuccess(t('itHubCollabCancelDone'));
        } else {
          await api.delete(
            `/independent-teacher/workspace-collaborators/${item.id}`,
          );
          nassaqSuccess(t('itHubCollabRevokeDone'));
        }
        await hub.refresh();
      } catch (err) {
        nassaqError(
          err?.response?.data?.detail || t('itHubCollabActionFailed'),
        );
      }
    });
  };

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
                  <Card className="card-nassaq" data-testid="account-section-profile">
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
                  <Card className="card-nassaq" data-testid="account-section-security">
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
                <Card className="card-nassaq" data-testid="account-section-notifications">
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
                <Card className="card-nassaq" data-testid="account-section-preferences">
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

              {activeSection === 'legal' && (
                <Card className="card-nassaq" data-testid="account-section-legal">
                  <CardHeader className="pb-4">
                    <CardTitle className="font-cairo flex items-center gap-2 text-lg">
                      <Shield className="h-5 w-5 text-brand-turquoise" />
                      {t('legalDocuments') || 'الوثائق القانونية'}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-muted-foreground font-tajawal leading-relaxed">
                      {t('legalDocumentsHubBlurb') ||
                        'تطبّق منصة نسّق سياسة خصوصية وشروطاً وأحكاماً موحّدة لجميع الحسابات (الإدارة، المعلم، ولي الأمر، الطالب، المعلم المستقل). تنطبق نفس الضوابط على بيانات الجميع، مع تخصيصات لكل دور بحسب الصلاحيات.'}
                    </p>
                    <div className="rounded-xl border border-border/60 bg-card divide-y divide-border/40">
                      <a
                        href="/privacy"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between gap-3 p-4 hover:bg-muted/40 transition-colors"
                        data-testid="link-account-privacy-policy"
                      >
                        <span className="flex items-center gap-3">
                          <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                          <span className="font-cairo text-sm">
                            {t('viewPrivacyPolicy') || (isRTL ? 'عرض سياسة الخصوصية' : 'View Privacy Policy')}
                          </span>
                        </span>
                        {isRTL ? <ChevronLeft className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                      </a>
                      <a
                        href="/terms"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-between gap-3 p-4 hover:bg-muted/40 transition-colors"
                        data-testid="link-account-terms"
                      >
                        <span className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                          <span className="font-cairo text-sm">
                            {t('viewTermsAndConditions') || (isRTL ? 'عرض الشروط والأحكام' : 'View Terms & Conditions')}
                          </span>
                        </span>
                        {isRTL ? <ChevronLeft className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
                      </a>
                    </div>
                    <p className="text-xs text-muted-foreground font-tajawal">
                      {t('legalDocumentsOpenInNewTab') ||
                        'تُفتح الوثائق في نافذة جديدة، ويمكنك طباعتها أو حفظها بصيغة PDF.'}
                    </p>
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

                    {/* Task #250 — Replay the IT first-login onboarding tour. */}
                    <div className="mt-6 pt-4 border-t border-workspace-accent-border/60 flex items-center justify-between gap-3 flex-wrap">
                      <div className="text-xs font-tajawal text-workspace-accent-fg/80">
                        {t('itTourReplayHint')}
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-workspace-accent hover:bg-workspace-accent-light rounded-xl font-tajawal"
                        data-testid="it-tour-replay"
                        onClick={async () => {
                          try {
                            await api.post('/independent-teacher/onboarding/reset');
                            window.location.assign('/teacher');
                          } catch (e) { /* surfaced via global axios error handler */ }
                        }}
                      >
                        {t('itTourReplay')}
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

              {/* Task #249 — IT-only: notifications inbox preferences.
          Per-category in_app/email toggles. in_app is forced TRUE
          server-side regardless of payload, so the toggle is shown
          but disabled to keep the UI honest about the contract. */}
              {activeSection === 'inbox_prefs' && isIndependentTeacher && (
                <Card className="card-nassaq border-workspace-accent-border" data-testid="it-inbox-prefs-section">
                  <CardHeader className="pb-4 border-b border-workspace-accent-border bg-workspace-accent-light/40">
                    <CardTitle className="font-cairo flex items-center gap-2 text-lg text-workspace-accent-fg">
                      <Bell className="h-5 w-5 text-workspace-accent" />
                      {t('itInboxPrefsSection')}
                    </CardTitle>
                    <p className="text-xs text-workspace-accent-fg/70 font-tajawal mt-1">
                      {t('itInboxPrefsHint')}
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-4 pt-5">
                    {!itInboxPrefsLoaded && (
                      <p className="text-xs text-muted-foreground">{t('loading')}</p>
                    )}
                    <div className="space-y-3">
                      {IT_INBOX_CATEGORIES.map((cat) => {
                        const pref = itInboxPrefs[cat] || _defaultInboxPref();
                        return (
                          <div
                            key={cat}
                            className="flex items-center justify-between gap-3 rounded-xl border border-border/40 p-3"
                            data-testid={`it-inbox-cat-${cat}`}
                          >
                            <div className="font-tajawal text-sm">
                              {t(`itInboxCat_${cat}`)}
                            </div>
                            <div className="flex items-center gap-4">
                              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                                <input
                                  type="checkbox"
                                  checked
                                  disabled
                                  data-testid={`it-inbox-${cat}-in_app`}
                                />
                                {t('inAppChannel')}
                              </label>
                              <label className="flex items-center gap-2 text-xs">
                                <input
                                  type="checkbox"
                                  checked={!!pref.email}
                                  onChange={(e) => setItInboxPrefs((prev) => ({
                                    ...prev,
                                    [cat]: { ...(prev[cat] || _defaultInboxPref()), email: e.target.checked },
                                  }))}
                                  data-testid={`it-inbox-${cat}-email`}
                                />
                                {t('emailChannel')}
                              </label>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex items-center justify-end pt-2 border-t border-border/30">
                      <SaveButton onClick={handleSaveInboxPrefs} sectionKey="inbox_prefs" label={t('saveSettings')} />
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
              {/* Task #252 — IT-only "إعدادات المساحة" hub: a single
                  section bundling Quota / Export & backup / Collaborators /
                  Lifecycle into four sub-cards. Reuses existing endpoints
                  through useWorkspaceHubData; destructive actions route
                  through nassaqConfirm per the project rule against
                  native confirms / toast.error. */}
              {activeSection === 'workspace-hub' && isIndependentTeacher && (
                <div className="space-y-6" data-testid="it-workspace-hub-section">
                  <Card className="card-nassaq">
                    <CardHeader className="pb-4 border-b border-border/40 bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5">
                      <div className="flex items-center justify-between">
                        <CardTitle className="font-cairo flex items-center gap-2 text-lg text-brand-navy">
                          <ShieldAlert className="h-5 w-5 text-brand-turquoise" />
                          {t('itHubSectionTitle')}
                        </CardTitle>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => hub.refresh()}
                          disabled={hub.loading}
                          className="rounded-xl gap-2"
                          data-testid="it-hub-refresh-btn"
                        >
                          {hub.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                          {t('itHubRefresh')}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('itHubSectionHint')}
                      </p>
                      {hub.partialErrors.length > 0 && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 font-tajawal mt-2" data-testid="it-hub-partial-errors">
                          {t('itHubPartialErrors')}
                        </p>
                      )}
                    </CardHeader>
                  </Card>

                  {/* Sub-card 1: Quota overview */}
                  <Card className="card-nassaq" data-testid="it-hub-quota-card">
                    <CardHeader className="pb-4 border-b border-border/40">
                      <CardTitle className="font-cairo flex items-center gap-2 text-base">
                        <Database className="h-4 w-4 text-brand-turquoise" />
                        {t('itHubQuotaTitle')}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('itHubQuotaHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="pt-5">
                      {hub.loading && !hub.quota ? (
                        <p className="text-sm text-muted-foreground font-tajawal">{t('itHubLoading')}</p>
                      ) : !hub.quota ? (
                        <p className="text-sm text-muted-foreground font-tajawal" data-testid="it-hub-quota-unavailable">
                          {t('itHubQuotaUnavailable')}
                        </p>
                      ) : (
                        <div className="space-y-4">
                          <QuotaBar label={t('itHubQuotaStudents')} used={hub.quota.current_students} max={hub.quota.max_students} t={t} testid="it-hub-quota-students" history={hub.quotaHistory?.students} />
                          <QuotaBar label={t('itHubQuotaClasses')} used={hub.quota.current_classes} max={hub.quota.max_classes} t={t} testid="it-hub-quota-classes" history={hub.quotaHistory?.classes} />
                          <QuotaBar label={t('itHubQuotaImportsToday')} used={hub.quota.imports_today} max={hub.quota.max_imports_per_day} t={t} testid="it-hub-quota-imports" history={hub.quotaHistory?.imports} />
                          <QuotaBar label={t('itHubQuotaLessonPlansToday')} used={hub.quota.lesson_plans_today} max={hub.quota.max_lesson_plans_per_day} t={t} testid="it-hub-quota-lesson-plans" history={hub.quotaHistory?.lesson_plans} />
                          <div className="flex justify-end pt-2 border-t border-border/30">
                            <a
                              href="/teacher/import-students"
                              className="inline-flex items-center gap-2 text-xs font-cairo text-brand-navy hover:text-brand-turquoise underline-offset-4 hover:underline"
                              data-testid="it-hub-quota-bulk-import-link"
                            >
                              <Database className="h-3.5 w-3.5" />
                              {t('itHubQuotaBulkImportLink')}
                            </a>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Sub-card 2: Export & backup */}
                  <Card className="card-nassaq" data-testid="it-hub-export-card">
                    <CardHeader className="pb-4 border-b border-border/40">
                      <CardTitle className="font-cairo flex items-center gap-2 text-base">
                        <Download className="h-4 w-4 text-brand-turquoise" />
                        {t('itHubExportTitle')}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('itHubExportHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="pt-5 space-y-3">
                      <div className="text-sm font-tajawal">
                        {hub.lifecycle?.last_export_at ? (
                          <>
                            <p data-testid="it-hub-export-last-at">
                              {t('itExportLastAt')}: {formatHijriDate(new Date(hub.lifecycle.last_export_at))}
                            </p>
                            {softDeleteEligible || (hub.lifecycle.last_export_at && (Date.now() - new Date(hub.lifecycle.last_export_at).getTime()) <= 24 * 60 * 60 * 1000) ? (
                              <p className="text-xs text-emerald-600 mt-1">{t('itHubExportEligible')}</p>
                            ) : (
                              <p className="text-xs text-amber-600 mt-1">{t('itHubExportStale')}</p>
                            )}
                          </>
                        ) : (
                          <p className="text-muted-foreground" data-testid="it-hub-export-never">
                            {t('itHubExportNever')}
                          </p>
                        )}
                      </div>
                      <div className="flex justify-end pt-2 border-t border-border/30">
                        <Button
                          type="button"
                          onClick={handleHubExport}
                          disabled={saving}
                          className="bg-brand-navy rounded-xl gap-2"
                          data-testid="it-hub-export-btn"
                        >
                          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                          {t('itHubExportRunOneShot')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Sub-card 2b: Auto-export weekly schedule (Task #275) */}
                  <Card className="card-nassaq" data-testid="it-hub-auto-export-card">
                    <CardHeader className="pb-4 border-b border-border/40">
                      <CardTitle className="font-cairo flex items-center gap-2 text-base">
                        <Clock className="h-4 w-4 text-brand-turquoise" />
                        {t('itHubAutoExportTitle')}
                      </CardTitle>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('itHubAutoExportHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="pt-5 space-y-4">
                      <ToggleRow
                        title={t('itHubAutoExportEnableTitle')}
                        desc={t('itHubAutoExportEnableDesc')}
                        checked={!!autoExport.enabled}
                        onChange={(v) => handleAutoExportToggle(v)}
                      />
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="it-hub-auto-export-schedule">
                        <div>
                          <Label className="text-xs font-cairo">{t('itHubAutoExportDow')}</Label>
                          <Select
                            value={String(autoExport.day_of_week ?? 0)}
                            onValueChange={(v) => handleAutoExportField({ day_of_week: Number(v) })}
                            disabled={!autoExport.enabled || autoExportSaving}
                          >
                            <SelectTrigger data-testid="it-hub-auto-export-dow-select">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {[0,1,2,3,4,5,6].map((d) => (
                                <SelectItem key={d} value={String(d)}>{t(`weekday_${d}`)}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs font-cairo">{t('itHubAutoExportHour')}</Label>
                          <Select
                            value={String(autoExport.hour ?? 2)}
                            onValueChange={(v) => handleAutoExportField({ hour: Number(v) })}
                            disabled={!autoExport.enabled || autoExportSaving}
                          >
                            <SelectTrigger data-testid="it-hub-auto-export-hour-select">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {Array.from({ length: 24 }, (_, h) => (
                                <SelectItem key={h} value={String(h)}>
                                  {String(h).padStart(2, '0')}:00 UTC
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="text-xs font-tajawal text-muted-foreground space-y-1 border-t border-border/30 pt-3">
                        {autoExport.last_run_at ? (
                          <p data-testid="it-hub-auto-export-last">
                            {t('itHubAutoExportLastRun')}: {formatHijriDate(new Date(autoExport.last_run_at))}
                            {autoExport.last_status ? ` — ${t(`itHubAutoExportStatus_${autoExport.last_status}`, { defaultValue: autoExport.last_status })}` : ''}
                          </p>
                        ) : (
                          <p data-testid="it-hub-auto-export-never">{t('itHubAutoExportNeverRun')}</p>
                        )}
                        {autoExport.enabled && autoExport.next_run_at ? (
                          <p data-testid="it-hub-auto-export-next">
                            {t('itHubAutoExportNextRun')}: {formatHijriDate(new Date(autoExport.next_run_at))}
                          </p>
                        ) : null}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Sub-card 3: Collaborators */}
                  <Card className="card-nassaq" data-testid="it-hub-collab-card">
                    <CardHeader className="pb-4 border-b border-border/40">
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <CardTitle className="font-cairo flex items-center gap-2 text-base">
                          <Users2 className="h-4 w-4 text-brand-turquoise" />
                          {t('itHubCollabTitle')}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <Badge className="bg-emerald-100 text-emerald-700 border-0 text-xs" data-testid="it-hub-collab-active-count">
                            {t('itHubCollabActive')}: {hub.counts.active}
                          </Badge>
                          <Badge className="bg-amber-100 text-amber-700 border-0 text-xs" data-testid="it-hub-collab-pending-count">
                            {t('itHubCollabPending')}: {hub.counts.pending}
                          </Badge>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('itHubCollabHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="pt-5 space-y-5">
                      {hub.loading && hub.collaborators.length === 0 ? (
                        <p className="text-sm text-muted-foreground font-tajawal">{t('itHubLoading')}</p>
                      ) : hub.collaborators.length === 0 ? (
                        <p className="text-sm text-muted-foreground font-tajawal" data-testid="it-hub-collab-empty">
                          {t('itHubCollabEmpty')}
                        </p>
                      ) : (
                        <>
                          {/* Per-class breakdown — one row per class with active/pending counts
                              and a deep-link to that class' Collaborators tab. */}
                          <div data-testid="it-hub-collab-by-class">
                            <p className="text-xs uppercase tracking-wide text-muted-foreground font-cairo mb-2">
                              {t('itHubCollabByClassHeader')}
                            </p>
                            <ul className="space-y-2">
                              {(() => {
                                const byClass = new Map();
                                for (const c of hub.collaborators) {
                                  if (!c.class_id) continue;
                                  if (!byClass.has(c.class_id)) {
                                    byClass.set(c.class_id, { class_id: c.class_id, class_name: c.class_name, active: 0, pending: 0 });
                                  }
                                  const row = byClass.get(c.class_id);
                                  if ((c.status || '').toLowerCase() === 'pending') row.pending += 1;
                                  else row.active += 1;
                                }
                                const rows = Array.from(byClass.values());
                                return rows.map((row) => (
                                  <li
                                    key={row.class_id}
                                    className="flex items-center justify-between gap-3 p-3 rounded-xl border border-border/50 bg-muted/10"
                                    data-testid={`it-hub-collab-class-${row.class_id}`}
                                  >
                                    <div className="min-w-0 flex-1">
                                      <p className="text-sm font-cairo font-medium truncate">{row.class_name}</p>
                                      <div className="flex items-center gap-2 mt-1">
                                        <Badge className="bg-emerald-100 text-emerald-700 border-0 text-[10px]">
                                          {t('itHubCollabActive')}: {row.active}
                                        </Badge>
                                        <Badge className="bg-amber-100 text-amber-700 border-0 text-[10px]">
                                          {t('itHubCollabPending')}: {row.pending}
                                        </Badge>
                                      </div>
                                    </div>
                                    <a
                                      href={`/teacher/classes/${row.class_id}?tab=collaborators`}
                                      className="text-xs font-cairo text-brand-navy hover:text-brand-turquoise underline-offset-4 hover:underline shrink-0"
                                      data-testid={`it-hub-collab-class-link-${row.class_id}`}
                                    >
                                      {t('itHubCollabManage')}
                                    </a>
                                  </li>
                                ));
                              })()}
                            </ul>
                          </div>

                          {/* Pending-only mini list — quick cancel without leaving the hub.
                              Task #274 — rendered through ResponsiveTable: a real
                              `<table>` at sm+ keeps email / class / cancel aligned;
                              below 640px each invite collapses to a stacked card
                              with the cancel button full-width so it stays tappable
                              on phones. `data-testid` hooks are preserved for the
                              §6.7 collaborator E2E suite. */}
                          {hub.counts.pending > 0 && (
                            <div data-testid="it-hub-collab-pending-list">
                              <p className="text-xs uppercase tracking-wide text-muted-foreground font-cairo mb-2">
                                {t('itHubCollabPendingHeader')}
                              </p>
                              <ResponsiveTable
                                ariaLabel={t('itHubCollabPendingHeader')}
                                rows={hub.collaborators.filter(
                                  (c) => (c.status || '').toLowerCase() === 'pending',
                                )}
                                getRowKey={(c) => c.id}
                                cardClassName="border-amber-200 bg-amber-50/40"
                                rowClassName="hover:bg-amber-50/40"
                                columns={[
                                  {
                                    key: 'collaborator_email',
                                    header: t('itHubCollabEmailLabel') || 'البريد',
                                    primary: true,
                                    render: (c) => (
                                      <span
                                        className="font-cairo font-medium break-words"
                                        data-testid={`it-hub-collab-pending-row-${c.id}`}
                                      >
                                        {c.collaborator_email}
                                      </span>
                                    ),
                                  },
                                  {
                                    key: 'class_name',
                                    header: t('itHubCollabClassLabel'),
                                    render: (c) => (
                                      <span className="text-xs font-tajawal break-words">
                                        {c.class_name}
                                      </span>
                                    ),
                                  },
                                  {
                                    key: 'actions',
                                    header: '',
                                    cellClassName: 'text-end',
                                    mobileFullWidth: true,
                                    render: (c) => (
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleHubCollabAction(c)}
                                        className="rounded-xl text-amber-700 border-amber-300 hover:bg-amber-100 w-full sm:w-auto"
                                        data-testid={`it-hub-collab-cancel-${c.id}`}
                                      >
                                        {t('itHubCollabCancelInvite')}
                                      </Button>
                                    ),
                                  },
                                ]}
                              />
                            </div>
                          )}
                        </>
                      )}
                    </CardContent>
                  </Card>

                  {/* Sub-card 4: Workspace lifecycle */}
                  <Card className="card-nassaq border-red-200 dark:border-red-900/40" data-testid="it-hub-lifecycle-card">
                    <CardHeader className="pb-4 border-b border-red-200 dark:border-red-900/40 bg-red-50/40 dark:bg-red-950/20">
                      <CardTitle className="font-cairo flex items-center gap-2 text-base text-red-700 dark:text-red-300">
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                        {t('itHubLifecycleTitle')}
                      </CardTitle>
                      <p className="text-xs text-red-600/80 dark:text-red-300/70 font-tajawal mt-1">
                        {t('itHubLifecycleHint')}
                      </p>
                    </CardHeader>
                    <CardContent className="pt-5 space-y-4">
                      <div className="text-sm font-tajawal flex items-center gap-2">
                        <span className="text-muted-foreground">{t('itHubLifecycleStatus')}:</span>
                        {hub.lifecycle?.pending_hard_delete ? (
                          <Badge className="bg-red-100 text-red-700 border-0 text-xs" data-testid="it-hub-lifecycle-status">
                            {t('itHubLifecycleStatusPendingDelete')}
                          </Badge>
                        ) : hub.lifecycle?.archived_at ? (
                          <Badge className="bg-amber-100 text-amber-700 border-0 text-xs" data-testid="it-hub-lifecycle-status">
                            {t('itHubLifecycleStatusArchived')}
                          </Badge>
                        ) : (
                          <Badge className="bg-emerald-100 text-emerald-700 border-0 text-xs" data-testid="it-hub-lifecycle-status">
                            {t('itHubLifecycleStatusActive')}
                          </Badge>
                        )}
                      </div>
                      {hub.lifecycle?.archived_at && (
                        <p className="text-xs text-muted-foreground font-tajawal" data-testid="it-hub-lifecycle-archived-at">
                          {t('itHubLifecycleArchivedOn').replace('{0}', formatHijriDate(new Date(hub.lifecycle.archived_at)))}
                        </p>
                      )}
                      {/* 30-day reactivation countdown — clamped to 0; once
                          pending_hard_delete flips, reactivation is no longer
                          possible and we surface a separate copy line. */}
                      {hub.lifecycle?.archived_at && !hub.lifecycle?.pending_hard_delete && (() => {
                        const archivedMs = new Date(hub.lifecycle.archived_at).getTime();
                        const elapsedDays = Math.floor((Date.now() - archivedMs) / (24 * 60 * 60 * 1000));
                        const remaining = Math.max(0, 30 - elapsedDays);
                        const tone = remaining <= 7 ? 'text-red-600' : remaining <= 14 ? 'text-amber-600' : 'text-emerald-600';
                        return (
                          <p className={`text-xs font-cairo font-medium ${tone}`} data-testid="it-hub-lifecycle-countdown">
                            {t('itHubLifecycleDaysRemaining').replace('{0}', String(remaining))}
                          </p>
                        );
                      })()}
                      {hub.lifecycle?.pending_hard_delete && (
                        <p className="text-xs font-cairo font-medium text-red-600" data-testid="it-hub-lifecycle-window-expired">
                          {t('itHubLifecycleWindowExpired')}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center justify-end gap-2 pt-2 border-t border-border/30">
                        {hub.lifecycle?.archived_at && !hub.lifecycle?.pending_hard_delete && (
                          <Button
                            type="button"
                            variant="outline"
                            onClick={handleHubReactivate}
                            className="rounded-xl border-emerald-300 text-emerald-700 hover:bg-emerald-50 gap-2"
                            data-testid="it-hub-reactivate-btn"
                          >
                            <RotateCcw className="h-4 w-4" />
                            {t('itHubLifecycleReactivate')}
                          </Button>
                        )}
                        <Button
                          type="button"
                          onClick={handleOpenSoftDelete}
                          variant="outline"
                          disabled={!softDeleteEligible || saving || !!hub.lifecycle?.archived_at}
                          className="rounded-xl border-red-300 text-red-600 hover:bg-red-50 gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                          data-testid="it-hub-archive-btn"
                        >
                          <AlertTriangle className="h-4 w-4" />
                          {t('itSoftDeleteOpen')}
                        </Button>
                        {/* Task #276 — IT GDPR right-to-be-forgotten CTA.
                            Distinct from archive: this is a ONE-WAY
                            erasure request that triggers the configured
                            grace window then a physical purge. Disabled
                            once the workspace is already archived/erasure
                            so users cannot double-submit. */}
                        <Button
                          type="button"
                          onClick={handleOpenErasure}
                          disabled={saving || !!hub.lifecycle?.archived_at || !!hub.lifecycle?.pending_hard_delete}
                          className="rounded-xl bg-red-600 hover:bg-red-700 text-white gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                          data-testid="it-hub-erasure-btn"
                        >
                          <Trash2 className="h-4 w-4" />
                          {t('itErasureOpen')}
                        </Button>
                      </div>
                      {!softDeleteEligible && !hub.lifecycle?.archived_at && (
                        <p
                          className="text-xs text-red-600/80 dark:text-red-300/80 font-tajawal rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/40 p-3"
                          data-testid="it-hub-archive-export-required"
                        >
                          {t('itSoftDeleteExportRequired')}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                </div>
              )}

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

        {/* Task #276 — IT account erasure (GDPR right-to-be-forgotten)
            STEP 2 confirm. Step 1 (consequences) is collected via
            NassaqAlertDialog (`nassaqConfirm`) inside
            `handleOpenErasure`. This inline AlertDialog only
            appears after the user accepts step 1; it collects the
            verbatim workspace-name match + explicit acknowledge
            checkbox. Tier-A MFA is collected automatically by the
            AuthContext axios interceptor when the POST returns the
            403 step-up envelope — no extra MFA UI here. */}
        <AlertDialog open={erasureOpen} onOpenChange={setErasureOpen}>
          <AlertDialogContent dir="rtl" data-testid="it-erasure-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle className="font-cairo text-red-700 flex items-center gap-2">
                <Trash2 className="h-4 w-4" />
                {t('itErasureDialogTitle')}
              </AlertDialogTitle>
              <AlertDialogDescription className="font-tajawal text-sm whitespace-pre-wrap">
                {t('itErasureDialogConfirmBody')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="space-y-3 py-2">
              <div className="space-y-2">
                <Label htmlFor="it-erasure-confirm-input" className="font-tajawal text-xs">
                  {t('itErasureConfirmLabel')}
                </Label>
                <Input
                  id="it-erasure-confirm-input"
                  value={erasureConfirmName}
                  onChange={(e) => setErasureConfirmName(e.target.value)}
                  placeholder={t('itErasureConfirmPlaceholder')}
                  data-testid="it-erasure-confirm-input"
                />
              </div>
              <label className="flex items-start gap-2 text-xs font-tajawal text-red-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={erasureAcknowledged}
                  onChange={(e) => setErasureAcknowledged(e.target.checked)}
                  className="mt-0.5 accent-red-600"
                  data-testid="it-erasure-ack-checkbox"
                />
                <span>{t('itErasureAckLabel')}</span>
              </label>
            </div>
            <AlertDialogFooter className="gap-2 flex-row-reverse">
              <Button
                type="button"
                onClick={handleConfirmErasure}
                disabled={
                  saving
                  || !erasureConfirmName.trim()
                  || !erasureAcknowledged
                }
                className="bg-red-600 hover:bg-red-700 text-white rounded-xl gap-2"
                data-testid="it-erasure-confirm-btn"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {t('itErasureConfirm')}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setErasureOpen(false)}
                className="rounded-xl"
                data-testid="it-erasure-cancel-btn"
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
