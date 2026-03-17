/**
 * TimetableViewControls Component
 * أدوات التحكم في عرض الجدول
 * 
 * يتحكم في طريقة عرض الجدول والفلاتر والبحث
 */

import React from 'react';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Switch } from '../../components/ui/switch';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { 
  GraduationCap, User, CalendarDays, BookOpen,
  Search, X, SlidersHorizontal, Eye, EyeOff
} from 'lucide-react';
import { ViewModes } from './types';

// View Mode Tabs Component
const TimetableViewModeTabs = ({ activeMode, onChange }) => {
  return (
    <Tabs value={activeMode} onValueChange={onChange}>
      <TabsList className="grid grid-cols-4 w-[400px] bg-muted/50">
        <TabsTrigger value={ViewModes.CLASS} className="gap-2 data-[state=active]:bg-brand-navy data-[state=active]:text-white">
          <GraduationCap className="h-4 w-4" />
          <span className="hidden sm:inline">بالفصل</span>
        </TabsTrigger>
        <TabsTrigger value={ViewModes.TEACHER} className="gap-2 data-[state=active]:bg-brand-navy data-[state=active]:text-white">
          <User className="h-4 w-4" />
          <span className="hidden sm:inline">بالمعلم</span>
        </TabsTrigger>
        <TabsTrigger value={ViewModes.GRADE} className="gap-2 data-[state=active]:bg-brand-navy data-[state=active]:text-white">
          <BookOpen className="h-4 w-4" />
          <span className="hidden sm:inline">بالصف</span>
        </TabsTrigger>
        <TabsTrigger value={ViewModes.DAY} className="gap-2 data-[state=active]:bg-brand-navy data-[state=active]:text-white">
          <CalendarDays className="h-4 w-4" />
          <span className="hidden sm:inline">باليوم</span>
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
};

// Search Input Component
const TimetableSearchInput = ({ value, placeholder = 'بحث...', onChange, onClear }) => {
  return (
    <div className="relative w-[240px]">
      <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-10 pl-8"
        data-testid="timetable-search-input"
      />
      {value && (
        <Button
          variant="ghost"
          size="icon"
          className="absolute left-1 top-1/2 -translate-y-1/2 h-6 w-6"
          onClick={onClear}
        >
          <X className="h-3 w-3" />
        </Button>
      )}
    </div>
  );
};

// Toggle Controls Component
const TimetableToggleControls = ({ toggles, onChange }) => {
  const handleToggle = (key) => {
    onChange({ [key]: !toggles[key] });
  };

  return (
    <div className="flex items-center gap-4 p-2 bg-muted/30 rounded-lg">
      <div className="flex items-center gap-2">
        <Switch
          id="show-breaks"
          checked={toggles.showBreaks}
          onCheckedChange={() => handleToggle('showBreaks')}
        />
        <Label htmlFor="show-breaks" className="text-xs cursor-pointer">
          الاستراحات
        </Label>
      </div>
      
      <div className="flex items-center gap-2">
        <Switch
          id="show-prayer"
          checked={toggles.showPrayer}
          onCheckedChange={() => handleToggle('showPrayer')}
        />
        <Label htmlFor="show-prayer" className="text-xs cursor-pointer">
          الصلاة
        </Label>
      </div>
      
      <div className="flex items-center gap-2">
        <Switch
          id="show-warnings"
          checked={toggles.showWarnings}
          onCheckedChange={() => handleToggle('showWarnings')}
        />
        <Label htmlFor="show-warnings" className="text-xs cursor-pointer">
          التحذيرات
        </Label>
      </div>
      
      <div className="flex items-center gap-2">
        <Switch
          id="show-color-coding"
          checked={toggles.showColorCoding}
          onCheckedChange={() => handleToggle('showColorCoding')}
        />
        <Label htmlFor="show-color-coding" className="text-xs cursor-pointer">
          الألوان
        </Label>
      </div>
    </div>
  );
};

// Main View Controls Component
const TimetableViewControls = ({
  activeViewMode = ViewModes.CLASS,
  selectedClassId,
  selectedTeacherId,
  selectedGradeId,
  selectedWeekday,
  selectedVersionId,
  selectedSubjectId,
  classes = [],
  teachers = [],
  grades = [],
  subjects = [],
  weekdays = [],
  versions = [],
  searchQuery = '',
  toggles = {
    showBreaks: true,
    showPrayer: true,
    showWarnings: true,
    showColorCoding: true,
    showCoreSubjectsOnly: false
  },
  onViewModeChange,
  onClassChange,
  onTeacherChange,
  onGradeChange,
  onWeekdayChange,
  onVersionChange,
  onSubjectChange,
  onSearchChange,
  onToggleChange,
  showFilters = true,
  showSearch = true,
  showToggles = false
}) => {

  // Get dynamic filters based on view mode
  const renderFilters = () => {
    switch (activeViewMode) {
      case ViewModes.CLASS:
        return (
          <>
            {/* Grade Filter */}
            <Select value={selectedGradeId || 'all'} onValueChange={(val) => onGradeChange(val === 'all' ? null : val)}>
              <SelectTrigger className="w-[160px]" data-testid="grade-filter">
                <SelectValue placeholder="كل الصفوف" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">كل الصفوف</SelectItem>
                {grades.filter(g => g.id || g.value).map(g => (
                  <SelectItem key={g.id || g.value} value={g.id || g.value}>
                    {g.name_ar || g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Class Filter */}
            {classes.length > 0 && (
              <Select value={selectedClassId || 'all'} onValueChange={(val) => onClassChange(val === 'all' ? null : val)}>
                <SelectTrigger className="w-[180px]" data-testid="class-filter">
                  <SelectValue placeholder="اختر الفصل" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">كل الفصول</SelectItem>
                  {classes.filter(c => c.id || c.value).map(c => (
                    <SelectItem key={c.id || c.value} value={c.id || c.value}>
                      {c.name || c.name_ar || c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </>
        );
        
      case ViewModes.TEACHER:
        return (
          <>
            {/* Teacher Filter */}
            {teachers.length > 0 && (
              <Select value={selectedTeacherId || 'all'} onValueChange={(val) => onTeacherChange(val === 'all' ? null : val)}>
                <SelectTrigger className="w-[200px]" data-testid="teacher-filter">
                  <SelectValue placeholder="اختر المعلم" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">كل المعلمين</SelectItem>
                  {teachers.filter(t => t.id || t.value).map(t => (
                    <SelectItem key={t.id || t.value} value={t.id || t.value}>
                      {t.full_name || t.name || t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            
            {/* Subject Filter (optional) */}
            <Select value={selectedSubjectId || 'all'} onValueChange={(val) => onSubjectChange(val === 'all' ? null : val)}>
              <SelectTrigger className="w-[160px]" data-testid="subject-filter">
                <SelectValue placeholder="كل المواد" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">كل المواد</SelectItem>
                {subjects.filter(s => s.id || s.value).map(s => (
                  <SelectItem key={s.id || s.value} value={s.id || s.value}>
                    {s.name_ar || s.name || s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        );
        
      case ViewModes.GRADE:
        return (
          <>
            {/* Grade Filter */}
            {grades.length > 0 && (
              <Select value={selectedGradeId || 'all'} onValueChange={(val) => onGradeChange(val === 'all' ? null : val)}>
                <SelectTrigger className="w-[180px]" data-testid="grade-filter">
                  <SelectValue placeholder="اختر الصف" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">كل الصفوف</SelectItem>
                  {grades.filter(g => g.id || g.value).map(g => (
                    <SelectItem key={g.id || g.value} value={g.id || g.value}>
                      {g.name_ar || g.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </>
        );
        
      case ViewModes.DAY:
        return (
          <>
            {/* Weekday Filter */}
            <Select value={selectedWeekday?.toString() || 'all'} onValueChange={(val) => onWeekdayChange(val === 'all' ? null : parseInt(val))}>
              <SelectTrigger className="w-[160px]" data-testid="weekday-filter">
                <SelectValue placeholder="اختر اليوم" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">كل الأيام</SelectItem>
                {weekdays.filter(d => d.number !== undefined || d.value !== undefined).map(d => (
                  <SelectItem key={d.number ?? d.value} value={(d.number ?? d.value)?.toString()}>
                    {d.ar || d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            {/* Grade or Teacher Filter */}
            <Select value={selectedGradeId || 'all'} onValueChange={(val) => onGradeChange(val === 'all' ? null : val)}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="كل الصفوف" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">كل الصفوف</SelectItem>
                {grades.filter(g => g.id || g.value).map(g => (
                  <SelectItem key={g.id || g.value} value={g.id || g.value}>
                    {g.name_ar || g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        );
        
      default:
        return null;
    }
  };

  return (
    <div 
      className="space-y-4 p-4 bg-white rounded-xl border border-gray-200 shadow-sm"
      data-testid="timetable-view-controls"
    >
      {/* Top Row - View Mode Tabs & Search */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* View Mode Tabs */}
        <TimetableViewModeTabs 
          activeMode={activeViewMode} 
          onChange={onViewModeChange}
        />
        
        {/* Search */}
        {showSearch && (
          <TimetableSearchInput
            value={searchQuery}
            placeholder={`بحث في الجدول...`}
            onChange={onSearchChange}
            onClear={() => onSearchChange('')}
          />
        )}
      </div>
      
      {/* Middle Row - Filters */}
      {showFilters && (
        <div className="flex flex-wrap items-center gap-3">
          {/* Dynamic Filters based on View Mode */}
          {renderFilters()}
          
          {/* Version Filter - Always Visible */}
          {versions.length > 0 && (
            <Select value={selectedVersionId || 'all'} onValueChange={(val) => onVersionChange(val === 'all' ? null : val)}>
              <SelectTrigger className="w-[180px]" data-testid="version-filter">
                <SelectValue placeholder="اختر النسخة" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">كل النسخ</SelectItem>
                {versions.filter(v => v.id || v.value).map(v => (
                  <SelectItem key={v.id || v.value} value={v.id || v.value}>
                    <div className="flex items-center gap-2">
                      <span>{v.versionName || v.name || v.label}</span>
                      {v.status && (
                        <Badge variant="outline" className="text-xs">
                          {v.status === 'published' ? 'منشور' : 'مسودة'}
                        </Badge>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      )}
      
      {/* Bottom Row - Toggle Controls */}
      {showToggles && (
        <TimetableToggleControls 
          toggles={toggles} 
          onChange={onToggleChange}
        />
      )}
    </div>
  );
};

export default TimetableViewControls;
export { TimetableViewModeTabs, TimetableSearchInput, TimetableToggleControls };
