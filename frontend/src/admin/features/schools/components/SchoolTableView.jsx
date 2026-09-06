import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/shared/components/ui/table';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from '@/shared/components/ui/dropdown-menu';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  MapPin, Eye, ExternalLink, MoreHorizontal, Pause, Play,
  ChevronRight, ChevronLeft, RefreshCw, Copy, Users, GraduationCap,
  Layers, SearchX, Plus, Mail
} from 'lucide-react';
import { toast } from 'sonner';
import { SCHOOL_STATUS, EDUCATIONAL_STAGES, getSchoolInitials } from '../constants/schoolConstants';

export default function SchoolTableView({
  schools,
  paginatedSchools,
  currentPage,
  totalPages,
  totalCount,
  itemsPerPage,
  onPageChange,
  onItemsPerPageChange,
  onNavigateDetail,
  onEnterDashboard,
  canEnterDashboard,
  onOpenSuspendDialog,
  onOpenActivateDialog,
  onResetFilters,
  onOpenCreateWizard,
  isRTL,
}) {
  const copyCode = (code) => {
    if (code) {
      navigator.clipboard.writeText(code);
      toast.success(isRTL ? `تم نسخ كود المدرسة: ${code}` : `Copied code: ${code}`);
    }
  };

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
            : 'Try adjusting your search criteria or clearing applied filters'}
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

  return (
    <Card className="rounded-2xl border border-slate-200/90 dark:border-slate-800 overflow-hidden shadow-sm bg-white dark:bg-slate-900 font-tajawal">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50/70 dark:bg-slate-800/60 border-b border-slate-200/90 dark:border-slate-800">
              <TableHead className={`font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 py-3.5 ${isRTL ? 'text-right' : 'text-left'}`}>
                {isRTL ? 'المدرسة / المستأجر' : 'School / Tenant'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'كود المستأجر' : 'Tenant Code'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'المدينة والمنطقة' : 'Location'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'النوع والمرحلة' : 'Type & Stage'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الحالة' : 'Status'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الطلاب' : 'Students'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'المعلمين' : 'Teachers'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الفصول' : 'Classes'}
              </TableHead>
              <TableHead className="font-bold font-cairo text-xs text-slate-700 dark:text-slate-300 text-center">
                {isRTL ? 'الإجراءات' : 'Actions'}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(paginatedSchools || schools || []).map((school) => {
              const statusCfg = SCHOOL_STATUS[school.status] || SCHOOL_STATUS.active;
              const stageLabel = EDUCATIONAL_STAGES.find(s => s.value === school.stage)?.label || school.stage;

              return (
                <TableRow
                  key={school.id}
                  className="border-b border-slate-100 dark:border-slate-800/80 hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                >
                  {/* School Avatar & Info */}
                  <TableCell className="py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200/90 dark:border-slate-700 flex items-center justify-center text-[#1C3D74] dark:text-[#46C1BE] font-black font-cairo text-xs shadow-2xs shrink-0 tracking-wider">
                        {getSchoolInitials(school.name, school.name_en)}
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-slate-900 dark:text-white text-xs sm:text-sm truncate max-w-[220px]" title={school.name}>
                          {school.name}
                        </p>
                        <div className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400 font-normal truncate max-w-[220px]">
                          {school.email ? (
                            <span className="flex items-center gap-1 truncate">
                              <Mail className="h-3 w-3 text-slate-400 shrink-0" />
                              <span className="truncate">{school.email}</span>
                            </span>
                          ) : school.name_en ? (
                            <span className="truncate">{school.name_en}</span>
                          ) : (
                            <span>—</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </TableCell>

                  {/* Tenant Code */}
                  <TableCell className="text-center">
                    {school.code ? (
                      <button
                        type="button"
                        onClick={() => copyCode(school.code)}
                        className="px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-mono text-xs font-semibold inline-flex items-center gap-1 transition-colors"
                        title={isRTL ? 'نسخ كود المدرسة' : 'Copy code'}
                      >
                        <span>#{school.code}</span>
                        <Copy className="h-2.5 w-2.5 opacity-50" />
                      </button>
                    ) : (
                      <span className="text-slate-400 text-xs">—</span>
                    )}
                  </TableCell>

                  {/* Location */}
                  <TableCell className="text-center text-xs">
                    <div className="inline-flex items-center gap-1 text-slate-600 dark:text-slate-400 font-medium">
                      <MapPin className="h-3 w-3 text-slate-400" />
                      <span>{school.city || (isRTL ? 'غير محدد' : '—')}</span>
                      {school.region && <span className="text-slate-400 font-normal">/ {school.region}</span>}
                    </div>
                  </TableCell>

                  {/* Type & Stage */}
                  <TableCell className="text-center text-xs">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="inline-flex items-center text-[11px] font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-md">
                        {school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}
                      </span>
                      {stageLabel && (
                        <span className="text-[10px] text-slate-400 truncate max-w-[120px]">
                          {stageLabel}
                        </span>
                      )}
                    </div>
                  </TableCell>

                  {/* Status Badge */}
                  <TableCell className="text-center">
                    <span className={`inline-flex items-center gap-1.5 text-[11px] font-bold px-2.5 py-0.5 rounded-full ${statusCfg.badge}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`} />
                      <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
                    </span>
                  </TableCell>

                  {/* Students */}
                  <TableCell className="text-center text-xs font-bold text-slate-800 dark:text-slate-200 font-mono">
                    <span className="inline-flex items-center gap-1">
                      <GraduationCap className="h-3.5 w-3.5 text-sky-500" />
                      <span>{(school.student_count || 0).toLocaleString()}</span>
                    </span>
                  </TableCell>

                  {/* Teachers */}
                  <TableCell className="text-center text-xs font-bold text-slate-800 dark:text-slate-200 font-mono">
                    <span className="inline-flex items-center gap-1">
                      <Users className="h-3.5 w-3.5 text-purple-500" />
                      <span>{(school.teacher_count || 0).toLocaleString()}</span>
                    </span>
                  </TableCell>

                  {/* Classes */}
                  <TableCell className="text-center text-xs font-bold text-slate-800 dark:text-slate-200 font-mono">
                    <span className="inline-flex items-center gap-1">
                      <Layers className="h-3.5 w-3.5 text-teal-500" />
                      <span>{(school.class_count || 0).toLocaleString()}</span>
                    </span>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-center py-2.5">
                    <div className="flex items-center justify-center gap-2">
                      <Button
                        size="sm"
                        className="h-9 px-3.5 rounded-xl bg-[#1C3D74] hover:bg-[#152e57] text-white font-bold font-cairo text-xs disabled:opacity-40 gap-1.5 shadow-2xs transition-colors"
                        onClick={() => onEnterDashboard(school)}
                        disabled={!canEnterDashboard(school)}
                      >
                        <Eye className="h-3.5 w-3.5 text-[#46C1BE]" />
                        <span>{isRTL ? 'دخول' : 'Enter'}</span>
                      </Button>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-9 w-9 p-0 rounded-xl border-slate-200 dark:border-slate-700 text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 shadow-2xs"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-50 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-xl shadow-lg p-1 font-cairo z-50">
                          <DropdownMenuItem
                            onClick={() => onNavigateDetail(school.id)}
                            className="rounded-lg font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer gap-2"
                          >
                            <ExternalLink className="h-3.5 w-3.5 text-slate-500" />
                            <span>{isRTL ? 'الملف التفصيلي للمدرسة' : 'Full School Profile'}</span>
                          </DropdownMenuItem>
                          {school.code && (
                            <DropdownMenuItem
                              onClick={() => copyCode(school.code)}
                              className="rounded-lg font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer gap-2"
                            >
                              <Copy className="h-3.5 w-3.5 text-slate-500" />
                              <span>{isRTL ? 'نسخ كود المستأجر' : 'Copy Code'}</span>
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          {school.status === 'active' && onOpenSuspendDialog ? (
                            <DropdownMenuItem
                              onClick={() => onOpenSuspendDialog(school)}
                              className="rounded-lg font-bold text-xs py-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer gap-2"
                            >
                              <Pause className="h-3.5 w-3.5" />
                              <span>{isRTL ? 'إيقاف المدرسة' : 'Suspend School'}</span>
                            </DropdownMenuItem>
                          ) : onOpenActivateDialog ? (
                            <DropdownMenuItem
                              onClick={() => onOpenActivateDialog(school)}
                              className="rounded-lg font-bold text-xs py-2 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 cursor-pointer gap-2"
                            >
                              <Play className="h-3.5 w-3.5" />
                              <span>{isRTL ? 'تفعيل المدرسة' : 'Activate School'}</span>
                            </DropdownMenuItem>
                          ) : null}
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
      <div className="p-3.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between flex-wrap gap-3 bg-white dark:bg-slate-900 font-tajawal">
        <div className="flex items-center gap-3 text-xs font-medium text-slate-500 dark:text-slate-400">
          <span>
            {isRTL
              ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, totalCount !== undefined ? totalCount : schools.length)} من أصل ${totalCount !== undefined ? totalCount : schools.length} مدرسة`
              : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, totalCount !== undefined ? totalCount : schools.length)} of ${totalCount !== undefined ? totalCount : schools.length} schools`}
          </span>

          {/* Items Per Page */}
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
      </div>
    </Card>
  );
}
