import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import {
  Key, UserPlus, RotateCcw, CheckCircle2, XCircle, AlertTriangle,
  Mail, Copy, Lock, Sparkles, Shield, UserCheck
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
    <Card dir={isRTL ? 'rtl' : 'ltr'} className="rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm overflow-hidden font-tajawal">
      <CardHeader className="pb-4 border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <CardTitle className="font-cairo text-sm sm:text-base font-extrabold flex items-center gap-2.5 text-slate-900 dark:text-white">
            <div className="w-8 h-8 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0 border border-amber-100 dark:border-amber-900/60">
              <Key className="h-4 w-4" />
            </div>
            <span>{t('systemLoginCredentials') || (isRTL ? 'حساب مدير المدرسة وبيانات الدخول' : 'Principal Account & Credentials')}</span>
          </CardTitle>

          <Button
            size="sm"
            onClick={() => onOpenCredForm(principal)}
            className={`gap-2 text-xs font-bold font-cairo rounded-xl h-9 px-4 shadow-2xs transition-all ${
              hasCreds
                ? 'bg-slate-100 hover:bg-slate-200 text-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-100 border border-slate-200 dark:border-slate-700'
                : 'bg-[#1C3D74] hover:bg-[#152e57] text-white shadow-xs'
            }`}
          >
            {hasCreds ? (
              <>
                <RotateCcw className="h-3.5 w-3.5 text-[#1C3D74] dark:text-[#46C1BE]" />
                <span>{t('updateCredentials') || (isRTL ? 'تعديل بيانات الدخول' : 'Update Credentials')}</span>
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

      <CardContent className="pt-5 pb-6 space-y-4">
        {hasCreds && principal ? (
          <div className="space-y-3.5">
            {/* Active Status Banner */}
            <div className="flex items-center gap-3 p-3.5 bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/60 rounded-xl">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/60 flex items-center justify-center flex-shrink-0 text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-emerald-900 dark:text-emerald-200 font-cairo">
                  {t('accountActive') || (isRTL ? 'حساب مدير المدرسة مهيأ ونشط' : 'Principal Account Active')}
                </p>
                <p className="text-[11px] text-emerald-700/90 dark:text-emerald-300/90 mt-0.5">
                  {t('principalAccountExistsAndIsAccessible') || (isRTL ? 'الحساب مسجل بصلاحيات الإدارة ويمكن تسجيل الدخول مباشرة للوحة التحكم' : 'Account is ready and has full administrative access')}
                </p>
              </div>
            </div>

            {/* Principal Info Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Full Name */}
              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold">{t('fullName') || (isRTL ? 'اسم المدير' : 'Principal Name')}</p>
                <p className="text-xs font-bold text-slate-900 dark:text-white truncate">{principal.full_name || '—'}</p>
              </div>

              {/* Email */}
              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-1">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold">{t('email2') || (isRTL ? 'البريد الإلكتروني' : 'Email')}</p>
                  <button
                    type="button"
                    onClick={() => onCopy(principal.email, isRTL ? 'البريد الإلكتروني' : 'Email')}
                    className="p-0.5 rounded text-slate-400 hover:text-[#1C3D74] dark:hover:text-[#46C1BE] hover:bg-slate-200/80 dark:hover:bg-slate-700 transition-colors"
                    title={isRTL ? 'نسخ البريد' : 'Copy email'}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                </div>
                <p className="text-xs font-mono font-medium text-slate-900 dark:text-white truncate" dir="ltr">{principal.email}</p>
              </div>

              {/* Account Status */}
              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold">{t('accountStatus') || (isRTL ? 'حالة الحساب' : 'Status')}</p>
                <div className="flex items-center gap-1.5">
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${
                    principal.is_active !== false
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                      : 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                  }`}>
                    {principal.is_active !== false ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                    <span>{principal.is_active !== false ? (t('active') || (isRTL ? 'نشط' : 'Active')) : (t('suspended2') || (isRTL ? 'موقوف' : 'Suspended'))}</span>
                  </span>
                </div>
              </div>

              {/* Password Flag */}
              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 space-y-1">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'نوع كلمة المرور' : 'Password Type'}</p>
                <div className="flex items-center gap-1.5">
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${
                    principal.must_change_password
                      ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                      : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700'
                  }`}>
                    {principal.must_change_password ? <AlertTriangle className="h-3 w-3" /> : <Shield className="h-3 w-3" />}
                    <span>{principal.must_change_password ? (isRTL ? 'مؤقتة (يلزم التغيير)' : 'Temp') : (isRTL ? 'دائمة' : 'Permanent')}</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Empty State */
          <div className="flex flex-col items-center justify-center py-7 text-center gap-2.5 bg-slate-50/50 dark:bg-slate-800/20 rounded-xl border border-dashed border-slate-200 dark:border-slate-800">
            <div className="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-center justify-center text-amber-600 dark:text-amber-400">
              <Lock className="h-5 w-5" />
            </div>
            <div className="space-y-0.5 max-w-md px-4">
              <p className="font-bold text-slate-800 dark:text-white font-cairo text-xs sm:text-sm">
                {t('noLoginAccountConfigured') || (isRTL ? 'لم يتم تكوين حساب مدير المدرسة حتى الآن' : 'No Principal Account Provisioned')}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('createAPrincipalAccountSoTheSchoolCanAccessTheSyst') || (isRTL ? 'قم بإنشاء حساب رسمي لمدير المدرسة لتمكينه من الدخول للوحة التحكم' : 'Provision an account to enable the school principal to log in')}
              </p>
            </div>
            <Button
              size="sm"
              onClick={() => onOpenCredForm(null)}
              className="mt-1 gap-2 text-xs font-bold rounded-xl h-9 px-5 bg-[#1C3D74] hover:bg-[#152e57] text-white shadow-xs"
            >
              <UserPlus className="h-3.5 w-3.5" />
              <span>{t('createPrincipalAccount') || (isRTL ? 'إنشاء حساب المدير الآن' : 'Create Principal Account Now')}</span>
            </Button>
          </div>
        )}

        {/* Dynamic Credentials Result Banner */}
        {credResult && (
          <div className="p-4 bg-sky-50/80 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 rounded-xl space-y-2.5 animate-in fade-in-30 duration-200">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <p className="text-xs font-bold text-[#1C3D74] dark:text-[#46C1BE] font-cairo flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-[#46C1BE]" />
                <span>{credResult.is_new ? (t('accountCreatedSaveTheseCredentials') || (isRTL ? 'تم إنشاء الحساب بنجاح، احفظ البيانات التالية:' : 'Account created successfully:')) : (isRTL ? 'تم تحديث بيانات الدخول بنجاح' : 'Credentials updated successfully')}</span>
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div className="flex items-center gap-2 p-2.5 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 shadow-2xs">
                <Mail className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                <span className="text-xs font-mono font-bold text-slate-800 dark:text-slate-200 flex-1 truncate" dir="ltr">{credResult.email}</span>
                <button type="button" onClick={() => onCopy(credResult.email, isRTL ? 'البريد' : 'Email')} className="text-slate-400 hover:text-[#1C3D74] p-1"><Copy className="h-3.5 w-3.5" /></button>
              </div>

              {credResult.password_was_changed && credResult.temp_password && (
                <div className="flex items-center gap-2 p-2.5 bg-white dark:bg-slate-900 rounded-lg border border-amber-200 dark:border-amber-800 shadow-2xs">
                  <Key className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                  <span className="text-xs font-mono font-extrabold flex-1 tracking-wider text-amber-600 dark:text-amber-400" dir="ltr">{credResult.temp_password}</span>
                  <button type="button" onClick={() => onCopy(credResult.temp_password, isRTL ? 'كلمة المرور' : 'Password')} className="text-slate-400 hover:text-amber-600 p-1"><Copy className="h-3.5 w-3.5" /></button>
                </div>
              )}
            </div>

            {credResult.password_was_changed && credResult.temp_password && (
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-1.5 rounded-xl border-slate-200 dark:border-slate-700 text-[#1C3D74] hover:bg-slate-100 dark:text-[#46C1BE] dark:hover:bg-slate-800 font-cairo text-xs font-bold h-9 transition-all"
                onClick={() => {
                  const msg = `مرحباً،\n\nإليك بيانات حسابك على منصة نَسَّق | NASSAQ.\n\nالبريد الإلكتروني: ${credResult.email}\nكلمة المرور المؤقتة: ${credResult.temp_password}\n\nيرجى تسجيل الدخول عبر الرابط التالي:\n${window.location.origin}/login\n\nإذا واجهت أي مشكلة أثناء تسجيل الدخول أو احتجت إلى مساعدة، يرجى التواصل مع إدارة المنصة.\n\nمع خالص التحية،\nإدارة منصة نَسَّق | NASSAQ`;
                  onCopy(msg, isRTL ? 'الرسالة الترحيبية' : 'Welcome message');
                }}
              >
                <Copy className="h-3.5 w-3.5" />
                <span>{t('copyWelcomeMessageWithCredentials') || (isRTL ? 'نسخ الرسالة الترحيبية الكاملة لمشاركتها مع المدير' : 'Copy Full Welcome Message')}</span>
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
