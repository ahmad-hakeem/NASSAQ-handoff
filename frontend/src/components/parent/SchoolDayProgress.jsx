import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

const SchoolDayProgress = ({ schoolDay }) => {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(interval);
  }, []);

  if (!schoolDay || !schoolDay.is_school_day || !schoolDay.all_sessions?.length) {
    return null;
  }

  const sessions = schoolDay.all_sessions;
  const firstStart = sessions[0]?.start_time || '07:00';
  const lastEnd = sessions[sessions.length - 1]?.end_time || '14:00';

  const timeToMinutes = (t) => {
    if (!t) return 0;
    const [h, m] = t.split(':').map(Number);
    return h * 60 + (m || 0);
  };

  const dayStart = timeToMinutes(firstStart);
  const dayEnd = timeToMinutes(lastEnd);
  const totalDuration = dayEnd - dayStart || 1;

  const currentMinutes = timeToMinutes(schoolDay.server_time || now.toTimeString().slice(0, 5));
  const progress = Math.min(100, Math.max(0, ((currentMinutes - dayStart) / totalDuration) * 100));

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Clock className="w-4 h-4" />
          <span>اليوم الدراسي</span>
        </div>
        <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2 py-1 rounded-full">
          {schoolDay.remaining_periods} حصص متبقية
        </span>
      </div>

      <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
        {sessions.map((session, i) => {
          const start = ((timeToMinutes(session.start_time) - dayStart) / totalDuration) * 100;
          const width = ((timeToMinutes(session.end_time) - timeToMinutes(session.start_time)) / totalDuration) * 100;
          const isCompleted = currentMinutes >= timeToMinutes(session.end_time);
          const isCurrent = currentMinutes >= timeToMinutes(session.start_time) && currentMinutes < timeToMinutes(session.end_time);

          return (
            <div
              key={i}
              className={`absolute top-0 h-full rounded-sm transition-colors ${
                isCompleted ? 'bg-indigo-200' : isCurrent ? 'bg-indigo-500 animate-pulse' : 'bg-gray-200'
              }`}
              style={{ right: `${start}%`, width: `${Math.max(width - 0.5, 0.5)}%` }}
              title={session.subject}
            />
          );
        })}
        <div
          className="absolute top-0 w-0.5 h-full bg-indigo-700 z-10"
          style={{ right: `${progress}%` }}
        />
      </div>

      <div className="flex justify-between mt-2 text-xs text-gray-400">
        <span>{lastEnd}</span>
        <span>{firstStart}</span>
      </div>
    </div>
  );
};

export default SchoolDayProgress;
