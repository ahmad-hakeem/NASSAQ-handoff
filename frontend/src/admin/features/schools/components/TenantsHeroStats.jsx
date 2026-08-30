import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Building2, Plus, Users, GraduationCap, RefreshCw,
  CheckCircle2, Clock, Download, XCircle, UserCheck, Layers, Sparkles
} from 'lucide-react';

export default function TenantsHeroStats({
  stats,
  activeStatusFilter,
  onStatusFilter,
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
      onClick: () => onStatusFilter(null),
      active: activeStatusFilter === null,
      color: 'text-blue-400',
      badgeBg: 'bg-blue-500/20 text-blue-300 border border-blue-400/30',
      cardBg: 'bg-blue-950/40 border-blue-500/20 hover:border-blue-400/40 hover:bg-blue-950/60',
      activeRing: 'border-[#46C1BE] ring-2 ring-[#46C1BE] bg-white/20 shadow-lg shadow-[#46C1BE]/20',
    },
    {
      key: 'active',
      label: isRTL ? 'المدارس النشطة' : 'Active Schools',
      subtitle: isRTL ? 'مفعلة وتعمل' : 'Operational',
      value: stats.active,
      icon: CheckCircle2,
      onClick: () => onStatusFilter('active'),
      active: activeStatusFilter === 'active',
      color: 'text-emerald-400',
      badgeBg: 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30',
      cardBg: 'bg-emerald-950/40 border-emerald-500/20 hover:border-emerald-400/40 hover:bg-emerald-950/60',
      activeRing: 'border-emerald-400 ring-2 ring-emerald-400 bg-white/20 shadow-lg shadow-emerald-500/20',
    },
    {
      key: 'suspended',
      label: isRTL ? 'المدارس الموقوفة' : 'Suspended',
      subtitle: isRTL ? 'تحتاج تدقيق' : 'Needs Review',
      value: stats.suspended,
      icon: XCircle,
      onClick: () => onStatusFilter('suspended'),
      active: activeStatusFilter === 'suspended',
      color: 'text-rose-400',
      badgeBg: 'bg-rose-500/20 text-rose-300 border border-rose-400/30',
      cardBg: 'bg-rose-950/40 border-rose-500/20 hover:border-rose-400/40 hover:bg-rose-950/60',
      activeRing: 'border-rose-400 ring-2 ring-rose-400 bg-white/20 shadow-lg shadow-rose-500/20',
    },
    {
      key: 'setup',
      label: isRTL ? 'المسودات' : 'Drafts',
      subtitle: isRTL ? 'قيد التهيئة' : 'In Setup',
      value: stats.drafts,
      icon: Clock,
      onClick: () => onStatusFilter('setup'),
      active: activeStatusFilter === 'setup',
      color: 'text-amber-400',
      badgeBg: 'bg-amber-500/20 text-amber-300 border border-amber-400/30',
      cardBg: 'bg-amber-950/40 border-amber-500/20 hover:border-amber-400/40 hover:bg-amber-950/60',
      activeRing: 'border-amber-400 ring-2 ring-amber-400 bg-white/20 shadow-lg shadow-amber-500/20',
    },
    {
      key: 'students',
      label: isRTL ? 'إجمالي الطلاب' : 'Students',
      subtitle: isRTL ? 'مقيدون بالمنظومة' : 'Enrolled',
      value: Number(stats.totalStudents || 0).toLocaleString(),
      icon: GraduationCap,
      color: 'text-sky-400',
      badgeBg: 'bg-sky-500/20 text-sky-300 border border-sky-400/30',
      cardBg: 'bg-sky-950/40 border-sky-500/20 hover:border-sky-400/40 hover:bg-sky-950/60',
    },
    {
      key: 'teachers',
      label: isRTL ? 'إجمالي المعلمين' : 'Teachers',
      subtitle: isRTL ? 'كادر تعليمي' : 'Faculty Staff',
      value: Number(stats.totalTeachers || 0).toLocaleString(),
      icon: UserCheck,
      color: 'text-teal-400',
      badgeBg: 'bg-teal-500/20 text-teal-300 border border-teal-400/30',
      cardBg: 'bg-teal-950/40 border-teal-500/20 hover:border-teal-400/40 hover:bg-teal-950/60',
    },
    {
      key: 'classes',
      label: isRTL ? 'الفصول الدراسية' : 'Classes',
      subtitle: isRTL ? 'شعبة مفعلة' : 'Active Sections',
      value: Number(stats.totalClasses || 0).toLocaleString(),
      icon: Layers,
      color: 'text-purple-400',
      badgeBg: 'bg-purple-500/20 text-purple-300 border border-purple-400/30',
      cardBg: 'bg-purple-950/40 border-purple-500/20 hover:border-purple-400/40 hover:bg-purple-950/60',
    },
  ];

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#1C3D74] via-[#163363] to-[#0d2244] p-6 sm:p-8 text-white shadow-2xl border border-white/15 backdrop-blur-xl font-tajawal">
      {/* Dynamic Ambient Background Highlights */}
      <div className="absolute top-0 right-1/4 w-96 h-96 bg-[#46C1BE]/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-80 h-80 bg-[#615090]/25 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(#46C1BE_1px,transparent_1px)] [background-size:24px_24px] opacity-10 pointer-events-none" />

      {/* Main Top Header Section */}
      <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">

        {/* Title & Badge Group */}
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 shadow-lg shadow-black/20 shrink-0 mt-1">
            <Building2 className="h-7 w-7 text-[#46C1BE]" />
          </div>

          <div className="space-y-1">
            {/* Live Indicator Overline Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/15 backdrop-blur-md text-[11px] font-bold text-white/90 shadow-inner">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#46C1BE] opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#46C1BE]" />
              </span>
              <span>{isRTL ? 'منظومة إدارة المستأجرين والمدارس' : 'Multi-Tenant Management Hub'}</span>
              <span className="text-white/40">•</span>
              <span className="text-[#46C1BE] font-mono font-bold">{isRTL ? 'محدث ومباشر' : 'Live & Synced'}</span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-black font-cairo tracking-tight text-white drop-shadow-xs">
              {isRTL ? 'إدارة المدارس والمستأجرين' : 'Schools & Tenants Management'}
            </h1>
            <p className="text-white/80 text-xs sm:text-sm font-medium leading-relaxed max-w-2xl">
              {isRTL
                ? 'المركز الموحد للتحكم في المدارس الأكاديمية، متابعة الجاهزية التشغيلية، والدخول المباشر كمدير مدرسة'
                : 'Unified console to manage school tenants, oversee operational readiness, and switch into school dashboards'}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5 flex-wrap w-full lg:w-auto justify-start lg:justify-end shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="rounded-2xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-11 px-4 backdrop-blur-md transition-all shadow-sm hover:scale-[1.02] active:scale-[0.98]"
            onClick={onRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} ${refreshing ? 'animate-spin text-[#46C1BE]' : ''}`} />
            <span>{isRTL ? 'تحديث' : 'Refresh'}</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="rounded-2xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-11 px-4 backdrop-blur-md transition-all shadow-sm hover:scale-[1.02] active:scale-[0.98]"
            onClick={onExport}
          >
            <Download className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-[#46C1BE]`} />
            <span>{isRTL ? 'تصدير CSV' : 'Export'}</span>
          </Button>

          <Button
            size="sm"
            className="rounded-2xl bg-[#46C1BE] hover:bg-[#3bb0ad] text-slate-950 font-black text-xs h-11 px-5 shadow-lg shadow-[#46C1BE]/25 gap-2 transition-all transform hover:scale-[1.03] active:scale-[0.98] border border-white/25"
            onClick={onOpenCreateWizard}
            data-testid="add-school-main-btn"
          >
            <Plus className="h-4.5 w-4.5 stroke-[3]" />
            <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
          </Button>
        </div>
      </div>

      {/* KPI Stats Interactive Ribbon */}
      <div className="relative z-10 mt-8 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 sm:gap-3.5">
        {statChips.map((chip) => {
          const Icon = chip.icon;
          const isClickable = !!chip.onClick;
          return (
            <button
              key={chip.key}
              type="button"
              onClick={chip.onClick}
              disabled={!isClickable}
              className={`group relative overflow-hidden rounded-2xl p-4 transition-all duration-300 border flex flex-col items-center justify-between min-h-[125px] ${
                chip.active
                  ? chip.activeRing + ' scale-[1.03]'
                  : chip.cardBg
              } ${isClickable ? 'cursor-pointer hover:-translate-y-1' : 'cursor-default'}`}
            >
              {/* Icon Container */}
              <div className="flex items-center justify-center mb-1">
                <div className={`p-2.5 rounded-xl backdrop-blur-md ${chip.badgeBg} transition-transform group-hover:scale-110 shadow-xs`}>
                  <Icon className={`h-4.5 w-4.5 ${chip.color}`} />
                </div>
              </div>

              {/* Number */}
              <p className="text-2xl sm:text-3xl font-black font-cairo text-white tracking-tight leading-none my-1 drop-shadow-xs">
                {chip.value}
              </p>

              {/* Labels */}
              <div className="text-center w-full">
                <p className="text-xs font-bold text-white/90 truncate">
                  {chip.label}
                </p>
                <p className="text-[10px] font-medium text-white/60 truncate mt-0.5">
                  {chip.subtitle}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
