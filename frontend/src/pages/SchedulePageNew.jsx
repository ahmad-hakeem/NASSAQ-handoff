/**
 * صفحة الجدول المدرسي — التصميم التفاعلي الجديد
 * نَسَّق | NASSAQ School Management System
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Progress } from '../components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';

import {
  Calendar, Clock, Users, BookOpen, GraduationCap,
  Loader2, Wand2, CheckCircle2, AlertTriangle,
  RefreshCw, Settings, Coffee, Moon, Sun, Send,
  Sparkles, User, BarChart3, Layers,
  Play, Star, Info, AlertCircle
} from 'lucide-react';
import { NotificationBell } from '../components/notifications/NotificationBell';
import CandidatesSidePanel from '../components/schedule/CandidatesSidePanel';

// ─── Constants ──────────────────────────────────────────────────────────────
const DAYS = [
  { key: 'sunday',    ar: 'الأحد',     color: 'from-violet-500 to-purple-600' },
  { key: 'monday',    ar: 'الإثنين',   color: 'from-blue-500 to-indigo-600' },
  { key: 'tuesday',   ar: 'الثلاثاء',  color: 'from-teal-500 to-cyan-600' },
  { key: 'wednesday', ar: 'الأربعاء',  color: 'from-amber-500 to-orange-600' },
  { key: 'thursday',  ar: 'الخميس',    color: 'from-rose-500 to-pink-600' },
];

const SUBJECT_PALETTE = [
  { bg: 'bg-gradient-to-br from-emerald-500 to-teal-600',  text: 'text-white', light: 'bg-emerald-50 text-emerald-800 border-emerald-200' },
  { bg: 'bg-gradient-to-br from-blue-500 to-indigo-600',   text: 'text-white', light: 'bg-blue-50 text-blue-800 border-blue-200' },
  { bg: 'bg-gradient-to-br from-purple-500 to-violet-600', text: 'text-white', light: 'bg-purple-50 text-purple-800 border-purple-200' },
  { bg: 'bg-gradient-to-br from-amber-500 to-orange-600',  text: 'text-white', light: 'bg-amber-50 text-amber-800 border-amber-200' },
  { bg: 'bg-gradient-to-br from-rose-500 to-pink-600',     text: 'text-white', light: 'bg-rose-50 text-rose-800 border-rose-200' },
  { bg: 'bg-gradient-to-br from-cyan-500 to-sky-600',      text: 'text-white', light: 'bg-cyan-50 text-cyan-800 border-cyan-200' },
  { bg: 'bg-gradient-to-br from-fuchsia-500 to-pink-600',  text: 'text-white', light: 'bg-fuchsia-50 text-fuchsia-800 border-fuchsia-200' },
  { bg: 'bg-gradient-to-br from-lime-500 to-green-600',    text: 'text-white', light: 'bg-lime-50 text-lime-800 border-lime-200' },
  { bg: 'bg-gradient-to-br from-slate-500 to-gray-600',    text: 'text-white', light: 'bg-slate-50 text-slate-800 border-slate-200' },
  { bg: 'bg-gradient-to-br from-red-500 to-rose-600',      text: 'text-white', light: 'bg-red-50 text-red-800 border-red-200' },
];

const SUBJECT_NAME_MAP = {
  'لغتي': 0, 'اللغة العربية': 0, 'القراءة': 0,
  'الرياضيات': 1, 'الحساب': 1,
  'العلوم': 2, 'الأحياء': 2, 'الكيمياء': 2, 'الفيزياء': 2,
  'الدراسات الإسلامية': 3, 'التربية الإسلامية': 3, 'القرآن': 3, 'الفقه': 3,
  'اللغة الإنجليزية': 4, 'الإنجليزية': 4,
  'التربية البدنية': 5, 'الرياضة': 5,
  'التربية الفنية': 6, 'الفنون': 6,
  'الدراسات الاجتماعية': 7, 'التاريخ': 7, 'الجغرافيا': 7,
  'الحاسب': 8, 'المهارات الرقمية': 8, 'تقنية المعلومات': 8,
};

const subjectColorIndex = (name) => {
  if (!name) return 9;
  for (const [key, idx] of Object.entries(SUBJECT_NAME_MAP)) {
    if (name.includes(key)) return idx;
  }
  const hash = [...name].reduce((a, c) => a + c.charCodeAt(0), 0);
  return hash % SUBJECT_PALETTE.length;
};

// ─── Session Card ─────────────────────────────────────────────────────────
const SessionCard = ({ session, viewMode, onClick, isDraggable, onDragStart, isDragging }) => {
  const palette = SUBJECT_PALETTE[subjectColorIndex(session.subject_name)];
  return (
    <div
      draggable={isDraggable}
      onDragStart={isDraggable ? (e) => {
        e.dataTransfer.setData('application/nassaq-session', JSON.stringify({
          id: session.id,
          day: session.day_of_week || session.day,
          period: session.period_number
        }));
        e.dataTransfer.effectAllowed = 'move';
        onDragStart?.(session.id);
      } : undefined}
      onDragEnd={() => onDragStart?.(null)}
      onClick={onClick}
      className={`w-full h-full min-h-[80px] p-2.5 rounded-xl ${palette.bg} ${palette.text}
        ${isDraggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'}
        hover:shadow-lg hover:scale-[1.03] active:scale-[0.98]
        transition-all duration-200 shadow-sm text-right group
        ${isDragging ? 'opacity-40 scale-95 ring-2 ring-white/50' : ''}`}
      data-testid={`session-${session.id}`}
    >
      <div className="flex flex-col h-full justify-between gap-1">
        <div>
          <p className="font-bold text-xs leading-tight line-clamp-2 drop-shadow-sm">
            {session.subject_name || 'مادة'}
          </p>
          <p className="text-[10px] opacity-85 mt-0.5 truncate font-medium">
            {viewMode === 'class' ? (session.teacher_name || '—') : (session.class_name || '—')}
          </p>
        </div>
        <div className="flex items-center justify-between gap-1">
          <span className="text-[9px] opacity-70 font-mono">
            {session.start_time?.substring(0, 5)}
          </span>
          {isDraggable
            ? <svg className="h-3 w-3 opacity-0 group-hover:opacity-70 transition-opacity" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/>
                <circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/>
                <circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/>
              </svg>
            : <Info className="h-2.5 w-2.5 opacity-0 group-hover:opacity-70 transition-opacity" />}
        </div>
      </div>
    </div>
  );
};

// ─── Empty Cell ───────────────────────────────────────────────────────────
const EmptyCell = ({ isDropTarget, isGap, canPick, onPick }) => {
  const Tag = canPick ? 'button' : 'div';
  return (
    <Tag
      type={canPick ? 'button' : undefined}
      onClick={canPick ? onPick : undefined}
      className={`w-full min-h-[80px] rounded-xl border-2 border-dashed relative
        flex flex-col items-center justify-center gap-1 transition-all duration-200 text-center
        ${canPick ? 'cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#46C1BE]/50' : ''}
        ${isDropTarget
          ? 'border-[#46C1BE] bg-[#46C1BE]/10 shadow-inner scale-[1.02]'
          : isGap
            ? 'border-red-300 bg-gradient-to-b from-red-50 to-amber-50/80 hover:border-red-400 hover:shadow-md'
            : canPick
              ? 'border-[#2BB5A0]/40 bg-[#2BB5A0]/5 hover:border-[#2BB5A0] hover:bg-[#2BB5A0]/10'
              : 'border-slate-200 bg-slate-50/50 hover:border-slate-300 hover:bg-slate-50'}`}
    >
      {isDropTarget ? (
        <span className="text-[#46C1BE] text-[10px] font-bold select-none">انقل هنا ↓</span>
      ) : isGap ? (
        <>
          <div className="absolute top-1 left-1 w-4 h-4 rounded-full bg-red-500 flex items-center justify-center animate-pulse">
            <span className="text-white text-[8px] font-black">!</span>
          </div>
          <svg className="h-5 w-5 text-red-400 mb-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 9v4m0 4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="text-red-600 text-[10px] font-extrabold select-none leading-tight">غير مستوفية</span>
          {canPick
            ? <span className="text-red-500 text-[9px] font-bold select-none underline">اختر معلم ←</span>
            : <span className="text-red-400 text-[8px] font-medium select-none">تحتاج تعيين مادة</span>}
        </>
      ) : canPick ? (
        <>
          <svg className="h-4 w-4 text-[#2BB5A0]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" strokeLinecap="round"/>
          </svg>
          <span className="text-[#2BB5A0] text-[10px] font-bold select-none">اختر معلم</span>
        </>
      ) : (
        <span className="text-slate-300 text-[10px] select-none">—</span>
      )}
    </Tag>
  );
};

// ─── Break Row ─────────────────────────────────────────────────────────────
const BreakRow = ({ slot }) => {
  const isPrayer = slot.is_prayer;
  return (
    <tr>
      <td className="px-3 py-2 border-b border-slate-100">
        <div className={`text-center rounded-lg py-1.5 ${isPrayer ? 'bg-emerald-50' : 'bg-amber-50'}`}>
          <p className={`font-bold text-xs ${isPrayer ? 'text-emerald-700' : 'text-amber-700'}`}>
            {isPrayer ? 'صلاة' : 'استراحة'}
          </p>
          <p className="text-[9px] text-slate-400 font-mono">
            {slot.start_time?.substring(0, 5)} — {slot.end_time?.substring(0, 5)}
          </p>
        </div>
      </td>
      <td colSpan={DAYS.length} className="px-4 py-2 border-b border-slate-100">
        <div className={`rounded-xl py-2.5 flex items-center justify-center gap-2.5
          ${isPrayer
            ? 'bg-gradient-to-r from-emerald-100 to-teal-100 border border-emerald-200'
            : 'bg-gradient-to-r from-amber-100 to-orange-100 border border-amber-200'}`}>
          {isPrayer
            ? <Moon className="h-4 w-4 text-emerald-600" />
            : <Coffee className="h-4 w-4 text-amber-600" />}
          <span className={`text-sm font-bold ${isPrayer ? 'text-emerald-700' : 'text-amber-700'}`}>
            {slot.name_ar || slot.name || (isPrayer ? 'وقت الصلاة' : 'فترة الاستراحة')}
          </span>
          <span className="text-xs text-slate-400">
            ({slot.start_time?.substring(0, 5)} — {slot.end_time?.substring(0, 5)})
          </span>
        </div>
      </td>
    </tr>
  );
};

// ─── Stat Badge ─────────────────────────────────────────────────────────────
const StatBadge = ({ icon: Icon, label, value, colorClass }) => (
  <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${colorClass}`}>
    <Icon className="h-3.5 w-3.5 shrink-0" />
    <div>
      <p className="text-[10px] opacity-70 leading-none">{label}</p>
      <p className="font-bold text-sm leading-tight">{value}</p>
    </div>
  </div>
);

// ─── Main Page ────────────────────────────────────────────────────────────
export default function SchedulePageNew() {
  const { user, api } = useAuth();
  const { isDark, toggleTheme } = useTheme();

  // State
  const [loading, setLoading]           = useState(true);
  const [sessions, setSessions]         = useState([]);
  const [timeSlots, setTimeSlots]       = useState([]);
  const [teachers, setTeachers]         = useState([]);
  const [classes, setClasses]           = useState([]);
  const [smartTimetables, setSmartTimetables] = useState([]);
  const [selectedTimetableId, setSelectedTimetableId] = useState(null);

  const [viewMode, setViewMode]         = useState('class');
  const [selectedClass, setSelectedClass]   = useState('');
  const [selectedTeacher, setSelectedTeacher] = useState('');
  const [sessionsLoading, setSessionsLoading] = useState(false);

  const [generating, setGenerating]     = useState(false);
  const [generationStep, setGenerationStep] = useState('');
  const [generationProgress, setGenerationProgress] = useState(0);
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [resultDialogOpen, setResultDialogOpen]     = useState(false);
  const [generationResult, setGenerationResult]     = useState(null);

  const [selectedSession, setSelectedSession]   = useState(null);
  const [sessionDetailOpen, setSessionDetailOpen] = useState(false);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [publishing, setPublishing]             = useState(false);

  const [draggingSessionId, setDraggingSessionId] = useState(null);
  const [dropTargetCell, setDropTargetCell]       = useState(null);

  // Candidates side-panel state
  const [candidatesPanelOpen, setCandidatesPanelOpen] = useState(false);
  const [activeSlot, setActiveSlot] = useState(null); // { class_id, class_name, day_of_week, period_number, ... }

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const schoolId = user?.tenant_id;

  // Principal/deputy may pick candidates for empty cells
  const canPickCandidates =
    user?.role === 'school_principal'
    || user?.role === 'school_sub_admin'
    || user?.role === 'platform_admin';

  // ── Fetch base data ────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    if (!schoolId) return;
    setLoading(true);
    try {
      const [slotsRes, teachersRes, classesRes, timetablesRes] = await Promise.all([
        api.get(`/time-slots?school_id=${schoolId}`).catch(() => ({ data: [] })),
        api.get(`/teachers`).catch(() => ({ data: [] })),
        api.get(`/classes`).catch(() => ({ data: [] })),
        api.get(`/smart-scheduling/timetables/${schoolId}`).catch(() => ({ data: { timetables: [] } })),
      ]);

      const slots = (Array.isArray(slotsRes.data) ? slotsRes.data : [])
        .sort((a, b) => (a.period_number || 0) - (b.period_number || 0));
      setTimeSlots(slots);

      const teacherList = Array.isArray(teachersRes.data) ? teachersRes.data : [];
      setTeachers(teacherList);

      const classList = Array.isArray(classesRes.data) ? classesRes.data : [];
      setClasses(classList);
      if (classList.length > 0 && !selectedClass) setSelectedClass(classList[0].id);
      if (teacherList.length > 0 && !selectedTeacher) setSelectedTeacher(teacherList[0].id);

      const timetableList = timetablesRes.data?.timetables || [];
      setSmartTimetables(timetableList);

      if (timetableList.length > 0 && !selectedTimetableId) {
        const published = timetableList.find(t => t.status === 'published');
        const best = published || timetableList[0];
        setSelectedTimetableId(best.id);
      }
    } catch (err) {
      console.error('fetchData error:', err);
      nassaqError('فشل تحميل البيانات');
    } finally {
      setLoading(false);
    }
  }, [schoolId, api]);

  // ── Fetch sessions ────────────────────────────────────────────────────
  const fetchSessions = useCallback(async (timetableId) => {
    const tid = timetableId || selectedTimetableId;
    if (!tid) { setSessions([]); return; }
    setSessionsLoading(true);
    try {
      const res = await api.get(`/smart-scheduling/timetable/${tid}/sessions`);
      setSessions(res.data?.sessions || []);
    } catch (err) {
      console.error('Sessions error:', err);
      setSessions([]);
    } finally {
      setSessionsLoading(false);
    }
  }, [selectedTimetableId, api]);

  useEffect(() => { fetchData(); }, [user?.tenant_id]);
  useEffect(() => { if (selectedTimetableId) fetchSessions(); }, [selectedTimetableId]);

  // ── Generate ───────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    setGenerating(true);
    setGenerationStep('التحقق من جاهزية البيانات...');
    setGenerationProgress(15);
    try {
      const validateRes = await api.get(`/smart-scheduling/validate/${schoolId}`);
      const critical = (validateRes.data?.issues || []).filter(i => i.severity === 'critical');
      if (critical.length > 0 && !validateRes.data.can_proceed) {
        nassaqError(critical[0].message_ar || 'بيانات غير مكتملة');
        return;
      }

      setGenerationStep('بناء الجدول بالذكاء الاصطناعي...');
      setGenerationProgress(50);

      const res = await api.post(`/smart-scheduling/generate/${schoolId}`, {});
      setGenerationProgress(100);
      setGenerationStep('تم بنجاح!');

      const result = res.data;
      const sessionsCreated = result.scheduled_sessions || result.sessions_created || 0;
      const totalSessions   = result.total_sessions || sessionsCreated;
      const unplaced        = result.unscheduled_count || result.unplaced_sessions || 0;
      const successRate     = result.success_rate
        || (totalSessions > 0 ? ((sessionsCreated / totalSessions) * 100).toFixed(1) : '0');

      setGenerationResult({
        timetable_id: result.timetable_id,
        sessions_created: sessionsCreated,
        unplaced,
        success_rate: successRate,
        name: result.timetable_name || 'الجدول الجديد',
        capacity_issues: result.capacity_issues || [],
      });

      setGenerateDialogOpen(false);
      setResultDialogOpen(true);

      // Refresh timetable list and switch to new timetable
      const tmRes = await api.get(`/smart-scheduling/timetables/${schoolId}`).catch(() => ({ data: { timetables: [] } }));
      setSmartTimetables(tmRes.data?.timetables || []);
      setSelectedTimetableId(result.timetable_id);
      fetchSessions(result.timetable_id);
    } catch (err) {
      const msg = err.response?.data?.message_ar || err.response?.data?.detail || err.message || 'فشل توليد الجدول';
      nassaqError(msg);
    } finally {
      setGenerating(false);
      setGenerationStep('');
      setGenerationProgress(0);
    }
  };

  // ── Publish ─────────────────────────────────────────────────────────────
  const handlePublish = async () => {
    if (!selectedTimetableId) return;
    setPublishing(true);
    try {
      await api.post(`/smart-scheduling/timetable/${selectedTimetableId}/publish`);
      toast.success('تم نشر الجدول بنجاح وأصبح مرئياً للجميع');
      setPublishDialogOpen(false);
      const tmRes = await api.get(`/smart-scheduling/timetables/${schoolId}`);
      setSmartTimetables(tmRes.data?.timetables || []);
    } catch (err) {
      nassaqError(err.response?.data?.detail || 'فشل نشر الجدول');
    } finally {
      setPublishing(false);
    }
  };

  // ── Session Matching (Bug-Fixed) ─────────────────────────────────────────
  // Sessions use period_number (integer); time slots also have period_number after the backend fix.
  // This function correctly matches sessions to grid cells.
  const getSessionForCell = useCallback((dayKey, slotPeriodNumber, filterId) => {
    return sessions.find(s => {
      const dayMatch    = (s.day_of_week || s.day) === dayKey;
      const periodMatch = s.period_number === slotPeriodNumber
                       || s.slot_number   === slotPeriodNumber;
      const filterMatch = viewMode === 'class'
        ? s.class_id   === filterId
        : s.teacher_id === filterId;
      return dayMatch && periodMatch && filterMatch;
    });
  }, [sessions, viewMode]);

  const currentTimetable = smartTimetables.find(t => t.id === selectedTimetableId);
  const canDragDrop = currentTimetable && currentTimetable.status !== 'published';

  const handleCellDragOver = useCallback((e, dayKey, periodNum) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDropTargetCell(`${dayKey}-${periodNum}`);
  }, []);

  const handleCellDragLeave = useCallback(() => {
    setDropTargetCell(null);
  }, []);

  const handleCellDrop = useCallback(async (e, targetDay, targetPeriod, targetSession) => {
    e.preventDefault();
    setDropTargetCell(null);
    setDraggingSessionId(null);

    let dragData;
    try {
      dragData = JSON.parse(e.dataTransfer.getData('application/nassaq-session'));
    } catch (e) { console.error('Error parsing drag data:', e); return; }

    const { id: draggedId, day: srcDay, period: srcPeriod } = dragData;
    if (draggedId === targetSession?.id) return;
    if (srcDay === targetDay && srcPeriod === targetPeriod) return;

    const prevSessions = [...sessions];

    if (targetSession) {
      setSessions(prev => prev.map(s => {
        if (s.id === draggedId) {
          return { ...s, day_of_week: targetDay, day: targetDay, period_number: targetPeriod, _justMoved: true };
        }
        if (s.id === targetSession.id) {
          return { ...s, day_of_week: srcDay, day: srcDay, period_number: srcPeriod, _justMoved: true };
        }
        return s;
      }));

      try {
        const res = await api.post('/smart-scheduling/sessions/swap', {
          session_id_1: draggedId,
          session_id_2: targetSession.id
        });
        if (res.data?.success || res.success) {
          toast.success('تم تبديل الحصتين بنجاح');
          fetchSessions();
        } else {
          setSessions(prevSessions);
          nassaqWarning(res.data?.detail || res.detail || 'فشل تبديل الحصتين');
        }
      } catch (err) {
        setSessions(prevSessions);
        const detail = err.response?.data?.detail || err.message || 'فشل تبديل الحصتين';
        nassaqWarning(detail);
      }
    } else {
      setSessions(prev => prev.map(s => {
        if (s.id === draggedId) {
          return { ...s, day_of_week: targetDay, day: targetDay, period_number: targetPeriod, _justMoved: true };
        }
        return s;
      }));

      try {
        const res = await api.post('/smart-scheduling/sessions/move', {
          session_id: draggedId,
          new_day: targetDay,
          new_period: targetPeriod
        });
        if (res.data?.success || res.success) {
          toast.success('تم نقل الحصة بنجاح');
          fetchSessions();
        } else {
          setSessions(prevSessions);
          nassaqWarning(res.data?.detail || res.detail || 'فشل نقل الحصة');
        }
      } catch (err) {
        setSessions(prevSessions);
        const detail = err.response?.data?.detail || err.message || 'فشل نقل الحصة';
        nassaqWarning(detail);
      }
    }
  }, [sessions, api, nassaqWarning, fetchSessions]);

  // ── Candidates side-panel handlers ─────────────────────────────────────
  const openCandidatesForCell = useCallback((dayKey, periodNum) => {
    if (!selectedClass || !selectedTimetableId) return;
    const cls = classes.find(c => c.id === selectedClass);
    setActiveSlot({
      timetable_id: selectedTimetableId,
      class_id: selectedClass,
      class_name: cls?.name || cls?.name_ar || '',
      day_of_week: dayKey,
      period_number: periodNum,
    });
    setCandidatesPanelOpen(true);
  }, [selectedClass, selectedTimetableId, classes]);

  const findNextEmptyCell = useCallback((fromDay, fromPeriod) => {
    if (!selectedClass) return null;
    const order = [];
    for (const slot of timeSlots) {
      if (slot.is_break || slot.is_prayer) continue;
      const pn = slot.period_number || slot.slot_number;
      for (const day of DAYS) {
        order.push({ day: day.key, period: pn });
      }
    }
    const startIdx = order.findIndex(o => o.day === fromDay && o.period === fromPeriod);
    const search = startIdx >= 0
      ? [...order.slice(startIdx + 1), ...order.slice(0, startIdx + 1)]
      : order;
    for (const o of search) {
      const exists = sessions.some(s =>
        (s.day_of_week || s.day) === o.day
        && (s.period_number === o.period || s.slot_number === o.period)
        && s.class_id === selectedClass
      );
      if (!exists) return o;
    }
    return null;
  }, [timeSlots, sessions, selectedClass]);

  const handleSlotAssigned = useCallback((sessionDoc, candidate) => {
    // Optimistic add
    setSessions(prev => [...prev, sessionDoc]);
    // Toast with undo
    toast.success(
      `تم تعيين ${candidate?.teacher_name || sessionDoc.teacher_name} للحصة`,
      {
        duration: 8000,
        action: {
          label: 'تراجع',
          onClick: async () => {
            try {
              await api.post('/schedule/slots/unassign', { session_id: sessionDoc.id });
              setSessions(prev => prev.filter(s => s.id !== sessionDoc.id));
              toast.success('تم التراجع عن التعيين');
            } catch (err) {
              toast.error(err.response?.data?.detail || 'تعذّر التراجع');
            }
          },
        },
      }
    );
  }, [api]);

  const handleSkipToNextEmpty = useCallback(() => {
    if (!activeSlot) return;
    const next = findNextEmptyCell(activeSlot.day_of_week, activeSlot.period_number);
    if (next) {
      const cls = classes.find(c => c.id === selectedClass);
      setActiveSlot({
        timetable_id: selectedTimetableId,
        class_id: selectedClass,
        class_name: cls?.name || cls?.name_ar || '',
        day_of_week: next.day,
        period_number: next.period,
      });
    } else {
      setCandidatesPanelOpen(false);
      setActiveSlot(null);
      toast.success('🎉 تم تعبئة جميع الخانات الفارغة لهذا الفصل');
    }
  }, [activeSlot, findNextEmptyCell, classes, selectedClass, selectedTimetableId]);

  // ── Derived ─────────────────────────────────────────────────────────────
  const currentFilter = viewMode === 'class' ? selectedClass : selectedTeacher;
  const currentFilterName = viewMode === 'class'
    ? (classes.find(c => c.id === selectedClass)?.name || classes.find(c => c.id === selectedClass)?.name_ar || '—')
    : (teachers.find(t => t.id === selectedTeacher)?.full_name || '—');

  const periodSlots      = timeSlots.filter(s => !s.is_break && !s.is_prayer);

  const gridSessions   = sessions.filter(s =>
    viewMode === 'class' ? s.class_id === currentFilter : s.teacher_id === currentFilter
  );
  const totalPossible  = periodSlots.length * DAYS.length;
  const coveragePct    = totalPossible > 0 ? Math.round((gridSessions.length / totalPossible) * 100) : 0;
  const uniqueSubjects = [...new Set(gridSessions.map(s => s.subject_name).filter(Boolean))];

  const periodGaps = useMemo(() => {
    if (!currentFilter || periodSlots.length === 0 || gridSessions.length === 0) return {};
    const gaps = {};
    periodSlots.forEach(slot => {
      const pNum = Number(slot.period_number || slot.slot_number);
      if (!pNum) return;
      let filledCount = 0;
      DAYS.forEach(day => {
        const has = gridSessions.some(s => {
          const dayMatch = (s.day_of_week || s.day) === day.key;
          const periodMatch = Number(s.period_number) === pNum || Number(s.slot_number) === pNum;
          return dayMatch && periodMatch;
        });
        if (has) filledCount++;
      });
      const emptyCount = DAYS.length - filledCount;
      if (emptyCount > 0) {
        gaps[pNum] = { filled: filledCount, empty: emptyCount, total: DAYS.length, pct: Math.round((filledCount / DAYS.length) * 100) };
      }
    });
    return gaps;
  }, [gridSessions, periodSlots, currentFilter]);

  const criticalGaps = useMemo(() => {
    return Object.entries(periodGaps)
      .filter(([_, g]) => g.empty >= 1)
      .sort((a, b) => b[1].empty - a[1].empty);
  }, [periodGaps]);

  // ── Loading Screen ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50/30">
          <div className="text-center space-y-4">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#1C3D74] to-[#2BB5A0] flex items-center justify-center mx-auto shadow-xl animate-pulse">
              <Calendar className="h-10 w-10 text-white" />
            </div>
            <Loader2 className="h-6 w-6 animate-spin mx-auto text-[#1C3D74]" />
            <p className="text-slate-500 font-medium">جاري تحميل الجدول المدرسي...</p>
          </div>
        </div>
      </Sidebar>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/20 to-slate-50" dir="rtl">

        {/* ── STICKY HEADER ──────────────────────────────────────────── */}
        <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-xl border-b border-slate-200 shadow-sm">
          <div className="px-6 py-3 flex items-center justify-between gap-4">

            {/* Logo + Title */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#1C3D74] to-[#2BB5A0] flex items-center justify-center shadow-lg shrink-0">
                <Calendar className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <h1 className="font-bold text-base text-slate-800 leading-tight">الجدول المدرسي</h1>
                <div className="flex items-center gap-1.5">
                  <p className="text-xs text-slate-500 truncate">
                    {currentTimetable?.name || 'لم يتم توليد جدول بعد'}
                  </p>
                  {currentTimetable && (
                    <Badge className={`text-[9px] px-1.5 py-0 h-4 ${currentTimetable.status === 'published' ? 'bg-green-100 text-green-700 border-green-200' : 'bg-amber-100 text-amber-700 border-amber-200'}`}>
                      {currentTimetable.status === 'published' ? 'منشور' : 'مسودة'}
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Stats (hidden on small) */}
            <div className="hidden md:flex items-center gap-2">
              <StatBadge icon={BookOpen}  label="حصص الجدول" value={gridSessions.length} colorClass="bg-blue-50 text-blue-700 border-blue-200" />
              <StatBadge icon={BarChart3} label="التغطية"    value={`${coveragePct}%`}
                colorClass={coveragePct >= 80 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'} />
              <StatBadge icon={Layers}   label="إجمالي الحصص" value={sessions.length} colorClass="bg-purple-50 text-purple-700 border-purple-200" />
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 shrink-0">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" onClick={() => { fetchData(); fetchSessions(); }} className="h-8 w-8">
                      <RefreshCw className={`h-3.5 w-3.5 ${sessionsLoading ? 'animate-spin' : ''}`} />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>تحديث البيانات</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" onClick={toggleTheme} className="h-8 w-8">
                      {isDark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{isDark ? 'الوضع النهاري' : 'الوضع الليلي'}</TooltipContent>
                </Tooltip>
              </TooltipProvider>

              {sessions.length > 0 && currentTimetable?.status !== 'published' && (
                <Button
                  size="sm"
                  variant="outline"
                  className="border-emerald-500 text-emerald-600 hover:bg-emerald-50 gap-1.5 h-8 text-xs"
                  onClick={() => setPublishDialogOpen(true)}
                >
                  <Send className="h-3.5 w-3.5" />
                  نشر
                </Button>
              )}

              <Button
                size="sm"
                onClick={() => setGenerateDialogOpen(true)}
                className="bg-gradient-to-r from-[#1C3D74] to-[#2a5ba8] hover:from-[#152d57] text-white gap-1.5 h-8 text-xs shadow-md"
              >
                <Wand2 className="h-3.5 w-3.5" />
                {smartTimetables.length > 0 ? 'توليد جديد' : 'توليد الجدول'}
              </Button>

              <NotificationBell />
            </div>
          </div>
        </header>

        {/* ── CONTROLS BAR ──────────────────────────────────────────── */}
        <div className="px-6 py-3 bg-white border-b border-slate-100 flex flex-wrap items-center gap-3">

          {/* View Mode Toggle */}
          <div className="flex items-center bg-slate-100 rounded-xl p-1 gap-1">
            {[
              { id: 'class',   label: 'بالفصل',  Icon: GraduationCap },
              { id: 'teacher', label: 'بالمعلم', Icon: User },
            ].map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setViewMode(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  viewMode === id
                    ? 'bg-white text-[#1C3D74] shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Class / Teacher Selector */}
          {viewMode === 'class' ? (
            <Select value={selectedClass} onValueChange={setSelectedClass}>
              <SelectTrigger className="w-[200px] h-9 text-xs border-slate-200" data-testid="class-selector">
                <SelectValue placeholder="اختر الفصل" />
              </SelectTrigger>
              <SelectContent>
                {classes.map(c => (
                  <SelectItem key={c.id} value={c.id} className="text-xs">
                    {c.name || c.name_ar}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Select value={selectedTeacher} onValueChange={setSelectedTeacher}>
              <SelectTrigger className="w-[200px] h-9 text-xs border-slate-200" data-testid="teacher-selector">
                <SelectValue placeholder="اختر المعلم" />
              </SelectTrigger>
              <SelectContent>
                {teachers.map(t => (
                  <SelectItem key={t.id} value={t.id} className="text-xs">
                    {t.full_name || t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* Timetable Selector (only if multiple) */}
          {smartTimetables.length > 1 && (
            <Select
              value={selectedTimetableId || ''}
              onValueChange={v => { setSelectedTimetableId(v); fetchSessions(v); }}
            >
              <SelectTrigger className="w-[240px] h-9 text-xs border-slate-200">
                <Layers className="h-3.5 w-3.5 ml-2 text-slate-400" />
                <SelectValue placeholder="اختر الجدول" />
              </SelectTrigger>
              <SelectContent>
                {smartTimetables.map(t => (
                  <SelectItem key={t.id} value={t.id} className="text-xs">
                    <div className="flex items-center gap-2">
                      {t.status === 'published' && <Star className="h-3 w-3 text-amber-500 shrink-0" />}
                      <span className="truncate">{t.name || `جدول ${t.id?.substring(0, 6)}`}</span>
                      <Badge className={`text-[9px] px-1 py-0 shrink-0 ${t.status === 'published' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                        {t.status === 'published' ? 'منشور' : 'مسودة'}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          {/* Coverage bar */}
          {currentFilter && sessions.length > 0 && (
            <div className="flex items-center gap-2 mr-auto">
              <span className="text-xs text-slate-500 whitespace-nowrap">تغطية {currentFilterName}:</span>
              <div className="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    coveragePct >= 80 ? 'bg-emerald-500' : coveragePct >= 50 ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${coveragePct}%` }}
                />
              </div>
              <span className={`text-xs font-bold whitespace-nowrap ${coveragePct >= 80 ? 'text-emerald-600' : 'text-amber-600'}`}>
                {coveragePct}%
              </span>
            </div>
          )}
        </div>

        {/* ── MAIN CONTENT ──────────────────────────────────────────── */}
        <main className="p-5 space-y-4 max-w-full">

          {/* No time slots */}
          {timeSlots.length === 0 && (
            <Card className="border-2 border-dashed border-slate-200">
              <CardContent className="text-center py-16">
                <Clock className="h-16 w-16 mx-auto mb-4 text-slate-200" />
                <h3 className="text-xl font-bold mb-2 text-slate-700">لم يتم تحديد الفترات الزمنية</h3>
                <p className="text-slate-500 mb-5">يجب إعداد الفترات الزمنية من إعدادات المدرسة أولاً</p>
                <Link to="/principal/settings?tab=timings">
                  <Button className="bg-[#1C3D74] hover:bg-[#152d57] gap-2">
                    <Settings className="h-4 w-4" />
                    إعداد الفترات الزمنية
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {/* No timetable yet */}
          {timeSlots.length > 0 && !selectedTimetableId && (
            <Card className="border-2 border-dashed border-[#1C3D74]/20">
              <CardContent className="text-center py-16">
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-[#1C3D74]/10 to-[#2BB5A0]/10 flex items-center justify-center mx-auto mb-5 shadow-inner">
                  <Sparkles className="h-10 w-10 text-[#1C3D74]" />
                </div>
                <h3 className="text-xl font-bold mb-2 text-slate-800">لا يوجد جدول بعد</h3>
                <p className="text-slate-500 mb-6 max-w-md mx-auto text-sm">
                  اضغط على "توليد الجدول" ليقوم الذكاء الاصطناعي ببناء جدول مدرسي كامل ومتوازن يراعي جميع القيود والمتطلبات تلقائياً
                </p>
                <Button
                  onClick={() => setGenerateDialogOpen(true)}
                  className="bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] hover:from-[#152d57] text-white gap-2 px-8 py-5 text-base shadow-lg"
                >
                  <Wand2 className="h-5 w-5" />
                  توليد الجدول بالذكاء الاصطناعي
                </Button>
              </CardContent>
            </Card>
          )}

          {/* ── COVERAGE GAPS WARNING ─────────────────────────────── */}
          {criticalGaps.length > 0 && selectedTimetableId && gridSessions.length > 0 && (() => {
            const totalEmpty = criticalGaps.reduce((s, [_, g]) => s + g.empty, 0);
            const isSevere = criticalGaps.some(([_, g]) => g.empty >= 4);
            const borderColor = isSevere ? 'border-red-300' : 'border-amber-300';
            const bgColor = isSevere ? 'bg-red-50/70' : 'bg-amber-50/60';
            const iconBg = isSevere ? 'bg-red-100' : 'bg-amber-100';
            const iconColor = isSevere ? 'text-red-600' : 'text-amber-600';
            return (
            <Card className={`border-2 ${borderColor} ${bgColor} shadow-md overflow-hidden`}>
              <div className="px-5 py-4 flex items-start gap-3">
                <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center shrink-0 mt-0.5 ${isSevere ? 'animate-pulse' : ''}`}>
                  <AlertTriangle className={`h-5 w-5 ${iconColor}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className={`font-bold text-sm ${isSevere ? 'text-red-800' : 'text-amber-800'}`}>
                      ⚠️ حصص غير مستوفية — {totalEmpty} خانة فارغة
                    </h3>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${isSevere ? 'bg-red-200 text-red-700' : 'bg-amber-200 text-amber-700'}`}>
                      {criticalGaps.length} {criticalGaps.length === 1 ? 'حصة' : 'حصص'}
                    </span>
                  </div>
                  <p className={`text-xs ${isSevere ? 'text-red-700' : 'text-amber-700'} mb-3`}>
                    الحصص التالية تحتوي على خانات فارغة لم يتم تعيين مواد لها بعد التوليد. يجب ملؤها لاكتمال الجدول:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {criticalGaps.map(([periodNum, gap]) => {
                      const severity = gap.empty === DAYS.length ? 'full' : gap.empty >= 3 ? 'high' : 'low';
                      return (
                      <div
                        key={periodNum}
                        className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold border-2 shadow-sm
                          ${severity === 'full'
                            ? 'bg-red-100 text-red-700 border-red-300 ring-1 ring-red-200'
                            : severity === 'high'
                              ? 'bg-red-50 text-red-600 border-red-200'
                              : 'bg-amber-100 text-amber-700 border-amber-300'}`}
                      >
                        <span className={`w-6 h-6 rounded-lg flex items-center justify-center text-[11px] font-black
                          ${severity === 'full' ? 'bg-red-500 text-white' : severity === 'high' ? 'bg-red-200 text-red-800' : 'bg-amber-200 text-amber-800'}`}>
                          {periodNum}
                        </span>
                        <div className="flex flex-col leading-tight">
                          <span>الحصة {periodNum}: {gap.empty} من {gap.total} فارغة</span>
                          {severity === 'full' && <span className="text-[9px] text-red-500 font-medium">فارغة بالكامل — لم يتم تعيين أي مادة</span>}
                          {severity === 'high' && <span className="text-[9px] text-red-400 font-medium">أغلب الأيام فارغة</span>}
                        </div>
                      </div>
                    );})}
                  </div>
                  <div className={`mt-3 p-2 rounded-lg ${isSevere ? 'bg-red-100/60' : 'bg-amber-100/60'} flex items-start gap-2`}>
                    <span className="text-sm mt-0.5">💡</span>
                    <p className={`text-[11px] ${isSevere ? 'text-red-700' : 'text-amber-700'} leading-relaxed`}>
                      اسحب حصص من أيام أخرى لملء الخانات الفارغة، أو أعد التوليد بعد التأكد من أن ساعات المنهج المُدخلة تغطي جميع الحصص.
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          );})()}

          {/* ── TIMETABLE GRID ──────────────────────────────────────── */}
          {timeSlots.length > 0 && selectedTimetableId && (
            <Card className="border border-slate-200 shadow-sm overflow-hidden" data-testid="schedule-page-new">
              <CardHeader className="py-3 px-5 bg-gradient-to-l from-[#1C3D74]/5 to-[#2BB5A0]/5 border-b border-slate-200">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {viewMode === 'class'
                      ? <GraduationCap className="h-5 w-5 text-[#1C3D74]" />
                      : <User className="h-5 w-5 text-[#1C3D74]" />}
                    <div>
                      <CardTitle className="text-base text-slate-800">
                        جدول {viewMode === 'class' ? 'الفصل' : 'المعلم'}:{' '}
                        <span className="text-[#1C3D74] font-bold">{currentFilterName}</span>
                      </CardTitle>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {gridSessions.length} حصة من {periodSlots.length * DAYS.length} حصة ممكنة
                        {gridSessions.length === 0 && sessions.length > 0 && (
                          <span className="text-amber-600 mr-2">
                            (الحصص موجودة لكن لا تطابق هذا {viewMode === 'class' ? 'الفصل' : 'المعلم'})
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {sessionsLoading && (
                      <div className="flex items-center gap-1.5 text-xs text-slate-400">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        تحميل...
                      </div>
                    )}
                    {canDragDrop && (
                      <Badge className="text-[9px] px-2 py-0.5 bg-[#46C1BE]/10 text-[#46C1BE] border-[#46C1BE]/30 font-medium">
                        اسحب وأفلت لنقل الحصص ↔
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>

              <div className="overflow-x-auto">
                <table className="w-full border-collapse min-w-[700px]">
                  {/* Day Headers */}
                  <thead>
                    <tr className="bg-slate-50/80 border-b border-slate-200">
                      <th className="w-[90px] min-w-[90px] p-3 border-l border-slate-200 text-center">
                        <div className="flex items-center justify-center gap-1 text-xs font-medium text-slate-500">
                          <Clock className="h-3.5 w-3.5" />
                          الحصة
                        </div>
                      </th>
                      {DAYS.map(day => (
                        <th key={day.key} className="p-3 text-center border-l border-slate-200 min-w-[130px]">
                          <div className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gradient-to-r ${day.color} text-white text-xs font-bold shadow-sm`}>
                            {day.ar}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {timeSlots.map((slot, idx) => {
                      const isBreak = slot.is_break || slot.is_prayer;
                      if (isBreak) return <BreakRow key={slot.id} slot={slot} />;

                      // period_number from DB (synced to slot_number by backend model_validator)
                      const slotPeriodNum = slot.period_number || slot.slot_number || (idx + 1);
                      const periodIdx     = periodSlots.findIndex(s => s.id === slot.id);
                      const isEven        = periodIdx % 2 === 0;

                      const rowGap = periodGaps[slotPeriodNum];
                      const isRowCritical = rowGap && rowGap.empty >= 1;
                      const isRowSevere = rowGap && rowGap.empty >= 4;

                      return (
                        <tr
                          key={slot.id}
                          className={`border-b ${isRowSevere ? 'border-red-200 bg-red-50/40' : isRowCritical ? 'border-amber-200 bg-amber-50/30' : 'border-slate-100'} ${!isRowCritical && (isEven ? '' : 'bg-slate-50/40')} hover:bg-blue-50/20 transition-colors group`}
                        >
                          {/* Period Label */}
                          <td className={`p-2 border-l border-slate-200 group-hover:bg-blue-50/30 transition-colors ${isRowSevere ? 'bg-red-50/70' : isRowCritical ? 'bg-amber-50/50' : 'bg-white'}`}>
                            <div className="text-center">
                              <div className={`w-8 h-8 rounded-lg font-bold text-sm flex items-center justify-center mx-auto mb-1 ${isRowSevere ? 'bg-red-100 text-red-700 ring-2 ring-red-300' : isRowCritical ? 'bg-amber-100 text-amber-700 ring-1 ring-amber-300' : 'bg-[#1C3D74]/10 text-[#1C3D74]'}`}>
                                {slotPeriodNum}
                              </div>
                              <p className="text-[9px] text-slate-400 font-mono leading-none">
                                {slot.start_time?.substring(0, 5)}
                              </p>
                              <p className="text-[9px] text-slate-300 font-mono">
                                {slot.end_time?.substring(0, 5)}
                              </p>
                              {rowGap && (
                                <div className="mt-1">
                                  <p className={`text-[9px] font-bold ${isRowSevere ? 'text-red-600' : 'text-amber-600'}`}>
                                    {rowGap.filled}/{rowGap.total}
                                  </p>
                                  <p className={`text-[7px] font-medium ${isRowSevere ? 'text-red-400' : 'text-amber-400'}`}>
                                    ناقص
                                  </p>
                                </div>
                              )}
                            </div>
                          </td>

                          {/* Day Cells */}
                          {DAYS.map(day => {
                            const session = getSessionForCell(day.key, slotPeriodNum, currentFilter);
                            const cellKey = `${day.key}-${slotPeriodNum}`;
                            const isTarget = dropTargetCell === cellKey;
                            const isCellGap = !session && rowGap && gridSessions.length > 0;
                            return (
                              <td
                                key={`${day.key}-${slot.id}`}
                                className={`p-1.5 border-l border-slate-100 transition-colors duration-150
                                  ${isTarget && session ? 'bg-amber-50 ring-2 ring-inset ring-amber-300 rounded' : ''}
                                  ${isTarget && !session ? 'bg-[#46C1BE]/5' : ''}`}
                                onDragOver={canDragDrop ? (e) => handleCellDragOver(e, day.key, slotPeriodNum) : undefined}
                                onDragLeave={canDragDrop ? handleCellDragLeave : undefined}
                                onDrop={canDragDrop ? (e) => handleCellDrop(e, day.key, slotPeriodNum, session) : undefined}
                              >
                                {session ? (
                                  <SessionCard
                                    session={session}
                                    viewMode={viewMode}
                                    onClick={() => { setSelectedSession(session); setSessionDetailOpen(true); }}
                                    isDraggable={canDragDrop}
                                    onDragStart={setDraggingSessionId}
                                    isDragging={draggingSessionId === session.id}
                                  />
                                ) : (
                                  <EmptyCell
                                    isDropTarget={isTarget}
                                    isGap={isCellGap}
                                    canPick={
                                      canPickCandidates
                                      && canDragDrop
                                      && viewMode === 'class'
                                      && !!selectedClass
                                    }
                                    onPick={() => openCandidatesForCell(day.key, slotPeriodNum)}
                                  />
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Subject Legend */}
          {uniqueSubjects.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap px-1">
              <span className="text-xs font-medium text-slate-500">المواد:</span>
              {uniqueSubjects.map(name => {
                const palette = SUBJECT_PALETTE[subjectColorIndex(name)];
                return (
                  <span
                    key={name}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${palette.light}`}
                  >
                    <span className={`w-2 h-2 rounded-full ${palette.bg} shadow-sm`} />
                    {name}
                  </span>
                );
              })}
            </div>
          )}
        </main>

        {/* ── GENERATE DIALOG ─────────────────────────────────────────── */}
        <Dialog open={generateDialogOpen} onOpenChange={o => { if (!generating) setGenerateDialogOpen(o); }}>
          <DialogContent className="max-w-md" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-3 text-[#1C3D74]">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#1C3D74] to-[#2BB5A0] flex items-center justify-center shrink-0">
                  <Wand2 className="h-4 w-4 text-white" />
                </div>
                توليد الجدول بالذكاء الاصطناعي
              </DialogTitle>
              <DialogDescription>
                سيقوم النظام بتحليل جميع البيانات وبناء جدول دراسي متوازن ومحسَّن تلقائياً
              </DialogDescription>
            </DialogHeader>

            {generating ? (
              <div className="space-y-4 py-2">
                <div className="p-4 bg-blue-50 rounded-xl border border-blue-100">
                  <div className="flex items-center gap-3 mb-3">
                    <Loader2 className="h-5 w-5 animate-spin text-[#1C3D74] shrink-0" />
                    <span className="text-sm font-medium text-[#1C3D74]">{generationStep}</span>
                  </div>
                  <Progress
                    value={generationProgress}
                    className="h-2 [&>div]:bg-[#1C3D74] [&>div]:transition-all [&>div]:duration-700"
                  />
                  <p className="text-xs text-center text-slate-400 mt-2">{generationProgress}%</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2 py-2">
                {[
                  { Icon: Users,       text: 'تحليل إسنادات المعلمين والفصول',   color: 'text-blue-600',   bg: 'bg-blue-50' },
                  { Icon: Clock,       text: 'توزيع الحصص على الفترات الزمنية',  color: 'text-purple-600', bg: 'bg-purple-50' },
                  { Icon: Star,        text: 'تحسين الجدول وتقليل التعارضات',    color: 'text-amber-600',  bg: 'bg-amber-50' },
                  { Icon: CheckCircle2,text: 'التحقق من جميع القيود والمتطلبات', color: 'text-emerald-600',bg: 'bg-emerald-50' },
                ].map(({ Icon, text, color, bg }) => (
                  <div key={text} className={`flex items-center gap-3 p-2.5 rounded-lg ${bg}`}>
                    <Icon className={`h-4 w-4 ${color} shrink-0`} />
                    <span className="text-xs text-slate-700">{text}</span>
                  </div>
                ))}
                {smartTimetables.length > 0 && (
                  <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 mt-2">
                    <p className="text-xs text-amber-700 flex items-start gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                      سيتم إنشاء جدول جديد وستُحفظ الجداول السابقة ({smartTimetables.length}) في القائمة.
                    </p>
                  </div>
                )}
              </div>
            )}

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setGenerateDialogOpen(false)} disabled={generating} className="text-xs">
                إلغاء
              </Button>
              <Button
                onClick={handleGenerate}
                disabled={generating}
                className="bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] text-white gap-2 text-xs"
              >
                {generating
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <Play className="h-3.5 w-3.5" />}
                {generating ? 'جاري التوليد...' : 'بدء التوليد'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── RESULT DIALOG ───────────────────────────────────────────── */}
        <Dialog open={resultDialogOpen} onOpenChange={setResultDialogOpen}>
          <DialogContent className="max-w-lg" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {parseFloat(generationResult?.success_rate) >= 90
                  ? <CheckCircle2 className="h-6 w-6 text-emerald-600" />
                  : parseFloat(generationResult?.success_rate) >= 50
                  ? <AlertTriangle className="h-6 w-6 text-amber-600" />
                  : <AlertCircle className="h-6 w-6 text-red-600" />}
                نتيجة توليد الجدول
              </DialogTitle>
            </DialogHeader>

            {generationResult && (
              <div className="space-y-4">
                {/* SVG Progress Ring */}
                <div className="flex flex-col items-center py-3">
                  <div className="relative w-28 h-28">
                    <svg className="w-28 h-28 -rotate-90" viewBox="0 0 100 100">
                      <circle cx="50" cy="50" r="40" fill="none" stroke="#e2e8f0" strokeWidth="9" />
                      <circle
                        cx="50" cy="50" r="40" fill="none"
                        stroke={parseFloat(generationResult.success_rate) >= 90 ? '#10b981' : parseFloat(generationResult.success_rate) >= 50 ? '#f59e0b' : '#ef4444'}
                        strokeWidth="9"
                        strokeDasharray={`${(Math.min(parseFloat(generationResult.success_rate), 100) / 100) * 251.2} 251.2`}
                        strokeLinecap="round"
                        className="transition-all duration-1000"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-2xl font-bold text-slate-800">
                        {Math.round(parseFloat(generationResult.success_rate))}%
                      </span>
                    </div>
                  </div>
                  <p className="text-sm font-medium text-slate-500 mt-2">نسبة النجاح</p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200 text-center">
                    <p className="text-3xl font-bold text-emerald-700">{generationResult.sessions_created}</p>
                    <p className="text-xs text-emerald-600 mt-1">حصة جُدولت</p>
                  </div>
                  <div className={`p-4 rounded-xl border text-center ${generationResult.unplaced > 0 ? 'bg-amber-50 border-amber-200' : 'bg-emerald-50 border-emerald-200'}`}>
                    <p className={`text-3xl font-bold ${generationResult.unplaced > 0 ? 'text-amber-700' : 'text-emerald-700'}`}>
                      {generationResult.unplaced}
                    </p>
                    <p className={`text-xs mt-1 ${generationResult.unplaced > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                      غير مجدولة
                    </p>
                  </div>
                </div>

                {generationResult.unplaced === 0 ? (
                  <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    <p className="text-sm text-emerald-700 font-medium">تم توليد جميع الحصص بنجاح كامل!</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                      <p className="text-xs text-amber-700">
                        يوجد {generationResult.unplaced} حصة لم تُجدَّل بسبب نقص في المعلمين أو تجاوز الطاقة الاستيعابية.
                      </p>
                    </div>
                    {generationResult.capacity_issues?.length > 0 && (
                      <div className="max-h-40 overflow-y-auto space-y-1.5">
                        {generationResult.capacity_issues.map((issue, idx) => (
                          <div
                            key={idx}
                            className={`p-2.5 rounded-lg border text-xs ${
                              issue.severity === 'critical'
                                ? 'bg-red-50 border-red-200'
                                : 'bg-amber-50 border-amber-200'
                            }`}
                          >
                            <p className={`font-medium mb-1 ${issue.severity === 'critical' ? 'text-red-700' : 'text-amber-700'}`}>
                              {issue.severity === 'critical' ? '⛔' : '⚠️'} {issue.message_ar}
                            </p>
                            {issue.fix_ar && (
                              <p className="text-slate-600">
                                <span className="font-semibold">الحل: </span>{issue.fix_ar}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <DialogFooter>
              <Button
                onClick={() => setResultDialogOpen(false)}
                className="bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] text-white gap-2 text-xs w-full"
              >
                <Calendar className="h-3.5 w-3.5" />
                عرض الجدول
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── SESSION DETAIL DIALOG ────────────────────────────────────── */}
        <Dialog open={sessionDetailOpen} onOpenChange={setSessionDetailOpen}>
          <DialogContent className="max-w-sm" dir="rtl">
            {selectedSession && (() => {
              const palette  = SUBJECT_PALETTE[subjectColorIndex(selectedSession.subject_name)];
              const dayLabel = DAYS.find(d => d.key === (selectedSession.day_of_week || selectedSession.day))?.ar || '—';
              return (
                <>
                  {/* Colored header */}
                  <div className={`-mx-6 -mt-6 px-6 pt-6 pb-5 ${palette.bg} rounded-t-xl mb-4`}>
                    <h3 className={`font-bold text-xl ${palette.text} drop-shadow-sm`}>
                      {selectedSession.subject_name || 'مادة'}
                    </h3>
                    <p className={`text-sm opacity-80 ${palette.text}`}>تفاصيل الحصة الدراسية</p>
                  </div>
                  <div className="space-y-2.5">
                    {[
                      { label: 'الفصل الدراسي', value: selectedSession.class_name,    Icon: GraduationCap },
                      { label: 'المعلم',         value: selectedSession.teacher_name,  Icon: User },
                      { label: 'يوم الأسبوع',   value: dayLabel,                       Icon: Calendar },
                      { label: 'رقم الحصة',     value: `الحصة ${selectedSession.period_number || selectedSession.slot_number || '—'}`, Icon: BookOpen },
                      { label: 'الوقت',          value: `${selectedSession.start_time || '—'} — ${selectedSession.end_time || '—'}`, Icon: Clock },
                    ].map(({ label, value, Icon }) => (
                      <div key={label} className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                        <Icon className="h-4 w-4 text-slate-400 shrink-0" />
                        <div>
                          <p className="text-[10px] text-slate-400 leading-none">{label}</p>
                          <p className="text-sm font-semibold text-slate-800 mt-0.5">{value || '—'}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              );
            })()}
          </DialogContent>
        </Dialog>

        {/* ── PUBLISH CONFIRM ──────────────────────────────────────────── */}
        <Dialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
          <DialogContent className="max-w-sm" dir="rtl">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-emerald-700">
                <Send className="h-5 w-5" />
                نشر الجدول المدرسي
              </DialogTitle>
              <DialogDescription>
                بعد النشر سيصبح الجدول مرئياً لجميع المعلمين والطلاب. هذا الإجراء لا يمكن التراجع عنه.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setPublishDialogOpen(false)} className="text-xs">
                إلغاء
              </Button>
              <Button
                onClick={handlePublish}
                disabled={publishing}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 text-xs"
              >
                {publishing
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <Send className="h-3.5 w-3.5" />}
                نعم، نشر الجدول
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── CANDIDATES SIDE PANEL ─────────────────────────────────── */}
        <CandidatesSidePanel
          open={candidatesPanelOpen}
          onOpenChange={(o) => { setCandidatesPanelOpen(o); if (!o) setActiveSlot(null); }}
          slot={activeSlot}
          api={api}
          teachers={teachers}
          subjectsForClass={[]}
          onAssigned={handleSlotAssigned}
          onSkipNext={handleSkipToNextEmpty}
        />

      </div>
    </Sidebar>
  );
}
