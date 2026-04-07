import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { PageHeader } from '../components/layout/PageHeader';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
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
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
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
const translations = {
  ar: {
    pageTitle: 'إعدادات النظام',
    pageSubtitle: 'إدارة وتكوين إعدادات المنصة الشاملة',
    accountSettings: 'إعدادات الحساب',
    generalSettings: 'الإعدادات العامة',
    brandIdentity: 'الهوية والعلامة التجارية',
    termsConditions: 'الشروط والأحكام',
    privacyPolicy: 'سياسة الخصوصية',
    contactInfo: 'بيانات التواصل',
    securitySessions: 'الأمان والجلسات',
    switchUser: 'تبديل المستخدم',
    logout: 'تسجيل الخروج',
    name: 'الاسم',
    email: 'البريد الإلكتروني',
    phone: 'رقم الهاتف',
    language: 'اللغة',
    profilePicture: 'الصورة الشخصية',
    changePassword: 'تغيير كلمة المرور',
    currentPassword: 'كلمة المرور الحالية',
    newPassword: 'كلمة المرور الجديدة',
    confirmPassword: 'تأكيد كلمة المرور',
    save: 'حفظ',
    cancel: 'إلغاء',
    saveChanges: 'حفظ التغييرات',
    saving: 'جاري الحفظ...',
    savedSuccessfully: 'تم الحفظ بنجاح',
    platformName: 'اسم المنصة',
    platformNameAr: 'اسم المنصة (عربي)',
    platformNameEn: 'اسم المنصة (إنجليزي)',
    browserTitle: 'عنوان المتصفح',
    logo: 'الشعار',
    favicon: 'أيقونة الموقع',
    primaryColor: 'اللون الأساسي',
    secondaryColor: 'اللون الثانوي',
    defaultLanguage: 'اللغة الافتراضية',
    dateFormat: 'نظام التاريخ',
    timezone: 'المنطقة الزمنية',
    arabic: 'العربية',
    english: 'الإنجليزية',
    hijri: 'هجري',
    gregorian: 'ميلادي',
    emailNotifications: 'إشعارات البريد',
    smsNotifications: 'إشعارات SMS',
    pushNotifications: 'إشعارات النظام',
    aiFeatures: 'ميزات الذكاء الاصطناعي',
    registrationOpen: 'التسجيل مفتوح',
    termsText: 'نص الشروط والأحكام',
    privacyText: 'نص سياسة الخصوصية',
    publishVersion: 'نشر نسخة جديدة',
    currentVersion: 'النسخة الحالية',
    lastUpdated: 'آخر تحديث',
    versionHistory: 'سجل الإصدارات',
    compareVersions: 'مقارنة الإصدارات',
    primaryEmail: 'البريد الإلكتروني الرئيسي',
    primaryPhone: 'رقم الهاتف الرئيسي',
    alternatePhone: 'رقم هاتف بديل',
    address: 'العنوان',
    workingHours: 'ساعات العمل',
    website: 'الموقع الإلكتروني',
    supportEmail: 'بريد الدعم الفني',
    socialMedia: 'وسائل التواصل الاجتماعي',
    ownerName: 'اسم الجهة المالكة',
    billingInfo: 'بيانات الفواتير',
    activeSessions: 'الجلسات النشطة',
    linkedDevices: 'الأجهزة المرتبطة',
    loginHistory: 'سجل تسجيل الدخول',
    switchHistory: 'سجل تبديل المستخدم',
    twoFactorAuth: 'المصادقة الثنائية',
    passwordPolicy: 'سياسة كلمات المرور',
    sessionTimeout: 'مهلة الجلسة',
    deviceRestrictions: 'قيود الأجهزة',
    endAllSessions: 'إنهاء جميع الجلسات',
    endOtherSessions: 'إنهاء الجلسات الأخرى',
    selectUser: 'اختر المستخدم',
    switchUserMode: 'أنت الآن في وضع تبديل المستخدم',
    returnToAdmin: 'العودة لحسابك',
    logoutNormal: 'تسجيل خروج عادي',
    logoutAllDevices: 'الخروج من جميع الأجهزة',
    logoutOtherDevices: 'إنهاء الجلسات الأخرى فقط',
    confirmLogout: 'تأكيد تسجيل الخروج',
    sessionExpiry: 'مدة صلاحية الجلسة (بالدقائق)',
    maxSessions: 'الحد الأقصى للجلسات المتزامنة',
    minutes: 'دقيقة',
    hours: 'ساعة',
    days: 'يوم',
    uploadLogo: 'رفع الشعار',
    uploadFavicon: 'رفع الأيقونة',
    uploadImage: 'رفع صورة',
    dragDrop: 'اسحب وأفلت أو انقر للرفع',
    systemInfo: 'معلومات النظام',
    version: 'الإصدار',
    environment: 'البيئة',
    serverStatus: 'حالة الخادم',
    databaseStatus: 'حالة قاعدة البيانات',
    online: 'متصل',
    offline: 'غير متصل',
    maintenanceMode: 'وضع الصيانة',
  },
  en: {
    pageTitle: 'System Settings',
    pageSubtitle: 'Manage and configure platform settings',
    accountSettings: 'Account Settings',
    generalSettings: 'General Settings',
    brandIdentity: 'Brand & Identity',
    termsConditions: 'Terms & Conditions',
    privacyPolicy: 'Privacy Policy',
    contactInfo: 'Contact Information',
    securitySessions: 'Security & Sessions',
    switchUser: 'Switch User',
    logout: 'Logout',
    name: 'Name',
    email: 'Email',
    phone: 'Phone Number',
    language: 'Language',
    profilePicture: 'Profile Picture',
    changePassword: 'Change Password',
    currentPassword: 'Current Password',
    newPassword: 'New Password',
    confirmPassword: 'Confirm Password',
    save: 'Save',
    cancel: 'Cancel',
    saveChanges: 'Save Changes',
    saving: 'Saving...',
    savedSuccessfully: 'Saved successfully',
    platformName: 'Platform Name',
    platformNameAr: 'Platform Name (Arabic)',
    platformNameEn: 'Platform Name (English)',
    browserTitle: 'Browser Title',
    logo: 'Logo',
    favicon: 'Favicon',
    primaryColor: 'Primary Color',
    secondaryColor: 'Secondary Color',
    defaultLanguage: 'Default Language',
    dateFormat: 'Date Format',
    timezone: 'Timezone',
    arabic: 'Arabic',
    english: 'English',
    hijri: 'Hijri',
    gregorian: 'Gregorian',
    emailNotifications: 'Email Notifications',
    smsNotifications: 'SMS Notifications',
    pushNotifications: 'Push Notifications',
    aiFeatures: 'AI Features',
    registrationOpen: 'Registration Open',
    termsText: 'Terms & Conditions Text',
    privacyText: 'Privacy Policy Text',
    publishVersion: 'Publish New Version',
    currentVersion: 'Current Version',
    lastUpdated: 'Last Updated',
    versionHistory: 'Version History',
    compareVersions: 'Compare Versions',
    primaryEmail: 'Primary Email',
    primaryPhone: 'Primary Phone',
    alternatePhone: 'Alternate Phone',
    address: 'Address',
    workingHours: 'Working Hours',
    website: 'Website',
    supportEmail: 'Support Email',
    socialMedia: 'Social Media',
    ownerName: 'Owner Name',
    billingInfo: 'Billing Information',
    activeSessions: 'Active Sessions',
    linkedDevices: 'Linked Devices',
    loginHistory: 'Login History',
    switchHistory: 'Switch User History',
    twoFactorAuth: 'Two-Factor Authentication',
    passwordPolicy: 'Password Policy',
    sessionTimeout: 'Session Timeout',
    deviceRestrictions: 'Device Restrictions',
    endAllSessions: 'End All Sessions',
    endOtherSessions: 'End Other Sessions',
    selectUser: 'Select User',
    switchUserMode: 'You are in Switch User mode',
    returnToAdmin: 'Return to your account',
    logoutNormal: 'Normal Logout',
    logoutAllDevices: 'Logout from All Devices',
    logoutOtherDevices: 'End Other Sessions Only',
    confirmLogout: 'Confirm Logout',
    sessionExpiry: 'Session Expiry (minutes)',
    maxSessions: 'Max Concurrent Sessions',
    minutes: 'minutes',
    hours: 'hours',
    days: 'days',
    uploadLogo: 'Upload Logo',
    uploadFavicon: 'Upload Favicon',
    uploadImage: 'Upload Image',
    dragDrop: 'Drag & drop or click to upload',
    systemInfo: 'System Information',
    version: 'Version',
    environment: 'Environment',
    serverStatus: 'Server Status',
    databaseStatus: 'Database Status',
    online: 'Online',
    offline: 'Offline',
    maintenanceMode: 'Maintenance Mode',
  }
};

// Navigation tabs
const SETTINGS_TABS = [
  { id: 'account', icon: User, label_ar: 'إعدادات الحساب', label_en: 'Account' },
  { id: 'general', icon: Settings, label_ar: 'الإعدادات العامة', label_en: 'General' },
  { id: 'brand', icon: Palette, label_ar: 'الهوية البصرية', label_en: 'Branding' },
  { id: 'terms', icon: FileText, label_ar: 'الشروط والأحكام', label_en: 'Terms' },
  { id: 'privacy', icon: Shield, label_ar: 'سياسة الخصوصية', label_en: 'Privacy' },
  { id: 'contact', icon: Mail, label_ar: 'بيانات التواصل', label_en: 'Contact' },
  { id: 'security', icon: Lock, label_ar: 'الأمان والجلسات', label_en: 'Security' },
];

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
  const [activeTab, setActiveTab] = useState('account');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [showLogoutDialog, setShowLogoutDialog] = useState(false);
  const [showSwitchUserDialog, setShowSwitchUserDialog] = useState(false);
  const [showPublishDialog, setShowPublishDialog] = useState(false);
  const [showVersionHistoryDialog, setShowVersionHistoryDialog] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [copiedField, setCopiedField] = useState(null);
  const [versionHistory, setVersionHistory] = useState([]);
  const [activeSessions, setActiveSessions] = useState([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [initialSnapshots, setInitialSnapshots] = useState({});
  
  // Account settings - using user data only
  const [accountData, setAccountData] = useState({
    name: user?.full_name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    language: user?.preferred_language || 'ar',
    profilePicture: user?.avatar_url || null,
    title: user?.title || '',
  });
  
  // Password form
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  
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
  
  const [availableTitles, setAvailableTitles] = useState({ ar: [], en: [] });

  const [contactInfo, setContactInfo] = useState({
    primaryEmail: 'info@nassaqapp.com',
    supportEmail: 'support@nassaqapp.com',
    primaryPhone: '+966 11 234 5678',
    alternatePhone: '+966 11 234 5679',
    address: 'الرياض، المملكة العربية السعودية، حي العليا، شارع العروبة',
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

  const [securitySettings, setSecuritySettings] = useState({
    twoFactorEnabled: false,
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
            address: data.address_ar || 'الرياض، المملكة العربية السعودية',
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
            twoFactorEnabled: false,
            sessionTimeout: data.session_duration_minutes || 60,
            maxSessions: data.max_concurrent_sessions || 3,
            passwordMinLength: data.min_password_length || 8,
            passwordRequireUppercase: (data.require_uppercase || 1) > 0,
            passwordRequireNumbers: (data.require_numbers || 1) > 0,
            passwordRequireSpecial: (data.require_special_chars || 1) > 0,
          });
        }
        
        // Fetch account settings
        const accountResponse = await api.get('/settings/account');
        if (accountResponse.data) {
          const data = accountResponse.data;
          setAccountData(prev => ({
            ...prev,
            name: data.name || prev.name,
            phone: data.phone || prev.phone,
            language: data.language || prev.language,
            profilePicture: data.profile_picture || prev.profilePicture,
            title: data.title || '',
          }));
        }
        
        // Fetch titles
        const titlesResponse = await api.get('/settings/titles');
        if (titlesResponse.data) {
          setAvailableTitles(titlesResponse.data);
        }
        
        // Fetch terms versions
        const termsResponse = await api.get('/settings/terms/versions');
        if (termsResponse.data?.length > 0) {
          const publishedVersion = termsResponse.data.find(v => v.is_published);
          if (publishedVersion) {
            setTermsData({
              content: publishedVersion.content_ar || '',
              version: `${publishedVersion.version_number}.0`,
              lastUpdated: publishedVersion.created_at,
              effectiveDate: publishedVersion.published_at,
            });
          }
          setVersionHistory(termsResponse.data);
        }
        
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
    if (!initialSnapshots.account) {
      setInitialSnapshots(prev => ({
        ...prev,
        account: JSON.stringify(accountData),
        general: JSON.stringify(generalSettings),
        contact: JSON.stringify(contactInfo),
        security: JSON.stringify(securitySettings),
      }));
      return;
    }
    const currentMap = {
      account: JSON.stringify(accountData),
      general: JSON.stringify(generalSettings),
      contact: JSON.stringify(contactInfo),
      security: JSON.stringify(securitySettings),
    };
    const changed = Object.keys(currentMap).some(k => initialSnapshots[k] && currentMap[k] !== initialSnapshots[k]);
    setHasUnsavedChanges(changed);
  }, [accountData, generalSettings, contactInfo, securitySettings, initialSnapshots]);

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
  
  // Terms and Privacy
  const [termsData, setTermsData] = useState({
    content: `الشروط والأحكام الخاصة باستخدام منصة نَسَّق التعليمية

1. مقدمة
مرحباً بكم في منصة نَسَّق التعليمية. باستخدامكم لهذه المنصة، فإنكم توافقون على الالتزام بهذه الشروط والأحكام.

2. التعريفات
- "المنصة": تشير إلى منصة نَسَّق الإلكترونية وجميع خدماتها.
- "المستخدم": أي شخص يستخدم المنصة بأي صفة.
- "المدرسة": المؤسسة التعليمية المشتركة في المنصة.

3. الاستخدام المقبول
يتعهد المستخدم بعدم استخدام المنصة لأي أغراض غير مشروعة أو محظورة.

4. الخصوصية وحماية البيانات
نلتزم بحماية بيانات المستخدمين وفقاً لسياسة الخصوصية المعمول بها.

5. حقوق الملكية الفكرية
جميع حقوق الملكية الفكرية للمنصة محفوظة لشركة نَسَّق.`,
    version: '2.1',
    lastUpdated: '2026-03-01T00:00:00Z',
    effectiveDate: '2026-03-15T00:00:00Z',
  });
  
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
      
      toast.success(t.savedSuccessfully);
      await fetchSettings();
    } catch (error) {
      console.error('Error saving general settings:', error);
      nassaqError(error.response?.data?.detail || (t('saveFailed2')));
    } finally {
      setLoading(false);
    }
  };
  
  // Save brand settings (disabled as per requirements)
  const handleSaveBrandSettings = async () => {
    toast.info(t('brandIdentitySectionDisabled'));
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
      toast.success(t.savedSuccessfully);
      await fetchSettings();
    } catch (error) {
      console.error('Error saving contact settings:', error);
      nassaqError(error.response?.data?.detail || (t('saveFailed2')));
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
      toast.success(t.savedSuccessfully);
      await fetchSettings();
    } catch (error) {
      console.error('Error saving security settings:', error);
      nassaqError(error.response?.data?.detail || (t('saveFailed2')));
    } finally {
      setLoading(false);
    }
  };
  
  const handleSaveAccountSettings = async () => {
    if (!accountData.name?.trim()) {
      nassaqError(t('nameIsRequired'));
      return;
    }
    setLoading(true);
    try {
      const res = await api.put('/settings/account', {
        name: accountData.name,
        title: accountData.title || '',
        phone: accountData.phone,
        language: accountData.language,
      });
      toast.success(res.data?.message || t.savedSuccessfully);
      if (refreshUser) await refreshUser();
      await fetchSettings();
    } catch (error) {
      console.error('Error saving account settings:', error);
      nassaqError(error.response?.data?.detail || (t('saveFailed2')));
    } finally {
      setLoading(false);
    }
  };
  
  // Upload profile picture
  const fileInputRef = React.useRef(null);
  const handleUploadProfilePicture = async (file) => {
    if (!file) return;
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      nassaqError(t('imageMustBeUnder5mb'));
      return;
    }
    if (!file.type.startsWith('image/')) {
      nassaqError(t('pleaseSelectAnImageFile'));
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post('/settings/account/upload-picture', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (response.data?.profile_picture) {
        setAccountData(prev => ({ ...prev, profilePicture: response.data.profile_picture }));
        toast.success(t('pictureUploadedSuccessfully'));
        if (refreshUser) await refreshUser();
      }
    } catch (error) {
      console.error('Error uploading picture:', error);
      nassaqError(isRTL ? 'فشل رفع الصورة' : 'Failed to upload picture');
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };
  
  // Save terms version
  const handleSaveTermsVersion = async () => {
    setLoading(true);
    try {
      const response = await api.post('/settings/terms', null, {
        params: { content_ar: termsData.content, content_en: '' }
      });
      if (response.data?.version_number) {
        setTermsData(prev => ({ ...prev, version: `${response.data.version_number}.0` }));
        toast.success(t('newTermsVersionSaved'));
      }
    } catch (error) {
      console.error('Error saving terms:', error);
      nassaqError(t('failedToSaveTerms'));
    } finally {
      setLoading(false);
    }
  };
  
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
      case 'account':
        await handleSaveAccountSettings();
        break;
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
      case 'terms':
        await handleSaveTermsVersion();
        break;
      case 'privacy':
        await handleSavePrivacyVersion();
        break;
      default:
        toast.success(t.savedSuccessfully);
    }
  };
  
  // Change password
  const handleChangePassword = async () => {
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      nassaqError(t('passwordsDoNotMatch3'));
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      });
      toast.success(t('passwordChangedSuccessfully'));
      setShowPasswordDialog(false);
      setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (error) {
      console.error('Error changing password:', error);
      nassaqError(t('failedToChangePassword'));
    } finally {
      setLoading(false);
    }
  };
  
  // End session
  const handleEndSession = async (sessionId) => {
    try {
      await api.delete(`/settings/sessions/${sessionId}`);
      toast.success(t('sessionEnded'));
    } catch (error) {
      nassaqError(t('failedToEndSession'));
    }
  };
  
  // End all sessions
  const handleEndAllSessions = async () => {
    try {
      await api.post('/settings/sessions/end-all', {});
      toast.success(t('allOtherSessionsEnded'));
    } catch (error) {
      nassaqError(t('failedToEndSessions'));
    }
  };
  
  // Logout
  const handleLogout = (type) => {
    toast.success(t('loggedOut'));
    setShowLogoutDialog(false);
    if (logout) logout();
    navigate('/login');
  };
  
  // Publish new version (terms or privacy)
  const handlePublishVersion = async (docType = null) => {
    const type = docType || (activeTab === 'terms' ? 'terms' : 'privacy');
    const data = type === 'terms' ? termsData : privacyData;
    const setData = type === 'terms' ? setTermsData : setPrivacyData;
    
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
                title={t.pageTitle} 
                subtitle={t.pageSubtitle}
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
                <Button 
                  className={`rounded-xl ${hasUnsavedChanges ? 'bg-brand-turquoise hover:bg-brand-turquoise/90 animate-pulse' : 'bg-brand-navy hover:bg-brand-navy/90'}`}
                  onClick={handleSave}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin me-2" />
                  ) : (
                    <Save className="h-4 w-4 me-2" />
                  )}
                  {loading ? t.saving : hasUnsavedChanges ? (t('saveChanges3')) : t.saveChanges}
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
                      {t.switchUser}
                    </button>
                    
                    {/* Logout */}
                    <button
                      onClick={() => setShowLogoutDialog(true)}
                      className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-all"
                    >
                      <LogOut className="h-5 w-5" />
                      {t.logout}
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
              
              {/* Account Settings */}
              {activeTab === 'account' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <User className="h-5 w-5 text-brand-navy" />
                        {t.accountSettings}
                      </CardTitle>
                      <CardDescription>
                        {t('manageYourPersonalAccountInformation')}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Profile Picture */}
                      <div className="flex items-center gap-6">
                        <div className="w-24 h-24 rounded-2xl overflow-hidden bg-gradient-to-br from-brand-navy to-brand-navy/70 flex items-center justify-center text-white text-3xl font-bold shadow-lg flex-shrink-0">
                          {accountData.profilePicture ? (
                            <img
                              src={accountData.profilePicture}
                              alt={accountData.name || ''}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            accountData.name?.charAt(0) || 'م'
                          )}
                        </div>
                        <div>
                          <h4 className="font-medium mb-2">{t.profilePicture}</h4>
                          <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/png,image/jpeg,image/webp"
                            className="hidden"
                            onChange={(e) => handleUploadProfilePicture(e.target.files?.[0])}
                          />
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-xl"
                              disabled={loading}
                              onClick={() => fileInputRef.current?.click()}
                            >
                              <Upload className="h-4 w-4 me-2" />
                              {t.uploadImage}
                            </Button>
                            {accountData.profilePicture && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="rounded-xl text-red-500 hover:text-red-600"
                                disabled={loading}
                                onClick={async () => {
                                  setLoading(true);
                                  try {
                                    await api.delete('/settings/account/profile-picture');
                                    setAccountData(prev => ({ ...prev, profilePicture: null }));
                                    toast.success(t('pictureRemoved'));
                                    if (refreshUser) await refreshUser();
                                  } catch (err) {
                                    nassaqError(t('failedToRemovePicture'));
                                  } finally {
                                    setLoading(false);
                                  }
                                }}
                              >
                                <Trash2 className="h-4 w-4 me-2" />
                                {isRTL ? 'حذف' : 'Remove'}
                              </Button>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {t('pngJpgOrWebpMax5mb')}
                          </p>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      {/* Account Info */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t.name}</Label>
                          <Input
                            value={accountData.name}
                            onChange={(e) => setAccountData({ ...accountData, name: e.target.value })}
                            className="rounded-xl"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.email}</Label>
                          <Input
                            type="email"
                            value={accountData.email}
                            onChange={(e) => setAccountData({ ...accountData, email: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.phone}</Label>
                          <Input
                            type="tel"
                            value={accountData.phone}
                            onChange={(e) => setAccountData({ ...accountData, phone: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.language}</Label>
                          <Select 
                            value={accountData.language} 
                            onValueChange={(v) => setAccountData({ ...accountData, language: v })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ar">{t.arabic}</SelectItem>
                              <SelectItem value="en">{t.english}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      
                      <Separator />
                      
                      {/* Change Password */}
                      <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center">
                            <Key className="h-5 w-5 text-orange-600" />
                          </div>
                          <div>
                            <h4 className="font-medium">{t.changePassword}</h4>
                            <p className="text-sm text-muted-foreground">
                              {t('changeYourAccountPassword')}
                            </p>
                          </div>
                        </div>
                        <Button variant="outline" className="rounded-xl" onClick={() => setShowPasswordDialog(true)}>
                          <Edit className="h-4 w-4 me-2" />
                          {t('change')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              
              {/* General Settings */}
              {activeTab === 'general' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5 text-brand-navy" />
                        {t.generalSettings}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Platform Name */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t.platformNameAr}</Label>
                          <Input
                            value={generalSettings.platformNameAr}
                            onChange={(e) => setGeneralSettings({ ...generalSettings, platformNameAr: e.target.value })}
                            className="rounded-xl"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.platformNameEn}</Label>
                          <Input
                            value={generalSettings.platformNameEn}
                            onChange={(e) => setGeneralSettings({ ...generalSettings, platformNameEn: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>{t.browserTitle}</Label>
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
                          <Label>{t.defaultLanguage}</Label>
                          <Select 
                            value={generalSettings.defaultLanguage} 
                            onValueChange={(v) => setGeneralSettings({ ...generalSettings, defaultLanguage: v })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="ar">{t.arabic}</SelectItem>
                              <SelectItem value="en">{t.english}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t.dateFormat}</Label>
                          <Select 
                            value={generalSettings.dateFormat} 
                            onValueChange={(v) => setGeneralSettings({ ...generalSettings, dateFormat: v })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="hijri">{t.hijri}</SelectItem>
                              <SelectItem value="gregorian">{t.gregorian}</SelectItem>
                              <SelectItem value="both">{t('both')}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t.timezone}</Label>
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
                            <span>{t.emailNotifications}</span>
                          </div>
                          <Switch
                            checked={generalSettings.emailNotifications}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, emailNotifications: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Smartphone className="h-5 w-5 text-muted-foreground" />
                            <span>{t.smsNotifications}</span>
                          </div>
                          <Switch
                            checked={generalSettings.smsNotifications}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, smsNotifications: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Bell className="h-5 w-5 text-muted-foreground" />
                            <span>{t.pushNotifications}</span>
                          </div>
                          <Switch
                            checked={generalSettings.pushNotifications}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, pushNotifications: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Zap className="h-5 w-5 text-muted-foreground" />
                            <span>{t.aiFeatures}</span>
                          </div>
                          <Switch
                            checked={generalSettings.aiFeatures}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, aiFeatures: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                          <div className="flex items-center gap-3">
                            <Users className="h-5 w-5 text-muted-foreground" />
                            <span>{t.registrationOpen}</span>
                          </div>
                          <Switch
                            checked={generalSettings.registrationOpen}
                            onCheckedChange={(v) => setGeneralSettings({ ...generalSettings, registrationOpen: v })}
                          />
                        </div>
                        <div className="flex items-center justify-between p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                          <div className="flex items-center gap-3">
                            <AlertTriangle className="h-5 w-5 text-yellow-600" />
                            <span className="text-yellow-800">{t.maintenanceMode}</span>
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
                          {t.systemInfo}
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t.version}</p>
                            <p className="font-mono font-bold">2.1.0</p>
                          </div>
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t.environment}</p>
                            <p className="font-mono font-bold">Production</p>
                          </div>
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t.serverStatus}</p>
                            <div className="flex items-center gap-2">
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                              <span className="font-bold text-green-600">{t.online}</span>
                            </div>
                          </div>
                          <div className="bg-muted/30 rounded-xl p-4">
                            <p className="text-sm text-muted-foreground">{t.databaseStatus}</p>
                            <div className="flex items-center gap-2">
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                              <span className="font-bold text-green-600">MongoDB</span>
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
                        {t.brandIdentity}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Logo & Favicon */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-3">
                          <Label>{t.logo}</Label>
                          <div className="border-2 border-dashed rounded-xl p-8 text-center hover:border-brand-navy/50 transition-colors cursor-pointer">
                            <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-brand-navy/10 flex items-center justify-center">
                              <Building2 className="h-10 w-10 text-brand-navy" />
                            </div>
                            <p className="text-sm text-muted-foreground">{t.dragDrop}</p>
                            <Button variant="outline" size="sm" className="mt-3 rounded-xl">
                              <Upload className="h-4 w-4 me-2" />
                              {t.uploadLogo}
                            </Button>
                          </div>
                        </div>
                        <div className="space-y-3">
                          <Label>{t.favicon}</Label>
                          <div className="border-2 border-dashed rounded-xl p-8 text-center hover:border-brand-navy/50 transition-colors cursor-pointer">
                            <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                              <Hash className="h-8 w-8 text-brand-navy" />
                            </div>
                            <p className="text-sm text-muted-foreground">32x32 px</p>
                            <Button variant="outline" size="sm" className="mt-3 rounded-xl">
                              <Upload className="h-4 w-4 me-2" />
                              {t.uploadFavicon}
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
                            <Label>{t.primaryColor}</Label>
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-12 h-12 rounded-xl shadow-inner cursor-pointer"
                                style={{ backgroundColor: brandSettings.primaryColor }}
                              />
                              <Input
                                value={brandSettings.primaryColor}
                                onChange={(e) => setBrandSettings({ ...brandSettings, primaryColor: e.target.value })}
                                className="rounded-xl font-mono"
                                dir="ltr"
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <Label>{t.secondaryColor}</Label>
                            <div className="flex items-center gap-3">
                              <div 
                                className="w-12 h-12 rounded-xl shadow-inner cursor-pointer"
                                style={{ backgroundColor: brandSettings.secondaryColor }}
                              />
                              <Input
                                value={brandSettings.secondaryColor}
                                onChange={(e) => setBrandSettings({ ...brandSettings, secondaryColor: e.target.value })}
                                className="rounded-xl font-mono"
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
                                onChange={(e) => setBrandSettings({ ...brandSettings, accentColor: e.target.value })}
                                className="rounded-xl font-mono"
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
              
              {/* Terms & Conditions */}
              {activeTab === 'terms' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <FileText className="h-5 w-5 text-brand-navy" />
                        {t.termsConditions}
                      </CardTitle>
                      <CardDescription>
                        {t('managePlatformTermsAndConditions')}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Version Info */}
                      <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="flex items-center gap-6">
                          <div>
                            <p className="text-sm text-muted-foreground">{t.currentVersion}</p>
                            <p className="font-bold">{termsData.version}</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">{t.lastUpdated}</p>
                            <p className="font-medium">{formatDateTime(termsData.lastUpdated)}</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" className="rounded-xl" onClick={() => setShowVersionHistoryDialog(true)}>
                            <History className="h-4 w-4 me-2" />
                            {t.versionHistory}
                          </Button>
                          <Button className="rounded-xl bg-brand-navy" onClick={() => setShowPublishDialog(true)}>
                            {t.publishVersion}
                          </Button>
                        </div>
                      </div>
                      
                      {/* Content Editor */}
                      <div className="space-y-2">
                        <Label>{t.termsText}</Label>
                        <Textarea
                          value={termsData.content}
                          onChange={(e) => setTermsData({ ...termsData, content: e.target.value })}
                          rows={20}
                          className="rounded-xl font-tajawal"
                        />
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
              
              {/* Privacy Policy */}
              {activeTab === 'privacy' && (
                <div className="space-y-6">
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-brand-navy" />
                        {t.privacyPolicy}
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
                            <p className="text-sm text-muted-foreground">{t.currentVersion}</p>
                            <p className="font-bold">{privacyData.version}</p>
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">{t.lastUpdated}</p>
                            <p className="font-medium">{formatDateTime(privacyData.lastUpdated)}</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" className="rounded-xl" onClick={() => setShowVersionHistoryDialog(true)}>
                            <History className="h-4 w-4 me-2" />
                            {t.versionHistory}
                          </Button>
                          <Button className="rounded-xl bg-brand-navy" onClick={() => setShowPublishDialog(true)}>
                            {t.publishVersion}
                          </Button>
                        </div>
                      </div>
                      
                      {/* Content Editor */}
                      <div className="space-y-2">
                        <Label>{t.privacyText}</Label>
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
                        {t.contactInfo}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* Contact Details */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t.primaryEmail}</Label>
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
                          <Label>{t.supportEmail}</Label>
                          <Input
                            type="email"
                            value={contactInfo.supportEmail}
                            onChange={(e) => setContactInfo({ ...contactInfo, supportEmail: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.primaryPhone}</Label>
                          <Input
                            type="tel"
                            value={contactInfo.primaryPhone}
                            onChange={(e) => setContactInfo({ ...contactInfo, primaryPhone: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.alternatePhone}</Label>
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
                        <Label>{t.address}</Label>
                        <Textarea
                          value={contactInfo.address}
                          onChange={(e) => setContactInfo({ ...contactInfo, address: e.target.value })}
                          rows={2}
                          className="rounded-xl"
                        />
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t.workingHours}</Label>
                          <Input
                            value={contactInfo.workingHours}
                            onChange={(e) => setContactInfo({ ...contactInfo, workingHours: e.target.value })}
                            className="rounded-xl"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>{t.website}</Label>
                          <Input
                            value={contactInfo.website}
                            onChange={(e) => setContactInfo({ ...contactInfo, website: e.target.value })}
                            className="rounded-xl"
                            dir="ltr"
                          />
                        </div>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>{t.ownerName}</Label>
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
                          {t.socialMedia}
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
                  {/* Active Sessions */}
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          <Monitor className="h-5 w-5 text-brand-navy" />
                          {t.activeSessions}
                        </CardTitle>
                        <CardDescription>
                          {t('yourActiveSessionsOnDifferentDevices')}
                        </CardDescription>
                      </div>
                      <Button variant="outline" className="rounded-xl" onClick={handleEndAllSessions}>
                        {t.endOtherSessions}
                      </Button>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {activeSessions.length === 0 ? (
                          <div className="text-center py-8 text-muted-foreground">
                            <Monitor className="h-12 w-12 mx-auto mb-2 opacity-50" />
                            <p>{t('noActiveSessions')}</p>
                          </div>
                        ) : (
                          activeSessions.map(session => (
                          <div 
                            key={session.id}
                            className={`flex items-center justify-between p-4 rounded-xl ${
                              session.current ? 'bg-green-50 border border-green-200' : 'bg-muted/30'
                            }`}
                          >
                            <div className="flex items-center gap-4">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                                session.current ? 'bg-green-100' : 'bg-muted'
                              }`}>
                                <Monitor className={`h-5 w-5 ${session.current ? 'text-green-600' : 'text-muted-foreground'}`} />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <p className="font-medium">{session.device}</p>
                                  {session.current && (
                                    <Badge className="bg-green-500">
                                      {t('current4')}
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-sm text-muted-foreground">
                                  {session.ip} • {session.location}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-4">
                              <p className="text-sm text-muted-foreground">
                                {formatDateTime(session.lastActive)}
                              </p>
                              {!session.current && (
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                  onClick={() => handleEndSession(session.id)}
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              )}
                            </div>
                          </div>
                        ))
                        )}
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Security Settings */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5 text-brand-navy" />
                        {t.securitySessions}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-6">
                      {/* 2FA */}
                      <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
                            <Shield className="h-5 w-5 text-purple-600" />
                          </div>
                          <div>
                            <h4 className="font-medium">{t.twoFactorAuth}</h4>
                            <p className="text-sm text-muted-foreground">
                              {t('extraLayerOfSecurityForYourAccount')}
                            </p>
                          </div>
                        </div>
                        <Switch
                          checked={securitySettings.twoFactorEnabled}
                          onCheckedChange={(v) => setSecuritySettings({ ...securitySettings, twoFactorEnabled: v })}
                        />
                      </div>
                      
                      {/* Session Settings */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-2">
                          <Label>{t.sessionExpiry}</Label>
                          <Select 
                            value={String(securitySettings.sessionTimeout)} 
                            onValueChange={(v) => setSecuritySettings({ ...securitySettings, sessionTimeout: parseInt(v) })}
                          >
                            <SelectTrigger className="rounded-xl">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="15">15 {t.minutes}</SelectItem>
                              <SelectItem value="30">30 {t.minutes}</SelectItem>
                              <SelectItem value="60">60 {t.minutes}</SelectItem>
                              <SelectItem value="120">2 {t.hours}</SelectItem>
                              <SelectItem value="1440">24 {t.hours}</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>{t.maxSessions}</Label>
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
                        <h4 className="font-medium mb-4">{t.passwordPolicy}</h4>
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
        
        {/* Change Password Dialog */}
        <Dialog open={showPasswordDialog} onOpenChange={setShowPasswordDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Key className="h-5 w-5 text-brand-navy" />
                {t.changePassword}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t.currentPassword}</Label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    value={passwordForm.currentPassword}
                    onChange={(e) => setPasswordForm({ ...passwordForm, currentPassword: e.target.value })}
                    className="rounded-xl pe-10"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute end-0 top-0"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label>{t.newPassword}</Label>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={passwordForm.newPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                  className="rounded-xl"
                />
              </div>
              <div className="space-y-2">
                <Label>{t.confirmPassword}</Label>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  value={passwordForm.confirmPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                  className="rounded-xl"
                />
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowPasswordDialog(false)}>{t.cancel}</Button>
              <Button onClick={handleChangePassword} disabled={loading} className="bg-brand-navy">
                {loading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Key className="h-4 w-4 me-2" />}
                {t.save}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Logout Dialog */}
        <AlertDialog open={showLogoutDialog} onOpenChange={setShowLogoutDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <LogOut className="h-5 w-5 text-red-600" />
                {t.confirmLogout}
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
                {t.logoutNormal}
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start rounded-xl"
                onClick={() => handleLogout('all')}
              >
                <Monitor className="h-4 w-4 me-3" />
                {t.logoutAllDevices}
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start rounded-xl"
                onClick={() => handleLogout('others')}
              >
                <Users className="h-4 w-4 me-3" />
                {t.logoutOtherDevices}
              </Button>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>{t.cancel}</AlertDialogCancel>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        
        {/* Switch User Dialog */}
        <Dialog open={showSwitchUserDialog} onOpenChange={setShowSwitchUserDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-brand-navy" />
                {t.switchUser}
              </DialogTitle>
              <DialogDescription>
                {t('temporarilyAccessAnotherUserAccount')}
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <div className="space-y-2">
                <Label>{t.selectUser}</Label>
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
              <Button variant="outline" onClick={() => setShowSwitchUserDialog(false)}>{t.cancel}</Button>
              <Button className="bg-brand-navy">
                <Users className="h-4 w-4 me-2" />
                {t.switchUser}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Publish Version Dialog */}
        <Dialog open={showPublishDialog} onOpenChange={setShowPublishDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t.publishVersion}</DialogTitle>
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
              <Button variant="outline" onClick={() => setShowPublishDialog(false)}>{t.cancel}</Button>
              <Button onClick={handlePublishVersion} className="bg-brand-navy">
                <CheckCircle2 className="h-4 w-4 me-2" />
                {t.publishVersion}
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
                {t.versionHistory}
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
              <Button variant="outline" onClick={() => setShowVersionHistoryDialog(false)}>{t.cancel}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};

export default PlatformSettingsPage;
