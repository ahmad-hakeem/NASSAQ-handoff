/**
 * شريط التبويبات الرئيسي لصفحة الجدول الذكي
 * نَسَّق | NASSAQ — Task #114
 *
 * يعرض ثلاثة تبويبات بنفس النمط البصري في كل صفحات الجدول:
 *   1) الجدول الرئيسي (المصفوفة)
 *   2) جدول حصص الانتظار
 *   3) إعدادات الجدول المدرسي
 *
 * كل تبويب يُحدِّث المسار ليبقى التنقل قابلاً للحفظ والمشاركة عبر الـ URL.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, Hourglass, Settings as SettingsIcon } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

// كل التبويبات تبقى ضمن `/school/schedule` ويُعبَّر عنها بمعطى
// `?tab=master|standby|settings` ليكون التبويب النشط قابلاً للحفظ والمشاركة
// عبر الـ URL، ويُسهِّل التنقل البرمجي إليه (مثل بطاقة الجاهزية).
const TABS = [
  {
    id: 'master',
    labelKey: 'masterScheduleTab',
    icon: CalendarDays,
    path: '/school/schedule?tab=master',
  },
  {
    id: 'standby',
    labelKey: 'standbyScheduleTab',
    icon: Hourglass,
    path: '/school/schedule?tab=standby',
  },
  {
    id: 'settings',
    labelKey: 'scheduleSettingsTab',
    icon: SettingsIcon,
    path: '/school/schedule?tab=settings',
  },
];

export default function ScheduleTabNav({ active }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div
      className="bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 flex flex-row flex-nowrap gap-1 shrink-0 overflow-x-auto sm:overflow-visible [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      role="tablist"
      data-testid="schedule-tab-nav"
    >
      {TABS.map((tab) => {
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
            className={`flex-none sm:flex-1 sm:min-w-0 whitespace-nowrap rounded-xl px-3 py-2.5 text-xs sm:text-sm font-semibold transition-all duration-300 flex items-center justify-center gap-2 ${
              isActive
                ? 'bg-[#1C3D74] text-white shadow-md'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="whitespace-nowrap">{t(tab.labelKey)}</span>
          </button>
        );
      })}
    </div>
  );
}
