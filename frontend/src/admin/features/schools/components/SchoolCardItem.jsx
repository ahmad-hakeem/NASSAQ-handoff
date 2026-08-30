import React from 'react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import {
  MapPin, ExternalLink, Eye, Users, GraduationCap, Layers,
  MoreHorizontal, Copy, Pause, Play
} from 'lucide-react';
import { toast } from 'sonner';
import { SCHOOL_STATUS, EDUCATIONAL_STAGES, getSchoolInitials } from '../constants/schoolConstants';

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
  const stageLabel = EDUCATIONAL_STAGES.find(s => s.value === school.stage)?.label || school.stage;

  const copyCode = (e) => {
    e.stopPropagation();
    if (school.code) {
      navigator.clipboard.writeText(school.code);
      toast.success(isRTL ? `تم نسخ كود المدرسة: ${school.code}` : `Copied code: ${school.code}`);
    }
  };

  return (
    <div
      className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/90 dark:border-slate-800 shadow-sm hover:shadow-md hover:border-slate-300 dark:hover:border-slate-700 transition-all p-5 flex flex-col justify-between font-tajawal group"
      data-testid={`school-card-${school.id}`}
    >
      <div>
        {/* Top Header: Avatar, Name, Status, and Menu */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-11 h-11 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200/90 dark:border-slate-700 text-[#1C3D74] dark:text-[#46C1BE] font-black font-cairo text-sm flex items-center justify-center shrink-0 shadow-2xs tracking-wider">
              {getSchoolInitials(school.name, school.name_en)}
            </div>

            <div className="min-w-0">
              <h3 className="text-sm sm:text-base font-bold font-cairo text-slate-900 dark:text-white truncate" title={school.name}>
                {school.name}
              </h3>
              <div className="flex items-center gap-2 mt-0.5">
                {school.code && (
                  <button
                    type="button"
                    onClick={copyCode}
                    className="text-[11px] font-mono text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 inline-flex items-center gap-1 transition-colors"
                    title={isRTL ? 'نسخ الكود' : 'Copy code'}
                  >
                    <span>#{school.code}</span>
                    <Copy className="h-2.5 w-2.5 opacity-60" />
                  </button>
                )}
                {school.name_en && (
                  <span className="text-[11px] text-slate-400 truncate max-w-[120px] font-sans">
                    {school.name_en}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-0.5 rounded-full ${statusCfg.badge}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`} />
              <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
            </span>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-48 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-xl shadow-lg p-1 font-cairo z-50">
                <DropdownMenuItem
                  onClick={() => onNavigateDetail(school.id)}
                  className="rounded-lg font-bold text-xs py-2 cursor-pointer gap-2"
                >
                  <ExternalLink className="h-4 w-4 text-slate-500" />
                  <span>{isRTL ? 'الملف التفصيلي' : 'Profile'}</span>
                </DropdownMenuItem>
                {school.code && (
                  <DropdownMenuItem
                    onClick={copyCode}
                    className="rounded-lg font-bold text-xs py-2 cursor-pointer gap-2"
                  >
                    <Copy className="h-4 w-4 text-slate-500" />
                  <span>{isRTL ? 'نسخ كود المستأجر' : 'Copy Code'}</span>
                </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                {school.status === 'active' && onOpenSuspendDialog ? (
                  <DropdownMenuItem
                    onClick={() => onOpenSuspendDialog(school)}
                    className="rounded-lg font-bold text-xs py-2 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer gap-2"
                  >
                    <Pause className="h-4 w-4" />
                    <span>{isRTL ? 'إيقاف المدرسة' : 'Suspend'}</span>
                  </DropdownMenuItem>
                ) : onOpenActivateDialog ? (
                  <DropdownMenuItem
                    onClick={() => onOpenActivateDialog(school)}
                    className="rounded-lg font-bold text-xs py-2 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 cursor-pointer gap-2"
                  >
                    <Play className="h-4 w-4" />
                    <span>{isRTL ? 'تفعيل المدرسة' : 'Activate'}</span>
                  </DropdownMenuItem>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* Location & Tags Row */}
        <div className="flex items-center gap-1.5 flex-wrap mb-4">
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg">
            <MapPin className="h-3 w-3 text-slate-400" />
            <span>{school.city || (isRTL ? 'غير محدد' : '—')}</span>
            {school.region && <span className="text-slate-400">/ {school.region}</span>}
          </span>

          <span className="inline-flex items-center text-[11px] font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg">
            {school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}
          </span>

          {stageLabel && (
            <span className="inline-flex items-center text-[11px] font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg truncate max-w-[130px]">
              {stageLabel}
            </span>
          )}
        </div>

        {/* Operational Metrics 3-Col Box */}
        <div className="bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 rounded-xl p-3 grid grid-cols-3 gap-2 text-center mb-4">
          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium flex items-center justify-center gap-1 mb-0.5">
              <GraduationCap className="h-3.5 w-3.5 text-sky-500" />
              <span>{isRTL ? 'الطلاب' : 'Students'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.student_count || 0).toLocaleString()}
            </p>
          </div>

          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium flex items-center justify-center gap-1 mb-0.5">
              <Users className="h-3.5 w-3.5 text-purple-500" />
              <span>{isRTL ? 'المعلمين' : 'Teachers'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.teacher_count || 0).toLocaleString()}
            </p>
          </div>

          <div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium flex items-center justify-center gap-1 mb-0.5">
              <Layers className="h-3.5 w-3.5 text-teal-500" />
              <span>{isRTL ? 'الفصول' : 'Classes'}</span>
            </p>
            <p className="text-base font-black text-slate-900 dark:text-white font-mono">
              {(school.class_count || 0).toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Action Footer Buttons */}
      <div className="flex items-center gap-2.5 pt-3.5 border-t border-slate-100 dark:border-slate-800">
        <Button
          variant="outline"
          onClick={() => onNavigateDetail(school.id)}
          className="flex-1 h-10 rounded-xl px-3 font-bold font-cairo text-xs border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white gap-2 shadow-2xs transition-colors"
        >
          <ExternalLink className="h-4 w-4 text-slate-400 shrink-0" />
          <span>{isRTL ? 'الملف التفصيلي' : 'Profile'}</span>
        </Button>

        <Button
          onClick={() => onEnterDashboard(school)}
          disabled={!canEnterDashboard(school)}
          className="flex-1 h-10 rounded-xl px-3 bg-[#1C3D74] hover:bg-[#152e57] text-white font-bold font-cairo text-xs gap-2 shadow-xs disabled:opacity-40 transition-colors"
        >
          <Eye className="h-4 w-4 text-[#46C1BE] shrink-0" />
          <span>{isRTL ? 'دخول كمدير' : 'Dashboard'}</span>
        </Button>
      </div>
    </div>
  );
}
