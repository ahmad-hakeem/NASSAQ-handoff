import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Building2, RefreshCw, Plus, SearchX } from 'lucide-react';
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
      <Card className="rounded-3xl border border-slate-200/80 dark:border-slate-800 p-12 text-center bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl shadow-md">
        <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-slate-100 to-slate-200/50 dark:from-slate-800 dark:to-slate-800/40 flex items-center justify-center mx-auto mb-5 text-slate-400 border border-slate-200 dark:border-slate-700/60 shadow-inner">
          <SearchX className="h-10 w-10 text-[#46C1BE]" />
        </div>
        <h3 className="font-black text-xl mb-1.5 font-cairo text-slate-900 dark:text-white">
          {isRTL ? 'لا توجد مدارس مطابقة لمعايير البحث' : 'No Schools Matching Criteria'}
        </h3>
        <p className="text-xs sm:text-sm font-medium text-slate-500 dark:text-slate-400 mb-6 max-w-md mx-auto leading-relaxed">
          {isRTL
            ? 'جرب تعديل كلمات البحث أو مسح الفلاتر المحددة للوصول لبيانات المدارس والمستأجرين'
            : 'Try adjusting your search query or reset active filters to view existing schools'}
        </p>
        <div className="flex items-center justify-center gap-3 flex-wrap">
          <Button
            onClick={onResetFilters}
            variant="outline"
            className="rounded-2xl h-11 px-5 font-bold text-xs border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 shadow-xs"
          >
            <RefreshCw className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-[#46C1BE]`} />
            <span>{isRTL ? 'إعادة ضبط الفلاتر' : 'Reset Filters'}</span>
          </Button>

          {onOpenCreateWizard && (
            <Button
              onClick={onOpenCreateWizard}
              className="rounded-2xl h-11 px-5 font-black text-xs bg-[#46C1BE] hover:bg-[#39a8a5] text-slate-950 shadow-md shadow-[#46C1BE]/20 gap-2"
            >
              <Plus className="h-4 w-4 stroke-[3]" />
              <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
            </Button>
          )}
        </div>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 animate-in fade-in-30 duration-300">
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
