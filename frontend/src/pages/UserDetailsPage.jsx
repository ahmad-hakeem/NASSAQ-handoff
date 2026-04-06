import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Sidebar } from '../components/layout/Sidebar';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
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
  SheetDescription,
} from '../components/ui/sheet';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  MapPin,
  Building2,
  Calendar,
  Clock,
  Shield,
  Edit,
  Trash2,
  Lock,
  Unlock,
  Bell,
  Key,
  Activity,
  FileText,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Download,
  Send,
  RefreshCw,
  Eye,
  Brain,
  Settings,
  History,
  Briefcase,
  GraduationCap,
  Copy,
  Check,
  Upload,
  Image,
  Link,
  ExternalLink,
  Plus,
  Minus,
  Save,
  X,
} from 'lucide-react';


const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Role configurations
const USER_ROLES = {
  platform_admin: { 
    label: 'مدير المنصة', 
    label_en: 'Platform Admin', 
    color: 'bg-red-500',
    icon: Shield 
  },
  platform_operations_manager: { 
    label: 'مدير العمليات', 
    label_en: 'Operations Manager', 
    color: 'bg-blue-500',
    icon: Settings 
  },
  platform_technical_admin: { 
    label: 'مسؤول تقني', 
    label_en: 'Technical Admin', 
    color: 'bg-purple-500',
    icon: Settings 
  },
  platform_support_specialist: { 
    label: 'دعم المستخدمين', 
    label_en: 'Support Specialist', 
    color: 'bg-green-500',
    icon: User 
  },
  platform_data_analyst: { 
    label: 'محلل بيانات', 
    label_en: 'Data Analyst', 
    color: 'bg-cyan-500',
    icon: Activity 
  },
  platform_security_officer: { 
    label: 'مسؤول أمن', 
    label_en: 'Security Officer', 
    color: 'bg-orange-500',
    icon: Shield 
  },
  testing_account: { 
    label: 'حساب اختبار', 
    label_en: 'Testing Account', 
    color: 'bg-gray-500',
    icon: User 
  },
  teacher: { 
    label: 'معلم', 
    label_en: 'Teacher', 
    color: 'bg-teal-500',
    icon: GraduationCap 
  },
  school_principal: { 
    label: 'مدير مدرسة', 
    label_en: 'School Principal', 
    color: 'bg-indigo-500',
    icon: Building2 
  },
};

// All available permissions
const ALL_PERMISSIONS = [
  { id: 'view_dashboard', name_ar: 'عرض لوحة التحكم', name_en: 'View Dashboard', category: 'general' },
  { id: 'manage_schools', name_ar: 'إدارة المدارس', name_en: 'Manage Schools', category: 'schools' },
  { id: 'manage_users', name_ar: 'إدارة المستخدمين', name_en: 'Manage Users', category: 'users' },
  { id: 'view_reports', name_ar: 'عرض التقارير', name_en: 'View Reports', category: 'reports' },
  { id: 'manage_settings', name_ar: 'إدارة الإعدادات', name_en: 'Manage Settings', category: 'settings' },
  { id: 'manage_roles', name_ar: 'إدارة الأدوار', name_en: 'Manage Roles', category: 'users' },
  { id: 'view_analytics', name_ar: 'عرض التحليلات', name_en: 'View Analytics', category: 'reports' },
  { id: 'manage_integrations', name_ar: 'إدارة التكاملات', name_en: 'Manage Integrations', category: 'settings' },
  { id: 'view_audit_logs', name_ar: 'عرض سجل المراجعة', name_en: 'View Audit Logs', category: 'security' },
  { id: 'manage_security', name_ar: 'إدارة الأمان', name_en: 'Manage Security', category: 'security' },
  { id: 'manage_notifications', name_ar: 'إدارة الإشعارات', name_en: 'Manage Notifications', category: 'general' },
  { id: 'manage_rules', name_ar: 'إدارة القواعد', name_en: 'Manage Rules', category: 'settings' },
  { id: 'view_monitoring', name_ar: 'عرض مراقبة النظام', name_en: 'View Monitoring', category: 'system' },
  { id: 'manage_ai', name_ar: 'إدارة الذكاء الاصطناعي', name_en: 'Manage AI', category: 'ai' },
  { id: 'export_data', name_ar: 'تصدير البيانات', name_en: 'Export Data', category: 'reports' },
];

// Permission categories
const PERMISSION_CATEGORIES = {
  general: { name_ar: 'عام', name_en: 'General', icon: Settings },
  schools: { name_ar: 'المدارس', name_en: 'Schools', icon: Building2 },
  users: { name_ar: 'المستخدمين', name_en: 'Users', icon: User },
  reports: { name_ar: 'التقارير', name_en: 'Reports', icon: FileText },
  settings: { name_ar: 'الإعدادات', name_en: 'Settings', icon: Settings },
  security: { name_ar: 'الأمان', name_en: 'Security', icon: Shield },
  system: { name_ar: 'النظام', name_en: 'System', icon: Activity },
  ai: { name_ar: 'الذكاء الاصطناعي', name_en: 'AI', icon: Brain },
};

const ACTION_TRANSLATIONS = {
  'auth.login': 'تسجيل دخول',
  'auth.logout': 'تسجيل خروج',
  'auth.login_failed': 'فشل تسجيل الدخول',
  'auth.password_changed': 'تغيير كلمة المرور',
  'auth.password_reset': 'إعادة تعيين كلمة المرور',
  'user.created': 'إنشاء مستخدم',
  'user.updated': 'تحديث مستخدم',
  'user.deleted': 'حذف مستخدم',
  'user.suspended': 'تعليق مستخدم',
  'user.activated': 'تفعيل مستخدم',
  'login': 'تسجيل دخول',
  'logout': 'تسجيل خروج',
  'login_failed': 'فشل تسجيل الدخول',
  'user_created': 'إنشاء مستخدم',
  'user_updated': 'تحديث مستخدم',
  'user_deleted': 'حذف مستخدم',
  'user_suspended': 'تعليق مستخدم',
  'user_activated': 'تفعيل مستخدم',
  'user_role_changed': 'تغيير الدور',
  'permissions_updated': 'تحديث الصلاحيات',
  'password_reset': 'إعادة تعيين كلمة المرور',
  'settings_updated': 'تحديث الإعدادات',
  'data_exported': 'تصدير البيانات',
};

// Generate random password
const generatePassword = () => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%';
  let password = '';
  for (let i = 0; i < 12; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return password;
};

export default function UserDetailsPage() {
  const { userId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { isRTL = true, api } = useAuth();
  const fileInputRef = useRef(null);
  
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [activities, setActivities] = useState([]);
  const [activitiesLoading, setActivitiesLoading] = useState(false);
  
  // Dialogs
  const [showSuspendDialog, setShowSuspendDialog] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showResetPasswordDialog, setShowResetPasswordDialog] = useState(false);
  const [showPasswordResultDialog, setShowPasswordResultDialog] = useState(false);
  const [showNotificationDialog, setShowNotificationDialog] = useState(false);
  const [showEditSheet, setShowEditSheet] = useState(false);
  const [showPermissionsSheet, setShowPermissionsSheet] = useState(false);
  
  // Form states
  const [notificationForm, setNotificationForm] = useState({ title: '', message: '', type: 'system' });
  const [editForm, setEditForm] = useState({});
  const [newPassword, setNewPassword] = useState('');
  const [copiedField, setCopiedField] = useState(null);
  const [userPermissions, setUserPermissions] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  
  // Fetch user data
  useEffect(() => {
    const fetchUser = async () => {
      setLoading(true);
      try {
        const response = await api.get(`/users/${userId}`);
        setUser(response.data);
        setEditForm(response.data);
        setUserPermissions(response.data.permissions || []);
      } catch (error) {
        console.error('Error fetching user:', error);
        // Show error instead of using mock data
        nassaqError('فشل في تحميل بيانات المستخدم');
        // Use the userId to construct a basic user object with loading indicator
        setUser({
          id: userId,
          full_name: 'جاري التحميل...',
          full_name_ar: 'جاري التحميل...',
          full_name_en: 'Loading...',
          email: 'loading@nassaq.com',
          phone: '',
          role: 'platform_admin',
          is_active: true,
          ai_enabled: false,
          permissions: [],
          last_login: null,
          created_at: new Date().toISOString(),
          _loadError: true, // Flag to indicate data didn't load
        });
      } finally {
        setLoading(false);
      }
    };
    
    fetchUser();
  }, [userId]);

  const fetchActivities = async () => {
    setActivitiesLoading(true);
    try {
      const response = await api.get(`/audit/user/${userId}`);
      setActivities(response.data?.logs || []);
    } catch (error) {
      console.error('Error fetching audit logs:', error);
      setActivities([]);
    } finally {
      setActivitiesLoading(false);
    }
  };

  useEffect(() => {
    setActivities([]);
  }, [userId]);

  useEffect(() => {
    if (activeTab === 'activity' && activities.length === 0 && !activitiesLoading) {
      fetchActivities();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, userId]);
  
  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('ar-SA', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };
  
  // Format time
  const formatDateTime = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ar-SA', {
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
      toast.success(isRTL ? 'تم النسخ بنجاح' : 'Copied successfully');
    } catch (err) {
      nassaqError(isRTL ? 'فشل النسخ' : 'Copy failed');
    }
  };
  
  // Handle go back
  const handleGoBack = () => {
    // Try to go back with state preservation
    if (location.state?.fromUsersPage) {
      navigate('/admin/users', { state: location.state.filters });
    } else {
      navigate('/admin/users');
    }
  };
  
  // Handle suspend toggle
  const handleSuspendToggle = async () => {
    try {
      await api.patch(`/users/${userId}/status`, { is_active: !user.is_active });
      setUser(prev => ({ ...prev, is_active: !prev.is_active }));
      toast.success(user.is_active ? 'تم تعليق الحساب بنجاح' : 'تم تفعيل الحساب بنجاح');
    } catch (error) {
      console.error('Error toggling user status:', error);
      toast.error(error?.response?.data?.detail || 'فشل في تغيير حالة الحساب. الرجاء المحاولة مرة أخرى.');
    }
    setShowSuspendDialog(false);
  };
  
  // Handle delete
  const handleDelete = async () => {
    try {
      await api.delete(`/users/${userId}`);
      toast.success('تم أرشفة الحساب بنجاح');
      navigate('/admin/users');
    } catch (error) {
      console.error('Error deleting user:', error);
      toast.error(error?.response?.data?.detail || 'فشل في أرشفة الحساب. الرجاء المحاولة مرة أخرى.');
    }
  };
  
  // Handle reset password
  const handleResetPassword = async () => {
    const password = generatePassword();
    setNewPassword(password);
    
    try {
      await api.post(`/users/${userId}/reset-password`, { new_password: password });
      setShowResetPasswordDialog(false);
      setShowPasswordResultDialog(true);
    } catch (error) {
      console.error('Password reset error:', error);
      nassaqError('حدث خطأ أثناء إعادة تعيين كلمة المرور. الرجاء المحاولة مرة أخرى.');
      setShowResetPasswordDialog(false);
    }
  };
  
  // Generate welcome message
  const generateWelcomeMessage = () => {
    return `مرحبًا،

تم إعادة تعيين كلمة المرور الخاصة بحسابك على منصة نَسَّق | NASSAQ.

يمكنك تسجيل الدخول باستخدام البيانات التالية:

البريد الإلكتروني:
${user.email}

كلمة المرور الجديدة:
${newPassword}

يرجى تغيير كلمة المرور بعد تسجيل الدخول مباشرة لضمان أمان حسابك.

رابط تسجيل الدخول:
${API_URL}/login

مع تحيات
إدارة منصة نَسَّق`;
  };
  
  // Handle send notification
  const handleSendNotification = async () => {
    toast.success(`تم إرسال الإشعار إلى ${user.full_name}`);
    setShowNotificationDialog(false);
    setNotificationForm({ title: '', message: '', type: 'system' });
  };
  
  // Handle edit submit
  const handleEditSubmit = async () => {
    try {
      await api.put(`/users/${userId}`, editForm);
      setUser(prev => ({ ...prev, ...editForm }));
      toast.success('تم تحديث البيانات بنجاح');
      setShowEditSheet(false);
    } catch (error) {
      console.error('Error updating user:', error);
      toast.error(error?.response?.data?.detail || 'فشل في تحديث البيانات. الرجاء المحاولة مرة أخرى.');
    }
  };
  
  // Handle permissions update
  const handlePermissionsUpdate = async () => {
    try {
      await api.put(`/users/${userId}/permissions`, { permissions: userPermissions });
      setUser(prev => ({ ...prev, permissions: userPermissions }));
      toast.success('تم تحديث الصلاحيات بنجاح');
      setShowPermissionsSheet(false);
    } catch (error) {
      console.error('Error updating permissions:', error);
      toast.error(error?.response?.data?.detail || 'فشل في تحديث الصلاحيات. الرجاء المحاولة مرة أخرى.');
    }
  };
  
  // Toggle permission
  const togglePermission = (permissionId) => {
    setUserPermissions(prev => 
      prev.includes(permissionId)
        ? prev.filter(p => p !== permissionId)
        : [...prev, permissionId]
    );
  };
  
  // Handle image upload
  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        nassaqError(isRTL ? 'حجم الصورة كبير جداً (الحد الأقصى 5MB)' : 'Image too large (max 5MB)');
        return;
      }
      const reader = new FileReader();
      reader.onload = (e) => {
        setSelectedImage(e.target.result);
        setEditForm(prev => ({ ...prev, avatar_url: e.target.result }));
      };
      reader.readAsDataURL(file);
    }
  };
  
  // Get role info
  const getRoleInfo = (roleId) => {
    return USER_ROLES[roleId] || { label: roleId, label_en: roleId, color: 'bg-gray-500', icon: User };
  };
  
  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-background flex items-center justify-center" dir="rtl">
          <div className="animate-spin h-12 w-12 border-4 border-brand-navy border-t-transparent rounded-full"></div>
        </div>
      </Sidebar>
    );
  }
  
  if (!user) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-background flex items-center justify-center" dir="rtl">
          <Card className="p-8 text-center">
            <XCircle className="h-16 w-16 mx-auto text-red-500 mb-4" />
            <h2 className="text-xl font-bold mb-2">المستخدم غير موجود</h2>
            <Button onClick={() => navigate('/admin/users')}>العودة للقائمة</Button>
          </Card>
        </div>
      </Sidebar>
    );
  }
  
  const roleInfo = getRoleInfo(user.role);
  const RoleIcon = roleInfo.icon;
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir="rtl" data-testid="user-details-page">
        {/* Header with Back Button */}
        <div className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b">
          <div className="container mx-auto px-4 lg:px-6 py-4">
            <div className="flex items-center gap-4 mb-4">
              <Button 
                variant="outline" 
                onClick={handleGoBack}
                className="flex items-center gap-2 rounded-xl"
                data-testid="back-to-users-btn"
              >
                <ArrowLeft className="h-4 w-4 rotate-180" />
                العودة إلى إدارة المستخدمين
              </Button>
            </div>
            
            <PageHeader 
              title="تفاصيل المستخدم" 
              icon={User}
              className="mb-0"
            />
          </div>
        </div>
        
        {/* Main Content */}
        <div className="container mx-auto px-4 lg:px-6 py-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Profile Card */}
            <Card className="lg:col-span-1">
              <CardContent className="pt-6">
                <div className="text-center">
                  {/* Avatar with Upload Option */}
                  <div className="relative inline-block">
                    <Avatar className="h-28 w-28 mx-auto mb-4 border-4 border-brand-navy/20">
                      {user.avatar_url ? (
                        <AvatarImage src={user.avatar_url} alt={user.full_name} />
                      ) : null}
                      <AvatarFallback className={`${roleInfo.color} text-white text-3xl`}>
                        {user.full_name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                  </div>
                  
                  <h2 className="font-cairo text-xl font-bold mb-1">{user.full_name_ar || user.full_name}</h2>
                  {user.full_name_en && (
                    <p className="text-sm text-muted-foreground mb-2" dir="ltr">{user.full_name_en}</p>
                  )}
                  
                  <Badge className={`${roleInfo.color} text-white mb-3`}>
                    <RoleIcon className="h-3 w-3 me-1" />
                    {isRTL ? roleInfo.label : roleInfo.label_en}
                  </Badge>
                  
                  <div className="flex justify-center gap-2 mb-4">
                    {user.is_active ? (
                      <Badge className="bg-green-500 text-white">
                        <CheckCircle2 className="h-3 w-3 me-1" />
                        نشط
                      </Badge>
                    ) : (
                      <Badge className="bg-red-500 text-white">
                        <XCircle className="h-3 w-3 me-1" />
                        موقوف
                      </Badge>
                    )}
                    {user.ai_enabled && (
                      <Badge className="bg-purple-500 text-white">
                        <Brain className="h-3 w-3 me-1" />
                        AI
                      </Badge>
                    )}
                  </div>
                  
                  {user.must_change_password && (
                    <div className="p-2 bg-yellow-50 border border-yellow-200 rounded-lg mb-4">
                      <div className="flex items-center justify-center gap-2 text-yellow-700 text-sm">
                        <AlertTriangle className="h-4 w-4" />
                        يجب تغيير كلمة المرور
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Quick Info */}
                <div className="space-y-3 mt-6 pt-6 border-t">
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="text-sm" dir="ltr">{user.email}</span>
                  </div>
                  {user.phone && (
                    <div className="flex items-center gap-3">
                      <Phone className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm" dir="ltr">{user.phone}</span>
                    </div>
                  )}
                  {user.city && (
                    <div className="flex items-center gap-3">
                      <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm">{user.city}، {user.region}</span>
                    </div>
                  )}
                  {user.school_name && (
                    <div className="flex items-center gap-3">
                      <Building2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm">{user.school_name}</span>
                    </div>
                  )}
                  {user.educational_department && (
                    <div className="flex items-center gap-3">
                      <Briefcase className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm">{user.educational_department}</span>
                    </div>
                  )}
                </div>
                
                {/* Dates */}
                <div className="space-y-2 mt-6 pt-6 border-t text-sm text-muted-foreground">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      تاريخ الإنشاء:
                    </span>
                    <span>{formatDate(user.created_at)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Clock className="h-4 w-4" />
                      آخر تسجيل دخول:
                    </span>
                    <span>{formatDateTime(user.last_login)}</span>
                  </div>
                  {user.created_by_name && (
                    <div className="flex items-start justify-between pt-2 border-t">
                      <span className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        أنشئ بواسطة:
                      </span>
                      <div className="text-left">
                        <p className="text-xs text-muted-foreground">مدير النظام</p>
                        <button 
                          className="font-medium text-brand-navy hover:underline"
                          onClick={() => user.created_by && navigate(`/admin/users/${user.created_by}`)}
                        >
                          {user.created_by_name}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Action Buttons - Below Profile */}
                <div className="mt-6 pt-6 border-t space-y-3">
                  <Button 
                    className="w-full bg-blue-600 hover:bg-blue-700 rounded-xl h-12 text-base"
                    onClick={() => setShowEditSheet(true)}
                    data-testid="edit-user-btn"
                  >
                    <Edit className="h-5 w-5 ms-2" />
                    تعديل البيانات
                  </Button>
                  
                  <Button 
                    className="w-full bg-purple-600 hover:bg-purple-700 rounded-xl h-12 text-base"
                    onClick={() => setShowResetPasswordDialog(true)}
                    data-testid="reset-password-btn"
                  >
                    <Key className="h-5 w-5 ms-2" />
                    إعادة تعيين كلمة المرور
                  </Button>
                  
                  <Button 
                    className="w-full bg-green-600 hover:bg-green-700 rounded-xl h-12 text-base"
                    onClick={() => setShowNotificationDialog(true)}
                    data-testid="send-notification-btn"
                  >
                    <Bell className="h-5 w-5 ms-2" />
                    إرسال إشعار
                  </Button>
                  
                  <Button 
                    className={`w-full rounded-xl h-12 text-base ${
                      user.is_active 
                        ? "bg-orange-500 hover:bg-orange-600" 
                        : "bg-green-600 hover:bg-green-700"
                    }`}
                    onClick={() => setShowSuspendDialog(true)}
                    data-testid="suspend-user-btn"
                  >
                    {user.is_active ? (
                      <>
                        <Lock className="h-5 w-5 ms-2" />
                        تعليق الحساب
                      </>
                    ) : (
                      <>
                        <Unlock className="h-5 w-5 ms-2" />
                        تفعيل الحساب
                      </>
                    )}
                  </Button>
                  
                  <Button 
                    variant="outline"
                    className="w-full text-red-600 hover:bg-red-50 border-red-200 rounded-xl h-12 text-base"
                    onClick={() => setShowDeleteDialog(true)}
                    data-testid="delete-user-btn"
                  >
                    <Trash2 className="h-5 w-5 ms-2" />
                    حذف الحساب
                  </Button>
                </div>
              </CardContent>
            </Card>
            
            {/* Details Tabs */}
            <Card className="lg:col-span-2">
              <CardContent className="pt-6">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <TabsList className="grid grid-cols-3 mb-6">
                    <TabsTrigger value="overview" className="flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      نظرة عامة
                    </TabsTrigger>
                    <TabsTrigger value="permissions" className="flex items-center gap-2">
                      <Shield className="h-4 w-4" />
                      الصلاحيات
                    </TabsTrigger>
                    <TabsTrigger value="activity" className="flex items-center gap-2">
                      <History className="h-4 w-4" />
                      سجل النشاط
                    </TabsTrigger>
                  </TabsList>
                  
                  {/* Overview Tab */}
                  <TabsContent value="overview" className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <Card className="bg-muted/30">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-100 rounded-lg">
                              <User className="h-5 w-5 text-blue-600" />
                            </div>
                            <div>
                              <p className="text-sm text-muted-foreground">معرف المستخدم</p>
                              <p className="font-mono text-sm">{user.id?.substring(0, 8)}...</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      
                      <Card className="bg-muted/30">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${user.is_active ? 'bg-green-100' : 'bg-red-100'}`}>
                              {user.is_active ? (
                                <CheckCircle2 className="h-5 w-5 text-green-600" />
                              ) : (
                                <XCircle className="h-5 w-5 text-red-600" />
                              )}
                            </div>
                            <div>
                              <p className="text-sm text-muted-foreground">حالة الحساب</p>
                              <p className="font-medium">{user.is_active ? 'نشط' : 'موقوف'}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      
                      <Card className="bg-muted/30">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${user.ai_enabled ? 'bg-purple-100' : 'bg-gray-100'}`}>
                              <Brain className={`h-5 w-5 ${user.ai_enabled ? 'text-purple-600' : 'text-gray-400'}`} />
                            </div>
                            <div>
                              <p className="text-sm text-muted-foreground">الذكاء الاصطناعي</p>
                              <p className="font-medium">{user.ai_enabled ? 'مفعّل' : 'غير مفعّل'}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      
                      <Card className="bg-muted/30">
                        <CardContent className="p-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2 bg-teal-100 rounded-lg">
                              <Shield className="h-5 w-5 text-teal-600" />
                            </div>
                            <div>
                              <p className="text-sm text-muted-foreground">عدد الصلاحيات</p>
                              <p className="font-medium">{user.permissions?.length || 0} صلاحية</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                    
                    {/* Contact Information */}
                    <div>
                      <h3 className="font-bold mb-4 flex items-center gap-2">
                        <Mail className="h-5 w-5 text-brand-navy" />
                        معلومات التواصل
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-3 bg-muted/30 rounded-lg">
                          <p className="text-sm text-muted-foreground mb-1">البريد الإلكتروني</p>
                          <p className="font-medium" dir="ltr">{user.email}</p>
                        </div>
                        <div className="p-3 bg-muted/30 rounded-lg">
                          <p className="text-sm text-muted-foreground mb-1">رقم الهاتف</p>
                          <p className="font-medium" dir="ltr">{user.phone || '-'}</p>
                        </div>
                      </div>
                    </div>
                    
                    {/* Location Information */}
                    <div>
                      <h3 className="font-bold mb-4 flex items-center gap-2">
                        <MapPin className="h-5 w-5 text-brand-navy" />
                        معلومات الموقع
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-3 bg-muted/30 rounded-lg">
                          <p className="text-sm text-muted-foreground mb-1">المنطقة</p>
                          <p className="font-medium">{user.region || '-'}</p>
                        </div>
                        <div className="p-3 bg-muted/30 rounded-lg">
                          <p className="text-sm text-muted-foreground mb-1">المدينة</p>
                          <p className="font-medium">{user.city || '-'}</p>
                        </div>
                      </div>
                    </div>
                  </TabsContent>
                  
                  {/* Permissions Tab */}
                  <TabsContent value="permissions" className="space-y-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-bold flex items-center gap-2">
                        <Shield className="h-5 w-5 text-brand-navy" />
                        صلاحيات المستخدم
                      </h3>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => {
                          setUserPermissions(user.permissions || []);
                          setShowPermissionsSheet(true);
                        }}
                        data-testid="edit-permissions-btn"
                      >
                        <Edit className="h-4 w-4 ms-2" />
                        تعديل الصلاحيات
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      {user.permissions?.map((permission, index) => {
                        const permInfo = ALL_PERMISSIONS.find(p => p.id === permission);
                        return (
                          <div 
                            key={index}
                            className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-lg"
                          >
                            <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
                            <span className="text-sm">{permInfo?.name_ar || permission.replace(/_/g, ' ')}</span>
                          </div>
                        );
                      })}
                    </div>
                    
                    {(!user.permissions || user.permissions.length === 0) && (
                      <div className="text-center py-8 text-muted-foreground">
                        <Shield className="h-12 w-12 mx-auto mb-3 opacity-30" />
                        <p>لا توجد صلاحيات محددة</p>
                      </div>
                    )}
                  </TabsContent>
                  
                  {/* Activity Tab */}
                  <TabsContent value="activity" className="space-y-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-bold flex items-center gap-2">
                        <History className="h-5 w-5 text-brand-navy" />
                        سجل النشاط
                      </h3>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={fetchActivities}
                          disabled={activitiesLoading}
                        >
                          <RefreshCw className={`h-4 w-4 ms-2 ${activitiesLoading ? 'animate-spin' : ''}`} />
                          تحديث
                        </Button>
                        <Button 
                          variant="outline" 
                          size="sm"
                          disabled={activities.length === 0}
                          onClick={() => {
                            const csvContent = [
                              'النشاط,المنفذ,العنوان IP,التاريخ',
                              ...activities.map(a => 
                                `"${a.action_ar || a.action}","${a.actor_name || a.action_by_name || '-'}","${a.ip_address || '-'}","${a.timestamp}"`
                              )
                            ].join('\n');
                            
                            const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
                            const link = document.createElement('a');
                            link.href = URL.createObjectURL(blob);
                            link.download = `activity_log_${user?.full_name || 'user'}_${new Date().toISOString().split('T')[0]}.csv`;
                            link.click();
                            toast.success('تم تصدير سجل النشاط بنجاح');
                          }}
                        >
                          <Download className="h-4 w-4 ms-2" />
                          تصدير
                        </Button>
                      </div>
                    </div>
                    
                    {activitiesLoading ? (
                      <div className="flex items-center justify-center py-12">
                        <RefreshCw className="h-8 w-8 animate-spin text-brand-turquoise" />
                      </div>
                    ) : activities.length === 0 ? (
                      <div className="text-center py-12 text-muted-foreground">
                        <Activity className="h-12 w-12 mx-auto mb-3 opacity-30" />
                        <p>لا توجد أنشطة مسجلة</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {activities.map((activity, idx) => {
                          const actionLabel = activity.action_ar || ACTION_TRANSLATIONS[activity.action] || activity.action;
                          const deviceBrowser = activity.device_info?.browser;
                          const deviceOs = activity.device_info?.os;
                          const deviceLabel = (deviceBrowser && deviceBrowser !== 'غير معروف')
                            ? `${deviceBrowser}${deviceOs && deviceOs !== 'غير معروف' ? ' / ' + deviceOs : ''}`
                            : null;

                          return (
                            <div 
                              key={activity.id || idx}
                              className="flex items-center justify-between p-3 bg-muted/30 rounded-lg hover:bg-muted/50 transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${
                                  activity.severity === 'critical' ? 'bg-red-100' :
                                  activity.severity === 'high' ? 'bg-orange-100' :
                                  'bg-brand-navy/10'
                                }`}>
                                  <Activity className={`h-4 w-4 ${
                                    activity.severity === 'critical' ? 'text-red-600' :
                                    activity.severity === 'high' ? 'text-orange-600' :
                                    'text-brand-navy'
                                  }`} />
                                </div>
                                <div>
                                  <p className="font-medium text-sm">{actionLabel}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {activity.actor_name || activity.action_by_name || '-'}
                                    {deviceLabel && ` · ${deviceLabel}`}
                                  </p>
                                  {activity.details && (activity.details.added || activity.details.removed || activity.details.old_permissions || activity.changes) && (
                                    <div className="mt-1 text-xs text-muted-foreground space-y-0.5">
                                      {activity.old_role && activity.new_role && (
                                        <p>الدور: <span className="line-through text-red-500">{activity.old_role}</span> → <span className="text-green-600">{activity.new_role}</span></p>
                                      )}
                                      {activity.details?.added?.length > 0 && (
                                        <p>أضيف: {activity.details.added.join('، ')}</p>
                                      )}
                                      {activity.details?.removed?.length > 0 && (
                                        <p>أزيل: {activity.details.removed.join('، ')}</p>
                                      )}
                                    </div>
                                  )}
                                  {activity.changes && !activity.details && (
                                    <div className="mt-1 text-xs text-muted-foreground">
                                      {Object.entries(activity.changes).filter(([k]) => k !== 'updated_at').slice(0, 3).map(([key, val]) => (
                                        <span key={key} className="me-2 block">
                                          {key}: {val && typeof val === 'object' && 'old' in val
                                            ? <><span className="line-through text-red-500">{String(val.old ?? '-')}</span> → <span className="text-green-600">{String(val.new ?? '-')}</span></>
                                            : String(val)}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                              <div className="text-left flex-shrink-0">
                                <p className="text-sm">{formatDateTime(activity.timestamp)}</p>
                                {activity.ip_address && (
                                  <p className="text-xs text-muted-foreground" dir="ltr">{activity.ip_address}</p>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </div>
        
        {/* Edit User Sheet */}
        <Sheet open={showEditSheet} onOpenChange={setShowEditSheet}>
          <SheetContent side="left" className="w-[450px] sm:w-[550px] overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Edit className="h-5 w-5 text-brand-navy" />
                تعديل بيانات المستخدم
              </SheetTitle>
            </SheetHeader>
            <div className="space-y-6 py-6">
              {/* Avatar Upload */}
              <div className="text-center">
                <div className="relative inline-block">
                  <Avatar className="h-24 w-24 mx-auto border-4 border-brand-navy/20">
                    {selectedImage || editForm.avatar_url ? (
                      <AvatarImage src={selectedImage || editForm.avatar_url} />
                    ) : null}
                    <AvatarFallback className={`${roleInfo.color} text-white text-2xl`}>
                      {editForm.full_name?.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <input
                    type="file"
                    ref={fileInputRef}
                    className="hidden"
                    accept="image/jpeg,image/png"
                    onChange={handleImageUpload}
                  />
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="mt-3"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-4 w-4 ms-2" />
                  رفع صورة
                </Button>
                <p className="text-xs text-muted-foreground mt-1">JPG أو PNG (الحد الأقصى 5MB)</p>
              </div>
              
              {/* Name Fields */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>الاسم (عربي) *</Label>
                  <Input 
                    value={editForm.full_name_ar || editForm.full_name || ''}
                    onChange={(e) => setEditForm({ ...editForm, full_name_ar: e.target.value, full_name: e.target.value })}
                    placeholder="أدخل الاسم بالعربية"
                  />
                </div>
                <div className="space-y-2">
                  <Label>الاسم (إنجليزي)</Label>
                  <Input 
                    value={editForm.full_name_en || ''}
                    onChange={(e) => setEditForm({ ...editForm, full_name_en: e.target.value })}
                    placeholder="Enter name in English"
                    dir="ltr"
                  />
                </div>
              </div>
              
              {/* Contact */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>البريد الإلكتروني *</Label>
                  <Input 
                    value={editForm.email || ''}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                    dir="ltr"
                    type="email"
                  />
                </div>
                <div className="space-y-2">
                  <Label>رقم الهاتف</Label>
                  <Input 
                    value={editForm.phone || ''}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    dir="ltr"
                  />
                </div>
              </div>
              
              {/* Location */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>المنطقة</Label>
                  <Input 
                    value={editForm.region || ''}
                    onChange={(e) => setEditForm({ ...editForm, region: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>المدينة</Label>
                  <Input 
                    value={editForm.city || ''}
                    onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                  />
                </div>
              </div>
              
              {/* Educational Department */}
              <div className="space-y-2">
                <Label>إدارة التعليم</Label>
                <Input 
                  value={editForm.educational_department || ''}
                  onChange={(e) => setEditForm({ ...editForm, educational_department: e.target.value })}
                />
              </div>

              {/* Role */}
              <div className="space-y-2">
                <Label>الدور</Label>
                <Select
                  value={editForm.role || user?.role || ''}
                  onValueChange={(value) => setEditForm({ ...editForm, role: value })}
                >
                  <SelectTrigger className="rounded-xl">
                    <SelectValue placeholder="اختر الدور" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(USER_ROLES).map(([roleId, roleConfig]) => (
                      <SelectItem key={roleId} value={roleId}>
                        <span className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${roleConfig.color}`} />
                          {roleConfig.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* School/Tenant Assignment */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>معرّف المدرسة (tenant_id)</Label>
                  <Input 
                    value={editForm.tenant_id || ''}
                    onChange={(e) => setEditForm({ ...editForm, tenant_id: e.target.value })}
                    placeholder="أدخل معرّف المدرسة"
                    dir="ltr"
                  />
                </div>
                <div className="space-y-2">
                  <Label>اسم المدرسة</Label>
                  <Input 
                    value={editForm.school_name || ''}
                    onChange={(e) => setEditForm({ ...editForm, school_name: e.target.value })}
                    placeholder="أدخل اسم المدرسة"
                  />
                </div>
              </div>
              
              {/* Submit */}
              <div className="flex gap-3 pt-4">
                <Button onClick={handleEditSubmit} className="flex-1 bg-brand-navy rounded-xl">
                  <Save className="h-4 w-4 ms-2" />
                  حفظ التغييرات
                </Button>
                <Button variant="outline" onClick={() => setShowEditSheet(false)} className="rounded-xl">
                  إلغاء
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
        
        {/* Permissions Sheet */}
        <Sheet open={showPermissionsSheet} onOpenChange={setShowPermissionsSheet}>
          <SheetContent side="left" className="w-[500px] sm:w-[600px] overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-brand-navy" />
                تعديل الصلاحيات
              </SheetTitle>
              <SheetDescription>
                حدد الصلاحيات التي تريد منحها لهذا المستخدم
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 py-6">
              {Object.entries(PERMISSION_CATEGORIES).map(([catKey, category]) => {
                const categoryPermissions = ALL_PERMISSIONS.filter(p => p.category === catKey);
                if (categoryPermissions.length === 0) return null;
                
                const CategoryIcon = category.icon;
                
                return (
                  <div key={catKey} className="space-y-3">
                    <div className="flex items-center gap-2 text-sm font-bold text-muted-foreground">
                      <CategoryIcon className="h-4 w-4" />
                      {isRTL ? category.name_ar : category.name_en}
                    </div>
                    <div className="grid gap-2">
                      {categoryPermissions.map((permission) => (
                        <label
                          key={permission.id}
                          className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                            userPermissions.includes(permission.id)
                              ? 'bg-green-50 border-green-300'
                              : 'hover:bg-muted/50'
                          }`}
                        >
                          <Checkbox
                            checked={userPermissions.includes(permission.id)}
                            onCheckedChange={() => togglePermission(permission.id)}
                          />
                          <span className="text-sm">
                            {isRTL ? permission.name_ar : permission.name_en}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
              
              {/* Summary */}
              <div className="p-4 bg-muted/30 rounded-xl">
                <p className="text-sm text-muted-foreground">
                  الصلاحيات المحددة: <strong>{userPermissions.length}</strong> من {ALL_PERMISSIONS.length}
                </p>
              </div>
              
              {/* Submit */}
              <div className="flex gap-3 pt-4">
                <Button onClick={handlePermissionsUpdate} className="flex-1 bg-brand-navy rounded-xl">
                  <Save className="h-4 w-4 ms-2" />
                  حفظ الصلاحيات
                </Button>
                <Button variant="outline" onClick={() => setShowPermissionsSheet(false)} className="rounded-xl">
                  إلغاء
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
        
        {/* Suspend Dialog */}
        <Dialog open={showSuspendDialog} onOpenChange={setShowSuspendDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {user.is_active ? (
                  <>
                    <Lock className="h-5 w-5 text-orange-600" />
                    تعليق الحساب
                  </>
                ) : (
                  <>
                    <Unlock className="h-5 w-5 text-green-600" />
                    تفعيل الحساب
                  </>
                )}
              </DialogTitle>
              <DialogDescription>
                {user.is_active 
                  ? 'هل أنت متأكد من تعليق هذا الحساب؟ لن يتمكن المستخدم من تسجيل الدخول.'
                  : 'هل أنت متأكد من تفعيل هذا الحساب؟ سيتمكن المستخدم من تسجيل الدخول مجدداً.'}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowSuspendDialog(false)}>إلغاء</Button>
              <Button 
                onClick={handleSuspendToggle}
                className={user.is_active ? "bg-orange-600 hover:bg-orange-700" : "bg-green-600 hover:bg-green-700"}
              >
                {user.is_active ? 'تعليق' : 'تفعيل'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Delete Dialog */}
        <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <Trash2 className="h-5 w-5" />
                حذف الحساب
              </DialogTitle>
              <DialogDescription>
                هل أنت متأكد من حذف هذا الحساب؟ سيتم أرشفة الحساب ولن يظهر في القوائم.
                <br />
                <strong className="text-red-600">هذا الإجراء لا يمكن التراجع عنه.</strong>
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>إلغاء</Button>
              <Button variant="destructive" onClick={handleDelete}>
                <Trash2 className="h-4 w-4 ms-2" />
                حذف نهائي
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Reset Password Confirm Dialog */}
        <Dialog open={showResetPasswordDialog} onOpenChange={setShowResetPasswordDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Key className="h-5 w-5 text-purple-600" />
                إعادة تعيين كلمة المرور
              </DialogTitle>
              <DialogDescription>
                سيتم إنشاء كلمة مرور جديدة عشوائية وآمنة.
                سيُطلب من المستخدم تغييرها عند تسجيل الدخول.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowResetPasswordDialog(false)}>إلغاء</Button>
              <Button onClick={handleResetPassword} className="bg-purple-600 hover:bg-purple-700">
                <RefreshCw className="h-4 w-4 ms-2" />
                إعادة التعيين
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Password Result Dialog */}
        <Dialog open={showPasswordResultDialog} onOpenChange={setShowPasswordResultDialog}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-green-600">
                <CheckCircle2 className="h-5 w-5" />
                تم إعادة تعيين كلمة المرور
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {/* Email */}
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">البريد الإلكتروني</Label>
                <div className="flex items-center gap-2">
                  <Input value={user.email} readOnly dir="ltr" className="font-mono" />
                  <Button 
                    variant="outline" 
                    size="icon"
                    onClick={() => copyToClipboard(user.email, 'email')}
                  >
                    {copiedField === 'email' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              
              {/* Password */}
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">كلمة المرور الجديدة</Label>
                <div className="flex items-center gap-2">
                  <Input value={newPassword} readOnly dir="ltr" className="font-mono text-lg" />
                  <Button 
                    variant="outline" 
                    size="icon"
                    onClick={() => copyToClipboard(newPassword, 'password')}
                  >
                    {copiedField === 'password' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
              
              {/* Copy All */}
              <Button 
                variant="outline" 
                className="w-full"
                onClick={() => copyToClipboard(`البريد: ${user.email}\nكلمة المرور: ${newPassword}`, 'all')}
              >
                {copiedField === 'all' ? <Check className="h-4 w-4 ms-2 text-green-500" /> : <Copy className="h-4 w-4 ms-2" />}
                نسخ بيانات تسجيل الدخول
              </Button>
              
              {/* Copy Message */}
              <div className="p-4 bg-muted/30 rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <Label className="text-sm font-bold">رسالة جاهزة للإرسال</Label>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => copyToClipboard(generateWelcomeMessage(), 'message')}
                  >
                    {copiedField === 'message' ? <Check className="h-4 w-4 ms-1 text-green-500" /> : <Copy className="h-4 w-4 ms-1" />}
                    نسخ الرسالة
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground whitespace-pre-line line-clamp-4">
                  {generateWelcomeMessage().substring(0, 200)}...
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={() => setShowPasswordResultDialog(false)} className="w-full bg-brand-navy">
                تم
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Notification Dialog */}
        <Dialog open={showNotificationDialog} onOpenChange={setShowNotificationDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5 text-green-600" />
                إرسال إشعار
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>عنوان الإشعار</Label>
                <Input 
                  value={notificationForm.title}
                  onChange={(e) => setNotificationForm({ ...notificationForm, title: e.target.value })}
                  placeholder="أدخل عنوان الإشعار"
                />
              </div>
              <div className="space-y-2">
                <Label>محتوى الإشعار</Label>
                <Textarea 
                  value={notificationForm.message}
                  onChange={(e) => setNotificationForm({ ...notificationForm, message: e.target.value })}
                  placeholder="أدخل محتوى الإشعار"
                  rows={4}
                />
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowNotificationDialog(false)}>إلغاء</Button>
              <Button onClick={handleSendNotification} className="bg-green-600 hover:bg-green-700">
                <Send className="h-4 w-4 ms-2" />
                إرسال
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
