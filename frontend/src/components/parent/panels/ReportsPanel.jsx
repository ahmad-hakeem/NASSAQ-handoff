/**
 * Parent Reports Panel
 *
 * Renders the per-child report (KPIs, attendance details, subject GPAs,
 * behaviour and participation summaries) for a single student. Designed
 * to live inside the parent ``StudentProfilePage`` as a lazy-loaded tab
 * — it does NOT render the student identity header (the profile shell
 * already shows that) and it does not wrap itself in a ``PortalLayout``.
 *
 * Data: ``GET /parent-portal/child/{childId}/progress-report`` — same
 * endpoint the legacy standalone Reports page used. Backend RBAC and
 * parent-scoped access checks are unchanged.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../../../contexts/AuthContext';
import { useTranslation } from '../../../contexts/ThemeContext';
import { Card, CardContent } from '../../ui/card';
import { Progress } from '../../ui/progress';
import { Skeleton } from '../../ui/skeleton';
import { CheckCircle, TrendingUp, Heart, Star, FileText } from 'lucide-react';

const ReportsPanel = ({ childId }) => {
  const { t } = useTranslation();
  const { api } = useAuth();
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(false);
  const abortRef = useRef(null);

  const fetchReport = useCallback(async () => {
    if (!childId) return;
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(false);
    try {
      const res = await api.get(
        `/parent-portal/child/${childId}/progress-report`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setReport(res.data || null);
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return;
      setError(true);
      setReport(null);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [api, childId]);

  useEffect(() => {
    fetchReport();
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, [fetchReport]);

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20 rounded-2xl" />
        <Skeleton className="h-24 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
      </div>
    );
  }

  if (error) {
    return (
      <Card className="rounded-2xl border-0 shadow-sm">
        <CardContent className="py-10 text-center">
          <FileText className="h-10 w-10 mx-auto mb-2 text-muted-foreground/50" />
          <p className="text-sm text-muted-foreground">{t('noReportsAvailable')}</p>
        </CardContent>
      </Card>
    );
  }

  const fmtPct = (v) =>
    (v === null || v === undefined || Number.isNaN(Number(v))) ? '-' : `${v}%`;
  const fmtNum = (v) =>
    (v === null || v === undefined || Number.isNaN(Number(v))) ? '-' : v;
  const subjects = report?.academics?.subject_averages || {};
  const hasSubjects = Object.keys(subjects).length > 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40 rounded-xl text-center">
          <CheckCircle className="h-6 w-6 mx-auto mb-1 text-emerald-600 dark:text-emerald-400" />
          <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">{fmtPct(report?.attendance?.rate)}</p>
          <p className="text-[10px] text-muted-foreground">{t('attendance2')}</p>
        </div>
        <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 rounded-xl text-center">
          <TrendingUp className="h-6 w-6 mx-auto mb-1 text-blue-600 dark:text-blue-400" />
          <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{fmtPct(report?.academics?.overall_average)}</p>
          <p className="text-[10px] text-muted-foreground">{t('average')}</p>
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-bold font-cairo text-foreground">{t('attendanceDetails')}</h3>
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="p-2 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40 rounded-lg">
            <p className="font-bold text-emerald-600 dark:text-emerald-400">{fmtNum(report?.attendance?.present)}</p>
            <p className="text-muted-foreground">{t('present')}</p>
          </div>
          <div className="p-2 bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/40 rounded-lg">
            <p className="font-bold text-red-600 dark:text-red-400">{fmtNum(report?.attendance?.absent)}</p>
            <p className="text-muted-foreground">{t('absent')}</p>
          </div>
          <div className="p-2 bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40 rounded-lg">
            <p className="font-bold text-amber-600 dark:text-amber-400">{fmtNum(report?.attendance?.late)}</p>
            <p className="text-muted-foreground">{t('late')}</p>
          </div>
        </div>
      </div>

      {hasSubjects ? (
        <div className="space-y-3">
          <h3 className="text-sm font-bold font-cairo text-foreground">{t('subjectAverages')}</h3>
          {Object.entries(subjects).map(([subj, raw]) => {
            const num = Number(raw);
            const isValid = raw !== null && raw !== undefined && Number.isFinite(num);
            const clamped = isValid ? Math.max(0, Math.min(100, num)) : 0;
            const colorClass = !isValid
              ? 'text-muted-foreground'
              : num >= 90 ? 'text-emerald-600 dark:text-emerald-400'
              : num >= 75 ? 'text-blue-600 dark:text-blue-400'
              : num >= 60 ? 'text-amber-600 dark:text-amber-400'
              : 'text-red-600 dark:text-red-400';
            return (
              <div key={subj}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-foreground truncate me-2">{subj}</span>
                  <span className={`font-bold tabular-nums shrink-0 ${colorClass}`}>{isValid ? `${num}%` : '-'}</span>
                </div>
                {isValid && <Progress value={clamped} className="h-2" />}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="space-y-2">
          <h3 className="text-sm font-bold font-cairo text-foreground">{t('subjectAverages')}</h3>
          <p className="text-xs text-muted-foreground">{t('noData')}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="p-3 bg-brand-purple/5 dark:bg-brand-purple/15 border border-brand-purple/10 dark:border-brand-purple/30 rounded-xl">
          <Heart className="h-5 w-5 text-brand-purple dark:text-brand-purple/90 mb-1" />
          <p className="text-sm font-bold font-cairo text-foreground">{t('behavior')}</p>
          <p className="text-xs text-muted-foreground">
            {t('positive')}: {fmtNum(report?.behaviour?.positive)} | {t('negative')}: {fmtNum(report?.behaviour?.negative)}
          </p>
        </div>
        <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40 rounded-xl">
          <Star className="h-5 w-5 text-amber-600 dark:text-amber-400 mb-1" />
          <p className="text-sm font-bold font-cairo text-foreground">{t('participation')}</p>
          <p className="text-xs text-muted-foreground">
            {fmtNum(report?.participation?.total_points)} {t('points')}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ReportsPanel;
