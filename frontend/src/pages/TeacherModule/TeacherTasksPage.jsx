import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  ClipboardCheck, Users, CheckCircle2, Clock, AlertCircle,
  Loader2, RefreshCw, BookOpen, FileText, ArrowLeft
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

export default function TeacherTasksPage() {
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [attendanceStatus, setAttendanceStatus] = useState({});
  const teacherId = user?.teacher_id || user?.id;

  const loadTasks = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const classRes = await api.get(`/teacher/classes/${teacherId}`).catch(() => null);
      let classList = [];
      if (classRes?.data) {
        classList = Array.isArray(classRes.data) ? classRes.data :
          classRes.data.classes || classRes.data.data || [];
      }
      setClasses(classList);

      const today = new Date().toISOString().split('T')[0];
      const attRes = await api.get(`/teacher/attendance/status?date=${today}`).catch(() => null);
      if (attRes?.data) {
        const statusMap = {};
        const records = attRes.data.records || attRes.data || [];
        if (Array.isArray(records)) {
          records.forEach(r => { statusMap[r.class_id] = true; });
        }
        setAttendanceStatus(statusMap);
      }
    } catch (e) { console.error('Error loading teacher tasks:', e); }
    setLoading(false);
  }, [api, teacherId]);

  useEffect(() => { loadTasks(); }, [loadTasks]);

  const pendingClasses = classes.filter(c => !attendanceStatus[c.id]);
  const completedClasses = classes.filter(c => attendanceStatus[c.id]);

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="p-4 md:p-6 space-y-5 max-w-[1000px] mx-auto">

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-gradient-to-br from-orange-500 to-orange-600 shadow-lg">
                <ClipboardCheck className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-bold font-cairo text-foreground">
                  {isRTL ? 'المهام المفتوحة' : 'Open Tasks'}
                </h1>
                <p className="text-xs text-muted-foreground font-tajawal">
                  {isRTL ? 'المهام المطلوب إنجازها اليوم' : "Today's pending tasks"}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={loadTasks} disabled={loading}
                className="rounded-xl border-border/50 hover:bg-muted gap-2 font-tajawal text-xs">
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                {isRTL ? 'تحديث' : 'Refresh'}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => navigate('/teacher')}
                className="rounded-xl gap-1 font-tajawal text-xs">
                <ArrowLeft className="h-3.5 w-3.5" />
                {isRTL ? 'الرئيسية' : 'Home'}
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-6">

              {pendingClasses.length > 0 && (
                <Card className="border-orange-200/50 dark:border-orange-800/30 shadow-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-sm font-cairo">
                      <div className="p-1.5 rounded-lg bg-orange-100 dark:bg-orange-900/30">
                        <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                      </div>
                      {isRTL ? 'تسجيل الحضور' : 'Attendance Recording'}
                      <Badge className="bg-orange-500 text-white text-[10px] font-cairo ms-auto">{pendingClasses.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {pendingClasses.map(cls => (
                      <div key={cls.id} className="flex items-center justify-between p-3 rounded-xl bg-orange-50 dark:bg-orange-950/20 border border-orange-200/50 dark:border-orange-800/30">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-orange-100 dark:bg-orange-900/30">
                            <Users className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                          </div>
                          <div>
                            <p className="text-sm font-medium font-cairo text-foreground">{cls.name}</p>
                            <p className="text-xs text-muted-foreground font-tajawal">
                              {cls.student_count || cls.students || 0} {isRTL ? 'طالب' : 'students'}
                            </p>
                          </div>
                        </div>
                        <Button size="sm"
                          className="bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white rounded-xl font-cairo text-xs shadow-sm"
                          onClick={() => navigate(`/teacher/attendance?class=${cls.id}`)}>
                          <ClipboardCheck className="h-3.5 w-3.5 me-1" />
                          {isRTL ? 'تسجيل' : 'Record'}
                        </Button>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              <Card className="border-blue-200/50 dark:border-blue-800/30 shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm font-cairo">
                    <div className="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                      <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                    </div>
                    {isRTL ? 'التقييمات والاختبارات' : 'Assessments & Tests'}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-blue-50 dark:bg-blue-950/20 border border-blue-200/50 dark:border-blue-800/30">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                        <BookOpen className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <p className="text-sm font-medium font-cairo text-foreground">
                          {isRTL ? 'إدارة التقييمات' : 'Manage Assessments'}
                        </p>
                        <p className="text-xs text-muted-foreground font-tajawal">
                          {isRTL ? 'إنشاء ومتابعة التقييمات' : 'Create and manage assessments'}
                        </p>
                      </div>
                    </div>
                    <Button size="sm" variant="outline"
                      className="border-blue-300 text-blue-700 hover:bg-blue-50 rounded-xl font-cairo text-xs"
                      onClick={() => navigate('/teacher/assessments')}>
                      {isRTL ? 'فتح' : 'Open'}
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {completedClasses.length > 0 && (
                <Card className="border-green-200/50 dark:border-green-800/30 shadow-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-sm font-cairo">
                      <div className="p-1.5 rounded-lg bg-green-100 dark:bg-green-900/30">
                        <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                      </div>
                      {isRTL ? 'مكتمل اليوم' : 'Completed Today'}
                      <Badge className="bg-green-500 text-white text-[10px] font-cairo ms-auto">{completedClasses.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {completedClasses.map(cls => (
                      <div key={cls.id} className="flex items-center justify-between p-3 rounded-xl bg-green-50/50 dark:bg-green-950/10 border border-green-200/30 dark:border-green-800/20">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/20">
                            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                          </div>
                          <div>
                            <p className="text-sm font-medium font-cairo text-foreground">{cls.name}</p>
                            <p className="text-xs text-green-600 dark:text-green-400 font-tajawal">
                              {isRTL ? 'تم تسجيل الحضور' : 'Attendance recorded'}
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className="border-green-300 text-green-700 text-[10px] font-cairo">
                          <CheckCircle2 className="h-3 w-3 me-1" />
                          {isRTL ? 'مكتمل' : 'Done'}
                        </Badge>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {pendingClasses.length === 0 && completedClasses.length === 0 && (
                <div className="text-center py-16">
                  <CheckCircle2 className="h-12 w-12 text-green-400 mx-auto mb-3" />
                  <p className="text-muted-foreground font-tajawal">
                    {isRTL ? 'لا توجد مهام معلقة حالياً' : 'No pending tasks right now'}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
