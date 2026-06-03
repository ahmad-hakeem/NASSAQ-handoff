import { useState, useCallback, useEffect, useRef } from 'react';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { Textarea } from '../ui/textarea';
import { toast } from 'sonner';
import {
  GraduationCap,
  User,
  Users,
  Heart,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Copy,
  Download,
  AlertTriangle,
  UserPlus,
  Phone,
  Mail,
  Calendar,
  QrCode,
  Sparkles,
  Search,
  Link2,
  UserCheck,
  Loader2,
  ArrowRight,
  ArrowLeft,
  FileText,
  Shield,
} from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';
import { filterGradesByStage, gradeBelongsToStage } from '../../utils/stageGrade';
import { getFormErrorMessage } from '../../utils/apiError';
const STEPS = [
  { id: 1, title_ar: 'بيانات الطالب', title_en: 'Student Info', icon: GraduationCap, color: 'blue' },
  { id: 2, title_ar: 'ولي الأمر', title_en: 'Parent', icon: Users, color: 'green' },
  { id: 3, title_ar: 'الصحة', title_en: 'Health', icon: Heart, color: 'rose' },
  { id: 4, title_ar: 'المراجعة', title_en: 'Review', icon: FileText, color: 'amber' },
  { id: 5, title_ar: 'تم', title_en: 'Done', icon: Sparkles, color: 'emerald' },
];

const EDUCATION_LEVELS = [
  { id: 'primary', name_ar: 'المرحلة الابتدائية', name_en: 'Primary' },
  { id: 'middle', name_ar: 'المرحلة المتوسطة', name_en: 'Middle School' },
  { id: 'high', name_ar: 'المرحلة الثانوية', name_en: 'High School' },
];

const RELATIONSHIPS = [
  { id: 'father', name_ar: 'أب', name_en: 'Father' },
  { id: 'mother', name_ar: 'أم', name_en: 'Mother' },
  { id: 'guardian', name_ar: 'ولي أمر', name_en: 'Guardian' },
];

const StepProgress = ({ currentStep, steps, isRTL }) => {
  const { t } = useTranslation();
  const totalSteps = steps.length - 1;
  const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;

  return (
    <div className="px-6 py-4">
      <div className="relative">
        <div className="absolute top-4 left-0 right-0 h-1 bg-muted rounded-full">
          <div
            className="h-full bg-gradient-to-r from-brand-navy via-brand-turquoise to-emerald-500 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
        <div className="relative flex justify-between">
          {steps.filter(s => s.id <= 4).map((s) => {
            const Icon = s.icon;
            const isActive = currentStep === s.id;
            const isDone = currentStep > s.id;
            return (
              <div key={s.id} className="flex flex-col items-center">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-300 border-2 ${
                  isDone ? 'bg-emerald-500 border-emerald-500 text-white scale-90' :
                  isActive ? 'bg-brand-navy border-brand-navy text-white scale-110 shadow-lg shadow-brand-navy/30' :
                  'bg-background border-muted-foreground/20 text-muted-foreground'
                }`}>
                  {isDone ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </div>
                <span className={`text-[10px] mt-1.5 font-medium transition-colors ${
                  isActive ? 'text-brand-navy dark:text-brand-turquoise' : isDone ? 'text-emerald-600' : 'text-muted-foreground'
                }`}>
                  {isRTL ? s.title_ar : s.title_en}
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

const SectionHeader = ({ icon: Icon, title, subtitle, color = 'blue' }) => {
  const colors = {
    blue: 'from-blue-500 to-brand-navy',
    green: 'from-emerald-500 to-green-600',
    rose: 'from-rose-400 to-red-500',
    amber: 'from-amber-400 to-orange-500',
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

export default function AddStudentWizard({
  open,
  onOpenChange,
  onSuccess,
  api,
  isRTL = true,
  grades = [],
  classes = [],
  // When the wizard is launched from a class detail page, the caller
  // pre-selects the target class so the new student is actually
  // attached to it. Without this, the class selector defaults to ''
  // and the student is created with no class linkage. The matching
  // grade_id / education_level are seeded from the class so step-1
  // validation still passes and the user cannot accidentally clear
  // the class picker.
  preselectedClassId = '',
  preselectedGradeId = '',
  preselectedEducationLevel = '',
  // #192 spec §5.6 — `workspace` mode is the IT inline-create variant.
  // It hides the parent-directory search, drops `check-parent`, makes
  // every parent field optional, and skips the school-only relationship
  // requirement so the wizard can submit a student with zero parent data.
  mode = 'school',
}) {
  const hasPreselectedClass = Boolean(preselectedClassId);
  // Lock individual selectors only when we actually have a value to
  // pre-fill them with. This avoids a step-1 lockout on schools whose
  // class metadata doesn't expose a numeric grade (so we couldn't
  // derive education_level) or doesn't expose a grade_id.
  const lockClass = hasPreselectedClass;
  const lockGrade = hasPreselectedClass && Boolean(preselectedGradeId);
  const lockEducation = hasPreselectedClass && Boolean(preselectedEducationLevel);
  const isWorkspaceMode = mode === 'workspace';
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const [step, setStep] = useState(1);

  const [internalGrades, setInternalGrades] = useState([]);
  const [gradesLoadError, setGradesLoadError] = useState(false);
  const [isLoadingGrades, setIsLoadingGrades] = useState(false);
  const gradesFetchedRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedMessage, setCopiedMessage] = useState(false);

  const [studentData, setStudentData] = useState({
    full_name: '',
    email: '',
    national_id: '',
    gender: 'male',
    date_of_birth: '',
    education_level: preselectedEducationLevel || '',
    grade_id: preselectedGradeId || '',
    class_id: preselectedClassId || '',
  });

  // Re-seed pre-selected fields whenever the wizard is opened or the
  // pre-selection changes (e.g. navigating between class pages without
  // unmounting). We never overwrite user-entered free-text fields.
  useEffect(() => {
    if (!open) return;
    if (!hasPreselectedClass) return;
    setStudentData(prev => ({
      ...prev,
      class_id: preselectedClassId,
      grade_id: preselectedGradeId || prev.grade_id,
      education_level: preselectedEducationLevel || prev.education_level,
    }));
  }, [open, hasPreselectedClass, preselectedClassId, preselectedGradeId, preselectedEducationLevel]);

  const [parentData, setParentData] = useState({
    full_name: '',
    national_id: '',
    phone: '',
    email: '',
    relationship: 'father',
    address: '',
  });

  const [healthData, setHealthData] = useState({
    health_status: '',
    allergies: '',
    medications: '',
    special_needs: '',
    notes: '',
  });

  const [existingParent, setExistingParent] = useState(null);
  const [siblings, setSiblings] = useState([]);
  const [checkingParent, setCheckingParent] = useState(false);
  const [linkToExisting, setLinkToExisting] = useState(false);

  // Workspace mode (#192) hides the parent-directory toggle entirely
  // and locks the wizard into the "new parent (optional)" flow.
  const [parentMode, setParentMode] = useState(isWorkspaceMode ? 'new' : 'new');
  const [parentSearchQuery, setParentSearchQuery] = useState('');
  const [parentSearchResults, setParentSearchResults] = useState([]);
  const [searchingParents, setSearchingParents] = useState(false);
  const [selectedExistingParent, setSelectedExistingParent] = useState(null);

  const [createdStudent, setCreatedStudent] = useState(null);
  const [createdParent, setCreatedParent] = useState(null);

  const allGrades = internalGrades.length > 0 ? internalGrades : grades;

  const fetchGrades = useCallback(async () => {
    setIsLoadingGrades(true);
    setGradesLoadError(false);
    try {
      const res = await api.get('/grade-levels');
      const fetched = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      setInternalGrades(fetched);
      gradesFetchedRef.current = true;
    } catch (_err) {
      setGradesLoadError(true);
    } finally {
      setIsLoadingGrades(false);
    }
  }, [api]);

  useEffect(() => {
    if (!open) return;
    if (grades.length > 0) return;
    if (gradesFetchedRef.current) return;
    fetchGrades();
  }, [open, grades.length, fetchGrades]);

  const checkParentExists = useCallback(async () => {
    // Workspace mode (#192) intentionally skips the parent-directory probe:
    // IT operators rarely have other parents in their workspace and the
    // endpoint is school-scoped.
    if (isWorkspaceMode) return;
    if (!parentData.phone && !parentData.email && !parentData.national_id) return;
    setCheckingParent(true);
    try {
      const params = new URLSearchParams();
      if (parentData.phone) params.append('phone', parentData.phone);
      if (parentData.email) params.append('email', parentData.email);
      if (parentData.national_id) params.append('national_id', parentData.national_id);
      const response = await api.post(`/student-wizard/check-parent?${params.toString()}`);
      if (response.data?.found) {
        setExistingParent(response.data.parent);
        setSiblings(response.data.students || []);
      } else {
        setExistingParent(null);
        setSiblings([]);
      }
    } catch (error) {
      console.error('Error checking parent:', error);
    } finally {
      setCheckingParent(false);
    }
  }, [api, parentData.phone, parentData.email, parentData.national_id]);

  const searchParents = useCallback(async (query) => {
    if (!query || query.length < 2) { setParentSearchResults([]); return; }
    setSearchingParents(true);
    try {
      const response = await api.get(`/student-wizard/search-parents?q=${encodeURIComponent(query)}`);
      setParentSearchResults(response.data?.parents || []);
    } catch (error) {
      console.error('Error searching parents:', error);
      setParentSearchResults([]);
    } finally {
      setSearchingParents(false);
    }
  }, [api]);

  const handleParentSearch = (value) => {
    setParentSearchQuery(value);
    const timeoutId = setTimeout(() => { searchParents(value); }, 300);
    return () => clearTimeout(timeoutId);
  };

  const selectParentFromSearch = (parent) => {
    setSelectedExistingParent(parent);
    setParentData({
      full_name: parent.full_name || '',
      national_id: parent.national_id || '',
      phone: parent.phone || '',
      email: parent.email || '',
      relationship: parent.relationship || 'father',
      address: parent.address || '',
    });
    setSiblings(parent.children || []);
    setLinkToExisting(true);
    setParentSearchResults([]);
    setParentSearchQuery('');
  };

  const isStepValid = () => {
    switch (step) {
      case 1: {
        const baseValid = Boolean(
          studentData.full_name &&
          studentData.gender &&
          studentData.date_of_birth &&
          studentData.education_level &&
          studentData.grade_id
        );
        const classValid = classes.length === 0 || Boolean(studentData.class_id);
        return baseValid && classValid;
      }
      case 2:
        // Workspace mode (#192 spec §5.6) — parent step is fully optional;
        // the user can leave every field blank and still advance.
        if (isWorkspaceMode) return true;
        if (parentMode === 'search' && selectedExistingParent) return true;
        if (linkToExisting && existingParent) return true;
        return parentData.full_name && parentData.phone && parentData.relationship;
      case 3: return true;
      case 4: return true;
      default: return true;
    }
  };

  const nextStep = () => {
    if (step === 2) checkParentExists();
    if (step < 5) setStep(step + 1);
  };

  const prevStep = () => { if (step > 1) setStep(step - 1); };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      let parentIdToLink = null;
      if (parentMode === 'search' && selectedExistingParent) {
        parentIdToLink = selectedExistingParent.id;
      } else if (linkToExisting && existingParent) {
        parentIdToLink = existingParent.id;
      }

      // Normalize optional identifier fields so blank inputs are sent as
      // null instead of empty strings. Empty strings collide on the
      // (national_id, school_id) UNIQUE constraint on the second blank
      // submission, producing a false-positive "ID already registered"
      // error. NULLs are treated as distinct by PostgreSQL.
      const _blankToNull = (v) => {
        if (v === undefined || v === null) return null;
        if (typeof v === 'string' && v.trim() === '') return null;
        return typeof v === 'string' ? v.trim() : v;
      };

      const sanitizedStudent = {
        ...studentData,
        national_id: _blankToNull(studentData.national_id),
        email: _blankToNull(studentData.email),
      };

      const sanitizedParent = {
        ...parentData,
        full_name: _blankToNull(parentData.full_name),
        phone: _blankToNull(parentData.phone),
        national_id: _blankToNull(parentData.national_id),
        email: _blankToNull(parentData.email),
        address: _blankToNull(parentData.address),
      };

      // Workspace mode (#192 spec §5.6): when EVERY parent field is blank
      // we omit the `parent` payload entirely so the backend writes
      // pending_parent_* as NULLs instead of materialising an empty
      // parents row. When a partial payload is supplied (e.g. just a
      // name or just a phone) we still send it and the backend persists
      // it into the pending_parent_* columns.
      const parentIsEmpty = isWorkspaceMode && !parentIdToLink && !sanitizedParent.full_name && !sanitizedParent.phone && !sanitizedParent.email && !sanitizedParent.national_id && !sanitizedParent.address;

      const requestData = {
        ...sanitizedStudent,
        parent: parentIsEmpty ? null : sanitizedParent,
        health: healthData.health_status || healthData.allergies || healthData.medications ? {
          health_status: healthData.health_status || null,
          allergies: healthData.allergies ? healthData.allergies.split(',').map(a => a.trim()) : [],
          medications: healthData.medications ? healthData.medications.split(',').map(m => m.trim()) : [],
          special_needs: healthData.special_needs || null,
          notes: healthData.notes || null,
        } : null,
        link_to_parent_id: parentIdToLink,
      };

      const response = await api.post('/student-wizard/create', requestData);
      if (response.data?.success) {
        setCreatedStudent(response.data.student);
        setCreatedParent(response.data.parent);
        setSiblings(response.data.siblings?.list || []);
        setStep(5);
        toast.success(t('accountCreatedSuccessfully'));
        if (onSuccess) onSuccess(response.data);
      } else {
        nassaqError(t('failedToCreateAccount'));
      }
    } catch (error) {
      console.error('Error creating student:', error);
      // The backend returns one of three shapes depending on the handler:
      //   { detail: "..." }                  (axios interceptor fallback)
      //   { error: { message: "..." } }      (custom HTTP/Integrity handler)
      //   { error: { detail: "..." } }       (older shape)
      // Surface the most specific, field-aware message to the admin so they
      // know exactly which field needs correction.
      const data = error.response?.data;
      const errorMessage =
        getFormErrorMessage(error, { t }) ||
        data?.detail ||
        data?.error?.detail ||
        t('errorCreatingAccount');
      nassaqError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyWelcomeMessage = () => {
    if (!createdStudent || !createdParent) return;
    const loginUrl = window.location.origin + '/login';
    const isRealParentEmail = (email) => {
      if (!email) return false;
      const trimmed = String(email).trim();
      if (!trimmed || trimmed.toLowerCase() === 'null') return false;
      if (trimmed.endsWith('@nassaq.local')) return false;
      return true;
    };
    const studentLines = [
      `📛 اسم الطالب: ${createdStudent.full_name}`,
      `🆔 رقم الطالب: ${createdStudent.student_id}`,
    ];
    if (isRealParentEmail(createdStudent.email)) {
      studentLines.push(`📧 البريد الإلكتروني: ${createdStudent.email}`);
    }
    studentLines.push(`🔑 كلمة المرور المؤقتة: ${createdStudent.temp_password}`);

    const parentLines = [`👤 اسم ولي الأمر: ${createdParent.full_name}`];
    if (isRealParentEmail(createdParent.email)) {
      parentLines.push(`📧 البريد الإلكتروني: ${createdParent.email}`);
    }
    if (createdParent.phone) {
      parentLines.push(`📱 رقم الهاتف: ${createdParent.phone}`);
    }
    parentLines.push(
      createdParent.is_new
        ? `🔑 كلمة المرور المؤقتة: ${createdParent.temp_password}`
        : '(حساب ولي الأمر موجود مسبقًا)'
    );

    const message = `السلام عليكم ورحمة الله وبركاته\n\nولي الأمر الكريم / ${createdParent.full_name}\n\nيسعدنا إبلاغكم بأنه تم إتمام تسجيل الطالب ${createdStudent.full_name} بنجاح داخل المدرسة عبر منصة نَسَّق | NASSAQ.\n\nأولًا: بيانات الطالب\n━━━━━━━━━━━━━━━━━━━━\n${studentLines.join('\n')}\n\nثانيًا: بيانات ولي الأمر\n━━━━━━━━━━━━━━━━━━━━\n${parentLines.join('\n')}\n\n🔗 رابط الدخول للمنصة:\n${loginUrl}\n\n━━━━━━━━━━━━━━━━━━━━\nنرجو تغيير كلمة المرور عند أول تسجيل دخول.\n\nمع خالص التحية،\nإدارة المدرسة\nمنصة نَسَّق | NASSAQ`;
    navigator.clipboard.writeText(message);
    setCopiedMessage(true);
    setTimeout(() => setCopiedMessage(false), 2000);
    toast.success(t('welcomeMessageCopied'));
  };

  const downloadQRCode = () => {
    if (!createdStudent?.qr_code) return;
    const link = document.createElement('a');
    link.href = `data:image/png;base64,${createdStudent.qr_code}`;
    link.download = `student_${createdStudent.student_id}_qr.png`;
    link.click();
    toast.success(t('qrCodeDownloaded'));
  };

  const resetForm = () => {
    setStep(1);
    setStudentData({
      full_name: '',
      email: '',
      national_id: '',
      gender: 'male',
      date_of_birth: '',
      education_level: preselectedEducationLevel || '',
      grade_id: preselectedGradeId || '',
      class_id: preselectedClassId || '',
    });
    setParentData({ full_name: '', national_id: '', phone: '', email: '', relationship: 'father', address: '' });
    setHealthData({ health_status: '', allergies: '', medications: '', special_needs: '', notes: '' });
    setExistingParent(null);
    setSiblings([]);
    setLinkToExisting(false);
    setCreatedStudent(null);
    setCreatedParent(null);
    setSelectedExistingParent(null);
    setParentSearchResults([]);
    setParentSearchQuery('');
    setParentMode('new');
    setInternalGrades([]);
    setGradesLoadError(false);
    setIsLoadingGrades(false);
    gradesFetchedRef.current = false;
  };

  return (
    <Dialog open={open} onOpenChange={(val) => { if (!val) resetForm(); onOpenChange(val); }}>
      <DialogContent className="max-w-3xl h-[85vh] flex flex-col p-0 gap-0 overflow-hidden" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="bg-gradient-to-r from-brand-navy to-brand-navy/90 text-white px-6 py-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
            <div>
              <DialogTitle className="font-cairo text-lg text-white">{t('addNewStudent')}</DialogTitle>
              <DialogDescription className="text-white/70 text-xs">
                {t('step')} {Math.min(step, 4)} {isRTL ? 'من' : 'of'} 4
              </DialogDescription>
            </div>
          </div>
        </div>

        {step < 5 && <StepProgress currentStep={step} steps={STEPS} isRTL={isRTL} />}

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {step === 1 && (
            <div className="space-y-5">
              <SectionHeader icon={GraduationCap} title={t('studentBasicInformation')} subtitle={t('enterTheStudentBasicInfo')} color="blue" />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField label={t('fullName')} required>
                  <Input
                    value={studentData.full_name}
                    onChange={(e) => setStudentData({...studentData, full_name: e.target.value})}
                    placeholder={t('enterFullName')}
                    className="h-10 rounded-lg"
                  />
                </FormField>

                <FormField label={t('gender')} required>
                  <div className="flex gap-2">
                    {[
                      { val: 'male', ar: 'ذكر', en: 'Male', color: 'blue' },
                      { val: 'female', ar: 'أنثى', en: 'Female', color: 'pink' },
                    ].map(g => (
                      <button
                        key={g.val}
                        type="button"
                        onClick={() => setStudentData({...studentData, gender: g.val})}
                        className={`flex-1 h-10 rounded-lg border-2 text-sm font-medium transition-all ${
                          studentData.gender === g.val
                            ? g.color === 'blue' ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : 'border-pink-500 bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300'
                            : 'border-border hover:border-muted-foreground/40'
                        }`}
                      >
                        {isRTL ? g.ar : g.en}
                      </button>
                    ))}
                  </div>
                </FormField>

                <FormField label={t('dateOfBirth')} required>
                  <Input type="date" value={studentData.date_of_birth} onChange={(e) => setStudentData({...studentData, date_of_birth: e.target.value})} className="h-10 rounded-lg" />
                </FormField>

                <FormField label={t('nationalId')}>
                  <Input value={studentData.national_id} onChange={(e) => setStudentData({...studentData, national_id: e.target.value})} className="h-10 rounded-lg" dir="ltr" placeholder="10xxxxxxxxxx" />
                </FormField>

                <FormField label={t('email2')}>
                  <Input type="email" value={studentData.email} onChange={(e) => setStudentData({...studentData, email: e.target.value})} placeholder="student@example.com" className="h-10 rounded-lg" dir="ltr" />
                </FormField>
              </div>

              <div className="border-t pt-4 mt-2">
                <p className="text-xs font-semibold text-muted-foreground mb-3 flex items-center gap-1.5">
                  <GraduationCap className="h-3.5 w-3.5" />
                  {t('academicInformation')}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <FormField label={t('educationLevel')} required>
                    <Select value={studentData.education_level} onValueChange={(val) => setStudentData(prev => {
                      // Preserve grade only when it still belongs to the new stage; otherwise clear it.
                      const currentGrade = allGrades.find(g => g.id === prev.grade_id);
                      const keepGrade = currentGrade && gradeBelongsToStage(currentGrade, val);
                      return { ...prev, education_level: val, grade_id: keepGrade ? prev.grade_id : '' };
                    })} disabled={lockEducation}>
                      <SelectTrigger className="h-10 rounded-lg"><SelectValue placeholder={t('selectLevel')} /></SelectTrigger>
                      <SelectContent>
                        {EDUCATION_LEVELS.map(level => (<SelectItem key={level.id} value={level.id}>{isRTL ? level.name_ar : level.name_en}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>

                  <FormField label={t('grade')} required>
                    {(() => {
                      const stageFiltered = filterGradesByStage(allGrades, studentData.education_level);
                      const stageSelected = Boolean(studentData.education_level);
                      return (
                        <div className="space-y-1.5">
                          <Select
                            value={studentData.grade_id}
                            onValueChange={(val) => setStudentData({ ...studentData, grade_id: val })}
                            disabled={lockGrade || !stageSelected || isLoadingGrades}
                          >
                            <SelectTrigger className="h-10 rounded-lg">
                              {isLoadingGrades ? (
                                <span className="flex items-center gap-2 text-muted-foreground text-sm">
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  {isRTL ? 'جاري التحميل…' : 'Loading…'}
                                </span>
                              ) : (
                                <SelectValue placeholder={!stageSelected ? (isRTL ? 'اختر المرحلة أولاً' : 'Select stage first') : t('selectGrade')} />
                              )}
                            </SelectTrigger>
                            <SelectContent>
                              {!stageSelected ? (
                                <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                                  {isRTL ? 'اختر المرحلة التعليمية أولاً' : 'Select an educational stage first'}
                                </div>
                              ) : stageFiltered.length > 0 ? (
                                stageFiltered.map(grade => (
                                  <SelectItem key={grade.id} value={grade.id}>
                                    {isRTL ? (grade.name_ar || grade.name) : (grade.name_en || grade.name)}
                                  </SelectItem>
                                ))
                              ) : (
                                <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                                  {isRTL ? 'لا توجد صفوف لهذه المرحلة' : 'No grades for this stage'}
                                </div>
                              )}
                            </SelectContent>
                          </Select>
                          {gradesLoadError && allGrades.length === 0 && (
                            <div className="flex items-center gap-2 mt-1">
                              <p className="text-xs text-red-500 flex-1">
                                {isRTL ? 'تعذّر تحميل الصفوف' : 'Failed to load grades'}
                              </p>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-6 text-xs rounded-md px-2"
                                onClick={fetchGrades}
                                disabled={isLoadingGrades}
                              >
                                {isLoadingGrades ? <Loader2 className="h-3 w-3 animate-spin" /> : (isRTL ? 'إعادة المحاولة' : 'Retry')}
                              </Button>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </FormField>

                  <FormField label={t('class')} required={classes.length > 0}>
                    <Select value={studentData.class_id} onValueChange={(val) => setStudentData({...studentData, class_id: val})} disabled={lockClass}>
                      <SelectTrigger className="h-10 rounded-lg"><SelectValue placeholder={t('selectClass')} /></SelectTrigger>
                      <SelectContent>
                        {classes.length > 0 ? (
                          classes.map(cls => (<SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>))
                        ) : (
                          <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                            {isRTL ? 'لا توجد فصول متاحة' : 'No classes available'}
                          </div>
                        )}
                      </SelectContent>
                    </Select>
                  </FormField>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <SectionHeader
                icon={Users}
                title={isRTL ? 'بيانات ولي الأمر' : 'Parent Information'}
                subtitle={isWorkspaceMode
                  ? (isRTL ? 'اختياري — يمكنك تخطّي هذه الخطوة وربط ولي الأمر لاحقاً' : 'Optional — you can skip and link a parent later')
                  : t('addNewOrLinkExistingParent')}
                color="green"
              />

              {!isWorkspaceMode && (
              <div className="grid grid-cols-2 gap-2 p-1 bg-muted/50 rounded-xl">
                <button
                  type="button"
                  className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    parentMode === 'new' ? 'bg-brand-navy text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => { setParentMode('new'); setSelectedExistingParent(null); setParentSearchResults([]); setParentSearchQuery(''); }}
                >
                  <UserPlus className="h-4 w-4" />
                  {t('newParent')}
                </button>
                <button
                  type="button"
                  className={`flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    parentMode === 'search' ? 'bg-brand-navy text-white shadow-sm' : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => { setParentMode('search'); setExistingParent(null); setLinkToExisting(false); }}
                >
                  <Link2 className="h-4 w-4" />
                  {t('linkExisting')}
                </button>
              </div>
              )}

              {!isWorkspaceMode && parentMode === 'search' && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/50 dark:bg-blue-950/20">
                    <p className="text-xs text-blue-600 dark:text-blue-400 mb-2.5">
                      {t('searchForAnExistingParentToLinkThisStudent')}
                    </p>
                    <div className="relative">
                      <Search className={`absolute ${isRTL ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground`} />
                      <Input
                        value={parentSearchQuery}
                        onChange={(e) => handleParentSearch(e.target.value)}
                        placeholder={t('searchByNameOrPhone')}
                        className={`h-10 rounded-lg ${isRTL ? 'pr-10' : 'pl-10'}`}
                        data-testid="parent-search-input"
                      />
                      {searchingParents && <Loader2 className={`absolute ${isRTL ? 'left-3' : 'right-3'} top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground`} />}
                    </div>
                  </div>

                  {parentSearchResults.length > 0 && (
                    <div className="max-h-48 overflow-y-auto space-y-2 border rounded-xl p-2">
                      {parentSearchResults.map((parent) => (
                        <div
                          key={parent.id}
                          className="p-3 rounded-lg border hover:border-brand-navy hover:bg-blue-50/50 dark:hover:bg-blue-950/20 cursor-pointer transition-all"
                          onClick={() => selectParentFromSearch(parent)}
                          data-testid={`parent-result-${parent.id}`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                                <User className="h-4 w-4 text-blue-600" />
                              </div>
                              <div>
                                <p className="font-medium text-sm">{parent.full_name}</p>
                                <p className="text-xs text-muted-foreground flex items-center gap-1.5"><Phone className="h-3 w-3" /> {parent.phone}</p>
                              </div>
                            </div>
                            {parent.children_count > 0 && (
                              <Badge variant="secondary" className="text-[10px]">{parent.children_count} {t('children')}</Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {parentSearchQuery.length >= 2 && !searchingParents && parentSearchResults.length === 0 && (
                    <div className="p-6 rounded-xl border border-dashed text-center text-muted-foreground">
                      <Search className="h-6 w-6 mx-auto mb-2 opacity-40" />
                      <p className="text-sm">{t('noResultsFound')}</p>
                    </div>
                  )}

                  {selectedExistingParent && (
                    <div className="p-4 rounded-xl border-2 border-emerald-400 bg-emerald-50 dark:bg-emerald-950/20">
                      <div className="flex items-start gap-3">
                        <UserCheck className="h-5 w-5 text-emerald-600 mt-0.5" />
                        <div className="flex-1">
                          <p className="font-semibold text-sm text-emerald-800 dark:text-emerald-300">{t('parentSelected')}</p>
                          <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1">{selectedExistingParent.full_name} - {selectedExistingParent.phone}</p>
                          {siblings.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mt-2">
                              {siblings.map((s, idx) => (<Badge key={idx} variant="secondary" className="text-[10px]">{s.name || s.full_name}</Badge>))}
                            </div>
                          )}
                          <Button size="sm" variant="outline" className="mt-3 h-7 text-xs rounded-lg" onClick={() => {
                            setSelectedExistingParent(null);
                            setParentData({ full_name: '', national_id: '', phone: '', email: '', relationship: 'father', address: '' });
                            setSiblings([]);
                            setLinkToExisting(false);
                          }}>
                            {t('clearSelection')}
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {!isWorkspaceMode && parentMode === 'new' && existingParent && (
                <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-950/20">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
                    <div className="flex-1">
                      <p className="font-semibold text-sm text-amber-800">{t('existingParentFound')}</p>
                      <p className="text-xs text-amber-700 mt-1">{existingParent.full_name} - {existingParent.phone}</p>
                      {siblings.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">{siblings.map(s => (<Badge key={s.id} variant="secondary" className="text-[10px]">{s.name}</Badge>))}</div>
                      )}
                      <div className="flex gap-2 mt-3">
                        <Button size="sm" variant={linkToExisting ? "default" : "outline"} onClick={() => setLinkToExisting(true)} className="h-7 text-xs rounded-lg">{t('yesLink')}</Button>
                        <Button size="sm" variant={!linkToExisting ? "default" : "outline"} onClick={() => setLinkToExisting(false)} className="h-7 text-xs rounded-lg">{t('noCreateNew')}</Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {parentMode === 'new' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField label={isRTL ? 'اسم ولي الأمر' : 'Parent Name'} required={!isWorkspaceMode}>
                    <Input value={parentData.full_name} onChange={(e) => setParentData({...parentData, full_name: e.target.value})} className="h-10 rounded-lg" />
                  </FormField>
                  <FormField label={t('relationship')} required={!isWorkspaceMode}>
                    <Select value={parentData.relationship} onValueChange={(val) => setParentData({...parentData, relationship: val})}>
                      <SelectTrigger className="h-10 rounded-lg"><SelectValue /></SelectTrigger>
                      <SelectContent>{RELATIONSHIPS.map(rel => (<SelectItem key={rel.id} value={rel.id}>{isRTL ? rel.name_ar : rel.name_en}</SelectItem>))}</SelectContent>
                    </Select>
                  </FormField>
                  <FormField label={t('phone3')} required={!isWorkspaceMode}>
                    <Input value={parentData.phone} onChange={(e) => setParentData({...parentData, phone: e.target.value})} onBlur={checkParentExists} placeholder="05xxxxxxxx" className="h-10 rounded-lg" dir="ltr" />
                  </FormField>
                  <FormField label={t('email2')}>
                    <Input type="email" value={parentData.email} onChange={(e) => setParentData({...parentData, email: e.target.value})} onBlur={checkParentExists} className="h-10 rounded-lg" dir="ltr" />
                  </FormField>
                  <FormField label={t('nationalId')}>
                    <Input value={parentData.national_id} onChange={(e) => setParentData({...parentData, national_id: e.target.value})} onBlur={checkParentExists} className="h-10 rounded-lg" dir="ltr" />
                  </FormField>
                  <FormField label={t('address')}>
                    <Input value={parentData.address} onChange={(e) => setParentData({...parentData, address: e.target.value})} className="h-10 rounded-lg" />
                  </FormField>
                </div>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-5">
              <SectionHeader icon={Heart} title={t('healthInformation')} subtitle={t('allFieldsAreOptional')} color="rose" />
              <div className="p-3 rounded-lg bg-rose-50/50 dark:bg-rose-950/10 border border-rose-200/50 text-xs text-rose-600 dark:text-rose-400 flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 shrink-0" />
                {t('thisInformationIsConfidentialAndUsedOnlyForSchoolH')}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <FormField label={t('generalHealthStatus')}>
                    <Textarea value={healthData.health_status} onChange={(e) => setHealthData({...healthData, health_status: e.target.value})} className="rounded-lg resize-none" rows={2} placeholder={t('egGoodHealthCondition')} />
                  </FormField>
                </div>
                <FormField label={t('allergies2')}>
                  <Input value={healthData.allergies} onChange={(e) => setHealthData({...healthData, allergies: e.target.value})} className="h-10 rounded-lg" placeholder={t('separateWithCommas')} />
                </FormField>
                <FormField label={t('medications')}>
                  <Input value={healthData.medications} onChange={(e) => setHealthData({...healthData, medications: e.target.value})} className="h-10 rounded-lg" placeholder={t('separateWithCommas')} />
                </FormField>
                <div className="md:col-span-2">
                  <FormField label={t('specialNeeds')}>
                    <Textarea value={healthData.special_needs} onChange={(e) => setHealthData({...healthData, special_needs: e.target.value})} className="rounded-lg resize-none" rows={2} />
                  </FormField>
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <SectionHeader icon={FileText} title={t('reviewBeforeSaving')} subtitle={t('verifyAllInformationIsCorrect')} color="amber" />

              <div className="rounded-xl border overflow-hidden">
                <div className="px-4 py-2.5 bg-blue-50 dark:bg-blue-950/20 border-b flex items-center gap-2">
                  <GraduationCap className="h-4 w-4 text-blue-600" />
                  <span className="font-semibold text-sm text-blue-800 dark:text-blue-300">{t('student2')}</span>
                </div>
                <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                  <div><span className="text-muted-foreground text-xs">{t('name')}</span><p className="font-medium">{studentData.full_name}</p></div>
                  <div><span className="text-muted-foreground text-xs">{t('gender')}</span><p className="font-medium">{studentData.gender === 'male' ? (t('male')) : (t('female'))}</p></div>
                  <div><span className="text-muted-foreground text-xs">{isRTL ? 'تاريخ الميلاد' : 'DOB'}</span><p className="font-medium">{studentData.date_of_birth}</p></div>
                  {studentData.education_level && <div><span className="text-muted-foreground text-xs">{t('level')}</span><p className="font-medium">{EDUCATION_LEVELS.find(l => l.id === studentData.education_level)?.[isRTL ? 'name_ar' : 'name_en']}</p></div>}
                </div>
              </div>

              <div className="rounded-xl border overflow-hidden">
                <div className="px-4 py-2.5 bg-green-50 dark:bg-green-950/20 border-b flex items-center gap-2">
                  <Users className="h-4 w-4 text-green-600" />
                  <span className="font-semibold text-sm text-green-800 dark:text-green-300">{t('parent')}</span>
                  {(selectedExistingParent || linkToExisting) && <Badge className="text-[10px] bg-amber-100 text-amber-700">{t('existing')}</Badge>}
                </div>
                <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                  <div><span className="text-muted-foreground text-xs">{t('name')}</span><p className="font-medium">{parentData.full_name}</p></div>
                  <div><span className="text-muted-foreground text-xs">{t('phone2')}</span><p className="font-medium" dir="ltr">{parentData.phone}</p></div>
                  <div><span className="text-muted-foreground text-xs">{t('relation')}</span><p className="font-medium">{RELATIONSHIPS.find(r => r.id === parentData.relationship)?.[isRTL ? 'name_ar' : 'name_en']}</p></div>
                </div>
              </div>

              {(healthData.health_status || healthData.allergies || healthData.medications) && (
                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-rose-50 dark:bg-rose-950/20 border-b flex items-center gap-2">
                    <Heart className="h-4 w-4 text-rose-500" />
                    <span className="font-semibold text-sm text-rose-800 dark:text-rose-300">{isRTL ? 'البيانات الصحية' : 'Health'}</span>
                  </div>
                  <div className="p-4 text-sm space-y-1">
                    {healthData.health_status && <p><span className="text-muted-foreground">{t('status')}</span> {healthData.health_status}</p>}
                    {healthData.allergies && <p><span className="text-muted-foreground">{t('allergies3')}</span> {healthData.allergies}</p>}
                    {healthData.medications && <p><span className="text-muted-foreground">{t('medications2')}</span> {healthData.medications}</p>}
                  </div>
                </div>
              )}
            </div>
          )}

          {step === 5 && createdStudent && (
            <div className="space-y-5 py-2">
              <div className="text-center">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-emerald-400 to-green-600 mx-auto flex items-center justify-center mb-4 shadow-lg shadow-emerald-500/20">
                  <CheckCircle2 className="h-8 w-8 text-white" />
                </div>
                <h2 className="text-xl font-bold text-emerald-600 font-cairo mb-1">{t('accountCreated')}</h2>
                <p className="text-sm text-muted-foreground">{t('studentAndParentAccountsCreated')}</p>
              </div>

              <div className="p-4 rounded-xl border-2 border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20">
                <div className="flex items-start gap-4">
                  {createdStudent.qr_code && (
                    <div className="shrink-0">
                      <img src={`data:image/png;base64,${createdStudent.qr_code}`} alt="QR" className="w-20 h-20 rounded-lg border" />
                      <Button size="sm" variant="ghost" className="w-full mt-1 h-6 text-[10px]" onClick={downloadQRCode}>
                        <Download className="h-3 w-3 me-1" /> {isRTL ? 'تحميل' : 'Save'}
                      </Button>
                    </div>
                  )}
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'رقم الطالب' : 'Student ID'}</p>
                        <p className="font-bold font-mono text-brand-navy">{createdStudent.student_id}</p>
                      </div>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { navigator.clipboard.writeText(createdStudent.student_id); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                        {copied ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs p-2 bg-white dark:bg-background rounded-lg">
                      <div><span className="text-muted-foreground">{t('email3')}</span><p className="font-mono">{createdStudent.email}</p></div>
                      <div><span className="text-muted-foreground">{t('password2')}</span><p className="font-mono">{createdStudent.temp_password}</p></div>
                    </div>
                  </div>
                </div>
              </div>

              {createdParent && (
                <div className="p-4 rounded-xl border bg-blue-50/50 dark:bg-blue-950/20">
                  <p className="text-xs font-semibold text-blue-700 dark:text-blue-300 mb-2 flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5" />
                    {isRTL ? 'بيانات ولي الأمر' : 'Parent Account'}
                    {createdParent.is_new ? (
                      <Badge className="text-[9px] h-4 bg-emerald-100 text-emerald-700 border-0">{t('new2')}</Badge>
                    ) : (
                      <Badge className="text-[9px] h-4 bg-amber-100 text-amber-700 border-0">{t('existing')}</Badge>
                    )}
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><span className="text-muted-foreground">{t('name2')}</span><p className="font-medium">{createdParent.full_name}</p></div>
                    <div><span className="text-muted-foreground">{t('phone4')}</span><p className="font-mono" dir="ltr">{createdParent.phone}</p></div>
                    {createdParent.email && <div><span className="text-muted-foreground">{t('email3')}</span><p className="font-mono" dir="ltr">{createdParent.email}</p></div>}
                    {createdParent.is_new && createdParent.temp_password && (
                      <div><span className="text-muted-foreground">{t('password2')}</span><p className="font-mono">{createdParent.temp_password}</p></div>
                    )}
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <Button variant="outline" className="flex-1 h-10 rounded-lg" onClick={copyWelcomeMessage}>
                  {copiedMessage ? <CheckCircle2 className="h-4 w-4 me-2 text-emerald-500" /> : <Copy className="h-4 w-4 me-2" />}
                  {t('copyWelcomeMessage')}
                </Button>
              </div>

              <div className="flex justify-center gap-3 pt-2">
                <Button variant="outline" className="rounded-lg" onClick={() => onOpenChange(false)}>{t('close')}</Button>
                <Button className="rounded-lg bg-brand-navy hover:bg-brand-navy/90" onClick={resetForm}>{t('addAnother')}</Button>
              </div>
            </div>
          )}
        </div>

        {step < 5 && (
          <div className="flex items-center justify-between px-6 py-3 border-t bg-muted/20 flex-shrink-0">
            <div>
              {step > 1 && (
                <Button variant="ghost" size="sm" onClick={prevStep} className="gap-1.5 rounded-lg h-9">
                  {isRTL ? <ArrowRight className="h-3.5 w-3.5" /> : <ArrowLeft className="h-3.5 w-3.5" />}
                  {t('back')}
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="rounded-lg h-9" onClick={() => onOpenChange(false)}>{t('cancel')}</Button>
              {step < 4 ? (
                <Button size="sm" onClick={nextStep} disabled={!isStepValid()} className="bg-brand-navy hover:bg-brand-navy/90 gap-1.5 rounded-lg h-9 px-5">
                  {t('next')}
                  {isRTL ? <ArrowLeft className="h-3.5 w-3.5" /> : <ArrowRight className="h-3.5 w-3.5" />}
                </Button>
              ) : (
                <Button size="sm" onClick={handleSubmit} disabled={isSubmitting} className="bg-emerald-600 hover:bg-emerald-700 gap-1.5 rounded-lg h-9 px-5">
                  {isSubmitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  {t('confirmSave')}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
