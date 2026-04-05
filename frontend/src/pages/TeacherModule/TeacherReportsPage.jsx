import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Progress } from '../../components/ui/progress';
import { Avatar, AvatarFallback } from '../../components/ui/avatar';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  BarChart3, TrendingUp, TrendingDown, Users, ClipboardCheck,
  FileText, Loader2, RefreshCw, Download, Calendar, Star,
  Award, AlertTriangle, BookOpen, GraduationCap, Activity,
  Target, Flame, Eye, ChevronRight, ChevronLeft, Minus,
  MessageSquare, Brain, Lightbulb, Shield, ThumbsUp, ThumbsDown,
  UserCheck, AlertCircle, Sparkles
} from 'lucide-react';

export default function TeacherReportsPage() {
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [reportData, setReportData] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [exporting, setExporting] = useState(null);
  const [timePeriod, setTimePeriod] = useState('all');

  const { nassaqError } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  const fetchClasses = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const classesRes = await api.get(`/teacher/classes/${teacherId}`).catch(() => null);
      const classList = Array.isArray(classesRes?.data) ? classesRes.data : [];
      setClasses(classList);
      if (classList.length > 0 && !selectedClass) {
        setSelectedClass(classList[0].id);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, selectedClass]);

  const schoolId = user?.tenant_id || user?.school_id || '';

  const fetchReportData = useCallback(async () => {
    if (!selectedClass) return;
    setLoading(true);
    try {
      const [studentsRes, attendanceRes, gradesRes, behaviorRes, metricsRes] = await Promise.all([
        api.get(`/classes/${selectedClass}/students`).catch(() => null),
        api.get(`/attendance/class/${selectedClass}?start_date=2020-01-01`).catch(() => null),
        api.get(`/assessments?class_id=${selectedClass}`).catch(() => null),
        schoolId ? api.get(`/behaviour-records/class/${selectedClass}?school_id=${schoolId}`).catch(() => null) : Promise.resolve(null),
        teacherId ? api.get(`/teacher/${teacherId}/class-metrics`).catch(() => null) : Promise.resolve(null),
      ]);

      const students = Array.isArray(studentsRes?.data) ? studentsRes.data : [];
      const attendance = Array.isArray(attendanceRes?.data) ? attendanceRes.data : [];
      const grades = Array.isArray(gradesRes?.data) ? gradesRes.data : [];
      const behaviorRaw = behaviorRes?.data;
      let behavior = [];
      let behaviorSummary = null;
      if (Array.isArray(behaviorRaw)) {
        behavior = behaviorRaw;
      } else if (behaviorRaw && typeof behaviorRaw === 'object') {
        behaviorSummary = behaviorRaw;
        behavior = [];
      }
      const classMetrics = (metricsRes?.data && typeof metricsRes.data === 'object') ? (metricsRes.data[selectedClass] || {}) : {};

      const filterByTime = (items, dateField = 'created_at') => {
        if (timePeriod === 'all') return items;
        const now = new Date();
        const cutoff = new Date();
        if (timePeriod === 'today') cutoff.setHours(0, 0, 0, 0);
        else if (timePeriod === 'week') cutoff.setDate(now.getDate() - 7);
        else if (timePeriod === 'month') cutoff.setMonth(now.getMonth() - 1);
        else if (timePeriod === 'semester') cutoff.setMonth(now.getMonth() - 6);
        return items.filter(item => {
          const d = item[dateField] || item.date || item.created_at;
          return d && new Date(d) >= cutoff;
        });
      };

      const filteredAtt = filterByTime(attendance, 'date');
      const filteredGrades = filterByTime(grades);
      const filteredBehavior = filterByTime(behavior);

      const totalStudents = students.length;
      const presentCount = filteredAtt.filter(a => a.status === 'present').length;
      const absentCount = filteredAtt.filter(a => a.status === 'absent').length;
      const lateCount = filteredAtt.filter(a => a.status === 'late').length;
      const attendanceRate = filteredAtt.length > 0 ? Math.round((presentCount / filteredAtt.length) * 100) : (classMetrics.attendance_rate || 0);

      const avgGrade = filteredGrades.length > 0 ? Math.round(filteredGrades.reduce((sum, g) => sum + (g.score || g.percentage || 0), 0) / filteredGrades.length) : 0;

      const positiveBehaviorCount = behaviorSummary ? (behaviorSummary.positive_total || 0) : filteredBehavior.filter(b => b.type === 'positive' || (b.points || 0) > 0).length;
      const negativeBehaviorCount = behaviorSummary ? (behaviorSummary.negative_total || 0) : filteredBehavior.filter(b => b.type === 'negative' || (b.points || 0) < 0).length;
      const totalBehaviorRecords = behaviorSummary ? (behaviorSummary.total_records || 0) : filteredBehavior.length;

      const gradeDistribution = { excellent: 0, veryGood: 0, good: 0, needsWork: 0 };
      const studentGrades = {};
      filteredGrades.forEach(g => {
        const sid = g.student_id;
        if (!studentGrades[sid]) studentGrades[sid] = [];
        studentGrades[sid].push(g.score || g.percentage || 0);
      });
      Object.values(studentGrades).forEach(scores => {
        const avg = scores.reduce((s, v) => s + v, 0) / scores.length;
        if (avg >= 90) gradeDistribution.excellent++;
        else if (avg >= 75) gradeDistribution.veryGood++;
        else if (avg >= 60) gradeDistribution.good++;
        else gradeDistribution.needsWork++;
      });

      const topPerformers = Object.entries(studentGrades)
        .map(([sid, scores]) => {
          const s = students.find(st => st.id === sid);
          return { id: sid, full_name: s?.full_name || sid, avg: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) };
        })
        .sort((a, b) => b.avg - a.avg).slice(0, 5);

      const studentAttendance = {};
      filteredAtt.forEach(a => {
        if (!studentAttendance[a.student_id]) studentAttendance[a.student_id] = { total: 0, present: 0, absent: 0, late: 0 };
        studentAttendance[a.student_id].total++;
        if (a.status === 'present') studentAttendance[a.student_id].present++;
        if (a.status === 'absent') studentAttendance[a.student_id].absent++;
        if (a.status === 'late') studentAttendance[a.student_id].late++;
      });

      const mostAbsent = students.map(s => {
        const att = studentAttendance[s.id];
        return { ...s, absentCount: att?.absent || 0, attRate: att && att.total > 0 ? Math.round((att.present / att.total) * 100) : null };
      }).filter(s => s.absentCount > 0).sort((a, b) => b.absentCount - a.absentCount).slice(0, 5);

      const mostPresent = students.map(s => {
        const att = studentAttendance[s.id];
        return { ...s, presentCount: att?.present || 0, attRate: att && att.total > 0 ? Math.round((att.present / att.total) * 100) : null };
      }).filter(s => s.presentCount > 0).sort((a, b) => b.presentCount - a.presentCount).slice(0, 5);

      const studentBehavior = {};
      filteredBehavior.forEach(b => {
        if (!studentBehavior[b.student_id]) studentBehavior[b.student_id] = { positive: 0, negative: 0 };
        if (b.type === 'positive' || (b.points || 0) > 0) studentBehavior[b.student_id].positive++;
        else studentBehavior[b.student_id].negative++;
      });

      const behaviorTypes = {};
      filteredBehavior.forEach(b => {
        const t = b.category || b.behavior_type || b.type || 'other';
        behaviorTypes[t] = (behaviorTypes[t] || 0) + 1;
      });

      const studentParticipation = {};
      const participationData = await api.get(`/classes/${selectedClass}/student-stats`).catch(() => ({ data: {} }));
      const pStats = participationData.data?.students || [];

      const needsAttention = students.map(s => {
        const issues = [];
        const att = studentAttendance[s.id];
        if (att && att.total > 0 && (att.present / att.total) < 0.8) issues.push('attendance');
        const sg = studentGrades[s.id];
        if (sg && sg.length > 0) {
          const avg = sg.reduce((a, b) => a + b, 0) / sg.length;
          if (avg < 60) issues.push('grades');
        }
        const sb = studentBehavior[s.id];
        if (sb && sb.negative >= 2) issues.push('behavior');
        return { ...s, issues, attRate: att ? Math.round((att.present / att.total) * 100) : null, gradeAvg: sg ? Math.round(sg.reduce((a, b) => a + b, 0) / sg.length) : null };
      }).filter(s => s.issues.length > 0).sort((a, b) => b.issues.length - a.issues.length).slice(0, 8);

      const attendanceByDate = {};
      filteredAtt.forEach(a => {
        const date = a.date || (a.created_at ? a.created_at.split('T')[0] : null);
        if (!date) return;
        if (!attendanceByDate[date]) attendanceByDate[date] = { total: 0, present: 0 };
        attendanceByDate[date].total++;
        if (a.status === 'present') attendanceByDate[date].present++;
      });
      const weeklyTrend = Object.entries(attendanceByDate).sort(([a], [b]) => a.localeCompare(b)).slice(-7).map(([date, d]) => ({
        date, displayDate: new Date(date).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { weekday: 'short', day: 'numeric' }),
        rate: d.total > 0 ? Math.round((d.present / d.total) * 100) : 0,
      }));

      setReportData({
        summary: { totalStudents, attendanceRate, avgGrade, positiveBehavior: positiveBehaviorCount, negativeBehavior: negativeBehaviorCount, assessmentsCount: filteredGrades.length, behaviorRecords: totalBehaviorRecords, totalSessions: classMetrics.total_sessions || 0, participationRate: classMetrics.participation_rate || 0, presentCount, absentCount, lateCount },
        gradeDistribution, topPerformers, needsAttention, weeklyTrend, mostAbsent, mostPresent, behaviorTypes, studentBehavior, studentGrades,
      });
    } catch (error) {
      console.error('Error:', error);
      nassaqError(isRTL ? 'خطأ في تحميل التقارير' : 'Error loading reports');
    } finally {
      setLoading(false);
    }
  }, [api, selectedClass, teacherId, schoolId, isRTL, timePeriod]);

  useEffect(() => { fetchClasses(); }, [fetchClasses]);
  useEffect(() => { if (selectedClass) fetchReportData(); }, [selectedClass, fetchReportData]);

  const getGradeColor = (grade) => {
    if (grade >= 90) return 'text-green-600 bg-green-100 dark:bg-green-900/40';
    if (grade >= 75) return 'text-blue-600 bg-blue-100 dark:bg-blue-900/40';
    if (grade >= 60) return 'text-amber-600 bg-amber-100 dark:bg-amber-900/40';
    return 'text-red-600 bg-red-100 dark:bg-red-900/40';
  };

  const handleExport = async (fmt) => {
    setExporting(fmt);
    try {
      toast.info(isRTL ? 'جاري تحضير التقرير...' : 'Preparing report...');
      const response = await api.get(`/export/report/teacher_activity?format=${fmt}`, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement('a');
      a.href = url; a.download = `teacher_activity.${fmt}`; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      toast.success(isRTL ? 'تم تصدير التقرير بنجاح' : 'Report exported successfully');
    } catch (err) {
      console.error('Export error:', err);
      nassaqError(isRTL ? 'فشل تصدير التقرير' : 'Export failed');
    } finally { setExporting(null); }
  };

  const selectedClassName = classes.find(c => c.id === selectedClass)?.name || '';
  const rd = reportData;

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {isRTL ? 'التقارير والتحليلات' : 'Reports & Analytics'}
              </h1>
              <p className="text-sm text-muted-foreground">
                {selectedClassName ? (isRTL ? `تقارير: ${selectedClassName}` : `Reports: ${selectedClassName}`) : (isRTL ? 'اختر فصلاً لعرض التقارير' : 'Select a class')}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-full sm:w-[160px]"><SelectValue placeholder={isRTL ? 'الفصل' : 'Class'} /></SelectTrigger>
                <SelectContent>{classes.map(cls => (<SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>))}</SelectContent>
              </Select>
              <Select value={timePeriod} onValueChange={setTimePeriod}>
                <SelectTrigger className="w-full sm:w-[130px]"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{isRTL ? 'كل الفترات' : 'All Time'}</SelectItem>
                  <SelectItem value="today">{isRTL ? 'اليوم' : 'Today'}</SelectItem>
                  <SelectItem value="week">{isRTL ? 'الأسبوع' : 'This Week'}</SelectItem>
                  <SelectItem value="month">{isRTL ? 'الشهر' : 'This Month'}</SelectItem>
                  <SelectItem value="semester">{isRTL ? 'الفصل الدراسي' : 'Semester'}</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={fetchReportData} disabled={loading}><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} /></Button>
              <div className="flex border rounded-lg overflow-hidden">
                {['pdf', 'csv', 'xlsx'].map(fmt => (
                  <Button key={fmt} variant="ghost" size="sm" className="rounded-none border-e last:border-e-0 h-8 px-3 text-xs" onClick={() => handleExport(fmt)} disabled={!!exporting}>
                    {exporting === fmt ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3 me-1" />}{fmt.toUpperCase()}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 max-w-[1400px] mx-auto space-y-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
              <p className="text-sm text-muted-foreground font-tajawal">{isRTL ? 'جاري تحميل التقارير...' : 'Loading reports...'}</p>
            </div>
          ) : !rd ? (
            <Card><CardContent className="text-center py-16"><BarChart3 className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" /><p className="text-muted-foreground font-cairo">{isRTL ? 'اختر فصلاً' : 'Select a class'}</p></CardContent></Card>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
                {[
                  { label: isRTL ? 'الطلاب' : 'Students', value: rd.summary.totalStudents, icon: Users, color: 'text-brand-navy', bg: 'bg-blue-50 dark:bg-blue-950/30' },
                  { label: isRTL ? 'الحضور' : 'Attendance', value: `${rd.summary.attendanceRate}%`, icon: ClipboardCheck, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30' },
                  { label: isRTL ? 'المعدل' : 'Avg Grade', value: rd.summary.avgGrade || '-', icon: FileText, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30' },
                  { label: isRTL ? 'المشاركة' : 'Participation', value: `${rd.summary.participationRate}%`, icon: Activity, color: 'text-purple-600', bg: 'bg-purple-50 dark:bg-purple-950/30' },
                  { label: isRTL ? 'الحصص' : 'Sessions', value: rd.summary.totalSessions, icon: Flame, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/30' },
                  { label: isRTL ? 'إيجابي' : 'Positive', value: rd.summary.positiveBehavior, icon: TrendingUp, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30' },
                  { label: isRTL ? 'سلبي' : 'Negative', value: rd.summary.negativeBehavior, icon: TrendingDown, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30' },
                  { label: isRTL ? 'التقييمات' : 'Assessments', value: rd.summary.assessmentsCount, icon: BookOpen, color: 'text-purple-600', bg: 'bg-purple-50 dark:bg-purple-950/30' },
                ].map(stat => (
                  <Card key={stat.label} className="overflow-hidden"><CardContent className={`p-3 text-center ${stat.bg}`}>
                    <stat.icon className={`h-5 w-5 mx-auto mb-1.5 ${stat.color}`} />
                    <div className={`text-xl font-bold font-cairo ${stat.color}`}>{stat.value}</div>
                    <div className="text-[10px] text-muted-foreground font-tajawal">{stat.label}</div>
                  </CardContent></Card>
                ))}
              </div>

              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="mb-4 bg-muted/50 flex-wrap">
                  <TabsTrigger value="overview" className="gap-1.5"><BarChart3 className="h-3.5 w-3.5" />{isRTL ? 'نظرة عامة' : 'Overview'}</TabsTrigger>
                  <TabsTrigger value="attendance" className="gap-1.5"><ClipboardCheck className="h-3.5 w-3.5" />{isRTL ? 'الحضور' : 'Attendance'}</TabsTrigger>
                  <TabsTrigger value="behavior" className="gap-1.5"><Shield className="h-3.5 w-3.5" />{isRTL ? 'السلوك' : 'Behavior'}</TabsTrigger>
                  <TabsTrigger value="grades" className="gap-1.5"><Star className="h-3.5 w-3.5" />{isRTL ? 'الدرجات' : 'Grades'}</TabsTrigger>
                  <TabsTrigger value="attention" className="gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />{isRTL ? 'يحتاج متابعة' : 'Needs Attention'}
                    {rd.needsAttention.length > 0 && <Badge className="bg-amber-500 text-white text-[9px] px-1.5 h-4 border-0">{rd.needsAttention.length}</Badge>}
                  </TabsTrigger>
                  <TabsTrigger value="trend" className="gap-1.5"><TrendingUp className="h-3.5 w-3.5" />{isRTL ? 'الاتجاه' : 'Trends'}</TabsTrigger>
                </TabsList>

                <TabsContent value="overview">
                  <div className="grid md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><BarChart3 className="h-4 w-4 text-brand-turquoise" />{isRTL ? 'توزيع الدرجات' : 'Grade Distribution'}</CardTitle></CardHeader>
                      <CardContent className="space-y-3">
                        {[
                          { label: isRTL ? 'ممتاز (90+)' : 'Excellent (90+)', count: rd.gradeDistribution.excellent, color: 'bg-green-500', textColor: 'text-green-600' },
                          { label: isRTL ? 'جيد جداً (75-89)' : 'Very Good (75-89)', count: rd.gradeDistribution.veryGood, color: 'bg-blue-500', textColor: 'text-blue-600' },
                          { label: isRTL ? 'جيد (60-74)' : 'Good (60-74)', count: rd.gradeDistribution.good, color: 'bg-amber-500', textColor: 'text-amber-600' },
                          { label: isRTL ? 'يحتاج تحسين (<60)' : 'Needs Work (<60)', count: rd.gradeDistribution.needsWork, color: 'bg-red-500', textColor: 'text-red-600' },
                        ].map(tier => {
                          const pct = rd.summary.totalStudents > 0 ? (tier.count / rd.summary.totalStudents) * 100 : 0;
                          return (<div key={tier.label}><div className="flex justify-between text-sm mb-1"><span className={`${tier.textColor} font-medium text-xs`}>{tier.label}</span><span className="text-xs font-bold font-cairo">{tier.count} ({Math.round(pct)}%)</span></div><div className="h-2.5 bg-muted/30 rounded-full overflow-hidden"><div className={`h-full ${tier.color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} /></div></div>);
                        })}
                        {Object.values(rd.gradeDistribution).every(v => v === 0) && (<p className="text-center text-sm text-muted-foreground py-4">{isRTL ? 'لا توجد درجات' : 'No grades yet'}</p>)}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><Award className="h-4 w-4 text-amber-500" />{isRTL ? 'المتفوقون' : 'Top Performers'}</CardTitle></CardHeader>
                      <CardContent>
                        {rd.topPerformers.length === 0 ? (<div className="text-center py-8 text-sm text-muted-foreground">{isRTL ? 'لا توجد بيانات' : 'No data'}</div>) : (
                          <div className="space-y-2">{rd.topPerformers.map((student, idx) => (
                            <div key={student.id || idx} className="flex items-center justify-between p-2.5 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                              <div className="flex items-center gap-3">
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm shrink-0 ${idx === 0 ? 'bg-amber-400 text-white shadow-sm' : idx === 1 ? 'bg-gray-300 text-gray-700' : idx === 2 ? 'bg-amber-600 text-white' : 'bg-muted text-muted-foreground'}`}>{idx + 1}</div>
                                <span className="font-medium text-sm">{student.full_name}</span>
                              </div>
                              <Badge className={`${getGradeColor(student.avg)} border-0 font-cairo`}>{student.avg}%</Badge>
                            </div>
                          ))}</div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>

                <TabsContent value="attendance">
                  <div className="grid md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><ClipboardCheck className="h-4 w-4 text-green-500" />{isRTL ? 'ملخص الحضور' : 'Attendance Summary'}</CardTitle></CardHeader>
                      <CardContent className="space-y-4">
                        <div className="grid grid-cols-3 gap-3 text-center">
                          <div className="p-3 rounded-xl bg-green-50 dark:bg-green-950/30"><div className="text-2xl font-bold font-cairo text-green-600">{rd.summary.presentCount}</div><div className="text-[10px] text-muted-foreground">{isRTL ? 'حاضر' : 'Present'}</div></div>
                          <div className="p-3 rounded-xl bg-red-50 dark:bg-red-950/30"><div className="text-2xl font-bold font-cairo text-red-600">{rd.summary.absentCount}</div><div className="text-[10px] text-muted-foreground">{isRTL ? 'غائب' : 'Absent'}</div></div>
                          <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30"><div className="text-2xl font-bold font-cairo text-amber-600">{rd.summary.lateCount}</div><div className="text-[10px] text-muted-foreground">{isRTL ? 'متأخر' : 'Late'}</div></div>
                        </div>
                        <div><div className="flex justify-between text-sm mb-1"><span className="text-muted-foreground text-xs">{isRTL ? 'نسبة الحضور العامة' : 'Overall Attendance'}</span><span className="font-bold font-cairo text-xs">{rd.summary.attendanceRate}%</span></div><Progress value={rd.summary.attendanceRate} className="h-2.5" /></div>
                      </CardContent>
                    </Card>
                    <div className="space-y-4">
                      <Card>
                        <CardHeader className="pb-2"><CardTitle className="text-sm font-cairo flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-red-500" />{isRTL ? 'الأكثر غياباً' : 'Most Absent'}</CardTitle></CardHeader>
                        <CardContent>
                          {rd.mostAbsent.length === 0 ? <p className="text-xs text-muted-foreground text-center py-4">{isRTL ? 'لا يوجد غياب' : 'No absences'}</p> : (
                            <div className="space-y-1.5">{rd.mostAbsent.map((s, i) => (
                              <div key={s.id || i} className="flex items-center justify-between p-2 rounded-lg bg-red-50/50 dark:bg-red-950/10">
                                <span className="text-xs font-medium truncate">{s.full_name}</span>
                                <Badge className="bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-0 text-[10px]">{s.absentCount} {isRTL ? 'غياب' : 'absent'}</Badge>
                              </div>
                            ))}</div>
                          )}
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader className="pb-2"><CardTitle className="text-sm font-cairo flex items-center gap-2"><UserCheck className="h-4 w-4 text-green-500" />{isRTL ? 'الأكثر التزاماً' : 'Most Present'}</CardTitle></CardHeader>
                        <CardContent>
                          {rd.mostPresent.length === 0 ? <p className="text-xs text-muted-foreground text-center py-4">{isRTL ? 'لا توجد بيانات' : 'No data'}</p> : (
                            <div className="space-y-1.5">{rd.mostPresent.slice(0, 3).map((s, i) => (
                              <div key={s.id || i} className="flex items-center justify-between p-2 rounded-lg bg-green-50/50 dark:bg-green-950/10">
                                <span className="text-xs font-medium truncate">{s.full_name}</span>
                                <Badge className="bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-0 text-[10px]">{s.attRate}%</Badge>
                              </div>
                            ))}</div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="behavior">
                  <div className="grid md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><Shield className="h-4 w-4 text-purple-500" />{isRTL ? 'ملخص السلوك' : 'Behavior Summary'}</CardTitle></CardHeader>
                      <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-3 text-center">
                          <div className="p-4 rounded-xl bg-green-50 dark:bg-green-950/30"><ThumbsUp className="w-6 h-6 mx-auto mb-1 text-green-600" /><div className="text-2xl font-bold font-cairo text-green-600">{rd.summary.positiveBehavior}</div><div className="text-[10px] text-muted-foreground">{isRTL ? 'إيجابي' : 'Positive'}</div></div>
                          <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/30"><ThumbsDown className="w-6 h-6 mx-auto mb-1 text-red-600" /><div className="text-2xl font-bold font-cairo text-red-600">{rd.summary.negativeBehavior}</div><div className="text-[10px] text-muted-foreground">{isRTL ? 'سلبي' : 'Negative'}</div></div>
                        </div>
                        {Object.keys(rd.behaviorTypes).length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold font-cairo mb-2">{isRTL ? 'أنواع السلوكيات' : 'Behavior Types'}</h4>
                            <div className="space-y-1.5">{Object.entries(rd.behaviorTypes).sort(([, a], [, b]) => b - a).slice(0, 5).map(([type, count]) => (
                              <div key={type} className="flex items-center justify-between p-2 rounded-lg bg-muted/30">
                                <span className="text-xs capitalize">{type}</span>
                                <Badge variant="secondary" className="text-[10px]">{count}</Badge>
                              </div>
                            ))}</div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                    <Card>
                      <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><AlertCircle className="h-4 w-4 text-amber-500" />{isRTL ? 'طلاب يحتاجون متابعة سلوكية' : 'Behavior Watch List'}</CardTitle></CardHeader>
                      <CardContent>
                        {Object.keys(rd.studentBehavior).length === 0 ? (<div className="text-center py-8 text-sm text-muted-foreground">{isRTL ? 'لا توجد سجلات سلوك' : 'No behavior records'}</div>) : (
                          <div className="space-y-2">{Object.entries(rd.studentBehavior).filter(([, b]) => b.negative >= 2).sort(([, a], [, b]) => b.negative - a.negative).slice(0, 5).map(([sid, b]) => {
                            const student = rd.topPerformers.find(s => s.id === sid) || { full_name: sid };
                            return (<div key={sid} className="flex items-center justify-between p-2.5 rounded-lg border border-amber-200/60 dark:border-amber-800/30 bg-amber-50/50 dark:bg-amber-950/10">
                              <span className="text-xs font-medium">{student.full_name}</span>
                              <div className="flex gap-1.5"><Badge className="bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-0 text-[10px]">+{b.positive}</Badge><Badge className="bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 border-0 text-[10px]">-{b.negative}</Badge></div>
                            </div>);
                          })}</div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>

                <TabsContent value="grades">
                  <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { label: isRTL ? 'ممتاز' : 'Excellent', labelEn: '90+', count: rd.gradeDistribution.excellent, icon: Star, gradient: 'from-green-500 to-emerald-600', bg: 'bg-green-50 dark:bg-green-950/30' },
                      { label: isRTL ? 'جيد جداً' : 'Very Good', labelEn: '75-89', count: rd.gradeDistribution.veryGood, icon: GraduationCap, gradient: 'from-blue-500 to-indigo-600', bg: 'bg-blue-50 dark:bg-blue-950/30' },
                      { label: isRTL ? 'جيد' : 'Good', labelEn: '60-74', count: rd.gradeDistribution.good, icon: FileText, gradient: 'from-amber-500 to-yellow-600', bg: 'bg-amber-50 dark:bg-amber-950/30' },
                      { label: isRTL ? 'يحتاج تحسين' : 'Needs Work', labelEn: '<60', count: rd.gradeDistribution.needsWork, icon: AlertTriangle, gradient: 'from-red-500 to-rose-600', bg: 'bg-red-50 dark:bg-red-950/30' },
                    ].map(tier => (
                      <Card key={tier.label} className={`overflow-hidden ${tier.bg}`}><CardContent className="p-5 text-center">
                        <div className={`w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br ${tier.gradient} flex items-center justify-center shadow-sm`}><tier.icon className="h-6 w-6 text-white" /></div>
                        <div className="text-3xl font-bold font-cairo text-foreground">{tier.count}</div>
                        <div className="text-sm font-medium mt-1">{tier.label}</div><div className="text-xs text-muted-foreground mt-0.5">{tier.labelEn}</div>
                      </CardContent></Card>
                    ))}
                  </div>
                </TabsContent>

                <TabsContent value="attention">
                  <Card>
                    <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-500" />{isRTL ? 'طلاب يحتاجون متابعة' : 'Students Needing Attention'}</CardTitle></CardHeader>
                    <CardContent>
                      {rd.needsAttention.length === 0 ? (
                        <div className="flex flex-col items-center py-10 text-center">
                          <div className="w-14 h-14 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-3"><Target className="h-7 w-7 text-green-500" /></div>
                          <p className="font-cairo font-medium text-muted-foreground">{isRTL ? 'جميع الطلاب يسيرون بشكل جيد' : 'All students are on track'}</p>
                        </div>
                      ) : (
                        <div className="space-y-2.5">{rd.needsAttention.map((student, idx) => (
                          <div key={student.id || idx} className="p-3.5 rounded-xl border border-amber-200/60 dark:border-amber-800/30 bg-amber-50/50 dark:bg-amber-950/10">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-3">
                                <Avatar className="h-8 w-8"><AvatarFallback className={`text-xs font-bold ${student.issues.length >= 2 ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'}`}>{student.full_name?.charAt(0) || '?'}</AvatarFallback></Avatar>
                                <div>
                                  <span className="font-medium text-sm">{student.full_name || `${isRTL ? 'طالب' : 'Student'} ${idx + 1}`}</span>
                                  <div className="flex gap-2 text-[10px] text-muted-foreground mt-0.5">
                                    {student.attRate !== null && <span>{isRTL ? 'حضور' : 'Att'}: {student.attRate}%</span>}
                                    {student.gradeAvg !== null && <span>{isRTL ? 'معدل' : 'Avg'}: {student.gradeAvg}%</span>}
                                  </div>
                                </div>
                              </div>
                              <div className="flex gap-1.5">{student.issues.map(issue => (
                                <Badge key={issue} className={`text-[10px] border-0 ${issue === 'attendance' ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400' : issue === 'grades' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400' : 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400'}`}>
                                  {issue === 'attendance' ? (isRTL ? 'حضور' : 'Attendance') : issue === 'grades' ? (isRTL ? 'درجات' : 'Grades') : (isRTL ? 'سلوك' : 'Behavior')}
                                </Badge>
                              ))}</div>
                            </div>
                          </div>
                        ))}</div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="trend">
                  <Card>
                    <CardHeader className="pb-3"><CardTitle className="text-base font-cairo flex items-center gap-2"><TrendingUp className="h-4 w-4 text-brand-turquoise" />{isRTL ? 'اتجاه الحضور (آخر 7 أيام)' : 'Attendance Trend (Last 7 Days)'}</CardTitle></CardHeader>
                    <CardContent>
                      {rd.weeklyTrend.length === 0 ? (
                        <div className="flex flex-col items-center py-10 text-center"><Calendar className="h-10 w-10 text-muted-foreground/30 mb-3" /><p className="text-sm text-muted-foreground font-cairo">{isRTL ? 'لا توجد بيانات حضور كافية' : 'Not enough attendance data'}</p></div>
                      ) : (
                        <div className="space-y-4">
                          <div className="flex items-end gap-2 h-40">{rd.weeklyTrend.map((day, i) => {
                            const barColor = day.rate >= 90 ? 'bg-green-500' : day.rate >= 75 ? 'bg-blue-500' : day.rate >= 60 ? 'bg-amber-500' : 'bg-red-500';
                            return (<div key={i} className="flex-1 flex flex-col items-center gap-1"><span className="text-[10px] font-bold font-cairo text-muted-foreground">{day.rate}%</span><div className="w-full bg-muted/30 rounded-t-lg overflow-hidden" style={{ height: '120px' }}><div className={`w-full ${barColor} rounded-t-lg transition-all duration-700`} style={{ height: `${day.rate}%`, marginTop: `${100 - day.rate}%` }} /></div><span className="text-[9px] text-muted-foreground text-center leading-tight">{day.displayDate}</span></div>);
                          })}</div>
                          <div className="flex items-center justify-center gap-4 text-[10px] text-muted-foreground">
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> 90%+</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> 75-89%</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> 60-74%</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500" /> {'<60%'}</span>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </>
          )}
        </div>
      </div>
    </Sidebar>
  );
}
