import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  BookOpen, Calendar, Bell, GraduationCap, Clock, CheckCircle2,
  AlertCircle, TrendingUp, Award, FileText, BarChart3, CalendarDays,
  Home, User, Settings, ChevronLeft, ChevronRight, Loader2
} from 'lucide-react';
import { formatHijriDate } from '../utils/hijriDate';

export default function StudentDashboard() {
  const { user, api, isRTL = true } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [studentData, setStudentData] = useState(null);
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [stats, setStats] = useState({
    attendanceRate: 0,
    averageGrade: 0,
    presentDays: 0,
    absentDays: 0,
    todayLessons: []
  });
  const [grades, setGrades] = useState([]);
  const [notifications, setNotifications] = useState([]);

  const fetchStudentData = useCallback(async () => {
    setLoading(true);
    try {
      const studentId = user?.student_id || user?.id;
      
      if (!studentId) {
        setLoading(false);
        return;
      }
      
      const response = await api.get(`/student/dashboard/${studentId}`);
      
      if (response?.data) {
        const data = response.data;
        
        setStudentData({
          name: data.student?.name || user?.full_name,
          className: data.student?.class_name || 'غير محدد',
          schoolId: data.student?.school_id
        });
        
        setStats({
          attendanceRate: data.stats?.attendance_rate || 0,
          averageGrade: data.stats?.average_grade || 0,
          presentDays: data.stats?.present_days || 0,
          absentDays: data.stats?.absent_days || 0,
          todayLessons: data.today_schedule?.map(lesson => ({
            time: lesson.time,
            period: lesson.period,
            subject: lesson.subject,
            teacher: lesson.teacher,
            room: lesson.room || ''
          })) || []
        });
        
        setGrades(data.recent_grades?.map(g => ({
          subject: g.subject,
          grade: g.grade,
          date: g.date
        })) || []);
        
        setNotifications(data.notifications?.map(n => ({
          title: n.title || n.message,
          time: n.time ? new Date(n.time).toLocaleDateString('ar-SA') : 'مؤخراً',
          type: n.type || 'info'
        })) || []);
      }
    } catch (error) {
      console.error('Error fetching student data:', error);
      nassaqError('خطأ في جلب البيانات');
    } finally {
      setLoading(false);
    }
  }, [api, user?.id, user?.student_id, user?.full_name]);

  useEffect(() => {
    fetchStudentData();
  }, [fetchStudentData]);

  const getGradeColor = (grade) => {
    if (grade >= 90) return 'text-green-600';
    if (grade >= 80) return 'text-blue-600';
    if (grade >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getGradeBg = (grade) => {
    if (grade >= 90) return 'bg-green-100';
    if (grade >= 80) return 'bg-blue-100';
    if (grade >= 70) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-emerald-600 mx-auto mb-4" />
          <p className="text-muted-foreground">جارٍ التحميل...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24" dir="rtl" data-testid="student-dashboard">
      {/* Header */}
      <div className="relative bg-gradient-to-br from-emerald-600 to-teal-500 text-white overflow-hidden">
        <div className="absolute inset-0 nassaq-pattern opacity-[0.05] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
        <div className="relative px-4 py-6 space-y-4">
          {/* Date */}
          <p className="text-emerald-100 text-sm text-center">{formatHijriDate()}</p>
          
          {/* Student Info */}
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16 border-2 border-white/30 shadow-lg">
              <AvatarImage src={user?.avatar_url} alt={studentData?.name} />
              <AvatarFallback className="bg-white/20 text-white text-xl font-bold">
                {studentData?.name?.charAt(0) || 'ط'}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="font-cairo text-xl font-bold">
                مرحباً {studentData?.name || 'الطالب'}
              </h1>
              <p className="text-emerald-100 text-sm flex items-center gap-2">
                <GraduationCap className="h-4 w-4" />
                {studentData?.className || 'غير محدد'}
              </p>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 gap-3 mt-4">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-3 text-center">
              <p className="text-emerald-100 text-xs">نسبة الحضور</p>
              <p className="text-2xl font-bold">{stats.attendanceRate}%</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-3 text-center">
              <p className="text-emerald-100 text-xs">المعدل العام</p>
              <p className="text-2xl font-bold">{stats.averageGrade}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-4 space-y-4 -mt-4">
        
        {/* Today's Schedule Card */}
        <Card className="rounded-2xl shadow-sm border-0">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarDays className="h-5 w-5 text-emerald-600" />
              جدول اليوم
              <Badge variant="secondary" className="ms-auto">
                {stats.todayLessons.length} حصص
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {stats.todayLessons.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <CalendarDays className="h-10 w-10 mx-auto mb-2 opacity-50" />
                <p>لا توجد حصص اليوم</p>
              </div>
            ) : (
              stats.todayLessons.map((lesson, index) => (
                <div 
                  key={index} 
                  className={`flex items-center gap-3 p-3 rounded-xl transition-all ${
                    index === 0 
                      ? 'bg-gradient-to-l from-emerald-500 to-emerald-600 text-white' 
                      : 'bg-gray-50'
                  }`}
                >
                  <div className={`w-14 h-12 rounded-xl flex flex-col items-center justify-center ${
                    index === 0 ? 'bg-white/20' : 'bg-white border'
                  }`}>
                    <span className={`font-bold text-sm ${index === 0 ? 'text-white' : 'text-emerald-600'}`}>
                      {lesson.time}
                    </span>
                  </div>
                  <div className="flex-1">
                    <p className={`font-bold text-sm ${index === 0 ? 'text-white' : 'text-gray-900'}`}>
                      {lesson.subject}
                    </p>
                    <p className={`text-xs ${index === 0 ? 'text-emerald-100' : 'text-muted-foreground'}`}>
                      {lesson.teacher} {lesson.room && `• ${lesson.room}`}
                    </p>
                  </div>
                  {index === 0 && (
                    <Badge className="bg-white/20 text-white border-0">الآن</Badge>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Grades Card */}
        <Card className="rounded-2xl shadow-sm border-0">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-5 w-5 text-blue-600" />
              درجاتي
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {grades.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <Award className="h-10 w-10 mx-auto mb-2 opacity-50" />
                <p>لا توجد درجات مسجلة</p>
              </div>
            ) : (
              grades.map((item, index) => (
                <div key={index} className="flex items-center justify-between p-3 rounded-xl bg-gray-50">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${getGradeBg(item.grade)}`}>
                      <BookOpen className={`h-4 w-4 ${getGradeColor(item.grade)}`} />
                    </div>
                    <div>
                      <span className="font-medium text-sm">{item.subject}</span>
                      <p className="text-xs text-muted-foreground">{item.date}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`font-bold text-lg ${getGradeColor(item.grade)}`}>
                      {item.grade}%
                    </span>
                    {item.grade >= 85 && <TrendingUp className="h-4 w-4 text-green-500" />}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Attendance Summary */}
        <Card className="rounded-2xl shadow-sm border-0">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              ملخص الحضور
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">نسبة الحضور</span>
                <span className="font-bold text-green-600">{stats.attendanceRate}%</span>
              </div>
              <Progress value={stats.attendanceRate} className="h-2" />
              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="bg-green-50 rounded-xl p-3 text-center">
                  <CheckCircle2 className="h-6 w-6 text-green-600 mx-auto mb-1" />
                  <p className="text-xl font-bold text-green-600">{stats.presentDays}</p>
                  <p className="text-xs text-muted-foreground">أيام الحضور</p>
                </div>
                <div className="bg-red-50 rounded-xl p-3 text-center">
                  <AlertCircle className="h-6 w-6 text-red-600 mx-auto mb-1" />
                  <p className="text-xl font-bold text-red-600">{stats.absentDays}</p>
                  <p className="text-xs text-muted-foreground">أيام الغياب</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="rounded-2xl shadow-sm border-0">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Bell className="h-5 w-5 text-orange-500" />
              الإشعارات
              {notifications.length > 0 && (
                <Badge variant="destructive" className="ms-auto text-xs">
                  {notifications.length}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {notifications.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <Bell className="h-10 w-10 mx-auto mb-2 opacity-50" />
                <p>لا توجد إشعارات</p>
              </div>
            ) : (
              notifications.slice(0, 3).map((notif, index) => (
                <div key={index} className="flex items-start gap-3 p-3 rounded-xl bg-gray-50">
                  <div className={`p-2 rounded-full ${
                    notif.type === 'exam' ? 'bg-red-100' :
                    notif.type === 'grade' ? 'bg-green-100' : 'bg-blue-100'
                  }`}>
                    {notif.type === 'exam' ? (
                      <AlertCircle className="h-4 w-4 text-red-600" />
                    ) : notif.type === 'grade' ? (
                      <Award className="h-4 w-4 text-green-600" />
                    ) : (
                      <Calendar className="h-4 w-4 text-blue-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-sm">{notif.title}</p>
                    <p className="text-xs text-muted-foreground">{notif.time}</p>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-50">
        <div className="flex items-center justify-around py-2">
          <button className="flex flex-col items-center gap-1 p-2 text-emerald-600">
            <Home className="h-6 w-6" />
            <span className="text-xs font-medium">الرئيسية</span>
          </button>
          <button className="flex flex-col items-center gap-1 p-2 text-gray-400">
            <CalendarDays className="h-6 w-6" />
            <span className="text-xs">الجدول</span>
          </button>
          <button className="flex flex-col items-center gap-1 p-2 text-gray-400">
            <BookOpen className="h-6 w-6" />
            <span className="text-xs">الدرجات</span>
          </button>
          <button className="flex flex-col items-center gap-1 p-2 text-gray-400">
            <User className="h-6 w-6" />
            <span className="text-xs">حسابي</span>
          </button>
        </div>
      </nav>
    </div>
  );
}
