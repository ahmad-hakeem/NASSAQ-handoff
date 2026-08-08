/**
 * StandbyDayCentricTable — جدول الانتظار السعودي (day-centric).
 * نَسَّق | NASSAQ — Task #157
 *
 * يعرض جدول الانتظار بصيغة وزارة التعليم السعودية:
 *   • عمود اليوم (مدمج عمودياً عبر صفوف اليوم).
 *   • عمود «عدد المنتظرين» (1..N).
 *   • أعمدة الحصص (الحصة الأولى … الحصة السابعة).
 *
 * يقرأ payload `day_centric` المُسقَط من الباك‑إند بدون أي إعادة حساب
 * في الواجهة. التعديل اليدوي والمصدر التلقائي مميَّزان بصرياً.
 */
import React from 'react';
import { Loader2, Sparkles, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useCanViewInternalIds } from '@/shared/hooks/useCanViewInternalIds';
import { maskInternalId } from '@/shared/models/utils/internalId';

const DAY_AR = {
  sunday: 'يوم الأحد',
  monday: 'يوم الإثنين',
  tuesday: 'يوم الثلاثاء',
  wednesday: 'يوم الأربعاء',
  thursday: 'يوم الخميس',
};

const PERIOD_AR = {
  1: 'الحصة الأولى',
  2: 'الحصة الثانية',
  3: 'الحصة الثالثة',
  4: 'الحصة الرابعة',
  5: 'الحصة الخامسة',
  6: 'الحصة السادسة',
  7: 'الحصة السابعة',
  8: 'الحصة الثامنة',
  9: 'الحصة التاسعة',
};

function periodLabel(p) {
  return PERIOD_AR[p] || `الحصة ${p}`;
}

export default function StandbyDayCentricTable({
  loading,
  error,
  dayCentric,
  periods,
  busyCellKey,
  onCellClick,
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <Loader2 className="h-6 w-6 animate-spin ml-2" />
        جارٍ تحميل جدول الانتظار…
      </div>
    );
  }
  if (error) {
    return <div className="p-6 text-center text-red-600">{error}</div>;
  }
  if (!dayCentric || !dayCentric.days) {
    return (
      <div className="p-6 text-center text-slate-500">
        لا توجد بيانات لعرضها بعد.
      </div>
    );
  }

  const days = dayCentric.days || [];
  const warnings = dayCentric.warnings || [];

  return (
    <div className="overflow-auto">
      {warnings.length > 0 && (
        <div
          dir="rtl"
          className="m-3 p-3 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 text-xs"
        >
          <div className="flex items-center gap-1.5 font-bold mb-1">
            <AlertTriangle className="h-4 w-4" />
            تنبيهات تعديلات يدوية ({warnings.length})
          </div>
          <ul className="list-disc me-5 space-y-0.5">
            {warnings.slice(0, 5).map((w, i) => (
              <li key={i}>{w.message_ar}</li>
            ))}
            {warnings.length > 5 && (
              <li className="opacity-70">… و{warnings.length - 5} تنبيهات أخرى</li>
            )}
          </ul>
        </div>
      )}

      <table
        dir="rtl"
        className="w-full border-collapse text-[12px] text-slate-800"
        data-testid="standby-day-centric-table"
      >
        <thead>
          <tr className="bg-[#1C3D74] text-white">
            <th className="border border-[#1C3D74] px-2 py-2 font-bold w-[110px]">
              اليوم
            </th>
            <th className="border border-[#1C3D74] px-2 py-2 font-bold w-[90px]">
              عدد المنتظرين
            </th>
            {periods.map((p) => (
              <th
                key={`ph-${p}`}
                className="border border-[#1C3D74] px-2 py-2 font-bold whitespace-nowrap"
              >
                {periodLabel(p)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {days.map((day) => {
            const slotCount = day.slot_count || 1;
            // Always expose one trailing empty "add another" row so every
            // period offers a "+" cell — even when every period already
            // holds exactly one teacher (Task: multi-teacher standby).
            // The trailing slot is the next slot_index after slot_count.
            const trailingRow = {
              slot_index: slotCount + 1,
              cells: {},
              is_trailing: true,
            };
            const rows = [...(day.rows || []), trailingRow];
            const renderRowCount = rows.length;
            return rows.map((row, rIdx) => (
              <tr key={`${day.day}-${row.slot_index}`} className="hover:bg-slate-50">
                {rIdx === 0 && (
                  <td
                    rowSpan={renderRowCount}
                    className="border border-slate-300 bg-[#F4F7FB] text-center font-bold text-[#1C3D74] align-middle"
                  >
                    {DAY_AR[day.day] || day.day}
                  </td>
                )}
                <td className="border border-slate-300 bg-slate-50 text-center font-bold text-slate-600">
                  <span
                    className={`inline-flex items-center justify-center w-6 h-6 rounded-md bg-white border text-[11px] ${
                      row.is_trailing
                        ? 'border-dashed border-emerald-300 text-emerald-500'
                        : 'border-slate-300'
                    }`}
                  >
                    {row.slot_index}
                  </span>
                </td>
                {periods.map((p) => {
                  const cell = row.cells[String(p)];
                  const cellKey = cell
                    ? `${cell.teacher_id}:${day.day}:${p}`
                    : `empty:${day.day}:${p}:${row.slot_index}`;
                  const isBusy = busyCellKey === cellKey;
                  return (
                    <Cell
                      key={cellKey}
                      cell={cell}
                      busy={isBusy}
                      testId={`standby-cell-${day.day}-${p}-${row.slot_index}`}
                      onClick={
                        onCellClick
                          ? () => onCellClick({
                              cell,
                              day: day.day,
                              period: p,
                              slot_index: row.slot_index,
                            })
                          : undefined
                      }
                    />
                  );
                })}
              </tr>
            ));
          })}
        </tbody>
      </table>
    </div>
  );
}

function Cell({ cell, onClick, busy, testId }) {
  const canViewInternalIds = useCanViewInternalIds();
  if (!cell) {
    return (
      <td className="border border-slate-300 p-0 align-middle">
        <button
          type="button"
          onClick={onClick}
          disabled={busy}
          data-testid={testId}
          title="إضافة معلم لخانة الانتظار"
          className="w-full h-12 text-slate-300 hover:bg-emerald-50 hover:text-emerald-600 transition-colors disabled:opacity-50 text-lg leading-none"
        >
          +
        </button>
      </td>
    );
  }

  const isManual = cell.source === 'manual';
  const bg = isManual ? 'bg-violet-50' : 'bg-white';
  const text = isManual ? 'text-violet-800' : 'text-slate-800';
  const Icon = isManual ? Sparkles : CheckCircle2;
  const tooltip = isManual
    ? 'مُسند يدوياً — اضغط لإلغاء الإسناد'
    : 'انتظار تلقائي — اضغط لاستثنائه';

  return (
    <td className="border border-slate-300 p-0 align-middle">
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        title={tooltip}
        className={`w-full h-12 px-1 flex flex-col items-center justify-center ${bg} ${text} hover:brightness-95 transition-all disabled:opacity-50`}
      >
        <span className="flex items-center gap-1 max-w-full">
          <Icon className={`h-3 w-3 shrink-0 ${isManual ? 'text-violet-500' : 'text-emerald-500'}`} />
          <span className="font-semibold truncate text-[11px]">
            {cell.teacher_name}
          </span>
        </span>
        {maskInternalId(cell.subject, canViewInternalIds) && (
          <span className="text-[9px] text-slate-400 truncate max-w-full leading-tight">
            {maskInternalId(cell.subject, canViewInternalIds)}
          </span>
        )}
      </button>
    </td>
  );
}
