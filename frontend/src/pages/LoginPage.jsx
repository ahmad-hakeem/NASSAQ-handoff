import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import MfaLoginChallengePanel from '../components/mfa/MfaLoginChallengePanel';
import {
  Eye,
  EyeOff,
  Mail,
  Lock,
  ArrowRight,
  ArrowLeft,
  Globe,
  Home,
  Loader2,
  Sparkles,
} from 'lucide-react';

const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';
const BG_PATTERN = '/nassaq-pattern.png';
const HAKIM_CHARACTER = '/hakim-poses/welcome.png';

export const LoginPage = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  // Task #195 — single login state machine. Replaces the ad-hoc
  // loading/error/mfaChallenge flags so we can never end up with a
  // success toast and an error surface for the same attempt.
  //   idle           — accepting input
  //   submitting     — POST /auth/login in flight
  //   awaiting_mfa   — backend asked for a second factor
  //   bootstrapping  — login OK; resolving /auth/me + redirect target
  //   redirecting    — redirect committed; final UI = success toast
  //   failed         — surfaced exactly one error; back to accepting input
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const passwordRef = useRef(null);
  const submittingRef = useRef(false); // double-submit guard
  const mountedRef = useRef(true);

  const { login, refreshUser, clearAuthState } = useAuth();
  const { isRTL, toggleLanguage } = useTheme();
  const { nassaqError } = useNassaqAlert();
  const navigate = useNavigate();

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // The submit button (and the inputs) stay disabled for the entire
  // orchestration — not just the raw API call — so a second click can
  // never fire a parallel /auth/login.
  const isBusy = status === 'submitting' || status === 'bootstrapping' || status === 'redirecting' || status === 'awaiting_mfa';

  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [hakimMsg, setHakimMsg] = useState(0);
  // Task #169 Step 10 — MFA challenge handed back from /auth/login.
  // When non-null, the inline factor picker replaces the password form.
  const [mfaChallenge, setMfaChallenge] = useState(null);

  const hakimMessages = isRTL
    ? [
        'مرحبًا! أنا حكيم، مساعدك الذكي.',
        'سجّل دخولك لتبدأ رحلتك مع نَسَّق.',
        'البيانات في انتظارك… دعنا نبدأ!',
      ]
    : [
        "Welcome! I'm Hakim, your smart assistant.",
        'Sign in to start your journey with NASSAQ.',
        'Your data awaits... let\'s get started!',
      ];

  useEffect(() => {
    const interval = setInterval(() => {
      setHakimMsg((prev) => (prev + 1) % hakimMessages.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [hakimMessages.length]);

  const validateEmail = (value) => {
    if (!value) {
      setEmailError(t('emailIsRequired'));
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setEmailError(t('invalidEmailFormat2'));
      return false;
    }
    setEmailError('');
    return true;
  };

  const validatePassword = (value) => {
    if (!value) {
      setPasswordError(t('passwordIsRequired'));
      return false;
    }
    if (value.length < 6) {
      setPasswordError(t('passwordMustBeAtLeast6Characters'));
      return false;
    }
    setPasswordError('');
    return true;
  };

  // Resolve a target route for the authenticated user. Returns the path
  // string when one was found, or null when the role/tenant combination
  // can't be mapped — fail-closed so we never silently dump the user on a
  // generic /dashboard they may not have permission to load.
  const resolveRedirectTarget = (role, userData) => {
    if (role === 'independent_teacher') {
      if (!userData?.mfa_enrolled_at) return '/auth/mfa/enroll';
      if (!userData?.tenant_id) return '/teacher/onboarding';
      return '/teacher';
    }
    switch (role) {
      case 'platform_admin': return '/admin';
      case 'school_principal': return '/principal';
      case 'school_sub_admin': return '/school';
      case 'school_admin': return '/principal';
      case 'platform_operations_manager': return '/admin';
      case 'teacher': return '/teacher';
      case 'student': return '/student';
      case 'parent': return '/parent';
      default: return null;
    }
  };

  // Surface a single failure for the login attempt and reset to `failed`.
  // `kind` picks the surface so we never double-fire:
  //   credentials → inline banner only (validation / 401 / 404)
  //   system      → NassaqAlertDialog only (network, 5xx, bootstrap)
  const failLoginAttempt = (msg, kind = 'credentials') => {
    if (!mountedRef.current) return;
    submittingRef.current = false;
    setStatus('failed');
    if (kind === 'system') {
      setError('');
      nassaqError(msg);
    } else {
      setError(msg);
    }
  };

  // Bootstrap = /auth/me + role/redirect resolution. Treated as part of
  // the login transition: if any step fails we abandon the freshly-issued
  // session locally, leave the user on /login, and surface exactly one
  // safe Arabic error. The success toast only fires after the redirect
  // has been committed.
  const bootstrapAndRedirect = async (fallbackUser) => {
    setStatus('bootstrapping');
    let fresh = null;
    try {
      // /auth/me is the canonical truth (esp. for IT first-login orchestration
      // where mfa_enrolled_at / tenant_id may have just been stamped). If the
      // hook isn't present at all we fall back to the snapshot from /auth/login;
      // a present-but-failing refreshUser is treated as a hard failure.
      if (typeof refreshUser === 'function') {
        fresh = await refreshUser();
      } else {
        fresh = fallbackUser;
      }
    } catch (err) {
      console.error('Login bootstrap: refreshUser threw', err);
      fresh = null;
    }
    if (!mountedRef.current) return;

    if (!fresh || !fresh.role) {
      console.error('Login bootstrap failed at step: me');
      try { clearAuthState?.(); } catch {}
      failLoginAttempt(t('anErrorOccurredDuringLogin'), 'system');
      return;
    }

    const target = resolveRedirectTarget(fresh.role, fresh);
    if (!target) {
      console.error('Login bootstrap failed at step: redirect (unresolved role)', fresh.role);
      try { clearAuthState?.(); } catch {}
      failLoginAttempt(t('anErrorOccurredDuringLogin'), 'system');
      return;
    }

    setStatus('redirecting');
    toast.success(t('loginSuccessful'));
    navigate(target);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submittingRef.current) return;
    if (status !== 'idle' && status !== 'failed') return;

    setError('');

    const isEmailValid = validateEmail(email);
    const isPasswordValid = validatePassword(password);

    if (!isEmailValid || !isPasswordValid) {
      return;
    }

    submittingRef.current = true;
    setStatus('submitting');

    let result;
    try {
      result = await login(email, password, rememberMe);
    } catch (err) {
      console.error('Login: unexpected throw from auth.login', err);
      failLoginAttempt(t('anErrorOccurredDuringLogin'), 'system');
      return;
    }
    if (!mountedRef.current) return;

    if (result?.mfaChallenge) {
      // Switch the card into MFA-challenge mode. No success toast yet —
      // it must wait until /auth/mfa/verify + /auth/me succeed and the
      // redirect commits.
      submittingRef.current = false;
      setMfaChallenge(result.mfaChallenge);
      setStatus('awaiting_mfa');
      setError('');
      return;
    }

    if (!result?.success) {
      const msg = result?.error || t('invalidCredentials');
      const kind = result?.kind === 'system' ? 'system' : 'credentials';
      failLoginAttempt(msg, kind);
      return;
    }

    await bootstrapAndRedirect(result.user);
  };

  const handleMfaSuccess = async (userData) => {
    setMfaChallenge(null);
    await bootstrapAndRedirect(userData);
  };

  const handleMfaCancel = () => {
    submittingRef.current = false;
    setMfaChallenge(null);
    setPassword('');
    setError('');
    setStatus('idle');
  };

  return (
    <div className="min-h-screen flex" dir={isRTL ? 'rtl' : 'ltr'} data-testid="login-page">
      {/* ========== Brand / Visual Side ========== */}
      <div
        className="hidden lg:flex flex-1 flex-col justify-center items-center p-12 relative overflow-hidden"
        style={{
          backgroundImage: `url(${BG_PATTERN})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-brand-navy/95" />

        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 start-10 w-72 h-72 rounded-full bg-brand-turquoise/8 blur-3xl animate-pulse" />
          <div className="absolute bottom-20 end-10 w-96 h-96 rounded-full bg-brand-purple/8 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
          <div className="absolute top-1/2 start-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full bg-brand-turquoise/5 blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />
        </div>

        <div className="relative z-10 text-center max-w-md">
          <img
            src={LOGO_WHITE}
            alt="نَسَّق"
            className="h-32 lg:h-40 w-auto mx-auto mb-8 rounded-3xl animate-fade-in"
            data-testid="login-logo"
          />

          <h2 className="font-cairo text-4xl font-bold text-white mb-4">
            {t('nassaq')}
          </h2>
          <p className="text-2xl text-brand-turquoise font-cairo font-semibold mb-8">
            {t('fromDataToDecisions')}
          </p>

          <p className="text-white/60 font-tajawal mb-10">
            {t('signInToAccessYourDashboardAndManageYourSchoolSmar')
            }
          </p>

          {/* Hakim Trust Element */}
          <div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-4 max-w-sm mx-auto">
            <div className="relative flex-shrink-0">
              <div className="absolute inset-0 rounded-full bg-brand-turquoise/30 blur-md animate-pulse" />
              <img
                src={HAKIM_CHARACTER}
                alt={t('hakim')}
                className="relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl bg-gradient-to-br from-cyan-50 to-violet-50 p-1"
              />
            </div>
            <div className="text-start flex-1 min-h-[48px]">
              <div className="flex items-center gap-1.5 mb-1">
                <Sparkles className="h-3.5 w-3.5 text-brand-turquoise" />
                <span className="text-brand-turquoise font-bold font-cairo text-sm">{t('hakim')}</span>
              </div>
              <p className="text-white/80 text-sm font-tajawal leading-snug transition-all duration-500">
                {hakimMessages[hakimMsg]}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ========== Login Form Side ========== */}
      <div className="flex-1 flex flex-col bg-background">
        <div className="flex items-center justify-between p-4 border-b border-border/50">
          <Button
            variant="ghost"
            asChild
            className="text-muted-foreground hover:text-foreground rounded-xl"
            data-testid="back-to-website-btn"
          >
            <Link to="/" className="flex items-center gap-2">
              <Home className="h-5 w-5" />
              <span className="font-tajawal">
                {t('backToWebsite')}
              </span>
            </Link>
          </Button>

          <Button
            variant="outline"
            onClick={toggleLanguage}
            className="rounded-xl border-border/50"
            data-testid="language-toggle-btn"
          >
            <Globe className="h-5 w-5 me-2" />
            <span className="font-tajawal">{t('key_awupdb')}</span>
          </Button>
        </div>

        <div className="flex-1 flex flex-col justify-center items-center px-4 py-6 sm:p-6 lg:p-12">
          <Card className="w-full max-w-md card-nassaq" data-testid="login-card">
            <CardHeader className="text-center pb-2">
              {/* Mobile-only Hakim + Logo */}
              <div className="lg:hidden flex items-center justify-center gap-3 mb-4">
                <img src={HAKIM_CHARACTER} alt={t('hakim')} className="hakim-img w-16 h-16 rounded-2xl object-contain border-2 border-brand-turquoise bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
                <img src={LOGO_WHITE} alt="نَسَّق" className="h-10 rounded-xl bg-brand-navy p-1.5" />
              </div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'تسجيل الدخول' : 'Sign In'}
              </h1>
              <p className="text-muted-foreground font-tajawal text-sm">
                {t('enterYourCredentialsToAccessYourDashboard')}
              </p>
            </CardHeader>

            <CardContent className="pt-4">
              {error && !mfaChallenge && (
                <div className="mb-4 p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm font-tajawal text-center animate-fade-in">
                  {error}
                </div>
              )}

              {mfaChallenge ? (
                <MfaLoginChallengePanel
                  challenge={mfaChallenge}
                  isRTL={isRTL}
                  onSuccess={handleMfaSuccess}
                  onCancel={handleMfaCancel}
                />
              ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="font-tajawal">
                    {t('email2')}
                  </Label>
                  <div className="relative">
                    <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <Input
                      id="email"
                      type="email"
                      placeholder={t('enterYourEmail')}
                      value={email}
                      autoComplete="off"
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (emailError) validateEmail(e.target.value);
                      }}
                      onBlur={() => validateEmail(email)}
                      className={`ps-10 h-12 rounded-xl font-tajawal ${emailError ? 'border-destructive' : ''}`}
                      disabled={isBusy}
                      data-testid="login-email-input"
                    />
                  </div>
                  {emailError && (
                    <p className="text-destructive text-xs font-tajawal animate-fade-in">{emailError}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label htmlFor="password" className="font-tajawal">
                      {t('password')}
                    </Label>
                    <Link
                      to="/forgot-password"
                      className="text-sm text-brand-turquoise hover:underline font-tajawal"
                      data-testid="forgot-password-link"
                    >
                      {t('forgotPassword')}
                    </Link>
                  </div>
                  <div className="relative">
                    <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <Input
                      ref={passwordRef}
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder={t('enterYourPassword')}
                      value={password}
                      autoComplete="off"
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (passwordError) validatePassword(e.target.value);
                      }}
                      onBlur={() => validatePassword(password)}
                      className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${passwordError ? 'border-destructive' : ''}`}
                      disabled={isBusy}
                      data-testid="login-password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={t('togglePasswordVisibility')}
                      data-testid="toggle-password-btn"
                    >
                      {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                    </button>
                  </div>
                  {passwordError && (
                    <p className="text-destructive text-xs font-tajawal animate-fade-in">{passwordError}</p>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Checkbox
                    id="rememberMe"
                    checked={rememberMe}
                    onCheckedChange={setRememberMe}
                    className="rounded"
                    data-testid="remember-me-checkbox"
                  />
                  <Label htmlFor="rememberMe" className="font-tajawal text-sm cursor-pointer">
                    {t('rememberMe')}
                  </Label>
                </div>

                <Button
                  type="submit"
                  className="w-full h-12 rounded-xl bg-brand-navy hover:bg-brand-navy-light font-cairo text-base shadow-lg hover:shadow-xl transition-all active:scale-[0.98]"
                  disabled={isBusy}
                  data-testid="login-submit-btn"
                >
                  {isBusy ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      {t('signingIn')}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      {isRTL ? 'تسجيل الدخول' : 'Sign In'}
                      {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
                    </span>
                  )}
                </Button>
              </form>
              )}

              {!mfaChallenge && (
              <div className="mt-6 text-center">
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('dontHaveAnAccount')}{' '}
                  <Link
                    to="/register"
                    className="text-brand-turquoise hover:underline font-medium"
                    data-testid="register-link"
                  >
                    {t('register')}
                  </Link>
                </p>
              </div>
              )}

            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
