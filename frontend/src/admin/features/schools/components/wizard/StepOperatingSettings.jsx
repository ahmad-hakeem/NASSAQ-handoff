import React from 'react';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  GraduationCap, Languages, Calendar, Building2, Award, Sparkles, RotateCcw
} from 'lucide-react';
import {
  CALENDAR_SYSTEMS, SCHOOL_TYPES, EDUCATIONAL_STAGES,
  EDUCATIONAL_PATHWAYS, ASSESSMENT_SYSTEMS
} from '../../constants/schoolConstants';

export default function StepOperatingSettings({
  settingsData,
  setSettingsData,
  onResetDefaults,
  isRTL,
}) {
  return (
    <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300 font-tajawal" data-testid="wizard-step-2">
      {/* Title */}
      <div className="mb-6 text-start">
        <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
          <GraduationCap className="h-5 w-5 text-[#46C1BE]" />
          <span>{isRTL ? 'إعدادات التشغيل والنظام المدرسي' : 'School Operating Settings'}</span>
        </h3>
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
          {isRTL ? 'حدد التقويم والمرحلة ونظام التقييم المعتمد للمدرسة' : 'Set the calendar, educational stage, and grading system'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
        {/* Language */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
            <Languages className="h-4 w-4 text-[#46C1BE]" />
            <span>{isRTL ? 'اللغة الافتراضية' : 'Default Language'}</span>
          </Label>
          <Select
            value={settingsData.defaultLanguage}
            onValueChange={(v) => setSettingsData({ ...settingsData, defaultLanguage: v })}
          >
            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="language-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
              <SelectItem value="ar" className="font-medium text-slate-900 dark:text-slate-100">العربية (RTL)</SelectItem>
              <SelectItem value="en" className="font-medium text-slate-900 dark:text-slate-100">English (LTR)</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
            {isRTL ? 'يمكن لكل مستخدم تخصيص لغته لاحقاً' : 'Each user can customize language later'}
          </p>
        </div>

        {/* Calendar System */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
            <Calendar className="h-4 w-4 text-[#46C1BE]" />
            <span>{isRTL ? 'نظام التقويم' : 'Calendar System'}</span>
          </Label>
          <Select
            value={settingsData.calendarSystem}
            onValueChange={(v) => setSettingsData({ ...settingsData, calendarSystem: v })}
          >
            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="calendar-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
              {CALENDAR_SYSTEMS.map((cal) => (
                <SelectItem key={cal.value} value={cal.value} className="font-medium text-slate-900 dark:text-slate-100">
                  {isRTL ? cal.label : cal.label_en}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
            {isRTL ? 'التقويم الأساسي لحساب التواريخ المدرسية' : 'Primary calendar for school dates'}
          </p>
        </div>

        {/* School Type */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
            <Building2 className="h-4 w-4 text-[#46C1BE]" />
            <span>{isRTL ? 'نوع المدرسة' : 'School Type'}</span>
          </Label>
          <Select
            value={settingsData.schoolType}
            onValueChange={(v) => setSettingsData({ ...settingsData, schoolType: v })}
          >
            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="school-type-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
              {SCHOOL_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value} className="font-medium text-slate-900 dark:text-slate-100">
                  {isRTL ? type.label : type.label_en}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
            {isRTL ? 'حكومية أو أهلية معتمدة' : 'Public or accredited private'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
        {/* Educational Stage */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
            <GraduationCap className="h-4 w-4 text-[#1C3D74] dark:text-[#46C1BE]" />
            <span>{isRTL ? 'المرحلة التعليمية' : 'Educational Stage'}</span>
          </Label>
          <Select
            value={settingsData.educationalStage}
            onValueChange={(v) =>
              setSettingsData({
                ...settingsData,
                educationalStage: v,
                educationalPathway: v === 'secondary_pathways' ? settingsData.educationalPathway : '',
              })
            }
          >
            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="stage-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
              {EDUCATIONAL_STAGES.map((stage) => (
                <SelectItem key={stage.value} value={stage.value} className="font-medium text-slate-900 dark:text-slate-100">
                  {isRTL ? stage.label : stage.label_en}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
            {isRTL ? 'تحدد الكتالوج الافتراضي للمواد الدراسية' : 'Determines default subjects catalog'}
          </p>
        </div>

        {/* Assessment System */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
            <Award className="h-4 w-4 text-[#1C3D74] dark:text-[#46C1BE]" />
            <span>{isRTL ? 'نظام التقييم والدرجات' : 'Assessment System'}</span>
          </Label>
          <Select
            value={settingsData.assessmentSystem}
            onValueChange={(v) => setSettingsData({ ...settingsData, assessmentSystem: v })}
          >
            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="assessment-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
              {ASSESSMENT_SYSTEMS.map((sys) => (
                <SelectItem key={sys.value} value={sys.value} className="font-medium text-slate-900 dark:text-slate-100">
                  {isRTL ? sys.label : sys.label_en}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400 leading-tight">
            {isRTL ? 'يرتبط بقواعد الاختبارات وحساب المعدلات' : 'Linked to tests & GPA rules'}
          </p>
        </div>
      </div>

      {/* Secondary Pathways Option */}
      {settingsData.educationalStage === 'secondary_pathways' && (
        <div className="mb-5 p-5 bg-indigo-50/70 dark:bg-slate-900 rounded-3xl border border-indigo-200 dark:border-indigo-900/60 shadow-sm animate-in fade-in-30 duration-200 space-y-2">
          <Label className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
            <Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-400" />
            <span>{isRTL ? 'المسار التخصصي للمرحلة الثانوية' : 'Secondary Educational Pathway'}</span>
          </Label>
          <Select
            value={settingsData.educationalPathway}
            onValueChange={(v) => setSettingsData({ ...settingsData, educationalPathway: v })}
          >
            <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="pathway-select">
              <SelectValue placeholder={isRTL ? 'اختر المسار التخصصي...' : 'Select educational pathway...'} />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
              {EDUCATIONAL_PATHWAYS.map((pathway) => (
                <SelectItem key={pathway.value} value={pathway.value} className="font-medium text-slate-900 dark:text-slate-100">
                  {isRTL ? pathway.label : pathway.label_en}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Reset to Defaults button */}
      <div className="flex justify-center pt-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onResetDefaults}
          className="text-xs font-bold text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 rounded-xl"
        >
          <RotateCcw className={`h-3.5 w-3.5 ${isRTL ? 'ms-1.5' : 'me-1.5'} text-slate-500`} />
          <span>{isRTL ? 'استعادة الإعدادات الافتراضية' : 'Reset to Defaults'}</span>
        </Button>
      </div>
    </div>
  );
}
