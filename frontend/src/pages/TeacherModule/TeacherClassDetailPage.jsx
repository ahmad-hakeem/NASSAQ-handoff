import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Progress } from '../../components/ui/progress';
import { Switch } from '../../components/ui/switch';
import { Checkbox } from '../../components/ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
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
  Users, BookOpen, ClipboardCheck, FileText, Star, Calendar,
  ArrowRight, Loader2, RefreshCw, BarChart3, TrendingUp,
  GraduationCap, Clock, ChevronLeft, ChevronDown, ChevronUp,
  Play, Search, AlertTriangle, CheckCircle2, Award, Activity,
  Eye, EyeOff, Plus, Trash2, Edit3, Upload, FileSpreadsheet,
  Settings, Info, X, Check, Minus, CircleDot
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';
import HakimPresence from '../../components/hakim/HakimPresence';
import FollowupGradesTable from '../../components/teacher/FollowupGradesTable';

import { useTranslation } from '../../contexts/ThemeContext';

const GRADE_COLORS = {
  '1': 'bg-sky-500 dark:bg-sky-600',
  '2': 'bg-emerald-500 dark:bg-emerald-600',
  '3': 'bg-violet-500 dark:bg-violet-600',
  '4': 'bg-amber-500 dark:bg-amber-600',
  '5': 'bg-rose-500 dark:bg-rose-600',
  '6': 'bg-indigo-500 dark:bg-indigo-600',
};

export default function TeacherClassDetailPage() {
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const { classId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classData, setClassData] = useState(null);
  const [students, setStudents] = useState([]);
  const [schedule, setSchedule] = useState([]);

  const VALID_TABS = ['curriculum', 'records', 'absence'];
  const tabFromUrl = searchParams.get('tab');
  const activeTab = VALID_TABS.includes(tabFromUrl) ? tabFromUrl : 'curriculum';
  const setActiveTab = (tab) => {
    setSearchParams({ tab }, { replace: true });
  };

  const [curriculumData, setCurriculumData] = useState({ lessons: [], total: 0, completed: 0, progress: 0 });
  const [curriculumLoading, setCurriculumLoading] = useState(false);
  const [expandedWeeks, setExpandedWeeks] = useState({});
  const [showAddLesson, setShowAddLesson] = useState(false);
  const [newLessonTitle, setNewLessonTitle] = useState('');
  const [newLessonWeek, setNewLessonWeek] = useState(1);
  const [editingLesson, setEditingLesson] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');

  const [gradeColumns, setGradeColumns] = useState([]);
  const [studentGrades, setStudentGrades] = useState({});
  const [gradesLoading, setGradesLoading] = useState(false);
  const [showColumnSettings, setShowColumnSettings] = useState(false);
  const [showQuickAddCol, setShowQuickAddCol] = useState(false);
  const [newColName, setNewColName] = useState('');
  const [newColType, setNewColType] = useState('coursework');
  const [newColMax, setNewColMax] = useState(10);
  const [editingCol, setEditingCol] = useState(null);
  const [editingColMax, setEditingColMax] = useState(10);

  const [absenceData, setAbsenceData] = useState([]);
  const [absenceLoading, setAbsenceLoading] = useState(false);
  const [studentSearch, setStudentSearch] = useState('');

  const teacherId = user?.teacher_id || user?.id;
  const fileInputRef = useRef(null);

  const fetchClassData = useCallback(async () => {
    if (!classId) return;
    setLoading(true);
    try {
      const [classRes, studentsRes, scheduleRes, statsRes] = await Promise.all([
        api.get(`/classes/${classId}`).catch(() => null),
        api.get(`/classes/${classId}/students`).catch(() => null),
        teacherId ? api.get(`/teacher/schedule/${teacherId}`).catch(() => null) : Promise.resolve(null),
        api.get(`/classes/${classId}/student-stats`).catch(() => null),
      ]);

      const scheduleData = Array.isArray(scheduleRes?.data) ? scheduleRes.data : [];
      const classSchedule = scheduleData.filter(s => s.class_id === classId);
      const studentsList = Array.isArray(studentsRes?.data) ? studentsRes.data : [];
      const statsMap = (statsRes?.data && typeof statsRes.data === 'object' && !Array.isArray(statsRes.data)) ? statsRes.data : {};

      const enrichedStudents = studentsList.map(student => {
        const s = statsMap[student.id] || {};
        return {
          ...student,
          attendance_rate: s.attendance_rate ?? 0,
          average_grade: s.average_grade ?? 0,
          behavior_points: s.behavior_points ?? 0,
          participation_rate: s.participation_rate ?? 0,
          total_sessions: s.total_sessions_attended ?? 0,
        };
      });

      const avgAttendance = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.attendance_rate || 0), 0) / enrichedStudents.length
        : 0;
      const avgParticipation = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.participation_rate || 0), 0) / enrichedStudents.length
        : 0;

      const cls = (classRes?.data && typeof classRes.data === 'object') ? classRes.data : {};
      const gl = cls.grade_level || cls.grade_id || '';
      const gradeOrdinals = { '1': t('gradeOrdinal1'), '2': t('gradeOrdinal2'), '3': t('gradeOrdinal3'), '4': t('gradeOrdinal4'), '5': t('gradeOrdinal5'), '6': t('gradeOrdinal6') };
      const gradeNum = typeof gl === 'string' ? gl.match(/\d+/)?.[0] : String(gl);
      const gradeName = cls.grade_name || (gradeNum ? `${t('gradeLevel')} ${gradeOrdinals[gradeNum] || gradeNum}` : cls.name || '');

      setClassData({
        ...(typeof cls === 'object' ? cls : {}),
        id: classId,
        name: cls.name || cls.name_ar || t('class'),
        grade_name: gradeName,
        grade_level: gl,
        student_count: studentsList.length,
        attendance_rate: Math.round(avgAttendance),
        participation_rate: Math.round(avgParticipation),
        weekly_periods: classSchedule.length,
      });

      setStudents(enrichedStudents);
      setSchedule(classSchedule);
    } catch (error) {
      console.error('Error loading class data:', error);
      nassaqError(t('errorLoadingClassData'));
    } finally {
      setLoading(false);
    }
  }, [api, classId, teacherId]);

  useEffect(() => {
    fetchClassData();
  }, [fetchClassData]);

  const fetchCurriculum = useCallback(async () => {
    if (!classId) return;
    setCurriculumLoading(true);
    try {
      const res = await api.get(`/class/${classId}/curriculum-plan`);
      setCurriculumData(res.data || { lessons: [], total: 0, completed: 0, progress: 0 });
      const weeks = {};
      (res.data?.lessons || []).forEach(l => { weeks[l.week] = true; });
      setExpandedWeeks(weeks);
    } catch (err) {
      console.error('Error loading curriculum:', err);
    } finally {
      setCurriculumLoading(false);
    }
  }, [api, classId]);

  const fetchGradeColumns = useCallback(async () => {
    if (!classId) return;
    setGradesLoading(true);
    try {
      const res = await api.get(`/class/${classId}/grade-columns`);
      setGradeColumns(res.data || []);
    } catch (err) {
      console.error('Error loading grade columns:', err);
    } finally {
      setGradesLoading(false);
    }
  }, [api, classId]);

  const fetchAbsenceData = useCallback(async () => {
    if (!classId) return;
    setAbsenceLoading(true);
    try {
      const res = await api.get(`/attendance/class/${classId}?start_date=2024-01-01&end_date=2030-12-31`);
      const records = Array.isArray(res.data) ? res.data : [];
      const absences = records.filter(r => r.status === 'absent');
      setAbsenceData(absences);
    } catch (err) {
      console.error('Error loading absences:', err);
    } finally {
      setAbsenceLoading(false);
    }
  }, [api, classId]);

  useEffect(() => {
    if (activeTab === 'curriculum') fetchCurriculum();
    else if (activeTab === 'records') fetchGradeColumns();
    else if (activeTab === 'absence') fetchAbsenceData();
  }, [activeTab, fetchCurriculum, fetchGradeColumns, fetchAbsenceData]);

  const handleToggleLesson = async (lesson) => {
    try {
      await api.put(`/curriculum-lesson/${lesson.id}`, { is_completed: !lesson.is_completed });
      toast.success(lesson.is_completed ? t('lessonMarkedIncomplete') : t('lessonCompleted'));
      fetchCurriculum();
    } catch (err) {
      console.error(err);
      nassaqError(t('errorLoadingCurriculum'));
    }
  };

  const handleSkipLesson = async (lesson) => {
    try {
      await api.put(`/curriculum-lesson/${lesson.id}`, { is_skipped: !lesson.is_skipped });
      toast.success(lesson.is_skipped ? t('lessonUpdated') : t('skipped'));
      fetchCurriculum();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteLesson = async (lessonId) => {
    try {
      await api.delete(`/curriculum-lesson/${lessonId}`);
      toast.success(t('lessonDeleted'));
      fetchCurriculum();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddLesson = async () => {
    if (!newLessonTitle.trim()) return;
    try {
      const weekLessons = curriculumData.lessons.filter(l => l.week === newLessonWeek);
      await api.post(`/class/${classId}/curriculum-plan/lesson`, {
        title: newLessonTitle.trim(),
        week: newLessonWeek,
        order: weekLessons.length + 1,
      });
      toast.success(t('lessonAdded'));
      setNewLessonTitle('');
      setShowAddLesson(false);
      fetchCurriculum();
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditLesson = async (lesson) => {
    if (!editingTitle.trim()) return;
    try {
      await api.put(`/curriculum-lesson/${lesson.id}`, { title: editingTitle.trim() });
      toast.success(t('lessonUpdated'));
      setEditingLesson(null);
      setEditingTitle('');
      fetchCurriculum();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddColumn = async () => {
    if (!newColName.trim()) return;
    try {
      await api.post(`/class/${classId}/grade-columns`, {
        name: newColName.trim(),
        column_type: newColType,
        max_grade: newColMax,
        order: gradeColumns.length + 1,
      });
      toast.success(t('columnAdded'));
      setNewColName('');
      setNewColType('coursework');
      setNewColMax(10);
      setShowQuickAddCol(false);
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleColumnVisibility = async (col) => {
    try {
      await api.put(`/grade-column/${col.id}`, { visible: !col.visible });
      toast.success(t('columnUpdated'));
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteColumn = async (colId) => {
    try {
      await api.delete(`/grade-column/${colId}`);
      toast.success(t('columnDeleted'));
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditColumnMax = async (col) => {
    try {
      await api.put(`/grade-column/${col.id}`, { max_grade: editingColMax });
      toast.success(t('columnUpdated'));
      setEditingCol(null);
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleReorderColumn = async (col, direction) => {
    const sorted = [...gradeColumns].sort((a, b) => (a.order || 0) - (b.order || 0));
    const idx = sorted.findIndex(c => c.id === col.id);
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;
    try {
      await Promise.all([
        api.put(`/grade-column/${sorted[idx].id}`, { order: sorted[swapIdx].order }),
        api.put(`/grade-column/${sorted[swapIdx].id}`, { order: sorted[idx].order }),
      ]);
      toast.success(t('columnUpdated'));
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleGradeChange = (studentId, colId, value) => {
    setStudentGrades(prev => ({
      ...prev,
      [`${studentId}_${colId}`]: value,
    }));
  };

  const filteredStudents = useMemo(() => {
    if (!studentSearch) return students;
    return students.filter(s =>
      s.full_name?.toLowerCase().includes(studentSearch.toLowerCase()) ||
      s.student_number?.toLowerCase().includes(studentSearch.toLowerCase())
    );
  }, [students, studentSearch]);

  const weekGroups = useMemo(() => {
    const groups = {};
    (curriculumData.lessons || []).forEach(l => {
      const w = l.week || 1;
      if (!groups[w]) groups[w] = [];
      groups[w].push(l);
    });
    Object.keys(groups).forEach(w => {
      groups[w].sort((a, b) => (a.order || 0) - (b.order || 0));
    });
    return groups;
  }, [curriculumData.lessons]);

  const maxWeek = useMemo(() => {
    const weeks = Object.keys(weekGroups).map(Number);
    return weeks.length > 0 ? Math.max(...weeks) : 0;
  }, [weekGroups]);

  const absencesByStudent = useMemo(() => {
    const map = {};
    students.forEach(s => { map[s.id] = { student: s, absences: [] }; });
    absenceData.forEach(r => {
      if (map[r.student_id]) {
        map[r.student_id].absences.push(r);
      }
    });
    Object.values(map).forEach(entry => {
      entry.absences.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    });
    return Object.values(map);
  }, [students, absenceData]);

  const { currentLessonId, nextLessonId } = useMemo(() => {
    const allLessons = (curriculumData.lessons || [])
      .filter(l => !l.is_skipped)
      .sort((a, b) => (a.week || 0) - (b.week || 0) || (a.order || 0) - (b.order || 0));
    const firstIncomplete = allLessons.find(l => !l.is_completed);
    const firstIncompleteIdx = firstIncomplete ? allLessons.indexOf(firstIncomplete) : -1;
    const nextIdx = firstIncompleteIdx >= 0 ? firstIncompleteIdx + 1 : -1;
    return {
      currentLessonId: firstIncomplete?.id || null,
      nextLessonId: nextIdx < allLessons.length && nextIdx >= 0 ? allLessons[nextIdx]?.id : null,
    };
  }, [curriculumData.lessons]);

  const isBehind = curriculumData.total > 0 && curriculumData.progress < 40;

  const visibleColumns = gradeColumns.filter(c => c.visible !== false);

  const gc = GRADE_COLORS[String(classData?.grade_level)] || 'bg-blue-500 dark:bg-blue-600';

  const getColumnDisplay = (col) => {
    if (!isRTL && col.name_en) return col.name_en;
    return col.name;
  };

  const renderCurriculumTab = () => (
    <div className="space-y-4">
      <div className="grid sm:grid-cols-3 gap-3">
        <Card className="bg-brand-turquoise/5 border-brand-turquoise/20">
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-brand-turquoise">{curriculumData.progress}%</div>
            <div className="text-xs text-muted-foreground mt-1">{t('planProgress')}</div>
            <Progress value={curriculumData.progress} className="h-2 mt-2" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-emerald-600">{curriculumData.completed}</div>
            <div className="text-xs text-muted-foreground mt-1">{t('completedLessons')}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-foreground">{curriculumData.total}</div>
            <div className="text-xs text-muted-foreground mt-1">{t('totalLessons')}</div>
          </CardContent>
        </Card>
      </div>

      {isBehind && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0" />
          <p className="text-sm text-amber-700 dark:text-amber-300 font-tajawal">{t('curriculumBehindSchedule')}</p>
          <Badge className="bg-amber-100 text-amber-700 border-0 ms-auto text-xs">{t('behind')}</Badge>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setShowAddLesson(true)}>
            <Plus className="h-3.5 w-3.5" />
            {t('addLesson')}
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-3.5 w-3.5" />
            {t('importPlan')}
          </Button>
        </div>
        <Badge variant="secondary" className="text-xs">
          {curriculumData.progress >= 80 ? t('onSchedule') : isBehind ? t('behind') : t('onSchedule')}
        </Badge>
      </div>

      {curriculumLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      ) : Object.keys(weekGroups).length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="text-center py-16">
            <BookOpen className="h-14 w-14 mx-auto mb-4 text-muted-foreground/20" />
            <h3 className="font-bold text-lg mb-2 font-cairo">{t('noLessonsInPlan')}</h3>
            <p className="text-sm text-muted-foreground font-tajawal">{t('addLessonsToStartTracking')}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {Object.keys(weekGroups).sort((a, b) => Number(a) - Number(b)).map(week => {
            const lessons = weekGroups[week];
            const weekCompleted = lessons.filter(l => l.is_completed).length;
            const isExpanded = expandedWeeks[week];
            return (
              <Card key={week} className="overflow-hidden">
                <button
                  className="w-full flex items-center justify-between p-3 hover:bg-muted/30 transition-colors duration-150"
                  onClick={() => setExpandedWeeks(prev => ({ ...prev, [week]: !prev[week] }))}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-brand-navy/10 dark:bg-brand-turquoise/10 flex items-center justify-center">
                      <span className="text-sm font-bold text-brand-navy dark:text-brand-turquoise">{week}</span>
                    </div>
                    <div className="text-start">
                      <p className="font-medium text-sm font-cairo">{t('weekNumber')} {week}</p>
                      <p className="text-xs text-muted-foreground">{weekCompleted}/{lessons.length} {t('completedLessons')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress value={lessons.length > 0 ? (weekCompleted / lessons.length) * 100 : 0} className="w-20 h-1.5" />
                    {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                  </div>
                </button>
                {isExpanded && (
                  <div className="border-t border-border/50 px-3 pb-3 space-y-1">
                    {lessons.map((lesson, idx) => {
                      const isCurrent = lesson.id === currentLessonId;
                      const isNext = lesson.id === nextLessonId;
                      return (
                      <div
                        key={lesson.id}
                        className={`flex items-center gap-3 p-2.5 rounded-lg transition-colors duration-150 ${
                          isCurrent ? 'bg-brand-turquoise/10 dark:bg-brand-turquoise/5 ring-1 ring-brand-turquoise/30' :
                          lesson.is_completed ? 'bg-emerald-50/50 dark:bg-emerald-900/10' :
                          lesson.is_skipped ? 'bg-red-50/50 dark:bg-red-900/10 opacity-60' :
                          isNext ? 'bg-blue-50/50 dark:bg-blue-900/10' : 'hover:bg-muted/30'
                        }`}
                      >
                        <Checkbox
                          checked={lesson.is_completed}
                          onCheckedChange={() => handleToggleLesson(lesson)}
                          disabled={lesson.is_skipped}
                          className="data-[state=checked]:bg-emerald-500 data-[state=checked]:border-emerald-500"
                        />
                        <div className="flex-1 min-w-0">
                          {editingLesson === lesson.id ? (
                            <div className="flex items-center gap-2">
                              <Input
                                value={editingTitle}
                                onChange={(e) => setEditingTitle(e.target.value)}
                                className="h-7 text-sm"
                                onKeyDown={(e) => e.key === 'Enter' && handleEditLesson(lesson)}
                              />
                              <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleEditLesson(lesson)}>
                                <Check className="h-3.5 w-3.5" />
                              </Button>
                              <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setEditingLesson(null)}>
                                <X className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <p className={`text-sm font-tajawal ${
                                lesson.is_completed ? 'line-through text-muted-foreground' :
                                lesson.is_skipped ? 'line-through text-red-400' : ''
                              }`}>
                                {lesson.title}
                              </p>
                              {isCurrent && (
                                <Badge className="bg-brand-turquoise/20 text-brand-turquoise border-0 text-[10px] px-1.5 py-0">
                                  {t('currentLesson')}
                                </Badge>
                              )}
                              {isNext && !isCurrent && (
                                <Badge variant="outline" className="text-blue-500 border-blue-200 text-[10px] px-1.5 py-0">
                                  {t('nextLesson')}
                                </Badge>
                              )}
                              {lesson.is_skipped && (
                                <Badge className="bg-red-100 text-red-500 border-0 text-[10px] px-1.5 py-0">
                                  {t('skipped')}
                                </Badge>
                              )}
                            </div>
                          )}
                        </div>
                        {!editingLesson && (
                          <div className="flex items-center gap-0.5">
                            <Button
                              size="sm" variant="ghost" className="h-7 w-7 p-0"
                              title={lesson.is_skipped ? t('markComplete') : t('skipped')}
                              onClick={() => handleSkipLesson(lesson)}
                            >
                              <Minus className={`h-3 w-3 ${lesson.is_skipped ? 'text-red-400' : 'text-muted-foreground'}`} />
                            </Button>
                            <Button
                              size="sm" variant="ghost" className="h-7 w-7 p-0"
                              onClick={() => { setEditingLesson(lesson.id); setEditingTitle(lesson.title); }}
                            >
                              <Edit3 className="h-3 w-3 text-muted-foreground" />
                            </Button>
                            <Button
                              size="sm" variant="ghost" className="h-7 w-7 p-0"
                              onClick={() => handleDeleteLesson(lesson.id)}
                            >
                              <Trash2 className="h-3 w-3 text-red-400" />
                            </Button>
                          </div>
                        )}
                      </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderRecordsTab = () => {
    const visibleColCount = gradeColumns.filter(c => c.visible !== false).length;
    return (
      <div className="space-y-4">
        {/* Search row */}
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('searchByNameOrId')}
            value={studentSearch}
            onChange={(e) => setStudentSearch(e.target.value)}
            className="ps-9 h-9"
          />
        </div>

        {/* Toolbar — mirrors كشف المتابعة */}
        <div className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg bg-muted/40 dark:bg-card/40 border border-border">
          <div className="text-xs text-muted-foreground font-cairo">
            {students.length} طالب
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button size="sm" variant="outline" className="gap-1.5 font-cairo" onClick={() => fileInputRef.current?.click()}>
              <FileSpreadsheet className="h-3.5 w-3.5" />
              {t('importGrades')}
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5 font-cairo" onClick={() => setShowColumnSettings(true)}>
              <Settings className="h-3.5 w-3.5" />
              إعدادات الأعمدة
            </Button>
            <Button
              size="sm"
              className="gap-1.5 font-cairo bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
              onClick={() => setShowQuickAddCol(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              إضافة عمود
            </Button>
          </div>
        </div>

        {gradesLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
          </div>
        ) : (
          <Card className="overflow-hidden">
            {(() => {
              // Adapt class-detail data shapes to the shared FollowupGradesTable contract.
              const adaptedColumns = gradeColumns.map(c => ({
                id: c.id,
                name: getColumnDisplay(c),
                group: c.column_type === 'exams' ? 'exams' : 'coursework',
                maxGrade: c.max_grade,
                hidden: c.visible === false,
              }));
              const adaptedGrades = {};
              filteredStudents.forEach(s => {
                const row = {};
                gradeColumns.forEach(c => {
                  const raw = studentGrades[`${s.id}_${c.id}`];
                  if (raw !== undefined && raw !== '') row[c.id] = raw;
                });
                adaptedGrades[s.id] = row;
              });
              return (
                <FollowupGradesTable
                  students={filteredStudents}
                  columns={adaptedColumns}
                  gradesData={adaptedGrades}
                  onGradeChange={(sid, cid, value) => handleGradeChange(sid, cid, value)}
                  emptyMessage={t('noStudents')}
                  t={t}
                />
              );
            })()}
          </Card>
        )}

        {/* Footer chip — visible columns count */}
        <div className="flex items-center justify-end px-1">
          <span className="text-xs text-muted-foreground font-cairo">
            {visibleColCount} عمود ظاهر
          </span>
        </div>
      </div>
    );
  };

  const resetNewColumnForm = () => {
    setNewColName('');
    setNewColType('coursework');
    setNewColMax(10);
  };

  const renderQuickAddColumnDialog = () => (
    <Dialog
      open={showQuickAddCol}
      onOpenChange={(o) => {
        setShowQuickAddCol(o);
        if (!o) resetNewColumnForm();
      }}
    >
      <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Plus className="h-5 w-5 text-brand-turquoise" />
            إضافة عمود جديد
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="block text-xs font-cairo font-semibold mb-1">اسم العمود</label>
            <Input
              type="text"
              value={newColName}
              onChange={(e) => setNewColName(e.target.value)}
              placeholder="مثال: نشاط صفي"
              onKeyDown={(e) => e.key === 'Enter' && handleAddColumn()}
            />
          </div>
          <div>
            <label className="block text-xs font-cairo font-semibold mb-1">نوع العمود</label>
            <Select value={newColType} onValueChange={setNewColType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="coursework">أعمال سنة</SelectItem>
                <SelectItem value="exams">اختبارات</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="block text-xs font-cairo font-semibold mb-1">الدرجة القصوى</label>
            <Input
              type="number"
              min={1}
              max={100}
              value={newColMax}
              onChange={(e) => setNewColMax(parseInt(e.target.value) || 10)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setShowQuickAddCol(false); resetNewColumnForm(); }}
          >
            {t('cancel') || 'إلغاء'}
          </Button>
          <Button size="sm" onClick={handleAddColumn} className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white">
            {t('save') || 'حفظ'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const renderAbsenceTab = () => (
    <div className="space-y-4">
      {absenceLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  <th className="p-3 text-start font-medium font-cairo min-w-[200px]">{t('name')}</th>
                  <th className="p-3 text-start font-medium font-cairo">{t('attendanceRecords')}</th>
                </tr>
              </thead>
              <tbody>
                {absencesByStudent.length === 0 ? (
                  <tr>
                    <td colSpan={2} className="text-center py-12 text-muted-foreground">{t('noStudents')}</td>
                  </tr>
                ) : (
                  absencesByStudent.map(({ student, absences }) => (
                    <tr key={student.id} className="border-b border-border/50 hover:bg-muted/20 transition-colors duration-150">
                      <td className="p-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-full bg-brand-navy dark:bg-brand-turquoise flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                            {student.full_name?.charAt(0) || '?'}
                          </div>
                          <div>
                            <p className="font-medium text-sm font-cairo">{student.full_name}</p>
                            <p className="text-[10px] text-muted-foreground">
                              {absences.length > 0 ? `${absences.length} ${t('absencesCount')}` : t('noAbsences')}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="p-3">
                        {absences.length === 0 ? (
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                            <span className="text-xs text-emerald-600 font-tajawal">{t('studentHasFullAttendance')}</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2 flex-wrap">
                            {absences.slice(0, 12).map((abs, idx) => {
                              const d = abs.date ? new Date(abs.date) : null;
                              const isValid = d && !isNaN(d.getTime());
                              const shortLabel = isValid
                                ? `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
                                : '';
                              const fullLabel = isValid
                                ? d.toLocaleDateString(isRTL ? 'ar-EG' : 'en-GB', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })
                                : '';
                              return (
                                <div key={abs.id || idx} className="flex flex-col items-center gap-0.5" title={fullLabel}>
                                  <div className="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/30 border-2 border-red-300 dark:border-red-700 flex items-center justify-center">
                                    <X className="h-3.5 w-3.5 text-red-500" />
                                  </div>
                                  <span className="text-[10px] text-muted-foreground whitespace-nowrap font-tajawal">
                                    {shortLabel}
                                  </span>
                                </div>
                              );
                            })}
                            {absences.length > 12 && (
                              <Badge variant="secondary" className="text-[10px]">
                                +{absences.length - 12}
                              </Badge>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );

  const renderAddLessonDialog = () => (
    <Dialog open={showAddLesson} onOpenChange={setShowAddLesson}>
      <DialogContent className="max-w-sm" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Plus className="h-5 w-5 text-brand-turquoise" />
            {t('addLesson')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label className="font-cairo text-sm">{t('lessonTitle')}</Label>
            <Input
              value={newLessonTitle}
              onChange={(e) => setNewLessonTitle(e.target.value)}
              placeholder={t('lessonTitle')}
              onKeyDown={(e) => e.key === 'Enter' && handleAddLesson()}
            />
          </div>
          <div className="space-y-2">
            <Label className="font-cairo text-sm">{t('weekNumber')}</Label>
            <Input
              type="number"
              min={1}
              max={52}
              value={newLessonWeek}
              onChange={(e) => setNewLessonWeek(parseInt(e.target.value) || 1)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowAddLesson(false)}>{t('cancel')}</Button>
          <Button className="bg-brand-navy hover:bg-brand-navy-dark text-white" onClick={handleAddLesson}>
            <Plus className="h-4 w-4 me-2" />
            {t('add')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const renderColumnSettings = () => (
    <Dialog open={showColumnSettings} onOpenChange={setShowColumnSettings}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Settings className="h-5 w-5 text-brand-turquoise" />
            {t('columnSettings')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            {[...gradeColumns].sort((a, b) => (a.order || 0) - (b.order || 0)).map((col, idx) => (
              <div key={col.id} className="p-2.5 rounded-lg border bg-card space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Switch
                      checked={col.visible !== false}
                      onCheckedChange={() => handleToggleColumnVisibility(col)}
                    />
                    <div>
                      <p className="text-sm font-medium font-cairo">{getColumnDisplay(col)}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {col.column_type === 'exams' ? t('exams') : t('coursework')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" disabled={idx === 0}
                      onClick={() => handleReorderColumn(col, 'up')}>
                      <ChevronUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" disabled={idx === gradeColumns.length - 1}
                      onClick={() => handleReorderColumn(col, 'down')}>
                      <ChevronDown className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleDeleteColumn(col.id)}>
                      <Trash2 className="h-3.5 w-3.5 text-red-400" />
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-2 ps-10">
                  <Label className="text-[11px] text-muted-foreground whitespace-nowrap">{t('maxGrade')}:</Label>
                  {editingCol === col.id ? (
                    <div className="flex items-center gap-1">
                      <Input
                        type="number" min={1} max={100} value={editingColMax}
                        onChange={(e) => setEditingColMax(parseFloat(e.target.value) || 10)}
                        className="h-7 w-16 text-sm text-center"
                      />
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleEditColumnMax(col)}>
                        <Check className="h-3 w-3 text-emerald-500" />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setEditingCol(null)}>
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <button
                      className="text-sm font-medium text-blue-600 hover:underline"
                      onClick={() => { setEditingCol(col.id); setEditingColMax(col.max_grade); }}
                    >
                      {col.max_grade}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-border pt-4 space-y-3">
            <p className="text-sm font-medium font-cairo">{t('addColumn')}</p>
            <div className="space-y-2">
              <Input
                placeholder={t('columnName')}
                value={newColName}
                onChange={(e) => setNewColName(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-2">
                <Select value={newColType} onValueChange={setNewColType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="coursework">{t('coursework')}</SelectItem>
                    <SelectItem value="exams">{t('exams')}</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={newColMax}
                  onChange={(e) => setNewColMax(parseInt(e.target.value) || 10)}
                  placeholder={t('maxGrade')}
                />
              </div>
              <Button className="w-full bg-brand-navy hover:bg-brand-navy-dark text-white" onClick={handleAddColumn}>
                <Plus className="h-4 w-4 me-2" />
                {t('addColumn')}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );

  return (
    <Sidebar>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl border-b border-border/50 shadow-sm">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => navigate('/teacher/classes')}>
                  <ArrowRight className="h-5 w-5" />
                </Button>
                <div className={`w-10 h-10 rounded-xl ${gc} flex items-center justify-center shadow-md`}>
                  <GraduationCap className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                    {classData?.name || t('class')}
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    {classData?.grade_name || ''} {classData?.student_count ? `• ${classData.student_count} ${t('students')}` : ''}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="h-9" onClick={fetchClassData} disabled={loading}>
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
                <Button
                  className="bg-brand-turquoise hover:bg-brand-turquoise/90 h-9"
                  size="sm"
                  onClick={() => navigate(`/teacher/attendance?class=${classId}`)}
                >
                  <ClipboardCheck className="h-4 w-4 me-1" />
                  {t('attendance3')}
                </Button>
              </div>
            </div>
          </div>

          <div className="px-4 sm:px-6 flex gap-0 border-t border-border/30">
            {[
              { key: 'curriculum', label: t('curriculumPlan'), icon: BookOpen },
              { key: 'records', label: t('studentRecords'), icon: ClipboardCheck },
              { key: 'absence', label: t('absenceLog'), icon: Calendar },
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 sm:px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                  activeTab === tab.key
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <span className="flex items-center gap-1.5">
                  <tab.icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </span>
                {activeTab === tab.key && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise" />
            <p className="text-sm text-muted-foreground font-tajawal">{t('loading2')}</p>
          </div>
        ) : (
          <div className="px-4 sm:px-6 py-4 space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-2xl bg-violet-50/80 dark:bg-violet-950/30 border border-violet-100/50 dark:border-violet-800/30">
              <HakimPresence size="xs" showMessage={true} messagePosition="bottom" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: t('students'), value: classData?.student_count || 0, icon: Users, iconBg: 'bg-blue-500 dark:bg-blue-600', light: 'bg-blue-50 dark:bg-blue-900/20' },
                { label: t('attendance2'), value: `${classData?.attendance_rate || 0}%`, icon: ClipboardCheck, iconBg: 'bg-emerald-500 dark:bg-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20' },
                { label: t('participation'), value: `${classData?.participation_rate || 0}%`, icon: Activity, iconBg: 'bg-purple-500 dark:bg-purple-600', light: 'bg-purple-50 dark:bg-purple-900/20' },
                { label: t('perWeek'), value: classData?.weekly_periods || 0, icon: Calendar, iconBg: 'bg-amber-500 dark:bg-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20' },
              ].map(({ label, value, icon: Icon, iconBg, light }) => (
                <Card key={label} className={`${light} border-0 shadow-sm`}>
                  <CardContent className="p-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center shadow-md flex-shrink-0`}>
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <div className="text-xl font-bold text-foreground">{value}</div>
                        <div className="text-[10px] text-muted-foreground">{label}</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {activeTab === 'curriculum' && renderCurriculumTab()}
            {activeTab === 'records' && renderRecordsTab()}
            {activeTab === 'absence' && renderAbsenceTab()}
          </div>
        )}
      </div>

      {renderAddLessonDialog()}
      {renderColumnSettings()}
      {renderQuickAddColumnDialog()}

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".xlsx,.xls,.csv,.pdf"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) toast.success(t('importData') + ': ' + file.name);
          if (fileInputRef.current) fileInputRef.current.value = '';
        }}
      />

      <HakimAssistant />
    </Sidebar>
  );
}
