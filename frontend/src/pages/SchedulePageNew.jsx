/**
 * إدارة الجداول الذكية — Smart Master Grid
 * نَسَّق | NASSAQ School Management System
 *
 * مصفوفة موحَّدة تعرض كل المعلمين كصفوف وكل (يوم × حصة) كأعمدة في تصميم RTL
 * مع رؤوس مثبَّتة، لوحة مؤشرات أداء أعلى الشاشة، شريط تنبيه أحمر ديناميكي،
 * وأزرار إجراءات أساسية (إنشاء تلقائي + تسجيل غياب).
 *
 * تستهلك endpoint وحيد: GET /api/schedule/master-grid
 */

import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../components/ui/tooltip';
import {
  Wand2, UserX, Sparkles, Loader2, RefreshCw,
  Scale, Hourglass, UserMinus, AlertOctagon, AlertTriangle, Repeat,
  ShieldAlert, Settings, ArrowLeft, ListChecks,
  Undo2, Layers,
} from 'lucide-react';
import CandidatesSidePanel from '../components/schedule/CandidatesSidePanel';
import BulkSubstitutionPanel from '../components/schedule/BulkSubstitutionPanel';

// ─── Infeasibility issue → contextual next step ────────────────────────────
// كل كود INF يحدد الصفحة الأنسب التي تحل المشكلة. عند غياب الكود نوجِّه إلى
// إعدادات المدرسة العامة كملاذ افتراضي.
const ISSUE_NEXT_STEP = {
  'INF-01': { label: 'فتح إعدادات الهيكل الأكاديمي', path: '/school/settings?section=academic' },
  'INF-02': { label: 'فتح إعدادات الهيكل الأكاديمي', path: '/school/settings?section=academic' },
  'INF-03': { label: 'فتح صفحة المعلمين والإسنادات',  path: '/school/teachers' },
  'INF-04': { label: 'فتح إعدادات القاعات',           path: '/school/settings?section=dynamic' },
  'INF-05': { label: 'فتح إعدادات اليوم الدراسي',     path: '/school/settings?section=dynamic' },
};
const DEFAULT_NEXT_STEP = { label: 'فتح إعدادات المدرسة', path: '/school/settings' };

const DAYS = [
  { key: 'sunday',    ar: 'الأحد' },
  { key: 'monday',    ar: 'الإثنين' },
  { key: 'tuesday',   ar: 'الثلاثاء' },
  { key: 'wednesday', ar: 'الأربعاء' },
  { key: 'thursday',  ar: 'الخميس' },
];
const PERIODS = [1, 2, 3, 4, 5, 6, 7];

const RANK_AR = {
  expert: 'خبير',
  advanced: 'متقدم',
  practitioner: 'ممارس',
  assistant: 'مساعد',
};

// Tiny Arabic relative-time formatter (mirrors TeacherAttendancePage).
// Used by the absence tooltip so principals can see when a row was flipped.
function formatAbsenceTimeAr(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const diffSec = Math.round((Date.now() - then.getTime()) / 1000);
  if (diffSec < 5) return 'الآن';
  if (diffSec < 60) return `قبل ${diffSec} ثانية`;
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `قبل ${mins} دقيقة`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `قبل ${hours} ساعة`;
  const days = Math.round(hours / 24);
  if (days < 7) return `قبل ${days} يوم`;
  return then.toLocaleDateString('ar-EG');
}

// ─── Absence pill with recorder tooltip ───────────────────────────────────
// The pill itself is unchanged visually; hovering reveals "سجَّله: <name>"
// and the relative time. Falls back gracefully when the audit fields are
// absent (older absence rows that predate the recorder feature).
function AbsencePill({ recorderName, recordedAt }) {
  const pill = (
    <span
      tabIndex={0}
      className="text-[10px] font-semibold rounded border border-red-400 text-red-700 bg-red-100 px-1.5 py-0.5 cursor-help focus:outline-none focus:ring-1 focus:ring-red-400"
    >
      غائب
    </span>
  );

  const hasAudit = Boolean(recorderName) || Boolean(recordedAt);
  if (!hasAudit) return pill;

  const relTime = formatAbsenceTimeAr(recordedAt);
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{pill}</TooltipTrigger>
        <TooltipContent
          side="top"
          align="start"
          className="bg-slate-900 text-white text-[11px] leading-tight max-w-[220px]"
        >
          <div dir="rtl" className="space-y-0.5">
            <div>
              <span className="font-semibold">سجَّله:</span>{' '}
              {recorderName || '—'}
            </div>
            {relTime && (
              <div className="opacity-80">{relTime}</div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ─── Top-level KPI card ────────────────────────────────────────────────────
function KpiCard({ icon: Icon, label, value, suffix, accent }) {
  // accent: { bg, ring, iconBg, iconText, valueText }
  return (
    <Card className={`border ${accent.ring} ${accent.bg} shadow-sm`}>
      <CardContent className="p-4 flex items-center gap-4">
        <div className={`h-12 w-12 rounded-xl flex items-center justify-center ${accent.iconBg}`}>
          <Icon className={`h-6 w-6 ${accent.iconText}`} />
        </div>
        <div className="flex-1">
          <p className="text-xs text-slate-600 mb-1">{label}</p>
          <div className="flex items-baseline gap-1">
            <span className={`text-2xl font-bold ${accent.valueText}`}>{value}</span>
            {suffix && <span className="text-sm text-slate-500">{suffix}</span>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Cell renderers ────────────────────────────────────────────────────────
function FilledCell({ cell, onClick }) {
  // cell.is_vacant => حصة شاغرة (معلمها غائب) — تفتح نافذة المرشحين عند الضغط
  if (cell?.is_vacant) {
    return (
      <button
        type="button"
        onClick={onClick}
        title="اضغط لاختيار بديل من جدول الانتظار"
        className="w-full h-full min-h-[44px] flex flex-col items-center justify-center text-[11px] font-semibold leading-tight px-1 py-1
                   bg-red-100 hover:bg-red-200 text-red-800 border border-red-300 rounded-md transition-colors"
      >
        <span className="font-bold">شاغرة</span>
        <span className="text-[10px] opacity-75 truncate max-w-full">{cell.class_name}</span>
      </button>
    );
  }
  // cell.is_substituted => الخانة الأصلية للمعلم الغائب بعد إسناد بديل
  if (cell?.is_substituted) {
    return (
      <div
        className="w-full h-full min-h-[44px] flex flex-col items-center justify-center text-[11px] leading-tight px-1 py-1
                   bg-emerald-50 border border-emerald-300 rounded-md text-emerald-800"
        title={`بديل: ${cell.substitute_teacher_name || ''}`}
      >
        <span className="font-bold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          بديل: {cell.substitute_teacher_name || '—'}
        </span>
      </div>
    );
  }
  // cell.is_substitute => الخانة المضافة لصف المعلم البديل
  if (cell?.is_substitute) {
    return (
      <div
        className="w-full h-full min-h-[44px] flex flex-col items-center justify-center text-[11px] leading-tight px-1 py-1
                   bg-violet-50 border border-violet-300 rounded-md text-violet-800 relative"
        title={`بديل عن ${cell.original_teacher_name || ''}`}
      >
        <Repeat className="absolute top-0.5 right-0.5 h-2.5 w-2.5 opacity-70" />
        <span className="font-bold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          {cell.subject_name || ''}
        </span>
      </div>
    );
  }
  return (
    <div
      className="w-full h-full min-h-[44px] flex flex-col items-center justify-center text-[11px] leading-tight px-1 py-1
                 bg-white border border-slate-200 rounded-md text-slate-800"
      title={cell?.subject_name || ''}
    >
      <span className="font-bold">{cell?.class_name || '—'}</span>
      {cell?.subject_name && (
        <span className="text-[10px] text-slate-500 truncate max-w-full">{cell.subject_name}</span>
      )}
    </div>
  );
}

function EmptyCell({ teacherAbsent }) {
  // فراغ في صف المعلم — لا تنبيه. حتى لو كان المعلم غائباً، الخلية الفارغة تبقى
  // فارغة (تظهر فقط بصبغة حمراء خفيفة على الصف). الخانات التي يجب وسمها "شاغرة"
  // هي الخانات التي كان فيها حصة مجدولة وتحوّلت إلى vacant بسبب الغياب — وهي
  // تُرَنْدَر عبر FilledCell.is_vacant = true.
  return (
    <div
      className={`w-full h-full min-h-[44px] rounded-md border border-dashed ${
        teacherAbsent
          ? 'bg-red-50/60 border-red-200'
          : 'bg-slate-50 border-slate-200'
      }`}
    />
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────
export default function SchedulePageNew() {
  const { user, api } = useAuth();
  const navigate = useNavigate();
  const schoolId = user?.tenant_id;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [grid, setGrid] = useState(null);

  // Substitution drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSlot, setDrawerSlot] = useState(null);

  // Bulk substitution drawer state
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkTarget, setBulkTarget] = useState(null);

  // إنشاء الجدول تلقائياً
  const [generating, setGenerating] = useState(false);

  // حوار "تعذّر التوليد" مع تفاصيل الـ infeasibility report
  const [blockedOpen, setBlockedOpen] = useState(false);
  const [blockedReport, setBlockedReport] = useState(null);

  // تسجيل الغياب
  const [absenceOpen, setAbsenceOpen] = useState(false);
  const [absenceTeacherId, setAbsenceTeacherId] = useState('');
  const [absenceNotes, setAbsenceNotes] = useState('');
  const [savingAbsence, setSavingAbsence] = useState(false);

  // إلغاء الغياب
  const [undoTeacher, setUndoTeacher] = useState(null);
  const [undoingAbsence, setUndoingAbsence] = useState(false);

  const loadGrid = useCallback(async () => {
    if (!schoolId) return;
    try {
      const response = await api.get('/schedule/master-grid', {
        params: { school_id: schoolId },
        headers: { 'X-School-Context': schoolId },
      });
      setGrid(response.data);
      setError('');
    } catch (e) {
      const msg = e?.response?.data?.error?.message || e?.message || 'تعذّر تحميل الجدول';
      setError(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, schoolId]);

  useEffect(() => { loadGrid(); }, [loadGrid]);

  const handleAutoGenerate = useCallback(async () => {
    if (!schoolId) {
      toast.error('تعذّر تحديد المدرسة الحالية');
      return;
    }
    if (generating) return;

    setGenerating(true);
    const toastId = toast.loading('جارٍ تشغيل محرك التوليد التلقائي…', {
      description: 'قد تستغرق العملية بضع ثوانٍ بحسب حجم البيانات.',
    });

    try {
      const response = await api.post(
        `/smart-scheduling/generate/${schoolId}`,
        {},
        { headers: { 'X-School-Context': schoolId } },
      );
      const data = response.data || {};
      const scheduled = data.scheduled_sessions ?? 0;
      const total = data.total_sessions ?? 0;
      const conflicts = data.conflicts_count ?? 0;
      const unscheduled = data.unscheduled_count ?? 0;
      const pct = Math.round(data.completion_percentage ?? 0);
      const summary =
        `تم جدولة ${scheduled} من ${total} حصة (${pct}%)` +
        (conflicts ? ` • ${conflicts} تعارض` : '') +
        (unscheduled ? ` • ${unscheduled} حصة لم تُجدول` : '');

      if (data.success) {
        toast.success(data.message_ar || 'تم توليد الجدول بنجاح', {
          id: toastId,
          description: summary,
        });
      } else {
        toast.warning(data.message_ar || 'اكتمل التوليد مع ملاحظات', {
          id: toastId,
          description: summary,
        });
      }

      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;

      // الحالة الخاصة: المحرك يرفض التشغيل بسبب بيانات ناقصة → نعرض حواراً
      // مفصَّلاً بالأسباب بدلاً من رسالة عامة، حتى يستطيع المدير معالجتها فوراً.
      if (status === 422 && detail?.code === 'GENERATION_BLOCKED' && detail?.report) {
        toast.dismiss(toastId);
        setBlockedReport(detail.report);
        setBlockedOpen(true);
        return;
      }

      let msg = 'فشل توليد الجدول، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (detail?.code === 'GENERATION_BLOCKED') {
        // Fallback: server returned the code but no report payload.
        msg = 'تعذّر التوليد: البيانات غير جاهزة بعد لتشغيل المحرك';
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = 'لا تملك صلاحية تشغيل التوليد التلقائي';
      } else if (status === 404) {
        msg = 'لم يتم العثور على بيانات المدرسة المطلوبة';
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = 'تعذّر الاتصال بالخادم، تحقق من الشبكة وحاول مجدداً';
      }
      toast.error(msg, { id: toastId });
    } finally {
      setGenerating(false);
    }
  }, [api, schoolId, generating, loadGrid]);

  const handleLogAbsence = useCallback(() => {
    setAbsenceTeacherId('');
    setAbsenceNotes('');
    setAbsenceOpen(true);
  }, []);

  const handleSubmitAbsence = useCallback(async () => {
    if (!absenceTeacherId) {
      toast.error('يرجى اختيار معلم');
      return;
    }
    if (!schoolId) {
      toast.error('تعذّر تحديد المدرسة الحالية');
      return;
    }

    const today = new Date().toISOString().split('T')[0];
    setSavingAbsence(true);
    try {
      await api.post(
        '/teacher-attendance/bulk',
        {
          records: [
            {
              teacher_id: absenceTeacherId,
              date: today,
              status: 'absent',
              check_in_time: null,
              notes: absenceNotes || '',
            },
          ],
        },
        { headers: { 'X-School-Context': schoolId } },
      );
      toast.success('تم تسجيل الغياب');
      setAbsenceOpen(false);
      setAbsenceTeacherId('');
      setAbsenceNotes('');
      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = 'فشل تسجيل الغياب، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = 'لا تملك صلاحية تسجيل الغياب';
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = 'تعذّر الاتصال بالخادم، تحقق من الشبكة وحاول مجدداً';
      }
      toast.error(msg);
    } finally {
      setSavingAbsence(false);
    }
  }, [api, schoolId, absenceTeacherId, absenceNotes, loadGrid]);

  const handleRequestUndoAbsence = useCallback((teacher) => {
    if (!teacher?.id) return;
    setUndoTeacher({ id: teacher.id, full_name: teacher.full_name || '' });
  }, []);

  const handleConfirmUndoAbsence = useCallback(async () => {
    if (!undoTeacher?.id) return;
    if (!schoolId) {
      toast.error('تعذّر تحديد المدرسة الحالية');
      return;
    }

    const today = new Date().toISOString().split('T')[0];
    setUndoingAbsence(true);
    try {
      await api.post(
        '/teacher-attendance/bulk',
        {
          records: [
            {
              teacher_id: undoTeacher.id,
              date: today,
              status: 'present',
              check_in_time: null,
              notes: '',
            },
          ],
        },
        { headers: { 'X-School-Context': schoolId } },
      );
      toast.success('تم إلغاء الغياب');
      setUndoTeacher(null);
      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = 'فشل إلغاء الغياب، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = 'لا تملك صلاحية تعديل سجل الحضور';
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = 'تعذّر الاتصال بالخادم، تحقق من الشبكة وحاول مجدداً';
      }
      toast.error(msg);
    } finally {
      setUndoingAbsence(false);
    }
  }, [api, schoolId, undoTeacher, loadGrid]);

  const handleVacantClick = useCallback((cellData) => {
    if (!cellData?.session?.session_id) {
      toast.error('لا يمكن فتح المرشحين — الخانة لا ترتبط بحصة معروفة');
      return;
    }
    const today = grid?.today || cellData.day_of_week;
    const todayDate = new Date().toISOString().slice(0, 10);
    setDrawerSlot({
      original_session_id: cellData.session.session_id,
      day_of_week: cellData.day_of_week,
      period_number: cellData.period_number,
      class_id: cellData.session.class_id,
      class_name: cellData.session.class_name,
      subject_id: cellData.session.subject_id,
      subject_name: cellData.session.subject_name,
      absent_teacher_name: cellData.teacher_name,
      absence_date: cellData.day_of_week === today ? todayDate : todayDate,
      school_id: schoolId,
    });
    setDrawerOpen(true);
  }, [grid?.today, schoolId]);

  const handleUndoSubstitution = useCallback(async (substitutionId) => {
    try {
      await api.delete(`/substitutions/${substitutionId}`, {
        params: { school_id: schoolId },
        headers: { 'X-School-Context': schoolId },
      });
      await loadGrid();
      toast.success('تم التراجع عن الإسناد');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'فشل التراجع';
      toast.error(msg);
    }
  }, [api, schoolId, loadGrid]);

  const handleAssigned = useCallback((substitution, cand) => {
    // Optimistic refresh + undo toast
    loadGrid();
    const subId = substitution?.id;
    toast.success('تم إسناد الحصة وإرسال إشعار', {
      description: `البديل: ${cand?.teacher_name || '—'}`,
      duration: 10000,
      action: subId
        ? { label: 'تراجع', onClick: () => handleUndoSubstitution(subId) }
        : undefined,
    });
  }, [loadGrid, handleUndoSubstitution]);

  // ── Bulk substitution handlers ─────────────────────────────────────
  const handleOpenBulkPanel = useCallback((teacher) => {
    if (!teacher?.id) return;
    const todayDate = new Date().toISOString().slice(0, 10);
    setBulkTarget({
      absent_teacher_id: teacher.id,
      absent_teacher_name: teacher.full_name,
      absence_date: todayDate,
      school_id: schoolId,
    });
    setBulkOpen(true);
  }, [schoolId]);

  const handleUndoBulkBatch = useCallback(async (batchId) => {
    if (!batchId) return;
    try {
      await api.delete(`/substitutions/batch/${batchId}`, {
        params: { school_id: schoolId },
        headers: { 'X-School-Context': schoolId },
      });
      await loadGrid();
      toast.success('تم التراجع عن الدفعة بالكامل');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'فشل التراجع عن الدفعة';
      toast.error(msg);
    }
  }, [api, schoolId, loadGrid]);

  const handleAssignedBatch = useCallback((batchResult) => {
    loadGrid();
    const succeeded = batchResult?.succeeded || 0;
    const failed = batchResult?.failed || 0;
    const batchId = batchResult?.batch_id;
    if (succeeded === 0) return;

    const description = failed > 0
      ? `نجح ${succeeded} وفشل ${failed} — تم إرسال إشعار مجمَّع لكل بديل`
      : `تم إرسال إشعار مجمَّع لكل بديل — ${succeeded} حصة`;

    toast.success(`تم إسناد ${succeeded} حصة دفعة واحدة`, {
      description,
      duration: 12000,
      action: batchId
        ? { label: 'تراجع عن الدفعة', onClick: () => handleUndoBulkBatch(batchId) }
        : undefined,
    });
  }, [loadGrid, handleUndoBulkBatch]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadGrid();
  }, [loadGrid]);

  // ── Derived grid view model ───────────────────────────────────────────
  const teacherRows = grid?.teachers || [];
  const cellsByTeacher = grid?.cells || {};
  const days = grid?.days || DAYS.map(d => d.key);
  const periods = grid?.periods || PERIODS;
  const kpis = grid?.kpis || { fairness_pct: 0, assigned_waiting: 0, absent_teachers_today: 0, vacant_sessions_today: 0 };
  const alertText = grid?.alert;

  const dayLabelMap = useMemo(() => Object.fromEntries(DAYS.map(d => [d.key, d.ar])), []);

  return (
    <Sidebar>
      <div
        dir="rtl"
        className="flex flex-col h-[calc(100dvh-3.5rem)] lg:h-[100dvh] p-4 md:p-6 gap-5 bg-slate-50 text-slate-900 overflow-hidden"
      >
        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 shrink-0">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#1C3D74] flex items-center gap-2">
              <Sparkles className="h-7 w-7 text-violet-600" />
              إدارة الجداول الذكية
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              مصفوفة موحَّدة لكل المعلمين × أيام الأسبوع × الحصص — مع متابعة لحظية للحصص الشاغرة.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => navigate('/school/standby')}
              variant="outline"
              className="border-amber-300 text-amber-800 hover:bg-amber-50"
              title="فتح جدول الانتظار للتعديل اليدوي"
            >
              <ListChecks className="h-4 w-4 ml-2" />
              جدول الانتظار
            </Button>
            <Button
              onClick={handleAutoGenerate}
              disabled={generating}
              className="bg-violet-600 hover:bg-violet-700 text-white shadow-md"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 ml-2 animate-spin" />
              ) : (
                <Wand2 className="h-4 w-4 ml-2" />
              )}
              {generating ? 'جارٍ التوليد…' : 'إنشاء الجدول تلقائياً'}
            </Button>
            <Button
              onClick={handleLogAbsence}
              variant="outline"
              className="border-slate-300 text-slate-700 hover:bg-slate-100"
            >
              <UserX className="h-4 w-4 ml-2" />
              تسجيل غياب
            </Button>
            <Button
              onClick={handleRefresh}
              variant="ghost"
              size="icon"
              disabled={refreshing}
              title="تحديث"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* ── KPI cards ────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">
          <KpiCard
            icon={Scale}
            label="عدالة التوزيع"
            value={kpis.fairness_pct}
            suffix="%"
            accent={{
              bg: 'bg-emerald-50', ring: 'border-emerald-200',
              iconBg: 'bg-emerald-100', iconText: 'text-emerald-700',
              valueText: 'text-emerald-800',
            }}
          />
          <KpiCard
            icon={Hourglass}
            label="انتظار مُسند"
            value={kpis.assigned_waiting}
            accent={{
              bg: 'bg-blue-50', ring: 'border-blue-200',
              iconBg: 'bg-blue-100', iconText: 'text-[#1C3D74]',
              valueText: 'text-[#1C3D74]',
            }}
          />
          <KpiCard
            icon={UserMinus}
            label="معلم غائب"
            value={kpis.absent_teachers_today}
            accent={{
              bg: 'bg-amber-50', ring: 'border-amber-200',
              iconBg: 'bg-amber-100', iconText: 'text-amber-700',
              valueText: 'text-amber-800',
            }}
          />
          <KpiCard
            icon={AlertOctagon}
            label="حصة شاغرة"
            value={kpis.vacant_sessions_today}
            accent={{
              bg: 'bg-red-50', ring: 'border-red-200',
              iconBg: 'bg-red-100', iconText: 'text-red-700',
              valueText: 'text-red-800',
            }}
          />
        </div>

        {/* ── Smart alert banner ───────────────────────────────────── */}
        {alertText && (
          <div className="flex items-center gap-3 p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 shrink-0">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p className="text-sm font-medium">{alertText}</p>
          </div>
        )}

        {/* ── Substitution drawer (single slot) ─────────────────────── */}
        <CandidatesSidePanel
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          slot={drawerSlot}
          api={api}
          onAssigned={handleAssigned}
        />

        {/* ── Bulk substitution drawer (full absent teacher) ─────────── */}
        <BulkSubstitutionPanel
          open={bulkOpen}
          onOpenChange={setBulkOpen}
          target={bulkTarget}
          api={api}
          onAssignedBatch={handleAssignedBatch}
        />

        {/* ── Master matrix grid ───────────────────────────────────── */}
        <Card className="border border-slate-200 shadow-sm overflow-hidden flex-1 min-h-0 flex flex-col">
          <CardContent className="p-0 flex-1 min-h-0 flex flex-col">
            {loading ? (
              <div className="flex flex-1 items-center justify-center py-20 text-slate-500">
                <Loader2 className="h-6 w-6 animate-spin ml-2" />
                جارٍ تحميل المصفوفة…
              </div>
            ) : error ? (
              <div className="p-6 text-center text-red-600">{error}</div>
            ) : teacherRows.length === 0 ? (
              <div className="p-6 text-center text-slate-500">
                لا يوجد معلمون مسجَّلون في هذه المدرسة بعد.
              </div>
            ) : (
              <MasterMatrix
                teachers={teacherRows}
                cells={cellsByTeacher}
                days={days}
                periods={periods}
                dayLabelMap={dayLabelMap}
                onVacantClick={handleVacantClick}
                onUndoAbsence={handleRequestUndoAbsence}
                onBulkCoverClick={handleOpenBulkPanel}
                today={grid?.today}
              />
            )}
          </CardContent>
        </Card>

        {/* ── Absence dialog ─────────────────────────────────────── */}
        <Dialog open={absenceOpen} onOpenChange={setAbsenceOpen}>
          <DialogContent dir="rtl" className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[#1C3D74]">
                <UserX className="h-5 w-5 text-red-600" />
                تسجيل غياب معلم
              </DialogTitle>
              <DialogDescription>
                سيُسجَّل المعلم المختار كغائب اليوم وتُحدَّث الخلايا والمؤشرات فوراً.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="absence-teacher">المعلم</Label>
                <Select value={absenceTeacherId} onValueChange={setAbsenceTeacherId}>
                  <SelectTrigger id="absence-teacher" className="w-full">
                    <SelectValue placeholder="اختر معلماً…" />
                  </SelectTrigger>
                  <SelectContent>
                    {teacherRows.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-slate-500">
                        لا يوجد معلمون متاحون
                      </div>
                    ) : (
                      teacherRows.map((t) => (
                        <SelectItem key={t.id} value={t.id} disabled={t.is_absent_today}>
                          {t.full_name}
                          {t.is_absent_today ? ' (غائب اليوم)' : ''}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="absence-notes">ملاحظات (اختياري)</Label>
                <Textarea
                  id="absence-notes"
                  value={absenceNotes}
                  onChange={(e) => setAbsenceNotes(e.target.value)}
                  placeholder="سبب الغياب أو أي ملاحظات…"
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="outline"
                onClick={() => setAbsenceOpen(false)}
                disabled={savingAbsence}
              >
                إلغاء
              </Button>
              <Button
                onClick={handleSubmitAbsence}
                disabled={savingAbsence || !absenceTeacherId}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {savingAbsence ? (
                  <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                ) : (
                  <UserX className="h-4 w-4 ml-2" />
                )}
                {savingAbsence ? 'جارٍ الحفظ…' : 'تسجيل الغياب'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── Generation-blocked dialog (HTTP 422 / GENERATION_BLOCKED) ──── */}
        <BlockedGenerationDialog
          open={blockedOpen}
          onOpenChange={setBlockedOpen}
          report={blockedReport}
          onNavigate={(path) => {
            setBlockedOpen(false);
            navigate(path);
          }}
        />

        {/* ── Undo absence confirmation dialog ─────────────────────── */}
        <Dialog
          open={!!undoTeacher}
          onOpenChange={(open) => {
            if (!open && !undoingAbsence) setUndoTeacher(null);
          }}
        >
          <DialogContent dir="rtl" className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[#1C3D74]">
                <Undo2 className="h-5 w-5 text-emerald-600" />
                إلغاء الغياب
              </DialogTitle>
              <DialogDescription>
                سيُعاد تسجيل المعلم كحاضر اليوم وتُحدَّث الخلايا والمؤشرات فوراً.
              </DialogDescription>
            </DialogHeader>

            <div className="py-2 text-sm text-slate-700">
              هل تريد فعلاً إلغاء غياب{' '}
              <span className="font-semibold text-slate-900">
                {undoTeacher?.full_name || '—'}
              </span>{' '}
              لهذا اليوم؟
            </div>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="outline"
                onClick={() => setUndoTeacher(null)}
                disabled={undoingAbsence}
              >
                تراجع
              </Button>
              <Button
                onClick={handleConfirmUndoAbsence}
                disabled={undoingAbsence}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {undoingAbsence ? (
                  <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                ) : (
                  <Undo2 className="h-4 w-4 ml-2" />
                )}
                {undoingAbsence ? 'جارٍ الإلغاء…' : 'تأكيد إلغاء الغياب'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}

// ─── Generation-blocked dialog ─────────────────────────────────────────────
// عند رفض المحرك للتوليد (HTTP 422 / GENERATION_BLOCKED) نعرض هنا قائمة
// المشاكل بالعربية مع زر يفتح الصفحة الأنسب لمعالجة كل مشكلة.
function BlockedGenerationDialog({ open, onOpenChange, report, onNavigate }) {
  const issues = Array.isArray(report?.issues) ? report.issues : [];
  const blockers  = issues.filter((i) => i.severity === 'blocker');
  const advisories = issues.filter((i) => i.severity === 'advisory');

  // اختر الإجراء الأساسي بناءً على أول blocker (أكثر إلحاحاً) أو الافتراضي.
  const primaryStep = (blockers[0] && ISSUE_NEXT_STEP[blockers[0].code]) || DEFAULT_NEXT_STEP;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-700">
            <ShieldAlert className="h-5 w-5" />
            تعذّر تشغيل التوليد التلقائي
          </DialogTitle>
          <DialogDescription>
            رفض المحرك بدء التوليد لأن البيانات الأساسية غير مكتملة. عالج
            النقاط التالية ثم أعد المحاولة:
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2 max-h-[55vh] overflow-y-auto pr-1">
          {issues.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">
              لا توجد تفاصيل إضافية متاحة من المحرك.
            </p>
          ) : (
            <>
              {blockers.length > 0 && (
                <ul className="space-y-2">
                  {blockers.map((iss, idx) => {
                    const step = ISSUE_NEXT_STEP[iss.code] || DEFAULT_NEXT_STEP;
                    return (
                      <li
                        key={`b-${iss.code}-${idx}`}
                        className="rounded-lg border border-red-200 bg-red-50 p-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge className="bg-red-600 hover:bg-red-600 text-white text-[10px]">
                                مانع
                              </Badge>
                              <span className="text-[11px] font-mono text-slate-500">
                                {iss.code}
                              </span>
                            </div>
                            <p className="text-sm text-red-900 leading-relaxed">
                              {iss.message_ar || iss.message_en}
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="border-red-300 text-red-700 hover:bg-red-100 shrink-0"
                            onClick={() => onNavigate(step.path)}
                          >
                            <Settings className="h-3.5 w-3.5 ml-1" />
                            <span className="text-xs">{step.label}</span>
                          </Button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              {advisories.length > 0 && (
                <div className="pt-2">
                  <p className="text-xs font-semibold text-slate-600 mb-2">
                    ملاحظات إضافية (لا تمنع التوليد):
                  </p>
                  <ul className="space-y-2">
                    {advisories.map((iss, idx) => (
                      <li
                        key={`a-${iss.code}-${idx}`}
                        className="rounded-lg border border-amber-200 bg-amber-50 p-3"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="border-amber-400 text-amber-800 bg-amber-100 text-[10px]">
                            إرشاد
                          </Badge>
                          <span className="text-[11px] font-mono text-slate-500">
                            {iss.code}
                          </span>
                        </div>
                        <p className="text-sm text-amber-900 leading-relaxed">
                          {iss.message_ar || iss.message_en}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            إغلاق
          </Button>
          <Button
            onClick={() => onNavigate(primaryStep.path)}
            className="bg-[#1C3D74] hover:bg-[#162f5a] text-white"
          >
            <ArrowLeft className="h-4 w-4 ml-2" />
            {primaryStep.label}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Master Matrix Grid Component ─────────────────────────────────────────
// ملاحظة: نستخدم CSS Grid مع `position: sticky` على عمود المعلم وصف الرأس
// للحصول على تثبيت بالاتجاهين في RTL مع تمرير سلس.
function MasterMatrix({ teachers, cells, days, periods, dayLabelMap, onVacantClick, onUndoAbsence, onBulkCoverClick, today }) {
  // ترتيب الأعمدة: لكل يوم تُضاف أعمدة الحصص (1..7) متتالية.
  const totalDataCols = days.length * periods.length;
  // عرض كل عمود حصة + عرض عمود المعلم الجانبي.
  // عرض أكبر للخلايا حتى يتنفّس النص العربي ويُقرأ بسهولة؛ التمرير الأفقي
  // الطبيعي مفضَّل على نص مضغوط غير مقروء.
  const TEACHER_COL_WIDTH = 280;
  const PERIOD_COL_WIDTH = 112;
  const DAY_HEADER_HEIGHT = 44; // ارتفاع صف الرأس الأول (أيام الأسبوع)
  const DAY_COLS_TOTAL_PX = totalDataCols * PERIOD_COL_WIDTH;

  // gridTemplateColumns: عمود المعلم + (يوم × حصص).
  const gridTemplate = `${TEACHER_COL_WIDTH}px repeat(${totalDataCols}, ${PERIOD_COL_WIDTH}px)`;

  return (
    // h-full + overflow-auto => تمرير عمودي وأفقي طبيعي داخل بطاقة المصفوفة،
    // مع شريط تمرير واحد يصل إلى أسفل الشاشة بدلاً من صندوق صغير داخلي.
    <div className="h-full w-full overflow-auto relative">
      <div
        className="grid text-[12px]"
        style={{ gridTemplateColumns: gridTemplate, minWidth: TEACHER_COL_WIDTH + DAY_COLS_TOTAL_PX }}
      >
        {/* ── Sticky header row 1: day spans ─────────────────────── */}
        {/* الزاوية العلوية الجانبية (تقاطع رأس + عمود المعلم) — أعلى z-index */}
        <div
          className="sticky top-0 bg-[#1C3D74] text-white font-bold px-3 flex items-center border-l border-white/20"
          style={{ insetInlineStart: 0, zIndex: 50, height: DAY_HEADER_HEIGHT }}
        >
          المعلم
        </div>
        {days.map((dayKey) => (
          <div
            key={`day-h-${dayKey}`}
            className="sticky top-0 z-30 bg-[#1C3D74] text-white text-center font-bold flex items-center justify-center border-l border-white/20"
            style={{ gridColumn: `span ${periods.length}`, height: DAY_HEADER_HEIGHT }}
          >
            {dayLabelMap[dayKey] || dayKey}
            {dayKey === today && (
              <span className="mr-2 inline-block px-1.5 py-0.5 text-[10px] rounded bg-white/20">
                اليوم
              </span>
            )}
          </div>
        ))}

        {/* ── Sticky header row 2: period numbers ────────────────── */}
        <div
          className="sticky bg-[#243f6a] text-white text-xs px-3 py-1.5 text-right border-l border-white/20"
          style={{ top: DAY_HEADER_HEIGHT, insetInlineStart: 0, zIndex: 50 }}
        >
          {teachers.length} معلم • {periods.length} حصص × {days.length} أيام
        </div>
        {days.map((dayKey) => (
          periods.map((p) => (
            <div
              key={`ph-${dayKey}-${p}`}
              className="sticky z-30 bg-[#243f6a] text-white text-center text-[11px] py-1.5 border-l border-white/10"
              style={{ top: DAY_HEADER_HEIGHT }}
            >
              {p}
            </div>
          ))
        ))}

        {/* ── Body rows: one per teacher ─────────────────────────── */}
        {teachers.map((teacher, idx) => {
          const teacherCells = cells[teacher.id] || {};
          const rowAbsentTint = teacher.is_absent_today;
          const rowBg = rowAbsentTint
            ? 'bg-red-50'
            : (idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/60');
          // Count vacant slots for the absent teacher today (drives the
          // bulk-cover button visibility/label).
          const todayCells = (today && teacherCells[today]) || {};
          const vacantTodayCount = teacher.is_absent_today
            ? Object.values(todayCells).filter((c) => c && c.is_vacant).length
            : 0;
          return (
            <React.Fragment key={teacher.id}>
              {/* Sticky teacher column */}
              <div
                className={`sticky z-20 px-3 py-2 border-t border-l border-slate-200 ${rowBg}`}
                style={{ insetInlineStart: 0 }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 text-sm truncate flex items-center gap-1">
                      {teacher.full_name}
                      {teacher.is_absent_today && (
                        <AbsencePill
                          recorderName={teacher.absence_recorded_by_name}
                          recordedAt={teacher.absence_recorded_at}
                        />
                      )}
                    </p>
                    <p className="text-[11px] text-slate-500 truncate">
                      {teacher.subject || '—'}
                      {teacher.rank ? ` • ${RANK_AR[teacher.rank] || teacher.rank}` : ''}
                    </p>
                  </div>
                  <div className="text-[11px] font-semibold text-slate-700 whitespace-nowrap">
                    {teacher.assigned_periods}
                    <span className="text-slate-400">/</span>
                    {teacher.weekly_quota || '—'}
                  </div>
                </div>
                {teacher.is_absent_today && (
                  <div className="mt-1.5 flex flex-col gap-1.5">
                    <button
                      type="button"
                      onClick={() => onUndoAbsence?.(teacher)}
                      title="إعادة المعلم إلى حالة الحضور لهذا اليوم"
                      aria-label={`إلغاء غياب ${teacher.full_name}`}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold rounded-md border border-emerald-400 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 hover:border-emerald-500 hover:text-emerald-800 transition-colors px-2 py-0.5 cursor-pointer self-start"
                    >
                      <Undo2 className="h-3 w-3" aria-hidden="true" />
                      <span>إلغاء الغياب</span>
                    </button>
                    {vacantTodayCount > 0 && onBulkCoverClick && (
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => onBulkCoverClick(teacher)}
                        className="w-full h-7 text-[11px] font-bold bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] hover:from-[#152d57] text-white shadow-sm"
                        title="فتح لوحة تغطية كل الحصص الشاغرة لهذا المعلم اليوم"
                      >
                        <Layers className="h-3 w-3 ml-1" />
                        تغطية كل حصصه ({vacantTodayCount})
                      </Button>
                    )}
                  </div>
                )}
              </div>

              {/* Cells: per day, per period */}
              {days.map((dayKey) => (
                periods.map((p) => {
                  const cell = teacherCells[dayKey]?.[String(p)] || null;
                  const cellData = {
                    teacher_id: teacher.id,
                    teacher_name: teacher.full_name,
                    day_of_week: dayKey,
                    period_number: p,
                    is_today: dayKey === today,
                    teacher_absent: teacher.is_absent_today,
                    session: cell,
                  };
                  return (
                    <div
                      key={`${teacher.id}-${dayKey}-${p}`}
                      className={`p-1 border-t border-l border-slate-200 ${rowBg}`}
                    >
                      {cell ? (
                        <FilledCell
                          cell={cell}
                          onClick={cell.is_vacant ? () => onVacantClick(cellData) : undefined}
                        />
                      ) : (
                        <EmptyCell teacherAbsent={rowAbsentTint} />
                      )}
                    </div>
                  );
                })
              ))}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
