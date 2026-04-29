import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Switch } from '../../components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { ImageCropModal } from '../../components/ui/ImageCropModal';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import HakimPresence from '../../components/hakim/HakimPresence';
import {
  User, Lock, Bell, Globe, Save, Loader2, Camera, Mail, Phone, Key,
  Eye, EyeOff, Award, BookOpen, Users, CheckCircle2, Activity, Flame,
  Shield, History, Clock, Building2, IdCard, ChevronLeft, ChevronRight,
  Check, X, LogIn, LogOut, ClipboardList, ClipboardCheck, MessageSquare,
  Star, FileText, Trash2, Upload, Settings as SettingsIcon
} from 'lucide-react';

const BG_PATTERN = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/1itjy61q_Nassaq%20Background.png';

const PasswordStrength = ({ password, isRTL }) => {
  const { t } = useTranslation();
  const checks = [
    { test: password.length >= 8, label: t('atLeast8Characters') },
    { test: /[A-Z]/.test(password), label: t('uppercaseLetter') },
    { test: /[a-z]/.test(password), label: t('lowercaseLetter') },
    { test: /[0-9]/.test(password), label: t('number') },
    { test: /[^A-Za-z0-9]/.test(password), label: t('specialCharacter') },
  ];
  const passed = checks.filter(c => c.test).length;
  const strength = passed === 0 ? 0 : passed <= 2 ? 1 : passed <= 3 ? 2 : passed <= 4 ? 3 : 4;
  const labels = isRTL ? ['', 'ضعيفة', 'مقبولة', 'جيدة', 'قوية جداً'] : ['', 'Weak', 'Fair', 'Good', 'Very Strong'];
  const colors = ['', 'bg-red-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500'];
  if (!password) return null;
  return (
    <div className="space-y-2 mt-2">
      <div className="flex gap-1.5">{[1,2,3,4].map(i => <div key={i} className={`h-1.5 flex-1 rounded-full transition-all ${i <= strength ? colors[strength] : 'bg-muted/30'}`} />)}</div>
      <span className={`text-xs font-cairo ${strength >= 3 ? 'text-emerald-600' : strength >= 2 ? 'text-amber-600' : 'text-red-600'}`}>{labels[strength]}</span>
      <div className="grid grid-cols-2 gap-1">{checks.map((c, i) => (
        <div key={i} className="flex items-center gap-1.5">
          {c.test ? <Check className="h-3 w-3 text-emerald-500" /> : <X className="h-3 w-3 text-muted-foreground/40" />}
          <span className={`text-[10px] ${c.test ? 'text-emerald-600' : 'text-muted-foreground/50'}`}>{c.label}</span>
        </div>
      ))}</div>
    </div>
  );
};

const EVENT_META = {
  'auth.login':                { ar: 'تسجيل دخول',          en: 'Login',                icon: LogIn },
  'auth.logout':               { ar: 'تسجيل خروج',          en: 'Logout',               icon: LogOut },
  'session.start':             { ar: 'بدء حصة',             en: 'Session Started',      icon: BookOpen },
  'session.end':               { ar: 'إنهاء حصة',           en: 'Session Ended',        icon: BookOpen },
  'attendance.record':         { ar: 'تسجيل حضور وغياب',    en: 'Attendance Recorded',  icon: ClipboardCheck },
  'attendance.create':         { ar: 'تسجيل حضور وغياب',    en: 'Attendance Recorded',  icon: ClipboardCheck },
  'attendance.update':         { ar: 'تعديل الحضور',        en: 'Attendance Updated',   icon: ClipboardCheck },
  'attendance.bulk_recorded':  { ar: 'تسجيل حضور وغياب',    en: 'Attendance Recorded',  icon: ClipboardCheck },
  'behavior.create':           { ar: 'تسجيل سلوك',          en: 'Behavior Recorded',    icon: Star },
  'behavior.bulk_recorded':    { ar: 'تسجيل سلوك',          en: 'Behavior Recorded',    icon: Star },
  'grade.create':              { ar: 'تسجيل درجات',         en: 'Grades Recorded',      icon: FileText },
  'grade.bulk_recorded':       { ar: 'تسجيل درجات',         en: 'Grades Recorded',      icon: FileText },
  'message.send':              { ar: 'إرسال رسالة',         en: 'Message Sent',         icon: MessageSquare },
  'notification.send':         { ar: 'إرسال إشعار',         en: 'Notification Sent',    icon: Bell },
  'user.update':               { ar: 'تحديث الملف الشخصي',  en: 'Profile Updated',      icon: User },
  'user_updated':              { ar: 'تحديث الملف الشخصي',  en: 'Profile Updated',      icon: User },
  'profile.update':            { ar: 'تحديث الملف الشخصي',  en: 'Profile Updated',      icon: User },
  'password.change':           { ar: 'تغيير كلمة المرور',   en: 'Password Changed',     icon: Key },
  'settings.update':           { ar: 'تحديث الإعدادات',     en: 'Settings Updated',     icon: SettingsIcon },
};

const CATEGORY_ICONS = {
  auth: LogIn,
  session: BookOpen,
  attendance: ClipboardCheck,
  behavior: Star,
  grade: FileText,
  message: MessageSquare,
  notification: Bell,
  user: User,
  profile: User,
  password: Key,
  security: Shield,
  settings: SettingsIcon,
};

const humanizeKey = (key) => {
  if (!key || typeof key !== 'string') return '';
  return key
    .replace(/[._]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const resolveActivity = (act, isRTL, fallbackText) => {
  const action = (act && act.action) || '';
  const meta = EVENT_META[action];
  if (meta) {
    return { label: isRTL ? meta.ar : meta.en, Icon: meta.icon };
  }
  const backendLabel = isRTL ? act?.label_ar : act?.label_en;
  const label = (backendLabel && backendLabel !== action)
    ? backendLabel
    : (humanizeKey(action) || fallbackText);
  const prefix = action.split('.')[0];
  const Icon = CATEGORY_ICONS[prefix] || CATEGORY_ICONS[act?.icon] || Activity;
  return { label, Icon };
};

export default function TeacherSettingsPage() {
  const { t } = useTranslation();
  const { user, api, isRTL, refreshUser } = useAuth();
  const { isDark, toggleTheme, language, setLanguage } = useTheme();
  const { nassaqError } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('profile');

  const [profile, setProfile] = useState({ full_name: '', email: '', phone: '', avatar_url: '' });
  const [teacherInfo, setTeacherInfo] = useState(null);
  const [teachingStats, setTeachingStats] = useState(null);
  const [activities, setActivities] = useState([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  const [notifications, setNotifications] = useState({
    email_notifications: true, sms_notifications: false, push_notifications: true,
    attendance_alerts: true, grade_reminders: true, meeting_reminders: true, behavior_alerts: true,
  });

  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [showPw, setShowPw] = useState({ current: false, new: false, confirm: false });
  const [cropModalOpen, setCropModalOpen] = useState(false);

  const teacherId = user?.teacher_id || user?.id;
  const schoolName = user?.school_name || user?.tenant_name || '';

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    try {
      const [teacherRes, notifRes] = await Promise.all([
        api.get(`/teachers/${teacherId}`).catch(() => null),
        api.get(`/users/${user?.id}/notifications/settings`).catch(() => null),
      ]);

      const teacherData = teacherRes?.data;
      if (teacherData) {
        setTeacherInfo(teacherData);
        setProfile({
          full_name: teacherData.full_name || user?.full_name || '',
          email: teacherData.email || user?.email || '',
          phone: teacherData.phone || user?.phone || '',
          avatar_url: teacherData.avatar_url || user?.avatar_url || '',
        });
      } else {
        setProfile({
          full_name: user?.full_name || '',
          email: user?.email || '',
          phone: user?.phone || '',
          avatar_url: user?.avatar_url || '',
        });
      }

      if (notifRes?.data) setNotifications(prev => ({ ...prev, ...notifRes.data }));
    } catch (e) {
      console.error('Error fetching profile:', e);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, user]);

  const fetchStats = useCallback(async () => {
    if (!teacherId) return;
    try {
      const [metricsRes, dashRes] = await Promise.all([
        api.get(`/teacher/${teacherId}/class-metrics`).catch(() => null),
        api.get(`/teacher/dashboard/${teacherId}`).catch(() => null),
      ]);
      const stats = {};
      if (metricsRes?.data) {
        const classes = Object.values(metricsRes.data);
        if (classes.length > 0) {
          stats.avgAttendance = Math.round(classes.reduce((s, c) => s + (c.attendance_rate || 0), 0) / classes.length);
          stats.avgParticipation = Math.round(classes.reduce((s, c) => s + (c.participation_rate || 0), 0) / classes.length);
          stats.totalSessions = classes.reduce((s, c) => s + (c.total_sessions || 0), 0);
        }
      }
      if (dashRes?.data) {
        stats.classesCount = dashRes.data.stats?.my_classes || 0;
        stats.studentsCount = dashRes.data.stats?.my_students || 0;
      }
      if (Object.keys(stats).length > 0) setTeachingStats(stats);
    } catch (e) { console.error('Error fetching teaching stats:', e); }
  }, [teacherId, api]);

  const fetchActivities = useCallback(async () => {
    if (!teacherId) return;
    setActivitiesLoading(true);
    try {
      const res = await api.get(`/teacher/profile/${teacherId}/activity?limit=50`);
      setActivities(res?.data?.activities || []);
    } catch (e) {
      console.error('Error fetching activities:', e);
      setActivities([]);
    } finally {
      setActivitiesLoading(false);
    }
  }, [teacherId, api]);

  useEffect(() => { fetchProfile(); fetchStats(); }, [fetchProfile, fetchStats]);
  useEffect(() => { if (activeTab === 'activity') fetchActivities(); }, [activeTab, fetchActivities]);

  const saveProfile = async () => {
    setSaving(true);
    try {
      const payload = {};
      if (profile.full_name) payload.full_name = profile.full_name;
      if (profile.email) payload.email = profile.email;
      if (profile.phone) payload.phone = profile.phone;
      if (profile.bio !== undefined && profile.bio !== null) payload.bio = profile.bio;
      await api.put('/users/me/profile', payload);
      await refreshUser?.();
      toast.success(t('profileSavedSuccessfully'));
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (t('errorSavingProfile'));
      nassaqError(msg);
    } finally {
      setSaving(false);
    }
  };

  const saveNotifications = async () => {
    setSaving(true);
    try {
      await api.put(`/users/${user?.id}/notifications/settings`, notifications);
      toast.success(t('notificationSettingsSaved'));
    } catch (e) {
      console.error('Error saving notification settings:', e);
      nassaqError(t('errorSavingSettings'));
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async () => {
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      nassaqError(t('passwordsDoNotMatch4'));
      return;
    }
    if (passwordForm.new_password.length < 8) {
      nassaqError(t('passwordMustBeAtLeast8Characters2'));
      return;
    }
    setSaving(true);
    try {
      await api.put(`/users/${user?.id}/password`, {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      toast.success(t('passwordChangedSuccessfully'));
      setShowPasswordDialog(false);
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (error) {
      const msg = error?.response?.data?.detail;
      nassaqError(msg || (t('errorChangingPassword2')));
    } finally {
      setSaving(false);
    }
  };

  const handleAvatarCropSave = async (base64) => {
    try {
      await api.post('/users/me/avatar', { image_data: base64 });
      setProfile(p => ({ ...p, avatar_url: base64 }));
      window.dispatchEvent(new CustomEvent('user-updated', { detail: { avatar_url: base64 } }));
      await refreshUser?.();
      toast.success(t('profilePictureUpdated'));
    } catch (err) {
      console.error('Error uploading avatar:', err);
      nassaqError(err?.response?.data?.detail || t('errorUploadingImage'));
      throw err;
    }
  };

  const removeAvatar = async () => {
    try {
      await api.put('/users/me/profile', { avatar_url: '' });
      setProfile(p => ({ ...p, avatar_url: '' }));
      await refreshUser?.();
      toast.success(t('profilePictureRemoved'));
    } catch (e) {
      console.error('Error removing avatar:', e);
      nassaqError(t('errorRemovingImage'));
    }
  };

  const handleThemeToggle = () => {
    toggleTheme();
    const willBeDark = !isDark;
    toast.success(
      willBeDark
        ? (t('darkModeEnabled'))
        : (t('lightModeEnabled'))
    );
  };

  const handleLanguageChange = async (lang) => {
    try {
      await api.put('/users/me/preferences', { language: lang });
      setLanguage?.(lang);
      await refreshUser?.();
      toast.success(lang === 'ar' ? 'تم تغيير اللغة إلى العربية' : 'Language changed to English');
    } catch (e) {
      console.error('Error changing language:', e);
      nassaqError(t('errorChangingLanguage'));
    }
  };

  const sections = [
    { id: 'profile', label: t('profile3'), desc: isRTL ? 'البيانات الأساسية' : 'Basic info', icon: User },
    { id: 'security', label: t('security'), desc: t('passwordProtection'), icon: Shield },
    { id: 'notifications', label: t('notifications'), desc: t('alertPreferences'), icon: Bell },
    { id: 'preferences', label: t('preferences'), desc: t('languageAppearance'), icon: Globe },
    { id: 'activity', label: t('activityLog'), desc: t('recentActions'), icon: History },
  ];

  const Chevron = isRTL ? ChevronLeft : ChevronRight;

  const formatTimestamp = (ts) => {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      return d.toLocaleString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' });
    } catch (e) { console.error('Timestamp format error:', e); return ts; }
  };

  const groupActivitiesByDate = (acts) => {
    const groups = {};
    acts.forEach(act => {
      const ts = act.timestamp;
      let dateKey = t('unknownDate');
      if (ts) {
        try {
          dateKey = new Date(ts).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { dateStyle: 'long' });
        } catch (e) { console.error('Date parse error:', e); }
      }
      if (!groups[dateKey]) groups[dateKey] = [];
      groups[dateKey].push(act);
    });
    return groups;
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b">
          <div className="p-4 sm:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-turquoise to-brand-navy flex items-center justify-center shadow-lg">
                  <User className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl sm:text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                    {t('profileSettings')}
                  </h1>
                  <p className="text-sm text-muted-foreground font-cairo">
                    {t('manageYourAccountAndPersonalData')}
                  </p>
                </div>
              </div>
              <div className="hidden sm:flex items-center gap-3 p-3 rounded-2xl bg-gradient-to-r from-violet-50/80 via-cyan-50/50 to-transparent dark:from-violet-900/20 dark:via-cyan-900/10 dark:to-transparent border border-violet-100/50 dark:border-violet-800/30">
                <HakimPresence size="sm" showMessage={true} messagePosition="bottom" />
              </div>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-32">
            <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise" />
          </div>
        ) : (
          <div className="p-4 sm:p-6">
            <div className="grid lg:grid-cols-[280px_1fr] gap-6">
              <div className="space-y-4">
                <Card>
                  <div className="h-20 bg-gradient-to-r from-brand-turquoise to-brand-navy relative rounded-t-lg" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: 'cover', backgroundBlendMode: 'overlay' }} />
                  <CardContent className="pt-0 pb-4 -mt-10 text-center">
                    <div className="relative inline-block">
                      <Avatar className="h-20 w-20 border-4 border-white dark:border-gray-800 shadow-lg">
                        <AvatarImage src={profile.avatar_url} />
                        <AvatarFallback className="bg-brand-navy text-white text-2xl font-cairo">{profile.full_name?.charAt(0) || 'م'}</AvatarFallback>
                      </Avatar>
                      <button type="button" onClick={() => setCropModalOpen(true)} className="absolute -bottom-1 -end-1 z-10 w-7 h-7 rounded-full bg-brand-turquoise text-white flex items-center justify-center shadow-md hover:scale-110 transition-transform cursor-pointer">
                        <Camera className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <h3 className="font-bold text-lg mt-3 font-cairo text-foreground">{profile.full_name}</h3>
                    <Badge variant="outline" className="mt-1 text-brand-turquoise border-brand-turquoise/30 bg-brand-turquoise/5">
                      {t('teacher')}
                    </Badge>
                    {schoolName && (
                      <div className="flex items-center justify-center gap-1.5 mt-2 text-xs text-muted-foreground">
                        <Building2 className="h-3 w-3" />
                        <span className="font-cairo">{schoolName}</span>
                      </div>
                    )}
                    {teacherInfo?.teacher_number && (
                      <div className="flex items-center justify-center gap-1.5 mt-1 text-xs text-muted-foreground">
                        <IdCard className="h-3 w-3" />
                        <span dir="ltr">{teacherInfo.teacher_number}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-2">
                    <nav className="space-y-1">
                      {sections.map(s => {
                        const Icon = s.icon;
                        const active = activeTab === s.id;
                        return (
                          <button key={s.id} onClick={() => setActiveTab(s.id)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-cairo transition-all text-start ${active ? 'bg-gradient-to-r from-brand-turquoise/10 to-brand-purple/5 text-brand-turquoise border border-brand-turquoise/20 shadow-sm' : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'}`}>
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${active ? 'bg-brand-turquoise/15' : 'bg-muted/30'}`}>
                              <Icon className={`h-4 w-4 ${active ? 'text-brand-turquoise' : ''}`} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className={`font-medium text-sm ${active ? 'text-foreground' : ''}`}>{s.label}</p>
                              <p className="text-[10px] text-muted-foreground truncate">{s.desc}</p>
                            </div>
                            {active && <Chevron className="h-4 w-4 text-brand-turquoise shrink-0" />}
                          </button>
                        );
                      })}
                    </nav>
                  </CardContent>
                </Card>
              </div>

              <div className="space-y-6">
                {activeTab === 'profile' && (
                  <>
                    {teachingStats && (
                      <Card>
                        <CardContent className="p-4">
                          <div className="flex items-center gap-2 mb-4">
                            <Award className="h-4 w-4 text-brand-turquoise" />
                            <span className="font-cairo font-bold text-sm text-brand-navy dark:text-brand-turquoise">{t('teachingStats')}</span>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                            {[
                              { label: t('myClasses'), value: teachingStats.classesCount || 0, icon: BookOpen, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-900/30' },
                              { label: t('myStudents'), value: teachingStats.studentsCount || 0, icon: Users, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-900/30' },
                              { label: t('attendanceRateLabel'), value: `${teachingStats.avgAttendance || 0}%`, icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-900/30' },
                              { label: t('participation'), value: `${teachingStats.avgParticipation || 0}%`, icon: Activity, color: 'text-purple-600', bg: 'bg-purple-50 dark:bg-purple-900/30' },
                              { label: t('totalSessionsLabel'), value: teachingStats.totalSessions || 0, icon: Flame, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-900/30' },
                            ].map(stat => (
                              <div key={stat.label} className={`flex items-center gap-2.5 p-3 rounded-xl ${stat.bg} border border-transparent`}>
                                <stat.icon className={`h-5 w-5 ${stat.color} shrink-0`} />
                                <div className="min-w-0">
                                  <p className="text-base font-bold font-cairo text-foreground">{stat.value}</p>
                                  <p className="text-[10px] text-muted-foreground truncate font-cairo">{stat.label}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    <Card>
                      <CardHeader className="pb-4">
                        <CardTitle className="text-lg font-cairo flex items-center gap-2">
                          <User className="h-5 w-5 text-brand-turquoise" />
                          {t('personalInformation')}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-5">
                        <div className="grid sm:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label className="flex items-center gap-1.5 text-sm font-cairo"><User className="h-3.5 w-3.5 text-muted-foreground" />{t('fullName')}</Label>
                            <Input value={profile.full_name} disabled className="bg-muted/30 cursor-not-allowed" />
                            <p className="text-[10px] text-muted-foreground font-cairo">{t('nameCanOnlyBeChangedByAdmin')}</p>
                          </div>
                          <div className="space-y-2">
                            <Label className="flex items-center gap-1.5 text-sm font-cairo"><Mail className="h-3.5 w-3.5 text-muted-foreground" />{t('email2')}</Label>
                            <Input value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} type="email" dir="ltr" />
                          </div>
                          <div className="space-y-2">
                            <Label className="flex items-center gap-1.5 text-sm font-cairo"><Phone className="h-3.5 w-3.5 text-muted-foreground" />{t('phoneNumber')}</Label>
                            <Input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} dir="ltr" placeholder="+966 5XX XXX XXXX" />
                          </div>
                          <div className="space-y-2">
                            <Label className="flex items-center gap-1.5 text-sm font-cairo"><Building2 className="h-3.5 w-3.5 text-muted-foreground" />{t('school')}</Label>
                            <Input value={schoolName} disabled className="bg-muted/30 cursor-not-allowed" />
                          </div>
                          <div className="space-y-2">
                            <Label className="flex items-center gap-1.5 text-sm font-cairo"><Shield className="h-3.5 w-3.5 text-muted-foreground" />{t('role2')}</Label>
                            <Input value={t('teacher')} disabled className="bg-muted/30 cursor-not-allowed" />
                          </div>
                          {teacherInfo?.teacher_number && (
                            <div className="space-y-2">
                              <Label className="flex items-center gap-1.5 text-sm font-cairo"><IdCard className="h-3.5 w-3.5 text-muted-foreground" />{t('teacherId')}</Label>
                              <Input value={teacherInfo.teacher_number} disabled className="bg-muted/30 cursor-not-allowed" dir="ltr" />
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-3 pt-2">
                          <Button onClick={saveProfile} disabled={saving} className="bg-brand-turquoise hover:bg-brand-turquoise/90">
                            {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
                            {t('saveChanges2')}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="pb-4">
                        <CardTitle className="text-lg font-cairo flex items-center gap-2">
                          <Camera className="h-5 w-5 text-brand-turquoise" />
                          {t('profilePicture')}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center gap-5">
                          <Avatar className="h-24 w-24 border-2 border-muted">
                            <AvatarImage src={profile.avatar_url} />
                            <AvatarFallback className="bg-brand-navy text-white text-3xl font-cairo">{profile.full_name?.charAt(0) || 'م'}</AvatarFallback>
                          </Avatar>
                          <div className="space-y-2">
                            <div className="flex items-center gap-2">
                              <Button variant="outline" size="sm" onClick={() => setCropModalOpen(true)}>
                                <Upload className="h-4 w-4 me-1.5" />{t('uploadPhoto')}
                              </Button>
                              {profile.avatar_url && (
                                <Button variant="outline" size="sm" onClick={removeAvatar} className="text-red-500 hover:text-red-600">
                                  <Trash2 className="h-4 w-4 me-1.5" />{t('remove')}
                                </Button>
                              )}
                            </div>
                            <p className="text-[10px] text-muted-foreground font-cairo">{t('jpgPngOrWebpMax5mb')}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </>
                )}

                {activeTab === 'security' && (
                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="text-lg font-cairo flex items-center gap-2">
                        <Shield className="h-5 w-5 text-brand-turquoise" />
                        {t('securityPassword')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="p-4 rounded-xl border hover:shadow-sm transition-shadow">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                              <Key className="h-5 w-5 text-amber-600" />
                            </div>
                            <div>
                              <p className="font-medium font-cairo">{t('password')}</p>
                              <p className="text-xs text-muted-foreground font-cairo">{t('changeYourAccountPassword2')}</p>
                            </div>
                          </div>
                          <Button variant="outline" onClick={() => setShowPasswordDialog(true)}>
                            <Lock className="h-4 w-4 me-1.5" />{t('change')}
                          </Button>
                        </div>
                      </div>

                      <div className="p-4 rounded-xl border">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-green-50 dark:bg-green-900/30 flex items-center justify-center">
                              <CheckCircle2 className="h-5 w-5 text-green-600" />
                            </div>
                            <div>
                              <p className="font-medium font-cairo">{t('accountStatus')}</p>
                              <p className="text-xs text-muted-foreground font-cairo">{t('yourAccountIsActiveAndProtected')}</p>
                            </div>
                          </div>
                          <Badge className="bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 border-0">
                            {t('active')}
                          </Badge>
                        </div>
                      </div>

                      <div className="p-4 rounded-xl border">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center">
                              <Mail className="h-5 w-5 text-blue-600" />
                            </div>
                            <div>
                              <p className="font-medium font-cairo">{t('linkedEmail')}</p>
                              <p className="text-xs text-muted-foreground" dir="ltr">{profile.email}</p>
                            </div>
                          </div>
                          <Badge variant="outline" className="text-blue-600 border-blue-200">
                            {t('verified2')}
                          </Badge>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {activeTab === 'notifications' && (
                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="text-lg font-cairo flex items-center gap-2">
                        <Bell className="h-5 w-5 text-brand-turquoise" />
                        {t('notificationSettings')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      <div>
                        <h3 className="font-medium font-cairo text-sm mb-3">{t('notificationMethods')}</h3>
                        <div className="space-y-3">
                          {[
                            { key: 'email_notifications', labelAr: 'إشعارات البريد', labelEn: 'Email Notifications', descAr: 'استلام الإشعارات عبر البريد الإلكتروني', descEn: 'Receive notifications via email' },
                            { key: 'sms_notifications', labelAr: 'الرسائل النصية', labelEn: 'SMS Notifications', descAr: 'استلام الإشعارات عبر الرسائل النصية', descEn: 'Receive text message notifications' },
                            { key: 'push_notifications', labelAr: 'الإشعارات الفورية', labelEn: 'Push Notifications', descAr: 'إشعارات التطبيق والمتصفح', descEn: 'Browser and in-app notifications' },
                          ].map(item => (
                            <div key={item.key} className="flex items-center justify-between p-4 rounded-xl border hover:bg-muted/20 transition-colors">
                              <div>
                                <p className="font-medium text-sm font-cairo">{isRTL ? item.labelAr : item.labelEn}</p>
                                <p className="text-xs text-muted-foreground font-cairo mt-0.5">{isRTL ? item.descAr : item.descEn}</p>
                              </div>
                              <Switch checked={notifications[item.key]} onCheckedChange={(v) => setNotifications({ ...notifications, [item.key]: v })} />
                            </div>
                          ))}
                        </div>
                      </div>

                      <div>
                        <h3 className="font-medium font-cairo text-sm mb-3">{t('alertTypes')}</h3>
                        <div className="space-y-3">
                          {[
                            { key: 'attendance_alerts', labelAr: 'تنبيهات الحضور', labelEn: 'Attendance Alerts', descAr: 'تنبيهات غياب الطلاب والتأخر', descEn: 'Student absence and tardiness alerts' },
                            { key: 'grade_reminders', labelAr: 'تذكير الدرجات', labelEn: 'Grade Reminders', descAr: 'تذكيرات إدخال الدرجات والتقييمات', descEn: 'Grade entry and assessment reminders' },
                            { key: 'behavior_alerts', labelAr: 'تنبيهات السلوك', labelEn: 'Behavior Alerts', descAr: 'إشعارات بسلوكيات الطلاب الملحوظة', descEn: 'Notable student behavior notifications' },
                            { key: 'meeting_reminders', labelAr: 'تذكير الاجتماعات', labelEn: 'Meeting Reminders', descAr: 'تذكيرات بالاجتماعات والمواعيد', descEn: 'Meeting and appointment reminders' },
                          ].map(item => (
                            <div key={item.key} className="flex items-center justify-between p-4 rounded-xl border hover:bg-muted/20 transition-colors">
                              <div>
                                <p className="font-medium text-sm font-cairo">{isRTL ? item.labelAr : item.labelEn}</p>
                                <p className="text-xs text-muted-foreground font-cairo mt-0.5">{isRTL ? item.descAr : item.descEn}</p>
                              </div>
                              <Switch checked={notifications[item.key]} onCheckedChange={(v) => setNotifications({ ...notifications, [item.key]: v })} />
                            </div>
                          ))}
                        </div>
                      </div>

                      <Button onClick={saveNotifications} disabled={saving} className="bg-brand-turquoise hover:bg-brand-turquoise/90">
                        {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
                        {t('saveNotificationSettings')}
                      </Button>
                    </CardContent>
                  </Card>
                )}

                {activeTab === 'preferences' && (
                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="text-lg font-cairo flex items-center gap-2">
                        <Globe className="h-5 w-5 text-brand-turquoise" />
                        {t('preferences')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-5">
                      <div className="p-4 rounded-xl border">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-brand-turquoise/10 flex items-center justify-center">
                              <Globe className="h-5 w-5 text-brand-turquoise" />
                            </div>
                            <div>
                              <p className="font-medium font-cairo">{t('interfaceLanguage')}</p>
                              <p className="text-xs text-muted-foreground font-cairo">{t('chooseYourPreferredLanguage')}</p>
                            </div>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <button onClick={() => handleLanguageChange('ar')} className={`p-4 rounded-xl border-2 text-center transition-all ${(language || user?.preferred_language) === 'ar' ? 'border-brand-turquoise bg-brand-turquoise/5 shadow-sm' : 'border-muted hover:border-brand-turquoise/30'}`}>
                            <span className="text-2xl mb-1 block">🇸🇦</span>
                            <p className="font-cairo font-medium text-sm">العربية</p>
                            <p className="text-[10px] text-muted-foreground">Arabic</p>
                          </button>
                          <button onClick={() => handleLanguageChange('en')} className={`p-4 rounded-xl border-2 text-center transition-all ${(language || user?.preferred_language) === 'en' ? 'border-brand-turquoise bg-brand-turquoise/5 shadow-sm' : 'border-muted hover:border-brand-turquoise/30'}`}>
                            <span className="text-2xl mb-1 block">🇬🇧</span>
                            <p className="font-medium text-sm">English</p>
                            <p className="text-[10px] text-muted-foreground">الإنجليزية</p>
                          </button>
                        </div>
                      </div>

                      <div className="p-4 rounded-xl border">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isDark ? 'bg-indigo-900/30' : 'bg-amber-50'}`}>
                              {isDark ? <span className="text-lg">🌙</span> : <span className="text-lg">☀️</span>}
                            </div>
                            <div>
                              <p className="font-medium font-cairo">{t('appearance')}</p>
                              <p className="text-xs text-muted-foreground font-cairo">{isDark ? (t('darkModeEnabled2')) : (t('lightModeEnabled2'))}</p>
                            </div>
                          </div>
                          <Switch checked={isDark} onCheckedChange={handleThemeToggle} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {activeTab === 'activity' && (
                  <Card>
                    <CardHeader className="pb-4">
                      <CardTitle className="text-lg font-cairo flex items-center gap-2">
                        <History className="h-5 w-5 text-brand-turquoise" />
                        {t('activityLog')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {activitiesLoading ? (
                        <div className="flex items-center justify-center py-16">
                          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                        </div>
                      ) : activities.length === 0 ? (
                        <div className="flex flex-col items-center py-16 text-center">
                          <History className="h-12 w-12 mb-3 text-muted-foreground/30" />
                          <p className="text-muted-foreground font-cairo">{t('noActivitiesRecordedYet')}</p>
                          <p className="text-xs text-muted-foreground/60 mt-1 font-cairo">{t('yourActivitiesWillAppearHereAsYouUseThePlatform')}</p>
                        </div>
                      ) : (
                        <div className="space-y-8">
                          {Object.entries(groupActivitiesByDate(activities)).map(([date, acts]) => (
                            <div key={date}>
                              <div className="flex items-center gap-3 mb-4">
                                <span className="text-sm font-semibold text-brand-navy dark:text-brand-turquoise font-cairo">{date}</span>
                                <Badge variant="secondary" className="bg-brand-turquoise/10 text-brand-turquoise border-0 text-[11px] h-5 px-2 font-cairo font-medium">
                                  {isRTL
                                    ? `${acts.length} ${acts.length === 1 ? 'حدث' : (acts.length === 2 ? 'حدثان' : 'أحداث')}`
                                    : `${acts.length} ${acts.length === 1 ? 'event' : 'events'}`}
                                </Badge>
                                <div className="flex-1 h-px bg-border" />
                              </div>
                              <div className="relative">
                                <div
                                  className="absolute top-4 bottom-4 w-px bg-brand-turquoise/30 pointer-events-none"
                                  style={isRTL ? { right: '30px' } : { left: '30px' }}
                                  aria-hidden
                                />
                                <div className="space-y-3 relative">
                                  {acts.map((act, idx) => {
                                    const { label, Icon } = resolveActivity(act, isRTL, t('unknownEvent'));
                                    return (
                                      <div
                                        key={act.id || idx}
                                        className="flex items-start gap-4 p-3 rounded-xl hover:bg-muted/30 transition-colors"
                                      >
                                        <div className="relative z-10 w-9 h-9 rounded-full bg-white dark:bg-gray-900 border-2 border-brand-turquoise/40 flex items-center justify-center shadow-sm shrink-0">
                                          <Icon className="h-4 w-4 text-brand-turquoise" />
                                        </div>
                                        <div className="flex-1 min-w-0 pt-1">
                                          <p className="font-semibold text-sm text-foreground font-cairo leading-tight">
                                            {label}
                                          </p>
                                          {act.description && typeof act.description === 'string' && (
                                            <p className="text-xs text-muted-foreground mt-1 line-clamp-1 font-cairo">
                                              {act.description}
                                            </p>
                                          )}
                                          <div className="flex items-center gap-2 mt-2">
                                            <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 font-cairo">
                                              <Clock className="h-3 w-3" />
                                              {act.timestamp
                                                ? new Date(act.timestamp).toLocaleTimeString(
                                                    isRTL ? 'ar-SA' : 'en-US',
                                                    { timeStyle: 'short' }
                                                  )
                                                : ''}
                                            </span>
                                            {act.page && (
                                              <Badge variant="outline" className="text-[10px] h-5 px-1.5 font-cairo border-muted-foreground/20 text-muted-foreground/80">
                                                {act.page}
                                              </Badge>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}

        <Dialog open={showPasswordDialog} onOpenChange={setShowPasswordDialog}>
          <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <Lock className="h-5 w-5 text-brand-turquoise" />
                {t('changePassword')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label className="font-cairo">{t('currentPassword')}</Label>
                <div className="relative">
                  <Input type={showPw.current ? 'text' : 'password'} value={passwordForm.current_password} onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })} dir="ltr" className="pe-10" />
                  <button type="button" onClick={() => setShowPw({ ...showPw, current: !showPw.current })} className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPw.current ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <Label className="font-cairo">{t('newPassword')}</Label>
                <div className="relative">
                  <Input type={showPw.new ? 'text' : 'password'} value={passwordForm.new_password} onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })} dir="ltr" className="pe-10" />
                  <button type="button" onClick={() => setShowPw({ ...showPw, new: !showPw.new })} className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPw.new ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <PasswordStrength password={passwordForm.new_password} isRTL={isRTL} />
              </div>
              <div className="space-y-2">
                <Label className="font-cairo">{t('confirmNewPassword')}</Label>
                <div className="relative">
                  <Input type={showPw.confirm ? 'text' : 'password'} value={passwordForm.confirm_password} onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })} dir="ltr" className="pe-10" />
                  <button type="button" onClick={() => setShowPw({ ...showPw, confirm: !showPw.confirm })} className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showPw.confirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {passwordForm.confirm_password && passwordForm.new_password !== passwordForm.confirm_password && (
                  <p className="text-xs text-red-500 font-cairo flex items-center gap-1"><X className="h-3 w-3" />{t('passwordsDoNotMatch5')}</p>
                )}
                {passwordForm.confirm_password && passwordForm.new_password === passwordForm.confirm_password && passwordForm.new_password.length > 0 && (
                  <p className="text-xs text-emerald-500 font-cairo flex items-center gap-1"><Check className="h-3 w-3" />{t('passwordsMatch2')}</p>
                )}
              </div>
            </div>
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => { setShowPasswordDialog(false); setPasswordForm({ current_password: '', new_password: '', confirm_password: '' }); }}>
                {t('cancel')}
              </Button>
              <Button onClick={changePassword} disabled={saving || !passwordForm.current_password || !passwordForm.new_password || passwordForm.new_password !== passwordForm.confirm_password} className="bg-brand-turquoise hover:bg-brand-turquoise/90">
                {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Lock className="h-4 w-4 me-2" />}
                {t('changePassword')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <div className="sm:hidden fixed bottom-4 start-4 z-30">
          <div className="flex items-center gap-2 p-2 rounded-2xl bg-gradient-to-r from-violet-50/90 via-cyan-50/70 to-transparent dark:from-violet-900/30 dark:via-cyan-900/20 dark:to-transparent border border-violet-100/50 dark:border-violet-800/30 shadow-lg backdrop-blur-sm">
            <HakimPresence size="sm" showMessage={true} messagePosition="bottom" />
          </div>
        </div>
      </div>
      <ImageCropModal
        open={cropModalOpen}
        onOpenChange={setCropModalOpen}
        onSave={handleAvatarCropSave}
        isRTL={isRTL}
      />
    </Sidebar>
  );
}
