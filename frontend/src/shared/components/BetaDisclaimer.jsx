import { useState } from 'react';
import { X, Wrench } from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';

const DISMISS_KEY = 'nassaq_beta_banner_dismissed_v1';

const readInitialVisibility = () => {
  if (typeof window === 'undefined') return false;
  try {
    return !window.localStorage.getItem(DISMISS_KEY);
  } catch {
    return true;
  }
};

export function BetaBanner() {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(readInitialVisibility);

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()));
    } catch {}
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="relative z-50 w-full bg-amber-50 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-800/60"
    >
      <div className="max-w-7xl mx-auto px-3 py-2 flex items-center gap-2 text-amber-900 dark:text-amber-200">
        <Wrench className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-300" aria-hidden="true" />
        <p className="text-xs sm:text-sm leading-snug flex-1">
          <span className="font-semibold">{t('betaBannerTitle')}</span>
          <span className="opacity-80"> — {t('betaBannerBody')}</span>
        </p>
        <button
          type="button"
          onClick={dismiss}
          aria-label={t('betaDismiss')}
          className="shrink-0 p-1 rounded-md hover:bg-amber-100 dark:hover:bg-amber-900/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function BetaBadge({ className = '' }) {
  const { t } = useTranslation();
  return (
    <span
      title={t('betaBadgeTooltip')}
      aria-label={t('betaBadgeTooltip')}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wide bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 border border-amber-200 dark:border-amber-800/60 ${className}`}
    >
      {t('betaBadgeLabel')}
    </span>
  );
}

export default BetaBanner;
