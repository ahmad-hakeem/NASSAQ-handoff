import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Building2, Plus, GraduationCap, RefreshCw,
  CheckCircle2, Clock, Download, XCircle, UserCheck, Layers
} from 'lucide-react';

export default function TenantsHeroStats({
  stats,
  onRefresh,
  refreshing,
  onExport,
  onOpenCreateWizard,
  isRTL,
}) {
  const statChips = [
    {
      key: 'all',
      label: isRTL ? 'إجمالي المدارس' : 'Total Schools',
      subtitle: isRTL ? 'جميع المؤسسات' : 'All Institutions',
      value: stats.total,
      icon: Building2,
      iconColor: 'text-[#1C3D74] dark:text-[#46C1BE]',
      iconBg: 'bg-[#1C3D74]/10 dark:bg-[#46C1BE]/15',
    },
    {
      key: 'active',
      label: isRTL ? 'المدارس النشطة' : 'Active Schools',
      subtitle: isRTL ? 'مفعلة وتعمل' : 'Operational',
      value: stats.active,
      icon: CheckCircle2,
      iconColor: 'text-emerald-600 dark:text-emerald-400',
      iconBg: 'bg-emerald-50 dark:bg-emerald-950/50',
    },
    {
      key: 'suspended',
      label: isRTL ? 'المدارس الموقوفة' : 'Suspended',
      subtitle: isRTL ? 'تحتاج تدقيق' : 'Needs Review',
      value: stats.suspended,
      icon: XCircle,
      iconColor: 'text-rose-600 dark:text-rose-400',
      iconBg: 'bg-rose-50 dark:bg-rose-950/50',
    },
    {
      key: 'setup',
      label: isRTL ? 'المسودات' : 'Drafts',
      subtitle: isRTL ? 'قيد التهيئة' : 'In Setup',
      value: stats.drafts,
      icon: Clock,
      iconColor: 'text-amber-600 dark:text-amber-400',
      iconBg: 'bg-amber-50 dark:bg-amber-950/50',
    },
    {
      key: 'students',
      label: isRTL ? 'إجمالي الطلاب' : 'Students',
      subtitle: isRTL ? 'مقيدون بالمنظومة' : 'Enrolled',
      value: Number(stats.totalStudents || 0).toLocaleString(),
      icon: GraduationCap,
      iconColor: 'text-sky-600 dark:text-sky-400',
      iconBg: 'bg-sky-50 dark:bg-sky-950/50',
    },
    {
      key: 'teachers',
      label: isRTL ? 'إجمالي المعلمين' : 'Teachers',
      subtitle: isRTL ? 'كادر تعليمي' : 'Faculty Staff',
      value: Number(stats.totalTeachers || 0).toLocaleString(),
      icon: UserCheck,
      iconColor: 'text-teal-600 dark:text-teal-400',
      iconBg: 'bg-teal-50 dark:bg-teal-950/50',
    },
    {
      key: 'classes',
      label: isRTL ? 'الفصول الدراسية' : 'Classes',
      subtitle: isRTL ? 'شعبة مفعلة' : 'Active Sections',
      value: Number(stats.totalClasses || 0).toLocaleString(),
      icon: Layers,
      iconColor: 'text-purple-600 dark:text-purple-400',
      iconBg: 'bg-purple-50 dark:bg-purple-950/50',
    },
  ];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-sm p-5 sm:p-6 font-tajawal">
      {/* Top Header Row */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        {/* Title Group */}
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#1C3D74] to-[#152e57] flex items-center justify-center text-[#46C1BE] shadow-xs shrink-0">
            <Building2 className="h-6 w-6" />
          </div>

          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl sm:text-2xl font-black font-cairo text-slate-900 dark:text-white">
                {isRTL ? 'إدارة المدارس والمستأجرين' : 'Schools & Tenants Management'}
              </h1>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-[11px] font-bold text-emerald-700 dark:text-emerald-300">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>{isRTL ? 'محدث ومباشر' : 'Live'}</span>
              </span>
            </div>
            <p className="text-xs sm:text-sm font-medium text-slate-500 dark:text-slate-400 mt-0.5">
              {isRTL
                ? 'المركز الموحد لإدارة ومتابعة المدارس الأكاديمية والجاهزية التشغيلية'
                : 'Central console for school tenants, operational readiness, and management'}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5 flex-wrap w-full lg:w-auto justify-start lg:justify-end shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={refreshing}
            className="rounded-xl border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-bold text-xs h-10 px-3.5 gap-2 shadow-xs"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin text-[#46C1BE]' : 'text-slate-500'}`} />
            <span>{isRTL ? 'تحديث' : 'Refresh'}</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onExport}
            className="rounded-xl border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-bold text-xs h-10 px-3.5 gap-2 shadow-xs"
          >
            <Download className="h-4 w-4 text-slate-500" />
            <span>{isRTL ? 'تصدير CSV' : 'Export'}</span>
          </Button>

          <Button
            size="sm"
            onClick={onOpenCreateWizard}
            data-testid="add-school-main-btn"
            className="rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white font-bold text-xs h-10 px-4 gap-2 shadow-sm shadow-[#1C3D74]/20 transition-all hover:shadow-md"
          >
            <Plus className="h-4 w-4 stroke-[2.5] text-[#46C1BE]" />
            <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
          </Button>
        </div>
      </div>

      {/* KPI Stats Ribbon */}
      <div className="mt-5 pt-5 border-t border-slate-100 dark:border-slate-800 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {statChips.map((chip) => {
          const Icon = chip.icon;

          return (
            <div
              key={chip.key}
              className="rounded-xl p-3.5 bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 flex flex-col justify-between min-h-[100px]"
            >
              <div className="flex items-center justify-between w-full mb-1">
                <div className={`p-1.5 rounded-lg ${chip.iconBg}`}>
                  <Icon className={`h-4 w-4 ${chip.iconColor}`} />
                </div>
              </div>

              <div>
                <p className="text-xl font-black font-cairo text-slate-900 dark:text-white leading-none font-mono">
                  {chip.value}
                </p>
                <p className="text-xs font-bold text-slate-700 dark:text-slate-300 mt-1 truncate">
                  {chip.label}
                </p>
                <p className="text-[10px] font-medium text-slate-400 dark:text-slate-500 truncate mt-0.5">
                  {chip.subtitle}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
