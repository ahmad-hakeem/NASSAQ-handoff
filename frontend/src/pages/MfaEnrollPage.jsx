import { useCallback, useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import MfaSecuritySection from '../components/mfa/MfaSecuritySection';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ArrowRight, ArrowLeft, ShieldCheck, LogOut } from 'lucide-react';

// Standalone MFA enrolment surface required by spec §5.1 first-login
// orchestration for Independent-Teacher accounts:
//   signup → MFA enrolment → recent assertion → wizard → bootstrap.
//
// RouteGuards.ProtectedRoute redirects pre-MFA IT users here; before
// this page existed the redirect target (`/auth/mfa/enroll`) had no
// matching <Route> so the catch-all bounced the user back to "/" and
// they appeared to "fall off" the login flow onto the landing page.
//
// Once `mfa_enrolled_at` is stamped on the user, this page hands off
// to the next step in the spec — `/teacher/onboarding` — automatically.
export default function MfaEnrollPage() {
  const { user, refreshUser, logout } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Local "did the section just enroll a factor" flag. We can't rely
  // solely on `user.mfa_enrolled_at` for the Continue-button gate
  // because some browsers/contexts can race the /auth/me refresh after
  // a successful TOTP confirm — without this, the button stays disabled
  // even though enrolment succeeded server-side and the section shows
  // the factor as enabled. The ProtectedRoute check downstream still
  // re-validates against authoritative state, so this only affects
  // when the button becomes clickable.
  const [sectionEnrolled, setSectionEnrolled] = useState(false);

  // Re-pull /auth/me on mount in case the user just enrolled in another
  // tab; this lets us short-circuit the page if they're already done.
  useEffect(() => {
    if (typeof refreshUser === 'function') {
      refreshUser().catch(() => {});
    }
  }, [refreshUser]);

  // Called by MfaSecuritySection after a successful enrol / regen /
  // acknowledge. Pull /auth/me so the AuthContext user (and therefore
  // every downstream guard) sees the new mfa_enrolled_at stamp, and
  // flip the local fast-path flag for the Continue button.
  const handleSectionChange = useCallback(() => {
    setSectionEnrolled(true);
    if (typeof refreshUser === 'function') {
      refreshUser().catch(() => {});
    }
  }, [refreshUser]);

  // Enrolled — advance to the next gate. IT users without a tenant_id
  // go to the onboarding wizard; bootstrapped IT users go to /teacher;
  // any non-IT user who lands here goes to "/" and lets the role-aware
  // guards take it from there.
  // Demo kill switch — when MFA enforcement is disabled the backend will
  // never gate any flow on ``mfa_enrolled_at``. Treat that as "enrolment
  // not required" so a deep-link to /auth/mfa/enroll bounces straight to
  // the role dashboard instead of trapping the user on this page during
  // a demo.
  const mfaEnforcementOff = !!user?.mfa_enforcement_disabled;
  if (user?.mfa_enrolled_at || mfaEnforcementOff) {
    if (user.role === 'independent_teacher') {
      return <Navigate to={user.tenant_id ? '/teacher' : '/teacher/onboarding'} replace />;
    }
    if (user.role === 'parent') return <Navigate to="/parent" replace />;
    if (user.role === 'teacher') return <Navigate to="/teacher" replace />;
    return <Navigate to="/" replace />;
  }

  const ContinueIcon = isRTL ? ArrowLeft : ArrowRight;

  return (
    <div className="min-h-screen bg-background py-10 px-4" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="max-w-3xl mx-auto space-y-6">
        <Card className="rounded-2xl">
          <CardHeader className="flex flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-7 w-7 text-brand-turquoise" />
              <CardTitle className="text-xl font-tajawal">
                {isRTL ? 'إعداد التحقق بخطوتين' : 'Set up two-factor authentication'}
              </CardTitle>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { logout?.(); navigate('/login', { replace: true }); }}
              className="rounded-xl"
              data-testid="mfa-enroll-logout-btn"
            >
              <LogOut className="h-4 w-4 me-2" />
              <span className="font-tajawal">
                {isRTL ? 'تسجيل الخروج' : 'Sign out'}
              </span>
            </Button>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground font-tajawal leading-relaxed">
              {isRTL
                ? 'لحماية مساحتك، يلزم تفعيل عامل تحقق ثانوي قبل المتابعة. أكمل أحد الخيارات أدناه ثم تابع إلى إعداد المساحة.'
                : 'For your account security, please enable a second factor before continuing. Complete one of the options below, then proceed to your workspace setup.'}
            </p>
          </CardContent>
        </Card>

        <MfaSecuritySection onChange={handleSectionChange} />

        <div className="flex justify-end">
          <Button
            onClick={async () => {
              // Re-pull /auth/me so we get the authoritative
              // mfa_enrolled_at + tenant_id before deciding the route.
              let fresh = user;
              try {
                const updated = await refreshUser?.();
                if (updated) fresh = updated;
              } catch { /* fall back to whatever we have */ }
              if (fresh?.role === 'independent_teacher') {
                navigate(fresh?.tenant_id ? '/teacher' : '/teacher/onboarding', { replace: true });
              } else if (fresh?.role === 'parent') {
                navigate('/parent', { replace: true });
              } else if (fresh?.role === 'teacher') {
                navigate('/teacher', { replace: true });
              } else {
                navigate('/', { replace: true });
              }
            }}
            className="rounded-xl"
            data-testid="mfa-enroll-continue-btn"
            disabled={!user?.mfa_enrolled_at && !sectionEnrolled}
          >
            <span className="font-tajawal">
              {isRTL ? 'متابعة' : 'Continue'}
            </span>
            <ContinueIcon className="h-4 w-4 ms-2" />
          </Button>
        </div>
      </div>
    </div>
  );
}
