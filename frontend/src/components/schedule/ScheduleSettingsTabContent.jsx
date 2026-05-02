/**
 * محتوى تبويب "إعدادات الجدول المدرسي" داخل صفحة الجدول الذكي
 * نَسَّق | NASSAQ — Task #114
 *
 * يُعيد استخدام نفس مكوّن DynamicSettingsContent ونفس مودالات
 * SettingsModals وخطّاف useSchoolSettings المستعملة في صفحة "إعدادات
 * المدرسة"، لكن بقائمة تبويبات فرعية مقتصرة على إعدادات الجدول الخمس:
 *   - التوقيت والحصص
 *   - الفصول والشعب
 *   - إسناد المعلمين
 *   - أوقات عدم التوفر
 *   - قيود الجدول
 *
 * لا تعديلات داخلية على المكوّنات أو الخطّاف — مجرد تمرير قائمة
 * تبويبات مُصفّاة عبر prop.
 */

import React, { useEffect } from 'react';
import { Loader2, Clock, School, Link2, UserX, Shield } from 'lucide-react';
import { useSchoolSettings } from '../../hooks/useSchoolSettings';
import { DynamicSettingsContent } from '../school-settings/DynamicSettingsContent';
import { SettingsModals } from '../school-settings/SettingsModals';

const scheduleSubTabs = [
  { id: 'timings', label: 'التوقيت والحصص', icon: Clock },
  { id: 'classes', label: 'الفصول والشعب', icon: School },
  { id: 'teacher-assignments', label: 'إسناد المعلمين', icon: Link2 },
  { id: 'unavailability', label: 'أوقات عدم التوفر', icon: UserX },
  { id: 'constraints', label: 'قيود الجدول', icon: Shield },
];

const SCHEDULE_TAB_IDS = scheduleSubTabs.map(t => t.id);

export default function ScheduleSettingsTabContent() {
  const hook = useSchoolSettings();
  const { loading, activeTab, setActiveTab } = hook;

  // التبويب الافتراضي للجدول هو "التوقيت والحصص" — إذا فتح المستخدم
  // التبويب وكان النشط هو "بيانات المدرسة" (وهو غير معروض هنا) أو أي
  // قيمة غير معروفة، نعيد ضبطه على أول تبويب صحيح.
  useEffect(() => {
    if (!SCHEDULE_TAB_IDS.includes(activeTab)) {
      setActiveTab('timings');
    }
  }, [activeTab, setActiveTab]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500">
        <Loader2 className="h-6 w-6 animate-spin ml-2" />
        جارٍ تحميل إعدادات الجدول…
      </div>
    );
  }

  return (
    <div data-testid="schedule-settings-tab-content">
      <DynamicSettingsContent hook={hook} dynamicTabs={scheduleSubTabs} />
      <SettingsModals hook={hook} />
    </div>
  );
}
