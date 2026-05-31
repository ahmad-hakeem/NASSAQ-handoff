import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import { useSyncRouteChildToActive, useParentActiveStudent } from '../../contexts/ParentActiveStudentContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { GaugeChart, PerformanceLine, SubjectRadar } from '../../components/parent/AnalyticsCharts';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import BackgroundRefreshChip from '../../components/parent/BackgroundRefreshChip';
import { ChevronLeft, TrendingUp, TrendingDown, Activity, CheckCircle, AlertTriangle, ShieldAlert, RefreshCw } from 'lucide-react';

const StudentAnalyticsPage = () => {
  const { t } = useTranslation();
  // Task #146 — read effective child id from the global context.
  const { childId: routeChildId } = useParams();
  useSyncRouteChildToActive(routeChildId);
  const {
    activeChildId,
    hasLoadedChildren,
    getCachedEndpoint,
    setCachedEndpoint,
  } = useParentActiveStudent();
  const childId = activeChildId;
  const { api } = useAuth();
  // Task #149 — seed from cache so a return visit renders instantly.
  const cachedAnalytics = getCachedEndpoint(childId, 'analytics');
  const [data, setData] = useState(cachedAnalytics ?? null);
  const [loading, setLoading] = useState(!cachedAnalytics);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);

  // Stale-response guard against out-of-order responses on rapid switches.
  const activeChildRef = useRef(null);
  activeChildRef.current = childId;

  // Task #151 — bump to force a silent refetch when a relevant
  // ``nassaq:child_data_updated`` event fires for the active child.
  const [refreshBump, setRefreshBump] = useState(0);

  useEffect(() => {
    if (hasLoadedChildren && !childId) {
      setLoading(false);
      setRefreshing(false);
      return;
    }
    if (!hasLoadedChildren || !childId) return;
    let cancelled = false;
    const requestedFor = childId;
    setError(false);
    const cached = getCachedEndpoint(requestedFor, 'analytics');
    if (cached) {
      setData(cached);
      setLoading(false);
      setRefreshing(true);
    } else {
      setData(null);
      setLoading(true);
      setRefreshing(false);
    }
    (async () => {
      try {
        const res = await api.get(`/parent-portal/child/${requestedFor}/analytics`);
        if (cancelled || String(activeChildRef.current) !== String(requestedFor)) return;
        setCachedEndpoint(requestedFor, 'analytics', res.data);
        setData(res.data);
      } catch {
        if (cancelled || String(activeChildRef.current) !== String(requestedFor)) return;
        if (!cached) { setData(null); setError(true); }
      } finally {
        if (!cancelled && String(activeChildRef.current) === String(requestedFor)) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [childId, hasLoadedChildren, api, getCachedEndpoint, setCachedEndpoint, refreshBump]);

  // Task #151 — silently refetch the analytics aggregate whenever any
  // upstream child data (attendance, grade, behaviour, homework) for the
  // currently-viewed child changes.
  useEffect(() => {
    const onUpdated = (e) => {
      const d = e?.detail || {};
      if (!['attendance', 'assessment', 'behaviour', 'homework'].includes(d.kind)) return;
      if (String(d.childId) !== String(childId)) return;
      setRefreshBump((b) => b + 1);
    };
    window.addEventListener('nassaq:child_data_updated', onUpdated);
    return () => window.removeEventListener('nassaq:child_data_updated', onUpdated);
  }, [childId]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-10 w-48 rounded-xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-60 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  if (error) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <AlertTriangle className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="font-bold font-cairo text-lg text-foreground mb-4">
                {t('couldNotLoadData')}
              </h3>
              <div className="flex items-center justify-center gap-3">
                <Button onClick={() => { setError(false); setLoading(true); setRefreshBump((b) => b + 1); }}>
                  <RefreshCw className="h-4 w-4 me-2" strokeWidth={1.5} aria-hidden="true" />
                  {t('retry')}
                </Button>
                <Link to={`/parent/child/${childId}/profile`}>
                  <Button variant="outline">{t('goBack')}</Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  if (!data) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 text-center text-muted-foreground mt-20">
          <p>لا توجد بيانات تحليلية متاحة حالياً</p>
        </div>
      </PortalLayout>
    );
  }

  const followUpConfig = {
    'مستقر': { color: 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900/40', icon: CheckCircle, barColor: 'bg-emerald-500' },
    'يحتاج متابعة': { color: 'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-900/40', icon: AlertTriangle, barColor: 'bg-amber-500' },
    'بحاجة دعم': { color: 'bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-900/40', icon: ShieldAlert, barColor: 'bg-red-500' },
  };

  const fuConf = followUpConfig[data.follow_up?.status] || followUpConfig['مستقر'];
  const FuIcon = fuConf.icon;

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir="rtl">
        <BackgroundRefreshChip visible={refreshing} />
        <div className="flex items-center gap-3 mb-2">
          <Link to={`/parent/child/${childId}/profile`}>
            <button className="p-2 rounded-lg hover:bg-muted/40 transition-colors">
              <ChevronLeft className="w-5 h-5 text-muted-foreground" />
            </button>
          </Link>
          <div>
            <h1 className="text-lg font-bold font-cairo text-foreground">تحليل الأداء</h1>
            <p className="text-xs text-muted-foreground">{data.student_name}</p>
          </div>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-xl bg-brand-navy/5">
                <p className="text-2xl font-bold text-brand-navy">{data.summary?.overall_average}%</p>
                <p className="text-xs text-brand-navy mt-1">المتوسط العام</p>
              </div>
              <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30">
                <p className="text-2xl font-bold text-blue-700 dark:text-blue-300">{data.summary?.class_average}%</p>
                <p className="text-xs text-blue-600 dark:text-blue-400 mt-1">متوسط الفصل</p>
              </div>
              <div className="p-3 rounded-xl bg-brand-purple/5">
                <p className="text-2xl font-bold text-brand-purple">{data.summary?.total_assessments}</p>
                <p className="text-xs text-brand-purple mt-1">التقييمات</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm font-semibold font-cairo text-foreground mb-3">مستوى الأداء الحالي</p>
            <GaugeChart value={data.gauge_data?.value || 0} level={data.gauge_data?.level || ''} />
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm font-semibold font-cairo text-foreground mb-3">اتجاه الأداء</p>
            <PerformanceLine data={data.line_chart_data} />
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm font-semibold font-cairo text-foreground mb-3">توزيع النتائج في المواد</p>
            <SubjectRadar data={data.radar_data} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {data.strengths?.length > 0 && (
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <p className="text-sm font-semibold font-cairo text-foreground">نقاط القوة</p>
                </div>
                <div className="space-y-2">
                  {data.strengths.map((s, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40">
                      <p className="text-sm font-medium text-emerald-800 dark:text-emerald-300">{s.area}</p>
                      <p className="text-xs text-emerald-600 dark:text-emerald-400">{s.detail}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {data.weaknesses?.length > 0 && (
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  <p className="text-sm font-semibold font-cairo text-foreground">يحتاج تحسين</p>
                </div>
                <div className="space-y-2">
                  {data.weaknesses.map((w, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40">
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{w.area}</p>
                      <p className="text-xs text-amber-600 dark:text-amber-400">{w.detail}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-muted-foreground" />
                <p className="text-sm font-semibold font-cairo text-foreground">مؤشر المتابعة المنزلية</p>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${fuConf.color}`}>
                <FuIcon className="w-3.5 h-3.5" />
                {data.follow_up?.status}
              </span>
            </div>
            <div className="space-y-2.5">
              <BreakdownBar label="الحضور" value={data.follow_up?.breakdown?.attendance_rate} color={fuConf.barColor} />
              <BreakdownBar label="الواجبات" value={data.follow_up?.breakdown?.homework_rate} color={fuConf.barColor} />
              <BreakdownBar label="المشاركة" value={data.follow_up?.breakdown?.participation_score} color={fuConf.barColor} />
              <BreakdownBar label="الأكاديمي" value={data.follow_up?.breakdown?.academic_average} color={fuConf.barColor} />
            </div>
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

const BreakdownBar = ({ label, value, color }) => (
  <div className="flex items-center gap-3">
    <span className="text-xs text-muted-foreground w-16 shrink-0">{label}</span>
    <div className="flex-1 h-2 bg-muted/40 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value || 0, 100)}%` }} />
    </div>
    <span className="text-xs font-medium text-muted-foreground w-10 text-left tabular-nums">{Math.round(value || 0)}%</span>
  </div>
);

export default StudentAnalyticsPage;
