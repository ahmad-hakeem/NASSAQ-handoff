import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '../components/ui/sheet';
import {
  Building2, Search, Filter, Plus, LayoutGrid, List, Users, GraduationCap,
  MapPin, Brain, Eye, Pause, Play, RefreshCw, CheckCircle2, XCircle,
  AlertTriangle, Clock, ArrowLeft, ChevronRight, School, Sparkles, X,
  Loader2, Layers, Calendar, Activity, UserCheck, Hash, ExternalLink,
  FileEdit, Trash2, ChevronDown, ChevronUp,
} from 'lucide-react';
import { Textarea } from '../components/ui/textarea';
import CreateSchoolWizard from '../components/wizards/CreateSchoolWizard';
import { Sidebar } from '../components/layout/Sidebar';

const SCHOOL_STATUS = {
  active: { label: 'نشطة', label_en: 'Active', color: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  suspended: { label: 'موقوفة', label_en: 'Suspended', color: 'bg-red-500', badge: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  setup: { label: 'قيد الإعداد', label_en: 'Setup', color: 'bg-amber-500', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  pending: { label: 'معلقة', label_en: 'Pending', color: 'bg-slate-500', badge: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300' },
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
  const { api, isRTL: contextIsRTL, enterSchoolContext } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const isRTL = contextIsRTL !== false;

  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [showCreateWizard, setShowCreateWizard] = useState(false);
  const [activeStatusFilter, setActiveStatusFilter] = useState(null);
  const [showSuspendDialog, setShowSuspendDialog] = useState(null);
  const [showActivateDialog, setShowActivateDialog] = useState(null);
  const [actionReason, setActionReason] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const [showDrafts, setShowDrafts] = useState(true);
  const [deletingDraftId, setDeletingDraftId] = useState(null);

  const [filters, setFilters] = useState({
    status: 'all',
    city: 'all',
  });

  const fetchSchools = useCallback(async (showToast = false) => {
    if (showToast) setRefreshing(true);
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
          status: s.status || 'active',
          city: s.city || '',
          region: s.region || '',
          school_type: s.type || s.school_type || '',
          stage: s.stage || '',
          student_count: s.student_count || s.current_students || 0,
          teacher_count: s.teacher_count || s.current_teachers || 0,
          class_count: s.class_count || 0,
          parent_count: s.parent_count || 0,
          sessions_today: 0,
          setup_score: 50,
          has_timetable: false,
          created_at: s.created_at || '',
          last_activity: s.updated_at || s.created_at || '',
        }));
      }
      setSchools(schoolsData);
      if (showToast) toast.success(t('dataRefreshed'));
    } catch (error) {
      console.error('Error fetching schools:', error);
      nassaqError(t('errorLoadingSchools'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, isRTL]);

  useEffect(() => { fetchSchools(); }, [fetchSchools]);

  const draftSchools = React.useMemo(() => schools.filter(s => s.status === 'setup'), [schools]);

  const filteredSchools = React.useMemo(() => {
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
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s =>
        s.name?.toLowerCase().includes(q) ||
        s.name_en?.toLowerCase().includes(q) ||
        s.city?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [schools, searchQuery, filters, activeStatusFilter]);

  const cities = [...new Set(schools.map(s => s.city).filter(Boolean))];

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
    setFilters({ status: 'all', city: 'all' });
    setSearchQuery('');
    setActiveStatusFilter(null);
  };

  const handleStatusFilter = (status) => {
    setActiveStatusFilter(prev => prev === status ? null : status);
  };

  const handleEnterSchoolDashboard = async (school) => {
    if (!school?.id) {
      nassaqError(t('errorInvalidSchoolData'));
      return;
    }
    // Task #511: enterSchoolContext now mints an impersonation token
    // via /role-switch/switch (MFA step-up handled by the axios
    // interceptor). Only post-step-up failures surface here.
    try {
      await enterSchoolContext(school);
    } catch (err) {
      const dt = err?.response?.data?.detail;
      nassaqError(typeof dt === 'string' ? dt : t('errorSwitchingRole'));
      return;
    }
    toast.success(
      isRTL ? `تم الدخول إلى ${school.name} كمدير مدرسة` : `Entered ${school.name_en || school.name} as School Manager`
    );
    navigate('/principal');
  };

  const handleSuspendConfirm = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired'));
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/schools/${showSuspendDialog.id}/suspend`, { reason: actionReason });
      setSchools(prev => prev.map(s =>
        s.id === showSuspendDialog.id ? { ...s, status: 'suspended' } : s
      ));
      toast.success(isRTL ? `تم تعليق ${showSuspendDialog.name}` : `${showSuspendDialog.name} suspended`);
      setShowSuspendDialog(null);
      setActionReason('');
    } catch (err) {
      nassaqError(err.response?.data?.detail || (isRTL ? 'فشل تعليق المدرسة' : 'Failed to suspend school'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivateConfirm = async () => {
    if (!actionReason.trim()) {
      nassaqError(t('reasonIsRequired2'));
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
      nassaqError(err.response?.data?.detail || (isRTL ? 'فشل تفعيل المدرسة' : 'Failed to activate school'));
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
      nassaqError(err.response?.data?.detail || (t('failedToDeleteDraft')));
    } finally {
      setDeletingDraftId(null);
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
            <Loader2 className="h-12 w-12 animate-spin text-brand-turquoise mx-auto" />
            <p className="text-lg font-cairo text-slate-600 dark:text-slate-400">
              {t('loadingSchools')}
            </p>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">

          {/* Hero Section */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple p-6 sm:p-8 text-white shadow-2xl">
            <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0zNiAxOGMwLTkuOTQtOC4wNi0xOC0xOC0xOFYwYzE5Ljg4IDAgMzYgMTYuMTIgMzYgMzZ6IiBmaWxsPSJyZ2JhKDI1NSwyNTUsMjU1LDAuMDMpIi8+PC9nPjwvc3ZnPg==')] opacity-30" />
            <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/10 rounded-xl backdrop-blur-sm">
                    <Building2 className="h-6 w-6" />
                  </div>
                  <div>
                    <h1 className="text-2xl sm:text-3xl font-bold font-cairo">{t('tenantsPageTitle')}</h1>
                    <p className="text-white/70 text-sm font-tajawal">{t('tenantsPageSubtitle')}</p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline" size="sm"
                  className="border-white/20 text-white hover:bg-white/10"
                  onClick={() => fetchSchools(true)}
                  disabled={refreshing}
                >
                  <RefreshCw className={`h-4 w-4 me-1.5 ${refreshing ? 'animate-spin' : ''}`} />
                  {t('refresh')}
                </Button>
                <Button
                  size="sm"
                  className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
                  onClick={() => setShowCreateWizard(true)}
                >
                  <Plus className="h-4 w-4 me-1.5" />
                  {t('addSchool')}
                </Button>
              </div>
            </div>

            {/* Stats Row */}
            <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              {[
                { label: t('totalSchools'), value: stats.total, icon: Building2, onClick: () => setActiveStatusFilter(null) },
                { label: t('activeSchools'), value: stats.active, icon: CheckCircle2, onClick: () => handleStatusFilter('active'), active: activeStatusFilter === 'active', color: 'text-emerald-400' },
                { label: t('suspendedSchools'), value: stats.suspended, icon: XCircle, onClick: () => handleStatusFilter('suspended'), active: activeStatusFilter === 'suspended', color: 'text-red-400' },
                { label: t('pendingSchools'), value: stats.pending, icon: Clock, onClick: () => handleStatusFilter('pending'), active: activeStatusFilter === 'pending', color: 'text-amber-400' },
                { label: t('totalStudents'), value: stats.totalStudents.toLocaleString(), icon: GraduationCap },
                { label: t('totalTeachers'), value: stats.totalTeachers, icon: UserCheck },
                { label: t('totalClasses'), value: stats.totalClasses, icon: Layers },
              ].map((item, i) => (
                <button
                  key={i}
                  onClick={item.onClick}
                  className={`bg-white/10 backdrop-blur-sm rounded-xl p-3 text-center transition-all hover:bg-white/20 ${item.active ? 'ring-2 ring-white/50 bg-white/20' : ''}`}
                >
                  <item.icon className={`h-5 w-5 mx-auto mb-1 ${item.color || 'text-brand-turquoise'}`} />
                  <p className="text-xl font-bold">{item.value}</p>
                  <p className="text-[10px] text-white/60">{item.label}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Active Filter Indicator */}
          {activeStatusFilter && (
            <div className="p-3 bg-brand-purple/10 border border-brand-purple/30 rounded-xl flex items-center justify-between">
              <span className="text-sm font-medium text-brand-purple flex items-center gap-2">
                <Filter className="h-4 w-4" />
                {isRTL ? `عرض المدارس ${SCHOOL_STATUS[activeStatusFilter]?.label || ''}` : `Showing ${SCHOOL_STATUS[activeStatusFilter]?.label_en || ''} schools`}
              </span>
              <Button variant="ghost" size="sm" onClick={() => setActiveStatusFilter(null)} className="text-brand-purple hover:bg-brand-purple/20 hover:text-brand-purple focus-visible:text-brand-purple">
                <X className="h-4 w-4 me-1" />
                {isRTL ? 'إلغاء' : 'Clear'}
              </Button>
            </div>
          )}

          {/* Search & Filters Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="ps-10 rounded-xl border-slate-200 dark:border-slate-700"
              />
              {searchQuery && (
                <Button variant="ghost" size="icon" className="absolute end-1 top-1/2 -translate-y-1/2 h-7 w-7" onClick={() => setSearchQuery('')}>
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>

            <div className="hidden sm:flex items-center gap-2">
              <Select value={filters.status} onValueChange={(v) => { setFilters(f => ({ ...f, status: v })); setActiveStatusFilter(null); }}>
                <SelectTrigger className="w-36 rounded-xl">
                  <SelectValue placeholder={t('status')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allStatus')}</SelectItem>
                  <SelectItem value="active">{t('active')}</SelectItem>
                  <SelectItem value="suspended">{t('suspended')}</SelectItem>
                  <SelectItem value="pending">{t('pending')}</SelectItem>
                </SelectContent>
              </Select>

              <Select value={filters.city} onValueChange={(v) => setFilters(f => ({ ...f, city: v }))}>
                <SelectTrigger className="w-36 rounded-xl">
                  <SelectValue placeholder={t('city')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allCities')}</SelectItem>
                  {cities.map(city => (
                    <SelectItem key={city} value={city}>{city}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button variant="outline" size="sm" onClick={resetFilters} className="rounded-xl">
                <RefreshCw className="h-4 w-4 me-1.5" />
                {t('reset')}
              </Button>

              <div className="flex items-center border rounded-xl overflow-hidden ms-1">
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} size="icon" className="rounded-none h-9 w-9" onClick={() => setViewMode('grid')}>
                  <LayoutGrid className="h-4 w-4" />
                </Button>
                <Button variant={viewMode === 'table' ? 'default' : 'ghost'} size="icon" className="rounded-none h-9 w-9" onClick={() => setViewMode('table')}>
                  <List className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <Button variant="outline" size="icon" className="sm:hidden rounded-xl" onClick={() => setShowFilters(true)}>
              <Filter className="h-5 w-5" />
            </Button>
          </div>

          {/* Drafts Section */}
          {draftSchools.length > 0 && !activeStatusFilter && (
            <div className="space-y-3">
              <button
                onClick={() => setShowDrafts(p => !p)}
                className="w-full flex items-center justify-between p-3 rounded-xl bg-amber-50 dark:bg-amber-950/20 border-2 border-dashed border-amber-300 dark:border-amber-700 hover:bg-amber-100 dark:hover:bg-amber-950/30 transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center">
                    <FileEdit className="h-5 w-5 text-amber-600" />
                  </div>
                  <div className="text-start">
                    <p className="text-sm font-bold text-amber-800 dark:text-amber-300 font-cairo">
                      {isRTL ? `مسودات الإنشاء (${draftSchools.length})` : `School Drafts (${draftSchools.length})`}
                    </p>
                    <p className="text-xs text-amber-600/70 dark:text-amber-400/60">
                      {t('schoolsNotFullySetUpYetContinueSetupOrDelete')}
                    </p>
                  </div>
                </div>
                {showDrafts ? <ChevronUp className="h-5 w-5 text-amber-500" /> : <ChevronDown className="h-5 w-5 text-amber-500" />}
              </button>

              {showDrafts && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {draftSchools.map((draft) => (
                    <div
                      key={draft.id}
                      className="relative p-4 rounded-xl bg-white dark:bg-slate-900 border-2 border-dashed border-amber-200 dark:border-amber-800 hover:border-amber-400 dark:hover:border-amber-600 transition-all group/card"
                    >
                      <div className="flex items-start gap-3 mb-3">
                        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-400 flex items-center justify-center flex-shrink-0`}>
                          <span className="text-white font-bold text-sm">{draft.name?.charAt(0) || '?'}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-slate-800 dark:text-white truncate font-cairo text-sm">{draft.name || (t('draftSchool'))}</p>
                          <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-0.5">
                            {draft.city && <><MapPin className="h-3 w-3" /><span>{draft.city}</span></>}
                            {draft.created_at && (
                              <span className="ms-auto text-[10px]">
                                {new Date(draft.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-GB')}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <Badge className="mb-3 bg-amber-100 text-amber-700 border-amber-200 text-[10px]">
                        <Clock className="h-3 w-3 me-1" />
                        {t('setup2')}
                      </Badge>

                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          className="flex-1 bg-brand-navy text-white hover:bg-brand-navy/90 text-xs gap-1.5 h-8"
                          onClick={() => navigate(`/platform/schools/${draft.id}`)}
                        >
                          <FileEdit className="h-3.5 w-3.5" />
                          {t('continueSetup')}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-500 border-red-200 hover:bg-red-50 hover:text-red-600 dark:border-red-800 dark:hover:bg-red-950/30 h-8 w-8 p-0"
                          onClick={() => handleDeleteDraft(draft)}
                          disabled={deletingDraftId === draft.id}
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

          {/* Schools Content */}
          {filteredSchools.length === 0 ? (
            <Card className="border-0 shadow-md p-12 text-center">
              <Building2 className="h-16 w-16 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
              <h3 className="font-bold text-lg mb-2 font-cairo">{t('noResults')}</h3>
              <p className="text-slate-500 mb-4">{t('tryChangingFilters')}</p>
              <Button onClick={resetFilters} variant="outline">
                <RefreshCw className="h-4 w-4 me-2" />
                {t('resetFilters')}
              </Button>
            </Card>
          ) : viewMode === 'table' ? (
            /* Table View */
            <Card className="border-0 shadow-md overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                      <th className="text-start p-3 font-medium text-slate-500">{t('school')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('students')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('teachers')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('classes')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('parents')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('setup_score')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('status')}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t('actions2')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSchools.map((school) => (
                      <tr key={school.id} className="border-b border-slate-50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                        <td className="p-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${getLogoGradient(school.id)} flex items-center justify-center flex-shrink-0`}>
                              <span className="text-white font-bold text-sm">{school.name?.charAt(0)}</span>
                            </div>
                            <div>
                              <p className="font-semibold text-slate-800 dark:text-white">{school.name}</p>
                              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                                <MapPin className="h-3 w-3" />
                                {school.city || '—'}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="p-3 text-center font-semibold text-blue-600">{school.student_count || 0}</td>
                        <td className="p-3 text-center font-semibold text-purple-600">{school.teacher_count || 0}</td>
                        <td className="p-3 text-center font-semibold text-slate-600 dark:text-slate-400">{school.class_count || 0}</td>
                        <td className="p-3 text-center font-semibold text-emerald-600">{school.parent_count || 0}</td>
                        <td className="p-3 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            <div className="w-14 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${school.setup_score === 100 ? 'bg-emerald-500' : school.setup_score >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${school.setup_score || 0}%` }} />
                            </div>
                            <span className="text-xs font-medium text-slate-500">{school.setup_score || 0}%</span>
                          </div>
                        </td>
                        <td className="p-3 text-center">
                          <Badge className={`text-xs ${SCHOOL_STATUS[school.status]?.badge || SCHOOL_STATUS.active.badge}`}>
                            {isRTL ? SCHOOL_STATUS[school.status]?.label : SCHOOL_STATUS[school.status]?.label_en}
                          </Badge>
                        </td>
                        <td className="p-3 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            <Button size="sm" variant="outline" className="rounded-lg text-xs border-brand-navy/30 text-brand-navy" onClick={() => navigate(`/platform/schools/${school.id}`)}>
                              <ExternalLink className="h-3 w-3 me-1" />
                              {t('details2')}
                            </Button>
                            <Button size="sm" className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg text-xs" onClick={() => handleEnterSchoolDashboard(school)}>
                              <Eye className="h-3.5 w-3.5 me-1" />
                              {t('openDashboard')}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : (
            /* Grid View */
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {filteredSchools.map((school) => (
                <Card key={school.id} className="group border-0 shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden">
                  <CardContent className="p-0">
                    {/* Card Header with gradient */}
                    <div className={`bg-gradient-to-r ${getLogoGradient(school.id)} p-4 text-white`}>
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                            <span className="text-xl font-bold">{school.name?.charAt(0)}</span>
                          </div>
                          <div>
                            <h3 className="font-cairo font-bold text-base leading-tight line-clamp-1">{school.name}</h3>
                            {school.name_en && (
                              <p className="text-xs text-white/70 line-clamp-1">{school.name_en}</p>
                            )}
                          </div>
                        </div>
                        <Badge className={`text-[10px] ${SCHOOL_STATUS[school.status]?.badge || 'bg-white/20 text-white'}`}>
                          {isRTL ? SCHOOL_STATUS[school.status]?.label : SCHOOL_STATUS[school.status]?.label_en}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-3 mt-3 text-xs text-white/70">
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {school.city || '—'}
                        </span>
                        {school.has_timetable && (
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {t('hasTimetable')}
                          </span>
                        )}
                        {school.sessions_today > 0 && (
                          <span className="flex items-center gap-1">
                            <Activity className="h-3 w-3" />
                            {school.sessions_today} {t('sessionsToday')}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-4 gap-0 border-b border-slate-100 dark:border-slate-800">
                      {[
                        { label: t('students'), value: school.student_count || 0, color: 'text-blue-600' },
                        { label: t('teachers'), value: school.teacher_count || 0, color: 'text-purple-600' },
                        { label: t('classes'), value: school.class_count || 0, color: 'text-indigo-600' },
                        { label: t('parents'), value: school.parent_count || 0, color: 'text-emerald-600' },
                      ].map((stat, i) => (
                        <div key={i} className={`text-center py-3 ${i < 3 ? 'border-e border-slate-100 dark:border-slate-800' : ''}`}>
                          <p className={`text-lg font-bold ${stat.color}`}>{stat.value}</p>
                          <p className="text-[10px] text-slate-400">{stat.label}</p>
                        </div>
                      ))}
                    </div>

                    {/* Setup Score & Actions */}
                    <div className="p-4 space-y-3">
                      {/* Setup Score */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-500">{t('setup_score')}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${(school.setup_score || 0) === 100 ? 'bg-emerald-500' : (school.setup_score || 0) >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                              style={{ width: `${school.setup_score || 0}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-slate-600 dark:text-slate-400">{school.setup_score || 0}%</span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-xl text-xs border-brand-navy/30 text-brand-navy hover:bg-brand-navy/5 hover:text-brand-navy focus-visible:text-brand-navy"
                          onClick={() => navigate(`/platform/schools/${school.id}`)}
                        >
                          <ExternalLink className="h-3.5 w-3.5 me-1" />
                          {t('details2')}
                        </Button>
                        <Button
                          size="sm"
                          className="flex-1 bg-brand-navy hover:bg-brand-navy/90 text-white rounded-xl text-xs"
                          onClick={() => handleEnterSchoolDashboard(school)}
                        >
                          <Eye className="h-3.5 w-3.5 me-1" />
                          {t('openDashboard')}
                        </Button>
                        <div className="flex items-center gap-1.5 px-2 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-xl">
                          <Switch
                            checked={school.status !== 'suspended'}
                            onCheckedChange={(checked) => {
                              if (!checked) { setShowSuspendDialog(school); setActionReason(''); }
                              else { setShowActivateDialog(school); setActionReason(''); }
                            }}
                            className="data-[state=checked]:bg-emerald-500"
                          />
                          <span className="text-[10px] text-slate-500">{school.status === 'suspended' ? t('activate') : t('suspend')}</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

        </div>
      </div>

      {/* Mobile Filter Sheet */}
      <Sheet open={showFilters} onOpenChange={setShowFilters}>
        <SheetContent side={isRTL ? 'right' : 'left'} className="w-[85vw] sm:w-[400px]">
          <SheetHeader>
            <SheetTitle className="font-cairo">{t('filters')}</SheetTitle>
          </SheetHeader>
          <div className="space-y-6 mt-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('status')}</label>
              <Select value={filters.status} onValueChange={(v) => { setFilters(f => ({ ...f, status: v })); setActiveStatusFilter(null); }}>
                <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allStatus')}</SelectItem>
                  <SelectItem value="active">{t('active')}</SelectItem>
                  <SelectItem value="suspended">{t('suspended')}</SelectItem>
                  <SelectItem value="pending">{t('pending')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('city')}</label>
              <Select value={filters.city} onValueChange={(v) => setFilters(f => ({ ...f, city: v }))}>
                <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allCities')}</SelectItem>
                  {cities.map(city => (
                    <SelectItem key={city} value={city}>{city}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-3 pt-4">
              <Button variant="outline" onClick={resetFilters} className="flex-1 rounded-xl">{t('reset')}</Button>
              <Button onClick={() => setShowFilters(false)} className="flex-1 bg-brand-navy rounded-xl">{t('apply')}</Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* Suspend Confirmation Dialog */}
      <Dialog open={!!showSuspendDialog} onOpenChange={(o) => { if (!o) { setShowSuspendDialog(null); setActionReason(''); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-5 w-5" />
              {t('suspendSchool')}
            </DialogTitle>
            <DialogDescription>
              {t('suspendConfirm')}
              <br />
              <strong>{showSuspendDialog?.name}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="text-sm font-medium">
              {t('reasonForSuspensionRequired')}
            </label>
            <Textarea
              placeholder={t('enterReasonForSuspension')}
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              rows={3}
              className="rounded-xl"
            />
          </div>
          <DialogFooter className="flex-row-reverse gap-2">
            <Button variant="outline" onClick={() => { setShowSuspendDialog(null); setActionReason(''); }} disabled={actionLoading}>
              {t('cancel')}
            </Button>
            <Button variant="destructive" onClick={handleSuspendConfirm} disabled={actionLoading || !actionReason.trim()}>
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Pause className="h-4 w-4 me-2" />}
              {t('suspend')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Activate Confirmation Dialog */}
      <Dialog open={!!showActivateDialog} onOpenChange={(o) => { if (!o) { setShowActivateDialog(null); setActionReason(''); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-600">
              <Play className="h-5 w-5" />
              {t('activateSchool')}
            </DialogTitle>
            <DialogDescription>
              {isRTL
                ? `تأكيد تفعيل مدرسة "${showActivateDialog?.name}" وإعادة جميع الحسابات للعمل.`
                : `Confirm activating "${showActivateDialog?.name_en || showActivateDialog?.name}".`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="text-sm font-medium">
              {t('reasonForActivationRequired')}
            </label>
            <Textarea
              placeholder={t('enterReasonForActivation')}
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              rows={3}
              className="rounded-xl"
            />
          </div>
          <DialogFooter className="flex-row-reverse gap-2">
            <Button variant="outline" onClick={() => { setShowActivateDialog(null); setActionReason(''); }} disabled={actionLoading}>
              {t('cancel')}
            </Button>
            <Button className="bg-emerald-500 hover:bg-emerald-600" onClick={handleActivateConfirm} disabled={actionLoading || !actionReason.trim()}>
              {actionLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Play className="h-4 w-4 me-2" />}
              {t('activate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create School Wizard */}
      <CreateSchoolWizard
        open={showCreateWizard}
        onOpenChange={setShowCreateWizard}
        onSuccess={handleSchoolCreated}
        api={api}
        isRTL={isRTL}
      />
    </Sidebar>
  );
}
