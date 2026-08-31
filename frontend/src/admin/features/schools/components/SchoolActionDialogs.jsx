import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { AlertTriangle, CheckCircle2, Loader2, Pause, Play, ShieldAlert } from 'lucide-react';

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
        <DialogContent className="rounded-3xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border border-slate-200 dark:border-slate-800 max-w-md shadow-2xl p-6 font-cairo z-50">
          <DialogHeader>
            <div className="w-12 h-12 rounded-2xl bg-rose-500/15 text-rose-600 dark:text-rose-400 flex items-center justify-center mb-2 border border-rose-500/20">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <DialogTitle className="font-cairo text-lg font-black text-rose-600 dark:text-rose-400">
              {isRTL ? 'إيقاف حساب المدرسة والمستأجر' : 'Suspend School Tenant'}
            </DialogTitle>
            <DialogDescription className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1.5 leading-relaxed">
              {isRTL
                ? `سيتم إيقاف وصول جميع منسوبي وإداريي مدرسة "${suspendDialogSchool?.name}" للنظام بشكل فوري مؤقتاً.`
                : `This will immediately suspend system access for all staff of "${suspendDialogSchool?.name}".`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-3 font-tajawal">
            <label className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
              {isRTL ? 'سبب الإيقاف المؤقت (اختياري)' : 'Suspension Reason (Optional)'}
            </label>
            <Textarea
              value={actionReason}
              onChange={(e) => onChangeActionReason(e.target.value)}
              placeholder={isRTL ? 'اكتب سبب الإيقاف أو الملاحظات الإدارية...' : 'Enter reason for suspension...'}
              className="rounded-2xl text-xs bg-slate-50 dark:bg-slate-950 font-medium min-h-[95px] border-slate-200 dark:border-slate-800 focus:ring-2 focus:ring-rose-500/20"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={onCloseSuspendDialog}
              className="rounded-2xl text-xs font-bold border-slate-300 dark:border-slate-700 h-10 px-4"
            >
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={onConfirmSuspend}
              disabled={actionLoading}
              className="rounded-2xl text-xs font-black bg-rose-600 hover:bg-rose-700 text-white shadow-lg shadow-rose-600/25 gap-2 h-10 px-5"
            >
              {actionLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Pause className="h-4 w-4" />
              )}
              <span>{isRTL ? 'إيقاف الحساب' : 'Suspend Account'}</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Activate Confirmation Dialog */}
      <Dialog open={!!activateDialogSchool} onOpenChange={onCloseActivateDialog}>
        <DialogContent className="rounded-3xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border border-slate-200 dark:border-slate-800 max-w-md shadow-2xl p-6 font-cairo z-50">
          <DialogHeader>
            <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-2 border border-emerald-500/20">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <DialogTitle className="font-cairo text-lg font-black text-emerald-600 dark:text-emerald-400">
              {isRTL ? 'تفعيل حساب المدرسة' : 'Activate School'}
            </DialogTitle>
            <DialogDescription className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1.5 leading-relaxed">
              {isRTL
                ? `سيتم إعادة تفعيل صلاحيات مدرسة "${activateDialogSchool?.name}" وإتاحة تسجيل الدخول لجميع منسوبيها فوراً.`
                : `This will reactivate access for "${activateDialogSchool?.name}" and restore login permissions.`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-3 font-tajawal">
            <label className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
              {isRTL ? 'ملاحظة التفعيل (اختياري)' : 'Activation Note (Optional)'}
            </label>
            <Textarea
              value={actionReason}
              onChange={(e) => onChangeActionReason(e.target.value)}
              placeholder={isRTL ? 'اكتب ملاحظة التفعيل...' : 'Enter activation notes...'}
              className="rounded-2xl text-xs bg-slate-50 dark:bg-slate-950 font-medium min-h-[95px] border-slate-200 dark:border-slate-800 focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="outline"
              onClick={onCloseActivateDialog}
              className="rounded-2xl text-xs font-bold border-slate-300 dark:border-slate-700 h-10 px-4"
            >
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={onConfirmActivate}
              disabled={actionLoading}
              className="rounded-2xl text-xs font-black bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg shadow-emerald-600/25 gap-2 h-10 px-5"
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
