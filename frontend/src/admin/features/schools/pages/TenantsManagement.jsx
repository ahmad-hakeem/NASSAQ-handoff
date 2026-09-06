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
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [serverStats, setServerStats] = useState(null);
  const [serverDrafts, setServerDrafts] = useState([]);
  const [serverCities, setServerCities] = useState([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'table'
  const [showFilters, setShowFilters] = useState(false);
  const [showCreateWizard, setShowCreateWizard] = useState(false);
  const [selectedDraftForEdit, setSelectedDraftForEdit] = useState(null);
  const [activeStatusFilter, setActiveStatusFilter] = useState(null);
  const [showSuspendDialog, setShowSuspendDialog] = useState(null);
  const [showActivateDialog, setShowActivateDialog] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const [showDrafts, setShowDrafts] = useState(true);
  const [deletingDraftId, setDeletingDraftId] = useState(null);

  // Sorting
  const [sortBy, setSortBy] = useState('name_asc');

  // Pagination for table and grid view
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);

  // Advanced Filters
  const [filters, setFilters] = useState({
    status: 'all',
    city: 'all',
    schoolType: 'all',
    stage: 'all',
  });

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchSchoolsInFlightRef = useRef(null);

  const fetchStatsAndDrafts = useCallback(async () => {
    try {
      const [draftsRes, statsRes] = await Promise.all([
        api.get('/schools/draft'),
        api.get('/schools/numbers'),
      ]);
      setServerDrafts(draftsRes.data || []);
      if (statsRes.data) setServerStats(statsRes.data);
    } catch (error) {
      console.error('Error fetching stats and drafts:', error);
    }
  }, [api]);

  const fetchSchools = useCallback(async (showToast = false, pageOverride = null) => {
    if (!showToast && fetchSchoolsInFlightRef.current) return fetchSchoolsInFlightRef.current;
    if (showToast) setRefreshing(true);

    const pageToFetch = pageOverride !== null ? pageOverride : currentPage;

    const task = (async () => {
      try {
        const params = {
          page: pageToFetch,
          limit: itemsPerPage,
        };

        if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
        if (activeStatusFilter) {
          params.status = activeStatusFilter;
        } else if (filters.status !== 'all') {
          params.status = filters.status;
        }
        if (filters.city !== 'all') params.city = filters.city;
        if (filters.schoolType !== 'all') params.school_type = filters.schoolType;
        if (filters.stage !== 'all') params.stage = filters.stage;
        if (sortBy) params.sort_by = sortBy;

        const schoolsRes = await api.get('/schools', { params });

        const rawData = schoolsRes.data || {};
        const schoolsData = Array.isArray(rawData) ? rawData : (rawData.schools || []);
        const total = rawData.total !== undefined ? rawData.total : schoolsData.length;
        const totalPagesCount = rawData.total_pages || Math.ceil(total / itemsPerPage) || 1;

        setSchools(schoolsData);
        setTotalCount(total);
        setTotalPages(totalPagesCount);
        if (rawData.cities && rawData.cities.length > 0) setServerCities(rawData.cities);

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
  }, [api, isRTL, nassaqError, t, currentPage, itemsPerPage, debouncedSearch, activeStatusFilter, filters, sortBy]);

  useEffect(() => {
    fetchStatsAndDrafts();
  }, [fetchStatsAndDrafts]);

  useEffect(() => {
    fetchSchools();
  }, [fetchSchools]);

  const draftSchools = useMemo(() => {
    if (serverDrafts && serverDrafts.length > 0) return serverDrafts;
    return schools.filter(s => s.status === 'setup');
  }, [serverDrafts, schools]);

  const cities = useMemo(() => {
    if (serverCities && serverCities.length > 0) return serverCities;
    const unique = [...new Set(schools.map(s => s.city).filter(Boolean))];
    unique.sort((a, b) => a.localeCompare(b, isRTL ? 'ar' : 'en'));
    return unique;
  }, [serverCities, schools, isRTL]);

  const stats = useMemo(() => {
    if (serverStats) {
      return {
        total: serverStats.total ?? serverStats.total_schools ?? schools.filter(s => s.status !== 'setup').length,
        active: serverStats.active ?? serverStats.active_schools ?? schools.filter(s => s.status === 'active').length,
        suspended: serverStats.suspended ?? serverStats.suspended_schools ?? schools.filter(s => s.status === 'suspended').length,
        pending: serverStats.pending ?? serverStats.pending_schools ?? schools.filter(s => s.status === 'pending').length,
        drafts: serverStats.drafts ?? serverStats.draft_schools ?? draftSchools.length,
        totalStudents: serverStats.totalStudents ?? serverStats.total_students ?? schools.reduce((sum, s) => sum + (s.student_count || s.current_students || 0), 0),
        totalTeachers: serverStats.totalTeachers ?? serverStats.total_teachers ?? schools.reduce((sum, s) => sum + (s.teacher_count || s.current_teachers || 0), 0),
        totalClasses: serverStats.totalClasses ?? serverStats.total_classes ?? schools.reduce((sum, s) => sum + (s.class_count || 0), 0),
      };
    }
    return {
      total: schools.filter(s => s.status !== 'setup').length,
      active: schools.filter(s => s.status === 'active').length,
      suspended: schools.filter(s => s.status === 'suspended').length,
      pending: schools.filter(s => s.status === 'pending').length,
      drafts: draftSchools.length,
      totalStudents: schools.reduce((sum, s) => sum + (s.student_count || s.current_students || 0), 0),
      totalTeachers: schools.reduce((sum, s) => sum + (s.teacher_count || s.current_teachers || 0), 0),
      totalClasses: schools.reduce((sum, s) => sum + (s.class_count || 0), 0),
    };
  }, [serverStats, schools, draftSchools.length]);

  const filteredSchools = schools;
  const paginatedSchools = schools;

  const resetFilters = () => {
    setFilters({ status: 'all', city: 'all', schoolType: 'all', stage: 'all' });
    setSearchQuery('');
    setDebouncedSearch('');
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
    const reason = actionReason.trim() || (isRTL ? 'إيقاف إداري مؤقت' : 'Temporary administrative suspension');
    setActionLoading(true);
    try {
      await api.post(`/schools/${showSuspendDialog.id}/suspend`, { reason });
      setSchools(prev => prev.map(s =>
        s.id === showSuspendDialog.id ? { ...s, status: 'suspended' } : s
      ));
      toast.success(isRTL ? `تم إيقاف مدرسة "${showSuspendDialog.name}" بنجاح` : `"${showSuspendDialog.name}" suspended successfully`);
      setShowSuspendDialog(null);
      setActionReason('');
      fetchSchools();
      fetchStatsAndDrafts();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (isRTL ? 'فشل إيقاف المدرسة' : 'Failed to suspend school'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivateConfirm = async () => {
    const reason = actionReason.trim() || (isRTL ? 'إعادة تفعيل المدرسة' : 'Reactivate school');
    setActionLoading(true);
    try {
      await api.post(`/schools/${showActivateDialog.id}/activate`, { reason });
      setSchools(prev => prev.map(s =>
        s.id === showActivateDialog.id ? { ...s, status: 'active' } : s
      ));
      toast.success(isRTL ? `تم تفعيل مدرسة "${showActivateDialog.name}" بنجاح` : `"${showActivateDialog.name}" activated successfully`);
      setShowActivateDialog(null);
      setActionReason('');
      fetchSchools();
      fetchStatsAndDrafts();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (isRTL ? 'فشل تفعيل المدرسة' : 'Failed to activate school'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleSchoolCreated = () => {
    setSelectedDraftForEdit(null);
    setShowCreateWizard(false);
    setShowDrafts(true);
    setActiveStatusFilter(null);
    fetchSchools(true);
    fetchStatsAndDrafts();
  };

  const handleResumeDraft = async (draft) => {
    try {
      const res = await api.get(`/schools/${draft.id}`);
      setSelectedDraftForEdit(res.data || draft);
    } catch (err) {
      console.warn('Could not fetch fresh draft details, using local data:', err);
      setSelectedDraftForEdit(draft);
    }
    setShowCreateWizard(true);
  };

  const handleDeleteDraft = async (draft) => {
    setDeletingDraftId(draft.id);
    try {
      await api.delete(`/schools/${draft.id}/draft`);
      setSchools(prev => prev.filter(s => s.id !== draft.id));
      toast.success(isRTL ? `تم حذف مسودة "${draft.name}"` : `Draft "${draft.name}" deleted`);
      fetchSchools();
      fetchStatsAndDrafts();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || (t('failedToDeleteDraft') || (isRTL ? 'فشل حذف المسودة' : 'Failed to delete draft')));
    } finally {
      setDeletingDraftId(null);
    }
  };

  const handleRefreshAll = useCallback(async () => {
    await Promise.all([
      fetchSchools(true),
      fetchStatsAndDrafts(),
    ]);
  }, [fetchSchools, fetchStatsAndDrafts]);

  const exportToCSV = async () => {
    try {
      let exportData = schools;
      try {
        const fullRes = await api.get('/schools');
        if (Array.isArray(fullRes.data)) {
          exportData = fullRes.data;
        } else if (Array.isArray(fullRes.data?.schools)) {
          exportData = fullRes.data.schools;
        }
      } catch (err) {
        console.warn('Export fallback to current page:', err);
      }
      const headers = ['اسم المدرسة', 'كود المدرسة', 'المدينة', 'المنطقة', 'الحالة', 'نوع المدرسة', 'المرحلة', 'عدد الطلاب', 'عدد المعلمين', 'عدد الفصول'];
      const rows = exportData.map(s => [
        `"${s.name || ''}"`,
        `"${s.code || ''}"`,
        `"${s.city || ''}"`,
        `"${s.region || ''}"`,
        `"${SCHOOL_STATUS[s.status]?.label || s.status}"`,
        `"${s.school_type === 'private' ? 'أهلية' : 'حكومية'}"`,
        `"${s.stage || ''}"`,
        s.student_count || s.current_students || 0,
        s.teacher_count || s.current_teachers || 0,
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
            onRefresh={handleRefreshAll}
            refreshing={refreshing}
            onExport={exportToCSV}
            onOpenCreateWizard={() => {
              setSelectedDraftForEdit(null);
              setShowCreateWizard(true);
            }}
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
            totalResultsCount={totalCount}
            isRTL={isRTL}
          />

          {/* 3. Setup Drafts Banner */}
          {draftSchools.length > 0 && activeStatusFilter !== 'active' && activeStatusFilter !== 'suspended' && (
            <TenantsDraftsSection
              draftSchools={draftSchools}
              showDrafts={showDrafts}
              onToggleShowDrafts={() => setShowDrafts(!showDrafts)}
              onNavigateToDraft={handleResumeDraft}
              onDeleteDraft={handleDeleteDraft}
              deletingDraftId={deletingDraftId}
              isRTL={isRTL}
            />
          )}

          {/* 4. Schools Display (Card Grid or Table View) */}
          {viewMode === 'table' ? (
            <SchoolTableView
              schools={paginatedSchools}
              paginatedSchools={paginatedSchools}
              currentPage={currentPage}
              totalPages={totalPages}
              totalCount={totalCount}
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
              onOpenCreateWizard={() => {
                setSelectedDraftForEdit(null);
                setShowCreateWizard(true);
              }}
              isRTL={isRTL}
            />
          ) : (
            <SchoolCardGrid
              schools={paginatedSchools}
              currentPage={currentPage}
              totalPages={totalPages}
              totalCount={totalCount}
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
              onOpenCreateWizard={() => {
                setSelectedDraftForEdit(null);
                setShowCreateWizard(true);
              }}
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
            onOpenChange={(isOpen) => {
              setShowCreateWizard(isOpen);
              if (!isOpen) setSelectedDraftForEdit(null);
            }}
            draftSchool={selectedDraftForEdit}
            onSuccess={handleSchoolCreated}
            api={api}
            isRTL={isRTL}
          />
        )}
      </Suspense>
    </Sidebar>
  );
}
