import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useSyncRouteChildToActive, useParentActiveStudent } from '../../contexts/ParentActiveStudentContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import BackgroundRefreshChip from '../../components/parent/BackgroundRefreshChip';
import {
  ClipboardList, Clock, CheckCircle, AlertCircle, BookOpen, Calendar, RefreshCw
} from 'lucide-react';


const ChildHomeworkPage = () => {
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
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  // Task #149 — seed from cache so a return visit renders instantly.
  const cachedHomework = getCachedEndpoint(childId, 'homework');
  const [loading, setLoading] = useState(!cachedHomework);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState(cachedHomework ?? null);
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
    const cached = getCachedEndpoint(requestedFor, 'homework');
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
        const res = await api.get(`/parent-portal/child/${requestedFor}/homework`);
        if (cancelled || String(activeChildRef.current) !== String(requestedFor)) return;
        setCachedEndpoint(requestedFor, 'homework', res.data);
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
  }, [childId, hasLoadedChildren, token, api, getCachedEndpoint, setCachedEndpoint, refreshBump]);

  // Task #151 — silently refetch when homework is assigned/graded for
  // the currently-viewed child.
  useEffect(() => {
    const onUpdated = (e) => {
      const d = e?.detail || {};
      if (d.kind !== 'homework') return;
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
          <Skeleton className="h-24 rounded-2xl" />
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-20 rounded-2xl" />)}
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
              <AlertCircle className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="font-bold font-cairo text-lg text-foreground mb-4">
                {t('couldNotLoadData')}
              </h3>
              <Button onClick={() => { setError(false); setLoading(true); setRefreshBump((b) => b + 1); }}>
                <RefreshCw className="h-4 w-4 me-2" strokeWidth={1.5} aria-hidden="true" />
                {t('retry')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  const assignments = data?.assignments || [];
  const stats = data?.statistics || {};

  const getStatusInfo = (status) => {
    const map = {
      pending: { label: t('notStarted'), cls: 'bg-muted/40 text-foreground', icon: Clock },
      submitted: { label: t('submitted'), cls: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300', icon: CheckCircle },
      graded: { label: t('graded2'), cls: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300', icon: BookOpen },
      late: { label: t('late'), cls: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300', icon: AlertCircle },
    };
    return map[status] || map.pending;
  };

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="child-homework-page">
        <BackgroundRefreshChip visible={refreshing} />
        <div className="flex items-center gap-2 mb-2">
          <ClipboardList className="h-6 w-6 text-brand-navy" />
          <h1 className="text-xl font-bold font-cairo">
            {isRTL ? `واجبات ${data?.child_name || ''}` : `${data?.child_name || ''}'s Homework`}
          </h1>
        </div>

        <div className="grid grid-cols-4 gap-2">
          {[
            { label: t('pending'), value: stats.pending || 0, color: 'gray' },
            { label: t('submitted2'), value: stats.submitted || 0, color: 'green' },
            { label: t('graded3'), value: stats.graded || 0, color: 'blue' },
            { label: t('late'), value: stats.late || 0, color: 'red' },
          ].map((s, i) => (
            <Card key={i} className="rounded-xl border-0 shadow-sm">
              <CardContent className="p-3 text-center">
                <p className={`text-xl font-bold text-${s.color}-600`}>{s.value}</p>
                <p className="text-[10px] text-muted-foreground">{s.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {assignments.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <ClipboardList className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
              <p className="text-muted-foreground text-sm">{t('noHomeworkFound')}</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {assignments.map((a, idx) => {
              const si = getStatusInfo(a.status);
              return (
                <Card key={idx} className="rounded-xl border-0 shadow-sm">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-medium text-sm truncate flex-1">{a.title}</p>
                      <Badge className={`${si.cls} border-0 text-xs`}>{si.label}</Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        <span>{t('due')} {a.due_date?.slice(0, 10)}</span>
                      </div>
                      {a.grade !== null && a.grade !== undefined && (
                        <Badge variant="outline" className="text-xs">{t('grade3')} {a.grade}</Badge>
                      )}
                    </div>
                    {a.submission_date && (
                      <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                        {t('submitted3')} {a.submission_date.slice(0, 10)}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </PortalLayout>
  );
};

export default ChildHomeworkPage;
