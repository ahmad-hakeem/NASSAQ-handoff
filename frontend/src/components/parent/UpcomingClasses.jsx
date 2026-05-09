import React, { useState } from 'react';
import { BookOpen, Clock, User, ChevronDown } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

/**
 * UpcomingClasses
 * - Shows the immediate next class by default.
 * - The remaining classes are revealed via a collapsible accordion.
 * - Backwards-compatible: when `collapsible={false}`, renders the full list.
 */
const UpcomingClasses = ({ classes, collapsible = true }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  if (!classes || classes.length === 0) return null;

  const next = classes[0];
  const rest = classes.slice(1);
  const showAll = !collapsible;

  return (
    <div className="bg-gradient-to-br from-white via-white to-brand-navy/[0.025] rounded-2xl shadow-sm border border-brand-navy/12 overflow-hidden">
      <div className="p-4 border-b border-brand-navy/10 flex items-center justify-between bg-brand-navy/[0.02]">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-brand-navy/10 text-brand-navy flex items-center justify-center">
            <Clock className="w-4.5 h-4.5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-800 font-cairo leading-tight">
              {t('nextClass')}
            </h3>
            {rest.length > 0 && (
              <p className="text-[11px] text-gray-400 font-tajawal mt-0.5">
                +{rest.length} {t('remainingClassesToday')}
              </p>
            )}
          </div>
        </div>
        <span className="text-[11px] text-brand-navy font-bold bg-brand-navy/5 border border-brand-navy/10 rounded-full px-2.5 py-1">
          {classes.length} {t('periods')}
        </span>
      </div>

      {/* Featured next class */}
      <div className="p-4">
        <ClassRow cls={next} highlight t={t} />
      </div>

      {/* Collapsible remaining list */}
      {rest.length > 0 && (showAll ? (
        <div className="px-4 pb-4 space-y-2">
          {rest.map((cls, i) => (
            <ClassRow key={i} cls={cls} t={t} />
          ))}
        </div>
      ) : (
        <>
          <button
            type="button"
            onClick={() => setOpen(o => !o)}
            aria-expanded={open}
            data-testid="toggle-remaining-classes"
            className="w-full flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold text-brand-navy bg-brand-navy/[0.03] hover:bg-brand-navy/[0.06] border-t border-gray-100 transition-colors font-cairo"
          >
            <span>{open ? t('hideMoreClasses') : t('showMoreClasses')}</span>
            <ChevronDown
              className={`w-3.5 h-3.5 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
            />
          </button>
          {open && (
            <div className="px-4 pt-3 pb-4 space-y-2 bg-brand-navy/[0.025] border-t border-brand-navy/10 animate-in slide-in-from-top-2 duration-200">
              {rest.map((cls, i) => (
                <ClassRow key={i} cls={cls} t={t} />
              ))}
            </div>
          )}
        </>
      ))}
    </div>
  );
};

const ClassRow = ({ cls, highlight = false, t }) => (
  <div
    className={`flex items-center justify-between py-3 px-3.5 rounded-xl transition-colors group ${
      highlight
        ? 'bg-gradient-to-r from-brand-navy/[0.10] to-brand-turquoise/[0.10] border border-brand-navy/20 shadow-sm shadow-brand-navy/[0.06]'
        : 'bg-white border border-brand-navy/8 hover:border-brand-navy/20 hover:bg-brand-navy/[0.03]'
    }`}
  >
    <div className="flex items-center gap-3 min-w-0">
      <div
        className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
          highlight
            ? 'bg-brand-navy text-white shadow-sm shadow-brand-navy/30'
            : 'bg-brand-navy/15 text-brand-navy group-hover:bg-brand-navy/20'
        }`}
      >
        <BookOpen className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <span className="text-sm font-bold text-gray-800 block truncate font-cairo">
          {cls.subject}
        </span>
        {cls.teacher && cls.teacher !== t('notSpecified') && (
          <span className="flex items-center gap-1 text-[11px] text-gray-500 mt-0.5 font-tajawal">
            <User className="w-3 h-3" />
            <span className="truncate">{cls.teacher}</span>
          </span>
        )}
      </div>
    </div>
    <div className="flex items-center gap-1.5 text-xs text-gray-600 font-tajawal shrink-0 ms-3">
      <Clock className="w-3.5 h-3.5" />
      <span className="tabular-nums">{cls.start_time} — {cls.end_time}</span>
    </div>
  </div>
);

export default UpcomingClasses;
