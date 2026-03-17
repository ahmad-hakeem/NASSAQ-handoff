import { useNassaqAlert } from '../ui/NassaqAlertDialog';
/**
 * TeacherScheduleGrid Component
 * شبكة جدول المعلمين - Teacher-based Schedule Grid
 * 
 * This component displays the schedule in a grid format where:
 * - Rows = Teachers (الصفوف = المعلمون)
 * - Columns = Days of the week (الأعمدة الرئيسية = أيام الدراسة)
 * - Sub-columns = 7 periods per day (الأعمدة الفرعية = 7 حصص)
 * 
 * Features:
 * - Multi-level header (Days → Periods)
 * - Drag & Drop support
 * - Conflict detection
 * - Session cards with subject and class info
 * - Teacher workload visualization
 * - Sticky first column for teacher names
 * - Horizontal and vertical scrolling support
 */

import { useState, useCallback, useMemo } from 'react';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../../components/ui/tooltip';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { 
  GripVertical, 
  Clock, 
  AlertTriangle, 
  Lock,
  User,
  BookOpen,
  MapPin,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  Info,
  Coffee
} from 'lucide-react';
import { toast } from 'sonner';

// Subject colors mapping
const SUBJECT_COLORS = {
  'اللغة العربية': { bg: 'bg-emerald-100 dark:bg-emerald-900/30', border: 'border-emerald-300', text: 'text-emerald-700 dark:text-emerald-400' },
  'الرياضيات': { bg: 'bg-blue-100 dark:bg-blue-900/30', border: 'border-blue-300', text: 'text-blue-700 dark:text-blue-400' },
  'العلوم': { bg: 'bg-purple-100 dark:bg-purple-900/30', border: 'border-purple-300', text: 'text-purple-700 dark:text-purple-400' },
  'اللغة الإنجليزية': { bg: 'bg-red-100 dark:bg-red-900/30', border: 'border-red-300', text: 'text-red-700 dark:text-red-400' },
  'الدراسات الإسلامية': { bg: 'bg-amber-100 dark:bg-amber-900/30', border: 'border-amber-300', text: 'text-amber-700 dark:text-amber-400' },
  'الدراسات الاجتماعية': { bg: 'bg-orange-100 dark:bg-orange-900/30', border: 'border-orange-300', text: 'text-orange-700 dark:text-orange-400' },
  'الحاسب الآلي': { bg: 'bg-cyan-100 dark:bg-cyan-900/30', border: 'border-cyan-300', text: 'text-cyan-700 dark:text-cyan-400' },
  'المهارات الرقمية': { bg: 'bg-teal-100 dark:bg-teal-900/30', border: 'border-teal-300', text: 'text-teal-700 dark:text-teal-400' },
  'التربية الفنية': { bg: 'bg-pink-100 dark:bg-pink-900/30', border: 'border-pink-300', text: 'text-pink-700 dark:text-pink-400' },
  'التربية البدنية': { bg: 'bg-indigo-100 dark:bg-indigo-900/30', border: 'border-indigo-300', text: 'text-indigo-700 dark:text-indigo-400' },
};

const DEFAULT_COLOR = { bg: 'bg-gray-100 dark:bg-gray-800', border: 'border-gray-300', text: 'text-gray-700 dark:text-gray-400' };

// Default days of week (should come from school settings in production)
const DEFAULT_DAYS = [
  { key: 'sunday', ar: 'الأحد', en: 'Sunday' },
  { key: 'monday', ar: 'الاثنين', en: 'Monday' },
  { key: 'tuesday', ar: 'الثلاثاء', en: 'Tuesday' },
  { key: 'wednesday', ar: 'الأربعاء', en: 'Wednesday' },
  { key: 'thursday', ar: 'الخميس', en: 'Thursday' },
];

// Session Card Component - Compact version for grid cells
const SessionCard = ({ session, isRTL, onDragStart, onDragEnd, onSessionClick, conflicts, isLocked }) => {
  const colors = SUBJECT_COLORS[session?.subject_name] || DEFAULT_COLOR;
  const hasConflict = conflicts?.some(c => c.session_id === session?.id);
  
  // Get first letters of subject for very compact display
  const subjectInitials = session?.subject_name?.split(' ').map(w => w[0]).join('').slice(0, 2) || '?';
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            draggable={!isLocked}
            onDragStart={(e) => onDragStart?.(e, session)}
            onDragEnd={onDragEnd}
            onClick={() => onSessionClick?.(session)}
            className={`
              relative h-full min-h-[50px] p-1 rounded cursor-pointer transition-all duration-200
              ${colors.bg} ${colors.border} border
              hover:shadow-md hover:z-10
              ${hasConflict ? 'ring-2 ring-red-500 ring-offset-1' : ''}
              ${isLocked ? 'opacity-70' : ''}
            `}
            data-testid={`session-card-${session?.id}`}
          >
            {/* Conflict Icon */}
            {hasConflict && (
              <div className="absolute top-0.5 end-0.5">
                <AlertTriangle className="h-2.5 w-2.5 text-red-500" />
              </div>
            )}
            
            {/* Lock Icon */}
            {isLocked && (
              <div className="absolute top-0.5 start-0.5">
                <Lock className="h-2.5 w-2.5 text-orange-500" />
              </div>
            )}
            
            {/* Content */}
            <div className="flex flex-col h-full justify-center items-center gap-0.5">
              <span className={`text-[9px] font-bold ${colors.text} line-clamp-1 text-center`}>
                {session?.subject_name?.split(' ')[0] || ''}
              </span>
              <span className="text-[8px] text-muted-foreground line-clamp-1">
                {session?.class_name || ''}
              </span>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <div className="space-y-1 text-xs">
            <p className="font-bold">{session?.subject_name}</p>
            <p className="text-muted-foreground">{session?.class_name}</p>
            {session?.room && <p className="flex items-center gap-1"><MapPin className="h-3 w-3" />{session.room}</p>}
            {hasConflict && <p className="text-red-500 flex items-center gap-1"><AlertTriangle className="h-3 w-3" />{isRTL ? 'يوجد تعارض' : 'Conflict detected'}</p>}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

// Empty Slot Component - Drop target
const EmptySlot = ({ day, periodIndex, teacherId, isRTL, onDragOver, onDrop, isDropTarget, isBreak }) => {
  if (isBreak) {
    return (
      <div className="h-full min-h-[50px] bg-amber-50/50 dark:bg-amber-900/10 border border-dashed border-amber-200 dark:border-amber-800 rounded flex items-center justify-center">
        <Coffee className="h-3 w-3 text-amber-400" />
      </div>
    );
  }
  
  return (
    <div
      onDragOver={onDragOver}
      onDrop={(e) => onDrop(e, day, periodIndex + 1, teacherId)}
      className={`
        h-full min-h-[50px] border border-dashed rounded transition-colors
        ${isDropTarget 
          ? 'bg-brand-turquoise/20 border-brand-turquoise' 
          : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'
        }
      `}
      data-testid={`empty-slot-${day}-${periodIndex}-${teacherId}`}
    />
  );
};

// Teacher Row Component
const TeacherRow = ({ 
  teacher, 
  sessions, 
  timeSlots,
  daysToShow,
  isRTL, 
  onDragStart, 
  onDragEnd, 
  onDragOver, 
  onDrop, 
  onSessionClick,
  conflicts,
  lockedSessions,
  dropTarget,
}) => {
  // Calculate teacher stats
  const totalSessions = sessions.length;
  const maxLoad = 35; // Standard teaching load
  const loadPercentage = Math.min((totalSessions / maxLoad) * 100, 100);
  
  // Get session for specific day and period
  const getSession = (dayKey, periodIndex) => {
    return sessions.find(s => 
      (s.day_of_week === dayKey || s.day === dayKey) && 
      (s.slot_number === periodIndex + 1 || s.period_number === periodIndex + 1)
    );
  };

  // Check if slot is a break
  const isBreakSlot = (periodIndex) => {
    return timeSlots[periodIndex]?.is_break || false;
  };

  return (
    <div className="flex border-b border-border/50 hover:bg-muted/10 transition-colors">
      {/* Teacher Info - Sticky Column */}
      <div className="w-52 flex-shrink-0 p-2 border-e border-border sticky start-0 bg-background z-10">
        <div className="flex items-center gap-2">
          <Avatar className="h-8 w-8 flex-shrink-0">
            <AvatarImage src={teacher.avatar_url} alt={teacher.full_name} />
            <AvatarFallback className="bg-brand-navy text-white text-xs">
              {teacher.full_name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium truncate">{teacher.full_name}</p>
            <div className="flex items-center gap-1">
              <span className="text-[10px] text-muted-foreground truncate">{teacher.subject || teacher.specialization}</span>
            </div>
            {/* Workload indicator */}
            <div className="mt-1 flex items-center gap-1">
              <div className="h-1 flex-1 bg-muted rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all ${
                    loadPercentage > 90 ? 'bg-red-500' : 
                    loadPercentage > 70 ? 'bg-amber-500' : 'bg-brand-turquoise'
                  }`}
                  style={{ width: `${loadPercentage}%` }}
                />
              </div>
              <span className="text-[9px] text-muted-foreground">{totalSessions}/{maxLoad}</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Schedule Cells - Grid of Days × Periods */}
      <div className="flex-1 overflow-x-auto">
        <div className="flex min-w-max">
          {daysToShow.map(day => (
            <div 
              key={day.key} 
              className="border-e border-border/30"
              style={{ width: `${timeSlots.length * 60}px` }}
            >
              <div className="flex">
                {timeSlots.map((slot, periodIndex) => {
                  const session = getSession(day.key, periodIndex);
                  const isBreak = isBreakSlot(periodIndex);
                  const isCurrentDropTarget = dropTarget?.day === day.key && dropTarget?.slot === periodIndex + 1;
                  
                  return (
                    <div 
                      key={`${day.key}-${periodIndex}`} 
                      className="w-[60px] p-0.5 border-e border-border/20 last:border-e-0"
                    >
                      {session ? (
                        <SessionCard
                          session={session}
                          isRTL={isRTL}
                          onDragStart={onDragStart}
                          onDragEnd={onDragEnd}
                          onSessionClick={onSessionClick}
                          conflicts={conflicts}
                          isLocked={lockedSessions?.includes(session.id)}
                        />
                      ) : (
                        <EmptySlot
                          day={day.key}
                          periodIndex={periodIndex}
                          teacherId={teacher.id}
                          isRTL={isRTL}
                          onDragOver={onDragOver}
                          onDrop={onDrop}
                          isDropTarget={isCurrentDropTarget}
                          isBreak={isBreak}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Main Component
export const TeacherScheduleGrid = ({
  teachers = [],
  sessions = [],
  timeSlots = [],
  classes = [],
  subjects = [],
  conflicts = [],
  lockedSessions = [],
  isRTL = true,
  displayedDays = null, // Days to display (from school settings or filter)
  onSessionMove,
  onSessionClick,
  onSessionEdit,
}) => {
  const { nassaqWarning } = useNassaqAlert();
  const [draggedSession, setDraggedSession] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);
  
  // Use provided displayedDays or default to DEFAULT_DAYS
  const daysToShow = displayedDays || DEFAULT_DAYS;

  // Generate default time slots if not provided
  const effectiveTimeSlots = useMemo(() => {
    if (timeSlots && timeSlots.length > 0) return timeSlots;
    
    // Default 7 periods
    return [
      { id: 1, name: 'الحصة 1', name_en: 'Period 1', start_time: '07:30', end_time: '08:15', is_break: false },
      { id: 2, name: 'الحصة 2', name_en: 'Period 2', start_time: '08:20', end_time: '09:05', is_break: false },
      { id: 3, name: 'الحصة 3', name_en: 'Period 3', start_time: '09:10', end_time: '09:55', is_break: false },
      { id: 4, name: 'الفسحة', name_en: 'Break', start_time: '09:55', end_time: '10:15', is_break: true },
      { id: 5, name: 'الحصة 4', name_en: 'Period 4', start_time: '10:15', end_time: '11:00', is_break: false },
      { id: 6, name: 'الحصة 5', name_en: 'Period 5', start_time: '11:05', end_time: '11:50', is_break: false },
      { id: 7, name: 'الحصة 6', name_en: 'Period 6', start_time: '11:55', end_time: '12:40', is_break: false },
    ];
  }, [timeSlots]);

  // Handle drag start
  const handleDragStart = useCallback((e, session) => {
    setDraggedSession(session);
    e.dataTransfer.setData('text/plain', JSON.stringify(session));
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  // Handle drag end
  const handleDragEnd = useCallback(() => {
    setDraggedSession(null);
    setDropTarget(null);
  }, []);

  // Handle drag over
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  // Handle drop
  const handleDrop = useCallback((e, day, slot, teacherId) => {
    e.preventDefault();
    
    if (!draggedSession) return;
    
    // Check for conflicts before moving
    const existingSessionInSlot = sessions.find(s => 
      s.teacher_id === teacherId &&
      (s.day_of_week === day || s.day === day) &&
      (s.slot_number === slot || s.period_number === slot) &&
      s.id !== draggedSession.id
    );
    
    if (existingSessionInSlot) {
      nassaqWarning(isRTL 
        ? 'يوجد تعارض! المعلم لديه حصة أخرى في هذا الوقت'
        : 'Conflict! Teacher already has a session at this time'
      );
      return;
    }
    
    // Notify parent of the move
    onSessionMove?.({
      sessionId: draggedSession.id,
      newDay: day,
      newSlot: slot,
      newTeacherId: teacherId,
      oldDay: draggedSession.day_of_week || draggedSession.day,
      oldSlot: draggedSession.slot_number || draggedSession.period_number,
      oldTeacherId: draggedSession.teacher_id,
    });
    
    setDraggedSession(null);
    setDropTarget(null);
  }, [draggedSession, sessions, isRTL, onSessionMove]);

  // Get sessions for a specific teacher
  const getTeacherSessions = (teacherId) => {
    return sessions.filter(s => s.teacher_id === teacherId);
  };

  // Calculate total columns width
  const gridWidth = daysToShow.length * effectiveTimeSlots.length * 60;

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-background" data-testid="teacher-schedule-grid">
      {/* Multi-level Header */}
      <div className="sticky top-0 z-20 bg-background">
        {/* Level 1: Days Header */}
        <div className="flex border-b border-border">
          {/* Teacher Column Header */}
          <div className="w-52 flex-shrink-0 p-3 border-e border-border font-medium text-sm sticky start-0 bg-muted/50 z-30">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-brand-navy" />
              <span>{isRTL ? 'المعلم' : 'Teacher'}</span>
            </div>
            <p className="text-[10px] text-muted-foreground mt-1">
              {isRTL ? `${teachers.length} معلم` : `${teachers.length} teachers`}
            </p>
          </div>
          
          {/* Day Headers */}
          <div className="flex-1 overflow-x-auto">
            <div className="flex min-w-max">
              {daysToShow.map(day => (
                <div 
                  key={day.key}
                  className="border-e border-border bg-brand-navy/5 dark:bg-brand-navy/20"
                  style={{ width: `${effectiveTimeSlots.length * 60}px` }}
                >
                  <div className="p-2 text-center">
                    <p className="font-bold text-sm text-brand-navy dark:text-brand-turquoise">
                      {isRTL ? day.ar : day.en}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {effectiveTimeSlots.filter(s => !s.is_break).length} {isRTL ? 'حصص' : 'periods'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        {/* Level 2: Periods Header */}
        <div className="flex border-b border-border bg-muted/30">
          {/* Empty cell under teacher column */}
          <div className="w-52 flex-shrink-0 p-1 border-e border-border sticky start-0 bg-muted/30 z-10">
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <Clock className="h-3 w-3" />
              {isRTL ? 'الحصص' : 'Periods'}
            </div>
          </div>
          
          {/* Period headers for each day */}
          <div className="flex-1 overflow-x-auto">
            <div className="flex min-w-max">
              {daysToShow.map(day => (
                <div 
                  key={`periods-${day.key}`}
                  className="border-e border-border/30"
                  style={{ width: `${effectiveTimeSlots.length * 60}px` }}
                >
                  <div className="flex">
                    {effectiveTimeSlots.map((slot, idx) => (
                      <div 
                        key={`${day.key}-period-${idx}`}
                        className={`w-[60px] py-1 text-center border-e border-border/20 last:border-e-0 ${
                          slot.is_break ? 'bg-amber-50 dark:bg-amber-900/20' : ''
                        }`}
                      >
                        <p className="text-[9px] font-medium">
                          {slot.is_break 
                            ? (isRTL ? 'فسحة' : 'Break')
                            : (idx + 1)
                          }
                        </p>
                        <p className="text-[8px] text-muted-foreground">
                          {slot.start_time}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      
      {/* Teacher Rows */}
      <div className="max-h-[600px] overflow-y-auto">
        {teachers.length > 0 ? (
          teachers.map(teacher => (
            <TeacherRow
              key={teacher.id}
              teacher={teacher}
              sessions={getTeacherSessions(teacher.id)}
              timeSlots={effectiveTimeSlots}
              daysToShow={daysToShow}
              isRTL={isRTL}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onSessionClick={onSessionClick}
              conflicts={conflicts.filter(c => c.teacher_id === teacher.id)}
              lockedSessions={lockedSessions}
              dropTarget={dropTarget}
            />
          ))
        ) : (
          <div className="p-8 text-center text-muted-foreground">
            <User className="h-12 w-12 mx-auto mb-4 opacity-20" />
            <p>{isRTL ? 'لا يوجد معلمون للعرض' : 'No teachers to display'}</p>
          </div>
        )}
      </div>
      
      {/* Legend */}
      <div className="p-3 border-t border-border bg-muted/20">
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-4 h-4 bg-brand-turquoise/20 border border-brand-turquoise rounded" />
            <span className="text-muted-foreground">{isRTL ? 'حصة نشطة' : 'Active session'}</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-4 border border-dashed border-muted-foreground/40 rounded" />
            <span className="text-muted-foreground">{isRTL ? 'خانة فارغة' : 'Empty slot'}</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-4 bg-amber-50 border border-amber-200 rounded flex items-center justify-center">
              <Coffee className="h-2.5 w-2.5 text-amber-500" />
            </div>
            <span className="text-muted-foreground">{isRTL ? 'فسحة' : 'Break'}</span>
          </div>
          <div className="flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            <span className="text-muted-foreground">{isRTL ? 'تعارض' : 'Conflict'}</span>
          </div>
          <div className="flex items-center gap-1">
            <Lock className="h-3.5 w-3.5 text-orange-500" />
            <span className="text-muted-foreground">{isRTL ? 'مقفل' : 'Locked'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TeacherScheduleGrid;
