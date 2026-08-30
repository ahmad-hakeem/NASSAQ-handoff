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
    <div className="p-4 sm:p-5 rounded-3xl bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border border-amber-500/25 shadow-xs">
      <div className="flex items-center justify-between gap-2 mb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-xl bg-amber-500/20 text-amber-700 dark:text-amber-300">
            <Clock className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-bold text-xs sm:text-sm font-cairo text-amber-950 dark:text-amber-200">
              {isRTL
                ? `مسودات المدارس قيد التهيئة (${draftSchools.length})`
                : `School Setup Drafts (${draftSchools.length})`}
            </h3>
            <p className="text-[11px] text-amber-800/80 dark:text-amber-300/70 font-medium">
              {isRTL
                ? 'مدارس تم حفظ بياناتها كمسودة ويمكن استكمال خطوات إعدادها في أي وقت'
                : 'Schools saved as drafts that can be completed at any time'}
            </p>
          </div>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={onToggleShowDrafts}
          className="h-8 text-xs font-bold text-amber-900 dark:text-amber-300 hover:bg-amber-500/20 rounded-xl px-3"
        >
          {showDrafts ? (
            <>
              <ChevronUp className={`h-3.5 w-3.5 ${isRTL ? 'ms-1' : 'me-1'}`} />
              <span>{isRTL ? 'إخفاء' : 'Hide'}</span>
            </>
          ) : (
            <>
              <ChevronDown className={`h-3.5 w-3.5 ${isRTL ? 'ms-1' : 'me-1'}`} />
              <span>{isRTL ? 'عرض' : 'Show'}</span>
            </>
          )}
        </Button>
      </div>

      {showDrafts && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 animate-in fade-in-30 duration-200">
          {draftSchools.map((draft) => (
            <div
              key={draft.id}
              className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900/60 shadow-xs flex flex-col justify-between hover:shadow-md transition-shadow"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <strong className="text-xs sm:text-sm font-black text-slate-900 dark:text-white line-clamp-1 font-cairo">
                    {draft.name}
                  </strong>
                  <Badge className="text-[10px] bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-800 shrink-0">
                    {isRTL ? 'مسودة' : 'Draft'}
                  </Badge>
                </div>

                <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mb-3.5">
                  <MapPin className="h-3.5 w-3.5 text-slate-400" />
                  <span>{draft.city || (isRTL ? 'المدينة غير محددة' : 'City unset')}</span>
                  {draft.region && <span>• {draft.region}</span>}
                </p>
              </div>

              <div className="flex items-center gap-2 pt-2.5 border-t border-slate-100 dark:border-slate-800">
                <Button
                  size="sm"
                  className="flex-1 h-8.5 rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white text-xs font-bold gap-1.5 shadow-xs"
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
                  className="h-8.5 w-8.5 p-0 rounded-xl text-rose-600 border-rose-200 hover:bg-rose-50 dark:border-rose-900/60 dark:hover:bg-rose-950/40"
                  title={isRTL ? 'حذف المسودة' : 'Delete Draft'}
                >
                  {deletingDraftId === draft.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
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
