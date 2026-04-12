/**
 * Parent Portal - Child Details Page
 * صفحة تفاصيل الابن لولي الأمر
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { ScrollArea } from '../../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import CumulativeAnalytics from '../../components/parent/CumulativeAnalytics';
import {
  User,
  Calendar,
  BookOpen,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Award,
  TrendingUp,
  MessageSquare,
  ChevronLeft,
  MapPin,
  Phone,
  Mail,
  BarChart3,
} from 'lucide-react';


const ChildDetailsPage = () => {
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const { childId } = useParams();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [child, setChild] = useState(null);
  const [grades, setGrades] = useState(null);
  const [attendance, setAttendance] = useState(null);
  const [schedule, setSchedule] = useState(null);

  useEffect(() => {
    fetchChildData();
  }, [childId, token]);

  const fetchChildData = async () => {
    try {
      const [childRes, gradesRes, attendanceRes, scheduleRes] = await Promise.all([
        api.get(`/parent-portal/child/${childId}`),
        api.get(`/parent-portal/child/${childId}/grades`),
        api.get(`/parent-portal/child/${childId}/attendance`),
        api.get(`/parent-portal/child/${childId}/schedule`)
      ]);
      
      setChild(childRes.data);
      setGrades(gradesRes.data);
      setAttendance(attendanceRes.data);
      setSchedule(scheduleRes.data);
    } catch (error) {
      console.error('Error fetching child data:', error);
      nassaqError(t('errorFetchingData'));
    } finally {
      setLoading(false);
    }
  };

  const getGradeColor = (percentage) => {
    if (percentage >= 90) return 'text-green-600';
    if (percentage >= 75) return 'text-blue-600';
    if (percentage >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'present':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'absent':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'late':
        return <Clock className="h-4 w-4 text-amber-600" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-400" />;
    }
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  if (!child) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <User className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="font-bold text-lg text-gray-700 mb-2">
                {t('studentNotFound')}
              </h3>
              <Link to="/parent">
                <Button variant="outline">
                  <ChevronLeft className="h-4 w-4 me-2" />
                  {t('goBack')}
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="child-details-page">
        {/* Child Profile Card */}
        <Card className="rounded-2xl border-0 shadow-sm bg-gradient-to-br from-indigo-500 to-purple-600 text-white">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <Avatar className="h-20 w-20 border-4 border-white/30">
                <AvatarImage src={child.profile_picture} />
                <AvatarFallback className="bg-white/20 text-white text-2xl font-bold">
                  {child.name?.charAt(0)}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <h1 className="text-2xl font-bold font-cairo">{child.name}</h1>
                <p className="text-indigo-100 flex items-center gap-2 mt-1">
                  <MapPin className="h-4 w-4" />
                  {child.school_name}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  <Badge className="bg-white/20 text-white border-0">
                    {child.grade}
                  </Badge>
                  <Badge className="bg-white/20 text-white border-0">
                    {child.class_name}
                  </Badge>
                </div>
              </div>
              <Link to={`/parent/child/${childId}/profile`} className="self-start">
                <Button variant="ghost" size="icon" className="text-white hover:bg-white/20 rounded-xl">
                  <User className="h-5 w-5" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 gap-3">
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="p-2 rounded-lg bg-green-100">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                </div>
                <span className="text-2xl font-bold text-green-600">
                  {attendance?.statistics?.attendance_rate || 0}%
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</p>
              <Progress value={attendance?.statistics?.attendance_rate || 0} className="h-1.5 mt-2" />
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="p-2 rounded-lg bg-blue-100">
                  <Award className="h-5 w-5 text-blue-600" />
                </div>
                <span className="text-2xl font-bold text-blue-600">
                  {grades?.overall_average || 0}%
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{t('average2')}</p>
              <Progress value={grades?.overall_average || 0} className="h-1.5 mt-2" />
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="analytics" className="w-full">
          <TabsList className="grid w-full grid-cols-4 bg-gray-100 rounded-xl p-1">
            <TabsTrigger value="analytics" className="rounded-lg text-xs">
              {t('cumulativeAnalytics')}
            </TabsTrigger>
            <TabsTrigger value="grades" className="rounded-lg text-xs">
              {t('grades')}
            </TabsTrigger>
            <TabsTrigger value="attendance" className="rounded-lg text-xs">
              {t('attendance2')}
            </TabsTrigger>
            <TabsTrigger value="schedule" className="rounded-lg text-xs">
              {t('schedule')}
            </TabsTrigger>
          </TabsList>

          {/* Analytics Tab */}
          <TabsContent value="analytics" className="mt-4">
            <CumulativeAnalytics childId={childId} viewerRole="parent" />
          </TabsContent>

          {/* Grades Tab */}
          <TabsContent value="grades" className="mt-4">
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardContent className="p-4">
                <ScrollArea className="h-[400px]">
                  {grades?.subjects?.length > 0 ? (
                    <div className="space-y-4">
                      {grades.subjects.map((subject, idx) => (
                        <div key={idx} className="space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <BookOpen className={`h-4 w-4 ${getGradeColor(subject.average)}`} />
                              <span className="font-medium text-sm">{subject.subject}</span>
                            </div>
                            <span className={`font-bold ${getGradeColor(subject.average)}`}>
                              {subject.average}%
                            </span>
                          </div>
                          <Progress value={subject.average} className="h-2" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <Award className="h-12 w-12 mb-3 opacity-30" />
                      <p>{t('noGrades')}</p>
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Attendance Tab */}
          <TabsContent value="attendance" className="mt-4">
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardHeader className="pb-2">
                <div className="grid grid-cols-4 gap-2 text-center">
                  <div className="p-2 bg-green-50 rounded-lg">
                    <p className="text-lg font-bold text-green-600">{attendance?.statistics?.present || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('present')}</p>
                  </div>
                  <div className="p-2 bg-red-50 rounded-lg">
                    <p className="text-lg font-bold text-red-600">{attendance?.statistics?.absent || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('absent')}</p>
                  </div>
                  <div className="p-2 bg-amber-50 rounded-lg">
                    <p className="text-lg font-bold text-amber-600">{attendance?.statistics?.late || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('late')}</p>
                  </div>
                  <div className="p-2 bg-blue-50 rounded-lg">
                    <p className="text-lg font-bold text-blue-600">{attendance?.statistics?.excused || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('excused2')}</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  {attendance?.records?.length > 0 ? (
                    <div className="space-y-2">
                      {attendance.records.slice(0, 20).map((record, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(record.status)}
                            <span className="text-sm">{record.date}</span>
                          </div>
                          <Badge variant="outline" className="text-xs">
                            {record.status === 'present' && (t('present'))}
                            {record.status === 'absent' && (t('absent'))}
                            {record.status === 'late' && (t('late'))}
                            {record.status === 'excused' && (t('excused2'))}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <Calendar className="h-12 w-12 mb-3 opacity-30" />
                      <p>{t('noRecords')}</p>
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Schedule Tab */}
          <TabsContent value="schedule" className="mt-4">
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardContent className="p-4">
                <ScrollArea className="h-[400px]">
                  {schedule?.days?.length > 0 ? (
                    <div className="space-y-4">
                      {schedule.days.map((day) => (
                        <div key={day}>
                          <h3 className="font-bold text-sm mb-2 text-indigo-600">{day}</h3>
                          {schedule.schedule[day]?.length > 0 ? (
                            <div className="space-y-2">
                              {schedule.schedule[day].map((entry, idx) => (
                                <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                                  <div className="w-14 h-10 rounded bg-indigo-100 flex items-center justify-center">
                                    <span className="text-xs font-bold text-indigo-600">{entry.start_time}</span>
                                  </div>
                                  <div>
                                    <p className="font-medium text-sm">{entry.subject}</p>
                                    <p className="text-xs text-muted-foreground">{entry.teacher}</p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground py-2">
                              {isRTL ? 'لا توجد حصص' : 'No classes'}
                            </p>
                          )}
                        </div>
                      ))}
                      <Link to={`/parent/child/${childId}/schedule`}>
                        <Button variant="outline" className="w-full mt-2 gap-2">
                          <Calendar className="h-4 w-4" />
                          {t('viewFullSchedule')}
                        </Button>
                      </Link>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <Calendar className="h-12 w-12 mb-3 opacity-30" />
                      <p>{t('noSchedule')}</p>
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Contact Teachers */}
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-indigo-600" />
              {t('contactTeachers')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Link to={`/parent/child/${childId}/teachers`}>
              <Button className="w-full bg-indigo-600 hover:bg-indigo-700">
                {t('viewTeachersList')}
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

export default ChildDetailsPage;
