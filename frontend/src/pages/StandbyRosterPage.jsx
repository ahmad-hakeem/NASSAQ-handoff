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
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';

import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Hourglass, Loader2, RefreshCw, ArrowRight, Sparkles,
  CheckCircle2, MinusCircle, Lock, CalendarOff, LayoutGrid, Rows3,
} from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import ScheduleTabNav from '../components/schedule/ScheduleTabNav';
import StandbyDayCentricTable from '../components/schedule/StandbyDayCentricTable';

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
  const navigate = useNavigate();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();
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
      const msg = e?.response?.data?.detail || e?.message || 'تعذّر تحميل جدول الانتظار';
      setError(typeof msg === 'string' ? msg : 'تعذّر تحميل جدول الانتظار');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, schoolId]);

  useEffect(() => { loadRoster(); }, [loadRoster]);

  const sendOverride = useCallback(async (teacherId, day, period, action, slotIndex = null) => {
    if (!schoolId) return;
    const cellKey = slotIndex != null
      ? `slot:${day}:${period}:${slotIndex}`
      : `${teacherId}:${day}:${period}`;
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
      const detail = e?.response?.data?.detail;
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
      // Edits are slot-addressable: server scopes the change to the
      // exact (day, period, slot_index) so other rows are unaffected.
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
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 shrink-0">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#1C3D74] flex items-center gap-2">
              <Hourglass className="h-7 w-7 text-amber-500" />
              جدول حصص الانتظار
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              عرض وزارة التعليم: لكل يوم صفوف بعدد المعلمين المنتظرين، وأعمدة بالحصص. التعديلات اليدوية محفوظة بين عمليات إعادة التوليد.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-md border border-slate-300 overflow-hidden bg-white">
              <button
                type="button"
                onClick={() => setViewMode('day')}
                className={`px-3 py-1.5 text-xs font-semibold flex items-center gap-1 ${viewMode === 'day' ? 'bg-[#1C3D74] text-white' : 'text-slate-600 hover:bg-slate-50'}`}
                title="عرض حسب اليوم (افتراضي)"
              >
                <Rows3 className="h-3.5 w-3.5" />
                حسب اليوم
              </button>
              <button
                type="button"
                onClick={() => setViewMode('matrix')}
                className={`px-3 py-1.5 text-xs font-semibold flex items-center gap-1 ${viewMode === 'matrix' ? 'bg-[#1C3D74] text-white' : 'text-slate-600 hover:bg-slate-50'}`}
                title="عرض المصفوفة الكامل (معلم × يوم × حصة)"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                مصفوفة المعلمين
              </button>
            </div>
            <Button
              variant="outline"
              onClick={() => navigate('/school/schedule')}
              className="border-slate-300"
            >
              <ArrowRight className="h-4 w-4 ml-2" />
              العودة لإدارة الجداول
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

        {/* ── Summary strip ───────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
          <Card className="bg-white shadow-sm rounded-lg border border-slate-200 border-t-4 border-t-blue-400">
            <CardContent className="p-3">
              <p className="text-[11px] font-medium text-slate-500 mb-1">معلمون</p>
              <p className="text-xl font-bold text-slate-900">{totals.teachers}</p>
            </CardContent>
          </Card>
          <Card className="bg-white shadow-sm rounded-lg border border-slate-200 border-t-4 border-t-emerald-400">
            <CardContent className="p-3">
              <p className="text-[11px] font-medium text-slate-500 mb-1">خانات تلقائية</p>
              <p className="text-xl font-bold text-slate-900">{totals.auto_slots}</p>
            </CardContent>
          </Card>
          <Card className="bg-white shadow-sm rounded-lg border border-slate-200 border-t-4 border-t-violet-400">
            <CardContent className="p-3">
              <p className="text-[11px] font-medium text-slate-500 mb-1">تعديلات يدوية</p>
              <p className="text-xl font-bold text-slate-900">{totals.overrides}</p>
            </CardContent>
          </Card>
          <Card className="bg-white shadow-sm rounded-lg border border-slate-200 border-t-4 border-t-amber-400">
            <CardContent className="p-3">
              <p className="text-[11px] font-medium text-slate-500 mb-1">إجمالي خانات الانتظار</p>
              <p className="text-xl font-bold text-slate-900">{totals.final_slots}</p>
            </CardContent>
          </Card>
        </div>

        {/* ── Legend ──────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-1 shrink-0">
          {viewMode === 'day' ? (
            <>
              <LegendChip color="bg-white border border-emerald-300" label="انتظار تلقائي" />
              <LegendChip color="bg-violet-100 border border-violet-400" label="مُسند يدوياً" />
              <span className="text-[11px] text-slate-500 mr-auto">
                اضغط خانة فارغة لإضافة معلم • اضغط معلماً لاستثنائه.
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
                          {t.subject || '—'} • {t.assigned_periods}/{t.weekly_quota || '—'} حصص
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
        className="flex flex-col h-[calc(100dvh-3.5rem)] lg:h-[100dvh] p-4 md:p-6 gap-5 bg-slate-50 text-slate-900 overflow-hidden"
      >
        <ScheduleTabNav active="standby" />
        <StandbyRosterContent />
      </div>
    </Sidebar>
  );
}

// ─── Matrix component (legacy teacher-centric view) ─────────────────────
function RosterMatrix({ teachers, cells, days, periods, dayLabelMap, onCycle, busyCell }) {
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
                    {teacher.subject || '—'}
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
