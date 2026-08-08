import React, { useEffect, useCallback, useState, lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { useParentActiveStudent } from '@/shared/contexts/ParentActiveStudentContext';
import { useAuth } from '@/shared/contexts/AuthContext';
import PortalLayout from '@/features/student-portal/components/portal/PortalLayout';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import StudentProfileDialog from '@/features/parent-portal/components/parent/StudentProfileDialog';
import { getTalentConfig } from '@/features/students/components/student-profile/ProfileComponents';
import {
  User as UserIcon, GraduationCap, CheckCircle, TrendingUp, Calendar,
  ClipboardList, Heart, Pencil, Sparkles, Star, Trophy,
} from 'lucide-react';

const WeeklyAnalysisPanel = lazy(() => import('@/features/parent-portal/components/parent/WeeklyAnalysisPanel'));
const DetailsPanel = lazy(() => import('@/features/parent-portal/components/parent/panels/DetailsPanel'));
const SchedulePanel = lazy(() => import('@/features/parent-portal/components/parent/panels/SchedulePanel'));
const HomeworkPanel = lazy(() => import('@/features/parent-portal/components/parent/panels/HomeworkPanel'));
const BehaviorPanel = lazy(() => import('@/features/parent-portal/components/parent/panels/BehaviorPanel'));

const VALID_TABS = ['details', 'schedule', 'homework', 'behavior'];

const ParentChildrenPage = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  // Task #146 — children + active student come from the global parent
  // context (mounted at App root). This page only owns the URL `?child=` /
  // `?tab=` projection so deep links keep working.
  const {
    linkedChildren: children,
    activeChildId,
    activeChild,
    setActiveChildId,
    isLoading: loading,
  } = useParentActiveStudent();
  const { api, token } = useAuth();

  const urlChildId = searchParams.get('child');
  const urlTabRaw = searchParams.get('tab');
  const activeTab = VALID_TABS.includes(urlTabRaw) ? urlTabRaw : 'details';

  // Unified Student Profile editor (chips for health, behavior, family)
  // opens from the header CTA. Lives at the page level so it can be
  // re-keyed per child to guarantee sibling isolation.
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);

  // Lift grades + attendance fetches to page level so both the top KPI
  // strip and DetailsPanel read from the same live endpoint response,
  // eliminating the stale-cache vs. fresh-fetch mismatch.
  const [childGrades, setChildGrades] = useState(null);
  const [childAttendance, setChildAttendance] = useState(null);
  const [kpiLoading, setKpiLoading] = useState(false);

  useEffect(() => {
    if (!activeChild?.id) return;
    let cancelled = false;
    setKpiLoading(true);
    setChildGrades(null);
    setChildAttendance(null);
    (async () => {
      try {
        const [gradesRes, attendanceRes] = await Promise.all([
          api.get(`/parent-portal/child/${activeChild.id}/grades`).catch(() => ({ data: null })),
          api.get(`/parent-portal/child/${activeChild.id}/attendance`).catch(() => ({ data: null })),
        ]);
        if (cancelled) return;
        setChildGrades(gradesRes.data);
        setChildAttendance(attendanceRes.data);
      } finally {
        if (!cancelled) setKpiLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [activeChild?.id, token, api]);

  // Force-close the dialog when the parent switches to a different
  // child via the shell switcher. The dialog is also re-keyed by
  // activeChild.id below so internal state is reset, but explicitly
  // closing here satisfies the spec acceptance criterion that sibling
  // switching dismisses the open profile modal rather than keeping it
  // open against a freshly mounted child.
  useEffect(() => {
    setProfileDialogOpen(false);
  }, [activeChild?.id]);

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

  // One-way: route ?child= → context. Runs once children are loaded so the
  // initial deep link wins over the context's "first child" default. We
  // call setActiveChildId for *both* valid and invalid ids — invalid ids
  // are rejected by the context with the standard Arabic NassaqAlert and
  // the URL canonicalizer below then strips the bad `?child=` value, so
  // UX parity matches the legacy `:childId` invalid-route handling.
  useEffect(() => {
    if (!urlChildId || children.length === 0) return;
    if (String(urlChildId) !== String(activeChildId)) {
      setActiveChildId(urlChildId);
    }
  }, [urlChildId, children, activeChildId, setActiveChildId]);

  // Keep the URL canonical for sharing: mirror the resolved active child +
  // tab back into ?child= / ?tab= when they drift.
  //
  // IMPORTANT: do NOT canonicalize while there is a `?child=` deep link that
  // refers to a valid linked child but hasn't won context resolution yet.
  // Otherwise the canonicalizer races the route→context sync and can rewrite
  // the URL back to the previously-active child, silently dropping the deep
  // link the user just navigated to.
  useEffect(() => {
    if (!activeChild) return;
    if (
      urlChildId &&
      String(urlChildId) !== String(activeChildId) &&
      children.some((c) => String(c.id) === String(urlChildId))
    ) {
      // A valid deep-linked child id is pending sync into the context —
      // skip this canonicalization pass and let the route→context effect
      // converge first.
      return;
    }
    const patch = {};
    if (urlChildId !== String(activeChild.id)) patch.child = activeChild.id;
    if (urlTabRaw !== activeTab) patch.tab = activeTab;
    if (Object.keys(patch).length > 0) updateParams(patch);
  }, [activeChild, activeChildId, children, urlChildId, urlTabRaw, activeTab, updateParams]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <LoadingState variant="fullpage" />
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
            {/* Child switcher lives in the shell (PortalLayout / Task #146);
                no inline switcher here so there is one source of truth. */}

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
                      <p className="text-xs text-muted-foreground truncate">
                        {activeChild.is_independent_teacher_workspace
                          ? (activeChild.teacher_display_name
                              ? (t('teacherWorkspaceLabel') || (isRTL ? 'مساحة الأستاذ/ة {name}' : "{name}'s workspace"))
                                  .replace('{name}', activeChild.teacher_display_name)
                              : (t('independentTeacherWorkspace') || (isRTL ? 'مساحة معلّم مستقل' : 'Independent teacher workspace')))
                          : activeChild.school_name}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setProfileDialogOpen(true)}
                      className="shrink-0 rounded-xl gap-1.5 font-cairo bg-card/80 hover:bg-card"
                      data-testid="link-edit-student-profile"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">
                        {isRTL ? 'تعديل ملف الطالب' : 'Edit Student Profile'}
                      </span>
                      <span className="sm:hidden">
                        {isRTL ? 'تعديل' : 'Edit'}
                      </span>
                    </Button>
                  </div>
                </div>

                <CardContent className="p-4 space-y-4">
                  {/* KPI summary — reads from the live /grades and /attendance
                      endpoints (same source as DetailsPanel) so the numbers
                      are always consistent, never stale from the children list. */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40">
                      <span className="w-9 h-9 rounded-lg bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 flex items-center justify-center shrink-0">
                        <CheckCircle className="h-5 w-5" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300 tabular-nums">
                          {kpiLoading ? '…' : (() => {
                            const r = childAttendance?.statistics?.attendance_rate;
                            return r == null ? '—' : `${r}%`;
                          })()}
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
                          {kpiLoading ? '…' : (() => {
                            const o = childGrades?.overall_average;
                            return o == null ? '—' : `${o}%`;
                          })()}
                        </p>
                        <p className="text-[10px] text-muted-foreground font-tajawal">{t('average')}</p>
                      </div>
                    </div>
                  </div>

                  {/* المواهب والمهارات — read-only mirror of the talents the
                      school stores on the student record (same values +
                      colors as the admin profile via getTalentConfig).
                      Hidden cleanly when the school has recorded none. */}
                  {(activeChild.talents?.length > 0) && (
                    <div
                      className="p-3 rounded-xl bg-brand-turquoise/5 dark:bg-brand-turquoise/10 border border-brand-turquoise/20 dark:border-brand-turquoise/25 space-y-2.5"
                      data-testid="parent-child-talents"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-cairo font-bold text-foreground flex items-center gap-1.5">
                          <Sparkles className="h-4 w-4 text-brand-turquoise" aria-hidden="true" />
                          {t('talentsSkills')}
                        </p>
                        {activeChild.is_gifted && (
                          <Badge
                            className="bg-gradient-to-r from-yellow-400 to-amber-500 text-white border-0 px-2.5 py-0.5 font-cairo text-[11px]"
                            data-testid="badge-gifted-student"
                          >
                            <Trophy className="h-3 w-3 me-1" aria-hidden="true" />
                            {t('giftedStudent')}
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {activeChild.talents.map((talent) => {
                          const cfg = getTalentConfig(talent);
                          return (
                            <span
                              key={talent}
                              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-cairo font-medium ${cfg.color}`}
                              data-testid={`talent-chip-${talent}`}
                            >
                              <Star className="h-3.5 w-3.5 fill-current opacity-60" aria-hidden="true" />
                              {isRTL ? cfg.ar : cfg.en}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Weekly academic analysis — backend-aggregated, real
                      data only. NO per-child key here on purpose: the
                      component stays mounted across child switches and
                      refetches silently (its internal request-seq guard
                      drops stale responses), so the previous payload
                      remains visible until fresh data arrives instead of
                      flashing a skeleton on every switch. */}
                  <Suspense fallback={<LoadingState variant="section" />}>
                    <WeeklyAnalysisPanel childId={activeChild.id} />
                  </Suspense>

                  {/* Cohesive insights (general strengths/weaknesses, Hakim
                      narrative, per-subject accordion) now lives inside the
                      "Details" tab via DetailsPanel — keeps the profile
                      header light and groups all per-subject context with
                      the rest of the academic detail. */}

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
                    <Suspense fallback={<LoadingState variant="section" />}>
                      {activeTab === 'details' && (
                        <DetailsPanel
                          key={`details-${activeChild.id}`}
                          childId={activeChild.id}
                          grades={childGrades}
                          attendance={childAttendance}
                        />
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

            {/* Per-child key guarantees the dialog unmounts on sibling
                switch, so child A's in-progress edit state cannot leak
                into child B (ProfileEditor's own sibling-reset test
                still covers this at the editor level). */}
            {activeChild && (
              <StudentProfileDialog
                key={`profile-${activeChild.id}`}
                childId={activeChild.id}
                open={profileDialogOpen}
                onOpenChange={setProfileDialogOpen}
              />
            )}
          </>
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentChildrenPage;
