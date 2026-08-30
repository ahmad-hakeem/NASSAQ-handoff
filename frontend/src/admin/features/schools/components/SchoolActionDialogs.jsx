import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { AlertTriangle, CheckCircle2, Loader2, Pause, Play } from 'lucide-react';

export default function SchoolActionDialogs({
  suspendDialogSchool,
  onCloseSuspendDialog,
  onConfirmSuspend,
  activateDialogSchool,
  onCloseActivateDialog,
  onConfirmActivate,
  actionReason,
  onChangeActionReason,
  actionLoading,
  isRTL,
}) {
  return (
    <>
      {/* Suspend Confirmation Dialog */}
      <Dialog open={!!suspendDialogSchool} onOpenChange={onCloseSuspendDialog}>
        <DialogContent className="rounded-3xl bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 max-w-md shadow-2xl p-6 font-cairo">
          <DialogHeader>
            <DialogTitle className="font-cairo text-lg font-black text-rose-600 dark:text-rose-400 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              <span>{isRTL ? 'إيقاف حساب المدرسة' : 'Suspend School'}</span>
            </DialogTitle>
            <DialogDescription className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1.5">
              {isRTL
                ? `سيتم إيقاف وصول منسوبي مدرسة "${suspendDialogSchool?.name}" للنظام مؤقتاً.`
                : `This will suspend access for all users of "${suspendDialogSchool?.name}".`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-3">
            <label className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
              {isRTL ? 'سبب الإيقاف (مطلوب)' : 'Suspension Reason (Required)'}
            </label>
            <Textarea
              value={actionReason}
              onChange={(e) => onChangeActionReason(e.target.value)}
              placeholder={isRTL ? 'اكتب سبب الإيقاف هنا...' : 'Enter reason for suspension...'}
              className="rounded-xl text-xs bg-slate-50 dark:bg-slate-950 font-medium min-h-[90px] border-slate-300 dark:border-slate-700 focus:ring-2 focus:ring-rose-500/20"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={onCloseSuspendDialog}
              className="rounded-xl text-xs font-bold border-slate-300 dark:border-slate-700"
            >
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={onConfirmSuspend}
              disabled={actionLoading || !actionReason.trim()}
              className="rounded-xl text-xs font-extrabold bg-rose-600 hover:bg-rose-700 text-white shadow-md shadow-rose-600/20 gap-1.5"
            >
              {actionLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Pause className="h-4 w-4" />
              )}
              <span>{isRTL ? 'تأكيد الإيقاف' : 'Confirm Suspend'}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Activate Confirmation Dialog */}
      <Dialog open={!!activateDialogSchool} onOpenChange={onCloseActivateDialog}>
        <DialogContent className="rounded-3xl bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 max-w-md shadow-2xl p-6 font-cairo">
          <DialogHeader>
            <DialogTitle className="font-cairo text-lg font-black text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5" />
              <span>{isRTL ? 'تفعيل حساب المدرسة' : 'Activate School'}</span>
            </DialogTitle>
            <DialogDescription className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1.5">
              {isRTL
                ? `سيتم إعادة تفعيل صلاحيات مدرسة "${activateDialogSchool?.name}" وإتاحة الوصول للنظام فوراً.`
                : `This will reactivate access for "${activateDialogSchool?.name}".`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-3">
            <label className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
              {isRTL ? 'ملاحظة التفعيل (مطلوب)' : 'Activation Note (Required)'}
            </label>
            <Textarea
              value={actionReason}
              onChange={(e) => onChangeActionReason(e.target.value)}
              placeholder={isRTL ? 'اكتب ملاحظة التفعيل هنا...' : 'Enter activation notes...'}
              className="rounded-xl text-xs bg-slate-50 dark:bg-slate-950 font-medium min-h-[90px] border-slate-300 dark:border-slate-700 focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={onCloseActivateDialog}
              className="rounded-xl text-xs font-bold border-slate-300 dark:border-slate-700"
            >
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={onConfirmActivate}
              disabled={actionLoading || !actionReason.trim()}
              className="rounded-xl text-xs font-extrabold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20 gap-1.5"
            >
              {actionLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              <span>{isRTL ? 'تأكيد التفعيل' : 'Confirm Activate'}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
