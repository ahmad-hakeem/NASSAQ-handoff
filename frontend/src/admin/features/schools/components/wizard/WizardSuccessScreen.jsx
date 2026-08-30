import React from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  CheckCircle2, ExternalLink, KeyRound, ShieldCheck, Copy
} from 'lucide-react';

export default function WizardSuccessScreen({
  createdSchool,
  schoolName,
  onCopyWelcomeMessage,
  onClose,
  isRTL,
}) {
  return (
    <div className="p-8 md:p-10 flex-1 flex flex-col justify-center animate-in zoom-in-95 duration-400 bg-white dark:bg-slate-900 font-tajawal" data-testid="wizard-success-screen">
      <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto items-center w-full">
        {/* Left Side: Success Status */}
        <div className="space-y-6 text-center md:text-start">
          <div>
            <div className="w-20 h-20 rounded-3xl bg-emerald-50 dark:bg-emerald-950/60 border-2 border-emerald-500/30 flex items-center justify-center mx-auto md:mx-0 mb-4 shadow-xl shadow-emerald-500/10">
              <CheckCircle2 className="h-10 w-10 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h2 className="font-cairo text-2xl md:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              {isRTL ? 'تم إنشاء المدرسة بنجاح!' : 'School Created Successfully!'}
            </h2>
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
              {isRTL
                ? 'تم إنشاء المستأجر وحساب المدير وتجهيز الكتالوج الأكاديمي بنجاح'
                : 'Tenant, principal account, and academic catalog are ready'}
            </p>
          </div>

          <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-slate-50/80 dark:bg-slate-800/80">
            <CardContent className="p-4.5 space-y-3 text-xs">
              <div className="flex items-center justify-between py-1 border-b border-slate-200 dark:border-slate-700">
                <span className="text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'كود المستأجر:' : 'Tenant Code:'}</span>
                <Badge className="text-base font-mono font-black bg-[#1C3D74] text-white px-3 py-1 rounded-xl" data-testid="tenant-code">
                  {createdSchool?.tenant_code || createdSchool?.code}
                </Badge>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-200 dark:border-slate-700">
                <span className="text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'اسم المدرسة:' : 'School Name:'}</span>
                <strong className="text-slate-900 dark:text-slate-100 font-bold">{createdSchool?.name || schoolName}</strong>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'الحالة:' : 'Status:'}</span>
                <Badge className="bg-emerald-600 text-white font-bold">{isRTL ? 'نشطة' : 'Active'}</Badge>
              </div>
            </CardContent>
          </Card>

          <div className="flex gap-3 pt-2">
            <Button
              className="flex-1 rounded-xl h-11 border-slate-200 dark:border-slate-700 font-bold text-slate-800 dark:text-slate-200"
              variant="outline"
              onClick={() => window.open('/school', '_blank')}
            >
              <ExternalLink className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-slate-400`} />
              <span>{isRTL ? 'لوحة تحكم المدرسة' : 'School Dashboard'}</span>
            </Button>
            <Button
              variant="default"
              className="flex-1 rounded-xl h-11 bg-[#1C3D74] hover:bg-[#152e57] text-white font-extrabold shadow-md shadow-[#1C3D74]/20"
              onClick={onClose}
              data-testid="back-to-actions-btn"
            >
              <span>{isRTL ? 'العودة للوحة الإدارة' : 'Back to Admin'}</span>
            </Button>
          </div>
        </div>

        {/* Right Side: Ready-to-copy Credentials Card */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-cairo text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-[#46C1BE]" />
              <span>{isRTL ? 'الرسالة الترحيبية وبيانات الدخول' : 'Welcome Message & Credentials'}</span>
            </h3>
            <Badge variant="outline" className="text-[11px] font-bold text-emerald-700 bg-emerald-50 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800">
              {isRTL ? 'جاهزة للإرسال' : 'Ready to send'}
            </Badge>
          </div>

          <Card className="bg-slate-900 text-slate-100 rounded-3xl border-slate-800 shadow-xl overflow-hidden">
            <CardContent className="p-5 text-xs space-y-3" dir={isRTL ? 'rtl' : 'ltr'}>
              <p className="font-bold text-slate-100 text-sm font-cairo">أهلاً بك في منصة نَسَّق لإدارة التعليم والمدارس الذكية.</p>
              <p className="text-slate-300 font-medium">بيانات دخول حساب إدارة المدرسة:</p>
              <div className="bg-slate-950 rounded-2xl p-3.5 space-y-2 font-mono text-xs border border-slate-800 text-emerald-400">
                <div>
                  <span className="text-slate-400">رابط المنصة: </span>
                  <span className="text-slate-200 select-all font-semibold">{window.location.origin}</span>
                </div>
                <div>
                  <span className="text-slate-400">اسم المستخدم: </span>
                  <span className="text-white font-bold select-all">{createdSchool?.principal?.email}</span>
                </div>
                <div>
                  <span className="text-slate-400">كلمة المرور: </span>
                  <span className="text-amber-300 font-bold bg-amber-400/15 px-2 py-0.5 rounded-lg select-all">{createdSchool?.principal?.temp_password}</span>
                </div>
                <div>
                  <span className="text-slate-400">كود المدرسة: </span>
                  <span className="text-[#46C1BE] font-bold select-all">{createdSchool?.tenant_code || createdSchool?.code}</span>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 flex items-center gap-1.5 font-medium">
                <ShieldCheck className="h-3.5 w-3.5 text-[#46C1BE]" />
                <span>يرجى تغيير كلمة المرور عند أول تسجيل دخول لضمان الأمان.</span>
              </p>
            </CardContent>
          </Card>

          <Button
            onClick={onCopyWelcomeMessage}
            className="w-full h-11 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-extrabold shadow-sm border border-slate-700"
            variant="outline"
            data-testid="copy-message-btn"
          >
            <Copy className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-[#46C1BE]`} />
            <span>{isRTL ? 'نسخ الرسالة الترحيبية وبيانات الدخول' : 'Copy Welcome Message'}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
