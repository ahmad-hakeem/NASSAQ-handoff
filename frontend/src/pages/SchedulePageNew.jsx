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
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Wand2, UserX, Sparkles, Loader2, RefreshCw,
  Scale, Hourglass, UserMinus, AlertOctagon, AlertTriangle, Repeat,
} from 'lucide-react';
import CandidatesSidePanel from '../components/schedule/CandidatesSidePanel';

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
  const schoolId = user?.tenant_id;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [grid, setGrid] = useState(null);

  // Substitution drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSlot, setDrawerSlot] = useState(null);

  // إنشاء الجدول تلقائياً
  const [generating, setGenerating] = useState(false);

  // تسجيل الغياب
  const [absenceOpen, setAbsenceOpen] = useState(false);
  const [absenceTeacherId, setAbsenceTeacherId] = useState('');
  const [absenceNotes, setAbsenceNotes] = useState('');
  const [savingAbsence, setSavingAbsence] = useState(false);

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
      let msg = 'فشل توليد الجدول، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (detail?.code === 'GENERATION_BLOCKED') {
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
      <div dir="rtl" className="p-4 md:p-6 space-y-5 bg-slate-50 min-h-full text-slate-900">
        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
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
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
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
          <div className="flex items-center gap-3 p-3 rounded-lg border border-red-300 bg-red-50 text-red-800">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p className="text-sm font-medium">{alertText}</p>
          </div>
        )}

        {/* ── Substitution drawer ───────────────────────────────────── */}
        <CandidatesSidePanel
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          slot={drawerSlot}
          api={api}
          onAssigned={handleAssigned}
        />

        {/* ── Master matrix grid ───────────────────────────────────── */}
        <Card className="border border-slate-200 shadow-sm overflow-hidden">
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-20 text-slate-500">
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
      </div>
    </Sidebar>
  );
}

// ─── Master Matrix Grid Component ─────────────────────────────────────────
// ملاحظة: نستخدم CSS Grid مع `position: sticky` على عمود المعلم وصف الرأس
// للحصول على تثبيت بالاتجاهين في RTL مع تمرير سلس.
function MasterMatrix({ teachers, cells, days, periods, dayLabelMap, onVacantClick, today }) {
  // ترتيب الأعمدة: لكل يوم تُضاف أعمدة الحصص (1..7) متتالية.
  const totalDataCols = days.length * periods.length;
  // عرض كل عمود حصة + عرض عمود المعلم الجانبي.
  const TEACHER_COL_WIDTH = 240;
  const PERIOD_COL_WIDTH = 78;
  const DAY_COLS_TOTAL_PX = totalDataCols * PERIOD_COL_WIDTH;

  // gridTemplateColumns: عمود المعلم + (يوم × حصص).
  const gridTemplate = `${TEACHER_COL_WIDTH}px repeat(${totalDataCols}, ${PERIOD_COL_WIDTH}px)`;

  return (
    <div className="overflow-auto max-h-[calc(100vh-360px)] relative">
      <div
        className="grid text-[12px]"
        style={{ gridTemplateColumns: gridTemplate, minWidth: TEACHER_COL_WIDTH + DAY_COLS_TOTAL_PX }}
      >
        {/* ── Sticky header row 1: day spans ─────────────────────── */}
        <div
          className="sticky top-0 z-30 bg-[#1C3D74] text-white font-bold px-3 py-2 border-l border-white/20"
          style={{ position: 'sticky', insetInlineStart: 0, zIndex: 40 }}
        >
          المعلم
        </div>
        {days.map((dayKey) => (
          <div
            key={`day-h-${dayKey}`}
            className="sticky top-0 z-20 bg-[#1C3D74] text-white text-center font-bold py-2 border-l border-white/20"
            style={{ gridColumn: `span ${periods.length}` }}
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
          className="sticky z-30 bg-[#243f6a] text-white text-xs px-3 py-1.5 text-right"
          style={{ top: 38, position: 'sticky', insetInlineStart: 0, zIndex: 40 }}
        >
          {teachers.length} معلم • {periods.length} حصص × {days.length} أيام
        </div>
        {days.map((dayKey) => (
          periods.map((p) => (
            <div
              key={`ph-${dayKey}-${p}`}
              className="sticky z-20 bg-[#243f6a] text-white text-center text-[11px] py-1.5 border-l border-white/10"
              style={{ top: 38 }}
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
          return (
            <React.Fragment key={teacher.id}>
              {/* Sticky teacher column */}
              <div
                className={`sticky z-10 px-3 py-2 border-t border-l border-slate-200 ${rowBg}`}
                style={{ insetInlineStart: 0 }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 text-sm truncate flex items-center gap-1">
                      {teacher.full_name}
                      {teacher.is_absent_today && (
                        <Badge variant="outline" className="text-[10px] border-red-400 text-red-700 bg-red-100">
                          غائب
                        </Badge>
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
