import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { RefreshCw, Plus, SearchX, ChevronRight, ChevronLeft } from 'lucide-react';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
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
  currentPage = 1,
  totalPages = 1,
  totalCount,
  itemsPerPage = 10,
  onPageChange,
  onItemsPerPageChange,
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
            className="rounded-xl h-11 px-6 font-bold text-sm border-slate-300 dark:border-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white gap-2 shadow-2xs"
          >
            <RefreshCw className="h-4 w-4 text-slate-500" />
            <span>{isRTL ? 'إعادة ضبط الفلاتر' : 'Reset Filters'}</span>
          </Button>

          {onOpenCreateWizard && (
            <Button
              onClick={onOpenCreateWizard}
              className="rounded-xl h-11 px-6 font-bold text-sm bg-[#1C3D74] hover:bg-[#152e57] text-white shadow-xs gap-2"
            >
              <Plus className="h-4 w-4 text-[#46C1BE]" />
              <span>{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</span>
            </Button>
          )}
        </div>
      </Card>
    );
  }

  const effectiveTotal = totalCount !== undefined ? totalCount : schools.length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 sm:gap-6 animate-in fade-in-30 duration-200">
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

      {/* Pagination Bar for Grid View */}
      {onPageChange && (
        <Card className="p-3.5 rounded-2xl border border-slate-200/90 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3 bg-white dark:bg-slate-900 shadow-sm font-tajawal">
          <div className="flex items-center gap-3 text-xs font-medium text-slate-500 dark:text-slate-400">
            <span>
              {isRTL
                ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, effectiveTotal)} من أصل ${effectiveTotal} مدرسة`
                : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, effectiveTotal)} of ${effectiveTotal} schools`}
            </span>

            {onItemsPerPageChange && (
              <div className="flex items-center gap-1.5 ms-2">
                <span className="text-[11px] text-slate-400">{isRTL ? 'لكل صفحة:' : 'Per page:'}</span>
                <Select value={String(itemsPerPage)} onValueChange={(v) => onItemsPerPageChange(Number(v))}>
                  <SelectTrigger className="h-8 w-18 rounded-lg bg-slate-50 dark:bg-slate-950 text-xs font-bold border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="font-cairo">
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="25">25</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
                disabled={currentPage === 1}
                className="rounded-lg h-8 px-2.5 font-bold text-xs border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-200 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
              >
                {isRTL ? <ChevronRight className="h-3.5 w-3.5 ms-1" /> : <ChevronLeft className="h-3.5 w-3.5 me-1" />}
                <span>{isRTL ? 'السابق' : 'Previous'}</span>
              </Button>
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 font-mono">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
                disabled={currentPage === totalPages}
                className="rounded-lg h-8 px-2.5 font-bold text-xs border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-200 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
              >
                <span>{isRTL ? 'التالي' : 'Next'}</span>
                {isRTL ? <ChevronLeft className="h-3.5 w-3.5 me-1" /> : <ChevronRight className="h-3.5 w-3.5 ms-1" />}
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
