import { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
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
const BG_PATTERN = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/1itjy61q_Nassaq%20Background.png';
const HAKIM_CHARACTER = '/hakim-poses/welcome.png';

export const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const passwordRef = useRef(null);

  const { login } = useAuth();
  const { isRTL, toggleLanguage } = useTheme();
  const { nassaqError } = useNassaqAlert();
  const navigate = useNavigate();

  const [emailError, setEmailError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [hakimMsg, setHakimMsg] = useState(0);

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
      setEmailError(isRTL ? 'البريد الإلكتروني مطلوب' : 'Email is required');
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setEmailError(isRTL ? 'البريد الإلكتروني غير صالح' : 'Invalid email format');
      return false;
    }
    setEmailError('');
    return true;
  };

  const validatePassword = (value) => {
    if (!value) {
      setPasswordError(isRTL ? 'كلمة المرور مطلوبة' : 'Password is required');
      return false;
    }
    if (value.length < 6) {
      setPasswordError(isRTL ? 'كلمة المرور يجب أن تكون 6 أحرف على الأقل' : 'Password must be at least 6 characters');
      return false;
    }
    setPasswordError('');
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const isEmailValid = validateEmail(email);
    const isPasswordValid = validatePassword(password);

    if (!isEmailValid || !isPasswordValid) {
      return;
    }

    setLoading(true);

    try {
      const result = await login(email, password);

      if (result.success) {
        toast.success(isRTL ? 'تم تسجيل الدخول بنجاح' : 'Login successful');

        if (rememberMe) {
          localStorage.setItem('rememberMe', 'true');
        }

        switch (result.user.role) {
          case 'platform_admin':
            navigate('/admin');
            break;
          case 'school_principal':
            navigate('/principal');
            break;
          case 'school_sub_admin':
            navigate('/school');
            break;
          case 'school_admin':
            navigate('/principal');
            break;
          case 'platform_operations_manager':
            navigate('/admin');
            break;
          case 'teacher':
            navigate('/teacher');
            break;
          case 'student':
            navigate('/student');
            break;
          case 'parent':
            navigate('/parent');
            break;
          default:
            navigate('/dashboard');
        }
      } else {
        setError(result.error || (isRTL ? 'بيانات الدخول غير صحيحة' : 'Invalid credentials'));
        nassaqError(result.error || (isRTL ? 'بيانات الدخول غير صحيحة' : 'Invalid credentials'));
      }
    } catch (err) {
      setError(isRTL ? 'حدث خطأ أثناء تسجيل الدخول' : 'An error occurred during login');
      nassaqError(isRTL ? 'حدث خطأ أثناء تسجيل الدخول' : 'An error occurred during login');
    } finally {
      setLoading(false);
    }
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
            {isRTL ? 'نَسَّق' : 'NASSAQ'}
          </h2>
          <p className="text-2xl text-brand-turquoise font-cairo font-semibold mb-8">
            {isRTL ? 'من البيانات إلى القرار' : 'From Data to Decisions'}
          </p>

          <p className="text-white/60 font-tajawal mb-10">
            {isRTL
              ? 'سجل دخولك للوصول إلى لوحة التحكم وإدارة مدرستك بذكاء'
              : 'Sign in to access your dashboard and manage your school smartly'
            }
          </p>

          {/* Hakim Trust Element */}
          <div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-4 max-w-sm mx-auto">
            <div className="relative flex-shrink-0">
              <div className="absolute inset-0 rounded-full bg-brand-turquoise/30 blur-md animate-pulse" />
              <img
                src={HAKIM_CHARACTER}
                alt={isRTL ? 'حكيم' : 'Hakim'}
                className="relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl bg-gradient-to-br from-cyan-50 to-violet-50 p-1"
              />
            </div>
            <div className="text-start flex-1 min-h-[48px]">
              <div className="flex items-center gap-1.5 mb-1">
                <Sparkles className="h-3.5 w-3.5 text-brand-turquoise" />
                <span className="text-brand-turquoise font-bold font-cairo text-sm">{isRTL ? 'حكيم' : 'Hakim'}</span>
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
                {isRTL ? 'العودة للموقع' : 'Back to Website'}
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
            <span className="font-tajawal">{isRTL ? 'EN' : 'عربي'}</span>
          </Button>
        </div>

        <div className="flex-1 flex flex-col justify-center items-center px-4 py-6 sm:p-6 lg:p-12">
          <Card className="w-full max-w-md card-nassaq" data-testid="login-card">
            <CardHeader className="text-center pb-2">
              {/* Mobile-only Hakim + Logo */}
              <div className="lg:hidden flex items-center justify-center gap-3 mb-4">
                <img src={HAKIM_CHARACTER} alt={isRTL ? 'حكيم' : 'Hakim'} className="w-16 h-16 rounded-2xl object-contain border-2 border-brand-turquoise bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
                <img src={LOGO_WHITE} alt="نَسَّق" className="h-10 rounded-xl bg-brand-navy p-1.5" />
              </div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'تسجيل الدخول' : 'Sign In'}
              </h1>
              <p className="text-muted-foreground font-tajawal text-sm">
                {isRTL
                  ? 'أدخل بيانات حسابك للوصول إلى لوحة التحكم'
                  : 'Enter your credentials to access your dashboard'}
              </p>
            </CardHeader>

            <CardContent className="pt-4">
              {error && (
                <div className="mb-4 p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm font-tajawal text-center animate-fade-in">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="email" className="font-tajawal">
                    {isRTL ? 'البريد الإلكتروني' : 'Email'}
                  </Label>
                  <div className="relative">
                    <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <Input
                      id="email"
                      type="email"
                      placeholder={isRTL ? 'أدخل بريدك الإلكتروني' : 'Enter your email'}
                      value={email}
                      autoComplete="off"
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (emailError) validateEmail(e.target.value);
                      }}
                      onBlur={() => validateEmail(email)}
                      className={`ps-10 h-12 rounded-xl font-tajawal ${emailError ? 'border-destructive' : ''}`}
                      disabled={loading}
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
                      {isRTL ? 'كلمة المرور' : 'Password'}
                    </Label>
                    <Link
                      to="/forgot-password"
                      className="text-sm text-brand-turquoise hover:underline font-tajawal"
                      data-testid="forgot-password-link"
                    >
                      {isRTL ? 'نسيت كلمة المرور؟' : 'Forgot password?'}
                    </Link>
                  </div>
                  <div className="relative">
                    <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                    <Input
                      ref={passwordRef}
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder={isRTL ? 'أدخل كلمة المرور' : 'Enter your password'}
                      value={password}
                      autoComplete="off"
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (passwordError) validatePassword(e.target.value);
                      }}
                      onBlur={() => validatePassword(password)}
                      className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${passwordError ? 'border-destructive' : ''}`}
                      disabled={loading}
                      data-testid="login-password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={isRTL ? 'إظهار/إخفاء كلمة المرور' : 'Toggle password visibility'}
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
                    {isRTL ? 'تذكرني' : 'Remember me'}
                  </Label>
                </div>

                <Button
                  type="submit"
                  className="w-full h-12 rounded-xl bg-brand-navy hover:bg-brand-navy-light font-cairo text-base shadow-lg hover:shadow-xl transition-all active:scale-[0.98]"
                  disabled={loading}
                  data-testid="login-submit-btn"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      {isRTL ? 'جاري تسجيل الدخول...' : 'Signing in...'}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      {isRTL ? 'تسجيل الدخول' : 'Sign In'}
                      {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
                    </span>
                  )}
                </Button>
              </form>

              <div className="mt-6 text-center">
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? 'ليس لديك حساب؟' : "Don't have an account?"}{' '}
                  <Link
                    to="/register"
                    className="text-brand-turquoise hover:underline font-medium"
                    data-testid="register-link"
                  >
                    {isRTL ? 'تسجيل جديد' : 'Register'}
                  </Link>
                </p>
              </div>

              {/* Quick Login Accounts */}
              <div className="mt-6 pt-6 border-t border-border/50">
                <p className="text-xs text-muted-foreground font-tajawal text-center mb-3">
                  {isRTL ? '⚡ اضغط على حساب لتعبئة البريد الإلكتروني تلقائياً' : '⚡ Click an account to auto-fill the email'}
                </p>

                <p className="text-[10px] font-bold text-muted-foreground font-tajawal mb-1.5 px-1">
                  {isRTL ? '🏫 مدرسة النور الأهلية' : '🏫 Al-Noor Ahlia School'}
                </p>
                {[
                  {
                    icon: '👑',
                    label: isRTL ? 'مدير المنصة' : 'Platform Admin',
                    badge: isRTL ? 'صلاحيات كاملة' : 'Full Access',
                    email: 'admin@nassaq.com',
                    color: 'from-brand-navy/10 to-brand-gold/10 border-brand-navy/30 hover:border-brand-navy/60',
                    labelColor: 'text-brand-navy dark:text-brand-gold',
                    iconBg: 'bg-brand-navy',
                  },
                  {
                    icon: '🏫',
                    label: isRTL ? 'مدير مدرسة النور الأهلية' : 'Al-Noor Ahlia Principal',
                    sublabel: isRTL ? 'عبدالله محمد الشمري' : 'Abdullah Al-Shamri',
                    badge: isRTL ? 'إدارة المدرسة' : 'School Management',
                    email: 'admin@noor-ahlia.edu.sa',
                    color: 'bg-blue-500/5 border-blue-500/25 hover:bg-blue-500/10',
                    labelColor: 'text-blue-600 dark:text-blue-400',
                    iconBg: 'bg-blue-500',
                  },
                  {
                    icon: '📚',
                    label: isRTL ? 'معلم — احمد زلط' : 'Teacher — Ahmed Zalt',
                    sublabel: isRTL ? 'مدرسة النور الأهلية' : 'Al-Noor Ahlia School',
                    badge: isRTL ? 'تدريس' : 'Teaching',
                    email: 'teacher1@nassaq.com',
                    color: 'bg-purple-500/5 border-purple-500/25 hover:bg-purple-500/10',
                    labelColor: 'text-purple-600 dark:text-purple-400',
                    iconBg: 'bg-purple-500',
                  },
                  {
                    icon: '🧑‍🎓',
                    label: isRTL ? 'طالب — يوسف السلمي' : 'Student — Yousef Al-Salmi',
                    sublabel: isRTL ? 'الصف الأول (أ)' : 'Grade 1 (A)',
                    badge: isRTL ? 'بوابة الطالب' : 'Student Portal',
                    email: 'student1@noor-ahlia.edu.sa',
                    color: 'bg-emerald-500/5 border-emerald-500/25 hover:bg-emerald-500/10',
                    labelColor: 'text-emerald-600 dark:text-emerald-400',
                    iconBg: 'bg-emerald-500',
                  },
                  {
                    icon: '👨‍👩‍👦',
                    label: isRTL ? 'ولي أمر — حصة الأنصاري' : 'Parent — Hessa Al-Ansari',
                    sublabel: isRTL ? 'ولي أمر يوسف السلمي' : 'Parent of Yousef Al-Salmi',
                    badge: isRTL ? 'بوابة الأهل' : 'Parent Portal',
                    email: 'parent1@noor-ahlia.edu.sa',
                    color: 'bg-amber-500/5 border-amber-500/25 hover:bg-amber-500/10',
                    labelColor: 'text-amber-600 dark:text-amber-400',
                    iconBg: 'bg-amber-500',
                  },
                ].map((acc) => (
                  <div
                    key={acc.email}
                    className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all mb-2 active:scale-[0.98] ${acc.color}`}
                    onClick={() => {
                      setEmail(acc.email);
                      setPassword('');
                      setEmailError('');
                      setPasswordError('');
                      setTimeout(() => passwordRef.current?.focus(), 100);
                    }}
                  >
                    <div className={`h-8 w-8 rounded-lg ${acc.iconBg} flex items-center justify-center flex-shrink-0`}>
                      <span className="text-sm">{acc.icon}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-bold ${acc.labelColor}`}>{acc.label}</p>
                      {acc.sublabel && <p className="text-[10px] text-muted-foreground">{acc.sublabel}</p>}
                      <p className="text-[10px] text-muted-foreground font-mono truncate">{acc.email}</p>
                    </div>
                    <span className={`text-[10px] font-medium ${acc.labelColor} whitespace-nowrap`}>{acc.badge}</span>
                  </div>
                ))}

                <p className="text-[10px] text-muted-foreground font-tajawal text-center mt-2">
                  {isRTL ? '💡 اضغط على حساب لتعبئة البريد ثم أدخل كلمة المرور' : '💡 Click an account to fill email, then enter password'}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
