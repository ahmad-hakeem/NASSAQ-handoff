import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { toast } from 'sonner';
import {
  BookOpen, Users, Calendar, ClipboardCheck, Bell, Settings,
  GraduationCap, Clock, CheckCircle2, AlertCircle, ChevronLeft,
  BarChart3, FileText, Star, TrendingUp, CalendarDays, Menu
} from 'lucide-react';
import { Sidebar } from '../components/layout/Sidebar';
import { formatHijriOnly, formatGregorianArabic } from '../utils/hijriDate';

import { useTranslation } from '../contexts/ThemeContext';
export default function TeacherDashboard() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [stats, setStats] = useState({
    myClasses: 0,
    myStudents: 0,
    todayLessons: 0,
    pendingAttendance: 0,
    pendingAssessments: 0,
    upcomingLessons: []
  });
  const [recentActivities, setRecentActivities] = useState([]);

  const fetchTeacherData = useCallback(async () => {
    setLoading(true);
    try {
      // Get teacher ID from user
      const teacherId = user?.teacher_id || user?.id;
      
      // Fetch teacher dashboard data from API
      const dashboardRes = await api.get(`/teacher/dashboard/${teacherId}`).catch(() => null);
      
      if (dashboardRes?.data) {
        const data = dashboardRes.data;
        setStats({
          myClasses: data.stats.my_classes || 0,
          myStudents: data.stats.my_students || 0,
          todayLessons: data.stats.today_lessons || 0,
          pendingAttendance: data.stats.pending_attendance || 0,
          pendingAssessments: 0,
          upcomingLessons: data.today_schedule?.map(lesson => ({
            time: lesson.time,
            subject: lesson.subject,
            class: lesson.class_name
          })) || []
        });
        
        setRecentActivities(data.recent_activities?.map(a => ({
          type: a.type?.includes('attendance') ? 'attendance' : 
                a.type?.includes('assessment') ? 'assessment' : 'notification',
          message: a.message,
          time: a.time ? new Date(a.time).toLocaleDateString('ar-SA') : 'مؤخراً'
        })) || []);
      } else {
        // No data available - show zeros instead of mock data
        const [classesRes, assignmentsRes] = await Promise.all([
          api.get('/classes').catch(() => ({ data: [] })),
          api.get('/teacher-assignments').catch(() => ({ data: [] }))
        ]);

        const myAssignments = assignmentsRes.data || [];
        const myClassIds = [...new Set(myAssignments.map(a => a.class_id))];
        
        setStats({
          myClasses: myClassIds.length || 0,
          myStudents: 0,
          todayLessons: 0,
          pendingAttendance: 0,
          pendingAssessments: 0,
          upcomingLessons: []
        });

        setRecentActivities([]);
      }

    } catch (error) {
      console.error('Error fetching teacher data:', error);
    } finally {
      setLoading(false);
    }
  }, [api, user?.teacher_id, user?.id]);

  useEffect(() => {
    fetchTeacherData();
  }, [fetchTeacherData]);

  const quickActions = [
    { icon: ClipboardCheck, label: isRTL ? 'تسجيل الحضور' : 'Take Attendance', path: '/admin/attendance', color: 'bg-green-500' },
    { icon: FileText, label: t('addAssessment'), path: '/admin/assessments', color: 'bg-blue-500' },
    { icon: Calendar, label: t('mySchedule'), path: '/admin/schedule', color: 'bg-purple-500' },
    { icon: Bell, label: t('notifications'), path: '/notifications', color: 'bg-orange-500' },
  ];

  const statsCards = [
    { 
      icon: BookOpen, 
      label: t('myClasses2'), 
      value: stats.myClasses, 
      color: 'text-blue-600', 
      bgColor: 'bg-blue-100',
      description: t('classesAssignedToYou')
    },
    { 
      icon: Users, 
      label: t('myStudents'), 
      value: stats.myStudents, 
      color: 'text-green-600', 
      bgColor: 'bg-green-100',
      description: isRTL ? 'إجمالي الطلاب' : 'Total students'
    },
    { 
      icon: CalendarDays, 
      label: isRTL ? 'حصص اليوم' : 'Today\'s Lessons', 
      value: stats.todayLessons, 
      color: 'text-purple-600', 
      bgColor: 'bg-purple-100',
      description: t('remainingLessonsToday')
    },
    { 
      icon: AlertCircle, 
      label: t('pendingAttendance'), 
      value: stats.pendingAttendance, 
      color: 'text-orange-600', 
      bgColor: 'bg-orange-100',
      description: t('needsRecording')
    },
  ];

  return (
    <div className={`flex min-h-screen bg-gray-50 ${isRTL ? 'flex-row-reverse' : ''}`}>
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />

      {/* Main Content */}
      <main className={`flex-1 transition-all duration-300 ${sidebarOpen ? (isRTL ? 'mr-64' : 'ml-64') : (isRTL ? 'mr-20' : 'ml-20')}`}>
        <div className="p-4 sm:p-6 space-y-6">
          
          {/* Welcome Card */}
          <Card className="relative overflow-hidden bg-gradient-to-r from-brand-navy/5 via-brand-turquoise/5 to-brand-purple/5 border-brand-navy/20">
            <div className="absolute inset-0 nassaq-pattern opacity-[0.03] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
            <CardContent className="relative py-5 px-6">
              <div className="flex items-center justify-between">
                {/* User Info */}
                <div className="flex items-center gap-4">
                  <Avatar className="h-16 w-16 border-2 border-brand-turquoise shadow-lg">
                    <AvatarImage src={user?.avatar_url} alt={user?.full_name} />
                    <AvatarFallback className="bg-gradient-to-br from-brand-navy to-brand-turquoise text-white text-xl font-bold">
                      {user?.full_name?.charAt(0) || 'م'}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <h1 className="font-cairo text-xl font-bold text-brand-navy">
                      {isRTL ? `مرحباً أستاذ ${user?.full_name || 'المعلم'}` : `Welcome, ${user?.full_name || 'Teacher'}`}
                    </h1>
                    <p className="text-sm text-muted-foreground font-medium flex items-center gap-2">
                      <GraduationCap className="h-4 w-4" />
                      {t('teacherDashboard')}
                    </p>
                  </div>
                </div>

                {/* Semester Info */}
                <div className="text-center px-6 py-2 bg-brand-turquoise/10 rounded-xl border border-brand-turquoise/20">
                  <p className="text-xs text-muted-foreground font-medium">{t('semester')}</p>
                  <p className="font-cairo font-bold text-brand-turquoise text-lg">{t('2nd14461447')}</p>
                </div>

                {/* Date */}
                <div className="flex items-center gap-3 bg-muted/30 px-4 py-2 rounded-xl">
                  <Calendar className="h-5 w-5 text-brand-navy" />
                  <div className="text-end">
                    <p className="font-cairo text-lg font-bold text-brand-navy">
                      {formatHijriOnly()}
                    </p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {formatGregorianArabic()}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {quickActions.map((action, index) => (
              <Button
                key={index}
                variant="outline"
                className="h-24 flex flex-col items-center justify-center gap-2 hover:bg-accent transition-all border-2 hover:border-brand-turquoise"
                onClick={() => navigate(action.path)}
              >
                <div className={`p-2 rounded-full ${action.color}`}>
                  <action.icon className="h-5 w-5 text-white" />
                </div>
                <span className="font-medium text-sm">{action.label}</span>
              </Button>
            ))}
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {statsCards.map((stat, index) => (
              <Card key={index} className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => {
                if (stat.label.includes('صفوف') || stat.label.includes('Classes')) navigate('/admin/classes');
                if (stat.label.includes('طلاب') || stat.label.includes('Students')) navigate('/admin/students');
                if (stat.label.includes('حضور') || stat.label.includes('Attendance')) navigate('/admin/attendance');
              }}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground mb-1">{stat.label}</p>
                      <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
                      <p className="text-xs text-muted-foreground mt-1">{stat.description}</p>
                    </div>
                    <div className={`p-3 rounded-xl ${stat.bgColor}`}>
                      <stat.icon className={`h-6 w-6 ${stat.color}`} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            {/* Today's Schedule */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Clock className="h-5 w-5 text-brand-turquoise" />
                  {t('todaysSchedule')}
                </CardTitle>
                <CardDescription>
                  {t('yourRemainingLessonsForToday')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {stats.upcomingLessons.map((lesson, index) => (
                  <div 
                    key={index} 
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      index === 0 ? 'bg-brand-turquoise/10 border-brand-turquoise' : 'bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                        index === 0 ? 'bg-brand-turquoise text-white' : 'bg-gray-200'
                      }`}>
                        <span className="font-bold text-sm">{lesson.time}</span>
                      </div>
                      <div>
                        <p className="font-medium">{lesson.subject}</p>
                        <p className="text-sm text-muted-foreground">{lesson.class}</p>
                      </div>
                    </div>
                    {index === 0 && (
                      <Badge className="bg-brand-turquoise">
                        {isRTL ? 'الحصة الحالية' : 'Current'}
                      </Badge>
                    )}
                  </div>
                ))}
                <Button variant="outline" className="w-full mt-2" onClick={() => navigate('/admin/schedule')}>
                  {t('viewFullSchedule')}
                </Button>
              </CardContent>
            </Card>

            {/* Recent Activities */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Bell className="h-5 w-5 text-brand-purple" />
                  {t('recentActivities')}
                </CardTitle>
                <CardDescription>
                  {t('latestActivitiesAndUpdates')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {recentActivities.map((activity, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                    <div className={`p-2 rounded-full ${
                      activity.type === 'attendance' ? 'bg-green-100' :
                      activity.type === 'assessment' ? 'bg-blue-100' : 'bg-orange-100'
                    }`}>
                      {activity.type === 'attendance' ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : activity.type === 'assessment' ? (
                        <FileText className="h-4 w-4 text-blue-600" />
                      ) : (
                        <Bell className="h-4 w-4 text-orange-600" />
                      )}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{activity.message}</p>
                      <p className="text-xs text-muted-foreground">{activity.time}</p>
                    </div>
                  </div>
                ))}
                <Button variant="outline" className="w-full mt-2" onClick={() => navigate('/notifications')}>
                  {t('viewAllNotifications')}
                </Button>
              </CardContent>
            </Card>

          </div>

          {/* Pending Tasks */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-lg">
                <AlertCircle className="h-5 w-5 text-orange-500" />
                {t('pendingTasks')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-orange-50 border border-orange-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-orange-800">{t('unrecordedAttendance2')}</span>
                    <Badge variant="destructive">{stats.pendingAttendance}</Badge>
                  </div>
                  <Button size="sm" className="w-full" onClick={() => navigate('/admin/attendance')}>
                    {t('recordNow')}
                  </Button>
                </div>
                <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-blue-800">{t('pendingAssessments')}</span>
                    <Badge className="bg-blue-500">{stats.pendingAssessments}</Badge>
                  </div>
                  <Button size="sm" variant="outline" className="w-full" onClick={() => navigate('/admin/assessments')}>
                    {t('completeAssessment')}
                  </Button>
                </div>
                <div className="p-4 rounded-lg bg-green-50 border border-green-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-green-800">{t('reportsToReview')}</span>
                    <Badge className="bg-green-500">0</Badge>
                  </div>
                  <Button size="sm" variant="outline" className="w-full" disabled>
                    {t('noReports')}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

        </div>
      </main>
    </div>
  );
}
