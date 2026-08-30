import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  Search, SlidersHorizontal, LayoutGrid, List, X, Filter, RotateCcw
} from 'lucide-react';
import { SCHOOL_STATUS } from '../constants/schoolConstants';

export default function TenantsFilterBar({
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  showFilters,
  onToggleFilters,
  filters,
  onFilterChange,
  onResetFilters,
  activeStatusFilter,
  onClearActiveStatusFilter,
  cities,
  isRTL,
}) {
  const hasActiveFilters =
    filters.status !== 'all' ||
    filters.city !== 'all' ||
    filters.schoolType !== 'all' ||
    filters.stage !== 'all' ||
    searchQuery.trim() !== '';

  return (
    <div className="space-y-3">
      {/* Active Status Quick Pill Indicator */}
      {activeStatusFilter && (
        <div className="p-3.5 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-2xl flex items-center justify-between shadow-xs animate-in fade-in-30 duration-200">
          <div className="flex items-center gap-2">
            <span className="p-1 rounded-lg bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300">
              <Filter className="h-3.5 w-3.5" />
            </span>
            <span className="text-xs font-bold text-blue-950 dark:text-blue-200">
              {isRTL
                ? `تصفية المدارس حسب الحالة: ${SCHOOL_STATUS[activeStatusFilter]?.label || activeStatusFilter}`
                : `Filtered by status: ${SCHOOL_STATUS[activeStatusFilter]?.label_en || activeStatusFilter}`}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearActiveStatusFilter}
            className="h-7 text-xs font-bold text-blue-800 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 rounded-lg px-2.5"
          >
            <X className={`h-3.5 w-3.5 ${isRTL ? 'ms-1' : 'me-1'}`} />
            <span>{isRTL ? 'إلغاء الفلتر' : 'Clear Filter'}</span>
          </Button>
        </div>
      )}

      {/* Main Control Card */}
      <Card className="rounded-2xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 p-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative w-full md:w-96">
            <Search className={`absolute ${isRTL ? 'right-3.5' : 'left-3.5'} top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400`} />
            <Input
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={isRTL ? 'بحث باسم المدرسة، الكود، المدينة، البريد...' : 'Search by school name, code, city, email...'}
              className={`${isRTL ? 'pr-10 pl-9' : 'pl-10 pr-9'} h-11 rounded-xl bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-medium text-xs focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]`}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => onSearchChange('')}
                className={`absolute ${isRTL ? 'left-3' : 'right-3'} top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors`}
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Actions & View Mode Toggle */}
          <div className="flex items-center gap-2.5 w-full md:w-auto justify-end flex-wrap">
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onResetFilters}
                className="h-11 px-3 text-xs font-bold text-slate-600 dark:text-slate-300 hover:text-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl"
              >
                <RotateCcw className={`h-3.5 w-3.5 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
                <span>{isRTL ? 'إعادة ضبط' : 'Reset'}</span>
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={onToggleFilters}
              className={`rounded-xl h-11 px-4 text-xs font-bold border-slate-200 dark:border-slate-700 gap-1.5 transition-all ${
                showFilters || filters.status !== 'all' || filters.city !== 'all' || filters.schoolType !== 'all' || filters.stage !== 'all'
                  ? 'bg-[#1C3D74] text-white border-[#1C3D74] hover:bg-[#152e57]'
                  : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50'
              }`}
            >
              <SlidersHorizontal className="h-4 w-4" />
              <span>{isRTL ? 'فلاتر متقدمة' : 'Filters'}</span>
            </Button>

            {/* View Mode Toggle: Grid vs Table */}
            <div className="flex items-center bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl border border-slate-200/80 dark:border-slate-700/80">
              <button
                type="button"
                onClick={() => onViewModeChange('grid')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  viewMode === 'grid'
                    ? 'bg-white dark:bg-slate-900 text-[#1C3D74] dark:text-[#46C1BE] shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span>{isRTL ? 'بطاقات' : 'Cards'}</span>
              </button>
              <button
                type="button"
                onClick={() => onViewModeChange('table')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  viewMode === 'table'
                    ? 'bg-white dark:bg-slate-900 text-[#1C3D74] dark:text-[#46C1BE] shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <List className="h-3.5 w-3.5" />
                <span>{isRTL ? 'جدول' : 'Table'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Expandable Advanced Filters Grid */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 animate-in fade-in-30 duration-200">
            {/* Status Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">
                {isRTL ? 'الحالة' : 'Status'}
              </label>
              <Select
                value={filters.status}
                onValueChange={(v) => onFilterChange('status', v)}
              >
                <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  <SelectItem value="all">{isRTL ? 'جميع الحالات' : 'All Statuses'}</SelectItem>
                  <SelectItem value="active">{isRTL ? 'نشطة' : 'Active'}</SelectItem>
                  <SelectItem value="suspended">{isRTL ? 'موقوفة' : 'Suspended'}</SelectItem>
                  <SelectItem value="pending">{isRTL ? 'معلقة' : 'Pending'}</SelectItem>
                  <SelectItem value="setup">{isRTL ? 'مسودة' : 'Draft'}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* City Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">
                {isRTL ? 'المدينة' : 'City'}
              </label>
              <Select
                value={filters.city}
                onValueChange={(v) => onFilterChange('city', v)}
              >
                <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  <SelectItem value="all">{isRTL ? 'جميع المدن' : 'All Cities'}</SelectItem>
                  {cities.map((city) => (
                    <SelectItem key={city} value={city}>{city}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* School Type Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">
                {isRTL ? 'نوع المدرسة' : 'School Type'}
              </label>
              <Select
                value={filters.schoolType}
                onValueChange={(v) => onFilterChange('schoolType', v)}
              >
                <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  <SelectItem value="all">{isRTL ? 'جميع الأنواع' : 'All Types'}</SelectItem>
                  <SelectItem value="public">{isRTL ? 'حكومية' : 'Public'}</SelectItem>
                  <SelectItem value="private">{isRTL ? 'أهلية' : 'Private'}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Stage Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300">
                {isRTL ? 'المرحلة التعليمية' : 'Stage'}
              </label>
              <Select
                value={filters.stage}
                onValueChange={(v) => onFilterChange('stage', v)}
              >
                <SelectTrigger className="h-10 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  <SelectItem value="all">{isRTL ? 'جميع المراحل' : 'All Stages'}</SelectItem>
                  <SelectItem value="primary">{isRTL ? 'ابتدائية' : 'Primary'}</SelectItem>
                  <SelectItem value="intermediate">{isRTL ? 'متوسطة' : 'Intermediate'}</SelectItem>
                  <SelectItem value="secondary_general">{isRTL ? 'ثانوية عامة' : 'Secondary General'}</SelectItem>
                  <SelectItem value="secondary_pathways">{isRTL ? 'ثانوية مسارات' : 'Secondary Pathways'}</SelectItem>
                  <SelectItem value="school_complex">{isRTL ? 'مجمع مدارس' : 'Complex'}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
