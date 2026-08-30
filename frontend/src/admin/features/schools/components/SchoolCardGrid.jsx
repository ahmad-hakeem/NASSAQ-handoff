import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Building2, RefreshCw } from 'lucide-react';
import SchoolCardItem from './SchoolCardItem';

export default function SchoolCardGrid({
  schools,
  onNavigateDetail,
  onEnterDashboard,
  canEnterDashboard,
  onResetFilters,
  isRTL,
}) {
  if (!schools || schools.length === 0) {
    return (
      <Card className="rounded-3xl border-slate-200 dark:border-slate-800 p-12 text-center bg-white dark:bg-slate-900 shadow-sm">
        <div className="w-16 h-16 rounded-3xl bg-slate-100 dark:bg-slate-800/80 flex items-center justify-center mx-auto mb-4 text-slate-400">
          <Building2 className="h-8 w-8" />
        </div>
        <h3 className="font-black text-lg mb-1 font-cairo text-slate-900 dark:text-white">
          {isRTL ? 'لا توجد مدارس مطابقة للبحث' : 'No Schools Found'}
        </h3>
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-5 max-w-sm mx-auto">
          {isRTL
            ? 'جرب تغيير معايير البحث أو إلغاء الفلاتر المحددة لعرض المدارس المسجلة'
            : 'Try adjusting your search criteria or clearing applied filters'}
        </p>
        <Button onClick={onResetFilters} variant="outline" className="rounded-xl font-bold text-xs">
          <RefreshCw className={`h-4 w-4 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
          <span>{isRTL ? 'إعادة ضبط الفلاتر' : 'Reset Filters'}</span>
        </Button>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
      {schools.map((school) => (
        <SchoolCardItem
          key={school.id}
          school={school}
          onNavigateDetail={onNavigateDetail}
          onEnterDashboard={onEnterDashboard}
          canEnterDashboard={canEnterDashboard}
          isRTL={isRTL}
        />
      ))}
    </div>
  );
}
