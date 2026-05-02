import React from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import {
  Save, RefreshCw, GraduationCap,
  Building2, Zap,
} from 'lucide-react';
import { AcademicStructureContent } from './AcademicStructurePage';
import { useSchoolSettings } from '../hooks/useSchoolSettings';
import { DynamicSettingsContent } from '../components/school-settings/DynamicSettingsContent';
import { SettingsModals } from '../components/school-settings/SettingsModals';

// بعد المهمة #114 لم يعد يُعرض هنا سوى تبويب "بيانات المدرسة" — نُقلت بقية
// تبويبات الإعدادات (التوقيت، الفصول، الإسناد، عدم التوفر، القيود) إلى
// تبويب جديد داخل صفحة "الجدول المدرسي الذكي".
const dynamicTabs = [
  { id: 'school-info', label: 'بيانات المدرسة', icon: Building2 },
];


function SchoolSettingsPagePro() {
  const hook = useSchoolSettings();
  const {
    activeSection, setActiveSection, activeTab, setActiveTab,
    loading, saving, hasChanges,
    fetchData, saveAllSettings,
  } = hook;

  // نضمن أن يكون التبويب النشط هو دائماً "بيانات المدرسة" داخل صفحة
  // إعدادات المدرسة، حتى لو كان الرابط يحمل قيمة أخرى تركتها صفحة أخرى.
  React.useEffect(() => {
    if (activeSection === 'dynamic' && activeTab !== 'school-info') {
      setActiveTab('school-info');
    }
  }, [activeSection, activeTab, setActiveTab]);

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
              <p className="text-slate-500 mt-1">بيانات المدرسة الأساسية والهيكل الأكاديمي</p>
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

          {/* بانر "جاهزية الجدول" حُذف بناءً على طلب المنتج — لم يعد له
              مكان في صفحة إعدادات المدرسة بعد فصل تبويبات الجدول إلى
              صفحة "الجدول المدرسي الذكي". */}

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
                <p className={`font-bold text-sm truncate ${activeSection === 'dynamic' ? 'text-white' : 'text-slate-800'}`}>بيانات المدرسة</p>
                <p className={`text-xs truncate ${activeSection === 'dynamic' ? 'text-white/70' : 'text-slate-400'}`}>المعلومات الأساسية والاعتماد الرسمي</p>
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
