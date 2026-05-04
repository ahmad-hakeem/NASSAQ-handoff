/**
 * DayHeaderBand — colored day name band + numbered period sub-row.
 *
 * Renders a single day group: a strong colored band (day name in white,
 * Cairo 700) stacked above small per-period number cells tinted in the
 * day's lighter shade.
 *
 * Props:
 *   dayKey       — 'sunday' | 'monday' | ...
 *   dayLabel     — translated day name to display
 *   timeSlots    — array of slot objects { start_time, is_break, ... }
 *   slotWidthPx  — width of one period column in pixels (default 60)
 */
import React from 'react';
import { Coffee } from 'lucide-react';
import {
  getDayBandClass,
  getDayTintClass,
  getDayTextOnBand,
} from './dayPalette';

export default function DayHeaderBand({ dayKey, dayLabel, timeSlots, slotWidthPx = 60 }) {
  const bandClass = getDayBandClass(dayKey);
  const tintClass = getDayTintClass(dayKey);
  const textClass = getDayTextOnBand(dayKey);
  const totalWidth = (timeSlots?.length || 0) * slotWidthPx;

  return (
    <div className="flex-shrink-0" style={{ width: `${totalWidth}px` }}>
      <div
        className={`${bandClass} ${textClass} px-2 py-1.5 text-center font-cairo font-bold text-sm border-e border-white/20`}
        data-testid={`day-band-${dayKey}`}
      >
        {dayLabel}
      </div>
      <div className={`flex ${tintClass} border-e border-border/30`}>
        {(timeSlots || []).map((slot, idx) => (
          <div
            key={`${dayKey}-period-${idx}`}
            className="text-center border-e border-white/40 last:border-e-0 py-1"
            style={{ width: `${slotWidthPx}px` }}
            data-testid={`day-period-${dayKey}-${idx}`}
          >
            {slot.is_break ? (
              <Coffee className="h-3 w-3 text-amber-600 mx-auto" aria-label="break" />
            ) : (
              <>
                <p className="text-[10px] font-tajawal font-semibold text-foreground/80">{idx + 1}</p>
                <p className="text-[8px] text-foreground/55 font-tajawal">{slot.start_time}</p>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
