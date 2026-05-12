/**
 * Parent Invitation accept landing — Task #206 (IT-P2 §6.2c).
 *
 * Public, unauthenticated route. The page reads `?token=…` from the
 * URL, posts it to `/public/parent-invitations/accept`, and on success
 * stores the returned one-shot parent bearer in localStorage under the
 * canonical `nassaq_token` key (the same key AuthContext bootstraps
 * from on mount). It then hard-navigates to `/parent?student_id=<id>`
 * so the existing AuthContext + ParentActiveStudentContext pipelines
 * pick up the new identity and select the correct child.
 *
 * All failure modes surface through NassaqAlertDialog (info / warning
 * / error variants) using locale-keyed copy. No `console.log`, no
 * native browser dialogs, Arabic-first.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

import { Button } from '../components/ui/button';
import { useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';

const RESOLVED_BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

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
  const { t, isRTL } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { showAlert } = useNassaqAlert();
  const ranRef = useRef(false);
  const [phase, setPhase] = useState('working'); // working | success | error

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
          // Match AuthContext bootstrap key. The full reload below
          // re-creates the AuthContext provider so it reads this token
          // on mount — no need to plumb `setToken` from this public
          // page (AuthContext is not mounted here).
          localStorage.setItem('nassaq_token', accessToken);
          localStorage.removeItem('nassaq_refresh_token');
        } catch {
          /* private-mode storage may throw; fall through to navigation */
        }
        setPhase('success');
        // Hard navigate so AuthContext bootstraps fresh with the new
        // bearer. Deep-link uses `?student_id=` (alias for `?child=`)
        // honoured by ParentActiveStudentContext.
        const target = `/parent?student_id=${encodeURIComponent(studentId)}`;
        window.setTimeout(() => {
          window.location.assign(target);
        }, 600);
      })
      .catch((err) => {
        // Backend contract (POST /public/parent-invitations/accept):
        //   400 → invalid / tampered / decoded-but-expired token
        //   409 → already-used / already-linked
        //   429 → IP rate-limit
        // 400 lumps "invalid signature" with "exp claim past now",
        // and the canonical Arabic detail string the backend returns
        // for both is "رابط الدعوة غير صالح أو منتهي الصلاحية"
        // (invalid OR expired). We render that as the "invalid_link"
        // warning variant so the FE matches the backend wording. 409
        // (already accepted / parent already linked elsewhere) is
        // treated as the info-variant "expired/used" path, since
        // from the parent's POV the link no longer functions.
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
      className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-50 to-white p-4"
      data-testid="parent-invitation-accept-page"
    >
      <div className="w-full max-w-md rounded-2xl border border-gray-100 bg-white shadow-xl p-8 text-center font-cairo">
        {phase === 'working' && (
          <>
            <Loader2 className="h-10 w-10 mx-auto mb-4 text-brand-turquoise animate-spin" />
            <h1 className="text-lg font-bold text-brand-navy mb-2">
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
        {phase === 'success' && (
          <>
            <CheckCircle2 className="h-10 w-10 mx-auto mb-4 text-emerald-500" />
            <h1 className="text-lg font-bold text-brand-navy mb-2">
              {t('invitationAcceptSuccess') || (isRTL ? 'تم قبول الدعوة بنجاح' : 'Invitation accepted')}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t('invitationAcceptRedirecting')
                || (isRTL ? 'يجري نقلك إلى بوابة ولي الأمر…' : 'Redirecting you to the parent portal…')}
            </p>
          </>
        )}
        {phase === 'error' && (
          <>
            <AlertCircle className="h-10 w-10 mx-auto mb-4 text-red-500" />
            <h1 className="text-lg font-bold text-brand-navy mb-2">
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
    </div>
  );
};

export default ParentInvitationAcceptPage;
