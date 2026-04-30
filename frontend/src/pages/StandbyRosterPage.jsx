/**
 * جدول الانتظار — Standby Roster (manual override surface)
 * نَسَّق | NASSAQ — Task #102
 *
 * مصفوفة (معلمين × أيام × حصص) تعرض الجدول التلقائي مع إمكانية تعديل يدوي
 * لكل خانة. الضغط على خانة فارغة يُضيف المعلم إلى الانتظار في تلك الخانة،
 * والضغط على خانة انتظار يُزيلها، والضغط مرة ثالثة يُعيد القرار للمحرك
 * التلقائي. الخانات المشغولة بحصة فعلية أو في يوم محظور لا يمكن تعديلها.
 *
 * Endpoints:
 *   GET /api/standby/roster
 *   PUT /api/standby/roster/cell
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Hourglass, Loader2, RefreshCw, ArrowRight, Sparkles,
  CheckCircle2, MinusCircle, Lock, CalendarOff, Wand2,
} from 'lucide-react';

const DAYS = [
  { key: 'sunday',    ar: 'الأحد' },
  { key: 'monday',    ar: 'الإثنين' },
  { key: 'tuesday',   ar: 'الثلاثاء' },
  { key: 'wednesday', ar: 'الأربعاء' },
  { key: 'thursday',  ar: 'الخميس' },
];

// ─── Cell renderer ────────────────────────────────────────────────────────
function StandbyCell({ cell, onCycle, busy }) {
  if (!cell) return <div className="w-full h-full min-h-[40px] rounded-md bg-slate-50 border border-dashed border-slate-200" />;

  const status = cell.status; // standby | busy | blocked | free
  const ov = cell.override;   // add | remove | null
  const isAuto = !!cell.auto;

  if (status === 'busy') {
    return (
      <div
        className="w-full h-full min-h-[40px] flex flex-col items-center justify-center text-[10px] leading-tight px-1 py-1
                   bg-slate-100 border border-slate-300 rounded-md text-slate-700"
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
        className="w-full h-full min-h-[40px] flex items-center justify-center text-[10px]
                   bg-slate-50 border border-slate-200 rounded-md text-slate-400"
        title="يوم إجازة لهذا المعلم"
      >
        <CalendarOff className="h-3.5 w-3.5" />
      </div>
    );
  }

  // status is "standby" or "free" — clickable
  const isStandby = status === 'standby';
  const overrideLabel = ov === 'add' ? 'مُجبر' : ov === 'remove' ? 'مُلغى' : null;

  let bgCls, textCls, borderCls, Icon;
  if (isStandby && ov === 'add') {
    // Forced standby (override-add)
    bgCls = 'bg-violet-100 hover:bg-violet-200';
    textCls = 'text-violet-800';
    borderCls = 'border-violet-400';
    Icon = Sparkles;
  } else if (isStandby) {
    // Auto-picked standby
    bgCls = 'bg-emerald-50 hover:bg-emerald-100';
    textCls = 'text-emerald-800';
    borderCls = 'border-emerald-300';
    Icon = CheckCircle2;
  } else if (ov === 'remove') {
    // Auto picked it but principal removed it
    bgCls = 'bg-rose-50 hover:bg-rose-100';
    textCls = 'text-rose-700';
    borderCls = 'border-rose-300';
    Icon = MinusCircle;
  } else {
    // Plain free slot
    bgCls = 'bg-white hover:bg-slate-50';
    textCls = 'text-slate-400';
    borderCls = 'border-slate-200';
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
      className={`w-full h-full min-h-[40px] flex flex-col items-center justify-center text-[10px] leading-tight px-1 py-1
                  ${bgCls} ${textCls} border ${borderCls} rounded-md transition-colors disabled:opacity-50`}
    >
      {Icon ? <Icon className="h-3.5 w-3.5 mb-0.5" /> : <span className="opacity-30">—</span>}
      {overrideLabel && (
        <span className="text-[9px] font-bold opacity-80">{overrideLabel}</span>
      )}
    </button>
  );
}

// ─── Legend chip ──────────────────────────────────────────────────────────
function LegendChip({ color, label }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`inline-block w-3 h-3 rounded ${color}`} />
      <span className="text-[11px] text-slate-600">{label}</span>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────
export default function StandbyRosterPage() {
  const { user, api } = useAuth();
  const navigate = useNavigate();
  const schoolId = user?.tenant_id;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState(null);
  const [busyCell, setBusyCell] = useState(null); // `${tid}:${day}:${period}`

  const loadRoster = useCallback(async () => {
    if (!schoolId) return;
    try {
      const response = await api.get('/standby/roster', {
        params: { school_id: schoolId },
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

  const cycleCell = useCallback(async (teacherId, day, period, current) => {
    if (!schoolId) return;
    // Cycle: free → add → remove → reset (back to auto/free).
    // Simplified rules based on current state:
    //   - free  + no override        → action="add"
    //   - standby (auto only)        → action="remove"
    //   - standby (override="add")   → action="reset"
    //   - free   (override="remove") → action="reset"
    const { status, override, auto } = current;
    let action;
    if (status === 'standby' && override === 'add') {
      action = 'reset';
    } else if (status === 'standby' && auto) {
      action = 'remove';
    } else if (status === 'standby') {
      action = 'remove';
    } else if (status === 'free' && override === 'remove') {
      action = 'reset';
    } else {
      action = 'add';
    }

    const cellKey = `${teacherId}:${day}:${period}`;
    setBusyCell(cellKey);
    try {
      await api.put(
        '/standby/roster/cell',
        { teacher_id: teacherId, day, period, action },
        {
          params: { school_id: schoolId },
          headers: { 'X-School-Context': schoolId },
        },
      );
      await loadRoster();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : 'تعذّر حفظ التعديل';
      toast.error(msg);
    } finally {
      setBusyCell(null);
    }
  }, [api, schoolId, loadRoster]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadRoster();
  }, [loadRoster]);

  const teachers = data?.teachers || [];
  const cells = data?.cells || {};
  const periods = data?.periods || [1, 2, 3, 4, 5, 6, 7];
  const days = data?.days || DAYS.map(d => d.key);
  const totals = data?.totals || { teachers: 0, auto_slots: 0, final_slots: 0, overrides: 0 };

  const dayLabelMap = useMemo(() => Object.fromEntries(DAYS.map(d => [d.key, d.ar])), []);

  return (
    <Sidebar>
      <div dir="rtl" className="p-4 md:p-6 space-y-5 bg-slate-50 min-h-full text-slate-900">
        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#1C3D74] flex items-center gap-2">
              <Hourglass className="h-7 w-7 text-amber-500" />
              جدول الانتظار
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              عدِّل يدوياً مَن يكون في انتظار في كل خانة. التعديلات اليدوية تأخذ الأولوية على التوزيع التلقائي ولا تُمحى عند إعادة التوليد.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="border border-slate-200">
            <CardContent className="p-3">
              <p className="text-[11px] text-slate-500 mb-1">معلمون</p>
              <p className="text-xl font-bold text-[#1C3D74]">{totals.teachers}</p>
            </CardContent>
          </Card>
          <Card className="border border-emerald-200 bg-emerald-50/40">
            <CardContent className="p-3">
              <p className="text-[11px] text-emerald-700 mb-1">خانات تلقائية</p>
              <p className="text-xl font-bold text-emerald-800">{totals.auto_slots}</p>
            </CardContent>
          </Card>
          <Card className="border border-violet-200 bg-violet-50/40">
            <CardContent className="p-3">
              <p className="text-[11px] text-violet-700 mb-1">تعديلات يدوية</p>
              <p className="text-xl font-bold text-violet-800">{totals.overrides}</p>
            </CardContent>
          </Card>
          <Card className="border border-amber-200 bg-amber-50/40">
            <CardContent className="p-3">
              <p className="text-[11px] text-amber-700 mb-1">إجمالي خانات الانتظار</p>
              <p className="text-xl font-bold text-amber-800">{totals.final_slots}</p>
            </CardContent>
          </Card>
        </div>

        {/* ── Legend ──────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-1">
          <LegendChip color="bg-emerald-100 border border-emerald-300" label="انتظار تلقائي" />
          <LegendChip color="bg-violet-100 border border-violet-400" label="مُسند يدوياً" />
          <LegendChip color="bg-rose-50 border border-rose-300" label="مُستثنى يدوياً" />
          <LegendChip color="bg-slate-100 border border-slate-300" label="حصة مجدولة" />
          <LegendChip color="bg-slate-50 border border-slate-200" label="فارغ / يوم إجازة" />
          <span className="text-[11px] text-slate-500 mr-auto">
            اضغط على أي خانة قابلة للتعديل لتدوير الحالة (إضافة → إزالة → إعادة للمحرك).
          </span>
        </div>

        {/* ── Matrix ──────────────────────────────────────────────── */}
        <Card className="border border-slate-200 shadow-sm overflow-hidden">
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-20 text-slate-500">
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
                busyCell={busyCell}
                onCycle={cycleCell}
              />
            )}
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}

// ─── Matrix component (sticky teacher column + sticky header) ────────────
function RosterMatrix({ teachers, cells, days, periods, dayLabelMap, onCycle, busyCell }) {
  const totalDataCols = days.length * periods.length;
  const TEACHER_COL_WIDTH = 220;
  const PERIOD_COL_WIDTH = 64;
  const DAY_COLS_TOTAL_PX = totalDataCols * PERIOD_COL_WIDTH;
  const gridTemplate = `${TEACHER_COL_WIDTH}px repeat(${totalDataCols}, ${PERIOD_COL_WIDTH}px)`;

  return (
    <div className="overflow-auto max-h-[calc(100vh-360px)] relative">
      <div
        className="grid text-[12px]"
        style={{ gridTemplateColumns: gridTemplate, minWidth: TEACHER_COL_WIDTH + DAY_COLS_TOTAL_PX }}
      >
        {/* Sticky header row 1: day spans */}
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
          </div>
        ))}

        {/* Sticky header row 2: period numbers */}
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

        {/* Teacher rows */}
        {teachers.map((teacher, idx) => {
          const teacherCells = cells[teacher.id] || {};
          const rowBg = idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/60';
          return (
            <React.Fragment key={teacher.id}>
              <div
                className={`sticky z-10 px-3 py-2 border-t border-l border-slate-200 ${rowBg}`}
                style={{ insetInlineStart: 0 }}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900 text-sm truncate">{teacher.full_name}</p>
                    <p className="text-[11px] text-slate-500 truncate">{teacher.subject || '—'}</p>
                  </div>
                  <div className="text-[11px] font-semibold text-slate-700 whitespace-nowrap flex flex-col items-end">
                    <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800 text-[10px]">
                      {teacher.standby_capacity} انتظار
                    </Badge>
                    <span className="text-[10px] text-slate-500">
                      {teacher.assigned_periods}
                      <span className="text-slate-400">/</span>
                      {teacher.weekly_quota || '—'}
                    </span>
                  </div>
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
                      className={`p-1 border-t border-l border-slate-200 ${rowBg}`}
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
    </div>
  );
}
