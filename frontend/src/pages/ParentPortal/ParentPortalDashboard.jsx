import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import useParentDashboard from '../../hooks/useParentDashboard';
import CurrentClassCard from '../../components/parent/CurrentClassCard';
import UpcomingClasses from '../../components/parent/UpcomingClasses';
import WeeklyStory from '../../components/parent/WeeklyStory';
import BackgroundRefreshChip from '../../components/parent/BackgroundRefreshChip';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { LoadingState } from '../../components/ui/LoadingState';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import {
  Users, GraduationCap, Calendar, MessageSquare,
  Building, RefreshCw, AlertCircle,
  Clock, CheckCircle2, Star, Sparkles, CalendarDays,
  ArrowLeft, ArrowRight, Award, UserCheck, X, Zap,
} from 'lucide-react';
import { formatFullDate } from '../../utils/hijriDate';

/* -------------------------------------------------------------------------- */
/* Task #277 — one-shot welcome card for IT-invited parents                    */
/*                                                                            */
/* Reads the localStorage flag seeded by ParentInvitationAcceptPage on a      */
/* successful accept, renders a dismissible welcome banner that names the     */
/* inviting teacher and the workspace, and clears the flag after dismissal    */
/* (or after 14 days, whichever comes first) so it never re-appears.          */
/* -------------------------------------------------------------------------- */
const INVITE_WELCOME_TTL_MS = 14 * 24 * 60 * 60 * 1000;

const InviteWelcomeCard = ({ studentId, t, isRTL }) => {
  const storageKey = studentId ? `nassaq_invite_welcome_${studentId}` : null;
  const [payload, setPayload] = useState(() => {
    if (!storageKey) return null;
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed?.seeded_at && Date.now() - parsed.seeded_at > INVITE_WELCOME_TTL_MS) {
        localStorage.removeItem(storageKey);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  });

  if (!payload) return null;

  const dismiss = () => {
    try { if (storageKey) localStorage.removeItem(storageKey); } catch { /* noop */ }
    setPayload(null);
  };

  return (
    <div
      className="relative rounded-2xl bg-gradient-to-br from-emerald-500/15 via-brand-turquoise/10 to-transparent border border-emerald-400/40 p-4 md:p-5 text-foreground"
      data-testid="parent-invite-welcome-card"
    >
      <button
        type="button"
        onClick={dismiss}
        className={`absolute top-2 ${isRTL ? 'left-2' : 'right-2'} p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-foreground/5`}
        aria-label={t('dismiss') || 'Dismiss'}
        data-testid="invite-welcome-dismiss"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-600 flex items-center justify-center shrink-0">
          <UserCheck className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-tajawal font-bold uppercase tracking-wide text-emerald-600">
            {t('invitationWelcomeBadge') || (isRTL ? 'مرحبًا بك' : 'Welcome')}
          </p>
          <h3 className="text-base md:text-lg font-cairo font-bold mt-0.5">
            {payload.student_name
              ? (t('invitationWelcomeTitleNamed')
                  || (isRTL ? 'تم ربط حسابك بالطالب {name}' : 'Your account is linked to {name}'))
                  .replace('{name}', payload.student_name)
              : (t('invitationWelcomeTitle') || (isRTL ? 'تم تفعيل حسابك بنجاح' : 'Your account is active'))}
          </h3>
          {(payload.inviter_teacher_name || payload.workspace_name) && (
            <p className="text-sm font-tajawal text-muted-foreground mt-1">
              {payload.inviter_teacher_name && (
                (t('invitedByTeacherInline') || (isRTL ? 'تمت إضافتك من قِبل الأستاذ/ة {teacher}' : 'You were invited by {teacher}'))
                  .replace('{teacher}', payload.inviter_teacher_name)
              )}
              {payload.inviter_teacher_name && payload.workspace_name && ' — '}
              {payload.workspace_name && (
                <span className="text-foreground/80">{payload.workspace_name}</span>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* Hero school-day strip (RTL-safe, compact, on dark navy)                    */
/* -------------------------------------------------------------------------- */
const HeroDayStrip = ({ schoolDay, t }) => {
  const sessions = schoolDay?.all_sessions || [];
  if (!schoolDay?.is_school_day || sessions.length === 0) {
    return (
      <div className="rounded-2xl bg-white/5 border border-white/10 px-4 py-3 flex items-center gap-2 text-sm text-white/70">
        <Clock className="w-4 h-4 text-brand-turquoise" />
        <span className="font-tajawal">{t('noScheduleToday')}</span>
      </div>
    );
  }

  const toMin = (s) => {
    if (!s) return 0;
    const [h, m] = s.split(':').map(Number);
    return h * 60 + (m || 0);
  };

  const firstStart = sessions[0]?.start_time || '07:00';
  const lastEnd = sessions[sessions.length - 1]?.end_time || '14:00';
  const dayStart = toMin(firstStart);
  const dayEnd = toMin(lastEnd);
  const total = dayEnd - dayStart || 1;
  const nowMin = toMin(schoolDay.server_time || new Date().toTimeString().slice(0, 5));
  const progress = Math.min(100, Math.max(0, ((nowMin - dayStart) / total) * 100));

  const completed = schoolDay.completed_periods ?? 0;
  const totalPeriods = schoolDay.total_periods ?? sessions.length;
  const remaining = schoolDay.remaining_periods ?? Math.max(totalPeriods - completed, 0);
  const isAfter = nowMin >= dayEnd;
  const isBefore = nowMin < dayStart;

  return (
    <div className="rounded-2xl bg-white/5 border border-white/10 backdrop-blur p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-cairo font-bold text-sm text-white flex items-center gap-2">
          <Clock className="h-4 w-4 text-brand-turquoise" />
          {t('schoolDayTimeline')}
        </h3>
        <div className="flex items-center gap-3 text-[11px] font-tajawal text-white/70">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            {completed} {t('periodsCompleted')}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-white/30" />
            {remaining} {t('periodsRemaining')}
          </span>
        </div>
      </div>

      {/* Period cells row */}
      <div className="flex items-center gap-1.5">
        {sessions.map((session, i) => {
          const sStart = toMin(session.start_time);
          const sEnd = toMin(session.end_time);
          const done = nowMin >= sEnd;
          const active = nowMin >= sStart && nowMin < sEnd;
          const cellCls = done
            ? 'bg-emerald-400/15 border-emerald-300/40 text-emerald-200'
            : active
              ? 'bg-brand-turquoise/25 border-brand-turquoise/60 ring-2 ring-brand-turquoise/40 text-white shadow-sm'
              : 'bg-white/5 border-white/15 text-white/70';
          return (
            <div
              key={i}
              className={`flex-1 h-10 rounded-lg flex items-center justify-center border transition-colors duration-300 ${cellCls}`}
              title={`${session.subject || ''} (${session.start_time} - ${session.end_time})`}
            >
              {done ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : active ? (
                <div className="relative">
                  <span className="font-cairo font-bold text-sm">{i + 1}</span>
                  <span className="absolute -top-0.5 -end-1 w-2 h-2 bg-brand-turquoise rounded-full animate-ping" />
                </div>
              ) : (
                <span className="font-cairo text-sm">{i + 1}</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Time axis */}
      <div className="mt-3 flex items-center justify-between text-[10px] font-tajawal text-white/50 tabular-nums">
        <span>{firstStart}</span>
        {!isBefore && !isAfter && (
          <span className="text-brand-turquoise font-bold">
            {Math.round(progress)}%
          </span>
        )}
        <span>{lastEnd}</span>
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* Star of the Week — derived from existing weeklyStory data                  */
/* -------------------------------------------------------------------------- */
const StarOfTheWeek = ({ weeklyStory, studentName, t }) => {
  const participation = weeklyStory?.participation_count || 0;
  const positive = weeklyStory?.positive_behaviors || 0;
  const skills = weeklyStory?.acquired_skills || [];
  const topSubject = weeklyStory?.strong_subjects?.[0];
  // Display-only excellence (التميز) bonus this week — awarded once per run of
  // 5 consecutive correct answers, matching what the teacher saw live. Not added
  // to any total here.
  const streakBonusPoints = weeklyStory?.streak_bonus_points || 0;
  const totalPoints = participation + positive;
  const hasHighlight = totalPoints > 0 || skills.length > 0 || !!topSubject;

  return (
    <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-brand-turquoise/20 via-brand-turquoise/10 to-transparent border border-brand-turquoise/30 p-4 h-full">
      <div className="absolute -top-6 -end-6 w-28 h-28 rounded-full bg-brand-turquoise/20 blur-2xl pointer-events-none" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-brand-turquoise/25 border border-brand-turquoise/40 flex items-center justify-center shadow-sm shadow-brand-turquoise/20">
              <Star className="w-4.5 h-4.5 text-brand-turquoise fill-brand-turquoise/30" />
            </div>
            <div>
              <p className="font-cairo font-bold text-sm text-white leading-tight">
                {t('starOfTheWeek')}
              </p>
              <p className="text-[10px] text-white/55 font-tajawal mt-0.5">
                {t('weeklyChampion')}
              </p>
            </div>
          </div>
          {totalPoints > 0 && (
            <span className="flex items-center gap-1 text-[11px] font-bold font-cairo text-brand-turquoise bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full px-2.5 py-1 tabular-nums">
              <Sparkles className="w-3 h-3" />
              {totalPoints}
            </span>
          )}
        </div>

        {hasHighlight ? (
          <>
            {studentName && (
              <p className="text-white font-cairo text-base font-bold truncate">
                {studentName}
              </p>
            )}
            <div className="grid grid-cols-2 gap-2 mt-3">
              <div className="rounded-xl bg-white/5 border border-white/10 px-2.5 py-2">
                <p className="text-[10px] text-white/55 font-tajawal">{t('classParticipation')}</p>
                <p className="text-lg font-bold font-cairo text-white tabular-nums leading-tight">{participation}</p>
              </div>
              <div className="rounded-xl bg-white/5 border border-white/10 px-2.5 py-2">
                <p className="text-[10px] text-white/55 font-tajawal">{t('positiveBehavior')}</p>
                <p className="text-lg font-bold font-cairo text-emerald-300 tabular-nums leading-tight">{positive}</p>
              </div>
            </div>
            {streakBonusPoints > 0 && (
              <div className="mt-2 flex items-center gap-2 rounded-xl bg-amber-400/10 border border-amber-400/25 px-3 py-2">
                <Zap className="w-3.5 h-3.5 text-amber-300 shrink-0" strokeWidth={1.5} aria-hidden="true" />
                <span className="text-[11px] font-tajawal text-white/85">
                  {t('streakBonus')}
                </span>
                <span className="ms-auto text-[11px] font-bold font-cairo text-amber-300 tabular-nums">
                  +{streakBonusPoints}
                </span>
              </div>
            )}
            {(topSubject || skills[0]) && (
              <div className="mt-3 flex items-center gap-2 rounded-xl bg-white/5 border border-white/10 px-3 py-2">
                <Award className="w-3.5 h-3.5 text-brand-turquoise shrink-0" />
                <span className="text-[11px] font-tajawal text-white/85 truncate">
                  {topSubject
                    ? `${t('excelledIn')}: ${topSubject.subject}${topSubject.average ? ` — ${topSubject.average}%` : ''}`
                    : skills[0]}
                </span>
              </div>
            )}
          </>
        ) : (
          <div className="mt-2">
            <p className="text-sm font-cairo font-medium text-white/85">
              {t('noWeeklyHighlightYet')}
            </p>
            <p className="text-[11px] text-white/55 font-tajawal mt-1 leading-relaxed">
              {t('weeklyHighlightHint')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */
const ParentPortalDashboard = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const {
    children,
    selectedChild,
    selectedChildId,
    liveData,
    weeklyStory,
    loading,
    liveLoading,
    liveError,
    weeklyLoading,
    weeklyError,
    childrenError,
    refreshing,
    refreshLiveData,
    refreshWeeklyStory,
    refreshChildren,
  } = useParentDashboard();

  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(id);
  }, []);

  const dateInfo = useMemo(() => {
    try { return formatFullDate(now, isRTL ? 'ar' : 'en'); } catch { return null; }
  }, [now, isRTL]);

  const PageArrow = isRTL ? ArrowLeft : ArrowRight;

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <LoadingState variant="fullpage" />
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div
        className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
        dir={isRTL ? 'rtl' : 'ltr'}
        data-testid="parent-portal-dashboard"
      >
        {/* Task #146 — the active-student switcher lives in the shell
            (PortalLayout) so every parent page shares one control. */}

        {/* Task #150 — subtle chip while a background refresh runs on top
            of cached dashboard data after switching back to a previously-
            viewed child. Hidden on cold loads (the skeleton covers it). */}
        <BackgroundRefreshChip visible={refreshing} />

        {childrenError && (() => {
          // Differentiate empty/auth/server/network so we never blame
          // connectivity for a backend error or session problem.
          const kind = (typeof childrenError === 'object' && childrenError?.kind) || 'network';
          let title = t('failedToLoadChildrenData');
          let detail = t('checkConnectionAndRetry');
          if (kind === 'auth') {
            title = t('sessionExpiredTitle') || (isRTL ? 'انتهت صلاحية الجلسة' : 'Session expired');
            detail = t('sessionExpiredDetail') || (isRTL ? 'يرجى تسجيل الدخول من جديد للمتابعة.' : 'Please sign in again to continue.');
          } else if (kind === 'server') {
            title = t('childrenServerErrorTitle') || (isRTL ? 'تعذر تحميل بيانات الأبناء حالياً' : 'Children data is temporarily unavailable');
            detail = t('childrenServerErrorDetail') || (isRTL ? 'حدث خلل مؤقت في الخادم. يرجى إعادة المحاولة بعد قليل.' : 'A temporary server issue occurred. Please retry in a moment.');
          }
          return (
            <Card className="rounded-2xl border border-red-100 dark:border-red-900/40 shadow-sm bg-card" data-testid={`parent-children-error-${kind}`}>
              <CardContent className="py-8 text-center">
                <AlertCircle className="h-10 w-10 mx-auto mb-3 text-red-400 dark:text-red-300" />
                <p className="text-foreground text-sm font-medium mb-1">{title}</p>
                <p className="text-muted-foreground text-xs mb-3">{detail}</p>
                <Button variant="outline" size="sm" onClick={refreshChildren}>
                  <RefreshCw className="h-3.5 w-3.5 me-1.5" />
                  {t('retry')}
                </Button>
              </CardContent>
            </Card>
          );
        })()}

        {!childrenError && (!children || children.length === 0) && !loading && (
          <Card className="rounded-2xl border-0 shadow-sm bg-card">
            <CardContent className="py-12 text-center">
              <Users className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="font-bold text-lg text-foreground mb-2 font-cairo">{t('noChildrenEnrolled')}</h3>
              <p className="text-muted-foreground text-sm mb-4">{t('contactSchoolAdministrationToLinkYourAccount')}</p>
              <Button variant="outline" asChild>
                <Link to="/parent/communication">
                  <MessageSquare className="h-4 w-4 me-2" />
                  {t('contactAdmin')}
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Task #277 — one-shot welcome card for IT-invited parents.
            Renders only while the localStorage flag set on accept is
            present; clears itself on dismiss or after 14 days. */}
        {selectedChildId && (
          <InviteWelcomeCard studentId={selectedChildId} t={t} isRTL={isRTL} />
        )}

        {selectedChild && liveData && (
          <>
            {/* ============================================================= */}
            {/* HERO — wide branded NASSAQ surface                           */}
            {/* ============================================================= */}
            <section
              className="relative overflow-hidden rounded-3xl bg-brand-navy text-white border border-white/5 shadow-2xl shadow-brand-navy/25"
              data-testid="parent-hero"
            >
              {/* Background brand layers */}
              <div
                className="absolute inset-0 opacity-[0.06] pointer-events-none"
                style={{ backgroundImage: "url('/nassaq-pattern.png')" }}
              />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_85%_15%,rgba(70,193,190,0.18),transparent_55%)] pointer-events-none" />
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_95%,rgba(97,80,144,0.22),transparent_55%)] pointer-events-none" />
              <div className="absolute -top-20 end-1/3 w-72 h-72 rounded-full bg-brand-turquoise/5 blur-3xl pointer-events-none" />

              <div className="relative z-10 p-5 md:p-7 lg:p-8 space-y-5 md:space-y-6">
                {/* Top row — identity + date/time + primary action */}
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
                  {/* Identity */}
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="relative shrink-0">
                      <Avatar className="h-16 w-16 md:h-20 md:w-20 border-[3px] border-brand-turquoise/40 shadow-2xl shadow-brand-turquoise/20 ring-4 ring-white/5">
                        <AvatarImage src={liveData.student?.profile_picture || liveData.student?.photo_url} alt={liveData.student?.name} />
                        <AvatarFallback className="bg-gradient-to-br from-brand-turquoise to-brand-purple text-white text-2xl font-bold font-cairo">
                          {liveData.student?.name?.charAt(0) || 'ط'}
                        </AvatarFallback>
                      </Avatar>
                      <div className="absolute -bottom-1 -end-1 w-6 h-6 rounded-lg bg-emerald-500 flex items-center justify-center border-2 border-brand-navy shadow-lg">
                        <CheckCircle2 className="h-3 w-3 text-white" />
                      </div>
                    </div>

                    <div className="min-w-0">
                      <p className="text-brand-turquoise text-[11px] md:text-xs font-tajawal font-bold tracking-wide uppercase">
                        {t('welcome')}
                      </p>
                      <h1 className="font-cairo text-xl md:text-2xl lg:text-3xl font-bold mt-0.5 truncate">
                        {liveData.student?.name}
                      </h1>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        {(liveData.student?.class_name || liveData.student?.grade_level) && (
                          <span
                            className="flex items-center gap-1.5 text-xs font-tajawal text-white/80 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1"
                            data-testid="hero-class-tag"
                          >
                            <GraduationCap className="w-3.5 h-3.5 shrink-0 text-brand-turquoise" aria-hidden="true" />
                            <span className="truncate max-w-[200px]">
                              {liveData.student?.class_name
                                || `${t('grade') || (isRTL ? 'الصف' : 'Grade')} ${liveData.student?.grade_level}`}
                            </span>
                          </span>
                        )}
                        {liveData.student?.is_independent_teacher_workspace ? (
                          <span
                            className="flex items-center gap-1.5 text-xs font-tajawal text-brand-turquoise bg-brand-turquoise/10 border border-brand-turquoise/40 rounded-lg px-2.5 py-1"
                            data-testid="hero-it-badge"
                          >
                            <UserCheck className="w-3.5 h-3.5 shrink-0" />
                            <span className="truncate max-w-[220px]">
                              {liveData.student?.teacher_display_name
                                ? (t('teacherWorkspaceLabel') || (isRTL ? 'مساحة الأستاذ/ة {name}' : "{name}'s workspace"))
                                    .replace('{name}', liveData.student.teacher_display_name)
                                : (t('independentTeacherWorkspace') || (isRTL ? 'مساحة معلّم مستقل' : 'Independent teacher workspace'))}
                            </span>
                          </span>
                        ) : (
                          liveData.student?.school_name && (
                            <span className="flex items-center gap-1.5 text-xs font-tajawal text-white/65 bg-white/5 border border-white/10 rounded-lg px-2.5 py-1">
                              <Building className="w-3.5 h-3.5 shrink-0" />
                              <span className="truncate max-w-[220px]">{liveData.student?.school_name}</span>
                            </span>
                          )
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Date / Time / Primary action */}
                  <div className="flex items-center gap-3 md:gap-4 shrink-0 flex-wrap lg:flex-nowrap lg:justify-end">
                    <div className="hidden sm:flex items-center gap-3 bg-white/5 backdrop-blur rounded-xl px-4 py-2.5 border border-white/10">
                      <CalendarDays className="h-5 w-5 text-brand-turquoise" />
                      <div className="font-tajawal">
                        <p className="text-sm font-bold font-cairo leading-tight">{dateInfo?.weekday || ''}</p>
                        <p className="text-[11px] text-white/55 leading-tight mt-0.5">{dateInfo?.full || ''}</p>
                      </div>
                    </div>

                    <div className="text-center px-1">
                      <p className="text-2xl md:text-3xl font-bold font-cairo tabular-nums leading-none">
                        {now.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' })}
                      </p>
                      <p className="text-[10px] text-white/45 font-tajawal mt-1">
                        {liveData.school_day?.is_school_day ? t('schoolInSession') : t('outsideSchoolHours')}
                      </p>
                    </div>

                    {selectedChildId && (
                      <Link to={`/parent/child/${selectedChildId}/schedule`} data-testid="hero-view-timetable">
                        <button
                          type="button"
                          className="group flex items-center gap-2 rounded-xl bg-brand-turquoise hover:bg-brand-turquoise/90 text-brand-navy font-cairo font-bold text-sm px-4 md:px-5 py-2.5 md:py-3 shadow-lg shadow-brand-turquoise/30 transition-all hover:shadow-xl hover:shadow-brand-turquoise/40 hover:-translate-y-0.5"
                        >
                          <Calendar className="w-4.5 h-4.5" />
                          <span>{t('viewTimetable')}</span>
                          <PageArrow className="w-4 h-4 opacity-70 group-hover:opacity-100 transition-opacity" />
                        </button>
                      </Link>
                    )}
                  </div>
                </div>

                {/* Bottom row — School day strip (2/3) + Star of the Week (1/3) */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-2">
                    <HeroDayStrip schoolDay={liveData.school_day} t={t} />
                  </div>
                  <div className="lg:col-span-1">
                    <StarOfTheWeek
                      weeklyStory={weeklyStory}
                      studentName={liveData.student?.name?.split(' ').slice(0, 2).join(' ')}
                      t={t}
                    />
                  </div>
                </div>
              </div>
            </section>

            {/* ============================================================= */}
            {/* Below-hero — focused parent overview (single column flow)     */}
            {/* ============================================================= */}
            <div className="space-y-4 md:space-y-5">
              {/* 1. Where is the student now? */}
              <CurrentClassCard
                currentClass={liveData.current_class}
                studentName={liveData.student?.name?.split(' ')[0]}
                dayStatus={liveData.school_day?.day_status}
              />

              {/* 2. Next class (default) + collapsible remaining classes */}
              <UpcomingClasses classes={liveData.upcoming_classes} collapsible />

              {/* 3. Story of the Week + Tip of the Week */}
              <WeeklyStory
                data={weeklyStory}
                loading={weeklyLoading}
                error={weeklyError}
                onRetry={refreshWeeklyStory}
              />
            </div>
          </>
        )}

        {selectedChild && !liveData && !liveLoading && liveError && (
          <Card className="rounded-2xl border border-red-100 dark:border-red-900/40 shadow-sm bg-card">
            <CardContent className="py-8 text-center">
              <AlertCircle className="h-10 w-10 mx-auto mb-3 text-red-400 dark:text-red-300" />
              <p className="text-foreground text-sm font-medium mb-1">{t('failedToLoadSchoolDayData')}</p>
              <p className="text-muted-foreground text-xs mb-3">{t('checkConnectionAndRetry')}</p>
              <Button variant="outline" size="sm" onClick={refreshLiveData}>
                <RefreshCw className="h-3.5 w-3.5 me-1.5" />
                {t('retry')}
              </Button>
            </CardContent>
          </Card>
        )}

        {selectedChild && !liveData && !liveLoading && !liveError && (
          <Card className="rounded-2xl border-0 shadow-sm bg-card">
            <CardContent className="py-8 text-center">
              <GraduationCap className="h-10 w-10 mx-auto mb-3 text-muted-foreground/50" />
              <p className="text-muted-foreground text-sm">{t('noDataAvailable')}</p>
            </CardContent>
          </Card>
        )}

        {/* Hakim chat is mounted globally via GlobalHakimMount (App.js) —
            it binds to the active child from ParentActiveStudentContext. */}
      </div>
    </PortalLayout>
  );
};

export default ParentPortalDashboard;
