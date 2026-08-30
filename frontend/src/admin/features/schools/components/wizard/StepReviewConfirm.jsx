import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import {
  Building2, GraduationCap, User, CheckCircle2, Edit3
} from 'lucide-react';
import {
  COUNTRIES, CALENDAR_SYSTEMS, SCHOOL_TYPES, EDUCATIONAL_STAGES, ASSESSMENT_SYSTEMS
} from '../../constants/schoolConstants';

export default function StepReviewConfirm({
  schoolData,
  settingsData,
  principalData,
  onGoToStep,
  isRTL,
}) {
  return (
    <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300 font-tajawal" data-testid="wizard-step-4">
      {/* Title */}
      <div className="mb-6 text-start">
        <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          <span>{isRTL ? 'مراجعة وتأكيد البيانات' : 'Review & Confirm'}</span>
        </h3>
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
          {isRTL ? 'يرجى مراجعة كافة بيانات المدرسة قبل تأكيد عملية الإنشاء' : 'Please review all details before creating the school'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* School Profile Summary Card */}
        <Card className="bg-white dark:bg-slate-900 rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <CardHeader className="py-3.5 px-4 bg-slate-50/80 dark:bg-slate-800/80 border-b border-slate-200/80 dark:border-slate-700">
            <CardTitle className="text-xs font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
              <span className="flex items-center gap-1.5 font-cairo">
                <Building2 className="h-4 w-4 text-[#46C1BE]" />
                <span>{isRTL ? 'بيانات المدرسة' : 'School Info'}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onGoToStep(1)}
                className="h-7 text-[11px] font-bold text-[#1C3D74] dark:text-[#46C1BE] hover:bg-slate-200/60 dark:hover:bg-slate-700 px-2 rounded-lg"
              >
                <Edit3 className={`h-3 w-3 ${isRTL ? 'ms-1' : 'me-1'}`} />
                <span>{isRTL ? 'تعديل' : 'Edit'}</span>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-2.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الاسم:' : 'Name:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-bold truncate max-w-[150px]">{schoolData.name}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الدولة:' : 'Country:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{COUNTRIES.find((c) => c.code === schoolData.country)?.name}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'المدينة:' : 'City:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{schoolData.city}</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'العنوان:' : 'Address:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold truncate max-w-[140px]">{schoolData.address}</strong>
            </div>
          </CardContent>
        </Card>

        {/* Operating Settings Summary Card */}
        <Card className="bg-white dark:bg-slate-900 rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <CardHeader className="py-3.5 px-4 bg-slate-50/80 dark:bg-slate-800/80 border-b border-slate-200/80 dark:border-slate-700">
            <CardTitle className="text-xs font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
              <span className="flex items-center gap-1.5 font-cairo">
                <GraduationCap className="h-4 w-4 text-[#1C3D74] dark:text-[#46C1BE]" />
                <span>{isRTL ? 'إعدادات التشغيل' : 'Settings'}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onGoToStep(2)}
                className="h-7 text-[11px] font-bold text-[#1C3D74] dark:text-[#46C1BE] hover:bg-slate-200/60 dark:hover:bg-slate-700 px-2 rounded-lg"
              >
                <Edit3 className={`h-3 w-3 ${isRTL ? 'ms-1' : 'me-1'}`} />
                <span>{isRTL ? 'تعديل' : 'Edit'}</span>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-2.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'اللغة:' : 'Language:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{settingsData.defaultLanguage === 'ar' ? 'العربية' : 'English'}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'التقويم:' : 'Calendar:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{CALENDAR_SYSTEMS.find((c) => c.value === settingsData.calendarSystem)?.label}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'النوع:' : 'Type:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{SCHOOL_TYPES.find((st) => st.value === settingsData.schoolType)?.label}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'المرحلة:' : 'Stage:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{EDUCATIONAL_STAGES.find((s) => s.value === settingsData.educationalStage)?.label}</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'التقييم:' : 'Assessment:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-semibold">{ASSESSMENT_SYSTEMS.find((a) => a.value === settingsData.assessmentSystem)?.label}</strong>
            </div>
          </CardContent>
        </Card>

        {/* Principal Account Summary Card */}
        <Card className="bg-white dark:bg-slate-900 rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
          <CardHeader className="py-3.5 px-4 bg-slate-50/80 dark:bg-slate-800/80 border-b border-slate-200/80 dark:border-slate-700">
            <CardTitle className="text-xs font-bold flex items-center justify-between text-slate-900 dark:text-slate-100">
              <span className="flex items-center gap-1.5 font-cairo">
                <User className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <span>{isRTL ? 'مدير المدرسة' : 'Principal'}</span>
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onGoToStep(3)}
                className="h-7 text-[11px] font-bold text-[#1C3D74] dark:text-[#46C1BE] hover:bg-slate-200/60 dark:hover:bg-slate-700 px-2 rounded-lg"
              >
                <Edit3 className={`h-3 w-3 ${isRTL ? 'ms-1' : 'me-1'}`} />
                <span>{isRTL ? 'تعديل' : 'Edit'}</span>
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-2.5 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الاسم:' : 'Name:'}</span>
              <strong className="text-slate-900 dark:text-slate-100 font-bold truncate max-w-[150px]">{principalData.fullName}</strong>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'الهاتف:' : 'Phone:'}</span>
              <strong dir="ltr" className="text-slate-900 dark:text-slate-100 font-mono font-semibold">{principalData.primaryPhone}</strong>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-500 dark:text-slate-400 font-medium">{isRTL ? 'البريد:' : 'Email:'}</span>
              <strong dir="ltr" className="text-slate-900 dark:text-slate-100 font-mono font-semibold truncate max-w-[140px]">{principalData.email}</strong>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
