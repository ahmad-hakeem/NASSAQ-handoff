import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useSyncRouteChildToActive, useParentActiveStudent } from '../../contexts/ParentActiveStudentContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { ScrollArea } from '../../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import BackgroundRefreshChip from '../../components/parent/BackgroundRefreshChip';
import {
  Calendar, BookOpen, ChevronLeft, Clock, User, Printer
} from 'lucide-react';


const DAY_NAMES = {
  sunday: { ar: 'الأحد', color: 'from-blue-500 to-blue-600' },
  monday: { ar: 'الإثنين', color: 'from-brand-purple to-brand-purple-dark' },
  tuesday: { ar: 'الثلاثاء', color: 'from-green-500 to-green-600' },
  wednesday: { ar: 'الأربعاء', color: 'from-amber-500 to-amber-600' },
  thursday: { ar: 'الخميس', color: 'from-rose-500 to-rose-600' },
  friday: { ar: 'الجمعة', color: 'from-emerald-500 to-emerald-600' },
  saturday: { ar: 'السبت', color: 'from-slate-500 to-slate-600' },
};

const ChildSchedulePage = () => {
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  // Task #146 — fetch effective child id from global active-student context.
  const { childId: routeChildId } = useParams();
  useSyncRouteChildToActive(routeChildId);
  const {
    activeChildId,
    activeChild,
    hasLoadedChildren,
    getCachedEndpoint,
    setCachedEndpoint,
  } = useParentActiveStudent();
  // Context-only fetch id; the hook above rejects unauthorized route ids.
  const childId = activeChildId;
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  // Task #149 — seed from the per-(child, endpoint) cache so a return visit
  // renders the previous schedule instantly instead of flashing a skeleton.
  const cachedSchedule = getCachedEndpoint(childId, 'schedule');
  const [loading, setLoading] = useState(!cachedSchedule);
  const [refreshing, setRefreshing] = useState(false);
  const [schedule, setSchedule] = useState(cachedSchedule ?? null);
  // Task #148 — basic identity (name, class) is read from the global
  // active-student context instead of re-fetching `/parent-portal/child/:id`
  // on every navigation.
  const child = activeChild;
  const [viewMode, setViewMode] = useState('list');

  // Stale-response guard: out-of-order responses for a previous child must
  // not overwrite state for the currently active child.
  const activeChildRef = useRef(null);
  activeChildRef.current = childId;

  const fetchData = useCallback(async ({ silent = false } = {}) => {
    if (!hasLoadedChildren || !childId) return;
    const requestedFor = childId;
    if (!silent) setRefreshing(true);
    try {
      // Task #148 — only fetch the page-specific schedule endpoint; basic
      // identity (name, class) comes from the global active-student context.
      const scheduleRes = await api.get(`/parent-portal/child/${requestedFor}/schedule`);
      if (String(activeChildRef.current) !== String(requestedFor)) return;
      setCachedEndpoint(requestedFor, 'schedule', scheduleRes.data);
      setSchedule(scheduleRes.data);
    } catch (error) {
      if (String(activeChildRef.current) !== String(requestedFor)) return;
      // Stay quiet on a background refresh failure if we already have data
      // on screen — the user shouldn't see an alert for a soft refresh.
      const hadData = !!getCachedEndpoint(requestedFor, 'schedule');
      if (!silent && !hadData) nassaqError(t('errorFetchingSchedule'));
    } finally {
      if (String(activeChildRef.current) === String(requestedFor)) {
        if (!silent) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    }
  }, [childId, hasLoadedChildren, api, nassaqError, t, getCachedEndpoint, setCachedEndpoint]);

  useEffect(() => {
    // No active child once children loaded → exit loading; the route-sync
    // hook handles URL canonicalization separately.
    if (hasLoadedChildren && !childId) {
      setLoading(false);
      setRefreshing(false);
      return;
    }
    if (!hasLoadedChildren || !childId) return;
    // Task #149 — render cached data immediately if present; otherwise show
    // the skeleton. Either way, kick off a background refresh.
    const cached = getCachedEndpoint(childId, 'schedule');
    if (cached) {
      setSchedule(cached);
      setLoading(false);
    } else {
      setSchedule(null);
      setLoading(true);
    }
    fetchData();
  }, [token, fetchData, hasLoadedChildren, childId, getCachedEndpoint]);

  // Task #145 — silently refetch this child's published schedule when the
  // school admin publishes a new timetable, via the tenant-scoped
  // ``nassaq:schedule_published`` event bridged from WebSocketContext.
  useEffect(() => {
    const onPublished = () => { fetchData({ silent: true }); };
    window.addEventListener('nassaq:schedule_published', onPublished);
    return () => window.removeEventListener('nassaq:schedule_published', onPublished);
  }, [fetchData]);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const days = schedule?.days || [];
  const scheduleData = schedule?.schedule || {};

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="child-schedule-page">
        <BackgroundRefreshChip visible={refreshing} />
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to={`/parent/child/${childId}`}>
              <Button variant="ghost" size="sm">
                <ChevronLeft className="h-4 w-4 me-1" />
                {isRTL ? 'العودة' : 'Back'}
              </Button>
            </Link>
            <div>
              <h1 className="text-lg font-bold font-cairo">
                {isRTL ? 'الجدول الدراسي' : 'Class Schedule'}
              </h1>
              {child && (
                <p className="text-sm text-muted-foreground">
                  {child.name} - {child.class_name}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handlePrint} className="gap-2 print:hidden">
              <Printer className="h-4 w-4" />
              {t('print')}
            </Button>
            <div className="flex bg-muted/40 rounded-lg p-0.5 print:hidden">
              <button
                onClick={() => setViewMode('list')}
                className={`px-3 py-1 text-xs rounded-md transition ${viewMode === 'list' ? 'bg-white dark:bg-card shadow-sm font-medium' : 'text-muted-foreground'}`}
              >
                {t('list')}
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`px-3 py-1 text-xs rounded-md transition ${viewMode === 'grid' ? 'bg-white dark:bg-card shadow-sm font-medium' : 'text-muted-foreground'}`}
              >
                {t('grid')}
              </button>
            </div>
          </div>
        </div>

        {days.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <Calendar className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="font-bold font-cairo text-lg text-foreground mb-2">
                {t('noScheduleAvailable')}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t('scheduleWillAppearAfterItIsPublishedBySchoolAdmin')}
              </p>
            </CardContent>
          </Card>
        ) : viewMode === 'list' ? (
          <div className="space-y-4">
            {days.map((day) => {
              const dayInfo = DAY_NAMES[day] || { ar: day, color: 'from-gray-500 to-gray-600' };
              const entries = scheduleData[day] || [];
              return (
                <Card key={day} className="rounded-2xl border-0 shadow-sm overflow-hidden">
                  <div className={`bg-gradient-to-r ${dayInfo.color} px-4 py-2.5`}>
                    <h3 className="font-bold font-cairo text-white text-sm flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      {isRTL ? dayInfo.ar : day}
                      <Badge className="bg-white/20 text-white border-0 text-[10px]">
                        {entries.length} {isRTL ? 'حصص' : 'classes'}
                      </Badge>
                    </h3>
                  </div>
                  <CardContent className="p-3">
                    {entries.length > 0 ? (
                      <div className="space-y-2">
                        {entries.map((entry, idx) => (
                          <div key={idx} className="flex items-center gap-3 p-3 bg-muted/40 rounded-xl hover:bg-muted/40 transition">
                            <div className="flex flex-col items-center justify-center min-w-[56px] h-12 rounded-lg bg-brand-navy/15">
                              <span className="text-[10px] font-bold text-brand-navy">{entry.start_time}</span>
                              <span className="text-[9px] text-brand-navy/60">{entry.end_time}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <BookOpen className="h-3.5 w-3.5 text-brand-navy flex-shrink-0" />
                                <p className="font-semibold text-sm truncate">{entry.subject}</p>
                              </div>
                              <div className="flex items-center gap-2 mt-0.5">
                                <User className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                                <p className="text-xs text-muted-foreground truncate">{entry.teacher}</p>
                              </div>
                            </div>
                            {entry.period && (
                              <Badge variant="outline" className="text-[10px] shrink-0">
                                {isRTL ? `ح${entry.period}` : `P${entry.period}`}
                              </Badge>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-center text-sm text-muted-foreground py-4">
                        {isRTL ? 'لا توجد حصص' : 'No classes'}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        ) : (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="p-3">
              <ScrollArea className="w-full">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse" dir="rtl">
                    <thead>
                      <tr>
                        <th className="p-2 text-muted-foreground font-medium border-b w-16">
                          {t('period')}
                        </th>
                        {days.map(day => {
                          const dayInfo = DAY_NAMES[day] || { ar: day, color: 'from-gray-500 to-gray-600' };
                          return (
                            <th key={day} className="p-2 border-b">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-white text-[10px] font-bold bg-gradient-to-r ${dayInfo.color}`}>
                                {isRTL ? dayInfo.ar : day}
                              </span>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const maxPeriods = Math.max(...days.map(d => (scheduleData[d] || []).length), 0);
                        return Array.from({ length: maxPeriods }, (_, i) => (
                          <tr key={i} className="hover:bg-muted/40 dark:hover:bg-muted/30">
                            <td className="p-1.5 text-center font-medium text-muted-foreground border-b">
                              {i + 1}
                            </td>
                            {days.map(day => {
                              const entry = (scheduleData[day] || [])[i];
                              if (!entry) {
                                return (
                                  <td key={day} className="p-1 border-b">
                                    <div className="h-12 rounded-lg bg-muted/40 border border-dashed border-border" />
                                  </td>
                                );
                              }
                              return (
                                <td key={day} className="p-1 border-b">
                                  <div className="h-12 rounded-lg bg-brand-navy/5 border border-brand-navy/10 flex flex-col items-center justify-center px-1">
                                    <span className="text-[10px] font-semibold text-brand-navy truncate max-w-full">
                                      {entry.subject}
                                    </span>
                                    <span className="text-[9px] text-muted-foreground truncate max-w-full">
                                      {entry.teacher}
                                    </span>
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        )}
      </div>

      <style>{`
        @media print {
          .print\\:hidden { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>
    </PortalLayout>
  );
};

export default ChildSchedulePage;
