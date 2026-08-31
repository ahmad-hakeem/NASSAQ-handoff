import React from 'react';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  User, Mail, Phone, ShieldCheck, UserCheck
} from 'lucide-react';

function RequiredBadge({ text = 'إجباري' }) {
  return (
    <span className="text-[11px] font-bold text-rose-700 bg-rose-50 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-200 dark:border-rose-800 px-2 py-0.5 rounded-md leading-none shadow-2xs">
      {text}
    </span>
  );
}

function OptionalBadge({ text = 'اختياري' }) {
  return (
    <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 px-2 py-0.5 rounded-md leading-none">
      {text}
    </span>
  );
}

export default function StepPrincipalAccount({
  principalData,
  setPrincipalData,
  errors,
  clearFieldError,
  isRTL,
}) {
  return (
    <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300 font-tajawal" data-testid="wizard-step-3">
      {/* Title */}
      <div className="mb-6 text-start">
        <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
          <User className="h-5 w-5 text-[#46C1BE]" />
          <span>{isRTL ? 'إنشاء حساب مدير المدرسة' : 'Create School Principal Account'}</span>
        </h3>
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
          {isRTL ? 'أدخل البيانات الرسمية للمدير لإنشاء الحساب وتوليد بيانات الدخول' : 'Enter principal official credentials for account creation'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5 bg-white dark:bg-slate-900 p-6 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        {/* Full Name */}
        <div className="space-y-1.5" data-field="fullName">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-[#46C1BE]" />
              <span>{isRTL ? 'اسم مدير المدرسة' : 'Principal Name'}</span>
            </span>
            <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
          </Label>
          <Input
            value={principalData.fullName}
            onChange={(e) => {
              setPrincipalData({ ...principalData, fullName: e.target.value });
              clearFieldError('fullName');
            }}
            placeholder={isRTL ? 'الاسم الثلاثي لمدير المدرسة' : 'Principal full name'}
            className={`h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 ${
              errors.fullName ? 'border-rose-500 bg-rose-50/20' : 'border-slate-200 dark:border-slate-800'
            }`}
            data-testid="principal-name-input"
          />
          {errors.fullName && <p className="text-xs text-rose-600 font-bold">{errors.fullName}</p>}
        </div>

        {/* Email */}
        <div className="space-y-1.5" data-field="email">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5 text-[#46C1BE]" />
              <span>{isRTL ? 'البريد الإلكتروني (اسم المستخدم)' : 'Official Email (Username)'}</span>
            </span>
            <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
          </Label>
          <Input
            type="email"
            value={principalData.email}
            onChange={(e) => {
              setPrincipalData({ ...principalData, email: e.target.value });
              clearFieldError('email');
            }}
            placeholder="principal@school.edu.sa"
            className={`h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 ${
              errors.email ? 'border-rose-500 bg-rose-50/20' : 'border-slate-200 dark:border-slate-800'
            }`}
            dir="ltr"
            data-testid="principal-email-input"
          />
          {errors.email && <p className="text-xs text-rose-600 font-bold">{errors.email}</p>}
        </div>

        {/* Primary Phone */}
        <div className="space-y-1.5" data-field="primaryPhone">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-[#46C1BE]" />
              <span>{isRTL ? 'رقم الهاتف الأساسي' : 'Primary Phone'}</span>
            </span>
            <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
          </Label>
          <Input
            value={principalData.primaryPhone}
            onChange={(e) => {
              setPrincipalData({ ...principalData, primaryPhone: e.target.value });
              clearFieldError('primaryPhone');
            }}
            placeholder="05XXXXXXXX"
            className={`h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 ${
              errors.primaryPhone ? 'border-rose-500 bg-rose-50/20' : 'border-slate-200 dark:border-slate-800'
            }`}
            dir="ltr"
            data-testid="principal-phone-input"
          />
          {errors.primaryPhone && <p className="text-xs text-rose-600 font-bold">{errors.primaryPhone}</p>}
        </div>

        {/* Secondary Phone */}
        <div className="space-y-1.5">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-slate-400" />
              <span>{isRTL ? 'رقم هاتف إضافي' : 'Secondary Phone'}</span>
            </span>
            <OptionalBadge text={isRTL ? 'اختياري' : 'Optional'} />
          </Label>
          <Input
            value={principalData.secondaryPhone}
            onChange={(e) => setPrincipalData({ ...principalData, secondaryPhone: e.target.value })}
            placeholder="05XXXXXXXX"
            className="h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 border-slate-200 dark:border-slate-800"
            dir="ltr"
            data-testid="principal-secondary-phone-input"
          />
        </div>
      </div>

      {/* Security & Credentials Info Box */}
      <div className="bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-2xl p-5 flex items-start gap-4 shadow-sm">
        <div className="w-11 h-11 rounded-xl bg-[#1C3D74] flex items-center justify-center shrink-0 shadow-sm">
          <ShieldCheck className="h-6 w-6 text-[#46C1BE]" />
        </div>
        <div className="flex-1 space-y-3">
          <p className="font-bold text-sm text-blue-950 dark:text-blue-100 leading-snug">
            {isRTL ? 'سيتم توليد كلمة مرور مؤقتة وتفعيل الحساب تلقائياً' : 'A temporary password will be generated and the account activated automatically'}
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1.5 bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200 text-xs font-medium px-3 py-1.5 rounded-lg border border-blue-200 dark:border-blue-700">
              <Phone className="h-3.5 w-3.5 shrink-0" />
              {isRTL ? 'التحقق من عدم تكرار أرقام الهواتف' : 'No duplicate phone numbers'}
            </span>
            <span className="inline-flex items-center gap-1.5 bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200 text-xs font-medium px-3 py-1.5 rounded-lg border border-blue-200 dark:border-blue-700">
              <Mail className="h-3.5 w-3.5 shrink-0" />
              {isRTL ? 'التحقق من تفرد البريد الإلكتروني' : 'No duplicate emails'}
            </span>
            <span className="inline-flex items-center gap-1.5 bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200 text-xs font-medium px-3 py-1.5 rounded-lg border border-blue-200 dark:border-blue-700">
              <UserCheck className="h-3.5 w-3.5 shrink-0" />
              {isRTL ? 'منح صلاحية مدير المدرسة للمستأجر' : 'Principal role assigned automatically'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
