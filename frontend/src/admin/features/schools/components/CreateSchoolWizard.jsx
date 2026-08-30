import React, { useState, useRef, useCallback } from 'react';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Dialog, DialogContent } from '@/shared/components/ui/dialog';
import { toast } from 'sonner';
import {
  Building2, GraduationCap, User, CheckCircle
} from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

// Wizard Sub-components
import WizardHeader from './wizard/WizardHeader';
import WizardFooter from './wizard/WizardFooter';
import StepSchoolProfile from './wizard/StepSchoolProfile';
import StepOperatingSettings from './wizard/StepOperatingSettings';
import StepPrincipalAccount from './wizard/StepPrincipalAccount';
import StepReviewConfirm from './wizard/StepReviewConfirm';
import WizardSuccessScreen from './wizard/WizardSuccessScreen';

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
    if (!schoolData.name.trim()) newErrors.name = t('schoolNameIsRequired') || (isRTL ? 'اسم المدرسة مطلوب' : 'School name is required');
    if (!schoolData.country) newErrors.country = t('countryIsRequired') || (isRTL ? 'الدولة مطلوبة' : 'Country is required');
    if (!schoolData.city) newErrors.city = t('cityIsRequired') || (isRTL ? 'المدينة مطلوبة' : 'City is required');
    if (!schoolData.address.trim()) newErrors.address = t('addressIsRequired') || (isRTL ? 'العنوان التفصيلي مطلوب' : 'Address is required');
    if (!(schoolData.principal_mobile || '').trim()) {
      newErrors.principal_mobile = t('principalMobileIsRequired') || (isRTL ? 'رقم جوال التواصل مطلوب' : 'Mobile is required');
    }
    if (
      schoolData.principal_mobile &&
      !/^05\d{8}$/.test(schoolData.principal_mobile.replace(/\s/g, ''))
    ) {
      newErrors.principal_mobile = t('invalidPhoneMustStartWith0510Digits') || (isRTL ? 'رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام' : 'Invalid mobile format (05XXXXXXXX)');
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
    if (!principalData.fullName.trim()) newErrors.fullName = t('principalNameIsRequired') || (isRTL ? 'اسم المدير مطلوب' : 'Principal name is required');
    if (!principalData.primaryPhone.trim()) newErrors.primaryPhone = t('phoneNumberIsRequired') || (isRTL ? 'رقم الهاتف مطلوب' : 'Phone is required');
    if (!principalData.email.trim()) newErrors.email = t('emailIsRequired') || (isRTL ? 'البريد الإلكتروني مطلوب' : 'Email is required');

    if (principalData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(principalData.email)) {
      newErrors.email = t('invalidEmailFormat') || (isRTL ? 'صيغة البريد الإلكتروني غير صحيحة' : 'Invalid email format');
    }

    if (
      principalData.primaryPhone &&
      !/^05\d{8}$/.test(principalData.primaryPhone.replace(/\s/g, ''))
    ) {
      newErrors.primaryPhone = t('invalidPhoneMustStartWith0510Digits') || (isRTL ? 'رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام' : 'Invalid phone format (05XXXXXXXX)');
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
    toast.success(t('settingsResetToDefault') || (isRTL ? 'تمت استعادة الإعدادات للوضع الافتراضي' : 'Settings reset to default'));
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
        name: schoolData.name || (t('draftSchool') || (isRTL ? 'مسودة مدرسة جديدة' : 'New School Draft')),
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
      toast.success(t('schoolSavedAsDraftFindItInTheDraftsSection') || (isRTL ? 'تم حفظ المدرسة كمسودة بنجاح' : 'School saved as draft'));

      if (onSuccess) onSuccess(response.data);
      handleClose();
    } catch (error) {
      console.error('Error saving draft:', error);
      const rawDetail = getApiErrorMessage(error) || '';
      nassaqError(rawDetail || t('failedToSaveDraftPleaseTryAgain') || (isRTL ? 'فشل حفظ المسودة، يرجى المحاولة لاحقاً' : 'Failed to save draft'));
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
      toast.success(t('schoolCreatedSuccessfully') || (isRTL ? 'تم إنشاء المدرسة بنجاح' : 'School created successfully'));

      if (onSuccess) onSuccess(response.data);
    } catch (error) {
      console.error('Error creating school:', error);
      const rawDetail = getApiErrorMessage(error) || '';

      const codeConflictEntry = {
        step: 1,
        field: 'name',
        userMsg: t('schoolCodeConflictPleaseTryAgain') || (isRTL ? 'رمز المدرسة مستخدم مسبقاً، يرجى اختيار اسم آخر' : 'School code conflict'),
        fieldMsg: t('schoolCodeConflictPleaseTryAgain2') || (isRTL ? 'رمز المدرسة مستخدم مسبقاً' : 'School code conflict'),
      };

      const BACKEND_ERROR_MAP = {
        'رمز المدرسة مستخدم مسبقاً': codeConflictEntry,
        'رمز المدرسة مستخدم مسبقاً — يُرجى اختيار رمز آخر': codeConflictEntry,
        'البريد الإلكتروني مستخدم مسبقاً': {
          step: 3,
          field: 'email',
          userMsg: t('thisEmailIsAlreadyRegisteredPleaseChangeItInThePri') || (isRTL ? 'البريد الإلكتروني مستخدم مسبقاً' : 'Email already registered'),
          fieldMsg: t('thisEmailIsAlreadyRegistered') || (isRTL ? 'البريد الإلكتروني مستخدم مسبقاً' : 'Email already registered'),
        },
        'رقم الهاتف مستخدم مسبقاً': {
          step: 3,
          field: 'primaryPhone',
          userMsg: t('thisPhoneNumberIsAlreadyRegisteredPleaseChangeItIn') || (isRTL ? 'رقم الهاتف مستخدم مسبقاً' : 'Phone already registered'),
          fieldMsg: t('thisPhoneNumberIsAlreadyRegistered') || (isRTL ? 'رقم الهاتف مستخدم مسبقاً' : 'Phone already registered'),
        },
      };

      const mapped = BACKEND_ERROR_MAP[rawDetail];
      if (mapped) {
        setErrors((prev) => ({ ...prev, [mapped.field]: mapped.fieldMsg }));
        setCurrentStep(mapped.step);
        nassaqError(mapped.userMsg);
        setTimeout(() => focusFirstError([mapped.field]), 200);
      } else {
        const fallback = rawDetail || t('errorCreatingSchoolPleaseTryAgain') || (isRTL ? 'حدث خطأ أثناء إنشاء المدرسة' : 'Error creating school');
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
    toast.success(t('welcomeMessageCopied') || (isRTL ? 'تم نسخ الرسالة الترحيبية' : 'Welcome message copied'));
  };

  // Steps Configuration
  const steps = [
    { number: 1, title: isRTL ? 'بيانات المدرسة' : 'School Info', icon: Building2 },
    { number: 2, title: isRTL ? 'إعدادات التشغيل' : 'Operating Settings', icon: GraduationCap },
    { number: 3, title: isRTL ? 'مدير المدرسة' : 'Principal Account', icon: User },
    { number: 4, title: isRTL ? 'مراجعة وتأكيد' : 'Review & Confirm', icon: CheckCircle },
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
            <WizardHeader
              steps={steps}
              currentStep={currentStep}
              onStepClick={setCurrentStep}
              isRTL={isRTL}
            />

            {/* Scrollable Content Form Area */}
            <div className="flex-1 min-h-0 p-6 md:px-8 md:py-6 overflow-y-auto bg-slate-50/60 dark:bg-slate-900" ref={formRef}>
              {currentStep === 1 && (
                <StepSchoolProfile
                  schoolData={schoolData}
                  setSchoolData={setSchoolData}
                  errors={errors}
                  clearFieldError={clearFieldError}
                  onLogoUpload={handleLogoUpload}
                  isRTL={isRTL}
                />
              )}

              {currentStep === 2 && (
                <StepOperatingSettings
                  settingsData={settingsData}
                  setSettingsData={setSettingsData}
                  onResetDefaults={resetSettingsToDefault}
                  isRTL={isRTL}
                />
              )}

              {currentStep === 3 && (
                <StepPrincipalAccount
                  principalData={principalData}
                  setPrincipalData={setPrincipalData}
                  errors={errors}
                  clearFieldError={clearFieldError}
                  isRTL={isRTL}
                />
              )}

              {currentStep === 4 && (
                <StepReviewConfirm
                  schoolData={schoolData}
                  settingsData={settingsData}
                  principalData={principalData}
                  onGoToStep={setCurrentStep}
                  isRTL={isRTL}
                />
              )}
            </div>

            {/* Bottom Actions Footer */}
            <WizardFooter
              currentStep={currentStep}
              onClose={handleClose}
              onSaveAsDraft={handleSaveAsDraft}
              onPrevious={handlePrevious}
              onNext={handleNext}
              onCreateSchool={handleCreateSchool}
              isSubmitting={isSubmitting}
              isRTL={isRTL}
            />
          </>
        ) : (
          /* Success Screen */
          <WizardSuccessScreen
            createdSchool={createdSchool}
            schoolName={schoolData.name}
            onCopyWelcomeMessage={copyWelcomeMessage}
            onClose={handleClose}
            isRTL={isRTL}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
