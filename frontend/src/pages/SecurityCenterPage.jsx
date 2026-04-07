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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Progress } from '../components/ui/progress';
import { Switch } from '../components/ui/switch';
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
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '../components/ui/sheet';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Lock,
  Unlock,
  Key,
  UserCheck,
  UserX,
  Users,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  Download,
  Eye,
  EyeOff,
  Activity,
  Server,
  Database,
  HardDrive,
  FileText,
  Search,
  Filter,
  RotateCcw,
  Zap,
  Brain,
  Loader2,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  LogIn,
  LogOut,
  KeyRound,
  Fingerprint,
  Settings,
  History,
  Bell,
  BellRing,
  TriangleAlert,
  Info,
  Play,
  Pause,
  Ban,
  LockKeyhole,
  Gauge,
  CloudOff,
  Cloud,
  Wifi,
  WifiOff,
} from 'lucide-react';


// Translations
const translations = {
  ar: {
    pageTitle: 'مركز الأمان',
    pageSubtitle: 'إدارة ومراقبة الوضع الأمني للمنصة',
    overview: 'نظرة عامة',
    indicators: 'المؤشرات',
    alerts: 'التنبيهات',
    logs: 'السجلات',
    tools: 'الأدوات',
    securityScore: 'درجة الأمان',
    excellent: 'ممتاز',
    good: 'جيد',
    warning: 'تحذير',
    critical: 'حرج',
    protectedAccounts: 'الحسابات المحمية',
    applicationSecurity: 'تأمين التطبيق',
    failedLogins: 'محاولات الدخول الفاشلة',
    lockedAccounts: 'الحسابات المقفلة',
    encryptedData: 'البيانات المشفرة',
    passwordPolicy: 'سياسة كلمات المرور',
    backupStatus: 'حالة النسخ الاحتياطي',
    loggingCoverage: 'تغطية السجلات',
    strong: 'قوية',
    medium: 'متوسطة',
    weak: 'ضعيفة',
    lastBackup: 'آخر نسخة احتياطية',
    totalBackups: 'إجمالي النسخ',
    securityAlerts: 'التنبيهات الأمنية',
    highPriority: 'أولوية عالية',
    mediumPriority: 'أولوية متوسطة',
    lowPriority: 'أولوية منخفضة',
    viewDetails: 'عرض التفاصيل',
    dismiss: 'تجاهل',
    escalate: 'تصعيد',
    securityEvents: 'الأحداث الأمنية',
    loginAttempt: 'محاولة دخول',
    loginFailed: 'دخول فاشل',
    passwordChange: 'تغيير كلمة مرور',
    accountLocked: 'قفل حساب',
    accountUnlocked: 'فتح حساب',
    permissionChange: 'تغيير صلاحيات',
    sessionEnded: 'إنهاء جلسة',
    quickActions: 'إجراءات سريعة',
    lockAccount: 'قفل حساب',
    unlockAccount: 'فتح حساب',
    endAllSessions: 'إنهاء جميع الجلسات',
    forcePasswordChange: 'فرض تغيير كلمة المرور',
    runSecurityScan: 'تشغيل فحص أمني',
    downloadReport: 'تحميل تقرير الأمان',
    reviewIncidents: 'مراجعة الحوادث',
    aiAnalysis: 'تحليل AI للأمان',
    aiRecommendations: 'توصيات الذكاء الاصطناعي',
    generateReport: 'إنشاء تقرير',
    filterByType: 'تصفية حسب النوع',
    filterByPriority: 'تصفية حسب الأولوية',
    search: 'بحث...',
    all: 'الكل',
    today: 'اليوم',
    thisWeek: 'هذا الأسبوع',
    thisMonth: 'هذا الشهر',
    refresh: 'تحديث',
    export: 'تصدير',
    close: 'إغلاق',
    confirm: 'تأكيد',
    cancel: 'إلغاء',
    hoursAgo: 'ساعة',
    minutesAgo: 'دقيقة',
    accounts: 'حساب',
    improveScore: 'تحسين الدرجة',
    scoreFactors: 'عوامل الدرجة',
    recommendations: 'التوصيات',
  },
  en: {
    pageTitle: 'Security Center',
    pageSubtitle: 'Manage and monitor platform security',
    overview: 'Overview',
    indicators: 'Indicators',
    alerts: 'Alerts',
    logs: 'Logs',
    tools: 'Tools',
    securityScore: 'Security Score',
    excellent: 'Excellent',
    good: 'Good',
    warning: 'Warning',
    critical: 'Critical',
    protectedAccounts: 'Protected Accounts',
    applicationSecurity: 'Application Security',
    failedLogins: 'Failed Login Attempts',
    lockedAccounts: 'Locked Accounts',
    encryptedData: 'Encrypted Data',
    passwordPolicy: 'Password Policy',
    backupStatus: 'Backup Status',
    loggingCoverage: 'Logging Coverage',
    strong: 'Strong',
    medium: 'Medium',
    weak: 'Weak',
    lastBackup: 'Last Backup',
    totalBackups: 'Total Backups',
    securityAlerts: 'Security Alerts',
    highPriority: 'High Priority',
    mediumPriority: 'Medium Priority',
    lowPriority: 'Low Priority',
    viewDetails: 'View Details',
    dismiss: 'Dismiss',
    escalate: 'Escalate',
    securityEvents: 'Security Events',
    loginAttempt: 'Login Attempt',
    loginFailed: 'Login Failed',
    passwordChange: 'Password Change',
    accountLocked: 'Account Locked',
    accountUnlocked: 'Account Unlocked',
    permissionChange: 'Permission Change',
    sessionEnded: 'Session Ended',
    quickActions: 'Quick Actions',
    lockAccount: 'Lock Account',
    unlockAccount: 'Unlock Account',
    endAllSessions: 'End All Sessions',
    forcePasswordChange: 'Force Password Change',
    runSecurityScan: 'Run Security Scan',
    downloadReport: 'Download Security Report',
    reviewIncidents: 'Review Incidents',
    aiAnalysis: 'AI Security Analysis',
    aiRecommendations: 'AI Recommendations',
    generateReport: 'Generate Report',
    filterByType: 'Filter by Type',
    filterByPriority: 'Filter by Priority',
    search: 'Search...',
    all: 'All',
    today: 'Today',
    thisWeek: 'This Week',
    thisMonth: 'This Month',
    refresh: 'Refresh',
    export: 'Export',
    close: 'Close',
    confirm: 'Confirm',
    cancel: 'Cancel',
    hoursAgo: 'hours ago',
    minutesAgo: 'minutes ago',
    accounts: 'accounts',
    improveScore: 'Improve Score',
    scoreFactors: 'Score Factors',
    recommendations: 'Recommendations',
  }
};

// Security score factors
// Empty initial states - data will be fetched from API
const INITIAL_SCORE_FACTORS = [];
const INITIAL_SECURITY_ALERTS = [];
const INITIAL_SECURITY_EVENTS = [];
const INITIAL_AI_RECOMMENDATIONS = [];

export default function SecurityCenterPage() {
  const { isRTL = true, isDark } = useTheme();
  const navigate = useNavigate();
  const { api } = useAuth();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showScoreDetailsDialog, setShowScoreDetailsDialog] = useState(false);
  const [showAlertDetailsSheet, setShowAlertDetailsSheet] = useState(false);
  const [showLockAccountDialog, setShowLockAccountDialog] = useState(false);
  const [showUnlockAccountDialog, setShowUnlockAccountDialog] = useState(false);
  const [showEndSessionsDialog, setShowEndSessionsDialog] = useState(false);
  const [showForcePasswordDialog, setShowForcePasswordDialog] = useState(false);
  const [showAIReportDialog, setShowAIReportDialog] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [generatingReport, setGeneratingReport] = useState(false);
  
  // Dynamic data states
  const [scoreFactors, setScoreFactors] = useState(INITIAL_SCORE_FACTORS);
  const [securityAlerts, setSecurityAlerts] = useState(INITIAL_SECURITY_ALERTS);
  const [securityEvents, setSecurityEvents] = useState(INITIAL_SECURITY_EVENTS);
  const [aiRecommendations, setAiRecommendations] = useState(INITIAL_AI_RECOMMENDATIONS);
  
  // New states for security operations
  const [accountSearchQuery, setAccountSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [forcePasswordType, setForcePasswordType] = useState('user'); // 'user', 'role', 'all'
  const [selectedRole, setSelectedRole] = useState('');
  const [availableRoles, setAvailableRoles] = useState([]);
  const [lockReason, setLockReason] = useState('suspicious');
  
  const [metrics, setMetrics] = useState({
    securityScore: 87,
    protectedAccounts: 1240,
    totalAccounts: 1425,
    applicationSecurity: 93,
    failedLogins24h: 15,
    lockedAccounts: 3,
    encryptedData: 100,
    passwordPolicyStrength: 'strong',
    lastBackup: '2026-03-09T06:00:00Z',
    totalBackups: 12,
    loggingCoverage: 100,
  });
  
  const getScoreColor = (score) => {
  const { t } = useTranslation();
    if (score >= 90) return { color: 'text-green-600', bg: 'bg-green-500', label: t.excellent };
    if (score >= 70) return { color: 'text-blue-600', bg: 'bg-blue-500', label: t.good };
    if (score >= 50) return { color: 'text-yellow-600', bg: 'bg-yellow-500', label: t.warning };
    return { color: 'text-red-600', bg: 'bg-red-500', label: t.critical };
  };
  
  const scoreInfo = getScoreColor(metrics.securityScore);
  
  const formatRelativeTime = (dateStr) => {
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    if (diffMins < 60) return `${diffMins} ${t.minutesAgo}`;
    if (diffHours < 24) return `${diffHours} ${t.hoursAgo}`;
    return date.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US');
  };
  
  const formatDateTime = (dateStr) => {
    return new Date(dateStr).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };
  
  const getEventTypeInfo = (type) => {
    const types = {
      login: { icon: LogIn, color: 'text-green-600 bg-green-100', label: t.loginAttempt },
      login_failed: { icon: LogIn, color: 'text-red-600 bg-red-100', label: t.loginFailed },
      password_change: { icon: KeyRound, color: 'text-blue-600 bg-blue-100', label: t.passwordChange },
      account_locked: { icon: Lock, color: 'text-orange-600 bg-orange-100', label: t.accountLocked },
      permission_change: { icon: Settings, color: 'text-purple-600 bg-purple-100', label: t.permissionChange },
    };
    return types[type] || types.login;
  };
  
  const getAlertPriorityInfo = (type) => {
    const types = {
      high: { icon: AlertTriangle, color: 'text-red-600 bg-red-100 border-red-200', label: t.highPriority },
      medium: { icon: AlertCircle, color: 'text-yellow-600 bg-yellow-100 border-yellow-200', label: t.mediumPriority },
      low: { icon: Info, color: 'text-blue-600 bg-blue-100 border-blue-200', label: t.lowPriority },
    };
    return types[type] || types.low;
  };
  
  const handleRefresh = () => {
    setRefreshing(true);
    setTimeout(() => { setRefreshing(false); toast.success(t('dataRefreshed')); }, 1500);
  };
  
  // ============= NEW SECURITY API FUNCTIONS =============
  
  // Search for account by email or phone
  const handleSearchAccount = async () => {
    if (!accountSearchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const response = await api.post('/security/search-account', { search_query: accountSearchQuery });
      setSearchResults(response.data || []);
      if (response.data?.length === 0) {
        toast.info(t('noResultsFound'));
      }
    } catch (error) {
      console.error('Search error:', error);
      nassaqError(t('searchFailed'));
    } finally {
      setSearchLoading(false);
    }
  };
  
  // Lock account
  const handleLockAccount = async () => {
    if (!selectedAccount) return;
    setActionLoading(true);
    try {
      await api.post(`/security/lock-account/${selectedAccount.id}`);
      toast.success(t('accountLockedSuccessfully'));
      setShowLockAccountDialog(false);
      setSelectedAccount(null);
      setSearchResults([]);
      setAccountSearchQuery('');
    } catch (error) {
      console.error('Lock error:', error);
      nassaqError(t('failedToLockAccount'));
    } finally {
      setActionLoading(false);
    }
  };
  
  // Unlock account
  const handleUnlockAccount = async () => {
    if (!selectedAccount) return;
    setActionLoading(true);
    try {
      await api.post(`/security/unlock-account/${selectedAccount.id}`);
      toast.success(t('accountUnlockedSuccessfully'));
      setShowUnlockAccountDialog(false);
      setSelectedAccount(null);
      setSearchResults([]);
      setAccountSearchQuery('');
    } catch (error) {
      console.error('Unlock error:', error);
      nassaqError(t('failedToUnlockAccount'));
    } finally {
      setActionLoading(false);
    }
  };
  
  // End all sessions
  const handleEndAllSessions = async () => {
    setActionLoading(true);
    try {
      const response = await api.post('/security/end-all-sessions');
      toast.success(
        isRTL 
          ? `تم إنهاء ${response.data.affected_count} جلسة` 
          : `${response.data.affected_count} sessions ended`
      );
      setShowEndSessionsDialog(false);
    } catch (error) {
      console.error('End sessions error:', error);
      nassaqError(t('failedToEndSessions'));
    } finally {
      setActionLoading(false);
    }
  };
  
  // Force password change
  const handleForcePasswordChange = async () => {
    setActionLoading(true);
    try {
      const payload = {
        target_type: forcePasswordType,
        user_id: forcePasswordType === 'user' ? selectedAccount?.id : null,
        role: forcePasswordType === 'role' ? selectedRole : null,
      };
      
      const response = await api.post('/security/force-password-change', payload);
      toast.success(
        isRTL 
          ? `تم فرض تغيير كلمة المرور على ${response.data.affected_count} مستخدم` 
          : `Password change forced for ${response.data.affected_count} users`
      );
      setShowForcePasswordDialog(false);
      setSelectedAccount(null);
      setForcePasswordType('user');
    } catch (error) {
      console.error('Force password error:', error);
      nassaqError(t('failedToForcePasswordChange'));
    } finally {
      setActionLoading(false);
    }
  };
  
  // Fetch available roles
  const fetchRoles = async () => {
    try {
      const response = await api.get('/security/roles');
      setAvailableRoles(response.data || []);
    } catch (error) {
      console.error('Fetch roles error:', error);
    }
  };
  
  // Load roles on component mount
  React.useEffect(() => {
    fetchRoles();
  }, []);
  
  // Reset search when dialog opens
  const openLockDialog = () => {
    setAccountSearchQuery('');
    setSearchResults([]);
    setSelectedAccount(null);
    setShowLockAccountDialog(true);
  };
  
  const openUnlockDialog = () => {
    setAccountSearchQuery('');
    setSearchResults([]);
    setSelectedAccount(null);
    setShowUnlockAccountDialog(true);
  };
  
  const openForcePasswordDialog = () => {
    setAccountSearchQuery('');
    setSearchResults([]);
    setSelectedAccount(null);
    setForcePasswordType('user');
    setShowForcePasswordDialog(true);
  };
  
  // ============= END NEW SECURITY API FUNCTIONS =============

  const handleDownloadReport = () => {
    setLoading(true);
    // إنشاء تقرير أمان حقيقي
    const report = {
      generated_at: new Date().toISOString(),
      security_score: metrics.securityScore,
      metrics: metrics,
      alerts: securityAlerts,
      recent_events: securityEvents.slice(0, 20),
      recommendations: [
        'تفعيل المصادقة الثنائية لجميع المستخدمين',
        'مراجعة الحسابات غير النشطة',
        'تحديث سياسات كلمات المرور',
        'فحص سجلات الدخول المشبوهة',
      ],
    };
    
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `security_report_${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    
    setLoading(false);
    toast.success(t('securityReportDownloaded'));
  };
  
  const handleGenerateAIReport = () => {
    setGeneratingReport(true);
    setTimeout(() => { setGeneratingReport(false); toast.success(t('aiReportGenerated')); setShowAIReportDialog(false); }, 3000);
  };
  
  const handleQuickAction = (action) => {
    // محاكاة تنفيذ الإجراء مع تأخير بسيط
    const actionMessages = {
      'Unlock Account': { ar: 'تم فتح الحساب بنجاح', en: 'Account unlocked successfully' },
      'End All Sessions': { ar: 'تم إنهاء جميع الجلسات النشطة', en: 'All sessions terminated' },
      'Force Password Change': { ar: 'تم إرسال طلب تغيير كلمة المرور', en: 'Password change request sent' },
      'Security Scan': { ar: 'بدء فحص الأمان...', en: 'Starting security scan...' },
    };
    
    const msg = actionMessages[action] || { ar: `تم تنفيذ: ${action}`, en: `Executed: ${action}` };
    
    if (action === 'Security Scan') {
      toast.promise(
        new Promise((resolve) => setTimeout(resolve, 3000)),
        {
          loading: t('runningSecurityScan'),
          success: t('securityScanCompleteScore95'),
          error: t('scanFailed'),
        }
      );
    } else {
      toast.success(isRTL ? msg.ar : msg.en);
    }
  };
  
  const filteredEvents = securityEvents.filter(event => {
    if (filterType !== 'all' && event.type !== filterType) return false;
    if (searchQuery && !event.user.toLowerCase().includes(searchQuery.toLowerCase()) && !event.email.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });
  
  const filteredAlerts = securityAlerts.filter(alert => filterPriority === 'all' || alert.type === filterPriority);
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'} data-testid="security-center-page">
        <header className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b">
          <div className="container mx-auto px-4 lg:px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <PageHeader title={t.pageTitle} subtitle={t.pageSubtitle} icon={Shield} className="mb-0" />
              <div className="flex items-center gap-2">
                <Button variant="outline" className="rounded-xl" onClick={handleRefresh} disabled={refreshing}>
                  {refreshing ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <RefreshCw className="h-4 w-4 me-2" />}
                  {t.refresh}
                </Button>
                <Button className="rounded-xl bg-brand-navy hover:bg-brand-navy/90" onClick={handleDownloadReport} disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Download className="h-4 w-4 me-2" />}
                  {t.downloadReport}
                </Button>
              </div>
            </div>
          </div>
        </header>
        
        <main className="container mx-auto px-4 lg:px-6 py-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <TabsList className="grid w-full max-w-2xl grid-cols-5">
              <TabsTrigger value="overview"><Shield className="h-4 w-4 me-2" />{t.overview}</TabsTrigger>
              <TabsTrigger value="indicators"><Gauge className="h-4 w-4 me-2" />{t.indicators}</TabsTrigger>
              <TabsTrigger value="alerts"><BellRing className="h-4 w-4 me-2" />{t.alerts}</TabsTrigger>
              <TabsTrigger value="logs"><History className="h-4 w-4 me-2" />{t.logs}</TabsTrigger>
              <TabsTrigger value="tools"><Settings className="h-4 w-4 me-2" />{t.tools}</TabsTrigger>
            </TabsList>
            
            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-6">
              <Card className={`bg-gradient-to-br ${metrics.securityScore >= 90 ? 'from-green-500 to-green-600' : metrics.securityScore >= 70 ? 'from-blue-500 to-blue-600' : 'from-yellow-500 to-yellow-600'} text-white cursor-pointer hover:shadow-xl transition-all`} onClick={() => setShowScoreDetailsDialog(true)}>
                <CardContent className="p-8">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-6">
                      <div className="relative w-32 h-32">
                        <svg className="w-full h-full transform -rotate-90">
                          <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="12" fill="none" className="text-white/20" />
                          <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="12" fill="none" strokeDasharray={`${metrics.securityScore * 3.52} 352`} className="text-white" strokeLinecap="round" />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center"><span className="text-4xl font-bold">{metrics.securityScore}%</span></div>
                      </div>
                      <div>
                        <h2 className="text-3xl font-bold mb-2">{t.securityScore}</h2>
                        <Badge className="bg-white/20 text-white text-lg px-4 py-1">{scoreInfo.label}</Badge>
                        <p className="text-white/70 mt-2">{t('clickToViewScoreDetails')}</p>
                      </div>
                    </div>
                    <ShieldCheck className="h-24 w-24 text-white/20" />
                  </div>
                </CardContent>
              </Card>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="hover:shadow-lg transition-all">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <UserCheck className="h-8 w-8 text-green-600" />
                      <Badge variant="outline" className="text-green-600">{((metrics.protectedAccounts / metrics.totalAccounts) * 100).toFixed(0)}%</Badge>
                    </div>
                    <h3 className="font-bold text-2xl">{metrics.protectedAccounts.toLocaleString()}</h3>
                    <p className="text-sm text-muted-foreground">{t.protectedAccounts}</p>
                    <Progress value={(metrics.protectedAccounts / metrics.totalAccounts) * 100} className="mt-2 h-2" />
                  </CardContent>
                </Card>
                <Card className="hover:shadow-lg transition-all">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <Shield className="h-8 w-8 text-blue-600" />
                      <Badge variant="outline" className="text-blue-600">{metrics.applicationSecurity}%</Badge>
                    </div>
                    <h3 className="font-bold text-2xl">{metrics.applicationSecurity}%</h3>
                    <p className="text-sm text-muted-foreground">{t.applicationSecurity}</p>
                    <Progress value={metrics.applicationSecurity} className="mt-2 h-2" />
                  </CardContent>
                </Card>
                <Card className="hover:shadow-lg transition-all">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <AlertTriangle className="h-8 w-8 text-orange-600" />
                      <Badge variant="outline" className="text-orange-600">24h</Badge>
                    </div>
                    <h3 className="font-bold text-2xl">{metrics.failedLogins24h}</h3>
                    <p className="text-sm text-muted-foreground">{t.failedLogins}</p>
                  </CardContent>
                </Card>
                <Card className="hover:shadow-lg transition-all">
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <Lock className="h-8 w-8 text-red-600" />
                      <Badge variant="outline" className="text-red-600">{t.accounts}</Badge>
                    </div>
                    <h3 className="font-bold text-2xl">{metrics.lockedAccounts}</h3>
                    <p className="text-sm text-muted-foreground">{t.lockedAccounts}</p>
                  </CardContent>
                </Card>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-green-50 border-green-200">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center"><Lock className="h-5 w-5 text-green-600" /></div>
                      <div>
                        <p className="text-sm text-muted-foreground">{t.encryptedData}</p>
                        <p className="font-bold text-xl text-green-600">{metrics.encryptedData}%</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-green-600" /><span className="text-sm text-green-600">{t('fullyEncrypted')}</span></div>
                  </CardContent>
                </Card>
                <Card className="bg-blue-50 border-blue-200">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center"><Key className="h-5 w-5 text-blue-600" /></div>
                      <div>
                        <p className="text-sm text-muted-foreground">{t.passwordPolicy}</p>
                        <p className="font-bold text-xl text-blue-600">{t.strong}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-blue-600" /><span className="text-sm text-blue-600">{t('12Characters')}</span></div>
                  </CardContent>
                </Card>
                <Card className="bg-purple-50 border-purple-200">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center"><Database className="h-5 w-5 text-purple-600" /></div>
                      <div>
                        <p className="text-sm text-muted-foreground">{t.backupStatus}</p>
                        <p className="font-bold text-xl text-purple-600">{metrics.totalBackups}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2"><Clock className="h-4 w-4 text-purple-600" /><span className="text-sm text-purple-600">{formatRelativeTime(metrics.lastBackup)}</span></div>
                  </CardContent>
                </Card>
                <Card className="bg-cyan-50 border-cyan-200">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-xl bg-cyan-100 flex items-center justify-center"><FileText className="h-5 w-5 text-cyan-600" /></div>
                      <div>
                        <p className="text-sm text-muted-foreground">{t.loggingCoverage}</p>
                        <p className="font-bold text-xl text-cyan-600">{metrics.loggingCoverage}%</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-cyan-600" /><span className="text-sm text-cyan-600">{t('fullCoverage')}</span></div>
                  </CardContent>
                </Card>
              </div>
              
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-2"><BellRing className="h-5 w-5 text-brand-navy" />{t.securityAlerts}</CardTitle>
                  <Button variant="outline" size="sm" onClick={() => setActiveTab('alerts')}>{t('viewAll')}<ChevronRight className="h-4 w-4 ms-1 rtl:rotate-180" /></Button>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {securityAlerts.slice(0, 3).map(alert => {
                      const priorityInfo = getAlertPriorityInfo(alert.type);
                      const PriorityIcon = priorityInfo.icon;
                      return (
                        <div key={alert.id} className={`p-4 rounded-xl border ${priorityInfo.color} cursor-pointer hover:shadow-md transition-all`} onClick={() => { setSelectedAlert(alert); setShowAlertDetailsSheet(true); }}>
                          <div className="flex items-start gap-3">
                            <PriorityIcon className="h-5 w-5 mt-0.5" />
                            <div className="flex-1">
                              <div className="flex items-center justify-between mb-1">
                                <h4 className="font-medium">{isRTL ? alert.title_ar : alert.title_en}</h4>
                                <Badge variant="outline">{formatRelativeTime(alert.timestamp)}</Badge>
                              </div>
                              <p className="text-sm text-muted-foreground">{isRTL ? alert.description_ar : alert.description_en}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* Indicators Tab */}
            <TabsContent value="indicators" className="space-y-6">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Gauge className="h-5 w-5 text-brand-navy" />{t.scoreFactors}</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {scoreFactors.map(factor => (
                      <div key={factor.id} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{isRTL ? factor.label_ar : factor.label_en}</span>
                          <span className="text-sm text-muted-foreground">{factor.value}% ({factor.weight}%)</span>
                        </div>
                        <Progress value={factor.value} className="h-2" />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* Alerts Tab */}
            <TabsContent value="alerts" className="space-y-6">
              <div className="flex items-center gap-4">
                <Select value={filterPriority} onValueChange={setFilterPriority}>
                  <SelectTrigger className="w-48"><SelectValue placeholder={t.filterByPriority} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t.all}</SelectItem>
                    <SelectItem value="high">{t.highPriority}</SelectItem>
                    <SelectItem value="medium">{t.mediumPriority}</SelectItem>
                    <SelectItem value="low">{t.lowPriority}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-4">
                {filteredAlerts.map(alert => {
                  const priorityInfo = getAlertPriorityInfo(alert.type);
                  const PriorityIcon = priorityInfo.icon;
                  return (
                    <Card key={alert.id} className="border-2">
                      <CardContent className="p-5">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${priorityInfo.color}`}><PriorityIcon className="h-6 w-6" /></div>
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-bold">{isRTL ? alert.title_ar : alert.title_en}</h4>
                                <Badge>{alert.status}</Badge>
                              </div>
                              <p className="text-sm text-muted-foreground mb-2">{isRTL ? alert.description_ar : alert.description_en}</p>
                              <p className="text-xs text-muted-foreground">{formatDateTime(alert.timestamp)}</p>
                            </div>
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm"><Eye className="h-4 w-4 me-1" />{t.viewDetails}</Button>
                            <Button variant="outline" size="sm">{t.dismiss}</Button>
                            <Button variant="destructive" size="sm">{t.escalate}</Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </TabsContent>
            
            {/* Logs Tab */}
            <TabsContent value="logs" className="space-y-6">
              <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input placeholder={t.search} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="ps-10" />
                </div>
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-48"><SelectValue placeholder={t.filterByType} /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t.all}</SelectItem>
                    <SelectItem value="login">{t.loginAttempt}</SelectItem>
                    <SelectItem value="login_failed">{t.loginFailed}</SelectItem>
                    <SelectItem value="password_change">{t.passwordChange}</SelectItem>
                    <SelectItem value="account_locked">{t.accountLocked}</SelectItem>
                  </SelectContent>
                </Select>
                <Button variant="outline"><Download className="h-4 w-4 me-2" />{t.export}</Button>
              </div>
              <Card>
                <CardContent className="p-0">
                  <ScrollArea className="h-[500px]">
                    <div className="divide-y">
                      {filteredEvents.map(event => {
                        const typeInfo = getEventTypeInfo(event.type);
                        const TypeIcon = typeInfo.icon;
                        return (
                          <div key={event.id} className="p-4 hover:bg-muted/30 cursor-pointer transition-colors">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-4">
                                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${typeInfo.color}`}><TypeIcon className="h-5 w-5" /></div>
                                <div>
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium">{event.user}</span>
                                    <Badge variant="outline" className="text-xs">{typeInfo.label}</Badge>
                                  </div>
                                  <p className="text-sm text-muted-foreground">{event.email}</p>
                                </div>
                              </div>
                              <div className="text-end">
                                <p className="text-sm">{event.ip}</p>
                                <p className="text-xs text-muted-foreground">{formatRelativeTime(event.timestamp)}</p>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* Tools Tab */}
            <TabsContent value="tools" className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="cursor-pointer hover:shadow-lg transition-all border-2 border-red-100 hover:border-red-300" onClick={openLockDialog}>
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-red-100 flex items-center justify-center"><Lock className="h-7 w-7 text-red-600" /></div>
                    <h4 className="font-bold mb-1">{t.lockAccount}</h4>
                    <p className="text-xs text-muted-foreground">{t('searchLockAccount')}</p>
                  </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-lg transition-all border-2 border-green-100 hover:border-green-300" onClick={openUnlockDialog}>
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-green-100 flex items-center justify-center"><Unlock className="h-7 w-7 text-green-600" /></div>
                    <h4 className="font-bold mb-1">{t.unlockAccount}</h4>
                    <p className="text-xs text-muted-foreground">{t('searchUnlockAccount')}</p>
                  </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-lg transition-all border-2 border-orange-100 hover:border-orange-300" onClick={() => setShowEndSessionsDialog(true)}>
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-orange-100 flex items-center justify-center"><LogOut className="h-7 w-7 text-orange-600" /></div>
                    <h4 className="font-bold mb-1">{t.endAllSessions}</h4>
                    <p className="text-xs text-muted-foreground">{t('endAllSessions')}</p>
                  </CardContent>
                </Card>
                <Card className="cursor-pointer hover:shadow-lg transition-all border-2 border-purple-100 hover:border-purple-300" onClick={openForcePasswordDialog}>
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-purple-100 flex items-center justify-center"><KeyRound className="h-7 w-7 text-purple-600" /></div>
                    <h4 className="font-bold mb-1">{t.forcePasswordChange}</h4>
                    <p className="text-xs text-muted-foreground">{t('userRoleAll')}</p>
                  </CardContent>
                </Card>
              </div>
              
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2"><Brain className="h-5 w-5 text-brand-navy" />{t.aiRecommendations}</CardTitle></CardHeader>
                <CardContent className="space-y-4">
                  {aiRecommendations.map(rec => (
                    <div key={rec.id} className="p-4 bg-muted/30 rounded-xl">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium">{isRTL ? rec.title_ar : rec.title_en}</h4>
                        <Badge variant={rec.priority === 'high' ? 'destructive' : rec.priority === 'medium' ? 'default' : 'secondary'}>{rec.priority === 'high' ? t.highPriority : rec.priority === 'medium' ? t.mediumPriority : t.lowPriority}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">{isRTL ? rec.description_ar : rec.description_en}</p>
                      <Badge variant="outline" className="text-green-600"><TrendingUp className="h-3 w-3 me-1" />{rec.impact}</Badge>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </main>
        
        {/* Score Details Dialog */}
        <Dialog open={showScoreDetailsDialog} onOpenChange={setShowScoreDetailsDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><Gauge className="h-5 w-5 text-brand-navy" />{t.scoreFactors}</DialogTitle></DialogHeader>
            <div className="py-4 space-y-4">
              {scoreFactors.map(factor => (
                <div key={factor.id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{isRTL ? factor.label_ar : factor.label_en}</span>
                    <div className="flex items-center gap-2">
                      <span className={`font-bold ${factor.value >= 90 ? 'text-green-600' : factor.value >= 70 ? 'text-blue-600' : 'text-yellow-600'}`}>{factor.value}%</span>
                      <Badge variant="outline">{factor.weight}%</Badge>
                    </div>
                  </div>
                  <Progress value={factor.value} className="h-2" />
                </div>
              ))}
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <span className="font-bold">{t('totalScore')}</span>
                  <span className={`text-2xl font-bold ${scoreInfo.color}`}>{metrics.securityScore}%</span>
                </div>
              </div>
            </div>
            <DialogFooter><Button onClick={() => setShowScoreDetailsDialog(false)} className="bg-brand-navy">{t.close}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Lock Account Dialog - Enhanced with Search */}
        <Dialog open={showLockAccountDialog} onOpenChange={setShowLockAccountDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Lock className="h-5 w-5 text-red-600" />{t.lockAccount}</DialogTitle>
              <DialogDescription>{t('searchForAccountByEmailOrPhone')}</DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div className="flex gap-2">
                <Input 
                  placeholder={t('emailOrPhoneNumber')} 
                  value={accountSearchQuery}
                  onChange={(e) => setAccountSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchAccount()}
                />
                <Button onClick={handleSearchAccount} disabled={searchLoading} className="bg-brand-navy">
                  {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
              </div>
              
              {searchResults.length > 0 && (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {searchResults.map((account) => (
                    <div 
                      key={account.id}
                      onClick={() => setSelectedAccount(account)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        selectedAccount?.id === account.id 
                          ? 'border-red-500 bg-red-50' 
                          : 'hover:border-gray-300 hover:bg-muted/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{account.name}</p>
                          <p className="text-sm text-muted-foreground">{account.email}</p>
                          {account.phone && <p className="text-xs text-muted-foreground">{account.phone}</p>}
                        </div>
                        <div className="text-end">
                          <Badge variant="outline">{account.role}</Badge>
                          {account.is_locked && <Badge className="bg-red-500 text-white ms-2">{t('locked')}</Badge>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {selectedAccount && (
                <div className="space-y-2">
                  <Label>{t('reason2')}</Label>
                  <Select value={lockReason} onValueChange={setLockReason}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="suspicious">{t('suspiciousActivity')}</SelectItem>
                      <SelectItem value="violation">{t('policyViolation')}</SelectItem>
                      <SelectItem value="security">{t('securityConcern')}</SelectItem>
                      <SelectItem value="other">{t('other')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowLockAccountDialog(false)}>{t.cancel}</Button>
              <Button 
                variant="destructive" 
                onClick={handleLockAccount} 
                disabled={!selectedAccount || actionLoading}
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Lock className="h-4 w-4 me-2" />}
                {t.lockAccount}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Unlock Account Dialog - Enhanced with Search */}
        <Dialog open={showUnlockAccountDialog} onOpenChange={setShowUnlockAccountDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Unlock className="h-5 w-5 text-green-600" />{t.unlockAccount}</DialogTitle>
              <DialogDescription>{t('searchForLockedAccountToUnlock')}</DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div className="flex gap-2">
                <Input 
                  placeholder={t('emailOrPhoneNumber')} 
                  value={accountSearchQuery}
                  onChange={(e) => setAccountSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearchAccount()}
                />
                <Button onClick={handleSearchAccount} disabled={searchLoading} className="bg-brand-navy">
                  {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                </Button>
              </div>
              
              {searchResults.length > 0 && (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {searchResults.map((account) => (
                    <div 
                      key={account.id}
                      onClick={() => setSelectedAccount(account)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        selectedAccount?.id === account.id 
                          ? 'border-green-500 bg-green-50' 
                          : 'hover:border-gray-300 hover:bg-muted/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">{account.name}</p>
                          <p className="text-sm text-muted-foreground">{account.email}</p>
                        </div>
                        <div className="text-end">
                          <Badge variant="outline">{account.role}</Badge>
                          {account.is_locked && <Badge className="bg-red-500 text-white ms-2">{t('locked')}</Badge>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowUnlockAccountDialog(false)}>{t.cancel}</Button>
              <Button 
                className="bg-green-600 hover:bg-green-700"
                onClick={handleUnlockAccount} 
                disabled={!selectedAccount || actionLoading}
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Unlock className="h-4 w-4 me-2" />}
                {t.unlockAccount}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* End All Sessions Dialog */}
        <Dialog open={showEndSessionsDialog} onOpenChange={setShowEndSessionsDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><LogOut className="h-5 w-5 text-orange-600" />{t.endAllSessions}</DialogTitle>
              <DialogDescription>{t('thisWillEndAllActiveSessionsForAllUsers')}</DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <div className="p-4 bg-orange-50 border border-orange-200 rounded-xl">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-6 w-6 text-orange-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-orange-800">{t('importantWarning')}</p>
                    <p className="text-sm text-orange-700 mt-1">
                      {t('allUsersWillBeLoggedOutExceptYouUseThisOnlyInEmerg')
                      }
                    </p>
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowEndSessionsDialog(false)}>{t.cancel}</Button>
              <Button 
                variant="destructive" 
                onClick={handleEndAllSessions} 
                disabled={actionLoading}
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <LogOut className="h-4 w-4 me-2" />}
                {t('endAllSessions2')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Force Password Change Dialog - Enhanced with Options */}
        <Dialog open={showForcePasswordDialog} onOpenChange={setShowForcePasswordDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><KeyRound className="h-5 w-5 text-purple-600" />{t.forcePasswordChange}</DialogTitle>
              <DialogDescription>{t('forcePasswordChangeForUserRoleOrEveryone')}</DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              {/* Option Selection */}
              <div className="grid grid-cols-3 gap-2">
                <Button 
                  variant={forcePasswordType === 'user' ? 'default' : 'outline'}
                  onClick={() => setForcePasswordType('user')}
                  className={forcePasswordType === 'user' ? 'bg-purple-600' : ''}
                >
                  {t('specificUser')}
                </Button>
                <Button 
                  variant={forcePasswordType === 'role' ? 'default' : 'outline'}
                  onClick={() => setForcePasswordType('role')}
                  className={forcePasswordType === 'role' ? 'bg-purple-600' : ''}
                >
                  {t('byRole')}
                </Button>
                <Button 
                  variant={forcePasswordType === 'all' ? 'default' : 'outline'}
                  onClick={() => setForcePasswordType('all')}
                  className={forcePasswordType === 'all' ? 'bg-red-600' : ''}
                >
                  {t('everyone')}
                </Button>
              </div>
              
              {/* User Search */}
              {forcePasswordType === 'user' && (
                <>
                  <div className="flex gap-2">
                    <Input 
                      placeholder={t('emailOrPhoneNumber')} 
                      value={accountSearchQuery}
                      onChange={(e) => setAccountSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSearchAccount()}
                    />
                    <Button onClick={handleSearchAccount} disabled={searchLoading} className="bg-brand-navy">
                      {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    </Button>
                  </div>
                  
                  {searchResults.length > 0 && (
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                      {searchResults.map((account) => (
                        <div 
                          key={account.id}
                          onClick={() => setSelectedAccount(account)}
                          className={`p-3 rounded-xl border cursor-pointer transition-all ${
                            selectedAccount?.id === account.id 
                              ? 'border-purple-500 bg-purple-50' 
                              : 'hover:border-gray-300 hover:bg-muted/50'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium">{account.name}</p>
                              <p className="text-sm text-muted-foreground">{account.email}</p>
                            </div>
                            <Badge variant="outline">{account.role}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
              
              {/* Role Selection */}
              {forcePasswordType === 'role' && (
                <div className="space-y-2">
                  <Label>{t('selectRole')}</Label>
                  <Select value={selectedRole} onValueChange={setSelectedRole}>
                    <SelectTrigger><SelectValue placeholder={t('selectRole2')} /></SelectTrigger>
                    <SelectContent>
                      {availableRoles.map((role) => (
                        <SelectItem key={role.id} value={role.id}>
                          {isRTL ? role.name_ar : role.name_en}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              
              {/* All Users Warning */}
              {forcePasswordType === 'all' && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-6 w-6 text-red-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-red-800">{t('criticalWarning')}</p>
                      <p className="text-sm text-red-700 mt-1">
                        {t('allUsersWillBeLoggedOutAndForcedToChangePasswordUs')
                        }
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowForcePasswordDialog(false)}>{t.cancel}</Button>
              <Button 
                variant={forcePasswordType === 'all' ? 'destructive' : 'default'}
                className={forcePasswordType !== 'all' ? 'bg-purple-600 hover:bg-purple-700' : ''}
                onClick={handleForcePasswordChange} 
                disabled={
                  actionLoading || 
                  (forcePasswordType === 'user' && !selectedAccount) ||
                  (forcePasswordType === 'role' && !selectedRole)
                }
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <KeyRound className="h-4 w-4 me-2" />}
                {t.forcePasswordChange}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* AI Report Dialog */}
        <Dialog open={showAIReportDialog} onOpenChange={setShowAIReportDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="flex items-center gap-2"><Brain className="h-5 w-5 text-brand-navy" />{t.aiAnalysis}</DialogTitle><DialogDescription>{t('comprehensiveSecurityAnalysisUsingAi')}</DialogDescription></DialogHeader>
            <div className="py-4">
              <div className="p-4 bg-muted/30 rounded-xl text-center">
                <Brain className="h-16 w-16 mx-auto text-brand-navy/30 mb-4" />
                <p className="text-muted-foreground">{t('aiWillAnalyzeAllSecurityDataAndGenerateAComprehens')}</p>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowAIReportDialog(false)}>{t.cancel}</Button>
              <Button onClick={handleGenerateAIReport} disabled={generatingReport} className="bg-brand-navy">{generatingReport ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Zap className="h-4 w-4 me-2" />}{t.generateReport}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
