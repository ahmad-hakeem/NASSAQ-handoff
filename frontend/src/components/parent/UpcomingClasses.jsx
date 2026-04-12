import React from 'react';
import { BookOpen, Clock, User } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const UpcomingClasses = ({ classes }) => {
  const { t } = useTranslation();

  if (!classes || classes.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-800">{t('upcomingClasses')}</h3>
        <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded-full">
          {classes.length} {t('periods')}
        </span>
      </div>
      <div className="space-y-2">
        {classes.map((cls, i) => (
          <div
            key={i}
            className="flex items-center justify-between py-3 px-3.5 rounded-xl bg-gray-50 hover:bg-indigo-50 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center group-hover:bg-indigo-200 transition-colors">
                <BookOpen className="w-4 h-4" />
              </div>
              <div>
                <span className="text-sm font-medium text-gray-800 block">{cls.subject}</span>
                {cls.teacher && cls.teacher !== t('notSpecified') && (
                  <span className="flex items-center gap-1 text-[11px] text-gray-400 mt-0.5">
                    <User className="w-3 h-3" />
                    {cls.teacher}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Clock className="w-3.5 h-3.5" />
              <span className="tabular-nums">{cls.start_time} — {cls.end_time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UpcomingClasses;
