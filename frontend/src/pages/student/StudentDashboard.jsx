/**
 * Student Dashboard Page
 * لوحة تحكم الطالب
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Skeleton } from '../components/ui/skeleton';
import {
  GraduationCap,
  Calendar,
  BookOpen,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Bell,
  TrendingUp,
  User,
  MapPin,
} from 'lucide-react';


export const StudentDashboard = () => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);

  useEffect(() => {
    fetchDashboard();
  }, [token]);

  const fetchDashboard = async () => {
    try {
      const response = await api.get('/student-portal/dashboard');
      setDashboard(response.data);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const getAttendanceColor = (status) => {
    switch (status) {
      case 'present': return 'bg-green-500';
      case 'absent': return 'bg-red-500';
      case 'late': return 'bg-amber-500';
      default: return 'bg-gray-500';
    }
  };

  const getGradeColor = (percentage) => {
    if (percentage >= 90) return 'text-green-600';
    if (percentage >= 75) return 'text-blue-600';
    if (percentage >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-6">
          <div className="space-y-6">
            <Skeleton className="h-32 w-full rounded-xl" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Skeleton className="h-48 rounded-xl" />
              <Skeleton className="h-48 rounded-xl" />
              <Skeleton className="h-48 rounded-xl" />
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-6" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Welcome Header */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-2">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-turquoise to-brand-navy flex items-center justify-center">
              <GraduationCap className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold font-cairo text-brand-navy dark:text-white">
                {t('welcome')}, {dashboard?.student?.name}
              </h1>
              <p className="text-muted-foreground flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                {dashboard?.student?.school_name} - {dashboard?.student?.grade} ({dashboard?.student?.class_name})
              </p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            {dashboard?.current_day} - {dashboard?.current_date}
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <div className="w-12 h-12 mx-auto mb-2 rounded-xl bg-green-500/10 flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-green-500" />
              </div>
              <p className="text-2xl font-bold text-green-600">{dashboard?.attendance?.rate}%</p>
              <p className="text-xs text-muted-foreground">{t('attendanceRate')}</p>
            </CardContent>
          </Card>

          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <div className="w-12 h-12 mx-auto mb-2 rounded-xl bg-blue-500/10 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-blue-500" />
              </div>
              <p className="text-2xl font-bold text-blue-600">{dashboard?.average_score}%</p>
              <p className="text-xs text-muted-foreground">{t('averageScore')}</p>
            </CardContent>
          </Card>

          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <div className="w-12 h-12 mx-auto mb-2 rounded-xl bg-amber-500/10 flex items-center justify-center">
                <Calendar className="h-6 w-6 text-amber-500" />
              </div>
              <p className="text-2xl font-bold text-amber-600">{dashboard?.attendance?.total_days}</p>
              <p className="text-xs text-muted-foreground">{t('schoolDays')}</p>
            </CardContent>
          </Card>

          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <div className="w-12 h-12 mx-auto mb-2 rounded-xl bg-purple-500/10 flex items-center justify-center">
                <Bell className="h-6 w-6 text-purple-500" />
              </div>
              <p className="text-2xl font-bold text-purple-600">{dashboard?.unread_notifications}</p>
              <p className="text-xs text-muted-foreground">{t('newNotifications')}</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Today's Schedule */}
          <Card className="card-nassaq">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Clock className="h-5 w-5 text-brand-turquoise" />
                {t('todaysSchedule')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[300px]">
                {dashboard?.today_schedule?.length > 0 ? (
                  <div className="space-y-3">
                    {dashboard.today_schedule.map((entry, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-3 bg-muted/30 rounded-xl">
                        <div className="w-12 h-12 rounded-lg bg-brand-navy/10 flex items-center justify-center">
                          <BookOpen className="h-5 w-5 text-brand-navy" />
                        </div>
                        <div className="flex-1">
                          <p className="font-medium">{entry.subject}</p>
                          <p className="text-xs text-muted-foreground">
                            {entry.teacher} • {entry.room}
                          </p>
                        </div>
                        <div className="text-end">
                          <p className="text-sm font-medium">{entry.start_time}</p>
                          <p className="text-xs text-muted-foreground">{entry.end_time}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Calendar className="h-12 w-12 mb-3 opacity-30" />
                    <p>{t('noClassesToday')}</p>
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Recent Grades */}
          <Card className="card-nassaq">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <TrendingUp className="h-5 w-5 text-brand-purple" />
                {t('recentGrades')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[300px]">
                {dashboard?.recent_grades?.length > 0 ? (
                  <div className="space-y-3">
                    {dashboard.recent_grades.map((grade, idx) => (
                      <div key={idx} className="p-3 bg-muted/30 rounded-xl">
                        <div className="flex items-center justify-between mb-2">
                          <p className="font-medium">{grade.subject}</p>
                          <Badge variant="outline" className={getGradeColor(grade.percentage)}>
                            {grade.score}/{grade.max_score}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{grade.assessment_type}</span>
                          <span>{grade.date}</span>
                        </div>
                        <Progress value={grade.percentage} className="h-1.5 mt-2" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <TrendingUp className="h-12 w-12 mb-3 opacity-30" />
                    <p>{t('noGradesYet')}</p>
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Attendance Summary */}
          <Card className="card-nassaq lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <CheckCircle className="h-5 w-5 text-green-500" />
                {t('attendanceSummary')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-green-500/10 rounded-xl">
                  <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
                  <p className="text-2xl font-bold text-green-600">{dashboard?.attendance?.present}</p>
                  <p className="text-sm text-muted-foreground">{t('present')}</p>
                </div>
                <div className="text-center p-4 bg-red-500/10 rounded-xl">
                  <XCircle className="h-8 w-8 mx-auto mb-2 text-red-500" />
                  <p className="text-2xl font-bold text-red-600">{dashboard?.attendance?.absent}</p>
                  <p className="text-sm text-muted-foreground">{t('absent')}</p>
                </div>
                <div className="text-center p-4 bg-amber-500/10 rounded-xl">
                  <AlertCircle className="h-8 w-8 mx-auto mb-2 text-amber-500" />
                  <p className="text-2xl font-bold text-amber-600">{dashboard?.attendance?.late}</p>
                  <p className="text-sm text-muted-foreground">{t('late')}</p>
                </div>
                <div className="text-center p-4 bg-blue-500/10 rounded-xl">
                  <Calendar className="h-8 w-8 mx-auto mb-2 text-blue-500" />
                  <p className="text-2xl font-bold text-blue-600">{dashboard?.attendance?.total_days}</p>
                  <p className="text-sm text-muted-foreground">{t('totalDays')}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Sidebar>
  );
};

export default StudentDashboard;
