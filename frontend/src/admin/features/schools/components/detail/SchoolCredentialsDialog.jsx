import React from 'react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Key, Mail, Lock, Sparkles, Eye, EyeOff, Loader2, Save, User, ShieldCheck } from 'lucide-react';

export default function SchoolCredentialsDialog({
  open,
  onOpenChange,
  hasCredentials,
  credForm,
  setCredForm,
  showPassword,
  setShowPassword,
  onGeneratePassword,
  onSaveCredentials,
  credLoading,
  isRTL,
  t,
}) {
  const isPasswordMismatch = credForm.password && credForm.confirmPassword && credForm.password !== credForm.confirmPassword;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) setShowPassword(false);
      }}
    >
      <DialogContent className="max-w-lg rounded-3xl bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 shadow-2xl p-6 sm:p-7 font-cairo" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader className="space-y-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#1C3D74]/10 dark:bg-[#46C1BE]/10 text-[#1C3D74] dark:text-[#46C1BE] flex items-center justify-center shrink-0">
              <Key className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="font-cairo text-lg font-black text-slate-900 dark:text-white">
                {hasCredentials
                  ? (t('updateSchoolLoginCredentials') || (isRTL ? 'تحديث بيانات دخول مدير المدرسة' : 'Update Principal Credentials'))
                  : (t('createSchoolPrincipalAccount') || (isRTL ? 'إنشاء حساب رسمي لمدير المدرسة' : 'Create Principal Account'))
                }
              </DialogTitle>
              <DialogDescription className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-0.5">
                {hasCredentials
                  ? (t('updateTheEmailAndorPasswordForTheSchoolPrincipalAc') || (isRTL ? 'قم بتحديث البريد الإلكتروني أو تعيين كلمة مرور جديدة للمدير' : 'Update the email and/or password for the school principal account'))
                  : (t('createANewAccountForTheSchoolPrincipalToAccessTheS') || (isRTL ? 'إنشاء حساب بصلاحيات المدير لتمكينه من إدارة النظام المدرسي' : 'Create a new account for the school principal to access the system'))
                }
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-3">
          {/* Email Address */}
          <div className="space-y-1.5">
            <Label className="text-xs font-bold text-slate-700 dark:text-slate-200">
              {isRTL ? 'البريد الإلكتروني الرسمي' : 'Official Email Address'} <span className="text-rose-500">*</span>
            </Label>
            <div className="relative">
              <Mail className={`absolute ${isRTL ? 'right-3.5' : 'left-3.5'} top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400`} />
              <Input
                type="email"
                dir="ltr"
                placeholder="principal@school.edu.sa"
                value={credForm.email}
                onChange={(e) => setCredForm(f => ({ ...f, email: e.target.value }))}
                className={`${isRTL ? 'pr-10' : 'pl-10'} h-11 rounded-xl font-mono text-xs bg-slate-50/80 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]`}
              />
            </div>
          </div>

          {/* Principal Full Name */}
          <div className="space-y-1.5">
            <Label className="text-xs font-bold text-slate-700 dark:text-slate-200">
              {t('fullName') || (isRTL ? 'اسم مدير المدرسة' : 'Principal Full Name')}
            </Label>
            <div className="relative">
              <User className={`absolute ${isRTL ? 'right-3.5' : 'left-3.5'} top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400`} />
              <Input
                placeholder={t('principalFullName') || (isRTL ? 'مثال: أ. عبدالله محمد الفهد' : 'e.g. John Doe')}
                value={credForm.name}
                onChange={(e) => setCredForm(f => ({ ...f, name: e.target.value }))}
                className={`${isRTL ? 'pr-10' : 'pl-10'} h-11 rounded-xl text-xs bg-slate-50/80 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]`}
              />
            </div>
          </div>

          {/* Password with Generator */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold text-slate-700 dark:text-slate-200">
                {hasCredentials
                  ? (t('newPasswordLeaveBlankToKeepCurrent') || (isRTL ? 'كلمة المرور الجديدة (اتركها فارغة للإبقاء على الحالية)' : 'New Password (leave blank to keep current)'))
                  : (t('password') || (isRTL ? 'كلمة المرور' : 'Password'))
                }
              </Label>
              <button
                type="button"
                onClick={onGeneratePassword}
                className="text-xs font-bold text-[#46C1BE] hover:text-[#38a19e] hover:underline flex items-center gap-1 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>{t('generate') || (isRTL ? 'توليد كلمة سر قوية' : 'Generate Secure Password')}</span>
              </button>
            </div>
            <div className="relative">
              <Lock className={`absolute ${isRTL ? 'right-3.5' : 'left-3.5'} top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400`} />
              <Input
                type={showPassword ? 'text' : 'password'}
                dir="ltr"
                placeholder={isRTL ? '••••••••••••' : '••••••••••••'}
                value={credForm.password}
                onChange={(e) => setCredForm(f => ({ ...f, password: e.target.value }))}
                className={`${isRTL ? 'pr-10 pl-10' : 'pl-10 pr-10'} h-11 rounded-xl font-mono text-xs tracking-wider bg-slate-50/80 dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(s => !s)}
                className={`absolute ${isRTL ? 'left-3' : 'right-3'} top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1`}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Confirm Password (only if entered) */}
          {credForm.password && (
            <div className="space-y-1.5 animate-in fade-in-30 duration-200">
              <Label className="text-xs font-bold text-slate-700 dark:text-slate-200">
                {t('confirmPassword') || (isRTL ? 'تأكيد كلمة المرور' : 'Confirm Password')} <span className="text-rose-500">*</span>
              </Label>
              <div className="relative">
                <Lock className={`absolute ${isRTL ? 'right-3.5' : 'left-3.5'} top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400`} />
                <Input
                  type={showPassword ? 'text' : 'password'}
                  dir="ltr"
                  placeholder={t('reenterPassword') || (isRTL ? 'أعد إدخال كلمة المرور' : 'Re-enter password')}
                  value={credForm.confirmPassword}
                  onChange={(e) => setCredForm(f => ({ ...f, confirmPassword: e.target.value }))}
                  className={`${isRTL ? 'pr-10' : 'pl-10'} h-11 rounded-xl font-mono text-xs tracking-wider bg-slate-50/80 dark:bg-slate-950 ${
                    isPasswordMismatch
                      ? 'border-rose-400 focus:ring-rose-300 text-rose-600'
                      : 'border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white'
                  }`}
                />
              </div>
              {isPasswordMismatch && (
                <p className="text-xs text-rose-500 font-bold">{t('passwordsDoNotMatch') || (isRTL ? 'كلمات المرور غير متطابقة' : 'Passwords do not match')}</p>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={credLoading}
            className="rounded-xl text-xs font-bold border-slate-300 dark:border-slate-700"
          >
            {t('cancel') || (isRTL ? 'إلغاء' : 'Cancel')}
          </Button>
          <Button
            onClick={onSaveCredentials}
            disabled={credLoading || !credForm.email || isPasswordMismatch}
            className="rounded-xl text-xs font-extrabold bg-[#1C3D74] hover:bg-[#152e57] text-white shadow-md shadow-[#1C3D74]/20 gap-2 min-w-[120px]"
          >
            {credLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            <span>{hasCredentials ? (isRTL ? 'حفظ وتحديث' : 'Update') : (t('createAccount') || (isRTL ? 'إنشاء الحساب' : 'Create Account'))}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
