import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Progress } from '../../components/ui/progress';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Users, BookOpen, ClipboardCheck, FileText, Star, Calendar,
  ArrowRight, Loader2, RefreshCw, BarChart3, TrendingUp,
  GraduationCap, Clock, ChevronLeft, Play, Search,
  AlertTriangle, CheckCircle2, Award, Activity, Flame,
  Eye
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';
import HakimPresence from '../../components/hakim/HakimPresence';

import { useTranslation } from '../../contexts/ThemeContext';
const DAY_AR = {
  sunday: 'الأحد', monday: 'الاثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس'
};

const GRADE_COLORS = {
  '1': 'from-sky-500 to-sky-600',
  '2': 'from-emerald-500 to-emerald-600',
  '3': 'from-violet-500 to-violet-600',
  '4': 'from-amber-500 to-amber-600',
  '5': 'from-rose-500 to-rose-600',
  '6': 'from-indigo-500 to-indigo-600',
};

export default function TeacherClassDetailPage() {
  const { nassaqError } = useNassaqAlert();
  const { classId } = useParams();
  const navigate = useNavigate();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classData, setClassData] = useState(null);
  const [students, setStudents] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [activeTab, setActiveTab] = useState('students');
  const [studentSearch, setStudentSearch] = useState('');

  const teacherId = user?.teacher_id || user?.id;

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

      const avgGrade = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.average_grade || 0), 0) / enrichedStudents.length
        : 0;
      const avgAttendance = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.attendance_rate || 0), 0) / enrichedStudents.length
        : 0;
      const avgParticipation = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.participation_rate || 0), 0) / enrichedStudents.length
        : 0;

      const cls = (classRes?.data && typeof classRes.data === 'object') ? classRes.data : {};
      const gl = cls.grade_level || cls.grade_id || '';
      const gradeMap = { '1': 'الأول', '2': 'الثاني', '3': 'الثالث', '4': 'الرابع', '5': 'الخامس', '6': 'السادس',
        '7': 'السابع', '8': 'الثامن', '9': 'التاسع', '10': 'العاشر', '11': 'الحادي عشر', '12': 'الثاني عشر' };
      const gradeNum = typeof gl === 'string' ? gl.match(/\d+/)?.[0] : String(gl);
      const gradeName = cls.grade_name || (gradeNum ? `الصف ${gradeMap[gradeNum] || gradeNum}` : cls.name || '');

      setClassData({
        ...(typeof cls === 'object' ? cls : {}),
        id: classId,
        name: cls.name || cls.name_ar || 'الفصل',
        grade_name: gradeName,
        grade_level: gl,
        student_count: studentsList.length,
        attendance_rate: Math.round(avgAttendance),
        average_grade: Math.round(avgGrade),
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
  }, [api, classId, teacherId, isRTL]);

  useEffect(() => {
    fetchClassData();
  }, [fetchClassData]);

  const filteredStudents = useMemo(() => {
    if (!studentSearch) return students;
    return students.filter(s =>
      s.full_name?.toLowerCase().includes(studentSearch.toLowerCase()) ||
      s.student_number?.toLowerCase().includes(studentSearch.toLowerCase())
    );
  }, [students, studentSearch]);

  const getGradeColor = (grade) => {
    if (grade >= 90) return 'text-emerald-600';
    if (grade >= 75) return 'text-blue-600';
    if (grade >= 60) return 'text-amber-600';
    return 'text-red-500';
  };

  const getGradeBg = (grade) => {
    if (grade >= 90) return 'bg-emerald-50 dark:bg-emerald-900/20';
    if (grade >= 75) return 'bg-blue-50 dark:bg-blue-900/20';
    if (grade >= 60) return 'bg-amber-50 dark:bg-amber-900/20';
    return 'bg-red-50 dark:bg-red-900/20';
  };

  const getAttendanceBadge = (rate) => {
    if (rate >= 95) return { color: 'bg-emerald-100 text-emerald-700', label: t('excellent') };
    if (rate >= 85) return { color: 'bg-blue-100 text-blue-700', label: t('good') };
    if (rate >= 75) return { color: 'bg-amber-100 text-amber-700', label: isRTL ? 'مقبول' : 'Fair' };
    return { color: 'bg-red-100 text-red-700', label: isRTL ? 'ضعيف' : 'Poor' };
  };

  const gc = GRADE_COLORS[String(classData?.grade_level)] || 'from-blue-500 to-blue-600';

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl border-b border-border/50 shadow-sm">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => navigate('/teacher/classes')}>
                  <ArrowRight className="h-5 w-5" />
                </Button>
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gc} flex items-center justify-center shadow-md`}>
                  <GraduationCap className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                    {classData?.name || (t('class'))}
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    {classData?.grade_name || ''} • {classData?.student_count || 0} {isRTL ? 'طالب' : 'students'}
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
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise" />
            <p className="text-sm text-muted-foreground font-tajawal">{t('loading2')}</p>
          </div>
        ) : (
          <div className="px-4 sm:px-6 py-4 space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-2xl bg-gradient-to-r from-violet-50/80 via-cyan-50/50 to-transparent dark:from-violet-950/30 dark:via-cyan-950/20 dark:to-transparent border border-violet-100/50 dark:border-violet-800/30">
              <HakimPresence size="xs" showMessage={true} messagePosition="bottom" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: t('students'), value: classData?.student_count || 0, icon: Users, gradient: 'from-blue-500 to-blue-600', light: 'bg-blue-50 dark:bg-blue-900/20' },
                { label: t('attendance2'), value: `${classData?.attendance_rate || 0}%`, icon: ClipboardCheck, gradient: 'from-emerald-500 to-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20' },
                { label: isRTL ? 'المشاركة' : 'Participation', value: `${classData?.participation_rate || 0}%`, icon: Activity, gradient: 'from-purple-500 to-purple-600', light: 'bg-purple-50 dark:bg-purple-900/20' },
                { label: isRTL ? 'حصة/أسبوع' : 'Sessions/wk', value: classData?.weekly_periods || 0, icon: Calendar, gradient: 'from-amber-500 to-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20' },
              ].map(({ label, value, icon: Icon, gradient, light }) => (
                <Card key={label} className={`${light} border-0 shadow-sm`}>
                  <CardContent className="p-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-md flex-shrink-0`}>
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

            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="w-full sm:w-auto">
                <TabsTrigger value="students" className="flex-1 sm:flex-none">
                  <Users className="h-4 w-4 me-1.5" />
                  {t('students')}
                  <Badge variant="secondary" className="ms-1.5 text-[10px] px-1.5">{students.length}</Badge>
                </TabsTrigger>
                <TabsTrigger value="schedule" className="flex-1 sm:flex-none">
                  <Calendar className="h-4 w-4 me-1.5" />
                  {t('schedule')}
                </TabsTrigger>
                <TabsTrigger value="stats" className="flex-1 sm:flex-none">
                  <BarChart3 className="h-4 w-4 me-1.5" />
                  {t('statistics2')}
                </TabsTrigger>
              </TabsList>

              <TabsContent value="students" className="mt-4 space-y-3">
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('searchByNameOrId')}
                      value={studentSearch}
                      onChange={(e) => setStudentSearch(e.target.value)}
                      className="ps-9 h-9"
                    />
                  </div>
                </div>

                {filteredStudents.length === 0 ? (
                  <Card className="border-dashed">
                    <CardContent className="text-center py-12">
                      <Users className="h-12 w-12 mx-auto mb-3 text-muted-foreground/20" />
                      <p className="text-muted-foreground font-tajawal">
                        {studentSearch ? (t('noResults')) : (t('noStudents'))}
                      </p>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {filteredStudents.map((student, idx) => {
                      const ab = getAttendanceBadge(student.attendance_rate);
                      return (
                        <Card
                          key={student.id}
                          className="hover:shadow-md transition-all cursor-pointer group border hover:border-brand-turquoise/50"
                          onClick={() => navigate(`/teacher/students?id=${student.id}`)}
                        >
                          <CardContent className="p-4">
                            <div className="flex items-center gap-3 mb-3">
                              <Avatar className="h-10 w-10 border-2 border-brand-navy/10">
                                <AvatarImage src={student.avatar_url} />
                                <AvatarFallback className="bg-gradient-to-br from-brand-navy to-brand-turquoise text-white text-sm font-bold">
                                  {student.full_name?.charAt(0) || (idx + 1)}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-sm truncate font-cairo">{student.full_name || `طالب ${idx + 1}`}</p>
                                <p className="text-[11px] text-muted-foreground">{student.student_number || student.student_id || ''}</p>
                              </div>
                              <ChevronLeft className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                            <div className="grid grid-cols-3 gap-1.5 text-center text-xs">
                              <div className={`p-1.5 rounded-lg ${student.attendance_rate >= 85 ? 'bg-emerald-50 dark:bg-emerald-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
                                <div className={`font-bold ${student.attendance_rate >= 85 ? 'text-emerald-600' : 'text-red-500'}`}>
                                  {student.attendance_rate}%
                                </div>
                                <div className="text-muted-foreground text-[10px]">{isRTL ? 'حضور' : 'Attend.'}</div>
                              </div>
                              <div className={`p-1.5 rounded-lg ${getGradeBg(student.average_grade)}`}>
                                <div className={`font-bold ${getGradeColor(student.average_grade)}`}>
                                  {student.average_grade || '—'}
                                </div>
                                <div className="text-muted-foreground text-[10px]">{t('grade4')}</div>
                              </div>
                              <div className={`p-1.5 rounded-lg ${student.behavior_points >= 0 ? 'bg-purple-50 dark:bg-purple-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
                                <div className={`font-bold ${student.behavior_points >= 0 ? 'text-purple-600' : 'text-red-500'}`}>
                                  {student.behavior_points || 0}
                                </div>
                                <div className="text-muted-foreground text-[10px]">{t('behav')}</div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="schedule" className="mt-4">
                {schedule.length === 0 ? (
                  <Card className="border-dashed">
                    <CardContent className="text-center py-12">
                      <Calendar className="h-12 w-12 mx-auto mb-3 text-muted-foreground/20" />
                      <p className="text-muted-foreground font-tajawal">{t('noScheduleForThisClass')}</p>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="space-y-3">
                    {['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'].map(day => {
                      const daySessions = schedule.filter(s => (s.day_of_week || '').toLowerCase() === day);
                      if (daySessions.length === 0) return null;
                      daySessions.sort((a, b) => (a.slot_number || 0) - (b.slot_number || 0));
                      return (
                        <Card key={day}>
                          <CardHeader className="py-2.5 px-4">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2">
                              <Calendar className="h-4 w-4 text-brand-turquoise" />
                              {isRTL ? DAY_AR[day] : day.charAt(0).toUpperCase() + day.slice(1)}
                              <Badge variant="secondary" className="text-[10px] px-1.5">{daySessions.length}</Badge>
                            </CardTitle>
                          </CardHeader>
                          <CardContent className="px-4 pb-3 pt-0">
                            <div className="space-y-2">
                              {daySessions.map((session, idx) => (
                                <div
                                  key={session.id || idx}
                                  className="flex items-center justify-between p-2.5 rounded-lg border border-border/50 hover:bg-muted/30 transition-all"
                                >
                                  <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-lg bg-brand-turquoise/10 flex items-center justify-center">
                                      <Clock className="h-4 w-4 text-brand-turquoise" />
                                    </div>
                                    <div>
                                      <p className="font-medium text-sm font-cairo">{session.subject_name || (isRTL ? 'مادة' : 'Subject')}</p>
                                      <p className="text-xs text-muted-foreground">
                                        {session.start_time || ''} - {session.end_time || ''}
                                        {session.room_name ? ` • ${session.room_name}` : ''}
                                      </p>
                                    </div>
                                  </div>
                                  <Badge variant="outline" className="text-xs">
                                    {t('p')}{session.slot_number || session.period_number || idx + 1}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="stats" className="mt-4">
                <div className="grid sm:grid-cols-2 gap-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-cairo flex items-center gap-2">
                        <Award className="h-4 w-4 text-amber-500" />
                        {t('gradeDistribution')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {[
                        { label: t('excellent90'), color: 'text-emerald-600', bg: 'bg-emerald-500', filter: s => s.average_grade >= 90 },
                        { label: t('veryGood7589'), color: 'text-blue-600', bg: 'bg-blue-500', filter: s => s.average_grade >= 75 && s.average_grade < 90 },
                        { label: t('good6074'), color: 'text-amber-600', bg: 'bg-amber-500', filter: s => s.average_grade >= 60 && s.average_grade < 75 },
                        { label: t('needsWork60'), color: 'text-red-500', bg: 'bg-red-500', filter: s => s.average_grade > 0 && s.average_grade < 60 },
                      ].map((tier, idx) => {
                        const count = students.filter(tier.filter).length;
                        const pct = students.length > 0 ? Math.round((count / students.length) * 100) : 0;
                        return (
                          <div key={idx}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className={tier.color}>{tier.label}</span>
                              <span className="text-muted-foreground">{count} ({pct}%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-muted overflow-hidden">
                              <div className={`h-full rounded-full ${tier.bg} transition-all`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-cairo flex items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        {t('attendanceDistribution')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {[
                        { label: t('excellent95'), color: 'text-emerald-600', bg: 'bg-emerald-500', filter: s => s.attendance_rate >= 95 },
                        { label: t('good8594'), color: 'text-blue-600', bg: 'bg-blue-500', filter: s => s.attendance_rate >= 85 && s.attendance_rate < 95 },
                        { label: t('fair7584'), color: 'text-amber-600', bg: 'bg-amber-500', filter: s => s.attendance_rate >= 75 && s.attendance_rate < 85 },
                        { label: t('poor75'), color: 'text-red-500', bg: 'bg-red-500', filter: s => s.attendance_rate > 0 && s.attendance_rate < 75 },
                      ].map((tier, idx) => {
                        const count = students.filter(tier.filter).length;
                        const pct = students.length > 0 ? Math.round((count / students.length) * 100) : 0;
                        return (
                          <div key={idx}>
                            <div className="flex justify-between text-xs mb-1">
                              <span className={tier.color}>{tier.label}</span>
                              <span className="text-muted-foreground">{count} ({pct}%)</span>
                            </div>
                            <div className="h-2 rounded-full bg-muted overflow-hidden">
                              <div className={`h-full rounded-full ${tier.bg} transition-all`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-cairo flex items-center gap-2">
                        <Star className="h-4 w-4 text-amber-500" />
                        {t('topStudents2')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2.5">
                        {[...students]
                          .sort((a, b) => (b.average_grade || 0) - (a.average_grade || 0))
                          .slice(0, 5)
                          .map((student, idx) => (
                            <div
                              key={student.id}
                              className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/30 cursor-pointer transition-all"
                              onClick={() => navigate(`/teacher/students?id=${student.id}`)}
                            >
                              <div className="flex items-center gap-2.5">
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                                  idx === 0 ? 'bg-gradient-to-br from-amber-400 to-amber-500 text-white shadow-sm' :
                                  idx === 1 ? 'bg-gradient-to-br from-gray-300 to-gray-400 text-white' :
                                  idx === 2 ? 'bg-gradient-to-br from-amber-600 to-amber-700 text-white' :
                                  'bg-muted text-muted-foreground'
                                }`}>
                                  {idx + 1}
                                </div>
                                <span className="text-sm font-cairo">{student.full_name}</span>
                              </div>
                              <Badge className={`${getGradeColor(student.average_grade || 0)} border-0 bg-transparent`}>
                                {student.average_grade || 0}
                              </Badge>
                            </div>
                          ))}
                        {students.length === 0 && (
                          <p className="text-xs text-muted-foreground text-center py-4">{isRTL ? 'لا توجد بيانات' : 'No data'}</p>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-cairo flex items-center gap-2">
                        <TrendingUp className="h-4 w-4 text-emerald-500" />
                        {t('bestAttendance')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2.5">
                        {[...students]
                          .sort((a, b) => (b.attendance_rate || 0) - (a.attendance_rate || 0))
                          .slice(0, 5)
                          .map((student, idx) => (
                            <div
                              key={student.id}
                              className="flex items-center justify-between p-2 rounded-lg hover:bg-muted/30 cursor-pointer transition-all"
                              onClick={() => navigate(`/teacher/students?id=${student.id}`)}
                            >
                              <div className="flex items-center gap-2.5">
                                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                                  idx === 0 ? 'bg-gradient-to-br from-emerald-400 to-emerald-500 text-white shadow-sm' :
                                  idx === 1 ? 'bg-gradient-to-br from-emerald-300 to-emerald-400 text-white' :
                                  idx === 2 ? 'bg-gradient-to-br from-emerald-500 to-emerald-600 text-white' :
                                  'bg-muted text-muted-foreground'
                                }`}>
                                  {idx + 1}
                                </div>
                                <span className="text-sm font-cairo">{student.full_name}</span>
                              </div>
                              <Badge variant="outline" className="text-emerald-600 border-emerald-200 text-xs">
                                {student.attendance_rate || 0}%
                              </Badge>
                            </div>
                          ))}
                        {students.length === 0 && (
                          <p className="text-xs text-muted-foreground text-center py-4">{isRTL ? 'لا توجد بيانات' : 'No data'}</p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>
            </Tabs>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-cairo">{t('quickActions')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <Button
                    variant="outline"
                    className="h-auto py-3 flex-col gap-1.5"
                    onClick={() => navigate(`/teacher/attendance?class=${classId}`)}
                  >
                    <ClipboardCheck className="h-5 w-5 text-emerald-600" />
                    <span className="text-xs font-tajawal">{t('attendance3')}</span>
                  </Button>
                  <Button
                    variant="outline"
                    className="h-auto py-3 flex-col gap-1.5"
                    onClick={() => navigate(`/teacher/assessments?class=${classId}`)}
                  >
                    <FileText className="h-5 w-5 text-blue-600" />
                    <span className="text-xs font-tajawal">{t('assessments')}</span>
                  </Button>
                  <Button
                    variant="outline"
                    className="h-auto py-3 flex-col gap-1.5"
                    onClick={() => navigate(`/teacher/behavior?class=${classId}`)}
                  >
                    <Star className="h-5 w-5 text-purple-600" />
                    <span className="text-xs font-tajawal">{t('behavior')}</span>
                  </Button>
                  <Button
                    variant="outline"
                    className="h-auto py-3 flex-col gap-1.5"
                    onClick={() => navigate(`/teacher/reports?class=${classId}`)}
                  >
                    <BarChart3 className="h-5 w-5 text-amber-600" />
                    <span className="text-xs font-tajawal">{t('reports')}</span>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
