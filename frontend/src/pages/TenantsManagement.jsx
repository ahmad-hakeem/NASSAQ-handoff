import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
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
  Loader2, Layers, Calendar, Activity, UserCheck
} from 'lucide-react';
import CreateSchoolWizard from '../components/wizards/CreateSchoolWizard';
import { Sidebar } from '../components/layout/Sidebar';

const translations = {
  ar: {
    pageTitle: 'إدارة المدارس',
    pageSubtitle: 'إدارة جميع المدارس والمؤسسات التعليمية',
    addSchool: 'إضافة مدرسة',
    totalSchools: 'إجمالي المدارس',
    totalTeachers: 'إجمالي المعلمين',
    totalStudents: 'إجمالي الطلاب',
    totalClasses: 'إجمالي الفصول',
    activeSchools: 'نشطة',
    suspendedSchools: 'موقوفة',
    setupSchools: 'قيد الإعداد',
    pendingSchools: 'معلقة',
    searchPlaceholder: 'بحث بالاسم أو المدينة...',
    allStatus: 'جميع الحالات',
    active: 'نشطة',
    suspended: 'موقوفة',
    setup: 'قيد الإعداد',
    pending: 'معلقة',
    status: 'الحالة',
    allCities: 'جميع المدن',
    city: 'المدينة',
    reset: 'إعادة ضبط',
    filters: 'الفلاتر',
    apply: 'تطبيق',
    noResults: 'لا توجد نتائج',
    tryChangingFilters: 'جرب تغيير معايير البحث أو الفلاتر',
    resetFilters: 'إعادة ضبط الفلاتر',
    openDashboard: 'فتح لوحة التحكم',
    students: 'طالب',
    teachers: 'معلم',
    classes: 'فصل',
    parents: 'ولي أمر',
    setup_score: 'الجاهزية',
    suspend: 'تعليق',
    activate: 'تفعيل',
    school: 'مدرسة',
    suspendSchool: 'تعليق المدرسة',
    suspendConfirm: 'هل أنت متأكد من تعليق هذه المدرسة؟ سيتم تعطيل جميع الحسابات المرتبطة بها.',
    cancel: 'إلغاء',
    confirm: 'تأكيد',
    hasTimetable: 'لديها جدول',
    noTimetable: 'بدون جدول',
    sessionsToday: 'حصة اليوم',
    viewAll: 'عرض الكل',
  },
  en: {
    pageTitle: 'Schools Management',
    pageSubtitle: 'Manage all schools and educational institutions',
    addSchool: 'Add School',
    totalSchools: 'Total Schools',
    totalTeachers: 'Total Teachers',
    totalStudents: 'Total Students',
    totalClasses: 'Total Classes',
    activeSchools: 'Active',
    suspendedSchools: 'Suspended',
    setupSchools: 'Setup',
    pendingSchools: 'Pending',
    searchPlaceholder: 'Search by name or city...',
    allStatus: 'All Status',
    active: 'Active',
    suspended: 'Suspended',
    setup: 'Setup',
    pending: 'Pending',
    status: 'Status',
    allCities: 'All Cities',
    city: 'City',
    reset: 'Reset',
    filters: 'Filters',
    apply: 'Apply',
    noResults: 'No results found',
    tryChangingFilters: 'Try changing search criteria or filters',
    resetFilters: 'Reset Filters',
    openDashboard: 'Open Dashboard',
    students: 'Students',
    teachers: 'Teachers',
    classes: 'Classes',
    parents: 'Parents',
    setup_score: 'Setup',
    suspend: 'Suspend',
    activate: 'Activate',
    school: 'school',
    suspendSchool: 'Suspend School',
    suspendConfirm: 'Are you sure you want to suspend this school? All associated accounts will be disabled.',
    cancel: 'Cancel',
    confirm: 'Confirm',
    hasTimetable: 'Has Timetable',
    noTimetable: 'No Timetable',
    sessionsToday: 'Sessions Today',
    viewAll: 'View All',
  }
};

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
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const isRTL = contextIsRTL !== false;
  const t = translations[isRTL ? 'ar' : 'en'];

  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [showFilters, setShowFilters] = useState(false);
  const [showCreateWizard, setShowCreateWizard] = useState(false);
  const [activeStatusFilter, setActiveStatusFilter] = useState(null);
  const [showSuspendDialog, setShowSuspendDialog] = useState(null);

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
      if (showToast) toast.success(isRTL ? 'تم تحديث البيانات' : 'Data refreshed');
    } catch (error) {
      console.error('Error fetching schools:', error);
      nassaqError(isRTL ? 'خطأ في تحميل المدارس' : 'Error loading schools');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, isRTL]);

  useEffect(() => { fetchSchools(); }, [fetchSchools]);

  const filteredSchools = React.useMemo(() => {
    let result = [...schools];
    if (activeStatusFilter) {
      result = result.filter(s => s.status === activeStatusFilter);
    } else if (filters.status !== 'all') {
      result = result.filter(s => s.status === filters.status);
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
    total: schools.length,
    active: schools.filter(s => s.status === 'active').length,
    suspended: schools.filter(s => s.status === 'suspended').length,
    pending: schools.filter(s => s.status === 'pending' || s.status === 'setup').length,
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

  const handleEnterSchoolDashboard = (school) => {
    if (!school?.id) {
      nassaqError(isRTL ? 'خطأ: بيانات المدرسة غير صالحة' : 'Error: Invalid school data');
      return;
    }
    enterSchoolContext(school);
    toast.success(
      isRTL ? `تم الدخول إلى ${school.name} كمدير مدرسة` : `Entered ${school.name_en || school.name} as School Manager`
    );
    navigate('/principal');
  };

  const handleToggleSuspend = (school, suspend = true) => {
    setSchools(prev => prev.map(s =>
      s.id === school.id ? { ...s, status: suspend ? 'suspended' : 'active' } : s
    ));
    toast.success(suspend
      ? (isRTL ? `تم تعليق ${school.name}` : `${school.name} suspended`)
      : (isRTL ? `تم تفعيل ${school.name}` : `${school.name} activated`)
    );
    setShowSuspendDialog(null);
  };

  const handleSchoolCreated = () => {
    setShowCreateWizard(false);
    fetchSchools(true);
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
              {isRTL ? 'جاري تحميل المدارس...' : 'Loading schools...'}
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
                    <h1 className="text-2xl sm:text-3xl font-bold font-cairo">{t.pageTitle}</h1>
                    <p className="text-white/70 text-sm font-tajawal">{t.pageSubtitle}</p>
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
                  {isRTL ? 'تحديث' : 'Refresh'}
                </Button>
                <Button
                  size="sm"
                  className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
                  onClick={() => setShowCreateWizard(true)}
                >
                  <Plus className="h-4 w-4 me-1.5" />
                  {t.addSchool}
                </Button>
              </div>
            </div>

            {/* Stats Row */}
            <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
              {[
                { label: t.totalSchools, value: stats.total, icon: Building2, onClick: () => setActiveStatusFilter(null) },
                { label: t.activeSchools, value: stats.active, icon: CheckCircle2, onClick: () => handleStatusFilter('active'), active: activeStatusFilter === 'active', color: 'text-emerald-400' },
                { label: t.suspendedSchools, value: stats.suspended, icon: XCircle, onClick: () => handleStatusFilter('suspended'), active: activeStatusFilter === 'suspended', color: 'text-red-400' },
                { label: t.pendingSchools, value: stats.pending, icon: Clock, onClick: () => handleStatusFilter('pending'), active: activeStatusFilter === 'pending', color: 'text-amber-400' },
                { label: t.totalStudents, value: stats.totalStudents.toLocaleString(), icon: GraduationCap },
                { label: t.totalTeachers, value: stats.totalTeachers, icon: UserCheck },
                { label: t.totalClasses, value: stats.totalClasses, icon: Layers },
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
              <Button variant="ghost" size="sm" onClick={() => setActiveStatusFilter(null)} className="text-brand-purple hover:bg-brand-purple/20">
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
                placeholder={t.searchPlaceholder}
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
                  <SelectValue placeholder={t.status} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.allStatus}</SelectItem>
                  <SelectItem value="active">{t.active}</SelectItem>
                  <SelectItem value="suspended">{t.suspended}</SelectItem>
                  <SelectItem value="pending">{t.pending}</SelectItem>
                </SelectContent>
              </Select>

              <Select value={filters.city} onValueChange={(v) => setFilters(f => ({ ...f, city: v }))}>
                <SelectTrigger className="w-36 rounded-xl">
                  <SelectValue placeholder={t.city} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.allCities}</SelectItem>
                  {cities.map(city => (
                    <SelectItem key={city} value={city}>{city}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button variant="outline" size="sm" onClick={resetFilters} className="rounded-xl">
                <RefreshCw className="h-4 w-4 me-1.5" />
                {t.reset}
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

          {/* Schools Content */}
          {filteredSchools.length === 0 ? (
            <Card className="border-0 shadow-md p-12 text-center">
              <Building2 className="h-16 w-16 mx-auto text-slate-300 dark:text-slate-600 mb-4" />
              <h3 className="font-bold text-lg mb-2 font-cairo">{t.noResults}</h3>
              <p className="text-slate-500 mb-4">{t.tryChangingFilters}</p>
              <Button onClick={resetFilters} variant="outline">
                <RefreshCw className="h-4 w-4 me-2" />
                {t.resetFilters}
              </Button>
            </Card>
          ) : viewMode === 'table' ? (
            /* Table View */
            <Card className="border-0 shadow-md overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                      <th className="text-start p-3 font-medium text-slate-500">{isRTL ? 'المدرسة' : 'School'}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t.students}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t.teachers}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t.classes}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t.parents}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t.setup_score}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{t.status}</th>
                      <th className="text-center p-3 font-medium text-slate-500">{isRTL ? 'الإجراءات' : 'Actions'}</th>
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
                          <Button size="sm" className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg text-xs" onClick={() => handleEnterSchoolDashboard(school)}>
                            <Eye className="h-3.5 w-3.5 me-1" />
                            {t.openDashboard}
                          </Button>
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
                            {t.hasTimetable}
                          </span>
                        )}
                        {school.sessions_today > 0 && (
                          <span className="flex items-center gap-1">
                            <Activity className="h-3 w-3" />
                            {school.sessions_today} {t.sessionsToday}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-4 gap-0 border-b border-slate-100 dark:border-slate-800">
                      {[
                        { label: t.students, value: school.student_count || 0, color: 'text-blue-600' },
                        { label: t.teachers, value: school.teacher_count || 0, color: 'text-purple-600' },
                        { label: t.classes, value: school.class_count || 0, color: 'text-indigo-600' },
                        { label: t.parents, value: school.parent_count || 0, color: 'text-emerald-600' },
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
                        <span className="text-xs text-slate-500">{t.setup_score}</span>
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
                          className="flex-1 bg-brand-navy hover:bg-brand-navy/90 text-white rounded-xl text-sm"
                          onClick={() => handleEnterSchoolDashboard(school)}
                        >
                          <Eye className="h-4 w-4 me-1.5" />
                          {t.openDashboard}
                        </Button>
                        <div className="flex items-center gap-1.5 px-2 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-xl">
                          <Switch
                            checked={school.status !== 'suspended'}
                            onCheckedChange={(checked) => {
                              if (!checked) setShowSuspendDialog(school);
                              else handleToggleSuspend(school, false);
                            }}
                            className="data-[state=checked]:bg-emerald-500"
                          />
                          <span className="text-[10px] text-slate-500">{school.status === 'suspended' ? t.activate : t.suspend}</span>
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
            <SheetTitle className="font-cairo">{t.filters}</SheetTitle>
          </SheetHeader>
          <div className="space-y-6 mt-6">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t.status}</label>
              <Select value={filters.status} onValueChange={(v) => { setFilters(f => ({ ...f, status: v })); setActiveStatusFilter(null); }}>
                <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.allStatus}</SelectItem>
                  <SelectItem value="active">{t.active}</SelectItem>
                  <SelectItem value="suspended">{t.suspended}</SelectItem>
                  <SelectItem value="pending">{t.pending}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t.city}</label>
              <Select value={filters.city} onValueChange={(v) => setFilters(f => ({ ...f, city: v }))}>
                <SelectTrigger className="rounded-xl"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.allCities}</SelectItem>
                  {cities.map(city => (
                    <SelectItem key={city} value={city}>{city}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-3 pt-4">
              <Button variant="outline" onClick={resetFilters} className="flex-1 rounded-xl">{t.reset}</Button>
              <Button onClick={() => setShowFilters(false)} className="flex-1 bg-brand-navy rounded-xl">{t.apply}</Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* Suspend Confirmation Dialog */}
      <Dialog open={!!showSuspendDialog} onOpenChange={() => setShowSuspendDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600">
              <AlertTriangle className="h-5 w-5" />
              {t.suspendSchool}
            </DialogTitle>
            <DialogDescription>
              {t.suspendConfirm}
              <br />
              <strong>{showSuspendDialog?.name}</strong>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-row-reverse gap-2">
            <Button variant="outline" onClick={() => setShowSuspendDialog(null)}>{t.cancel}</Button>
            <Button variant="destructive" onClick={() => handleToggleSuspend(showSuspendDialog, true)}>
              <Pause className="h-4 w-4 me-2" />
              {t.suspend}
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
