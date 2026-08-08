import React from 'react';
import { Loader2 } from 'lucide-react';
import { useTheme } from '@/shared/contexts/ThemeContext';

/**
 * Tiny pill rendered while a background re-fetch is in flight on top of
 * cached child-scoped data (Task #149). Lets the parent see that fresh data
 * is loading without flashing a full skeleton over the previous result.
 */
const BackgroundRefreshChip = ({ visible }) => {
  const { isRTL } = useTheme();
  if (!visible) return null;
  return (
    <div
      className="pointer-events-none flex items-center justify-center print:hidden"
      data-testid="background-refresh-chip"
      aria-live="polite"
    >
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-brand-navy/10 text-brand-navy dark:bg-brand-navy-dark/40 dark:text-brand-navy-light text-[11px] font-medium">
        <Loader2 className="h-3 w-3 animate-spin" />
        {isRTL ? 'جارٍ التحديث…' : 'Refreshing…'}
      </span>
    </div>
  );
};

export default BackgroundRefreshChip;
