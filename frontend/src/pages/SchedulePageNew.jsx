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
  Wand2, UserX, Sparkles, Loader2, RefreshCw,
  Scale, Hourglass, UserMinus, AlertOctagon, AlertTriangle,
} from 'lucide-react';

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
  // cell.is_vacant => مستبدل أحمر (المعلم غائب — حصته شاغرة)
  if (cell?.is_vacant) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="w-full h-full min-h-[44px] flex flex-col items-center justify-center text-[11px] font-semibold leading-tight px-1 py-1
                   bg-red-100 hover:bg-red-200 text-red-800 border border-red-300 rounded-md transition-colors"
      >
        <span className="font-bold">شاغرة</span>
        <span className="text-[10px] opacity-75 truncate max-w-full">{cell.class_name}</span>
      </button>
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

function EmptyCell({ teacherAbsent, onClick, vacantPayload }) {
  // المعلم غائب => خانة فارغة تتحوّل لخانة شاغرة حمراء.
  if (teacherAbsent) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="w-full h-full min-h-[44px] flex items-center justify-center text-[11px] font-semibold
                   bg-red-100 hover:bg-red-200 text-red-700 border border-red-300 rounded-md transition-colors"
      >
        شاغرة
      </button>
    );
  }
  // فراغ عادي للمعلم — لا تنبيه
  return (
    <div className="w-full h-full min-h-[44px] bg-slate-50 border border-dashed border-slate-200 rounded-md" />
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

  const handleAutoGenerate = useCallback(() => {
    // مرحلة لاحقة: ستستدعي محرك التوليد الفعلي.
    console.log('Auto-generate clicked', { school_id: schoolId });
    toast.info('سيتم تشغيل محرك التوليد التلقائي قريباً', {
      description: 'هذه نسخة أولية — الزر مرتبط حالياً بمؤشّر فقط.',
    });
  }, [schoolId]);

  const handleLogAbsence = useCallback(() => {
    console.log('Log absence clicked', { school_id: schoolId });
    toast.info('سيتم فتح نافذة تسجيل الغياب قريباً');
  }, [schoolId]);

  const handleVacantClick = useCallback((cellData) => {
    console.log('Vacant clicked', cellData);
  }, []);

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
    <div dir="rtl" className="min-h-screen bg-slate-50 text-slate-900">
      <Sidebar />
      <main className="md:mr-72 p-4 md:p-6 space-y-5">
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
              className="bg-violet-600 hover:bg-violet-700 text-white shadow-md"
            >
              <Wand2 className="h-4 w-4 ml-2" />
              إنشاء الجدول تلقائياً
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
      </main>
    </div>
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
                        <EmptyCell
                          teacherAbsent={rowAbsentTint}
                          onClick={() => onVacantClick(cellData)}
                          vacantPayload={cellData}
                        />
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
