import { useState, useEffect } from 'react';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { useCanViewInternalIds } from '../../hooks/useCanViewInternalIds';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
// Loading-indicator standardization swept `<LoadingState>` into this wizard
// without its import — a runtime-only ReferenceError (webpack doesn't fail on
// free variables), so the class option crashed to the global error boundary.
import { LoadingState } from '../ui/LoadingState';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Textarea } from '../../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import { EDUCATION_STAGES, filterGradesByStage, gradeBelongsToStage, normalizeStage, availableStagesFromGrades } from '../../utils/stageGrade';
import { getFormErrorMessage } from '../../utils/apiError';
import {
  ArrowLeft,
  ArrowRight,
  Loader2,
  CheckCircle2,
  School,
  Users,
  User,
  FileText,
  MapPin,
  Building,
  Search,
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
            className="h-full bg-gradient-to-r from-violet-500 via-purple-500 to-fuchsia-500 rounded-full transition-all duration-500 ease-out"
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
                  isActive ? 'bg-purple-600 border-purple-600 text-white scale-110 shadow-lg shadow-purple-500/30' :
                  'bg-background border-muted-foreground/20 text-muted-foreground'
                }`}>
                  {isDone ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                </div>
                <span className={`text-[10px] mt-1.5 font-medium transition-colors ${
                  isActive ? 'text-purple-700 dark:text-purple-400' : isDone ? 'text-emerald-600' : 'text-muted-foreground'
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

const SectionHeader = ({ icon: Icon, title, subtitle, color = 'purple' }) => {
  const colors = {
    purple: 'from-violet-500 to-purple-600',
    green: 'from-emerald-500 to-green-600',
    blue: 'from-blue-500 to-indigo-600',
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

export const CreateClassWizard = ({ open, onOpenChange, onSuccess }) => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { token, api } = useAuth();
  const canViewInternalIds = useCanViewInternalIds();
  const { nassaqError } = useNassaqAlert();

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [data, setData] = useState({ capacity: 30, class_type: 'regular', student_ids: [] });
  const [options, setOptions] = useState({ grades: [], teachers: [], students: [], classTypes: [] });
  const [studentSearch, setStudentSearch] = useState('');

  const handleCloseDialog = (val) => {
    if (val === true) return;
    handleReset();
    if (onOpenChange) onOpenChange(false);
  };

  useEffect(() => {
    if (open) fetchOptions();
  }, [open]);

  const apiClient = api;

  const fetchOptions = async () => {
    setLoading(true);
    try {
      const [gradesRes, teachersRes, studentsRes, typesRes] = await Promise.all([
        apiClient.get('/classes/options/grades').catch(() => ({ data: { grades: [] } })),
        apiClient.get('/classes/options/teachers').catch(() => ({ data: { teachers: [] } })),
        apiClient.get('/classes/options/students').catch(() => ({ data: { students: [] } })),
        apiClient.get('/classes/options/class-types').catch(() => ({ data: { types: [] } })),
      ]);
      setOptions({
        grades: gradesRes.data.grades || [],
        teachers: teachersRes.data.teachers || [],
        students: studentsRes.data.students || [],
        classTypes: typesRes.data.types || [
          { code: 'regular', name_ar: 'عادي', name_en: 'Regular' },
          { code: 'advanced', name_ar: 'متقدم', name_en: 'Advanced' },
        ],
      });
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const validateStep = (step) => {
    const newErrors = {};
    if (step === 1) {
      if (!data.name_ar?.trim()) newErrors.name_ar = t('required');
      if (!data.stage) newErrors.stage = t('required');
      if (!data.grade_id) newErrors.grade_id = t('required');
      if (data.stage && data.grade_id) {
        const g = (options.grades || []).find(x => x.id === data.grade_id);
        if (g && !gradeBelongsToStage(g, data.stage)) newErrors.grade_id = isRTL ? 'الصف لا ينتمي للمرحلة المختارة' : 'Grade does not belong to selected stage';
      }
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validateStep(currentStep)) return;
    if (currentStep < 4) setCurrentStep(prev => prev + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(prev => prev - 1);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const response = await apiClient.post('/classes/create', data);
      if (response.data.success) {
        setResult(response.data);
        setCurrentStep(5);
        toast.success(t('classCreated'));
        if (onSuccess) onSuccess(response.data);
      } else {
        nassaqError(response.data.error || (t('errorOccurred')));
      }
    } catch (error) {
      let errorMessage = getFormErrorMessage(error, { t });
      if (!errorMessage) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string') errorMessage = detail;
        else if (Array.isArray(detail) && detail.length > 0) errorMessage = detail.map(d => d.msg || d.message || JSON.stringify(d)).join(', ');
        else if (detail && typeof detail === 'object') errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        else errorMessage = t('errorOccurred');
      }
      nassaqError(errorMessage);
      console.error('Create class error:', error.response?.data);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setCurrentStep(1);
    setData({ capacity: 30, class_type: 'regular', student_ids: [] });
    setErrors({});
    setResult(null);
    setStudentSearch('');
  };

  const onChange = (k, v) => setData(p => ({ ...p, [k]: v }));

  const toggleStudent = (studentId) => {
    const current = data.student_ids || [];
    const updated = current.includes(studentId) ? current.filter(id => id !== studentId) : [...current, studentId];
    onChange('student_ids', updated);
  };

  const filteredStudents = (options.students || []).filter(s => {
    // Students with an UNKNOWN grade (legacy rows without a canonical
    // grade) must stay visible — hiding them made step 3 show
    // "لا يوجد طلاب متاحين" for the whole roster and left legacy students
    // unassignable from this wizard.
    const matchGrade = !data.grade_id || !s.grade_id || s.grade_id === data.grade_id;
    const matchSearch = !studentSearch || (s.full_name_ar || s.full_name_en || '').toLowerCase().includes(studentSearch.toLowerCase());
    return matchGrade && matchSearch;
  });

  const getGradeName = (id) => options.grades?.find(g => g.id === id)?.[isRTL ? 'name_ar' : 'name_en'] || id;
  const getTeacherName = (id) => options.teachers?.find(tc => tc.teacher_id === id)?.full_name_ar || '';

  const steps = [
    { num: 1, title: t('info'), icon: School },
    { num: 2, title: t('teacher2'), icon: User },
    { num: 3, title: t('students'), icon: Users },
    { num: 4, title: t('review2'), icon: FileText },
  ];

  return (
    <Dialog open={open} onOpenChange={handleCloseDialog}>
      <DialogContent className="max-w-3xl h-[85vh] flex flex-col p-0 gap-0 overflow-hidden" data-testid="create-class-wizard" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="bg-gradient-to-r from-purple-700 to-violet-600 text-white px-6 py-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
              <School className="h-5 w-5 text-white" />
            </div>
            <div>
              <DialogTitle className="font-cairo text-lg text-white">{t('createNewClass')}</DialogTitle>
              <DialogDescription className="text-white/70 text-xs">
                {t('step')} {Math.min(currentStep, 4)} {isRTL ? 'من' : 'of'} 4
              </DialogDescription>
            </div>
          </div>
        </div>

        {currentStep < 5 && <StepProgress currentStep={currentStep} steps={steps} isRTL={isRTL} />}

        {loading ? (
          <LoadingState variant="section" className="flex-1" />
        ) : (
          <div className="flex-1 overflow-y-auto px-6 py-4">
            {currentStep === 1 && (
              <div className="space-y-5">
                <SectionHeader icon={School} title={t('classInformation')} subtitle={t('enterBasicClassDetails')} color="purple" />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField label={t('classNameArabic')} required error={errors.name_ar}>
                    <Input value={data.name_ar || ''} onChange={(e) => onChange('name_ar', e.target.value)} placeholder={t('example1a')} className={`h-10 rounded-lg ${errors.name_ar ? 'border-red-500' : ''}`} data-testid="class-name-ar" />
                  </FormField>
                  <FormField label={t('classNameEnglish')}>
                    <Input value={data.name_en || ''} onChange={(e) => onChange('name_en', e.target.value)} dir="ltr" className="h-10 rounded-lg" data-testid="class-name-en" />
                  </FormField>
                  <FormField label={isRTL ? 'المرحلة التعليمية' : 'Educational Stage'} required error={errors.stage}>
                    {(() => {
                      const stagesWithRows = availableStagesFromGrades(options.grades);
                      const stageList = stagesWithRows.length > 0 ? stagesWithRows : EDUCATION_STAGES;
                      return (
                        <Select
                          value={data.stage || ''}
                          onValueChange={(val) => setData(prev => {
                            const currentGrade = (options.grades || []).find(g => g.id === prev.grade_id);
                            const keepGrade = currentGrade && gradeBelongsToStage(currentGrade, val);
                            return { ...prev, stage: val, grade_id: keepGrade ? prev.grade_id : '' };
                          })}
                        >
                          <SelectTrigger className={`h-10 rounded-lg ${errors.stage ? 'border-red-500' : ''}`} data-testid="class-stage">
                            <SelectValue placeholder={isRTL ? 'اختر المرحلة' : 'Select Stage'} />
                          </SelectTrigger>
                          <SelectContent>
                            {stageList.map((s) => (
                              <SelectItem key={s.id} value={s.id}>{isRTL ? s.name_ar : s.name_en}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      );
                    })()}
                  </FormField>
                  <FormField label={t('grade2')} required error={errors.grade_id}>
                    {(() => {
                      const stageSelected = Boolean(data.stage);
                      const filtered = filterGradesByStage(options.grades, data.stage);
                      return (
                        <Select value={data.grade_id || ''} onValueChange={(val) => onChange('grade_id', val)} disabled={!stageSelected}>
                          <SelectTrigger className={`h-10 rounded-lg ${errors.grade_id ? 'border-red-500' : ''}`} data-testid="class-grade">
                            <SelectValue placeholder={!stageSelected ? (isRTL ? 'اختر المرحلة أولاً' : 'Select stage first') : (isRTL ? 'اختر الصف' : 'Select Grade')} />
                          </SelectTrigger>
                          <SelectContent>
                            {!stageSelected ? (
                              <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                                {isRTL ? 'اختر المرحلة التعليمية أولاً' : 'Select an educational stage first'}
                              </div>
                            ) : filtered.length > 0 ? (
                              filtered.map((g) => (<SelectItem key={g.id} value={g.id}>{isRTL ? g.name_ar : g.name_en}</SelectItem>))
                            ) : (
                              <div className="px-2 py-3 text-xs text-muted-foreground text-center">
                                {isRTL ? 'لا توجد صفوف لهذه المرحلة' : 'No grades for this stage'}
                              </div>
                            )}
                          </SelectContent>
                        </Select>
                      );
                    })()}
                  </FormField>
                  <FormField label={t('classType')}>
                    <Select value={data.class_type || 'regular'} onValueChange={(val) => onChange('class_type', val)}>
                      <SelectTrigger className="h-10 rounded-lg" data-testid="class-type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {options.classTypes?.map((ct) => (<SelectItem key={ct.code} value={ct.code}>{isRTL ? ct.name_ar : ct.name_en}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </FormField>
                  <FormField label={t('capacity')}>
                    <Input type="number" value={data.capacity || 30} onChange={(e) => onChange('capacity', parseInt(e.target.value) || 30)} min="1" max="50" className="h-10 rounded-lg" data-testid="class-capacity" />
                  </FormField>
                </div>

                <div className="border-t pt-4 mt-2">
                  <p className="text-xs font-semibold text-muted-foreground mb-3 flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5" />
                    {t('locationOptional')}
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <FormField label={t('roomNumber')}>
                      <Input value={data.room_number || ''} onChange={(e) => onChange('room_number', e.target.value)} className="h-10 rounded-lg" data-testid="class-room" />
                    </FormField>
                    <FormField label={t('floor')}>
                      <Input type="number" value={data.floor || ''} onChange={(e) => onChange('floor', parseInt(e.target.value) || '')} className="h-10 rounded-lg" data-testid="class-floor" />
                    </FormField>
                    <FormField label={t('building')}>
                      <Input value={data.building || ''} onChange={(e) => onChange('building', e.target.value)} className="h-10 rounded-lg" data-testid="class-building" />
                    </FormField>
                  </div>
                </div>
              </div>
            )}

            {currentStep === 2 && (
              <div className="space-y-5">
                <SectionHeader icon={User} title={t('homeroomTeacher')} subtitle={t('selectHomeroomTeacherOptional')} color="green" />
                <FormField label={t('homeroomTeacher')}>
                  <Select value={data.homeroom_teacher_id || 'none'} onValueChange={(val) => onChange('homeroom_teacher_id', val === 'none' ? null : val)}>
                    <SelectTrigger className="h-10 rounded-lg" data-testid="class-homeroom-teacher"><SelectValue placeholder={t('selectTeacher')} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">{t('noTeacher')}</SelectItem>
                      {options.teachers?.map((tc) => (<SelectItem key={tc.teacher_id} value={tc.teacher_id}>{tc.full_name_ar || tc.full_name_en}</SelectItem>))}
                    </SelectContent>
                  </Select>
                </FormField>
                {options.teachers?.length === 0 && (
                  <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/50 dark:bg-amber-950/20 text-center">
                    <p className="text-sm text-amber-700 font-cairo">{t('noTeachersAvailableYouCanAddThemLater')}</p>
                  </div>
                )}
              </div>
            )}

            {currentStep === 3 && (
              <div className="space-y-5">
                <SectionHeader icon={Users} title={t('students')} subtitle={t('selectStudentsForClassOptional')} color="blue" />

                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-xs">{isRTL ? `${(data.student_ids || []).length} طالب محدد` : `${(data.student_ids || []).length} selected`}</Badge>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="h-7 text-xs rounded-lg" onClick={() => onChange('student_ids', filteredStudents.map(s => s.student_id))}>{t('selectAll')}</Button>
                    <Button variant="outline" size="sm" className="h-7 text-xs rounded-lg" onClick={() => onChange('student_ids', [])}>{t('clear2')}</Button>
                  </div>
                </div>

                <div className="relative">
                  <Search className={`absolute ${isRTL ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground`} />
                  <Input value={studentSearch} onChange={(e) => setStudentSearch(e.target.value)} placeholder={t('searchStudent')} className={`h-10 rounded-lg ${isRTL ? 'pr-10' : 'pl-10'}`} />
                </div>

                <div className="max-h-52 overflow-y-auto border rounded-xl p-2">
                  {filteredStudents.length === 0 ? (
                    <p className="text-center text-muted-foreground py-6 text-sm">{t('noStudentsAvailable')}</p>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                      {filteredStudents.map((student) => (
                        <button
                          key={student.student_id}
                          type="button"
                          onClick={() => toggleStudent(student.student_id)}
                          className={`p-2.5 rounded-lg border-2 text-start transition-all ${
                            (data.student_ids || []).includes(student.student_id)
                              ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/30'
                              : 'border-transparent bg-muted/30 hover:bg-muted/50'
                          }`}
                        >
                          <p className="font-medium text-sm">{student.full_name_ar || student.full_name_en}</p>
                          <p className="text-[10px] text-muted-foreground" dir="ltr">{student.student_id}</p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {currentStep === 4 && (
              <div className="space-y-4">
                <SectionHeader icon={FileText} title={t('reviewInformation')} subtitle={t('verifyAllInformationBeforeCreating')} color="indigo" />

                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-purple-50 dark:bg-purple-950/20 border-b flex items-center gap-2">
                    <School className="h-4 w-4 text-purple-600" />
                    <span className="font-semibold text-sm text-purple-800 dark:text-purple-300">{isRTL ? 'بيانات الفصل' : 'Class Info'}</span>
                  </div>
                  <div className="p-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    <div><span className="text-muted-foreground text-xs">{t('name')}</span><p className="font-medium">{data.name_ar}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('grade')}</span><p className="font-medium">{getGradeName(data.grade_id)}</p></div>
                    <div><span className="text-muted-foreground text-xs">{t('capacity2')}</span><p className="font-medium">{data.capacity || 30}</p></div>
                    {data.room_number && <div><span className="text-muted-foreground text-xs">{t('room')}</span><p className="font-medium">{data.room_number}</p></div>}
                  </div>
                </div>

                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-green-50 dark:bg-green-950/20 border-b flex items-center gap-2">
                    <User className="h-4 w-4 text-green-600" />
                    <span className="font-semibold text-sm text-green-800 dark:text-green-300">{t('teacher2')}</span>
                  </div>
                  <div className="p-4 text-sm">
                    {data.homeroom_teacher_id ? (
                      <p className="font-medium">{getTeacherName(data.homeroom_teacher_id)}</p>
                    ) : (
                      <p className="text-muted-foreground">{t('noTeacherAssigned')}</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border overflow-hidden">
                  <div className="px-4 py-2.5 bg-blue-50 dark:bg-blue-950/20 border-b flex items-center gap-2">
                    <Users className="h-4 w-4 text-blue-600" />
                    <span className="font-semibold text-sm text-blue-800 dark:text-blue-300">{t('students')}</span>
                  </div>
                  <div className="p-4">
                    <Badge variant="secondary" className="text-xs">{isRTL ? `${(data.student_ids || []).length} طالب` : `${(data.student_ids || []).length} students`}</Badge>
                  </div>
                </div>
              </div>
            )}

            {currentStep === 5 && result && (
              <div className="space-y-5 py-2">
                <div className="text-center">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-400 to-purple-600 mx-auto flex items-center justify-center mb-4 shadow-lg shadow-purple-500/20">
                    <CheckCircle2 className="h-8 w-8 text-white" />
                  </div>
                  <h2 className="text-xl font-bold text-purple-600 font-cairo mb-1">{t('classCreated2')}</h2>
                  {canViewInternalIds && (
                    <p className="text-lg font-mono text-purple-700 mt-2">{result.class_id}</p>
                  )}
                </div>
                <div className="flex justify-center gap-3 pt-2">
                  <Button variant="outline" className="rounded-lg" onClick={() => handleCloseDialog(false)}>{t('close')}</Button>
                  <Button className="rounded-lg bg-purple-600 hover:bg-purple-700" onClick={handleReset}>{t('createAnother')}</Button>
                </div>
              </div>
            )}
          </div>
        )}

        {!loading && currentStep < 5 && (
          <div className="flex items-center justify-between px-6 py-3 border-t bg-muted/20 flex-shrink-0">
            <div>
              {currentStep > 1 && (
                <Button variant="ghost" size="sm" onClick={handleBack} className="gap-1.5 rounded-lg h-9">
                  {isRTL ? <ArrowRight className="h-3.5 w-3.5" /> : <ArrowLeft className="h-3.5 w-3.5" />}
                  {t('back')}
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="rounded-lg h-9" onClick={() => handleCloseDialog(false)}>{t('cancel')}</Button>
              {currentStep < 4 ? (
                <Button size="sm" onClick={handleNext} className="bg-purple-600 hover:bg-purple-700 gap-1.5 rounded-lg h-9 px-5">
                  {t('next')}
                  {isRTL ? <ArrowLeft className="h-3.5 w-3.5" /> : <ArrowRight className="h-3.5 w-3.5" />}
                </Button>
              ) : (
                <Button size="sm" onClick={handleSubmit} disabled={submitting} className="bg-emerald-600 hover:bg-emerald-700 gap-1.5 rounded-lg h-9 px-5">
                  {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  {t('create')}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default CreateClassWizard;
