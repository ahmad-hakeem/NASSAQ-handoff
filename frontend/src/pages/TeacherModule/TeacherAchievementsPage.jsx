import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  BookOpen, ClipboardCheck, FileText, Award, Users, TrendingUp,
  Loader2, RefreshCw, Plus, Trash2, Edit3, ChevronDown, ChevronUp,
  FolderOpen, BarChart3, GraduationCap, MessageSquare, Briefcase,
  Activity, Settings, CheckCircle2, AlertCircle, Calendar,
  FileArchive, Eye, Search, X, Zap, Target, Sparkles, Save,
  User as UserIcon, Mail, Phone, BookMarked, Heart, Compass,
  ScrollText, Shield, Building2, ListChecks, Video, ImageIcon,
  ClipboardList, FileCheck, PenSquare, Megaphone, HandHeart,
  PlayCircle, Wand2
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const SECTION_CONFIG = [
  { key: 'teaching_plans', icon: BookOpen, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30', types: ['lesson_plan', 'weekly_plan', 'unit_plan'] },
  { key: 'applied_lessons', icon: FileText, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', types: ['applied_lesson_report', 'collaborative_lesson'] },
  { key: 'assessment_grading', icon: GraduationCap, color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-900/30', types: ['exam_results', 'quiz_results', 'performance_task', 'exam_results_analysis', 'grade_analysis_tables'] },
  { key: 'attendance', icon: ClipboardCheck, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-50 dark:bg-green-900/30', types: ['attendance_record', 'late_tracking'] },
  { key: 'behaviour_guidance', icon: Award, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30', types: ['behaviour_tracking', 'struggling_student_plan', 'observation_notes'] },
  { key: 'parent_communication', icon: MessageSquare, color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-900/30', types: ['parent_communication_log', 'parent_meeting_minutes'] },
  { key: 'professional_development', icon: Briefcase, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-900/30', types: ['training_certificate', 'workshop_attendance', 'peer_observation'] },
  { key: 'participation_activities', icon: Activity, color: 'text-cyan-600 dark:text-cyan-400', bg: 'bg-cyan-50 dark:bg-cyan-900/30', types: ['participation_tracking', 'extracurricular_activity'] },
  { key: 'administrative', icon: Settings, color: 'text-slate-600 dark:text-slate-400', bg: 'bg-slate-50 dark:bg-slate-900/30', types: ['annual_goals', 'self_evaluation', 'professional_growth_plan'] },
];

const SECTION_TITLE_KEYS = {
  teaching_plans: 'portfolioTeachingPlans',
  applied_lessons: 'portfolioAppliedLessons',
  assessment_grading: 'portfolioAssessmentGrading',
  attendance: 'portfolioAttendance',
  behaviour_guidance: 'portfolioBehaviourGuidance',
  parent_communication: 'portfolioParentCommunication',
  professional_development: 'portfolioProfessionalDevelopment',
  participation_activities: 'portfolioParticipationActivities',
  administrative: 'portfolioAdministrative',
};

const TYPE_LABEL_KEYS = {
  lesson_plan: 'portfolioLessonPlan',
  weekly_plan: 'portfolioWeeklyPlan',
  unit_plan: 'portfolioUnitPlan',
  applied_lesson_report: 'portfolioAppliedLessonReport',
  collaborative_lesson: 'portfolioCollaborativeLesson',
  exam_results: 'portfolioExamResults',
  quiz_results: 'portfolioQuizResults',
  performance_task: 'portfolioPerformanceTask',
  exam_results_analysis: 'portfolioExamResultsAnalysis',
  grade_analysis_tables: 'portfolioGradeAnalysisTables',
  attendance_record: 'portfolioAttendanceRecord',
  late_tracking: 'portfolioLateTracking',
  behaviour_tracking: 'portfolioBehaviourTracking',
  struggling_student_plan: 'portfolioStrugglingStudentPlan',
  observation_notes: 'portfolioObservationNotes',
  parent_communication_log: 'portfolioParentCommunicationLog',
  parent_meeting_minutes: 'portfolioParentMeetingMinutes',
  training_certificate: 'portfolioTrainingCertificate',
  workshop_attendance: 'portfolioWorkshopAttendance',
  peer_observation: 'portfolioPeerObservation',
  participation_tracking: 'portfolioParticipationTracking',
  extracurricular_activity: 'portfolioExtracurricularActivity',
  annual_goals: 'portfolioAnnualGoals',
  self_evaluation: 'portfolioSelfEvaluation',
  professional_growth_plan: 'portfolioProfessionalGrowthPlan',
};

const ALL_EVIDENCE_TYPES = Object.keys(TYPE_LABEL_KEYS);

// =====================================================================
// Portfolio v2 — static national content (Arabic only) + sub-section config
// =====================================================================

const POLICY_GOALS_AR = [
  'ترسيخ العقيدة الإسلامية وبناء الشخصية الإسلامية',
  'تنمية المهارات الأساسية للمتعلم',
  'إعداد المواطن الصالح المنتمي لوطنه',
  'تنمية التفكير النقدي والإبداعي',
  'تعزيز القيم الوطنية والهوية السعودية',
  'تحقيق التميز في التعليم وفق رؤية 2030',
  'تنمية مهارات القرن الحادي والعشرين',
  'تعزيز التعلم مدى الحياة',
];

const ETHICS_CHARTER_AR = [
  'الأمانة في أداء الرسالة التعليمية',
  'العدل والمساواة بين الطلاب',
  'الاحترام المتبادل مع جميع الأطراف',
  'المحافظة على أسرار المهنة',
  'الالتزام بالتطوير المهني المستمر',
  'التعاون مع الزملاء والمجتمع المدرسي',
  'القدوة الحسنة في القول والعمل',
  'التحلي بالصبر والحكمة',
];

// New (v2) evidence type labels — Arabic only since spec is Arabic-native
const TYPE_LABEL_AR_V2 = {
  // planning
  curriculum_distribution_plan: 'خطة توزيع المنهج',
  weekly_plan: 'الخطة الأسبوعية',
  lesson_plan: 'خطة الدرس',
  preparation_record: 'سجل التحضير',
  unit_plan: 'خطة وحدة دراسية',
  classroom_activity_plan: 'خطة النشاط الصفي',
  struggling_student_plan: 'خطة دعم المتعثرين',
  gifted_student_plan: 'خطة رعاية المتفوقين',
  learning_loss_plan: 'خطة معالجة الفاقد التعليمي',
  // execution
  classroom_activity_photos: 'صور أنشطة صفية',
  student_worksheets: 'أوراق عمل الطلاب',
  applied_lesson_report: 'تقرير درس تطبيقي',
  lesson_video_recording: 'تسجيل فيديو لدرس',
  collaborative_lesson: 'أنشطة تعاونية',
  teaching_strategies: 'استراتيجيات تدريس',
  // assessment
  exam_results: 'الاختبارات',
  quiz_results: 'الاختبارات القصيرة',
  assessment_worksheet: 'أوراق العمل التقويمية',
  performance_task: 'المهام الأدائية',
  student_portfolio_files: 'ملفات إنجاز الطلاب',
  student_project: 'مشاريع الطلاب',
  oral_assessment: 'التقويم الشفهي',
  classroom_observation: 'الملاحظة الصفية',
  // results
  exam_results_analysis: 'تحليل نتائج الاختبارات',
  class_results_analysis: 'تحليل نتائج الفصل',
  student_progress_report: 'تقارير تقدم الطلاب',
  grade_analysis_tables: 'جداول تحليل الدرجات',
  before_after_comparison: 'مقارنة النتائج قبل وبعد',
  results_improvement_plan: 'خطة تحسين النتائج',
  // community
  parent_communication_log: 'سجل التواصل مع أولياء الأمور',
  parent_meeting_minutes: 'تقرير اجتماع مع أولياء الأمور',
  school_activity_participation: 'مشاركة في نشاط مدرسي',
  school_event_participation: 'مشاركة في الفعاليات المدرسية',
  // professional development v2
  training_attendance_report: 'تقرير حضور دورة',
  professional_growth_plan: 'خطة تطوير مهني',
  plc_participation: 'مجتمعات التعلم المهنية',
  peer_observation: 'تبادل الزيارات',
  workshop_attendance: 'حضور ورش عمل',
  workshop_delivery: 'تقديم ورش',
  volunteer_activity_report: 'تقرير نشاط تطوعي',
};

const SUBSECTION_CONFIG_V2 = [
  {
    key: 'planning', title: 'شواهد التخطيط', icon: ClipboardList,
    color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30',
    types: ['curriculum_distribution_plan', 'weekly_plan', 'lesson_plan', 'preparation_record', 'unit_plan', 'classroom_activity_plan', 'struggling_student_plan', 'gifted_student_plan', 'learning_loss_plan'],
  },
  {
    key: 'execution', title: 'شواهد التنفيذ', icon: PlayCircle,
    color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30',
    types: ['classroom_activity_photos', 'student_worksheets', 'applied_lesson_report', 'lesson_video_recording', 'collaborative_lesson', 'teaching_strategies'],
  },
  {
    key: 'assessment', title: 'شواهد التقويم', icon: FileCheck,
    color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-900/30',
    types: ['exam_results', 'quiz_results', 'assessment_worksheet', 'performance_task', 'student_portfolio_files', 'student_project', 'oral_assessment', 'classroom_observation'],
  },
  {
    key: 'results', title: 'شواهد النتائج', icon: BarChart3,
    color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30',
    types: ['exam_results_analysis', 'class_results_analysis', 'student_progress_report', 'grade_analysis_tables', 'before_after_comparison', 'results_improvement_plan'],
  },
  {
    key: 'community', title: 'شواهد التواصل والمجتمع', icon: Megaphone,
    color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-900/30',
    types: ['parent_communication_log', 'parent_meeting_minutes', 'school_activity_participation', 'school_event_participation'],
  },
  {
    key: 'professional_development_v2', title: 'شواهد التطوير المهني', icon: Briefcase,
    color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-900/30',
    types: ['training_attendance_report', 'professional_growth_plan', 'plc_participation', 'peer_observation', 'workshop_attendance', 'workshop_delivery', 'volunteer_activity_report'],
  },
];

const labelForType = (typeKey) =>
  TYPE_LABEL_AR_V2[typeKey] || typeKey.replace(/_/g, ' ');

export default function TeacherAchievementsPage() {
  const { t } = useTranslation();
  const { api, isRTL, user } = useAuth();
  const teacherId = user?.id;
  const { showAlert } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [portfolio, setPortfolio] = useState(null);
  const [progress, setProgress] = useState(null);
  const [activeTab, setActiveTab] = useState('portfolio');
  const [expandedSections, setExpandedSections] = useState({});
  const [evidenceDialog, setEvidenceDialog] = useState({ open: false, mode: 'add', data: null });
  const [evidenceForm, setEvidenceForm] = useState({ evidence_type: '', title_ar: '', title_en: '', description_ar: '', description_en: '', date: '' });
  const [saving, setSaving] = useState(false);
  const [hakimBusy, setHakimBusy] = useState({ title: null, description: null });
  const [fileFilter, setFileFilter] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState('all');

  // ----- Portfolio v2 state -----
  const [sectionsData, setSectionsData] = useState(null);
  const [introDraft, setIntroDraft] = useState('');
  const [vmvDraft, setVmvDraft] = useState({ vision: '', mission: '', values: '' });
  const [introBusy, setIntroBusy] = useState(false);
  const [vmvBusy, setVmvBusy] = useState(false);
  const [introAIBusy, setIntroAIBusy] = useState(false);
  const [vmvAIBusy, setVmvAIBusy] = useState(false);
  const [expandedV2, setExpandedV2] = useState({ intro: true });
  const [expandedSubsec, setExpandedSubsec] = useState({});
  const [cvDialog, setCvDialog] = useState({ open: false, kind: 'training_attended' });
  const [cvForm, setCvForm] = useState({ title: '', organization: '', date: '', hours: '', description: '' });
  const [cvSaving, setCvSaving] = useState(false);

  // Manual evidence dialog (V2 sub-sections)
  const [teacherClasses, setTeacherClasses] = useState([]);
  const [teacherSubjects, setTeacherSubjects] = useState([]);
  const [manualEvDialog, setManualEvDialog] = useState({ open: false });
  const [manualEvForm, setManualEvForm] = useState({
    section_key: '', evidence_type: '', title_ar: '', description_ar: '',
    class_id: '', subject_id: '', file_kind: 'pdf',
    file_url: '', file_name: '',
  });
  const [manualEvSaving, setManualEvSaving] = useState(false);
  const [manualEvUploading, setManualEvUploading] = useState(false);
  const [manualEvAIBusy, setManualEvAIBusy] = useState(false);
  const fileInputRef = useRef(null);

  const runManualEvHakim = async (mode) => {
    if (manualEvAIBusy) return;
    if (!manualEvForm.evidence_type) { toast.error('اختر التصنيف أولاً'); return; }
    if (mode === 'improve' && !(manualEvForm.description_ar || '').trim()) {
      toast.error('اكتب وصفاً أولاً ثم اضغط "تحسين بحكيم"');
      return;
    }
    setManualEvAIBusy(true);
    try {
      const res = await api.post('/teacher/portfolio/generate-evidence-desc', {
        mode,
        text: manualEvForm.description_ar || '',
        title: manualEvForm.title_ar || '',
        evidence_type: manualEvForm.evidence_type || '',
        section_key: manualEvForm.section_key || '',
      });
      if (res?.data?.success && res.data.text) {
        setManualEvForm(p => ({ ...p, description_ar: res.data.text }));
        toast.success(mode === 'improve' ? 'تم تحسين الوصف' : 'تم توليد الوصف');
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(detail === 'AI_DISABLED' ? 'الذكاء الاصطناعي غير متاح' : 'تعذّر توليد الوصف');
    } finally { setManualEvAIBusy(false); }
  };

  useEffect(() => {
    if (!teacherId) return;
    let cancelled = false;
    (async () => {
      const [classesRes, subjectsRes] = await Promise.allSettled([
        api.get(`/teacher/classes/${teacherId}`),
        api.get('/subjects'),
      ]);
      if (cancelled) return;
      if (classesRes.status === 'fulfilled') {
        const data = classesRes.value?.data;
        setTeacherClasses(Array.isArray(data) ? data : (data?.classes || []));
      }
      if (subjectsRes.status === 'fulfilled') {
        const data = subjectsRes.value?.data;
        setTeacherSubjects(Array.isArray(data) ? data : (data?.subjects || []));
      }
    })();
    return () => { cancelled = true; };
  }, [api, teacherId]);

  const openManualEvDialog = (sectionKey) => {
    const sub = SUBSECTION_CONFIG_V2.find(s => s.key === sectionKey);
    const defaultType = sub?.types?.[0] || '';
    setManualEvForm({
      section_key: sectionKey || (SUBSECTION_CONFIG_V2[0]?.key || ''),
      evidence_type: defaultType,
      title_ar: '', description_ar: '',
      class_id: '', subject_id: '', file_kind: 'pdf',
      file_url: '', file_name: '',
    });
    setManualEvDialog({ open: true });
  };

  const manualEvUploadTokenRef = useRef(0);
  const handleManualEvFile = async (file) => {
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    const MAX = 10 * 1024 * 1024;
    if (file.size > MAX) { toast.error('حجم الملف يتجاوز 10 ميغابايت'); return; }
    const token = ++manualEvUploadTokenRef.current;
    setManualEvUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/teacher/portfolio/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (token !== manualEvUploadTokenRef.current) return;
      if (res?.data?.success) {
        setManualEvForm(p => ({ ...p, file_url: res.data.file_url, file_name: res.data.file_name }));
        toast.success('تم رفع الملف');
      }
    } catch (err) {
      if (token !== manualEvUploadTokenRef.current) return;
      toast.error(err?.response?.data?.detail || 'فشل رفع الملف');
    } finally {
      if (token === manualEvUploadTokenRef.current) setManualEvUploading(false);
    }
  };

  const handleSaveManualEvidence = async () => {
    if (!manualEvForm.evidence_type || !(manualEvForm.title_ar || '').trim()) {
      toast.error('عنوان الشاهد ونوعه مطلوبان');
      return;
    }
    setManualEvSaving(true);
    try {
      await api.post('/teacher/portfolio/evidence', {
        evidence_type: manualEvForm.evidence_type,
        title_ar: manualEvForm.title_ar.trim(),
        description_ar: (manualEvForm.description_ar || '').trim() || null,
        date: new Date().toISOString().split('T')[0],
        class_id: manualEvForm.class_id || null,
        subject_id: manualEvForm.subject_id || null,
        file_url: manualEvForm.file_url || null,
        file_name: manualEvForm.file_name || null,
        metadata: { file_kind: manualEvForm.file_kind, source: 'manual_v2' },
      });
      toast.success('تمت إضافة الشاهد');
      setManualEvDialog({ open: false });
      // Make sure the relevant sub-section stays open
      setExpandedSubsec(p => ({ ...p, [manualEvForm.section_key]: true }));
      fetchPortfolio();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'فشل إضافة الشاهد');
    } finally { setManualEvSaving(false); }
  };

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      const [portfolioRes, progressRes, sectionsRes] = await Promise.allSettled([
        api.get('/teacher/portfolio'),
        api.get('/teacher/portfolio/progress'),
        api.get('/teacher/portfolio/sections'),
      ]);
      if (portfolioRes.status === 'fulfilled') setPortfolio(portfolioRes.value.data);
      else console.error('portfolio fetch failed:', portfolioRes.reason);
      if (progressRes.status === 'fulfilled') setProgress(progressRes.value.data);
      else console.error('progress fetch failed:', progressRes.reason);
      if (sectionsRes.status === 'fulfilled') {
        const sd = sectionsRes.value.data;
        setSectionsData(sd);
        // Hydrate drafts so save buttons start with current values
        setIntroDraft(sd?.intro?.text || '');
        setVmvDraft({
          vision: sd?.vmv?.vision || '',
          mission: sd?.vmv?.mission || '',
          values: sd?.vmv?.values || '',
        });
      } else {
        console.error('sections fetch failed:', sectionsRes.reason);
      }
    } catch (err) {
      console.error('Portfolio fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [api]);

  // ----- Portfolio v2 handlers -----
  const toggleV2 = (key) => setExpandedV2(p => ({ ...p, [key]: !p[key] }));
  const toggleSubsec = (key) => setExpandedSubsec(p => ({ ...p, [key]: !p[key] }));

  const handleSaveIntro = async () => {
    setIntroBusy(true);
    try {
      await api.put('/teacher/portfolio/intro', { text: introDraft });
      toast.success('تم حفظ المقدمة');
      fetchPortfolio();
    } catch (e) { toast.error('فشل الحفظ'); }
    finally { setIntroBusy(false); }
  };

  const handleGenerateIntro = async (mode = 'generate') => {
    if (mode === 'improve' && !(introDraft || '').trim()) {
      toast.error('اكتب المقدمة أولاً ليقوم حكيم بتحسينها');
      return;
    }
    setIntroAIBusy(true);
    try {
      const res = await api.post('/teacher/portfolio/generate-intro', {
        mode,
        text: mode === 'improve' ? introDraft : '',
      });
      if (res?.data?.text) {
        setIntroDraft(res.data.text);
        toast.success(mode === 'improve' ? 'تم تحسين المقدمة بحكيم' : 'تم توليد المقدمة بحكيم');
      }
    } catch (e) {
      const code = e?.response?.data?.detail;
      const msg = code === 'AI_DISABLED' ? 'الذكاء الاصطناعي غير مفعّل'
        : code === 'TEXT_TOO_SHORT' ? 'النص قصير جداً للتحسين'
        : (mode === 'improve' ? 'فشل التحسين' : 'فشل التوليد');
      toast.error(msg);
    } finally { setIntroAIBusy(false); }
  };

  const handleSaveVMV = async () => {
    setVmvBusy(true);
    try {
      await api.put('/teacher/portfolio/vmv', vmvDraft);
      toast.success('تم حفظ الرؤية والرسالة والقيم');
      fetchPortfolio();
    } catch (e) { toast.error('فشل الحفظ'); }
    finally { setVmvBusy(false); }
  };

  const handleGenerateVMV = async (mode = 'generate') => {
    if (mode === 'improve') {
      const hasAny = (vmvDraft.vision || '').trim() || (vmvDraft.mission || '').trim() || (vmvDraft.values || '').trim();
      if (!hasAny) {
        toast.error('اكتب الرؤية أو الرسالة أو القيم أولاً ليقوم حكيم بتحسينها');
        return;
      }
    }
    setVmvAIBusy(true);
    try {
      const res = await api.post('/teacher/portfolio/generate-vmv', {
        mode,
        vision: mode === 'improve' ? vmvDraft.vision : '',
        mission: mode === 'improve' ? vmvDraft.mission : '',
        values: mode === 'improve' ? vmvDraft.values : '',
      });
      if (res?.data) {
        setVmvDraft({
          vision: res.data.vision || '',
          mission: res.data.mission || '',
          values: res.data.values || '',
        });
        toast.success(mode === 'improve' ? 'تم تحسين المحتوى بحكيم' : 'تم توليد المحتوى بحكيم');
      }
    } catch (e) {
      const code = e?.response?.data?.detail;
      const msg = code === 'AI_DISABLED' ? 'الذكاء الاصطناعي غير مفعّل'
        : code === 'TEXT_TOO_SHORT' ? 'النص قصير جداً للتحسين'
        : (mode === 'improve' ? 'فشل التحسين' : 'فشل التوليد');
      toast.error(msg);
    } finally { setVmvAIBusy(false); }
  };

  const openCVDialog = (kind) => {
    setCvForm({ title: '', organization: '', date: '', hours: '', description: '' });
    setCvDialog({ open: true, kind });
  };

  const handleAddCVItem = async () => {
    if (!cvForm.title || cvForm.title.trim().length < 2) return;
    setCvSaving(true);
    try {
      await api.post('/teacher/portfolio/cv-item', {
        kind: cvDialog.kind,
        title: cvForm.title.trim(),
        organization: cvForm.organization.trim() || null,
        date: cvForm.date || null,
        hours: cvForm.hours ? Number(cvForm.hours) : null,
        description: cvForm.description.trim() || null,
      });
      toast.success('تمت الإضافة');
      setCvDialog({ open: false, kind: 'training_attended' });
      fetchPortfolio();
    } catch (e) { toast.error('فشل الحفظ'); }
    finally { setCvSaving(false); }
  };

  const handleDeleteCVItem = (item) => {
    if (item.source === 'auto') {
      toast.message('هذا العنصر يأتي تلقائياً من شواهد التطوير المهني');
      return;
    }
    showAlert({
      title: 'حذف العنصر؟',
      variant: 'danger',
      confirmText: 'حذف',
      onConfirm: async () => {
        try {
          await api.delete(`/teacher/portfolio/cv-item/${item.id}`);
          toast.success('تم الحذف');
          fetchPortfolio();
        } catch { toast.error('فشل الحذف'); }
      },
    });
  };

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const openAddDialog = (sectionKey) => {
    const cfg = SECTION_CONFIG.find(s => s.key === sectionKey);
    const defaultType = cfg?.types?.[0] || '';
    setEvidenceForm({ evidence_type: defaultType, title_ar: '', title_en: '', description_ar: '', description_en: '', date: new Date().toISOString().split('T')[0] });
    setEvidenceDialog({ open: true, mode: 'add', data: null });
  };

  const openEditDialog = (evidence) => {
    setEvidenceForm({
      evidence_type: evidence.evidence_type || '',
      title_ar: evidence.title_ar || '',
      title_en: evidence.title_en || '',
      description_ar: evidence.description_ar || '',
      description_en: evidence.description_en || '',
      date: evidence.date || '',
    });
    setEvidenceDialog({ open: true, mode: 'edit', data: evidence });
  };

  const hakimAbortRef = useRef({});
  const cancelHakimRequests = useCallback(() => {
    Object.values(hakimAbortRef.current || {}).forEach(c => {
      try { c?.abort?.(); } catch {}
    });
    hakimAbortRef.current = {};
    setHakimBusy({ title: null, description: null });
  }, []);
  // Abort any in-flight Hakim calls when the evidence dialog closes / unmounts
  useEffect(() => {
    if (!evidenceDialog.open) cancelHakimRequests();
  }, [evidenceDialog.open, cancelHakimRequests]);
  useEffect(() => () => cancelHakimRequests(), [cancelHakimRequests]);
  const handleHakimText = async (field, mode) => {
    const formField = field === 'title' ? 'title_ar' : 'description_ar';
    const text = (evidenceForm[formField] || '').trim();
    if (mode === 'improve' && text.length < 5) {
      toast.error(t('hakimNeedFiveChars'));
      return;
    }
    // Cancel any prior in-flight request for this field
    try { hakimAbortRef.current[field]?.abort?.(); } catch {}
    const controller = new AbortController();
    hakimAbortRef.current[field] = controller;
    setHakimBusy(prev => ({ ...prev, [field]: mode }));
    try {
      const res = await api.post('/teacher/portfolio/hakim-evidence-text', {
        mode,
        field,
        text,
        evidence_type: evidenceForm.evidence_type,
        title: evidenceForm.title_ar,
      }, { signal: controller.signal });
      if (controller.signal.aborted) return;
      const next = (res?.data?.text || '').trim();
      if (res?.data?.success && next) {
        setEvidenceForm(prev => ({ ...prev, [formField]: next }));
        toast.success(mode === 'generate' ? t('hakimGeneratedSuccess') : t('hakimImprovedSuccess'));
      } else {
        const reason = res?.data?.reason;
        if (reason === 'AI_DISABLED') toast.error(t('hakimUnavailable'));
        else if (reason === 'WRONG_LANGUAGE') toast.error(t('hakimUnavailable'));
        else if (reason === 'UNCHANGED') toast.message(t('hakimImprovedSuccess'));
        else toast.error(t('hakimUnavailable'));
      }
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') return;
      console.error('Hakim evidence text error:', err);
      const detail = err?.response?.data?.detail;
      if (detail === 'TEXT_TOO_SHORT') toast.error(t('hakimNeedFiveChars'));
      else toast.error(t('hakimUnavailable'));
    } finally {
      if (hakimAbortRef.current[field] === controller) {
        hakimAbortRef.current[field] = null;
      }
      setHakimBusy(prev => ({ ...prev, [field]: null }));
    }
  };

  const handleSaveEvidence = async () => {
    if (!evidenceForm.evidence_type || !evidenceForm.title_ar) return;
    setSaving(true);
    try {
      if (evidenceDialog.mode === 'add') {
        await api.post('/teacher/portfolio/evidence', evidenceForm);
        toast.success(t('portfolioSaveSuccess'));
      } else {
        await api.put(`/teacher/portfolio/evidence/${evidenceDialog.data.id}`, evidenceForm);
        toast.success(t('portfolioUpdateSuccess'));
      }
      setEvidenceDialog({ open: false, mode: 'add', data: null });
      fetchPortfolio();
    } catch (err) {
      console.error('Save evidence error:', err);
      toast.error(err?.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEvidence = (evidence) => {
    showAlert({
      title: t('portfolioDeleteConfirm'),
      variant: 'danger',
      confirmText: t('delete'),
      onConfirm: async () => {
        try {
          await api.delete(`/teacher/portfolio/evidence/${evidence.id}`);
          toast.success(t('portfolioDeleteSuccess'));
          fetchPortfolio();
        } catch (err) {
          console.error('Delete error:', err);
        }
      },
    });
  };

  const allEvidence = useMemo(() => {
    if (!portfolio?.sections) return [];
    const items = [];
    Object.values(portfolio.sections).forEach(sec => {
      if (sec.items) items.push(...sec.items);
    });
    return items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
  }, [portfolio]);

  const filteredFileEvidence = useMemo(() => {
    let items = allEvidence;
    if (fileTypeFilter && fileTypeFilter !== 'all') {
      items = items.filter(e => e.evidence_type === fileTypeFilter);
    }
    if (fileFilter) {
      const q = fileFilter.toLowerCase();
      items = items.filter(e =>
        (e.title_ar || '').toLowerCase().includes(q) ||
        (e.title_en || '').toLowerCase().includes(q) ||
        (e.description_ar || '').toLowerCase().includes(q)
      );
    }
    return items;
  }, [allEvidence, fileTypeFilter, fileFilter]);

  if (loading) {
    return (
      <Sidebar>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-brand-navy dark:text-brand-turquoise" />
        </div>
      </Sidebar>
    );
  }

  const coveragePercent = progress?.overall_percent || portfolio?.coverage_percent || 0;
  const totalEvidence = portfolio?.total_evidence || 0;
  const autoCount = portfolio?.auto_count || 0;
  const manualCount = portfolio?.manual_count || 0;

  return (
    <Sidebar>
      <div className={`p-4 md:p-6 space-y-6 max-w-6xl mx-auto ${isRTL ? 'text-right' : 'text-left'}`}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-brand-navy dark:text-white font-cairo">
              {t('portfolioTitle')}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 font-tajawal">
              {t('portfolioPatternAutoEvidence')}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchPortfolio} className="gap-2">
            <RefreshCw className="w-4 h-4" />
            {t('refresh')}
          </Button>
        </div>

        <Card className="border-0 shadow-sm bg-white dark:bg-gray-800">
          <CardContent className="p-4 md:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <div className={`w-14 h-14 rounded-xl bg-brand-navy/10 dark:bg-brand-turquoise/10 flex items-center justify-center shrink-0`}>
                <Target className="w-7 h-7 text-brand-navy dark:text-brand-turquoise" />
              </div>
              <div className="flex-1 min-w-0 w-full">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 font-cairo">
                    {t('portfolioOverallProgress')}
                  </span>
                  <span className="text-lg font-bold text-brand-navy dark:text-brand-turquoise">
                    {coveragePercent}%
                  </span>
                </div>
                <Progress value={coveragePercent} className="h-3 mb-3" />
                <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
                  <span className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    {totalEvidence} {t('portfolioEvidenceCount')}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    {autoCount} {t('portfolioAuto')}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Edit3 className="w-3.5 h-3.5 text-blue-500" />
                    {manualCount} {t('portfolioManual')}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5 text-green-500" />
                    {progress?.overall_covered || 0}/{progress?.overall_total || 0} {t('portfolioTypesCount')}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg w-fit">
          {['portfolio', 'files'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-md font-cairo ${
                activeTab === tab
                  ? 'bg-white dark:bg-gray-700 text-brand-navy dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {tab === 'portfolio' ? t('portfolioTab') : t('portfolioFileLibrary')}
            </button>
          ))}
        </div>

        {activeTab === 'portfolio' && (
          <PortfolioV2Sections
            sectionsData={sectionsData}
            isRTL={isRTL}
            openManualEvDialog={openManualEvDialog}
            expandedV2={expandedV2}
            toggleV2={toggleV2}
            expandedSubsec={expandedSubsec}
            toggleSubsec={toggleSubsec}
            introDraft={introDraft}
            setIntroDraft={setIntroDraft}
            introBusy={introBusy}
            introAIBusy={introAIBusy}
            handleSaveIntro={handleSaveIntro}
            handleGenerateIntro={handleGenerateIntro}
            vmvDraft={vmvDraft}
            setVmvDraft={setVmvDraft}
            vmvBusy={vmvBusy}
            vmvAIBusy={vmvAIBusy}
            handleSaveVMV={handleSaveVMV}
            handleGenerateVMV={handleGenerateVMV}
            openCVDialog={openCVDialog}
            handleDeleteCVItem={handleDeleteCVItem}
            openEditDialog={openEditDialog}
            handleDeleteEvidence={handleDeleteEvidence}
          />
        )}

        {activeTab === 'files' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className={`absolute top-2.5 ${isRTL ? 'right-3' : 'left-3'} w-4 h-4 text-gray-400`} />
                <Input
                  placeholder={t('search')}
                  value={fileFilter}
                  onChange={(e) => setFileFilter(e.target.value)}
                  className={`${isRTL ? 'pr-9' : 'pl-9'} h-9`}
                />
              </div>
              <Select value={fileTypeFilter} onValueChange={setFileTypeFilter}>
                <SelectTrigger className="w-full sm:w-48 h-9">
                  <SelectValue placeholder={t('portfolioEvidenceType')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('portfolioAllEvidence')}</SelectItem>
                  {ALL_EVIDENCE_TYPES.map(type => (
                    <SelectItem key={type} value={type}>{t(TYPE_LABEL_KEYS[type])}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {filteredFileEvidence.length === 0 ? (
              <Card className="border-0 shadow-sm bg-white dark:bg-gray-800">
                <CardContent className="py-12 text-center">
                  <FileArchive className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
                  <p className="text-gray-500 dark:text-gray-400 text-sm">{t('portfolioEmptyState')}</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {filteredFileEvidence.map(item => {
                  const sectionCfg = SECTION_CONFIG.find(s => s.types.includes(item.evidence_type));
                  const SIcon = sectionCfg?.icon || FileText;
                  return (
                    <Card key={item.id} className="border-0 shadow-sm bg-white dark:bg-gray-800 hover:shadow-md">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <div className={`w-9 h-9 rounded-lg ${sectionCfg?.bg || 'bg-gray-100 dark:bg-gray-700'} flex items-center justify-center shrink-0`}>
                            <SIcon className={`w-4 h-4 ${sectionCfg?.color || 'text-gray-500'}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate font-tajawal">
                              {isRTL ? item.title_ar : (item.title_en || item.title_ar)}
                            </p>
                            <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                              {t(TYPE_LABEL_KEYS[item.evidence_type] || item.evidence_type)}
                            </p>
                          </div>
                          <Badge variant="outline" className={`text-[10px] shrink-0 ${item.source === 'auto' ? 'border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-400' : 'border-blue-300 text-blue-600 dark:border-blue-700 dark:text-blue-400'}`}>
                            {item.source === 'auto' ? t('portfolioAuto') : t('portfolioManual')}
                          </Badge>
                        </div>
                        {(item.description_ar || item.description_en) && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 line-clamp-2">
                            {isRTL ? item.description_ar : (item.description_en || item.description_ar)}
                          </p>
                        )}
                        <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100 dark:border-gray-700">
                          <span className="text-[11px] text-gray-400 flex items-center gap-1">
                            <Calendar className="w-3 h-3" /> {item.date}
                          </span>
                          <div className="flex gap-1">
                            <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => openEditDialog(item)}>
                              <Edit3 className="w-3 h-3 text-gray-400" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => handleDeleteEvidence(item)}>
                              <Trash2 className="w-3 h-3 text-red-400" />
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <Dialog open={evidenceDialog.open} onOpenChange={(open) => { if (!open) setEvidenceDialog({ open: false, mode: 'add', data: null }); }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo">
              {evidenceDialog.mode === 'add' ? t('portfolioAddEvidence') : t('portfolioEditEvidence')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioEvidenceType')}</Label>
              <Select value={evidenceForm.evidence_type} onValueChange={(v) => setEvidenceForm(prev => ({ ...prev, evidence_type: v }))}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder={t('portfolioEvidenceType')} />
                </SelectTrigger>
                <SelectContent>
                  {ALL_EVIDENCE_TYPES.map(type => (
                    <SelectItem key={type} value={type}>{t(TYPE_LABEL_KEYS[type])}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5 gap-2 flex-wrap">
                <Label className="text-xs font-medium">{t('portfolioTitleAr')}</Label>
                <div className="flex items-center gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[11px] gap-1 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/30"
                    onClick={() => handleHakimText('title', 'generate')}
                    disabled={!!hakimBusy.title}
                  >
                    {hakimBusy.title === 'generate'
                      ? <Loader2 className="h-3 w-3 animate-spin" />
                      : <Zap className="h-3 w-3" />}
                    {t('hakimGenerate')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[11px] gap-1 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/30"
                    onClick={() => handleHakimText('title', 'improve')}
                    disabled={!!hakimBusy.title || (evidenceForm.title_ar || '').trim().length < 5}
                  >
                    {hakimBusy.title === 'improve'
                      ? <Loader2 className="h-3 w-3 animate-spin" />
                      : <Target className="h-3 w-3" />}
                    {t('hakimImprove')}
                  </Button>
                </div>
              </div>
              <Textarea
                value={evidenceForm.title_ar}
                onChange={(e) => setEvidenceForm(prev => ({ ...prev, title_ar: e.target.value }))}
                rows={2}
                placeholder={t('portfolioTitlePlaceholder')}
                dir={isRTL ? 'rtl' : 'ltr'}
                className="resize-none"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1.5 gap-2 flex-wrap">
                <Label className="text-xs font-medium">{t('portfolioDescriptionAr')}</Label>
                <div className="flex items-center gap-1.5">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[11px] gap-1 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/30"
                    onClick={() => handleHakimText('description', 'generate')}
                    disabled={!!hakimBusy.description}
                  >
                    {hakimBusy.description === 'generate'
                      ? <Loader2 className="h-3 w-3 animate-spin" />
                      : <Zap className="h-3 w-3" />}
                    {t('hakimGenerate')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="h-7 px-2 text-[11px] gap-1 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/30"
                    onClick={() => handleHakimText('description', 'improve')}
                    disabled={!!hakimBusy.description || (evidenceForm.description_ar || '').trim().length < 5}
                  >
                    {hakimBusy.description === 'improve'
                      ? <Loader2 className="h-3 w-3 animate-spin" />
                      : <Target className="h-3 w-3" />}
                    {t('hakimImprove')}
                  </Button>
                </div>
              </div>
              <Textarea
                value={evidenceForm.description_ar}
                onChange={(e) => setEvidenceForm(prev => ({ ...prev, description_ar: e.target.value }))}
                rows={4}
                placeholder={t('portfolioDescriptionPlaceholder')}
                dir={isRTL ? 'rtl' : 'ltr'}
                className="resize-none"
              />
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioEvidenceDate')}</Label>
              <Input type="date" value={evidenceForm.date} onChange={(e) => setEvidenceForm(prev => ({ ...prev, date: e.target.value }))} className="h-9" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEvidenceDialog({ open: false, mode: 'add', data: null })}>
              {t('cancel')}
            </Button>
            <Button onClick={handleSaveEvidence} disabled={saving || !evidenceForm.evidence_type || !evidenceForm.title_ar}>
              {saving && <Loader2 className={`w-4 h-4 animate-spin ${isRTL ? 'ml-2' : 'mr-2'}`} />}
              {t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual evidence dialog (V2) */}
      <Dialog open={manualEvDialog.open} onOpenChange={(open) => { if (!open) setManualEvDialog({ open: false }); }}>
        <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-cairo text-right">إضافة شاهد يدوي</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 mt-2" dir="rtl">
            <div>
              <Label className="text-xs font-medium mb-1 block">القسم</Label>
              <Select
                value={manualEvForm.section_key}
                onValueChange={(v) => {
                  const sub = SUBSECTION_CONFIG_V2.find(s => s.key === v);
                  setManualEvForm(p => ({ ...p, section_key: v, evidence_type: sub?.types?.[0] || '' }));
                }}
              >
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SUBSECTION_CONFIG_V2.map(s => (
                    <SelectItem key={s.key} value={s.key}>{s.title}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs font-medium mb-1 block">التصنيف الفرعي</Label>
              <Select
                value={manualEvForm.evidence_type}
                onValueChange={(v) => setManualEvForm(p => ({ ...p, evidence_type: v }))}
              >
                <SelectTrigger className="h-9"><SelectValue placeholder="اختر التصنيف" /></SelectTrigger>
                <SelectContent>
                  {(SUBSECTION_CONFIG_V2.find(s => s.key === manualEvForm.section_key)?.types || []).map(tk => (
                    <SelectItem key={tk} value={tk}>{labelForType(tk)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs font-medium mb-1 block">عنوان الشاهد</Label>
              <Input
                value={manualEvForm.title_ar}
                onChange={(e) => setManualEvForm(p => ({ ...p, title_ar: e.target.value }))}
                placeholder="مثال: ورقة عمل الوحدة الثالثة"
                className="h-9"
                dir="rtl"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs font-medium">الوصف</Label>
                <div className="flex items-center gap-1">
                  <Button
                    type="button" size="sm" variant="outline"
                    onClick={() => runManualEvHakim('generate')}
                    disabled={manualEvAIBusy || !manualEvForm.evidence_type}
                    className="h-7 px-2 text-[11px] gap-1 border-violet-300 text-violet-700 hover:bg-violet-50 dark:border-violet-700 dark:text-violet-300"
                    title="توليد وصف بحكيم"
                  >
                    {manualEvAIBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    إنشاء بحكيم
                  </Button>
                  <Button
                    type="button" size="sm" variant="outline"
                    onClick={() => runManualEvHakim('improve')}
                    disabled={manualEvAIBusy || !(manualEvForm.description_ar || '').trim()}
                    className="h-7 px-2 text-[11px] gap-1 border-fuchsia-300 text-fuchsia-700 hover:bg-fuchsia-50 dark:border-fuchsia-700 dark:text-fuchsia-300"
                    title="تحسين الوصف بحكيم"
                  >
                    {manualEvAIBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                    تحسين بحكيم
                  </Button>
                </div>
              </div>
              <Textarea
                value={manualEvForm.description_ar}
                onChange={(e) => setManualEvForm(p => ({ ...p, description_ar: e.target.value }))}
                placeholder="وصف مختصر للشاهد"
                rows={3}
                className="resize-none"
                dir="rtl"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs font-medium mb-1 block">المادة</Label>
                <Select
                  value={manualEvForm.subject_id}
                  onValueChange={(v) => setManualEvForm(p => ({ ...p, subject_id: v }))}
                >
                  <SelectTrigger className="h-9"><SelectValue placeholder="اختر المادة" /></SelectTrigger>
                  <SelectContent>
                    {teacherSubjects.map(s => (
                      <SelectItem key={s.id} value={s.id}>{s.name_ar || s.name || s.name_en || s.id}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-medium mb-1 block">الصف</Label>
                <Select
                  value={manualEvForm.class_id}
                  onValueChange={(v) => setManualEvForm(p => ({ ...p, class_id: v }))}
                >
                  <SelectTrigger className="h-9"><SelectValue placeholder="اختر الصف" /></SelectTrigger>
                  <SelectContent>
                    {teacherClasses.map(c => (
                      <SelectItem key={c.id} value={c.id}>{c.name_ar || c.name || c.id}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label className="text-xs font-medium mb-1 block">نوع الدليل</Label>
              <Select
                value={manualEvForm.file_kind}
                onValueChange={(v) => setManualEvForm(p => ({ ...p, file_kind: v, file_url: '', file_name: '' }))}
              >
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="pdf">ملف PDF</SelectItem>
                  <SelectItem value="image">صورة</SelectItem>
                  <SelectItem value="video">فيديو</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <input
                ref={fileInputRef}
                type="file"
                hidden
                accept={
                  manualEvForm.file_kind === 'pdf' ? 'application/pdf'
                    : manualEvForm.file_kind === 'image' ? 'image/*'
                    : 'video/*'
                }
                onChange={(e) => handleManualEvFile(e.target.files?.[0])}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={manualEvUploading}
                className="w-full py-6 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700 text-center hover:border-violet-400 dark:hover:border-violet-600 hover:bg-violet-50/40 dark:hover:bg-violet-900/10 transition-colors"
              >
                {manualEvUploading ? (
                  <div className="flex items-center justify-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <Loader2 className="w-4 h-4 animate-spin" /> جاري الرفع...
                  </div>
                ) : manualEvForm.file_url ? (
                  <div className="text-sm">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
                    <div className="text-emerald-700 dark:text-emerald-300 font-medium truncate px-2">{manualEvForm.file_name}</div>
                    <div className="text-[11px] text-gray-500 mt-1">انقر للاستبدال</div>
                  </div>
                ) : (
                  <div>
                    <FileArchive className="w-6 h-6 text-gray-400 mx-auto mb-1.5" />
                    <div className="text-sm text-gray-600 dark:text-gray-400">اضغط لرفع ملف أو اسحبه هنا</div>
                    <div className="text-[11px] text-gray-400 mt-0.5">PDF، صور، فيديو (حد أقصى 10 MB)</div>
                  </div>
                )}
              </button>
            </div>
          </div>

          <DialogFooter className="mt-3">
            <Button variant="outline" onClick={() => setManualEvDialog({ open: false })}>إلغاء</Button>
            <Button onClick={handleSaveManualEvidence} disabled={manualEvSaving || !manualEvForm.evidence_type || !(manualEvForm.title_ar || '').trim()} className="gap-1.5">
              {manualEvSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              إضافة الشاهد
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CV manual-add dialog */}
      <Dialog open={cvDialog.open} onOpenChange={(open) => { if (!open) setCvDialog({ open: false, kind: 'training_attended' }); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-cairo">
              {cvDialog.kind === 'training_attended' && 'إضافة دورة تدريبية مستفاد منها'}
              {cvDialog.kind === 'training_delivered' && 'إضافة دورة تدريبية منفذة'}
              {cvDialog.kind === 'award' && 'إضافة جائزة'}
              {cvDialog.kind === 'thank_letter' && 'إضافة خطاب شكر'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-xs font-medium mb-1.5 block">العنوان</Label>
              <Input value={cvForm.title} onChange={(e) => setCvForm(p => ({ ...p, title: e.target.value }))} placeholder="مثال: ورشة استراتيجيات التعليم النشط" dir={isRTL ? 'rtl' : 'ltr'} className="h-9" />
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">الجهة المانحة / المنظِّمة</Label>
              <Input value={cvForm.organization} onChange={(e) => setCvForm(p => ({ ...p, organization: e.target.value }))} placeholder="اختياري" dir={isRTL ? 'rtl' : 'ltr'} className="h-9" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-medium mb-1.5 block">التاريخ</Label>
                <Input type="date" value={cvForm.date} onChange={(e) => setCvForm(p => ({ ...p, date: e.target.value }))} className="h-9" />
              </div>
              {(cvDialog.kind === 'training_attended' || cvDialog.kind === 'training_delivered') && (
                <div>
                  <Label className="text-xs font-medium mb-1.5 block">عدد الساعات</Label>
                  <Input type="number" min="0" value={cvForm.hours} onChange={(e) => setCvForm(p => ({ ...p, hours: e.target.value }))} placeholder="اختياري" className="h-9" />
                </div>
              )}
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">وصف مختصر</Label>
              <Textarea value={cvForm.description} onChange={(e) => setCvForm(p => ({ ...p, description: e.target.value }))} rows={3} placeholder="اختياري" dir={isRTL ? 'rtl' : 'ltr'} className="resize-none" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCvDialog({ open: false, kind: 'training_attended' })}>إلغاء</Button>
            <Button onClick={handleAddCVItem} disabled={cvSaving || !cvForm.title || cvForm.title.trim().length < 2}>
              {cvSaving && <Loader2 className={`w-4 h-4 animate-spin ${isRTL ? 'ml-2' : 'mr-2'}`} />}
              حفظ
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Sidebar>
  );
}

// =====================================================================
// Portfolio v2 — UI sub-components
// =====================================================================

function AccordionCard({ icon: Icon, color, bg, title, subtitle, count, expanded, onToggle, children }) {
  return (
    <Card className="border-0 shadow-sm bg-white dark:bg-gray-800 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 md:px-5 md:py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750"
      >
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg ${bg} flex items-center justify-center`}>
            <Icon className={`w-5 h-5 ${color}`} />
          </div>
          <div className="text-right">
            <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100 font-cairo">{title}</h3>
            {subtitle && <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {count != null && count > 0 && (
            <Badge variant="secondary" className="text-xs">{count}</Badge>
          )}
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 md:px-5 md:pb-5 border-t border-gray-100 dark:border-gray-700 pt-3">
          {children}
        </div>
      )}
    </Card>
  );
}

function EvidenceRow({ item, isRTL, onEdit, onDelete }) {
  const handleView = () => {
    const url = item.file_url;
    if (!url) { toast.error('لا يوجد ملف مرفق لهذا الشاهد'); return; }
    try {
      const w = window.open();
      if (!w) { toast.error('يرجى السماح بالنوافذ المنبثقة'); return; }
      if (url.startsWith('data:')) {
        w.document.write(
          `<title>${(item.title_ar || item.title_en || 'preview').replace(/[<>]/g, '')}</title>` +
          (url.startsWith('data:image/')
            ? `<body style="margin:0;background:#111;display:flex;align-items:center;justify-content:center;height:100vh"><img src="${url}" style="max-width:100%;max-height:100%"/></body>`
            : url.startsWith('data:video/')
              ? `<body style="margin:0;background:#111;display:flex;align-items:center;justify-content:center;height:100vh"><video src="${url}" controls autoplay style="max-width:100%;max-height:100%"></video></body>`
              : `<body style="margin:0"><iframe src="${url}" style="border:0;width:100vw;height:100vh"></iframe></body>`)
        );
        w.document.close();
      } else {
        w.location.href = url;
      }
    } catch (e) {
      toast.error('فشل فتح الملف');
    }
  };

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-750 hover:bg-gray-100 dark:hover:bg-gray-700">
      <div className="w-9 h-9 rounded-full bg-white dark:bg-gray-800 flex items-center justify-center shrink-0 border border-gray-200 dark:border-gray-700">
        <FileText className="w-4 h-4 text-gray-500" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className="text-sm font-medium text-gray-800 dark:text-gray-100 font-tajawal">
            {isRTL ? (item.title_ar || item.title_en) : (item.title_en || item.title_ar)}
          </span>
          {item.source === 'auto' && (
            <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-400 gap-1">
              <Zap className="w-2.5 h-2.5" /> تقني
            </Badge>
          )}
        </div>
        {(item.description_ar || item.description_en) && (
          <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
            {isRTL ? (item.description_ar || item.description_en) : (item.description_en || item.description_ar)}
          </p>
        )}
        <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-400 dark:text-gray-500">
          {item.date && (
            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{item.date}</span>
          )}
          <span>{labelForType(item.evidence_type)}</span>
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {item.file_url && (
          <Button size="icon" variant="ghost" className="h-7 w-7" title="عرض الملف" onClick={handleView}>
            <Eye className="w-3.5 h-3.5 text-violet-500" />
          </Button>
        )}
        <Button size="icon" variant="ghost" className="h-7 w-7" title="تعديل" onClick={() => onEdit?.(item)}>
          <Edit className="w-3.5 h-3.5 text-gray-400" />
        </Button>
        <Button size="icon" variant="ghost" className="h-7 w-7" title="حذف" onClick={() => onDelete?.(item)}>
          <Trash2 className="w-3.5 h-3.5 text-red-400" />
        </Button>
      </div>
    </div>
  );
}

function CVItemRow({ item, isRTL, onDelete }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-750">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-sm font-medium text-gray-800 dark:text-gray-100 font-tajawal">{item.title}</span>
          {item.source === 'auto' && (
            <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-400 gap-1">
              <Zap className="w-2.5 h-2.5" /> تلقائي
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400 flex-wrap">
          {item.organization && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{item.organization}</span>}
          {item.date && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{item.date}</span>}
          {item.hours != null && <span>{item.hours} ساعة</span>}
        </div>
        {item.description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{item.description}</p>
        )}
      </div>
      {item.source !== 'auto' && (
        <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={() => onDelete?.(item)}>
          <Trash2 className="w-3.5 h-3.5 text-red-400" />
        </Button>
      )}
    </div>
  );
}

function PortfolioV2Sections(props) {
  const {
    sectionsData, isRTL, openManualEvDialog,
    expandedV2, toggleV2, expandedSubsec, toggleSubsec,
    introDraft, setIntroDraft, introBusy, introAIBusy, handleSaveIntro, handleGenerateIntro,
    vmvDraft, setVmvDraft, vmvBusy, vmvAIBusy, handleSaveVMV, handleGenerateVMV,
    openCVDialog, handleDeleteCVItem, openEditDialog, handleDeleteEvidence,
  } = props;

  const cv = sectionsData?.cv;
  const profile = cv?.profile || {};
  const subsecData = sectionsData?.evidence_subsections || {};

  return (
    <div className="space-y-3">

      {/* Section 1: Intro */}
      <AccordionCard
        icon={Sparkles} color="text-violet-600 dark:text-violet-400" bg="bg-violet-50 dark:bg-violet-900/30"
        title="المقدمة" subtitle="نبذة تعريفية عن المعلم — قابلة للتعديل"
        expanded={!!expandedV2.intro} onToggle={() => toggleV2('intro')}
      >
        <Textarea
          value={introDraft}
          onChange={(e) => setIntroDraft(e.target.value)}
          rows={5}
          placeholder="اكتب مقدمة تعريفية عن نفسك أو استخدم زر التوليد بحكيم..."
          dir="rtl"
          className="resize-none mb-3"
        />
        <div className="flex flex-wrap gap-2 justify-end">
          <Button size="sm" variant="outline" className="gap-1.5 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300" onClick={() => handleGenerateIntro('generate')} disabled={introAIBusy}>
            {introAIBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            توليد بحكيم
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5 border-fuchsia-200 dark:border-fuchsia-800 text-fuchsia-700 dark:text-fuchsia-300" onClick={() => handleGenerateIntro('improve')} disabled={introAIBusy || !(introDraft || '').trim()}>
            {introAIBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
            تحسين بحكيم
          </Button>
          <Button size="sm" className="gap-1.5" onClick={handleSaveIntro} disabled={introBusy}>
            {introBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            حفظ
          </Button>
        </div>
      </AccordionCard>

      {/* Section 2: Vision / Mission / Values */}
      <AccordionCard
        icon={Compass} color="text-cyan-600 dark:text-cyan-400" bg="bg-cyan-50 dark:bg-cyan-900/30"
        title="الرؤية والرسالة والقيم" subtitle="ثلاثة عناصر مولَّدة بحكيم وقابلة للتعديل"
        expanded={!!expandedV2.vmv} onToggle={() => toggleV2('vmv')}
      >
        <div className="space-y-3">
          <div>
            <Label className="text-xs font-medium mb-1.5 block flex items-center gap-1.5"><Eye className="w-3.5 h-3.5 text-cyan-600" /> الرؤية</Label>
            <Textarea value={vmvDraft.vision} onChange={(e) => setVmvDraft(p => ({ ...p, vision: e.target.value }))} rows={2} dir="rtl" className="resize-none" />
          </div>
          <div>
            <Label className="text-xs font-medium mb-1.5 block flex items-center gap-1.5"><Target className="w-3.5 h-3.5 text-cyan-600" /> الرسالة</Label>
            <Textarea value={vmvDraft.mission} onChange={(e) => setVmvDraft(p => ({ ...p, mission: e.target.value }))} rows={2} dir="rtl" className="resize-none" />
          </div>
          <div>
            <Label className="text-xs font-medium mb-1.5 block flex items-center gap-1.5"><Heart className="w-3.5 h-3.5 text-cyan-600" /> القيم</Label>
            <Textarea value={vmvDraft.values} onChange={(e) => setVmvDraft(p => ({ ...p, values: e.target.value }))} rows={2} dir="rtl" className="resize-none" />
          </div>
          <div className="flex flex-wrap gap-2 justify-end">
            <Button size="sm" variant="outline" className="gap-1.5 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300" onClick={() => handleGenerateVMV('generate')} disabled={vmvAIBusy}>
              {vmvAIBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              توليد بحكيم
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5 border-fuchsia-200 dark:border-fuchsia-800 text-fuchsia-700 dark:text-fuchsia-300" onClick={() => handleGenerateVMV('improve')} disabled={vmvAIBusy || !((vmvDraft.vision || '').trim() || (vmvDraft.mission || '').trim() || (vmvDraft.values || '').trim())}>
              {vmvAIBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
              تحسين بحكيم
            </Button>
            <Button size="sm" className="gap-1.5" onClick={handleSaveVMV} disabled={vmvBusy}>
              {vmvBusy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              حفظ
            </Button>
          </div>
        </div>
      </AccordionCard>

      {/* Section 3: Education Policy Goals (static) */}
      <AccordionCard
        icon={ScrollText} color="text-emerald-600 dark:text-emerald-400" bg="bg-emerald-50 dark:bg-emerald-900/30"
        title="أهداف سياسة التعليم" subtitle="ثمانية أهداف وطنية — محتوى ثابت"
        expanded={!!expandedV2.policy} onToggle={() => toggleV2('policy')}
      >
        <ol className="space-y-2">
          {POLICY_GOALS_AR.map((goal, idx) => (
            <li key={idx} className="flex items-start gap-3 p-2.5 rounded-lg bg-emerald-50/50 dark:bg-emerald-900/10">
              <span className="w-6 h-6 rounded-full bg-emerald-600 dark:bg-emerald-700 text-white text-xs flex items-center justify-center shrink-0 font-bold">{idx + 1}</span>
              <span className="text-sm text-gray-800 dark:text-gray-200 font-tajawal pt-0.5">{goal}</span>
            </li>
          ))}
        </ol>
      </AccordionCard>

      {/* Section 4: Code of Ethics (static) */}
      <AccordionCard
        icon={Shield} color="text-rose-600 dark:text-rose-400" bg="bg-rose-50 dark:bg-rose-900/30"
        title="ميثاق أخلاقيات مهنة التعليم" subtitle="ثمانية بنود — محتوى ثابت"
        expanded={!!expandedV2.ethics} onToggle={() => toggleV2('ethics')}
      >
        <ul className="space-y-2">
          {ETHICS_CHARTER_AR.map((item, idx) => (
            <li key={idx} className="flex items-start gap-3 p-2.5 rounded-lg bg-rose-50/50 dark:bg-rose-900/10">
              <CheckCircle2 className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-800 dark:text-gray-200 font-tajawal">{item}</span>
            </li>
          ))}
        </ul>
      </AccordionCard>

      {/* Section 5: CV */}
      <AccordionCard
        icon={UserIcon} color="text-blue-600 dark:text-blue-400" bg="bg-blue-50 dark:bg-blue-900/30"
        title="السيرة الذاتية"
        subtitle="البيانات الشخصية والدورات والجوائز"
        expanded={!!expandedV2.cv} onToggle={() => toggleV2('cv')}
      >
        {/* Personal data grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
          {[
            { icon: UserIcon, label: 'الاسم', value: profile.full_name },
            { icon: BookMarked, label: 'التخصص', value: profile.specialization || profile.subject },
            { icon: GraduationCap, label: 'المؤهل', value: profile.qualification },
            { icon: Phone, label: 'رقم الجوال', value: profile.phone },
            { icon: Mail, label: 'البريد الإلكتروني', value: profile.email },
            { icon: Briefcase, label: 'سنوات الخبرة', value: profile.years_of_experience ? `${profile.years_of_experience} سنة` : null },
          ].map((f, i) => (
            <div key={i} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-750">
              <div className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 mb-1">
                <f.icon className="w-3 h-3" />
                {f.label}
              </div>
              <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{f.value || '—'}</div>
            </div>
          ))}
        </div>

        {/* Training attended */}
        <CVCategorySection
          title="الدورات التدريبية المستفاد منها"
          icon={GraduationCap} color="text-blue-600 dark:text-blue-400"
          items={cv?.training_attended || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('training_attended')}
          onDelete={handleDeleteCVItem}
        />
        {/* Training delivered */}
        <CVCategorySection
          title="الدورات التدريبية المنفذة"
          icon={PenSquare} color="text-emerald-600 dark:text-emerald-400"
          items={cv?.training_delivered || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('training_delivered')}
          onDelete={handleDeleteCVItem}
        />
        {/* Awards */}
        <CVCategorySection
          title="الجوائز"
          icon={Award} color="text-amber-600 dark:text-amber-400"
          items={cv?.award || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('award')}
          onDelete={handleDeleteCVItem}
        />
        {/* Thank letters */}
        <CVCategorySection
          title="خطابات الشكر"
          icon={HandHeart} color="text-pink-600 dark:text-pink-400"
          items={cv?.thank_letter || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('thank_letter')}
          onDelete={handleDeleteCVItem}
        />
      </AccordionCard>

      {/* Section 6: Performance Evidence — 6 sub-accordions */}
      <AccordionCard
        icon={ListChecks} color="text-indigo-600 dark:text-indigo-400" bg="bg-indigo-50 dark:bg-indigo-900/30"
        title="شواهد الأداء الوظيفي"
        subtitle="ستة أقسام فرعية لشواهد العمل التربوي"
        expanded={!!expandedV2.evidence} onToggle={() => toggleV2('evidence')}
      >
        <div className="space-y-2">
          {SUBSECTION_CONFIG_V2.map(sub => {
            const sd = subsecData[sub.key] || { count: 0, items: [] };
            const isOpen = !!expandedSubsec[sub.key];
            const SubIcon = sub.icon;
            return (
              <div key={sub.key} className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <button
                  onClick={() => toggleSubsec(sub.key)}
                  className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <div className="flex items-center gap-2.5">
                    <div className={`w-8 h-8 rounded-lg ${sub.bg} flex items-center justify-center`}>
                      <SubIcon className={`w-4 h-4 ${sub.color}`} />
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-gray-800 dark:text-gray-100 font-cairo">{sub.title}</div>
                      <div className="text-[11px] text-gray-500 dark:text-gray-400">{sd.count} شاهد</div>
                    </div>
                  </div>
                  {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </button>
                {isOpen && (
                  <div className="px-3 pb-3 border-t border-gray-100 dark:border-gray-700 pt-2">
                    {/* Type chips */}
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {sub.types.map(typeKey => {
                        const has = sd.items?.some(it => it.evidence_type === typeKey);
                        return (
                          <Badge
                            key={typeKey}
                            variant="outline"
                            className={`text-[10px] ${has ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800' : 'text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-700'}`}
                          >
                            {has ? <CheckCircle2 className="w-3 h-3 ml-1" /> : <AlertCircle className="w-3 h-3 ml-1" />}
                            {labelForType(typeKey)}
                          </Badge>
                        );
                      })}
                    </div>
                    {/* Evidence rows */}
                    {(!sd.items || sd.items.length === 0) ? (
                      <div className="text-center py-6 text-gray-400 dark:text-gray-500">
                        <FolderOpen className="w-8 h-8 mx-auto mb-1.5 opacity-50" />
                        <p className="text-xs">لا توجد شواهد بعد</p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {sd.items.map(item => (
                          <EvidenceRow
                            key={item.id}
                            item={item}
                            isRTL={isRTL}
                            onEdit={openEditDialog}
                            onDelete={handleDeleteEvidence}
                          />
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => openManualEvDialog && openManualEvDialog(sub.key)}
                      className="mt-3 w-full py-2.5 rounded-lg border border-dashed border-violet-300 dark:border-violet-700 text-sm font-medium text-violet-700 dark:text-violet-300 hover:bg-violet-50 dark:hover:bg-violet-900/20 flex items-center justify-center gap-2 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                      إضافة شاهد يدوي
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </AccordionCard>

    </div>
  );
}

function CVCategorySection({ title, icon: Icon, color, items, isRTL, onAdd, onDelete }) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className={`w-4 h-4 ${color}`} />
          <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-100 font-cairo">{title}</h4>
          <Badge variant="secondary" className="text-[10px]">{items.length}</Badge>
        </div>
        <Button size="sm" variant="outline" className="gap-1 text-xs h-7" onClick={onAdd}>
          <Plus className="w-3 h-3" /> إضافة
        </Button>
      </div>
      {items.length === 0 ? (
        <div className="text-center py-4 text-gray-400 dark:text-gray-500 text-xs bg-gray-50 dark:bg-gray-750 rounded-lg">
          لا يوجد محتوى
        </div>
      ) : (
        <div className="space-y-1.5">
          {items.map(it => (
            <CVItemRow key={it.id} item={it} isRTL={isRTL} onDelete={onDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
