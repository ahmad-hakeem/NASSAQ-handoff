/**
 * WaitingSessionsPanel — لوحة جانبية ثابتة لحصص الانتظار/الخانات الفارغة
 * نَسَّق | NASSAQ
 *
 * Renders an organized, collapsible right-side panel that lists every empty
 * slot for the current class grouped by day, pins today's gaps in a
 * "Needs coverage now" section, and emits drag-and-drop / click events so
 * the parent page can open the candidates picker.
 */
import React, { useMemo, useState } from 'react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
  ChevronDown, ChevronUp, ChevronsLeft, ChevronsRight,
  AlertTriangle, Clock, CalendarDays, Sparkles,
} from 'lucide-react';

const DAY_INDEX = {
  sunday: 0, monday: 1, tuesday: 2, wednesday: 3,
  thursday: 4, friday: 5, saturday: 6,
};

// JS getDay(): Sunday=0..Saturday=6 — matches DAY_INDEX above.
const TODAY_KEY = (() => {
  const d = new Date().getDay();
  return Object.entries(DAY_INDEX).find(([, idx]) => idx === d)?.[0] || null;
})();

export default function WaitingSessionsPanel({
  collapsed,
  onToggleCollapsed,
  days,            // [{ key, ar, color }]
  periodSlots,     // time slots without breaks
  gridSessions,    // sessions for currently selected class
  canPick,
  onPickEmpty,     // (dayKey, periodNumber) => void
  contextLabel,    // e.g. class name for the empty-state hint
}) {
  // Compute empty slots for the current class.
  const emptyByDay = useMemo(() => {
    if (!periodSlots.length || !days.length) return {};
    const byDay = {};
    days.forEach(day => { byDay[day.key] = []; });
    days.forEach(day => {
      periodSlots.forEach(slot => {
        const periodNum = Number(slot.period_number || slot.slot_number);
        if (!periodNum) return;
        const filled = gridSessions.some(s =>
          (s.day_of_week || s.day) === day.key
          && (Number(s.period_number) === periodNum || Number(s.slot_number) === periodNum)
        );
        if (!filled) {
          byDay[day.key].push({
            day: day.key,
            period: periodNum,
            start_time: slot.start_time,
            end_time: slot.end_time,
          });
        }
      });
    });
    return byDay;
  }, [days, periodSlots, gridSessions]);

  const totalEmpty = useMemo(
    () => Object.values(emptyByDay).reduce((sum, arr) => sum + arr.length, 0),
    [emptyByDay]
  );

  // Today's empty slots get pinned at the top.
  const todayEmpty = TODAY_KEY ? (emptyByDay[TODAY_KEY] || []) : [];

  // ── Collapsed (thin rail) ──────────────────────────────────────────────
  if (collapsed) {
    return (
      <aside
        dir="rtl"
        className="hidden lg:flex shrink-0 w-12 flex-col items-center gap-3 py-4 border-l border-slate-200 bg-white/70 backdrop-blur"
        aria-label="لوحة حصص الانتظار (مطوية)"
      >
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="w-9 h-9 rounded-lg bg-white border border-slate-200 hover:border-[#2BB5A0] hover:bg-[#2BB5A0]/5 flex items-center justify-center text-slate-600 transition"
          title="فتح لوحة حصص الانتظار"
          data-testid="waiting-panel-expand"
        >
          <ChevronsRight className="h-4 w-4" />
        </button>
        <div className="rotate-180 [writing-mode:vertical-rl] text-[11px] font-bold text-slate-600 tracking-wide flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-[#2BB5A0]" />
          حصص الانتظار
          {totalEmpty > 0 && (
            <span className="px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-700 text-[10px] font-bold">
              {totalEmpty}
            </span>
          )}
        </div>
      </aside>
    );
  }

  // ── Expanded ───────────────────────────────────────────────────────────
  return (
    <aside
      dir="rtl"
      className="hidden lg:flex shrink-0 w-[340px] xl:w-[360px] flex-col border-l border-slate-200 bg-white/80 backdrop-blur"
      aria-label="لوحة حصص الانتظار"
      data-testid="waiting-panel"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-gradient-to-l from-[#1C3D74]/5 to-[#2BB5A0]/5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#1C3D74] to-[#2BB5A0] flex items-center justify-center shrink-0">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div className="min-w-0">
            <h2 className="font-bold text-sm text-slate-800 leading-tight truncate">حصص الانتظار</h2>
            <p className="text-[10px] text-slate-500 leading-tight">
              {totalEmpty > 0 ? `${totalEmpty} خانة بحاجة لتعيين` : 'لا توجد خانات فارغة'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 transition shrink-0"
          title="طيّ اللوحة"
          data-testid="waiting-panel-collapse"
        >
          <ChevronsLeft className="h-4 w-4" />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {totalEmpty === 0 ? (
          <EmptyState contextLabel={contextLabel} />
        ) : (
          <>
            {/* Pinned: needs coverage now (today) */}
            {todayEmpty.length > 0 && (
              <UrgentSection
                items={todayEmpty}
                dayLabel={days.find(d => d.key === TODAY_KEY)?.ar || ''}
                canPick={canPick}
                onPick={onPickEmpty}
              />
            )}

            {/* All days, grouped */}
            <div className="space-y-2">
              {days.map(day => {
                const items = emptyByDay[day.key] || [];
                if (items.length === 0) return null;
                // Skip today again here — already pinned above.
                if (day.key === TODAY_KEY) return null;
                return (
                  <DayGroup
                    key={day.key}
                    day={day}
                    items={items}
                    canPick={canPick}
                    onPick={onPickEmpty}
                  />
                );
              })}
              {/* If today still has items but today is pinned, show a tiny chip linking back (optional) */}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

// ── Subcomponents ─────────────────────────────────────────────────────────

function EmptyState({ contextLabel }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 gap-3 text-slate-500">
      <div className="w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center">
        <Sparkles className="h-7 w-7 text-emerald-400" />
      </div>
      <p className="text-sm font-semibold text-slate-700">الجدول مكتمل</p>
      <p className="text-[11px] text-slate-400 px-4 leading-relaxed">
        لا توجد خانات فارغة حالياً{contextLabel ? ` لـ${contextLabel}` : ''}. اختر فصلاً آخر إن أردت متابعة الانتظار.
      </p>
    </div>
  );
}

function UrgentSection({ items, dayLabel, canPick, onPick }) {
  return (
    <div className="rounded-xl border-2 border-red-200 bg-gradient-to-b from-red-50 to-amber-50/60 p-3">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-red-100 flex items-center justify-center animate-pulse">
          <AlertTriangle className="h-4 w-4 text-red-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-extrabold text-red-700 leading-tight">تحتاج تغطية الآن</p>
          <p className="text-[10px] text-red-500 leading-tight">{dayLabel} · {items.length} خانة</p>
        </div>
      </div>
      <ul className="space-y-1.5">
        {items.map(item => (
          <li key={`${item.day}-${item.period}`}>
            <SlotCard item={item} canPick={canPick} onPick={onPick} urgent />
          </li>
        ))}
      </ul>
    </div>
  );
}

function DayGroup({ day, items, canPick, onPick }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 hover:bg-slate-50 transition text-right"
        data-testid={`waiting-day-${day.key}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-lg bg-gradient-to-r ${day.color} text-white text-[11px] font-bold shadow-sm`}>
            {day.ar}
          </span>
          <Badge className="bg-amber-100 text-amber-700 border-amber-200 text-[10px] px-1.5 py-0 h-5">
            {items.length}
          </Badge>
        </div>
        {open
          ? <ChevronUp className="h-4 w-4 text-slate-400 shrink-0" />
          : <ChevronDown className="h-4 w-4 text-slate-400 shrink-0" />}
      </button>
      {open && (
        <ul className="px-2 pb-2 space-y-1.5">
          {items.map(item => (
            <li key={`${item.day}-${item.period}`}>
              <SlotCard item={item} canPick={canPick} onPick={onPick} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SlotCard({ item, canPick, onPick, urgent }) {
  const handleDragStart = (e) => {
    e.dataTransfer.setData(
      'application/nassaq-waiting-slot',
      JSON.stringify({ day: item.day, period: item.period })
    );
    e.dataTransfer.effectAllowed = 'copy';
  };

  return (
    <button
      type="button"
      draggable={canPick}
      onDragStart={canPick ? handleDragStart : undefined}
      onClick={canPick ? () => onPick(item.day, item.period) : undefined}
      disabled={!canPick}
      className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-right border transition
        ${urgent
          ? 'bg-white border-red-200 hover:border-red-400 hover:shadow-md'
          : 'bg-slate-50 border-slate-200 hover:border-[#2BB5A0] hover:bg-white'}
        ${canPick ? 'cursor-grab active:cursor-grabbing' : 'cursor-not-allowed opacity-70'}`}
      data-testid={`waiting-slot-${item.day}-${item.period}`}
    >
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-black text-xs shrink-0
        ${urgent ? 'bg-red-100 text-red-700' : 'bg-[#1C3D74]/10 text-[#1C3D74]'}`}>
        {item.period}
      </div>
      <div className="flex-1 min-w-0 text-right">
        <p className="text-xs font-bold text-slate-800 leading-tight">الحصة {item.period}</p>
        {item.start_time && (
          <p className="text-[10px] text-slate-500 font-mono leading-tight flex items-center gap-1 justify-start">
            <Clock className="h-2.5 w-2.5" />
            {item.start_time.substring(0, 5)}
            {item.end_time ? ` — ${item.end_time.substring(0, 5)}` : ''}
          </p>
        )}
      </div>
      {canPick && (
        <CalendarDays className="h-3.5 w-3.5 text-slate-300 shrink-0" />
      )}
    </button>
  );
}
