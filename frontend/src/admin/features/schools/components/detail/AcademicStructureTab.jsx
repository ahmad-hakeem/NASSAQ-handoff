import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import {
  GraduationCap, BookOpen, Layers, CheckCircle2, XCircle
} from 'lucide-react';

export default function AcademicStructureTab({
  students = [],
  classes = [],
  isRTL,
  t,
}) {
  return (
    <div className="space-y-6">
      {/* Students List Card */}
      <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
        <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-4">
          <CardTitle className="font-cairo text-base font-extrabold flex items-center gap-2 text-slate-900 dark:text-white">
            <GraduationCap className="h-5 w-5 text-[#46C1BE]" />
            <span>{isRTL ? `قائمة الطلاب (${students.length})` : `Students (${students.length})`}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {students.length === 0 ? (
            <div className="text-center py-12 px-4">
              <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-400">
                <GraduationCap className="h-7 w-7" />
              </div>
              <p className="font-bold text-xs text-slate-600 dark:text-slate-400 font-cairo">
                {isRTL ? 'لا يوجد طلاب مسجلون حالياً' : 'No students found'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50/80 dark:bg-slate-800/50 border-b border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-300">
                    <th className={`p-3.5 font-bold ${isRTL ? 'text-right' : 'text-left'}`}>{t('name') || (isRTL ? 'اسم الطالب' : 'Student Name')}</th>
                    <th className="p-3.5 font-bold text-center">{t('grade') || (isRTL ? 'الصف الدراسي' : 'Grade Level')}</th>
                    <th className="p-3.5 font-bold text-center">{t('status2') || (isRTL ? 'الحالة' : 'Status')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {students.slice(0, 50).map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3.5 font-bold text-slate-900 dark:text-white">
                        {s.full_name || s.name || '—'}
                      </td>
                      <td className="p-3.5 text-center font-medium text-slate-600 dark:text-slate-400">
                        {s.grade_level || s.grade || '—'}
                      </td>
                      <td className="p-3.5 text-center">
                        {s.is_active !== false ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>{t('active') || (isRTL ? 'نشط' : 'Active')}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-rose-500 font-bold">
                            <XCircle className="h-3.5 w-3.5" />
                            <span>{t('inactive') || (isRTL ? 'غير نشط' : 'Inactive')}</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Classes Grid Card */}
      <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
        <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-4">
          <CardTitle className="font-cairo text-base font-extrabold flex items-center gap-2 text-slate-900 dark:text-white">
            <BookOpen className="h-5 w-5 text-[#615090]" />
            <span>{isRTL ? `الفصول والشعب الدراسية (${classes.length})` : `Classes & Sections (${classes.length})`}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          {classes.length === 0 ? (
            <div className="text-center py-12 px-4">
              <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-400">
                <BookOpen className="h-7 w-7" />
              </div>
              <p className="font-bold text-xs text-slate-600 dark:text-slate-400 font-cairo">
                {t('noClassesFound2') || (isRTL ? 'لا توجد فصول دراسية مهيأة حتى الآن' : 'No classes configured yet')}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3.5">
              {classes.map((cls) => (
                <div
                  key={cls.id}
                  className="p-4 rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 text-center hover:border-slate-300 dark:hover:border-slate-700 transition-all shadow-2xs"
                >
                  <div className="w-8 h-8 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-[#615090] dark:text-purple-300 flex items-center justify-center mx-auto mb-2 font-bold text-xs">
                    <Layers className="h-4 w-4" />
                  </div>
                  <p className="font-bold text-slate-900 dark:text-white text-xs font-cairo truncate">
                    {cls.name || cls.class_name || '—'}
                  </p>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 truncate">
                    {cls.grade_level || cls.grade || (isRTL ? 'عام' : 'General')}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
