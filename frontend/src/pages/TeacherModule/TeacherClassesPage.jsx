import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Progress } from '../../components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Users, BookOpen, Search, RefreshCw, Loader2,
  GraduationCap, ClipboardCheck, BarChart3, Calendar,
  TrendingUp, LayoutGrid, List, Clock, Play,
  ChevronLeft, Star, AlertTriangle, CheckCircle2,
  ArrowUpDown
} from 'lucide-react';
import SessionsManageTab from './SessionsManageTab';


import { useTranslation } from '../../contexts/ThemeContext';
const DAY_AR = {
  sunday: 'الأحد', monday: 'الاثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس'
};
const DAY_EN = {
  sunday: 'Sun', monday: 'Mon', tuesday: 'Tue',
  wednesday: 'Wed', thursday: 'Thu'
};

const GRADE_COLORS = {
  '1': { bg: 'from-sky-500 to-sky-600', light: 'bg-sky-50 dark:bg-sky-900/20', text: 'text-sky-700 dark:text-sky-300', border: 'border-sky-200 dark:border-sky-800' },
  '2': { bg: 'from-emerald-500 to-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20', text: 'text-emerald-700 dark:text-emerald-300', border: 'border-emerald-200 dark:border-emerald-800' },
  '3': { bg: 'from-violet-500 to-violet-600', light: 'bg-violet-50 dark:bg-violet-900/20', text: 'text-violet-700 dark:text-violet-300', border: 'border-violet-200 dark:border-violet-800' },
  '4': { bg: 'from-amber-500 to-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20', text: 'text-amber-700 dark:text-amber-300', border: 'border-amber-200 dark:border-amber-800' },
  '5': { bg: 'from-rose-500 to-rose-600', light: 'bg-rose-50 dark:bg-rose-900/20', text: 'text-rose-700 dark:text-rose-300', border: 'border-rose-200 dark:border-rose-800' },
  '6': { bg: 'from-indigo-500 to-indigo-600', light: 'bg-indigo-50 dark:bg-indigo-900/20', text: 'text-indigo-700 dark:text-indigo-300', border: 'border-indigo-200 dark:border-indigo-800' },
};

const getGradeColor = (grade) => GRADE_COLORS[String(grade)] || GRADE_COLORS['1'];

export default function TeacherClassesPage() {
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') === 'sessions' ? 'sessions' : 'classes';
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('card');
  const [gradeFilter, setGradeFilter] = useState('all');
  const [sortBy, setSortBy] = useState('grade');

  const { nassaqError } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  const handleTabChange = (tab) => {
  const { t } = useTranslation();
    setSearchParams(tab === 'sessions' ? { tab: 'sessions' } : {});
  };

  const fetchClasses = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const [classesRes, metricsRes] = await Promise.all([
        api.get(`/teacher/classes/${teacherId}`),
        api.get(`/teacher/${teacherId}/class-metrics`).catch(() => ({ data: {} }))
      ]);
      const classesData = classesRes.data || [];
      const metricsData = metricsRes.data || {};

      const enriched = classesData.map(cls => {
        const m = metricsData[cls.id] || {};
        return {
          ...cls,
          attendance_rate: m.attendance_rate ?? 0,
          participation_rate: m.participation_rate ?? 0,
          avg_performance: m.avg_performance ?? 0,
          total_sessions: m.total_sessions ?? 0,
        };
      });
      setClasses(enriched);
    } catch (error) {
      console.error('Error fetching classes:', error);
      nassaqError(t('errorLoadingClasses'));
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, isRTL]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  const grades = useMemo(() => {
    const g = [...new Set(classes.map(c => c.grade_level || c.grade_id || ''))].filter(Boolean).sort();
    return g;
  }, [classes]);

  const filteredClasses = useMemo(() => {
    let result = classes.filter(cls => {
      const matchSearch = !searchQuery ||
        cls.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cls.grade_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (cls.subjects || []).some(s => s.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchGrade = gradeFilter === 'all' || String(cls.grade_level || cls.grade_id) === gradeFilter;
      return matchSearch && matchGrade;
    });

    if (sortBy === 'grade') {
      result.sort((a, b) => (a.grade_level || '0').localeCompare(b.grade_level || '0') || a.name?.localeCompare(b.name));
    } else if (sortBy === 'students') {
      result.sort((a, b) => (b.student_count || 0) - (a.student_count || 0));
    } else if (sortBy === 'attendance') {
      result.sort((a, b) => (b.attendance_rate || 0) - (a.attendance_rate || 0));
    } else if (sortBy === 'name') {
      result.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    }
    return result;
  }, [classes, searchQuery, gradeFilter, sortBy]);

  const stats = useMemo(() => {
    if (!classes.length) return null;
    return {
      totalClasses: classes.length,
      totalStudents: classes.reduce((s, c) => s + (c.student_count || 0), 0),
      totalSubjects: [...new Set(classes.flatMap(c => c.subjects || []))].length,
      avgAttendance: Math.round(classes.reduce((s, c) => s + (c.attendance_rate || 0), 0) / classes.length),
      totalSessions: classes.reduce((s, c) => s + (c.weekly_periods || 0), 0),
    };
  }, [classes]);

  const getStatusBadge = (cls) => {
    if (cls.next_session) {
      return (
        <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-0 text-[10px]">
          <CheckCircle2 className="h-3 w-3 me-1" />
          {t('active')}
        </Badge>
      );
    }
    if (cls.status === 'no_upcoming') {
      return (
        <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border-0 text-[10px]">
          <AlertTriangle className="h-3 w-3 me-1" />
          {t('noSession')}
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="text-[10px]">
        {t('enrolled2')}
      </Badge>
    );
  };

  const renderNextSession = (cls) => {
    if (!cls.next_session) return null;
    const ns = cls.next_session;
    const dayLabel = isRTL ? DAY_AR[ns.day] : DAY_EN[ns.day];
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
        <Clock className="h-3 w-3 text-brand-turquoise flex-shrink-0" />
        <span className="truncate">
          {dayLabel} • {ns.start_time} {ns.subject_name ? `• ${ns.subject_name}` : ''}
        </span>
      </div>
    );
  };

  const ClassCard = ({ cls }) => {

    const gc = getGradeColor(cls.grade_level || cls.grade_id);
    return (
      <Card
        className={`group hover:shadow-xl transition-all duration-300 cursor-pointer border-2 hover:border-brand-turquoise/50 overflow-hidden ${gc.border}`}
        onClick={() => navigate(`/teacher/class/${cls.id}`)}
      >
        <div className={`h-1.5 bg-gradient-to-r ${gc.bg}`} />
        <CardHeader className="pb-2 pt-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gc.bg} flex items-center justify-center shadow-md flex-shrink-0`}>
                <GraduationCap className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-base font-cairo truncate">{cls.name}</CardTitle>
                <p className={`text-xs ${gc.text} font-medium`}>{cls.grade_name}</p>
                {renderNextSession(cls)}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              {getStatusBadge(cls)}
              <ChevronLeft className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className={`p-2 rounded-lg ${gc.light}`}>
              <Users className={`h-3.5 w-3.5 mx-auto mb-0.5 ${gc.text}`} />
              <div className={`text-lg font-bold ${gc.text}`}>{cls.student_count || 0}</div>
              <div className="text-[10px] text-muted-foreground">{isRTL ? 'طالب' : 'Students'}</div>
            </div>
            <div className="p-2 rounded-lg bg-muted/40">
              <BookOpen className="h-3.5 w-3.5 mx-auto mb-0.5 text-blue-500" />
              <div className="text-lg font-bold text-foreground">{cls.subjects?.length || 0}</div>
              <div className="text-[10px] text-muted-foreground">{isRTL ? 'مادة' : 'Subjects'}</div>
            </div>
            <div className="p-2 rounded-lg bg-muted/40">
              <Calendar className="h-3.5 w-3.5 mx-auto mb-0.5 text-purple-500" />
              <div className="text-lg font-bold text-foreground">{cls.weekly_periods || 0}</div>
              <div className="text-[10px] text-muted-foreground">{isRTL ? 'حصة/أسبوع' : 'Per week'}</div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted-foreground">{t('attendance2')}</span>
              <span className={`font-bold ${
                cls.attendance_rate >= 90 ? 'text-emerald-600' :
                cls.attendance_rate >= 80 ? 'text-amber-600' : 'text-red-500'
              }`}>{cls.attendance_rate}%</span>
            </div>
            <Progress
              value={cls.attendance_rate || 0}
              className="h-1.5"
            />
          </div>

          {cls.subjects && cls.subjects.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {cls.subjects.slice(0, 3).map((subject, idx) => (
                <Badge key={idx} variant="outline" className="text-[10px] py-0.5 font-tajawal">
                  {subject}
                </Badge>
              ))}
              {cls.subjects.length > 3 && (
                <Badge variant="outline" className="text-[10px] py-0.5">
                  +{cls.subjects.length - 3}
                </Badge>
              )}
            </div>
          )}

          <div className="flex gap-1.5 pt-2 border-t border-border/50">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-8 text-xs"
              onClick={(e) => { e.stopPropagation(); navigate(`/teacher/class/${cls.id}`); }}
            >
              <Users className="h-3 w-3 me-1" />
              {t('students')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-8 text-xs"
              onClick={(e) => { e.stopPropagation(); navigate(`/teacher/attendance?class=${cls.id}`); }}
            >
              <ClipboardCheck className="h-3 w-3 me-1" />
              {t('attendance2')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-8 text-xs"
              onClick={(e) => { e.stopPropagation(); navigate(`/teacher/reports?class=${cls.id}`); }}
            >
              <BarChart3 className="h-3 w-3 me-1" />
              {t('reports2')}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  };

  const ClassTableRow = ({ cls }) => {

    const gc = getGradeColor(cls.grade_level || cls.grade_id);
    return (
      <tr
        className="hover:bg-muted/30 cursor-pointer transition-colors border-b border-border/50 last:border-0"
        onClick={() => navigate(`/teacher/class/${cls.id}`)}
      >
        <td className="p-3">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${gc.bg} flex items-center justify-center shadow-sm flex-shrink-0`}>
              <GraduationCap className="h-4 w-4 text-white" />
            </div>
            <div className="min-w-0">
              <p className="font-medium font-cairo text-sm truncate">{cls.name}</p>
              <p className={`text-xs ${gc.text}`}>{cls.grade_name}</p>
            </div>
          </div>
        </td>
        <td className="p-3">
          <div className="flex flex-wrap gap-1">
            {(cls.subjects || []).slice(0, 2).map((s, i) => (
              <Badge key={i} variant="outline" className="text-[10px] py-0">{s}</Badge>
            ))}
            {(cls.subjects || []).length > 2 && (
              <Badge variant="outline" className="text-[10px] py-0">+{cls.subjects.length - 2}</Badge>
            )}
          </div>
        </td>
        <td className="p-3 text-center">
          <div className="flex items-center justify-center gap-1">
            <Users className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-bold">{cls.student_count || 0}</span>
          </div>
        </td>
        <td className="p-3 text-center">
          <span className={`font-bold text-sm ${
            cls.attendance_rate >= 90 ? 'text-emerald-600' :
            cls.attendance_rate >= 80 ? 'text-amber-600' : 'text-red-500'
          }`}>{cls.attendance_rate}%</span>
        </td>
        <td className="p-3">
          {cls.next_session ? (
            <div className="flex items-center gap-1.5 text-xs">
              <Clock className="h-3 w-3 text-brand-turquoise" />
              <span>{isRTL ? DAY_AR[cls.next_session.day] : DAY_EN[cls.next_session.day]} {cls.next_session.start_time}</span>
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>
        <td className="p-3">{getStatusBadge(cls)}</td>
        <td className="p-3">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); navigate(`/teacher/class/${cls.id}`); }}>
              <Users className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); navigate(`/teacher/attendance?class=${cls.id}`); }}>
              <ClipboardCheck className="h-3.5 w-3.5" />
            </Button>
          </div>
        </td>
      </tr>
    );
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl border-b border-border/50 shadow-sm">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo flex items-center gap-2">
                  <GraduationCap className="h-7 w-7" />
                  {t('myClasses')}
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5 font-tajawal">
                  {t('manageAndTrackYourClassesAndSessions')}
                </p>
              </div>
              {activeTab === 'classes' && (
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('searchClassesOrSubjects')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-full sm:w-[220px] h-9"
                    />
                  </div>
                  <Select value={gradeFilter} onValueChange={setGradeFilter}>
                    <SelectTrigger className="w-[130px] h-9">
                      <SelectValue placeholder={isRTL ? 'المرحلة' : 'Grade'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('allGrades')}</SelectItem>
                      {grades.map(g => (
                        <SelectItem key={g} value={String(g)}>
                          {isRTL ? `الصف ${g}` : `Grade ${g}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="flex items-center border rounded-lg overflow-hidden h-9">
                    <Button
                      variant={viewMode === 'card' ? 'default' : 'ghost'}
                      size="sm"
                      className="h-full rounded-none px-2.5"
                      onClick={() => setViewMode('card')}
                    >
                      <LayoutGrid className="h-4 w-4" />
                    </Button>
                    <Button
                      variant={viewMode === 'table' ? 'default' : 'ghost'}
                      size="sm"
                      className="h-full rounded-none px-2.5"
                      onClick={() => setViewMode('table')}
                    >
                      <List className="h-4 w-4" />
                    </Button>
                  </div>
                  <Button variant="outline" size="sm" className="h-9" onClick={fetchClasses} disabled={loading}>
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              )}
            </div>
          </div>
          <div className="px-4 sm:px-6 flex gap-0 border-t border-border/30">
            <button
              onClick={() => handleTabChange('classes')}
              className={`px-5 py-2.5 text-sm font-medium font-cairo transition-all relative ${
                activeTab === 'classes'
                  ? 'text-brand-navy dark:text-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <GraduationCap className="h-4 w-4" />
                {t('myClasses')}
              </span>
              {activeTab === 'classes' && (
                <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
              )}
            </button>
            <button
              onClick={() => handleTabChange('sessions')}
              className={`px-5 py-2.5 text-sm font-medium font-cairo transition-all relative ${
                activeTab === 'sessions'
                  ? 'text-brand-navy dark:text-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <ClipboardCheck className="h-4 w-4" />
                {t('sessionManagement')}
              </span>
              {activeTab === 'sessions' && (
                <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
              )}
            </button>
          </div>
        </div>

        <div className="px-4 sm:px-6 py-4 space-y-4">
        {activeTab === 'sessions' ? (
          <SessionsManageTab />
        ) : (
          <>
          {!loading && stats && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { label: t('classes4'), value: stats.totalClasses, icon: GraduationCap, gradient: 'from-blue-500 to-blue-600', light: 'bg-blue-50 dark:bg-blue-900/20' },
                { label: isRTL ? 'طالب' : 'Students', value: stats.totalStudents, icon: Users, gradient: 'from-emerald-500 to-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20' },
                { label: isRTL ? 'مادة' : 'Subjects', value: stats.totalSubjects, icon: BookOpen, gradient: 'from-purple-500 to-purple-600', light: 'bg-purple-50 dark:bg-purple-900/20' },
                { label: isRTL ? 'حصة/أسبوع' : 'Sessions/wk', value: stats.totalSessions, icon: Calendar, gradient: 'from-amber-500 to-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20' },
                { label: isRTL ? 'متوسط الحضور' : 'Avg Attend.', value: `${stats.avgAttendance}%`, icon: TrendingUp, gradient: 'from-cyan-500 to-cyan-600', light: 'bg-cyan-50 dark:bg-cyan-900/20' },
              ].map(({ label, value, icon: Icon, gradient, light }) => (
                <Card key={label} className={`${light} border-0 shadow-sm`}>
                  <CardContent className="p-3 flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-md flex-shrink-0`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="text-xl font-bold text-foreground">{value}</div>
                      <div className="text-[10px] text-muted-foreground">{label}</div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise" />
              <p className="text-sm text-muted-foreground font-tajawal">{t('loadingClasses')}</p>
            </div>
          ) : filteredClasses.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="text-center py-16">
                <GraduationCap className="h-16 w-16 mx-auto mb-4 text-muted-foreground/20" />
                <h3 className="font-bold text-lg mb-2 font-cairo">
                  {searchQuery || gradeFilter !== 'all'
                    ? (t('noResults'))
                    : (t('noClassesFound2'))}
                </h3>
                <p className="text-muted-foreground text-sm font-tajawal">
                  {searchQuery || gradeFilter !== 'all'
                    ? (t('tryChangingSearchCriteria'))
                    : (t('noClassesAssignedToYouYet'))}
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL
                    ? `عرض ${filteredClasses.length} من ${classes.length} فصل`
                    : `Showing ${filteredClasses.length} of ${classes.length} classes`}
                </p>
                <Select value={sortBy} onValueChange={setSortBy}>
                  <SelectTrigger className="w-[140px] h-8 text-xs">
                    <ArrowUpDown className="h-3 w-3 me-1" />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="grade">{isRTL ? 'المرحلة' : 'By Grade'}</SelectItem>
                    <SelectItem value="name">{isRTL ? 'الاسم' : 'By Name'}</SelectItem>
                    <SelectItem value="students">{t('byStudents')}</SelectItem>
                    <SelectItem value="attendance">{isRTL ? 'الحضور' : 'By Attendance'}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {viewMode === 'card' ? (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {filteredClasses.map(cls => (
                    <ClassCard key={cls.id} cls={cls} />
                  ))}
                </div>
              ) : (
                <Card className="overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-muted/50 text-muted-foreground">
                          <th className="p-3 text-start font-medium">{t('class')}</th>
                          <th className="p-3 text-start font-medium">{t('subjects')}</th>
                          <th className="p-3 text-center font-medium">{t('students')}</th>
                          <th className="p-3 text-center font-medium">{t('attendance2')}</th>
                          <th className="p-3 text-start font-medium">{t('nextSession')}</th>
                          <th className="p-3 text-start font-medium">{t('status2')}</th>
                          <th className="p-3 text-start font-medium">{t('actions')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredClasses.map(cls => (
                          <ClassTableRow key={cls.id} cls={cls} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </>
          )}
          </>
        )}
        </div>
      </div>
    </Sidebar>
  );
}
