import { useState, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { toast } from 'sonner';
import {
  Eye,
  EyeOff,
  Lock,
  ArrowRight,
  ArrowLeft,
  Globe,
  Home,
  Loader2,
  CheckCircle2,
  ShieldCheck,
  XCircle,
  Check,
} from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const LOGO_WHITE = '/nassaq-logo-white.png';
const BG_PATTERN = '/nassaq-pattern.png';
const HAKIM_CHARACTER = '/hakim-poses/giving-instructions.png';

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const { isRTL, toggleLanguage } = useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const rules = useMemo(() => [
    { label: isRTL ? '٨ أحرف على الأقل' : 'At least 8 characters', test: (p) => p.length >= 8 },
    { label: isRTL ? 'حرف كبير' : 'Uppercase letter', test: (p) => /[A-Z]/.test(p) },
    { label: isRTL ? 'حرف صغير' : 'Lowercase letter', test: (p) => /[a-z]/.test(p) },
    { label: isRTL ? 'رقم' : 'Number', test: (p) => /[0-9]/.test(p) },
    { label: isRTL ? 'رمز خاص (@#$!...)' : 'Special character (@#$!...)', test: (p) => /[^A-Za-z0-9]/.test(p) },
  ], [isRTL]);

  const allValid = rules.every((r) => r.test(password)) && password === confirmPassword && confirmPassword.length > 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError(isRTL ? 'كلمتا المرور غير متطابقتين' : 'Passwords do not match');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/api/auth/reset-password`, { token, new_password: password });
      setSuccess(true);
      toast.success(res.data.message || (isRTL ? 'تم تغيير كلمة المرور بنجاح' : 'Password changed successfully'));
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      const msg = err.response?.data?.detail || (isRTL ? 'حدث خطأ. يرجى المحاولة مرة أخرى' : 'An error occurred. Please try again');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background" dir={isRTL ? 'rtl' : 'ltr'}>
        <Card className="w-full max-w-md card-nassaq">
          <CardContent className="text-center py-12 space-y-4">
            <XCircle className="h-16 w-16 text-destructive mx-auto" />
            <h2 className="font-cairo text-xl font-bold text-foreground">
              {isRTL ? 'رابط غير صالح' : 'Invalid Link'}
            </h2>
            <p className="text-muted-foreground font-tajawal text-sm">
              {isRTL ? 'رابط إعادة التعيين غير صالح أو منتهي الصلاحية.' : 'The reset link is invalid or expired.'}
            </p>
            <Button asChild variant="outline" className="rounded-xl mt-4">
              <Link to="/forgot-password" className="font-tajawal">
                {isRTL ? 'طلب رابط جديد' : 'Request New Link'}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex" dir={isRTL ? 'rtl' : 'ltr'}>
      <div
        className="hidden lg:flex flex-1 flex-col justify-center items-center p-12 relative overflow-hidden"
        style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
      >
        <div className="absolute inset-0 bg-brand-navy/95" />
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 start-10 w-72 h-72 rounded-full bg-brand-turquoise/8 blur-3xl animate-pulse" />
          <div className="absolute bottom-20 end-10 w-96 h-96 rounded-full bg-brand-purple/8 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        </div>
        <div className="relative z-10 text-center max-w-md">
          <img src={LOGO_WHITE} alt="نَسَّق" className="h-32 lg:h-40 w-auto mx-auto mb-8 rounded-3xl animate-fade-in" />
          <h2 className="font-cairo text-4xl font-bold text-white mb-4">{isRTL ? 'نَسَّق' : 'NASSAQ'}</h2>
          <div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-4 max-w-sm mx-auto">
            <img src={HAKIM_CHARACTER} alt="حكيم" className="w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
            <div className="text-start flex-1">
              <p className="text-white/80 text-sm font-tajawal leading-snug">
                {isRTL ? 'اختر كلمة مرور قوية للحفاظ على أمان حسابك!' : 'Choose a strong password to keep your account secure!'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-background">
        <div className="flex items-center justify-between p-4 border-b border-border/50">
          <Button variant="ghost" asChild className="text-muted-foreground hover:text-foreground rounded-xl">
            <Link to="/" className="flex items-center gap-2">
              <Home className="h-5 w-5" />
              <span className="font-tajawal">{isRTL ? 'العودة للموقع' : 'Back to Website'}</span>
            </Link>
          </Button>
          <Button variant="outline" onClick={toggleLanguage} className="rounded-xl border-border/50">
            <Globe className="h-5 w-5 me-2" />
            <span className="font-tajawal">{isRTL ? 'English' : 'العربية'}</span>
          </Button>
        </div>

        <div className="flex-1 flex flex-col justify-center items-center px-4 py-6 sm:p-6 lg:p-12">
          <Card className="w-full max-w-md card-nassaq">
            <CardHeader className="text-center pb-2">
              <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-brand-turquoise/10 flex items-center justify-center">
                <ShieldCheck className="h-8 w-8 text-brand-turquoise" />
              </div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'تعيين كلمة مرور جديدة' : 'Set New Password'}
              </h1>
            </CardHeader>

            <CardContent className="pt-4">
              {success ? (
                <div className="text-center space-y-4 py-4">
                  <div className="mx-auto w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                    <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
                  </div>
                  <h3 className="font-cairo text-lg font-semibold text-foreground">
                    {isRTL ? 'تم التغيير بنجاح!' : 'Password Changed!'}
                  </h3>
                  <p className="text-muted-foreground font-tajawal text-sm">
                    {isRTL ? 'سيتم تحويلك لصفحة تسجيل الدخول...' : 'Redirecting to login page...'}
                  </p>
                </div>
              ) : (
                <>
                  {error && (
                    <div className="mb-4 p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-sm font-tajawal text-center animate-fade-in">
                      {error}
                    </div>
                  )}

                  <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="space-y-2">
                      <Label htmlFor="password" className="font-tajawal">
                        {isRTL ? 'كلمة المرور الجديدة' : 'New Password'}
                      </Label>
                      <div className="relative">
                        <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="password"
                          type={showPassword ? 'text' : 'password'}
                          placeholder={isRTL ? 'أدخل كلمة المرور الجديدة' : 'Enter new password'}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          className="ps-10 pe-10 h-12 rounded-xl font-tajawal"
                          disabled={loading}
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        >
                          {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                      </div>
                    </div>

                    {password && (
                      <div className="bg-muted/50 rounded-xl p-3 space-y-1.5">
                        {rules.map((rule, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs font-tajawal">
                            {rule.test(password) ? (
                              <Check className="h-3.5 w-3.5 text-green-600 flex-shrink-0" />
                            ) : (
                              <XCircle className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                            )}
                            <span className={rule.test(password) ? 'text-green-600' : 'text-muted-foreground'}>
                              {rule.label}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="space-y-2">
                      <Label htmlFor="confirm" className="font-tajawal">
                        {isRTL ? 'تأكيد كلمة المرور' : 'Confirm Password'}
                      </Label>
                      <div className="relative">
                        <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="confirm"
                          type={showConfirm ? 'text' : 'password'}
                          placeholder={isRTL ? 'أعد كتابة كلمة المرور' : 'Re-enter password'}
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${confirmPassword && confirmPassword !== password ? 'border-destructive' : ''}`}
                          disabled={loading}
                        />
                        <button
                          type="button"
                          onClick={() => setShowConfirm(!showConfirm)}
                          className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        >
                          {showConfirm ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                      </div>
                      {confirmPassword && confirmPassword !== password && (
                        <p className="text-destructive text-xs font-tajawal animate-fade-in">
                          {isRTL ? 'كلمتا المرور غير متطابقتين' : 'Passwords do not match'}
                        </p>
                      )}
                    </div>

                    <Button
                      type="submit"
                      className="w-full h-12 rounded-xl bg-brand-navy hover:bg-brand-navy-light font-cairo text-base shadow-lg hover:shadow-xl transition-all active:scale-[0.98]"
                      disabled={loading || !allValid}
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="h-5 w-5 animate-spin" />
                          {isRTL ? 'جارِ الحفظ...' : 'Saving...'}
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          {isRTL ? 'تعيين كلمة المرور' : 'Set Password'}
                          {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
                        </span>
                      )}
                    </Button>
                  </form>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
