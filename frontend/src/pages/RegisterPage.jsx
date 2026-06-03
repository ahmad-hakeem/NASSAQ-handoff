import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { Checkbox } from '../components/ui/checkbox';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '../utils/apiError';
import { 
  User, 
  Phone, 
  ArrowLeft, 
  ArrowRight, 
  Globe,
  Home,
  Loader2,
  Building2,
  UserCheck,
  GraduationCap,
  CheckCircle2,
  Shield,
  Mail,
  MapPin,
  FileText,
  AlertTriangle,
  Lock,
  Eye,
  EyeOff,
} from 'lucide-react';

const LOGO_WHITE = '/nassaq-logo-white.png';
const BG_PATTERN = '/nassaq-background.png';

export const RegisterPage = () => {
  const { t } = useTranslation();
  const { isRTL, toggleLanguage } = useTheme();
  const { api, applyAuthSession } = useAuth();
  const navigate = useNavigate();
  
  const [currentStep, setCurrentStep] = useState(1);
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const totalSteps = 4;
  
  const [formData, setFormData] = useState({
    full_name: '',
    phone: '',
    acceptPrivacy: false,
    accountType: '',
    school_name: '',
    school_email: '',
    school_phone: '',
    school_city: '',
    school_address: '',
    student_capacity: '',
    teacher_email: '',
    school_code: '',
    specialization: '',
    years_of_experience: '',
    password: '',
    confirm_password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [schoolNameDuplicate, setSchoolNameDuplicate] = useState(false);
  const [checkingSchoolName, setCheckingSchoolName] = useState(false);

  const updateFormData = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const checkSchoolName = useCallback(async (name) => {
    if (!name || name.trim().length < 3) {
      setSchoolNameDuplicate(false);
      return;
    }
    setCheckingSchoolName(true);
    try {
      const res = await api.get(`/registration-requests/check-school-name?name=${encodeURIComponent(name.trim())}`);
      setSchoolNameDuplicate(res.data?.is_duplicate || false);
    } catch (e) {
      setSchoolNameDuplicate(false);
    } finally {
      setCheckingSchoolName(false);
    }
  }, [api]);

  useEffect(() => {
    if (formData.accountType === 'school' && formData.school_name.length >= 3) {
      const timer = setTimeout(() => checkSchoolName(formData.school_name), 600);
      return () => clearTimeout(timer);
    }
  }, [formData.school_name, formData.accountType, checkSchoolName]);

  const validateStep1 = () => {
    const newErrors = {};
    if (!formData.full_name.trim()) {
      newErrors.full_name = t('fullNameIsRequired');
    }
    if (!formData.phone.trim()) {
      newErrors.phone = t('phoneNumberIsRequired');
    } else if (!/^[0-9+\-\s]{9,15}$/.test(formData.phone)) {
      newErrors.phone = t('invalidPhoneNumber');
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = () => {
    const newErrors = {};
    if (!formData.acceptPrivacy) {
      newErrors.acceptPrivacy = t('youMustAcceptThePrivacyPolicy');
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep3 = () => {
    const newErrors = {};
    if (!formData.accountType) {
      newErrors.accountType = t('pleaseSelectAccountType');
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep4 = () => {
    const newErrors = {};
    
    if (formData.accountType === 'school') {
      if (!formData.school_name.trim()) {
        newErrors.school_name = t('schoolNameIsRequired');
      }
      if (!formData.school_email.trim()) {
        newErrors.school_email = t('schoolEmailIsRequired');
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.school_email)) {
        newErrors.school_email = t('invalidEmailFormat2');
      }
      if (!formData.school_city.trim()) {
        newErrors.school_city = t('cityIsRequired');
      }
      if (!formData.password) {
        newErrors.password = isRTL ? 'كلمة المرور مطلوبة' : 'Password is required';
      } else if (formData.password.length < 8) {
        newErrors.password = isRTL ? 'يجب أن تتكون كلمة المرور من 8 أحرف على الأقل' : 'Password must be at least 8 characters';
      }
      if (!formData.confirm_password) {
        newErrors.confirm_password = isRTL ? 'يرجى تأكيد كلمة المرور' : 'Please confirm password';
      } else if (formData.password !== formData.confirm_password) {
        newErrors.confirm_password = isRTL ? 'كلمتا المرور غير متطابقتين' : 'Passwords do not match';
      }
    } else if (formData.accountType === 'teacher') {
      if (!formData.teacher_email.trim()) {
        newErrors.teacher_email = t('emailIsRequired');
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.teacher_email)) {
        newErrors.teacher_email = t('invalidEmailFormat2');
      }
      if (!formData.specialization.trim()) {
        newErrors.specialization = t('specializationIsRequired');
      }
    } else if (formData.accountType === 'independent_teacher') {
      if (!formData.teacher_email.trim()) {
        newErrors.teacher_email = t('emailIsRequired');
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.teacher_email)) {
        newErrors.teacher_email = t('invalidEmailFormat2');
      }
      if (!formData.password) {
        newErrors.password = isRTL ? 'كلمة المرور مطلوبة' : 'Password is required';
      } else if (formData.password.length < 8) {
        newErrors.password = isRTL ? 'يجب أن تتكون كلمة المرور من 8 أحرف على الأقل' : 'Password must be at least 8 characters';
      }
      if (!formData.confirm_password) {
        newErrors.confirm_password = isRTL ? 'يرجى تأكيد كلمة المرور' : 'Please confirm password';
      } else if (formData.password !== formData.confirm_password) {
        newErrors.confirm_password = isRTL ? 'كلمتا المرور غير متطابقتين' : 'Passwords do not match';
      }
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    let isValid = false;
    
    switch (currentStep) {
      case 1:
        isValid = validateStep1();
        break;
      case 2:
        isValid = validateStep2();
        break;
      case 3:
        isValid = validateStep3();
        if (isValid && formData.accountType === 'teacher') {
          // School-teacher join flow lives on a separate page; IT stays
          // on this wizard and continues to step 4.
          navigate('/teacher-register', {
            replace: true,
            state: {
              prefill: {
                full_name: formData.full_name,
                phone: formData.phone,
              },
              acceptedPrivacy: true,
            },
          });
          return;
        }
        break;
      case 4:
        isValid = validateStep4();
        break;
      default:
        isValid = true;
    }
    
    if (isValid && currentStep < totalSteps) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const goToStep = (step) => {
    if (step < currentStep) {
      setCurrentStep(step);
    }
  };

  const handleSubmit = async () => {
    if (!validateStep4()) return;
    setLoading(true);

    try {
      const requestData = {
        full_name: formData.full_name,
        phone: formData.phone,
        account_type: formData.accountType,
        ...(formData.accountType === 'school' ? {
          school_name: formData.school_name,
          school_email: formData.school_email,
          school_phone: formData.school_phone,
          school_city: formData.school_city,
          school_address: formData.school_address,
          student_capacity: formData.student_capacity,
          password: formData.password,
        } : formData.accountType === 'independent_teacher' ? {
          email: formData.teacher_email,
          specialization: formData.specialization,
          years_of_experience: formData.years_of_experience,
          password: formData.password,
        } : {
          email: formData.teacher_email,
          school_code: formData.school_code,
          specialization: formData.specialization,
          years_of_experience: formData.years_of_experience,
        }),
      };

      const response = await api.post('/registration-requests', requestData);
      const data = response.data || {};

      if (data.access_token && data.user) {
        applyAuthSession({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          user: data.user,
        });

        if (formData.accountType === 'school') {
          toast.success(isRTL ? 'تم تسجيل المدرسة بنجاح' : 'School registered successfully');
        } else {
          toast.success(t('accountCreatedSuccessfully'));
        }

        const role = data.user.role;
        let target = '/dashboard';
        switch (role) {
          case 'school_principal':
          case 'school_admin':
            target = '/principal';
            break;
          case 'school_sub_admin':
            target = '/school';
            break;
          case 'independent_teacher':
            // Spec §5.1 first-login orchestration:
            //   signup → MFA enrolment → recent assertion → wizard → bootstrap.
            // The bootstrap endpoint hard-requires `users.mfa_enrolled_at`, so
            // a brand-new IT signup MUST land on the MFA enrolment page first;
            // otherwise the wizard submit returns 403 mfa_enrollment_required
            // and bounces the user with the "إعداد عامل تحقق ثانوي" dialog.
            // Mirrors LoginPage.resolveRedirectTarget().
            if (!data.user.mfa_enrolled_at) {
              target = '/auth/mfa/enroll';
            } else if (!data.user.tenant_id) {
              target = '/teacher/onboarding';
            } else {
              target = '/teacher';
            }
            break;
          case 'teacher':
            target = '/teacher';
            break;
          case 'platform_admin':
          case 'platform_operations_manager':
            target = '/admin';
            break;
          default:
            target = '/dashboard';
        }
        navigate(target, { replace: true });
        return;
      }

      navigate('/registration-confirmation', {
        state: {
          requestId: data.id,
          fullName: formData.full_name,
          accountType: formData.accountType,
          email: formData.accountType === 'school' ? formData.school_email : formData.teacher_email,
          phone: formData.phone,
          schoolName: formData.school_name,
        },
        replace: true,
      });
    } catch (err) {
      console.error('Registration error:', err);
      const detail = getApiErrorMessage(err);
      if (detail) {
        nassaqError(detail);
      } else {
        nassaqError(
          t('anErrorOccurredWhileSubmittingTheRegistrationReque')
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { number: 1, title: isRTL ? 'البيانات الأساسية' : 'Basic Info', icon: User },
    { number: 2, title: t('privacyPolicy'), icon: Shield },
    { number: 3, title: t('accountType'), icon: Building2 },
    { number: 4, title: t('completeInfo'), icon: FileText },
  ];

  return (
    <div className="min-h-screen flex" dir={isRTL ? 'rtl' : 'ltr'} data-testid="register-page">
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
            data-testid="register-logo"
          />
          
          <h2 className="font-cairo text-4xl font-bold text-white mb-4">
            {t('nassaq')}
          </h2>
          <p className="text-2xl text-brand-turquoise font-cairo font-semibold mb-8">
            {t('fromDataToDecisions')}
          </p>
          
          <p className="text-white/60 font-tajawal mt-6">
            {t('joinNassaqPlatformAndStartYourSmartManagementJourn')
            }
          </p>
        </div>
      </div>

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

        <div className="flex-1 flex flex-col justify-center items-center p-6 lg:p-12 overflow-y-auto">
          <Link to="/" className="lg:hidden mb-6">
            <img
              src={LOGO_WHITE}
              alt="نَسَّق"
              className="h-12 w-auto"
            />
          </Link>

          <div className="w-full max-w-lg mb-8">
            <div className="flex items-center justify-between">
              {steps.map((step, index) => (
                <div key={step.number} className="flex items-center">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center transition-all cursor-pointer ${
                        currentStep >= step.number
                          ? 'bg-brand-turquoise text-white'
                          : 'bg-muted text-muted-foreground'
                      }`}
                      onClick={() => goToStep(step.number)}
                      data-testid={`step-indicator-${step.number}`}
                    >
                      {currentStep > step.number ? (
                        <CheckCircle2 className="h-5 w-5" />
                      ) : (
                        <step.icon className="h-5 w-5" />
                      )}
                    </div>
                    <span className={`text-xs mt-2 font-tajawal text-center max-w-[60px] ${
                      currentStep >= step.number ? 'text-foreground' : 'text-muted-foreground'
                    }`}>
                      {step.title}
                    </span>
                  </div>
                  {index < steps.length - 1 && (
                    <div
                      className={`h-0.5 w-8 mx-1 transition-all ${
                        currentStep > step.number ? 'bg-brand-turquoise' : 'bg-muted'
                      }`}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          <Card className="w-full max-w-lg card-nassaq" data-testid="register-card">
            <CardHeader className="text-center pb-2">
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'تسجيل جديد' : 'Create Account'}
              </h1>
              <p className="text-muted-foreground font-tajawal text-sm">
                {steps[currentStep - 1].title}
              </p>
            </CardHeader>
            
            <CardContent className="pt-4">
              {currentStep === 1 && (
                <div className="space-y-5" data-testid="step-1-content">
                  <div className="space-y-2">
                    <Label htmlFor="full_name" className="font-tajawal">
                      {t('fullName')} *
                    </Label>
                    <div className="relative">
                      <User className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                      <Input
                        id="full_name"
                        placeholder={t('enterYourFullName')}
                        value={formData.full_name}
                        onChange={(e) => updateFormData('full_name', e.target.value)}
                        className={`ps-10 h-12 rounded-xl font-tajawal ${errors.full_name ? 'border-destructive' : ''}`}
                        data-testid="full-name-input"
                      />
                    </div>
                    {errors.full_name && (
                      <p className="text-destructive text-xs font-tajawal">{errors.full_name}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone" className="font-tajawal">
                      {isRTL ? 'رقم الهاتف' : 'Phone Number'} *
                    </Label>
                    <div className="relative">
                      <Phone className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                      <Input
                        id="phone"
                        type="tel"
                        placeholder={isRTL ? '+966 5X XXX XXXX' : '+966 5X XXX XXXX'}
                        value={formData.phone}
                        onChange={(e) => updateFormData('phone', e.target.value)}
                        className={`ps-10 h-12 rounded-xl font-tajawal ${errors.phone ? 'border-destructive' : ''}`}
                        dir="ltr"
                        data-testid="phone-input"
                      />
                    </div>
                    {errors.phone && (
                      <p className="text-destructive text-xs font-tajawal">{errors.phone}</p>
                    )}
                  </div>
                </div>
              )}

              {currentStep === 2 && (
                <div className="space-y-5" data-testid="step-2-content">
                  <div className="bg-muted/50 rounded-xl p-4 max-h-64 overflow-y-auto custom-scrollbar">
                    <h3 className="font-cairo font-bold text-foreground mb-3">
                      {t('privacyPolicyTermsOfUse')}
                    </h3>
                    <div className="text-sm text-muted-foreground font-tajawal leading-relaxed space-y-3">
                      <p>
                        {t('welcomeToNassaqSchoolManagementPlatformByUsingThis')}
                      </p>
                      <p>
                        {t('1DataCollectionWeCollectNecessaryDataToProvideOurS')}
                      </p>
                      <p>
                        {t('2DataUsageCollectedDataIsUsedOnlyForImprovingEduca')}
                      </p>
                      <p>
                        {t('3DataProtectionWeCommitToProtectingYourDataAccordi')}
                      </p>
                      <p>
                        {t('4DataSharingWeWillNotShareYourDataWithThirdParties')}
                      </p>
                      <p>
                        {t('5UserRightsYouHaveTheRightToAccessModifyOrDeleteYo')}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-3">
                    <Checkbox
                      id="acceptPrivacy"
                      checked={formData.acceptPrivacy}
                      onCheckedChange={(checked) => updateFormData('acceptPrivacy', checked)}
                      className="rounded mt-1"
                      data-testid="privacy-checkbox"
                    />
                    <Label htmlFor="acceptPrivacy" className="font-tajawal text-sm cursor-pointer leading-relaxed">
                      {t('iAgreeToThePrivacyPolicyAndTermsOfUse')}
                      {' — '}
                      <a
                        href="/privacy"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-turquoise hover:underline font-cairo"
                        data-testid="link-open-privacy-policy"
                      >
                        {t('privacyPolicy')}
                      </a>
                      {' · '}
                      <a
                        href="/terms"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-turquoise hover:underline font-cairo"
                        data-testid="link-open-terms"
                      >
                        {t('termsOfService') || 'الشروط والأحكام'}
                      </a>
                    </Label>
                  </div>
                  {errors.acceptPrivacy && (
                    <p className="text-destructive text-xs font-tajawal">{errors.acceptPrivacy}</p>
                  )}
                </div>
              )}

              {currentStep === 3 && (
                <div className="space-y-5" data-testid="step-3-content">
                  <p className="text-muted-foreground font-tajawal text-center mb-6">
                    {t('selectTheAccountTypeThatSuitsYou')}
                  </p>

                  <RadioGroup
                    value={formData.accountType}
                    onValueChange={(value) => updateFormData('accountType', value)}
                    className="space-y-4"
                  >
                    <div
                      className={`relative flex items-start gap-4 p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                        formData.accountType === 'school'
                          ? 'border-brand-turquoise bg-brand-turquoise/5'
                          : 'border-border hover:border-brand-turquoise/50'
                      }`}
                      onClick={() => updateFormData('accountType', 'school')}
                      data-testid="account-type-school"
                    >
                      <RadioGroupItem value="school" id="school" className="mt-1" />
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                            <Building2 className="h-5 w-5 text-brand-navy" />
                          </div>
                          <Label htmlFor="school" className="font-cairo font-bold text-lg cursor-pointer">
                            {t('newSchool')}
                          </Label>
                        </div>
                        <p className="text-muted-foreground text-sm font-tajawal">
                          {t('registerANewSchoolOnNassaqPlatformToStartManagingE')}
                        </p>
                      </div>
                    </div>

                    <div
                      className={`relative flex items-start gap-4 p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                        formData.accountType === 'teacher'
                          ? 'border-brand-turquoise bg-brand-turquoise/5'
                          : 'border-border hover:border-brand-turquoise/50'
                      }`}
                      onClick={() => updateFormData('accountType', 'teacher')}
                      data-testid="account-type-teacher"
                    >
                      <RadioGroupItem value="teacher" id="teacher" className="mt-1" />
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-10 h-10 rounded-xl bg-brand-purple/10 flex items-center justify-center">
                            <UserCheck className="h-5 w-5 text-brand-purple" />
                          </div>
                          <Label htmlFor="teacher" className="font-cairo font-bold text-lg cursor-pointer">
                            {t('teacher3')}
                          </Label>
                        </div>
                        <p className="text-muted-foreground text-sm font-tajawal">
                          {t('registerAsATeacherToJoinAnExistingSchoolOnThePlatf')}
                        </p>
                      </div>
                    </div>

                    <div
                      className={`relative flex items-start gap-4 p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                        formData.accountType === 'independent_teacher'
                          ? 'border-brand-turquoise bg-brand-turquoise/5'
                          : 'border-border hover:border-brand-turquoise/50'
                      }`}
                      onClick={() => updateFormData('accountType', 'independent_teacher')}
                      data-testid="account-type-independent-teacher"
                    >
                      <RadioGroupItem value="independent_teacher" id="independent_teacher" className="mt-1" />
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center">
                            <GraduationCap className="h-5 w-5 text-brand-turquoise" />
                          </div>
                          <Label htmlFor="independent_teacher" className="font-cairo font-bold text-lg cursor-pointer">
                            {t('itRoleBadgeLabel')}
                          </Label>
                        </div>
                        <p className="text-muted-foreground text-sm font-tajawal">
                          {t('independentTeacherCardDescription')}
                        </p>
                      </div>
                    </div>
                  </RadioGroup>

                  {errors.accountType && (
                    <p className="text-destructive text-xs font-tajawal text-center">{errors.accountType}</p>
                  )}
                </div>
              )}

              {currentStep === 4 && (
                <div className="space-y-5" data-testid="step-4-content">
                  {formData.accountType === 'school' && (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="school_name" className="font-tajawal">
                          {t('schoolName')} *
                        </Label>
                        <div className="relative">
                          <Building2 className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="school_name"
                            placeholder={t('enterSchoolName')}
                            value={formData.school_name}
                            onChange={(e) => updateFormData('school_name', e.target.value)}
                            className={`ps-10 h-12 rounded-xl font-tajawal ${errors.school_name ? 'border-destructive' : ''}`}
                            data-testid="school-name-input"
                          />
                          {checkingSchoolName && (
                            <Loader2 className="absolute end-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
                          )}
                        </div>
                        {errors.school_name && (
                          <p className="text-destructive text-xs font-tajawal">{errors.school_name}</p>
                        )}
                        {schoolNameDuplicate && (
                          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mt-2">
                            <div className="flex items-center gap-2">
                              <AlertTriangle className="h-4 w-4 text-amber-600" />
                              <span className="text-sm font-bold text-amber-700 font-tajawal">
                                {t('schoolNameAlreadyExists')}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="school_email" className="font-tajawal">
                          {t('schoolEmail')} *
                        </Label>
                        <div className="relative">
                          <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="school_email"
                            type="email"
                            placeholder="school@example.com"
                            value={formData.school_email}
                            onChange={(e) => updateFormData('school_email', e.target.value)}
                            className={`ps-10 h-12 rounded-xl font-tajawal ${errors.school_email ? 'border-destructive' : ''}`}
                            dir="ltr"
                            data-testid="school-email-input"
                          />
                        </div>
                        {errors.school_email && (
                          <p className="text-destructive text-xs font-tajawal">{errors.school_email}</p>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="school_city" className="font-tajawal">
                            {t('city')} *
                          </Label>
                          <div className="relative">
                            <MapPin className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                            <Input
                              id="school_city"
                              placeholder={t('riyadh')}
                              value={formData.school_city}
                              onChange={(e) => updateFormData('school_city', e.target.value)}
                              className={`ps-10 h-12 rounded-xl font-tajawal ${errors.school_city ? 'border-destructive' : ''}`}
                              data-testid="school-city-input"
                            />
                          </div>
                          {errors.school_city && (
                            <p className="text-destructive text-xs font-tajawal">{errors.school_city}</p>
                          )}
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="student_capacity" className="font-tajawal">
                            {t('studentCapacity')}
                          </Label>
                          <Input
                            id="student_capacity"
                            type="number"
                            placeholder="500"
                            value={formData.student_capacity}
                            onChange={(e) => updateFormData('student_capacity', e.target.value)}
                            className="h-12 rounded-xl font-tajawal"
                            data-testid="student-capacity-input"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="password" className="font-tajawal">
                          {isRTL ? 'كلمة المرور' : 'Password'} *
                        </Label>
                        <div className="relative">
                          <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="password"
                            type={showPassword ? 'text' : 'password'}
                            placeholder={isRTL ? '٨ أحرف على الأقل' : 'At least 8 characters'}
                            value={formData.password}
                            onChange={(e) => updateFormData('password', e.target.value)}
                            className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${errors.password ? 'border-destructive' : ''}`}
                            autoComplete="new-password"
                            data-testid="password-input"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            aria-label="toggle password visibility"
                            data-testid="toggle-password-btn"
                          >
                            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                          </button>
                        </div>
                        {formData.password && (() => {
                          const pwd = formData.password;
                          let score = 0;
                          if (pwd.length >= 8) score++;
                          if (pwd.length >= 12) score++;
                          if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score++;
                          if (/\d/.test(pwd)) score++;
                          if (/[^A-Za-z0-9]/.test(pwd)) score++;
                          const level = score <= 1 ? 'weak' : score <= 3 ? 'medium' : 'strong';
                          const labels = {
                            weak: isRTL ? 'ضعيفة' : 'Weak',
                            medium: isRTL ? 'متوسطة' : 'Medium',
                            strong: isRTL ? 'قوية' : 'Strong',
                          };
                          const colors = {
                            weak: 'bg-destructive',
                            medium: 'bg-amber-500',
                            strong: 'bg-emerald-500',
                          };
                          const widths = { weak: 'w-1/3', medium: 'w-2/3', strong: 'w-full' };
                          const textColors = {
                            weak: 'text-destructive',
                            medium: 'text-amber-600',
                            strong: 'text-emerald-600',
                          };
                          return (
                            <div className="space-y-1" data-testid="password-strength">
                              <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                                <div
                                  className={`h-full ${colors[level]} ${widths[level]} transition-all duration-300`}
                                  data-testid="password-strength-bar"
                                />
                              </div>
                              <p
                                className={`text-xs font-tajawal ${textColors[level]}`}
                                data-testid="password-strength-label"
                              >
                                {isRTL ? `قوة كلمة المرور: ${labels[level]}` : `Password strength: ${labels[level]}`}
                              </p>
                            </div>
                          );
                        })()}
                        {errors.password && (
                          <p className="text-destructive text-xs font-tajawal">{errors.password}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="confirm_password" className="font-tajawal">
                          {isRTL ? 'تأكيد كلمة المرور' : 'Confirm Password'} *
                        </Label>
                        <div className="relative">
                          <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="confirm_password"
                            type={showConfirmPassword ? 'text' : 'password'}
                            placeholder={isRTL ? 'أعد إدخال كلمة المرور' : 'Re-enter password'}
                            value={formData.confirm_password}
                            onChange={(e) => updateFormData('confirm_password', e.target.value)}
                            className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${errors.confirm_password ? 'border-destructive' : ''}`}
                            autoComplete="new-password"
                            data-testid="confirm-password-input"
                          />
                          <button
                            type="button"
                            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                            className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            aria-label="toggle confirm password visibility"
                            data-testid="toggle-confirm-password-btn"
                          >
                            {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                          </button>
                        </div>
                        {errors.confirm_password && (
                          <p className="text-destructive text-xs font-tajawal">{errors.confirm_password}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="school_phone" className="font-tajawal">
                          {t('schoolPhoneOptional')}
                        </Label>
                        <div className="relative">
                          <Phone className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="school_phone"
                            type="tel"
                            placeholder="+966 XX XXX XXXX"
                            value={formData.school_phone}
                            onChange={(e) => updateFormData('school_phone', e.target.value)}
                            className="ps-10 h-12 rounded-xl font-tajawal"
                            dir="ltr"
                            data-testid="school-phone-input"
                          />
                        </div>
                      </div>
                    </>
                  )}

                  {formData.accountType === 'independent_teacher' && (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="teacher_email" className="font-tajawal">
                          {t('email2')} *
                        </Label>
                        <div className="relative">
                          <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="teacher_email"
                            type="email"
                            placeholder="teacher@example.com"
                            value={formData.teacher_email}
                            onChange={(e) => updateFormData('teacher_email', e.target.value)}
                            className={`ps-10 h-12 rounded-xl font-tajawal ${errors.teacher_email ? 'border-destructive' : ''}`}
                            dir="ltr"
                            data-testid="it-email-input"
                          />
                        </div>
                        {errors.teacher_email && (
                          <p className="text-destructive text-xs font-tajawal">{errors.teacher_email}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="it_specialization" className="font-tajawal">
                          {t('specialization')}
                        </Label>
                        <Input
                          id="it_specialization"
                          placeholder={t('egMathematicsArabic')}
                          value={formData.specialization}
                          onChange={(e) => updateFormData('specialization', e.target.value)}
                          className="h-12 rounded-xl font-tajawal"
                          data-testid="it-specialization-input"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="it_password" className="font-tajawal">
                          {isRTL ? 'كلمة المرور' : 'Password'} *
                        </Label>
                        <div className="relative">
                          <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="it_password"
                            type={showPassword ? 'text' : 'password'}
                            placeholder={isRTL ? '٨ أحرف على الأقل' : 'At least 8 characters'}
                            value={formData.password}
                            onChange={(e) => updateFormData('password', e.target.value)}
                            className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${errors.password ? 'border-destructive' : ''}`}
                            autoComplete="new-password"
                            data-testid="it-password-input"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            aria-label="toggle password visibility"
                            data-testid="it-toggle-password-btn"
                          >
                            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                          </button>
                        </div>
                        {errors.password && (
                          <p className="text-destructive text-xs font-tajawal">{errors.password}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="it_confirm_password" className="font-tajawal">
                          {isRTL ? 'تأكيد كلمة المرور' : 'Confirm Password'} *
                        </Label>
                        <div className="relative">
                          <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="it_confirm_password"
                            type={showConfirmPassword ? 'text' : 'password'}
                            placeholder={isRTL ? 'أعد إدخال كلمة المرور' : 'Re-enter password'}
                            value={formData.confirm_password}
                            onChange={(e) => updateFormData('confirm_password', e.target.value)}
                            className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${errors.confirm_password ? 'border-destructive' : ''}`}
                            autoComplete="new-password"
                            data-testid="it-confirm-password-input"
                          />
                          <button
                            type="button"
                            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                            className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            aria-label="toggle confirm password visibility"
                            data-testid="it-toggle-confirm-password-btn"
                          >
                            {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                          </button>
                        </div>
                        {errors.confirm_password && (
                          <p className="text-destructive text-xs font-tajawal">{errors.confirm_password}</p>
                        )}
                      </div>
                    </>
                  )}

                  {formData.accountType === 'teacher' && (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="teacher_email" className="font-tajawal">
                          {t('email2')} *
                        </Label>
                        <div className="relative">
                          <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                          <Input
                            id="teacher_email"
                            type="email"
                            placeholder="teacher@example.com"
                            value={formData.teacher_email}
                            onChange={(e) => updateFormData('teacher_email', e.target.value)}
                            className={`ps-10 h-12 rounded-xl font-tajawal ${errors.teacher_email ? 'border-destructive' : ''}`}
                            dir="ltr"
                            data-testid="teacher-email-input"
                          />
                        </div>
                        {errors.teacher_email && (
                          <p className="text-destructive text-xs font-tajawal">{errors.teacher_email}</p>
                        )}
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="specialization" className="font-tajawal">
                          {t('specialization')} *
                        </Label>
                        <Input
                          id="specialization"
                          placeholder={t('egMathematicsArabic')}
                          value={formData.specialization}
                          onChange={(e) => updateFormData('specialization', e.target.value)}
                          className={`h-12 rounded-xl font-tajawal ${errors.specialization ? 'border-destructive' : ''}`}
                          data-testid="specialization-input"
                        />
                        {errors.specialization && (
                          <p className="text-destructive text-xs font-tajawal">{errors.specialization}</p>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="school_code" className="font-tajawal">
                            {t('schoolCodeOptional')}
                          </Label>
                          <Input
                            id="school_code"
                            placeholder="SCH001"
                            value={formData.school_code}
                            onChange={(e) => updateFormData('school_code', e.target.value)}
                            className="h-12 rounded-xl font-tajawal"
                            dir="ltr"
                            data-testid="school-code-input"
                          />
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="years_of_experience" className="font-tajawal">
                            {isRTL ? 'سنوات الخبرة' : 'Years of Experience'}
                          </Label>
                          <Input
                            id="years_of_experience"
                            type="number"
                            placeholder="5"
                            value={formData.years_of_experience}
                            onChange={(e) => updateFormData('years_of_experience', e.target.value)}
                            className="h-12 rounded-xl font-tajawal"
                            data-testid="experience-input"
                          />
                        </div>
                      </div>
                    </>
                  )}

                </div>
              )}

              <div className="flex items-center justify-between mt-8 pt-4 border-t border-border/50">
                <Button
                  variant="outline"
                  onClick={handlePrevious}
                  disabled={currentStep === 1}
                  className="rounded-xl font-tajawal"
                  data-testid="prev-step-btn"
                >
                  <ArrowRight className="h-4 w-4 me-2" />
                  {isRTL ? 'السابق' : 'Previous'}
                </Button>

                {currentStep < totalSteps ? (
                  <Button
                    onClick={handleNext}
                    className="bg-brand-navy hover:bg-brand-navy-light rounded-xl font-tajawal"
                    data-testid="next-step-btn"
                  >
                    {t('next')}
                    <ArrowLeft className="h-4 w-4 ms-2" />
                  </Button>
                ) : (
                  <Button
                    onClick={handleSubmit}
                    disabled={loading}
                    className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl font-cairo"
                    data-testid="submit-btn"
                  >
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="h-5 w-5 animate-spin" />
                        {t('creatingAccount')}
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        {t('createAccount')}
                        <CheckCircle2 className="h-5 w-5" />
                      </span>
                    )}
                  </Button>
                )}
              </div>

              <div className="mt-6 text-center">
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('alreadyHaveAnAccount')}{' '}
                  <Link 
                    to="/login" 
                    className="text-brand-turquoise hover:underline font-medium"
                    data-testid="login-link"
                  >
                    {isRTL ? 'تسجيل الدخول' : 'Sign In'}
                  </Link>
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
