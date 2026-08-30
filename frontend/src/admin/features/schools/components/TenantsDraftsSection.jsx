import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Clock, MapPin, FileEdit, Trash2, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

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

  return (
    <div className="relative overflow-hidden rounded-3xl bg-amber-50/70 dark:bg-amber-950/20 border border-amber-300/80 dark:border-amber-800/60 p-5 sm:p-6 shadow-sm backdrop-blur-md font-tajawal transition-all">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-amber-500/15 border border-amber-500/30 text-amber-700 dark:text-amber-300 flex items-center justify-center shadow-inner shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-extrabold text-sm sm:text-base font-cairo text-amber-950 dark:text-amber-100">
                {isRTL ? 'مسودات المدارس قيد التهيئة' : 'School Setup Drafts'}
              </h3>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-amber-500/20 text-amber-900 dark:text-amber-200 border border-amber-500/30 font-mono">
                {draftSchools.length} {isRTL ? (draftSchools.length === 1 ? 'مسودة' : 'مسودات') : (draftSchools.length === 1 ? 'draft' : 'drafts')}
              </span>
            </div>
            <p className="text-xs text-amber-900/80 dark:text-amber-300/80 font-medium mt-0.5">
              {isRTL
                ? 'مدارس تم حفظ بياناتها كمسودة أولية ويمكنك استكمال خطوات إعدادها في أي وقت'
                : 'Schools saved as drafts that can be completed and finalized at any time'}
            </p>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={onToggleShowDrafts}
          className="rounded-2xl h-9 px-3.5 text-xs font-bold text-amber-950 dark:text-amber-200 border-amber-300 dark:border-amber-800 bg-white/60 dark:bg-slate-900/60 hover:bg-amber-100/60 dark:hover:bg-amber-950/40 shadow-xs"
        >
          {showDrafts ? (
            <>
              <ChevronUp className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
              <span>{isRTL ? 'إخفاء المسودات' : 'Hide Drafts'}</span>
            </>
          ) : (
            <>
              <ChevronDown className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
              <span>{isRTL ? 'عرض المسودات' : 'Show Drafts'}</span>
            </>
          )}
        </Button>
      </div>

      {/* Draft Cards */}
      {showDrafts && (
        <div className={`mt-2 ${
          draftSchools.length === 1
            ? 'max-w-xl'
            : draftSchools.length === 2
            ? 'grid grid-cols-1 md:grid-cols-2 gap-4 max-w-4xl'
            : 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
        }`}>
          {draftSchools.map((draft) => (
            <div
              key={draft.id}
              className="group p-4.5 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200/90 dark:border-amber-800/80 shadow-xs hover:shadow-md hover:border-amber-400 dark:hover:border-amber-700 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h4 className="text-sm font-black text-slate-900 dark:text-white line-clamp-1 font-cairo" title={draft.name}>
                    {draft.name || (isRTL ? 'مسودة مدرسة بدون اسم' : 'Untitled Draft')}
                  </h4>
                  <Badge className="text-[10px] bg-amber-100/90 text-amber-900 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800 shrink-0 font-bold">
                    {isRTL ? 'مسودة' : 'Draft'}
                  </Badge>
                </div>

                <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mb-4">
                  <MapPin className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                  <span>{draft.city || (isRTL ? 'المدينة غير محددة' : 'City unset')}</span>
                  {draft.region && <span className="opacity-75">• {draft.region}</span>}
                </p>
              </div>

              <div className="flex items-center gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <Button
                  size="sm"
                  className="flex-1 h-9 rounded-xl bg-gradient-to-r from-[#1C3D74] to-[#152e57] hover:from-[#152e57] hover:to-[#0e213d] text-white text-xs font-black gap-1.5 shadow-sm shadow-[#1C3D74]/20"
                  onClick={() => onNavigateToDraft(draft.id)}
                >
                  <FileEdit className="h-3.5 w-3.5 text-[#46C1BE]" />
                  <span>{isRTL ? 'استكمال الإعداد' : 'Resume Setup'}</span>
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onDeleteDraft(draft)}
                  disabled={deletingDraftId === draft.id}
                  className="h-9 w-9 p-0 rounded-xl text-rose-600 border-rose-200 hover:bg-rose-50 dark:border-rose-900/60 dark:hover:bg-rose-950/40"
                  title={isRTL ? 'حذف المسودة' : 'Delete Draft'}
                >
                  {deletingDraftId === draft.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
