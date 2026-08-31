import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  Clock, MapPin, FileEdit, Trash2, Loader2,
  ChevronDown, ChevronUp, Building2, GraduationCap, Calendar, UserCheck
} from 'lucide-react';
import { getSchoolInitials, EDUCATIONAL_STAGES } from '../constants/schoolConstants';

export default function TenantsDraftsSection({
  draftSchools,
  showDrafts,
  onToggleShowDrafts,
  onNavigateToDraft,
  onDeleteDraft,
  deletingDraftId,
  isRTL,
}) {
  if (!draftSchools || draftSchools.length === 0) return null;

  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return null;
      return d.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return null;
    }
  };

  return (
    <div className="bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/60 rounded-2xl p-4 sm:p-5 font-tajawal transition-all">
      {/* Banner Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 flex items-center justify-center shrink-0">
            <Clock className="h-4.5 w-4.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-xs sm:text-sm font-cairo text-amber-950 dark:text-amber-100">
                {isRTL ? 'مسودات المدارس قيد التهيئة' : 'School Setup Drafts'}
              </h3>
              <Badge className="bg-amber-200/80 text-amber-900 dark:bg-amber-900 dark:text-amber-200 text-[10px] font-bold px-2 py-0.5 border-0">
                {draftSchools.length}
              </Badge>
            </div>
            <p className="text-[11px] sm:text-xs text-amber-800/80 dark:text-amber-300/80 font-medium">
              {isRTL
                ? 'مدارس تم حفظ بياناتها كمسودة أولية ويمكنك استكمال خطوات إعدادها في أي وقت'
                : 'Schools saved as drafts that can be finalized at any time'}
            </p>
          </div>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleShowDrafts}
          className="h-8 px-3 text-xs font-bold text-amber-900 dark:text-amber-200 hover:bg-amber-100/60 dark:hover:bg-amber-900/40 rounded-xl gap-1"
        >
          {showDrafts ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              <span>{isRTL ? 'إخفاء' : 'Hide'}</span>
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              <span>{isRTL ? 'عرض' : 'Show'}</span>
            </>
          )}
        </Button>
      </div>

      {/* Draft Cards Grid */}
      {showDrafts && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 mt-3.5 pt-3.5 border-t border-amber-200/60 dark:border-amber-800/50">
          {draftSchools.map((draft) => {
            const initials = getSchoolInitials(draft.name, draft.name_en);
            const stageObj = EDUCATIONAL_STAGES.find((s) => s.value === draft.stage);
            const stageLabel = isRTL ? stageObj?.label : stageObj?.label_en || draft.stage;
            const formattedDate = formatDate(draft.updated_at || draft.created_at);

            return (
              <div
                key={draft.id}
                className="group bg-white dark:bg-slate-900 rounded-2xl border border-amber-200/90 dark:border-amber-800/70 p-4 sm:p-4.5 shadow-xs hover:shadow-md hover:border-amber-300 dark:hover:border-amber-600 transition-all duration-200 flex flex-col justify-between"
              >
                <div>
                  {/* Card Header: Avatar + Title & Subtitle + Status Badge */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-10 h-10 rounded-xl bg-amber-100/70 dark:bg-amber-900/40 border border-amber-200/90 dark:border-amber-800/80 text-amber-900 dark:text-amber-200 font-bold font-cairo text-xs flex items-center justify-center shrink-0 shadow-2xs tracking-wide">
                        {initials && initials !== 'م د' ? (
                          <span>{initials}</span>
                        ) : (
                          <Building2 className="h-4.5 w-4.5 text-amber-700 dark:text-amber-300" />
                        )}
                      </div>

                      <div className="min-w-0">
                        <h4
                          className="text-xs sm:text-sm font-bold text-slate-900 dark:text-white font-cairo truncate leading-snug"
                          title={draft.name}
                        >
                          {draft.name || (isRTL ? 'مسودة مدرسة جديدة' : 'New School Draft')}
                        </h4>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {draft.code && (
                            <span className="text-[10px] font-mono text-slate-400">
                              #{draft.code}
                            </span>
                          )}
                          <span className="text-[11px] text-slate-400 font-medium truncate">
                            {isRTL ? 'قيد الإعداد' : 'In Setup'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-800 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-500/25 shrink-0 font-cairo">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                      <span>{isRTL ? 'مسودة' : 'Draft'}</span>
                    </span>
                  </div>

                  {/* Info Chips Section */}
                  <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    {/* Location Chip */}
                    <div className="inline-flex items-center gap-1 text-[11px] text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 px-2 py-0.5 rounded-lg border border-slate-200/60 dark:border-slate-700/60">
                      <MapPin className="h-3 w-3 text-amber-500 shrink-0" />
                      <span className="truncate max-w-[130px]">
                        {draft.city || (isRTL ? 'المدينة غير محددة' : 'City unset')}
                        {draft.region ? ` • ${draft.region}` : ''}
                      </span>
                    </div>

                    {/* Stage Chip */}
                    <div className="inline-flex items-center gap-1 text-[11px] text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 px-2 py-0.5 rounded-lg border border-slate-200/60 dark:border-slate-700/60">
                      <GraduationCap className="h-3 w-3 text-blue-500 shrink-0" />
                      <span className="truncate max-w-[120px]">
                        {stageLabel || (isRTL ? 'المرحلة غير محددة' : 'Stage unset')}
                      </span>
                    </div>

                    {/* Date Chip */}
                    {formattedDate && (
                      <div className="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/60 px-2 py-0.5 rounded-lg border border-slate-200/60 dark:border-slate-700/60">
                        <Calendar className="h-3 w-3 text-slate-400 shrink-0" />
                        <span>{formattedDate}</span>
                      </div>
                    )}

                    {/* Principal Chip */}
                    {draft.principal_name && (
                      <div className="inline-flex items-center gap-1 text-[11px] text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 px-2 py-0.5 rounded-lg border border-slate-200/60 dark:border-slate-700/60">
                        <UserCheck className="h-3 w-3 text-emerald-500 shrink-0" />
                        <span className="truncate max-w-[120px]">{draft.principal_name}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Footer: Action Buttons */}
                <div className="flex items-center gap-2.5 pt-3.5 border-t border-slate-100 dark:border-slate-800 mt-2">
                  <Button
                    onClick={() => onNavigateToDraft(draft.id)}
                    className="flex-1 h-10 rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white font-bold font-cairo text-xs gap-2 shadow-xs transition-all group/btn"
                  >
                    <FileEdit className="h-4 w-4 text-[#46C1BE] shrink-0 transition-transform group-hover/btn:scale-110" />
                    <span>{isRTL ? 'استكمال الإعداد' : 'Resume Setup'}</span>
                  </Button>

                  <Button
                    variant="outline"
                    onClick={() => onDeleteDraft(draft)}
                    disabled={deletingDraftId === draft.id}
                    className="h-10 w-10 p-0 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 border border-slate-200 dark:border-slate-800 hover:border-rose-200 dark:hover:border-rose-900/60 transition-colors shrink-0"
                    title={isRTL ? 'حذف المسودة' : 'Delete Draft'}
                  >
                    {deletingDraftId === draft.id ? (
                      <Loader2 className="h-4 w-4 animate-spin text-rose-500" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
