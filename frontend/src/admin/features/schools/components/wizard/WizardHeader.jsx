import React from 'react';
import { DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Badge } from '@/shared/components/ui/badge';
import { School, Layers, CheckCircle2 } from 'lucide-react';

export default function WizardHeader({
  steps,
  currentStep,
  onStepClick,
  isRTL,
}) {
  return (
    <DialogHeader className="px-6 py-5 border-b border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-[#1C3D74] flex items-center justify-center shadow-md shadow-[#1C3D74]/20 text-white">
            <School className="h-5 w-5 text-[#46C1BE]" />
          </div>
          <div>
            <DialogTitle className="font-cairo text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              {isRTL ? 'إنشاء مدرسة جديدة' : 'Create New School'}
            </DialogTitle>
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5">
              {isRTL ? 'إعداد وتهيئة مستأجر جديد في منظومة نَسَّق المدرسية' : 'Onboard a new school tenant in NASSAQ ecosystem'}
            </p>
          </div>
        </div>

        <Badge
          variant="outline"
          className="hidden sm:flex items-center gap-1.5 py-1 px-3 bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-800 dark:text-slate-200 rounded-full shadow-2xs"
        >
          <Layers className="h-3.5 w-3.5 text-[#46C1BE]" />
          <span>{isRTL ? `الخطوة ${currentStep} من 4` : `Step ${currentStep} of 4`}</span>
        </Badge>
      </div>

      {/* Progress Steps Indicator */}
      <div className="flex items-center justify-between max-w-3xl mx-auto w-full px-2 pt-2 pb-1">
        {steps.map((step, idx) => {
          const isActive = currentStep === step.number;
          const isPassed = currentStep > step.number;
          const Icon = step.icon;
          const isLast = idx === steps.length - 1;

          return (
            <React.Fragment key={step.number}>
              {/* Step Node */}
              <button
                type="button"
                disabled={!isPassed && !isActive}
                onClick={() => {
                  if (isPassed) onStepClick(step.number);
                }}
                className={`flex flex-col items-center group focus:outline-none z-10 shrink-0 ${
                  isPassed ? 'cursor-pointer' : 'cursor-default'
                }`}
              >
                <div
                  className={`w-11 h-11 rounded-2xl flex items-center justify-center transition-all duration-300 ${
                    isActive
                      ? 'bg-[#1C3D74] text-white ring-4 ring-[#46C1BE]/30 scale-105 shadow-lg shadow-[#1C3D74]/25'
                      : isPassed
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                      : 'bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-700 text-slate-400'
                  }`}
                >
                  {isPassed ? (
                    <CheckCircle2 className="h-5 w-5 text-white stroke-[2.5]" />
                  ) : (
                    <Icon className="h-5 w-5" />
                  )}
                </div>
                <span
                  className={`text-xs mt-2.5 transition-colors whitespace-nowrap ${
                    isActive
                      ? 'font-black text-[#1C3D74] dark:text-[#46C1BE]'
                      : isPassed
                      ? 'font-bold text-emerald-700 dark:text-emerald-400'
                      : 'font-bold text-slate-500 dark:text-slate-400'
                  }`}
                >
                  {step.title}
                </span>
              </button>

              {/* Segmented Connector Line */}
              {!isLast && (
                <div className="flex-1 mx-3 -mt-6 h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 ease-out rounded-full ${
                      currentStep > step.number ? 'w-full bg-emerald-500' : 'w-0 bg-transparent'
                    }`}
                  />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </DialogHeader>
  );
}
