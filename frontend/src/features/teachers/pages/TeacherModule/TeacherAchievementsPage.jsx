import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useCanViewInternalIds } from '@/shared/hooks/useCanViewInternalIds';
import { maskInternalId } from '@/shared/models/utils/internalId';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { Input } from '@/shared/components/ui/input';
import { Textarea } from '@/shared/components/ui/textarea';
import { Label } from '@/shared/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/shared/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import {
  BookOpen, ClipboardCheck, FileText, Award, Users, TrendingUp,
  Loader2, RefreshCw, Plus, Trash2, Edit3, ChevronDown, ChevronUp,
  FolderOpen, BarChart3, GraduationCap, MessageSquare, Briefcase,
  Activity, Settings, CheckCircle2, AlertCircle, Calendar,
  FileArchive, Eye, Search, X, Zap, Target, Sparkles, Save, Download,
  User as UserIcon, Mail, Phone, BookMarked, Heart, Compass,
  ScrollText, Shield, Building2, ListChecks, Video, ImageIcon,
  ClipboardList, FileCheck, PenSquare, Megaphone, HandHeart,
  PlayCircle, Wand2, Upload, ExternalLink
} from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';
import {
  EVIDENCE_TYPE_GROUPS,
  V2_SUBSECTIONS,
  labelForType,
} from './portfolioEvidenceTypes';

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

// Presentation only — the type vocabulary itself lives in
// ./portfolioEvidenceTypes so the filter, the dialogs and the cards can never
// drift apart (or away from the backend).
const SUBSECTION_ICONS = {
  planning: { icon: ClipboardList, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30' },
  execution: { icon: PlayCircle, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30' },
  assessment: { icon: FileCheck, color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-900/30' },
  results: { icon: BarChart3, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30' },
  community: { icon: Megaphone, color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-900/30' },
  professional_development: { icon: Briefcase, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-900/30' },
};

const SUBSECTION_CONFIG_V2 = V2_SUBSECTIONS.map(sub => ({ ...sub, ...SUBSECTION_ICONS[sub.key] }));

/** Every stored evidence type, grouped, for the library filter and the dialogs. */
function EvidenceTypeOptions({ t }) {
  return EVIDENCE_TYPE_GROUPS.map(group => (
    <SelectGroup key={group.key}>
      <SelectLabel className="text-[11px] text-gray-400">{group.title}</SelectLabel>
      {group.types.map(type => (
        <SelectItem key={type} value={type}>{labelForType(type, t)}</SelectItem>
      ))}
    </SelectGroup>
  ));
}

const FILE_KIND_OPTIONS = [
  { value: 'pdf',   label: 'ملف PDF' },
  { value: 'image', label: 'صورة' },
  { value: 'video', label: 'فيديو' },
  { value: 'docx',  label: 'مستند Word (DOCX)' },
  { value: 'pptx',  label: 'عرض PowerPoint (PPTX)' },
  { value: 'xlsx',  label: 'جدول Excel (XLSX)' },
  { value: 'txt',   label: 'ملف نصي (TXT)' },
  { value: 'md',    label: 'ملف Markdown (MD)' },
  { value: 'link',  label: 'رابط (Google Drive / Dropbox / غيره)' },
];

const FILE_KIND_ACCEPT = {
  pdf: 'application/pdf,.pdf',
  image: 'image/*',
  video: 'video/*',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,.docx,.doc',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.ms-powerpoint,.pptx,.ppt',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,.xlsx,.xls',
  txt: 'text/plain,.txt',
  md: 'text/markdown,text/x-markdown,.md,.markdown',
};

const acceptForKind = (k) => FILE_KIND_ACCEPT[k] || '*/*';

export default function TeacherAchievementsPage() {
  const { t } = useTranslation();
  const { api, isRTL, user } = useAuth();
  const teacherId = user?.id;
  const isIndependentTeacher = user?.role === 'independent_teacher';
  const { showAlert, nassaqError } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [portfolio, setPortfolio] = useState(null);
  const [progress, setProgress] = useState(null);
  const [activeTab, setActiveTab] = useState('portfolio');
  const [expandedSections, setExpandedSections] = useState({});
  const [evidenceDialog, setEvidenceDialog] = useState({ open: false, mode: 'add', data: null });
  const [evidenceForm, setEvidenceForm] = useState({ evidence_type: '', title_ar: '', title_en: '', description_ar: '', description_en: '', date: '', class_id: '', subject_id: '', file_url: '', file_id: '', file_name: '', file_kind: 'pdf' });
  const [editFileUploading, setEditFileUploading] = useState(false);
  const editFileInputRef = useRef(null);
  const editUploadTokenRef = useRef(0);

  // --- File preview state (evidence dialog) ---
  const [editPreviewSrc, setEditPreviewSrc] = useState(null);
  const [editPreviewMime, setEditPreviewMime] = useState(null);
  const editPreviewUrlRef = useRef(null);

  // --- File preview state (manual evidence dialog) ---
  const [manualEvPreviewSrc, setManualEvPreviewSrc] = useState(null);
  const [manualEvPreviewMime, setManualEvPreviewMime] = useState(null);
  const manualEvPreviewUrlRef = useRef(null);

  // --- File preview state (CV dialog) ---
  const [cvPreviewSrc, setCvPreviewSrc] = useState(null);
  const [cvPreviewMime, setCvPreviewMime] = useState(null);
  const cvPreviewUrlRef = useRef(null);

  const _clearEditPreview = () => {
    if (editPreviewUrlRef.current && editPreviewUrlRef.current !== 'office') {
      try { URL.revokeObjectURL(editPreviewUrlRef.current); } catch {}
    }
    editPreviewUrlRef.current = null;
    setEditPreviewSrc(null);
    setEditPreviewMime(null);
  };

  const _clearManualEvPreview = () => {
    if (manualEvPreviewUrlRef.current && manualEvPreviewUrlRef.current !== 'office') {
      try { URL.revokeObjectURL(manualEvPreviewUrlRef.current); } catch {}
    }
    manualEvPreviewUrlRef.current = null;
    setManualEvPreviewSrc(null);
    setManualEvPreviewMime(null);
  };

  const _setEditPreview = (file) => {
    _clearEditPreview();
    if (file.type.startsWith('image/') || file.type === 'application/pdf') {
      const url = URL.createObjectURL(file);
      editPreviewUrlRef.current = url;
      setEditPreviewSrc(url);
      setEditPreviewMime(file.type);
    } else {
      editPreviewUrlRef.current = 'office';
      setEditPreviewSrc('office');
      setEditPreviewMime(file.type);
    }
  };

  const _setManualEvPreview = (file) => {
    _clearManualEvPreview();
    if (file.type.startsWith('image/') || file.type === 'application/pdf') {
      const url = URL.createObjectURL(file);
      manualEvPreviewUrlRef.current = url;
      setManualEvPreviewSrc(url);
      setManualEvPreviewMime(file.type);
    } else {
      manualEvPreviewUrlRef.current = 'office';
      setManualEvPreviewSrc('office');
      setManualEvPreviewMime(file.type);
    }
  };

  const _clearCvPreview = () => {
    if (cvPreviewUrlRef.current && cvPreviewUrlRef.current !== 'office') {
      try { URL.revokeObjectURL(cvPreviewUrlRef.current); } catch {}
    }
    cvPreviewUrlRef.current = null;
    setCvPreviewSrc(null);
    setCvPreviewMime(null);
  };

  const _setCvPreview = (file) => {
    _clearCvPreview();
    if (file.type.startsWith('image/') || file.type === 'application/pdf') {
      const url = URL.createObjectURL(file);
      cvPreviewUrlRef.current = url;
      setCvPreviewSrc(url);
      setCvPreviewMime(file.type);
    } else {
      cvPreviewUrlRef.current = 'office';
      setCvPreviewSrc('office');
      setCvPreviewMime(file.type);
    }
  };

  const handleEditEvidenceFile = async (file) => {
    if (editFileInputRef.current) editFileInputRef.current.value = '';
    if (!file) return;
    const MAX = 10 * 1024 * 1024;
    if (file.size > MAX) { nassaqError('حجم الملف يتجاوز 10 ميغابايت'); return; }
    _setEditPreview(file);
    const token = ++editUploadTokenRef.current;
    setEditFileUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/teacher/portfolio/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (token !== editUploadTokenRef.current) return;
      if (res?.data?.success) {
        setEvidenceForm(prev => ({ ...prev, file_url: '', file_id: res.data.file_id, file_name: res.data.file_name }));
        toast.success('تم رفع الملف');
      }
    } catch (err) {
      if (token !== editUploadTokenRef.current) return;
      nassaqError(getApiErrorMessage(err) || 'فشل رفع الملف');
    } finally {
      if (token === editUploadTokenRef.current) setEditFileUploading(false);
    }
  };
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
  const [cvForm, setCvForm] = useState({ title: '', organization: '', date: '', hours: '', description: '', file_url: '', file_id: '', file_name: '' });
  const [cvFileUploading, setCvFileUploading] = useState(false);
  const cvFileInputRef = useRef(null);
  const cvUploadTokenRef = useRef(0);
  const [cvSaving, setCvSaving] = useState(false);

  // Manual evidence dialog (V2 sub-sections)
  const [teacherClasses, setTeacherClasses] = useState([]);
  const [teacherSubjects, setTeacherSubjects] = useState([]);
  const [manualEvDialog, setManualEvDialog] = useState({ open: false });
  const [viewEvDialog, setViewEvDialog] = useState({ open: false, item: null });
  const openViewDialog = (item) => setViewEvDialog({ open: true, item });
  const [extraClassNames, setExtraClassNames] = useState({});
  const [extraSubjectNames, setExtraSubjectNames] = useState({});

  useEffect(() => {
    const it = viewEvDialog.item;
    if (!it) return;
    const cid = it.class_id;
    if (cid && !teacherClasses.find(c => c.id === cid) && !(cid in extraClassNames)) {
      setExtraClassNames(prev => ({ ...prev, [cid]: '' }));
      api.get(`/classes/${cid}`)
        .then(r => {
          const d = r.data || {};
          const name = d.name_ar || d.name || d.name_en || '';
          setExtraClassNames(prev => ({ ...prev, [cid]: name }));
        })
        .catch(() => {});
    }
    const sid = it.subject_id;
    if (sid && !teacherSubjects.find(s => s.id === sid) && !(sid in extraSubjectNames)) {
      setExtraSubjectNames(prev => ({ ...prev, [sid]: '' }));
      api.get(`/subjects/${sid}`)
        .then(r => {
          const d = r.data || {};
          const name = d.name_ar || d.name || d.name_en || '';
          setExtraSubjectNames(prev => ({ ...prev, [sid]: name }));
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewEvDialog.item]);

  const openEvidenceFile = (url, targetWin = null) => {
    if (!url) { try { targetWin?.close(); } catch {} toast.error('لا يوجد ملف مرفق لهذا الشاهد'); return; }
    try {
      if (url.startsWith('data:')) {
        const m = url.match(/^data:([^;,]+)(;base64)?,(.*)$/);
        if (!m) { try { targetWin?.close(); } catch {} toast.error('صيغة الملف غير صالحة'); return; }
        const mime = m[1] || 'application/octet-stream';
        const isB64 = !!m[2];
        const payload = m[3] || '';
        let bytes;
        if (isB64) {
          const bin = atob(payload);
          bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        } else {
          bytes = new TextEncoder().encode(decodeURIComponent(payload));
        }
        const blob = new Blob([bytes], { type: mime });
        const blobUrl = URL.createObjectURL(blob);
        let w = targetWin;
        if (w) { w.location.href = blobUrl; }
        else { w = window.open(blobUrl, '_blank'); }
        if (!w) { toast.error('يرجى السماح بالنوافذ المنبثقة'); URL.revokeObjectURL(blobUrl); return; }
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
      } else if (targetWin) {
        targetWin.location.href = url;
      } else {
        const w = window.open(url, '_blank', 'noopener,noreferrer');
        if (!w) toast.error('يرجى السماح بالنوافذ المنبثقة');
      }
    } catch (e) {
      try { targetWin?.close(); } catch {}
      toast.error('فشل فتح الملف');
    }
  };

  // Attachments are no longer shipped inline in list payloads; resolve the
  // bytes on demand via /teacher/portfolio/file/{file_id} when the user opens one.
  const openEvidenceItem = async (item) => {
    if (!item) { toast.error('لا يوجد ملف مرفق لهذا الشاهد'); return; }
    if (item.file_url) { openEvidenceFile(item.file_url); return; }
    const handle = item.file_id || item.id;
    if (!handle || !(item.file_id || item.has_file)) { toast.error('لا يوجد ملف مرفق لهذا الشاهد'); return; }
    // Open the window synchronously so popup blockers tie it to the user click.
    const w = window.open('about:blank', '_blank');
    try {
      const res = await api.get(`/teacher/portfolio/file/${handle}`);
      openEvidenceFile(res.data?.file_url, w);
    } catch (err) {
      try { w?.close(); } catch {}
      nassaqError(getApiErrorMessage(err) || 'فشل فتح الملف');
    }
  };
  const [manualEvForm, setManualEvForm] = useState({
    section_key: '', evidence_type: '', title_ar: '', description_ar: '',
    class_id: '', subject_id: '', file_kind: 'pdf',
    file_url: '', file_id: '', file_name: '',
  });
  const [manualEvSaving, setManualEvSaving] = useState(false);
  const [manualEvUploading, setManualEvUploading] = useState(false);
  const [manualEvAIBusy, setManualEvAIBusy] = useState(false);
  const fileInputRef = useRef(null);

  const runManualEvHakim = async (mode, target = 'description') => {
    if (manualEvAIBusy) return;
    if (!manualEvForm.evidence_type) { toast.error('اختر التصنيف أولاً'); return; }
    const isTitle = target === 'title';
    const currentText = isTitle ? (manualEvForm.title_ar || '') : (manualEvForm.description_ar || '');
    if (mode === 'improve' && !currentText.trim()) {
      toast.error(isTitle
        ? 'اكتب عنواناً أولاً ثم اضغط "تحسين بحكيم"'
        : 'اكتب وصفاً أولاً ثم اضغط "تحسين بحكيم"');
      return;
    }
    setManualEvAIBusy(true);
    try {
      const res = await api.post('/teacher/portfolio/hakim-evidence-text', {
        mode,
        field: isTitle ? 'title' : 'description',
        text: currentText,
        title: isTitle ? '' : (manualEvForm.title_ar || ''),
        evidence_type: manualEvForm.evidence_type || '',
        subject: (teacherSubjects.find(s => s.id === manualEvForm.subject_id)?.name_ar) || null,
        grade: (teacherClasses.find(c => c.id === manualEvForm.class_id)?.name_ar) || null,
      });
      if (res?.data?.success && res.data.text) {
        setManualEvForm(p => isTitle
          ? { ...p, title_ar: res.data.text }
          : { ...p, description_ar: res.data.text });
        toast.success(
          isTitle
            ? (mode === 'improve' ? 'تم تحسين العنوان' : 'تم توليد العنوان')
            : (mode === 'improve' ? 'تم تحسين الوصف' : 'تم توليد الوصف')
        );
      } else if (res?.data && res.data.success === false) {
        const reason = res.data.reason;
        toast.error(reason === 'AI_DISABLED' ? 'الذكاء الاصطناعي غير متاح' : 'تعذّر توليد النص');
      }
    } catch (err) {
      const detail = getApiErrorMessage(err);
      const map = {
        AI_DISABLED: 'الذكاء الاصطناعي غير متاح',
        TEXT_TOO_SHORT: 'النص قصير جداً للتحسين',
        HAKIM_FAILED: 'تعذّر توليد النص',
      };
      toast.error(map[detail] || 'تعذّر توليد النص');
    } finally { setManualEvAIBusy(false); }
  };

  useEffect(() => {
    if (!teacherId) return;
    let cancelled = false;
    (async () => {
      // IT workspace classes are created via /classes/create and may not have
      // corresponding teacher_assignments rows, so /teacher/classes/{id}
      // returns [] for Independent-Teacher users. Use the tenant-scoped
      // /classes endpoint as the class source for IT accounts (same source
      // TeacherClassesPage uses); real-school teachers keep /teacher/classes.
      const classesPromise = isIndependentTeacher
        ? api.get('/classes')
        : api.get(`/teacher/classes/${teacherId}`);
      const [classesRes, subjectsRes] = await Promise.allSettled([
        classesPromise,
        api.get('/subjects'),
      ]);
      if (cancelled) return;
      if (classesRes.status === 'fulfilled') {
        const data = classesRes.value?.data;
        const list = Array.isArray(data)
          ? data
          : (data?.classes || data?.data || data?.items || []);
        setTeacherClasses(Array.isArray(list) ? list.filter(c => c?.is_active !== false) : []);
      }
      if (subjectsRes.status === 'fulfilled') {
        const data = subjectsRes.value?.data;
        setTeacherSubjects(Array.isArray(data) ? data : (data?.subjects || []));
      }
    })();
    return () => { cancelled = true; };
  }, [api, teacherId, isIndependentTeacher]);

  const openManualEvDialog = (sectionKey) => {
    const sub = SUBSECTION_CONFIG_V2.find(s => s.key === sectionKey);
    const defaultType = sub?.types?.[0] || '';
    _clearManualEvPreview();
    setManualEvForm({
      section_key: sectionKey || (SUBSECTION_CONFIG_V2[0]?.key || ''),
      evidence_type: defaultType,
      title_ar: '', description_ar: '',
      class_id: '', subject_id: '', file_kind: 'pdf',
      file_url: '', file_id: '', file_name: '',
    });
    setManualEvDialog({ open: true });
  };

  const manualEvUploadTokenRef = useRef(0);
  const handleManualEvFile = async (file) => {
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    const MAX = 10 * 1024 * 1024;
    if (file.size > MAX) { nassaqError('حجم الملف يتجاوز 10 ميغابايت'); return; }
    _setManualEvPreview(file);
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
        setManualEvForm(p => ({ ...p, file_url: '', file_id: res.data.file_id, file_name: res.data.file_name }));
        toast.success('تم رفع الملف');
      }
    } catch (err) {
      if (token !== manualEvUploadTokenRef.current) return;
      nassaqError(getApiErrorMessage(err) || 'فشل رفع الملف');
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
        file_id: manualEvForm.file_id || null,
        file_name: manualEvForm.file_name || null,
        metadata: { file_kind: manualEvForm.file_kind, source: 'manual_v2' },
      });
      toast.success('تمت إضافة الشاهد');
      setManualEvDialog({ open: false });
      // Make sure the relevant sub-section stays open
      setExpandedSubsec(p => ({ ...p, [manualEvForm.section_key]: true }));
      fetchPortfolio();
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || 'فشل إضافة الشاهد');
    } finally { setManualEvSaving(false); }
  };

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      const portfolioReq = api.get('/teacher/portfolio');
      // Perceived performance: unblock the page as soon as the primary payload
      // settles; progress/sections hydrate in place afterwards.
      portfolioReq.then(() => setLoading(false), () => {});
      const [portfolioRes, progressRes, sectionsRes] = await Promise.allSettled([
        portfolioReq,
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
      const res = await api.put('/teacher/portfolio/intro', { text: introDraft });
      if (!res.data?.success) throw new Error('save-failed');
      toast.success('تم حفظ المقدمة');
      fetchPortfolio();
    } catch (e) { nassaqError('فشل حفظ المقدمة. يرجى المحاولة مرة أخرى.'); }
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
      const code = getApiErrorMessage(e);
      const msg = code === 'AI_DISABLED' ? 'الذكاء الاصطناعي غير مفعّل'
        : code === 'TEXT_TOO_SHORT' ? 'النص قصير جداً للتحسين'
        : (mode === 'improve' ? 'فشل التحسين' : 'فشل التوليد');
      toast.error(msg);
    } finally { setIntroAIBusy(false); }
  };

  const handleSaveVMV = async () => {
    setVmvBusy(true);
    try {
      const res = await api.put('/teacher/portfolio/vmv', {
        vision: vmvDraft.vision || '',
        mission: vmvDraft.mission || '',
        values: vmvDraft.values || '',
      });
      if (!res.data?.success) throw new Error('save-failed');
      toast.success('تم حفظ الرؤية والرسالة والقيم');
      fetchPortfolio();
    } catch (e) { nassaqError('فشل حفظ الرؤية والرسالة والقيم. يرجى المحاولة مرة أخرى.'); }
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
      const code = getApiErrorMessage(e);
      const msg = code === 'AI_DISABLED' ? 'الذكاء الاصطناعي غير مفعّل'
        : code === 'TEXT_TOO_SHORT' ? 'النص قصير جداً للتحسين'
        : (mode === 'improve' ? 'فشل التحسين' : 'فشل التوليد');
      toast.error(msg);
    } finally { setVmvAIBusy(false); }
  };

  const openCVDialog = (kind) => {
    cvUploadTokenRef.current++;
    setCvFileUploading(false);
    setCvForm({ title: '', organization: '', date: '', hours: '', description: '', file_url: '', file_id: '', file_name: '' });
    setCvDialog({ open: true, kind });
  };

  const handleCvFile = async (file) => {
    if (cvFileInputRef.current) cvFileInputRef.current.value = '';
    if (!file) return;
    const MAX = 10 * 1024 * 1024;
    if (file.size > MAX) { nassaqError('حجم الملف يتجاوز 10 ميغابايت'); return; }
    _setCvPreview(file);
    const token = ++cvUploadTokenRef.current;
    setCvFileUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/teacher/portfolio/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (token !== cvUploadTokenRef.current) return;
      if (res?.data?.success) {
        setCvForm(p => ({ ...p, file_url: '', file_id: res.data.file_id, file_name: res.data.file_name }));
        toast.success('تم رفع الملف');
      }
    } catch (err) {
      if (token !== cvUploadTokenRef.current) return;
      nassaqError(getApiErrorMessage(err) || 'فشل رفع الملف');
    } finally {
      if (token === cvUploadTokenRef.current) setCvFileUploading(false);
    }
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
        file_url: cvForm.file_url || null,
        file_id: cvForm.file_id || null,
        file_name: cvForm.file_name || null,
      });
      setCvDialog({ open: false, kind: 'training_attended' });
      await fetchPortfolio();
      toast.success('تمت الإضافة');
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || 'فشل الحفظ');
    }
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
          await fetchPortfolio();
          toast.success('تم الحذف');
        } catch (e) { nassaqError(getApiErrorMessage(e) || 'فشل الحذف'); }
      },
    });
  };

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const closeEvidenceDialog = useCallback(() => {
    editUploadTokenRef.current++;
    setEditFileUploading(false);
    _clearEditPreview();
    setEvidenceDialog({ open: false, mode: 'add', data: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openAddDialog = (sectionKey) => {
    const cfg = SECTION_CONFIG.find(s => s.key === sectionKey);
    const defaultType = cfg?.types?.[0] || '';
    editUploadTokenRef.current++;
    setEditFileUploading(false);
    _clearEditPreview();
    setEvidenceForm({
      evidence_type: defaultType,
      title_ar: '', title_en: '',
      description_ar: '', description_en: '',
      date: new Date().toISOString().split('T')[0],
      class_id: '', subject_id: '',
      file_url: '', file_id: '', file_name: '', file_kind: 'pdf',
    });
    setEvidenceDialog({ open: true, mode: 'add', data: null });
  };

  const openEditDialog = (evidence) => {
    const url = evidence.file_url || '';
    const metaKind = evidence?.metadata?.file_kind;
    const validKinds = FILE_KIND_OPTIONS.map(o => o.value);
    let fileKind = validKinds.includes(metaKind) ? metaKind : null;
    if (!fileKind) {
      if (/^https?:\/\//i.test(url)) fileKind = 'link';
      else if (url.startsWith('data:image/')) fileKind = 'image';
      else if (url.startsWith('data:video/')) fileKind = 'video';
      else if (url.includes('wordprocessingml')) fileKind = 'docx';
      else if (url.includes('presentationml')) fileKind = 'pptx';
      else if (url.includes('spreadsheetml')) fileKind = 'xlsx';
      else if (url.startsWith('data:text/markdown')) fileKind = 'md';
      else if (url.startsWith('data:text/plain')) fileKind = 'txt';
      else fileKind = 'pdf';
    }
    // Invalidate any in-flight edit-upload from a previous open
    editUploadTokenRef.current++;
    setEditFileUploading(false);
    _clearEditPreview();
    setEvidenceForm({
      evidence_type: evidence.evidence_type || '',
      title_ar: evidence.title_ar || '',
      title_en: evidence.title_en || '',
      description_ar: evidence.description_ar || '',
      description_en: evidence.description_en || '',
      date: evidence.date || '',
      class_id: evidence.class_id || '',
      subject_id: evidence.subject_id || '',
      file_url: url,
      file_id: evidence.file_id || '',
      file_name: evidence.file_name || '',
      file_kind: fileKind,
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
      const detail = getApiErrorMessage(err);
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
        const orig = evidenceDialog.data?.metadata || {};
        const payload = {
          evidence_type: evidenceForm.evidence_type,
          title_ar: evidenceForm.title_ar,
          title_en: evidenceForm.title_en,
          description_ar: evidenceForm.description_ar,
          description_en: evidenceForm.description_en,
          date: evidenceForm.date,
          class_id: evidenceForm.class_id || null,
          subject_id: evidenceForm.subject_id || null,
          file_url: evidenceForm.file_url || null,
          file_id: evidenceForm.file_id || null,
          file_name: evidenceForm.file_name || null,
          metadata: { ...orig, file_kind: evidenceForm.file_kind },
        };
        await api.put(`/teacher/portfolio/evidence/${evidenceDialog.data.id}`, payload);
        toast.success(t('portfolioUpdateSuccess'));
      }
      closeEvidenceDialog();
      fetchPortfolio();
    } catch (err) {
      console.error('Save evidence error:', err);
      nassaqError(getApiErrorMessage(err) || t('portfolioSaveError') || 'فشل حفظ الشاهد. يرجى المحاولة مرة أخرى.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEvidence = (evidence) => {
    showAlert({
      type: 'confirm',
      title: t('portfolioDeleteConfirm'),
      message: (evidence?.title_ar || evidence?.title_en || '') + '\nلا يمكن التراجع عن هذا الإجراء.',
      confirmText: t('delete'),
      cancelText: 'إلغاء',
      showCancel: true,
      onConfirm: async () => {
        try {
          await api.delete(`/teacher/portfolio/evidence/${evidence.id}`);
          toast.success(t('portfolioDeleteSuccess'));
          fetchPortfolio();
        } catch (err) {
          console.error('Delete error:', err);
          nassaqError(getApiErrorMessage(err) || 'فشل الحذف');
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

  const filesOnlyEvidence = useMemo(
    () => allEvidence.filter(e => !!(e.file_url || e.file_id || e.has_file)),
    [allEvidence]
  );

  // The library lists EVERY evidence record (auto-captured rows carry no file
  // attachment — an independent teacher's portfolio is typically 100% auto,
  // and a files-only base list rendered it permanently empty).
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
        (e.description_ar || '').toLowerCase().includes(q) ||
        (e.file_name || '').toLowerCase().includes(q)
      );
    }
    return items;
  }, [allEvidence, fileTypeFilter, fileFilter]);

  const sectionStats = useMemo(() => {
    return SUBSECTION_CONFIG_V2.map(sec => ({
      ...sec,
      count: allEvidence.filter(e => (sec.types || []).includes(e.evidence_type)).length,
    }));
  }, [allEvidence]);

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
  const sectionsTotal = Array.isArray(progress?.sections)
    ? progress.sections.length
    : (sectionsData ? Object.keys(sectionsData).length : 0);
  const sectionsCompleted = Array.isArray(progress?.sections)
    ? progress.sections.filter(s => (s.percent ?? s.coverage ?? 0) >= 100).length
    : 0;
  const EXPORT_FORMATS = [
    { value: 'pdf', label: 'PDF', mime: 'application/pdf', ext: 'pdf' },
    { value: 'docx', label: 'Word (DOCX)', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ext: 'docx' },
    { value: 'html', label: 'صفحة ويب (HTML)', mime: 'text/html', ext: 'html' },
  ];
  const handleDownloadPortfolio = async (fmt = 'pdf') => {
    if (exportingPdf) return;
    setExportingPdf(true);
    try {
      const cfg = EXPORT_FORMATS.find(f => f.value === fmt) || EXPORT_FORMATS[0];
      const res = await api.get(`/teacher/portfolio/export?format=${cfg.value}`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: cfg.mime });
      let filename = `portfolio.${cfg.ext}`;
      const cd = res.headers?.['content-disposition'] || res.headers?.['Content-Disposition'];
      if (cd) {
        const m = /filename="?([^";]+)"?/i.exec(cd);
        if (m && m[1]) filename = m[1];
      }
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast.success(`تم تحميل الملف بصيغة ${cfg.label}`);
    } catch (e) {
      console.error('export portfolio failed', e);
      toast.error(t('downloadFailed') || 'فشل التحميل');
    } finally {
      setExportingPdf(false);
    }
  };
  const handleAddContent = () => openManualEvDialog(SUBSECTION_CONFIG_V2[0]?.key || '');

  return (
    <Sidebar>
      <div className={`p-4 md:p-6 space-y-6 max-w-6xl mx-auto ${isRTL ? 'text-right' : 'text-left'}`}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-md">
              <Award className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-white font-cairo">
                {t('portfolioTitle')}
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 font-tajawal">
                {t('portfolioPatternAutoEvidence')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 rounded-full"
                  disabled={exportingPdf}
                  title="تحميل ملف الإنجاز"
                  aria-label="تحميل ملف الإنجاز"
                >
                  {exportingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[200px]" dir={isRTL ? 'rtl' : 'ltr'}>
                <DropdownMenuLabel className="text-xs text-gray-500 font-cairo">اختر صيغة التحميل</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {EXPORT_FORMATS.map(f => (
                  <DropdownMenuItem
                    key={f.value}
                    onClick={() => handleDownloadPortfolio(f.value)}
                    disabled={exportingPdf}
                    className="gap-2 cursor-pointer font-cairo"
                  >
                    <Download className="w-3.5 h-3.5 text-violet-600" />
                    <span>{f.label}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              size="icon"
              className="h-9 w-9 rounded-full bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
              onClick={handleAddContent}
              title={t('addContent')}
              aria-label={t('addContent')}
            >
              <Plus className="w-4 h-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={fetchPortfolio} className="gap-2">
              <RefreshCw className="w-4 h-4" />
              {t('refresh')}
            </Button>
          </div>
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
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    {sectionsCompleted}/{sectionsTotal} {t('portfolioSectionsCompleted')}
                  </span>
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
            openViewDialog={openViewDialog}
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
            openEvidenceFile={openEvidenceItem}
          />
        )}

        {activeTab === 'files' && (
          <div className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 font-cairo flex items-center gap-2">
                  <FileArchive className="w-4 h-4 text-violet-600" />
                  جميع الشواهد والملفات
                  <span className="text-[11px] font-normal text-gray-500">
                    ({allEvidence.length} شاهد{filesOnlyEvidence.length > 0 ? ` · ${filesOnlyEvidence.length} بملف مرفق` : ''})
                  </span>
                </h3>
              </div>
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
                  <EvidenceTypeOptions t={t} />
                </SelectContent>
              </Select>
            </div>

            {filteredFileEvidence.length === 0 ? (
              <Card className="border-0 shadow-sm bg-white dark:bg-gray-800">
                <CardContent className="py-12 text-center">
                  <FileArchive className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
                  {allEvidence.length === 0 ? (
                    <p data-testid="file-library-empty" className="text-gray-500 dark:text-gray-400 text-sm">
                      {t('portfolioEmptyState')}
                    </p>
                  ) : (
                    <p data-testid="file-library-no-matches" className="text-gray-500 dark:text-gray-400 text-sm">
                      {t('portfolioNoFilterMatches')}
                    </p>
                  )}
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {filteredFileEvidence.map(item => {
                  const sectionCfg = SUBSECTION_CONFIG_V2.find(s => s.types.includes(item.evidence_type))
                    || SECTION_CONFIG.find(s => s.types.includes(item.evidence_type));
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
                              {labelForType(item.evidence_type, t)}
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
                            {(item.file_url || item.file_id || item.has_file) && (
                              <Button size="icon" variant="ghost" className="h-6 w-6" title="عرض الملف" onClick={() => openEvidenceItem(item)}>
                                <FileArchive className="w-3 h-3 text-violet-600" />
                              </Button>
                            )}
                            <Button size="icon" variant="ghost" className="h-6 w-6" title="عرض التفاصيل" onClick={() => openViewDialog(item)}>
                              <Eye className="w-3 h-3 text-gray-500" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-6 w-6" title="تعديل" onClick={() => openEditDialog(item)}>
                              <Edit3 className="w-3 h-3 text-gray-400" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-6 w-6" title="حذف" onClick={() => handleDeleteEvidence(item)}>
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

            <div>
              <h3 className="text-sm font-bold text-gray-800 dark:text-gray-100 font-cairo flex items-center gap-2 mb-3">
                <BarChart3 className="w-4 h-4 text-violet-600" />
                إحصائيات الشواهد حسب القسم
              </h3>
              <div className="grid gap-3 grid-cols-2 md:grid-cols-3">
                {sectionStats.map(sec => {
                  const Icon = sec.icon;
                  return (
                    <Card key={sec.key} className="border-0 shadow-sm bg-white dark:bg-gray-800 hover:shadow-md transition-shadow">
                      <CardContent className="p-4 flex items-center gap-3">
                        <div className={`w-11 h-11 rounded-xl ${sec.bg} flex items-center justify-center shrink-0`}>
                          <Icon className={`w-5 h-5 ${sec.color}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[12px] text-gray-600 dark:text-gray-300 font-cairo truncate">{sec.title}</p>
                          <p className={`text-xl font-bold font-cairo ${sec.color}`}>{sec.count}</p>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      <Dialog open={evidenceDialog.open} onOpenChange={(open) => { if (!open) closeEvidenceDialog(); }}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] flex flex-col p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-3 shrink-0 border-b border-gray-100 dark:border-gray-800">
            <DialogTitle className="font-cairo">
              {evidenceDialog.mode === 'add' ? t('portfolioAddEvidence') : t('portfolioEditEvidence')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 px-6 py-4 overflow-y-auto flex-1 min-h-0">
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioEvidenceType')}</Label>
              <Select value={evidenceForm.evidence_type} onValueChange={(v) => setEvidenceForm(prev => ({ ...prev, evidence_type: v }))}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder={t('portfolioEvidenceType')} />
                </SelectTrigger>
                <SelectContent>
                  <EvidenceTypeOptions t={t} />
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
                    className="h-7 px-2 text-[11px] gap-1 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300 hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-900/30 dark:hover:text-violet-300"
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
                    className="h-7 px-2 text-[11px] gap-1 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-900/30 dark:hover:text-amber-300"
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
                    className="h-7 px-2 text-[11px] gap-1 border-violet-200 dark:border-violet-800 text-violet-700 dark:text-violet-300 hover:bg-violet-50 hover:text-violet-700 dark:hover:bg-violet-900/30 dark:hover:text-violet-300"
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
                    className="h-7 px-2 text-[11px] gap-1 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-300 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-900/30 dark:hover:text-amber-300"
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
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs font-medium mb-1.5 block">المادة</Label>
                <Select
                  value={evidenceForm.subject_id || '__none__'}
                  onValueChange={(v) => setEvidenceForm(prev => ({ ...prev, subject_id: v === '__none__' ? '' : v }))}
                >
                  <SelectTrigger className="h-9"><SelectValue placeholder="اختر المادة" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— بدون —</SelectItem>
                    {teacherSubjects.map(s => (
                      <SelectItem key={s.id} value={s.id}>{s.name_ar || s.name || s.name_en || s.id}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-medium mb-1.5 block">الصف</Label>
                <Select
                  value={evidenceForm.class_id || '__none__'}
                  onValueChange={(v) => setEvidenceForm(prev => ({ ...prev, class_id: v === '__none__' ? '' : v }))}
                >
                  <SelectTrigger className="h-9"><SelectValue placeholder="اختر الصف" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— بدون —</SelectItem>
                    {teacherClasses.map(c => (
                      <SelectItem key={c.id} value={c.id}>{c.name_ar || c.name || c.id}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">نوع الملف</Label>
              <Select
                value={evidenceForm.file_kind || 'pdf'}
                onValueChange={(v) => { editUploadTokenRef.current++; setEditFileUploading(false); _clearEditPreview(); setEvidenceForm(prev => ({ ...prev, file_kind: v, file_url: '', file_id: '', file_name: '' })); }}
              >
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {FILE_KIND_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{evidenceForm.file_kind === 'link' ? 'الرابط المرفق' : 'الملف المرفق'}</Label>
              {evidenceForm.file_kind === 'link' ? (
                <div className="space-y-2">
                  <Input
                    type="url"
                    dir="ltr"
                    placeholder="https://drive.google.com/..."
                    value={evidenceForm.file_url || ''}
                    onChange={(e) => setEvidenceForm(prev => ({ ...prev, file_url: e.target.value }))}
                    className="h-9"
                  />
                  <Input
                    type="text"
                    dir="rtl"
                    placeholder="عنوان الرابط (اختياري) — مثال: ملف الخطة على Drive"
                    value={evidenceForm.file_name || ''}
                    onChange={(e) => setEvidenceForm(prev => ({ ...prev, file_name: e.target.value }))}
                    className="h-9"
                  />
                  <p className="text-[11px] text-gray-500">يدعم: Google Drive، OneDrive، Dropbox، YouTube، أو أي رابط آخر يبدأ بـ https://</p>
                </div>
              ) : (
                <>
                  <input
                    ref={editFileInputRef}
                    type="file"
                    hidden
                    accept={acceptForKind(evidenceForm.file_kind)}
                    onChange={(e) => handleEditEvidenceFile(e.target.files?.[0])}
                  />
                  <button
                    type="button"
                    onClick={() => editFileInputRef.current?.click()}
                    disabled={editFileUploading}
                    className="w-full py-5 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700 text-center hover:border-violet-400 dark:hover:border-violet-600 hover:bg-violet-50/40 dark:hover:bg-violet-900/10 transition-colors"
                  >
                    {editFileUploading ? (
                      <div className="flex items-center justify-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <Loader2 className="w-4 h-4 animate-spin" /> جاري الرفع...
                      </div>
                    ) : (evidenceForm.file_url || evidenceForm.file_id) ? (
                      <div className="text-sm">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
                        <div className="text-emerald-700 dark:text-emerald-300 font-medium truncate px-2">{evidenceForm.file_name || 'ملف مرفق'}</div>
                        <div className="text-[11px] text-gray-500 mt-1">انقر للاستبدال</div>
                      </div>
                    ) : (
                      <div>
                        <FileArchive className="w-6 h-6 text-gray-400 mx-auto mb-1.5" />
                        <div className="text-sm text-gray-600 dark:text-gray-400">اضغط لرفع ملف أو اسحبه هنا</div>
                        <div className="text-[11px] text-gray-400 mt-0.5">PDF، صور، فيديو، Office (حد أقصى 10 MB)</div>
                      </div>
                    )}
                  </button>
                  {/* Inline file preview */}
                  {editPreviewSrc && (
                    <div className="mt-3 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                        <span className="text-[11px] text-gray-500 font-cairo">معاينة الملف</span>
                        <button
                          type="button"
                          aria-label="إزالة الملف والمعاينة"
                          onClick={() => { editUploadTokenRef.current++; setEditFileUploading(false); _clearEditPreview(); setEvidenceForm(prev => ({ ...prev, file_url: '', file_id: '', file_name: '' })); }}
                          className="text-gray-400 hover:text-red-500 transition-colors p-0.5"
                        >
                          <X className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
                      </div>
                      <div className="p-3">
                        {editPreviewMime?.startsWith('image/') ? (
                          <img
                            src={editPreviewSrc}
                            alt={evidenceForm.file_name || 'معاينة الصورة'}
                            className="max-h-48 w-auto rounded-lg object-contain mx-auto block"
                          />
                        ) : editPreviewMime === 'application/pdf' ? (
                          <div className="flex flex-col items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                            <FileText className="w-12 h-12 text-red-500 dark:text-red-400" aria-hidden="true" strokeWidth={1.5} />
                            <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate max-w-full font-tajawal text-center">
                              {evidenceForm.file_name || 'ملف PDF'}
                            </div>
                            <a
                              href={editPreviewSrc}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm rounded-lg transition-colors font-cairo"
                            >
                              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" strokeWidth={1.5} />
                              فتح PDF
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
                            <FileText className="w-8 h-8 text-gray-400 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate font-tajawal">
                                {evidenceForm.file_name || 'ملف'}
                              </div>
                              <div className="text-[11px] text-gray-500 mt-0.5 font-cairo">لا تتوفر معاينة لهذا النوع</div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
              {(evidenceForm.file_url || evidenceForm.file_id) && !editPreviewSrc && (
                <button
                  type="button"
                  onClick={() => { editUploadTokenRef.current++; setEditFileUploading(false); _clearEditPreview(); setEvidenceForm(prev => ({ ...prev, file_url: '', file_id: '', file_name: '' })); }}
                  className="mt-2 text-[11px] text-red-600 hover:text-red-700 underline"
                >
                  {evidenceForm.file_kind === 'link' ? 'إزالة الرابط' : 'إزالة الملف'}
                </button>
              )}
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioEvidenceDate')}</Label>
              <Input type="date" value={evidenceForm.date} onChange={(e) => setEvidenceForm(prev => ({ ...prev, date: e.target.value }))} className="h-9" />
            </div>
          </div>
          <DialogFooter className="px-6 py-4 shrink-0 border-t border-gray-100 dark:border-gray-800">
            <Button variant="outline" onClick={closeEvidenceDialog}>
              {t('cancel')}
            </Button>
            <Button onClick={handleSaveEvidence} disabled={saving || editFileUploading || !evidenceForm.evidence_type || !evidenceForm.title_ar}>
              {saving && <Loader2 className={`w-4 h-4 animate-spin ${isRTL ? 'ml-2' : 'mr-2'}`} />}
              {t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual evidence dialog (V2) */}
      <Dialog open={manualEvDialog.open} onOpenChange={(open) => { if (!open) { _clearManualEvPreview(); setManualEvDialog({ open: false }); } }}>
        <DialogContent className="sm:max-w-md max-h-[90vh] flex flex-col p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-3 shrink-0 border-b border-gray-100 dark:border-gray-800">
            <DialogTitle className="font-cairo text-start">إضافة شاهد يدوي</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 overflow-y-auto flex-1 min-h-0" dir="rtl">
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
              <div className="flex items-center justify-between mb-1">
                <Label className="text-xs font-medium">عنوان الشاهد</Label>
                <div className="flex items-center gap-1">
                  <Button
                    type="button" size="sm" variant="outline"
                    onClick={() => runManualEvHakim('generate', 'title')}
                    disabled={manualEvAIBusy || !manualEvForm.evidence_type}
                    className="h-7 px-2 text-[11px] gap-1 border-violet-300 text-violet-700 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-700 dark:text-violet-300 dark:hover:text-violet-300"
                    title="إنشاء عنوان بحكيم"
                  >
                    {manualEvAIBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    إنشاء بحكيم
                  </Button>
                  <Button
                    type="button" size="sm" variant="outline"
                    onClick={() => runManualEvHakim('improve', 'title')}
                    disabled={manualEvAIBusy || !(manualEvForm.title_ar || '').trim()}
                    className="h-7 px-2 text-[11px] gap-1 border-fuchsia-300 text-fuchsia-700 hover:bg-fuchsia-50 hover:text-fuchsia-700 dark:border-fuchsia-700 dark:text-fuchsia-300 dark:hover:text-fuchsia-300"
                    title="تحسين العنوان بحكيم"
                  >
                    {manualEvAIBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wand2 className="w-3 h-3" />}
                    تحسين بحكيم
                  </Button>
                </div>
              </div>
              <Textarea
                value={manualEvForm.title_ar}
                onChange={(e) => setManualEvForm(p => ({ ...p, title_ar: e.target.value }))}
                placeholder="مثال: ورقة عمل الوحدة الثالثة"
                rows={2}
                className="resize-none"
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
                    className="h-7 px-2 text-[11px] gap-1 border-violet-300 text-violet-700 hover:bg-violet-50 hover:text-violet-700 dark:border-violet-700 dark:text-violet-300 dark:hover:text-violet-300"
                    title="توليد وصف بحكيم"
                  >
                    {manualEvAIBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                    إنشاء بحكيم
                  </Button>
                  <Button
                    type="button" size="sm" variant="outline"
                    onClick={() => runManualEvHakim('improve')}
                    disabled={manualEvAIBusy || !(manualEvForm.description_ar || '').trim()}
                    className="h-7 px-2 text-[11px] gap-1 border-fuchsia-300 text-fuchsia-700 hover:bg-fuchsia-50 hover:text-fuchsia-700 dark:border-fuchsia-700 dark:text-fuchsia-300 dark:hover:text-fuchsia-300"
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
                onValueChange={(v) => { _clearManualEvPreview(); setManualEvForm(p => ({ ...p, file_kind: v, file_url: '', file_id: '', file_name: '' })); }}
              >
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {FILE_KIND_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              {manualEvForm.file_kind === 'link' ? (
                <div className="space-y-2">
                  <Label className="text-xs font-medium block">الرابط</Label>
                  <Input
                    type="url"
                    dir="ltr"
                    placeholder="https://drive.google.com/..."
                    value={manualEvForm.file_url || ''}
                    onChange={(e) => setManualEvForm(p => ({ ...p, file_url: e.target.value }))}
                    className="h-9"
                  />
                  <Input
                    type="text"
                    dir="rtl"
                    placeholder="عنوان الرابط (اختياري) — مثال: ملف الخطة على Drive"
                    value={manualEvForm.file_name || ''}
                    onChange={(e) => setManualEvForm(p => ({ ...p, file_name: e.target.value }))}
                    className="h-9"
                  />
                  <p className="text-[11px] text-gray-500">يدعم: Google Drive، OneDrive، Dropbox، YouTube، أو أي رابط آخر يبدأ بـ https://</p>
                  {(manualEvForm.file_url || manualEvForm.file_id) && (
                    <button
                      type="button"
                      onClick={() => setManualEvForm(p => ({ ...p, file_url: '', file_id: '', file_name: '' }))}
                      className="text-[11px] text-red-600 hover:text-red-700 underline"
                    >
                      إزالة الرابط
                    </button>
                  )}
                </div>
              ) : (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    hidden
                    accept={acceptForKind(manualEvForm.file_kind)}
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
                    ) : (manualEvForm.file_url || manualEvForm.file_id) ? (
                      <div className="text-sm">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
                        <div className="text-emerald-700 dark:text-emerald-300 font-medium truncate px-2">{manualEvForm.file_name}</div>
                        <div className="text-[11px] text-gray-500 mt-1">انقر للاستبدال</div>
                      </div>
                    ) : (
                      <div>
                        <FileArchive className="w-6 h-6 text-gray-400 mx-auto mb-1.5" />
                        <div className="text-sm text-gray-600 dark:text-gray-400">اضغط لرفع ملف أو اسحبه هنا</div>
                        <div className="text-[11px] text-gray-400 mt-0.5">PDF، صور، فيديو، Office (حد أقصى 10 MB)</div>
                      </div>
                    )}
                  </button>
                  {/* Inline file preview */}
                  {manualEvPreviewSrc && (
                    <div className="mt-3 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                        <span className="text-[11px] text-gray-500 font-cairo">معاينة الملف</span>
                        <button
                          type="button"
                          aria-label="إزالة الملف والمعاينة"
                          onClick={() => { _clearManualEvPreview(); setManualEvForm(p => ({ ...p, file_url: '', file_id: '', file_name: '' })); }}
                          className="text-gray-400 hover:text-red-500 transition-colors p-0.5"
                        >
                          <X className="w-3.5 h-3.5" aria-hidden="true" />
                        </button>
                      </div>
                      <div className="p-3">
                        {manualEvPreviewMime?.startsWith('image/') ? (
                          <img
                            src={manualEvPreviewSrc}
                            alt={manualEvForm.file_name || 'معاينة الصورة'}
                            className="max-h-48 w-auto rounded-lg object-contain mx-auto block"
                          />
                        ) : manualEvPreviewMime === 'application/pdf' ? (
                          <div className="flex flex-col items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                            <FileText className="w-12 h-12 text-red-500 dark:text-red-400" aria-hidden="true" strokeWidth={1.5} />
                            <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate max-w-full font-tajawal text-center">
                              {manualEvForm.file_name || 'ملف PDF'}
                            </div>
                            <a
                              href={manualEvPreviewSrc}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm rounded-lg transition-colors font-cairo"
                            >
                              <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" strokeWidth={1.5} />
                              فتح PDF
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
                            <FileText className="w-8 h-8 text-gray-400 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                            <div className="min-w-0">
                              <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate font-tajawal">
                                {manualEvForm.file_name || 'ملف'}
                              </div>
                              <div className="text-[11px] text-gray-500 mt-0.5 font-cairo">لا تتوفر معاينة لهذا النوع</div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <DialogFooter className="px-6 py-4 shrink-0 border-t border-gray-100 dark:border-gray-800">
            <Button variant="outline" onClick={() => { _clearManualEvPreview(); setManualEvDialog({ open: false }); }}>إلغاء</Button>
            <Button onClick={handleSaveManualEvidence} disabled={manualEvSaving || !manualEvForm.evidence_type || !(manualEvForm.title_ar || '').trim()} className="gap-1.5">
              {manualEvSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              إضافة الشاهد
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View evidence details dialog */}
      <Dialog open={viewEvDialog.open} onOpenChange={(open) => { if (!open) setViewEvDialog({ open: false, item: null }); }}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] flex flex-col p-0 gap-0" dir="rtl">
          <DialogHeader className="px-6 pt-6 pb-3 shrink-0 border-b border-gray-100 dark:border-gray-800">
            <DialogTitle className="font-cairo text-start flex items-center gap-2">
              <Eye className="w-4 h-4 text-violet-600" /> تفاصيل الشاهد
            </DialogTitle>
          </DialogHeader>
          {viewEvDialog.item && (() => {
            const it = viewEvDialog.item;
            const sectionTitle = SUBSECTION_CONFIG_V2.find(s => (s.types || []).includes(it.evidence_type))?.title || '—';
            const cls = teacherClasses.find(c => c.id === it.class_id);
            const subj = teacherSubjects.find(s => s.id === it.subject_id);
            const className = cls?.name_ar || cls?.name
              || extraClassNames[it.class_id]
              || (it.class_id ? '—' : '—');
            const subjectName = subj?.name_ar || subj?.name || subj?.name_en
              || extraSubjectNames[it.subject_id]
              || (it.subject_id ? '—' : '—');
            return (
              <div className="space-y-3 px-6 py-4 text-right overflow-y-auto flex-1 min-h-0">
                <div>
                  <div className="text-[11px] text-gray-500 mb-0.5">العنوان</div>
                  <div className="text-sm font-semibold text-gray-800 dark:text-gray-100 font-cairo">
                    {isRTL ? (it.title_ar || it.title_en) : (it.title_en || it.title_ar)}
                  </div>
                </div>
                {(it.description_ar || it.description_en) && (
                  <div>
                    <div className="text-[11px] text-gray-500 mb-0.5">الوصف</div>
                    <div className="text-sm text-gray-700 dark:text-gray-200 leading-relaxed whitespace-pre-wrap">
                      {isRTL ? (it.description_ar || it.description_en) : (it.description_en || it.description_ar)}
                    </div>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[11px] text-gray-500 mb-0.5">القسم</div>
                    <div className="text-sm">{sectionTitle}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-gray-500 mb-0.5">التصنيف الفرعي</div>
                    <div className="text-sm">{labelForType(it.evidence_type, t)}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-gray-500 mb-0.5">المادة</div>
                    <div className="text-sm">{subjectName}</div>
                  </div>
                  <div>
                    <div className="text-[11px] text-gray-500 mb-0.5">الصف</div>
                    <div className="text-sm">{className}</div>
                  </div>
                  {it.date && (
                    <div>
                      <div className="text-[11px] text-gray-500 mb-0.5">التاريخ</div>
                      <div className="text-sm flex items-center gap-1"><Calendar className="w-3 h-3" />{it.date}</div>
                    </div>
                  )}
                  <div>
                    <div className="text-[11px] text-gray-500 mb-0.5">المصدر</div>
                    <div className="text-sm">
                      {it.source === 'auto'
                        ? <span className="inline-flex items-center gap-1 text-amber-600"><Zap className="w-3 h-3" /> تلقائي</span>
                        : 'إضافة يدوية'}
                    </div>
                  </div>
                </div>
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <div className="text-[11px] text-gray-500 mb-1">الملف المرفق</div>
                  {(it.file_url || it.file_id || it.has_file) ? (
                    <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <FileArchive className="w-4 h-4 text-violet-600 shrink-0" />
                        <span className="text-sm truncate">{it.file_name || 'ملف مرفق'}</span>
                      </div>
                      <Button size="sm" onClick={() => openEvidenceItem(it)} className="gap-1.5 bg-violet-600 hover:bg-violet-700 text-white shrink-0">
                        <Eye className="w-3.5 h-3.5" /> عرض الملف
                      </Button>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400 italic">لا يوجد ملف مرفق</div>
                  )}
                </div>
              </div>
            );
          })()}
          <DialogFooter className="px-6 py-4 shrink-0 border-t border-gray-100 dark:border-gray-800">
            <Button variant="outline" onClick={() => setViewEvDialog({ open: false, item: null })}>إغلاق</Button>
            {viewEvDialog.item && (
              <Button onClick={() => { const it = viewEvDialog.item; setViewEvDialog({ open: false, item: null }); openEditDialog(it); }} className="gap-1.5">
                <Edit3 className="w-3.5 h-3.5" /> تعديل
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* CV manual-add dialog */}
      <Dialog open={cvDialog.open} onOpenChange={(open) => { if (!open) { _clearCvPreview(); setCvDialog({ open: false, kind: 'training_attended' }); } }}>
        <DialogContent className="sm:max-w-md max-h-[90vh] flex flex-col p-0 gap-0">
          <DialogHeader className="px-6 pt-6 pb-3 shrink-0 border-b border-gray-100 dark:border-gray-800">
            <DialogTitle className="font-cairo">
              {cvDialog.kind === 'training_attended' && 'إضافة دورة تدريبية مستفاد منها'}
              {cvDialog.kind === 'training_delivered' && 'إضافة دورة تدريبية منفذة'}
              {cvDialog.kind === 'award' && 'إضافة جائزة'}
              {cvDialog.kind === 'thank_letter' && 'إضافة خطاب شكر'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 px-6 py-4 overflow-y-auto flex-1 min-h-0">
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
            {/* Optional file attachment — PDF / DOC / images */}
            <div>
              <Label className="text-xs font-medium mb-1.5 block">إرفاق ملف (اختياري) - PDF, DOC, pictures formats</Label>
              <input
                ref={cvFileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.gif,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,image/*"
                onChange={(e) => handleCvFile(e.target.files?.[0])}
              />
              {(cvForm.file_url || cvForm.file_id) ? (
                <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-violet-200 dark:border-violet-800/60 bg-violet-50/60 dark:bg-violet-900/20">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="w-4 h-4 text-violet-600 dark:text-violet-400 shrink-0" />
                    <span className="text-xs font-medium text-violet-700 dark:text-violet-300 truncate font-tajawal">
                      {cvForm.file_name || 'ملف مرفق'}
                    </span>
                  </div>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7 shrink-0"
                    title="إزالة الملف"
                    onClick={() => { cvUploadTokenRef.current++; setCvFileUploading(false); _clearCvPreview(); setCvForm(p => ({ ...p, file_url: '', file_id: '', file_name: '' })); }}
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-500" />
                  </Button>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={cvFileUploading}
                  onClick={() => cvFileInputRef.current?.click()}
                  className="w-full py-3 rounded-lg border-2 border-dashed border-violet-300 dark:border-violet-700 hover:border-violet-500 dark:hover:border-violet-500 hover:bg-violet-50/50 dark:hover:bg-violet-900/10 transition-colors flex flex-col items-center justify-center gap-1 text-violet-600 dark:text-violet-300 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {cvFileUploading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span className="text-xs font-tajawal">جارٍ الرفع…</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-5 h-5" />
                      <span className="text-xs font-tajawal">اضغط لاختيار ملف</span>
                      <span className="text-[10px] text-violet-500/80 dark:text-violet-400/80 font-tajawal">PDF, DOC, صور — حتى 10 ميغابايت</span>
                    </>
                  )}
                </button>
              )}
              {/* Inline file preview */}
              {cvPreviewSrc && (
                <div className="mt-3 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                    <span className="text-[11px] text-gray-500 font-cairo">معاينة الملف</span>
                    <button
                      type="button"
                      aria-label="إزالة الملف والمعاينة"
                      onClick={() => { cvUploadTokenRef.current++; setCvFileUploading(false); _clearCvPreview(); setCvForm(p => ({ ...p, file_url: '', file_id: '', file_name: '' })); }}
                      className="text-gray-400 hover:text-red-500 transition-colors p-0.5"
                    >
                      <X className="w-3.5 h-3.5" aria-hidden="true" />
                    </button>
                  </div>
                  <div className="p-3">
                    {cvPreviewMime?.startsWith('image/') ? (
                      <img
                        src={cvPreviewSrc}
                        alt={cvForm.file_name || 'معاينة الصورة'}
                        className="max-h-48 w-auto rounded-lg object-contain mx-auto block"
                      />
                    ) : cvPreviewMime === 'application/pdf' ? (
                      <div className="flex flex-col items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                        <FileText className="w-12 h-12 text-red-500 dark:text-red-400" aria-hidden="true" strokeWidth={1.5} />
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate max-w-full font-tajawal text-center">
                          {cvForm.file_name || 'ملف PDF'}
                        </div>
                        <a
                          href={cvPreviewSrc}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-sm rounded-lg transition-colors font-cairo"
                        >
                          <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" strokeWidth={1.5} />
                          فتح PDF
                        </a>
                      </div>
                    ) : (
                      <div className="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
                        <FileText className="w-8 h-8 text-gray-400 shrink-0" aria-hidden="true" strokeWidth={1.5} />
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-gray-700 dark:text-gray-200 truncate font-tajawal">
                            {cvForm.file_name || 'ملف'}
                          </div>
                          <div className="text-[11px] text-gray-500 mt-0.5 font-cairo">لا تتوفر معاينة لهذا النوع</div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
          <DialogFooter className="px-6 py-4 shrink-0 border-t border-gray-100 dark:border-gray-800">
            <Button variant="outline" onClick={() => { _clearCvPreview(); setCvDialog({ open: false, kind: 'training_attended' }); }}>إلغاء</Button>
            <Button onClick={handleAddCVItem} disabled={cvSaving || cvFileUploading || !cvForm.title || cvForm.title.trim().length < 2}>
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

function EvidenceRow({ item, isRTL, onView, onEdit, onDelete }) {
  const { t } = useTranslation();
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
              <Zap className="w-2.5 h-2.5" /> {t('portfolioAuto')}
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
          <span>{labelForType(item.evidence_type, t)}</span>
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Button size="icon" variant="ghost" className="h-7 w-7" title="عرض التفاصيل" onClick={() => onView?.(item)}>
          <Eye className="w-3.5 h-3.5 text-violet-500" />
        </Button>
        <Button size="icon" variant="ghost" className="h-7 w-7" title="تعديل" onClick={() => onEdit?.(item)}>
          <Edit3 className="w-3.5 h-3.5 text-gray-400" />
        </Button>
        <Button size="icon" variant="ghost" className="h-7 w-7" title="حذف" onClick={() => onDelete?.(item)}>
          <Trash2 className="w-3.5 h-3.5 text-red-400" />
        </Button>
      </div>
    </div>
  );
}

function CVItemRow({ item, isRTL, onDelete, onOpenFile }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-750">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className="text-sm font-medium text-gray-800 dark:text-gray-100 font-tajawal">{item.title}</span>
          {item.source === 'auto' && (
            <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-400 gap-1">
              <Zap className="w-2.5 h-2.5" aria-hidden="true" strokeWidth={1.5} /> تلقائي
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-gray-500 dark:text-gray-400 flex-wrap">
          {item.organization && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" aria-hidden="true" strokeWidth={1.5} />{item.organization}</span>}
          {item.date && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" aria-hidden="true" strokeWidth={1.5} />{item.date}</span>}
          {item.hours != null && <span>{item.hours} ساعة</span>}
        </div>
        {item.description && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">{item.description}</p>
        )}
        {(item.file_url || item.file_id || item.has_file) && (
          <div className="mt-2 flex items-center justify-between gap-2 p-2 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <FileArchive className="w-3.5 h-3.5 text-violet-600 shrink-0" aria-hidden="true" strokeWidth={1.5} />
              <span className="text-xs truncate text-start">{item.file_name || 'ملف مرفق'}</span>
            </div>
            <Button size="sm" variant="outline" onClick={() => onOpenFile?.(item)} className="gap-1.5 h-7 text-xs shrink-0">
              <Eye className="w-3.5 h-3.5" aria-hidden="true" strokeWidth={1.5} /> عرض الملف
            </Button>
          </div>
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
    sectionsData, isRTL, openManualEvDialog, openViewDialog,
    expandedV2, toggleV2, expandedSubsec, toggleSubsec,
    introDraft, setIntroDraft, introBusy, introAIBusy, handleSaveIntro, handleGenerateIntro,
    vmvDraft, setVmvDraft, vmvBusy, vmvAIBusy, handleSaveVMV, handleGenerateVMV,
    openCVDialog, handleDeleteCVItem, openEditDialog, handleDeleteEvidence,
    openEvidenceFile,
  } = props;

  const canViewInternalIds = useCanViewInternalIds();
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
            { icon: BookMarked, label: 'التخصص', value: maskInternalId(profile.specialization, canViewInternalIds) || maskInternalId(profile.subject, canViewInternalIds) },
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
          onOpenFile={openEvidenceFile}
        />
        {/* Training delivered */}
        <CVCategorySection
          title="الدورات التدريبية المنفذة"
          icon={PenSquare} color="text-emerald-600 dark:text-emerald-400"
          items={cv?.training_delivered || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('training_delivered')}
          onDelete={handleDeleteCVItem}
          onOpenFile={openEvidenceFile}
        />
        {/* Awards */}
        <CVCategorySection
          title="الجوائز"
          icon={Award} color="text-amber-600 dark:text-amber-400"
          items={cv?.award || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('award')}
          onDelete={handleDeleteCVItem}
          onOpenFile={openEvidenceFile}
        />
        {/* Thank letters */}
        <CVCategorySection
          title="خطابات الشكر"
          icon={HandHeart} color="text-pink-600 dark:text-pink-400"
          items={cv?.thank_letter || []}
          isRTL={isRTL}
          onAdd={() => openCVDialog('thank_letter')}
          onDelete={handleDeleteCVItem}
          onOpenFile={openEvidenceFile}
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
                        const count = (sd.items || []).filter(it => it.evidence_type === typeKey).length;
                        const has = count > 0;
                        return (
                          <Badge
                            key={typeKey}
                            variant="outline"
                            className={`text-[10px] ${has ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800' : 'text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-700'}`}
                          >
                            {has ? <CheckCircle2 className="w-3 h-3 ml-1" /> : <AlertCircle className="w-3 h-3 ml-1" />}
                            {labelForType(typeKey)}
                            {count > 1 && (
                              <span className="ml-1 px-1 rounded-full bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200 text-[9px] font-semibold">
                                {count}
                              </span>
                            )}
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
                            onView={openViewDialog}
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

function CVCategorySection({ title, icon: Icon, color, items, isRTL, onAdd, onDelete, onOpenFile }) {
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
            <CVItemRow key={it.id} item={it} isRTL={isRTL} onDelete={onDelete} onOpenFile={onOpenFile} />
          ))}
        </div>
      )}
    </div>
  );
}
