/**
 * Parent Portal - Dashboard Page
 * لوحة تحكم بوابة ولي الأمر
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { ScrollArea } from '../../components/ui/scroll-area';
import { toast } from 'sonner';
import {
  Users,
  GraduationCap,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Bell,
  TrendingUp,
  MessageSquare,
  ChevronLeft,
  ChevronRight,
  Award,
  Calendar,
  BookOpen,
} from 'lucide-react';


import { formatHijriDate } from '../../utils/hijriDate';

const ParentPortalDashboard = () => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [selectedChildIndex, setSelectedChildIndex] = useState(0);

  useEffect(() => {
    fetchDashboard();
  }, [token]);

  const fetchDashboard = async () => {
    try {
      const response = await api.get('/parent-portal/dashboard');
      setDashboard(response.data);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
      // Set default data if API fails
      setDashboard({
        parent: {
          name: user?.full_name || 'ولي أمر',
          email: user?.email,
          phone: user?.phone
        },
        children: [],
        children_count: 0,
        unread_notifications: 0,
        unread_messages: 0
      });
    } finally {
      setLoading(false);
    }
  };

  const selectedChild = dashboard?.children?.[selectedChildIndex];

  const getGradeColor = (percentage) => {
    if (percentage >= 90) return 'text-green-600';
    if (percentage >= 75) return 'text-blue-600';
    if (percentage >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-32 w-full rounded-2xl" />
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map(i => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-portal-dashboard">
        {/* Welcome Banner */}
        <Card className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white border-0 rounded-2xl overflow-hidden">
          <CardContent className="p-4 md:p-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 md:w-20 md:h-20 rounded-2xl bg-white/20 flex items-center justify-center backdrop-blur-sm">
                  <Users className="h-8 w-8 md:h-10 md:w-10 text-white" />
                </div>
                <div>
                  <p className="text-indigo-100 text-sm">{formatHijriDate()}</p>
                  <h1 className="text-xl md:text-2xl font-bold font-cairo mt-1">
                    {t('welcome')}, {dashboard?.parent?.name?.split(' ')[0]}
                  </h1>
                  <p className="text-indigo-100 flex items-center gap-2 mt-1 text-sm">
                    <GraduationCap className="h-4 w-4" />
                    {dashboard?.children_count || 0} {dashboard?.children_count === 1 ? (t('childEnrolled')) : (t('childrenEnrolled'))}
                  </p>
                </div>
              </div>
              
              {/* Quick Stats */}
              <div className="hidden md:flex gap-4">
                <div className="text-center px-4 py-2 bg-white/10 rounded-xl backdrop-blur-sm">
                  <p className="text-2xl font-bold">{dashboard?.unread_notifications || 0}</p>
                  <p className="text-xs text-indigo-100">{t('notifications2')}</p>
                </div>
                <div className="text-center px-4 py-2 bg-white/10 rounded-xl backdrop-blur-sm">
                  <p className="text-2xl font-bold">{dashboard?.unread_messages || 0}</p>
                  <p className="text-xs text-indigo-100">{t('messages3')}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Children Selector */}
        {dashboard?.children?.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-2">
            {dashboard.children.map((child, index) => (
              <button
                key={child.id}
                onClick={() => setSelectedChildIndex(index)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl whitespace-nowrap transition-all ${
                  selectedChildIndex === index
                    ? 'bg-indigo-600 text-white shadow-lg'
                    : 'bg-white text-gray-700 border shadow-sm'
                }`}
                data-testid={`child-selector-${child.id}`}
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage src={child.profile_picture} />
                  <AvatarFallback className={`text-sm ${
                    selectedChildIndex === index ? 'bg-white/20 text-white' : 'bg-indigo-100 text-indigo-600'
                  }`}>
                    {child.name?.charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <div className="text-start">
                  <span className="text-sm font-medium block">{child.name?.split(' ')[0]}</span>
                  <span className={`text-xs ${selectedChildIndex === index ? 'text-indigo-100' : 'text-muted-foreground'}`}>
                    {child.grade}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* No Children State */}
        {(!dashboard?.children || dashboard.children.length === 0) && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <Users className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="font-bold text-lg text-gray-700 mb-2">
                {t('noChildrenEnrolled')}
              </h3>
              <p className="text-muted-foreground text-sm mb-4">
                {t('contactSchoolAdministrationToLinkYourAccount')}
              </p>
              <Button variant="outline">
                <MessageSquare className="h-4 w-4 me-2" />
                {t('contactAdmin')}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Selected Child Stats */}
        {selectedChild && (
          <>
            {/* Child Info Card */}
            <Card className="rounded-2xl border-0 shadow-sm overflow-hidden">
              <div className="bg-gradient-to-l from-indigo-50 to-purple-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-14 w-14 border-2 border-indigo-200">
                      <AvatarImage src={selectedChild.profile_picture} />
                      <AvatarFallback className="bg-indigo-100 text-indigo-600 font-bold text-lg">
                        {selectedChild.name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <h2 className="font-cairo font-bold text-lg">{selectedChild.name}</h2>
                      <p className="text-sm text-muted-foreground">
                        {selectedChild.grade} - {selectedChild.class_name}
                      </p>
                      <p className="text-xs text-muted-foreground">{selectedChild.school_name}</p>
                    </div>
                  </div>
                  <Link to={`/parent/child/${selectedChild.id}`}>
                    <Button variant="outline" size="sm" className="text-indigo-600 border-indigo-200">
                      {t('details')}
                      <ChevronLeft className="h-4 w-4 ms-1" />
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3">
              <Card className="rounded-xl border-0 shadow-sm">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="p-2 rounded-lg bg-green-100">
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    </div>
                    <span className="text-2xl font-bold text-green-600">
                      {selectedChild.attendance_rate}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</p>
                  <Progress value={selectedChild.attendance_rate} className="h-1.5 mt-2" />
                </CardContent>
              </Card>

              <Card className="rounded-xl border-0 shadow-sm">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="p-2 rounded-lg bg-blue-100">
                      <Award className="h-5 w-5 text-blue-600" />
                    </div>
                    <span className="text-2xl font-bold text-blue-600">
                      {selectedChild.average_score}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">{t('average2')}</p>
                  <Progress value={selectedChild.average_score} className="h-1.5 mt-2" />
                </CardContent>
              </Card>
            </div>

            {/* Recent Grades */}
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between text-base">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-blue-600" />
                    {t('recentGrades')}
                  </div>
                  <Link to={`/parent/child/${selectedChild.id}/grades`} className="text-xs text-blue-600 hover:underline">
                    {t('viewAll')}
                  </Link>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedChild.recent_grades?.length > 0 ? (
                  <div className="space-y-2">
                    {selectedChild.recent_grades.map((grade, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                        <div className="flex items-center gap-2">
                          <BookOpen className="h-4 w-4 text-gray-400" />
                          <div>
                            <span className="font-medium text-sm">{grade.subject}</span>
                            <p className="text-xs text-muted-foreground">{grade.date}</p>
                          </div>
                        </div>
                        <Badge variant="outline" className={getGradeColor(grade.score / grade.max_score * 100)}>
                          {grade.score}/{grade.max_score}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                    <Award className="h-10 w-10 mb-2 opacity-30" />
                    <p className="text-sm">{isRTL ? 'لا توجد درجات' : 'No grades yet'}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Actions */}
            <div className="grid grid-cols-2 gap-3">
              <Link to={`/parent/child/${selectedChild.id}/schedule`}>
                <Card className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-4 text-center">
                    <Calendar className="h-8 w-8 mx-auto mb-2 text-indigo-600" />
                    <p className="text-sm font-medium">{t('schedule')}</p>
                  </CardContent>
                </Card>
              </Link>
              
              <Link to={`/parent/child/${selectedChild.id}/attendance`}>
                <Card className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-4 text-center">
                    <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-600" />
                    <p className="text-sm font-medium">{t('attendance2')}</p>
                  </CardContent>
                </Card>
              </Link>
              
              <Link to={`/parent/child/${selectedChild.id}/teachers`}>
                <Card className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-4 text-center">
                    <Users className="h-8 w-8 mx-auto mb-2 text-purple-600" />
                    <p className="text-sm font-medium">{t('teachers')}</p>
                  </CardContent>
                </Card>
              </Link>
              
              <Link to="/parent/messages">
                <Card className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all cursor-pointer">
                  <CardContent className="p-4 text-center">
                    <MessageSquare className="h-8 w-8 mx-auto mb-2 text-blue-600" />
                    <p className="text-sm font-medium">{t('messages')}</p>
                  </CardContent>
                </Card>
              </Link>
            </div>
          </>
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentPortalDashboard;
