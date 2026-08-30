import React, { useState, useRef, useCallback } from 'react';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
import { toast } from 'sonner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  Building2, Upload, Globe, MapPin, FileText, Languages, Calendar,
  GraduationCap, Award, User, Phone, Mail, ChevronRight,
  ChevronLeft, Save, X, Copy, ExternalLink, CheckCircle2, Sparkles,
  RotateCcw, ShieldCheck, KeyRound, Edit3, School, Layers, CheckCircle
} from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

// ─── Reference Data & Constants ──────────────────────────────────────────

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

const SAUDI_REGIONS = {
  central: { name: 'المنطقة الوسطى', cities: ['الرياض', 'القصيم', 'حائل'] },
  western: { name: 'المنطقة الغربية', cities: ['جدة', 'مكة المكرمة', 'المدينة المنورة', 'الطائف', 'ينبع'] },
  eastern: { name: 'المنطقة الشرقية', cities: ['الدمام', 'الخبر', 'الظهران', 'الأحساء', 'الجبيل'] },
  northern: { name: 'المنطقة الشمالية', cities: ['تبوك', 'عرعر', 'سكاكا'] },
  southern: { name: 'المنطقة الجنوبية', cities: ['أبها', 'جازان', 'نجران', 'خميس مشيط'] },
};

const ALL_SAUDI_CITIES = Object.values(SAUDI_REGIONS).flatMap((r) => r.cities);

const SCHOOL_TYPES = [
  { value: 'public', label: 'حكومية', label_en: 'Public', desc: 'مدرسة تابعة للتعليم الحكومي العام' },
  { value: 'private', label: 'أهلية', label_en: 'Private', desc: 'مدرسة تابعة لقطاع التعليم الخاص' },
];

const EDUCATIONAL_STAGES = [
  { value: 'primary', label: 'ابتدائية', label_en: 'Primary', desc: 'الصفوف من الأول إلى السادس' },
  { value: 'intermediate', label: 'متوسطة', label_en: 'Intermediate', desc: 'الصفوف من الأول إلى الثالث متوسط' },
  { value: 'secondary_general', label: 'ثانوية عامة', label_en: 'Secondary General', desc: 'المرحلة الثانوية بنظام المقررات' },
  { value: 'secondary_pathways', label: 'ثانوية مسارات', label_en: 'Secondary Pathways', desc: 'المرحلة الثانوية بنظام المسارات التخصصية' },
  { value: 'school_complex', label: 'مجمع مدارس', label_en: 'School Complex', desc: 'مجمع تعليمي يشمل مراحل متعددة' },
];

const EDUCATIONAL_PATHWAYS = [
  { value: 'general', label: 'المسار العام', label_en: 'General Pathway' },
  { value: 'cs_engineering', label: 'مسار علوم الحاسب والهندسة', label_en: 'CS & Engineering Pathway' },
  { value: 'health_life', label: 'مسار الصحة والحياة', label_en: 'Health & Life Pathway' },
  { value: 'business', label: 'مسار إدارة الأعمال', label_en: 'Business Administration Pathway' },
  { value: 'sharia', label: 'المسار الشرعي', label_en: 'Sharia Pathway' },
];

const CALENDAR_SYSTEMS = [
  { value: 'hijri', label: 'هجري', label_en: 'Hijri' },
  { value: 'gregorian', label: 'ميلادي', label_en: 'Gregorian' },
  { value: 'hijri_gregorian', label: 'هجري + ميلادي', label_en: 'Hijri + Gregorian' },
  { value: 'gregorian_hijri', label: 'ميلادي + هجري', label_en: 'Gregorian + Hijri' },
];

const ASSESSMENT_SYSTEMS = [
  { value: 'standard', label: 'النظام القياسي (100 درجة)', label_en: 'Standard (100 points)' },
  { value: 'gpa', label: 'نظام المعدل التراكمي', label_en: 'GPA System' },
  { value: 'competency', label: 'نظام الكفايات', label_en: 'Competency Based' },
];

const generateTempPassword = () => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789@#$';
  let password = '';
  for (let i = 0; i < 12; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return password;
};

const INITIAL_SCHOOL_STATE = {
  name: '',
  logo: null,
  logoPreview: null,
  country: 'SA',
  city: '',
  region: '',
  address: '',
  email: '',
  principal_name: '',
  principal_mobile: '',
};

const INITIAL_SETTINGS_STATE = {
  defaultLanguage: 'ar',
  calendarSystem: 'hijri_gregorian',
  schoolType: 'public',
  educationalStage: 'primary',
  educationalPathway: '',
  assessmentSystem: 'standard',
};

const INITIAL_PRINCIPAL_STATE = {
  fullName: '',
  primaryPhone: '',
  secondaryPhone: '',
  email: '',
};

// ─── High Contrast Badge Components ───────────────────────────────────────

function RequiredBadge({ text = 'إجباري' }) {
  return (
    <span className="text-[11px] font-bold text-rose-700 bg-rose-50 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-300 dark:border-rose-800 px-2 py-0.5 rounded-md leading-none shadow-2xs">
      {text}
    </span>
  );
}

function OptionalBadge({ text = 'اختياري' }) {
  return (
    <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 dark:bg-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700 px-2 py-0.5 rounded-md leading-none">
      {text}
    </span>
  );
}

// ─── Main Wizard Component ───────────────────────────────────────────────

export default function CreateSchoolWizard({ open, onOpenChange, onSuccess, api, isRTL = true }) {
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning } = useNassaqAlert();

  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const formRef = useRef(null);

  // Form States
  const [schoolData, setSchoolData] = useState(INITIAL_SCHOOL_STATE);
  const [settingsData, setSettingsData] = useState(INITIAL_SETTINGS_STATE);
  const [principalData, setPrincipalData] = useState(INITIAL_PRINCIPAL_STATE);
  const [createdSchool, setCreatedSchool] = useState(null);
  const [errors, setErrors] = useState({});

  const clearFieldError = useCallback((field) => {
    setErrors((prev) => {
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

  // ─── Validation Functions ───────────────────────────────────────────────

  const validateStep1 = useCallback(() => {
    const newErrors = {};
    if (!schoolData.name.trim()) newErrors.name = t('schoolNameIsRequired') || 'اسم المدرسة مطلوب';
    if (!schoolData.country) newErrors.country = t('countryIsRequired') || 'الدولة مطلوبة';
    if (!schoolData.city) newErrors.city = t('cityIsRequired') || 'المدينة مطلوبة';
    if (!schoolData.address.trim()) newErrors.address = t('addressIsRequired') || 'العنوان التفصيلي مطلوب';
    if (!(schoolData.principal_mobile || '').trim()) {
      newErrors.principal_mobile = t('principalMobileIsRequired') || 'رقم جوال التواصل مطلوب';
    }
    if (
      schoolData.principal_mobile &&
      !/^05\d{8}$/.test(schoolData.principal_mobile.replace(/\s/g, ''))
    ) {
      newErrors.principal_mobile = t('invalidPhoneMustStartWith0510Digits') || 'رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام';
    }
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
  }, [schoolData, t, isRTL, nassaqWarning, focusFirstError]);

  const validateStep3 = useCallback(() => {
    const newErrors = {};
    if (!principalData.fullName.trim()) newErrors.fullName = t('principalNameIsRequired') || 'اسم المدير مطلوب';
    if (!principalData.primaryPhone.trim()) newErrors.primaryPhone = t('phoneNumberIsRequired') || 'رقم الهاتف مطلوب';
    if (!principalData.email.trim()) newErrors.email = t('emailIsRequired') || 'البريد الإلكتروني مطلوب';

    if (principalData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(principalData.email)) {
      newErrors.email = t('invalidEmailFormat') || 'صيغة البريد الإلكتروني غير صحيحة';
    }

    if (
      principalData.primaryPhone &&
      !/^05\d{8}$/.test(principalData.primaryPhone.replace(/\s/g, ''))
    ) {
      newErrors.primaryPhone = t('invalidPhoneMustStartWith0510Digits') || 'رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام';
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
  }, [principalData, t, isRTL, nassaqWarning, focusFirstError]);

  // ─── Step Navigation ────────────────────────────────────────────────────

  const handleNext = () => {
    if (currentStep === 1 && !validateStep1()) return;
    if (currentStep === 3 && !validateStep3()) return;
    setCurrentStep((prev) => Math.min(prev + 1, 4));
  };

  const handlePrevious = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleLogoUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setSchoolData((prev) => ({ ...prev, logo: file, logoPreview: event.target.result }));
      };
      reader.readAsDataURL(file);
    }
  };

  const resetSettingsToDefault = () => {
    setSettingsData(INITIAL_SETTINGS_STATE);
    toast.success(t('settingsResetToDefault') || 'تمت استعادة الإعدادات للوضع الافتراضي');
  };

  const resetWizard = useCallback(() => {
    setCurrentStep(1);
    setIsComplete(false);
    setCreatedSchool(null);
    setSchoolData(INITIAL_SCHOOL_STATE);
    setSettingsData(INITIAL_SETTINGS_STATE);
    setPrincipalData(INITIAL_PRINCIPAL_STATE);
    setErrors({});
  }, []);

  const handleClose = useCallback(() => {
    resetWizard();
    onOpenChange(false);
  }, [resetWizard, onOpenChange]);

  // ─── Save as Draft ──────────────────────────────────────────────────────

  const handleSaveAsDraft = async () => {
    setIsSubmitting(true);
    try {
      const schoolPayload = {
        name: schoolData.name || t('draftSchool'),
        country: schoolData.country || 'SA',
        city: schoolData.city || '',
        region: schoolData.region || '',
        address: schoolData.address || '',
        language: settingsData.defaultLanguage,
        calendar_system: settingsData.calendarSystem,
        school_type: settingsData.schoolType,
        stage: settingsData.educationalStage,
        educational_pathway:
          settingsData.educationalStage === 'secondary_pathways'
            ? settingsData.educationalPathway
            : '',
        principal_name: schoolData.principal_name || principalData.fullName || '',
        principal_phone: principalData.primaryPhone || '',
        principal_mobile: schoolData.principal_mobile || '',
        status: 'setup',
      };
      if (schoolData.email && schoolData.email.trim()) schoolPayload.email = schoolData.email.trim();
      if (principalData.email && principalData.email.trim()) {
        schoolPayload.principal_email = principalData.email.trim();
      }

      const response = await api.post('/schools/draft', schoolPayload);
      toast.success(t('schoolSavedAsDraftFindItInTheDraftsSection') || 'تم حفظ المدرسة كمسودة');

      if (onSuccess) onSuccess(response.data);
      handleClose();
    } catch (error) {
      console.error('Error saving draft:', error);
      const rawDetail = getApiErrorMessage(error) || '';
      nassaqError(rawDetail || t('failedToSaveDraftPleaseTryAgain') || 'فشل حفظ المسودة، يرجى المحاولة لاحقاً');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Create School (Final Step) ─────────────────────────────────────────

  const handleCreateSchool = async () => {
    if (!validateStep3()) {
      setCurrentStep(3);
      return;
    }

    setIsSubmitting(true);
    try {
      const tempPassword = generateTempPassword();

      const schoolPayload = {
        name: schoolData.name,
        country: schoolData.country,
        city: schoolData.city,
        region: schoolData.region,
        address: schoolData.address,
        language: settingsData.defaultLanguage,
        calendar_system: settingsData.calendarSystem,
        school_type: settingsData.schoolType,
        stage: settingsData.educationalStage,
        educational_pathway:
          settingsData.educationalStage === 'secondary_pathways'
            ? settingsData.educationalPathway
            : '',
        principal_name: schoolData.principal_name || principalData.fullName,
        principal_email: principalData.email,
        principal_phone: principalData.primaryPhone,
        principal_mobile: schoolData.principal_mobile,
      };
      if (schoolData.email && schoolData.email.trim()) schoolPayload.email = schoolData.email.trim();

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
      toast.success(t('schoolCreatedSuccessfully') || 'تم إنشاء المدرسة بنجاح');

      if (onSuccess) onSuccess(response.data);
    } catch (error) {
      console.error('Error creating school:', error);
      const rawDetail = getApiErrorMessage(error) || '';

      const codeConflictEntry = {
        step: 1,
        field: 'name',
        userMsg: t('schoolCodeConflictPleaseTryAgain') || 'رمز المدرسة مستخدم مسبقاً، يرجى اختيار اسم آخر',
        fieldMsg: t('schoolCodeConflictPleaseTryAgain2') || 'رمز المدرسة مستخدم مسبقاً',
      };

      const BACKEND_ERROR_MAP = {
        'رمز المدرسة مستخدم مسبقاً': codeConflictEntry,
        'رمز المدرسة مستخدم مسبقاً — يُرجى اختيار رمز آخر': codeConflictEntry,
        'البريد الإلكتروني مستخدم مسبقاً': {
          step: 3,
          field: 'email',
          userMsg: t('thisEmailIsAlreadyRegisteredPleaseChangeItInThePri') || 'البريد الإلكتروني مستخدم مسبقاً',
          fieldMsg: t('thisEmailIsAlreadyRegistered') || 'البريد الإلكتروني مستخدم مسبقاً',
        },
        'رقم الهاتف مستخدم مسبقاً': {
          step: 3,
          field: 'primaryPhone',
          userMsg: t('thisPhoneNumberIsAlreadyRegisteredPleaseChangeItIn') || 'رقم الهاتف مستخدم مسبقاً',
          fieldMsg: t('thisPhoneNumberIsAlreadyRegistered') || 'رقم الهاتف مستخدم مسبقاً',
        },
      };

      const mapped = BACKEND_ERROR_MAP[rawDetail];
      if (mapped) {
        setErrors((prev) => ({ ...prev, [mapped.field]: mapped.fieldMsg }));
        setCurrentStep(mapped.step);
        nassaqError(mapped.userMsg);
        setTimeout(() => focusFirstError([mapped.field]), 200);
      } else {
        const fallback = rawDetail || t('errorCreatingSchoolPleaseTryAgain') || 'حدث خطأ أثناء إنشاء المدرسة';
        nassaqError(fallback);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Copy Welcome Message ───────────────────────────────────────────────

  const copyWelcomeMessage = () => {
    const message = `أهلاً بك في منصة نَسَّق لإدارة التعليم والمدارس الذكية.

بيانات دخول حساب إدارة المدرسة:
━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 رابط المنصة: ${window.location.origin}
📧 البريد الإلكتروني: ${createdSchool?.principal?.email}
🔑 كلمة المرور المؤقتة: ${createdSchool?.principal?.temp_password}
🏫 كود المدرسة: ${createdSchool?.tenant_code}
━━━━━━━━━━━━━━━━━━━━━━━━━━

* يرجى تغيير كلمة المرور عند أول تسجيل دخول لضمان أمان الحساب.`;

    navigator.clipboard.writeText(message);
    toast.success(t('welcomeMessageCopied') || 'تم نسخ الرسالة الترحيبية');
  };

  // Steps Configuration
  const steps = [
    { number: 1, title: 'بيانات المدرسة', icon: Building2 },
    { number: 2, title: 'إعدادات التشغيل', icon: GraduationCap },
    { number: 3, title: 'مدير المدرسة', icon: User },
    { number: 4, title: 'مراجعة وتأكيد', icon: CheckCircle },
  ];

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        className="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl rounded-3xl"
        data-testid="create-school-wizard"
      >
        {!isComplete ? (
          <>
            {/* Header with Steps Bar */}
            <DialogHeader className="px-6 py-5 border-b border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-[#1C3D74] flex items-center justify-center shadow-md shadow-[#1C3D74]/20 text-white">
                    <School className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <DialogTitle className="font-cairo text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                      {isRTL ? 'إنشاء مدرسة جديدة' : 'Create New School'}
                    </DialogTitle>
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-0.5">
                      {isRTL ? 'إعداد وتهيئة مستأجر جديد في منظومة نَسَّق المدرسية' : 'Onboard a new school tenant in NASSAQ ecosystem'}
                    </p>
                  </div>
                </div>

                <Badge variant="outline" className="hidden sm:flex items-center gap-1.5 py-1 px-3 bg-slate-50 dark:bg-slate-800 border-slate-300 dark:border-slate-700 text-xs font-bold text-slate-800 dark:text-slate-200 rounded-full shadow-2xs">
                  <Layers className="h-3.5 w-3.5 text-[#00C5B2]" />
                  <span>{isRTL ? `الخطوة ${currentStep} من 4` : `Step ${currentStep} of 4`}</span>
                </Badge>
              </div>

              {/* Progress Steps Indicator */}
              <div className="flex items-center justify-between max-w-3xl mx-auto w-full px-2 pt-2 pb-1">
                {steps.map((step, idx) => {
                  const isActive = currentStep === step.number;
                  const isPassed = currentStep > step.number;
                  const Icon = step.icon;
                  const isLast = idx === steps.length - 1;

                  return (
                    <React.Fragment key={step.number}>
                      {/* Step Node */}
                      <button
                        type="button"
                        disabled={!isPassed && !isActive}
                        onClick={() => {
                          if (isPassed) setCurrentStep(step.number);
                        }}
                        className={`flex flex-col items-center group focus:outline-none z-10 shrink-0 ${
                          isPassed ? 'cursor-pointer' : 'cursor-default'
                        }`}
                      >
                        <div
                          className={`w-11 h-11 rounded-2xl flex items-center justify-center transition-all duration-300 ${
                            isActive
                              ? 'bg-[#1C3D74] text-white ring-4 ring-[#00C5B2]/30 scale-105 shadow-lg shadow-[#1C3D74]/25'
                              : isPassed
                              ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                              : 'bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-600 text-slate-500 dark:text-slate-400'
                          }`}
                        >
                          {isPassed ? (
                            <CheckCircle2 className="h-5 w-5 text-white stroke-[2.5]" />
                          ) : (
                            <Icon className="h-5 w-5" />
                          )}
                        </div>
                        <span
                          className={`text-xs mt-2.5 transition-colors whitespace-nowrap ${
                            isActive
                              ? 'font-black text-[#1C3D74] dark:text-[#00C5B2]'
                              : isPassed
                              ? 'font-bold text-emerald-700 dark:text-emerald-400'
                              : 'font-bold text-slate-500 dark:text-slate-400'
                          }`}
                        >
                          {step.title}
                        </span>
                      </button>

                      {/* Segmented Connector Line */}
                      {!isLast && (
                        <div className="flex-1 mx-3 -mt-6 h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                          <div
                            className={`h-full transition-all duration-500 ease-out rounded-full ${
                              currentStep > step.number
                                ? 'w-full bg-emerald-500'
                                : 'w-0 bg-transparent'
                            }`}
                          />
                        </div>
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </DialogHeader>

            {/* Scrollable Content */}
            <div className="flex-1 min-h-0 p-6 md:px-8 md:py-6 overflow-y-auto bg-slate-50 dark:bg-slate-900" ref={formRef}>
              {/* ── Step 1: School Profile ──────────────────────────────── */}
              {currentStep === 1 && (
                <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300" data-testid="wizard-step-1">
                  <div className="mb-6 text-start">
                    <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
                      <Building2 className="h-5 w-5 text-[#00C5B2]" />
                      {isRTL ? 'بيانات المدرسة الأساسية' : 'Basic School Information'}
                    </h3>
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">
                      {isRTL ? 'أدخل المعلومات الأساسية والموقع الجغرافي للمدرسة' : 'Enter the basic school information and physical location'}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-12 gap-6 mb-5">
                    {/* Logo Upload Card */}
                    <div className="md:col-span-4 flex flex-col items-center justify-center p-5 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                      <div className="relative group w-28 h-28 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-[#00C5B2] hover:bg-[#00C5B2]/5 flex items-center justify-center overflow-hidden transition-all duration-200 bg-slate-50 dark:bg-slate-800/80">
                        {schoolData.logoPreview ? (
                          <img src={schoolData.logoPreview} alt="School Logo" className="w-full h-full object-cover" />
                        ) : (
                          <div className="text-center p-3">
                            <Upload className="h-7 w-7 mx-auto text-slate-500 group-hover:text-[#00C5B2] mb-1.5 transition-colors" />
                            <span className="text-xs font-bold text-slate-700 dark:text-slate-200 block">{isRTL ? 'رفع الشعار' : 'Upload Logo'}</span>
                          </div>
                        )}
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleLogoUpload}
                          className="absolute inset-0 opacity-0 cursor-pointer"
                          data-testid="logo-upload"
                        />
                      </div>
                      <div className="mt-3 flex items-center gap-1.5">
                        <OptionalBadge text="اختياري" />
                        <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">PNG, JPG (Max 2MB)</span>
                      </div>
                    </div>

                    {/* School Name & Primary Details */}
                    <div className="md:col-span-8 space-y-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                      <div className="space-y-1.5" data-field="name">
                        <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <Building2 className="h-3.5 w-3.5 text-[#1C3D74] dark:text-[#00C5B2]" />
                            {isRTL ? 'اسم المدرسة' : 'School Name'}
                          </span>
                          <RequiredBadge text="إجباري" />
                        </Label>
                        <Input
                          value={schoolData.name}
                          onChange={(e) => {
                            setSchoolData({ ...schoolData, name: e.target.value });
                            clearFieldError('name');
                          }}
                          placeholder={isRTL ? 'مثال: مدرسة النور الأهلية' : 'e.g. Al-Noor Private School'}
                          className={`h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 transition-all focus:ring-2 focus:ring-[#00C5B2]/20 focus:border-[#00C5B2] ${
                            errors.name ? 'border-rose-500 bg-rose-50/20' : 'border-slate-300 dark:border-slate-700'
                          }`}
                          data-testid="school-name-input"
                        />
                        {errors.name && <p className="text-xs text-rose-600 font-bold">{errors.name}</p>}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-1.5" data-field="country">
                          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                            <span className="flex items-center gap-1.5">
                              <Globe className="h-3.5 w-3.5 text-[#00C5B2]" />
                              {isRTL ? 'الدولة' : 'Country'}
                            </span>
                            <RequiredBadge text="إجباري" />
                          </Label>
                          <Select
                            value={schoolData.country}
                            onValueChange={(v) => {
                              setSchoolData({ ...schoolData, country: v, city: '' });
                              clearFieldError('country');
                            }}
                          >
                            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="country-select">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                              {COUNTRIES.map((country) => (
                                <SelectItem key={country.code} value={country.code} className="font-medium text-slate-900 dark:text-slate-100">
                                  {isRTL ? country.name : country.name_en}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          {errors.country && <p className="text-xs text-rose-600 font-bold">{errors.country}</p>}
                        </div>

                        <div className="space-y-1.5" data-field="city">
                          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                            <span className="flex items-center gap-1.5">
                              <MapPin className="h-3.5 w-3.5 text-[#00C5B2]" />
                              {isRTL ? 'المدينة' : 'City'}
                            </span>
                            <RequiredBadge text="إجباري" />
                          </Label>
                          <Select
                            value={schoolData.city}
                            onValueChange={(v) => {
                              setSchoolData({ ...schoolData, city: v });
                              clearFieldError('city');
                            }}
                          >
                            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="city-select">
                              <SelectValue placeholder={isRTL ? 'اختر المدينة' : 'Select City'} />
                            </SelectTrigger>
                            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                              {schoolData.country === 'SA' ? (
                                ALL_SAUDI_CITIES.map((city) => (
                                  <SelectItem key={city} value={city} className="font-medium text-slate-900 dark:text-slate-100">
                                    {city}
                                  </SelectItem>
                                ))
                              ) : (
                                <SelectItem value="other" className="font-medium text-slate-900 dark:text-slate-100">{isRTL ? 'أخرى' : 'Other'}</SelectItem>
                              )}
                            </SelectContent>
                          </Select>
                          {errors.city && <p className="text-xs text-rose-600 font-bold">{errors.city}</p>}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                    <div className="space-y-1.5" data-field="address">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 text-[#00C5B2]" />
                          {isRTL ? 'العنوان التفصيلي' : 'Address'}
                        </span>
                        <RequiredBadge text="إجباري" />
                      </Label>
                      <Input
                        value={schoolData.address}
                        onChange={(e) => {
                          setSchoolData({ ...schoolData, address: e.target.value });
                          clearFieldError('address');
                        }}
                        placeholder={isRTL ? 'الحي، الشارع، رقم المبنى...' : 'District, Street, Building No...'}
                        className={`h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 ${
                          errors.address ? 'border-rose-500 bg-rose-50/20' : 'border-slate-300 dark:border-slate-700'
                        }`}
                        data-testid="address-input"
                      />
                      {errors.address && <p className="text-xs text-rose-600 font-bold">{errors.address}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="region">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <MapPin className="h-3.5 w-3.5 text-slate-500" />
                          {isRTL ? 'المنطقة الإدارية' : 'Administrative Region'}
                        </span>
                        <OptionalBadge text="اختياري" />
                      </Label>
                      <Input
                        value={schoolData.region}
                        onChange={(e) => setSchoolData({ ...schoolData, region: e.target.value })}
                        placeholder={isRTL ? 'مثال: منطقة الرياض' : 'e.g. Riyadh Region'}
                        className="h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 border-slate-300 dark:border-slate-700"
                        data-testid="region-input"
                      />
                    </div>

                    <div className="space-y-1.5" data-field="email">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Mail className="h-3.5 w-3.5 text-slate-500" />
                          {isRTL ? 'البريد الرسمي للمدرسة' : 'School Official Email'}
                        </span>
                        <OptionalBadge text="اختياري" />
                      </Label>
                      <Input
                        type="email"
                        value={schoolData.email}
                        onChange={(e) => setSchoolData({ ...schoolData, email: e.target.value })}
                        placeholder="info@school.edu.sa"
                        dir="ltr"
                        className="h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 border-slate-300 dark:border-slate-700"
                        data-testid="school-email-input"
                      />
                    </div>

                    <div className="space-y-1.5" data-field="principal_mobile">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Phone className="h-3.5 w-3.5 text-[#00C5B2]" />
                          {isRTL ? 'رقم جوال التواصل المعتمد' : 'Primary Mobile'}
                        </span>
                        <RequiredBadge text="إجباري" />
                      </Label>
                      <Input
                        value={schoolData.principal_mobile}
                        onChange={(e) => {
                          setSchoolData({ ...schoolData, principal_mobile: e.target.value });
                          clearFieldError('principal_mobile');
                        }}
                        placeholder="05XXXXXXXX"
                        dir="ltr"
                        className={`h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 ${
                          errors.principal_mobile ? 'border-rose-500 bg-rose-50/20' : 'border-slate-300 dark:border-slate-700'
                        }`}
                        data-testid="school-principal-mobile-input"
                      />
                      {errors.principal_mobile && <p className="text-xs text-rose-600 font-bold">{errors.principal_mobile}</p>}
                    </div>
                  </div>
                </div>
              )}

              {/* ── Step 2: Operating Settings ──────────────────────────── */}
              {currentStep === 2 && (
                <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300" data-testid="wizard-step-2">
                  <div className="mb-6 text-start">
                    <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
                      <GraduationCap className="h-5 w-5 text-[#00C5B2]" />
                      {isRTL ? 'إعدادات التشغيل والنظام المدرسي' : 'School Operating Settings'}
                    </h3>
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">
                      {isRTL ? 'حدد التقويم والمرحلة ونظام التقييم المعتمد للمدرسة' : 'Set the calendar, educational stage, and grading system'}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
                    {/* Language */}
                    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                        <Languages className="h-4 w-4 text-[#00C5B2]" />
                        {isRTL ? 'اللغة الافتراضية' : 'Default Language'}
                      </Label>
                      <Select
                        value={settingsData.defaultLanguage}
                        onValueChange={(v) => setSettingsData({ ...settingsData, defaultLanguage: v })}
                      >
                        <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="language-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                          <SelectItem value="ar" className="font-medium text-slate-900 dark:text-slate-100">العربية (RTL)</SelectItem>
                          <SelectItem value="en" className="font-medium text-slate-900 dark:text-slate-100">English (LTR)</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
                        {isRTL ? 'يمكن لكل مستخدم تخصيص لغته لاحقاً' : 'Each user can customize language later'}
                      </p>
                    </div>

                    {/* Calendar System */}
                    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                        <Calendar className="h-4 w-4 text-[#00C5B2]" />
                        {isRTL ? 'نظام التقويم' : 'Calendar System'}
                      </Label>
                      <Select
                        value={settingsData.calendarSystem}
                        onValueChange={(v) => setSettingsData({ ...settingsData, calendarSystem: v })}
                      >
                        <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="calendar-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                          {CALENDAR_SYSTEMS.map((cal) => (
                            <SelectItem key={cal.value} value={cal.value} className="font-medium text-slate-900 dark:text-slate-100">
                              {isRTL ? cal.label : cal.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
                        {isRTL ? 'التقويم الأساسي لحساب التواريخ المدرسية' : 'Primary calendar for school dates'}
                      </p>
                    </div>

                    {/* School Type */}
                    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                        <Building2 className="h-4 w-4 text-[#00C5B2]" />
                        {isRTL ? 'نوع المدرسة' : 'School Type'}
                      </Label>
                      <Select
                        value={settingsData.schoolType}
                        onValueChange={(v) => setSettingsData({ ...settingsData, schoolType: v })}
                      >
                        <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="school-type-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                          {SCHOOL_TYPES.map((type) => (
                            <SelectItem key={type.value} value={type.value} className="font-medium text-slate-900 dark:text-slate-100">
                              {isRTL ? type.label : type.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
                        {isRTL ? 'حكومية أو أهلية معتمدة' : 'Public or accredited private'}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
                    {/* Educational Stage */}
                    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                        <GraduationCap className="h-4 w-4 text-[#1C3D74] dark:text-[#00C5B2]" />
                        {isRTL ? 'المرحلة التعليمية' : 'Educational Stage'}
                      </Label>
                      <Select
                        value={settingsData.educationalStage}
                        onValueChange={(v) =>
                          setSettingsData({
                            ...settingsData,
                            educationalStage: v,
                            educationalPathway: v === 'secondary_pathways' ? settingsData.educationalPathway : '',
                          })
                        }
                      >
                        <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="stage-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                          {EDUCATIONAL_STAGES.map((stage) => (
                            <SelectItem key={stage.value} value={stage.value} className="font-medium text-slate-900 dark:text-slate-100">
                              {isRTL ? stage.label : stage.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
                        {isRTL ? 'تحدد الكتالوج الافتراضي للمواد الدراسية' : 'Determines default subjects catalog'}
                      </p>
                    </div>

                    {/* Assessment System */}
                    <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                        <Award className="h-4 w-4 text-[#1C3D74] dark:text-[#00C5B2]" />
                        {isRTL ? 'نظام التقييم والدرجات' : 'Assessment System'}
                      </Label>
                      <Select
                        value={settingsData.assessmentSystem}
                        onValueChange={(v) => setSettingsData({ ...settingsData, assessmentSystem: v })}
                      >
                        <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="assessment-select">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                          {ASSESSMENT_SYSTEMS.map((sys) => (
                            <SelectItem key={sys.value} value={sys.value} className="font-medium text-slate-900 dark:text-slate-100">
                              {isRTL ? sys.label : sys.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
                        {isRTL ? 'يرتبط بقواعد الاختبارات وحساب المعدلات' : 'Linked to tests & GPA rules'}
                      </p>
                    </div>
                  </div>

                  {/* Secondary Pathways Option */}
                  {settingsData.educationalStage === 'secondary_pathways' && (
                    <div className="mb-5 p-5 bg-indigo-50/70 dark:bg-slate-900 rounded-2xl border border-indigo-200 dark:border-indigo-900/60 shadow-sm animate-in fade-in-30 duration-200 space-y-2">
                      <Label className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                        <Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                        {isRTL ? 'المسار التخصصي للمرحلة الثانوية' : 'Secondary Educational Pathway'}
                      </Label>
                      <Select
                        value={settingsData.educationalPathway}
                        onValueChange={(v) => setSettingsData({ ...settingsData, educationalPathway: v })}
                      >
                        <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-300 dark:border-slate-700" data-testid="pathway-select">
                          <SelectValue placeholder={isRTL ? 'اختر المسار التخصصي...' : 'Select educational pathway...'} />
                        </SelectTrigger>
                        <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                          {EDUCATIONAL_PATHWAYS.map((pathway) => (
                            <SelectItem key={pathway.value} value={pathway.value} className="font-medium text-slate-900 dark:text-slate-100">
                              {isRTL ? pathway.label : pathway.label_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="flex justify-center pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={resetSettingsToDefault}
                      className="text-xs font-bold text-slate-700 dark:text-slate-200 border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50"
                    >
                      <RotateCcw className="h-3.5 w-3.5 me-1.5 text-slate-500" />
                      {isRTL ? 'استعادة الإعدادات الافتراضية' : 'Reset to Defaults'}
                    </Button>
                  </div>
                </div>
              )}

              {/* ── Step 3: Principal Account ───────────────────────────── */}
              {currentStep === 3 && (
                <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300" data-testid="wizard-step-3">
                  <div className="mb-6 text-start">
                    <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
                      <User className="h-5 w-5 text-[#00C5B2]" />
                      {isRTL ? 'إنشاء حساب مدير المدرسة' : 'Create School Principal Account'}
                    </h3>
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">
                      {isRTL ? 'أدخل البيانات الرسمية للمدير لإنشاء الحساب وتوليد بيانات الدخول' : 'Enter principal official credentials for account creation'}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                    <div className="space-y-1.5" data-field="fullName">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <User className="h-3.5 w-3.5 text-[#00C5B2]" />
                          {isRTL ? 'اسم مدير المدرسة' : 'Principal Name'}
                        </span>
                        <RequiredBadge text="إجباري" />
                      </Label>
                      <Input
                        value={principalData.fullName}
                        onChange={(e) => {
                          setPrincipalData({ ...principalData, fullName: e.target.value });
                          clearFieldError('fullName');
                        }}
                        placeholder={isRTL ? 'الاسم الثلاثي لمدير المدرسة' : 'Principal full name'}
                        className={`h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 ${
                          errors.fullName ? 'border-rose-500 bg-rose-50/20' : 'border-slate-300 dark:border-slate-700'
                        }`}
                        data-testid="principal-name-input"
                      />
                      {errors.fullName && <p className="text-xs text-rose-600 font-bold">{errors.fullName}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="email">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Mail className="h-3.5 w-3.5 text-[#00C5B2]" />
                          {isRTL ? 'البريد الإلكتروني (اسم المستخدم)' : 'Official Email (Username)'}
                        </span>
                        <RequiredBadge text="إجباري" />
                      </Label>
                      <Input
                        type="email"
                        value={principalData.email}
                        onChange={(e) => {
                          setPrincipalData({ ...principalData, email: e.target.value });
                          clearFieldError('email');
                        }}
                        placeholder="principal@school.edu.sa"
                        className={`h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 ${
                          errors.email ? 'border-rose-500 bg-rose-50/20' : 'border-slate-300 dark:border-slate-700'
                        }`}
                        dir="ltr"
                        data-testid="principal-email-input"
                      />
                      {errors.email && <p className="text-xs text-rose-600 font-bold">{errors.email}</p>}
                    </div>

                    <div className="space-y-1.5" data-field="primaryPhone">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Phone className="h-3.5 w-3.5 text-[#00C5B2]" />
                          {isRTL ? 'رقم الهاتف الأساسي' : 'Primary Phone'}
                        </span>
                        <RequiredBadge text="إجباري" />
                      </Label>
                      <Input
                        value={principalData.primaryPhone}
                        onChange={(e) => {
                          setPrincipalData({ ...principalData, primaryPhone: e.target.value });
                          clearFieldError('primaryPhone');
                        }}
                        placeholder="05XXXXXXXX"
                        className={`h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 ${
                          errors.primaryPhone ? 'border-rose-500 bg-rose-50/20' : 'border-slate-300 dark:border-slate-700'
                        }`}
                        dir="ltr"
                        data-testid="principal-phone-input"
                      />
                      {errors.primaryPhone && <p className="text-xs text-rose-600 font-bold">{errors.primaryPhone}</p>}
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                        <span className="flex items-center gap-1.5">
                          <Phone className="h-3.5 w-3.5 text-slate-500" />
                          {isRTL ? 'رقم هاتف إضافي' : 'Secondary Phone'}
                        </span>
                        <OptionalBadge text="اختياري" />
                      </Label>
                      <Input
                        value={principalData.secondaryPhone}
                        onChange={(e) => setPrincipalData({ ...principalData, secondaryPhone: e.target.value })}
                        placeholder="05XXXXXXXX"
                        className="h-11 rounded-xl text-sm font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 border-slate-300 dark:border-slate-700"
                        dir="ltr"
                        data-testid="principal-secondary-phone-input"
                      />
                    </div>
                  </div>

                  {/* Security & Credentials Info Box */}
                  <div className="bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 rounded-2xl p-4 flex items-start gap-3.5 shadow-sm">
                    <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-xs">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div className="space-y-1 text-xs">
                      <p className="font-bold text-blue-950 dark:text-blue-200">
                        {isRTL ? 'سيتم توليد كلمة مرور مؤقتة وتفعيل الحساب تلقائياً' : 'A temporary password will be generated automatically'}
                      </p>
                      <div className="flex flex-wrap gap-x-5 gap-y-1 text-blue-800 dark:text-blue-300 font-semibold">
                        <span>• {isRTL ? 'التحقق من عدم تكرار أرقام الهواتف' : 'No duplicate phone numbers'}</span>
                        <span>• {isRTL ? 'التحقق من تفرد البريد الإلكتروني' : 'No duplicate emails'}</span>
                        <span>• {isRTL ? 'منح صلاحية مدير المدرسة للمستأجر' : 'Principal role assigned'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── Step 4: Review & Confirmation ───────────────────────── */}
              {currentStep === 4 && (
                <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300" data-testid="wizard-step-4">
                  <div className="mb-6 text-start">
                    <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                      {isRTL ? 'مراجعة وتأكيد البيانات' : 'Review & Confirm'}
                    </h3>
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">
                      {isRTL ? 'يرجى مراجعة كافة بيانات المدرسة قبل تأكيد عملية الإنشاء' : 'Please review all details before creating the school'}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    {/* School Profile Summary Card */}
                    <Card className="bg-white dark:bg-slate-900 rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                      <CardHeader className="py-3 px-4 bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700">
                        <CardTitle className="text-xs font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
                          <span className="flex items-center gap-1.5">
                            <Building2 className="h-4 w-4 text-[#00C5B2]" />
                            {isRTL ? 'بيانات المدرسة' : 'School Info'}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setCurrentStep(1)}
                            className="h-6 text-[11px] font-bold text-[#1C3D74] dark:text-[#00C5B2] hover:bg-slate-100 px-2 rounded-lg"
                          >
                            <Edit3 className="h-3 w-3 me-1" />
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2.5 text-xs">
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الاسم:' : 'Name:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-bold">{schoolData.name}</strong>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الدولة:' : 'Country:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{COUNTRIES.find((c) => c.code === schoolData.country)?.name}</strong>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'المدينة:' : 'City:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{schoolData.city}</strong>
                        </div>
                        <div className="flex justify-between py-1">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'العنوان:' : 'Address:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold truncate max-w-[140px]">{schoolData.address}</strong>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Operating Settings Summary Card */}
                    <Card className="bg-white dark:bg-slate-900 rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                      <CardHeader className="py-3 px-4 bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700">
                        <CardTitle className="text-xs font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
                          <span className="flex items-center gap-1.5">
                            <GraduationCap className="h-4 w-4 text-[#1C3D74] dark:text-[#00C5B2]" />
                            {isRTL ? 'إعدادات التشغيل' : 'Settings'}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setCurrentStep(2)}
                            className="h-6 text-[11px] font-bold text-[#1C3D74] dark:text-[#00C5B2] hover:bg-slate-100 px-2 rounded-lg"
                          >
                            <Edit3 className="h-3 w-3 me-1" />
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2.5 text-xs">
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'اللغة:' : 'Language:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{settingsData.defaultLanguage === 'ar' ? 'العربية' : 'English'}</strong>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'التقويم:' : 'Calendar:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{CALENDAR_SYSTEMS.find((c) => c.value === settingsData.calendarSystem)?.label}</strong>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'النوع:' : 'Type:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{SCHOOL_TYPES.find((st) => st.value === settingsData.schoolType)?.label}</strong>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'المرحلة:' : 'Stage:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{EDUCATIONAL_STAGES.find((s) => s.value === settingsData.educationalStage)?.label}</strong>
                        </div>
                        <div className="flex justify-between py-1">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'التقييم:' : 'Assessment:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-semibold">{ASSESSMENT_SYSTEMS.find((a) => a.value === settingsData.assessmentSystem)?.label}</strong>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Principal Account Summary Card */}
                    <Card className="bg-white dark:bg-slate-900 rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                      <CardHeader className="py-3 px-4 bg-slate-50 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-700">
                        <CardTitle className="text-xs font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
                          <span className="flex items-center gap-1.5">
                            <User className="h-4 w-4 text-emerald-600" />
                            {isRTL ? 'مدير المدرسة' : 'Principal'}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setCurrentStep(3)}
                            className="h-6 text-[11px] font-bold text-[#1C3D74] dark:text-[#00C5B2] hover:bg-slate-100 px-2 rounded-lg"
                          >
                            <Edit3 className="h-3 w-3 me-1" />
                            {isRTL ? 'تعديل' : 'Edit'}
                          </Button>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-4 space-y-2.5 text-xs">
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الاسم:' : 'Name:'}</span>
                          <strong className="text-slate-900 dark:text-slate-100 font-bold">{principalData.fullName}</strong>
                        </div>
                        <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الهاتف:' : 'Phone:'}</span>
                          <strong dir="ltr" className="text-slate-900 dark:text-slate-100 font-mono font-semibold">{principalData.primaryPhone}</strong>
                        </div>
                        <div className="flex justify-between py-1">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'البريد:' : 'Email:'}</span>
                          <strong dir="ltr" className="text-slate-900 dark:text-slate-100 font-mono font-semibold truncate max-w-[140px]">{principalData.email}</strong>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="px-6 py-4 md:px-8 border-t border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleClose}
                    data-testid="cancel-btn"
                    className="h-10 px-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white hover:bg-rose-50 dark:bg-slate-800 dark:hover:bg-rose-950/40 text-slate-600 hover:text-rose-600 dark:text-slate-300 dark:hover:text-rose-400 text-xs font-bold shadow-2xs gap-1.5 transition-all hover:border-rose-200 dark:hover:border-rose-800"
                  >
                    <X className="h-4 w-4 text-slate-500 hover:text-rose-600" />
                    <span>{isRTL ? 'إلغاء' : 'Cancel'}</span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleSaveAsDraft}
                    disabled={isSubmitting}
                    data-testid="save-draft-btn"
                    className="h-10 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-white hover:bg-slate-50 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold shadow-2xs gap-2 transition-all hover:border-slate-400"
                  >
                    <Save className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                    <span>{isRTL ? 'حفظ كمسودة' : 'Save Draft'}</span>
                  </Button>
                </div>

                <div className="flex items-center gap-2.5">
                  {currentStep > 1 && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handlePrevious}
                      data-testid="back-btn"
                      className="h-10 px-5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white hover:bg-slate-50 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold gap-1.5 transition-all"
                    >
                      {isRTL ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                      <span>{isRTL ? 'السابق' : 'Back'}</span>
                    </Button>
                  )}

                  {currentStep < 4 ? (
                    <Button
                      type="button"
                      onClick={handleNext}
                      className="h-10 px-7 rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white text-xs font-extrabold shadow-md shadow-[#1C3D74]/20 gap-1.5 transition-all"
                      data-testid="next-btn"
                    >
                      <span>{isRTL ? 'التالي' : 'Next'}</span>
                      {isRTL ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      onClick={handleCreateSchool}
                      disabled={isSubmitting}
                      className="h-10 px-7 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-extrabold shadow-lg shadow-emerald-600/25 gap-1.5 transition-all"
                      data-testid="create-school-btn"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>{isRTL ? 'جاري الإنشاء...' : 'Creating...'}</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="h-4 w-4" />
                          <span>{isRTL ? 'إنشاء المدرسة' : 'Create School'}</span>
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </>
        ) : (
          /* ── Success Screen ────────────────────────────────────────── */
          <div className="p-8 md:p-10 flex-1 flex flex-col justify-center animate-in zoom-in-95 duration-400 bg-white dark:bg-slate-900" data-testid="wizard-success-screen">
            <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto items-center w-full">
              {/* Left Side — Celebratory Status */}
              <div className="space-y-6 text-center md:text-start">
                <div>
                  <div className="w-20 h-20 rounded-3xl bg-emerald-50 dark:bg-emerald-950/60 border-2 border-emerald-500/30 flex items-center justify-center mx-auto md:mx-0 mb-4 shadow-xl shadow-emerald-500/10">
                    <CheckCircle2 className="h-10 w-10 text-emerald-600" />
                  </div>
                  <h2 className="font-cairo text-2xl md:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                    {isRTL ? 'تم إنشاء المدرسة بنجاح!' : 'School Created Successfully!'}
                  </h2>
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">
                    {isRTL ? 'تم إنشاء المستأجر وحساب المدير وتجهيز الكتالوج الأكاديمي بنجاح' : 'Tenant, principal account, and academic catalog are ready'}
                  </p>
                </div>

                <Card className="rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm bg-slate-50 dark:bg-slate-800/90">
                  <CardContent className="p-4 space-y-3 text-xs">
                    <div className="flex items-center justify-between py-1 border-b border-slate-200 dark:border-slate-700">
                      <span className="text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'كود المستأجر:' : 'Tenant Code:'}</span>
                      <Badge className="text-base font-mono font-black bg-[#1C3D74] text-white px-3 py-1 rounded-lg" data-testid="tenant-code">
                        {createdSchool?.tenant_code}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between py-1 border-b border-slate-200 dark:border-slate-700">
                      <span className="text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'اسم المدرسة:' : 'School Name:'}</span>
                      <strong className="text-slate-900 dark:text-slate-100 font-bold">{createdSchool?.name || schoolData.name}</strong>
                    </div>
                    <div className="flex items-center justify-between py-1">
                      <span className="text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'الحالة:' : 'Status:'}</span>
                      <Badge className="bg-emerald-600 text-white font-bold">{isRTL ? 'نشطة' : 'Active'}</Badge>
                    </div>
                  </CardContent>
                </Card>

                <div className="flex gap-3 pt-2">
                  <Button className="flex-1 rounded-xl h-11 border-slate-300 dark:border-slate-700 font-bold text-slate-800 dark:text-slate-200" variant="outline" onClick={() => window.open('/school', '_blank')}>
                    <ExternalLink className="h-4 w-4 me-2 text-slate-500" />
                    {isRTL ? 'لوحة تحكم المدرسة' : 'School Dashboard'}
                  </Button>
                  <Button
                    variant="default"
                    className="flex-1 rounded-xl h-11 bg-[#1C3D74] hover:bg-[#152e57] text-white font-extrabold shadow-md shadow-[#1C3D74]/20"
                    onClick={handleClose}
                    data-testid="back-to-actions-btn"
                  >
                    {isRTL ? 'العودة للوحة الإدارة' : 'Back to Actions'}
                  </Button>
                </div>
              </div>

              {/* Right Side — Ready-to-copy Credentials Card */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-cairo text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <KeyRound className="h-4 w-4 text-[#00C5B2]" />
                    {isRTL ? 'الرسالة الترحيبية وبيانات الدخول' : 'Welcome Message & Credentials'}
                  </h3>
                  <Badge variant="outline" className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border-emerald-300">
                    {isRTL ? 'جاهزة للإرسال' : 'Ready to send'}
                  </Badge>
                </div>

                <Card className="bg-slate-900 text-slate-100 rounded-2xl border-slate-800 shadow-xl overflow-hidden">
                  <CardContent className="p-5 text-xs space-y-3" dir={isRTL ? 'rtl' : 'ltr'}>
                    <p className="font-bold text-slate-100 text-sm">أهلاً بك في منصة نَسَّق لإدارة التعليم والمدارس الذكية.</p>
                    <p className="text-slate-300 font-medium">بيانات دخول حساب إدارة المدرسة:</p>
                    <div className="bg-slate-950 rounded-xl p-3.5 space-y-2 font-mono text-xs border border-slate-800 text-emerald-400">
                      <div>
                        <span className="text-slate-400">رابط المنصة: </span>
                        <span className="text-slate-200 select-all font-semibold">{window.location.origin}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">اسم المستخدم: </span>
                        <span className="text-white font-bold select-all">{createdSchool?.principal?.email}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">كلمة المرور: </span>
                        <span className="text-amber-300 font-bold bg-amber-400/15 px-2 py-0.5 rounded select-all">{createdSchool?.principal?.temp_password}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">كود المدرسة: </span>
                        <span className="text-[#00C5B2] font-bold select-all">{createdSchool?.tenant_code}</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-300 flex items-center gap-1.5 font-medium">
                      <ShieldCheck className="h-3.5 w-3.5 text-[#00C5B2]" />
                      يرجى تغيير كلمة المرور عند أول تسجيل دخول لضمان الأمان.
                    </p>
                  </CardContent>
                </Card>

                <Button
                  onClick={copyWelcomeMessage}
                  className="w-full h-11 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-extrabold shadow-sm"
                  variant="outline"
                  data-testid="copy-message-btn"
                >
                  <Copy className="h-4 w-4 me-2 text-[#00C5B2]" />
                  {isRTL ? 'نسخ الرسالة الترحيبية وبيانات الدخول' : 'Copy Welcome Message'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
