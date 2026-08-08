import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { PageHeader } from '@/shared/components/layout/PageHeader';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { useAuth } from '@/shared/contexts/AuthContext';
import { DEFAULT_PLATFORM_ADDRESS_AR } from '@/shared/models/constants/platformContact';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Switch } from '@/shared/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Separator } from '@/shared/components/ui/separator';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/shared/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import {
  Settings,
  Save,
  RefreshCw,
  User,
  Building2,
  Palette,
  FileText,
  Shield,
  Mail,
  Phone,
  Globe,
  Lock,
  Key,
  Eye,
  EyeOff,
  LogOut,
  Users,
  Clock,
  Calendar,
  MapPin,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Info,
  Camera,
  Upload,
  Edit,
  Languages,
  Sun,
  Moon,
  Bell,
  Smartphone,
  History,
  Monitor,
  ChevronRight,
  X,
  Copy,
  Check,
  ExternalLink,
  Twitter,
  Facebook,
  Instagram,
  Linkedin,
  Youtube,
  Link2,
  Hash,
  AtSign,
  Server,
  Database,
  HardDrive,
  Activity,
  Zap,
  Trash2,
} from 'lucide-react';

// Translations
// Navigation tabs
// Task #173: the personal "Account" tab has been removed from Platform
// Settings — every personal field (profile photo, name, phone, email,
// language, password, MFA, sessions, notifications, preferences) is owned
// exclusively by `/account/settings` (AccountSettingsPage). Platform
// admins reach it via the new sidebar entry. Platform Settings is now
// platform/system configuration only.
// SETTINGS_TABS lives in its own pure module (`./platformSettingsTabs`) so the
// regression test can import it without dragging in router/auth/axios. The
// re-export here keeps any prior `import { SETTINGS_TABS } from '.../PlatformSettingsPage'`
// callers working.
export { SETTINGS_TABS } from './platformSettingsTabs';
import { SETTINGS_TABS } from './platformSettingsTabs';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

// Active sessions - fetched from API (empty by default)
const INITIAL_ACTIVE_SESSIONS = [];

// Version history - fetched from API (empty by default)
const INITIAL_VERSION_HISTORY = [];

export const PlatformSettingsPage = () => {
  const { t } = useTranslation();
  const { isRTL = true, isDark, toggleTheme, toggleLanguage } = useTheme();
  const { user, logout, token, refreshUser, api } = useAuth();
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  
  // States
  // Task #173: default landing tab is now General (was 'account', which no
  // longer exists on this surface).
  const [activeTab, setActiveTab] = useState('general');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [showLogoutDialog, setShowLogoutDialog] = useState(false);
  const [showSwitchUserDialog, setShowSwitchUserDialog] = useState(false);
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showVersionHistoryDialog, setShowVersionHistoryDialog] = useState(false);
  const [copiedField, setCopiedField] = useState(null);
  const [versionHistory, setVersionHistory] = useState([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [initialSnapshots, setInitialSnapshots] = useState({});
  const [systemInfo, setSystemInfo] = useState(null);
  const [systemInfoLoading, setSystemInfoLoading] = useState(false);
  const [systemInfoError, setSystemInfoError] = useState(false);
  
  // Task #173: account/profile data and password form moved to
  // AccountSettingsPage. PlatformSettingsPage no longer owns any personal
  // identity state.

  // General settings
  const [generalSettings, setGeneralSettings] = useState({
    platformNameAr: 'نَسَّق | NASSAQ',
    platformNameEn: 'NASSAQ',
    browserTitle: 'نَسَّق - منصة إدارة المدارس الذكية',
    defaultLanguage: 'ar',
    dateFormat: 'hijri',
    timezone: 'Asia/Riyadh',
    emailNotifications: true,
    smsNotifications: false,
    pushNotifications: true,
    aiFeatures: true,
    registrationOpen: true,
    maintenanceMode: false,
  });
  
  const [contactInfo, setContactInfo] = useState({
    primaryEmail: 'info@nassaqapp.com',
    supportEmail: 'support@nassaqapp.com',
    primaryPhone: '+966 11 234 5678',
    alternatePhone: '+966 11 234 5679',
    address: DEFAULT_PLATFORM_ADDRESS_AR,
    workingHours: 'الأحد - الخميس: 8:00 ص - 4:00 م',
    website: 'https://nassaqapp.com',
    ownerName: 'شركة نَسَّق للتقنية التعليمية',
    socialMedia: {
      twitter: 'https://twitter.com/nassaqapp',
      facebook: '',
      instagram: '',
      linkedin: 'https://linkedin.com/company/nassaq',
      youtube: '',
    },
  });

  // Task #172 P0: dropped the `twoFactorEnabled` field entirely. The toggle
  // it backed never reached the server — the `/settings/security` PUT handler
  // doesn't accept it and would now reject it (extra='forbid' on the schema).
  // Per-account MFA lives in Account Settings → Security (MfaSecuritySection).
  const [securitySettings, setSecuritySettings] = useState({
    sessionTimeout: 30,
    maxSessions: 5,
    passwordMinLength: 8,
    passwordRequireUppercase: true,
    passwordRequireNumbers: true,
    passwordRequireSpecial: true,
  });

  // Load settings from API using new endpoints
  const fetchSettings = React.useCallback(async () => {
      try {
        // Fetch general settings
        const generalResponse = await api.get('/settings/general');
        if (generalResponse.data) {
          const data = generalResponse.data;
          setGeneralSettings({
            platformNameAr: data.platform_name || 'نَسَّق | NASSAQ',
            platformNameEn: data.platform_name_en || 'NASSAQ',
            browserTitle: data.browser_title || 'نَسَّق - منصة إدارة المدارس الذكية',
            defaultLanguage: data.default_language || 'ar',
            dateFormat: data.date_system || 'both',
            timezone: data.timezone || 'Asia/Riyadh',
            emailNotifications: true,
            smsNotifications: false,
            pushNotifications: true,
            aiFeatures: true,
            registrationOpen: true,
            maintenanceMode: false,
          });
        }
        
        // Fetch maintenance settings
        const maintenanceResponse = await api.get('/settings/maintenance');
        if (maintenanceResponse.data) {
          setGeneralSettings(prev => ({
            ...prev,
            maintenanceMode: maintenanceResponse.data.maintenance_mode || false,
            registrationOpen: maintenanceResponse.data.registration_open ?? true,
          }));
        }
        
        // Fetch contact info
        const contactResponse = await api.get('/settings/contact');
        if (contactResponse.data) {
          const data = contactResponse.data;
          setContactInfo({
            primaryEmail: data.email || 'info@nassaqapp.com',
            supportEmail: data.email || 'support@nassaqapp.com',
            primaryPhone: data.phone || '+966 11 234 5678',
            alternatePhone: '',
            address: data.address_ar || DEFAULT_PLATFORM_ADDRESS_AR,
            workingHours: data.working_hours_ar || 'الأحد - الخميس: 8:00 ص - 4:00 م',
            website: '',
            ownerName: 'شركة نَسَّق للتقنية التعليمية',
            socialMedia: {
              twitter: data.social_twitter || '',
              facebook: data.social_facebook || '',
              instagram: data.social_instagram || '',
              linkedin: data.social_linkedin || '',
              youtube: data.social_youtube || '',
            },
          });
        }
        
        // Fetch security settings
        const securityResponse = await api.get('/settings/security');
        if (securityResponse.data) {
          const data = securityResponse.data;
          setSecuritySettings({
            sessionTimeout: data.session_duration_minutes || 60,
            maxSessions: data.max_concurrent_sessions || 3,
            passwordMinLength: data.min_password_length || 8,
            passwordRequireUppercase: (data.require_uppercase || 1) > 0,
            passwordRequireNumbers: (data.require_numbers || 1) > 0,
            passwordRequireSpecial: (data.require_special_chars || 1) > 0,
          });
        }
        
        // Task #173: account/title fetches moved to AccountSettingsPage.
        // Terms versions fetch removed: T&C is now centrally maintained at /terms.

        // Fetch privacy versions
        const privacyResponse = await api.get('/settings/privacy/versions');
        if (privacyResponse.data?.length > 0) {
          const publishedVersion = privacyResponse.data.find(v => v.is_published);
          if (publishedVersion) {
            setPrivacyData({
              content: publishedVersion.content_ar || '',
              version: `${publishedVersion.version_number}.0`,
              lastUpdated: publishedVersion.created_at,
              effectiveDate: publishedVersion.published_at,
            });
          }
        }
        
      } catch (error) {
        console.error('Error fetching settings:', error);
      } finally {
        setInitialLoading(false);
        setTimeout(() => {
          setInitialSnapshots({ _loaded: true, _reset: Date.now() });
        }, 200);
      }
  }, [api]);

  useEffect(() => {
    if (token) {
      fetchSettings();
    }
  }, [fetchSettings, token]);

  useEffect(() => {
    if (!initialSnapshots._loaded) return;
    // Task #173: dropped the "account" snapshot key — personal data is no
    // longer tracked here. Dirty-state now reflects platform-config tabs only.
    if (!initialSnapshots.general) {
      setInitialSnapshots(prev => ({
        ...prev,
        general: JSON.stringify(generalSettings),
        contact: JSON.stringify(contactInfo),
        security: JSON.stringify(securitySettings),
      }));
      return;
    }
    const currentMap = {
      general: JSON.stringify(generalSettings),
      contact: JSON.stringify(contactInfo),
      security: JSON.stringify(securitySettings),
    };
    const changed = Object.keys(currentMap).some(k => initialSnapshots[k] && currentMap[k] !== initialSnapshots[k]);
    setHasUnsavedChanges(changed);
  }, [generalSettings, contactInfo, securitySettings, initialSnapshots]);

  useEffect(() => {
    const handler = (e) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasUnsavedChanges]);
  
  // Brand settings
  const [brandSettings, setBrandSettings] = useState({
    logo: null,
    favicon: null,
    primaryColor: '#1e3a5f',
    secondaryColor: '#3b82f6',
    accentColor: '#10b981',
  });
  
  // T&C state removed — public /terms page owns the canonical content.

  const [privacyData, setPrivacyData] = useState({
    content: `سياسة الخصوصية لمنصة نَسَّق التعليمية

1. جمع المعلومات
نقوم بجمع المعلومات التي تقدمها لنا مباشرة عند:
- إنشاء حساب
- استخدام خدماتنا
- التواصل معنا

2. استخدام المعلومات
نستخدم المعلومات المجمعة لـ:
- تقديم وتحسين خدماتنا
- التواصل معكم
- ضمان أمان المنصة

3. مشاركة المعلومات
لا نشارك معلوماتكم الشخصية مع أطراف ثالثة إلا في الحالات التالية:
- بموافقتكم الصريحة
- للامتثال للقوانين
- لحماية حقوقنا

4. أمان البيانات
نستخدم تقنيات تشفير متقدمة لحماية بياناتكم.

5. حقوقكم
لديكم الحق في الوصول إلى بياناتكم وتصحيحها أو حذفها.`,
    version: '2.0',
    lastUpdated: '2026-02-15T00:00:00Z',
    effectiveDate: '2026-03-01T00:00:00Z',
  });
  
  // Format date
  const formatDateTime = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };
  
  // Copy to clipboard
  const copyToClipboard = async (text, field) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
      toast.success(isRTL ? 'تم النسخ' : 'Copied');
    } catch (err) {
      nassaqError(t('copyFailed'));
    }
  };
  
  // Save general settings using new API
  const handleSaveGeneralSettings = async () => {
    setLoading(true);
    try {
      await api.put('/settings/general', {
        platform_name: generalSettings.platformNameAr,
        platform_name_en: generalSettings.platformNameEn,
        browser_title: generalSettings.browserTitle,
        default_language: generalSettings.defaultLanguage,
        date_system: generalSettings.dateFormat,
        timezone: generalSettings.timezone,
      });
      
      // Save maintenance settings separately
      await api.put('/settings/maintenance', {
        maintenance_mode: generalSettings.maintenanceMode,
        registration_open: generalSettings.registrationOpen,
      });
      
      toast.success(t('savedSuccessfully'));
      await fetchSettings();
    } catch (error) {
      console.error('Error saving general settings:', error);
      nassaqError(getApiErrorMessage(error) || (t('saveFailed2')));
    } finally {
      setLoading(false);
    }
  };
  
  // Task #172 P1: Visual Identity tab is preview-only — there is no
  // backend endpoint and no transient UI feedback fires from the global
  // Save button. The Save action is also disabled at the header level
  // when activeTab === 'brand', so this handler is a defensive no-op.
  const handleSaveBrandSettings = async () => {
    return;
  };
  
  // Save contact settings using new API
  const handleSaveContactSettings = async () => {
    setLoading(true);
    try {
      await api.put('/settings/contact', {
        email: contactInfo.primaryEmail,
        phone: contactInfo.primaryPhone,
        working_hours_ar: contactInfo.workingHours,
        working_hours_en: contactInfo.workingHours,
        address_ar: contactInfo.address,
        address_en: contactInfo.address,
        social_twitter: contactInfo.socialMedia.twitter,
        social_linkedin: contactInfo.socialMedia.linkedin,
        social_instagram: contactInfo.socialMedia.instagram,
        social_facebook: contactInfo.socialMedia.facebook,
        social_youtube: contactInfo.socialMedia.youtube,
      });
      toast.success(t('savedSuccessfully'));
      await fetchSettings();
    } catch (error) {
      console.error('Error saving contact settings:', error);
      nassaqError(getApiErrorMessage(error) || (t('saveFailed2')));
    } finally {
      setLoading(false);
    }
  };
  
  // Save security settings using new API
  const handleSaveSecuritySettings = async () => {
    setLoading(true);
    try {
      await api.put('/settings/security', {
        session_duration_minutes: securitySettings.sessionTimeout,
        max_concurrent_sessions: securitySettings.maxSessions,
        min_password_length: securitySettings.passwordMinLength,
        require_uppercase: securitySettings.passwordRequireUppercase ? 1 : 0,
        require_lowercase: 1,
        require_numbers: securitySettings.passwordRequireNumbers ? 1 : 0,
        require_special_chars: securitySettings.passwordRequireSpecial ? 1 : 0,
      });
      toast.success(t('savedSuccessfully'));
      await fetchSettings();
    } catch (error) {
      console.error('Error saving security settings:', error);
      nassaqError(getApiErrorMessage(error) || (t('saveFailed2')));
    } finally {
      setLoading(false);
    }
  };
  
  // Task #173: handleSaveAccountSettings and handleUploadProfilePicture
  // were removed. Personal profile/photo writes are now done exclusively
  // from AccountSettingsPage via /users/me/profile and /users/me/avatar
  // (self-scoped). This page no longer mutates any user-owned data.

  // handleSaveTermsVersion removed — public /terms page owns the canonical content.

  // Save privacy version
  const handleSavePrivacyVersion = async () => {
    setLoading(true);
    try {
      const response = await api.post('/settings/privacy', null, {
        params: { content_ar: privacyData.content, content_en: '' }
      });
      if (response.data?.version_number) {
        setPrivacyData(prev => ({ ...prev, version: `${response.data.version_number}.0` }));
        toast.success(t('newPrivacyVersionSaved'));
      }
    } catch (error) {
      console.error('Error saving privacy:', error);
      nassaqError(t('failedToSavePrivacy'));
    } finally {
      setLoading(false);
    }
  };
  
  // Save handler - based on active tab
  const handleSave = async () => {
    switch(activeTab) {
      case 'general':
        await handleSaveGeneralSettings();
        break;
      case 'brand':
        await handleSaveBrandSettings();
        break;
      case 'contact':
        await handleSaveContactSettings();
        break;
      case 'security':
        await handleSaveSecuritySettings();
        break;
      case 'privacy':
        await handleSavePrivacyVersion();
        break;
      default:
        toast.success(t('savedSuccessfully'));
    }
  };
  
  // Task #173: handleChangePassword removed — password changes now happen
  // exclusively from AccountSettingsPage → Security.

  // Task #173: personal "Active Sessions" listing/end/end-all flows
  // moved to AccountSettingsPage. Platform Settings no longer reads or
  // mutates the caller's own sessions; the Security tab here is
  // strictly platform-wide session/password policy.

  const loadSystemInfo = async () => {
    setSystemInfoLoading(true);
    setSystemInfoError(false);
    try {
      const res = await api.get('/system/status');
      setSystemInfo(res?.data || null);
    } catch (error) {
      console.error('Error loading system info:', error);
      setSystemInfo(null);
      setSystemInfoError(true);
    } finally {
      setSystemInfoLoading(false);
    }
  };

  useEffect(() => {
    if (token && activeTab === 'general' && !systemInfo && !systemInfoLoading) {
      loadSystemInfo();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, activeTab]);

  // Task #173: handleEndSession / handleEndAllSessions removed —
  // personal session revocation lives in AccountSettingsPage.

  // Logout
  const handleLogout = (type) => {
    toast.success(t('loggedOut'));
    setShowLogoutDialog(false);
    if (logout) logout();
    navigate('/login');
  };
  
  // Publish new privacy version. (Terms publishing was removed — /terms is
  // centrally maintained.)
  const handlePublishVersion = async (docType = null) => {
    const type = docType || 'privacy';
    const data = privacyData;
    const setData = setPrivacyData;
    
    setLoading(true);
    try {
      // Increment version
      const currentVersion = parseFloat(data.version) || 1.0;
      const newVersion = (currentVersion + 0.1).toFixed(1);
      
      await api.put(`/settings/platform/${type}`, {
        content: data.content,
        version: newVersion,
        effective_date: new Date().toISOString(),
      });
      
      setData(prev => ({
        ...prev,
        version: newVersion,
        lastUpdated: new Date().toISOString(),
      }));
      
      toast.success(t('newVersionPublished'));
      setShowPublishDialog(false);
    } catch (error) {
      console.error('Error publishing version:', error);
      nassaqError(t('failedToPublishVersion'));
    } finally {
      setLoading(false);
    }
  };
  
  // Load version history
  const loadVersionHistory = async (docType) => {
    try {
      const response = await api.get(`/settings/legal-versions/${docType}`);
      setVersionHistory(response.data.versions || []);
      setShowVersionHistoryDialog(true);
    } catch (error) {
      console.error('Error loading version history:', error);
      nassaqError(t('failedToLoadVersionHistory'));
    }
  };
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'} data-testid="platform-settings-page">
        {/* Header */}
        <header className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b">
          <div className="container mx-auto px-4 lg:px-6 py-4">
            <div className="flex items-center justify-between">
              <PageHeader 
                title={t('settingsPageTitle')} 
                subtitle={t('settingsPageSubtitle')}
                icon={Settings}
                className="mb-0"
              />
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                  <Globe className="h-5 w-5" />
                </Button>
                <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                  {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                </Button>
                {/* Task #172 P1: hard-disable the global Save action while
                    on the Visual Identity tab — that section is preview-only
                    and has no backend endpoint to write to. */}
                <Button
                  className={`rounded-xl ${activeTab === 'brand' ? 'bg-muted text-muted-foreground' : hasUnsavedChanges ? 'bg-brand-turquoise hover:bg-brand-turquoise/90 animate-pulse' : 'bg-brand-navy hover:bg-brand-navy/90'}`}
                  onClick={handleSave}
                  disabled={loading || activeTab === 'brand'}
                  aria-disabled={loading || activeTab === 'brand'}
                  title={activeTab === 'brand' ? (isRTL ? 'الهوية البصرية: معاينة فقط' : 'Visual Identity: preview only') : undefined}
                  data-testid="platform-settings-save-button"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin me-2" />
                  ) : (
                    <Save className="h-4 w-4 me-2" />
                  )}
                  {activeTab === 'brand'
                    ? (isRTL ? 'معاينة فقط' : 'Preview only')
                    : (loading ? t('saving') : hasUnsavedChanges ? (t('saveChanges3')) : t('saveChanges'))}
                </Button>
              </div>
            </div>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="container mx-auto px-4 lg:px-6 py-6">
          <div className="flex gap-6">
            {/* Sidebar Navigation */}
            <aside className="w-64 shrink-0 hidden lg:block">
              <Card className="sticky top-24">
                <CardContent className="p-2">
                  <nav className="space-y-1">
                    {SETTINGS_TABS.map(tab => {
                      const TabIcon = tab.icon;
                      const isActive = activeTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => {
                            if (hasUnsavedChanges) {
                              nassaqWarning(t('youHaveUnsavedChangesContinue'), {
                                onConfirm: () => setActiveTab(tab.id),
                              });
                            } else {
                              setActiveTab(tab.id);
                            }
                          }}
                          className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                            isActive 
                              ? 'bg-brand-navy text-white' 
                              : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                          }`}
                          data-testid={`settings-tab-${tab.id}`}
                        >
                          <TabIcon className="h-5 w-5" />
                          {isRTL ? tab.label_ar : tab.label_en}
                        </button>
                      );
                    })}
                    
                    <Separator className="my-2" />
                    
                    {/* Switch User */}
                    <button
                      onClick={() => setShowSwitchUserDialog(true)}
                      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-all"
                    >
                      <Users className="h-5 w-5" />
                      {t('switchUser')}
                    </button>
                    
                    {/* Logout */}
                    <button
                      onClick={() => setShowLogoutDialog(true)}
                      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-all"
                    >
                      <LogOut className="h-5 w-5" />
                      {t('logout')}
                    </button>
                  </nav>
                </CardContent>
              </Card>
            </aside>
            
            {/* Content Area */}
            <div className="flex-1 min-w-0">
              {/* Mobile Tabs */}
              <div className="lg:hidden mb-6 overflow-x-auto">
                <div className="flex gap-2 pb-2">
                  {SETTINGS_TABS.map(tab => {
                    const TabIcon = tab.icon;
                    return (
                      <Button
                        key={tab.id}
                        variant={activeTab === tab.id ? 'default' : 'outline'}
                        size="sm"
                        className={`rounded-xl whitespace-nowrap ${activeTab === tab.id ? 'bg-brand-navy' : ''}`}
                        onClick={() => {
                          if (hasUnsavedChanges) {
                            nassaqWarning(t('youHaveUnsavedChangesContinue'), {
                              onConfirm: () => setActiveTab(tab.id),
                            });
                          } else {
                            setActiveTab(tab.id);
                          }
                        }}
                      >
                        <TabIcon className="h-4 w-4 me-2" />
                        {isRTL ? tab.label_ar : tab.label_en}
                      </Button>
                    );
                  })}
                </div>
              </div>
              
              {/* Task #173: personal "Account Settings" tab removed —
                  see AccountSettingsPage (`/account/settings`). */}

              {/* General Settings */}
              {activeTab === 'general' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5 text-brand-navy" />
                        {t('generalSettings')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Platform Name */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t('platformNameAr')}</Label>
                          <Input
                            value={generalSettings.platformNameAr}
                            onChange={(e) => setGeneralSettings({ ...generalSettings, platformNameAr: e.target.value })}
                            className="rounded-xl"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('platformNameEn')}</Label>
                          <Input
                            value={generalSettings.platformNameEn}
                            onChange={(e) => setGeneralSettings({ ...generalSettings, platformNameEn: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>{t('browserTitle')}</Label>
                        <Input
                          value={generalSettings.browserTitle}
                          onChange={(e) => setGeneralSettings({ ...generalSettings, browserTitle: e.target.value })}
                          className="rounded-xl"
                        />
                      </div>
                      
                      <Separator />
                      
                      {/* Language & Date */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="space-y-2">
                          <Label>{t('defaultLanguage')}</Label>
                          <Select 
                            value={generalSettings.defaultLanguage} 
                            onValueChange={(v) => setGeneralSettings({ ...generalSettings, defaultLanguage: v })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ar">{t('arabic')}</SelectItem>
                              <SelectItem value="en">{t('english')}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t('dateFormat')}</Label>
                          <Select 
                            value={generalSettings.dateFormat} 
                            onValueChange={(v) => setGeneralSettings({ ...generalSettings, dateFormat: v })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="hijri">{t('hijri')}</SelectItem>
                              <SelectItem value="gregorian">{t('gregorian')}</SelectItem>
                              <SelectItem value="both">{t('both')}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t('timezone')}</Label>
                          <Select 
                            value={generalSettings.timezone} 
                            onValueChange={(v) => setGeneralSettings({ ...generalSettings, timezone: v })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="Asia/Riyadh">{t('riyadh')} (GMT+3)</SelectItem>
                              <SelectItem value="Asia/Dubai">{t('dubai')} (GMT+4)</SelectItem>
                              <SelectItem value="Africa/Cairo">{t('cairo')} (GMT+2)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      {/* Toggles */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Mail className="h-5 w-5 text-muted-foreground" />
                            <span>{t('emailNotifications')}</span>
                          </div>
                          <Switch
                            checked={generalSettings.emailNotifications}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, emailNotifications: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Smartphone className="h-5 w-5 text-muted-foreground" />
                            <span>{t('smsNotifications')}</span>
                          </div>
                          <Switch
                            checked={generalSettings.smsNotifications}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, smsNotifications: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Bell className="h-5 w-5 text-muted-foreground" />
                            <span>{t('pushNotifications')}</span>
                          </div>
                          <Switch
                            checked={generalSettings.pushNotifications}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, pushNotifications: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Zap className="h-5 w-5 text-muted-foreground" />
                            <span>{t('aiFeatures')}</span>
                          </div>
                          <Switch
                            checked={generalSettings.aiFeatures}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, aiFeatures: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Users className="h-5 w-5 text-muted-foreground" />
                            <span>{t('registrationOpen')}</span>
                          </div>
                          <Switch
                            checked={generalSettings.registrationOpen}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, registrationOpen: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                          <div className="flex items-center gap-3">
                            <AlertTriangle className="h-5 w-5 text-yellow-600" />
                            <span className="text-yellow-800">{t('maintenanceMode')}</span>
                          </div>
                          <Switch
                            checked={generalSettings.maintenanceMode}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, maintenanceMode: v })}
                          />
                        </div>
                      </div>
                      
                      <Separator />
                      
                      {/* System Info */}
                      <div>
                        <h4 className="font-medium mb-4 flex items-center gap-2">
                          <Server className="h-5 w-5" />
                          {t('systemInfo')}
                        </h4>
                        {systemInfoError && (
                          <div className="mb-3 text-sm text-red-600">
                            {t('errorLoadingData') || 'تعذر تحميل معلومات النظام'}
                          </div>
                        )}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t('version')}</p>
                            <p className="font-mono font-bold">
                              {systemInfoLoading ? '…' : (systemInfo?.version || '—')}
                            </p>
                          </div>
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t('environment')}</p>
                            <p className="font-mono font-bold capitalize">
                              {systemInfoLoading ? '…' : (systemInfo?.environment || '—')}
                            </p>
                          </div>
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t('serverStatus')}</p>
                            <div className="flex items-center gap-2">
                              {systemInfoLoading ? (
                                <span className="font-bold text-muted-foreground">…</span>
                              ) : systemInfo?.status === 'operational' ? (
                                <>
                                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                                  <span className="font-bold text-green-600">{t('online')}</span>
                                </>
                              ) : (
                                <>
                                  <AlertTriangle className="h-4 w-4 text-yellow-500" />
                                  <span className="font-bold text-yellow-600">
                                    {systemInfo?.status || (t('offline') || 'غير متصل')}
                                  </span>
                                </>
                              )}
                            </div>
                            {systemInfo?.uptime && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {t('uptime') || 'مدة التشغيل'}: {systemInfo.uptime}
                              </p>
                            )}
                          </div>
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t('databaseStatus')}</p>
                            <div className="flex items-center gap-2">
                              {systemInfoLoading ? (
                                <span className="font-bold text-muted-foreground">…</span>
                              ) : systemInfo?.database?.connected ? (
                                <>
                                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                                  <span className="font-bold text-green-600">
                                    {systemInfo?.database?.engine || 'PostgreSQL'}
                                  </span>
                                </>
                              ) : (
                                <>
                                  <AlertTriangle className="h-4 w-4 text-red-500" />
                                  <span className="font-bold text-red-600">
                                    {t('disconnected') || 'غير متصل'}
                                  </span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              
              {/* Brand & Identity */}
              {activeTab === 'brand' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Palette className="h-5 w-5 text-brand-navy" />
                        {t('brandIdentity')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Logo & Favicon */}
                      {/* Task #172 P1: Visual Identity is preview-only — no
                          backend wiring exists for logo/favicon upload or
                          color persistence. The controls remain visible so
                          the existing layout is preserved, but every
                          mutating affordance is disabled and labelled. */}
                      <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 border border-amber-200/60 text-amber-800" dir={isRTL ? 'rtl' : 'ltr'} data-testid="visual-identity-preview-badge">
                        <Shield className="h-4 w-4 flex-shrink-0 mt-0.5" />
                        <div className="text-xs font-tajawal">
                          <span className="font-semibold">
                            {isRTL ? 'معاينة فقط' : 'Preview only'}
                          </span>
                          {' — '}
                          {isRTL
                            ? 'تخصيص الهوية البصرية (الشعار، الأيقونة، الألوان) قيد التطوير ولا يتم حفظ التغييرات بعد.'
                            : 'Visual identity customisation (logo, favicon, colours) is a work-in-progress and changes are not persisted yet.'}
                        </div>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-3">
                          <Label>{t('logo')}</Label>
                          <div className="border-2 border-dashed rounded-xl p-8 text-center opacity-60 cursor-not-allowed">
                            <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-brand-navy/10 flex items-center justify-center">
                              <Building2 className="h-10 w-10 text-brand-navy" />
                            </div>
                            <p className="text-sm text-muted-foreground">{t('dragDrop')}</p>
                            <Button variant="outline" size="sm" className="mt-3 rounded-xl" disabled aria-disabled="true">
                              <Upload className="h-4 w-4 me-2" />
                              {t('uploadLogo')}
                            </Button>
                          </div>
                        </div>
                        <div className="space-y-3">
                          <Label>{t('favicon')}</Label>
                          <div className="border-2 border-dashed rounded-xl p-8 text-center opacity-60 cursor-not-allowed">
                            <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                              <Hash className="h-8 w-8 text-brand-navy" />
                            </div>
                            <p className="text-sm text-muted-foreground">32x32 px</p>
                            <Button variant="outline" size="sm" className="mt-3 rounded-xl" disabled aria-disabled="true">
                              <Upload className="h-4 w-4 me-2" />
                              {t('uploadFavicon')}
                            </Button>
                          </div>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      {/* Colors */}
                      <div>
                        <h4 className="font-medium mb-4">{t('colors')}</h4>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                          <div className="space-y-2">
                            <Label>{t('primaryColor')}</Label>
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-12 h-12 rounded-xl shadow-inner cursor-pointer"
                                style={{ backgroundColor: brandSettings.primaryColor }}
                              />
                              <Input
                                value={brandSettings.primaryColor}
                                readOnly
                                disabled
                                aria-disabled="true"
                                className="rounded-xl font-mono opacity-70 cursor-not-allowed"
                                dir="ltr"
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <Label>{t('secondaryColor')}</Label>
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-12 h-12 rounded-xl shadow-inner cursor-pointer"
                                style={{ backgroundColor: brandSettings.secondaryColor }}
                              />
                              <Input
                                value={brandSettings.secondaryColor}
                                readOnly
                                disabled
                                aria-disabled="true"
                                className="rounded-xl font-mono opacity-70 cursor-not-allowed"
                                dir="ltr"
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <Label>{t('accentColor')}</Label>
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-12 h-12 rounded-xl shadow-inner cursor-pointer"
                                style={{ backgroundColor: brandSettings.accentColor }}
                              />
                              <Input
                                value={brandSettings.accentColor}
                                readOnly
                                disabled
                                aria-disabled="true"
                                className="rounded-xl font-mono opacity-70 cursor-not-allowed"
                                dir="ltr"
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              
              {/* Terms & Conditions tab removed — see /terms (public) for the unified content. */}

              {/* Privacy Policy */}
              {activeTab === 'privacy' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-brand-navy" />
                        {t('privacyPolicy')}
                      </CardTitle>
                      <CardDescription>
                        {t('managePlatformPrivacyPolicy')}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Version Info */}
                      <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="flex items-center gap-6">
                          <div>
                            <p className="text-sm text-muted-foreground">{t('currentVersion')}</p>
                            <p className="font-bold">{privacyData.version}</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">{t('lastUpdated')}</p>
                            <p className="font-medium">{formatDateTime(privacyData.lastUpdated)}</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" className="rounded-xl" onClick={() => loadVersionHistory('privacy')}>
                            <History className="h-4 w-4 me-2" />
                            {t('versionHistory')}
                          </Button>
                          <Button className="rounded-xl bg-brand-navy" onClick={() => setShowPublishDialog(true)}>
                            {t('publishVersion')}
                          </Button>
                        </div>
                      </div>
                      
                      {/* Content Editor */}
                      <div className="space-y-2">
                        <Label>{t('privacyText')}</Label>
                        <Textarea
                          value={privacyData.content}
                          onChange={(e) => setPrivacyData({ ...privacyData, content: e.target.value })}
                          rows={20}
                          className="rounded-xl font-tajawal"
                        />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              
              {/* Contact Information */}
              {activeTab === 'contact' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Mail className="h-5 w-5 text-brand-navy" />
                        {t('contactInfo')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Contact Details */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t('primaryEmail')}</Label>
                          <div className="flex gap-2">
                            <Input
                              type="email"
                              value={contactInfo.primaryEmail}
                              onChange={(e) => setContactInfo({ ...contactInfo, primaryEmail: e.target.value })}
                              className="rounded-xl"
                              dir="ltr"
                            />
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => copyToClipboard(contactInfo.primaryEmail, 'email')}
                            >
                              {copiedField === 'email' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                            </Button>
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label>{t('supportEmail')}</Label>
                          <Input
                            type="email"
                            value={contactInfo.supportEmail}
                            onChange={(e) => setContactInfo({ ...contactInfo, supportEmail: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('primaryPhone')}</Label>
                          <Input
                            type="tel"
                            value={contactInfo.primaryPhone}
                            onChange={(e) => setContactInfo({ ...contactInfo, primaryPhone: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('alternatePhone')}</Label>
                          <Input
                            type="tel"
                            value={contactInfo.alternatePhone}
                            onChange={(e) => setContactInfo({ ...contactInfo, alternatePhone: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>{t('address')}</Label>
                        <Textarea
                          value={contactInfo.address}
                          onChange={(e) => setContactInfo({ ...contactInfo, address: e.target.value })}
                          rows={2}
                          className="rounded-xl"
                        />
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t('workingHours')}</Label>
                          <Input
                            value={contactInfo.workingHours}
                            onChange={(e) => setContactInfo({ ...contactInfo, workingHours: e.target.value })}
                            className="rounded-xl"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t('website')}</Label>
                          <Input
                            value={contactInfo.website}
                            onChange={(e) => setContactInfo({ ...contactInfo, website: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>{t('ownerName')}</Label>
                        <Input
                          value={contactInfo.ownerName}
                          onChange={(e) => setContactInfo({ ...contactInfo, ownerName: e.target.value })}
                          className="rounded-xl"
                        />
                      </div>
                      
                      <Separator />
                      
                      {/* Social Media */}
                      <div>
                        <h4 className="font-medium mb-4 flex items-center gap-2">
                          <Link2 className="h-5 w-5" />
                          {t('socialMedia')}
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                            <Twitter className="h-5 w-5 text-blue-400" />
                            <Input
                              placeholder="Twitter URL"
                              value={contactInfo.socialMedia.twitter}
                              onChange={(e) => setContactInfo({ 
                                ...contactInfo, 
                                socialMedia: { ...contactInfo.socialMedia, twitter: e.target.value }
                              })}
                              className="rounded-lg border-0 bg-transparent"
                              dir="ltr"
                            />
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                            <Facebook className="h-5 w-5 text-blue-600" />
                            <Input
                              placeholder="Facebook URL"
                              value={contactInfo.socialMedia.facebook}
                              onChange={(e) => setContactInfo({ 
                                ...contactInfo, 
                                socialMedia: { ...contactInfo.socialMedia, facebook: e.target.value }
                              })}
                              className="rounded-lg border-0 bg-transparent"
                              dir="ltr"
                            />
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                            <Instagram className="h-5 w-5 text-pink-500" />
                            <Input
                              placeholder="Instagram URL"
                              value={contactInfo.socialMedia.instagram}
                              onChange={(e) => setContactInfo({ 
                                ...contactInfo, 
                                socialMedia: { ...contactInfo.socialMedia, instagram: e.target.value }
                              })}
                              className="rounded-lg border-0 bg-transparent"
                              dir="ltr"
                            />
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                            <Linkedin className="h-5 w-5 text-blue-700" />
                            <Input
                              placeholder="LinkedIn URL"
                              value={contactInfo.socialMedia.linkedin}
                              onChange={(e) => setContactInfo({ 
                                ...contactInfo, 
                                socialMedia: { ...contactInfo.socialMedia, linkedin: e.target.value }
                              })}
                              className="rounded-lg border-0 bg-transparent"
                              dir="ltr"
                            />
                          </div>
                          <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                            <Youtube className="h-5 w-5 text-red-600" />
                            <Input
                              placeholder="YouTube URL"
                              value={contactInfo.socialMedia.youtube}
                              onChange={(e) => setContactInfo({ 
                                ...contactInfo, 
                                socialMedia: { ...contactInfo.socialMedia, youtube: e.target.value }
                              })}
                              className="rounded-lg border-0 bg-transparent"
                              dir="ltr"
                            />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              
              {/* Security & Sessions */}
              {activeTab === 'security' && (
                <div className="space-y-6">
                  {/* Task #173: personal "Active Sessions" card removed.
                      Personal session listing/revocation lives in
                      AccountSettingsPage → Security. This tab now
                      contains only platform-wide session/password
                      policy. */}

                  {/* Security Settings */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-brand-navy" />
                        {t('securitySessions')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Task #173: the per-account MFA CTA was removed
                          from Platform Settings. Personal MFA is reached
                          directly from the sidebar entry → Account
                          Settings (`/account/settings`) → Security. This
                          tab is now strictly platform-wide policy
                          (session/password rules). */}

                      {/* Session Settings */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t('sessionExpiry')}</Label>
                          <Select 
                            value={String(securitySettings.sessionTimeout)} 
                            onValueChange={(v) => setSecuritySettings({ ...securitySettings, sessionTimeout: parseInt(v) })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="15">15 {t('minutes')}</SelectItem>
                              <SelectItem value="30">30 {t('minutes')}</SelectItem>
                              <SelectItem value="60">60 {t('minutes')}</SelectItem>
                              <SelectItem value="120">2 {t('hours')}</SelectItem>
                              <SelectItem value="1440">24 {t('hours')}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t('maxSessions')}</Label>
                          <Select 
                            value={String(securitySettings.maxSessions)} 
                            onValueChange={(v) => setSecuritySettings({ ...securitySettings, maxSessions: parseInt(v) })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="1">1</SelectItem>
                              <SelectItem value="3">3</SelectItem>
                              <SelectItem value="5">5</SelectItem>
                              <SelectItem value="10">10</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      {/* Password Policy */}
                      <div>
                        <h4 className="font-medium mb-4">{t('passwordPolicy')}</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                            <span>{t('minimumLength')}</span>
                            <Badge variant="outline">{securitySettings.passwordMinLength} {t('chars')}</Badge>
                          </div>
                          <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                            <span>{t('uppercase')}</span>
                            <Switch
                              checked={securitySettings.passwordRequireUppercase}
                              onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, passwordRequireUppercase: v })}
                            />
                          </div>
                          <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                            <span>{t('numbers')}</span>
                            <Switch
                              checked={securitySettings.passwordRequireNumbers}
                              onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, passwordRequireNumbers: v })}
                            />
                          </div>
                          <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                            <span>{t('specialChars')}</span>
                            <Switch
                              checked={securitySettings.passwordRequireSpecial}
                              onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, passwordRequireSpecial: v })}
                            />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          </div>
        </main>
        
        {/* Task #173: change-password dialog moved to AccountSettingsPage. */}

        {/* Logout Dialog */}
        <AlertDialog open={showLogoutDialog} onOpenChange={setShowLogoutDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <LogOut className="h-5 w-5 text-red-600" />
                {t('confirmLogout')}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {t('chooseLogoutMethod')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="py-4 space-y-3">
              <Button 
                variant="outline" 
                className="w-full justify-start rounded-xl"
                onClick={() => handleLogout('normal')}
              >
                <LogOut className="h-4 w-4 me-3" />
                {t('logoutNormal')}
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start rounded-xl"
                onClick={() => handleLogout('all')}
              >
                <Monitor className="h-4 w-4 me-3" />
                {t('logoutAllDevices')}
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start rounded-xl"
                onClick={() => handleLogout('others')}
              >
                <Users className="h-4 w-4 me-3" />
                {t('logoutOtherDevices')}
              </Button>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        
        {/* Switch User Dialog */}
        <Dialog open={showSwitchUserDialog} onOpenChange={setShowSwitchUserDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-brand-navy" />
                {t('switchUser')}
              </DialogTitle>
              <DialogDescription>
                {t('temporarilyAccessAnotherUserAccount')}
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <div className="space-y-2">
                <Label>{t('selectUser')}</Label>
                <Select>
                  <SelectTrigger className="rounded-xl">
                    <SelectValue placeholder={t('selectUser')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user1">{t('ahmedMohammedSchoolAdmin')}</SelectItem>
                    <SelectItem value="user2">{t('saraAhmedTeacher')}</SelectItem>
                    <SelectItem value="user3">{t('mohammedAliParent')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div>
                    <p className="text-sm text-yellow-800 font-medium">
                      {t('importantNotice')}
                    </p>
                    <p className="text-sm text-yellow-700 mt-1">
                      {t('thisActionWillBeLoggedUseThisFeatureCarefully')}
                    </p>
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowSwitchUserDialog(false)}>{t('cancel')}</Button>
              <Button className="bg-brand-navy">
                <Users className="h-4 w-4 me-2" />
                {t('switchUser')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Publish Version Dialog */}
        <Dialog open={showPublishDialog} onOpenChange={setShowPublishDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('publishVersion')}</DialogTitle>
              <DialogDescription>
                {t('publishANewVersionOfTermsOrPolicy')}
              </DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div className="flex items-center gap-4 p-4 bg-muted/30 rounded-xl">
                <Info className="h-5 w-5 text-blue-600" />
                <p className="text-sm">
                  {t('currentVersionWillBeArchivedAndNewVersionWillBeAct')}
                </p>
              </div>
              <div className="space-y-2">
                <Label>{t('changeNotes')}</Label>
                <Textarea 
                  placeholder={t('describeChangesInThisVersion')}
                  rows={3}
                  className="rounded-xl"
                />
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowPublishDialog(false)}>{t('cancel')}</Button>
              <Button onClick={handlePublishVersion} className="bg-brand-navy">
                <CheckCircle2 className="h-4 w-4 me-2" />
                {t('publishVersion')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Version History Dialog */}
        <Dialog open={showVersionHistoryDialog} onOpenChange={setShowVersionHistoryDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <History className="h-5 w-5 text-brand-navy" />
                {t('versionHistory')}
              </DialogTitle>
            </DialogHeader>
            <ScrollArea className="h-[300px] py-4">
              <div className="space-y-3">
                {versionHistory.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <History className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p>{t('noVersionHistory')}</p>
                  </div>
                ) : (
                  versionHistory.map((version, idx) => (
                    <div key={idx} className="p-4 bg-muted/30 rounded-xl">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant={idx === 0 ? 'default' : 'secondary'}>
                          v{version.version}
                        </Badge>
                        <span className="text-sm text-muted-foreground">{version.date}</span>
                      </div>
                      <p className="text-sm">{version.changes}</p>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowVersionHistoryDialog(false)}>{t('cancel')}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      {/* Task #173: ImageCropModal usage removed — profile photo upload
          lives in AccountSettingsPage. */}
    </Sidebar>
  );
};

export default PlatformSettingsPage;
