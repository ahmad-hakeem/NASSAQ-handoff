import {
  DAY_PALETTE,
  getDayTintClass,
  getDayBandClass,
  getDayTextOnBand,
  getDayKeys,
} from '../grid-theme/dayPalette';

describe('dayPalette', () => {
  it('exposes the five school days in week order', () => {
    expect(getDayKeys()).toEqual(['sunday', 'monday', 'tuesday', 'wednesday', 'thursday']);
  });

  it('returns a Tailwind tint class for each day', () => {
    expect(getDayTintClass('sunday')).toBe('bg-[hsl(var(--day-sun-tint))]');
    expect(getDayTintClass('monday')).toBe('bg-[hsl(var(--day-mon-tint))]');
    expect(getDayTintClass('tuesday')).toBe('bg-[hsl(var(--day-tue-tint))]');
    expect(getDayTintClass('wednesday')).toBe('bg-[hsl(var(--day-wed-tint))]');
    expect(getDayTintClass('thursday')).toBe('bg-[hsl(var(--day-thu-tint))]');
  });

  it('returns a Tailwind band class for each day', () => {
    expect(getDayBandClass('sunday')).toBe('bg-[hsl(var(--day-sun-band))]');
    expect(getDayBandClass('thursday')).toBe('bg-[hsl(var(--day-thu-band))]');
  });

  it('text-on-band is white for every day', () => {
    getDayKeys().forEach((day) => {
      expect(getDayTextOnBand(day)).toBe('text-white');
    });
  });

  it('falls back to a neutral tint when day key is unknown', () => {
    expect(getDayTintClass('saturday')).toBe('bg-muted/40');
    expect(getDayBandClass('saturday')).toBe('bg-muted');
  });

  it('DAY_PALETTE entries each carry tintClass and bandClass', () => {
    Object.values(DAY_PALETTE).forEach((entry) => {
      expect(entry).toHaveProperty('tintClass');
      expect(entry).toHaveProperty('bandClass');
    });
  });
});
