import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import SectionErrorBoundary from '../components/SectionErrorBoundary';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  DndContext,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  useDraggable,
  useDroppable,
} from '@dnd-kit/core';
import {
  Calendar,
  Plus,
  Trash2,
  Loader2,
  Clock,
  Settings,
  UserCheck,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  BookOpen,
  GraduationCap,
  Play,
  User,
  X,
  Phone,
  Mail,
  Award,
  Briefcase,
  Filter,
  Lightbulb,
  Wand2,
  GripVertical,
  Move,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '../components/ui/sheet';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Link } from 'react-router-dom';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';

// Days configuration
const DAYS = [
  { key: 'sunday', ar: 'الأحد', en: 'Sun' },
  { key: 'monday', ar: 'الاثنين', en: 'Mon' },
  { key: 'tuesday', ar: 'الثلاثاء', en: 'Tue' },
  { key: 'wednesday', ar: 'الأربعاء', en: 'Wed' },
  { key: 'thursday', ar: 'الخميس', en: 'Thu' },
];

// Subject colors
const SUBJECT_COLORS = {
  'اللغة العربية': 'bg-emerald-100 dark:bg-emerald-900/30 border-emerald-300 text-emerald-700',
  'الرياضيات': 'bg-blue-100 dark:bg-blue-900/30 border-blue-300 text-blue-700',
  'العلوم': 'bg-purple-100 dark:bg-purple-900/30 border-purple-300 text-purple-700',
  'اللغة الإنجليزية': 'bg-red-100 dark:bg-red-900/30 border-red-300 text-red-700',
  'الدراسات الإسلامية': 'bg-amber-100 dark:bg-amber-900/30 border-amber-300 text-amber-700',
  'default': 'bg-gray-100 dark:bg-gray-800 border-gray-300 text-gray-700',
};

const getSubjectColor = (subjectName) => {
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  return SUBJECT_COLORS[subjectName] || SUBJECT_COLORS.default;
};

// Draggable Session Component
const DraggableSession = ({ session, isRTL, onClick }) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: session.id,
    data: { session },
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    zIndex: isDragging ? 1000 : 1,
    opacity: isDragging ? 0.8 : 1,
    cursor: 'grabbing',
  } : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`p-0.5 rounded border cursor-grab transition-all hover:shadow-md active:cursor-grabbing ${
        getSubjectColor(session.subject_name)
      } ${isDragging ? 'shadow-lg ring-2 ring-brand-turquoise scale-105' : ''}`}
      data-testid={`session-${session.id}`}
    >
      <div className="flex items-start gap-0.5">
        <div 
          {...listeners} 
          {...attributes}
          className="flex-shrink-0 cursor-grab active:cursor-grabbing p-0.5 hover:bg-black/5 rounded"
        >
          <GripVertical className="h-2.5 w-2.5 text-muted-foreground/50" />
        </div>
        <div 
          onClick={(e) => { e.stopPropagation(); onClick(); }}
          className="flex-1 min-w-0"
        >
          <p className="font-medium truncate leading-tight text-[8px]">
            {session.subject_name?.split(' ')[0]?.slice(0, 4)}
          </p>
          <p className="opacity-70 truncate leading-tight text-[8px]">
            {session.class_name?.slice(0, 5)}
          </p>
        </div>
      </div>
    </div>
  );
};

// Droppable Cell Component
const DroppableCell = ({ id, children, isOver }) => {
  const { setNodeRef, isOver: hovering } = useDroppable({ id });

  return (
    <td 
      ref={setNodeRef}
      className={`p-0.5 border-e border-border/20 min-w-[40px] max-w-[50px] align-top transition-colors ${
        hovering ? 'bg-brand-turquoise/20 ring-2 ring-brand-turquoise ring-inset' : ''
      }`}
    >
      {children}
    </td>
  );
};

// Session Overlay for Drag Preview
const SessionDragOverlay = ({ session, isRTL }) => {
  if (!session) return null;
  
  return (
    <div className={`p-2 rounded-lg border-2 shadow-xl ${getSubjectColor(session.subject_name)} min-w-[80px]`}>
      <div className="flex items-center gap-2">
        <Move className="h-4 w-4 text-brand-navy" />
        <div>
          <p className="font-bold text-sm">{session.subject_name}</p>
          <p className="text-xs opacity-70">{session.class_name}</p>
          <p className="text-xs opacity-70">{session.teacher_name}</p>
        </div>
      </div>
    </div>
  );
};

export const SchedulePage = () => {
  const { user, api } = useAuth();
  const { isRTL, isDark } = useTheme();
  
  // State
  const [sessions, setSessions] = useState([]);
  const [timeSlots, setTimeSlots] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [seedingSlots, setSeedingSlots] = useState(false);
  
  // Filters
  const [selectedSchedule, setSelectedSchedule] = useState('');
  const [filterTeacher, setFilterTeacher] = useState('all');
  const [filterClass, setFilterClass] = useState('all');
  const [viewPeriod, setViewPeriod] = useState('weekly');
  const [selectedDay, setSelectedDay] = useState(() => {
    const today = new Date().getDay();
    const dayMap = { 0: 'sunday', 1: 'monday', 2: 'tuesday', 3: 'wednesday', 4: 'thursday' };
    return dayMap[today] || 'sunday';
  });
  
  // Dialogs
  const [createScheduleOpen, setCreateScheduleOpen] = useState(false);
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [conflictsSheetOpen, setConflictsSheetOpen] = useState(false);
  const [sessionDetailOpen, setSessionDetailOpen] = useState(false);
  const [teacherDetailOpen, setTeacherDetailOpen] = useState(false);
  const [generationResultOpen, setGenerationResultOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [generationStats, setGenerationStats] = useState(null);
  const [conflictStats, setConflictStats] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [applyingSuggestion, setApplyingSuggestion] = useState(null);
  const [autoResolving, setAutoResolving] = useState(false);
  
  // New schedule form
  const [newSchedule, setNewSchedule] = useState({
    name: '',
    academic_year: '2026-2027',
    semester: 1,
    effective_from: new Date().toISOString().split('T')[0],
  });

  // Drag and Drop State
  const [activeSession, setActiveSession] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  // DnD Sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  );

  const schoolId = user?.tenant_id;

  // Seed default time slots
  const seedDefaultTimeSlots = async () => {
    if (!schoolId) {
      nassaqError(isRTL ? 'لم يتم تحديد المدرسة' : 'School not identified');
      return;
    }
    
    setSeedingSlots(true);
    try {
      const response = await api.post(`/seed/time-slots/${schoolId}`);
      toast.success(response.data.message || (isRTL ? 'تم إنشاء الفترات الزمنية' : 'Time slots created'));
      fetchData();
    } catch (error) {
      console.error('Seed error:', error);
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل إنشاء الفترات الزمنية' : 'Failed to create time slots'));
    } finally {
      setSeedingSlots(false);
    }
  };

  const fetchData = useCallback(async () => {
    if (!schoolId) return;
    
    setLoading(true);
    try {
      const [schedulesRes, slotsRes, teachersRes, classesRes] = await Promise.all([
        api.get(`/schedules?school_id=${schoolId}`),
        api.get(`/time-slots?school_id=${schoolId}`),
        api.get(`/teachers?school_id=${schoolId}`),
        api.get(`/classes?school_id=${schoolId}`),
      ]);
      
      setSchedules(schedulesRes.data);
      setTimeSlots(slotsRes.data.filter(s => !s.is_break).sort((a, b) => a.slot_number - b.slot_number));
      setTeachers(teachersRes.data);
      setClasses(classesRes.data);
      
      if (schedulesRes.data.length > 0 && !selectedSchedule) {
        const firstSchedule = schedulesRes.data.find(s => s.status !== 'archived') || schedulesRes.data[0];
        setSelectedSchedule(firstSchedule.id);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(isRTL ? 'فشل تحميل البيانات' : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, [schoolId, api, isRTL, selectedSchedule]);

  const fetchSessions = useCallback(async () => {
    if (!selectedSchedule) {
      setSessions([]);
      return;
    }
    
    try {
      const [sessionsRes, conflictsRes, suggestionsRes] = await Promise.all([
        api.get(`/schedule-sessions?schedule_id=${selectedSchedule}`),
        api.get(`/schedules/${selectedSchedule}/conflicts`),
        api.get(`/schedules/${selectedSchedule}/conflicts/suggestions`),
      ]);
      
      setSessions(sessionsRes.data);
      setConflicts(conflictsRes.data.conflicts || []);
      setConflictStats(conflictsRes.data.statistics || null);
      setSuggestions(suggestionsRes.data.suggestions || []);
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    }
  }, [selectedSchedule, api]);

  useEffect(() => {
    if (user) fetchData();
  }, [user, fetchData]);

  useEffect(() => {
    if (schoolId) fetchData();
  }, [schoolId, fetchData]);

  useEffect(() => {
    fetchSessions();
  }, [selectedSchedule, fetchSessions]);

  const handleCreateSchedule = async () => {
    if (!newSchedule.name) {
      nassaqError(isRTL ? 'يرجى إدخال اسم الجدول' : 'Please enter schedule name');
      return;
    }

    try {
      const response = await api.post('/schedules', {
        ...newSchedule,
        school_id: schoolId,
        working_days: DAYS.map(d => d.key),
      });
      toast.success(isRTL ? 'تم إنشاء الجدول بنجاح' : 'Schedule created successfully');
      setCreateScheduleOpen(false);
      setNewSchedule({ name: '', academic_year: '2026-2027', semester: 1, effective_from: new Date().toISOString().split('T')[0] });
      fetchData();
      setSelectedSchedule(response.data.id);
    } catch (error) {
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل إنشاء الجدول' : 'Failed to create schedule'));
    }
  };

  const handleGenerateSchedule = async () => {
    setGenerating(true);
    try {
      let scheduleId = selectedSchedule;
      
      // If no schedule exists, create one automatically
      if (!scheduleId) {
        const createResponse = await api.post('/schedules', {
          name: isRTL ? 'الجدول المدرسي - تلقائي' : 'Auto Schedule',
          academic_year: '2026-2027',
          semester: 1,
          effective_from: new Date().toISOString().split('T')[0],
          school_id: schoolId,
          working_days: DAYS.map(d => d.key),
        });
        scheduleId = createResponse.data.id;
        setSelectedSchedule(scheduleId);
        toast.success(isRTL ? 'تم إنشاء جدول جديد' : 'New schedule created');
      }
      
      const response = await api.post(`/schedules/${scheduleId}/generate?respect_workload=true&balance_daily=true&avoid_consecutive=true`);
      
      // Store generation stats
      setGenerationStats(response.data);
      setGenerateDialogOpen(false);
      setGenerationResultOpen(true);
      
      if (response.data.success) {
        toast.success(isRTL 
          ? `تم إنشاء ${response.data.sessions_created} من ${response.data.sessions_requested} حصة (${response.data.success_rate}%)` 
          : `Created ${response.data.sessions_created} of ${response.data.sessions_requested} sessions (${response.data.success_rate}%)`
        );
      } else {
        nassaqWarning(isRTL 
          ? `تم إنشاء ${response.data.sessions_created} حصة مع ${response.data.unplaced_sessions} حصة غير مجدولة` 
          : `Created ${response.data.sessions_created} sessions with ${response.data.unplaced_sessions} unplaced`
        );
      }
      
      fetchData();
      fetchSessions();
    } catch (error) {
      console.error('Generate schedule error:', error);
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل توليد الجدول' : 'Failed to generate schedule'));
    } finally {
      setGenerating(false);
    }
  };

  const handleDeleteSession = async (sessionId) => {
    try {
      await api.delete(`/schedule-sessions/${sessionId}`);
      toast.success(isRTL ? 'تم حذف الحصة' : 'Session deleted');
      fetchSessions();
      setSessionDetailOpen(false);
    } catch (error) {
      nassaqError(isRTL ? 'فشل حذف الحصة' : 'Failed to delete session');
    }
  };

  // Apply single suggestion
  const handleApplySuggestion = async (suggestion) => {
    setApplyingSuggestion(suggestion.id);
    try {
      const response = await api.post(`/schedules/${selectedSchedule}/conflicts/apply-suggestion`, null, {
        params: {
          session_id: suggestion.session_id,
          target_day: suggestion.target_day,
          target_slot_id: suggestion.target_slot_id
        }
      });
      
      toast.success(response.data.message_ar || response.data.message_en);
      fetchSessions();
    } catch (error) {
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل تطبيق الاقتراح' : 'Failed to apply suggestion'));
    } finally {
      setApplyingSuggestion(null);
    }
  };

  // Auto-resolve all conflicts
  const handleAutoResolveAll = async () => {
    if (!selectedSchedule) return;
    
    setAutoResolving(true);
    try {
      const response = await api.post(`/schedules/${selectedSchedule}/conflicts/auto-resolve`);
      
      if (response.data.success) {
        toast.success(response.data.message_ar || response.data.message_en);
      } else {
        nassaqWarning(response.data.message_ar || response.data.message_en);
      }
      
      fetchSessions();
    } catch (error) {
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل حل التعارضات' : 'Failed to resolve conflicts'));
    } finally {
      setAutoResolving(false);
    }
  };

  const handlePublishSchedule = async () => {
    if (!selectedSchedule) return;
    
    try {
      await api.put(`/schedules/${selectedSchedule}/publish`);
      toast.success(isRTL ? 'تم نشر الجدول' : 'Schedule published');
      fetchData();
    } catch (error) {
      nassaqError(isRTL ? 'فشل نشر الجدول' : 'Failed to publish schedule');
    }
  };

  // Filter sessions
  const filteredSessions = sessions.filter(session => {
    if (filterTeacher !== 'all' && session.teacher_id !== filterTeacher) return false;
    if (filterClass !== 'all' && session.class_id !== filterClass) return false;
    return true;
  });

  // Get displayed days
  const displayedDays = viewPeriod === 'daily' ? DAYS.filter(day => day.key === selectedDay) : DAYS;

  // Get session for specific day and time slot
  const getSessionsForCell = (teacherId, dayKey, slotId) => {
    return filteredSessions.filter(s => 
      s.teacher_id === teacherId && 
      s.day_of_week === dayKey && 
      s.time_slot_id === slotId
    );
  };

  // Format time
  const formatTime = (time) => {
    if (!time) return '';
    const [hours, minutes] = time.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? (isRTL ? 'م' : 'PM') : (isRTL ? 'ص' : 'AM');
    const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
    return `${displayHour}:${minutes} ${ampm}`;
  };

  // Get teacher workload
  const getTeacherWorkload = (teacherId) => {
    return filteredSessions.filter(s => s.teacher_id === teacherId).length;
  };

  const currentSchedule = schedules.find(s => s.id === selectedSchedule);

  // Display teachers based on filter
  const displayTeachers = filterTeacher === 'all' ? teachers : teachers.filter(t => t.id === filterTeacher);

  // Drag and Drop Handlers
  const handleDragStart = (event) => {
    const { active } = event;
    const session = sessions.find(s => s.id === active.id);
    setActiveSession(session);
    setIsDragging(true);
  };

  const handleDragEnd = async (event) => {
    const { active, over } = event;
    setActiveSession(null);
    setIsDragging(false);

    if (!over) return;

    const sessionId = active.id;
    const [targetTeacherId, targetDay, targetSlotId] = over.id.split('__');
    
    const session = sessions.find(s => s.id === sessionId);
    if (!session) return;

    // Check if dropped in the same place
    if (session.teacher_id === targetTeacherId && 
        session.day_of_week === targetDay && 
        session.time_slot_id === targetSlotId) {
      return;
    }

    // Move the session
    try {
      await api.put(`/schedule-sessions/${sessionId}/move`, {
        new_day_of_week: targetDay,
        new_time_slot_id: targetSlotId,
      });

      toast.success(isRTL ? 'تم نقل الحصة بنجاح' : 'Session moved successfully');
      fetchSessions();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || (isRTL ? 'فشل نقل الحصة - قد يوجد تعارض' : 'Failed to move session - conflict may exist');
      nassaqError(errorMsg);
    }
  };

  const handleDragCancel = () => {
    setActiveSession(null);
    setIsDragging(false);
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background overflow-hidden max-w-full" data-testid="schedule-page">
        {/* Sticky Header with Controls */}
        <div className="sticky top-0 z-40 bg-background border-b border-border/50 shadow-sm">
          {/* Page Title */}
          <header className="px-6 py-4 border-b border-border/30">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  {isRTL ? `مرحباً، ${user?.full_name || 'المستخدم'}` : `Welcome, ${user?.full_name || 'User'}`}
                </h1>
                <p className="text-base text-muted-foreground font-tajawal">
                  {isRTL ? 'الجدول المدرسي' : 'School Schedule'}
                </p>
              </div>
              
              <div className="flex items-center gap-2">
                <Link to="/admin/time-slots">
                  <Button variant="outline" size="sm" className="rounded-xl">
                    <Clock className="h-4 w-4 me-2" />
                    {isRTL ? 'الفترات' : 'Slots'}
                  </Button>
                </Link>
                <Link to="/admin/teacher-assignments">
                  <Button variant="outline" size="sm" className="rounded-xl">
                    <UserCheck className="h-4 w-4 me-2" />
                    {isRTL ? 'الإسنادات' : 'Assign'}
                  </Button>
                </Link>
              </div>
            </div>
          </header>

          {/* Filters Bar - Sticky */}
          <div className="px-6 py-3 bg-muted/30">
            <div className="flex flex-wrap gap-3 items-center justify-between">
              {/* Left Side Filters */}
              <div className="flex flex-wrap gap-2 items-center">
                {/* Schedule Select */}
                <Select value={selectedSchedule} onValueChange={setSelectedSchedule}>
                  <SelectTrigger className="w-[180px] h-9 rounded-xl text-sm" data-testid="schedule-select">
                    <Calendar className="h-4 w-4 me-2" />
                    <SelectValue placeholder={isRTL ? 'الجدول' : 'Schedule'} />
                  </SelectTrigger>
                  <SelectContent>
                    {schedules.map(schedule => (
                      <SelectItem key={schedule.id} value={schedule.id}>
                        <div className="flex items-center gap-2">
                          {schedule.name}
                          <Badge variant="secondary" className="text-xs">
                            {schedule.status === 'published' ? (isRTL ? 'منشور' : 'Published') : (isRTL ? 'مسودة' : 'Draft')}
                          </Badge>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Filter by Class */}
                <Select value={filterClass} onValueChange={setFilterClass}>
                  <SelectTrigger className="w-[160px] h-9 rounded-xl text-sm" data-testid="class-filter">
                    <GraduationCap className="h-4 w-4 me-2" />
                    <SelectValue placeholder={isRTL ? 'الفصل' : 'Class'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{isRTL ? 'جميع الفصول' : 'All Classes'}</SelectItem>
                    {classes.map(c => (
                      <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* Filter by Teacher */}
                <Select value={filterTeacher} onValueChange={setFilterTeacher}>
                  <SelectTrigger className="w-[160px] h-9 rounded-xl text-sm" data-testid="teacher-filter">
                    <User className="h-4 w-4 me-2" />
                    <SelectValue placeholder={isRTL ? 'المعلم' : 'Teacher'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{isRTL ? 'جميع المعلمين' : 'All Teachers'}</SelectItem>
                    {teachers.map(t => (
                      <SelectItem key={t.id} value={t.id}>{t.full_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {/* View Period Toggle */}
                <div className="flex rounded-xl border border-border overflow-hidden">
                  <Button
                    variant={viewPeriod === 'weekly' ? 'default' : 'ghost'}
                    size="sm"
                    className={`rounded-none h-9 ${viewPeriod === 'weekly' ? 'bg-brand-turquoise' : ''}`}
                    onClick={() => setViewPeriod('weekly')}
                    data-testid="view-weekly-btn"
                  >
                    {isRTL ? 'أسبوعي' : 'Weekly'}
                  </Button>
                  <Button
                    variant={viewPeriod === 'daily' ? 'default' : 'ghost'}
                    size="sm"
                    className={`rounded-none h-9 ${viewPeriod === 'daily' ? 'bg-brand-turquoise' : ''}`}
                    onClick={() => setViewPeriod('daily')}
                    data-testid="view-daily-btn"
                  >
                    {isRTL ? 'يومي' : 'Daily'}
                  </Button>
                </div>

                {/* Day Selector */}
                {viewPeriod === 'daily' && (
                  <Select value={selectedDay} onValueChange={setSelectedDay}>
                    <SelectTrigger className="w-[120px] h-9 rounded-xl text-sm" data-testid="day-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DAYS.map(day => (
                        <SelectItem key={day.key} value={day.key}>
                          {isRTL ? day.ar : day.en}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              {/* Right Side Actions */}
              <div className="flex gap-2 items-center">
                {/* Conflicts Sheet - moved from after New Schedule */}
                {conflicts.length > 0 && (
                  <Sheet open={conflictsSheetOpen} onOpenChange={setConflictsSheetOpen}>
                    <SheetTrigger asChild>
                      <Button variant="destructive" size="sm" className="rounded-xl h-9 animate-pulse" data-testid="conflicts-btn">
                        <AlertTriangle className="h-4 w-4 me-1" />
                        {conflicts.length} {isRTL ? 'تعارض' : 'conflicts'}
                      </Button>
                    </SheetTrigger>
                    <SheetContent className="w-[500px]">
                      <SheetHeader>
                        <SheetTitle className="font-cairo flex items-center gap-2 text-red-600">
                          <AlertTriangle className="h-5 w-5" />
                          {isRTL ? 'التعارضات المكتشفة' : 'Detected Conflicts'} ({conflicts.length})
                        </SheetTitle>
                        <SheetDescription>
                          {isRTL ? 'يجب حل هذه التعارضات قبل نشر الجدول' : 'These conflicts must be resolved before publishing'}
                        </SheetDescription>
                      </SheetHeader>
                      
                      {/* Conflict Statistics */}
                      {conflictStats && (
                        <div className="mt-4 grid grid-cols-3 gap-2">
                          <div className="p-2 rounded-lg bg-orange-50 dark:bg-orange-900/20 text-center">
                            <p className="text-lg font-bold text-orange-600">{conflictStats.teacher_conflicts || 0}</p>
                            <p className="text-xs text-muted-foreground">{isRTL ? 'تعارض معلم' : 'Teacher'}</p>
                          </div>
                          <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-900/20 text-center">
                            <p className="text-lg font-bold text-purple-600">{conflictStats.class_conflicts || 0}</p>
                            <p className="text-xs text-muted-foreground">{isRTL ? 'تعارض فصل' : 'Class'}</p>
                          </div>
                          <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-center">
                            <p className="text-lg font-bold text-blue-600">{conflictStats.room_conflicts || 0}</p>
                            <p className="text-xs text-muted-foreground">{isRTL ? 'تعارض قاعة' : 'Room'}</p>
                          </div>
                        </div>
                      )}
                      
                      {/* Auto-Resolve Button */}
                      {suggestions.length > 0 && (
                        <div className="mt-4">
                          <Button 
                            onClick={handleAutoResolveAll}
                            disabled={autoResolving}
                            className="w-full bg-green-600 hover:bg-green-700 rounded-xl"
                            data-testid="auto-resolve-btn"
                          >
                            {autoResolving ? (
                              <>
                                <Loader2 className="h-4 w-4 me-2 animate-spin" />
                                {isRTL ? 'جارٍ الحل...' : 'Resolving...'}
                              </>
                            ) : (
                              <>
                                <Wand2 className="h-4 w-4 me-2" />
                                {isRTL ? `حل الكل تلقائياً (${suggestions.length})` : `Auto-Resolve All (${suggestions.length})`}
                              </>
                            )}
                          </Button>
                        </div>
                      )}
                      
                      <div className="mt-4 space-y-3 max-h-[50vh] overflow-y-auto">
                        {conflicts.map((conflict, index) => {
                          // Find suggestion for this conflict
                          const suggestion = suggestions.find(s => 
                            (s.conflict_type === conflict.type) && 
                            (s.teacher_id === conflict.teacher_id || s.class_id === conflict.class_id)
                          );
                          
                          return (
                            <div key={conflict.id || index} className={`p-3 rounded-xl border ${
                              conflict.type === 'teacher_overlap' ? 'border-orange-200 bg-orange-50 dark:bg-orange-900/20' :
                              conflict.type === 'class_overlap' ? 'border-purple-200 bg-purple-50 dark:bg-purple-900/20' :
                              conflict.type === 'room_overlap' ? 'border-blue-200 bg-blue-50 dark:bg-blue-900/20' :
                              'border-red-200 bg-red-50 dark:bg-red-900/20'
                            }`}>
                              <div className="flex items-start gap-3">
                                <div className={`p-2 rounded-lg ${
                                  conflict.type === 'teacher_overlap' ? 'bg-orange-100 text-orange-600' :
                                  conflict.type === 'class_overlap' ? 'bg-purple-100 text-purple-600' :
                                  conflict.type === 'room_overlap' ? 'bg-blue-100 text-blue-600' :
                                  'bg-red-100 text-red-600'
                                }`}>
                                  {conflict.type === 'teacher_overlap' ? (
                                    <UserCheck className="h-4 w-4" />
                                  ) : conflict.type === 'class_overlap' ? (
                                    <GraduationCap className="h-4 w-4" />
                                  ) : conflict.type === 'room_overlap' ? (
                                    <Calendar className="h-4 w-4" />
                                  ) : (
                                    <XCircle className="h-4 w-4" />
                                  )}
                                </div>
                                <div className="flex-1">
                                  <p className="font-medium text-sm">
                                    {conflict.type === 'teacher_overlap' 
                                      ? (isRTL ? `تعارض معلم: ${conflict.teacher_name || ''}` : `Teacher: ${conflict.teacher_name || ''}`)
                                      : conflict.type === 'class_overlap'
                                      ? (isRTL ? `تعارض فصل: ${conflict.class_name || ''}` : `Class: ${conflict.class_name || ''}`)
                                      : conflict.type === 'room_overlap'
                                      ? (isRTL ? `تعارض قاعة: ${conflict.room_name || ''}` : `Room: ${conflict.room_name || ''}`)
                                      : (isRTL ? 'تعارض' : 'Conflict')
                                    }
                                  </p>
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {conflict.description_ar || conflict.message_ar || conflict.message || conflict.description_en}
                                  </p>
                                  <div className="flex gap-2 mt-2">
                                    <Badge variant="secondary" className="text-xs">
                                      {DAYS.find(d => d.key === conflict.day_of_week || d.key === conflict.day)?.[isRTL ? 'ar' : 'en'] || conflict.day_of_week || conflict.day}
                                    </Badge>
                                    {conflict.period && (
                                      <Badge variant="outline" className="text-xs">
                                        {isRTL ? `الحصة ${conflict.period}` : `Period ${conflict.period}`}
                                      </Badge>
                                    )}
                                  </div>
                                  
                                  {/* Suggestion & Apply Button */}
                                  {suggestion && (
                                    <div className="mt-3 p-2 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200">
                                      <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
                                        <Lightbulb className="h-4 w-4" />
                                        <span className="text-xs font-medium">{isRTL ? 'اقتراح:' : 'Suggestion:'}</span>
                                      </div>
                                      <p className="text-xs mt-1 text-green-800 dark:text-green-300">
                                        {suggestion.suggestion_ar || suggestion.suggestion_en}
                                      </p>
                                      <div className="flex items-center justify-between mt-2">
                                        <Badge variant="outline" className="text-xs bg-green-100 text-green-700 border-green-300">
                                          {isRTL ? `ثقة ${suggestion.confidence}%` : `${suggestion.confidence}% confidence`}
                                        </Badge>
                                        <Button
                                          size="sm"
                                          onClick={() => handleApplySuggestion(suggestion)}
                                          disabled={applyingSuggestion === suggestion.id}
                                          className="h-7 px-3 text-xs bg-green-600 hover:bg-green-700 rounded-lg"
                                          data-testid={`apply-suggestion-${suggestion.id}`}
                                        >
                                          {applyingSuggestion === suggestion.id ? (
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                          ) : (
                                            <>
                                              <CheckCircle2 className="h-3 w-3 me-1" />
                                              {isRTL ? 'تطبيق' : 'Apply'}
                                            </>
                                          )}
                                        </Button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </SheetContent>
                  </Sheet>
                )}

                {/* Generate Schedule with AI - Primary Action */}
                <AlertDialog open={generateDialogOpen} onOpenChange={setGenerateDialogOpen}>
                  <Button 
                    size="sm"
                    className="rounded-xl h-9 bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white shadow-lg shadow-purple-500/25"
                    onClick={() => setGenerateDialogOpen(true)}
                    data-testid="generate-schedule-btn"
                  >
                    <Wand2 className="h-4 w-4 me-1" />
                    {isRTL ? 'معالجة الجدول بالذكاء الاصطناعي' : 'AI Schedule Processing'}
                  </Button>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle className="font-cairo flex items-center gap-2">
                        <Wand2 className="h-5 w-5 text-violet-600" />
                        {isRTL ? 'معالجة الجدول بالذكاء الاصطناعي' : 'AI Schedule Processing'}
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        {isRTL 
                          ? 'سيقوم الذكاء الاصطناعي بتحليل إسنادات المعلمين والفصول وإنشاء جدول متوازن يراعي جميع القيود والأولويات.'
                          : 'AI will analyze teacher assignments and classes to create a balanced schedule considering all constraints and priorities.'}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel className="rounded-xl">{isRTL ? 'إلغاء' : 'Cancel'}</AlertDialogCancel>
                      <AlertDialogAction onClick={handleGenerateSchedule} disabled={generating} className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-xl">
                        {generating ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Wand2 className="h-4 w-4 me-2" />}
                        {isRTL ? 'ابدأ المعالجة' : 'Start Processing'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>

                {/* Publish */}
                {currentSchedule && currentSchedule.status !== 'published' && (
                  <Button 
                    size="sm"
                    className="bg-brand-navy rounded-xl h-9"
                    onClick={handlePublishSchedule}
                    disabled={conflicts.length > 0}
                    data-testid="publish-schedule-btn"
                  >
                    <CheckCircle2 className="h-4 w-4 me-1" />
                    {isRTL ? 'نشر' : 'Publish'}
                  </Button>
                )}
              </div>
            </div>

            {/* Status Bar */}
            {currentSchedule && (
              <div className="flex items-center gap-4 mt-3 text-sm">
                <Badge className={`${currentSchedule.status === 'published' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                  {currentSchedule.status === 'published' ? (isRTL ? 'منشور' : 'Published') : (isRTL ? 'مسودة' : 'Draft')}
                </Badge>
                <span className="text-muted-foreground">{filteredSessions.length} {isRTL ? 'حصة' : 'sessions'}</span>
                <span className="text-muted-foreground">{displayTeachers.length} {isRTL ? 'معلم' : 'teachers'}</span>
              </div>
            )}
          </div>
        </div>

        {/* Schedule Grid Content */}
        <div className="p-4 overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : timeSlots.length === 0 ? (
            <Card className="card-nassaq">
              <CardContent className="text-center py-16">
                <Clock className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <h3 className="text-xl font-bold mb-2 text-brand-navy dark:text-brand-turquoise">
                  {isRTL ? 'لم يتم تحديد الفترات الزمنية' : 'Time slots not defined'}
                  <Link to="/principal/settings?tab=timings" className="mr-2 inline-flex items-center gap-1 text-sm font-normal text-brand-turquoise underline hover:no-underline">
                    <Settings className="h-3 w-3" />
                    {isRTL ? 'إعداد التوقيت' : 'Set up timings'}
                  </Link>
                </h3>
                <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                  {isRTL 
                    ? 'يجب إعداد الفترات الزمنية (الحصص) أولاً قبل إنشاء الجدول المدرسي. يمكنك إنشاء الفترات الافتراضية بنقرة واحدة.'
                    : 'Time slots (periods) must be set up before creating a schedule. You can create default slots with one click.'}
                </p>
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                  <Button 
                    className="rounded-xl bg-brand-turquoise hover:bg-brand-turquoise/90"
                    onClick={seedDefaultTimeSlots}
                    disabled={seedingSlots}
                    data-testid="seed-time-slots-btn"
                  >
                    {seedingSlots ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Sparkles className="h-4 w-4 me-2" />}
                    {isRTL ? 'إنشاء الفترات الافتراضية' : 'Create Default Slots'}
                  </Button>
                  <Link to="/school/settings">
                    <Button variant="outline" className="rounded-xl">
                      <Settings className="h-4 w-4 me-2" />
                      {isRTL ? 'إعدادات المدرسة' : 'School Settings'}
                    </Button>
                  </Link>
                </div>
                <div className="mt-6 p-4 bg-muted/50 rounded-xl max-w-lg mx-auto">
                  <h4 className="font-medium mb-2 text-sm">{isRTL ? 'الفترات الافتراضية تشمل:' : 'Default slots include:'}</h4>
                  <ul className="text-sm text-muted-foreground space-y-1 text-start">
                    <li>• {isRTL ? '7 حصص دراسية (45 دقيقة لكل حصة)' : '7 study periods (45 min each)'}</li>
                    <li>• {isRTL ? 'استراحة واحدة (20 دقيقة)' : '1 break (20 min)'}</li>
                    <li>• {isRTL ? 'فترة صلاة (20 دقيقة)' : '1 prayer time (20 min)'}</li>
                    <li>• {isRTL ? 'من 7:00 صباحاً إلى 1:15 ظهراً' : 'From 7:00 AM to 1:15 PM'}</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          ) : (
            <SectionErrorBoundary name="ScheduleGrid" isRTL={isRTL}>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDragCancel={handleDragCancel}
            >
              <Card className="card-nassaq overflow-hidden w-full" data-testid="schedule-grid">
                {/* Drag Hint */}
                {isDragging && (
                  <div className="absolute top-2 left-1/2 -translate-x-1/2 z-50 bg-brand-turquoise text-white px-4 py-2 rounded-full shadow-lg text-sm flex items-center gap-2">
                    <Move className="h-4 w-4" />
                    {isRTL ? 'اسحب وأفلت لنقل الحصة' : 'Drag and drop to move session'}
                  </div>
                )}
                
                <div className="overflow-x-auto max-w-full">
                  <table className="w-full border-collapse">
                    {/* Header */}
                    <thead className="sticky top-0 z-10 bg-background">
                      {/* Days Row */}
                      <tr className="border-b">
                        <th className="sticky start-0 z-20 bg-muted/50 p-2 text-start font-medium border-e min-w-[120px] max-w-[140px]">
                          <div className="flex items-center gap-2">
                            <User className="h-4 w-4 text-brand-navy" />
                            {isRTL ? 'المعلم' : 'Teacher'}
                          </div>
                        </th>
                        {displayedDays.map(day => (
                          <th 
                            key={day.key} 
                            colSpan={timeSlots.length}
                            className="p-3 text-center font-medium bg-brand-navy/5 dark:bg-brand-navy/20 border-b"
                          >
                            <span className="font-bold text-brand-navy dark:text-brand-turquoise">
                              {isRTL ? day.ar : day.en}
                            </span>
                          </th>
                        ))}
                      </tr>
                      {/* Periods Row */}
                      <tr className="border-b bg-muted/30">
                        <th className="sticky start-0 z-20 bg-muted/30 p-2 border-e">
                          <div className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Clock className="h-3 w-3" />
                            {isRTL ? 'الحصص' : 'Periods'}
                          </div>
                        </th>
                        {displayedDays.map(day => (
                          timeSlots.map((slot, idx) => (
                            <th key={`${day.key}-${slot.id}`} className="p-1 text-center border-e border-border/20 min-w-[40px] max-w-[50px]">
                              <div className="text-[9px] font-medium">{idx + 1}</div>
                              <div className="text-[8px] text-muted-foreground">{slot.start_time?.slice(0,5)}</div>
                            </th>
                          ))
                        ))}
                      </tr>
                    </thead>
                    
                    {/* Body */}
                    <tbody>
                      {displayTeachers.map((teacher, teacherIdx) => (
                        <tr key={teacher.id} className={`border-b hover:bg-muted/10 ${teacherIdx % 2 === 0 ? '' : 'bg-muted/5'}`}>
                          {/* Teacher Cell - Sticky & Clickable */}
                          <td className="sticky start-0 z-10 bg-background p-1 border-e min-w-[120px] max-w-[140px]">
                            <div 
                              className="flex items-center gap-2 cursor-pointer hover:bg-muted/50 rounded-lg p-1 transition-colors"
                              onClick={() => {
                                setSelectedTeacher(teacher);
                                setTeacherDetailOpen(true);
                              }}
                              data-testid={`teacher-cell-${teacher.id}`}
                            >
                              <Avatar className="h-8 w-8 flex-shrink-0">
                                <AvatarImage src={teacher.avatar_url} />
                                <AvatarFallback className="bg-brand-navy text-white text-xs">
                                  {teacher.full_name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
                                </AvatarFallback>
                              </Avatar>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-medium truncate text-brand-navy dark:text-brand-turquoise">
                                  {teacher.full_name}
                                </p>
                                <div className="flex items-center gap-1">
                                  <Badge variant="secondary" className="text-[9px] px-1 py-0">
                                    {getTeacherWorkload(teacher.id)} {isRTL ? 'ح' : 'p'}
                                  </Badge>
                                </div>
                              </div>
                            </div>
                          </td>
                          
                          {/* Session Cells - Droppable */}
                          {displayedDays.map(day => (
                            timeSlots.map(slot => {
                              const cellSessions = getSessionsForCell(teacher.id, day.key, slot.id);
                              const cellId = `${teacher.id}__${day.key}__${slot.id}`;
                              
                              return (
                                <DroppableCell key={cellId} id={cellId}>
                                  {cellSessions.length > 0 ? (
                                    <div className="space-y-0.5">
                                      {cellSessions.map(session => (
                                        <DraggableSession
                                          key={session.id}
                                          session={session}
                                          isRTL={isRTL}
                                          onClick={() => {
                                            setSelectedSession(session);
                                            setSessionDetailOpen(true);
                                          }}
                                        />
                                      ))}
                                    </div>
                                  ) : (
                                    <div className={`h-8 border border-dashed rounded transition-colors ${
                                      isDragging ? 'border-brand-turquoise/50 bg-brand-turquoise/5' : 'border-muted-foreground/20'
                                    }`} />
                                  )}
                                </DroppableCell>
                              );
                            })
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
              
              {/* Drag Overlay */}
              <DragOverlay>
                {activeSession && <SessionDragOverlay session={activeSession} isRTL={isRTL} />}
              </DragOverlay>
            </DndContext>
            </SectionErrorBoundary>
          )}
        </div>

        {/* Teacher Detail Dialog */}
        <Dialog open={teacherDetailOpen} onOpenChange={setTeacherDetailOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-3">
                <Avatar className="h-12 w-12">
                  <AvatarImage src={selectedTeacher?.avatar_url} />
                  <AvatarFallback className="bg-brand-navy text-white">
                    {selectedTeacher?.full_name?.split(' ').map(n => n[0]).join('').slice(0, 2)}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="text-lg">{selectedTeacher?.full_name}</p>
                  <p className="text-sm text-muted-foreground font-normal">{selectedTeacher?.specialization || selectedTeacher?.subject}</p>
                </div>
              </DialogTitle>
            </DialogHeader>
            {selectedTeacher && (
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1 p-3 bg-muted/30 rounded-xl">
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <Briefcase className="h-3 w-3" />
                      {isRTL ? 'النصاب' : 'Workload'}
                    </p>
                    <p className="font-bold text-lg text-brand-navy">
                      {getTeacherWorkload(selectedTeacher.id)} / 24
                    </p>
                  </div>
                  <div className="space-y-1 p-3 bg-muted/30 rounded-xl">
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <Award className="h-3 w-3" />
                      {isRTL ? 'الرتبة' : 'Rank'}
                    </p>
                    <p className="font-medium">{selectedTeacher.rank || (isRTL ? 'معلم' : 'Teacher')}</p>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <BookOpen className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">{isRTL ? 'المادة:' : 'Subject:'}</span>
                    <span className="font-medium">{selectedTeacher.specialization || selectedTeacher.subject}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <GraduationCap className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">{isRTL ? 'المرحلة:' : 'Level:'}</span>
                    <span className="font-medium">{selectedTeacher.education_level || (isRTL ? 'ابتدائي' : 'Primary')}</span>
                  </div>
                  {selectedTeacher.phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">{isRTL ? 'الهاتف:' : 'Phone:'}</span>
                      <span className="font-medium" dir="ltr">{selectedTeacher.phone}</span>
                    </div>
                  )}
                  {selectedTeacher.email && (
                    <div className="flex items-center gap-2 text-sm">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">{isRTL ? 'البريد:' : 'Email:'}</span>
                      <span className="font-medium text-xs" dir="ltr">{selectedTeacher.email}</span>
                    </div>
                  )}
                </div>

                {/* Teacher's Sessions Summary */}
                <div className="pt-2 border-t">
                  <p className="text-sm font-medium mb-2">{isRTL ? 'توزيع الحصص' : 'Sessions Distribution'}</p>
                  <div className="flex flex-wrap gap-1">
                    {DAYS.map(day => {
                      const daySessions = filteredSessions.filter(s => s.teacher_id === selectedTeacher.id && s.day_of_week === day.key);
                      return (
                        <Badge key={day.key} variant="outline" className="text-xs">
                          {isRTL ? day.ar : day.en}: {daySessions.length}
                        </Badge>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setTeacherDetailOpen(false)} className="rounded-xl">
                {isRTL ? 'إغلاق' : 'Close'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Session Detail Dialog */}
        <Dialog open={sessionDetailOpen} onOpenChange={setSessionDetailOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-cairo">{isRTL ? 'تفاصيل الحصة' : 'Session Details'}</DialogTitle>
            </DialogHeader>
            {selectedSession && (
              <div className="space-y-4 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">{isRTL ? 'المادة' : 'Subject'}</p>
                    <p className="font-medium flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-brand-navy" />
                      {selectedSession.subject_name}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">{isRTL ? 'المعلم' : 'Teacher'}</p>
                    <p className="font-medium flex items-center gap-2">
                      <UserCheck className="h-4 w-4 text-brand-turquoise" />
                      {selectedSession.teacher_name}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">{isRTL ? 'الفصل' : 'Class'}</p>
                    <p className="font-medium flex items-center gap-2">
                      <GraduationCap className="h-4 w-4 text-brand-purple" />
                      {selectedSession.class_name}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">{isRTL ? 'اليوم' : 'Day'}</p>
                    <Badge variant="secondary" className="rounded-lg">
                      {DAYS.find(d => d.key === selectedSession.day_of_week)?.[isRTL ? 'ar' : 'en']}
                    </Badge>
                  </div>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="destructive" onClick={() => handleDeleteSession(selectedSession?.id)} className="rounded-xl" data-testid="delete-session-btn">
                <Trash2 className="h-4 w-4 me-2" />
                {isRTL ? 'حذف' : 'Delete'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Generation Results Dialog */}
        <Dialog open={generationResultOpen} onOpenChange={setGenerationResultOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                {generationStats?.success ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                )}
                {isRTL ? 'نتائج التوليد الذكي' : 'Smart Generation Results'}
              </DialogTitle>
              <DialogDescription>
                {generationStats?.message || generationStats?.message_en}
              </DialogDescription>
            </DialogHeader>
            {generationStats && (
              <div className="space-y-4 py-4">
                {/* Main Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-xl text-center">
                    <p className="text-2xl font-bold text-green-600">{generationStats.sessions_created}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'حصة تم إنشاؤها' : 'Sessions Created'}</p>
                  </div>
                  <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl text-center">
                    <p className="text-2xl font-bold text-blue-600">{generationStats.success_rate}%</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'نسبة النجاح' : 'Success Rate'}</p>
                  </div>
                </div>

                {/* Additional Stats */}
                {generationStats.statistics && (
                  <div className="space-y-2 p-3 bg-muted/30 rounded-xl">
                    <p className="text-sm font-medium mb-2">{isRTL ? 'إحصائيات التوليد' : 'Generation Statistics'}</p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">{isRTL ? 'المعلمون المجدولون:' : 'Teachers Scheduled:'}</span>
                        <span className="font-medium">{generationStats.statistics.teachers_scheduled}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">{isRTL ? 'التعارضات المتجنبة:' : 'Conflicts Avoided:'}</span>
                        <span className="font-medium text-green-600">{generationStats.statistics.conflicts_avoided}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">{isRTL ? 'محاولات الوضع:' : 'Placement Attempts:'}</span>
                        <span className="font-medium">{generationStats.statistics.placement_attempts}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">{isRTL ? 'وقت التوليد:' : 'Generation Time:'}</span>
                        <span className="font-medium">{generationStats.generation_time_seconds}s</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Unplaced Warning */}
                {generationStats.unplaced_sessions > 0 && (
                  <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200">
                    <div className="flex items-center gap-2 text-amber-700">
                      <AlertTriangle className="h-4 w-4" />
                      <span className="text-sm font-medium">
                        {isRTL 
                          ? `${generationStats.unplaced_sessions} حصة لم يتم جدولتها`
                          : `${generationStats.unplaced_sessions} sessions could not be placed`
                        }
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {isRTL 
                        ? 'قد تحتاج لمراجعة الإسنادات أو إضافة فترات زمنية'
                        : 'You may need to review assignments or add more time slots'
                      }
                    </p>
                  </div>
                )}
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setGenerationResultOpen(false)} className="rounded-xl">
                {isRTL ? 'إغلاق' : 'Close'}
              </Button>
              <Button onClick={() => { setGenerationResultOpen(false); setConflictsSheetOpen(true); }} className="bg-brand-navy rounded-xl">
                {isRTL ? 'عرض التعارضات' : 'View Conflicts'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
