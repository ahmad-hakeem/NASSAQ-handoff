import React, { useState, useEffect } from 'react';
import { BookOpen, User, Clock, Timer } from 'lucide-react';

const CurrentClassCard = ({ currentClass, studentName }) => {
  const [countdown, setCountdown] = useState('');

  useEffect(() => {
    if (!currentClass?.end_time) return;

    const updateCountdown = () => {
      const now = new Date();
      const [h, m] = currentClass.end_time.split(':').map(Number);
      const endDate = new Date();
      endDate.setHours(h, m, 0, 0);

      const diff = endDate - now;
      if (diff <= 0) {
        setCountdown('انتهت');
        return;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setCountdown(`${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`);
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [currentClass?.end_time]);

  if (!currentClass) {
    return (
      <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-2xl p-5 border border-gray-200">
        <p className="text-gray-500 text-center text-sm">
          اليوم الدراسي انتهى أو لم يبدأ بعد
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-br from-indigo-600 to-purple-700 rounded-2xl p-5 text-white shadow-lg shadow-indigo-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium opacity-90">أين {studentName} الآن؟</h3>
        <div className="flex items-center gap-1 bg-white/20 rounded-full px-3 py-1">
          <Timer className="w-3.5 h-3.5" />
          <span className="text-sm font-bold tabular-nums">{countdown}</span>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <p className="text-lg font-bold">{currentClass.subject}</p>
            <div className="flex items-center gap-2 text-sm opacity-80">
              <User className="w-3.5 h-3.5" />
              <span>{currentClass.teacher}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-sm opacity-80">
          <Clock className="w-3.5 h-3.5" />
          <span>{currentClass.start_time} - {currentClass.end_time}</span>
        </div>
      </div>
    </div>
  );
};

export default CurrentClassCard;
