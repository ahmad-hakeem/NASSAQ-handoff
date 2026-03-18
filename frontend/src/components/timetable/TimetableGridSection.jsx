import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Card, CardContent } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip';
import {
  Coffee, Moon, User, AlertTriangle,
  Lock, Sparkles, Filter, Calendar, BookOpen, GripVertical, ArrowLeftRight
} from 'lucide-react';
import {
  ViewModes, getSubjectColor, NEUTRAL_COLOR, WEEKDAYS
} from './types';

const DAY_COLORS = [
  { header: 'from-[#0F2C59] to-[#1a3d70]', light: 'bg-[#0F2C59]/5' },
  { header: 'from-[#143861] to-[#1B5A7A]', light: 'bg-[#1B5A7A]/5' },
  { header: 'from-[#186E8A] to-[#1B93A4]', light: 'bg-[#1B93A4]/5' },
  { header: 'from-[#1B93A4] to-[#4BA9B8]', light: 'bg-[#4BA9B8]/5' },
  { header: 'from-[#5B3E96] to-[#7C3AED]', light: 'bg-[#7C3AED]/5' },
  { header: 'from-[#0F2C59] to-[#1B93A4]', light: 'bg-[#1B93A4]/5' },
  { header: 'from-[#3B3565] to-[#5B3E96]', light: 'bg-[#5B3E96]/5' },
];

const TimetableCell = ({ session, showClassName, onClick, showColorCoding = true, isDraggable = false, onDragStart, draggedSessionId }) => {
  const [justLanded, setJustLanded] = useState(false);

  useEffect(() => {
    if (session?._justMoved) {
      setJustLanded(true);
      const timer = setTimeout(() => setJustLanded(false), 800);
      return () => clearTimeout(timer);
    }
  }, [session?.id, session?.day_of_week, session?.day, session?.period_number, session?._justMoved]);

  if (!session) {
    return (
      <div className="rounded-lg bg-gray-50/60 border border-dashed border-gray-200 h-full min-h-[68px] flex items-center justify-center group hover:bg-gray-100/50 transition-colors">
        <span className="text-gray-300 text-xs">—</span>
      </div>
    );
  }

  const subjectName = session.subject_name;
  const teacherName = session.teacher_name;
  const className = session.class_name;
  const roomName = session.room_name;
  const isLocked = session.is_locked || session.status === 'locked';
  const isAiGenerated = session.is_ai_generated || session.source === 'ai';
  const hasWarning = session.has_warning || (session.warnings && session.warnings.length > 0);
  const isDragging = draggedSessionId === session.id;

  const colors = showColorCoding ? getSubjectColor(subjectName) : NEUTRAL_COLOR;

  const handleDragStart = (e) => {
    if (!isDraggable || isLocked) return;
    const dragData = JSON.stringify({
      id: session.id,
      day: session.day_of_week || session.day,
      period: session.period_number,
      subject_name: subjectName,
      teacher_name: teacherName,
      class_name: className
    });
    e.dataTransfer.setData('application/nassaq-session', dragData);
    e.dataTransfer.setData('text/plain', dragData);
    e.dataTransfer.effectAllowed = 'move';
    if (onDragStart) onDragStart(session.id);
  };

  const cellContent = (
    <div
      draggable={isDraggable && !isLocked}
      onDragStart={handleDragStart}
      onClick={() => onClick && onClick(session)}
      className={`p-2.5 rounded-lg ${colors.bg} border ${colors.border} cursor-pointer
        hover:shadow-md hover:scale-[1.01] active:scale-[0.99] transition-all duration-200 h-full min-h-[68px]
        shadow-sm relative flex flex-col justify-center
        ${isDraggable && !isLocked ? 'cursor-grab active:cursor-grabbing' : ''}
        ${isDragging ? 'opacity-40 scale-95 ring-2 ring-violet-400 ring-dashed' : ''}
        ${justLanded ? 'nassaq-cell-land' : ''}`}
    >
      <div className={`absolute top-0 start-0 w-1 h-full rounded-s-lg ${colors.accent}`} />

      {isDraggable && !isLocked && (
        <div className="absolute top-1 end-1 opacity-60">
          <GripVertical className="h-3 w-3 text-gray-400" />
        </div>
      )}

      {(isLocked || isAiGenerated || hasWarning) && (
        <div className="absolute top-1.5 left-1.5 flex gap-0.5">
          {isLocked && <Lock className="h-2.5 w-2.5 text-gray-400" />}
          {isAiGenerated && <Sparkles className="h-2.5 w-2.5 text-violet-400" />}
          {hasWarning && <AlertTriangle className="h-2.5 w-2.5 text-amber-400" />}
        </div>
      )}
      <p className={`text-[11px] font-bold ${colors.text} leading-tight mb-1 line-clamp-2 ps-2`}>{subjectName}</p>
      <div className="flex items-center gap-1">
        <User className="h-2.5 w-2.5 text-gray-400 flex-shrink-0" />
        <p className="text-[9px] text-gray-500 leading-tight line-clamp-1">{teacherName}</p>
      </div>
      {showClassName && className && (
        <p className="text-[8px] text-gray-400 leading-tight mt-0.5 line-clamp-1">{className}</p>
      )}
    </div>
  );

  if (isDraggable && !isLocked) {
    return cellContent;
  }

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          {cellContent}
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[220px] p-3" dir="rtl">
          <div className="text-xs space-y-1.5">
            <p className="font-bold text-sm">{subjectName}</p>
            <p className="text-muted-foreground">المعلم: {teacherName}</p>
            {className && <p className="text-muted-foreground">الفصل: {className}</p>}
            {roomName && <p className="text-muted-foreground">القاعة: {roomName}</p>}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

const TimetableEmptyGridState = ({ reason, onGenerate, onClearFilters }) => {
  const configs = {
    no_version: {
      icon: <Calendar className="h-16 w-16 text-gray-200" />,
      title: 'لا يوجد جدول بعد',
      desc: 'قم بتوليد الجدول المدرسي باستخدام الذكاء الاصطناعي',
      action: onGenerate && (
        <button onClick={onGenerate} className="mt-4 px-6 py-2.5 bg-gradient-to-r from-[#0F2C59] to-[#1B93A4] text-white rounded-xl hover:opacity-90 transition-all shadow-lg hover:shadow-xl text-sm font-medium">
          توليد الجدول
        </button>
      )
    },
    no_filter_selection: {
      icon: <Filter className="h-16 w-16 text-gray-200" />,
      title: 'اختر فلتر لعرض الجدول',
      desc: 'اختر فصلاً أو معلماً أو مادة من القائمة أعلاه لعرض الجدول الأسبوعي',
      action: null
    },
    no_matching_results: {
      icon: <BookOpen className="h-16 w-16 text-gray-200" />,
      title: 'لا توجد حصص لهذا الاختيار',
      desc: 'جرب اختيار فصل أو معلم آخر',
      action: onClearFilters && (
        <button onClick={onClearFilters} className="mt-4 px-5 py-2 border border-gray-300 rounded-xl hover:bg-gray-50 transition-colors text-sm">
          إعادة ضبط الفلتر
        </button>
      )
    }
  };
  const c = configs[reason] || configs.no_version;
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {c.icon}
      <h3 className="text-lg font-bold mt-4 mb-1 text-gray-700">{c.title}</h3>
      <p className="text-gray-400 text-sm max-w-md">{c.desc}</p>
      {c.action}
    </div>
  );
};

const TimetableGridSkeleton = () => (
  <div className="overflow-x-auto">
    <div className="grid grid-cols-6 gap-3 min-w-[900px]">
      <Skeleton className="h-12 rounded-xl" />
      {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-12 rounded-xl" />)}
      {Array.from({length: 42}).map((_, i) => <Skeleton key={i} className="h-[68px] rounded-lg" />)}
    </div>
  </div>
);

const TimetableGridSection = ({
  loading = false,
  hasData = false,
  activeViewMode = ViewModes.CLASS,
  workingDays = [],
  timeSlots = [],
  sessions = [],
  selectedFilter = null,
  filterType = 'class',
  showBreaks = true,
  showPrayer = true,
  showWarnings = true,
  showColorCoding = true,
  conflictCells = [],
  onSessionClick,
  onGenerate,
  onRegenerate,
  onClearFilters,
  enableDragDrop = false,
  onSessionSwap,
  onSessionMove,
  timetableStatus
}) => {
  const [draggedSessionId, setDraggedSessionId] = useState(null);
  const [dropTargetKey, setDropTargetKey] = useState(null);
  const dragCounterRef = useRef({});

  const isDraftMode = enableDragDrop && timetableStatus !== 'published';

  const days = workingDays.length > 0
    ? workingDays
    : WEEKDAYS.filter(d => ['sunday','monday','tuesday','wednesday','thursday'].includes(d.key));

  const getSessionsForCell = (dayKey, slotId, slotNumber, periodNumber) => {
    const sn = slotNumber != null ? Number(slotNumber) : null;
    const pn = periodNumber != null ? Number(periodNumber) : null;
    return sessions.filter(s => {
      const dayMatch = s.day_of_week === dayKey || s.day === dayKey;
      const sPeriod = s.period_number != null ? Number(s.period_number) : null;
      const slotMatch =
        s.time_slot_id === slotId ||
        (pn != null && sPeriod != null && sPeriod === pn) ||
        (pn == null && sPeriod != null && sn != null && sPeriod === sn);

      let filterMatch = true;
      if (selectedFilter && filterType === 'class') filterMatch = s.class_id === selectedFilter;
      else if (selectedFilter && filterType === 'teacher') filterMatch = s.teacher_id === selectedFilter;
      return dayMatch && slotMatch && filterMatch;
    });
  };

  const isBreakSlot = (slot) => slot.is_break || slot.type === 'break';
  const isPrayerSlot = (slot) => slot.is_prayer || slot.type === 'prayer';

  const handleDragStart = useCallback((sessionId) => {
    setDraggedSessionId(sessionId);
  }, []);

  const handleDragOver = useCallback((e, cellKey) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (cellKey) setDropTargetKey(cellKey);
  }, []);

  const handleDragEnter = useCallback((e, cellKey) => {
    e.preventDefault();
    dragCounterRef.current[cellKey] = (dragCounterRef.current[cellKey] || 0) + 1;
    setDropTargetKey(cellKey);
  }, []);

  const handleDragLeave = useCallback((e, cellKey) => {
    dragCounterRef.current[cellKey] = (dragCounterRef.current[cellKey] || 0) - 1;
    if (dragCounterRef.current[cellKey] <= 0) {
      dragCounterRef.current[cellKey] = 0;
      setDropTargetKey(prev => prev === cellKey ? null : prev);
    }
  }, []);

  const handleDrop = useCallback((e, dayKey, slotNumber, cellSessions) => {
    e.preventDefault();
    e.stopPropagation();
    setDropTargetKey(null);
    dragCounterRef.current = {};

    try {
      const raw = e.dataTransfer.getData('application/nassaq-session') || e.dataTransfer.getData('text/plain');
      if (!raw) { setDraggedSessionId(null); return; }
      const dragData = JSON.parse(raw);
      const draggedId = dragData.id;
      if (!draggedId) { setDraggedSessionId(null); return; }

      if (cellSessions.length > 0) {
        const targetSession = cellSessions[0];
        if (targetSession.id !== draggedId && onSessionSwap) {
          onSessionSwap(draggedId, targetSession.id);
        }
      } else {
        if (onSessionMove) {
          onSessionMove(draggedId, dayKey, slotNumber);
        }
      }
    } catch (err) {
      console.error('Drop error:', err);
    }

    setDraggedSessionId(null);
  }, [onSessionSwap, onSessionMove]);

  const handleDragEnd = useCallback(() => {
    setDraggedSessionId(null);
    setDropTargetKey(null);
    dragCounterRef.current = {};
  }, []);

  if (loading) {
    return (
      <Card className="border border-gray-200/80 shadow-sm rounded-2xl overflow-hidden">
        <CardContent className="p-5">
          <TimetableGridSkeleton />
        </CardContent>
      </Card>
    );
  }

  if (!hasData || timeSlots.length === 0) {
    return (
      <Card className="border-2 border-dashed border-gray-200 rounded-2xl">
        <CardContent>
          <TimetableEmptyGridState
            reason={timeSlots.length === 0 ? 'no_version' : 'no_filter_selection'}
            onGenerate={onGenerate}
            onClearFilters={onClearFilters}
          />
        </CardContent>
      </Card>
    );
  }

  const visibleSlots = timeSlots.filter(slot => {
    if (!showBreaks && isBreakSlot(slot)) return false;
    if (!showPrayer && isPrayerSlot(slot)) return false;
    return true;
  });

  const filteredSessions = (() => {
    if (filterType === 'all') return sessions;
    if (!selectedFilter) return sessions;
    if (filterType === 'class') return sessions.filter(s => s.class_id === selectedFilter);
    if (filterType === 'teacher') return sessions.filter(s => s.teacher_id === selectedFilter);
    return sessions;
  })();

  if (selectedFilter && filteredSessions.length === 0 && sessions.length === 0 && filterType !== 'all') {
    return (
      <Card className="border-2 border-dashed border-gray-200 rounded-2xl">
        <CardContent>
          <TimetableEmptyGridState reason="no_matching_results" onClearFilters={onClearFilters} />
        </CardContent>
      </Card>
    );
  }

  const showClassName = filterType === 'teacher' || filterType === 'subject' || filterType === 'day' || filterType === 'all';

  let periodCounter = 0;

  return (
    <Card className="border border-gray-200/60 shadow-sm rounded-2xl overflow-hidden">
      {isDraftMode && (
        <div className="bg-gradient-to-l from-violet-50 to-purple-50 border-b border-violet-100 px-4 py-2 flex items-center gap-2">
          <ArrowLeftRight className="h-4 w-4 text-violet-500" />
          <span className="text-xs font-tajawal text-violet-700 font-medium">يمكنك سحب وإفلات الحصص لتبديلها أو نقلها إلى خانة فارغة</span>
        </div>
      )}
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <div
            className="min-w-[850px]"
            onDragEnd={handleDragEnd}
            style={{
              display: 'grid',
              gridTemplateColumns: `110px repeat(${days.length}, 1fr)`,
              gap: '0',
            }}
          >
            <div className="bg-gradient-to-bl from-[#0F2C59] to-[#1a3d70] p-3 flex items-center justify-center">
              <span className="text-[11px] font-semibold text-white/80 tracking-wide">الحصة / اليوم</span>
            </div>
            {days.map((day, i) => {
              const dc = DAY_COLORS[i % DAY_COLORS.length];
              return (
                <div key={day.key} className={`bg-gradient-to-l ${dc.header} p-3 text-center`}>
                  <span className="text-sm font-bold text-white tracking-wide">{day.ar || day.label}</span>
                </div>
              );
            })}

            {visibleSlots.map((slot, idx) => {
              const isBreak = isBreakSlot(slot);
              const isPrayer = isPrayerSlot(slot);
              const isSpecial = isBreak || isPrayer;
              const rowBg = idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/40';

              if (!isSpecial) periodCounter++;

              if (isSpecial) {
                return (
                  <div
                    key={slot.id || `special-${idx}`}
                    className={`border-y ${
                      isBreak
                        ? 'bg-gradient-to-l from-amber-50/80 via-orange-50/60 to-amber-50/40 border-amber-100'
                        : 'bg-gradient-to-l from-emerald-50/80 via-teal-50/60 to-emerald-50/40 border-emerald-100'
                    }`}
                    style={{ gridColumn: `1 / -1` }}
                  >
                    <div className="flex items-center justify-center gap-3 py-2.5 px-4">
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                        isBreak ? 'bg-amber-100/80' : 'bg-emerald-100/80'
                      }`}>
                        {isBreak
                          ? <Coffee className="h-3.5 w-3.5 text-amber-600" />
                          : <Moon className="h-3.5 w-3.5 text-emerald-600" />
                        }
                      </div>
                      <div className="text-center">
                        <p className={`text-xs font-semibold ${isBreak ? 'text-amber-700' : 'text-emerald-700'}`}>
                          {slot.name_ar || (isPrayer ? 'صلاة' : 'استراحة')}
                        </p>
                        <p className={`text-[10px] ${isBreak ? 'text-amber-400' : 'text-emerald-400'}`}>
                          {slot.start_time} - {slot.end_time}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              }

              const currentPeriod = periodCounter;

              return (
                <React.Fragment key={slot.id || idx}>
                  <div className={`p-2 text-center flex flex-col justify-center border-b border-gray-100/80 ${rowBg}`}
                    style={{
                      background: idx % 2 === 0
                        ? 'linear-gradient(135deg, rgba(15,44,89,0.04) 0%, rgba(27,147,164,0.03) 100%)'
                        : 'linear-gradient(135deg, rgba(15,44,89,0.07) 0%, rgba(27,147,164,0.05) 100%)',
                      borderInlineEnd: '3px solid rgba(27,147,164,0.25)',
                    }}
                  >
                    <p className="text-[11px] font-bold text-[#0F2C59]">
                      الحصة {currentPeriod}
                    </p>
                    <p className="text-[9px] text-gray-400 mt-0.5 font-medium">
                      {slot.start_time} - {slot.end_time}
                    </p>
                  </div>

                  {days.map(day => {
                    const cellSessions = getSessionsForCell(day.key, slot.id, slot.slot_number, slot.period_number);
                    const slotNum = Number(slot.period_number || slot.slot_number || currentPeriod);
                    const cellKey = `${day.key}-${slotNum}`;
                    const isConflict = conflictCells.some(
                      cc => cc.day === day.key && cc.period === slotNum
                    );
                    const isDropTarget = dropTargetKey === cellKey && draggedSessionId;
                    const hasDraggedSession = cellSessions.some(s => s.id === draggedSessionId);

                    const isSwapTarget = isDropTarget && !hasDraggedSession && cellSessions.length > 0;
                    const isMoveTarget = isDropTarget && !hasDraggedSession && cellSessions.length === 0;

                    return (
                      <div
                        key={`${day.key}-${slot.id || idx}`}
                        id={`cell-${day.key}-${slotNum}`}
                        className={`p-1.5 border-b border-gray-100/80 ${rowBg} group transition-all duration-200 relative ${
                          isConflict
                            ? 'bg-red-50 dark:bg-red-950/30 ring-2 ring-red-400 ring-inset rounded-sm'
                            : ''
                        } ${isMoveTarget
                            ? 'bg-violet-50 ring-2 ring-violet-400 ring-dashed rounded-lg scale-[1.02] shadow-md'
                            : ''
                        } ${isSwapTarget
                            ? 'bg-amber-50 ring-2 ring-amber-400 rounded-lg scale-[1.02] shadow-md'
                            : ''
                        }`}
                        onDragOver={isDraftMode ? (e) => handleDragOver(e, cellKey) : undefined}
                        onDragEnter={isDraftMode ? (e) => handleDragEnter(e, cellKey) : undefined}
                        onDragLeave={isDraftMode ? (e) => handleDragLeave(e, cellKey) : undefined}
                        onDrop={isDraftMode ? (e) => handleDrop(e, day.key, slotNum, cellSessions) : undefined}
                      >
                        {isConflict && (
                          <div className="absolute top-0.5 end-0.5 z-10">
                            <AlertTriangle className="h-3.5 w-3.5 text-red-500 animate-pulse" />
                          </div>
                        )}
                        {isMoveTarget && (
                          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
                            <div className="text-violet-400 text-[10px] font-bold font-tajawal flex items-center gap-1">
                              <ArrowLeftRight className="h-3 w-3" />
                              أفلت هنا
                            </div>
                          </div>
                        )}
                        {isSwapTarget && (
                          <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
                            <div className="bg-amber-500/90 text-white text-[10px] font-bold font-tajawal px-2 py-0.5 rounded-full flex items-center gap-1 shadow-lg">
                              <ArrowLeftRight className="h-3 w-3" />
                              تبديل
                            </div>
                          </div>
                        )}
                        {cellSessions.length === 0 ? (
                          <TimetableCell session={null} showClassName={showClassName} onClick={onSessionClick} showColorCoding={showColorCoding} />
                        ) : cellSessions.length === 1 ? (
                          <TimetableCell
                            session={cellSessions[0]}
                            showClassName={showClassName}
                            onClick={onSessionClick}
                            showColorCoding={showColorCoding}
                            isDraggable={isDraftMode}
                            onDragStart={handleDragStart}
                            draggedSessionId={draggedSessionId}
                          />
                        ) : (
                          <div className="flex flex-col gap-1 h-full">
                            {cellSessions.slice(0, 3).map((s, si) => (
                              <TimetableCell
                                key={si}
                                session={s}
                                showClassName={true}
                                onClick={onSessionClick}
                                showColorCoding={showColorCoding}
                                isDraggable={isDraftMode}
                                onDragStart={handleDragStart}
                                draggedSessionId={draggedSessionId}
                              />
                            ))}
                            {cellSessions.length > 3 && (
                              <span className="text-[9px] text-gray-400 text-center">+{cellSessions.length - 3} أخرى</span>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export { TimetableCell, TimetableEmptyGridState, TimetableGridSkeleton };
export default TimetableGridSection;
