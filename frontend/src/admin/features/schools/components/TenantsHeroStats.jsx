import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Building2, Plus, Users, GraduationCap, RefreshCw,
  CheckCircle2, Clock, Download, XCircle, UserCheck, Layers
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
      label: isRTL ? 'إجمالي المدارس' : 'Total Schools',
      value: stats.total,
      icon: Building2,
      onClick: () => onStatusFilter(null),
      active: activeStatusFilter === null,
      color: 'text-white',
      badgeColor: 'bg-white/10 text-white',
    },
    {
      label: isRTL ? 'المدارس النشطة' : 'Active Schools',
      value: stats.active,
      icon: CheckCircle2,
      onClick: () => onStatusFilter('active'),
      active: activeStatusFilter === 'active',
      color: 'text-emerald-300',
      badgeColor: 'bg-emerald-500/20 text-emerald-300',
    },
    {
      label: isRTL ? 'المدارس الموقوفة' : 'Suspended',
      value: stats.suspended,
      icon: XCircle,
      onClick: () => onStatusFilter('suspended'),
      active: activeStatusFilter === 'suspended',
      color: 'text-rose-300',
      badgeColor: 'bg-rose-500/20 text-rose-300',
    },
    {
      label: isRTL ? 'المسودات' : 'Drafts',
      value: stats.drafts,
      icon: Clock,
      onClick: () => onStatusFilter('setup'),
      active: activeStatusFilter === 'setup',
      color: 'text-amber-300',
      badgeColor: 'bg-amber-500/20 text-amber-300',
    },
    {
      label: isRTL ? 'إجمالي الطلاب' : 'Students',
      value: Number(stats.totalStudents || 0).toLocaleString(),
      icon: GraduationCap,
      color: 'text-sky-300',
      badgeColor: 'bg-sky-500/20 text-sky-300',
    },
    {
      label: isRTL ? 'إجمالي المعلمين' : 'Teachers',
      value: Number(stats.totalTeachers || 0).toLocaleString(),
      icon: UserCheck,
      color: 'text-teal-300',
      badgeColor: 'bg-teal-500/20 text-teal-300',
    },
    {
      label: isRTL ? 'الفصول الدراسية' : 'Classes',
      value: Number(stats.totalClasses || 0).toLocaleString(),
      icon: Layers,
      color: 'text-purple-300',
      badgeColor: 'bg-purple-500/20 text-purple-300',
    },
  ];

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#1C3D74] via-[#152e57] to-[#1C3D74] p-6 sm:p-8 text-white shadow-xl border border-white/10">
      {/* Background Accent Grid */}
      <div className="absolute inset-0 bg-[radial-gradient(#46C1BE_1px,transparent_1px)] [background-size:20px_20px] opacity-10 pointer-events-none" />

      {/* Top Bar Header & Action Buttons */}
      <div className="relative flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
        <div className="flex items-center gap-3.5">
          <div className="w-13 h-13 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 shadow-inner">
            <Building2 className="h-7 w-7 text-[#46C1BE]" />
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold font-cairo tracking-tight text-white">
              {isRTL ? 'إدارة المدارس والمستأجرين' : 'Schools & Tenants Management'}
            </h1>
            <p className="text-white/80 text-xs sm:text-sm font-medium mt-0.5">
              {isRTL
                ? 'المركز الموحد لإدارة المستأجرين، المدارس الأكاديمية، والتحكم في إعدادات التشغيل'
                : 'Unified hub for managing school tenants, academic setups, and operations'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap w-full md:w-auto justify-start md:justify-end">
          <Button
            variant="outline"
            size="sm"
            className="rounded-xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-10 px-3.5 backdrop-blur-md transition-all shadow-xs"
            onClick={onRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'} ${refreshing ? 'animate-spin' : ''}`} />
            <span>{isRTL ? 'تحديث' : 'Refresh'}</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="rounded-xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-10 px-3.5 backdrop-blur-md transition-all shadow-xs"
            onClick={onExport}
          >
            <Download className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'} text-[#46C1BE]`} />
            <span>{isRTL ? 'تصدير CSV' : 'Export'}</span>
          </Button>

          <Button
            size="sm"
            className="rounded-xl bg-[#46C1BE] hover:bg-[#38a19e] text-slate-950 font-black text-xs h-10 px-5 shadow-lg shadow-[#46C1BE]/25 gap-1.5 transition-all transform hover:-translate-y-0.5"
            onClick={onOpenCreateWizard}
            data-testid="add-school-main-btn"
          >
            <Plus className="h-4 w-4 stroke-[3]" />
            <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
          </Button>
        </div>
      </div>

      {/* KPI Stats Ribbon */}
      <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {statChips.map((chip, idx) => {
          const Icon = chip.icon;
          const isClickable = !!chip.onClick;
          return (
            <button
              key={idx}
              type="button"
              onClick={chip.onClick}
              disabled={!isClickable}
              className={`rounded-2xl p-3 text-center transition-all border text-start sm:text-center ${
                chip.active
                  ? 'bg-white/25 border-[#46C1BE] ring-2 ring-[#46C1BE] shadow-md scale-[1.02]'
                  : 'bg-white/10 border-white/10 hover:bg-white/15'
              } ${isClickable ? 'cursor-pointer' : 'cursor-default'}`}
            >
              <div className="flex items-center justify-center mb-1.5">
                <div className={`p-1.5 rounded-xl ${chip.badgeColor}`}>
                  <Icon className={`h-4 w-4 ${chip.color}`} />
                </div>
              </div>
              <p className="text-xl font-black font-cairo leading-tight">{chip.value}</p>
              <p className="text-[11px] font-medium text-white/75 mt-0.5 truncate">{chip.label}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
