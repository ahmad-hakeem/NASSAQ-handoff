import React, { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Skeleton } from '../../components/ui/skeleton';
import {
  User as UserIcon, GraduationCap, CheckCircle, TrendingUp, Calendar,
  ClipboardList, Heart,
} from 'lucide-react';

const DetailsPanel = lazy(() => import('../../components/parent/panels/DetailsPanel'));
const SchedulePanel = lazy(() => import('../../components/parent/panels/SchedulePanel'));
const HomeworkPanel = lazy(() => import('../../components/parent/panels/HomeworkPanel'));
const BehaviorPanel = lazy(() => import('../../components/parent/panels/BehaviorPanel'));

const VALID_TABS = ['details', 'schedule', 'homework', 'behavior'];

const ParentChildrenPage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [children, setChildren] = useState([]);

  // URL is the single source of truth for active child + active tab. Tab
  // changes and child changes go through setSearchParams, and what we render
  // is derived from searchParams every render (no shadow useState).
  const urlChildId = searchParams.get('child');
  const urlTabRaw = searchParams.get('tab');
  const activeTab = VALID_TABS.includes(urlTabRaw) ? urlTabRaw : 'details';

  const activeChild = useMemo(() => {
    if (children.length === 0) return null;
    const match = urlChildId && children.find(c => String(c.id) === String(urlChildId));
    return match || children[0];
  }, [children, urlChildId]);
  const selectedChildId = activeChild ? String(activeChild.id) : null;

  const updateParams = useCallback((patch) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      Object.entries(patch).forEach(([k, v]) => {
        if (v == null) next.delete(k);
        else next.set(k, String(v));
      });
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    let cancelled = false;
    const fetchChildren = async () => {
      try {
        const res = await api.get('/parent-portal/children');
        if (!cancelled) setChildren(res.data.children || []);
      } catch {
        try {
          const res2 = await api.get('/parent-portal/dashboard');
          if (!cancelled) setChildren(res2.data.children || []);
        } catch {
          if (!cancelled) setChildren([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchChildren();
    return () => { cancelled = true; };
  }, [token, api]);

  // Normalize URL once children are loaded: if URL is missing/invalid, write
  // the resolved child + tab back so the URL stays canonical for sharing.
  useEffect(() => {
    if (!activeChild) return;
    const patch = {};
    if (urlChildId !== String(activeChild.id)) patch.child = activeChild.id;
    if (urlTabRaw !== activeTab) patch.tab = activeTab;
    if (Object.keys(patch).length > 0) updateParams(patch);
  }, [activeChild, urlChildId, urlTabRaw, activeTab, updateParams]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const tabs = [
    { id: 'details', label: t('details'), icon: GraduationCap },
    { id: 'schedule', label: t('schedule'), icon: Calendar },
    { id: 'homework', label: t('homework'), icon: ClipboardList },
    { id: 'behavior', label: t('behavior'), icon: Heart },
  ];

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-student-profile-page">
        <div className="flex items-center gap-2 mb-2">
          <UserIcon className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{t('studentProfile')}</h1>
        </div>

        {children.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm bg-card">
            <CardContent className="py-16 text-center">
              <UserIcon className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="font-cairo font-bold text-lg text-foreground mb-2">
                {t('noChildrenEnrolled')}
              </h3>
              <p className="text-muted-foreground text-sm">
                {t('contactSchoolAdministrationToLinkYourAccount')}
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Child switcher (only when more than one) */}
            {children.length > 1 && (
              <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
                {children.map(c => {
                  const isActive = String(c.id) === String(activeChild?.id);
                  return (
                    <button
                      key={c.id}
                      onClick={() => updateParams({ child: c.id })}
                      className={`flex items-center gap-2 shrink-0 px-3 py-2 rounded-xl border transition ${
                        isActive
                          ? 'bg-brand-navy/10 dark:bg-brand-turquoise/15 border-brand-navy/30 dark:border-brand-turquoise/40 text-brand-navy dark:text-brand-turquoise font-semibold'
                          : 'bg-card border-border text-foreground hover:bg-muted/40'
                      }`}
                    >
                      <Avatar className="h-7 w-7">
                        <AvatarImage src={c.photo_url || c.profile_picture} />
                        <AvatarFallback className="text-xs bg-brand-navy/15 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise">
                          {c.name?.charAt(0)}
                        </AvatarFallback>
                      </Avatar>
                      <span className="text-sm truncate max-w-[120px]">{c.name}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {activeChild && (
              <Card className="rounded-2xl border border-border shadow-sm overflow-hidden bg-card">
                {/* Student summary header */}
                <div className="bg-gradient-to-l from-brand-navy/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/15 p-4 border-b border-border">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-16 w-16 border-2 border-brand-navy/20 dark:border-brand-turquoise/30">
                      <AvatarImage src={activeChild.photo_url || activeChild.profile_picture} />
                      <AvatarFallback className="bg-brand-navy/15 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise font-bold text-xl">
                        {activeChild.name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <h2 className="font-cairo font-bold text-lg text-foreground truncate">
                        {activeChild.name}
                      </h2>
                      <p className="text-sm text-muted-foreground truncate">
                        {activeChild.grade} - {activeChild.class_name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">{activeChild.school_name}</p>
                    </div>
                  </div>
                </div>

                <CardContent className="p-4 space-y-4">
                  {/* KPI summary */}
                  <div className="grid grid-cols-2 gap-3">
                    {/* KPI render is honest: backend returns null when the
                        student has no attendance/grade records, and we show
                        an em-dash here rather than inventing a 0% / 100%
                        value that would mask missing data. */}
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40">
                      <span className="w-9 h-9 rounded-lg bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 flex items-center justify-center shrink-0">
                        <CheckCircle className="h-5 w-5" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300 tabular-nums">
                          {activeChild.attendance_rate == null ? '—' : `${activeChild.attendance_rate}%`}
                        </p>
                        <p className="text-[10px] text-muted-foreground font-tajawal">{t('attendance2')}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40">
                      <span className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 flex items-center justify-center shrink-0">
                        <TrendingUp className="h-5 w-5" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-blue-700 dark:text-blue-300 tabular-nums">
                          {activeChild.average_score == null ? '—' : `${activeChild.average_score}%`}
                        </p>
                        <p className="text-[10px] text-muted-foreground font-tajawal">{t('average')}</p>
                      </div>
                    </div>
                  </div>

                  {/* Tab nav */}
                  <div
                    role="tablist"
                    aria-label={t('studentProfile')}
                    className="flex gap-1 p-1 bg-muted/40 rounded-xl overflow-x-auto"
                  >
                    {tabs.map(tab => {
                      const Icon = tab.icon;
                      const isActive = activeTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          role="tab"
                          aria-selected={isActive}
                          aria-controls={`panel-${tab.id}`}
                          id={`tab-${tab.id}`}
                          data-testid={`student-tab-${tab.id}`}
                          onClick={() => updateParams({ tab: tab.id })}
                          className={`flex-1 min-w-fit flex items-center justify-center gap-1.5 px-3 py-2 text-xs rounded-lg whitespace-nowrap transition ${
                            isActive
                              ? 'bg-card shadow-sm font-semibold text-foreground'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          {tab.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Active panel — lazy + per-child key so switching child resets state */}
                  <div
                    role="tabpanel"
                    id={`panel-${activeTab}`}
                    aria-labelledby={`tab-${activeTab}`}
                    className="pt-1"
                  >
                    <Suspense fallback={<Skeleton className="h-48 w-full rounded-2xl" />}>
                      {activeTab === 'details' && (
                        <DetailsPanel key={`details-${activeChild.id}`} childId={activeChild.id} />
                      )}
                      {activeTab === 'schedule' && (
                        <SchedulePanel key={`schedule-${activeChild.id}`} childId={activeChild.id} />
                      )}
                      {activeTab === 'homework' && (
                        <HomeworkPanel key={`homework-${activeChild.id}`} childId={activeChild.id} />
                      )}
                      {activeTab === 'behavior' && (
                        <BehaviorPanel key={`behavior-${activeChild.id}`} childId={activeChild.id} />
                      )}
                    </Suspense>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentChildrenPage;
