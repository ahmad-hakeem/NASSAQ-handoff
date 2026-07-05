import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader } from '../components/ui/card';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '../components/ui/select';
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
  CheckCircle2,
  Mail,
  MapPin,
  GraduationCap,
  BookOpen,
  Award,
  Clock,
  Copy,
  Search,
  Timer,
  AlertCircle,
  Sparkles,
  IdCard,
  Lock,
  Eye,
  EyeOff,
} from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
// Assets
const LOGO_WHITE = '/nassaq-logo-white.png';
const BG_PATTERN = '/nassaq-background.png';


export const TeacherSelfRegistration = () => {
  const { t } = useTranslation();
  const { isRTL, toggleLanguage } = useTheme();
  const { api, updateToken } = useAuth();
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [searchParams] = useSearchParams();
  const inviteCode = searchParams.get('invite');
  const location = useLocation();
  const prefill = location.state?.prefill || {};
  
  // Step management
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 5;
  
  // Dropdown options
  const [subjects, setSubjects] = useState([]);
  const [educationLevels, setEducationLevels] = useState([]);
  const [teacherRanks, setTeacherRanks] = useState([]);
  const [academicDegrees, setAcademicDegrees] = useState([]);
  const [schoolTypes, setSchoolTypes] = useState([]);
  
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Form data
  const [formData, setFormData] = useState({
    // Step 1: البيانات الأساسية
    full_name: prefill.full_name || '',
    national_id: '',
    phone: prefill.phone || '',
    email: '',
    password: '',
    confirm_password: '',
    
    // Step 2: المعلومات المهنية
    subject: '',
    education_level: '',
    years_of_experience: '',
    academic_degree: '',
    
    // Step 3: رتبة المعلم
    teacher_rank: '',
    
    // Step 4: بيانات المدرسة
    school_name: '',
    school_country: 'SA', // Default Saudi Arabia
    school_city: '',
    school_type: '',
    
    // Referral
    referred_by: inviteCode || '',
  });
  
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [inviteInfo, setInviteInfo] = useState(null);
  
  // Success state
  const [submissionResult, setSubmissionResult] = useState(null);
  
  // Tracking state
  const [trackingCode, setTrackingCode] = useState('');
  const [trackingResult, setTrackingResult] = useState(null);
  const [isTracking, setIsTracking] = useState(false);

  // Fetch dropdown options
  useEffect(() => {
    const fetchOptions = async () => {
      try {
        const [subjectsRes, levelsRes, ranksRes, degreesRes, typesRes] = await Promise.all([
          api.get('/teacher-registration/options/subjects'),
          api.get('/teacher-registration/options/education-levels'),
          api.get('/teacher-registration/options/teacher-ranks'),
          api.get('/teacher-registration/options/academic-degrees'),
          api.get('/teacher-registration/options/school-types'),
        ]);
        
        setSubjects(subjectsRes.data.subjects || []);
        setEducationLevels(levelsRes.data.levels || []);
        setTeacherRanks(ranksRes.data.ranks || []);
        setAcademicDegrees(degreesRes.data.degrees || []);
        setSchoolTypes(typesRes.data.types || []);
      } catch (error) {
        console.error('Error fetching options:', error);
      }
    };
    
    fetchOptions();
  }, []);
  
  // Fetch invite info if present
  useEffect(() => {
    const fetchInviteInfo = async () => {
      if (!inviteCode) return;
      
      try {
        const response = await api.get(`/teacher-registration/invite/${inviteCode}`);
        if (response.data.valid) {
          setInviteInfo(response.data);
          // Pre-fill some data
          setFormData(prev => ({
            ...prev,
            full_name: response.data.invitee_name || '',
            email: response.data.invitee_email || '',
            referred_by: inviteCode,
          }));
          toast.success(t('inviteRecognizedSuccessfully'));
        }
      } catch (error) {
        console.error('Invalid invite:', error);
        nassaqError(t('invalidInviteCode'));
      }
    };
    
    fetchInviteInfo();
  }, [inviteCode, isRTL]);

  // Update form data
  const updateFormData = (field, value) => {
    const nextValue = field === 'email' && typeof value === 'string'
      ? value.toLowerCase()
      : value;
    setFormData(prev => ({ ...prev, [field]: nextValue }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  // Validation functions
  const validateStep1 = () => {
    const newErrors = {};
    
    if (!formData.full_name.trim()) {
      newErrors.full_name = t('fullNameIsRequired');
    }
    if (!formData.national_id.trim()) {
      newErrors.national_id = t('nationalIdIsRequired');
    } else if (!/^[0-9]{10}$/.test(formData.national_id)) {
      newErrors.national_id = t('nationalIdMustBe10Digits');
    }
    if (!formData.phone.trim()) {
      newErrors.phone = t('phoneNumberIsRequired');
    } else if (!/^[0-9+\-\s]{9,15}$/.test(formData.phone)) {
      newErrors.phone = t('invalidPhoneNumber');
    }
    if (!formData.email.trim()) {
      newErrors.email = t('emailIsRequired');
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = t('invalidEmailFormat2');
    }
    if (!formData.password) {
      newErrors.password = t('passwordIsRequired');
    } else if (formData.password.length < 6) {
      newErrors.password = t('passwordMustBeAtLeast6Characters');
    }
    if (!formData.confirm_password) {
      newErrors.confirm_password = t('pleaseConfirmYourPassword');
    } else if (formData.password !== formData.confirm_password) {
      newErrors.confirm_password = t('passwordsDoNotMatch3');
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = () => {
    const newErrors = {};
    
    if (!formData.subject) {
      newErrors.subject = t('subjectIsRequired');
    }
    if (!formData.education_level) {
      newErrors.education_level = t('educationLevelIsRequired');
    }
    if (!formData.years_of_experience) {
      newErrors.years_of_experience = t('yearsOfExperienceRequired');
    }
    if (!formData.academic_degree) {
      newErrors.academic_degree = t('academicDegreeIsRequired');
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep3 = () => {
    const newErrors = {};
    
    if (!formData.teacher_rank) {
      newErrors.teacher_rank = t('teacherRankIsRequired');
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep4 = () => {
    const newErrors = {};
    
    if (!formData.school_name.trim()) {
      newErrors.school_name = t('schoolNameIsRequired');
    }
    if (!formData.school_city.trim()) {
      newErrors.school_city = t('schoolCityIsRequired');
    }
    if (!formData.school_type) {
      newErrors.school_type = t('schoolTypeIsRequired');
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle navigation
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

  // Submit registration (direct — no approval queue)
  const handleSubmit = async () => {
    if (!validateStep4()) {
      return;
    }
    
    setSubmitting(true);
    
    try {
      const response = await api.post('/teacher-registration/direct', {
        full_name: formData.full_name,
        national_id: formData.national_id,
        phone: formData.phone,
        email: formData.email,
        password: formData.password,
        subject: formData.subject,
        education_level: formData.education_level,
        years_of_experience: parseInt(formData.years_of_experience),
        academic_degree: formData.academic_degree,
        teacher_rank: formData.teacher_rank,
        school_name: formData.school_name,
        school_country: formData.school_country,
        school_city: formData.school_city,
        school_type: formData.school_type,
        referred_by: formData.referred_by || null,
      });
      
      const { access_token, refresh_token } = response.data;
      localStorage.removeItem('nassaq_refresh_token');
      if (refresh_token) {
        sessionStorage.setItem('nassaq_refresh_token', refresh_token);
      }

      // Hydrate the auth context (sets token, fetches /auth/me, updates user)
      // so the user is fully signed in without a full page reload.
      await updateToken(access_token);

      toast.success(t('accountCreatedSuccessfullyLoggingIn'));

      // This CTA mints an Independent Teacher (معلم مستقل) pre-bootstrap, so
      // route through the canonical IT first-login orchestration instead of
      // jumping straight to /teacher. Mirrors RegisterPage / LoginPage:
      //   signup → MFA enrolment → onboarding wizard → workspace bootstrap.
      const newUser = response.data?.user || {};
      const role = newUser.role;
      let target = '/teacher';
      if (role === 'independent_teacher') {
        if (!newUser.mfa_enrolled_at) {
          target = '/auth/mfa/enroll';
        } else if (!newUser.tenant_id) {
          target = '/teacher/onboarding';
        } else {
          target = '/teacher';
        }
      }

      setTimeout(() => {
        navigate(target, { replace: true });
      }, 800);
    } catch (error) {
      console.error('Submission error:', error);
      const errData = error.response?.data;
      const message = errData?.error?.message || errData?.detail || (t('errorSubmittingRequest'));
      nassaqError(message);
    } finally {
      setSubmitting(false);
    }
  };

  // Track request
  const handleTrackRequest = async () => {
    if (!trackingCode.trim()) {
      nassaqError(t('pleaseEnterTrackingCode'));
      return;
    }
    
    setIsTracking(true);
    
    try {
      const response = await api.get(`/teacher-registration/status/${trackingCode}`);
      setTrackingResult(response.data);
    } catch (error) {
      console.error('Tracking error:', error);
      nassaqError(t('requestNotFound'));
      setTrackingResult(null);
    } finally {
      setIsTracking(false);
    }
  };

  // Copy tracking code
  const copyTrackingCode = () => {
    if (submissionResult?.tracking_code) {
      navigator.clipboard.writeText(submissionResult.tracking_code);
      toast.success(t('trackingCodeCopied'));
    }
  };

  // Format remaining time
  const formatRemainingTime = (seconds) => {
    if (!seconds || seconds <= 0) return t('expired');
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (isRTL) {
      return `${hours} ساعة و ${minutes} دقيقة`;
    }
    return `${hours}h ${minutes}m`;
  };

  // Get status color and label
  const getStatusInfo = (status) => {
    const statusMap = {
      pending: { 
        color: 'bg-amber-100 text-amber-700 border-amber-200', 
        label: isRTL ? 'قيد المراجعة' : 'Pending Review',
        icon: Clock
      },
      approved: { 
        color: 'bg-green-100 text-green-700 border-green-200', 
        label: isRTL ? 'مقبول' : 'Approved',
        icon: CheckCircle2
      },
      rejected: { 
        color: 'bg-red-100 text-red-700 border-red-200', 
        label: t('rejected'),
        icon: AlertCircle
      },
      more_info: { 
        color: 'bg-blue-100 text-blue-700 border-blue-200', 
        label: t('moreInfoRequired'),
        icon: AlertCircle
      },
    };
    
    return statusMap[status] || statusMap.pending;
  };

  // Step indicators
  const steps = [
    { 
      number: 1, 
      title: isRTL ? 'البيانات الأساسية' : 'Basic Info',
      icon: User,
    },
    { 
      number: 2, 
      title: t('professionalInfo2'),
      icon: GraduationCap,
    },
    { 
      number: 3, 
      title: t('teacherRank2'),
      icon: Award,
    },
    { 
      number: 4, 
      title: isRTL ? 'بيانات المدرسة' : 'School Info',
      icon: Building2,
    },
    { 
      number: 5, 
      title: t('confirmation'),
      icon: CheckCircle2,
    },
  ];

  // Countries list
  const countries = [
    { value: 'SA', label_ar: 'المملكة العربية السعودية', label_en: 'Saudi Arabia' },
    { value: 'AE', label_ar: 'الإمارات العربية المتحدة', label_en: 'UAE' },
    { value: 'KW', label_ar: 'الكويت', label_en: 'Kuwait' },
    { value: 'QA', label_ar: 'قطر', label_en: 'Qatar' },
    { value: 'BH', label_ar: 'البحرين', label_en: 'Bahrain' },
    { value: 'OM', label_ar: 'عُمان', label_en: 'Oman' },
    { value: 'EG', label_ar: 'مصر', label_en: 'Egypt' },
    { value: 'JO', label_ar: 'الأردن', label_en: 'Jordan' },
    { value: 'OTHER', label_ar: 'أخرى', label_en: 'Other' },
  ];

  return (
    <div className="min-h-screen flex" dir={isRTL ? 'rtl' : 'ltr'} data-testid="teacher-self-registration-page">
      {/* ========== الجانب البصري ========== */}
      <div
        className="hidden lg:flex flex-1 flex-col justify-center items-center p-12 relative max-w-md"
        style={{
          backgroundImage: `url(${BG_PATTERN})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <div className="absolute inset-0 bg-brand-navy/95" />
        
        <div className="relative z-10 text-center">
          {/* Logo */}
          <img
            src={LOGO_WHITE}
            alt="نَسَّق"
            className="h-28 w-auto mx-auto mb-8 rounded-3xl"
            data-testid="registration-logo"
          />
          
          {/* Tagline */}
          <h2 className="font-cairo text-3xl font-bold text-white mb-4">
            {t('nassaq')}
          </h2>
          <p className="text-xl text-brand-turquoise font-cairo font-semibold mb-8">
            {t('smartEducationManagement')}
          </p>
          
          <div className="space-y-4 text-white/80 font-tajawal text-sm">
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-brand-turquoise" />
              <span>{t('advancedEducationalTools')}</span>
            </div>
            <div className="flex items-center gap-3">
              <Award className="h-5 w-5 text-brand-turquoise" />
              <span>{t('continuousProfessionalDevelopment')}</span>
            </div>
            <div className="flex items-center gap-3">
              <BookOpen className="h-5 w-5 text-brand-turquoise" />
              <span>{t('richEducationalResources')}</span>
            </div>
          </div>
          
          {/* Invite Banner */}
          {inviteInfo && (
            <div className="mt-8 p-4 bg-white/10 rounded-2xl backdrop-blur-sm">
              <p className="text-white/90 text-sm font-tajawal">
                {t('invitedBy')}
                <span className="font-bold text-brand-turquoise">{inviteInfo.inviter_name}</span>
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ========== الجانب التشغيلي ========== */}
      <div className="flex-1 flex flex-col bg-background">
        {/* Top Navigation */}
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

        {/* Registration Form */}
        <div className="flex-1 flex flex-col justify-center items-center p-6 lg:p-8 overflow-y-auto">
          {/* Mobile Logo */}
          <Link to="/" className="lg:hidden mb-6">
            <img src={LOGO_WHITE} alt="نَسَّق" className="h-12 w-auto rounded-xl" />
          </Link>

          {/* Track Request Button */}
          {currentStep !== 5 && (
            <div className="w-full max-w-2xl mb-6">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('enterTrackingCodeToCheckYourRequest')}
                    value={trackingCode}
                    onChange={(e) => setTrackingCode(e.target.value)}
                    className="ps-10 h-10 rounded-xl text-sm"
                    dir="ltr"
                    data-testid="tracking-code-input"
                  />
                </div>
                <Button
                  onClick={handleTrackRequest}
                  disabled={isTracking}
                  variant="outline"
                  className="rounded-xl h-10 px-4"
                  data-testid="track-request-btn"
                >
                  {isTracking ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <Timer className="h-4 w-4 me-2" />
                      {t('track')}
                    </>
                  )}
                </Button>
              </div>
              
              {/* Tracking Result */}
              {trackingResult && (
                <div className="mt-4 p-4 bg-card border rounded-xl">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-tajawal text-sm text-muted-foreground">
                      {t('requestStatus')}
                    </span>
                    <div className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusInfo(trackingResult.status).color}`}>
                      {getStatusInfo(trackingResult.status).label}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Timer className="h-4 w-4 text-brand-turquoise" />
                    <span className="font-tajawal">
                      {t('reviewTimeRemaining')}
                      <span className="font-bold">{formatRemainingTime(trackingResult.remaining_seconds)}</span>
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step Indicators */}
          {currentStep < 5 && (
            <div className="w-full max-w-2xl mb-8">
              <div className="flex items-center justify-between">
                {steps.slice(0, 4).map((step, index) => (
                  <div key={step.number} className="flex items-center">
                    <div className="flex flex-col items-center">
                      <div
                        className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                          currentStep >= step.number
                            ? 'bg-brand-turquoise text-white'
                            : 'bg-muted text-muted-foreground'
                        }`}
                        data-testid={`step-indicator-${step.number}`}
                      >
                        {currentStep > step.number ? (
                          <CheckCircle2 className="h-5 w-5" />
                        ) : (
                          <step.icon className="h-5 w-5" />
                        )}
                      </div>
                      <span className={`text-xs mt-2 font-tajawal text-center max-w-[70px] ${
                        currentStep >= step.number ? 'text-foreground' : 'text-muted-foreground'
                      }`}>
                        {step.title}
                      </span>
                    </div>
                    {index < 3 && (
                      <div
                        className={`h-0.5 w-8 sm:w-16 mx-1 sm:mx-2 transition-all ${
                          currentStep > step.number ? 'bg-brand-turquoise' : 'bg-muted'
                        }`}
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <Card className="w-full max-w-2xl card-nassaq" data-testid="registration-card">
            <CardHeader className="text-center pb-2">
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {t('newTeacherRegistration')}
              </h1>
              {currentStep < 5 && (
                <p className="text-muted-foreground font-tajawal text-sm">
                  {t('step')} {currentStep} {isRTL ? 'من' : 'of'} 4 - {steps[currentStep - 1].title}
                </p>
              )}
            </CardHeader>
            
            <CardContent className="pt-4">
              {/* ========== Step 1: البيانات الأساسية ========== */}
              {currentStep === 1 && (
                <div className="space-y-5" data-testid="step-1-content">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      <Label htmlFor="national_id" className="font-tajawal">
                        {t('nationalId')} *
                      </Label>
                      <div className="relative">
                        <IdCard className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="national_id"
                          placeholder={isRTL ? '1XXXXXXXXX' : '1XXXXXXXXX'}
                          value={formData.national_id}
                          onChange={(e) => updateFormData('national_id', e.target.value)}
                          className={`ps-10 h-12 rounded-xl font-tajawal ${errors.national_id ? 'border-destructive' : ''}`}
                          dir="ltr"
                          maxLength={10}
                          data-testid="national-id-input"
                        />
                      </div>
                      {errors.national_id && (
                        <p className="text-destructive text-xs font-tajawal">{errors.national_id}</p>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="phone" className="font-tajawal">
                        {isRTL ? 'رقم الهاتف' : 'Phone Number'} *
                      </Label>
                      <div className="relative">
                        <Phone className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="phone"
                          type="tel"
                          placeholder="+966 5X XXX XXXX"
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

                    <div className="space-y-2">
                      <Label htmlFor="email" className="font-tajawal">
                        {t('email2')} *
                      </Label>
                      <div className="relative">
                        <Mail className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="email"
                          type="email"
                          placeholder="teacher@example.com"
                          value={formData.email}
                          onChange={(e) => updateFormData('email', e.target.value)}
                          className={`ps-10 h-12 rounded-xl font-tajawal ${errors.email ? 'border-destructive' : ''}`}
                          dir="ltr"
                          data-testid="email-input"
                        />
                      </div>
                      {errors.email && (
                        <p className="text-destructive text-xs font-tajawal">{errors.email}</p>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="password" className="font-tajawal">
                        {t('password')} *
                      </Label>
                      <div className="relative">
                        <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="password"
                          type={showPassword ? 'text' : 'password'}
                          placeholder={isRTL ? 'أدخل كلمة المرور' : 'Enter password'}
                          value={formData.password}
                          onChange={(e) => updateFormData('password', e.target.value)}
                          className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${errors.password ? 'border-destructive' : ''}`}
                          dir="ltr"
                          data-testid="password-input"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          tabIndex={-1}
                        >
                          {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                      </div>
                      {errors.password && (
                        <p className="text-destructive text-xs font-tajawal">{errors.password}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="confirm_password" className="font-tajawal">
                        {t('confirmPassword')} *
                      </Label>
                      <div className="relative">
                        <Lock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="confirm_password"
                          type={showConfirmPassword ? 'text' : 'password'}
                          placeholder={t('reenterPassword2')}
                          value={formData.confirm_password}
                          onChange={(e) => updateFormData('confirm_password', e.target.value)}
                          className={`ps-10 pe-10 h-12 rounded-xl font-tajawal ${errors.confirm_password ? 'border-destructive' : ''}`}
                          dir="ltr"
                          data-testid="confirm-password-input"
                        />
                        <button
                          type="button"
                          onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                          className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          tabIndex={-1}
                        >
                          {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                        </button>
                      </div>
                      {errors.confirm_password && (
                        <p className="text-destructive text-xs font-tajawal">{errors.confirm_password}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* ========== Step 2: المعلومات المهنية ========== */}
              {currentStep === 2 && (
                <div className="space-y-5" data-testid="step-2-content">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="font-tajawal">
                        {t('subject4')} *
                      </Label>
                      <Select
                        value={formData.subject}
                        onValueChange={(value) => updateFormData('subject', value)}
                      >
                        <SelectTrigger 
                          className={`h-12 rounded-xl ${errors.subject ? 'border-destructive' : ''}`}
                          data-testid="subject-select"
                        >
                          <SelectValue placeholder={t('selectSubject')} />
                        </SelectTrigger>
                        <SelectContent>
                          {subjects.map((subject) => (
                            <SelectItem key={subject.value} value={subject.value}>
                              {isRTL ? subject.label_ar : subject.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {errors.subject && (
                        <p className="text-destructive text-xs font-tajawal">{errors.subject}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label className="font-tajawal">
                        {t('educationLevel')} *
                      </Label>
                      <Select
                        value={formData.education_level}
                        onValueChange={(value) => updateFormData('education_level', value)}
                      >
                        <SelectTrigger 
                          className={`h-12 rounded-xl ${errors.education_level ? 'border-destructive' : ''}`}
                          data-testid="education-level-select"
                        >
                          <SelectValue placeholder={t('selectLevel')} />
                        </SelectTrigger>
                        <SelectContent>
                          {educationLevels.map((level) => (
                            <SelectItem key={level.value} value={level.value}>
                              {isRTL ? level.label_ar : level.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {errors.education_level && (
                        <p className="text-destructive text-xs font-tajawal">{errors.education_level}</p>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="years_of_experience" className="font-tajawal">
                        {isRTL ? 'سنوات الخبرة' : 'Years of Experience'} *
                      </Label>
                      <div className="relative">
                        <Clock className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                        <Input
                          id="years_of_experience"
                          type="number"
                          min="0"
                          max="50"
                          placeholder={t('eg5')}
                          value={formData.years_of_experience}
                          onChange={(e) => updateFormData('years_of_experience', e.target.value)}
                          className={`ps-10 h-12 rounded-xl font-tajawal ${errors.years_of_experience ? 'border-destructive' : ''}`}
                          data-testid="years-experience-input"
                        />
                      </div>
                      {errors.years_of_experience && (
                        <p className="text-destructive text-xs font-tajawal">{errors.years_of_experience}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label className="font-tajawal">
                        {t('academicDegree')} *
                      </Label>
                      <Select
                        value={formData.academic_degree}
                        onValueChange={(value) => updateFormData('academic_degree', value)}
                      >
                        <SelectTrigger 
                          className={`h-12 rounded-xl ${errors.academic_degree ? 'border-destructive' : ''}`}
                          data-testid="academic-degree-select"
                        >
                          <SelectValue placeholder={t('selectDegree2')} />
                        </SelectTrigger>
                        <SelectContent>
                          {academicDegrees.map((degree) => (
                            <SelectItem key={degree.value} value={degree.value}>
                              {isRTL ? degree.label_ar : degree.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {errors.academic_degree && (
                        <p className="text-destructive text-xs font-tajawal">{errors.academic_degree}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* ========== Step 3: رتبة المعلم ========== */}
              {currentStep === 3 && (
                <div className="space-y-5" data-testid="step-3-content">
                  <p className="text-muted-foreground font-tajawal text-center mb-6">
                    {t('selectYourProfessionalRankAccordingToTheApprovedSy')}
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {teacherRanks.map((rank) => (
                      <div
                        key={rank.value}
                        onClick={() => updateFormData('teacher_rank', rank.value)}
                        className={`p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                          formData.teacher_rank === rank.value
                            ? 'border-brand-turquoise bg-brand-turquoise/5'
                            : 'border-border hover:border-brand-turquoise/50'
                        }`}
                        data-testid={`rank-${rank.value}`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                            formData.teacher_rank === rank.value
                              ? 'bg-brand-turquoise text-white'
                              : 'bg-muted text-muted-foreground'
                          }`}>
                            <Award className="h-5 w-5" />
                          </div>
                          <div>
                            <p className="font-cairo font-bold">
                              {isRTL ? rank.label_ar : rank.label_en}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {errors.teacher_rank && (
                    <p className="text-destructive text-xs font-tajawal text-center">{errors.teacher_rank}</p>
                  )}
                </div>
              )}

              {/* ========== Step 4: بيانات المدرسة ========== */}
              {currentStep === 4 && (
                <div className="space-y-5" data-testid="step-4-content">
                  <div className="bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-xl p-4 mb-4">
                    <p className="text-sm text-foreground font-tajawal">
                      <span className="font-bold">
                        {t('note2')}
                      </span>
                      {t('enterYourCurrentSchoolInformationEvenIfNotRegister')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="school_name" className="font-tajawal">
                      {t('schoolName')} *
                    </Label>
                    <div className="relative">
                      <Building2 className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                      <Input
                        id="school_name"
                        placeholder={t('schoolName3')}
                        value={formData.school_name}
                        onChange={(e) => updateFormData('school_name', e.target.value)}
                        className={`ps-10 h-12 rounded-xl font-tajawal ${errors.school_name ? 'border-destructive' : ''}`}
                        data-testid="school-name-input"
                      />
                    </div>
                    {errors.school_name && (
                      <p className="text-destructive text-xs font-tajawal">{errors.school_name}</p>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="font-tajawal">
                        {t('country')} *
                      </Label>
                      <Select
                        value={formData.school_country}
                        onValueChange={(value) => updateFormData('school_country', value)}
                      >
                        <SelectTrigger className="h-12 rounded-xl" data-testid="school-country-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {countries.map((country) => (
                            <SelectItem key={country.value} value={country.value}>
                              {isRTL ? country.label_ar : country.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

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
                  </div>

                  <div className="space-y-2">
                    <Label className="font-tajawal">
                      {t('schoolType')} *
                    </Label>
                    <Select
                      value={formData.school_type}
                      onValueChange={(value) => updateFormData('school_type', value)}
                    >
                      <SelectTrigger 
                        className={`h-12 rounded-xl ${errors.school_type ? 'border-destructive' : ''}`}
                        data-testid="school-type-select"
                      >
                        <SelectValue placeholder={t('selectSchoolType')} />
                      </SelectTrigger>
                      <SelectContent>
                        {schoolTypes.map((type) => (
                          <SelectItem key={type.value} value={type.value}>
                            {isRTL ? type.label_ar : type.label_en}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.school_type && (
                      <p className="text-destructive text-xs font-tajawal">{errors.school_type}</p>
                    )}
                  </div>
                </div>
              )}

              {/* ========== Step 5: (unused — auto-redirect on success) ========== */}

              {/* Navigation Buttons */}
              {currentStep < 5 && (
                <div className="flex items-center justify-between mt-8 pt-4 border-t border-border/50">
                  <Button
                    variant="outline"
                    onClick={handlePrevious}
                    disabled={currentStep === 1}
                    className="rounded-xl font-tajawal"
                    data-testid="prev-step-btn"
                  >
                    {isRTL ? (
                      <>
                        <ArrowRight className="h-4 w-4 me-2" />
                        {isRTL ? 'السابق' : 'Previous'}
                      </>
                    ) : (
                      <>
                        <ArrowLeft className="h-4 w-4 me-2" />
                        Previous
                      </>
                    )}
                  </Button>

                  {currentStep < 4 ? (
                    <Button
                      onClick={handleNext}
                      className="bg-brand-navy hover:bg-brand-navy-light rounded-xl font-tajawal"
                      data-testid="next-step-btn"
                    >
                      {t('next')}
                      {isRTL ? (
                        <ArrowLeft className="h-4 w-4 ms-2" />
                      ) : (
                        <ArrowRight className="h-4 w-4 ms-2" />
                      )}
                    </Button>
                  ) : (
                    <Button
                      onClick={handleSubmit}
                      disabled={submitting}
                      className="bg-brand-turquoise hover:bg-brand-turquoise/90 rounded-xl font-cairo"
                      data-testid="submit-btn"
                    >
                      {submitting ? (
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
              )}

              {/* Login Link */}
              {currentStep < 5 && (
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
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default TeacherSelfRegistration;
