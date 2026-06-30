import React, { useState, useEffect } from 'react';
import { BookOpen, User, Clock, Timer, Hash } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const CurrentClassCard = ({ currentClass, studentName, dayStatus }) => {
  const { t } = useTranslation();
  const [countdown, setCountdown] = useState('');
  const [countdownPercent, setCountdownPercent] = useState(0);

  useEffect(() => {
    if (!currentClass?.end_time || !currentClass?.start_time) return;

    const updateCountdown = () => {
      const now = new Date();
      const [eh, em] = currentClass.end_time.split(':').map(Number);
      const [sh, sm] = currentClass.start_time.split(':').map(Number);
      const endDate = new Date();
      endDate.setHours(eh, em, 0, 0);
      const startDate = new Date();
      startDate.setHours(sh, sm, 0, 0);

      const diff = endDate - now;
      const totalDiff = endDate - startDate;

      if (diff <= 0) {
        setCountdown(t('ended'));
        setCountdownPercent(100);
        return;
      }

      const elapsed = now - startDate;
      setCountdownPercent(Math.min(100, Math.max(0, (elapsed / totalDiff) * 100)));

      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setCountdown(`${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [currentClass?.end_time, currentClass?.start_time, t]);

  if (!currentClass) {
    const statusMessageKey = {
      before_school: 'schoolDayNotStartedYet',
      after_school: 'schoolDayEnded',
      break: 'currentlyOnBreak',
      no_schedule: 'noScheduleToday',
      unknown: 'scheduleTimesUnavailable',
    }[dayStatus] || 'schoolDayEndedOrNotStarted';

    return (
      <div className="bg-muted rounded-2xl p-5 border border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-muted-foreground/15 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-muted-foreground" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{t('whereIsStudentNow', { name: studentName })}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{t(statusMessageKey)}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-brand-navy to-brand-purple rounded-2xl overflow-hidden text-white shadow-lg shadow-brand-navy/15">
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium opacity-90 font-cairo">{t('whereIsStudentNow', { name: studentName })}</h3>
          <div className="flex items-center gap-1.5 bg-white/20 backdrop-blur-sm rounded-full px-3 py-1.5">
            <Timer className="w-3.5 h-3.5" />
            <span className="text-sm font-bold tabular-nums tracking-wider">{countdown}</span>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <BookOpen className="w-6 h-6" />
            </div>
            <div className="flex-1">
              <p className="text-lg font-bold">{currentClass.subject}</p>
              <div className="flex items-center gap-3 mt-0.5">
                <div className="flex items-center gap-1.5 text-sm opacity-80">
                  <User className="w-3.5 h-3.5" />
                  <span>{currentClass.teacher}</span>
                </div>
                {currentClass.period && (
                  <div className="flex items-center gap-1 text-sm opacity-70">
                    <Hash className="w-3 h-3" />
                    <span>{t('period')} {currentClass.period}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 text-sm opacity-80">
            <Clock className="w-3.5 h-3.5" />
            <span className="tabular-nums">{currentClass.start_time} — {currentClass.end_time}</span>
          </div>
        </div>
      </div>

      <div className="h-1.5 bg-white/10">
        <div
          className="h-full bg-white/40 rounded-full transition-all duration-1000 ease-linear"
          style={{ width: `${countdownPercent}%` }}
        />
      </div>
    </div>
  );
};

export default CurrentClassCard;
