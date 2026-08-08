/**
 * Parent Portal - Child Details Page
 * صفحة تفاصيل الابن لولي الأمر
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { useSyncRouteChildToActive, useParentActiveStudent } from '@/shared/contexts/ParentActiveStudentContext';
import PortalLayout from '@/features/student-portal/components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import CumulativeAnalytics from '@/features/parent-portal/components/parent/CumulativeAnalytics';
import BackgroundRefreshChip from '@/features/parent-portal/components/parent/BackgroundRefreshChip';
import { formatAttendanceDate } from '@/shared/models/utils/hijriDate';
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
  RefreshCw,
} from 'lucide-react';


const ChildDetailsPage = () => {
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  // Task #146 — single source of truth: route `:childId` only seeds the
  // global active-student context; all data fetches read the *effective*
  // child id from that context. This prevents stale-id fetches when the
  // user switches via the shell switcher and ensures unauthorized route
  // ids are rejected before any request fires.
  const { childId: routeChildId } = useParams();
  useSyncRouteChildToActive(routeChildId);
  const {
    activeChildId,
    activeChild,
    hasLoadedChildren,
    getCachedEndpoint,
    setCachedEndpoint,
  } = useParentActiveStudent();
  // Context-only fetch id: never use the raw route param as a fetch input;
  // it might be unauthorized. The hook above rejects bad ids and redirects.
  const childId = activeChildId;
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  // Task #149 — seed page-specific data from the per-(child, endpoint) cache
  // so flipping back to a previously-viewed child renders instantly. We only
  // fall back to a skeleton on a true cold load.
  const cachedDetails = getCachedEndpoint(childId, 'details');
  const [loading, setLoading] = useState(!cachedDetails);
  const [refreshing, setRefreshing] = useState(false);
  const [grades, setGrades] = useState(cachedDetails?.grades ?? null);
  const [attendance, setAttendance] = useState(cachedDetails?.attendance ?? null);
  const [schedule, setSchedule] = useState(cachedDetails?.schedule ?? null);
  const [error, setError] = useState(false);

  // Task #148 — basic identity (name, grade, class, avatar, school) is
  // already in the global active-student context after Task #146, so we
  // read it from there instead of re-fetching `/parent-portal/child/:id`
  // on every navigation. Only page-specific data is fetched per page.
  const child = activeChild;

  // Stale-response guard: discard out-of-order responses for previous children.
  const activeChildRef = useRef(null);
  activeChildRef.current = childId;

  // Task #151 — bump to force a silent refetch when an attendance / grade /
  // behaviour event fires for the currently-viewed child.
  const [refreshBump, setRefreshBump] = useState(0);

  useEffect(() => {
    // Wait until the linked-children list resolves so we never fetch with an
    // unverified id. If load completes with no valid active child, the
    // route-sync hook will have already redirected away — but we still drop
    // out of the loading state so the page never spins forever.
    if (hasLoadedChildren && !childId) {
      setLoading(false);
      setRefreshing(false);
      return;
    }
    if (!hasLoadedChildren || !childId) return;
    let cancelled = false;
    const requestedFor = childId;
    setError(false);
    // Task #149 — render cached data immediately if we have it, otherwise
    // show the skeleton. Either way we kick off a background refresh.
    const cached = getCachedEndpoint(requestedFor, 'details');
    if (cached) {
      setGrades(cached.grades ?? null);
      setAttendance(cached.attendance ?? null);
      setSchedule(cached.schedule ?? null);
      setLoading(false);
      setRefreshing(true);
    } else {
      setGrades(null);
      setAttendance(null);
      setSchedule(null);
      setLoading(true);
      setRefreshing(false);
    }
    (async () => {
      try {
        const [gradesRes, attendanceRes, scheduleRes] = await Promise.all([
          api.get(`/parent-portal/child/${requestedFor}/grades`),
          api.get(`/parent-portal/child/${requestedFor}/attendance`),
          api.get(`/parent-portal/child/${requestedFor}/schedule`),
        ]);
        if (cancelled || String(activeChildRef.current) !== String(requestedFor)) return;
        const next = {
          grades: gradesRes.data,
          attendance: attendanceRes.data,
          schedule: scheduleRes.data,
        };
        setCachedEndpoint(requestedFor, 'details', next);
        setGrades(next.grades);
        setAttendance(next.attendance);
        setSchedule(next.schedule);
      } catch (error) {
        if (cancelled || String(activeChildRef.current) !== String(requestedFor)) return;
        // On cold-load failure surface a recoverable error screen; if we
        // already had cached data we keep showing it and stay quiet
        // (background refresh failed).
        if (!cached) setError(true);
      } finally {
        if (!cancelled && String(activeChildRef.current) === String(requestedFor)) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId, hasLoadedChildren, token, refreshBump]);

  // Task #151 — silently refetch the details bundle when a teacher posts
  // new attendance, a grade, or a behaviour record for the active child.
  useEffect(() => {
    const onUpdated = (e) => {
      const d = e?.detail || {};
      if (!['attendance', 'assessment', 'behaviour'].includes(d.kind)) return;
      if (String(d.childId) !== String(childId)) return;
      setRefreshBump((b) => b + 1);
    };
    window.addEventListener('nassaq:child_data_updated', onUpdated);
    return () => window.removeEventListener('nassaq:child_data_updated', onUpdated);
  }, [childId]);

  const getGradeColor = (percentage) => {
    if (percentage >= 90) return 'text-green-600 dark:text-green-400';
    if (percentage >= 75) return 'text-blue-600 dark:text-blue-400';
    if (percentage >= 60) return 'text-amber-600 dark:text-amber-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'present':
        return <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />;
      case 'absent':
        return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />;
      case 'late':
        return <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
      default:
        return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <LoadingState variant="fullpage" />
      </PortalLayout>
    );
  }

  if (error) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <AlertCircle className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="font-bold font-cairo text-lg text-foreground mb-4">
                {t('couldNotLoadData')}
              </h3>
              <div className="flex items-center justify-center gap-3">
                <Button onClick={() => { setError(false); setLoading(true); setRefreshBump((b) => b + 1); }}>
                  <RefreshCw className="h-4 w-4 me-2" strokeWidth={1.5} aria-hidden="true" />
                  {t('retry')}
                </Button>
                <Link to="/parent">
                  <Button variant="outline">
                    <ChevronLeft className="h-4 w-4 me-2" strokeWidth={1.5} aria-hidden="true" />
                    {t('goBack')}
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
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
              <User className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="font-bold font-cairo text-lg text-foreground mb-2">
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
        <BackgroundRefreshChip visible={refreshing} />
        {/* Child Profile Card */}
        <Card className="rounded-2xl border-0 shadow-sm bg-gradient-to-br from-brand-navy to-brand-purple text-white">
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
                <p className="text-white/80 flex items-center gap-2 mt-1">
                  <MapPin className="h-4 w-4" />
                  {child.is_independent_teacher_workspace
                    ? (child.teacher_display_name
                        ? (t('teacherWorkspaceLabel') || (isRTL ? 'مساحة الأستاذ/ة {name}' : "{name}'s workspace"))
                            .replace('{name}', child.teacher_display_name)
                        : (t('independentTeacherWorkspace') || (isRTL ? 'مساحة معلّم مستقل' : 'Independent teacher workspace')))
                    : child.school_name}
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
                <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/40">
                  <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
                <span className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {attendance?.statistics?.attendance_rate != null ? `${attendance.statistics.attendance_rate}%` : '—'}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</p>
              <Progress value={attendance?.statistics?.attendance_rate ?? 0} className="h-1.5 mt-2" />
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/40">
                  <Award className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <span className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {grades?.overall_average != null ? `${grades.overall_average}%` : '—'}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">{t('average2')}</p>
              <Progress value={grades?.overall_average ?? 0} className="h-1.5 mt-2" />
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="analytics" className="w-full">
          <TabsList className="grid w-full grid-cols-4 bg-muted/40 rounded-xl p-1">
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
                  <div className="p-2 bg-green-50 dark:bg-green-950/30 rounded-lg">
                    <p className="text-lg font-bold text-green-600 dark:text-green-400">{attendance?.statistics?.present || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('present')}</p>
                  </div>
                  <div className="p-2 bg-red-50 dark:bg-red-950/30 rounded-lg">
                    <p className="text-lg font-bold text-red-600 dark:text-red-400">{attendance?.statistics?.absent || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('absent')}</p>
                  </div>
                  <div className="p-2 bg-amber-50 dark:bg-amber-950/30 rounded-lg">
                    <p className="text-lg font-bold text-amber-600 dark:text-amber-400">{attendance?.statistics?.late || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('late')}</p>
                  </div>
                  <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                    <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{attendance?.statistics?.excused || 0}</p>
                    <p className="text-[10px] text-muted-foreground">{t('excused2')}</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  {attendance?.records?.length > 0 ? (
                    <div className="space-y-2">
                      {attendance.records.slice(0, 20).map((record, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-muted/40 rounded-lg">
                          <div className="flex items-center gap-2">
                            {getStatusIcon(record.status)}
                            <span className="text-sm">{formatAttendanceDate(record.date, isRTL ? 'ar' : 'en')}</span>
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
                          <h3 className="font-bold font-cairo text-sm mb-2 text-brand-navy">{day}</h3>
                          {schedule.schedule[day]?.length > 0 ? (
                            <div className="space-y-2">
                              {schedule.schedule[day].map((entry, idx) => (
                                <div key={idx} className="flex items-center gap-3 p-3 bg-muted/40 rounded-lg">
                                  <div className="w-14 h-10 rounded bg-brand-navy/15 flex items-center justify-center">
                                    <span className="text-xs font-bold text-brand-navy">{entry.start_time}</span>
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

        {/* Contact Teachers — hidden for IT-invited parents (Task #277):
            the teacher-list page is a school-only roster surface that does
            not apply to a single-teacher workspace. */}
        {!child.is_independent_teacher_workspace && (
          <Card
            data-testid="contact-teachers-card"
            className="rounded-2xl border-0 shadow-sm"
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-brand-navy" />
                {t('contactTeachers')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Link to={`/parent/child/${childId}/teachers`}>
                <Button className="w-full bg-brand-navy hover:bg-brand-navy-dark">
                  {t('viewTeachersList')}
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </div>
    </PortalLayout>
  );
};

export default ChildDetailsPage;
