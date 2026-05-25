/**
 * SessionCell — day-tinted, click-to-open session cell.
 *
 * Replaces the visual default branch of FilledCell. Special states
 * (vacant / substituted / relocated) keep their existing renderers in
 * FilledCell.jsx; SessionCell is the canonical "filled, normal" cell.
 *
 * Props:
 *   session       — { id, subject_name, class_name, day_of_week, slot_number, start_time, end_time, ... }
 *   dayKey        — day key for color tint
 *   onClick(session) — invoked on click / Enter / Space
 *   isLocked      — show lock icon, dim slightly
 *   hasConflict   — show conflict icon
 */
import React from 'react';
import { Lock, AlertTriangle } from 'lucide-react';
import { getDayTintClass, getDayBandClass } from './dayPalette';

export default function SessionCell({
  session,
  dayKey,
  onClick,
  isLocked = false,
  hasConflict = false,
  compact = true,
}) {
  const tint = getDayTintClass(dayKey);
  const band = getDayBandClass(dayKey);
  const handleActivate = (e) => {
    if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault?.();
    onClick?.(session);
  };
  const subject = session?.subject_name || '';
  const klass = session?.class_name || '—';
  // Tertiary meta line — slot/period number gives the operator a third
  // anchor (subject → class → meta) so they can locate the lesson on the
  // timetable without hovering for the tooltip. We prefer the explicit
  // start_time when the backend ships it; otherwise we fall back to the
  // human "الحصة N" label using slot_number.
  const slot = session?.slot_number ?? session?.period_number;
  const meta = session?.start_time
    ? session.start_time
    : (slot != null ? `#${slot}` : '');
  const ariaLabel = `${subject} · ${klass} · ${dayKey} · ${slot ?? ''}`;

  // Task #142 — readable typography in BOTH modes:
  // weekly (compact = true) uses 11px primary + 11px secondary + 10px
  // meta, daily (compact = false) opens up to text-sm + text-xs.
  // Operators must be able to read every cell at a glance without
  // hovering; the previous 9–10px sizes failed the at-a-glance test.
  const containerSize = compact ? 'min-h-[60px] p-1.5' : 'min-h-[76px] p-2.5';
  const subjectClass = compact
    ? 'text-[11px] font-cairo font-bold leading-tight tracking-tight line-clamp-1 max-w-full truncate text-brand-navy'
    : 'text-sm font-cairo font-bold leading-snug tracking-tight line-clamp-2 max-w-full text-brand-navy';
  const classClass = compact
    ? 'text-[11px] font-tajawal font-medium leading-tight line-clamp-1 max-w-full truncate text-brand-navy/70'
    : 'text-xs font-tajawal font-medium leading-snug line-clamp-2 max-w-full text-brand-navy/75';
  const metaClass = compact
    ? 'text-[10px] font-tajawal tabular-nums leading-none line-clamp-1 max-w-full truncate text-brand-navy/55'
    : 'text-[11px] font-tajawal tabular-nums leading-tight line-clamp-1 max-w-full truncate text-brand-navy/60';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleActivate}
      onKeyDown={handleActivate}
      aria-label={ariaLabel}
      data-testid={`session-cell-${session?.id}`}
      className={`group relative h-full ${containerSize} min-w-0 overflow-hidden rounded-lg cursor-pointer bg-white border border-slate-200/80 shadow-[0_1px_2px_rgba(15,42,75,0.06),0_1px_3px_rgba(15,42,75,0.04)] transition-[transform,box-shadow] duration-200 ease-out hover:-translate-y-0.5 hover:shadow-[0_8px_18px_rgba(15,42,75,0.14)] hover:border-slate-300 hover:z-10 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-1 motion-reduce:hover:translate-y-0 ${isLocked ? 'opacity-80' : ''}`}
    >
      {/* Day-band colored top stripe — preserves the day-color signal
          (matches the sticky day-band header) while the card body
          stays a crisp white "tile" instead of a flat tinted square. */}
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute inset-x-0 top-0 h-[3px] ${band}`}
      />
      {/* Day-tint echo at the bottom — very faint, repeats the day
          color so weekly mode still scans by color at a glance. */}
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute inset-x-0 bottom-0 h-1/3 opacity-50 ${tint}`}
      />
      {isLocked && (
        <Lock
          data-testid="session-cell-lock-icon"
          className="absolute top-1 start-1 h-2.5 w-2.5 text-brand-navy/60 z-[1]"
          strokeWidth={1.5}
          aria-hidden="true"
        />
      )}
      {hasConflict && (
        <AlertTriangle
          className="absolute top-1 end-1 h-2.5 w-2.5 text-red-500 z-[1]"
          strokeWidth={1.5}
          aria-hidden="true"
        />
      )}
      <div className="relative flex flex-col h-full justify-center items-center gap-0.5 text-center">
        <span className={subjectClass} data-testid="session-cell-subject">
          {subject}
        </span>
        <span className={classClass} data-testid="session-cell-class">
          {klass}
        </span>
        {meta && (
          <span className={metaClass} data-testid="session-cell-meta">
            {meta}
          </span>
        )}
      </div>
    </div>
  );
}
