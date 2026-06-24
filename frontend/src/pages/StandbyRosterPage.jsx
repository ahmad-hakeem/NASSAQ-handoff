/**
 * جدول حصص الانتظار — Standby Roster
 * نَسَّق | NASSAQ — Task #102 / #114 / #157
 *
 * التصميم الافتراضي الآن day-centric يطابق نموذج وزارة التعليم السعودية:
 *   • صفّ مدمج لكل يوم.
 *   • صفوف فرعية لعدد المعلمين المنتظرين في ذلك اليوم.
 *   • أعمدة الحصص (الأولى…السابعة).
 * يبقى العرض القديم teacher-centric متاحاً عبر زر تبديل لمن يفضّله.
 *
 * Endpoints:
 *   GET /api/standby/roster?shape=day_centric
 *   PUT /api/standby/roster/cell
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';

import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Hourglass, Loader2, RefreshCw, Sparkles,
  CheckCircle2, MinusCircle, Lock, CalendarOff, LayoutGrid, Rows3,
  Users, Bot, Hand, ListChecks,
} from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import ScheduleTabNav from '../components/schedule/ScheduleTabNav';
import StandbyDayCentricTable from '../components/schedule/StandbyDayCentricTable';
import { getApiErrorMessage } from '../utils/apiError';
import { useCanViewInternalIds } from '../hooks/useCanViewInternalIds';
import { maskInternalId } from '../utils/internalId';

const DAYS = [
  { key: 'sunday',    ar: 'الأحد' },
  { key: 'monday',    ar: 'الإثنين' },
  { key: 'tuesday',   ar: 'الثلاثاء' },
  { key: 'wednesday', ar: 'الأربعاء' },
  { key: 'thursday',  ar: 'الخميس' },
];

// ─── Cell renderer (legacy teacher-centric matrix) ──────────────────────
function StandbyCell({ cell, onCycle, busy }) {
  if (!cell) return <div className="w-full h-full" />;

  const status = cell.status;
  const ov = cell.override;
  const isAuto = !!cell.auto;

  if (status === 'busy') {
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-slate-50 text-slate-600"
        title={`حصة مجدولة: ${cell.class_name || ''} ${cell.subject_name ? '— ' + cell.subject_name : ''}`}
      >
        <Lock className="h-3 w-3 mb-0.5 opacity-60" />
        <span className="font-semibold truncate max-w-full">{cell.class_name || 'مشغول'}</span>
      </div>
    );
  }

  if (status === 'blocked') {
    return (
      <div
        className="w-full h-full flex items-center justify-center text-[10px] bg-slate-50/60 text-slate-400"
        title="يوم إجازة لهذا المعلم"
      >
        <CalendarOff className="h-3.5 w-3.5" />
      </div>
    );
  }

  const isStandby = status === 'standby';
  const overrideLabel = ov === 'add' ? 'مُجبر' : ov === 'remove' ? 'مُلغى' : null;

  let bgCls, textCls, Icon;
  if (isStandby && ov === 'add') {
    bgCls = 'bg-violet-50 hover:bg-violet-100';
    textCls = 'text-violet-700';
    Icon = Sparkles;
  } else if (isStandby) {
    bgCls = 'bg-emerald-50 hover:bg-emerald-100';
    textCls = 'text-emerald-700';
    Icon = CheckCircle2;
  } else if (ov === 'remove') {
    bgCls = 'bg-rose-50 hover:bg-rose-100';
    textCls = 'text-rose-700';
    Icon = MinusCircle;
  } else {
    bgCls = 'bg-transparent hover:bg-slate-50';
    textCls = 'text-slate-300';
    Icon = null;
  }

  const tooltip = (() => {
    if (isStandby && ov === 'add') return 'مُسند يدوياً • اضغط للإلغاء';
    if (isStandby && isAuto) return 'انتظار تلقائي • اضغط لاستثنائه';
    if (isStandby) return 'انتظار • اضغط لإزالته';
    if (ov === 'remove') return 'تم استثناؤه يدوياً • اضغط لإعادة المحرك';
    return 'فارغ • اضغط لإضافة المعلم لخانة الانتظار';
  })();

  return (
    <button
      type="button"
      onClick={onCycle}
      disabled={busy}
      title={tooltip}
      className={`w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                  ${bgCls} ${textCls} transition-colors disabled:opacity-50`}
    >
      {Icon ? <Icon className="h-3.5 w-3.5 mb-0.5" /> : <span className="opacity-30">—</span>}
      {overrideLabel && (
        <span className="text-[9px] font-bold opacity-80">{overrideLabel}</span>
      )}
    </button>
  );
}

const KPI_ACCENTS = {
  blue:    { ring: 'ring-blue-100',    bar: 'bg-blue-500',    iconBg: 'bg-blue-50',    iconFg: 'text-blue-600' },
  emerald: { ring: 'ring-emerald-100', bar: 'bg-emerald-500', iconBg: 'bg-emerald-50', iconFg: 'text-emerald-600' },
  violet:  { ring: 'ring-violet-100',  bar: 'bg-violet-500',  iconBg: 'bg-violet-50',  iconFg: 'text-violet-600' },
  amber:   { ring: 'ring-amber-100',   bar: 'bg-amber-500',   iconBg: 'bg-amber-50',   iconFg: 'text-amber-600' },
};

function KpiCard({ icon: Icon, label, value, accent = 'blue', emphasis = false }) {
  const a = KPI_ACCENTS[accent] || KPI_ACCENTS.blue;
  return (
    <Card
      dir="rtl"
      className={`relative overflow-hidden bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow h-full ring-1 ${a.ring}`}
    >
      <span className={`absolute top-0 right-0 h-full w-1 ${a.bar}`} aria-hidden="true" />
      <CardContent className="p-3.5 pr-4 flex items-center gap-3 h-full">
        <div className={`shrink-0 h-9 w-9 rounded-lg ${a.iconBg} flex items-center justify-center`}>
          <Icon className={`h-4.5 w-4.5 ${a.iconFg}`} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium text-slate-500 mb-0.5 truncate">{label}</p>
          <p className={`font-bold text-slate-900 leading-none tabular-nums ${emphasis ? 'text-2xl' : 'text-xl'}`}>
            {value}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function LegendChip({ color, label }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`inline-block w-3 h-3 rounded ${color}`} />
      <span className="text-[11px] text-slate-600">{label}</span>
    </div>
  );
}

// ─── Standby content ──────────────────────────────────────────────────
export function StandbyRosterContent() {
  const { user, api } = useAuth();
  const canViewInternalIds = useCanViewInternalIds();
  const { nassaqConfirm, nassaqError, nassaqSuccess, nassaqInfo } = useNassaqAlert();
  const schoolId = user?.tenant_id;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [busyCellKey, setBusyCellKey] = useState(null);
  const [viewMode, setViewMode] = useState('day'); // 'day' | 'matrix'
  const [picker, setPicker] = useState(null); // { day, period, slot_index }
  const [pickerSearch, setPickerSearch] = useState('');

  const loadRoster = useCallback(async () => {
    if (!schoolId) return;
    try {
      const response = await api.get('/standby/roster', {
        params: { school_id: schoolId, shape: 'day_centric' },
        headers: { 'X-School-Context': schoolId },
      });
      setData(response.data);
      setError('');
    } catch (e) {
      const msg = getApiErrorMessage(e) || e?.message || 'تعذّر تحميل جدول الانتظار';
      setError(typeof msg === 'string' ? msg : 'تعذّر تحميل جدول الانتظار');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, schoolId]);

  useEffect(() => { loadRoster(); }, [loadRoster]);

  const sendOverride = useCallback(async (teacherId, day, period, action, slotIndex = null) => {
    if (!schoolId) return;
    const cellKey = `${teacherId}:${day}:${period}`;
    setBusyCellKey(cellKey);
    try {
      const body = { teacher_id: teacherId, day, period, action };
      if (slotIndex != null) body.slot_index = slotIndex;
      await api.put(
        '/standby/roster/cell',
        body,
        {
          params: { school_id: schoolId },
          headers: { 'X-School-Context': schoolId },
        },
      );
      await loadRoster();
    } catch (e) {
      const detail = getApiErrorMessage(e);
      const msg = typeof detail === 'string' ? detail : 'تعذّر حفظ التعديل';
      nassaqError(msg);
    } finally {
      setBusyCellKey(null);
    }
  }, [api, schoolId, loadRoster, nassaqError]);

  // Legacy teacher-centric matrix: cycle a single cell.
  const cycleCell = useCallback(async (teacherId, day, period, current) => {
    const { status, override, auto } = current;
    let action;
    if (status === 'standby' && override === 'add') action = 'reset';
    else if (status === 'standby' && auto) action = 'remove';
    else if (status === 'standby') action = 'remove';
    else if (status === 'free' && override === 'remove') action = 'reset';
    else action = 'add';
    await sendOverride(teacherId, day, period, action);
  }, [sendOverride]);

  // Day-centric: handle filled or empty cell click.
  const onDayCellClick = useCallback(({ cell, day, period, slot_index }) => {
    if (cell) {
      // Filled — confirm remove (or reset for manual-add overrides).
      const action = cell.source === 'manual' ? 'reset' : 'remove';
      const verb = action === 'reset' ? 'إلغاء الإسناد اليدوي' : 'استثناء المعلم';
      nassaqConfirm(
        `${verb} «${cell.teacher_name}» من خانة الانتظار؟`,
        () => sendOverride(cell.teacher_id, day, period, action, slot_index),
        { title: 'تأكيد التعديل', confirmText: 'تأكيد', cancelText: 'إلغاء' },
      );
    } else {
      // Empty — open the teacher picker.
      setPicker({ day, period, slot_index });
      setPickerSearch('');
    }
  }, [nassaqConfirm, sendOverride]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadRoster();
  }, [loadRoster]);

  // Real server-side regenerate: POST rebuilds the standby roster from
  // the current master timetable (preserving manual overrides) and
  // returns the fresh payload — no full-page reload.
  const regenerateRoster = useCallback(async () => {
    if (!schoolId) return;
    setRefreshing(true);
    const prevSignature = JSON.stringify(data?.day_centric?.days || data?.cells || null);
    try {
      const response = await api.post(
        '/standby/roster/regenerate',
        null,
        {
          params: { school_id: schoolId, shape: 'day_centric' },
          headers: { 'X-School-Context': schoolId },
        },
      );
      const fresh = response.data;
      setData(fresh);
      setError('');

      const warnings = Array.isArray(fresh?.day_centric?.warnings) ? fresh.day_centric.warnings : [];
      const overrides = fresh?.totals?.overrides || 0;
      const newSignature = JSON.stringify(fresh?.day_centric?.days || fresh?.cells || null);
      const unchanged = prevSignature && prevSignature === newSignature;

      if (warnings.length > 0) {
        nassaqInfo(
          `تمت إعادة التوليد. التعديلات اليدوية محفوظة (${overrides})، وظهرت ${warnings.length} تنبيهات تعارض أعلى الجدول.`,
          { title: 'إعادة توليد جدول الانتظار' },
        );
      } else if (unchanged) {
        nassaqInfo(
          'تمت إعادة التوليد ولم تتغيّر النتائج لعدم تغيّر المعطيات في الجدول الرئيسي.',
          { title: 'إعادة توليد جدول الانتظار' },
        );
      } else {
        nassaqSuccess(
          `تمت إعادة التوليد بنجاح. التعديلات اليدوية محفوظة (${overrides}).`,
          { title: 'إعادة توليد جدول الانتظار' },
        );
      }
    } catch (e) {
      const detail = getApiErrorMessage(e);
      const msg = typeof detail === 'string' ? detail : 'تعذّر إعادة توليد جدول الانتظار';
      nassaqError(msg);
    } finally {
      setRefreshing(false);
    }
  }, [api, schoolId, data, nassaqError, nassaqSuccess, nassaqInfo]);

  const teachers = data?.teachers || [];
  const cells = data?.cells || {};
  const periods = data?.periods || [1, 2, 3, 4, 5, 6, 7];
  const days = data?.days || DAYS.map(d => d.key);
  const totals = data?.totals || { teachers: 0, auto_slots: 0, final_slots: 0, overrides: 0 };
  const dayCentric = data?.day_centric;

  const dayLabelMap = useMemo(() => Object.fromEntries(DAYS.map(d => [d.key, d.ar])), []);

  // Eligible teachers for the picker: status === "free" at (day, period).
  const eligibleForPicker = useMemo(() => {
    if (!picker) return [];
    const { day, period } = picker;
    const standbyTeacherIds = new Set();
    if (dayCentric) {
      const dayPayload = dayCentric.days?.find(d => d.day === day);
      if (dayPayload) {
        for (const row of dayPayload.rows) {
          const c = row.cells?.[String(period)];
          if (c) standbyTeacherIds.add(c.teacher_id);
        }
      }
    }
    const search = pickerSearch.trim();
    return teachers.filter(t => {
      const tCell = cells[t.id]?.[day]?.[String(period)];
      if (!tCell || tCell.status !== 'free') return false;
      if (standbyTeacherIds.has(t.id)) return false;
      if (!search) return true;
      return (t.full_name || '').includes(search) || (t.subject || '').includes(search);
    });
  }, [picker, pickerSearch, teachers, cells, dayCentric]);

  return (
    <>
      {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 shrink-0">
          <div className="min-w-0">
            <h1 className="text-xl md:text-2xl font-bold text-[#1C3D74] flex items-center gap-2 leading-tight">
              <Hourglass className="h-5 w-5 md:h-6 md:w-6 text-amber-500 shrink-0" />
              جدول حصص الانتظار
              <span className="hidden md:inline text-[11px] font-medium text-slate-400">
                — كل خانة (يوم/حصة) تدعم عدّة معلمين بترتيب الأولوية.
              </span>
            </h1>
          </div>

          {/* Unified toolbar: view toggle + refresh + primary regenerate. */}
          <div
            dir="rtl"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white shadow-sm p-1.5"
          >
            <div className="inline-flex rounded-lg overflow-hidden bg-slate-50 ring-1 ring-slate-200">
              <button
                type="button"
                onClick={() => setViewMode('day')}
                className={`px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 transition-colors ${viewMode === 'day' ? 'bg-[#1C3D74] text-white shadow-sm' : 'text-slate-600 hover:bg-white'}`}
                title="عرض حسب اليوم (افتراضي)"
              >
                <Rows3 className="h-3.5 w-3.5" />
                حسب اليوم
              </button>
              <button
                type="button"
                onClick={() => setViewMode('matrix')}
                className={`px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 transition-colors ${viewMode === 'matrix' ? 'bg-[#1C3D74] text-white shadow-sm' : 'text-slate-600 hover:bg-white'}`}
                title="عرض المصفوفة الكامل (معلم × يوم × حصة)"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                مصفوفة المعلمين
              </button>
            </div>
            <span className="h-6 w-px bg-slate-200" />
            <Button
              onClick={handleRefresh}
              variant="ghost"
              size="icon"
              disabled={refreshing}
              title="تحديث"
              className="h-8 w-8 text-slate-600 hover:text-[#1C3D74]"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              onClick={() => nassaqConfirm(
                'سيُعاد بناء الإسناد التلقائي لجدول الانتظار من الجدول الرئيسي الحالي. التعديلات اليدوية المحفوظة لن تُمسح، وأي تعارضات (إجازات/منع زمني/يوم إجازة) ستظهر في تنبيهات أعلى الجدول.',
                () => regenerateRoster(),
                { confirmText: 'إعادة التوليد', title: 'إعادة توليد جدول الانتظار' },
              )}
              disabled={refreshing}
              className="h-8 px-3 bg-[#1C3D74] text-white hover:bg-[#15305c] shadow-sm disabled:opacity-60"
              title="إعادة توليد الإسناد التلقائي من الجدول الرئيسي مع الحفاظ على التعديلات اليدوية"
            >
              {refreshing
                ? <Loader2 className="h-4 w-4 ml-1.5 animate-spin" />
                : <Sparkles className="h-4 w-4 ml-1.5" />}
              {refreshing ? 'جارٍ إعادة التوليد…' : 'إعادة التوليد'}
            </Button>
          </div>
        </div>

        {/* ── Summary strip ───────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
          <KpiCard
            icon={Users}
            label="المعلمون النشطون"
            value={totals.teachers}
            accent="blue"
          />
          <KpiCard
            icon={Bot}
            label="خانات تلقائية"
            value={totals.auto_slots}
            accent="emerald"
          />
          <KpiCard
            icon={Hand}
            label="تعديلات يدوية"
            value={totals.overrides}
            accent="violet"
          />
          <KpiCard
            icon={ListChecks}
            label="إجمالي خانات الانتظار"
            value={totals.final_slots}
            accent="amber"
            emphasis
          />
        </div>

        {/* ── Legend ──────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-1 shrink-0 -mt-1">
          {viewMode === 'day' ? (
            <>
              <LegendChip color="bg-white border border-emerald-300" label="تلقائي" />
              <LegendChip color="bg-violet-100 border border-violet-400" label="يدوي" />
              <span className="text-[11px] text-slate-500 mr-auto">
                اضغط + لإضافة معلم • اضغط الاسم لاستثنائه.
              </span>
            </>
          ) : (
            <>
              <LegendChip color="bg-emerald-100 border border-emerald-300" label="انتظار تلقائي" />
              <LegendChip color="bg-violet-100 border border-violet-400" label="مُسند يدوياً" />
              <LegendChip color="bg-rose-50 border border-rose-300" label="مُستثنى يدوياً" />
              <LegendChip color="bg-slate-100 border border-slate-300" label="حصة مجدولة" />
              <LegendChip color="bg-slate-50 border border-slate-200" label="فارغ / يوم إجازة" />
              <span className="text-[11px] text-slate-500 mr-auto">
                اضغط على أي خانة قابلة للتعديل لتدوير الحالة.
              </span>
            </>
          )}
        </div>

        {/* ── Body ────────────────────────────────────────────────── */}
        <div className="flex-1 min-h-0 overflow-auto bg-white border border-slate-200 rounded-lg">
          {viewMode === 'day' ? (
            <StandbyDayCentricTable
              loading={loading}
              error={error}
              dayCentric={dayCentric}
              periods={periods}
              busyCellKey={busyCellKey}
              onCellClick={onDayCellClick}
            />
          ) : loading ? (
            <div className="flex h-full items-center justify-center py-20 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin ml-2" />
              جارٍ تحميل جدول الانتظار…
            </div>
          ) : error ? (
            <div className="p-6 text-center text-red-600">{error}</div>
          ) : teachers.length === 0 ? (
            <div className="p-6 text-center text-slate-500">
              لا يوجد معلمون مسجَّلون في هذه المدرسة بعد.
            </div>
          ) : (
            <RosterMatrix
              teachers={teachers}
              cells={cells}
              days={days}
              periods={periods}
              dayLabelMap={dayLabelMap}
              busyCell={busyCellKey}
              onCycle={cycleCell}
            />
          )}
        </div>

        {/* ── Teacher picker (day-centric add) ────────────────────── */}
        <Dialog open={!!picker} onOpenChange={(open) => { if (!open) setPicker(null); }}>
          <DialogContent dir="rtl" className="max-w-md">
            <DialogHeader>
              <DialogTitle>إضافة معلم لخانة الانتظار</DialogTitle>
            </DialogHeader>
            {picker && (
              <div className="space-y-3">
                <p className="text-sm text-slate-600">
                  {dayLabelMap[picker.day] || picker.day} — الحصة {picker.period} — الصف {picker.slot_index}
                </p>
                <Input
                  placeholder="ابحث باسم المعلم أو التخصص…"
                  value={pickerSearch}
                  onChange={(e) => setPickerSearch(e.target.value)}
                  autoFocus
                />
                <div className="max-h-72 overflow-auto border border-slate-200 rounded-md divide-y">
                  {eligibleForPicker.length === 0 ? (
                    <p className="text-center text-sm text-slate-400 p-4">
                      لا يوجد معلمون مؤهَّلون لهذه الخانة.
                    </p>
                  ) : eligibleForPicker.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={async () => {
                        const { day, period, slot_index } = picker;
                        setPicker(null);
                        await sendOverride(t.id, day, period, 'add', slot_index);
                      }}
                      className="w-full text-right px-3 py-2 hover:bg-emerald-50 flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900 truncate">{t.full_name}</p>
                        <p className="text-[11px] text-slate-500 truncate">
                          {maskInternalId(t.subject, canViewInternalIds) || '—'} • {t.assigned_periods}/{t.weekly_quota || '—'} حصص
                        </p>
                      </div>
                      <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800 text-[10px] shrink-0">
                        {t.standby_capacity} انتظار
                      </Badge>
                    </button>
                  ))}
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setPicker(null)}>إغلاق</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
    </>
  );
}

// Thin wrapper for the standalone `/school/standby` route.
export default function StandbyRosterPage() {
  return (
    <Sidebar>
      <div
        dir="rtl"
        className="flex flex-col h-[calc(100dvh-3.5rem)] lg:h-[100dvh] p-3 md:p-5 gap-3 bg-slate-50 text-slate-900 overflow-hidden"
      >
        <ScheduleTabNav active="standby" />
        <StandbyRosterContent />
      </div>
    </Sidebar>
  );
}

// ─── Matrix component (legacy teacher-centric view) ─────────────────────
function RosterMatrix({ teachers, cells, days, periods, dayLabelMap, onCycle, busyCell }) {
  const canViewInternalIds = useCanViewInternalIds();
  const totalDataCols = days.length * periods.length;
  const TEACHER_COL_WIDTH = 220;
  const PERIOD_COL_WIDTH = 56;
  const DAY_HEADER_HEIGHT = 28;
  const PERIOD_HEADER_HEIGHT = 24;
  const ROW_HEIGHT = 56;
  const DAY_COLS_TOTAL_PX = totalDataCols * PERIOD_COL_WIDTH;
  const gridTemplate = `${TEACHER_COL_WIDTH}px repeat(${totalDataCols}, ${PERIOD_COL_WIDTH}px)`;

  const teacherStickyShadow = 'shadow-[-2px_0_5px_rgba(0,0,0,0.02)]';

  return (
    <div
      className="grid text-[11px]"
      style={{ gridTemplateColumns: gridTemplate, minWidth: TEACHER_COL_WIDTH + DAY_COLS_TOTAL_PX }}
    >
      <div
        className={`sticky top-0 bg-slate-50 text-slate-700 text-xs font-semibold flex items-center justify-center border-b border-l border-slate-200 ${teacherStickyShadow}`}
        style={{ insetInlineStart: 0, zIndex: 30, height: DAY_HEADER_HEIGHT }}
      >
        المعلم
      </div>
      {days.map((dayKey) => (
        <div
          key={`day-h-${dayKey}`}
          className="sticky top-0 z-20 bg-slate-50 text-slate-700 text-xs font-semibold text-center flex items-center justify-center border-b border-l border-slate-200"
          style={{ gridColumn: `span ${periods.length}`, height: DAY_HEADER_HEIGHT }}
        >
          {dayLabelMap[dayKey] || dayKey}
        </div>
      ))}

      <div
        className={`sticky bg-slate-50 text-slate-500 text-[10px] font-medium px-2 flex items-center justify-end border-b border-l border-slate-200 ${teacherStickyShadow}`}
        style={{ top: DAY_HEADER_HEIGHT, insetInlineStart: 0, zIndex: 30, height: PERIOD_HEADER_HEIGHT }}
      >
        {teachers.length} معلم • {periods.length}×{days.length}
      </div>
      {days.map((dayKey) => (
        periods.map((p) => (
          <div
            key={`ph-${dayKey}-${p}`}
            className="sticky z-20 bg-slate-50 text-slate-700 text-center text-[11px] flex items-center justify-center border-b border-l border-slate-200"
            style={{ top: DAY_HEADER_HEIGHT, height: PERIOD_HEADER_HEIGHT }}
          >
            {p}
          </div>
        ))
      ))}

      {teachers.map((teacher) => {
        const teacherCells = cells[teacher.id] || {};
        const rowBg = 'bg-white';
        return (
          <React.Fragment key={teacher.id}>
            <div
              className={`sticky z-10 px-3 py-2 border-b border-l border-slate-200 ${rowBg} ${teacherStickyShadow}`}
              style={{ insetInlineStart: 0, minHeight: ROW_HEIGHT }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-900 truncate">{teacher.full_name}</p>
                  <p className="text-[10px] text-slate-500 truncate">
                    {maskInternalId(teacher.subject, canViewInternalIds) || '—'}
                    {' • '}
                    <span className="font-semibold text-slate-600">
                      {teacher.assigned_periods}
                      <span className="text-slate-400">/</span>
                      {teacher.weekly_quota || '—'}
                    </span>
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className="border-amber-300 bg-amber-50 text-amber-800 text-[10px] whitespace-nowrap shrink-0"
                >
                  {teacher.standby_capacity} انتظار
                </Badge>
              </div>
            </div>

            {days.map((dayKey) => (
              periods.map((p) => {
                const cell = teacherCells[dayKey]?.[String(p)] || null;
                const cellKey = `${teacher.id}:${dayKey}:${p}`;
                const isBusy = busyCell === cellKey;
                const cycle = cell && (cell.status === 'standby' || cell.status === 'free')
                  ? () => onCycle(teacher.id, dayKey, p, cell)
                  : undefined;
                return (
                  <div
                    key={cellKey}
                    className={`min-w-[48px] h-14 border-b border-l border-slate-100 ${rowBg}`}
                  >
                    <StandbyCell cell={cell} onCycle={cycle} busy={isBusy} />
                  </div>
                );
              })
            ))}
          </React.Fragment>
        );
      })}
    </div>
  );
}
