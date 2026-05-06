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
import { getDayTintClass } from './dayPalette';

export default function SessionCell({
  session,
  dayKey,
  onClick,
  isLocked = false,
  hasConflict = false,
  compact = true,
}) {
  const tint = getDayTintClass(dayKey);
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
    ? 'text-[11px] font-cairo font-bold leading-tight line-clamp-1 max-w-full truncate'
    : 'text-sm font-cairo font-bold line-clamp-2 max-w-full leading-snug';
  const classClass = compact
    ? 'text-[11px] font-tajawal font-medium opacity-85 leading-tight line-clamp-1 max-w-full truncate'
    : 'text-xs font-tajawal font-medium opacity-90 line-clamp-2 max-w-full leading-snug';
  const metaClass = compact
    ? 'text-[10px] font-tajawal opacity-60 leading-none line-clamp-1 max-w-full truncate'
    : 'text-[11px] font-tajawal opacity-70 leading-tight line-clamp-1 max-w-full truncate';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleActivate}
      onKeyDown={handleActivate}
      aria-label={ariaLabel}
      data-testid={`session-cell-${session?.id}`}
      className={`relative h-full ${containerSize} min-w-0 overflow-hidden rounded-md cursor-pointer ${tint} border border-white/60 text-brand-navy transition-all duration-200 ease-out hover:scale-[1.02] hover:shadow-md hover:z-10 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-1 motion-reduce:hover:scale-100 ${isLocked ? 'opacity-80' : ''}`}
    >
      {isLocked && (
        <Lock
          data-testid="session-cell-lock-icon"
          className="absolute top-0.5 start-0.5 h-2.5 w-2.5 text-brand-navy/60"
        />
      )}
      {hasConflict && (
        <AlertTriangle
          className="absolute top-0.5 end-0.5 h-2.5 w-2.5 text-red-500"
        />
      )}
      <div className="flex flex-col h-full justify-center items-center gap-0.5 text-center">
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
