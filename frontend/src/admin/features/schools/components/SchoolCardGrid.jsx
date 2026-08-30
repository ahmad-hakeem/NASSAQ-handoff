import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { RefreshCw, Plus, SearchX } from 'lucide-react';
import SchoolCardItem from './SchoolCardItem';

export default function SchoolCardGrid({
  schools,
  onNavigateDetail,
  onEnterDashboard,
  canEnterDashboard,
  onOpenSuspendDialog,
  onOpenActivateDialog,
  onResetFilters,
  onOpenCreateWizard,
  isRTL,
}) {
  if (!schools || schools.length === 0) {
    return (
      <Card className="rounded-2xl border border-slate-200/90 dark:border-slate-800 p-10 text-center bg-white dark:bg-slate-900 shadow-sm font-tajawal">
        <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4 text-slate-400 border border-slate-200 dark:border-slate-700">
          <SearchX className="h-8 w-8 text-[#46C1BE]" />
        </div>
        <h3 className="font-bold text-lg mb-1 font-cairo text-slate-900 dark:text-white">
          {isRTL ? 'لا توجد مدارس مطابقة لمعايير البحث' : 'No Schools Found'}
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-5 max-w-sm mx-auto leading-relaxed">
          {isRTL
            ? 'جرب تعديل كلمات البحث أو مسح الفلاتر المحددة لعرض المدارس'
            : 'Try adjusting your search criteria or resetting applied filters'}
        </p>
        <div className="flex items-center justify-center gap-2.5 flex-wrap">
          <Button
            onClick={onResetFilters}
            variant="outline"
            className="rounded-xl h-9.5 px-4 font-bold text-xs border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 gap-1.5 shadow-2xs"
          >
            <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
            <span>{isRTL ? 'إعادة ضبط الفلاتر' : 'Reset Filters'}</span>
          </Button>

          {onOpenCreateWizard && (
            <Button
              onClick={onOpenCreateWizard}
              className="rounded-xl h-9.5 px-4 font-bold text-xs bg-[#1C3D74] hover:bg-[#152e57] text-white shadow-xs gap-1.5"
            >
              <Plus className="h-3.5 w-3.5 text-[#46C1BE]" />
              <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
            </Button>
          )}
        </div>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4.5 animate-in fade-in-30 duration-200">
      {schools.map((school) => (
        <SchoolCardItem
          key={school.id}
          school={school}
          onNavigateDetail={onNavigateDetail}
          onEnterDashboard={onEnterDashboard}
          canEnterDashboard={canEnterDashboard}
          onOpenSuspendDialog={onOpenSuspendDialog}
          onOpenActivateDialog={onOpenActivateDialog}
          isRTL={isRTL}
        />
      ))}
    </div>
  );
}
