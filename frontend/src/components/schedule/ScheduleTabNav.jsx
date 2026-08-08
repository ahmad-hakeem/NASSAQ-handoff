/**
 * شريط التبويبات الرئيسي لصفحة الجدول الذكي
 * نَسَّق | NASSAQ — Task #114
 *
 * يعرض ثلاثة تبويبات بنفس النمط البصري في كل صفحات الجدول:
 *   1) الجدول الرئيسي (المصفوفة)
 *   2) جدول حصص الانتظار
 *   3) إعدادات الجدول المدرسي
 *
 * على الشاشات الصغيرة (الجوال) يظهر التبويبان الأساسيان داخل عنصر تحكم
 * مقسوم نصفياً، بينما تنتقل «الإعدادات» إلى زر ترس مستقل بجانبه. على
 * الشاشات الأكبر (sm: وما فوق) يبقى صف التبويبات الثلاثية كما هو.
 *
 * كل تبويب يُحدِّث المسار ليبقى التنقل قابلاً للحفظ والمشاركة عبر الـ URL.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, Hourglass, Settings as SettingsIcon } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

// كل التبويبات تبقى ضمن `/principal/schedule` ويُعبَّر عنها بمعطى
// `?tab=master|standby|settings` ليكون التبويب النشط قابلاً للحفظ والمشاركة
// عبر الـ URL، ويُسهِّل التنقل البرمجي إليه (مثل بطاقة الجاهزية).
const TABS = [
  {
    id: 'master',
    labelKey: 'masterScheduleTab',
    icon: CalendarDays,
    path: '/principal/schedule?tab=master',
  },
  {
    id: 'standby',
    labelKey: 'standbyScheduleTab',
    icon: Hourglass,
    path: '/principal/schedule?tab=standby',
  },
  {
    id: 'settings',
    labelKey: 'scheduleSettingsTab',
    icon: SettingsIcon,
    path: '/principal/schedule?tab=settings',
  },
];

// أنماط مشتركة لكل زر تبويب: الارتفاع والحشو والحدّ السفلي ثابتة بصرف النظر
// عن حالة النشاط، حتى لا يحدث أي انزياح في الارتفاع عند التنقل بين التبويبات.
const TAB_BUTTON_BASE =
  'h-10 rounded-xl px-3 text-xs sm:text-sm font-semibold leading-none transition-colors duration-200 flex items-center justify-center gap-2 border-b-2';
const TAB_BUTTON_ACTIVE = 'bg-[#1C3D74] text-white border-[#1C3D74]';
const TAB_BUTTON_INACTIVE =
  'bg-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50 border-transparent';

function tabClasses(isActive, extra = '') {
  return `${TAB_BUTTON_BASE} ${isActive ? TAB_BUTTON_ACTIVE : TAB_BUTTON_INACTIVE} ${extra}`.trim();
}

export default function ScheduleTabNav({ active }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const masterTab = TABS[0];
  const standbyTab = TABS[1];
  const settingsTab = TABS[2];

  const renderTabButton = (tab, { extraClassName = '', srOnlyLabel = false } = {}) => {
    const Icon = tab.icon;
    const isActive = active === tab.id;
    return (
      <button
        key={tab.id}
        type="button"
        role="tab"
        aria-selected={isActive}
        onClick={() => navigate(tab.path)}
        data-testid={`schedule-nav-${tab.id}`}
        className={tabClasses(isActive, extraClassName)}
        aria-label={srOnlyLabel ? t(tab.labelKey) : undefined}
      >
        <Icon className="h-4 w-4 shrink-0" strokeWidth={1.5} aria-hidden="true" />
        {srOnlyLabel ? (
          <span className="sr-only">{t(tab.labelKey)}</span>
        ) : (
          <span className="whitespace-nowrap">{t(tab.labelKey)}</span>
        )}
      </button>
    );
  };

  return (
    <div className="shrink-0" data-testid="schedule-tab-nav-wrapper">
      {/* تخطيط الجوال: تبويبان متساويان + زر ترس مستقل للإعدادات */}
      <div className="flex sm:hidden flex-row items-stretch gap-2" data-testid="schedule-tab-nav-mobile">
        <div
          className="bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 flex flex-row flex-nowrap gap-1 flex-1 min-w-0"
          role="tablist"
          data-testid="schedule-tab-nav"
        >
          {renderTabButton(masterTab, { extraClassName: 'flex-1 min-w-0' })}
          {renderTabButton(standbyTab, { extraClassName: 'flex-1 min-w-0' })}
        </div>
        <div className="bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 flex items-stretch ms-0">
          {renderTabButton(settingsTab, {
            extraClassName: 'aspect-square w-10 px-0',
            srOnlyLabel: true,
          })}
        </div>
      </div>

      {/* تخطيط الشاشات الأكبر: صف التبويبات الثلاثية الأصلي */}
      <div
        className="hidden sm:flex bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 flex-row flex-nowrap gap-1"
        role="tablist"
        data-testid="schedule-tab-nav-desktop"
      >
        {TABS.map((tab) => renderTabButton(tab, { extraClassName: 'flex-1 min-w-0' }))}
      </div>
    </div>
  );
}
