import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { ChevronRight, ChevronLeft, Loader2 } from 'lucide-react';

export function StickyActionBar({
  isFirstStep,
  isLastStep,
  onNext,
  onPrev,
  onCancel,
  nextLabel = 'التالي',
  prevLabel = 'السابق',
  cancelLabel = 'إلغاء',
  loading = false,
  isRTL = true,
}) {
  const PrevIcon = isRTL ? ChevronRight : ChevronLeft;
  const NextIcon = isRTL ? ChevronLeft : ChevronRight;

  return (
    <div className="shrink-0 sticky bottom-0 bg-background/95 backdrop-blur-sm border-t pt-3 pb-2 px-1 z-10">
      <div className="flex items-center justify-between gap-3">
        <div>
          {!isFirstStep && (
            <Button
              type="button"
              variant="outline"
              onClick={onPrev}
              disabled={loading}
              className="gap-1"
            >
              <PrevIcon className="h-4 w-4" />
              {prevLabel}
            </Button>
          )}
          {isFirstStep && onCancel && (
            <Button
              type="button"
              variant="ghost"
              onClick={onCancel}
              disabled={loading}
            >
              {cancelLabel}
            </Button>
          )}
        </div>
        <Button
          type="button"
          onClick={onNext}
          disabled={loading}
          className={isLastStep ? 'bg-brand-navy hover:bg-brand-navy/90 gap-2' : 'gap-1'}
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" />}
          {nextLabel}
          {!isLastStep && <NextIcon className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
