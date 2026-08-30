import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { CreditCard, Users, Zap, ShieldCheck } from 'lucide-react';

export default function BillingSubscriptionTab({
  school,
  stats,
  isRTL,
  t,
}) {
  const capacity = school?.student_capacity || 500;
  const currentStudents = stats?.total_students || 0;
  const utilizationPercent = Math.min(Math.round((currentStudents / (capacity || 1)) * 100), 100);

  return (
    <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
      <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-4">
        <CardTitle className="font-cairo text-base font-extrabold flex items-center gap-2 text-slate-900 dark:text-white">
          <CreditCard className="h-5 w-5 text-[#615090]" />
          <span>{t('billingSubscription') || (isRTL ? 'الاشتراك والسعة التشغيلية' : 'Billing & Subscription')}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6 space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Subscription Plan Card */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-[#1C3D74]/5 to-[#1C3D74]/10 border border-[#1C3D74]/20 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">
                {t('subscriptionPlan') || (isRTL ? 'باقة الاشتراك' : 'Subscription Plan')}
              </span>
              <Zap className="h-4 w-4 text-[#1C3D74] dark:text-[#46C1BE]" />
            </div>
            <p className="text-2xl font-extrabold text-[#1C3D74] dark:text-[#46C1BE] font-cairo">
              {isRTL ? 'الباقة المدرسية الموحدة' : 'Unified School Tier'}
            </p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {t('subscriptionNotConfiguredYet') || (isRTL ? 'الاشتراك مفعّل عبر المنظومة السحابية' : 'Subscription active via cloud cluster')}
            </p>
          </div>

          {/* Student Capacity Card */}
          <div className="p-5 rounded-2xl bg-gradient-to-br from-[#46C1BE]/5 to-[#46C1BE]/10 border border-[#46C1BE]/20 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-600 dark:text-slate-400">
                {t('studentCapacity') || (isRTL ? 'السعة الاستيعابية للطلاب' : 'Student Capacity')}
              </span>
              <Users className="h-4 w-4 text-[#46C1BE]" />
            </div>
            <p className="text-2xl font-extrabold text-slate-900 dark:text-white font-mono">
              {capacity.toLocaleString()} <span className="text-xs font-medium text-slate-500">{isRTL ? 'طالب' : 'Students'}</span>
            </p>
            <div>
              <div className="flex items-center justify-between text-[11px] font-bold mb-1">
                <span className="text-slate-600 dark:text-slate-400">
                  {isRTL ? `المستخدم: ${currentStudents}` : `Used: ${currentStudents}`}
                </span>
                <span className="font-mono text-[#46C1BE]">{utilizationPercent}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                <div
                  className="h-full bg-[#46C1BE] rounded-full transition-all duration-500"
                  style={{ width: `${utilizationPercent}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Enterprise Notice */}
        <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 flex items-center gap-3">
          <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] shrink-0">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 font-medium">
            {t('billingSystemUnderDevelopment') || (isRTL ? 'يتم إدارة فواتير المستأجر والمدارس تلقائياً عبر العقود المؤسسية لنظام نَسَّق.' : 'Tenant subscriptions and billing are managed via enterprise contracts.')}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
