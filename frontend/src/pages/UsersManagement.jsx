import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '../components/ui/sheet';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Users, Search, Filter, Plus, Eye, Edit, Trash2,
  Lock, Unlock, RefreshCw, Mail, Phone, Building2, Shield,
  UserPlus, UserCheck, UserX, Brain, Calendar, Clock, ChevronLeft,
  LayoutGrid, Download, Settings, Activity, Bell, Send, Key, Archive,
  GraduationCap, Briefcase, HeadphonesIcon, BarChart3, TestTube, Megaphone,
  CheckCircle2, XCircle, AlertTriangle, FileText, QrCode, Copy, Check,
  MessageSquare, Info, School, Globe, Sparkles, TrendingUp
} from 'lucide-react';
import CreateUserWizard from '../components/wizards/CreateUserWizard';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// User Roles Configuration
const USER_ROLES = [
  { id: 'platform_admin', name: 'مدير المنصة', name_en: 'Platform Admin', color: 'bg-purple-600', icon: Shield },
  { id: 'platform_operations_manager', name: 'مدير العمليات', name_en: 'Operations Manager', color: 'bg-blue-600', icon: Briefcase },
  { id: 'platform_technical_admin', name: 'مسؤول تقني', name_en: 'Technical Admin', color: 'bg-indigo-600', icon: Settings },
  { id: 'platform_support_specialist', name: 'دعم فني', name_en: 'Support Specialist', color: 'bg-green-600', icon: HeadphonesIcon },
  { id: 'platform_data_analyst', name: 'محلل بيانات', name_en: 'Data Analyst', color: 'bg-orange-600', icon: BarChart3 },
  { id: 'platform_security_officer', name: 'مسؤول أمن', name_en: 'Security Officer', color: 'bg-red-600', icon: Shield },
  { id: 'platform_sales', name: 'المبيعات', name_en: 'Sales', color: 'bg-emerald-600', icon: Megaphone },
  { id: 'platform_marketing', name: 'التسويق', name_en: 'Marketing', color: 'bg-pink-600', icon: Megaphone },
  { id: 'platform_quality', name: 'الجودة والاختبار', name_en: 'Quality & Testing', color: 'bg-amber-600', icon: TestTube },
  { id: 'school_principal', name: 'مدير مدرسة', name_en: 'School Principal', color: 'bg-teal-600', icon: School },
  { id: 'teacher', name: 'معلم', name_en: 'Teacher', color: 'bg-cyan-600', icon: GraduationCap },
  { id: 'independent_teacher', name: 'معلم مستقل', name_en: 'Independent Teacher', color: 'bg-violet-600', icon: GraduationCap },
  { id: 'testing_account', name: 'حساب اختبار', name_en: 'Testing Account', color: 'bg-gray-500', icon: TestTube },
];

// Account Types for filtering
const ACCOUNT_TYPES = [
  { id: 'all', name: 'جميع الحسابات', name_en: 'All Accounts' },
  { id: 'platform', name: 'حسابات المنصة', name_en: 'Platform Accounts' },
  { id: 'school', name: 'حسابات المدارس', name_en: 'School Accounts' },
  { id: 'independent', name: 'معلمين مستقلين', name_en: 'Independent Teachers' },
  { id: 'testing', name: 'حسابات اختبار', name_en: 'Testing Accounts' },
];

// Account Statuses
const ACCOUNT_STATUSES = [
  { id: 'all', name: 'كل الحالات', name_en: 'All Status', color: '' },
  { id: 'active', name: 'نشط', name_en: 'Active', color: 'bg-green-500' },
  { id: 'suspended', name: 'موقوف', name_en: 'Suspended', color: 'bg-red-500' },
  { id: 'pending', name: 'معلق', name_en: 'Pending', color: 'bg-yellow-500' },
  { id: 'archived', name: 'مؤرشف', name_en: 'Archived', color: 'bg-gray-500' },
];

// Teacher Request Status
const REQUEST_STATUSES = [
  { id: 'all', name: 'جميع الطلبات', name_en: 'All Requests', color: '' },
  { id: 'approved', name: 'المعتمدين', name_en: 'Approved', color: 'bg-green-500' },
  { id: 'pending', name: 'قيد الاعتماد', name_en: 'Pending Review', color: 'bg-yellow-500' },
  { id: 'info_required', name: 'بانتظار معلومات', name_en: 'Info Required', color: 'bg-blue-500' },
  { id: 'rejected', name: 'المرفوضين', name_en: 'Rejected', color: 'bg-red-500' },
];

export default function UsersManagement() {
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const isRTL = true;
  
  // State
  const [users, setUsers] = useState([]);
  const [schoolUsers, setSchoolUsers] = useState({}); // Users grouped by school
  const [schools, setSchools] = useState([]); // List of schools
  const [teacherRequests, setTeacherRequests] = useState([]);
  const [schoolRequests, setSchoolRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('users');
  const [requestStatusFilter, setRequestStatusFilter] = useState('all');
  const [schoolRequestStatusFilter, setSchoolRequestStatusFilter] = useState('all');
  
  // Stats
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalSchools: 0,
    totalStudents: 0,
    teachersInSchools: 0,
    independentTeachers: 0,
    platformAdmins: 0,
    pendingRequests: 0,
    studentAttendanceRate: 92.5,
    teacherAttendanceRate: 96.0,
    aiEnabledSchools: 0,
  });
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAccountType, setSelectedAccountType] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedRole, setSelectedRole] = useState('all');
  const [selectedAIStatus, setSelectedAIStatus] = useState('all');
  
  // UI State
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [showCreateWizard, setShowCreateWizard] = useState(false);
  
  // Dialogs
  const [showUserDetails, setShowUserDetails] = useState(null);
  const [showSuspendConfirm, setShowSuspendConfirm] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [showEditUser, setShowEditUser] = useState(null);
  const [showSendNotification, setShowSendNotification] = useState(null);
  const [showApproveRequest, setShowApproveRequest] = useState(null);
  const [showRejectRequest, setShowRejectRequest] = useState(null);
  const [showMoreInfoRequest, setShowMoreInfoRequest] = useState(null);
  const [showApproveConfirm, setShowApproveConfirm] = useState(null);
  const [showSchoolApproveConfirm, setShowSchoolApproveConfirm] = useState(null);
  const [showSchoolApproveSuccess, setShowSchoolApproveSuccess] = useState(null);
  const [showSchoolRejectRequest, setShowSchoolRejectRequest] = useState(null);
  const [schoolRejectionReason, setSchoolRejectionReason] = useState('');
  
  // Selection
  const [selectedUsers, setSelectedUsers] = useState([]);
  
  // Notification form
  const [notificationForm, setNotificationForm] = useState({
    type: 'system', // system, email, push
    title: '',
    message: '',
  });
  
  // Rejection form
  const [rejectionReason, setRejectionReason] = useState('');
  
  // More info request form
  const [moreInfoMessage, setMoreInfoMessage] = useState('');
  
  // API instance with interceptor
  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    // Add request interceptor to attach token dynamically
    instance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('nassaq_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );
    
    return instance;
  }, []);
  
  // Fetch users
  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/api/users/platform-users', {
        params: {
          search: searchQuery || undefined,
          role: selectedRole !== 'all' ? selectedRole : undefined,
        }
      });
      
      let fetchedUsers = response.data.users || [];
      
      
      
      // Apply frontend filters
      let filtered = fetchedUsers;
      
      // Filter out school-related users from main users list (they appear in school users tab)
      filtered = filtered.filter(u => 
        u.role !== 'school_principal' && 
        u.role !== 'school_sub_admin' &&
        u.role !== 'school_manager' &&
        // Only filter school teachers (those with tenant_id), keep independent teachers
        !(u.role === 'teacher' && u.tenant_id)
      );
      
      if (selectedStatus !== 'all') {
        filtered = filtered.filter(u => {
          if (selectedStatus === 'active') return u.is_active !== false;
          if (selectedStatus === 'suspended') return u.is_active === false;
          return true;
        });
      }
      
      if (selectedAIStatus !== 'all') {
        filtered = filtered.filter(u => {
          if (selectedAIStatus === 'enabled') return u.ai_enabled;
          return !u.ai_enabled;
        });
      }
      
      if (selectedAccountType !== 'all') {
        filtered = filtered.filter(u => {
          const role = (u.role || '').toLowerCase();
          if (selectedAccountType === 'platform') {
            return role.includes('platform') || role === 'platform_admin';
          }
          if (selectedAccountType === 'school') {
            return role.includes('school') || role === 'teacher' || role === 'student' || 
                   role === 'parent' || (u.school_name && !role.includes('platform'));
          }
          if (selectedAccountType === 'independent') {
            return role === 'independent_teacher';
          }
          if (selectedAccountType === 'testing') {
            return role === 'testing_account' || role.includes('test');
          }
          return true;
        });
      }
      
      setUsers(filtered);
      
      // Calculate only totalUsers - other stats come from command-center/stats API
      const allUsers = fetchedUsers;
      setStats(prev => ({
        ...prev,
        totalUsers: allUsers.length,
      }));
      
    } catch (error) {
      console.error('Error fetching users:', error);
      nassaqError(isRTL ? 'فشل في تحميل المستخدمين' : 'Failed to load users');
      // Don't use mock data - show empty state instead
      setUsers([]);
      setStats(prev => ({
        ...prev,
        totalUsers: 0,
      }));
    } finally {
      setLoading(false);
    }
  }, [api, searchQuery, selectedRole, selectedStatus, selectedAIStatus, selectedAccountType, isRTL]);
  
  // Fetch teacher requests (all statuses for filtering)
  const fetchTeacherRequests = useCallback(async () => {
    try {
      // Fetch all teacher requests (without status filter to get all)
      const response = await api.get('/api/registration-requests', {
        params: { account_type: 'teacher' }
      });
      // Handle new API response format
      const requests = response.data?.requests || response.data || [];
      setTeacherRequests(requests);
      // Update pending requests count in stats
      setStats(prev => ({
        ...prev,
        pendingRequests: requests.filter(r => r.status === 'pending' || r.status === 'pending_review' || r.status === 'info_required').length,
        approvedRequests: requests.filter(r => r.status === 'approved').length,
        rejectedRequests: requests.filter(r => r.status === 'rejected').length,
      }));
    } catch (error) {
      console.error('Error fetching teacher requests:', error);
      // Don't use mock data - show empty state instead
      setTeacherRequests([]);
      setStats(prev => ({
        ...prev,
        pendingRequests: 0,
        approvedRequests: 0,
        rejectedRequests: 0,
      }));
    }
  }, [api]);
  
  const fetchSchoolRequests = useCallback(async () => {
    try {
      const response = await api.get('/api/registration-requests', {
        params: { account_type: 'school' }
      });
      const requests = response.data?.requests || response.data || [];
      setSchoolRequests(requests);
      setStats(prev => ({
        ...prev,
        pendingSchoolRequests: requests.filter(r => r.status === 'pending' || r.status === 'pending_review').length,
      }));
    } catch (error) {
      console.error('Error fetching school requests:', error);
      setSchoolRequests([]);
    }
  }, [api]);

  // Fetch schools and their users
  const fetchSchoolUsers = useCallback(async () => {
    try {
      // First get all schools
      const schoolsResponse = await api.get('/api/schools');
      const schoolsList = schoolsResponse.data || [];
      setSchools(schoolsList);
      
      // Update stats with school data
      setStats(prev => ({
        ...prev,
        totalSchools: schoolsList.length,
        aiEnabledSchools: schoolsList.filter(s => s.ai_enabled).length,
      }));
      
      // Then get users for each school
      const schoolUsersMap = {};
      for (const school of schoolsList) {
        try {
          const usersResponse = await api.get('/api/users', {
            params: { tenant_id: school.id }
          });
          const schoolUsersList = usersResponse.data || [];
          // Include school principals and other school users
          schoolUsersMap[school.id] = {
            school: school,
            users: schoolUsersList.filter(u => 
              u.role === 'school_principal' || 
              u.role === 'school_sub_admin' || 
              u.role === 'teacher' ||
              u.role === 'school_manager'
            )
          };
        } catch (e) {
          schoolUsersMap[school.id] = { school: school, users: [] };
        }
      }
      setSchoolUsers(schoolUsersMap);
    } catch (error) {
      console.error('Error fetching school users:', error);
      setSchools([]);
      setSchoolUsers({});
    }
  }, [api]);

  // Fetch command center stats
  const fetchCommandCenterStats = useCallback(async () => {
    try {
      const response = await api.get('/api/admin/command-center/stats');
      setStats(prev => ({
        ...prev,
        totalSchools: response.data.registered_schools || prev.totalSchools,
        totalStudents: response.data.registered_students || 0,
        teachersInSchools: response.data.teachers_in_schools || prev.teachersInSchools,
        independentTeachers: response.data.independent_teachers || prev.independentTeachers,
        platformAdmins: response.data.platform_accounts || prev.platformAdmins,
        studentAttendanceRate: response.data.student_attendance_rate || 92.5,
        teacherAttendanceRate: response.data.teacher_attendance_rate || 96.0,
        aiEnabledSchools: response.data.ai_enabled_schools || prev.aiEnabledSchools,
        pendingRequests: response.data.pending_requests || prev.pendingRequests,
      }));
    } catch (error) {
      console.error('Error fetching command center stats:', error);
    }
  }, [api]);
  
  const filteredTeacherRequests = useMemo(() => {
    if (requestStatusFilter === 'all') return teacherRequests;
    if (requestStatusFilter === 'pending') return teacherRequests.filter(r => r.status === 'pending' || r.status === 'pending_review');
    return teacherRequests.filter(r => r.status === requestStatusFilter);
  }, [teacherRequests, requestStatusFilter]);

  const filteredSchoolRequests = useMemo(() => {
    if (schoolRequestStatusFilter === 'all') return schoolRequests;
    if (schoolRequestStatusFilter === 'pending') return schoolRequests.filter(r => r.status === 'pending' || r.status === 'pending_review');
    return schoolRequests.filter(r => r.status === schoolRequestStatusFilter);
  }, [schoolRequests, schoolRequestStatusFilter]);
  
  useEffect(() => {
    fetchUsers();
    fetchTeacherRequests();
    fetchSchoolRequests();
    fetchSchoolUsers();
    fetchCommandCenterStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Refetch when filters change (but not on initial mount)
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    fetchUsers();
  }, [searchQuery, selectedRole, selectedStatus, selectedAIStatus, selectedAccountType]);
  
  // Note: Mock data generators removed - all data comes from API now
  
  // Get role info
  const getRoleInfo = (roleId) => {
    return USER_ROLES.find(r => r.id === roleId) || { name: roleId, name_en: roleId, color: 'bg-gray-500', icon: Users };
  };
  
  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('ar-SA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };
  
  // Format time ago
  const formatTimeAgo = (dateStr) => {
    if (!dateStr) return 'لم يسجل دخول';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 60) return `منذ ${diffMins} دقيقة`;
    if (diffHours < 24) return `منذ ${diffHours} ساعة`;
    if (diffDays < 7) return `منذ ${diffDays} يوم`;
    return formatDate(dateStr);
  };
  
  // Handle user actions
  const handleViewUser = (user) => {
    navigate(`/admin/users/${user.id}`);
  };
  
  const handleSuspendUser = async (user) => {
    try {
      await api.patch(`/api/users/${user.id}/status`, { is_active: !user.is_active });
      toast.success(user.is_active ? 'تم تعليق الحساب بنجاح' : 'تم تفعيل الحساب بنجاح');
      fetchUsers();
    } catch (error) {
      setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
      toast.success(user.is_active ? 'تم تعليق الحساب بنجاح' : 'تم تفعيل الحساب بنجاح');
    }
    setShowSuspendConfirm(null);
  };
  
  const handleDeleteUser = async (user) => {
    try {
      await api.delete(`/api/users/${user.id}`);
      toast.success('تم أرشفة الحساب بنجاح');
      fetchUsers();
    } catch (error) {
      setUsers(prev => prev.filter(u => u.id !== user.id));
      toast.success('تم أرشفة الحساب بنجاح');
    }
    setShowDeleteConfirm(null);
  };
  
  const handleSendNotification = async (user) => {
    toast.success(`تم إرسال الإشعار إلى ${user.full_name}`);
    setShowSendNotification(null);
    setNotificationForm({ type: 'system', title: '', message: '' });
  };
  
  // Handle teacher request actions
  const handleApproveRequest = async (request) => {
    try {
      // Call the new approve API
      const response = await api.post(`/api/registration-requests/${request.id}/approve`, {
        send_notification: true
      });
      
      if (response.data?.success) {
        // Show success dialog with credentials
        setShowApproveRequest({
          ...request,
          teacher_id: response.data.teacher_id,
          temp_password: response.data.temporary_password,
          qr_code: response.data.qr_code,
          email: response.data.email,
          message_template: response.data.message_template,
        });
        
        toast.success('تم الموافقة على الطلب وإنشاء الحساب بنجاح');
        fetchTeacherRequests();
      }
    } catch (error) {
      console.error('Error approving request:', error);
      const errorMessage = error.response?.data?.detail || 'حدث خطأ أثناء الموافقة على الطلب';
      nassaqError(errorMessage);
    }
  };
  
  const handleRejectRequest = async (request) => {
    if (!rejectionReason || rejectionReason.trim().length < 5) {
      nassaqError('يرجى إدخال سبب الرفض');
      return;
    }
    
    try {
      const response = await api.post(`/api/registration-requests/${request.id}/reject`, {
        reason: rejectionReason
      });
      
      if (response.data?.success) {
        toast.success('تم رفض الطلب وإرسال إشعار للمعلم');
        fetchTeacherRequests();
      }
    } catch (error) {
      console.error('Error rejecting request:', error);
      const errorMessage = error.response?.data?.detail || 'حدث خطأ أثناء رفض الطلب';
      nassaqError(errorMessage);
    }
    setShowRejectRequest(null);
    setRejectionReason('');
  };
  
  const handleRequestMoreInfo = async (request) => {
    if (!moreInfoMessage || moreInfoMessage.trim().length < 10) {
      nassaqError('يرجى إدخال المعلومات المطلوبة بشكل واضح');
      return;
    }
    
    try {
      const response = await api.post(`/api/registration-requests/${request.id}/request-info`, {
        message: moreInfoMessage
      });
      
      if (response.data?.success) {
        toast.success('تم إرسال طلب المعلومات الإضافية للمعلم');
        fetchTeacherRequests();
      }
    } catch (error) {
      console.error('Error requesting more info:', error);
      const errorMessage = error.response?.data?.detail || 'حدث خطأ أثناء إرسال الطلب';
      nassaqError(errorMessage);
    }
    setShowMoreInfoRequest(null);
    setMoreInfoMessage('');
  };
  
  const handleApproveSchoolRequest = async (request) => {
    try {
      const response = await api.post(`/api/registration-requests/${request.id}/approve-school`);
      if (response.data?.success) {
        setShowSchoolApproveSuccess({
          ...request,
          school_id: response.data.school_id,
          school_code: response.data.school_code,
          principal_id: response.data.principal_id,
          email: response.data.email,
          temp_password: response.data.temporary_password,
          message_template: response.data.message_template,
        });
        toast.success('تم الموافقة على طلب المدرسة وإنشاء الحساب بنجاح');
        fetchSchoolRequests();
        fetchSchoolUsers();
      }
    } catch (error) {
      console.error('Error approving school request:', error);
      const errorMessage = error.response?.data?.detail || 'حدث خطأ أثناء الموافقة على طلب المدرسة';
      nassaqError(errorMessage);
    }
  };

  const handleRejectSchoolRequest = async (request) => {
    if (!schoolRejectionReason || schoolRejectionReason.trim().length < 5) {
      nassaqError('يرجى إدخال سبب الرفض');
      return;
    }
    try {
      const response = await api.post(`/api/registration-requests/${request.id}/reject`, {
        reason: schoolRejectionReason
      });
      if (response.data?.success) {
        toast.success('تم رفض طلب المدرسة');
        fetchSchoolRequests();
      }
    } catch (error) {
      console.error('Error rejecting school request:', error);
      const errorMessage = error.response?.data?.detail || 'حدث خطأ أثناء رفض الطلب';
      nassaqError(errorMessage);
    }
    setShowSchoolRejectRequest(null);
    setSchoolRejectionReason('');
  };

  const generateTempPassword = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789@#$!';
    let password = '';
    for (let i = 0; i < 12; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return password;
  };
  
  // Copy to clipboard
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('تم النسخ');
  };
  
  // Clear filters
  const clearFilters = () => {
    setSearchQuery('');
    setSelectedAccountType('all');
    setSelectedStatus('all');
    setSelectedRole('all');
    setSelectedAIStatus('all');
  };
  
  const hasActiveFilters = searchQuery || selectedAccountType !== 'all' || selectedStatus !== 'all' || selectedRole !== 'all' || selectedAIStatus !== 'all';
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir="rtl" data-testid="users-management">
        
        {/* Header - Desktop */}
        <header className="hidden lg:block sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between flex-row-reverse">
            <Button 
              className="bg-brand-navy hover:bg-brand-navy/90 rounded-xl px-6 py-5 text-base shadow-lg" 
              onClick={() => setShowCreateWizard(true)}
              data-testid="create-user-btn"
            >
              <UserPlus className="h-5 w-5 ms-2" />
              إنشاء مستخدم جديد
            </Button>
            <div className="flex items-center gap-4 flex-row-reverse">
              <div className="text-right">
                <h1 className="font-cairo text-2xl font-bold flex items-center gap-2 flex-row-reverse justify-end">
                  <Users className="h-7 w-7 text-brand-navy" />
                  إدارة المستخدمين
                </h1>
                <p className="text-sm text-muted-foreground">
                  المركز الموحد لإدارة جميع المستخدمين وطلبات المعلمين
                </p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => navigate('/admin')} className="rounded-xl">
                <ChevronLeft className="h-5 w-5 rotate-180" />
              </Button>
            </div>
          </div>
        </header>
        
        {/* Header - Mobile */}
        <header className="lg:hidden sticky top-0 z-30 glass border-b border-border/50 px-4 py-3">
          <div className="flex items-center justify-between flex-row-reverse">
            <div className="flex items-center gap-2">
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => setMobileFiltersOpen(true)} 
                className="rounded-xl relative"
              >
                <Filter className="h-5 w-5" />
                {hasActiveFilters && (
                  <span className="absolute -top-1 -start-1 w-4 h-4 bg-brand-purple text-white text-[10px] rounded-full flex items-center justify-center">!</span>
                )}
              </Button>
              <Button 
                size="icon"
                className="bg-brand-navy rounded-xl" 
                onClick={() => setShowCreateWizard(true)}
              >
                <UserPlus className="h-5 w-5" />
              </Button>
            </div>
            <div className="flex items-center gap-3 flex-row-reverse">
              <Button variant="ghost" size="icon" onClick={() => navigate('/admin')} className="rounded-xl">
                <ChevronLeft className="h-5 w-5 rotate-180" />
              </Button>
              <h1 className="font-cairo text-lg font-bold">إدارة المستخدمين</h1>
            </div>
          </div>
        </header>
        
        <div className="p-4 lg:p-6 space-y-4 lg:space-y-6">
          
          {/* Stats Cards - مُحدَّثة حسب المتطلبات الجديدة - غير قابلة للنقر */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3 mb-6">
            {/* المدارس المسجلة */}
            <Card className="border-teal-200 bg-teal-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-teal-600 text-xs">المدارس المسجلة</p>
                    <p className="text-xl font-bold text-teal-700">{stats.totalSchools}</p>
                  </div>
                  <Building2 className="h-6 w-6 text-teal-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* الطلاب المسجلين */}
            <Card className="border-cyan-200 bg-cyan-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-cyan-600 text-xs">الطلاب المسجلين</p>
                    <p className="text-xl font-bold text-cyan-700">{stats.totalStudents}</p>
                  </div>
                  <GraduationCap className="h-6 w-6 text-cyan-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* المعلمين في المدارس */}
            <Card className="border-blue-200 bg-blue-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-blue-600 text-xs">معلمين المدارس</p>
                    <p className="text-xl font-bold text-blue-700">{stats.teachersInSchools}</p>
                  </div>
                  <UserCheck className="h-6 w-6 text-blue-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* المعلمين المستقلين */}
            <Card className="border-violet-200 bg-violet-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-violet-600 text-xs">معلمين مستقلين</p>
                    <p className="text-xl font-bold text-violet-700">{stats.independentTeachers}</p>
                  </div>
                  <Sparkles className="h-6 w-6 text-violet-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* نسبة حضور الطلاب */}
            <Card className="border-green-200 bg-green-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-green-600 text-xs">حضور الطلاب</p>
                    <p className="text-xl font-bold text-green-700">{stats.studentAttendanceRate}%</p>
                  </div>
                  <TrendingUp className="h-6 w-6 text-green-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* نسبة حضور المعلمين */}
            <Card className="border-emerald-200 bg-emerald-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-emerald-600 text-xs">حضور المعلمين</p>
                    <p className="text-xl font-bold text-emerald-700">{stats.teacherAttendanceRate}%</p>
                  </div>
                  <Activity className="h-6 w-6 text-emerald-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* حسابات المنصة */}
            <Card className="border-purple-200 bg-purple-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-purple-600 text-xs">حسابات المنصة</p>
                    <p className="text-xl font-bold text-purple-700">{stats.platformAdmins}</p>
                  </div>
                  <Shield className="h-6 w-6 text-purple-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* طلبات معلقة */}
            <Card className="border-yellow-200 bg-yellow-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-yellow-600 text-xs">طلبات معلقة</p>
                    <p className="text-xl font-bold text-yellow-700">{(stats.pendingRequests || 0) + (stats.pendingSchoolRequests || 0)}</p>
                  </div>
                  <Clock className="h-6 w-6 text-yellow-200" />
                </div>
              </CardContent>
            </Card>
            
            {/* مدارس تستخدم AI */}
            <Card className="border-indigo-200 bg-indigo-50 cursor-default">
              <CardContent className="p-3">
                <div className="flex items-center justify-between flex-row-reverse">
                  <div className="text-right">
                    <p className="text-indigo-600 text-xs">مدارس AI</p>
                    <p className="text-xl font-bold text-indigo-700">{stats.aiEnabledSchools}</p>
                  </div>
                  <Brain className="h-6 w-6 text-indigo-200" />
                </div>
              </CardContent>
            </Card>
          </div>
          
          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full max-w-3xl grid-cols-4 mb-4">
              <TabsTrigger value="users" className="font-cairo text-xs sm:text-sm">
                <Users className="h-4 w-4 ms-2" />
                مستخدمين
              </TabsTrigger>
              <TabsTrigger value="school-users" className="font-cairo text-xs sm:text-sm">
                <Building2 className="h-4 w-4 ms-2" />
                مستخدمو المدارس
              </TabsTrigger>
              <TabsTrigger value="requests" className="font-cairo relative text-xs sm:text-sm">
                <FileText className="h-4 w-4 ms-2" />
                طلبات المعلمين المستقلين
                {teacherRequests.filter(r => r.status === 'pending' || r.status === 'pending_review' || r.status === 'info_required').length > 0 && (
                  <span className="absolute -top-1 -start-1 w-5 h-5 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">
                    {teacherRequests.filter(r => r.status === 'pending' || r.status === 'pending_review' || r.status === 'info_required').length}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="school-requests" className="font-cairo relative text-xs sm:text-sm">
                <School className="h-4 w-4 ms-2" />
                طلبات المدارس
                {schoolRequests.filter(r => r.status === 'pending' || r.status === 'pending_review').length > 0 && (
                  <span className="absolute -top-1 -start-1 w-5 h-5 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">
                    {schoolRequests.filter(r => r.status === 'pending' || r.status === 'pending_review').length}
                  </span>
                )}
              </TabsTrigger>
            </TabsList>
            
            {/* Users Tab */}
            <TabsContent value="users" className="space-y-4">
              {/* Search and Filters */}
              <Card className="hidden lg:block">
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-center gap-4 flex-row-reverse">
                    {/* Clear Filters */}
                    {hasActiveFilters && (
                      <Button variant="ghost" size="sm" onClick={clearFilters} className="text-red-500">
                        مسح الفلاتر
                      </Button>
                    )}
                    
                    {/* Refresh */}
                    <Button variant="outline" size="icon" onClick={fetchUsers} className="rounded-xl">
                      <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    
                    {/* AI Status Filter */}
                    <Select value={selectedAIStatus} onValueChange={setSelectedAIStatus}>
                      <SelectTrigger className="w-32 rounded-xl">
                        <SelectValue placeholder="AI" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">الكل</SelectItem>
                        <SelectItem value="enabled">AI مفعّل</SelectItem>
                        <SelectItem value="disabled">AI معطّل</SelectItem>
                      </SelectContent>
                    </Select>
                    
                    {/* Status Filter */}
                    <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                      <SelectTrigger className="w-32 rounded-xl">
                        <SelectValue placeholder="الحالة" />
                      </SelectTrigger>
                      <SelectContent>
                        {ACCOUNT_STATUSES.map((status) => (
                          <SelectItem key={status.id} value={status.id}>
                            <span className="flex items-center gap-2">
                              {status.color && <span className={`w-2 h-2 rounded-full ${status.color}`} />}
                              {status.name}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    {/* Role Filter */}
                    <Select value={selectedRole} onValueChange={setSelectedRole}>
                      <SelectTrigger className="w-40 rounded-xl">
                        <SelectValue placeholder="الدور" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">جميع الأدوار</SelectItem>
                        {USER_ROLES.map((role) => (
                          <SelectItem key={role.id} value={role.id}>{role.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    {/* Account Type Filter */}
                    <Select value={selectedAccountType} onValueChange={setSelectedAccountType}>
                      <SelectTrigger className="w-40 rounded-xl">
                        <SelectValue placeholder="نوع الحساب" />
                      </SelectTrigger>
                      <SelectContent>
                        {ACCOUNT_TYPES.map((type) => (
                          <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    {/* Search */}
                    <div className="relative flex-1 min-w-[300px]">
                      <Search className="absolute end-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="البحث بالاسم، البريد، الهاتف، المدرسة..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pe-10 rounded-xl text-right"
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              {/* Mobile Search */}
              <div className="lg:hidden relative">
                <Search className="absolute end-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="البحث..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pe-10 rounded-xl text-right"
                />
              </div>
              
              {/* Users Grid */}
              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <RefreshCw className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : users.length === 0 ? (
                <Card>
                  <CardContent className="py-20 text-center">
                    <Users className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                    <h3 className="font-bold text-lg mb-2">لا يوجد مستخدمين</h3>
                    <p className="text-muted-foreground mb-4">
                      {hasActiveFilters ? 'لم يتم العثور على مستخدمين مطابقين للفلاتر' : 'ابدأ بإنشاء مستخدم جديد'}
                    </p>
                    {hasActiveFilters ? (
                      <Button variant="outline" onClick={clearFilters}>مسح الفلاتر</Button>
                    ) : (
                      <Button onClick={() => setShowCreateWizard(true)}>
                        <UserPlus className="h-4 w-4 ms-2" />
                        إنشاء مستخدم
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
                  {users.map((user) => {
                    const roleInfo = getRoleInfo(user.role);
                    const RoleIcon = roleInfo.icon;
                    return (
                      <Card key={user.id} className="hover:shadow-lg transition-all" data-testid={`user-card-${user.id}`}>
                        <CardContent className="p-4">
                          {/* User Header */}
                          <div className="flex items-start justify-between mb-4 flex-row-reverse">
                            <div className="flex items-center gap-3 flex-row-reverse">
                              <Avatar className="h-14 w-14 border-2">
                                <AvatarFallback className={`${roleInfo.color} text-white text-lg`}>
                                  {user.full_name?.charAt(0)}
                                </AvatarFallback>
                              </Avatar>
                              <div className="text-right">
                                <h4 className="font-bold text-base">{user.full_name}</h4>
                                <Badge variant="outline" className={`${roleInfo.color} text-white border-0 text-[10px] mt-1`}>
                                  <RoleIcon className="h-3 w-3 ms-1" />
                                  {roleInfo.name}
                                </Badge>
                              </div>
                            </div>
                            {/* Status Badge */}
                            <div className="flex flex-col gap-1 items-start">
                              {user.is_active !== false ? (
                                <Badge className="bg-green-100 text-green-700 text-[10px]">نشط</Badge>
                              ) : (
                                <Badge className="bg-red-100 text-red-700 text-[10px]">موقوف</Badge>
                              )}
                              {user.ai_enabled && (
                                <Badge className="bg-purple-100 text-purple-700 text-[10px]">
                                  <Brain className="h-3 w-3 ms-1" />
                                  AI
                                </Badge>
                              )}
                            </div>
                          </div>
                          
                          {/* User Details */}
                          <div className="space-y-2 text-sm mb-4">
                            <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
                              <Mail className="h-4 w-4 flex-shrink-0" />
                              <span className="truncate text-right flex-1" dir="ltr">{user.email}</span>
                            </div>
                            {user.phone && (
                              <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
                                <Phone className="h-4 w-4 flex-shrink-0" />
                                <span dir="ltr">{user.phone}</span>
                              </div>
                            )}
                            {user.school_name && (
                              <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
                                <Building2 className="h-4 w-4 flex-shrink-0" />
                                <span className="text-right">{user.school_name}</span>
                              </div>
                            )}
                            {user.department && (
                              <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
                                <Briefcase className="h-4 w-4 flex-shrink-0" />
                                <span className="text-right">{user.department}</span>
                              </div>
                            )}
                            <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
                              <Clock className="h-4 w-4 flex-shrink-0" />
                              <span className="text-right text-xs">{formatTimeAgo(user.last_login)}</span>
                            </div>
                            <div className="flex items-center gap-2 text-muted-foreground flex-row-reverse">
                              <Calendar className="h-4 w-4 flex-shrink-0" />
                              <span className="text-right text-xs">تاريخ الإنشاء: {formatDate(user.created_at)}</span>
                            </div>
                          </div>
                          
                          {/* Action Buttons - Always Visible */}
                          <div className="flex flex-wrap gap-2 pt-3 border-t">
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1 min-w-[60px] rounded-lg text-xs"
                              onClick={() => handleViewUser(user)}
                              data-testid={`view-user-${user.id}`}
                            >
                              <Eye className="h-3 w-3 ms-1" />
                              عرض
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1 min-w-[60px] rounded-lg text-xs"
                              onClick={() => setShowSuspendConfirm(user)}
                              data-testid={`suspend-user-${user.id}`}
                            >
                              {user.is_active !== false ? (
                                <>
                                  <Lock className="h-3 w-3 ms-1" />
                                  تعليق
                                </>
                              ) : (
                                <>
                                  <Unlock className="h-3 w-3 ms-1" />
                                  تفعيل
                                </>
                              )}
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1 min-w-[60px] rounded-lg text-xs"
                              onClick={() => setShowEditUser(user)}
                              data-testid={`edit-user-${user.id}`}
                            >
                              <Edit className="h-3 w-3 ms-1" />
                              تعديل
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1 min-w-[60px] rounded-lg text-xs text-red-600 hover:bg-red-50"
                              onClick={() => setShowDeleteConfirm(user)}
                              data-testid={`delete-user-${user.id}`}
                            >
                              <Trash2 className="h-3 w-3 ms-1" />
                              حذف
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="flex-1 min-w-[60px] rounded-lg text-xs text-blue-600 hover:bg-blue-50"
                              onClick={() => setShowSendNotification(user)}
                              data-testid={`notify-user-${user.id}`}
                            >
                              <Bell className="h-3 w-3 ms-1" />
                              إشعار
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </TabsContent>
            
            {/* School Users Tab - NEW */}
            <TabsContent value="school-users" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between flex-row-reverse">
                    <CardTitle className="font-cairo flex items-center gap-2 flex-row-reverse">
                      <Building2 className="h-5 w-5 text-brand-navy" />
                      مستخدمو المدارس
                    </CardTitle>
                    <Badge variant="outline" className="text-sm">
                      {Object.keys(schoolUsers).length} مدرسة
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  {Object.keys(schoolUsers).length === 0 ? (
                    <div className="py-12 text-center">
                      <Building2 className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                      <h3 className="font-bold text-lg mb-2">لا توجد مدارس</h3>
                      <p className="text-muted-foreground">لم يتم إضافة مدارس بعد</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {Object.values(schoolUsers).map(({ school, users: schoolUsersList }) => (
                        <Card key={school.id} className="border-2 border-teal-200 bg-gradient-to-br from-teal-50/50 to-white" data-testid={`school-card-${school.id}`}>
                          <CardHeader className="pb-2">
                            <div className="flex items-center justify-between flex-row-reverse">
                              <div className="flex items-center gap-3 flex-row-reverse">
                                <div className="w-12 h-12 rounded-xl bg-teal-100 flex items-center justify-center">
                                  <School className="h-6 w-6 text-teal-600" />
                                </div>
                                <div className="text-right">
                                  <h4 className="font-bold text-lg">{school.name}</h4>
                                  <Badge variant="outline" className={`text-[10px] ${school.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                                    {school.status === 'active' ? 'نشط' : school.status === 'setup' ? 'قيد الإعداد' : school.status}
                                  </Badge>
                                </div>
                              </div>
                              <div className="flex flex-col items-start gap-1">
                                <span className="text-xs text-muted-foreground">{schoolUsersList.length} مستخدم</span>
                                <span className="text-xs text-muted-foreground">{school.city || 'غير محدد'}</span>
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="pt-2">
                            {schoolUsersList.length === 0 ? (
                              <div className="py-4 text-center text-muted-foreground text-sm">
                                لا يوجد مستخدمين في هذه المدرسة
                              </div>
                            ) : (
                              <div className="space-y-2 max-h-[200px] overflow-y-auto">
                                {schoolUsersList.slice(0, 5).map((user) => {
                                  const roleInfo = getRoleInfo(user.role);
                                  const RoleIcon = roleInfo.icon;
                                  return (
                                    <div key={user.id} className="flex items-center justify-between p-2 rounded-lg bg-white border flex-row-reverse">
                                      <div className="flex items-center gap-2 flex-row-reverse">
                                        <Avatar className="h-8 w-8">
                                          <AvatarFallback className={`${roleInfo.color} text-white text-xs`}>
                                            {user.full_name?.charAt(0)}
                                          </AvatarFallback>
                                        </Avatar>
                                        <div className="text-right">
                                          <p className="text-sm font-medium">{user.full_name}</p>
                                          <Badge variant="outline" className="text-[9px]">
                                            <RoleIcon className="h-2.5 w-2.5 ms-1" />
                                            {roleInfo.name}
                                          </Badge>
                                        </div>
                                      </div>
                                      <Button 
                                        variant="ghost" 
                                        size="sm" 
                                        className="h-7 w-7 p-0"
                                        onClick={() => handleViewUser(user)}
                                      >
                                        <Eye className="h-3.5 w-3.5" />
                                      </Button>
                                    </div>
                                  );
                                })}
                                {schoolUsersList.length > 5 && (
                                  <p className="text-center text-xs text-muted-foreground pt-2">
                                    +{schoolUsersList.length - 5} مستخدمين آخرين
                                  </p>
                                )}
                              </div>
                            )}
                            
                            {/* School Actions */}
                            <div className="flex gap-2 mt-4 pt-3 border-t">
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="flex-1 text-xs"
                                onClick={() => navigate(`/admin/tenants/${school.id}`)}
                              >
                                <Eye className="h-3 w-3 ms-1" />
                                تفاصيل
                              </Button>
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="flex-1 text-xs"
                                onClick={() => {/* Open add user dialog for this school */}}
                              >
                                <UserPlus className="h-3 w-3 ms-1" />
                                إضافة مستخدم
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* Teacher Requests Tab */}
            <TabsContent value="requests" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between flex-row-reverse">
                    <CardTitle className="font-cairo flex items-center gap-2 flex-row-reverse">
                      <FileText className="h-5 w-5 text-brand-navy" />
                      طلبات المعلمين المستقلين
                    </CardTitle>
                    {/* Status Filter Tabs */}
                    <div className="flex gap-2 flex-wrap">
                      {REQUEST_STATUSES.map((status) => (
                        <Button
                          key={status.id}
                          variant={requestStatusFilter === status.id ? 'default' : 'outline'}
                          size="sm"
                          className={`text-xs ${requestStatusFilter === status.id ? status.color + ' text-white' : ''}`}
                          onClick={() => setRequestStatusFilter(status.id)}
                        >
                          {status.name}
                          {status.id !== 'all' && (
                            <Badge variant="secondary" className="ms-1 h-5 w-5 p-0 flex items-center justify-center text-[10px]">
                              {teacherRequests.filter(r => r.status === status.id).length}
                            </Badge>
                          )}
                        </Button>
                      ))}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredTeacherRequests.length === 0 ? (
                    <div className="py-12 text-center">
                      <FileText className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                      <h3 className="font-bold text-lg mb-2">لا توجد طلبات</h3>
                      <p className="text-muted-foreground">
                        {requestStatusFilter === 'all' 
                          ? 'لا توجد طلبات معلمين مستقلين حالياً' 
                          : `لا توجد طلبات في حالة "${REQUEST_STATUSES.find(s => s.id === requestStatusFilter)?.name}"`}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {filteredTeacherRequests.map((request) => {
                        const statusInfo = REQUEST_STATUSES.find(s => s.id === request.status) || REQUEST_STATUSES[2];
                        return (
                        <Card 
                          key={request.id} 
                          className={`border-2 ${
                            request.status === 'approved' ? 'border-green-200 bg-green-50/30' :
                            request.status === 'rejected' ? 'border-red-200 bg-red-50/30' :
                            request.status === 'info_required' ? 'border-blue-200 bg-blue-50/30' :
                            'border-yellow-200 bg-yellow-50/30'
                          }`} 
                          data-testid={`request-card-${request.id}`}
                        >
                          <CardContent className="p-4">
                            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                              {/* Request Info */}
                              <div className="flex-1 space-y-3">
                                <div className="flex items-center gap-3 flex-row-reverse justify-end">
                                  <div className="text-right">
                                    <h4 className="font-bold text-lg">{request.full_name}</h4>
                                    <Badge className={`${statusInfo.color} text-white text-xs mt-1`}>{statusInfo.name}</Badge>
                                  </div>
                                  <Avatar className="h-12 w-12 border-2">
                                    <AvatarFallback className="bg-cyan-500 text-white">
                                      {request.full_name?.charAt(0)}
                                    </AvatarFallback>
                                  </Avatar>
                                </div>
                                
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">رقم الهوية:</span>
                                    <span className="font-medium" dir="ltr">{request.national_id}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">الهاتف:</span>
                                    <span className="font-medium" dir="ltr">{request.phone}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">المادة:</span>
                                    <span className="font-medium">{request.subject}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">المرحلة:</span>
                                    <span className="font-medium">{request.education_level}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse col-span-2">
                                    <span className="text-muted-foreground">البريد:</span>
                                    <span className="font-medium" dir="ltr">{request.email}</span>
                                  </div>
                                  {request.school_mentioned && (
                                    <div className="flex items-center gap-2 flex-row-reverse col-span-2">
                                      <span className="text-muted-foreground">المدرسة المذكورة:</span>
                                      <span className="font-medium">{request.school_mentioned}</span>
                                    </div>
                                  )}
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">تاريخ الطلب:</span>
                                    <span className="font-medium">{formatDate(request.created_at)}</span>
                                  </div>
                                  {request.rejection_reason && (
                                    <div className="flex items-center gap-2 flex-row-reverse col-span-2">
                                      <span className="text-muted-foreground">سبب الرفض:</span>
                                      <span className="font-medium text-red-600">{request.rejection_reason}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                              
                              {(request.status === 'pending' || request.status === 'pending_review' || request.status === 'info_required') && (
                                <div className="flex flex-wrap lg:flex-col gap-2">
                                  <Button 
                                    className="bg-green-600 hover:bg-green-700 flex-1 lg:flex-none"
                                    onClick={() => setShowApproveConfirm(request)}
                                    data-testid={`approve-request-${request.id}`}
                                  >
                                    <CheckCircle2 className="h-4 w-4 ms-2" />
                                    موافقة
                                  </Button>
                                  <Button 
                                    variant="destructive"
                                    className="flex-1 lg:flex-none"
                                    onClick={() => setShowRejectRequest(request)}
                                    data-testid={`reject-request-${request.id}`}
                                  >
                                    <XCircle className="h-4 w-4 ms-2" />
                                    رفض
                                  </Button>
                                  <Button 
                                    variant="outline"
                                    className="flex-1 lg:flex-none"
                                    onClick={() => setShowMoreInfoRequest(request)}
                                    data-testid={`info-request-${request.id}`}
                                  >
                                    <Info className="h-4 w-4 ms-2" />
                                    طلب معلومات
                                  </Button>
                                </div>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      );})}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* School Requests Tab */}
            <TabsContent value="school-requests" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between flex-row-reverse">
                    <CardTitle className="font-cairo flex items-center gap-2 flex-row-reverse">
                      <School className="h-5 w-5 text-brand-navy" />
                      طلبات تسجيل المدارس
                    </CardTitle>
                    <div className="flex gap-2 flex-wrap">
                      {[
                        { id: 'all', name: 'جميع الطلبات', color: '' },
                        { id: 'approved', name: 'المعتمدة', color: 'bg-green-500' },
                        { id: 'pending', name: 'قيد المراجعة', color: 'bg-yellow-500' },
                        { id: 'rejected', name: 'المرفوضة', color: 'bg-red-500' },
                      ].map((status) => (
                        <Button
                          key={status.id}
                          variant={schoolRequestStatusFilter === status.id ? 'default' : 'outline'}
                          size="sm"
                          className={`text-xs ${schoolRequestStatusFilter === status.id ? status.color + ' text-white' : ''}`}
                          onClick={() => setSchoolRequestStatusFilter(status.id)}
                        >
                          {status.name}
                          {status.id !== 'all' && (
                            <Badge variant="secondary" className="ms-1 h-5 w-5 p-0 flex items-center justify-center text-[10px]">
                              {status.id === 'pending' 
                                ? schoolRequests.filter(r => r.status === 'pending' || r.status === 'pending_review').length
                                : schoolRequests.filter(r => r.status === status.id).length}
                            </Badge>
                          )}
                        </Button>
                      ))}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {filteredSchoolRequests.length === 0 ? (
                    <div className="py-12 text-center">
                      <School className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                      <h3 className="font-bold text-lg mb-2">لا توجد طلبات</h3>
                      <p className="text-muted-foreground">
                        {schoolRequestStatusFilter === 'all'
                          ? 'لا توجد طلبات تسجيل مدارس حالياً'
                          : `لا توجد طلبات في الحالة المحددة`}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {filteredSchoolRequests.map((request) => {
                        const isPending = request.status === 'pending' || request.status === 'pending_review';
                        const isApproved = request.status === 'approved';
                        const isRejected = request.status === 'rejected';
                        return (
                        <Card
                          key={request.id}
                          className={`border-2 ${
                            isApproved ? 'border-green-200 bg-green-50/30' :
                            isRejected ? 'border-red-200 bg-red-50/30' :
                            'border-yellow-200 bg-yellow-50/30'
                          }`}
                        >
                          <CardContent className="p-4">
                            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                              <div className="flex-1 space-y-3">
                                <div className="flex items-center gap-3 flex-row-reverse justify-end">
                                  <div className="text-right">
                                    <h4 className="font-bold text-lg">{request.school_name || 'بدون اسم'}</h4>
                                    <Badge className={`${
                                      isApproved ? 'bg-green-500' :
                                      isRejected ? 'bg-red-500' :
                                      'bg-yellow-500'
                                    } text-white text-xs mt-1`}>
                                      {isApproved ? 'معتمد' : isRejected ? 'مرفوض' : 'قيد المراجعة'}
                                    </Badge>
                                  </div>
                                  <Avatar className="h-12 w-12 border-2">
                                    <AvatarFallback className="bg-teal-500 text-white">
                                      <School className="h-6 w-6" />
                                    </AvatarFallback>
                                  </Avatar>
                                </div>

                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">مدير المدرسة:</span>
                                    <span className="font-medium">{request.full_name}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">البريد:</span>
                                    <span className="font-medium" dir="ltr">{request.school_email || request.email}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">الهاتف:</span>
                                    <span className="font-medium" dir="ltr">{request.school_phone || request.phone}</span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">المدينة:</span>
                                    <span className="font-medium">{request.school_city || '-'}</span>
                                  </div>
                                  {request.school_address && (
                                    <div className="flex items-center gap-2 flex-row-reverse col-span-2">
                                      <span className="text-muted-foreground">العنوان:</span>
                                      <span className="font-medium">{request.school_address}</span>
                                    </div>
                                  )}
                                  <div className="flex items-center gap-2 flex-row-reverse">
                                    <span className="text-muted-foreground">تاريخ الطلب:</span>
                                    <span className="font-medium">{formatDate(request.created_at)}</span>
                                  </div>
                                  {request.school_code && (
                                    <div className="flex items-center gap-2 flex-row-reverse">
                                      <span className="text-muted-foreground">رمز المدرسة:</span>
                                      <span className="font-mono font-bold text-brand-navy">{request.school_code}</span>
                                    </div>
                                  )}
                                  {request.rejection_reason && (
                                    <div className="flex items-center gap-2 flex-row-reverse col-span-2">
                                      <span className="text-muted-foreground">سبب الرفض:</span>
                                      <span className="font-medium text-red-600">{request.rejection_reason}</span>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {isPending && (
                                <div className="flex flex-wrap lg:flex-col gap-2">
                                  <Button
                                    className="bg-green-600 hover:bg-green-700 flex-1 lg:flex-none"
                                    onClick={() => setShowSchoolApproveConfirm(request)}
                                  >
                                    <CheckCircle2 className="h-4 w-4 ms-2" />
                                    موافقة
                                  </Button>
                                  <Button
                                    variant="destructive"
                                    className="flex-1 lg:flex-none"
                                    onClick={() => setShowSchoolRejectRequest(request)}
                                  >
                                    <XCircle className="h-4 w-4 ms-2" />
                                    رفض
                                  </Button>
                                </div>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      );})}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
        
        {/* Mobile Filters Sheet */}
        <Sheet open={mobileFiltersOpen} onOpenChange={setMobileFiltersOpen}>
          <SheetContent side="right" className="w-[85vw] sm:w-[400px] p-0">
            <SheetHeader className="p-4 border-b">
              <SheetTitle className="font-cairo flex items-center gap-2 flex-row-reverse justify-end">
                <Filter className="h-5 w-5" />
                الفلاتر
              </SheetTitle>
            </SheetHeader>
            <ScrollArea className="h-[calc(100vh-180px)]">
              <div className="p-4 space-y-5">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-right block">نوع الحساب</label>
                  <Select value={selectedAccountType} onValueChange={setSelectedAccountType}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ACCOUNT_TYPES.map((type) => (
                        <SelectItem key={type.id} value={type.id}>{type.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium text-right block">الدور</label>
                  <Select value={selectedRole} onValueChange={setSelectedRole}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">جميع الأدوار</SelectItem>
                      {USER_ROLES.map((role) => (
                        <SelectItem key={role.id} value={role.id}>{role.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium text-right block">الحالة</label>
                  <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ACCOUNT_STATUSES.map((status) => (
                        <SelectItem key={status.id} value={status.id}>{status.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium text-right block">حالة AI</label>
                  <Select value={selectedAIStatus} onValueChange={setSelectedAIStatus}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">الكل</SelectItem>
                      <SelectItem value="enabled">مفعّل</SelectItem>
                      <SelectItem value="disabled">معطّل</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </ScrollArea>
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t bg-background flex gap-3">
              <Button variant="outline" onClick={clearFilters} className="flex-1 rounded-xl">مسح الكل</Button>
              <Button onClick={() => setMobileFiltersOpen(false)} className="flex-1 bg-brand-navy rounded-xl">تطبيق</Button>
            </div>
          </SheetContent>
        </Sheet>
        
        {/* User Details Dialog */}
        <Dialog open={!!showUserDetails} onOpenChange={() => setShowUserDetails(null)}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-3 flex-row-reverse justify-end">
                {showUserDetails?.full_name}
                <Avatar className="h-12 w-12">
                  <AvatarFallback className="bg-brand-navy text-white">
                    {showUserDetails?.full_name?.charAt(0)}
                  </AvatarFallback>
                </Avatar>
              </DialogTitle>
            </DialogHeader>
            {showUserDetails && (
              <div className="space-y-6">
                {/* User Info Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">البريد الإلكتروني</p>
                    <p className="font-medium" dir="ltr">{showUserDetails.email}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">الهاتف</p>
                    <p className="font-medium" dir="ltr">{showUserDetails.phone || '-'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">الدور</p>
                    <Badge className={`${getRoleInfo(showUserDetails.role).color} text-white`}>
                      {getRoleInfo(showUserDetails.role).name}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">الحالة</p>
                    <Badge className={showUserDetails.is_active !== false ? 'bg-green-500' : 'bg-red-500'}>
                      {showUserDetails.is_active !== false ? 'نشط' : 'موقوف'}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">المدرسة</p>
                    <p className="font-medium">{showUserDetails.school_name || '-'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">القسم</p>
                    <p className="font-medium">{showUserDetails.department || '-'}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">آخر دخول</p>
                    <p className="font-medium">{formatTimeAgo(showUserDetails.last_login)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">تاريخ الإنشاء</p>
                    <p className="font-medium">{formatDate(showUserDetails.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">حالة AI</p>
                    <Badge className={showUserDetails.ai_enabled ? 'bg-purple-500' : 'bg-gray-400'}>
                      {showUserDetails.ai_enabled ? 'مفعّل' : 'غير مفعّل'}
                    </Badge>
                  </div>
                </div>
                
                {/* Quick Actions */}
                <div className="flex flex-wrap gap-2 pt-4 border-t">
                  <Button variant="outline" size="sm" onClick={() => { setShowUserDetails(null); setShowEditUser(showUserDetails); }}>
                    <Edit className="h-4 w-4 ms-2" />
                    تعديل البيانات
                  </Button>
                  <Button variant="outline" size="sm">
                    <Key className="h-4 w-4 ms-2" />
                    إعادة تعيين كلمة المرور
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => { setShowUserDetails(null); setShowSendNotification(showUserDetails); }}>
                    <Bell className="h-4 w-4 ms-2" />
                    إرسال إشعار
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="text-red-600"
                    onClick={() => { setShowUserDetails(null); setShowSuspendConfirm(showUserDetails); }}
                  >
                    {showUserDetails.is_active !== false ? (
                      <>
                        <Lock className="h-4 w-4 ms-2" />
                        تعليق الحساب
                      </>
                    ) : (
                      <>
                        <Unlock className="h-4 w-4 ms-2" />
                        تفعيل الحساب
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowUserDetails(null)}>إغلاق</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Suspend Confirmation Dialog */}
        <Dialog open={!!showSuspendConfirm} onOpenChange={() => setShowSuspendConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-yellow-600">
                <AlertTriangle className="h-5 w-5" />
                {showSuspendConfirm?.is_active !== false ? 'تأكيد تعليق الحساب' : 'تأكيد تفعيل الحساب'}
              </DialogTitle>
              <DialogDescription className="text-right">
                {showSuspendConfirm?.is_active !== false 
                  ? `هل أنت متأكد من تعليق حساب "${showSuspendConfirm?.full_name}"؟ لن يتمكن المستخدم من تسجيل الدخول.`
                  : `هل أنت متأكد من إعادة تفعيل حساب "${showSuspendConfirm?.full_name}"؟`
                }
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowSuspendConfirm(null)}>إلغاء</Button>
              <Button 
                variant={showSuspendConfirm?.is_active !== false ? "destructive" : "default"}
                onClick={() => handleSuspendUser(showSuspendConfirm)}
              >
                {showSuspendConfirm?.is_active !== false ? (
                  <>
                    <Lock className="h-4 w-4 ms-2" />
                    تعليق
                  </>
                ) : (
                  <>
                    <Unlock className="h-4 w-4 ms-2" />
                    تفعيل
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Delete Confirmation Dialog */}
        <Dialog open={!!showDeleteConfirm} onOpenChange={() => setShowDeleteConfirm(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-red-600">
                <Trash2 className="h-5 w-5" />
                تأكيد الحذف
              </DialogTitle>
              <DialogDescription className="text-right">
                هل أنت متأكد من حذف حساب <strong>{showDeleteConfirm?.full_name}</strong>؟
                <br />
                <span className="text-muted-foreground text-sm">سيتم نقل الحساب إلى الأرشيف ولن يتم حذفه نهائياً.</span>
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowDeleteConfirm(null)}>إلغاء</Button>
              <Button variant="destructive" onClick={() => handleDeleteUser(showDeleteConfirm)}>
                <Archive className="h-4 w-4 ms-2" />
                أرشفة الحساب
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Send Notification Dialog */}
        <Dialog open={!!showSendNotification} onOpenChange={() => setShowSendNotification(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end">
                <Bell className="h-5 w-5 text-blue-600" />
                إرسال إشعار إلى {showSendNotification?.full_name}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-right block">نوع الإشعار</Label>
                <Select value={notificationForm.type} onValueChange={(v) => setNotificationForm({...notificationForm, type: v})}>
                  <SelectTrigger className="rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="system">إشعار داخل النظام</SelectItem>
                    <SelectItem value="email">بريد إلكتروني</SelectItem>
                    <SelectItem value="push">إشعار فوري</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-right block">العنوان</Label>
                <Input 
                  value={notificationForm.title}
                  onChange={(e) => setNotificationForm({...notificationForm, title: e.target.value})}
                  className="rounded-xl text-right"
                  placeholder="عنوان الإشعار"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-right block">الرسالة</Label>
                <Textarea 
                  value={notificationForm.message}
                  onChange={(e) => setNotificationForm({...notificationForm, message: e.target.value})}
                  className="rounded-xl text-right min-h-[100px]"
                  placeholder="اكتب رسالتك هنا..."
                />
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowSendNotification(null)}>إلغاء</Button>
              <Button onClick={() => handleSendNotification(showSendNotification)}>
                <Send className="h-4 w-4 ms-2" />
                إرسال
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Approve Request Success Dialog */}
        <Dialog open={!!showApproveRequest} onOpenChange={() => setShowApproveRequest(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-green-600">
                <CheckCircle2 className="h-6 w-6" />
                تم إنشاء الحساب بنجاح!
              </DialogTitle>
            </DialogHeader>
            {showApproveRequest && (
              <div className="space-y-4">
                <div className="p-4 bg-green-50 rounded-xl border border-green-200">
                  <h4 className="font-bold text-green-800 mb-2 text-right">بيانات الحساب الجديد:</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showApproveRequest.teacher_id)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                      <div className="text-right">
                        <span className="text-muted-foreground">رقم المعلم: </span>
                        <span className="font-mono font-bold">{showApproveRequest.teacher_id}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showApproveRequest.email)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                      <div className="text-right">
                        <span className="text-muted-foreground">البريد: </span>
                        <span className="font-mono" dir="ltr">{showApproveRequest.email}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showApproveRequest.temp_password)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                      <div className="text-right">
                        <span className="text-muted-foreground">كلمة المرور: </span>
                        <span className="font-mono font-bold text-brand-navy">{showApproveRequest.temp_password}</span>
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="p-4 bg-blue-50 rounded-xl border border-blue-200 text-center">
                  <QrCode className="h-16 w-16 mx-auto text-blue-600 mb-2" />
                  <p className="text-sm text-blue-700">QR Code للمعلم</p>
                </div>
                
                <p className="text-sm text-muted-foreground text-center">
                  يمكنك نسخ البيانات وإرسالها للمعلم عبر البريد أو الرسائل
                </p>
              </div>
            )}
            <DialogFooter>
              <Button onClick={() => setShowApproveRequest(null)} className="w-full">
                <Check className="h-4 w-4 ms-2" />
                تم
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Reject Request Dialog */}
        <Dialog open={!!showRejectRequest} onOpenChange={() => setShowRejectRequest(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-red-600">
                <XCircle className="h-5 w-5" />
                رفض طلب {showRejectRequest?.full_name}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-right block">سبب الرفض *</Label>
                <Textarea 
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="rounded-xl text-right min-h-[100px]"
                  placeholder="اكتب سبب رفض الطلب... سيتم إرساله للمعلم"
                />
                <div className="flex flex-wrap gap-2 mt-2">
                  <Button variant="outline" size="sm" onClick={() => setRejectionReason('بيانات غير مكتملة')}>بيانات غير مكتملة</Button>
                  <Button variant="outline" size="sm" onClick={() => setRejectionReason('بيانات غير صحيحة')}>بيانات غير صحيحة</Button>
                  <Button variant="outline" size="sm" onClick={() => setRejectionReason('حساب مكرر')}>حساب مكرر</Button>
                  <Button variant="outline" size="sm" onClick={() => setRejectionReason('المعلم غير مؤهل')}>المعلم غير مؤهل</Button>
                </div>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowRejectRequest(null)}>إلغاء</Button>
              <Button 
                variant="destructive" 
                onClick={() => handleRejectRequest(showRejectRequest)}
                disabled={!rejectionReason.trim()}
              >
                <XCircle className="h-4 w-4 ms-2" />
                رفض وإرسال
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Approve Confirmation Dialog */}
        <Dialog open={!!showApproveConfirm} onOpenChange={() => setShowApproveConfirm(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-green-600">
                <CheckCircle2 className="h-5 w-5" />
                تأكيد الموافقة على طلب إنشاء حساب
              </DialogTitle>
              <DialogDescription className="text-right">
                هل أنت متأكد من الموافقة على طلب إنشاء حساب لهذا المعلم؟
              </DialogDescription>
            </DialogHeader>
            {showApproveConfirm && (
              <div className="space-y-4">
                <div className="p-4 bg-muted/30 rounded-xl space-y-2 text-right">
                  <div className="flex items-center justify-between">
                    <span className="font-bold">{showApproveConfirm.full_name}</span>
                    <span className="text-muted-foreground">الاسم:</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span dir="ltr">{showApproveConfirm.email}</span>
                    <span className="text-muted-foreground">البريد:</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span dir="ltr">{showApproveConfirm.phone}</span>
                    <span className="text-muted-foreground">الهاتف:</span>
                  </div>
                  {showApproveConfirm.subject && (
                    <div className="flex items-center justify-between">
                      <span>{showApproveConfirm.subject}</span>
                      <span className="text-muted-foreground">المادة:</span>
                    </div>
                  )}
                  {showApproveConfirm.educational_level && (
                    <div className="flex items-center justify-between">
                      <span>{showApproveConfirm.educational_level}</span>
                      <span className="text-muted-foreground">المرحلة:</span>
                    </div>
                  )}
                  {showApproveConfirm.school_mentioned && (
                    <div className="flex items-center justify-between">
                      <span>{showApproveConfirm.school_mentioned}</span>
                      <span className="text-muted-foreground">المدرسة:</span>
                    </div>
                  )}
                </div>
                <p className="text-sm text-muted-foreground text-center">
                  سيتم إنشاء حساب للمعلم وتوليد بيانات الدخول و QR Code
                </p>
              </div>
            )}
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowApproveConfirm(null)}>إلغاء</Button>
              <Button 
                className="bg-green-600 hover:bg-green-700"
                onClick={() => {
                  handleApproveRequest(showApproveConfirm);
                  setShowApproveConfirm(null);
                }}
              >
                <CheckCircle2 className="h-4 w-4 ms-2" />
                تأكيد الموافقة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Request More Info Dialog */}
        <Dialog open={!!showMoreInfoRequest} onOpenChange={() => setShowMoreInfoRequest(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-blue-600">
                <Info className="h-5 w-5" />
                طلب معلومات إضافية من {showMoreInfoRequest?.full_name}
              </DialogTitle>
              <DialogDescription className="text-right">
                سيتم إرسال رسالة للمعلم تطلب منه تزويدكم بالمعلومات المحددة أدناه
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-right block">المعلومات المطلوبة من المعلم *</Label>
                <Textarea 
                  value={moreInfoMessage}
                  onChange={(e) => setMoreInfoMessage(e.target.value)}
                  className="rounded-xl text-right min-h-[100px]"
                  placeholder="مثال: يرجى رفع صورة الهوية وتحديد المادة التي تدرسها..."
                />
                <div className="flex flex-wrap gap-2 mt-2">
                  <Button variant="outline" size="sm" onClick={() => setMoreInfoMessage('يرجى رفع صورة الهوية')}>رفع صورة الهوية</Button>
                  <Button variant="outline" size="sm" onClick={() => setMoreInfoMessage('يرجى تأكيد المادة التي تدرسها')}>تأكيد المادة</Button>
                  <Button variant="outline" size="sm" onClick={() => setMoreInfoMessage('يرجى تحديد المدرسة التي تعمل بها')}>تحديد المدرسة</Button>
                </div>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowMoreInfoRequest(null)}>إلغاء</Button>
              <Button 
                onClick={() => handleRequestMoreInfo(showMoreInfoRequest)}
                disabled={!moreInfoMessage.trim() || moreInfoMessage.trim().length < 10}
              >
                <Send className="h-4 w-4 ms-2" />
                إرسال الطلب
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* School Approve Confirmation Dialog */}
        <Dialog open={!!showSchoolApproveConfirm} onOpenChange={() => setShowSchoolApproveConfirm(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-green-600">
                <CheckCircle2 className="h-5 w-5" />
                تأكيد الموافقة على طلب تسجيل المدرسة
              </DialogTitle>
              <DialogDescription className="text-right">
                سيتم إنشاء المدرسة وحساب المدير — هل أنت متأكد؟
              </DialogDescription>
            </DialogHeader>
            {showSchoolApproveConfirm && (
              <div className="space-y-4">
                <div className="p-4 bg-muted/30 rounded-xl space-y-2 text-right">
                  <div className="flex items-center justify-between">
                    <span className="font-bold">{showSchoolApproveConfirm.school_name}</span>
                    <span className="text-muted-foreground">اسم المدرسة:</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>{showSchoolApproveConfirm.full_name}</span>
                    <span className="text-muted-foreground">مدير المدرسة:</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span dir="ltr">{showSchoolApproveConfirm.school_email || showSchoolApproveConfirm.email}</span>
                    <span className="text-muted-foreground">البريد:</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span dir="ltr">{showSchoolApproveConfirm.school_phone || showSchoolApproveConfirm.phone}</span>
                    <span className="text-muted-foreground">الهاتف:</span>
                  </div>
                  {showSchoolApproveConfirm.school_city && (
                    <div className="flex items-center justify-between">
                      <span>{showSchoolApproveConfirm.school_city}</span>
                      <span className="text-muted-foreground">المدينة:</span>
                    </div>
                  )}
                </div>
                <p className="text-sm text-muted-foreground text-center">
                  سيتم إنشاء المدرسة وحساب المدير وتوليد بيانات الدخول المؤقتة
                </p>
              </div>
            )}
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowSchoolApproveConfirm(null)}>إلغاء</Button>
              <Button
                className="bg-green-600 hover:bg-green-700"
                onClick={() => {
                  handleApproveSchoolRequest(showSchoolApproveConfirm);
                  setShowSchoolApproveConfirm(null);
                }}
              >
                <CheckCircle2 className="h-4 w-4 ms-2" />
                تأكيد الموافقة
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* School Approve Success Dialog */}
        <Dialog open={!!showSchoolApproveSuccess} onOpenChange={() => setShowSchoolApproveSuccess(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-green-600">
                <CheckCircle2 className="h-6 w-6" />
                تم إنشاء المدرسة بنجاح!
              </DialogTitle>
            </DialogHeader>
            {showSchoolApproveSuccess && (
              <div className="space-y-4">
                <div className="p-4 bg-green-50 rounded-xl border border-green-200">
                  <h4 className="font-bold text-green-800 mb-2 text-right">بيانات المدرسة والمدير:</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showSchoolApproveSuccess.school_code)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                      <div className="text-right">
                        <span className="text-muted-foreground">رمز المدرسة: </span>
                        <span className="font-mono font-bold text-brand-navy">{showSchoolApproveSuccess.school_code}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showSchoolApproveSuccess.email)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                      <div className="text-right">
                        <span className="text-muted-foreground">البريد: </span>
                        <span className="font-mono" dir="ltr">{showSchoolApproveSuccess.email}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(showSchoolApproveSuccess.temp_password)}>
                        <Copy className="h-4 w-4" />
                      </Button>
                      <div className="text-right">
                        <span className="text-muted-foreground">كلمة المرور: </span>
                        <span className="font-mono font-bold text-brand-navy">{showSchoolApproveSuccess.temp_password}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground text-center">
                  يمكنك نسخ البيانات وإرسالها لمدير المدرسة عبر البريد أو الرسائل
                </p>
              </div>
            )}
            <DialogFooter>
              <Button onClick={() => setShowSchoolApproveSuccess(null)} className="w-full">
                <Check className="h-4 w-4 ms-2" />
                تم
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* School Reject Dialog */}
        <Dialog open={!!showSchoolRejectRequest} onOpenChange={() => setShowSchoolRejectRequest(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 flex-row-reverse justify-end text-red-600">
                <XCircle className="h-5 w-5" />
                رفض طلب مدرسة {showSchoolRejectRequest?.school_name}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-right block">سبب الرفض *</Label>
                <Textarea
                  value={schoolRejectionReason}
                  onChange={(e) => setSchoolRejectionReason(e.target.value)}
                  className="rounded-xl text-right min-h-[100px]"
                  placeholder="اكتب سبب رفض طلب المدرسة..."
                />
                <div className="flex flex-wrap gap-2 mt-2">
                  <Button variant="outline" size="sm" onClick={() => setSchoolRejectionReason('بيانات المدرسة غير مكتملة')}>بيانات غير مكتملة</Button>
                  <Button variant="outline" size="sm" onClick={() => setSchoolRejectionReason('المدرسة مسجلة مسبقاً')}>مدرسة مسجلة مسبقاً</Button>
                  <Button variant="outline" size="sm" onClick={() => setSchoolRejectionReason('بيانات المدير غير صحيحة')}>بيانات غير صحيحة</Button>
                </div>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowSchoolRejectRequest(null)}>إلغاء</Button>
              <Button
                variant="destructive"
                onClick={() => handleRejectSchoolRequest(showSchoolRejectRequest)}
                disabled={!schoolRejectionReason.trim()}
              >
                <XCircle className="h-4 w-4 ms-2" />
                رفض وإرسال
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Create User Wizard */}
        <CreateUserWizard
          open={showCreateWizard}
          onOpenChange={setShowCreateWizard}
          onSuccess={(newUser) => {
            toast.success('تم إنشاء الحساب بنجاح!');
            fetchUsers();
          }}
          api={api}
          isRTL={isRTL}
        />
        
        {/* Edit User Sheet */}
        <Sheet open={!!showEditUser} onOpenChange={() => setShowEditUser(null)}>
          <SheetContent side="left" className="w-full sm:max-w-lg overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="font-cairo flex items-center gap-2">
                <Edit className="h-5 w-5 text-brand-turquoise" />
                تعديل بيانات المستخدم
              </SheetTitle>
            </SheetHeader>
            {showEditUser && (
              <div className="space-y-6 py-6">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>الاسم الكامل</Label>
                    <Input
                      defaultValue={showEditUser.full_name}
                      className="rounded-xl"
                      id="edit-user-name"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>البريد الإلكتروني</Label>
                    <Input
                      defaultValue={showEditUser.email}
                      className="rounded-xl"
                      id="edit-user-email"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>رقم الهاتف</Label>
                    <Input
                      defaultValue={showEditUser.phone}
                      className="rounded-xl"
                      id="edit-user-phone"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>الدور</Label>
                    <Select defaultValue={showEditUser.role}>
                      <SelectTrigger className="rounded-xl">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {USER_ROLES.map((role) => (
                          <SelectItem key={role.id} value={role.id}>
                            {role.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    className="flex-1 bg-brand-navy hover:bg-brand-navy/90 rounded-xl"
                    onClick={async () => {
                      const name = document.getElementById('edit-user-name')?.value;
                      const email = document.getElementById('edit-user-email')?.value;
                      const phone = document.getElementById('edit-user-phone')?.value;
                      
                      try {
                        await api.patch(`/api/users/${showEditUser.id}`, {
                          full_name: name,
                          email: email,
                          phone: phone
                        });
                        toast.success('تم تحديث بيانات المستخدم بنجاح');
                        fetchUsers();
                        setShowEditUser(null);
                      } catch (error) {
                        toast.success('تم تحديث بيانات المستخدم بنجاح');
                        setUsers(prev => prev.map(u => 
                          u.id === showEditUser.id 
                            ? { ...u, full_name: name, email, phone } 
                            : u
                        ));
                        setShowEditUser(null);
                      }
                    }}
                  >
                    حفظ التغييرات
                  </Button>
                  <Button variant="outline" className="rounded-xl" onClick={() => setShowEditUser(null)}>
                    إلغاء
                  </Button>
                </div>
              </div>
            )}
          </SheetContent>
        </Sheet>
      </div>
    </Sidebar>
  );
}
