import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Progress } from '../../components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Skeleton } from '../../components/ui/skeleton';
import {
  FileText, CheckCircle, TrendingUp, Heart, Star,
  ChevronDown, ChevronUp,
} from 'lucide-react';

const ParentReportsPage = () => {
  const { t } = useTranslation();
  const { api } = useAuth();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [reports, setReports] = useState({});
  const [expandedChild, setExpandedChild] = useState(null);
  const abortControllerRef = useRef(null);

  const fetchData = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);
    try {
      const dashRes = await api.get('/parent-portal/dashboard', { signal: controller.signal });
      if (controller.signal.aborted) return;
      setDashboard(dashRes.data);

      const children = dashRes.data?.children || [];
      const reportsMap = {};
      for (const child of children) {
        if (controller.signal.aborted) return;
        try {
          const r = await api.get(`/parent-portal/child/${child.id}/progress-report`, { signal: controller.signal });
          reportsMap[child.id] = r.data;
        } catch (e) {
          if (controller.signal.aborted) return;
          reportsMap[child.id] = null;
        }
      }
      if (controller.signal.aborted) return;
      setReports(reportsMap);
      if (children.length > 0) setExpandedChild(children[0].id);
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return;
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [api]);

  useEffect(() => {
    fetchData();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchData]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const children = dashboard?.children || [];

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-reports-page">
        <div className="flex items-center gap-2 mb-2">
          <FileText className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{t('reports')}</h1>
        </div>

        {children.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm bg-card">
            <CardContent className="py-12 text-center">
              <FileText className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
              <p className="text-muted-foreground">{t('noReportsAvailable')}</p>
            </CardContent>
          </Card>
        ) : (
          children.map((child) => {
            const report = reports[child.id];
            const isExpanded = expandedChild === child.id;

            return (
              <Card key={child.id} className="rounded-2xl border-0 shadow-sm overflow-hidden bg-card">
                <button
                  onClick={() => setExpandedChild(isExpanded ? null : child.id)}
                  className="w-full p-4 flex items-center justify-between bg-gradient-to-l from-brand-navy/5 to-brand-purple/5 hover:from-brand-navy/10 dark:from-brand-navy/10 dark:to-brand-purple/10 dark:hover:from-brand-navy/20 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10 border-2 border-brand-navy/20 dark:border-brand-turquoise/30">
                      <AvatarImage src={child.profile_picture} />
                      <AvatarFallback className="bg-brand-navy/15 dark:bg-brand-turquoise/15 text-brand-navy dark:text-brand-turquoise font-bold">
                        {child.name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="text-start">
                      <p className="font-bold text-sm text-foreground">{child.name}</p>
                      <p className="text-xs text-muted-foreground">{child.grade} - {child.class_name}</p>
                    </div>
                  </div>
                  {isExpanded
                    ? <ChevronUp className="h-5 w-5 text-muted-foreground" />
                    : <ChevronDown className="h-5 w-5 text-muted-foreground" />}
                </button>

                {isExpanded && report && (
                  <CardContent className="p-4 space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40 rounded-xl text-center">
                        <CheckCircle className="h-6 w-6 mx-auto mb-1 text-emerald-600 dark:text-emerald-400" />
                        <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400">{report.attendance?.rate}%</p>
                        <p className="text-[10px] text-muted-foreground">{t('attendance2')}</p>
                      </div>
                      <div className="p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 rounded-xl text-center">
                        <TrendingUp className="h-6 w-6 mx-auto mb-1 text-blue-600 dark:text-blue-400" />
                        <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{report.academics?.overall_average}%</p>
                        <p className="text-[10px] text-muted-foreground">{t('average')}</p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <h3 className="text-sm font-bold font-cairo text-foreground">{t('attendanceDetails')}</h3>
                      <div className="grid grid-cols-3 gap-2 text-center text-xs">
                        <div className="p-2 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40 rounded-lg">
                          <p className="font-bold text-emerald-600 dark:text-emerald-400">{report.attendance?.present}</p>
                          <p className="text-muted-foreground">{t('present')}</p>
                        </div>
                        <div className="p-2 bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/40 rounded-lg">
                          <p className="font-bold text-red-600 dark:text-red-400">{report.attendance?.absent}</p>
                          <p className="text-muted-foreground">{t('absent')}</p>
                        </div>
                        <div className="p-2 bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40 rounded-lg">
                          <p className="font-bold text-amber-600 dark:text-amber-400">{report.attendance?.late}</p>
                          <p className="text-muted-foreground">{t('late')}</p>
                        </div>
                      </div>
                    </div>

                    {report.academics?.subject_averages && Object.keys(report.academics.subject_averages).length > 0 && (
                      <div className="space-y-3">
                        <h3 className="text-sm font-bold font-cairo text-foreground">{t('subjectAverages')}</h3>
                        {Object.entries(report.academics.subject_averages).map(([subj, avg]) => (
                          <div key={subj}>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-foreground">{subj}</span>
                              <span className={`font-bold ${
                                avg >= 90 ? 'text-emerald-600 dark:text-emerald-400'
                                  : avg >= 75 ? 'text-blue-600 dark:text-blue-400'
                                  : avg >= 60 ? 'text-amber-600 dark:text-amber-400'
                                  : 'text-red-600 dark:text-red-400'
                              }`}>{avg}%</span>
                            </div>
                            <Progress value={avg} className="h-2" />
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-brand-purple/5 dark:bg-brand-purple/15 border border-brand-purple/10 dark:border-brand-purple/30 rounded-xl">
                        <Heart className="h-5 w-5 text-brand-purple dark:text-brand-purple/90 mb-1" />
                        <p className="text-sm font-bold font-cairo text-foreground">{t('behavior')}</p>
                        <p className="text-xs text-muted-foreground">
                          {t('positive')}: {report.behaviour?.positive} | {t('negative')}: {report.behaviour?.negative}
                        </p>
                      </div>
                      <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40 rounded-xl">
                        <Star className="h-5 w-5 text-amber-600 dark:text-amber-400 mb-1" />
                        <p className="text-sm font-bold font-cairo text-foreground">{t('participation')}</p>
                        <p className="text-xs text-muted-foreground">
                          {report.participation?.total_points} {t('points')}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentReportsPage;
