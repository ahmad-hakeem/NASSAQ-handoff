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
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  Building2, MapPin, Eye, ExternalLink, MoreHorizontal, Pause, Play,
  ChevronRight, ChevronLeft, RefreshCw, Copy, Users, GraduationCap,
  Layers, SearchX, Plus, Mail
} from 'lucide-react';
import { toast } from 'sonner';
import { SCHOOL_STATUS, getLogoGradient, EDUCATIONAL_STAGES } from '../constants/schoolConstants';

export default function SchoolTableView({
  schools,
  paginatedSchools,
  currentPage,
  totalPages,
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
      toast.success(isRTL ? `تم نسخ كود المدرسة: ${code}` : `Copied tenant code: ${code}`);
    }
  };

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
            ? 'جرب تعديل كلمات البحث أو مسح الفلاتر المحددة لعرض المدارس المسجلة'
            : 'Try adjusting your search criteria or clearing applied filters'}
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
    <Card className="rounded-3xl border border-slate-200/80 dark:border-slate-800 overflow-hidden shadow-lg bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-slate-50/90 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800">
              <TableHead className={`font-black text-xs text-slate-800 dark:text-slate-200 py-4 ${isRTL ? 'text-right' : 'text-left'}`}>
                {isRTL ? 'المدرسة / المستأجر' : 'School / Tenant'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'كود المستأجر' : 'Tenant Code'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'المدينة والمنطقة' : 'Location'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'النوع والمرحلة' : 'Type & Stage'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'الحالة' : 'Status'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'الطلاب' : 'Students'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'المعلمين' : 'Teachers'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'الفصول' : 'Classes'}
              </TableHead>
              <TableHead className="font-black text-xs text-slate-800 dark:text-slate-200 text-center">
                {isRTL ? 'الإجراءات' : 'Actions'}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedSchools.map((school) => {
              const statusCfg = SCHOOL_STATUS[school.status] || SCHOOL_STATUS.active;
              const gradient = getLogoGradient(school.id || school.code);
              const stageLabel = EDUCATIONAL_STAGES.find(s => s.value === school.stage)?.label || school.stage;

              return (
                <TableRow
                  key={school.id}
                  className="border-b border-slate-100 dark:border-slate-800/80 hover:bg-slate-50/80 dark:hover:bg-slate-800/50 transition-colors group"
                >
                  {/* School Avatar & Info */}
                  <TableCell className="py-3.5">
                    <div className="flex items-center gap-3.5">
                      <div className={`w-11 h-11 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center text-white font-black text-base shadow-sm shrink-0 border border-white/20`}>
                        {school.name?.trim().charAt(0) || 'م'}
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
                  <TableCell className="text-center font-mono text-xs font-bold text-[#1C3D74] dark:text-[#46C1BE]">
                    {school.code ? (
                      <button
                        type="button"
                        onClick={() => copyCode(school.code)}
                        className="px-2.5 py-1 rounded-xl bg-blue-50/80 hover:bg-blue-100/80 dark:bg-blue-950/60 dark:hover:bg-blue-900/60 border border-blue-200 dark:border-blue-800 inline-flex items-center gap-1 transition-all"
                        title={isRTL ? 'نسخ كود المدرسة' : 'Copy code'}
                      >
                        <span>#{school.code}</span>
                        <Copy className="h-3 w-3 text-blue-500 opacity-60" />
                      </button>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </TableCell>

                  {/* Location */}
                  <TableCell className="text-center text-xs font-semibold text-slate-700 dark:text-slate-300">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-slate-100/70 dark:bg-slate-800/70">
                      <MapPin className="h-3.5 w-3.5 text-[#46C1BE]" />
                      <span>{school.city || (isRTL ? 'غير محدد' : '—')}</span>
                      {school.region && <span className="text-slate-400 font-normal">/ {school.region}</span>}
                    </div>
                  </TableCell>

                  {/* Type & Stage */}
                  <TableCell className="text-center text-xs">
                    <div className="flex flex-col items-center gap-1">
                      <Badge variant="outline" className="text-[10px] font-bold border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
                        {school.school_type === 'private' ? (isRTL ? 'أهلية' : 'Private') : (isRTL ? 'حكومية' : 'Public')}
                      </Badge>
                      {stageLabel && (
                        <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 truncate max-w-[120px]">
                          {stageLabel}
                        </span>
                      )}
                    </div>
                  </TableCell>

                  {/* Status Badge */}
                  <TableCell className="text-center">
                    <span className={`inline-flex items-center gap-1.5 text-[11px] font-extrabold px-2.5 py-1 rounded-full ${statusCfg.badge}`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot}`} />
                      <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
                    </span>
                  </TableCell>

                  {/* Students */}
                  <TableCell className="text-center text-xs font-black text-sky-600 dark:text-sky-400 font-mono">
                    <span className="px-2.5 py-1 rounded-xl bg-sky-50 dark:bg-sky-950/50 border border-sky-200/60 dark:border-sky-800/60 inline-flex items-center gap-1">
                      <GraduationCap className="h-3 w-3" />
                      <span>{(school.student_count || 0).toLocaleString()}</span>
                    </span>
                  </TableCell>

                  {/* Teachers */}
                  <TableCell className="text-center text-xs font-black text-purple-600 dark:text-purple-400 font-mono">
                    <span className="px-2.5 py-1 rounded-xl bg-purple-50 dark:bg-purple-950/50 border border-purple-200/60 dark:border-purple-800/60 inline-flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      <span>{(school.teacher_count || 0).toLocaleString()}</span>
                    </span>
                  </TableCell>

                  {/* Classes */}
                  <TableCell className="text-center text-xs font-black text-emerald-600 dark:text-emerald-400 font-mono">
                    <span className="px-2.5 py-1 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200/60 dark:border-emerald-800/60 inline-flex items-center gap-1">
                      <Layers className="h-3 w-3" />
                      <span>{(school.class_count || 0).toLocaleString()}</span>
                    </span>
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="text-center py-2.5">
                    <div className="flex items-center justify-center gap-1.5">
                      <Button
                        size="sm"
                        className="h-9 px-3.5 rounded-xl bg-gradient-to-r from-[#46C1BE] to-[#2fa8a5] hover:from-[#3bb0ad] hover:to-[#279491] text-slate-950 font-black text-xs disabled:opacity-40 gap-1.5 shadow-sm shadow-[#46C1BE]/20"
                        onClick={() => onEnterDashboard(school)}
                        disabled={!canEnterDashboard(school)}
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>{isRTL ? 'دخول' : 'Enter'}</span>
                      </Button>

                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-9 w-9 p-0 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-52 bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 rounded-2xl shadow-xl p-1.5 font-cairo z-50">
                          <DropdownMenuItem
                            onClick={() => onNavigateDetail(school.id)}
                            className="rounded-xl font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer"
                          >
                            <ExternalLink className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-[#46C1BE]`} />
                            <span>{isRTL ? 'الملف التفصيلي للمدرسة' : 'Full School Profile'}</span>
                          </DropdownMenuItem>
                          {school.code && (
                            <DropdownMenuItem
                              onClick={() => copyCode(school.code)}
                              className="rounded-xl font-bold text-xs py-2 text-slate-700 dark:text-slate-200 cursor-pointer"
                            >
                              <Copy className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'} text-slate-400`} />
                              <span>{isRTL ? 'نسخ كود المستأجر' : 'Copy Code'}</span>
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          {school.status === 'active' && onOpenSuspendDialog ? (
                            <DropdownMenuItem
                              onClick={() => onOpenSuspendDialog(school)}
                              className="rounded-xl font-bold text-xs py-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                            >
                              <Pause className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'}`} />
                              <span>{isRTL ? 'إيقاف المدرسة' : 'Suspend School'}</span>
                            </DropdownMenuItem>
                          ) : onOpenActivateDialog ? (
                            <DropdownMenuItem
                              onClick={() => onOpenActivateDialog(school)}
                              className="rounded-xl font-bold text-xs py-2 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 cursor-pointer"
                            >
                              <Play className={`h-4 w-4 ${isRTL ? 'ms-2' : 'me-2'}`} />
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
      <div className="p-4 border-t border-slate-200/80 dark:border-slate-800 flex items-center justify-between flex-wrap gap-4 bg-slate-50/60 dark:bg-slate-900/60 font-tajawal">
        <div className="flex items-center gap-3 text-xs font-semibold text-slate-600 dark:text-slate-400">
          <span>
            {isRTL
              ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, schools.length)} من أصل ${schools.length} مدرسة`
              : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, schools.length)} of ${schools.length} schools`}
          </span>

          {/* Items Per Page */}
          {onItemsPerPageChange && (
            <div className="flex items-center gap-1.5 ms-2">
              <span className="text-[11px] text-slate-400">{isRTL ? 'لكل صفحة:' : 'Per page:'}</span>
              <Select value={String(itemsPerPage)} onValueChange={(v) => onItemsPerPageChange(Number(v))}>
                <SelectTrigger className="h-8 w-18 rounded-xl bg-white dark:bg-slate-950 text-xs font-bold border-slate-200 dark:border-slate-800">
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
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
              disabled={currentPage === 1}
              className="rounded-xl h-9 px-3 font-bold text-xs border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-200 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
            >
              {isRTL ? <ChevronRight className="h-4 w-4 ms-1" /> : <ChevronLeft className="h-4 w-4 me-1" />}
              <span>{isRTL ? 'السابق' : 'Previous'}</span>
            </Button>
            <span className="text-xs font-black text-slate-800 dark:text-slate-200 px-2.5 py-1 rounded-xl bg-slate-200/60 dark:bg-slate-800 font-mono">
              {currentPage} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
              disabled={currentPage === totalPages}
              className="rounded-xl h-9 px-3 font-bold text-xs border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-200 hover:bg-slate-100 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-white"
            >
              <span>{isRTL ? 'التالي' : 'Next'}</span>
              {isRTL ? <ChevronLeft className="h-4 w-4 me-1" /> : <ChevronRight className="h-4 w-4 ms-1" />}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
