import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import {
  Mail,
  ArrowRight,
  ArrowLeft,
  Globe,
  Home,
  Loader2,
  CheckCircle2,
  KeyRound,
} from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';
const BG_PATTERN = '/nassaq-pattern.png';
const HAKIM_CHARACTER = '/hakim-poses/explaining-concept.png';

export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const { isRTL, toggleLanguage } = useTheme();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) {
      setError(isRTL ? 'يرجى إدخال البريد الإلكتروني' : 'Please enter your email');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/auth/forgot-password`, { email: email.trim() });
      setSent(true);
    } catch {
      setSent(true);
    } finally {
      setLoading(false);
    }
  };

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
          <h2 className="font-cairo text-4xl font-bold text-white mb-4">{isRTL ? 'نسّاق' : 'NASSAQ'}</h2>
          <p className="text-2xl text-brand-turquoise font-cairo font-semibold mb-8">
            {isRTL ? 'من البيانات إلى القرارات' : 'From Data to Decisions'}
          </p>
          <div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm border border-white/20 rounded-2xl p-4 max-w-sm mx-auto">
            <img src={HAKIM_CHARACTER} alt="حكيم" className="w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
            <div className="text-start flex-1">
              <p className="text-white/80 text-sm font-tajawal leading-snug">
                {isRTL ? 'لا تقلق! سنساعدك في استعادة حسابك بسهولة.' : "Don't worry! We'll help you recover your account easily."}
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
              <div className="lg:hidden flex items-center justify-center gap-3 mb-4">
                <img src={HAKIM_CHARACTER} alt="حكيم" className="w-16 h-16 rounded-2xl object-contain border-2 border-brand-turquoise bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
                <img src={LOGO_WHITE} alt="نَسَّق" className="h-10 rounded-xl bg-brand-navy p-1.5" />
              </div>

              <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-brand-turquoise/10 flex items-center justify-center">
                <KeyRound className="h-8 w-8 text-brand-turquoise" />
              </div>

              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'نسيت كلمة المرور؟' : 'Forgot Password?'}
              </h1>
              <p className="text-muted-foreground font-tajawal text-sm mt-2">
                {isRTL
                  ? 'أدخل بريدك الإلكتروني وسنرسل لك رابط إعادة تعيين كلمة المرور'
                  : "Enter your email and we'll send you a password reset link"}
              </p>
            </CardHeader>

            <CardContent className="pt-4">
              {sent ? (
                <div className="text-center space-y-4 py-4">
                  <div className="mx-auto w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                    <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
                  </div>
                  <h3 className="font-cairo text-lg font-semibold text-foreground">
                    {isRTL ? 'تم إرسال الرابط!' : 'Link Sent!'}
                  </h3>
                  <p className="text-muted-foreground font-tajawal text-sm leading-relaxed">
                    {isRTL
                      ? 'إذا كان هذا البريد مسجلاً لدينا، ستصلك رسالة تحتوي على رابط إعادة تعيين كلمة المرور. يرجى التحقق من صندوق الوارد والبريد غير المرغوب فيه.'
                      : 'If this email is registered, you will receive a password reset link. Please check your inbox and spam folder.'}
                  </p>
                  <div className="pt-4">
                    <Button asChild variant="outline" className="rounded-xl">
                      <Link to="/login" className="flex items-center gap-2 font-tajawal">
                        {isRTL ? <ArrowRight className="h-4 w-4" /> : <ArrowLeft className="h-4 w-4" />}
                        {isRTL ? 'العودة لتسجيل الدخول' : 'Back to Login'}
                      </Link>
                    </Button>
                  </div>
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
                          onChange={(e) => setEmail(e.target.value)}
                          className="ps-10 h-12 rounded-xl font-tajawal"
                          disabled={loading}
                          autoFocus
                        />
                      </div>
                    </div>

                    <Button
                      type="submit"
                      className="w-full h-12 rounded-xl bg-brand-navy hover:bg-brand-navy-light font-cairo text-base shadow-lg hover:shadow-xl transition-all active:scale-[0.98]"
                      disabled={loading}
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="h-5 w-5 animate-spin" />
                          {isRTL ? 'جارِ الإرسال...' : 'Sending...'}
                        </span>
                      ) : (
                        <span className="flex items-center gap-2">
                          {isRTL ? 'إرسال رابط الاستعادة' : 'Send Reset Link'}
                          {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
                        </span>
                      )}
                    </Button>
                  </form>

                  <div className="mt-6 text-center">
                    <Link to="/login" className="text-sm text-brand-turquoise hover:underline font-tajawal">
                      {isRTL ? 'العودة لتسجيل الدخول' : 'Back to Login'}
                    </Link>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
