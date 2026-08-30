import React, { useState, useEffect, useRef, useCallback, useMemo, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { usePlatformAdminSchoolPreview } from '@/shared/hooks/usePlatformAdminSchoolPreview';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';
import { Loader2 } from 'lucide-react';

// Sub-components
import TenantsHeroStats from '../components/TenantsHeroStats';
import TenantsFilterBar from '../components/TenantsFilterBar';
import TenantsDraftsSection from '../components/TenantsDraftsSection';
import SchoolCardGrid from '../components/SchoolCardGrid';
import SchoolTableView from '../components/SchoolTableView';
import SchoolActionDialogs from '../components/SchoolActionDialogs';
import { SCHOOL_STATUS } from '../constants/schoolConstants';

const CreateSchoolWizard = lazy(() => import('@/admin/features/schools/components/CreateSchoolWizard'));

export default function TenantsManagement() {
  const { api, isRTL: contextIsRTL } = useAuth();
  const { openPrincipalDashboard, canOpenPrincipalDashboard } = usePlatformAdminSchoolPreview();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { nassaqError } = useNassaqAlert();
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

  // Sorting
  const [sortBy, setSortBy] = useState('name_asc');

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
        if (showToast) toast.success(t('dataRefreshed') || (isRTL ? 'تم تحديث البيانات بنجاح' : 'Data refreshed'));
      } catch (error) {
        console.error('Error fetching schools:', error);
        nassaqError(t('errorLoadingSchools') || (isRTL ? 'خطأ في تحميل المدارس' : 'Error loading schools'));
      } finally {
        setLoading(false);
        setRefreshing(false);
        fetchSchoolsInFlightRef.current = null;
      }
    })();

    fetchSchoolsInFlightRef.current = task;
    return task;
  }, [api, isRTL, nassaqError, t]);

  useEffect(() => {
    fetchSchools();
  }, [fetchSchools]);

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

    if (searchQuery.trim()) {
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

    // Sort
    if (sortBy === 'name_asc') {
      result.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ar'));
    } else if (sortBy === 'name_desc') {
      result.sort((a, b) => (b.name || '').localeCompare(a.name || '', 'ar'));
    } else if (sortBy === 'students_desc') {
      result.sort((a, b) => (b.student_count || 0) - (a.student_count || 0));
    } else if (sortBy === 'teachers_desc') {
      result.sort((a, b) => (b.teacher_count || 0) - (a.teacher_count || 0));
    } else if (sortBy === 'classes_desc') {
      result.sort((a, b) => (b.class_count || 0) - (a.class_count || 0));
    } else if (sortBy === 'newest') {
      result.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    }

    return result;
  }, [schools, searchQuery, filters, activeStatusFilter, sortBy]);

  const totalPages = Math.ceil(filteredSchools.length / itemsPerPage) || 1;
  const paginatedSchools = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredSchools.slice(start, start + itemsPerPage);
  }, [filteredSchools, currentPage, itemsPerPage]);

  const cities = useMemo(() => [...new Set(schools.map(s => s.city).filter(Boolean))], [schools]);

  const stats = useMemo(() => ({
    total: schools.filter(s => s.status !== 'setup').length,
    active: schools.filter(s => s.status === 'active').length,
    suspended: schools.filter(s => s.status === 'suspended').length,
    pending: schools.filter(s => s.status === 'pending').length,
    drafts: draftSchools.length,
    totalStudents: schools.reduce((sum, s) => sum + (s.student_count || 0), 0),
    totalTeachers: schools.reduce((sum, s) => sum + (s.teacher_count || 0), 0),
    totalClasses: schools.reduce((sum, s) => sum + (s.class_count || 0), 0),
  }), [schools, draftSchools.length]);

  const resetFilters = () => {
    setFilters({ status: 'all', city: 'all', schoolType: 'all', stage: 'all' });
    setSearchQuery('');
    setActiveStatusFilter(null);
    setSortBy('name_asc');
    setCurrentPage(1);
  };

  const handleStatusFilter = (status) => {
    setActiveStatusFilter(prev => prev === status ? null : status);
    setCurrentPage(1);
  };

  const handleEnterSchoolDashboard = (school) => openPrincipalDashboard(school);

  const handleSuspendConfirm = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired') || (isRTL ? 'سبب الإيقاف مطلوب' : 'Suspension reason is required'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${showSuspendDialog.id}/suspend`, { reason: actionReason });
      setSchools(prev => prev.map(s =>
        s.id === showSuspendDialog.id ? { ...s, status: 'suspended' } : s
      ));
      toast.success(isRTL ? `تم إيقاف مدرسة "${showSuspendDialog.name}" بنجاح` : `"${showSuspendDialog.name}" suspended successfully`);
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
      nassaqError(t('reasonIsRequired2') || (isRTL ? 'سبب التفعيل مطلوب' : 'Activation note is required'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${showActivateDialog.id}/activate`, { reason: actionReason });
      setSchools(prev => prev.map(s =>
        s.id === showActivateDialog.id ? { ...s, status: 'active' } : s
      ));
      toast.success(isRTL ? `تم تفعيل مدرسة "${showActivateDialog.name}" بنجاح` : `"${showActivateDialog.name}" activated successfully`);
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
      nassaqError(getApiErrorMessage(err) || (t('failedToDeleteDraft') || (isRTL ? 'فشل حذف المسودة' : 'Failed to delete draft')));
    } finally {
      setDeletingDraftId(null);
    }
  };

  const exportToCSV = () => {
    try {
      const headers = ['اسم المدرسة', 'كود المدرسة', 'المدينة', 'المنطقة', 'الحالة', 'نوع المدرسة', 'المرحلة', 'عدد الطلاب', 'عدد المعلمين', 'عدد الفصول'];
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
        s.class_count || 0,
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

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center bg-slate-50/70 dark:bg-slate-950">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 rounded-3xl bg-[#1C3D74]/10 dark:bg-[#46C1BE]/10 flex items-center justify-center mx-auto border border-[#46C1BE]/30 shadow-lg">
              <Loader2 className="h-8 w-8 animate-spin text-[#46C1BE]" />
            </div>
            <p className="text-base font-cairo font-bold text-slate-700 dark:text-slate-300">
              {t('loadingSchools') || (isRTL ? 'جاري تحميل منظومة المدارس...' : 'Loading schools ecosystem...')}
            </p>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50/80 via-slate-50/50 to-slate-100/40 dark:from-slate-950 dark:via-slate-950 dark:to-slate-900 font-tajawal" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">

          {/* 1. Hero Statistics & Actions */}
          <TenantsHeroStats
            stats={stats}
            onRefresh={() => fetchSchools(true)}
            refreshing={refreshing}
            onExport={exportToCSV}
            onOpenCreateWizard={() => setShowCreateWizard(true)}
            isRTL={isRTL}
          />

          {/* 2. Control Bar (Search, Filters, Sort, View Modes) */}
          <TenantsFilterBar
            searchQuery={searchQuery}
            onSearchChange={(q) => {
              setSearchQuery(q);
              setCurrentPage(1);
            }}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            showFilters={showFilters}
            onToggleFilters={() => setShowFilters(!showFilters)}
            filters={filters}
            onFilterChange={(key, val) => {
              setFilters(prev => ({ ...prev, [key]: val }));
              setCurrentPage(1);
            }}
            onResetFilters={resetFilters}
            activeStatusFilter={activeStatusFilter}
            onStatusFilterChange={handleStatusFilter}
            cities={cities}
            sortBy={sortBy}
            onSortChange={(val) => {
              setSortBy(val);
              setCurrentPage(1);
            }}
            totalResultsCount={filteredSchools.length}
            isRTL={isRTL}
          />

          {/* 3. Setup Drafts Banner */}
          {draftSchools.length > 0 && activeStatusFilter !== 'active' && activeStatusFilter !== 'suspended' && (
            <TenantsDraftsSection
              draftSchools={draftSchools}
              showDrafts={showDrafts}
              onToggleShowDrafts={() => setShowDrafts(!showDrafts)}
              onNavigateToDraft={(id) => navigate(`/platform/schools/${id}`)}
              onDeleteDraft={handleDeleteDraft}
              deletingDraftId={deletingDraftId}
              isRTL={isRTL}
            />
          )}

          {/* 4. Schools Display (Card Grid or Table View) */}
          {viewMode === 'table' ? (
            <SchoolTableView
              schools={filteredSchools}
              paginatedSchools={paginatedSchools}
              currentPage={currentPage}
              totalPages={totalPages}
              itemsPerPage={itemsPerPage}
              onPageChange={setCurrentPage}
              onItemsPerPageChange={(val) => {
                setItemsPerPage(val);
                setCurrentPage(1);
              }}
              onNavigateDetail={(id) => navigate(`/platform/schools/${id}`)}
              onEnterDashboard={handleEnterSchoolDashboard}
              canEnterDashboard={canOpenPrincipalDashboard}
              onOpenSuspendDialog={(school) => {
                setShowSuspendDialog(school);
                setActionReason('');
              }}
              onOpenActivateDialog={(school) => {
                setShowActivateDialog(school);
                setActionReason('');
              }}
              onResetFilters={resetFilters}
              onOpenCreateWizard={() => setShowCreateWizard(true)}
              isRTL={isRTL}
            />
          ) : (
            <SchoolCardGrid
              schools={filteredSchools}
              onNavigateDetail={(id) => navigate(`/platform/schools/${id}`)}
              onEnterDashboard={handleEnterSchoolDashboard}
              canEnterDashboard={canOpenPrincipalDashboard}
              onOpenSuspendDialog={(school) => {
                setShowSuspendDialog(school);
                setActionReason('');
              }}
              onOpenActivateDialog={(school) => {
                setShowActivateDialog(school);
                setActionReason('');
              }}
              onResetFilters={resetFilters}
              onOpenCreateWizard={() => setShowCreateWizard(true)}
              isRTL={isRTL}
            />
          )}

        </div>
      </div>

      {/* 5. Modals & Action Dialogs */}
      <SchoolActionDialogs
        suspendDialogSchool={showSuspendDialog}
        onCloseSuspendDialog={() => setShowSuspendDialog(null)}
        onConfirmSuspend={handleSuspendConfirm}
        activateDialogSchool={showActivateDialog}
        onCloseActivateDialog={() => setShowActivateDialog(null)}
        onConfirmActivate={handleActivateConfirm}
        actionReason={actionReason}
        onChangeActionReason={setActionReason}
        actionLoading={actionLoading}
        isRTL={isRTL}
      />

      {/* 6. Create School Wizard Modal */}
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
