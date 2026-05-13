import { useEffect, useState, useLayoutEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { useAuth } from '../../../contexts/AuthContext';
import { useTranslation } from '../../../contexts/ThemeContext';
import { Button } from '../../ui/button';
import { ChevronLeft, ChevronRight, X, Sparkles } from 'lucide-react';
import { TOUR_STEPS } from './steps';

const PADDING = 8;

function useTargetRect(selector) {
  const [rect, setRect] = useState(null);
  useLayoutEffect(() => {
    if (!selector) { setRect(null); return undefined; }
    const measure = () => {
      const el = document.querySelector(selector);
      if (!el) { setRect(null); return; }
      try { el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }); } catch (e) { /* old browsers */ }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(document.body);
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    const t = setTimeout(measure, 80);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
      clearTimeout(t);
    };
  }, [selector]);
  return rect;
}

export function OnboardingTour({ open, onFinish, onSkip }) {
  const { t } = useTranslation();
  const { isRTL } = useAuth();
  const [index, setIndex] = useState(0);
  const step = TOUR_STEPS[index];
  const rect = useTargetRect(open ? step?.target : null);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onSkip?.();
      else if (e.key === 'ArrowRight') (isRTL ? prev : next)();
      else if (e.key === 'ArrowLeft') (isRTL ? next : prev)();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, index, isRTL]);

  const next = useCallback(() => {
    if (index >= TOUR_STEPS.length - 1) onFinish?.();
    else setIndex((i) => i + 1);
  }, [index, onFinish]);

  const prev = useCallback(() => {
    setIndex((i) => Math.max(0, i - 1));
  }, []);

  if (!open) return null;

  const targetVisible = !!rect;
  const vw = typeof window !== 'undefined' ? window.innerWidth : 1024;
  const vh = typeof window !== 'undefined' ? window.innerHeight : 768;

  let tipStyle;
  const tipWidth = Math.min(380, vw - 32);
  if (targetVisible) {
    const spaceBelow = vh - (rect.top + rect.height);
    const above = spaceBelow < 220 && rect.top > 240;
    const top = above ? Math.max(16, rect.top - PADDING - 220) : rect.top + rect.height + PADDING;
    let left = rect.left + rect.width / 2 - tipWidth / 2;
    left = Math.max(16, Math.min(vw - tipWidth - 16, left));
    tipStyle = { top, left, width: tipWidth };
  } else {
    tipStyle = { top: vh / 2 - 110, left: vw / 2 - tipWidth / 2, width: tipWidth };
  }

  const node = (
    <div
      className="fixed inset-0 z-[9999]"
      dir={isRTL ? 'rtl' : 'ltr'}
      data-testid="it-onboarding-tour"
      role="dialog"
      aria-modal="true"
    >
      {/* Spotlight overlay using SVG mask */}
      <svg className="absolute inset-0 w-full h-full pointer-events-auto" onClick={onSkip}>
        <defs>
          <mask id="nassaq-tour-mask">
            <rect width="100%" height="100%" fill="white" />
            {targetVisible && (
              <rect
                x={Math.max(0, rect.left - 6)}
                y={Math.max(0, rect.top - 6)}
                width={rect.width + 12}
                height={rect.height + 12}
                rx="12"
                ry="12"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(2, 6, 23, 0.62)"
          mask="url(#nassaq-tour-mask)"
        />
      </svg>

      {targetVisible && (
        <div
          className="absolute pointer-events-none rounded-xl ring-2 ring-brand-turquoise shadow-[0_0_0_4px_rgba(20,184,166,0.25)]"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
          }}
        />
      )}

      <div
        className="absolute bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-border p-5 pointer-events-auto"
        style={tipStyle}
        onClick={(e) => e.stopPropagation()}
        data-testid="it-onboarding-tour-card"
      >
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-turquoise/15 flex items-center justify-center">
              <Sparkles className="h-4 w-4 text-brand-turquoise" />
            </div>
            <div>
              <p className="font-cairo font-bold text-base text-foreground leading-tight">
                {t(step.titleKey)}
              </p>
              <p className="text-[11px] text-muted-foreground font-tajawal">
                {t('itTourStepCounter')
                  .replace('{0}', String(index + 1))
                  .replace('{1}', String(TOUR_STEPS.length))}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground p-1 rounded"
            onClick={onSkip}
            aria-label={t('itTourSkip')}
            data-testid="it-onboarding-tour-skip"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-sm text-muted-foreground font-tajawal leading-relaxed mb-4">
          {t(step.bodyKey)}
        </p>

        <div className="flex items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={prev}
            disabled={index === 0}
            className="rounded-xl font-tajawal text-xs"
            data-testid="it-onboarding-tour-back"
          >
            {isRTL ? <ChevronRight className="h-4 w-4 me-1" /> : <ChevronLeft className="h-4 w-4 me-1" />}
            {t('itTourBack')}
          </Button>

          <div className="flex items-center gap-1">
            {TOUR_STEPS.map((s, i) => (
              <span
                key={s.id}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === index ? 'bg-brand-turquoise w-3' : 'bg-muted-foreground/30'
                }`}
              />
            ))}
          </div>

          <Button
            size="sm"
            onClick={next}
            className="rounded-xl bg-brand-turquoise hover:bg-brand-turquoise/90 text-white font-tajawal text-xs"
            data-testid="it-onboarding-tour-next"
          >
            {index >= TOUR_STEPS.length - 1 ? t('itTourFinish') : t('itTourNext')}
            {isRTL ? <ChevronLeft className="h-4 w-4 ms-1" /> : <ChevronRight className="h-4 w-4 ms-1" />}
          </Button>
        </div>
      </div>
    </div>
  );

  return ReactDOM.createPortal(node, document.body);
}

export default OnboardingTour;
