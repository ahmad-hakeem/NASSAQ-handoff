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
 * مزامنة ثنائية الاتجاه بين معطى الرابط `?sub=` وحالة التبويب الفرعي
 * النشط، حتى تكون كل تبويبة قابلة للحفظ والمشاركة عبر الـ URL.
 *
 * لا تعديلات داخلية على المكوّنات أو الخطّاف — مجرد تمرير قائمة
 * تبويبات مُصفّاة عبر prop.
 */

import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
const DEFAULT_SUB_TAB = 'timings';

export default function ScheduleSettingsTabContent() {
  const hook = useSchoolSettings();
  const { loading, activeTab, setActiveTab } = hook;
  const location = useLocation();
  const navigate = useNavigate();

  // ── 1) URL → state ─────────────────────────────────────────────
  // إذا تغيَّر معطى ?sub= في الرابط (مثلاً عبر زر "إصلاح" في بطاقة
  // الجاهزية أو رابط INF) نُزامن التبويب النشط ليطابقه. وإذا لم يكن
  // التبويب النشط ضمن تبويبات الجدول (مثلاً عند الانتقال من صفحة
  // إعدادات المدرسة حيث الافتراضي school-info) نضبطه على ?sub=
  // الموجود أو الافتراضي.
  useEffect(() => {
    const sub = new URLSearchParams(location.search).get('sub');
    if (sub && SCHEDULE_TAB_IDS.includes(sub)) {
      if (sub !== activeTab) setActiveTab(sub);
      return;
    }
    if (!SCHEDULE_TAB_IDS.includes(activeTab)) {
      setActiveTab(DEFAULT_SUB_TAB);
    }
  }, [location.search, activeTab, setActiveTab]);

  // ── 2) state → URL ─────────────────────────────────────────────
  // عندما يضغط المستخدم على تبويب فرعي داخل DynamicSettingsContent
  // (الذي يستدعي setActiveTab مباشرة) نكتب القيمة الجديدة في معطى
  // ?sub= حتى يكون الرابط دائماً معبِّراً عن الحالة المعروضة.
  useEffect(() => {
    if (!SCHEDULE_TAB_IDS.includes(activeTab)) return;
    const params = new URLSearchParams(location.search);
    if (params.get('sub') === activeTab) return;
    params.set('tab', 'settings');
    params.set('sub', activeTab);
    navigate(`${location.pathname}?${params.toString()}`, { replace: true });
  }, [activeTab, navigate, location.pathname, location.search]);

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
