import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '../components/ui/sheet';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Users, Filter, RefreshCw, UserPlus, Building2, ChevronLeft,
} from 'lucide-react';
import CreateUserWizard from '../components/wizards/CreateUserWizard';
import { useAuth } from '../contexts/AuthContext';

import {
  UsersStatsCards,
  UserCard,
  UsersFilters,
  SchoolUsersTab,
  ApprovalRequestsTab,
  UserDetailsDialog,
  SuspendDialog,
  DeleteDialog,
  NotificationDialog,
  ApprovalConfirmDialog,
  ApprovalSuccessDialog,
  RejectDialog,
  MoreInfoDialog,
  RequestDetailsDialog,
  EditUserSheet,
  APPROVAL_TYPE_CONFIG,
  USER_ROLES,
  ACCOUNT_TYPES,
  ACCOUNT_STATUSES,
  PENDING_STATUSES,
  getRoleInfo,
} from '../components/users-management';

export default function UsersManagement() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { nassaqError } = useNassaqAlert();
  const isRTL = true;

  const initialTab = useMemo(() => {
    const tabParam = searchParams.get('tab');
    if (!tabParam) return 'users';
    const validTabs = ['users', 'school-users', ...Object.values(APPROVAL_TYPE_CONFIG).map(c => c.tabValue)];
    return validTabs.includes(tabParam) ? tabParam : 'users';
  }, [searchParams]);

  const [users, setUsers] = useState([]);
  const [schoolUsers, setSchoolUsers] = useState({});
  const [schools, setSchools] = useState([]);
  const [requestsByType, setRequestsByType] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(initialTab);
  useEffect(() => { setActiveTab(initialTab); }, [initialTab]);
  const [requestFilters, setRequestFilters] = useState({});

  const [stats, setStats] = useState({
    totalUsers: 0, totalSchools: 0, totalStudents: 0,
    teachersInSchools: 0, independentTeachers: 0, platformAdmins: 0,
    pendingRequests: 0, studentAttendanceRate: null, teacherAttendanceRate: null,
    aiEnabledSchools: 0,
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAccountType, setSelectedAccountType] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedRole, setSelectedRole] = useState('all');
  const [selectedAIStatus, setSelectedAIStatus] = useState('all');

  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [showCreateWizard, setShowCreateWizard] = useState(false);

  const [showUserDetails, setShowUserDetails] = useState(null);
  const [showSuspendConfirm, setShowSuspendConfirm] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [showEditUser, setShowEditUser] = useState(null);
  const [showSendNotification, setShowSendNotification] = useState(null);
  const [approvalConfirm, setApprovalConfirm] = useState(null);
  const [approvalSuccess, setApprovalSuccess] = useState(null);
  const [rejectDialog, setRejectDialog] = useState(null);
  const [showMoreInfoRequest, setShowMoreInfoRequest] = useState(null);
  const [requestDetailsDialog, setRequestDetailsDialog] = useState(null);

  const [notificationForm, setNotificationForm] = useState({ type: 'system', title: '', message: '' });
  const [rejectionReason, setRejectionReason] = useState('');
  const [moreInfoMessage, setMoreInfoMessage] = useState('');

  const { api } = useAuth();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/users/platform-users', {
        params: {
          search: searchQuery || undefined,
          role: selectedRole !== 'all' ? selectedRole : undefined,
        }
      });

      let fetchedUsers = response.data.users || [];
      let filtered = fetchedUsers.filter(u =>
        u.role !== 'school_principal' &&
        u.role !== 'school_sub_admin' &&
        u.role !== 'school_manager' &&
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
        filtered = filtered.filter(u => selectedAIStatus === 'enabled' ? u.ai_enabled : !u.ai_enabled);
      }

      if (selectedAccountType !== 'all') {
        filtered = filtered.filter(u => {
          const role = (u.role || '').toLowerCase();
          if (selectedAccountType === 'platform') return role.includes('platform') || role === 'platform_admin';
          if (selectedAccountType === 'school') return role.includes('school') || role === 'teacher' || role === 'student' || role === 'parent' || (u.school_name && !role.includes('platform'));
          if (selectedAccountType === 'independent') return role === 'independent_teacher';
          if (selectedAccountType === 'testing') return role === 'testing_account' || role.includes('test');
          return true;
        });
      }

      setUsers(filtered);
      setStats(prev => ({ ...prev, totalUsers: fetchedUsers.length }));
    } catch (error) {
      console.error('Error fetching users:', error);
      nassaqError(isRTL ? 'فشل في تحميل المستخدمين' : 'Failed to load users');
      setUsers([]);
      setStats(prev => ({ ...prev, totalUsers: 0 }));
    } finally {
      setLoading(false);
    }
  }, [api, searchQuery, selectedRole, selectedStatus, selectedAIStatus, selectedAccountType, isRTL]);

  const fetchRequestsByType = useCallback(async (requestType) => {
    try {
      const response = await api.get('/registration-requests', { params: { account_type: requestType } });
      const requests = response.data?.requests || response.data || [];
      setRequestsByType(prev => ({ ...prev, [requestType]: requests }));
    } catch (error) {
      console.error(`Failed to fetch ${requestType} requests:`, error);
      setRequestsByType(prev => ({ ...prev, [requestType]: [] }));
    }
  }, [api]);

  const fetchAllRequests = useCallback(async () => {
    await Promise.all(Object.keys(APPROVAL_TYPE_CONFIG).map(type => fetchRequestsByType(type)));
  }, [fetchRequestsByType]);

  const getFilteredRequests = useCallback((requestType) => {
    const requests = requestsByType[requestType] || [];
    const filter = requestFilters[requestType] || 'all';
    if (filter === 'all') return requests;
    if (filter === 'pending') return requests.filter(r => PENDING_STATUSES.includes(r.status));
    return requests.filter(r => r.status === filter);
  }, [requestsByType, requestFilters]);

  const totalPendingRequests = useMemo(() => {
    return Object.values(requestsByType).reduce((total, requests) =>
      total + (requests || []).filter(r => PENDING_STATUSES.includes(r.status)).length, 0);
  }, [requestsByType]);

  const getPendingCount = useCallback((requestType) => {
    return (requestsByType[requestType] || []).filter(r => PENDING_STATUSES.includes(r.status)).length;
  }, [requestsByType]);

  const fetchSchoolUsers = useCallback(async () => {
    try {
      const schoolsResponse = await api.get('/schools');
      const schoolsList = schoolsResponse.data || [];
      setSchools(schoolsList);
      setStats(prev => ({
        ...prev,
        totalSchools: schoolsList.length,
        aiEnabledSchools: schoolsList.filter(s => s.ai_enabled).length,
      }));

      const schoolUsersMap = {};
      for (const school of schoolsList) {
        try {
          const usersResponse = await api.get('/users', { params: { tenant_id: school.id } });
          const schoolUsersList = usersResponse.data || [];
          schoolUsersMap[school.id] = {
            school,
            users: schoolUsersList.filter(u =>
              u.role === 'school_principal' || u.role === 'school_sub_admin' ||
              u.role === 'teacher' || u.role === 'school_manager'
            )
          };
        } catch (e) {
          schoolUsersMap[school.id] = { school, users: [] };
        }
      }
      setSchoolUsers(schoolUsersMap);
    } catch (error) {
      console.error('Error fetching school users:', error);
      setSchools([]);
      setSchoolUsers({});
    }
  }, [api]);

  const fetchCommandCenterStats = useCallback(async () => {
    try {
      const response = await api.get('/admin/command-center/stats');
      setStats(prev => ({
        ...prev,
        totalSchools: response.data.registered_schools || prev.totalSchools,
        totalStudents: response.data.registered_students || 0,
        teachersInSchools: response.data.teachers_in_schools || prev.teachersInSchools,
        independentTeachers: response.data.independent_teachers || prev.independentTeachers,
        platformAdmins: response.data.platform_accounts || prev.platformAdmins,
        studentAttendanceRate: response.data.student_attendance_rate ?? null,
        teacherAttendanceRate: response.data.teacher_attendance_rate ?? null,
        aiEnabledSchools: response.data.ai_enabled_schools || prev.aiEnabledSchools,
        pendingRequests: response.data.pending_requests || prev.pendingRequests,
      }));
    } catch (error) {
      console.error('Error fetching command center stats:', error);
    }
  }, [api]);

  useEffect(() => {
    fetchUsers();
    fetchAllRequests();
    fetchSchoolUsers();
    fetchCommandCenterStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return; }
    fetchUsers();
  }, [searchQuery, selectedRole, selectedStatus, selectedAIStatus, selectedAccountType]);

  const handleViewUser = (user) => navigate(`/admin/users/${user.id}`);

  const handleSuspendUser = async (user) => {
    try {
      await api.patch(`/users/${user.id}/status`, { is_active: !user.is_active });
      toast.success(user.is_active ? 'تم تعليق الحساب بنجاح' : 'تم تفعيل الحساب بنجاح');
      fetchUsers();
    } catch (error) {
      console.error('Error suspending user:', error);
      toast.error(error?.response?.data?.detail || 'فشل في تغيير حالة الحساب');
    }
    setShowSuspendConfirm(null);
  };

  const handleDeleteUser = async (user) => {
    try {
      await api.delete(`/users/${user.id}`);
      toast.success('تم أرشفة الحساب بنجاح');
      fetchUsers();
    } catch (error) {
      console.error('Error deleting user:', error);
      toast.error(error?.response?.data?.detail || 'فشل في أرشفة الحساب');
    }
    setShowDeleteConfirm(null);
  };

  const handleSendNotification = async (user) => {
    toast.success(`تم إرسال الإشعار إلى ${user.full_name}`);
    setShowSendNotification(null);
    setNotificationForm({ type: 'system', title: '', message: '' });
  };

  const handleUnifiedApprove = async (request, requestType) => {
    try {
      const response = await api.post(`/registration-requests/${request.id}/approve`);
      if (response.data?.success) {
        setApprovalSuccess({ request, requestType, ...response.data });
        toast.success(response.data.message || 'تم الموافقة وإنشاء الحساب بنجاح');
        fetchRequestsByType(requestType);
        if (requestType === 'school') fetchSchoolUsers();
      }
    } catch (error) {
      console.error(`Error approving ${requestType} request:`, error);
      nassaqError(error.response?.data?.detail || 'حدث خطأ أثناء الموافقة على الطلب');
    }
  };

  const handleUnifiedReject = async (request, requestType) => {
    if (!rejectionReason || rejectionReason.trim().length < 5) {
      nassaqError('يرجى إدخال سبب الرفض');
      return;
    }
    try {
      const response = await api.post(`/registration-requests/${request.id}/reject`, { reason: rejectionReason });
      if (response.data?.success) {
        toast.success('تم رفض الطلب بنجاح');
        fetchRequestsByType(requestType);
      }
    } catch (error) {
      console.error(`Error rejecting ${requestType} request:`, error);
      nassaqError(error.response?.data?.detail || 'حدث خطأ أثناء رفض الطلب');
    }
    setRejectDialog(null);
    setRejectionReason('');
  };

  const handleRequestMoreInfo = async (request) => {
    if (!moreInfoMessage || moreInfoMessage.trim().length < 10) {
      nassaqError('يرجى إدخال المعلومات المطلوبة بشكل واضح');
      return;
    }
    try {
      const response = await api.post(`/registration-requests/${request.id}/request-info`, { message: moreInfoMessage });
      if (response.data?.success) {
        toast.success('تم إرسال طلب المعلومات الإضافية');
        fetchRequestsByType(request.account_type || 'teacher');
      }
    } catch (error) {
      console.error('Error requesting more info:', error);
      nassaqError(error.response?.data?.detail || 'حدث خطأ أثناء إرسال الطلب');
    }
    setShowMoreInfoRequest(null);
    setMoreInfoMessage('');
  };

  const handleMarkUnderReview = async (request, requestType) => {
    try {
      const response = await api.post(`/registration-requests/${request.id}/under-review`, { notes: '' });
      if (response.data?.success) {
        toast.success('تم وضع الطلب تحت المراجعة');
        fetchRequestsByType(requestType);
      }
    } catch (error) {
      console.error(`Error marking ${requestType} request under review:`, error);
      nassaqError(error.response?.data?.detail || 'حدث خطأ أثناء تحديث حالة الطلب');
    }
  };

  const handleArchiveRequest = async (request, requestType) => {
    try {
      const response = await api.post(`/registration-requests/${request.id}/archive`);
      if (response.data?.success) {
        toast.success('تم أرشفة الطلب');
        fetchRequestsByType(requestType);
      }
    } catch (error) {
      console.error(`Error archiving ${requestType} request:`, error);
      nassaqError(error.response?.data?.detail || 'حدث خطأ أثناء أرشفة الطلب');
    }
  };

  const handleViewRequestDetails = async (request) => {
    try {
      const response = await api.get(`/registration-requests/${request.id}`);
      setRequestDetailsDialog(response.data);
    } catch (error) {
      console.error('Error fetching request details:', error);
      nassaqError('حدث خطأ أثناء تحميل تفاصيل الطلب');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('تم النسخ');
  };

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
                <p className="text-sm text-muted-foreground">المركز الموحد لإدارة جميع المستخدمين وطلبات المعلمين</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => navigate('/admin')} className="rounded-xl">
                <ChevronLeft className="h-5 w-5 rotate-180" />
              </Button>
            </div>
          </div>
        </header>

        <header className="lg:hidden sticky top-0 z-30 glass border-b border-border/50 px-4 py-3">
          <div className="flex items-center justify-between flex-row-reverse">
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={() => setMobileFiltersOpen(true)} className="rounded-xl relative">
                <Filter className="h-5 w-5" />
                {hasActiveFilters && (
                  <span className="absolute -top-1 -start-1 w-4 h-4 bg-brand-purple text-white text-[10px] rounded-full flex items-center justify-center">!</span>
                )}
              </Button>
              <Button size="icon" className="bg-brand-navy rounded-xl" onClick={() => setShowCreateWizard(true)}>
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
          <UsersStatsCards stats={stats} totalPendingRequests={totalPendingRequests} />

          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full max-w-3xl grid-cols-4 mb-4">
              <TabsTrigger value="users" className="font-cairo text-xs sm:text-sm">
                <Users className="h-4 w-4 ms-2" />مستخدمين
              </TabsTrigger>
              <TabsTrigger value="school-users" className="font-cairo text-xs sm:text-sm">
                <Building2 className="h-4 w-4 ms-2" />مستخدمو المدارس
              </TabsTrigger>
              {Object.entries(APPROVAL_TYPE_CONFIG).map(([type, config]) => {
                const TabIcon = config.tabIcon;
                const pending = getPendingCount(type);
                return (
                  <TabsTrigger key={type} value={config.tabValue} className="font-cairo relative text-xs sm:text-sm">
                    <TabIcon className="h-4 w-4 ms-2" />{config.tabLabel}
                    {pending > 0 && (
                      <span className="absolute -top-1 -start-1 w-5 h-5 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">{pending}</span>
                    )}
                  </TabsTrigger>
                );
              })}
            </TabsList>

            <TabsContent value="users" className="space-y-4">
              <UsersFilters
                searchQuery={searchQuery} setSearchQuery={setSearchQuery}
                selectedAccountType={selectedAccountType} setSelectedAccountType={setSelectedAccountType}
                selectedRole={selectedRole} setSelectedRole={setSelectedRole}
                selectedStatus={selectedStatus} setSelectedStatus={setSelectedStatus}
                selectedAIStatus={selectedAIStatus} setSelectedAIStatus={setSelectedAIStatus}
                hasActiveFilters={hasActiveFilters} clearFilters={clearFilters}
                loading={loading} onRefresh={fetchUsers}
              />

              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <RefreshCw className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : users.length === 0 ? (
                <div className="border rounded-lg py-20 text-center bg-card">
                  <Users className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                  <h3 className="font-bold text-lg mb-2">لا يوجد مستخدمين</h3>
                  <p className="text-muted-foreground mb-4">
                    {hasActiveFilters ? 'لم يتم العثور على مستخدمين مطابقين للفلاتر' : 'ابدأ بإنشاء مستخدم جديد'}
                  </p>
                  {hasActiveFilters ? (
                    <Button variant="outline" onClick={clearFilters}>مسح الفلاتر</Button>
                  ) : (
                    <Button onClick={() => setShowCreateWizard(true)}>
                      <UserPlus className="h-4 w-4 ms-2" />إنشاء مستخدم
                    </Button>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4">
                  {users.map((user) => (
                    <UserCard
                      key={user.id}
                      user={user}
                      onView={handleViewUser}
                      onSuspend={setShowSuspendConfirm}
                      onEdit={setShowEditUser}
                      onDelete={setShowDeleteConfirm}
                      onNotify={setShowSendNotification}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="school-users" className="space-y-4">
              <SchoolUsersTab schoolUsers={schoolUsers} />
            </TabsContent>

            {Object.entries(APPROVAL_TYPE_CONFIG).map(([requestType, config]) => (
              <TabsContent key={requestType} value={config.tabValue} className="space-y-4">
                <ApprovalRequestsTab
                  requestType={requestType}
                  config={config}
                  requests={requestsByType[requestType] || []}
                  filteredRequests={getFilteredRequests(requestType)}
                  currentFilter={requestFilters[requestType] || 'all'}
                  onFilterChange={(filterId) => setRequestFilters(prev => ({ ...prev, [requestType]: filterId }))}
                  onViewDetails={handleViewRequestDetails}
                  onApprove={(request) => setApprovalConfirm({ request, requestType })}
                  onMarkUnderReview={(request) => handleMarkUnderReview(request, requestType)}
                  onReject={(request) => setRejectDialog({ request, requestType })}
                  onArchive={(request) => handleArchiveRequest(request, requestType)}
                  onRequestMoreInfo={setShowMoreInfoRequest}
                />
              </TabsContent>
            ))}
          </Tabs>
        </div>

        {/* Mobile Filters Sheet */}
        <Sheet open={mobileFiltersOpen} onOpenChange={setMobileFiltersOpen}>
          <SheetContent side="right" className="w-[85vw] sm:w-[400px] p-0">
            <SheetHeader className="p-4 border-b">
              <SheetTitle className="font-cairo flex items-center gap-2 flex-row-reverse justify-end">
                <Filter className="h-5 w-5" />الفلاتر
              </SheetTitle>
            </SheetHeader>
            <ScrollArea className="h-[calc(100vh-180px)]">
              <div className="p-4 space-y-5">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-right block">نوع الحساب</label>
                  <Select value={selectedAccountType} onValueChange={setSelectedAccountType}>
                    <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
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
                    <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
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
                    <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
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
                    <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
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

        <UserDetailsDialog
          user={showUserDetails}
          onClose={() => setShowUserDetails(null)}
          onEdit={setShowEditUser}
          onSuspend={setShowSuspendConfirm}
          onNotify={setShowSendNotification}
        />

        <SuspendDialog
          user={showSuspendConfirm}
          onClose={() => setShowSuspendConfirm(null)}
          onConfirm={handleSuspendUser}
        />

        <DeleteDialog
          user={showDeleteConfirm}
          onClose={() => setShowDeleteConfirm(null)}
          onConfirm={handleDeleteUser}
        />

        <NotificationDialog
          user={showSendNotification}
          form={notificationForm}
          setForm={setNotificationForm}
          onClose={() => setShowSendNotification(null)}
          onSend={handleSendNotification}
        />

        <ApprovalConfirmDialog
          data={approvalConfirm}
          onClose={() => setApprovalConfirm(null)}
          onConfirm={handleUnifiedApprove}
        />

        <ApprovalSuccessDialog
          data={approvalSuccess}
          onClose={() => setApprovalSuccess(null)}
          copyToClipboard={copyToClipboard}
        />

        <RejectDialog
          data={rejectDialog}
          rejectionReason={rejectionReason}
          setRejectionReason={setRejectionReason}
          onClose={() => setRejectDialog(null)}
          onConfirm={handleUnifiedReject}
        />

        <MoreInfoDialog
          request={showMoreInfoRequest}
          message={moreInfoMessage}
          setMessage={setMoreInfoMessage}
          onClose={() => setShowMoreInfoRequest(null)}
          onConfirm={handleRequestMoreInfo}
        />

        <RequestDetailsDialog
          request={requestDetailsDialog}
          onClose={() => setRequestDetailsDialog(null)}
        />

        <CreateUserWizard
          open={showCreateWizard}
          onOpenChange={setShowCreateWizard}
          onSuccess={() => { toast.success('تم إنشاء الحساب بنجاح!'); fetchUsers(); }}
          api={api}
          isRTL={isRTL}
        />

        <EditUserSheet
          user={showEditUser}
          onClose={() => setShowEditUser(null)}
          onSave={(successMsg, errorMsg) => {
            if (successMsg) toast.success(successMsg);
            if (errorMsg) toast.error(errorMsg);
          }}
          api={api}
          fetchUsers={fetchUsers}
        />
      </div>
    </Sidebar>
  );
}
