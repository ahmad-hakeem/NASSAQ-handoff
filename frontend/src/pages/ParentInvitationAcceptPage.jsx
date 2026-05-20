/**
 * Parent Invitation accept landing — Task #206 (IT-P2 §6.2c) +
 * polish pass #277 (parent-portal polish for IT-invited parents).
 *
 * Public, unauthenticated route. The page reads `?token=…` from the
 * URL, posts it to `/public/parent-invitations/accept`, and on success
 * stores the returned one-shot parent bearer in localStorage under the
 * canonical `nassaq_token` key (the same key AuthContext bootstraps
 * from on mount). It then hard-navigates to `/parent?student_id=<id>`
 * so the existing AuthContext + ParentActiveStudentContext pipelines
 * pick up the new identity and select the correct child.
 *
 * After #277 the page renders the standard NASSAQ portal chrome
 * (logo + Hijri date band) and, on success, a centred welcome card
 * naming the inviting teacher and the workspace before the redirect.
 *
 * All failure modes surface through NassaqAlertDialog (info / warning
 * / error variants) using locale-keyed copy. No `console.log`, no
 * native browser dialogs, Arabic-first.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import {
  Loader2, CheckCircle2, AlertCircle, ArrowLeft, ArrowRight, GraduationCap,
} from 'lucide-react';

import { Button } from '../components/ui/button';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { formatFullDate } from '../utils/hijriDate';

const RESOLVED_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const LOGO_WHITE = '/nassaq-logo-white.png';

// Map an HTTP status to the NassaqAlert variant + locale key for the
// landing-page failure modes. Keeps the dialog wiring declarative and
// test-friendly.
const FAILURE_TABLE = {
  invalid_link: { variant: 'warning', key: 'invitationAcceptInvalidLinkLong' },
  expired:      { variant: 'info',    key: 'invitationAcceptExpiredLong' },
  rate_limited: { variant: 'warning', key: 'invitationAcceptRateLimited' },
  unknown:      { variant: 'error',   key: 'invitationAcceptUnknownError' },
};

const ParentInvitationAcceptPage = () => {
  const { t } = useTranslation();
  // ThemeContext is the single source of truth for both `isDark` and
  // `isRTL` — `useTranslation` returns only `{ t, language, localizedValue }`.
  const { isDark, isRTL } = useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { showAlert } = useNassaqAlert();
  const ranRef = useRef(false);
  const [phase, setPhase] = useState('working'); // working | success | error
  const [welcome, setWelcome] = useState(null); // { studentId, inviterName, workspaceName, studentName }

  const dateInfo = useMemo(() => {
    try { return formatFullDate(new Date(), isRTL ? 'ar' : 'en'); } catch { return null; }
  }, [isRTL]);

  const ArrowCTA = isRTL ? ArrowLeft : ArrowRight;

  const showFailure = (kind) => {
    const cfg = FAILURE_TABLE[kind] || FAILURE_TABLE.unknown;
    setPhase('error');
    showAlert({
      type: cfg.variant,
      title: t('invitationAcceptError') || (isRTL ? 'تعذّر قبول الدعوة' : 'Could not accept invitation'),
      message: t(cfg.key) || '',
      confirmText: t('goToSignIn') || (isRTL ? 'الذهاب إلى تسجيل الدخول' : 'Go to sign-in'),
      onConfirm: () => navigate('/login'),
    });
  };

  const goToPortal = (studentId) => {
    const target = `/parent?student_id=${encodeURIComponent(studentId)}`;
    window.location.assign(target);
  };

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;

    const token = (searchParams.get('token') || '').trim();
    if (!token) {
      showFailure('invalid_link');
      return;
    }

    const url = `${RESOLVED_BACKEND_URL}/api/public/parent-invitations/accept`;
    axios
      .post(url, { token })
      .then((res) => {
        const data = res?.data || {};
        const accessToken = data.access_token;
        const studentId = data.student_id;
        if (!accessToken || !studentId) {
          showFailure('unknown');
          return;
        }
        try {
          // Match AuthContext bootstrap key. The full reload on CTA
          // re-creates the AuthContext provider so it reads this token
          // on mount — no need to plumb `setToken` from this public
          // page (AuthContext is not mounted here).
          localStorage.setItem('nassaq_token', accessToken);
          localStorage.removeItem('nassaq_refresh_token');
          // Persist a one-shot welcome flag keyed by student id so the
          // parent home can render its own welcome card on first visit
          // even if the parent navigates away from this landing first.
          const flagKey = `nassaq_invite_welcome_${studentId}`;
          localStorage.setItem(flagKey, JSON.stringify({
            inviter_teacher_name: data.inviter_teacher_name || null,
            workspace_name: data.workspace_name || null,
            student_name: data.student_name || null,
            seeded_at: Date.now(),
          }));
        } catch {
          /* private-mode storage may throw; fall through to navigation */
        }
        setWelcome({
          studentId,
          inviterName: data.inviter_teacher_name || '',
          workspaceName: data.workspace_name || '',
          studentName: data.student_name || '',
        });
        setPhase('success');
      })
      .catch((err) => {
        // Backend contract (POST /public/parent-invitations/accept):
        //   400 → invalid / tampered / decoded-but-expired token
        //   409 → already-used / already-linked
        //   429 → IP rate-limit
        const status = err?.response?.status;
        if (status === 400) showFailure('invalid_link');
        else if (status === 409 || status === 410 || status === 404) showFailure('expired');
        else if (status === 429) showFailure('rate_limited');
        else showFailure('unknown');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      dir={isRTL ? 'rtl' : 'ltr'}
      className={`min-h-screen flex flex-col font-cairo ${isDark ? 'bg-brand-navy' : 'bg-gradient-to-b from-brand-navy via-brand-navy to-brand-purple/40'} text-white`}
      data-testid="parent-invitation-accept-page"
    >
      {/* Standard portal header — logo + Hijri/Greg date band */}
      <header className="sticky top-0 z-20 bg-brand-navy/85 backdrop-blur border-b border-white/10">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-3 px-4 sm:px-6 py-3">
          <div className="flex items-center gap-2 min-w-0">
            <img src={LOGO_WHITE} alt="نَسَّق" className="h-8 w-auto" />
          </div>
          {dateInfo && (
            <div className="text-end min-w-0">
              <p className="text-xs sm:text-sm font-tajawal text-white/85 truncate">
                {dateInfo.weekday}
              </p>
              <p className="text-[10px] sm:text-[11px] font-tajawal text-white/55 truncate">
                {dateInfo.full}
              </p>
            </div>
          )}
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center p-4">
        <div
          className="w-full max-w-md rounded-3xl bg-white/95 dark:bg-card text-brand-navy dark:text-foreground border border-white/10 shadow-2xl shadow-brand-navy/30 p-7 sm:p-8 text-center"
          data-testid="invitation-accept-card"
        >
          {phase === 'working' && (
            <>
              <Loader2 className="h-10 w-10 mx-auto mb-4 text-brand-turquoise animate-spin" />
              <h1 className="text-lg font-bold mb-2">
                {t('invitationAcceptWorking') || (isRTL ? 'جاري تأكيد الدعوة…' : 'Confirming invitation…')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('invitationAcceptInProgress')
                  || (isRTL
                    ? 'لحظة من فضلك بينما نُفعِّل حسابك ونربطك بالطالب.'
                    : 'One moment while we activate your account and link the student.')}
              </p>
            </>
          )}

          {phase === 'success' && welcome && (
            <div data-testid="invitation-welcome-card">
              <div className="mx-auto w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mb-4">
                <CheckCircle2 className="h-7 w-7 text-emerald-500" />
              </div>
              <h1 className="text-xl font-bold mb-1">
                {t('invitationAcceptSuccess') || (isRTL ? 'تم قبول الدعوة بنجاح' : 'Invitation accepted')}
              </h1>
              <p className="text-sm text-muted-foreground mb-5">
                {t('invitationWelcomeSubtitle')
                  || (isRTL
                    ? 'مرحبًا بك في بوابة ولي الأمر — كل ما تحتاجه عن ابنك في مكان واحد.'
                    : 'Welcome to the parent portal — everything about your student in one place.')}
              </p>

              {welcome.inviterName && (
                <div className="rounded-2xl bg-brand-navy/5 dark:bg-white/5 border border-brand-navy/10 dark:border-white/10 px-4 py-3 mb-3 flex items-center gap-3 text-start">
                  <div className="w-9 h-9 rounded-xl bg-brand-turquoise/15 text-brand-turquoise flex items-center justify-center shrink-0">
                    <GraduationCap className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[11px] font-tajawal text-muted-foreground leading-tight">
                      {t('invitedByTeacherLabel') || (isRTL ? 'تمت إضافتك من قِبل' : 'You were invited by')}
                    </p>
                    <p className="text-sm font-bold truncate">
                      {welcome.inviterName}
                    </p>
                    {welcome.workspaceName && (
                      <p className="text-[11px] font-tajawal text-muted-foreground truncate mt-0.5">
                        {welcome.workspaceName}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {welcome.studentName && (
                <p className="text-sm text-muted-foreground mb-5">
                  {(t('invitationLinkedStudent') || (isRTL ? 'تم ربط الطالب: {name}' : 'Linked student: {name}'))
                    .replace('{name}', welcome.studentName)}
                </p>
              )}

              <Button
                type="button"
                className="w-full bg-brand-turquoise hover:bg-brand-turquoise/90 text-brand-navy font-bold h-11"
                onClick={() => goToPortal(welcome.studentId)}
                data-testid="invitation-go-to-portal"
              >
                <span>
                  {t('goToParentPortal') || (isRTL ? 'الذهاب إلى بوابة ولي الأمر' : 'Open the parent portal')}
                </span>
                <ArrowCTA className="w-4 h-4 ms-2" />
              </Button>
              <p className="text-[11px] text-muted-foreground mt-3">
                {t('invitationAcceptRedirecting')
                  || (isRTL ? 'يجري نقلك إلى بوابة ولي الأمر…' : 'Redirecting you to the parent portal…')}
              </p>
            </div>
          )}

          {phase === 'error' && (
            <>
              <AlertCircle className="h-10 w-10 mx-auto mb-4 text-red-500" />
              <h1 className="text-lg font-bold mb-2">
                {t('invitationAcceptError') || (isRTL ? 'تعذّر قبول الدعوة' : 'Could not accept invitation')}
              </h1>
              <Button
                variant="outline"
                className="w-full mt-4"
                onClick={() => navigate('/login')}
                data-testid="parent-invitation-accept-go-login"
              >
                {t('goToSignIn') || (isRTL ? 'الذهاب إلى تسجيل الدخول' : 'Go to sign-in')}
              </Button>
            </>
          )}
        </div>
      </main>
    </div>
  );
};

export default ParentInvitationAcceptPage;
