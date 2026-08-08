import React, { useState, useEffect } from 'react';
import { Clock, CheckCircle2 } from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';

const SchoolDayProgress = ({ schoolDay }) => {
  const { t } = useTranslation();
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 15000);
    return () => clearInterval(interval);
  }, []);

  if (!schoolDay || !schoolDay.is_school_day || !schoolDay.all_sessions?.length) {
    return (
      <div className="bg-card rounded-2xl p-4 shadow-sm border border-border">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="w-4 h-4" />
          <span>{t('noScheduleToday')}</span>
        </div>
      </div>
    );
  }

  const sessions = schoolDay.all_sessions;
  const firstStart = sessions[0]?.start_time || '07:00';
  const lastEnd = sessions[sessions.length - 1]?.end_time || '14:00';

  const timeToMinutes = (timeStr) => {
    if (!timeStr) return 0;
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + (m || 0);
  };

  const dayStart = timeToMinutes(firstStart);
  const dayEnd = timeToMinutes(lastEnd);
  const totalDuration = dayEnd - dayStart || 1;

  const currentMinutes = timeToMinutes(schoolDay.server_time || now.toTimeString().slice(0, 5));
  const progress = Math.min(100, Math.max(0, ((currentMinutes - dayStart) / totalDuration) * 100));

  const completedCount = schoolDay.completed_periods || 0;
  const totalPeriods = schoolDay.total_periods || sessions.length;
  const remainingCount = schoolDay.remaining_periods || 0;

  const isBeforeSchool = currentMinutes < dayStart;
  const isAfterSchool = currentMinutes >= dayEnd;

  return (
    <div className="bg-card rounded-2xl p-4 shadow-sm border border-border">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-navy/5 dark:bg-brand-turquoise/15 flex items-center justify-center">
            <Clock className="w-4 h-4 text-brand-navy dark:text-brand-turquoise" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground font-cairo">{t('schoolDay')}</p>
            <p className="text-[10px] text-muted-foreground">{firstStart} — {lastEnd}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isAfterSchool ? (
            <span className="flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 px-2.5 py-1 rounded-full">
              <CheckCircle2 className="w-3 h-3" />
              {t('completed')}
            </span>
          ) : (
            <>
              <span className="text-xs font-medium text-brand-navy dark:text-brand-turquoise bg-brand-navy/5 dark:bg-brand-turquoise/15 px-2.5 py-1 rounded-full">
                {completedCount}/{totalPeriods} {t('periods')}
              </span>
              {remainingCount > 0 && (
                <span className="text-xs text-muted-foreground">
                  ({remainingCount} {t('remaining')})
                </span>
              )}
            </>
          )}
        </div>
      </div>

      <div className="relative h-4 bg-muted rounded-full overflow-hidden">
        {sessions.map((session, i) => {
          const startPos = ((timeToMinutes(session.start_time) - dayStart) / totalDuration) * 100;
          const width = ((timeToMinutes(session.end_time) - timeToMinutes(session.start_time)) / totalDuration) * 100;
          const isCompleted = currentMinutes >= timeToMinutes(session.end_time);
          const isCurrent = currentMinutes >= timeToMinutes(session.start_time) && currentMinutes < timeToMinutes(session.end_time);

          return (
            <div
              key={i}
              className={`absolute top-0 h-full rounded-sm transition-all duration-500 ${
                isCompleted
                  ? 'bg-brand-navy/40 dark:bg-brand-turquoise/40'
                  : isCurrent
                    ? 'bg-brand-navy dark:bg-brand-turquoise'
                    : 'bg-muted-foreground/15'
              }`}
              style={{ right: `${startPos}%`, width: `${Math.max(width - 0.5, 0.5)}%` }}
              title={`${session.subject} (${session.start_time} - ${session.end_time})`}
            >
              {isCurrent && (
                <div className="absolute inset-0 bg-brand-navy/60 animate-pulse rounded-sm opacity-50" />
              )}
            </div>
          );
        })}

        {!isBeforeSchool && !isAfterSchool && (
          <div
            className="absolute top-0 w-0.5 h-full bg-brand-navy-dark z-10 transition-all duration-500"
            style={{ right: `${progress}%` }}
          >
            <div className="absolute -top-1 -right-[3px] w-2 h-2 bg-brand-navy-dark rounded-full" />
          </div>
        )}
      </div>

      <div className="flex justify-between mt-2">
        <div className="flex gap-1">
          {sessions.map((session, i) => {
            const isCompleted = currentMinutes >= timeToMinutes(session.end_time);
            const isCurrent = currentMinutes >= timeToMinutes(session.start_time) && currentMinutes < timeToMinutes(session.end_time);
            return (
              <div
                key={i}
                className={`w-2 h-2 rounded-full transition-colors ${
                  isCompleted
                    ? 'bg-brand-navy/60 dark:bg-brand-turquoise/60'
                    : isCurrent
                      ? 'bg-brand-navy dark:bg-brand-turquoise animate-pulse'
                      : 'bg-muted-foreground/20'
                }`}
                title={`${t('period')} ${i + 1}: ${session.subject}`}
              />
            );
          })}
        </div>
        <div className="flex gap-3 text-[10px] text-muted-foreground">
          <span>{lastEnd}</span>
          <span>{firstStart}</span>
        </div>
      </div>
    </div>
  );
};

export default SchoolDayProgress;
