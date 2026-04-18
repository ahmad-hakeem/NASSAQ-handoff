import React from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Save, CheckCircle2, AlertTriangle,
  AlertCircle, Play, RefreshCw, X, GraduationCap,
  Building2, Zap, School, Link2, Edit2,
  Clock, UserX, Shield
} from 'lucide-react';
import { AcademicStructureContent } from './AcademicStructurePage';
import { useSchoolSettings } from '../hooks/useSchoolSettings';
import { DynamicSettingsContent } from '../components/school-settings/DynamicSettingsContent';
import { SettingsModals } from '../components/school-settings/SettingsModals';

const dynamicTabs = [
  { id: 'school-info', label: 'بيانات المدرسة', icon: Building2 },
  { id: 'timings', label: 'التوقيت والحصص', icon: Clock },
  { id: 'classes', label: 'الفصول والشعب', icon: School },
  { id: 'teacher-assignments', label: 'إسناد المعلمين', icon: Link2 },
  { id: 'unavailability', label: 'أوقات عدم التوفر', icon: UserX },
  { id: 'constraints', label: 'قيود الجدول', icon: Shield },
];


function SchoolSettingsPagePro() {
  const hook = useSchoolSettings();
  const {
    navigate, activeSection, setActiveSection, activeTab, setActiveTab,
    loading, saving, hasChanges, readinessData,
    fetchData, saveAllSettings, navigateToFix,
  } = hook;

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-slate-50" dir="rtl">
          <div className="flex items-center justify-center h-screen">
            <div className="text-center">
              <RefreshCw className="h-8 w-8 animate-spin text-[#1C3D74] mx-auto mb-4" />
              <p className="text-slate-600">جاري تحميل البيانات...</p>
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-slate-50" dir="rtl">
        <div className="overflow-auto">
          <div className="max-w-7xl mx-auto p-6 lg:p-8">

          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-slate-900">إعدادات المدرسة</h1>
              <p className="text-slate-500 mt-1">إدارة بيانات الجدول والمعلومات المرجعية</p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={fetchData} disabled={loading} data-testid="refresh-btn">
                <RefreshCw className={`h-4 w-4 ml-2 ${loading ? 'animate-spin' : ''}`} />
                تحديث
              </Button>
              {hasChanges && (
                <Button onClick={saveAllSettings} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-white px-6" data-testid="save-all-btn">
                  <Save className="h-4 w-4 ml-2" />
                  {saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                </Button>
              )}
            </div>
          </div>

          {readinessData && (
            <Card className="mb-6 overflow-hidden border-0 shadow-lg" data-testid="readiness-card">
              <div className={`p-5 ${
                readinessData.status === 'FULLY_READY'
                  ? 'bg-gradient-to-br from-emerald-600 via-emerald-500 to-brand-turquoise'
                  : readinessData.status === 'PARTIALLY_READY'
                  ? 'bg-gradient-to-br from-brand-navy via-[#2a5096] to-brand-turquoise/80'
                  : 'bg-gradient-to-br from-[#1C3D74] via-[#2a5096] to-brand-turquoise/60'
              } text-white`}>
                <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-5">
                    <div className="relative w-20 h-20 flex-shrink-0">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle cx="40" cy="40" r="34" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="6" />
                        <circle cx="40" cy="40" r="34" fill="none" stroke="white" strokeWidth="6" strokeLinecap="round" strokeDasharray={`${(readinessData.percentage / 100) * 214} 214`} />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-xl font-bold">{Math.round(readinessData.percentage)}%</span>
                      </div>
                    </div>
                    <div>
                      <h2 className="text-xl font-bold mb-1">
                        {readinessData.status === 'FULLY_READY' ? 'جاهز لإنشاء الجدول!' :
                         readinessData.status === 'PARTIALLY_READY' ? 'بيانات الجدول جاهزة جزئياً' :
                         'بيانات الجدول غير مكتملة'}
                      </h2>
                      <p className="text-white/80 text-sm">
                        {readinessData.summary?.critical_count > 0 && (
                          <span className="flex items-center gap-1">
                            <AlertCircle className="h-4 w-4" />
                            {readinessData.summary.critical_count} عناصر ضرورية مطلوبة لإنشاء الجدول
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <Button
                    size="lg"
                    className={`${readinessData.can_generate ? 'bg-white text-[#1C3D74] hover:bg-slate-100' : 'bg-white/20 text-white cursor-not-allowed'}`}
                    disabled={!readinessData.can_generate}
                    onClick={() => navigate('/school/schedule')}
                    data-testid="generate-timetable-btn"
                  >
                    <Play className="h-5 w-5 ml-2" />
                    {readinessData.can_generate ? 'الذهاب للجدول' : 'أكمل البيانات أولاً'}
                  </Button>
                </div>
              </div>

              {readinessData.critical_issues && readinessData.critical_issues.length > 0 && (
                <CardContent className="p-5 bg-white">
                  <div className="mb-4">
                    <h3 className="font-bold text-slate-800 flex items-center gap-2 mb-1">
                      <AlertTriangle className="h-5 w-5 text-amber-500" />
                      البيانات الضرورية المطلوبة
                    </h3>
                    <p className="text-sm text-slate-500">أكمل هذه البيانات لتتمكن من إنشاء الجدول المدرسي</p>
                  </div>
                  <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {Object.entries(readinessData.categories || {})
                      .filter(([_, cat]) => cat.status === 'critical')
                      .map(([categoryId, category]) => (
                        <div key={categoryId} className="p-4 rounded-xl border-2 border-red-200 bg-red-50 hover:border-red-300 transition-all">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-lg bg-red-500 flex items-center justify-center"><AlertCircle className="h-4 w-4 text-white" /></div>
                              <div>
                                <h4 className="font-bold text-red-800 text-sm">{category.name_ar}</h4>
                                <p className="text-xs text-red-600">{category.score}/{category.max_score} نقطة</p>
                              </div>
                            </div>
                          </div>
                          <ul className="space-y-1 mb-3">
                            {category.issues?.filter(i => i.type === 'critical').slice(0, 2).map((issue, idx) => (
                              <li key={idx} className="text-xs text-red-700 flex items-start gap-1"><X className="h-3 w-3 mt-0.5 flex-shrink-0" />{issue.message_ar}</li>
                            ))}
                          </ul>
                          <Button size="sm" className="w-full bg-red-600 hover:bg-red-700 text-white text-xs h-8" onClick={() => navigateToFix(categoryId)} data-testid={`fix-${categoryId}-btn`}>
                            <Edit2 className="h-3 w-3 ml-1" />{category.issues?.[0]?.fix_action || 'إصلاح'}
                          </Button>
                        </div>
                      ))}
                  </div>
                  {Object.entries(readinessData.categories || {}).filter(([_, cat]) => cat.status === 'ready').length > 0 && (
                    <div className="mt-4 pt-4 border-t">
                      <h4 className="text-sm font-medium text-slate-600 mb-2 flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" />البيانات المكتملة</h4>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(readinessData.categories || {}).filter(([_, cat]) => cat.status === 'ready').map(([categoryId, category]) => (
                          <Badge key={categoryId} className="bg-emerald-100 text-emerald-700 gap-1"><CheckCircle2 className="h-3 w-3" />{category.name_ar}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              )}

              {readinessData.status === 'FULLY_READY' && (
                <CardContent className="p-5 bg-emerald-50">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-8 w-8 text-emerald-600" />
                    <div>
                      <h3 className="font-bold text-emerald-800">جميع البيانات مكتملة!</h3>
                      <p className="text-sm text-emerald-600">يمكنك الآن إنشاء الجدول المدرسي بالذكاء الاصطناعي</p>
                    </div>
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          <div className="grid grid-cols-2 gap-3 mb-6">
            <button
              onClick={() => { setActiveSection('dynamic'); setActiveTab('school-info'); }}
              className={`relative group flex items-center gap-3 p-4 rounded-2xl border-2 transition-all duration-300 text-right ${
                activeSection === 'dynamic' ? 'border-[#1C3D74] bg-gradient-to-l from-[#1C3D74] to-[#2a5298] text-white shadow-lg scale-[1.02]' : 'border-slate-200 bg-white hover:border-[#1C3D74]/40 hover:shadow-md'
              }`}
              data-testid="section-dynamic-btn"
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all ${activeSection === 'dynamic' ? 'bg-white/20' : 'bg-[#1C3D74]/10'}`}>
                <Zap className={`h-5 w-5 ${activeSection === 'dynamic' ? 'text-white' : 'text-[#1C3D74]'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`font-bold text-sm truncate ${activeSection === 'dynamic' ? 'text-white' : 'text-slate-800'}`}>إعدادات المدرسة</p>
                <p className={`text-xs truncate ${activeSection === 'dynamic' ? 'text-white/70' : 'text-slate-400'}`}>بيانات المدرسة والفصول والإسناد</p>
              </div>
              {activeSection === 'dynamic' && <div className="absolute -bottom-1.5 right-1/2 translate-x-1/2 w-8 h-1.5 rounded-full bg-white/40" />}
            </button>

            <button
              onClick={() => setActiveSection('academic')}
              className={`relative group flex items-center gap-3 p-4 rounded-2xl border-2 transition-all duration-300 text-right ${
                activeSection === 'academic' ? 'border-teal-600 bg-gradient-to-l from-teal-600 to-teal-700 text-white shadow-lg scale-[1.02]' : 'border-slate-200 bg-white hover:border-teal-400 hover:shadow-md'
              }`}
              data-testid="section-academic-btn"
            >
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all ${activeSection === 'academic' ? 'bg-white/20' : 'bg-teal-600/10'}`}>
                <GraduationCap className={`h-5 w-5 ${activeSection === 'academic' ? 'text-white' : 'text-teal-600'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className={`font-bold text-sm truncate ${activeSection === 'academic' ? 'text-white' : 'text-slate-800'}`}>الهيكل الأكاديمي</p>
                <p className={`text-xs truncate ${activeSection === 'academic' ? 'text-white/70' : 'text-slate-400'}`}>السنة الدراسية والفصول والتقويم</p>
              </div>
              {activeSection === 'academic' && <div className="absolute -bottom-1.5 right-1/2 translate-x-1/2 w-8 h-1.5 rounded-full bg-white/40" />}
            </button>
          </div>

          {activeSection === 'dynamic' && <DynamicSettingsContent hook={hook} dynamicTabs={dynamicTabs} />}

          {activeSection === 'academic' && (
            <div className="space-y-6"><AcademicStructureContent /></div>
          )}

          </div>
        </div>
      </div>

      <SettingsModals hook={hook} />
    </Sidebar>
  );
}

export { SchoolSettingsPagePro };
export default SchoolSettingsPagePro;
