import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../../contexts/AuthContext';
import { useTranslation } from '../../../contexts/ThemeContext';
import { Card, CardContent } from '../../ui/card';
import { Badge } from '../../ui/badge';
import { Skeleton } from '../../ui/skeleton';
import { ClipboardList, CheckCircle, AlertCircle, Calendar } from 'lucide-react';

const SUBMITTED_STATUSES = new Set(['submitted', 'graded', 'corrected']);
const NOT_SUBMITTED_STATUSES = new Set(['pending', 'late', 'missing', 'not_submitted', 'overdue']);

export const isSubmittedStatus = (status) => SUBMITTED_STATUSES.has(String(status || '').toLowerCase());

export const computeParentHomeworkSummary = (assignments = [], statsFromApi = {}) => {
  if (Array.isArray(assignments) && assignments.length > 0) {
    let submitted = 0;
    let notSubmitted = 0;
    for (const a of assignments) {
      if (isSubmittedStatus(a?.status)) submitted += 1;
      else notSubmitted += 1;
    }
    return { submitted, notSubmitted };
  }
  const s = statsFromApi || {};
  const submitted = (s.submitted || 0) + (s.graded || 0) + (s.corrected || 0);
  const notSubmitted = (s.pending || 0) + (s.late || 0) + (s.missing || 0) + (s.not_submitted || 0);
  return { submitted, notSubmitted };
};

const HomeworkPanel = ({ childId }) => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const res = await api.get(`/parent-portal/child/${childId}/homework`);
        if (!cancelled) setData(res.data);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [childId, token, api]);

  const assignments = data?.assignments || [];
  const summary = useMemo(
    () => computeParentHomeworkSummary(assignments, data?.statistics || {}),
    [assignments, data]
  );

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20 rounded-2xl" />
        {[1, 2, 3].map(i => <Skeleton key={i} className="h-20 rounded-2xl" />)}
      </div>
    );
  }

  const cards = [
    {
      key: 'submitted',
      label: t('hwSubmittedShort'),
      value: summary.submitted,
      colorClass: 'text-green-600 dark:text-green-400',
    },
    {
      key: 'notSubmitted',
      label: t('hwNotSubmittedShort'),
      value: summary.notSubmitted,
      colorClass: 'text-red-600 dark:text-red-400',
    },
  ];

  return (
    <div className="space-y-4" dir="rtl">
      <div className="grid grid-cols-2 gap-3" data-testid="parent-homework-summary">
        {cards.map((s) => (
          <Card key={s.key} className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <p className={`text-2xl font-bold ${s.colorClass}`} data-testid={`hw-summary-${s.key}-value`}>
                {s.value}
              </p>
              <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
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
            const submitted = isSubmittedStatus(a.status);
            const badgeCls = submitted
              ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300'
              : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300';
            const Icon = submitted ? CheckCircle : AlertCircle;
            const label = submitted ? t('hwSubmittedShort') : t('hwNotSubmittedShort');
            return (
              <Card key={idx} className="rounded-xl border-0 shadow-sm">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2 gap-2">
                    <p className="font-medium text-sm truncate flex-1">{a.title}</p>
                    <Badge className={`${badgeCls} border-0 text-xs flex items-center gap-1`}>
                      <Icon className="h-3 w-3" />
                      {label}
                    </Badge>
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
  );
};

export default HomeworkPanel;
