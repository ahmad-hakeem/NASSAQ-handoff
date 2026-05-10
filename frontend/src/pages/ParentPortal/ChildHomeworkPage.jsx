import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useSyncRouteChildToActive } from '../../contexts/ParentActiveStudentContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import {
  ClipboardList, Clock, CheckCircle, AlertCircle, BookOpen, Calendar
} from 'lucide-react';


const ChildHomeworkPage = () => {
  const { t } = useTranslation();
  const { childId } = useParams();
  useSyncRouteChildToActive(childId); // Task #146
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get(`/parent-portal/child/${childId}/homework`);
        setData(res.data);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [childId, token]);

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
