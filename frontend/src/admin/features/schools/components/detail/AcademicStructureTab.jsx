import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import {
  GraduationCap, BookOpen, Layers, CheckCircle2, XCircle, Search, X, Users
} from 'lucide-react';

export default function AcademicStructureTab({
  students = [],
  classes = [],
  isRTL,
  t,
}) {
  const [studentSearch, setStudentSearch] = useState('');
  const [classSearch, setClassSearch] = useState('');

  const filteredStudents = useMemo(() => {
    if (!studentSearch.trim()) return students;
    const q = studentSearch.toLowerCase().trim();
    return students.filter(s =>
      s.full_name?.toLowerCase().includes(q) ||
      s.name?.toLowerCase().includes(q) ||
      s.grade_level?.toLowerCase().includes(q) ||
      s.grade?.toLowerCase().includes(q)
    );
  }, [students, studentSearch]);

  const filteredClasses = useMemo(() => {
    if (!classSearch.trim()) return classes;
    const q = classSearch.toLowerCase().trim();
    return classes.filter(c =>
      c.name?.toLowerCase().includes(q) ||
      c.class_name?.toLowerCase().includes(q) ||
      c.grade_level?.toLowerCase().includes(q)
    );
  }, [classes, classSearch]);

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'} className="space-y-6 font-tajawal">
      {/* 1. Classes and Sections Grid Card */}
      <Card className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800/80 pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-[#615090] dark:text-purple-300 flex items-center justify-center shrink-0 border border-purple-100 dark:border-purple-900/60">
              <BookOpen className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white">
                {isRTL ? 'الفصول والشعب الدراسية' : 'Classes & Sections'}
              </CardTitle>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                {isRTL ? `إجمالي الفصول: ${classes.length} فصل` : `Total classes: ${classes.length}`}
              </p>
            </div>
          </div>

          {classes.length > 0 && (
            <div className="relative w-full sm:w-56">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <Input
                value={classSearch}
                onChange={(e) => setClassSearch(e.target.value)}
                placeholder={isRTL ? 'بحث عن فصل...' : 'Search class...'}
                className="ps-9 pe-7 h-9 rounded-xl text-xs bg-slate-50/80 dark:bg-slate-950 border-slate-200/90 dark:border-slate-800 focus:ring-2 focus:ring-[#615090]/20 focus:border-[#615090]"
              />
              {classSearch && (
                <button
                  onClick={() => setClassSearch('')}
                  className="absolute end-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent className="p-5">
          {classes.length === 0 ? (
            <div className="text-center py-10 px-4">
              <div className="w-12 h-12 rounded-xl bg-purple-50 dark:bg-purple-950/40 border border-purple-100 dark:border-purple-900/60 flex items-center justify-center mx-auto mb-2.5 text-[#615090] dark:text-purple-300">
                <BookOpen className="h-6 w-6" />
              </div>
              <p className="font-bold text-xs text-slate-700 dark:text-slate-300 font-cairo">
                {t('noClassesFound2') || (isRTL ? 'لا توجد فصول دراسية مهيأة لهذه المدرسة حتى الآن' : 'No classes configured for this school yet')}
              </p>
            </div>
          ) : filteredClasses.length === 0 ? (
            <div className="text-center py-6 text-xs text-slate-500 font-medium">
              {isRTL ? 'لا توجد فصول مطابقة للبحث' : 'No classes matched your search'}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {filteredClasses.map((cls) => (
                <div
                  key={cls.id}
                  className="p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/40 text-center hover:border-purple-200 dark:hover:border-purple-800 hover:bg-slate-100/60 dark:hover:bg-slate-800/70 transition-all group"
                >
                  <div className="w-8 h-8 rounded-lg bg-white dark:bg-slate-900 text-[#615090] dark:text-purple-300 shadow-2xs border border-slate-200/60 dark:border-slate-700 flex items-center justify-center mx-auto mb-2 font-bold text-xs">
                    <Layers className="h-3.5 w-3.5" />
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

      {/* 2. Students List Card */}
      <Card className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
        <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800/80 pb-3.5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 flex items-center justify-center shrink-0 border border-sky-100 dark:border-sky-900/60">
              <GraduationCap className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white">
                {isRTL ? 'قائمة الطلاب المقيدين' : 'Enrolled Students'}
              </CardTitle>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                {isRTL ? `المسجلون: ${students.length} طالب` : `Total: ${students.length} students`}
              </p>
            </div>
          </div>

          {students.length > 0 && (
            <div className="relative w-full sm:w-56">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <Input
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                placeholder={isRTL ? 'بحث عن طالب...' : 'Search student...'}
                className="ps-9 pe-7 h-9 rounded-xl text-xs bg-slate-50/80 dark:bg-slate-950 border-slate-200/90 dark:border-slate-800 focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
              />
              {studentSearch && (
                <button
                  onClick={() => setStudentSearch('')}
                  className="absolute end-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent className="p-0">
          {students.length === 0 ? (
            <div className="text-center py-10 px-4">
              <div className="w-12 h-12 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-100 dark:border-sky-900/60 flex items-center justify-center mx-auto mb-2.5 text-sky-600 dark:text-sky-400">
                <GraduationCap className="h-6 w-6" />
              </div>
              <p className="font-bold text-xs text-slate-700 dark:text-slate-300 font-cairo">
                {isRTL ? 'لا يوجد طلاب مسجلون حالياً في هذه المدرسة' : 'No students enrolled yet'}
              </p>
            </div>
          ) : filteredStudents.length === 0 ? (
            <div className="text-center py-6 text-xs text-slate-500 font-medium">
              {isRTL ? 'لا توجد نتائج مطابقة لبحث الطلاب' : 'No students matched your search'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50/80 dark:bg-slate-800/50 border-b border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-300 font-cairo">
                    <th className="p-3 font-bold text-start">{t('name') || (isRTL ? 'اسم الطالب' : 'Student Name')}</th>
                    <th className="p-3 font-bold text-center">{t('grade') || (isRTL ? 'الصف الدراسي' : 'Grade Level')}</th>
                    <th className="p-3 font-bold text-center">{t('status2') || (isRTL ? 'الحالة' : 'Status')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                  {filteredStudents.slice(0, 50).map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3 font-bold text-slate-900 dark:text-white">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-300 flex items-center justify-center font-bold text-xs shrink-0 border border-sky-100 dark:border-sky-900/60">
                            {s.full_name?.charAt(0) || s.name?.charAt(0) || 'ط'}
                          </div>
                          <span>{s.full_name || s.name || '—'}</span>
                        </div>
                      </td>
                      <td className="p-3 text-center font-medium text-slate-600 dark:text-slate-400">
                        {s.grade_level || s.grade || '—'}
                      </td>
                      <td className="p-3 text-center">
                        {s.is_active !== false ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold text-xs">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>{t('active') || (isRTL ? 'نشط' : 'Active')}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-rose-500 font-bold text-xs">
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
    </div>
  );
}
