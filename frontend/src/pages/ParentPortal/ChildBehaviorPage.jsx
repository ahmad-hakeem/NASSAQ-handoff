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
  Heart, ThumbsUp, ThumbsDown, AlertCircle, Calendar, RefreshCw
} from 'lucide-react';


const ChildBehaviorPage = () => {
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
  const cachedBehavior = getCachedEndpoint(childId, 'behaviour');
  const [loading, setLoading] = useState(!cachedBehavior);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState(cachedBehavior ?? null);
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
    const cached = getCachedEndpoint(requestedFor, 'behaviour');
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
        const res = await api.get(`/parent-portal/child/${requestedFor}/behaviour`);
        if (cancelled || String(activeChildRef.current) !== String(requestedFor)) return;
        setCachedEndpoint(requestedFor, 'behaviour', res.data);
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

  // Task #151 — silently refetch when a teacher posts a new behaviour
  // record for the currently-viewed child.
  useEffect(() => {
    const onUpdated = (e) => {
      const d = e?.detail || {};
      if (d.kind !== 'behaviour') return;
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

  const records = data?.records || [];
  const positive = records.filter(r => r.type === 'positive');
  const negative = records.filter(r => r.type === 'negative');

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="child-behavior-page">
        <BackgroundRefreshChip visible={refreshing} />
        <div className="flex items-center gap-2 mb-2">
          <Heart className="h-6 w-6 text-brand-navy" />
          <h1 className="text-xl font-bold font-cairo">{isRTL ? 'سجل السلوك' : 'Behavior Record'}</h1>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <ThumbsUp className="h-8 w-8 mx-auto mb-2 text-green-600 dark:text-green-400" />
              <p className="text-2xl font-bold text-green-600 dark:text-green-400">{positive.length}</p>
              <p className="text-xs text-muted-foreground">{t('positive')}</p>
            </CardContent>
          </Card>
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <ThumbsDown className="h-8 w-8 mx-auto mb-2 text-red-600 dark:text-red-400" />
              <p className="text-2xl font-bold text-red-600 dark:text-red-400">{negative.length}</p>
              <p className="text-xs text-muted-foreground">{t('negative')}</p>
            </CardContent>
          </Card>
        </div>

        {records.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <Heart className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
              <p className="text-muted-foreground text-sm">{t('noBehaviorRecords')}</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {records.map((record, idx) => (
              <Card key={idx} className="rounded-xl border-0 shadow-sm">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      record.type === 'positive' ? 'bg-green-100 dark:bg-green-900/40' : 'bg-red-100 dark:bg-red-900/40'
                    }`}>
                      {record.type === 'positive' ? (
                        <ThumbsUp className="h-5 w-5 text-green-600 dark:text-green-400" />
                      ) : (
                        <ThumbsDown className="h-5 w-5 text-red-600 dark:text-red-400" />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <p className="font-medium text-sm">{record.category || record.title || (record.type === 'positive' ? (t('positive2')) : (t('negative2')))}</p>
                        <Badge className={`text-xs ${record.type === 'positive' ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300' : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'} border-0`}>
                          {record.points ? `${record.points > 0 ? '+' : ''}${record.points}` : record.type === 'positive' ? '+' : '-'}
                        </Badge>
                      </div>
                      {record.description && <p className="text-xs text-muted-foreground mt-1">{record.description}</p>}
                      {record.notes && <p className="text-xs text-muted-foreground mt-1">{record.notes}</p>}
                      <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        <span>{record.date || record.created_at?.slice(0, 10)}</span>
                        {record.teacher_name && <span>• {record.teacher_name}</span>}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </PortalLayout>
  );
};

export default ChildBehaviorPage;
