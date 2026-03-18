import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { toast } from 'sonner';
import {
  Users, BookOpen, Calendar, GraduationCap, Clock,
  Play, RefreshCw, Loader2,
  Target, Award, BarChart3,
  CheckCircle2, Activity, Flame, Building2, MapPin, Star, Briefcase
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';
import { formatHijriDate } from '../../utils/hijriDate';

const getTimeUntilLesson = (lessonTime) => {
  if (!lessonTime) return null;
  const now = new Date();
  const [hours, minutes] = lessonTime.split(':').map(Number);
  const lessonDate = new Date();
  lessonDate.setHours(hours, minutes, 0, 0);
  const lessonEndDate = new Date(lessonDate);
  lessonEndDate.setMinutes(lessonEndDate.getMinutes() + 45);
  const diff = lessonDate - now;
  const diffMinutes = Math.floor(diff / 60000);
  if (diff < 0 && now < lessonEndDate) return { status: 'ongoing', minutes: Math.abs(diffMinutes) };
  if (diff < 0) return { status: 'ended', minutes: Math.abs(diffMinutes) };
  if (diffMinutes <= 10) return { status: 'ready', minutes: diffMinutes };
  if (diffMinutes <= 30) return { status: 'soon', minutes: diffMinutes };
  return { status: 'upcoming', minutes: diffMinutes };
};

export default function TeacherHomePage() {
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [teacherInfo, setTeacherInfo] = useState(null);
  const [todayLessons, setTodayLessons] = useState([]);
  const { nassaqError, nassaqConfirm } = useNassaqAlert();
  const [stats, setStats] = useState({
    classesCount: 0,
    studentsCount: 0,
    stage: ''
  });
  const [classMetrics, setClassMetrics] = useState(null);

  const teacherId = user?.teacher_id || user?.id;

  const fetchTeacherData = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const dashboardRes = await api.get(`/teacher/dashboard/${teacherId}`).catch(() => null);
      if (dashboardRes?.data) {
        const data = dashboardRes.data;
        setTeacherInfo({
          name: data.teacher?.full_name || data.teacher?.name || user?.full_name || (isRTL ? 'معلم' : 'Teacher'),
          rank: data.teacher?.rank || '',
          qualification: data.teacher?.qualification || '',
          specialization: data.teacher?.specialization || '',
          school: data.school_name || (isRTL ? 'المدرسة' : 'School'),
          schoolCity: data.school_city || '',
          schoolType: data.school_type || '',
          stage: data.school_stage || '',
          subjectNames: data.subject_names || [],
          weeklySessions: data.stats?.weekly_sessions || 0,
          subjectsCount: data.stats?.subjects_count || 0
        });
        setStats({
          classesCount: data.stats?.my_classes || 0,
          studentsCount: data.stats?.my_students || 0,
          stage: data.school_stage || ''
        });
        const lessons = (data.today_schedule || []).map((lesson, idx) => ({
          id: lesson.session_id || lesson.id || `lesson-${idx}`,
          schedule_session_id: lesson.schedule_session_id || lesson.id,
          subject: lesson.subject || lesson.subject_name || (isRTL ? 'مادة' : 'Subject'),
          className: lesson.class_name || (isRTL ? 'فصل' : 'Class'),
          classId: lesson.class_id,
          subjectId: lesson.subject_id,
          time: lesson.time || lesson.start_time || `${8 + idx}:00`,
          endTime: lesson.end_time || `${9 + idx}:00`,
          period: lesson.period || lesson.slot_number || idx + 1
        }));
        setTodayLessons(lessons);
      } else {
        setTeacherInfo({
          name: user?.full_name || (isRTL ? 'معلم' : 'Teacher'),
          school: isRTL ? 'المدرسة' : 'School',
          stage: isRTL ? 'المرحلة' : 'Stage'
        });
      }
    } catch (error) {
      console.error('Error fetching teacher data:', error);
      nassaqError(isRTL ? 'خطأ في تحميل البيانات' : 'Error loading data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, teacherId, user, isRTL, nassaqError]);

  useEffect(() => {
    fetchTeacherData();
    const interval = setInterval(fetchTeacherData, 60000);
    return () => clearInterval(interval);
  }, [fetchTeacherData]);

  useEffect(() => {
    if (!teacherId) return;
    const fetchMetrics = async () => {
      try {
        const res = await api.get(`/teacher/${teacherId}/class-metrics`);
        if (res.data) {
          const classes = Object.values(res.data);
          if (classes.length > 0) {
            const avgAttendance = Math.round(classes.reduce((s, c) => s + (c.attendance_rate || 0), 0) / classes.length);
            const avgParticipation = Math.round(classes.reduce((s, c) => s + (c.participation_rate || 0), 0) / classes.length);
            const avgPerformance = Math.round(classes.reduce((s, c) => s + (c.avg_performance || 0), 0) / classes.length);
            const totalSessions = classes.reduce((s, c) => s + (c.total_sessions || 0), 0);
            setClassMetrics({ avgAttendance, avgParticipation, avgPerformance, totalSessions });
          }
        }
      } catch {}
    };
    fetchMetrics();
  }, [teacherId, api]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchTeacherData();
  };

  const handleEndActiveSession = async (activeSessionId) => {
    try {
      await api.post(`/session/${activeSessionId}/end`);
      toast.success(isRTL ? 'تم إنهاء الحصة السابقة' : 'Previous session ended');
      await fetchTeacherData();
    } catch {
      nassaqError(isRTL ? 'خطأ في إنهاء الحصة' : 'Error ending session');
    }
  };

  const handleStartClass = async (lesson) => {
    const lessonData = {
      lesson,
      schedule_session_id: lesson.schedule_session_id,
      class_id: lesson.classId,
      subject_id: lesson.subjectId
    };
    sessionStorage.setItem('current_lesson', JSON.stringify(lessonData));
    navigate('/teacher/session/start', { state: lessonData });
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        {refreshing && (
          <div className="fixed top-0 left-0 right-0 z-50 flex justify-center py-2 bg-brand-turquoise/10 backdrop-blur-sm">
            <Loader2 className="h-5 w-5 animate-spin text-brand-turquoise" />
          </div>
        )}

        <div className="p-4 space-y-4 max-w-lg mx-auto">

          {/* Teacher Info Card */}
          <Card className="overflow-hidden border-0 shadow-lg">
            <div className="relative bg-gradient-to-br from-brand-navy via-brand-navy to-slate-900 text-white overflow-hidden">
              <div className="absolute inset-0 nassaq-pattern opacity-[0.05] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
              <CardContent className="p-5 relative">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_20%,rgba(56,189,248,0.08),transparent)]" />
                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <Avatar className="h-16 w-16 border-2 border-brand-turquoise/40 shadow-xl">
                          <AvatarImage src={user?.avatar_url} />
                          <AvatarFallback className="bg-gradient-to-br from-brand-turquoise to-brand-purple text-white text-xl font-bold">
                            {teacherInfo?.name?.charAt(0) || 'م'}
                          </AvatarFallback>
                        </Avatar>
                        <div className="absolute -bottom-0.5 -end-0.5 w-5 h-5 rounded-md bg-emerald-500 flex items-center justify-center border-2 border-brand-navy">
                          <CheckCircle2 className="h-2.5 w-2.5 text-white" />
                        </div>
                      </div>
                      <div className="min-w-0">
                        <h1 className="font-cairo text-lg font-bold leading-tight">
                          {isRTL ? `الأستاذ ${teacherInfo?.name}` : teacherInfo?.name}
                        </h1>
                        {teacherInfo?.rank && (
                          <Badge className="mt-1 bg-brand-turquoise/20 text-brand-turquoise border-brand-turquoise/30 text-[11px] font-tajawal px-2 py-0">
                            <Star className="h-3 w-3 me-1" />
                            {teacherInfo.rank}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-white/50 hover:text-white hover:bg-white/10 rounded-xl flex-shrink-0"
                      onClick={handleRefresh}
                      disabled={refreshing}
                    >
                      <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                    </Button>
                  </div>

                  <div className="space-y-1.5 mb-3 ps-1">
                    <div className="flex items-center gap-2 text-white/60 text-sm">
                      <Building2 className="h-3.5 w-3.5 text-brand-turquoise/70 flex-shrink-0" />
                      <span className="font-tajawal truncate">{teacherInfo?.school}</span>
                      {teacherInfo?.schoolCity && (
                        <span className="flex items-center gap-1 text-white/40 text-xs">
                          <MapPin className="h-3 w-3" />{teacherInfo.schoolCity}
                        </span>
                      )}
                    </div>
                    {teacherInfo?.specialization && (
                      <div className="flex items-center gap-2 text-white/60 text-sm">
                        <BookOpen className="h-3.5 w-3.5 text-brand-turquoise/70 flex-shrink-0" />
                        <span className="font-tajawal truncate">{teacherInfo.specialization}</span>
                      </div>
                    )}
                    {teacherInfo?.qualification && (
                      <div className="flex items-center gap-2 text-white/60 text-sm">
                        <GraduationCap className="h-3.5 w-3.5 text-brand-turquoise/70 flex-shrink-0" />
                        <span className="font-tajawal">{teacherInfo.qualification}</span>
                      </div>
                    )}
                  </div>

                  <div className="text-center py-2 border-t border-white/10">
                    <p className="font-cairo text-white/70 text-sm">
                      {formatHijriDate()}
                    </p>
                  </div>

                  <div className="grid grid-cols-4 gap-2 mt-3">
                    {[
                      { icon: BookOpen, value: loading ? '-' : stats.classesCount, label: isRTL ? 'فصول' : 'Classes' },
                      { icon: Users, value: loading ? '-' : stats.studentsCount, label: isRTL ? 'طلاب' : 'Students' },
                      { icon: Briefcase, value: loading ? '-' : (teacherInfo?.subjectsCount || 0), label: isRTL ? 'مواد' : 'Subjects' },
                      { icon: Calendar, value: loading ? '-' : (teacherInfo?.weeklySessions || 0), label: isRTL ? 'حصة/أسبوع' : 'Wk Sessions' },
                    ].map((item, i) => (
                      <div key={i} className="text-center p-2.5 rounded-xl bg-white/5 border border-white/5">
                        <item.icon className="h-4 w-4 mx-auto mb-1 text-brand-turquoise" />
                        <div className="font-bold text-lg leading-tight">{item.value}</div>
                        <div className="text-[9px] text-white/40 font-tajawal leading-tight">{item.label}</div>
                      </div>
                    ))}
                  </div>

                  <Button
                    className="w-full mt-4 bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise/90 hover:to-cyan-400 text-white rounded-xl shadow-lg shadow-brand-turquoise/20 font-cairo"
                    onClick={() => navigate('/teacher/schedule')}
                  >
                    <Calendar className="h-4 w-4 me-2" />
                    {isRTL ? 'عرض الجدول' : 'View Schedule'}
                  </Button>
                </div>
              </CardContent>
            </div>
          </Card>

          {classMetrics && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[
                { label: isRTL ? 'الحضور' : 'Attendance', value: `${classMetrics.avgAttendance}%`, icon: CheckCircle2, gradient: 'from-emerald-500 to-emerald-600' },
                { label: isRTL ? 'المشاركة' : 'Participation', value: `${classMetrics.avgParticipation}%`, icon: Activity, gradient: 'from-blue-500 to-blue-600' },
                { label: isRTL ? 'الأداء' : 'Performance', value: `${classMetrics.avgPerformance}%`, icon: Target, gradient: 'from-purple-500 to-purple-600' },
                { label: isRTL ? 'الحصص' : 'Sessions', value: classMetrics.totalSessions, icon: Flame, gradient: 'from-amber-500 to-amber-600' },
              ].map(m => (
                <div key={m.label} className="bg-background rounded-xl p-3 text-center border border-border/50 shadow-sm">
                  <div className={`w-8 h-8 mx-auto rounded-lg bg-gradient-to-br ${m.gradient} flex items-center justify-center mb-1.5 shadow-md`}>
                    <m.icon className="h-3.5 w-3.5 text-white" />
                  </div>
                  <div className="text-base font-bold font-cairo text-foreground">{m.value}</div>
                  <div className="text-[10px] text-muted-foreground font-tajawal">{m.label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Today's Lessons */}
          <div>
            <h2 className="font-cairo font-bold text-lg text-foreground mb-3 flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-turquoise to-cyan-600 flex items-center justify-center shadow-md">
                <Clock className="h-4 w-4 text-white" />
              </div>
              {isRTL ? 'حصص اليوم' : "Today's Lessons"}
              {todayLessons.length > 0 && (
                <Badge variant="secondary" className="font-cairo text-xs">{todayLessons.length}</Badge>
              )}
            </h2>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
              </div>
            ) : todayLessons.length === 0 ? (
              <Card className="border-dashed border-border/50">
                <CardContent className="text-center py-12">
                  <Calendar className="h-12 w-12 mx-auto mb-3 text-muted-foreground/20" />
                  <p className="text-muted-foreground font-tajawal">{isRTL ? 'لا توجد حصص اليوم' : 'No lessons today'}</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {todayLessons.map((lesson, index) => {
                  const timeStatus = getTimeUntilLesson(lesson.time);
                  const isFirstLesson = index === 0;
                  const isEnded = timeStatus?.status === 'ended';

                  const cardBackground = isFirstLesson
                    ? { background: 'linear-gradient(135deg, #0d9488, #0891b2)' }
                    : { background: 'linear-gradient(135deg, #3b82f6, #6366f1)' };

                  return (
                    <div
                      key={lesson.id}
                      className={`rounded-2xl overflow-hidden transition-all duration-300 shadow-lg border border-white/10`}
                      style={cardBackground}
                      data-testid={`lesson-card-${lesson.id}`}
                    >
                      <div className="p-5">
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-2">
                            {isFirstLesson ? (
                              <Badge className="bg-white/20 text-white border-0 animate-pulse font-cairo text-xs">
                                {isRTL ? 'الحصة الحالية' : 'Current'}
                              </Badge>
                            ) : (
                              <Badge className="bg-white/15 text-white border-0 font-cairo text-xs">
                                {isRTL ? (isEnded ? 'حصة سابقة' : 'الحصة القادمة') : (isEnded ? 'Previous' : 'Upcoming')}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 text-white/80 text-sm">
                            <Clock className="h-3.5 w-3.5" />
                            <span className="font-mono font-bold">{lesson.time}</span>
                          </div>
                        </div>

                        <div className={`${isRTL ? 'text-right' : 'text-left'} mb-4`}>
                          <h3 className="font-cairo font-bold text-2xl text-white">
                            {lesson.subject}
                          </h3>
                          <p className="text-sm mt-0.5 text-white/60">
                            {lesson.className} • {isRTL ? `الحصة ${lesson.period}` : `Period ${lesson.period}`}
                          </p>
                        </div>

                        <Button
                          className="w-full h-13 text-lg font-bold rounded-xl transition-all font-cairo bg-white/95 text-brand-navy hover:bg-white shadow-lg"
                          onClick={() => handleStartClass(lesson)}
                          data-testid={`start-class-btn-${lesson.id}`}
                        >
                          <Play className="h-5 w-5 me-2" />
                          {isRTL ? 'ابدأ الحصة' : 'Start Class'}
                        </Button>

                        {!isFirstLesson && index > 0 && (
                          <Button
                            variant="ghost"
                            className="w-full mt-2 font-cairo text-white/60 hover:text-white hover:bg-white/10"
                            onClick={() => navigate('/teacher/schedule')}
                          >
                            {isRTL ? 'إدارة الدرس' : 'Manage Lesson'}
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick Navigation */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
            {[
              { icon: BookOpen, label: isRTL ? 'فصولي' : 'Classes', path: '/teacher/classes', gradient: 'from-blue-500 to-blue-600' },
              { icon: Users, label: isRTL ? 'طلابي' : 'Students', path: '/teacher/students', gradient: 'from-emerald-500 to-emerald-600' },
              { icon: BarChart3, label: isRTL ? 'التقارير' : 'Reports', path: '/teacher/reports', gradient: 'from-purple-500 to-purple-600' },
              { icon: Award, label: isRTL ? 'إنجازاتي' : 'Achievements', path: '/teacher/achievements', gradient: 'from-amber-500 to-amber-600' },
            ].map(nav => (
              <button
                key={nav.path}
                className="flex flex-col items-center gap-2 p-4 rounded-xl border border-border/50 bg-background hover:border-brand-turquoise/30 hover:shadow-md transition-all group"
                onClick={() => navigate(nav.path)}
              >
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${nav.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
                  <nav.icon className="h-5 w-5 text-white" />
                </div>
                <span className="text-xs font-cairo font-medium text-foreground">{nav.label}</span>
              </button>
            ))}
          </div>

        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
