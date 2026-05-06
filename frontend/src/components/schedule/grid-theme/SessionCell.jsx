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
  const ariaLabel = `${subject} · ${klass} · ${dayKey} · ${session?.slot_number ?? ''}`;

  // Daily view (compact = false) gives the cell more vertical room and lets
  // the subject / class wrap onto a second line. Weekly view keeps the dense
  // single-line look so the whole week still fits on screen.
  const containerSize = compact ? 'min-h-[50px] p-1' : 'min-h-[68px] p-2';
  const subjectClass = compact
    ? 'text-[10px] font-cairo font-semibold line-clamp-1 max-w-full truncate'
    : 'text-xs font-cairo font-semibold line-clamp-2 max-w-full leading-snug';
  const classClass = compact
    ? 'text-[9px] font-tajawal opacity-80 line-clamp-1 max-w-full truncate'
    : 'text-[11px] font-tajawal opacity-85 line-clamp-2 max-w-full leading-snug';

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
        <span className={subjectClass}>
          {subject}
        </span>
        <span className={classClass}>
          {klass}
        </span>
      </div>
    </div>
  );
}
