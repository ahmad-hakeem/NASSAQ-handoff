import { useLocation, Link, Navigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import {
  CheckCircle2,
  Clock,
  Mail,
  Phone,
  Building2,
  UserCheck,
  Home,
  Globe,
  ArrowLeft,
} from 'lucide-react';

const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';
const BG_PATTERN = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/1itjy61q_Nassaq%20Background.png';

export default function RegistrationConfirmationPage() {
  const { isRTL, toggleLanguage } = useTheme();
  const location = useLocation();
  const data = location.state;

  if (!data?.requestId) {
    return <Navigate to="/register" replace />;
  }

  const isSchool = data.accountType === 'school';

  return (
    <div className="min-h-screen flex" dir={isRTL ? 'rtl' : 'ltr'}>
      <div
        className="hidden lg:flex flex-1 flex-col justify-center items-center p-12 relative"
        style={{
          backgroundImage: `url(${BG_PATTERN})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-brand-navy/95" />
        <div className="relative z-10 text-center max-w-md">
          <img
            src={LOGO_WHITE}
            alt="نَسَّق"
            className="h-32 lg:h-40 w-auto mx-auto mb-8 rounded-3xl"
          />
          <h2 className="font-cairo text-4xl font-bold text-white mb-4">
            {isRTL ? 'نَسَّق' : 'NASSAQ'}
          </h2>
          <p className="text-2xl text-brand-turquoise font-cairo font-semibold">
            {isRTL ? 'من البيانات إلى القرار' : 'From Data to Decisions'}
          </p>
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-background">
        <div className="flex items-center justify-between p-4 border-b border-border/50">
          <Button
            variant="ghost"
            asChild
            className="text-muted-foreground hover:text-foreground rounded-xl"
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
          >
            <Globe className="h-5 w-5 me-2" />
            <span className="font-tajawal">{isRTL ? 'EN' : 'عربي'}</span>
          </Button>
        </div>

        <div className="flex-1 flex flex-col justify-center items-center p-6 lg:p-12">
          <Card className="w-full max-w-lg card-nassaq">
            <CardContent className="pt-8 pb-8 text-center">
              <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="h-10 w-10 text-green-600" />
              </div>

              <h1 className="font-cairo text-2xl font-bold text-foreground mb-3">
                {isRTL ? 'تم إرسال طلبك بنجاح!' : 'Request Submitted Successfully!'}
              </h1>

              <p className="text-muted-foreground font-tajawal mb-8 leading-relaxed max-w-sm mx-auto">
                {isRTL 
                  ? 'تم استلام طلب التسجيل وهو الآن قيد المراجعة من قبل إدارة المنصة. سيتم إشعارك بالنتيجة قريباً.'
                  : 'Your registration request has been received and is now under review by platform administration. You will be notified of the result soon.'}
              </p>

              <div className="bg-muted/50 rounded-2xl p-5 text-start space-y-3 mb-8">
                <h3 className="font-cairo font-bold text-sm text-foreground mb-3">
                  {isRTL ? 'تفاصيل الطلب' : 'Request Details'}
                </h3>

                <div className="flex items-center gap-3 text-sm">
                  <div className="w-8 h-8 rounded-lg bg-brand-navy/10 flex items-center justify-center shrink-0">
                    {isSchool ? <Building2 className="h-4 w-4 text-brand-navy" /> : <UserCheck className="h-4 w-4 text-brand-purple" />}
                  </div>
                  <div>
                    <span className="text-muted-foreground font-tajawal">{isRTL ? 'نوع الحساب' : 'Type'}: </span>
                    <span className="font-medium font-tajawal">{isSchool ? (isRTL ? 'مدرسة جديدة' : 'New School') : (isRTL ? 'معلم / معلمة' : 'Teacher')}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-sm">
                  <div className="w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center shrink-0">
                    <Mail className="h-4 w-4 text-brand-turquoise" />
                  </div>
                  <div>
                    <span className="text-muted-foreground font-tajawal">{isRTL ? 'الاسم' : 'Name'}: </span>
                    <span className="font-medium font-tajawal">{data.fullName}</span>
                  </div>
                </div>

                {data.email && (
                  <div className="flex items-center gap-3 text-sm">
                    <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                      <Mail className="h-4 w-4 text-blue-500" />
                    </div>
                    <div>
                      <span className="text-muted-foreground font-tajawal">{isRTL ? 'البريد' : 'Email'}: </span>
                      <span className="font-medium font-tajawal" dir="ltr">{data.email}</span>
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-3 text-sm">
                  <div className="w-8 h-8 rounded-lg bg-green-50 flex items-center justify-center shrink-0">
                    <Phone className="h-4 w-4 text-green-500" />
                  </div>
                  <div>
                    <span className="text-muted-foreground font-tajawal">{isRTL ? 'الهاتف' : 'Phone'}: </span>
                    <span className="font-medium font-tajawal" dir="ltr">{data.phone}</span>
                  </div>
                </div>

                {data.schoolName && (
                  <div className="flex items-center gap-3 text-sm">
                    <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center shrink-0">
                      <Building2 className="h-4 w-4 text-purple-500" />
                    </div>
                    <div>
                      <span className="text-muted-foreground font-tajawal">{isRTL ? 'المدرسة' : 'School'}: </span>
                      <span className="font-medium font-tajawal">{data.schoolName}</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-xl p-4 mb-8">
                <div className="flex items-center gap-2 justify-center mb-2">
                  <Clock className="h-4 w-4 text-brand-turquoise" />
                  <span className="text-sm font-bold text-brand-turquoise font-cairo">
                    {isRTL ? 'الخطوات القادمة' : 'Next Steps'}
                  </span>
                </div>
                <ul className="text-sm text-foreground font-tajawal space-y-2 text-start">
                  <li className="flex items-start gap-2">
                    <span className="text-brand-turquoise font-bold mt-0.5">1.</span>
                    <span>{isRTL ? 'سيقوم فريق نَسَّق بمراجعة طلبك خلال 24 ساعة' : 'NASSAQ team will review your request within 24 hours'}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-brand-turquoise font-bold mt-0.5">2.</span>
                    <span>{isRTL ? 'ستتلقى إشعاراً بالبريد الإلكتروني عند الموافقة' : 'You will receive an email notification upon approval'}</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-brand-turquoise font-bold mt-0.5">3.</span>
                    <span>{isRTL ? 'سيتم إرسال بيانات الدخول الخاصة بك' : 'Your login credentials will be sent to you'}</span>
                  </li>
                </ul>
              </div>

              <Button
                asChild
                className="bg-brand-navy hover:bg-brand-navy-light rounded-xl font-tajawal w-full h-12"
              >
                <Link to="/login" className="flex items-center justify-center gap-2">
                  <ArrowLeft className="h-4 w-4" />
                  {isRTL ? 'العودة لتسجيل الدخول' : 'Back to Login'}
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
