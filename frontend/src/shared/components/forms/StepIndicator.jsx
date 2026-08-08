import React from 'react';
import { Check } from 'lucide-react';

export function StepIndicator({ steps, currentStep, completedSteps = {}, onStepClick, isRTL = true }) {
  if (!steps || steps.length <= 1) return null;

  return (
    <div className="shrink-0 px-2 mb-4">
      <div className="flex items-center justify-center gap-0">
        {steps.map((step, index) => {
          const isActive = index === currentStep;
          const isCompleted = completedSteps[index] || index < currentStep;
          const isClickable = index < currentStep || completedSteps[index - 1] || index === 0;
          const StepIcon = step.icon;

          return (
            <React.Fragment key={index}>
              {index > 0 && (
                <div className={`h-0.5 w-8 sm:w-12 transition-colors ${
                  isCompleted ? 'bg-brand-turquoise' : 'bg-muted'
                }`} />
              )}
              <button
                type="button"
                onClick={() => isClickable && onStepClick?.(index)}
                disabled={!isClickable}
                className={`flex flex-col items-center gap-1 transition-all ${
                  isClickable ? 'cursor-pointer' : 'cursor-not-allowed opacity-50'
                }`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all ${
                  isActive
                    ? 'bg-brand-navy text-white ring-4 ring-brand-navy/20 scale-110'
                    : isCompleted
                    ? 'bg-brand-turquoise text-white'
                    : 'bg-muted text-muted-foreground'
                }`}>
                  {isCompleted && !isActive ? (
                    <Check className="h-4 w-4" />
                  ) : StepIcon ? (
                    <StepIcon className="h-4 w-4" />
                  ) : (
                    index + 1
                  )}
                </div>
                <span className={`text-[10px] sm:text-xs font-cairo max-w-[60px] sm:max-w-[80px] text-center leading-tight ${
                  isActive ? 'text-brand-navy font-bold' : 'text-muted-foreground'
                }`}>
                  {step.title}
                </span>
              </button>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
