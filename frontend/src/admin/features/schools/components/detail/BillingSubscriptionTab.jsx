import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { CreditCard, Users, Zap, ShieldCheck, Check } from 'lucide-react';

export default function BillingSubscriptionTab({
  school,
  stats,
  isRTL,
  t,
}) {
  const capacity = school?.student_capacity || 500;
  const currentStudents = stats?.total_students || 0;
  const utilizationPercent = Math.min(Math.round((currentStudents / (capacity || 1)) * 100), 100);

  const planFeatures = [
    isRTL ? 'توليد الجداول المدرسية الذكية' : 'Smart Timetable Scheduling',
    isRTL ? 'توزيع نصاب الحصص التلقائي للمعلمين' : 'Automated Teacher Workload Allocation',
    isRTL ? 'إدارة الفصول والشعب والغياب' : 'Class Sections & Attendance Tracking',
    isRTL ? 'تصدير التقارير التحليلية المتقدمة' : 'Analytics & Data Exports',
    isRTL ? 'صلاحيات متعددة الأدوار والإشراف' : 'Multi-Role Access & Permissions',
  ];

  return (
    <div className="space-y-6 font-tajawal">
      {/* Top 2 Cards: Plan Tier + Student Capacity Gauge */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* Subscription Plan Card */}
        <Card className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
          <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] flex items-center justify-center shrink-0 border border-blue-100 dark:border-blue-900/60">
                  <Zap className="h-4 w-4" />
                </div>
                <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white">
                  {t('subscriptionPlan') || (isRTL ? 'باقة الاشتراك' : 'Subscription Tier')}
                </CardTitle>
              </div>
              <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-bold text-xs px-2.5 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 me-1.5 animate-pulse" />
                {isRTL ? 'سارية ومفعّلة' : 'Active Plan'}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="pt-5 pb-5 space-y-4">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                {isRTL ? 'نوع الترخيص المؤسسي' : 'License Type'}
              </p>
              <h3 className="text-xl font-black text-slate-900 dark:text-white font-cairo mt-0.5">
                {isRTL ? 'الباقة الموحدة — نَسَّق برو' : 'NASSAQ Enterprise Suite'}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                {isRTL ? 'ترخيص شامل لجميع خدمات الجداول وإدارة الموارد المدرسية السحابية.' : 'Full access to school operations, scheduling, and AI modules.'}
              </p>
            </div>

            {/* Included Features Checklist */}
            <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800/80">
              <p className="text-xs font-bold text-slate-700 dark:text-slate-300 font-cairo mb-2">
                {isRTL ? 'الميزات المضمنة في الباقة:' : 'Included Features:'}
              </p>
              {planFeatures.map((feat, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <div className="w-4 h-4 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                    <Check className="h-2.5 w-2.5 stroke-[3]" />
                  </div>
                  <span>{feat}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Student Capacity & Quota Utilization */}
        <Card className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
          <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 flex items-center justify-center shrink-0 border border-teal-100 dark:border-teal-900/60">
                  <Users className="h-4 w-4" />
                </div>
                <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white">
                  {t('studentCapacity') || (isRTL ? 'السعة الطلابية والاستهلاك' : 'Student Quota & Utilization')}
                </CardTitle>
              </div>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700/80">
                {utilizationPercent}% {isRTL ? 'مستخدم' : 'Used'}
              </span>
            </div>
          </CardHeader>

          <CardContent className="pt-5 pb-5 space-y-5">
            <div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white font-mono">
                  {currentStudents.toLocaleString()}
                </span>
                <span className="text-xs sm:text-sm font-semibold text-slate-500 dark:text-slate-400 font-mono">
                  / {capacity.toLocaleString()} {isRTL ? 'طالب كحد أقصى' : 'Max Capacity'}
                </span>
              </div>

              {/* Enhanced Progress Bar */}
              <div className="mt-3 w-full h-2.5 rounded-full bg-slate-100 dark:bg-slate-800 p-0.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    utilizationPercent > 90
                      ? 'bg-rose-500'
                      : utilizationPercent > 75
                      ? 'bg-amber-500'
                      : 'bg-[#1C3D74] dark:bg-[#46C1BE]'
                  }`}
                  style={{ width: `${Math.max(utilizationPercent, 2)}%` }}
                />
              </div>
            </div>

            {/* Quick Metrics Breakdown */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'المقاعد الشاغرة' : 'Available Seats'}</p>
                <p className="text-base sm:text-lg font-black font-cairo text-slate-900 dark:text-white mt-0.5">
                  {Math.max(capacity - currentStudents, 0).toLocaleString()}
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800">
                <p className="text-xs text-slate-500 dark:text-slate-400 font-semibold">{isRTL ? 'نسبة الإشغال' : 'Occupancy Rate'}</p>
                <p className="text-base sm:text-lg font-black font-cairo text-[#1C3D74] dark:text-[#46C1BE] mt-0.5">
                  {utilizationPercent}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Enterprise Contract Notice Banner */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 flex items-start sm:items-center gap-3.5 shadow-sm">
        <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] flex items-center justify-center shrink-0 border border-blue-100 dark:border-blue-900/60">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-slate-900 dark:text-white font-cairo">
            {isRTL ? 'إدارة العقود والفواتير السحابية' : 'Enterprise Cloud Billing Agreement'}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {t('billingSystemUnderDevelopment') || (isRTL ? 'تتم تسوية الاشتراكات وتجديد التراخيص تلقائياً من خلال إدارة العقود المركزية لمنصة نَسَّق.' : 'Subscriptions and licenses are centrally provisioned via NASSAQ Cloud enterprise agreements.')}
          </p>
        </div>
      </div>
    </div>
  );
}
