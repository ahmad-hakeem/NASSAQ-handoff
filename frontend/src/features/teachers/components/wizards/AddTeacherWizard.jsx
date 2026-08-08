import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { toast } from 'sonner';
import { getFormErrorMessage } from '@/shared/models/utils/apiError';
import {
  User,
  Phone,
  Mail,
  ArrowLeft,
  ArrowRight,
  Loader2,
  CheckCircle2,
  GraduationCap,
  BookOpen,
  Calendar,
  Copy,
  Award,
  Briefcase,
  Clock,
  FileText,
  Shield,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';


const StepProgress = ({ currentStep, steps, isRTL }) => {
  const { t } = useTranslation();
  const totalSteps = steps.length;
  const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;

  return (
    <div className="px-6 py-4">
      <div className="relative">
        <div className="absolute top-4 left-0 right-0 h-1 bg-muted rounded-full">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-green-500 to-teal-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
        <div className="relative flex justify-between">
          {steps.map((s) => {
            const Icon = s.icon;
            const isActive = currentStep === s.num;
            const isDone = currentStep > s.num;
            return (
              <div key={s.num} className="flex flex-col items-center">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300 border-2 ${
                  isDone ? 'bg-emerald-500 border-emerald-500 text-white scale-90' :
                  isActive ? 'bg-green-600 border-green-600 text-white scale-110 shadow-lg shadow-green-500/30' :
                  'bg-background border-muted-foreground/20 text-muted-foreground'
                }`}>
                  {isDone ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </div>
                <span className={`text-[10px] mt-1.5 font-medium transition-colors ${
                  isActive ? 'text-green-700 dark:text-green-400' : isDone ? 'text-emerald-600' : 'text-muted-foreground'
                }`}>
                  {s.title}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

const FormField = ({ label, required, error, children }) => (
  <div className="space-y-1.5">
    <Label className="text-sm font-medium">
      {label} {required && <span className="text-red-500">*</span>}
    </Label>
    {children}
    {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
  </div>
);

const SectionHeader = ({ icon: Icon, title, subtitle, color = 'green' }) => {
  const colors = {
    green: 'from-emerald-500 to-green-600',
    blue: 'from-blue-500 to-indigo-600',
    purple: 'from-violet-500 to-purple-600',
    amber: 'from-amber-500 to-orange-500',
    indigo: 'from-indigo-500 to-blue-600',
  };
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colors[color]} flex items-center justify-center shadow-sm`}>
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div>
        <h3 className="font-bold text-base font-cairo">{title}</h3>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </div>
    </div>
  );
};

export const AddTeacherWizard = ({ open, onOpenChange, onSuccess }) => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { token, api } = useAuth();
  const { nassaqError } = useNassaqAlert();

  const handleCloseDialog = (val) => {
    if (val === true) return;
    if (submitting) return;
    handleReset();
    if (onOpenChange) onOpenChange(false);
  };

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);

  const [basicData, setBasicData] = useState({ nationality: 'SA' });
  const [qualData, setQualData] = useState({ years_of_experience: 0 });
  const [subjectData, setSubjectData] = useState({ subject_ids: [], grade_ids: [], max_periods_per_week: 24 });
  const [scheduleData, setScheduleData] = useState({ contract_type: 'permanent', available_days: ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'] });

  const [options, setOptions] = useState({
    subjects: [], grades: [], degrees: [], ranks: [], contractTypes: [], nationalities: []
  });
  const [subjectsError, setSubjectsError] = useState(false);

  useEffect(() => {
    if (open) fetchOptions();
  }, [open]);

  const apiClient = api;

  const fetchOptions = async () => {
    setLoading(true);
    setSubjectsError(false);
    let subjectsFailed = false;
    try {
      const [subjectsRes, gradesRes, degreesRes, ranksRes, contractsRes, nationsRes] = await Promise.all([
        apiClient.get('/teachers/options/subjects').catch(() => { subjectsFailed = true; return { data: { subjects: [] } }; }),
        apiClient.get('/teachers/options/grades').catch(() => ({ data: { grades: [] } })),
        apiClient.get('/teachers/options/academic-degrees').catch(() => ({ data: { degrees: [] } })),
        apiClient.get('/teachers/options/teacher-ranks').catch(() => ({ data: { ranks: [] } })),
        apiClient.get('/teachers/options/contract-types').catch(() => ({ data: { types: [] } })),
        apiClient.get('/teachers/options/nationalities').catch(() => ({ data: { nationalities: [] } })),
      ]);
      setOptions({
        subjects: subjectsRes.data.subjects || [],
        grades: gradesRes.data.grades || [],
        degrees: degreesRes.data.degrees || [],
        ranks: ranksRes.data.ranks || [],
        contractTypes: contractsRes.data.types || [],
        nationalities: nationsRes.data.nationalities || [],
      });
      setSubjectsError(subjectsFailed);
    } catch (error) {
      setSubjectsError(true);
    } finally {
      setLoading(false);
    }
  };

  const validateStep = (step) => {
    const newErrors = {};
    if (step === 1) {
      if (!basicData.full_name_ar?.trim()) newErrors.full_name_ar = t('required');
      if (!basicData.national_id || basicData.national_id.length !== 10) newErrors.national_id = t('10Digits');
      if (!basicData.gender) newErrors.gender = t('required');
      if (!basicData.phone?.trim()) newErrors.phone = t('required');
      if (!basicData.email?.trim()) newErrors.email = t('required');
    } else if (step === 2) {
      if (!qualData.academic_degree) newErrors.academic_degree = t('required');
      if (!qualData.teacher_rank) newErrors.teacher_rank = t('required');
    } else if (step === 3) {
      if (!subjectData.subject_ids?.length) newErrors.subject_ids = t('selectAtLeastOne');
      if (!subjectData.grade_ids?.length) newErrors.grade_ids = t('selectAtLeastOne2');
      if (!subjectData.primary_subject_id) newErrors.primary_subject_id = t('required');
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validateStep(currentStep)) return;
    if (currentStep < 5) { setCurrentStep(prev => prev + 1); setErrors({}); }
  };

  const handleBack = () => {
    if (currentStep > 1) { setCurrentStep(prev => prev - 1); setErrors({}); }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = { basic_info: basicData, qualifications: qualData, subjects: subjectData, schedule: scheduleData };
      const response = await apiClient.post('/teachers/create', payload);
      if (response.data.success) {
        setResult(response.data);
        setCurrentStep(6);
        toast.success(t('teacherAddedSuccessfully'));
        if (onSuccess) onSuccess(response.data);
      } else {
        nassaqError(response.data.error || (t('errorOccurred')));
      }
    } catch (error) {
      let errorMessage = getFormErrorMessage(error, { t });
      if (!errorMessage) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string') errorMessage = detail;
        else if (Array.isArray(detail)) errorMessage = detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
        else if (detail && typeof detail === 'object') errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        else errorMessage = t('error');
      }
      nassaqError(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setCurrentStep(1);
    setBasicData({ nationality: 'SA' });
    setQualData({ years_of_experience: 0 });
    setSubjectData({ subject_ids: [], grade_ids: [], max_periods_per_week: 24 });
    setScheduleData({ contract_type: 'permanent', available_days: ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'] });
    setErrors({});
    setResult(null);
    setSubmitting(false);
  };

  const steps = [
    { num: 1, title: isRTL ? 'البيانات' : 'Basic', icon: User },
    { num: 2, title: t('quals'), icon: GraduationCap },
    { num: 3, title: t('subjects'), icon: BookOpen },
    { num: 4, title: t('schedule'), icon: Calendar },
    { num: 5, title: t('review2'), icon: FileText },
  ];

  const days = [
    { id: 'sunday', ar: 'الأحد', en: 'Sun' },
    { id: 'monday', ar: 'الإثنين', en: 'Mon' },
    { id: 'tuesday', ar: 'الثلاثاء', en: 'Tue' },
    { id: 'wednesday', ar: 'الأربعاء', en: 'Wed' },
    { id: 'thursday', ar: 'الخميس', en: 'Thu' },
  ];

  const toggleSubject = (subjectId) => {
    const current = subjectData.subject_ids || [];
    const updated = current.includes(subjectId) ? current.filter(id => id !== subjectId) : [...current, subjectId];
    setSubjectData(p => ({ ...p, subject_ids: updated }));
  };

  const toggleGrade = (gradeId) => {
    const current = subjectData.grade_ids || [];
    const updated = current.includes(gradeId) ? current.filter(id => id !== gradeId) : [...current, gradeId];
    setSubjectData(p => ({ ...p, grade_ids: updated }));
  };

  const toggleDay = (dayId) => {
    const current = scheduleData.available_days || ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];
    const updated = current.includes(dayId) ? current.filter(id => id !== dayId) : [...current, dayId];
    setScheduleData(p => ({ ...p, available_days: updated }));
  };

  const getSubjectName = (id) => options.subjects?.find(s => s.id === id)?.[isRTL ? 'name_ar' : 'name_en'] || options.subjects?.find(s => s.id === id)?.name_ar || id;
  const getGradeName = (id) => options.grades?.find(g => g.id === id)?.[isRTL ? 'name_ar' : 'name_en'] || options.grades?.find(g => g.id === id)?.name_ar || id;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success(t('copied2'));
  };

  const generateWelcomeMessage = () => {
    const schoolName = result?.school_name || 'المدرسة';
    const teacherName = result?.teacher_name || result?.basic_info?.full_name_ar || basicData.full_name_ar || 'المعلم';
    const teacherId = result?.teacher_id || '';
    const email = result?.user_account?.email || '';
    const password = result?.user_account?.temp_password || '';
    const platformUrl = window.location.origin;

    if (isRTL) {
      return `السلام عليكم ورحمة الله وبركاته\n\nالأستاذ الكريم: ${teacherName}\n\nيسعدنا انضمامكم إلى فريق العمل في ${schoolName}، ويسرنا إبلاغكم بأنه تم إنشاء حساب خاص بكم على منصة نَسَّق | NASSAQ.\n\nبيانات حساب المعلم:\n• اسم المعلم: ${teacherName}\n• كود المعلم: ${teacherId}\n• اسم المدرسة: ${schoolName}\n\nبيانات تسجيل الدخول:\n• رابط المنصة: ${platformUrl}\n• اسم المستخدم: ${email}\n• كلمة المرور المؤقتة: ${password}\n\nننصحكم بتغيير كلمة المرور بعد أول تسجيل دخول.\n\nمع خالص التحية،\nإدارة ${schoolName}\nمنصة نَسَّق | NASSAQ`;
    }
    return `Dear ${teacherName},\n\nWelcome to ${schoolName}!\n\nAccount Details:\n• Teacher Name: ${teacherName}\n• Teacher ID: ${teacherId}\n\nLogin Credentials:\n• URL: ${platformUrl}\n• Email: ${email}\n• Temporary Password: ${password}\n\nPlease change your password after first login.\n\nBest regards,\n${schoolName} Administration`;
  };

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent className="max-w-3xl h-[85vh] flex flex-col p-0 gap-0 overflow-hidden" data-testid="add-teacher-wizard" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="bg-gradient-to-r from-green-700 to-emerald-600 text-white px-6 py-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <Briefcase className="h-5 w-5 text-white" />
            </div>
            <div>
              <DialogTitle className="font-cairo text-lg text-white">{t('addNewTeacher')}</DialogTitle>
              <DialogDescription className="text-white/70 text-xs">
                {t('step')} {Math.min(currentStep, 5)} {isRTL ? 'من' : 'of'} 5
              </DialogDescription>
            </div>
          </div>
        </div>

        {currentStep < 6 && <StepProgress currentStep={currentStep} steps={steps} isRTL={isRTL} />}

        {loading ? (
          <LoadingState variant="section" className="flex-1" />
        ) : (
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {currentStep === 1 && (
              <div className="space-y-5">
                <SectionHeader icon={User} title={t('basicInformation')} subtitle={t('enterTeacherPersonalInfo')} color="green" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField label={t('fullNameArabic')} required error={errors.full_name_ar}>
                    <Input value={basicData.full_name_ar || ''} onChange={(e) => setBasicData(p => ({ ...p, full_name_ar: e.target.value }))} className={`h-10 rounded-lg ${errors.full_name_ar ? 'border-red-500' : ''}`} data-testid="teacher-name-ar" />
                  </FormField>
                  <FormField label={t('fullNameEnglish')}>
                    <Input value={basicData.full_name_en || ''} onChange={(e) => setBasicData(p => ({ ...p, full_name_en: e.target.value }))} dir="ltr" className="h-10 rounded-lg" data-testid="teacher-name-en" />
                  </FormField>
                  <FormField label={t('nationalId')} required error={errors.national_id}>
                    <Input value={basicData.national_id || ''} onChange={(e) => setBasicData(p => ({ ...p, national_id: e.target.value.replace(/\D/g, '').slice(0, 10) }))} className={`h-10 rounded-lg ${errors.national_id ? 'border-red-500' : ''}`} maxLength={10} dir="ltr" data-testid="teacher-national-id" />
                  </FormField>
                  <FormField label={t('gender')} required error={errors.gender}>
                    <div className="flex gap-2">
                      {[{ val: 'male', ar: 'ذكر', en: 'Male' }, { val: 'female', ar: 'أنثى', en: 'Female' }].map(g => (
                        <button key={g.val} type="button" onClick={() => setBasicData(p => ({ ...p, gender: g.val }))}
                          className={`flex-1 h-10 rounded-lg border-2 text-sm font-medium transition-all ${
                            basicData.gender === g.val
                              ? g.val === 'male' ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : 'border-pink-500 bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300'
                              : 'border-border hover:border-muted-foreground/40'
                          }`}>
                          {isRTL ? g.ar : g.en}
                        </button>
                      ))}
                    </div>
                  </FormField>
                  <FormField label={t('nationality')}>
                    <Select value={basicData.nationality || 'SA'} onValueChange={(val) => setBasicData(p => ({ ...p, nationality: val }))}>
                      <SelectTrigger className="h-10 rounded-lg" data-testid="teacher-nationality"><SelectValue placeholder={t('select2')} /></SelectTrigger>
                      <SelectContent>
                        {options.nationalities?.map((n) => (<SelectItem key={n.id || n.code} value={n.id || n.code}>{isRTL ? (n.name || n.name_ar) : (n.name_en || n.name)}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>
                  <FormField label={t('dateOfBirth')}>
                    <Input type="date" value={basicData.date_of_birth || ''} onChange={(e) => setBasicData(p => ({ ...p, date_of_birth: e.target.value }))} className="h-10 rounded-lg" data-testid="teacher-dob" />
                  </FormField>
                  <FormField label={t('phone5')} required error={errors.phone}>
                    <Input value={basicData.phone || ''} onChange={(e) => setBasicData(p => ({ ...p, phone: e.target.value }))} className={`h-10 rounded-lg ${errors.phone ? 'border-red-500' : ''}`} dir="ltr" data-testid="teacher-phone" placeholder="05xxxxxxxx" />
                  </FormField>
                  <FormField label={t('email2')} required error={errors.email}>
                    <Input type="email" value={basicData.email || ''} onChange={(e) => setBasicData(p => ({ ...p, email: e.target.value }))} className={`h-10 rounded-lg ${errors.email ? 'border-red-500' : ''}`} dir="ltr" data-testid="teacher-email" />
                  </FormField>
                </div>
              </div>
            )}

            {currentStep === 2 && (
              <div className="space-y-5">
                <SectionHeader icon={GraduationCap} title={t('qualifications')} subtitle={t('enterQualificationAndExperienceInfo')} color="blue" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField label={isRTL ? 'الدرجة العلمية' : 'Academic Degree'} required error={errors.academic_degree}>
                    <Select value={qualData.academic_degree || ''} onValueChange={(val) => setQualData(p => ({ ...p, academic_degree: val }))}>
                      <SelectTrigger className={`h-10 rounded-lg ${errors.academic_degree ? 'border-red-500' : ''}`} data-testid="teacher-degree"><SelectValue placeholder={t('selectDegree')} /></SelectTrigger>
                      <SelectContent>
                        {options.degrees?.map((d) => (<SelectItem key={d.id || d.code} value={d.id || d.code}>{isRTL ? (d.name || d.name_ar) : (d.name_en || d.name)}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>
                  <FormField label={t('specialization')}>
                    <Input value={qualData.specialization || ''} onChange={(e) => setQualData(p => ({ ...p, specialization: e.target.value }))} className="h-10 rounded-lg" placeholder={t('egMathematics')} data-testid="teacher-specialization" />
                  </FormField>
                  <FormField label={t('university')}>
                    <Input value={qualData.university || ''} onChange={(e) => setQualData(p => ({ ...p, university: e.target.value }))} className="h-10 rounded-lg" data-testid="teacher-university" />
                  </FormField>
                  <FormField label={t('graduationYear')}>
                    <Input type="number" value={qualData.graduation_year || ''} onChange={(e) => setQualData(p => ({ ...p, graduation_year: parseInt(e.target.value) || '' }))} min="1970" max={new Date().getFullYear()} className="h-10 rounded-lg" data-testid="teacher-grad-year" />
                  </FormField>
                  <FormField label={isRTL ? 'سنوات الخبرة' : 'Years of Experience'} required error={errors.years_of_experience}>
                    <Input type="number" value={qualData.years_of_experience ?? ''} onChange={(e) => setQualData(p => ({ ...p, years_of_experience: parseInt(e.target.value) || 0 }))} min="0" className={`h-10 rounded-lg ${errors.years_of_experience ? 'border-red-500' : ''}`} data-testid="teacher-experience" />
                  </FormField>
                  <FormField label={t('teacherRank')} required error={errors.teacher_rank}>
                    <Select value={qualData.teacher_rank || ''} onValueChange={(val) => setQualData(p => ({ ...p, teacher_rank: val }))}>
                      <SelectTrigger className={`h-10 rounded-lg ${errors.teacher_rank ? 'border-red-500' : ''}`} data-testid="teacher-rank"><SelectValue placeholder={t('selectRank')} /></SelectTrigger>
                      <SelectContent>
                        {options.ranks?.map((r) => (<SelectItem key={r.id || r.code} value={r.id || r.code}>{isRTL ? (r.name || r.name_ar) : (r.name_en || r.name)}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>
                </div>
              </div>
            )}

            {currentStep === 3 && (
              <div className="space-y-5">
                <SectionHeader icon={BookOpen} title={t('subjectsGrades')} subtitle={t('selectTeachingSubjectsAndGrades')} color="purple" />

                <div className="space-y-4">
                  {subjectsError ? (
                    <div
                      className="flex flex-col items-center gap-3 rounded-lg border-2 border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950/30"
                      data-testid="subjects-load-error"
                    >
                      <AlertCircle className="h-7 w-7 text-red-500" strokeWidth={1.5} aria-hidden="true" />
                      <p className="text-sm font-medium text-red-700 dark:text-red-300">{t('subjectsLoadError')}</p>
                      <Button type="button" variant="outline" size="sm" className="gap-1.5 rounded-lg" onClick={fetchOptions}>
                        <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                        {t('retry')}
                      </Button>
                    </div>
                  ) : (options.subjects?.length || 0) === 0 ? (
                    <div
                      className="flex flex-col items-center gap-3 rounded-lg border-2 border-amber-200 bg-amber-50 p-6 text-center dark:border-amber-900 dark:bg-amber-950/30"
                      data-testid="subjects-empty-state"
                    >
                      <BookOpen className="h-7 w-7 text-amber-500" strokeWidth={1.5} aria-hidden="true" />
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-200">{t('noSubjectsConfigured')}</p>
                      <Button type="button" variant="outline" size="sm" className="gap-1.5 rounded-lg" asChild>
                        <Link to="/principal/subjects">
                          <BookOpen className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                          {t('goToSubjectsSettings')}
                        </Link>
                      </Button>
                    </div>
                  ) : (
                  <>
                  <div>
                    <Label className="mb-2 block text-sm font-medium">{t('subjects2')} <span className="text-red-500">*</span></Label>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                      {options.subjects?.map((subject) => (
                        <button key={subject.id} type="button" onClick={() => toggleSubject(subject.id)}
                          className={`p-2.5 rounded-lg border-2 text-sm font-medium text-start transition-all ${
                            (subjectData.subject_ids || []).includes(subject.id)
                              ? 'border-violet-500 bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300'
                              : 'border-border hover:border-muted-foreground/40 text-foreground'
                          }`}>
                          {isRTL ? (subject.name_ar || subject.name) : (subject.name_en || subject.name_ar || subject.name)}
                        </button>
                      ))}
                    </div>
                    {errors.subject_ids && <p className="text-red-500 text-xs mt-1">{errors.subject_ids}</p>}
                  </div>

                  <FormField label={t('primarySubject')} required error={errors.primary_subject_id}>
                    <Select value={subjectData.primary_subject_id || ''} onValueChange={(val) => setSubjectData(p => ({ ...p, primary_subject_id: val }))}>
                      <SelectTrigger className={`h-10 rounded-lg ${errors.primary_subject_id ? 'border-red-500' : ''}`} data-testid="teacher-primary-subject"><SelectValue placeholder={t('selectPrimarySubject')} /></SelectTrigger>
                      <SelectContent>
                        {options.subjects?.map((subject) => (<SelectItem key={subject.id} value={subject.id}>{isRTL ? (subject.name_ar || subject.name) : (subject.name_en || subject.name_ar || subject.name)}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>
                  </>
                  )}

                  <div>
                    <Label className="mb-2 block text-sm font-medium">{t('grades2')} <span className="text-red-500">*</span></Label>
                    <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                      {options.grades?.map((grade) => (
                        <button key={grade.id} type="button" onClick={() => toggleGrade(grade.id)}
                          className={`p-2 rounded-lg border-2 text-center text-sm font-medium transition-all ${
                            (subjectData.grade_ids || []).includes(grade.id)
                              ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                              : 'border-border hover:border-muted-foreground/40'
                          }`}>
                          {isRTL ? (grade.name_ar || grade.name) : (grade.name_en || grade.name_ar || grade.name)}
                        </button>
                      ))}
                    </div>
                    {errors.grade_ids && <p className="text-red-500 text-xs mt-1">{errors.grade_ids}</p>}
                  </div>

                  <FormField label={t('maxPeriodsweek')}>
                    <Input type="number" value={subjectData.max_periods_per_week || 24} onChange={(e) => setSubjectData(p => ({ ...p, max_periods_per_week: parseInt(e.target.value) || 24 }))} min="1" max="30" className="h-10 rounded-lg" data-testid="teacher-max-periods" />
                  </FormField>
                </div>
              </div>
            )}

            {currentStep === 4 && (
              <div className="space-y-5">
                <SectionHeader icon={Calendar} title={t('schedulePreferences')} subtitle={t('contractTypeAndWorkDays')} color="amber" />
                <div className="space-y-4">
                  <FormField label={t('contractType')}>
                    <Select value={scheduleData.contract_type || 'permanent'} onValueChange={(val) => setScheduleData(p => ({ ...p, contract_type: val }))}>
                      <SelectTrigger className="h-10 rounded-lg" data-testid="teacher-contract"><SelectValue placeholder={t('select2')} /></SelectTrigger>
                      <SelectContent>
                        {options.contractTypes?.map((c) => (<SelectItem key={c.id || c.code} value={c.id || c.code}>{isRTL ? (c.name || c.name_ar) : (c.name_en || c.name)}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>

                  <div>
                    <Label className="mb-2 block text-sm font-medium">{t('availableDays')}</Label>
                    <div className="grid grid-cols-5 gap-2">
                      {days.map((day) => (
                        <button key={day.id} type="button" onClick={() => toggleDay(day.id)}
                          className={`p-3 rounded-lg border-2 text-center transition-all ${
                            (scheduleData.available_days || ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday']).includes(day.id)
                              ? 'border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'border-border hover:border-muted-foreground/40'
                          }`}>
                          <p className="font-medium text-sm">{isRTL ? day.ar : day.en}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {currentStep === 5 && (
              <div className="space-y-4">
                <SectionHeader icon={FileText} title={t('reviewInformation')} subtitle={t('verifyAllInformationIsCorrect')} color="indigo" />

                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-green-50 dark:bg-green-950/20 border-b flex items-center gap-2">
                    <User className="h-4 w-4 text-green-600" />
                    <span className="font-semibold text-sm text-green-800 dark:text-green-300">{isRTL ? 'البيانات الأساسية' : 'Basic Info'}</span>
                  </div>
                  <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    <div><span className="text-muted-foreground text-xs">{t('name')}</span><p className="font-medium">{basicData.full_name_ar}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('id')}</span><p className="font-medium" dir="ltr">{basicData.national_id}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('email')}</span><p className="font-medium" dir="ltr">{basicData.email}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('phone')}</span><p className="font-medium" dir="ltr">{basicData.phone}</p></div>
                  </div>
                </div>

                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-blue-50 dark:bg-blue-950/20 border-b flex items-center gap-2">
                    <GraduationCap className="h-4 w-4 text-blue-600" />
                    <span className="font-semibold text-sm text-blue-800 dark:text-blue-300">{isRTL ? 'المؤهلات' : 'Qualifications'}</span>
                  </div>
                  <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    <div><span className="text-muted-foreground text-xs">{t('degree2')}</span><p className="font-medium">{qualData.academic_degree}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('experience2')}</span><p className="font-medium">{qualData.years_of_experience} {t('years')}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('rank')}</span><p className="font-medium">{qualData.teacher_rank}</p></div>
                  </div>
                </div>

                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-violet-50 dark:bg-violet-950/20 border-b flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-violet-600" />
                    <span className="font-semibold text-sm text-violet-800 dark:text-violet-300">{t('subjectsGrades')}</span>
                  </div>
                  <div className="p-4">
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {(subjectData.subject_ids || []).map(id => (<Badge key={id} variant="secondary" className="text-xs">{getSubjectName(id)}</Badge>))}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {(subjectData.grade_ids || []).map(id => (<Badge key={id} variant="outline" className="text-xs">{getGradeName(id)}</Badge>))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {currentStep === 6 && result && (
              <div className="space-y-5 py-2">
                <div className="text-center">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-emerald-400 to-green-600 mx-auto flex items-center justify-center mb-4 shadow-lg shadow-emerald-500/20">
                    <CheckCircle2 className="h-8 w-8 text-white" />
                  </div>
                  <h2 className="text-xl font-bold text-emerald-600 font-cairo mb-1">{t('teacherAdded')}</h2>
                </div>

                <div className="p-4 rounded-xl border-2 border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-xs text-muted-foreground">{t('teacherId')}</p>
                      <p className="text-lg font-bold font-mono text-emerald-800">{result.teacher_id}</p>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => copyToClipboard(result.teacher_id)} className="text-emerald-600">
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                  {result.user_account?.created && (
                    <div className="space-y-2 p-3 bg-white dark:bg-background rounded-lg text-sm">
                      <p className="font-semibold text-xs text-emerald-800 dark:text-emerald-300">{t('loginCredentials2')}</p>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">{t('email3')}</span>
                        <code className="text-xs bg-muted px-2 py-0.5 rounded">{result.user_account.email}</code>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">{t('password2')}</span>
                        <div className="flex items-center gap-1">
                          <code className="text-xs bg-muted px-2 py-0.5 rounded">{result.user_account.temp_password}</code>
                          <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => copyToClipboard(result.user_account.temp_password)}>
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <Button variant="outline" className="w-full h-10 rounded-lg" onClick={() => {
                  const message = generateWelcomeMessage();
                  navigator.clipboard.writeText(message);
                  toast.success(isRTL ? 'تم نسخ رسالة الترحيب' : 'Welcome message copied!');
                }}>
                  <Copy className="h-4 w-4 me-2" />
                  {t('copyWelcomeMessage')}
                </Button>

                <div className="flex justify-center gap-3 pt-2">
                  <Button variant="outline" className="rounded-lg" onClick={() => handleCloseDialog(false)}>{t('close')}</Button>
                  <Button className="rounded-lg bg-green-600 hover:bg-green-700" onClick={handleReset}>{t('addAnother2')}</Button>
                </div>
              </div>
            )}
          </div>
        )}

        {!loading && currentStep < 6 && (
          <div className="flex items-center justify-between px-6 py-3 border-t bg-muted/20 flex-shrink-0">
            <div>
              {currentStep > 1 && (
                <Button variant="ghost" size="sm" onClick={handleBack} disabled={submitting} className="gap-1.5 rounded-lg h-9">
                  {isRTL ? <ArrowRight className="h-3.5 w-3.5" /> : <ArrowLeft className="h-3.5 w-3.5" />}
                  {t('back')}
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="rounded-lg h-9" onClick={() => handleCloseDialog(false)} disabled={submitting}>{t('cancel')}</Button>
              {currentStep < 5 ? (
                <Button size="sm" onClick={handleNext} disabled={currentStep === 3 && (subjectsError || (options.subjects?.length || 0) === 0)} className="bg-green-600 hover:bg-green-700 gap-1.5 rounded-lg h-9 px-5">
                  {t('next')}
                  {isRTL ? <ArrowLeft className="h-3.5 w-3.5" /> : <ArrowRight className="h-3.5 w-3.5" />}
                </Button>
              ) : (
                <Button size="sm" onClick={handleSubmit} disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700 gap-1.5 rounded-lg h-9 px-5">
                  {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  {t('confirmSave')}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default AddTeacherWizard;
