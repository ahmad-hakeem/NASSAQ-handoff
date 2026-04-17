import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Skeleton } from '../../components/ui/skeleton';
import { Button } from '../../components/ui/button';
import {
  GraduationCap, Calendar, Clock, CheckCircle,
  AlertCircle, Bell, TrendingUp, MapPin, Award,
  Star, Trophy, Sparkles
} from 'lucide-react';


import { formatHijriDate } from '../../utils/hijriDate';

const StudentPortalDashboard = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [points, setPoints] = useState(null);
  const [activities, setActivities] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchAll = async () => {
      setError(false);
      try {
        // FIX (B2): All three endpoints DO exist on the backend
        // (student_portal_routes.py: /dashboard, /activities, /points).
        // The dashboard call is required; points/activities are optional —
        // if they fail (network/permission) we degrade gracefully instead
        // of blanking the whole screen.
        const [dashRes, pointsRes, actRes] = await Promise.all([
          api.get('/student-portal/dashboard'),
          api.get('/student-portal/points').catch(() => ({ data: null })),
          api.get('/student-portal/activities').catch(() => ({ data: { activities: [] } })),
        ]);
        setDashboard(dashRes.data);
        setPoints(pointsRes.data);
        setActivities(actRes.data);
      } catch (err) {
        console.error('Error fetching dashboard:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [token]);

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4 space-y-4">
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Skeleton className="h-64 rounded-2xl" />
            <Skeleton className="h-64 rounded-2xl" />
          </div>
        </div>
      </PortalLayout>
    );
  }

  if (error || !dashboard) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <AlertCircle className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="font-bold text-lg text-gray-700 mb-2">
                {t('couldNotLoadDashboard')}
              </h3>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm hover:bg-emerald-700"
              >
                {t('retry')}
              </button>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  const getActivityTypeBadge = (type) => {
    const map = {
      sports: { label: t('sports'), cls: 'bg-green-100 text-green-700' },
      cultural: { label: t('cultural'), cls: 'bg-blue-100 text-blue-700' },
      scientific: { label: t('scientific'), cls: 'bg-purple-100 text-purple-700' },
      social: { label: t('social'), cls: 'bg-amber-100 text-amber-700' },
      artistic: { label: t('artistic'), cls: 'bg-pink-100 text-pink-700' },
      volunteer: { label: t('volunteer'), cls: 'bg-teal-100 text-teal-700' },
      other: { label: t('other'), cls: 'bg-gray-100 text-gray-700' },
    };
    const s = map[type] || map.other;
    return <Badge className={`${s.cls} border-0 text-xs`}>{s.label}</Badge>;
  };

  const activityList = activities?.activities || [];
  const todaySchedule = dashboard?.today_schedule || [];

  const hakimMessages = [];
  if (dashboard?.attendance?.rate < 90) {
    hakimMessages.push(t('tryToImproveYourAttendanceToEarnExtraPoints'));
  }
  if (points?.rank && points.rank <= 3) {
    hakimMessages.push(isRTL ? `أنت في المركز ${points.rank}! استمر بالتميز.` : `You're ranked #${points.rank}! Keep it up.`);
  }
  if (hakimMessages.length === 0) {
    hakimMessages.push(t('greatPerformanceKeepUpTheHardWork'));
  }

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-portal-dashboard">
        <Card className="bg-gradient-to-br from-emerald-500 to-teal-600 text-white border-0 rounded-2xl overflow-hidden">
          <CardContent className="p-4 md:p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-white/20 flex items-center justify-center backdrop-blur-sm">
                  <GraduationCap className="h-8 w-8 md:h-10 md:w-10 text-white" />
                </div>
                <div>
                  <p className="text-emerald-100 text-sm">{formatHijriDate()}</p>
                  <h1 className="text-xl md:text-2xl font-bold font-cairo mt-1">
                    {t('welcome')}, {dashboard?.student?.name?.split(' ')[0]}
                  </h1>
                  <p className="text-emerald-100 flex items-center gap-2 mt-1 text-sm">
                    <MapPin className="h-4 w-4" />
                    {dashboard?.student?.school_name} - {dashboard?.student?.grade} ({dashboard?.student?.class_name})
                  </p>
                </div>
              </div>
              <div className="hidden md:flex gap-4">
                <div className="text-center px-4 py-2 bg-white/10 rounded-xl backdrop-blur-sm">
                  <p className="text-2xl font-bold">{dashboard?.attendance?.rate}%</p>
                  <p className="text-xs text-emerald-100">{t('attendance2')}</p>
                </div>
                <div className="text-center px-4 py-2 bg-white/10 rounded-xl backdrop-blur-sm">
                  <p className="text-2xl font-bold">{dashboard?.average_score}%</p>
                  <p className="text-xs text-emerald-100">{t('average')}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Panel 2: My Score — Gamification */}
        <Card className="rounded-2xl border-0 shadow-sm bg-gradient-to-l from-amber-50 to-yellow-50 overflow-hidden">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-400 to-yellow-500 flex items-center justify-center">
                  <Star className="h-6 w-6 text-white" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t('myScore')}</p>
                  <p className="text-2xl font-bold text-amber-600">{points?.total_score || 0}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">{t('rank2')}</p>
                  <p className="text-lg font-bold text-amber-600">
                    {points?.rank || '-'} / {points?.class_size || '-'}
                  </p>
                </div>
                <div className="text-center">
                  <p className="text-xs text-muted-foreground">{t('level2')}</p>
                  <Badge className="bg-amber-100 text-amber-700 border-amber-200 text-xs">
                    {isRTL ? points?.level_name : points?.level_name_en || `Lv.${points?.level || 1}`}
                  </Badge>
                </div>
                <Link to="/student/achievements">
                  <Button variant="ghost" size="sm" className="text-amber-600">
                    <Trophy className="h-4 w-4 me-1" />
                    {t('achievements')}
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:hidden">
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <CheckCircle className="h-5 w-5 mx-auto mb-1 text-green-600" />
              <p className="text-lg font-bold text-green-600">{dashboard?.attendance?.rate}%</p>
              <p className="text-[10px] text-muted-foreground">{t('attendance2')}</p>
            </CardContent>
          </Card>
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <TrendingUp className="h-5 w-5 mx-auto mb-1 text-blue-600" />
              <p className="text-lg font-bold text-blue-600">{dashboard?.average_score}%</p>
              <p className="text-[10px] text-muted-foreground">{t('average')}</p>
            </CardContent>
          </Card>
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <Calendar className="h-5 w-5 mx-auto mb-1 text-amber-600" />
              <p className="text-lg font-bold text-amber-600">{dashboard?.attendance?.total_days}</p>
              <p className="text-[10px] text-muted-foreground">{t('days2')}</p>
            </CardContent>
          </Card>
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <Bell className="h-5 w-5 mx-auto mb-1 text-purple-600" />
              <p className="text-lg font-bold text-purple-600">{dashboard?.unread_notifications}</p>
              <p className="text-[10px] text-muted-foreground">{t('notifications2')}</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Panel 1: Today's Classes */}
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-base">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-emerald-600" />
                  {isRTL ? 'حصص اليوم' : "Today's Classes"}
                </div>
                <Link to="/student/schedule" className="text-xs text-emerald-600 hover:underline">
                  {t('fullSchedule')}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[280px]">
                {todaySchedule.length > 0 ? (
                  <div className="space-y-2">
                    {todaySchedule.map((entry, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-all"
                      >
                        <div className="w-14 h-12 rounded-lg flex flex-col items-center justify-center bg-white border">
                          <span className="font-bold text-xs text-emerald-600">
                            {entry.start_time}
                          </span>
                          <span className="text-[10px] text-muted-foreground">{entry.end_time}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{entry.subject}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {entry.teacher} {entry.room && `- ${entry.room}`}
                          </p>
                        </div>
                        <Badge className="bg-emerald-100 text-emerald-700 border-0 text-xs">
                          {isRTL ? `الحصة ${entry.period}` : `P${entry.period}`}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Calendar className="h-12 w-12 mb-3 opacity-30" />
                    <p className="text-sm">{t('noClassesToday')}</p>
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Panel 3: Activities Participated In */}
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-base">
                <div className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-purple-600" />
                  {t('activities2')}
                </div>
                <span className="text-xs text-muted-foreground">
                  {activityList.length} {t('total4')}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[280px]">
                {activityList.length > 0 ? (
                  <div className="space-y-2">
                    {activityList.slice(0, 8).map((activity, idx) => (
                      <div
                        key={idx}
                        className="p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <p className="font-medium text-sm truncate flex-1">{activity.name}</p>
                          {getActivityTypeBadge(activity.type)}
                        </div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {activity.date?.slice(0, 10)}
                          </span>
                          {activity.description && (
                            <span className="truncate max-w-[150px]">{activity.description}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Award className="h-12 w-12 mb-3 opacity-30" />
                    <p className="text-sm">{t('noActivitiesYet')}</p>
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Recent Grades */}
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-base">
                <div className="flex items-center gap-2">
                  <Award className="h-5 w-5 text-blue-600" />
                  {t('recentGrades')}
                </div>
                <Link to="/student/grades" className="text-xs text-blue-600 hover:underline">
                  {t('viewAll')}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {dashboard?.recent_grades?.length > 0 ? (
                <div className="space-y-2">
                  {dashboard.recent_grades.map((grade, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 rounded-xl">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-sm">{grade.subject}</span>
                        <Badge variant="outline" className={
                          grade.percentage >= 90 ? 'bg-green-100 text-green-700 border-green-200' :
                          grade.percentage >= 75 ? 'bg-blue-100 text-blue-700 border-blue-200' :
                          grade.percentage >= 60 ? 'bg-amber-100 text-amber-700 border-amber-200' :
                          'bg-red-100 text-red-700 border-red-200'
                        }>
                          {grade.score}/{grade.max_score}
                        </Badge>
                      </div>
                      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                        <span>{grade.assessment_type}</span>
                        <span>{grade.date}</span>
                      </div>
                      <Progress value={grade.percentage} className="h-1.5" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <TrendingUp className="h-10 w-10 mb-2 opacity-30" />
                  <p className="text-sm">{t('noGradesYet')}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Panel 4: Hakim AI Panel */}
          <Card className="rounded-2xl border-0 shadow-sm bg-gradient-to-br from-violet-50 to-indigo-50">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                {t('hakimAi')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {hakimMessages.map((msg, idx) => (
                  <div key={idx} className="flex gap-3 items-start">
                    <div className="w-6 h-6 rounded-full bg-violet-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <Sparkles className="h-3 w-3 text-violet-600" />
                    </div>
                    <p className="text-sm text-gray-700">{msg}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 p-3 bg-white/60 rounded-xl">
                <p className="text-xs text-muted-foreground mb-2">
                  {t('askHakim3')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {[
                    t('howToImprove'),
                    t('myActivities'),
                    t('myRank'),
                  ].map((q, i) => (
                    <button
                      key={i}
                      className="text-xs px-3 py-1.5 bg-violet-100 text-violet-700 rounded-full hover:bg-violet-200 transition-all"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Attendance Summary */}
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-base">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-600" />
                {t('attendanceSummary')}
              </div>
              <Link to="/student/attendance" className="text-xs text-green-600 hover:underline">
                {t('details')}
              </Link>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-3">
              {[
                { icon: CheckCircle, value: dashboard?.attendance?.present || 0, label: t('present'), color: 'green' },
                { icon: AlertCircle, value: dashboard?.attendance?.absent || 0, label: t('absent'), color: 'red' },
                { icon: Clock, value: dashboard?.attendance?.late || 0, label: t('late'), color: 'amber' },
                { icon: Calendar, value: dashboard?.attendance?.total_days || 0, label: t('total2'), color: 'blue' },
              ].map((item, idx) => (
                <div key={idx} className={`text-center p-3 bg-${item.color}-50 rounded-xl`}>
                  <item.icon className={`h-6 w-6 mx-auto mb-1 text-${item.color}-600`} />
                  <p className={`text-xl font-bold text-${item.color}-600`}>{item.value}</p>
                  <p className="text-[10px] text-muted-foreground">{item.label}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

export default StudentPortalDashboard;
