import React, { useState, useEffect, useRef, useCallback, useMemo, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { usePlatformAdminSchoolPreview } from '@/shared/hooks/usePlatformAdminSchoolPreview';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import { Switch } from '@/shared/components/ui/switch';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/shared/components/ui/dialog';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import {
  Building2, Search, Filter, Plus, LayoutGrid, List, Users, GraduationCap,
  MapPin, Eye, Pause, Play, RefreshCw, CheckCircle2,
  AlertTriangle, Clock, ChevronRight, ChevronLeft, X,
  Loader2, Layers, Trash2, MoreHorizontal, Download,
  XCircle, UserCheck, FileEdit, ExternalLink, Calendar, Activity,
  SlidersHorizontal, CheckCircle, ArrowUpDown, ChevronDown, Check,
} from 'lucide-react';
import { Textarea } from '@/shared/components/ui/textarea';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const CreateSchoolWizard = lazy(() => import('@/admin/features/schools/components/CreateSchoolWizard'));

const SCHOOL_STATUS = {
  active: { label: 'نشطة', label_en: 'Active', color: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800' },
  suspended: { label: 'موقوفة', label_en: 'Suspended', color: 'bg-rose-500', badge: 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-800' },
  setup: { label: 'مسودة / قيد الإعداد', label_en: 'Draft / Setup', color: 'bg-amber-500', badge: 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800' },
  pending: { label: 'معلقة', label_en: 'Pending', color: 'bg-slate-500', badge: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700' },
};

const LOGO_GRADIENTS = [
  'from-blue-600 to-blue-500',
  'from-emerald-600 to-emerald-500',
  'from-violet-600 to-violet-500',
  'from-orange-600 to-orange-500',
  'from-rose-600 to-rose-500',
  'from-cyan-600 to-cyan-500',
  'from-indigo-600 to-indigo-500',
  'from-teal-600 to-teal-500',
];

export default function TenantsManagement() {
  const { api, isRTL: contextIsRTL } = useAuth();
  const { openPrincipalDashboard, canOpenPrincipalDashboard } = usePlatformAdminSchoolPreview();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const isRTL = contextIsRTL !== false;

  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'table'
  const [showFilters, setShowFilters] = useState(false);
  const [showCreateWizard, setShowCreateWizard] = useState(false);
  const [activeStatusFilter, setActiveStatusFilter] = useState(null);
  const [showSuspendDialog, setShowSuspendDialog] = useState(null);
  const [showActivateDialog, setShowActivateDialog] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const [showDrafts, setShowDrafts] = useState(true);
  const [deletingDraftId, setDeletingDraftId] = useState(null);

  // Pagination for table view
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Advanced Filters
  const [filters, setFilters] = useState({
    status: 'all',
    city: 'all',
    schoolType: 'all',
    stage: 'all',
  });

  const fetchSchoolsInFlightRef = useRef(null);

  const fetchSchools = useCallback(async (showToast = false) => {
    if (!showToast && fetchSchoolsInFlightRef.current) return fetchSchoolsInFlightRef.current;
    if (showToast) setRefreshing(true);

    const task = (async () => {
      try {
        const [overviewRes, schoolsRes] = await Promise.allSettled([
          api.get('/admin/command-center/schools-overview'),
          api.get('/schools'),
        ]);

        let schoolsData = [];
        if (overviewRes.status === 'fulfilled' && overviewRes.value.data?.schools?.length > 0) {
          schoolsData = overviewRes.value.data.schools;
        } else if (schoolsRes.status === 'fulfilled') {
          const rawSchools = Array.isArray(schoolsRes.value.data) ? schoolsRes.value.data : (schoolsRes.value.data?.schools || []);
          schoolsData = rawSchools.map(s => ({
            id: s.id,
            name: s.name,
            name_en: s.name_en,
            code: s.code || '',
            email: s.email || '',
            phone: s.phone || s.principal_mobile || '',
            status: s.status || 'active',
            city: s.city || '',
            region: s.region || '',
            school_type: s.type || s.school_type || 'public',
            stage: s.stage || 'primary',
            student_capacity: s.student_capacity || 500,
            student_count: s.student_count || s.current_students || 0,
            teacher_count: s.teacher_count || s.current_teachers || 0,
            class_count: s.class_count || 0,
            parent_count: s.parent_count || 0,
            sessions_today: 0,
            setup_score: s.status === 'active' ? 100 : 50,
            has_timetable: false,
            created_at: s.created_at || '',
            last_activity: s.updated_at || s.created_at || '',
          }));
        }
        setSchools(schoolsData);
        if (showToast) toast.success(t('dataRefreshed') || 'تم تحديث البيانات بنجاح');
      } catch (error) {
        console.error('Error fetching schools:', error);
        nassaqError(t('errorLoadingSchools') || 'خطأ في تحميل المدارس');
      } finally {
        setLoading(false);
        setRefreshing(false);
        fetchSchoolsInFlightRef.current = null;
      }
    })();

    fetchSchoolsInFlightRef.current = task;
    return task;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, isRTL]);

  useEffect(() => { fetchSchools(); }, [fetchSchools]);

  const draftSchools = useMemo(() => schools.filter(s => s.status === 'setup'), [schools]);

  const filteredSchools = useMemo(() => {
    let result = [...schools];
    if (activeStatusFilter === 'setup') {
      result = result.filter(s => s.status === 'setup');
    } else if (activeStatusFilter) {
      result = result.filter(s => s.status === activeStatusFilter);
    } else if (filters.status !== 'all') {
      result = result.filter(s => s.status === filters.status);
    } else {
      result = result.filter(s => s.status !== 'setup');
    }

    if (filters.city !== 'all') {
      result = result.filter(s => s.city === filters.city);
    }
    if (filters.schoolType !== 'all') {
      result = result.filter(s => s.school_type === filters.schoolType);
    }
    if (filters.stage !== 'all') {
      result = result.filter(s => s.stage === filters.stage);
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(s =>
        s.name?.toLowerCase().includes(q) ||
        s.name_en?.toLowerCase().includes(q) ||
        s.code?.toLowerCase().includes(q) ||
        s.city?.toLowerCase().includes(q) ||
        s.region?.toLowerCase().includes(q) ||
        s.email?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [schools, searchQuery, filters, activeStatusFilter]);

  const totalPages = Math.ceil(filteredSchools.length / itemsPerPage) || 1;
  const paginatedSchools = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredSchools.slice(start, start + itemsPerPage);
  }, [filteredSchools, currentPage, itemsPerPage]);

  const cities = useMemo(() => [...new Set(schools.map(s => s.city).filter(Boolean))], [schools]);

  const stats = {
    total: schools.filter(s => s.status !== 'setup').length,
    active: schools.filter(s => s.status === 'active').length,
    suspended: schools.filter(s => s.status === 'suspended').length,
    pending: schools.filter(s => s.status === 'pending').length,
    drafts: draftSchools.length,
    totalStudents: schools.reduce((sum, s) => sum + (s.student_count || 0), 0),
    totalTeachers: schools.reduce((sum, s) => sum + (s.teacher_count || 0), 0),
    totalClasses: schools.reduce((sum, s) => sum + (s.class_count || 0), 0),
  };

  const resetFilters = () => {
    setFilters({ status: 'all', city: 'all', schoolType: 'all', stage: 'all' });
    setSearchQuery('');
    setActiveStatusFilter(null);
    setCurrentPage(1);
  };

  const handleStatusFilter = (status) => {
    setActiveStatusFilter(prev => prev === status ? null : status);
    setCurrentPage(1);
  };

  const handleEnterSchoolDashboard = (school) => openPrincipalDashboard(school);

  const handleSuspendConfirm = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired') || 'سبب الإيقاف مطلوب');
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${showSuspendDialog.id}/suspend`, { reason: actionReason });
      setSchools(prev => prev.map(s =>
        s.id === showSuspendDialog.id ? { ...s, status: 'suspended' } : s
      ));
      toast.success(isRTL ? `تم إيقاف ${showSuspendDialog.name}` : `${showSuspendDialog.name} suspended`);
      setShowSuspendDialog(null);
      setActionReason('');
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (isRTL ? 'فشل إيقاف المدرسة' : 'Failed to suspend school'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivateConfirm = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired2') || 'سبب التفعيل مطلوب');
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${showActivateDialog.id}/activate`, { reason: actionReason });
      setSchools(prev => prev.map(s =>
        s.id === showActivateDialog.id ? { ...s, status: 'active' } : s
      ));
      toast.success(isRTL ? `تم تفعيل ${showActivateDialog.name}` : `${showActivateDialog.name} activated`);
      setShowActivateDialog(null);
      setActionReason('');
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (isRTL ? 'فشل تفعيل المدرسة' : 'Failed to activate school'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleSchoolCreated = () => {
    setShowCreateWizard(false);
    setShowDrafts(true);
    setActiveStatusFilter(null);
    fetchSchools(true);
  };

  const handleDeleteDraft = async (draft) => {
    setDeletingDraftId(draft.id);
    try {
      await api.delete(`/schools/${draft.id}/draft`);
      setSchools(prev => prev.filter(s => s.id !== draft.id));
      toast.success(isRTL ? `تم حذف مسودة "${draft.name}"` : `Draft "${draft.name}" deleted`);
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (t('failedToDeleteDraft') || 'فشل حذف المسودة'));
    } finally {
      setDeletingDraftId(null);
    }
  };

  const exportToCSV = () => {
    try {
      const headers = ['اسم المدرسة', 'كود المدرسة', 'المدينة', 'المنطقة', 'الحالة', 'نوع المدرسة', 'المرحلة', 'عدد الطلاب', 'عدد المعلمين'];
      const rows = filteredSchools.map(s => [
        `"${s.name || ''}"`,
        `"${s.code || ''}"`,
        `"${s.city || ''}"`,
        `"${s.region || ''}"`,
        `"${SCHOOL_STATUS[s.status]?.label || s.status}"`,
        `"${s.school_type === 'private' ? 'أهلية' : 'حكومية'}"`,
        `"${s.stage || ''}"`,
        s.student_count || 0,
        s.teacher_count || 0,
      ]);

      const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `schools_export_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success(isRTL ? 'تم تصدير ملف المدارس بنجاح' : 'Schools exported successfully');
    } catch (e) {
      console.error('Export error:', e);
      toast.error(isRTL ? 'فشل تصدير البيانات' : 'Failed to export data');
    }
  };

  const getLogoGradient = (id) => {
    const hash = (id || '').split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
    return LOGO_GRADIENTS[hash % LOGO_GRADIENTS.length];
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
          <div className="text-center space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-[#00C5B2] mx-auto" />
            <p className="text-lg font-cairo font-bold text-slate-700 dark:text-slate-300">
              {t('loadingSchools') || 'جاري تحميل بيانات المدارس...'}
            </p>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-slate-50/70 dark:bg-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">

          {/* Hero Section */}
          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#1C3D74] via-[#152e57] to-[#1C3D74] p-6 sm:p-8 text-white shadow-xl">
            <div className="absolute inset-0 bg-[radial-gradient(#00C5B2_1px,transparent_1px)] [background-size:16px_16px] opacity-15 pointer-events-none" />
            <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-white/10 rounded-2xl backdrop-blur-md flex items-center justify-center border border-white/20 shadow-inner">
                    <Building2 className="h-6 w-6 text-[#00C5B2]" />
                  </div>
                  <div>
                    <h1 className="text-2xl sm:text-3xl font-extrabold font-cairo tracking-tight">
                      {isRTL ? 'إدارة المدارس والمستأجرين' : 'Schools & Tenants Management'}
                    </h1>
                    <p className="text-white/80 text-xs sm:text-sm font-medium mt-0.5">
                      {isRTL ? 'المركز الموحد لإدارة المستأجرين، المدارس الأكاديمية، والتحكم في إعدادات التشغيل' : 'Unified hub for school tenants, academic setups, and operations'}
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-10 px-3.5 backdrop-blur-md"
                  onClick={() => fetchSchools(true)}
                  disabled={refreshing}
                >
                  <RefreshCw className={`h-4 w-4 me-1.5 ${refreshing ? 'animate-spin' : ''}`} />
                  {isRTL ? 'تحديث' : 'Refresh'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-10 px-3.5 backdrop-blur-md"
                  onClick={exportToCSV}
                >
                  <Download className="h-4 w-4 me-1.5 text-[#00C5B2]" />
                  {isRTL ? 'تصدير CSV' : 'Export'}
                </Button>
                <Button
                  size="sm"
                  className="rounded-xl bg-[#00C5B2] hover:bg-[#00b09f] text-slate-950 font-black text-xs h-10 px-5 shadow-lg shadow-[#00C5B2]/20 gap-1.5 transition-all"
                  onClick={() => setShowCreateWizard(true)}
                  data-testid="add-school-main-btn"
                >
                  <Plus className="h-4 w-4 stroke-[3]" />
                  <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
                </Button>
              </div>
            </div>

            {/* Stats Ribbon */}
            <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              {[
                { label: isRTL ? 'إجمالي المدارس' : 'Total Schools', value: stats.total, icon: Building2, onClick: () => setActiveStatusFilter(null), active: activeStatusFilter === null },
                { label: isRTL ? 'المدارس النشطة' : 'Active Schools', value: stats.active, icon: CheckCircle2, onClick: () => handleStatusFilter('active'), active: activeStatusFilter === 'active', color: 'text-emerald-400' },
                { label: isRTL ? 'المدارس الموقوفة' : 'Suspended', value: stats.suspended, icon: XCircle, onClick: () => handleStatusFilter('suspended'), active: activeStatusFilter === 'suspended', color: 'text-rose-400' },
                { label: isRTL ? 'المسودات' : 'Drafts', value: stats.drafts, icon: Clock, onClick: () => handleStatusFilter('setup'), active: activeStatusFilter === 'setup', color: 'text-amber-400' },
                { label: isRTL ? 'إجمالي الطلاب' : 'Students', value: stats.totalStudents.toLocaleString(), icon: GraduationCap },
                { label: isRTL ? 'إجمالي المعلمين' : 'Teachers', value: stats.totalTeachers.toLocaleString(), icon: UserCheck },
                { label: isRTL ? 'الفصول الدراسية' : 'Classes', value: stats.totalClasses.toLocaleString(), icon: Layers },
              ].map((item, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={item.onClick}
                  className={`bg-white/10 backdrop-blur-md rounded-2xl p-3 text-center transition-all border border-white/10 hover:bg-white/20 focus:outline-none ${
                    item.active ? 'ring-2 ring-[#00C5B2] bg-white/20 shadow-md' : ''
                  }`}
                >
                  <item.icon className={`h-5 w-5 mx-auto mb-1 ${item.color || 'text-[#00C5B2]'}`} />
                  <p className="text-xl font-black font-cairo">{item.value}</p>
                  <p className="text-[11px] font-medium text-white/75">{item.label}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Active Filter Indicator */}
          {activeStatusFilter && (
            <div className="p-3.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 rounded-2xl flex items-center justify-between shadow-xs">
              <span className="text-xs font-bold text-blue-950 dark:text-blue-200 flex items-center gap-2">
                <Filter className="h-4 w-4 text-[#00C5B2]" />
                {isRTL
                  ? `عرض المدارس حسب الحالة: ${SCHOOL_STATUS[activeStatusFilter]?.label || activeStatusFilter}`
                  : `Filtering by status: ${SCHOOL_STATUS[activeStatusFilter]?.label_en || activeStatusFilter}`}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActiveStatusFilter(null)}
                className="h-7 text-xs font-bold text-blue-800 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-lg px-2.5"
              >
                <X className="h-3.5 w-3.5 me-1" />
                {isRTL ? 'إلغاء الفلتر' : 'Clear'}
              </Button>
            </div>
          )}

          {/* Control Bar (Search, Filters & View Toggle) */}
          <Card className="rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 p-4">
            <div className="flex flex-col md:flex-row items-center justify-between gap-3">
              {/* Search Box */}
              <div className="relative w-full md:w-96">
                <Search className="absolute start-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setCurrentPage(1);
                  }}
                  placeholder={isRTL ? 'بحث باسم المدرسة، الكود، المدينة...' : 'Search by name, code, city...'}
                  className="ps-10 h-11 rounded-xl bg-slate-50 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white font-medium text-xs focus:ring-2 focus:ring-[#00C5B2]/20"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute end-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Action Buttons & View Toggles */}
              <div className="flex items-center gap-2.5 w-full md:w-auto justify-end flex-wrap">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowFilters(!showFilters)}
                  className={`rounded-xl h-11 px-4 text-xs font-bold border-slate-300 dark:border-slate-700 gap-1.5 transition-all ${
                    showFilters || filters.status !== 'all' || filters.city !== 'all' || filters.schoolType !== 'all'
                      ? 'bg-[#1C3D74] text-white border-[#1C3D74]'
                      : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200'
                  }`}
                >
                  <SlidersHorizontal className="h-4 w-4" />
                  <span>{isRTL ? 'فلاتر متقدمة' : 'Filters'}</span>
                </Button>

                {/* View Mode Toggle: Grid vs Table */}
                <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-xl border border-slate-200 dark:border-slate-700">
                  <button
                    type="button"
                    onClick={() => setViewMode('grid')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      viewMode === 'grid'
                        ? 'bg-white dark:bg-slate-900 text-[#1C3D74] dark:text-[#00C5B2] shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                    }`}
                  >
                    <LayoutGrid className="h-4 w-4" />
                    <span>{isRTL ? 'بطاقات' : 'Cards'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode('table')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                      viewMode === 'table'
                        ? 'bg-white dark:bg-slate-900 text-[#1C3D74] dark:text-[#00C5B2] shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                    }`}
                  >
                    <List className="h-4 w-4" />
                    <span>{isRTL ? 'جدول' : 'Table'}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Expandable Advanced Filters */}
            {showFilters && (
              <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 animate-in fade-in-30 duration-200">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">{isRTL ? 'الحالة' : 'Status'}</label>
                  <Select value={filters.status} onValueChange={(v) => { setFilters({ ...filters, status: v }); setCurrentPage(1); }}>
                    <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-300 dark:border-slate-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'جميع الحالات' : 'All Statuses'}</SelectItem>
                      <SelectItem value="active">{isRTL ? 'نشطة' : 'Active'}</SelectItem>
                      <SelectItem value="suspended">{isRTL ? 'موقوفة' : 'Suspended'}</SelectItem>
                      <SelectItem value="pending">{isRTL ? 'معلقة' : 'Pending'}</SelectItem>
                      <SelectItem value="setup">{isRTL ? 'مسودة' : 'Draft'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">{isRTL ? 'المدينة' : 'City'}</label>
                  <Select value={filters.city} onValueChange={(v) => { setFilters({ ...filters, city: v }); setCurrentPage(1); }}>
                    <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-300 dark:border-slate-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'جميع المدن' : 'All Cities'}</SelectItem>
                      {cities.map((city) => (
                        <SelectItem key={city} value={city}>{city}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">{isRTL ? 'نوع المدرسة' : 'School Type'}</label>
                  <Select value={filters.schoolType} onValueChange={(v) => { setFilters({ ...filters, schoolType: v }); setCurrentPage(1); }}>
                    <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-300 dark:border-slate-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'جميع الأنواع' : 'All Types'}</SelectItem>
                      <SelectItem value="public">{isRTL ? 'حكومية' : 'Public'}</SelectItem>
                      <SelectItem value="private">{isRTL ? 'أهلية' : 'Private'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">{isRTL ? 'المرحلة التعليمية' : 'Stage'}</label>
                  <Select value={filters.stage} onValueChange={(v) => { setFilters({ ...filters, stage: v }); setCurrentPage(1); }}>
                    <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-300 dark:border-slate-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'جميع المراحل' : 'All Stages'}</SelectItem>
                      <SelectItem value="primary">{isRTL ? 'ابتدائية' : 'Primary'}</SelectItem>
                      <SelectItem value="intermediate">{isRTL ? 'متوسطة' : 'Intermediate'}</SelectItem>
                      <SelectItem value="secondary_general">{isRTL ? 'ثانوية عامة' : 'Secondary General'}</SelectItem>
                      <SelectItem value="secondary_pathways">{isRTL ? 'ثانوية مسارات' : 'Secondary Pathways'}</SelectItem>
                      <SelectItem value="school_complex">{isRTL ? 'مجمع مدارس' : 'Complex'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </Card>

          {/* Drafts Section (Only shown when not specifically filtering for active/suspended) */}
          {draftSchools.length > 0 && activeStatusFilter !== 'active' && activeStatusFilter !== 'suspended' && (
            <div className="p-4 rounded-3xl bg-amber-500/10 border border-amber-500/30">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  <h3 className="font-bold text-xs font-cairo text-amber-950 dark:text-amber-200">
                    {isRTL ? `مسودات المدارس قيد التهيئة (${draftSchools.length})` : `School Setup Drafts (${draftSchools.length})`}
                  </h3>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDrafts(!showDrafts)}
                  className="h-7 text-xs text-amber-900 dark:text-amber-300 hover:bg-amber-500/20 rounded-lg"
                >
                  {showDrafts ? (isRTL ? 'إخفاء' : 'Hide') : (isRTL ? 'عرض' : 'Show')}
                </Button>
              </div>

              {showDrafts && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {draftSchools.map((draft) => (
                    <div
                      key={draft.id}
                      className="p-3.5 rounded-2xl bg-white dark:bg-slate-900 border border-amber-300 dark:border-amber-900/60 shadow-xs flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <strong className="text-xs font-black text-slate-900 dark:text-white line-clamp-1">{draft.name}</strong>
                          <Badge className="text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300">
                            {isRTL ? 'مسودة' : 'Draft'}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1 mb-3">
                          <MapPin className="h-3 w-3" />
                          <span>{draft.city || (isRTL ? 'غير محدد' : 'Unset')}</span>
                        </p>
                      </div>

                      <div className="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                        <Button
                          size="sm"
                          className="flex-1 h-8 rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white text-xs font-bold gap-1.5"
                          onClick={() => navigate(`/platform/schools/${draft.id}`)}
                        >
                          <FileEdit className="h-3.5 w-3.5" />
                          <span>{isRTL ? 'استكمال الإعداد' : 'Resume Setup'}</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteDraft(draft)}
                          disabled={deletingDraftId === draft.id}
                          className="h-8 w-8 p-0 rounded-xl text-rose-600 border-rose-200 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                        >
                          {deletingDraftId === draft.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Schools Content Rendering */}
          {filteredSchools.length === 0 ? (
            <Card className="rounded-3xl border-slate-200 dark:border-slate-800 p-12 text-center bg-white dark:bg-slate-900 shadow-sm">
              <Building2 className="h-16 w-16 mx-auto text-slate-300 dark:text-slate-700 mb-4" />
              <h3 className="font-extrabold text-lg mb-1 font-cairo text-slate-900 dark:text-white">
                {isRTL ? 'لا توجد مدارس مطابقة للبحث' : 'No Schools Found'}
              </h3>
              <p className="text-xs font-medium text-slate-500 mb-5">
                {isRTL ? 'جرب تغيير معايير البحث أو إلغاء الفلاتر المحددة' : 'Try adjusting search or clearing applied filters'}
              </p>
              <Button onClick={resetFilters} variant="outline" className="rounded-xl font-bold text-xs">
                <RefreshCw className="h-4 w-4 me-1.5" />
                {isRTL ? 'إعادة ضبط الفلاتر' : 'Reset Filters'}
              </Button>
            </Card>
          ) : viewMode === 'table' ? (
            /* ── Table View ────────────────────────────────────────── */
            <Card className="rounded-3xl border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm bg-white dark:bg-slate-900">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 py-3.5">{isRTL ? 'المدرسة' : 'School'}</TableHead>
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">{isRTL ? 'كود المستأجر' : 'Tenant Code'}</TableHead>
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">{isRTL ? 'المدينة / المنطقة' : 'City / Region'}</TableHead>
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">{isRTL ? 'الحالة' : 'Status'}</TableHead>
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">{isRTL ? 'الطلاب' : 'Students'}</TableHead>
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">{isRTL ? 'المعلمين' : 'Teachers'}</TableHead>
                      <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">{isRTL ? 'الإجراءات' : 'Actions'}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paginatedSchools.map((school) => (
                      <TableRow key={school.id} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                        <TableCell className="py-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-2xl bg-gradient-to-br ${getLogoGradient(school.id)} flex items-center justify-center text-white font-bold text-sm shadow-xs shrink-0`}>
                              {school.name?.charAt(0)}
                            </div>
                            <div>
                              <p className="font-bold text-slate-900 dark:text-white text-xs">{school.name}</p>
                              <p className="text-[11px] text-slate-500 font-normal truncate max-w-[180px]">{school.email || school.name_en || '—'}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-center font-mono text-xs font-bold text-[#1C3D74] dark:text-[#00C5B2]">
                          {school.code || '—'}
                        </TableCell>
                        <TableCell className="text-center text-xs font-medium text-slate-700 dark:text-slate-300">
                          <div className="flex items-center justify-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-slate-400" />
                            <span>{school.city || '—'}</span>
                            {school.region && <span className="text-slate-400">/ {school.region}</span>}
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge className={`text-[11px] font-bold ${SCHOOL_STATUS[school.status]?.badge || SCHOOL_STATUS.active.badge}`}>
                            {isRTL ? SCHOOL_STATUS[school.status]?.label : SCHOOL_STATUS[school.status]?.label_en}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-center text-xs font-bold text-blue-600 dark:text-blue-400">
                          {school.student_count || 0}
                        </TableCell>
                        <TableCell className="text-center text-xs font-bold text-purple-600 dark:text-purple-400">
                          {school.teacher_count || 0}
                        </TableCell>
                        <TableCell className="text-center py-2">
                          <div className="flex items-center justify-center gap-2">
                            <Button
                              size="sm"
                              className="h-8 px-3 rounded-xl bg-[#00C5B2] hover:bg-[#00b09f] text-slate-950 font-extrabold text-xs disabled:opacity-40 gap-1"
                              onClick={() => handleEnterSchoolDashboard(school)}
                              disabled={!canOpenPrincipalDashboard(school)}
                            >
                              <Eye className="h-3.5 w-3.5" />
                              <span>{isRTL ? 'الدخول' : 'Enter'}</span>
                            </Button>

                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0 rounded-xl">
                                  <MoreHorizontal className="h-4 w-4 text-slate-600" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-48 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl p-1.5 font-cairo">
                                <DropdownMenuItem
                                  onClick={() => navigate(`/platform/schools/${school.id}`)}
                                  className="rounded-xl font-bold text-xs py-2 text-slate-700 dark:text-slate-200"
                                >
                                  <ExternalLink className="h-4 w-4 me-2 text-slate-500" />
                                  {isRTL ? 'الملف التفصيلي للمدرسة' : 'Full School Profile'}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {school.status === 'active' ? (
                                  <DropdownMenuItem
                                    onClick={() => { setShowSuspendDialog(school); setActionReason(''); }}
                                    className="rounded-xl font-bold text-xs py-2 text-rose-600 hover:bg-rose-50"
                                  >
                                    <Pause className="h-4 w-4 me-2" />
                                    {isRTL ? 'إيقاف المدرسة' : 'Suspend School'}
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem
                                    onClick={() => { setShowActivateDialog(school); setActionReason(''); }}
                                    className="rounded-xl font-bold text-xs py-2 text-emerald-600 hover:bg-emerald-50"
                                  >
                                    <Play className="h-4 w-4 me-2" />
                                    {isRTL ? 'تفعيل المدرسة' : 'Activate School'}
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Table Pagination Bar */}
              {totalPages > 1 && (
                <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3">
                  <div className="text-xs font-semibold text-slate-500">
                    {isRTL
                      ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, filteredSchools.length)} من أصل ${filteredSchools.length} مدرسة`
                      : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, filteredSchools.length)} of ${filteredSchools.length} schools`}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.max(p - 1, 1))}
                      disabled={currentPage === 1}
                      className="rounded-xl h-8 px-3 font-bold text-xs border-slate-300"
                    >
                      {isRTL ? <ChevronRight className="h-4 w-4 me-1" /> : <ChevronLeft className="h-4 w-4 me-1" />}
                      {isRTL ? 'السابق' : 'Previous'}
                    </Button>
                    <span className="text-xs font-black text-slate-800 dark:text-slate-200 px-2">
                      {currentPage} / {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(p => Math.min(p + 1, totalPages))}
                      disabled={currentPage === totalPages}
                      className="rounded-xl h-8 px-3 font-bold text-xs border-slate-300"
                    >
                      {isRTL ? 'التالي' : 'Next'}
                      {isRTL ? <ChevronLeft className="h-4 w-4 ms-1" /> : <ChevronRight className="h-4 w-4 ms-1" />}
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          ) : (
            /* ── Card Grid View ─────────────────────────────────────── */
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {filteredSchools.map((school) => (
                <Card
                  key={school.id}
                  className="group rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-xl transition-all duration-300 overflow-hidden bg-white dark:bg-slate-900 flex flex-col justify-between"
                  data-testid={`school-card-${school.id}`}
                >
                  <div>
                    {/* Header Banner */}
                    <div className={`bg-gradient-to-r ${getLogoGradient(school.id)} p-5 text-white relative`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white font-extrabold text-xl shadow-inner shrink-0">
                            {school.name?.charAt(0)}
                          </div>
                          <div>
                            <h3 className="font-cairo font-black text-base leading-tight line-clamp-1 text-white">{school.name}</h3>
                            <p className="text-xs text-white/80 font-mono mt-0.5">{school.code || school.name_en || '—'}</p>
                          </div>
                        </div>
                        <Badge className={`text-[10px] font-bold ${SCHOOL_STATUS[school.status]?.badge || 'bg-white/20 text-white'}`}>
                          {isRTL ? SCHOOL_STATUS[school.status]?.label : SCHOOL_STATUS[school.status]?.label_en}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-4 mt-3.5 text-xs text-white/85">
                        <span className="flex items-center gap-1 font-medium">
                          <MapPin className="h-3.5 w-3.5" />
                          {school.city || '—'}
                        </span>
                        <span className="flex items-center gap-1 font-medium">
                          <Building2 className="h-3.5 w-3.5" />
                          {school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}
                        </span>
                      </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="p-5 grid grid-cols-3 gap-3 text-center border-b border-slate-100 dark:border-slate-800">
                      <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-2xl">
                        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium mb-1">{isRTL ? 'الطلاب' : 'Students'}</p>
                        <p className="text-base font-black text-blue-600 dark:text-blue-400">{school.student_count || 0}</p>
                      </div>
                      <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-2xl">
                        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium mb-1">{isRTL ? 'المعلمين' : 'Teachers'}</p>
                        <p className="text-base font-black text-purple-600 dark:text-purple-400">{school.teacher_count || 0}</p>
                      </div>
                      <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-2xl">
                        <p className="text-xs text-slate-500 dark:text-slate-400 font-medium mb-1">{isRTL ? 'الفصول' : 'Classes'}</p>
                        <p className="text-base font-black text-emerald-600 dark:text-emerald-400">{school.class_count || 0}</p>
                      </div>
                    </div>
                  </div>

                  {/* Actions Footer */}
                  <div className="p-4 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between gap-2.5">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-xl h-10 px-4 font-bold text-xs border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                      onClick={() => navigate(`/platform/schools/${school.id}`)}
                    >
                      <ExternalLink className="h-3.5 w-3.5 me-1.5 text-slate-500" />
                      {isRTL ? 'الملف التفصيلي' : 'Details'}
                    </Button>

                    <Button
                      size="sm"
                      className="rounded-xl h-10 px-5 bg-[#1C3D74] hover:bg-[#152e57] text-white font-extrabold text-xs shadow-md shadow-[#1C3D74]/20 disabled:opacity-40"
                      onClick={() => handleEnterSchoolDashboard(school)}
                      disabled={!canOpenPrincipalDashboard(school)}
                    >
                      <Eye className="h-4 w-4 me-1.5 text-[#00C5B2]" />
                      {isRTL ? 'دخول كمدير' : 'Open Dashboard'}
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}

        </div>
      </div>

      {/* Suspend Confirmation Dialog */}
      <Dialog open={!!showSuspendDialog} onOpenChange={() => setShowSuspendDialog(null)}>
        <DialogContent className="rounded-3xl bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="font-cairo text-lg font-black text-rose-600 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              {isRTL ? 'إيقاف حساب المدرسة' : 'Suspend School'}
            </DialogTitle>
            <DialogDescription className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              {isRTL
                ? `سيتم إيقاف وصول منسوبي ${showSuspendDialog?.name} للنظام مؤقتاً.`
                : `This will suspend access for all users of ${showSuspendDialog?.name}.`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <label className="text-xs font-bold text-slate-800 dark:text-slate-200">
              {isRTL ? 'سبب الإيقاف (مطلوب)' : 'Suspension Reason (Required)'}
            </label>
            <Textarea
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              placeholder={isRTL ? 'اكتب سبب الإيقاف هنا...' : 'Enter reason for suspension...'}
              className="rounded-xl text-xs bg-slate-50 dark:bg-slate-950 font-medium min-h-[80px]"
            />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowSuspendDialog(null)} className="rounded-xl text-xs font-bold">
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={handleSuspendConfirm}
              disabled={actionLoading}
              className="rounded-xl text-xs font-extrabold bg-rose-600 hover:bg-rose-700 text-white"
            >
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (isRTL ? 'تأكيد الإيقاف' : 'Confirm Suspend')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Activate Confirmation Dialog */}
      <Dialog open={!!showActivateDialog} onOpenChange={() => setShowActivateDialog(null)}>
        <DialogContent className="rounded-3xl bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 max-w-md">
          <DialogHeader>
            <DialogTitle className="font-cairo text-lg font-black text-emerald-600 flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5" />
              {isRTL ? 'تفعيل حساب المدرسة' : 'Activate School'}
            </DialogTitle>
            <DialogDescription className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              {isRTL
                ? `سيتم إعادة تفعيل صلاحيات ${showActivateDialog?.name} فوراً.`
                : `This will reactivate access for ${showActivateDialog?.name}.`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <label className="text-xs font-bold text-slate-800 dark:text-slate-200">
              {isRTL ? 'ملاحظة التفعيل (مطلوب)' : 'Activation Note (Required)'}
            </label>
            <Textarea
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              placeholder={isRTL ? 'اكتب ملاحظة التفعيل هنا...' : 'Enter activation notes...'}
              className="rounded-xl text-xs bg-slate-50 dark:bg-slate-950 font-medium min-h-[80px]"
            />
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowActivateDialog(null)} className="rounded-xl text-xs font-bold">
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={handleActivateConfirm}
              disabled={actionLoading}
              className="rounded-xl text-xs font-extrabold bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : (isRTL ? 'تأكيد التفعيل' : 'Confirm Activate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create School Wizard Modal */}
      <Suspense fallback={null}>
        {showCreateWizard && (
          <CreateSchoolWizard
            open={showCreateWizard}
            onOpenChange={setShowCreateWizard}
            onSuccess={handleSchoolCreated}
            api={api}
            isRTL={isRTL}
          />
        )}
      </Suspense>
    </Sidebar>
  );
}
