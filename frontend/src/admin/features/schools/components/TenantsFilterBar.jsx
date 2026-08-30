import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  Search, SlidersHorizontal, LayoutGrid, List, X, Filter, RotateCcw,
  ArrowUpDown, CheckCircle2, XCircle, Clock, Building2, Layers
} from 'lucide-react';
import { SCHOOL_STATUS, SCHOOL_TYPES, EDUCATIONAL_STAGES } from '../constants/schoolConstants';

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
  onStatusFilterChange,
  cities,
  sortBy,
  onSortChange,
  totalResultsCount,
  isRTL,
}) {
  const hasAdvancedFilters =
    filters.status !== 'all' ||
    filters.city !== 'all' ||
    filters.schoolType !== 'all' ||
    filters.stage !== 'all';

  const hasAnyFilters = hasAdvancedFilters || searchQuery.trim() !== '' || activeStatusFilter !== null;

  const activeFiltersCount = [
    filters.status !== 'all',
    filters.city !== 'all',
    filters.schoolType !== 'all',
    filters.stage !== 'all',
    searchQuery.trim() !== '',
    activeStatusFilter !== null,
  ].filter(Boolean).length;

  return (
    <div className="space-y-3 font-tajawal">
      {/* Main Control Card */}
      <Card className="rounded-3xl border-slate-200/80 dark:border-slate-800/80 shadow-md bg-white/90 dark:bg-slate-900/90 backdrop-blur-xl p-4 sm:p-5 transition-all">
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3.5">

          {/* Left: Search input & Match Counter */}
          <div className="relative flex-1 max-w-xl">
            <Search className={`absolute ${isRTL ? 'right-4' : 'left-4'} top-1/2 -translate-y-1/2 h-4.5 w-4.5 text-slate-400`} />
            <Input
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={
                isRTL
                  ? 'بحث باسم المدرسة، الكود، المدينة، البريد الإلكتروني...'
                  : 'Search by school name, tenant code, city, email...'
              }
              className={`${
                isRTL ? 'pr-11 pl-20' : 'pl-11 pr-20'
              } h-12 rounded-2xl bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white font-medium text-xs sm:text-sm focus:ring-2 focus:ring-[#46C1BE]/30 focus:border-[#46C1BE] shadow-xs transition-all`}
            />

            {/* Quick Clear Button & Count */}
            <div className={`absolute ${isRTL ? 'left-3' : 'right-3'} top-1/2 -translate-y-1/2 flex items-center gap-1.5`}>
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => onSearchChange('')}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800 transition-all"
                  title={isRTL ? 'مسح البحث' : 'Clear search'}
                >
                  <X className="h-4 w-4" />
                </button>
              )}
              {totalResultsCount !== undefined && (
                <span className="text-[11px] font-bold px-2 py-0.5 rounded-lg bg-slate-200/70 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono">
                  {totalResultsCount}
                </span>
              )}
            </div>
          </div>

          {/* Right: Quick Sort, Advanced Filter Button, View Mode Toggle */}
          <div className="flex items-center gap-2.5 flex-wrap justify-between lg:justify-end">

            {/* Sort Selector */}
            <div className="flex items-center gap-1.5">
              <Select value={sortBy || 'name_asc'} onValueChange={onSortChange}>
                <SelectTrigger className="h-11 rounded-2xl bg-slate-50 dark:bg-slate-950 font-bold text-xs border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 gap-2 px-3 shadow-xs">
                  <ArrowUpDown className="h-3.5 w-3.5 text-[#46C1BE]" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo rounded-2xl shadow-xl">
                  <SelectItem value="name_asc">{isRTL ? 'الاسم: أ - ي' : 'Name: A - Z'}</SelectItem>
                  <SelectItem value="name_desc">{isRTL ? 'الاسم: ي - أ' : 'Name: Z - A'}</SelectItem>
                  <SelectItem value="students_desc">{isRTL ? 'الأعلى طلاباً' : 'Most Students'}</SelectItem>
                  <SelectItem value="teachers_desc">{isRTL ? 'الأعلى معلمين' : 'Most Teachers'}</SelectItem>
                  <SelectItem value="classes_desc">{isRTL ? 'الأعلى فصولاً' : 'Most Classes'}</SelectItem>
                  <SelectItem value="newest">{isRTL ? 'الأحدث تسجيلاً' : 'Newest'}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Advanced Filters Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={onToggleFilters}
              className={`rounded-2xl h-11 px-4 text-xs font-bold gap-2 transition-all shadow-xs ${
                showFilters || hasAdvancedFilters
                  ? 'bg-[#1C3D74] text-white border-[#1C3D74] hover:bg-[#152e57] shadow-md shadow-[#1C3D74]/20'
                  : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-100'
              }`}
            >
              <SlidersHorizontal className="h-4 w-4 text-[#46C1BE]" />
              <span>{isRTL ? 'فلاتر متقدمة' : 'Filters'}</span>
              {activeFiltersCount > 0 && (
                <span className="w-5 h-5 rounded-full bg-[#46C1BE] text-slate-950 text-[10px] font-black flex items-center justify-center">
                  {activeFiltersCount}
                </span>
              )}
            </Button>

            {/* View Mode Toggle: Grid vs Table */}
            <div className="flex items-center bg-slate-100 dark:bg-slate-950 p-1 rounded-2xl border border-slate-200/80 dark:border-slate-800">
              <button
                type="button"
                onClick={() => onViewModeChange('grid')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  viewMode === 'grid'
                    ? 'bg-white dark:bg-slate-900 text-[#1C3D74] dark:text-[#46C1BE] shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title={isRTL ? 'عرض البطاقات' : 'Cards View'}
              >
                <LayoutGrid className="h-4 w-4" />
                <span className="hidden sm:inline">{isRTL ? 'بطاقات' : 'Cards'}</span>
              </button>
              <button
                type="button"
                onClick={() => onViewModeChange('table')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  viewMode === 'table'
                    ? 'bg-white dark:bg-slate-900 text-[#1C3D74] dark:text-[#46C1BE] shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
                title={isRTL ? 'عرض الجدول' : 'Table View'}
              >
                <List className="h-4 w-4" />
                <span className="hidden sm:inline">{isRTL ? 'جدول' : 'Table'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Expandable Advanced Filters Grid */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3.5 animate-in fade-in-30 slide-in-from-top-2 duration-200">
            {/* Status Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-[#46C1BE]" />
                <span>{isRTL ? 'الحالة' : 'Status'}</span>
              </label>
              <Select
                value={filters.status}
                onValueChange={(v) => onFilterChange('status', v)}
              >
                <SelectTrigger className="h-10.5 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
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
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Building2 className="h-3 w-3 text-[#46C1BE]" />
                <span>{isRTL ? 'المدينة' : 'City'}</span>
              </label>
              <Select
                value={filters.city}
                onValueChange={(v) => onFilterChange('city', v)}
              >
                <SelectTrigger className="h-10.5 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo max-h-60">
                  <SelectItem value="all">{isRTL ? 'جميع المدن' : 'All Cities'}</SelectItem>
                  {cities.map((city) => (
                    <SelectItem key={city} value={city}>{city}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* School Type Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Building2 className="h-3 w-3 text-[#46C1BE]" />
                <span>{isRTL ? 'نوع المدرسة' : 'School Type'}</span>
              </label>
              <Select
                value={filters.schoolType}
                onValueChange={(v) => onFilterChange('schoolType', v)}
              >
                <SelectTrigger className="h-10.5 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  <SelectItem value="all">{isRTL ? 'جميع الأنواع' : 'All Types'}</SelectItem>
                  {SCHOOL_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {isRTL ? t.label : t.label_en}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Stage Filter */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                <Layers className="h-3 w-3 text-[#46C1BE]" />
                <span>{isRTL ? 'المرحلة التعليمية' : 'Stage'}</span>
              </label>
              <Select
                value={filters.stage}
                onValueChange={(v) => onFilterChange('stage', v)}
              >
                <SelectTrigger className="h-10.5 rounded-xl bg-slate-50 dark:bg-slate-950 font-medium text-xs border-slate-200 dark:border-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  <SelectItem value="all">{isRTL ? 'جميع المراحل' : 'All Stages'}</SelectItem>
                  {EDUCATIONAL_STAGES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {isRTL ? s.label : s.label_en}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </Card>

      {/* Active Filters Tag Bar (When filters or search are active) */}
      {hasAnyFilters && (
        <div className="flex items-center gap-2 flex-wrap px-1 animate-in fade-in-30 duration-200">
          <span className="text-xs font-bold text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <Filter className="h-3.5 w-3.5 text-[#46C1BE]" />
            <span>{isRTL ? 'الفلاتر النشطة:' : 'Active Filters:'}</span>
          </span>

          {searchQuery && (
            <Badge className="rounded-xl px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-medium gap-1.5">
              <span>{isRTL ? `بحث: "${searchQuery}"` : `Search: "${searchQuery}"`}</span>
              <button
                type="button"
                onClick={() => onSearchChange('')}
                className="hover:text-rose-500"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {activeStatusFilter && (
            <Badge className="rounded-xl px-2.5 py-1 bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-blue-300 border border-blue-200 dark:border-blue-800 text-xs font-bold gap-1.5">
              <span>
                {isRTL
                  ? `الحالة: ${SCHOOL_STATUS[activeStatusFilter]?.label || activeStatusFilter}`
                  : `Status: ${SCHOOL_STATUS[activeStatusFilter]?.label_en || activeStatusFilter}`}
              </span>
              <button
                type="button"
                onClick={() => onStatusFilterChange(null)}
                className="hover:text-rose-500"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {filters.status !== 'all' && (
            <Badge className="rounded-xl px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-medium gap-1.5">
              <span>
                {isRTL
                  ? `الحالة: ${SCHOOL_STATUS[filters.status]?.label || filters.status}`
                  : `Status: ${SCHOOL_STATUS[filters.status]?.label_en || filters.status}`}
              </span>
              <button
                type="button"
                onClick={() => onFilterChange('status', 'all')}
                className="hover:text-rose-500"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {filters.city !== 'all' && (
            <Badge className="rounded-xl px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-medium gap-1.5">
              <span>{isRTL ? `المدينة: ${filters.city}` : `City: ${filters.city}`}</span>
              <button
                type="button"
                onClick={() => onFilterChange('city', 'all')}
                className="hover:text-rose-500"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {filters.schoolType !== 'all' && (
            <Badge className="rounded-xl px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-medium gap-1.5">
              <span>{isRTL ? `النوع: ${filters.schoolType === 'private' ? 'أهلية' : 'حكومية'}` : `Type: ${filters.schoolType}`}</span>
              <button
                type="button"
                onClick={() => onFilterChange('schoolType', 'all')}
                className="hover:text-rose-500"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          {filters.stage !== 'all' && (
            <Badge className="rounded-xl px-2.5 py-1 bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-medium gap-1.5">
              <span>
                {isRTL
                  ? `المرحلة: ${EDUCATIONAL_STAGES.find(s => s.value === filters.stage)?.label || filters.stage}`
                  : `Stage: ${EDUCATIONAL_STAGES.find(s => s.value === filters.stage)?.label_en || filters.stage}`}
              </span>
              <button
                type="button"
                onClick={() => onFilterChange('stage', 'all')}
                className="hover:text-rose-500"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={onResetFilters}
            className="h-7 text-xs font-bold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl px-2.5 gap-1"
          >
            <RotateCcw className="h-3 w-3" />
            <span>{isRTL ? 'مسح الكل' : 'Clear All'}</span>
          </Button>
        </div>
      )}
    </div>
  );
}
