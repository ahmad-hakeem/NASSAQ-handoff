import React from 'react';
import { BookOpen, Clock } from 'lucide-react';

const UpcomingClasses = ({ classes }) => {
  if (!classes || classes.length === 0) return null;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">الحصص القادمة</h3>
      <div className="space-y-2">
        {classes.map((cls, i) => (
          <div
            key={i}
            className="flex items-center justify-between py-2.5 px-3 rounded-xl bg-gray-50 hover:bg-indigo-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center">
                <BookOpen className="w-4 h-4" />
              </div>
              <span className="text-sm font-medium text-gray-800">{cls.subject}</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Clock className="w-3.5 h-3.5" />
              <span className="tabular-nums">{cls.start_time} - {cls.end_time}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UpcomingClasses;
