import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import {
  Building2, MapPin, Eye, ExternalLink, MoreHorizontal, Pause, Play,
  ChevronRight, ChevronLeft, RefreshCw
} from 'lucide-react';
import { SCHOOL_STATUS, getLogoGradient } from '../constants/schoolConstants';

export default function SchoolTableView({
  schools,
  paginatedSchools,
  currentPage,
  totalPages,
  itemsPerPage,
  onPageChange,
  onNavigateDetail,
  onEnterDashboard,
  canEnterDashboard,
  onOpenSuspendDialog,
  onOpenActivateDialog,
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
    <Card className="rounded-3xl border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm bg-white dark:bg-slate-900">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
              <TableHead className={`font-bold text-xs text-slate-700 dark:text-slate-300 py-3.5 ${isRTL ? 'text-right' : 'text-left'}`}>
                {isRTL ? 'المدرسة' : 'School'}
              </TableHead>
              <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'كود المستأجر' : 'Tenant Code'}
              </TableHead>
              <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'المدينة / المنطقة' : 'City / Region'}
              </TableHead>
              <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الحالة' : 'Status'}
              </TableHead>
              <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الطلاب' : 'Students'}
              </TableHead>
              <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'المعلمين' : 'Teachers'}
              </TableHead>
              <TableHead className="font-bold text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الإجراءات' : 'Actions'}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedSchools.map((school) => {
              const statusCfg = SCHOOL_STATUS[school.status] || SCHOOL_STATUS.active;
              const gradient = getLogoGradient(school.id);

              return (
                <TableRow
                  key={school.id}
                  className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
                >
                  {/* School Name & Avatar */}
                  <TableCell className="py-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white font-bold text-sm shadow-xs shrink-0`}>
                        {school.name?.charAt(0) || 'م'}
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-slate-900 dark:text-white text-xs truncate max-w-[200px]">
                          {school.name}
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 font-normal truncate max-w-[180px]">
                          {school.email || school.name_en || '—'}
                        </p>
                      </div>
                    </div>
                  </TableCell>

                  {/* Tenant Code */}
                  <TableCell className="text-center font-mono text-xs font-bold text-[#1C3D74] dark:text-[#46C1BE]">
                    <span className="px-2 py-0.5 rounded-lg bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800">
                      {school.code || '—'}
                    </span>
                  </TableCell>

                  {/* Location */}
                  <TableCell className="text-center text-xs font-medium text-slate-700 dark:text-slate-300">
                    <div className="flex items-center justify-center gap-1">
                      <MapPin className="h-3.5 w-3.5 text-slate-400" />
                      <span>{school.city || '—'}</span>
                      {school.region && <span className="text-slate-400">/ {school.region}</span>}
                    </div>
                  </TableCell>

                  {/* Status Badge */}
                  <TableCell className="text-center">
                    <Badge className={`text-[11px] font-bold ${statusCfg.badge}`}>
                      {isRTL ? statusCfg.label : statusCfg.label_en}
                    </Badge>
                  </TableCell>

                  {/* Students */}
                  <TableCell className="text-center text-xs font-bold text-sky-600 dark:text-sky-400 font-mono">
                    {(school.student_count || 0).toLocaleString()}
                  </TableCell>

                  {/* Teachers */}
                  <TableCell className="text-center text-xs font-bold text-purple-600 dark:text-purple-400 font-mono">
                    {(school.teacher_count || 0).toLocaleString()}
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-center py-2">
                    <div className="flex items-center justify-center gap-2">
                      <Button
                        size="sm"
                        className="h-8 px-3 rounded-xl bg-[#46C1BE] hover:bg-[#38a19e] text-slate-950 font-black text-xs disabled:opacity-40 gap-1 shadow-2xs"
                        onClick={() => onEnterDashboard(school)}
                        disabled={!canEnterDashboard(school)}
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>{isRTL ? 'الدخول' : 'Enter'}</span>
                      </Button>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm" className="h-8 w-8 p-0 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-52 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl p-1.5 font-cairo">
                          <DropdownMenuItem
                            onClick={() => onNavigateDetail(school.id)}
                            className="rounded-xl font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer"
                          >
                            <ExternalLink className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-slate-500`} />
                            <span>{isRTL ? 'الملف التفصيلي للمدرسة' : 'Full School Profile'}</span>
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          {school.status === 'active' ? (
                            <DropdownMenuItem
                              onClick={() => onOpenSuspendDialog(school)}
                              className="rounded-xl font-bold text-xs py-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                            >
                              <Pause className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'}`} />
                              <span>{isRTL ? 'إيقاف المدرسة' : 'Suspend School'}</span>
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onClick={() => onOpenActivateDialog(school)}
                              className="rounded-xl font-bold text-xs py-2 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 cursor-pointer"
                            >
                              <Play className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'}`} />
                              <span>{isRTL ? 'تفعيل المدرسة' : 'Activate School'}</span>
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="p-4 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3 bg-slate-50/40 dark:bg-slate-900/40">
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400">
            {isRTL
              ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, schools.length)} من أصل ${schools.length} مدرسة`
              : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, schools.length)} of ${schools.length} schools`}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
              disabled={currentPage === 1}
              className="rounded-xl h-8 px-3 font-bold text-xs border-slate-300 dark:border-slate-700"
            >
              {isRTL ? <ChevronRight className="h-4 w-4 ms-1" /> : <ChevronLeft className="h-4 w-4 me-1" />}
              <span>{isRTL ? 'السابق' : 'Previous'}</span>
            </Button>
            <span className="text-xs font-black text-slate-800 dark:text-slate-200 px-2 font-mono">
              {currentPage} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
              disabled={currentPage === totalPages}
              className="rounded-xl h-8 px-3 font-bold text-xs border-slate-300 dark:border-slate-700"
            >
              <span>{isRTL ? 'التالي' : 'Next'}</span>
              {isRTL ? <ChevronLeft className="h-4 w-4 me-1" /> : <ChevronRight className="h-4 w-4 ms-1" />}
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
