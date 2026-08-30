import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Clock, MapPin, FileEdit, Trash2, Loader2, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

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
    <div className="relative overflow-hidden p-5 sm:p-6 rounded-3xl bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-amber-500/5 border border-amber-500/30 shadow-lg backdrop-blur-xl animate-in fade-in-30 duration-300">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-700 dark:text-amber-300 flex items-center justify-center border border-amber-500/30 shadow-inner">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-extrabold text-sm sm:text-base font-cairo text-amber-950 dark:text-amber-100">
                {isRTL
                  ? `مسودات المدارس قيد التهيئة`
                  : `School Setup Drafts`}
              </h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-black bg-amber-500/25 text-amber-900 dark:text-amber-200 border border-amber-500/30">
                {draftSchools.length}
              </span>
            </div>
            <p className="text-xs text-amber-900/80 dark:text-amber-300/80 font-medium mt-0.5">
              {isRTL
                ? 'مدارس تم حفظ بياناتها كمسودة أولية ويمكن متابعة خطوات إعدادها في أي وقت'
                : 'Schools saved as drafts that can be finalized at any time'}
            </p>
          </div>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleShowDrafts}
          className="h-9 text-xs font-bold text-amber-950 dark:text-amber-200 hover:bg-amber-500/20 rounded-2xl px-3.5 border border-amber-500/20"
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

      {showDrafts && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 animate-in fade-in-30 slide-in-from-top-2 duration-300">
          {draftSchools.map((draft) => (
            <div
              key={draft.id}
              className="group p-4.5 rounded-2xl bg-white/90 dark:bg-slate-900/90 border border-amber-300/70 dark:border-amber-900/60 shadow-sm hover:shadow-xl hover:border-amber-400 dark:hover:border-amber-700 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h4 className="text-sm font-black text-slate-900 dark:text-white line-clamp-1 font-cairo" title={draft.name}>
                    {draft.name}
                  </h4>
                  <Badge className="text-[10px] bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800 shrink-0 font-bold">
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
