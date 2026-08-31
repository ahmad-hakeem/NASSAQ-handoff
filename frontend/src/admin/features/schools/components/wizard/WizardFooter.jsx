import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  X, Save, ChevronRight, ChevronLeft, CheckCircle2, Loader2
} from 'lucide-react';

export default function WizardFooter({
  currentStep,
  onClose,
  onSaveAsDraft,
  onPrevious,
  onNext,
  onCreateSchool,
  isSubmitting,
  isRTL,
  draftSchool = null,
}) {
  return (
    <div className="px-6 py-4 md:px-8 border-t border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 flex-shrink-0">
      <div className="flex items-center justify-between">
        {/* Left Side: Cancel & Draft */}
        <div className="flex items-center gap-2.5">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            data-testid="cancel-btn"
            className="h-10 px-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white hover:bg-rose-50 dark:bg-slate-800 dark:hover:bg-rose-950/40 text-slate-600 hover:text-rose-600 dark:text-slate-300 dark:hover:text-rose-400 text-xs font-bold shadow-2xs gap-1.5 transition-all"
          >
            <X className="h-4 w-4" />
            <span>{isRTL ? 'إلغاء' : 'Cancel'}</span>
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={onSaveAsDraft}
            disabled={isSubmitting}
            data-testid="save-draft-btn"
            className="h-10 px-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white hover:bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-bold shadow-2xs gap-2 transition-all"
          >
            <Save className="h-4 w-4 text-slate-400" />
            <span>{isRTL ? (draftSchool ? 'حفظ التعديلات كمسودة' : 'حفظ كمسودة') : (draftSchool ? 'Save Draft' : 'Save Draft')}</span>
          </Button>
        </div>

        {/* Right Side: Back & Next / Create */}
        <div className="flex items-center gap-2.5">
          {currentStep > 1 && (
            <Button
              type="button"
              variant="outline"
              onClick={onPrevious}
              data-testid="back-btn"
              className="h-10 px-5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white hover:bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-bold gap-1.5 transition-all"
            >
              {isRTL ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
              <span>{isRTL ? 'السابق' : 'Back'}</span>
            </Button>
          )}

          {currentStep < 4 ? (
            <Button
              type="button"
              onClick={onNext}
              className="h-10 px-7 rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white text-xs font-extrabold shadow-md shadow-[#1C3D74]/20 gap-1.5 transition-all"
              data-testid="next-btn"
            >
              <span>{isRTL ? 'التالي' : 'Next'}</span>
              {isRTL ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
          ) : (
            <Button
              type="button"
              onClick={onCreateSchool}
              disabled={isSubmitting}
              className="h-10 px-7 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-extrabold shadow-lg shadow-emerald-600/25 gap-1.5 transition-all"
              data-testid="create-school-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{isRTL ? (draftSchool ? 'جاري الاعتماد...' : 'جاري الإنشاء...') : (draftSchool ? 'Finalizing...' : 'Creating...')}</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{isRTL ? (draftSchool ? 'اعتماد وإنشاء المدرسة' : 'إنشاء المدرسة') : (draftSchool ? 'Finalize & Create' : 'Create School')}</span>
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
