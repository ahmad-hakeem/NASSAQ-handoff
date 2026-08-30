import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import {
  Key, UserPlus, RotateCcw, CheckCircle2, XCircle, AlertTriangle,
  Mail, Copy, Lock, Sparkles, Shield
} from 'lucide-react';

export default function SchoolCredentialsCard({
  principal,
  hasCreds,
  onOpenCredForm,
  credResult,
  onCopy,
  isRTL,
  t,
}) {
  return (
    <Card className="rounded-3xl border-2 border-dashed border-[#1C3D74]/20 dark:border-[#46C1BE]/30 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <CardTitle className="font-cairo text-base font-extrabold flex items-center gap-2 text-[#1C3D74] dark:text-[#46C1BE]">
            <Key className="h-5 w-5" />
            <span>{t('systemLoginCredentials') || (isRTL ? 'بيانات تسجيل الدخول للنظام' : 'System Login Credentials')}</span>
          </CardTitle>
          <Button
            size="sm"
            onClick={() => onOpenCredForm(principal)}
            className={`gap-1.5 text-xs font-bold font-cairo rounded-xl h-9 px-4 ${
              hasCreds
                ? 'bg-[#1C3D74]/10 text-[#1C3D74] hover:bg-[#1C3D74] hover:text-white dark:bg-[#46C1BE]/10 dark:text-[#46C1BE] dark:hover:bg-[#46C1BE] dark:hover:text-slate-950'
                : 'bg-[#1C3D74] text-white hover:bg-[#152e57]'
            }`}
            variant="ghost"
          >
            {hasCreds ? (
              <>
                <RotateCcw className="h-3.5 w-3.5" />
                <span>{t('updateCredentials') || (isRTL ? 'تحديث بيانات الدخول' : 'Update Credentials')}</span>
              </>
            ) : (
              <>
                <UserPlus className="h-3.5 w-3.5" />
                <span>{t('createPrincipalAccount') || (isRTL ? 'إنشاء حساب مدير المدرسة' : 'Create Principal Account')}</span>
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        {hasCreds && principal ? (
          <div className="space-y-4">
            {/* Status indicator bar */}
            <div className="flex items-center gap-3 p-3.5 bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/80 rounded-2xl">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/60 flex items-center justify-center flex-shrink-0 text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-emerald-900 dark:text-emerald-200 font-cairo">
                  {t('accountActive') || (isRTL ? 'حساب مدير المدرسة نشط وجاهز للاستخدام' : 'Principal Account is Active')}
                </p>
                <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">
                  {t('principalAccountExistsAndIsAccessible') || (isRTL ? 'تم إنشاء الحساب الإداري ويمكن تسجيل الدخول للوحة التحكم' : 'Principal can sign in to manage the school')}
                </p>
              </div>
            </div>

            {/* Principal Credentials Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {/* Full Name */}
              <div className="space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-bold">{t('fullName') || (isRTL ? 'الاسم الكامل' : 'Full Name')}</p>
                <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-800">
                  <span className="text-xs font-bold text-slate-800 dark:text-white flex-1">{principal.full_name || '—'}</span>
                </div>
              </div>

              {/* Email */}
              <div className="space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-bold">{t('email2') || (isRTL ? 'البريد الإلكتروني' : 'Email')}</p>
                <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-800">
                  <span className="text-xs font-mono font-medium text-slate-800 dark:text-white flex-1 truncate" dir="ltr">{principal.email}</span>
                  <button
                    type="button"
                    onClick={() => onCopy(principal.email, isRTL ? 'البريد الإلكتروني' : 'Email')}
                    className="p-1 rounded-lg text-slate-400 hover:text-[#1C3D74] dark:hover:text-[#46C1BE] hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Account Status */}
              <div className="space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-bold">{t('accountStatus') || (isRTL ? 'حالة الحساب' : 'Account Status')}</p>
                <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-800">
                  <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                    principal.is_active !== false
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                      : 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                  }`}>
                    {principal.is_active !== false ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                    <span>{principal.is_active !== false ? (t('active') || (isRTL ? 'نشط' : 'Active')) : (t('suspended2') || (isRTL ? 'موقوف' : 'Suspended'))}</span>
                  </span>
                </div>
              </div>

              {/* Password Change Flag */}
              <div className="space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-bold">{isRTL ? 'تغيير كلمة المرور مطلوب' : 'Password Reset Required'}</p>
                <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-800">
                  <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-0.5 rounded-full border ${
                    principal.must_change_password
                      ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                      : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700'
                  }`}>
                    {principal.must_change_password ? <AlertTriangle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                    <span>{principal.must_change_password ? (t('yes') || (isRTL ? 'نعم (مؤقتة)' : 'Yes')) : (t('no') || (isRTL ? 'لا' : 'No'))}</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Empty Credentials Prompt */
          <div className="flex flex-col items-center justify-center py-8 text-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <Lock className="h-6 w-6" />
            </div>
            <div>
              <p className="font-bold text-slate-800 dark:text-white font-cairo text-sm">
                {t('noLoginAccountConfigured') || (isRTL ? 'لم يتم تكوين حساب مدير المدرسة بعد' : 'No Principal Account Configured')}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm">
                {t('createAPrincipalAccountSoTheSchoolCanAccessTheSyst') || (isRTL ? 'قم بإنشاء حساب لمدير المدرسة لتمكينهم من تسجيل الدخول وإدارة العمليات' : 'Create an account to allow the principal to log in')}
              </p>
            </div>
          </div>
        )}

        {/* Dynamic Credentials Result Banner (After generating/updating) */}
        {credResult && (
          <div className="mt-4 p-4.5 bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-2xl space-y-3 animate-in fade-in-30 duration-200">
            <p className="text-xs font-bold text-[#1C3D74] dark:text-[#46C1BE] font-cairo flex items-center gap-2">
              <Sparkles className="h-4 w-4" />
              <span>{credResult.is_new ? (t('accountCreatedSaveTheseCredentials') || (isRTL ? 'تم إنشاء الحساب بنجاح، احفظ البيانات التالية:' : 'Account created successfully:')) : (isRTL ? 'تم تحديث بيانات الدخول بنجاح' : 'Credentials updated successfully')}</span>
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div className="flex items-center gap-2 p-2.5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700">
                <Mail className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                <span className="text-xs font-mono font-medium flex-1 truncate" dir="ltr">{credResult.email}</span>
                <button type="button" onClick={() => onCopy(credResult.email, isRTL ? 'البريد' : 'Email')} className="text-slate-400 hover:text-[#1C3D74]"><Copy className="h-3.5 w-3.5" /></button>
              </div>

              {credResult.password_was_changed && credResult.temp_password && (
                <div className="flex items-center gap-2 p-2.5 bg-white dark:bg-slate-900 rounded-xl border border-amber-200 dark:border-amber-800">
                  <Key className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                  <span className="text-xs font-mono font-bold flex-1 tracking-wider text-amber-600 dark:text-amber-400" dir="ltr">{credResult.temp_password}</span>
                  <button type="button" onClick={() => onCopy(credResult.temp_password, isRTL ? 'كلمة المرور' : 'Password')} className="text-slate-400 hover:text-amber-600"><Copy className="h-3.5 w-3.5" /></button>
                </div>
              )}
            </div>

            {credResult.password_was_changed && credResult.temp_password && (
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-2 rounded-xl border-[#1C3D74]/20 text-[#1C3D74] hover:bg-[#1C3D74] hover:text-white dark:text-[#46C1BE] dark:border-[#46C1BE]/30 dark:hover:bg-[#46C1BE] dark:hover:text-slate-950 font-cairo text-xs font-bold h-9.5 shadow-2xs"
                onClick={() => {
                  const msg = `مرحباً،\n\nإليك بيانات حسابك على منصة نَسَّق | NASSAQ.\n\nالبريد الإلكتروني: ${credResult.email}\nكلمة المرور المؤقتة: ${credResult.temp_password}\n\nيرجى تسجيل الدخول عبر الرابط التالي:\n${window.location.origin}/login\n\nإذا واجهت أي مشكلة أثناء تسجيل الدخول أو احتجت إلى مساعدة، يرجى التواصل مع إدارة المنصة.\n\nمع خالص التحية،\nإدارة منصة نَسَّق | NASSAQ`;
                  onCopy(msg, isRTL ? 'رسالة الترحيب' : 'Welcome message');
                }}
              >
                <Copy className="h-4 w-4" />
                <span>{t('copyWelcomeMessageWithCredentials') || (isRTL ? 'نسخ الرسالة الترحيبية مع بيانات الدخول' : 'Copy Welcome Message')}</span>
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
