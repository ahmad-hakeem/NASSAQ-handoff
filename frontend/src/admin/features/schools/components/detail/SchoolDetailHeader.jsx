import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  Users, GraduationCap, BookOpen, UserCheck, RefreshCw, LayoutDashboard,
  Play, Pause, Hash, MapPin, Building2
} from 'lucide-react';
import { SCHOOL_STATUS, getLogoGradient } from '../../constants/schoolConstants';

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
  const gradient = getLogoGradient(school?.id);

  const kpiTiles = [
    { label: t('users') || (isRTL ? 'المستخدمون' : 'Users'), value: stats?.total_users || 0, icon: Users, color: 'text-white' },
    { label: t('students') || (isRTL ? 'الطلاب' : 'Students'), value: stats?.total_students || 0, icon: GraduationCap, color: 'text-sky-300' },
    { label: t('teachers') || (isRTL ? 'المعلمون' : 'Teachers'), value: stats?.total_teachers || 0, icon: UserCheck, color: 'text-teal-300' },
    { label: t('classes2') || (isRTL ? 'الفصول الدراسية' : 'Classes'), value: stats?.total_classes || 0, icon: BookOpen, color: 'text-purple-300' },
  ];

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#1C3D74] via-[#152e57] to-[#1C3D74] p-6 sm:p-8 text-white shadow-xl border border-white/10">
      {/* Background radial accent */}
      <div className="absolute inset-0 bg-[radial-gradient(#46C1BE_1px,transparent_1px)] [background-size:20px_20px] opacity-10 pointer-events-none" />

      {/* Main Header Row */}
      <div className="relative flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
        <div className="flex items-center gap-4">
          <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center flex-shrink-0 border-2 border-white/20 shadow-lg`}>
            <span className="text-2xl font-black text-white font-cairo">
              {school?.name?.charAt(0) || 'م'}
            </span>
          </div>
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold font-cairo leading-tight text-white">
              {school?.name}
            </h1>
            {school?.name_en && (
              <p className="text-white/70 text-sm mt-0.5 font-medium">{school.name_en}</p>
            )}
            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-white/80 font-medium">
              <span className="flex items-center gap-1">
                <Hash className="h-3.5 w-3.5 text-[#46C1BE]" />
                <span className="font-mono font-bold">{school?.code || '—'}</span>
              </span>
              {school?.city && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-3.5 w-3.5 text-slate-300" />
                  <span>{school.city}</span>
                </span>
              )}
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/10 backdrop-blur-md border border-white/15">
                <div className={`w-2 h-2 rounded-full ${statusCfg.dot} animate-pulse`} />
                <span className="font-bold">{isRTL ? statusCfg.label : statusCfg.label_en}</span>
              </span>
            </div>
          </div>
        </div>

        {/* Action CTAs */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto justify-start md:justify-end">
          <Button
            size="sm"
            variant="outline"
            className="rounded-xl border-white/20 bg-white/10 hover:bg-white/20 text-white font-bold text-xs h-10 px-3.5 backdrop-blur-md shadow-xs"
            onClick={onRefresh}
          >
            <RefreshCw className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
            <span>{t('refresh') || (isRTL ? 'تحديث' : 'Refresh')}</span>
          </Button>

          <Button
            size="sm"
            className="rounded-xl bg-[#46C1BE] hover:bg-[#38a19e] text-slate-950 font-black text-xs h-10 px-5 shadow-lg shadow-[#46C1BE]/20 disabled:opacity-40 gap-1.5 transition-all"
            onClick={onEnterDashboard}
            disabled={!canEnterDashboard(school)}
            title={!canEnterDashboard(school) ? t('openDashboardBlockedHint') : undefined}
          >
            <LayoutDashboard className="h-4 w-4" />
            <span>{t('openDashboard') || (isRTL ? 'دخول لوحة المدرسة' : 'Open Dashboard')}</span>
          </Button>

          {isSuspended ? (
            <Button
              size="sm"
              className="rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-10 px-4 shadow-md gap-1.5"
              onClick={onOpenActivateDialog}
            >
              <Play className="h-4 w-4" />
              <span>{t('activateSchool') || (isRTL ? 'تفعيل المدرسة' : 'Activate')}</span>
            </Button>
          ) : (
            <Button
              size="sm"
              className="rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs h-10 px-4 shadow-md gap-1.5"
              onClick={onOpenSuspendDialog}
            >
              <Pause className="h-4 w-4" />
              <span>{t('suspendSchool') || (isRTL ? 'إيقاف المدرسة' : 'Suspend')}</span>
            </Button>
          )}
        </div>
      </div>

      {/* KPI Stats Ribbon */}
      <div className="relative mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {kpiTiles.map((tile, i) => {
          const Icon = tile.icon;
          return (
            <div
              key={i}
              className="bg-white/10 backdrop-blur-md rounded-2xl p-3.5 text-center border border-white/10 shadow-xs"
            >
              <Icon className={`h-5 w-5 mx-auto mb-1 ${tile.color}`} />
              <p className="text-xl font-black font-cairo font-mono">{tile.value.toLocaleString()}</p>
              <p className="text-[11px] font-medium text-white/75 mt-0.5">{tile.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
