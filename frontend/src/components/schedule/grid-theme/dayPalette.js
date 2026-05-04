/**
 * Single source of truth for schedule grid day colors.
 *
 * Tokens are defined as HSL CSS variables in `frontend/src/index.css`
 * (`--day-*-tint` / `--day-*-band`). Tailwind arbitrary-value classes wrap
 * those vars so consumers never hardcode a hex value.
 */

export const DAY_PALETTE = {
  sunday:    { tintClass: 'bg-[hsl(var(--day-sun-tint))]', bandClass: 'bg-[hsl(var(--day-sun-band))]', textOnBand: 'text-white' },
  monday:    { tintClass: 'bg-[hsl(var(--day-mon-tint))]', bandClass: 'bg-[hsl(var(--day-mon-band))]', textOnBand: 'text-white' },
  tuesday:   { tintClass: 'bg-[hsl(var(--day-tue-tint))]', bandClass: 'bg-[hsl(var(--day-tue-band))]', textOnBand: 'text-white' },
  wednesday: { tintClass: 'bg-[hsl(var(--day-wed-tint))]', bandClass: 'bg-[hsl(var(--day-wed-band))]', textOnBand: 'text-white' },
  thursday:  { tintClass: 'bg-[hsl(var(--day-thu-tint))]', bandClass: 'bg-[hsl(var(--day-thu-band))]', textOnBand: 'text-white' },
};

const FALLBACK = { tintClass: 'bg-muted/40', bandClass: 'bg-muted', textOnBand: 'text-foreground' };

export const getDayKeys = () => ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

export const getDayPalette = (dayKey) => DAY_PALETTE[dayKey] || FALLBACK;

export const getDayTintClass = (dayKey) => getDayPalette(dayKey).tintClass;
export const getDayBandClass = (dayKey) => getDayPalette(dayKey).bandClass;
export const getDayTextOnBand = (dayKey) => getDayPalette(dayKey).textOnBand;
