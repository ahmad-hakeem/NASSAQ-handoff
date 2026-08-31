import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Users, GraduationCap, BookOpen, UserCheck, RefreshCw, LayoutDashboard,
  Play, Pause, Hash, MapPin, Building2, ExternalLink
} from 'lucide-react';
import { SCHOOL_STATUS } from '../../constants/schoolConstants';

export default function SchoolDetailHeader({
  school,
  stats,
  onRefresh,
  onEnterDashboard,
  canEnterDashboard,
  onOpenSuspendDialog,
  onOpenActivateDialog,
  isRTL,
  t,
}) {
  const status = school?.status || 'active';
  const statusCfg = SCHOOL_STATUS[status] || SCHOOL_STATUS.active;
  const isSuspended = status === 'suspended';

  const kpiTiles = [
    {
      label: t('students') || (isRTL ? 'الطلاب المقيدون' : 'Enrolled Students'),
      value: stats?.total_students || 0,
      icon: GraduationCap,
      iconColor: 'text-sky-600 dark:text-sky-400',
      iconBg: 'bg-sky-50 dark:bg-sky-950/60 border border-sky-100 dark:border-sky-900/60',
    },
    {
      label: t('teachers') || (isRTL ? 'الكادر التعليمي' : 'Teaching Staff'),
      value: stats?.total_teachers || 0,
      icon: UserCheck,
      iconColor: 'text-teal-600 dark:text-teal-400',
      iconBg: 'bg-teal-50 dark:bg-teal-950/60 border border-teal-100 dark:border-teal-900/60',
    },
    {
      label: t('classes2') || (isRTL ? 'الفصول والشعب' : 'Classes & Sections'),
      value: stats?.total_classes || 0,
      icon: BookOpen,
      iconColor: 'text-purple-600 dark:text-purple-400',
      iconBg: 'bg-purple-50 dark:bg-purple-950/60 border border-purple-100 dark:border-purple-900/60',
    },
    {
      label: t('users') || (isRTL ? 'إجمالي الحسابات' : 'Total Accounts'),
      value: stats?.total_users || 0,
      icon: Users,
      iconColor: 'text-[#1C3D74] dark:text-[#46C1BE]',
      iconBg: 'bg-blue-50 dark:bg-blue-950/60 border border-blue-100 dark:border-blue-900/60',
    },
  ];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-sm p-5 sm:p-6 font-tajawal transition-all">
      {/* Top Main Row: School Profile & Actions */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-5">
        {/* School Avatar + Information */}
        <div className="flex items-start sm:items-center gap-4 min-w-0">
          {/* Logo / Monogram Avatar */}
          <div className="w-16 h-16 sm:w-18 sm:h-18 rounded-2xl bg-gradient-to-br from-[#1C3D74] to-[#152e57] text-white flex items-center justify-center flex-shrink-0 shadow-sm border border-slate-100 dark:border-slate-700 select-none">
            <span className="text-2xl sm:text-3xl font-black font-cairo">
              {school?.name?.trim()?.charAt(0) || <Building2 className="h-7 w-7 text-white" />}
            </span>
          </div>

          {/* School Name & Meta Tags */}
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-black font-cairo text-slate-900 dark:text-white tracking-tight leading-tight">
                {school?.name || (isRTL ? 'مدرسة غير محددة' : 'Unnamed School')}
              </h1>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border ${statusCfg.badge}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot} animate-pulse`} />
                <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
              </span>
            </div>

            {school?.name_en && (
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 font-medium" dir="ltr">
                {school.name_en}
              </p>
            )}

            {/* Meta Tags Row */}
            <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700/80 font-mono font-bold">
                <Hash className="h-3.5 w-3.5 text-[#46C1BE]" />
                <span>{school?.code || '—'}</span>
              </div>

              {school?.city && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700/80 font-medium">
                  <MapPin className="h-3.5 w-3.5 text-rose-500" />
                  <span>{school.city}</span>
                </div>
              )}

              {school?.school_type && (
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700/80 font-medium">
                  <Building2 className="h-3.5 w-3.5 text-[#1C3D74] dark:text-[#46C1BE]" />
                  <span>
                    {school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons with Proportional Ergonomic Sizing */}
        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto justify-start lg:justify-end">
          <Button
            variant="outline"
            className="rounded-xl border-slate-200 dark:border-slate-700 bg-white hover:bg-slate-50 text-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700 font-bold text-xs sm:text-sm h-10 px-4 shadow-2xs gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
            onClick={onRefresh}
          >
            <RefreshCw className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <span>{t('refresh') || (isRTL ? 'تحديث' : 'Refresh')}</span>
          </Button>

          <Button
            className="rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white font-bold text-xs sm:text-sm h-10 px-5 shadow-sm shadow-[#1C3D74]/20 disabled:opacity-40 gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
            onClick={onEnterDashboard}
            disabled={!canEnterDashboard(school)}
            title={!canEnterDashboard(school) ? t('openDashboardBlockedHint') : undefined}
          >
            <LayoutDashboard className="h-4 w-4 text-[#46C1BE]" />
            <span>{t('openDashboard') || (isRTL ? 'فتح لوحة التحكم' : 'Open Dashboard')}</span>
            <ExternalLink className="h-3.5 w-3.5 opacity-60" />
          </Button>

          {isSuspended ? (
            <Button
              className="rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:hover:bg-emerald-900/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-bold text-xs sm:text-sm h-10 px-4.5 gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
              onClick={onOpenActivateDialog}
            >
              <Play className="h-4 w-4 fill-current text-emerald-600 dark:text-emerald-400" />
              <span>{t('activateSchool') || (isRTL ? 'تفعيل المدرسة' : 'Activate')}</span>
            </Button>
          ) : (
            <Button
              className="rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800 font-bold text-xs sm:text-sm h-10 px-4.5 gap-2 transition-all hover:scale-[1.02] active:scale-[0.98]"
              onClick={onOpenSuspendDialog}
            >
              <Pause className="h-4 w-4 fill-current text-rose-600 dark:text-rose-400" />
              <span>{t('suspendSchool') || (isRTL ? 'تعليق المدرسة' : 'Suspend')}</span>
            </Button>
          )}
        </div>
      </div>

      {/* KPI Stats Ribbon - Clean Minimalist Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-3.5 pt-5 mt-5 border-t border-slate-100 dark:border-slate-800/80">
        {kpiTiles.map((tile, i) => {
          const Icon = tile.icon;
          return (
            <div
              key={i}
              className="p-3.5 sm:p-4 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800/80 flex items-center justify-between gap-3 transition-all hover:bg-slate-100/70 dark:hover:bg-slate-800/70"
            >
              <div className="space-y-1 min-w-0">
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 truncate">
                  {tile.label}
                </p>
                <p className="text-xl sm:text-2xl font-black font-cairo text-slate-900 dark:text-white font-mono tracking-tight">
                  {tile.value.toLocaleString()}
                </p>
              </div>

              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${tile.iconBg} ${tile.iconColor} shadow-2xs`}>
                <Icon className="h-5 w-5" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
