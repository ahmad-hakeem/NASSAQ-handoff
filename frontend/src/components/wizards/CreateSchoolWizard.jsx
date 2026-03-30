import React, { useState, useRef, useCallback } from 'react';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Textarea } from '../ui/textarea';
import { toast } from 'sonner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  Building2, Upload, Globe, MapPin, FileText, Languages, Calendar,
  GraduationCap, Award, User, Phone, Mail, Check, ChevronRight,
  ChevronLeft, Save, X, Copy, ExternalLink, CheckCircle2, Sparkles,
  RotateCcw
} from 'lucide-react';

// Countries list
const COUNTRIES = [
  { code: 'SA', name: 'المملكة العربية السعودية', name_en: 'Saudi Arabia' },
  { code: 'AE', name: 'الإمارات العربية المتحدة', name_en: 'UAE' },
  { code: 'KW', name: 'الكويت', name_en: 'Kuwait' },
  { code: 'QA', name: 'قطر', name_en: 'Qatar' },
  { code: 'BH', name: 'البحرين', name_en: 'Bahrain' },
  { code: 'OM', name: 'عمان', name_en: 'Oman' },
  { code: 'EG', name: 'مصر', name_en: 'Egypt' },
  { code: 'JO', name: 'الأردن', name_en: 'Jordan' },
];

// Saudi cities by region
const SAUDI_REGIONS = {
  central: { name: 'المنطقة الوسطى', cities: ['الرياض', 'القصيم', 'حائل'] },
  western: { name: 'المنطقة الغربية', cities: ['جدة', 'مكة المكرمة', 'المدينة المنورة', 'الطائف', 'ينبع'] },
  eastern: { name: 'المنطقة الشرقية', cities: ['الدمام', 'الخبر', 'الظهران', 'الأحساء', 'الجبيل'] },
  northern: { name: 'المنطقة الشمالية', cities: ['تبوك', 'عرعر', 'سكاكا'] },
  southern: { name: 'المنطقة الجنوبية', cities: ['أبها', 'جازان', 'نجران', 'خميس مشيط'] },
};

const ALL_SAUDI_CITIES = Object.values(SAUDI_REGIONS).flatMap(r => r.cities);

// School types
const SCHOOL_TYPES = [
  { value: 'public', label: 'حكومية', label_en: 'Public' },
  { value: 'private', label: 'أهلية', label_en: 'Private' },
];

// Educational stages
const EDUCATIONAL_STAGES = [
  { value: 'nursery', label: 'الحضانة', label_en: 'Nursery' },
  { value: 'kindergarten', label: 'رياض الأطفال', label_en: 'Kindergarten' },
  { value: 'primary', label: 'الابتدائية', label_en: 'Primary' },
  { value: 'intermediate', label: 'المتوسطة', label_en: 'Intermediate' },
  { value: 'secondary', label: 'الثانوية العامة', label_en: 'Secondary' },
  { value: 'continuous', label: 'التعليم المستمر', label_en: 'Continuous Education' },
  { value: 'special_needs', label: 'ذوي الإعاقة', label_en: 'Special Needs' },
  { value: 'scientific_institutes', label: 'المعاهد العلمية', label_en: 'Scientific Institutes' },
  { value: 'gifted', label: 'المطبقة لبرامج الموهوبين', label_en: 'Gifted Programs' },
  { value: 'arts', label: 'المطبقة لمبادرة الفنون', label_en: 'Arts Initiative' },
  { value: 'chinese', label: 'المطبقة للغة الصينية', label_en: 'Chinese Language' },
  { value: 'hadith', label: 'دار الحديث المكية / المدنية', label_en: 'Dar Al-Hadith' },
  { value: 'different_curriculum', label: 'مدارس بمنهج مختلف', label_en: 'Different Curriculum' },
];

// Calendar systems
const CALENDAR_SYSTEMS = [
  { value: 'hijri', label: 'هجري', label_en: 'Hijri' },
  { value: 'gregorian', label: 'ميلادي', label_en: 'Gregorian' },
  { value: 'hijri_gregorian', label: 'هجري + ميلادي', label_en: 'Hijri + Gregorian' },
  { value: 'gregorian_hijri', label: 'ميلادي + هجري', label_en: 'Gregorian + Hijri' },
];

// Assessment systems
const ASSESSMENT_SYSTEMS = [
  { value: 'standard', label: 'النظام القياسي (100 درجة)', label_en: 'Standard (100 points)' },
  { value: 'gpa', label: 'نظام المعدل التراكمي', label_en: 'GPA System' },
  { value: 'competency', label: 'نظام الكفايات', label_en: 'Competency Based' },
];

// Generate temporary password
const generateTempPassword = () => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789@#$';
  let password = '';
  for (let i = 0; i < 12; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return password;
};

export default function CreateSchoolWizard({ open, onOpenChange, onSuccess, api, isRTL = true }) {
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const formRef = useRef(null);
  
  // Step 1: School Profile
  const [schoolData, setSchoolData] = useState({
    name: '',
    logo: null,
    logoPreview: null,
    country: 'SA',
    city: '',
    address: '',
  });
  
  // Step 2: Operating Settings
  const [settingsData, setSettingsData] = useState({
    defaultLanguage: 'ar',
    calendarSystem: 'hijri_gregorian',
    schoolType: 'public',
    educationalStage: 'primary',
    assessmentSystem: 'standard',
  });
  
  // Step 3: Principal Account
  const [principalData, setPrincipalData] = useState({
    fullName: '',
    primaryPhone: '',
    secondaryPhone: '',
    email: '',
  });
  
  // Created school data
  const [createdSchool, setCreatedSchool] = useState(null);
  
  // Validation errors
  const [errors, setErrors] = useState({});

  const clearFieldError = useCallback((field) => {
    setErrors(prev => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }, []);

  const focusFirstError = useCallback((errorKeys) => {
    if (!errorKeys.length) return;
    setTimeout(() => {
      const firstKey = errorKeys[0];
      const el = formRef.current?.querySelector(`[data-field="${firstKey}"]`);
      if (el) {
        const input = el.querySelector('input, textarea, select, button');
        if (input) input.focus();
      }
    }, 100);
  }, []);
  
  const validateStep1 = () => {
    const newErrors = {};
    if (!schoolData.name.trim()) newErrors.name = isRTL ? 'اسم المدرسة مطلوب' : 'School name is required';
    if (!schoolData.country) newErrors.country = isRTL ? 'الدولة مطلوبة' : 'Country is required';
    if (!schoolData.city) newErrors.city = isRTL ? 'المدينة مطلوبة' : 'City is required';
    if (!schoolData.address.trim()) newErrors.address = isRTL ? 'العنوان مطلوب' : 'Address is required';
    setErrors(newErrors);
    const errorKeys = Object.keys(newErrors);
    if (errorKeys.length > 0) {
      nassaqWarning(
        isRTL
          ? `يرجى تعبئة الحقول المطلوبة: ${Object.values(newErrors).join('، ')}`
          : `Please fill required fields: ${Object.values(newErrors).join(', ')}`
      );
      focusFirstError(errorKeys);
    }
    return errorKeys.length === 0;
  };

  const validateStep3 = () => {
    const newErrors = {};
    if (!principalData.fullName.trim()) newErrors.fullName = isRTL ? 'اسم المدير مطلوب' : 'Principal name is required';
    if (!principalData.primaryPhone.trim()) newErrors.primaryPhone = isRTL ? 'رقم الهاتف مطلوب' : 'Phone number is required';
    if (!principalData.email.trim()) newErrors.email = isRTL ? 'البريد الإلكتروني مطلوب' : 'Email is required';

    if (principalData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(principalData.email)) {
      newErrors.email = isRTL ? 'صيغة البريد الإلكتروني غير صحيحة' : 'Invalid email format';
    }

    if (principalData.primaryPhone && !/^05\d{8}$/.test(principalData.primaryPhone.replace(/\s/g, ''))) {
      newErrors.primaryPhone = isRTL ? 'رقم الهاتف غير صحيح (يجب أن يبدأ بـ 05 ويتكون من 10 أرقام)' : 'Invalid phone (must start with 05, 10 digits)';
    }

    setErrors(newErrors);
    const errorKeys = Object.keys(newErrors);
    if (errorKeys.length > 0) {
      nassaqWarning(
        isRTL
          ? `يرجى تصحيح البيانات التالية: ${Object.values(newErrors).join('، ')}`
          : `Please fix the following: ${Object.values(newErrors).join(', ')}`
      );
      focusFirstError(errorKeys);
    }
    return errorKeys.length === 0;
  };

  const handleNext = () => {
    if (currentStep === 1 && !validateStep1()) return;
    if (currentStep === 3 && !validateStep3()) return;
    setCurrentStep(prev => Math.min(prev + 1, 4));
  };
  
  // Handle previous step
  const handlePrevious = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };
  
  // Handle logo upload
  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSchoolData({ ...schoolData, logo: file, logoPreview: event.target.result });
      };
      reader.readAsDataURL(file);
    }
  };
  
  // Handle save as draft - Save to database with status='setup'
  const handleSaveAsDraft = async () => {
    setIsSubmitting(true);
    
    try {
      // Prepare school data for API with draft status
      const schoolPayload = {
        name: schoolData.name || (isRTL ? 'مسودة مدرسة' : 'Draft School'),
        country: schoolData.country || 'SA',
        city: schoolData.city || '',
        address: schoolData.address || '',
        language: settingsData.defaultLanguage,
        calendar_system: settingsData.calendarSystem,
        school_type: settingsData.schoolType,
        stage: settingsData.educationalStage,
        principal_name: principalData.fullName || '',
        principal_email: principalData.email || '',
        principal_phone: principalData.primaryPhone || '',
        status: 'setup', // Mark as draft/setup
      };
      
      // API call to create school as draft
      const response = await api.post('/schools/draft', schoolPayload);
      
      toast.success(isRTL ? 'تم حفظ المدرسة كمسودة بنجاح' : 'School saved as draft successfully');
      
      // Close wizard and refresh parent
      if (onSuccess) onSuccess(response.data);
      handleClose();
      
    } catch (error) {
      console.error('Error saving draft:', error);
      
      // Fallback to localStorage if API fails
      const draft = {
        schoolData,
        settingsData,
        principalData,
        savedAt: new Date().toISOString()
      };
      localStorage.setItem('nassaq_school_draft', JSON.stringify(draft));
      toast.success(isRTL ? 'تم حفظ المسودة محلياً' : 'Draft saved locally');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Reset settings to default
  const resetSettingsToDefault = () => {
    setSettingsData({
      defaultLanguage: 'ar',
      calendarSystem: 'hijri_gregorian',
      schoolType: 'public',
      educationalStage: 'primary',
      assessmentSystem: 'standard',
    });
    toast.info(isRTL ? 'تم إعادة الإعدادات للوضع الافتراضي' : 'Settings reset to default');
  };
  
  // Handle create school
  const handleCreateSchool = async () => {
    if (!validateStep3()) {
      setCurrentStep(3);
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const tempPassword = generateTempPassword();
      
      // Prepare school data for API
      const schoolPayload = {
        name: schoolData.name,
        country: schoolData.country,
        city: schoolData.city,
        address: schoolData.address,
        language: settingsData.defaultLanguage,
        calendar_system: settingsData.calendarSystem,
        school_type: settingsData.schoolType,
        stage: settingsData.educationalStage,
        principal_name: principalData.fullName,
        principal_email: principalData.email,
        principal_phone: principalData.primaryPhone,
      };
      
      // API call to create school
      const response = await api.post('/schools', schoolPayload);
      
      setCreatedSchool({
        ...response.data,
        tenant_code: response.data.code,
        principal: {
          full_name: principalData.fullName,
          email: principalData.email,
          temp_password: tempPassword,
        },
      });
      
      setIsComplete(true);
      toast.success(isRTL ? 'تم إنشاء المدرسة بنجاح!' : 'School created successfully!');
      
      if (onSuccess) onSuccess(response.data);
      
    } catch (error) {
      console.error('Error creating school:', error);
      
      // Show actual error message to user
      const errorMessage = error.response?.data?.detail || 
                          (isRTL ? 'حدث خطأ أثناء إنشاء المدرسة. يرجى المحاولة مرة أخرى.' 
                                 : 'Error creating school. Please try again.');
      
      nassaqError(errorMessage);
      
      // Do NOT show success or set isComplete to true
      // Let user try again or fix the issue
      
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Copy welcome message
  const copyWelcomeMessage = () => {
    const message = `أهلاً بك في منصة نَسَّق المدعومة بالذكاء الاصطناعي.

بيانات دخولك على النظام كالتالي:

رابط المنصة:
${window.location.origin}

اسم المستخدم / البريد الإلكتروني:
${createdSchool?.principal?.email}

كلمة المرور المؤقتة:
${createdSchool?.principal?.temp_password}

كود المدرسة:
${createdSchool?.tenant_code}

يرجى تغيير كلمة المرور عند أول تسجيل دخول.`;
    
    navigator.clipboard.writeText(message);
    toast.success(isRTL ? 'تم نسخ رسالة الترحيب' : 'Welcome message copied');
  };
  
  // Reset wizard
  const resetWizard = () => {
    setCurrentStep(1);
    setIsComplete(false);
    setCreatedSchool(null);
    setSchoolData({ name: '', logo: null, logoPreview: null, country: 'SA', city: '', address: '' });
    setSettingsData({ defaultLanguage: 'ar', calendarSystem: 'hijri_gregorian', schoolType: 'public', educationalStage: 'primary', assessmentSystem: 'standard' });
    setPrincipalData({ fullName: '', primaryPhone: '', secondaryPhone: '', email: '' });
    setErrors({});
  };
  
  // Close handler
  const handleClose = () => {
    resetWizard();
    onOpenChange(false);
  };
  
  // Steps configuration
  const steps = [
    { number: 1, title: isRTL ? 'بيانات المدرسة' : 'School Profile', icon: Building2 },
    { number: 2, title: isRTL ? 'إعدادات التشغيل' : 'Settings', icon: GraduationCap },
    { number: 3, title: isRTL ? 'مدير المدرسة' : 'Principal', icon: User },
    { number: 4, title: isRTL ? 'مراجعة وتأكيد' : 'Review', icon: Check },
  ];
  
  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-5xl md:h-[80vh] h-[90vh] flex flex-col p-0 overflow-hidden" data-testid="create-school-wizard">
        {!isComplete ? (
          <>
            {/* Header with Steps */}
            <DialogHeader className="p-6 pb-0 border-b">
              <DialogTitle className="font-cairo text-xl mb-4">
                {isRTL ? 'إنشاء مدرسة جديدة' : 'Create New School Tenant'}
              </DialogTitle>
              
              {/* Steps Progress */}
              <div className="flex items-center justify-between mb-4">
                {steps.map((step, index) => (
                  <div key={step.number} className="flex items-center">
                    <div className={`flex items-center gap-2 ${
                      currentStep === step.number ? 'text-brand-turquoise' :
                      currentStep > step.number ? 'text-green-500' : 'text-muted-foreground'
                    }`}>
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${
                        currentStep === step.number ? 'border-brand-turquoise bg-brand-turquoise/10' :
                        currentStep > step.number ? 'border-green-500 bg-green-500/10' : 'border-muted-foreground/30'
                      }`}>
                        {currentStep > step.number ? (
                          <CheckCircle2 className="h-5 w-5 text-green-500" />
                        ) : (
                          <step.icon className="h-5 w-5" />
                        )}
                      </div>
                      <span className="text-sm font-medium hidden md:block">{step.title}</span>
                    </div>
                    {index < steps.length - 1 && (
                      <div className={`w-12 h-0.5 mx-2 transition-all ${
                        currentStep > step.number ? 'bg-green-500' : 'bg-muted-foreground/30'
                      }`} />
                    )}
                  </div>
                ))}
              </div>
            </DialogHeader>
            
            {/* Content — no-scroll on desktop, controlled scroll on mobile */}
            <div className="flex-1 min-h-0 p-6 md:overflow-hidden overflow-y-auto" ref={formRef}>
              {/* Step 1: School Profile — grid layout */}
              {currentStep === 1 && (
                <div className="h-full flex flex-col" data-testid="wizard-step-1">
                  <div className="text-center mb-4">
                    <h3 className="font-cairo text-lg font-bold">{isRTL ? 'بيانات المدرسة الأساسية' : 'Basic School Information'}</h3>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'أدخل المعلومات الأساسية للمدرسة' : 'Enter the basic school information'}</p>
                  </div>

                  <div className="flex gap-6 mb-4">
                    <div className="relative flex-shrink-0">
                      <div className={`w-24 h-24 rounded-2xl border-2 border-dashed flex items-center justify-center overflow-hidden transition-all ${
                        schoolData.logoPreview ? 'border-brand-turquoise bg-brand-turquoise/5' : 'border-muted-foreground/30 hover:border-brand-turquoise/50'
                      }`}>
                        {schoolData.logoPreview ? (
                          <img src={schoolData.logoPreview} alt="School Logo" className="w-full h-full object-cover" />
                        ) : (
                          <div className="text-center p-2">
                            <Upload className="h-6 w-6 mx-auto text-muted-foreground mb-1" />
                            <span className="text-[10px] text-muted-foreground leading-tight block">{isRTL ? 'رفع الشعار' : 'Upload Logo'}</span>
                            <Badge variant="outline" className="text-[9px] mt-0.5 block">{isRTL ? 'اختياري' : 'Optional'}</Badge>
                          </div>
                        )}
                      </div>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleLogoUpload}
                        className="absolute inset-0 opacity-0 cursor-pointer"
                        data-testid="logo-upload"
                      />
                    </div>

                    <div className="flex-1 space-y-1.5" data-field="name">
                      <Label className="flex items-center gap-2">
                        {isRTL ? 'اسم المدرسة' : 'School Name'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Input
                        value={schoolData.name}
                        onChange={(e) => { setSchoolData({ ...schoolData, name: e.target.value }); clearFieldError('name'); }}
                        placeholder={isRTL ? 'مثال: مدرسة النور الأهلية' : 'e.g., Al-Noor Private School'}
                        className={errors.name ? 'border-red-500' : ''}
                        data-testid="school-name-input"
                      />
                      {errors.name && <p className="text-sm text-red-500 font-medium">{errors.name}</p>}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div className="space-y-1.5" data-field="country">
                      <Label className="flex items-center gap-2">
                        <Globe className="h-4 w-4" />
                        {isRTL ? 'الدولة' : 'Country'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Select value={schoolData.country} onValueChange={(v) => { setSchoolData({ ...schoolData, country: v, city: '' }); clearFieldError('country'); }}>
                        <SelectTrigger className={errors.country ? 'border-red-500' : ''} data-testid="country-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {COUNTRIES.map((country) => (
                            <SelectItem key={country.code} value={country.code}>
                              {isRTL ? country.name : country.name_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {errors.country && <p className="text-sm text-red-500 font-medium">{errors.country}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="city">
                      <Label className="flex items-center gap-2">
                        <MapPin className="h-4 w-4" />
                        {isRTL ? 'المدينة' : 'City'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Select value={schoolData.city} onValueChange={(v) => { setSchoolData({ ...schoolData, city: v }); clearFieldError('city'); }}>
                        <SelectTrigger className={errors.city ? 'border-red-500' : ''} data-testid="city-select">
                          <SelectValue placeholder={isRTL ? 'اختر المدينة' : 'Select City'} />
                        </SelectTrigger>
                        <SelectContent>
                          {schoolData.country === 'SA' ? (
                            ALL_SAUDI_CITIES.map((city) => (
                              <SelectItem key={city} value={city}>{city}</SelectItem>
                            ))
                          ) : (
                            <SelectItem value="other">{isRTL ? 'أخرى' : 'Other'}</SelectItem>
                          )}
                        </SelectContent>
                      </Select>
                      {errors.city && <p className="text-sm text-red-500 font-medium">{errors.city}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="address">
                      <Label className="flex items-center gap-2">
                        <FileText className="h-4 w-4" />
                        {isRTL ? 'العنوان التفصيلي' : 'Address'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Input
                        value={schoolData.address}
                        onChange={(e) => { setSchoolData({ ...schoolData, address: e.target.value }); clearFieldError('address'); }}
                        placeholder={isRTL ? 'الحي، الشارع، المبنى...' : 'District, Street, Building...'}
                        className={errors.address ? 'border-red-500' : ''}
                        data-testid="address-input"
                      />
                      {errors.address && <p className="text-sm text-red-500 font-medium">{errors.address}</p>}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 2: Operating Settings — 3-col grid */}
              {currentStep === 2 && (
                <div className="h-full flex flex-col" data-testid="wizard-step-2">
                  <div className="text-center mb-4">
                    <h3 className="font-cairo text-lg font-bold">{isRTL ? 'إعدادات التشغيل الخاصة بالمدرسة' : 'School Operating Settings'}</h3>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'حدد الإعدادات الافتراضية للمدرسة' : 'Set the default settings for the school'}</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-2">
                        <Languages className="h-4 w-4" />
                        {isRTL ? 'اللغة الافتراضية' : 'Default Language'}
                      </Label>
                      <Select value={settingsData.defaultLanguage} onValueChange={(v) => setSettingsData({ ...settingsData, defaultLanguage: v })}>
                        <SelectTrigger data-testid="language-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ar">العربية (RTL)</SelectItem>
                          <SelectItem value="en">English (LTR)</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">{isRTL ? 'يمكن لكل مستخدم اختيار لغته' : 'Each user can choose their language'}</p>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        {isRTL ? 'نظام التقويم' : 'Calendar System'}
                      </Label>
                      <Select value={settingsData.calendarSystem} onValueChange={(v) => setSettingsData({ ...settingsData, calendarSystem: v })}>
                        <SelectTrigger data-testid="calendar-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {CALENDAR_SYSTEMS.map((cal) => (
                            <SelectItem key={cal.value} value={cal.value}>
                              {isRTL ? cal.label : cal.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-2">
                        <Building2 className="h-4 w-4" />
                        {isRTL ? 'نوع المدرسة' : 'School Type'}
                      </Label>
                      <Select value={settingsData.schoolType} onValueChange={(v) => setSettingsData({ ...settingsData, schoolType: v })}>
                        <SelectTrigger data-testid="school-type-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SCHOOL_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value}>
                              {isRTL ? type.label : type.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-2">
                        <GraduationCap className="h-4 w-4" />
                        {isRTL ? 'المرحلة التعليمية' : 'Educational Stage'}
                      </Label>
                      <Select value={settingsData.educationalStage} onValueChange={(v) => setSettingsData({ ...settingsData, educationalStage: v })}>
                        <SelectTrigger data-testid="stage-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {EDUCATIONAL_STAGES.map((stage) => (
                            <SelectItem key={stage.value} value={stage.value}>
                              {isRTL ? stage.label : stage.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-2">
                        <Award className="h-4 w-4" />
                        {isRTL ? 'نظام التقييم' : 'Assessment System'}
                      </Label>
                      <Select value={settingsData.assessmentSystem} onValueChange={(v) => setSettingsData({ ...settingsData, assessmentSystem: v })}>
                        <SelectTrigger data-testid="assessment-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ASSESSMENT_SYSTEMS.map((sys) => (
                            <SelectItem key={sys.value} value={sys.value}>
                              {isRTL ? sys.label : sys.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        {isRTL ? 'سيتم ربط نظام التقييم تلقائياً مع قواعد الاختبارات' : 'Assessment will be linked to test rules'}
                      </p>
                    </div>
                  </div>

                  <div className="flex justify-center">
                    <Button variant="outline" size="sm" onClick={resetSettingsToDefault} className="text-muted-foreground">
                      <RotateCcw className="h-4 w-4 me-2" />
                      {isRTL ? 'إعادة الإعدادات للوضع الافتراضي' : 'Reset to Defaults'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Step 3: Principal — 2-col grid with inline info */}
              {currentStep === 3 && (
                <div className="h-full flex flex-col" data-testid="wizard-step-3">
                  <div className="text-center mb-4">
                    <h3 className="font-cairo text-lg font-bold">{isRTL ? 'إنشاء حساب مدير المدرسة' : 'Create School Principal Account'}</h3>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'أدخل بيانات مدير المدرسة المسؤول' : 'Enter the principal information'}</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <div className="space-y-1.5" data-field="fullName">
                      <Label className="flex items-center gap-2">
                        <User className="h-4 w-4" />
                        {isRTL ? 'اسم المدير المسؤول' : 'Principal Name'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Input
                        value={principalData.fullName}
                        onChange={(e) => { setPrincipalData({ ...principalData, fullName: e.target.value }); clearFieldError('fullName'); }}
                        placeholder={isRTL ? 'الاسم الكامل' : 'Full Name'}
                        className={errors.fullName ? 'border-red-500' : ''}
                        data-testid="principal-name-input"
                      />
                      {errors.fullName && <p className="text-sm text-red-500 font-medium">{errors.fullName}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="email">
                      <Label className="flex items-center gap-2">
                        <Mail className="h-4 w-4" />
                        {isRTL ? 'البريد الإلكتروني' : 'Email Address'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Input
                        type="email"
                        value={principalData.email}
                        onChange={(e) => { setPrincipalData({ ...principalData, email: e.target.value }); clearFieldError('email'); }}
                        placeholder="principal@school.com"
                        className={errors.email ? 'border-red-500' : ''}
                        dir="ltr"
                        data-testid="principal-email-input"
                      />
                      {errors.email && <p className="text-sm text-red-500 font-medium">{errors.email}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="primaryPhone">
                      <Label className="flex items-center gap-2">
                        <Phone className="h-4 w-4" />
                        {isRTL ? 'رقم التواصل الرئيسي' : 'Primary Phone'}
                        <Badge variant="destructive" className="text-[10px]">{isRTL ? 'إجباري' : 'Required'}</Badge>
                      </Label>
                      <Input
                        value={principalData.primaryPhone}
                        onChange={(e) => { setPrincipalData({ ...principalData, primaryPhone: e.target.value }); clearFieldError('primaryPhone'); }}
                        placeholder="05XXXXXXXX"
                        className={errors.primaryPhone ? 'border-red-500' : ''}
                        dir="ltr"
                        data-testid="principal-phone-input"
                      />
                      {errors.primaryPhone && <p className="text-sm text-red-500 font-medium">{errors.primaryPhone}</p>}
                    </div>

                    <div className="space-y-1.5">
                      <Label className="flex items-center gap-2">
                        <Phone className="h-4 w-4" />
                        {isRTL ? 'رقم تواصل إضافي' : 'Secondary Phone'}
                        <Badge variant="outline" className="text-[10px]">{isRTL ? 'اختياري' : 'Optional'}</Badge>
                      </Label>
                      <Input
                        value={principalData.secondaryPhone}
                        onChange={(e) => setPrincipalData({ ...principalData, secondaryPhone: e.target.value })}
                        placeholder="05XXXXXXXX"
                        dir="ltr"
                        data-testid="principal-secondary-phone-input"
                      />
                    </div>
                  </div>

                  <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
                    <p className="text-sm text-blue-800 mb-1">
                      <Sparkles className="h-4 w-4 inline-block me-2" />
                      {isRTL
                        ? 'سيتم إنشاء كلمة مرور مؤقتة تلقائياً. يجب على المدير تغييرها عند أول تسجيل دخول.'
                        : 'A temporary password will be generated automatically. The principal must change it on first login.'
                      }
                    </p>
                    <div className="flex flex-wrap gap-x-6 gap-y-0.5 text-xs text-blue-700 mt-1">
                      <span>• {isRTL ? 'لا يسمح بتكرار رقم الهاتف' : 'No duplicate phones'}</span>
                      <span>• {isRTL ? 'لا يسمح بتكرار البريد الإلكتروني' : 'No duplicate emails'}</span>
                      <span>• {isRTL ? 'الدور: مدير المدرسة' : 'Role: School Principal'}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Step 4: Review — 3-col compact cards */}
              {currentStep === 4 && (
                <div className="h-full flex flex-col" data-testid="wizard-step-4">
                  <div className="text-center mb-4">
                    <h3 className="font-cairo text-lg font-bold">{isRTL ? 'مراجعة البيانات' : 'Review Information'}</h3>
                    <p className="text-sm text-muted-foreground">{isRTL ? 'راجع جميع البيانات قبل إنشاء المدرسة' : 'Review all information before creating the school'}</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card>
                      <CardHeader className="py-2 px-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-brand-turquoise" />
                          {isRTL ? 'بيانات المدرسة' : 'School Info'}
                          <Button variant="ghost" size="sm" onClick={() => setCurrentStep(1)} className="ms-auto h-5 text-[11px] text-brand-turquoise hover:text-brand-turquoise px-1">
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="px-3 pb-3 space-y-2 text-sm">
                        <div><span className="text-muted-foreground">{isRTL ? 'الاسم:' : 'Name:'}</span> <strong>{schoolData.name}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'الدولة:' : 'Country:'}</span> <strong>{COUNTRIES.find(c => c.code === schoolData.country)?.name}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'المدينة:' : 'City:'}</span> <strong>{schoolData.city}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'العنوان:' : 'Address:'}</span> <strong>{schoolData.address}</strong></div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="py-2 px-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <GraduationCap className="h-4 w-4 text-brand-purple" />
                          {isRTL ? 'الإعدادات' : 'Settings'}
                          <Button variant="ghost" size="sm" onClick={() => setCurrentStep(2)} className="ms-auto h-5 text-[11px] text-brand-turquoise hover:text-brand-turquoise px-1">
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="px-3 pb-3 space-y-2 text-sm">
                        <div><span className="text-muted-foreground">{isRTL ? 'اللغة:' : 'Lang:'}</span> <strong>{settingsData.defaultLanguage === 'ar' ? 'العربية' : 'English'}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'التقويم:' : 'Cal:'}</span> <strong>{CALENDAR_SYSTEMS.find(c => c.value === settingsData.calendarSystem)?.label}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'النوع:' : 'Type:'}</span> <strong>{SCHOOL_TYPES.find(t => t.value === settingsData.schoolType)?.label}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'المرحلة:' : 'Stage:'}</span> <strong>{EDUCATIONAL_STAGES.find(s => s.value === settingsData.educationalStage)?.label}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'التقييم:' : 'Assess:'}</span> <strong>{ASSESSMENT_SYSTEMS.find(a => a.value === settingsData.assessmentSystem)?.label}</strong></div>
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="py-2 px-3">
                        <CardTitle className="text-sm flex items-center gap-2">
                          <User className="h-4 w-4 text-green-500" />
                          {isRTL ? 'المدير' : 'Principal'}
                          <Button variant="ghost" size="sm" onClick={() => setCurrentStep(3)} className="ms-auto h-5 text-[11px] text-brand-turquoise hover:text-brand-turquoise px-1">
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="px-3 pb-3 space-y-2 text-sm">
                        <div><span className="text-muted-foreground">{isRTL ? 'الاسم:' : 'Name:'}</span> <strong>{principalData.fullName}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'الهاتف:' : 'Phone:'}</span> <strong dir="ltr">{principalData.primaryPhone}</strong></div>
                        <div><span className="text-muted-foreground">{isRTL ? 'البريد:' : 'Email:'}</span> <strong dir="ltr" className="break-all">{principalData.email}</strong></div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              )}
            </div>
            
            {/* Footer Actions */}
            <div className="p-4 border-t bg-background flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Button variant="outline" onClick={handleClose} data-testid="cancel-btn">
                    <X className="h-4 w-4 me-2" />
                    {isRTL ? 'إلغاء' : 'Cancel'}
                  </Button>
                  <Button variant="ghost" onClick={handleSaveAsDraft} data-testid="save-draft-btn">
                    <Save className="h-4 w-4 me-2" />
                    {isRTL ? 'حفظ كمسودة' : 'Save Draft'}
                  </Button>
                </div>
                
                <div className="flex items-center gap-2">
                  {currentStep > 1 && (
                    <Button variant="outline" onClick={handlePrevious} data-testid="back-btn">
                      {isRTL ? <ChevronRight className="h-4 w-4 me-2" /> : <ChevronLeft className="h-4 w-4 me-2" />}
                      {isRTL ? 'رجوع' : 'Back'}
                    </Button>
                  )}
                  
                  {currentStep < 4 ? (
                    <Button onClick={handleNext} className="bg-brand-turquoise hover:bg-brand-turquoise/90" data-testid="next-btn">
                      {isRTL ? 'التالي' : 'Next'}
                      {isRTL ? <ChevronLeft className="h-4 w-4 ms-2" /> : <ChevronRight className="h-4 w-4 ms-2" />}
                    </Button>
                  ) : (
                    <Button onClick={handleCreateSchool} disabled={isSubmitting} className="bg-green-600 hover:bg-green-700" data-testid="create-school-btn">
                      {isSubmitting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin me-2" />
                          {isRTL ? 'جاري الإنشاء...' : 'Creating...'}
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="h-4 w-4 me-2" />
                          {isRTL ? 'تأكيد إنشاء المدرسة' : 'Create School'}
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          /* Success Screen */
          <div className="p-8" data-testid="wizard-success-screen">
            <div className="grid md:grid-cols-2 gap-8">
              {/* Left Side - School Info */}
              <div className="space-y-6">
                <div className="text-center md:text-start">
                  <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto md:mx-0 mb-4">
                    <CheckCircle2 className="h-10 w-10 text-green-600" />
                  </div>
                  <h2 className="font-cairo text-2xl font-bold text-green-600 mb-2">
                    {isRTL ? 'تم إنشاء المدرسة بنجاح!' : 'School Created Successfully!'}
                  </h2>
                </div>
                
                <Card>
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">{isRTL ? 'كود المدرسة:' : 'Tenant Code:'}</span>
                      <Badge className="text-lg font-mono bg-brand-navy" data-testid="tenant-code">{createdSchool?.tenant_code}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">{isRTL ? 'اسم المدرسة:' : 'School Name:'}</span>
                      <strong>{createdSchool?.name || schoolData.name}</strong>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">{isRTL ? 'الحالة:' : 'Status:'}</span>
                      <Badge className="bg-green-500">{isRTL ? 'نشطة' : 'Active'}</Badge>
                    </div>
                  </CardContent>
                </Card>
                
                <div className="flex gap-3">
                  <Button className="flex-1" variant="outline" onClick={() => window.open('/school', '_blank')}>
                    <ExternalLink className="h-4 w-4 me-2" />
                    {isRTL ? 'لوحة تحكم المدرسة' : 'School Dashboard'}
                  </Button>
                  <Button variant="default" className="flex-1 bg-brand-turquoise hover:bg-brand-turquoise/90" onClick={handleClose} data-testid="back-to-actions-btn">
                    {isRTL ? 'العودة للإجراءات' : 'Back to Actions'}
                  </Button>
                </div>
              </div>
              
              {/* Right Side - Welcome Message */}
              <div className="space-y-4">
                <h3 className="font-cairo text-lg font-bold flex items-center gap-2">
                  <Mail className="h-5 w-5 text-brand-turquoise" />
                  {isRTL ? 'رسالة الترحيب' : 'Welcome Message'}
                </h3>
                
                <Card className="bg-muted/30">
                  <CardContent className="p-4 text-sm space-y-2" dir={isRTL ? 'rtl' : 'ltr'}>
                    <p className="font-bold">أهلاً بك في منصة نَسَّق المدعومة بالذكاء الاصطناعي.</p>
                    <p>بيانات دخولك على النظام كالتالي:</p>
                    <div className="bg-background rounded-lg p-3 space-y-2 font-mono text-xs">
                      <p><strong>رابط المنصة:</strong><br/>{window.location.origin}</p>
                      <p><strong>البريد الإلكتروني:</strong><br/>{createdSchool?.principal?.email}</p>
                      <p><strong>كلمة المرور المؤقتة:</strong><br/>{createdSchool?.principal?.temp_password}</p>
                      <p><strong>كود المدرسة:</strong><br/>{createdSchool?.tenant_code}</p>
                    </div>
                    <p className="text-muted-foreground">يرجى تغيير كلمة المرور عند أول تسجيل دخول.</p>
                  </CardContent>
                </Card>
                
                <Button onClick={copyWelcomeMessage} className="w-full" variant="outline" data-testid="copy-message-btn">
                  <Copy className="h-4 w-4 me-2" />
                  {isRTL ? 'نسخ رسالة الترحيب' : 'Copy Welcome Message'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
