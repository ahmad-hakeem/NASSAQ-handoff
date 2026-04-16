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
  CheckCircle2,
  Shield,
  Mail,
  MapPin,
  FileText,
  Eye,
  AlertTriangle,
  Edit3,
} from 'lucide-react';

const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';
const BG_PATTERN = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/1itjy61q_Nassaq%20Background.png';

export const RegisterPage = () => {
  const { t } = useTranslation();
  const { isRTL, toggleLanguage } = useTheme();
  const { api } = useAuth();
  const navigate = useNavigate();
  
  const [currentStep, setCurrentStep] = useState(1);
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const totalSteps = 5;
  
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
  });
  
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [similarSchools, setSimilarSchools] = useState([]);
  const [checkingSchoolName, setCheckingSchoolName] = useState(false);

  const updateFormData = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const checkSchoolName = useCallback(async (name) => {
    if (!name || name.trim().length < 3) {
      setSimilarSchools([]);
      return;
    }
    setCheckingSchoolName(true);
    try {
      const res = await api.get(`/registration-requests/check-school-name?name=${encodeURIComponent(name.trim())}`);
      setSimilarSchools(res.data?.similar_schools || []);
    } catch (e) {
      console.error('Error checking school name:', e);
      setSimilarSchools([]);
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
    } else if (formData.accountType === 'teacher') {
      if (!formData.teacher_email.trim()) {
        newErrors.teacher_email = t('emailIsRequired');
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.teacher_email)) {
        newErrors.teacher_email = t('invalidEmailFormat2');
      }
      if (!formData.specialization.trim()) {
        newErrors.specialization = t('specializationIsRequired');
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
          navigate('/teacher-register', { replace: true });
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
    setLoading(true);

    try {
      const requestData = {
        full_name: formData.full_name,
        phone: formData.phone,
        account_type: formData.accountType,
        status: 'pending',
        ...(formData.accountType === 'school' ? {
          school_name: formData.school_name,
          school_email: formData.school_email,
          school_phone: formData.school_phone,
          school_city: formData.school_city,
          school_address: formData.school_address,
          student_capacity: formData.student_capacity,
        } : {
          email: formData.teacher_email,
          school_code: formData.school_code,
          specialization: formData.specialization,
          years_of_experience: formData.years_of_experience,
        }),
      };

      const response = await api.post('/registration-requests', requestData);
      
      navigate('/registration-confirmation', { 
        state: { 
          requestId: response.data?.id,
          fullName: formData.full_name,
          accountType: formData.accountType,
          email: formData.accountType === 'school' ? formData.school_email : formData.teacher_email,
          phone: formData.phone,
          schoolName: formData.school_name,
        },
        replace: true
      });
    } catch (err) {
      console.error('Registration error:', err);
      const detail = err.response?.data?.detail;
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
    { number: 5, title: t('reviewSubmit'), icon: Eye },
  ];

  const getReviewData = () => {
    const common = [
      { label: t('fullName'), value: formData.full_name },
      { label: t('phone3'), value: formData.phone },
      { label: t('accountType'), value: formData.accountType === 'school' ? (t('newSchool')) : (t('teacher3')) },
    ];

    if (formData.accountType === 'school') {
      return [
        ...common,
        { label: t('schoolName'), value: formData.school_name },
        { label: t('email2'), value: formData.school_email },
        { label: t('city'), value: formData.school_city },
        ...(formData.school_phone ? [{ label: t('schoolPhone'), value: formData.school_phone }] : []),
        ...(formData.student_capacity ? [{ label: isRTL ? 'سعة الطلاب' : 'Capacity', value: formData.student_capacity }] : []),
      ];
    } else {
      return [
        ...common,
        { label: t('email2'), value: formData.teacher_email },
        { label: t('specialization'), value: formData.specialization },
        ...(formData.school_code ? [{ label: t('schoolCode'), value: formData.school_code }] : []),
        ...(formData.years_of_experience ? [{ label: t('experience'), value: formData.years_of_experience }] : []),
      ];
    }
  };

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
                        {similarSchools.length > 0 && (
                          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mt-2">
                            <div className="flex items-center gap-2 mb-2">
                              <AlertTriangle className="h-4 w-4 text-amber-600" />
                              <span className="text-sm font-bold text-amber-700 font-tajawal">
                                {t('similarSchoolsFound')}
                              </span>
                            </div>
                            <ul className="space-y-1">
                              {similarSchools.map((s, i) => (
                                <li key={i} className="text-sm text-amber-700 font-tajawal flex items-center gap-2">
                                  <span>{s.name}</span>
                                  {s.city && <span className="text-amber-500">({s.city})</span>}
                                  <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600">
                                    {s.source === 'registered' ? (t('registered')) : (t('pending4'))}
                                  </Badge>
                                </li>
                              ))}
                            </ul>
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

                  <div className="bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-xl p-4 mt-4">
                    <p className="text-sm text-foreground font-tajawal">
                      <span className="font-bold">{t('note2')}</span>
                      {t('yourRequestWillBeReviewedByPlatformAdminAndYouWill')}
                    </p>
                  </div>
                </div>
              )}

              {currentStep === 5 && (
                <div className="space-y-5" data-testid="step-5-content">
                  <div className="bg-brand-navy/5 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-cairo font-bold text-lg text-foreground">
                        {t('requestSummary')}
                      </h3>
                      <Badge className="bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/20">
                        {t('review')}
                      </Badge>
                    </div>

                    <div className="space-y-3">
                      {getReviewData().map((item, index) => (
                        <div key={index} className="flex items-center justify-between py-2 border-b border-border/30 last:border-0">
                          <span className="text-sm text-muted-foreground font-tajawal">{item.label}</span>
                          <span className="text-sm font-medium font-tajawal text-foreground max-w-[60%] text-end" dir="auto">
                            {item.value || '—'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentStep(1)}
                      className="rounded-xl font-tajawal text-xs"
                    >
                      <Edit3 className="h-3.5 w-3.5 me-1" />
                      {t('editInfo')}
                    </Button>
                  </div>

                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
                      <p className="text-sm text-amber-700 font-tajawal leading-relaxed">
                        {t('byClickingSubmitRequestIConfirmTheAccuracyOfTheEnt')}
                      </p>
                    </div>
                  </div>
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
                        {t('submitting')}
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        {t('submitRequest')}
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
