import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useSyncRouteChildToActive, useParentActiveStudent } from '../../contexts/ParentActiveStudentContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import {
  Heart, ThumbsUp, ThumbsDown, AlertCircle, Calendar
} from 'lucide-react';


const ChildBehaviorPage = () => {
  const { t } = useTranslation();
  // Task #146 — read effective child id from the global context.
  const { childId: routeChildId } = useParams();
  useSyncRouteChildToActive(routeChildId);
  const { activeChildId, hasLoadedChildren } = useParentActiveStudent();
  const childId = activeChildId;
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!hasLoadedChildren || !childId) return;
    let cancelled = false;
    setLoading(true);
    setData(null);
    (async () => {
      try {
        const res = await api.get(`/parent-portal/child/${childId}/behaviour`);
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [childId, hasLoadedChildren, token, api]);

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

  const records = data?.records || [];
  const positive = records.filter(r => r.type === 'positive');
  const negative = records.filter(r => r.type === 'negative');

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="child-behavior-page">
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
