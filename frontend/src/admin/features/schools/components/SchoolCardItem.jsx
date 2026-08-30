import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import {
  Building2, MapPin, ExternalLink, Eye, Users, GraduationCap, Layers,
  MoreVertical, Copy, Pause, Play, CheckCircle2, ShieldCheck, Mail
} from 'lucide-react';
import { toast } from 'sonner';
import { SCHOOL_STATUS, getLogoGradient, EDUCATIONAL_STAGES } from '../constants/schoolConstants';

export default function SchoolCardItem({
  school,
  onNavigateDetail,
  onEnterDashboard,
  canEnterDashboard,
  onOpenSuspendDialog,
  onOpenActivateDialog,
  isRTL,
}) {
  const statusCfg = SCHOOL_STATUS[school.status] || SCHOOL_STATUS.active;
  const gradient = getLogoGradient(school.id || school.code);

  const stageLabel = EDUCATIONAL_STAGES.find(s => s.value === school.stage)?.label || school.stage;

  const copyCode = (e) => {
    e.stopPropagation();
    if (school.code) {
      navigator.clipboard.writeText(school.code);
      toast.success(isRTL ? `تم نسخ كود المدرسة: ${school.code}` : `Copied tenant code: ${school.code}`);
    }
  };

  return (
    <Card
      className="group relative rounded-3xl border border-slate-200/80 dark:border-slate-800 shadow-sm hover:shadow-2xl hover:border-slate-300 dark:hover:border-slate-700 hover:-translate-y-1 transition-all duration-300 overflow-hidden bg-white dark:bg-slate-900 flex flex-col justify-between"
      data-testid={`school-card-${school.id}`}
    >
      <div>
        {/* Top Header with Multi-layer Dynamic Gradient */}
        <div className={`relative bg-gradient-to-br ${gradient} p-5 text-white overflow-hidden`}>
          {/* Subtle Ambient Texture & Overlay */}
          <div className="absolute inset-0 bg-black/15 pointer-events-none" />
          <div className="absolute -right-8 -top-8 w-32 h-32 bg-white/10 rounded-full blur-xl pointer-events-none" />
          <div className="absolute inset-0 bg-[radial-gradient(white_1px,transparent_1px)] [background-size:16px_16px] opacity-10 pointer-events-none" />

          {/* Top Row: Avatar + Name + Status Badge & Menu */}
          <div className="relative z-10 flex items-start justify-between gap-3">
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-13 h-13 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white font-black text-xl shadow-inner shrink-0 border border-white/30 group-hover:scale-105 transition-transform">
                {school.name?.trim().charAt(0) || 'م'}
              </div>
              <div className="min-w-0">
                <h3 className="font-cairo font-black text-base leading-snug truncate text-white drop-shadow-xs" title={school.name}>
                  {school.name}
                </h3>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  {school.code && (
                    <button
                      type="button"
                      onClick={copyCode}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-black/20 hover:bg-black/40 text-white/90 text-[11px] font-mono font-bold transition-colors border border-white/15"
                      title={isRTL ? 'انقر لنسخ الكود' : 'Click to copy code'}
                    >
                      <span>#{school.code}</span>
                      <Copy className="h-2.5 w-2.5 opacity-70" />
                    </button>
                  )}
                  {school.name_en && (
                    <span className="text-[11px] text-white/75 truncate max-w-[140px] font-sans">
                      {school.name_en}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Status Badge & Dropdown Actions */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className={`inline-flex items-center gap-1.5 text-[11px] font-extrabold px-2.5 py-1 rounded-full backdrop-blur-md ${
                school.status === 'active'
                  ? 'bg-emerald-500/25 text-emerald-100 border border-emerald-400/40'
                  : school.status === 'suspended'
                  ? 'bg-rose-500/25 text-rose-100 border border-rose-400/40'
                  : 'bg-amber-500/25 text-amber-100 border border-amber-400/40'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  school.status === 'active' ? 'bg-emerald-400 animate-pulse' : school.status === 'suspended' ? 'bg-rose-400' : 'bg-amber-400'
                }`} />
                <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
              </span>

              {/* Quick Actions Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 w-8 p-0 rounded-xl text-white/80 hover:text-white hover:bg-white/20"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-52 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl p-1.5 font-cairo z-50">
                  <DropdownMenuItem
                    onClick={() => onNavigateDetail(school.id)}
                    className="rounded-xl font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer"
                  >
                    <ExternalLink className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-[#46C1BE]`} />
                    <span>{isRTL ? 'الملف التفصيلي' : 'View Profile'}</span>
                  </DropdownMenuItem>
                  {school.code && (
                    <DropdownMenuItem
                      onClick={copyCode}
                      className="rounded-xl font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer"
                    >
                      <Copy className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-slate-400`} />
                      <span>{isRTL ? 'نسخ كود المستأجر' : 'Copy Code'}</span>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuSeparator />
                  {school.status === 'active' && onOpenSuspendDialog ? (
                    <DropdownMenuItem
                      onClick={() => onOpenSuspendDialog(school)}
                      className="rounded-xl font-bold text-xs py-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                    >
                      <Pause className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'}`} />
                      <span>{isRTL ? 'إيقاف المدرسة' : 'Suspend School'}</span>
                    </DropdownMenuItem>
                  ) : onOpenActivateDialog ? (
                    <DropdownMenuItem
                      onClick={() => onOpenActivateDialog(school)}
                      className="rounded-xl font-bold text-xs py-2 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 cursor-pointer"
                    >
                      <Play className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'}`} />
                      <span>{isRTL ? 'تفعيل المدرسة' : 'Activate School'}</span>
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>

          {/* Location & Tags Row */}
          <div className="relative z-10 flex items-center gap-2 mt-4 text-xs font-medium flex-wrap">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-white/15 backdrop-blur-md text-white border border-white/20 text-[11px] font-bold">
              <MapPin className="h-3 w-3 text-[#46C1BE]" />
              <span>{school.city || (isRTL ? 'غير محدد' : 'Unspecified')}</span>
              {school.region && <span className="opacity-80">/ {school.region}</span>}
            </span>

            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-white/15 backdrop-blur-md text-white border border-white/20 text-[11px] font-bold">
              <Building2 className="h-3 w-3 text-sky-300" />
              <span>{school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}</span>
            </span>

            {stageLabel && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-white/15 backdrop-blur-md text-white border border-white/20 text-[11px] font-bold truncate max-w-[130px]">
                <Layers className="h-3 w-3 text-purple-300" />
                <span className="truncate">{stageLabel}</span>
              </span>
            )}
          </div>
        </div>

        {/* Operational Metrics Cards */}
        <div className="p-4 grid grid-cols-3 gap-2.5 text-center border-b border-slate-100 dark:border-slate-800/80 bg-slate-50/40 dark:bg-slate-900/40">
          {/* Students */}
          <div className="bg-white dark:bg-slate-800/70 p-3 rounded-2xl border border-slate-200/70 dark:border-slate-800 shadow-2xs hover:border-sky-300 dark:hover:border-sky-700 transition-colors">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold mb-1 flex items-center justify-center gap-1">
              <GraduationCap className="h-3.5 w-3.5 text-sky-500" />
              <span>{isRTL ? 'الطلاب' : 'Students'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.student_count || 0).toLocaleString()}
            </p>
          </div>

          {/* Teachers */}
          <div className="bg-white dark:bg-slate-800/70 p-3 rounded-2xl border border-slate-200/70 dark:border-slate-800 shadow-2xs hover:border-purple-300 dark:hover:border-purple-700 transition-colors">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold mb-1 flex items-center justify-center gap-1">
              <Users className="h-3.5 w-3.5 text-purple-500" />
              <span>{isRTL ? 'المعلمين' : 'Teachers'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.teacher_count || 0).toLocaleString()}
            </p>
          </div>

          {/* Classes */}
          <div className="bg-white dark:bg-slate-800/70 p-3 rounded-2xl border border-slate-200/70 dark:border-slate-800 shadow-2xs hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors">
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-bold mb-1 flex items-center justify-center gap-1">
              <Layers className="h-3.5 w-3.5 text-emerald-500" />
              <span>{isRTL ? 'الفصول' : 'Classes'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.class_count || 0).toLocaleString()}
            </p>
          </div>
        </div>

        {/* Email or Contact Details strip */}
        {school.email && (
          <div className="px-4 py-2 bg-slate-50/60 dark:bg-slate-900/60 text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1.5 border-b border-slate-100 dark:border-slate-800/60 truncate">
            <Mail className="h-3 w-3 text-slate-400 shrink-0" />
            <span className="truncate">{school.email}</span>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="p-4 bg-white dark:bg-slate-900 flex items-center justify-between gap-2.5">
        <Button
          variant="outline"
          size="sm"
          className="flex-1 rounded-2xl h-10.5 px-3 font-bold text-xs border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 shadow-2xs gap-1.5 transition-all"
          onClick={() => onNavigateDetail(school.id)}
        >
          <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
          <span>{isRTL ? 'الملف التفصيلي' : 'Profile'}</span>
        </Button>

        <Button
          size="sm"
          className="flex-1 rounded-2xl h-10.5 px-4 bg-gradient-to-r from-[#1C3D74] to-[#152e57] hover:from-[#152e57] hover:to-[#0f2240] text-white font-black text-xs shadow-md shadow-[#1C3D74]/25 disabled:opacity-40 gap-1.5 transition-all transform active:scale-95"
          onClick={() => onEnterDashboard(school)}
          disabled={!canEnterDashboard(school)}
        >
          <Eye className="h-3.5 w-3.5 text-[#46C1BE]" />
          <span>{isRTL ? 'دخول كمدير' : 'Dashboard'}</span>
        </Button>
      </div>
    </Card>
  );
}
