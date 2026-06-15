import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { getDayBandClass, getDayTextOnBand, getDayTintClass } from '../../components/schedule/grid-theme';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Calendar, Clock, ChevronRight, ChevronLeft, BookOpen,
  Users, Loader2, RefreshCw, Printer, Download, Play,
  MapPin, AlertTriangle, Timer, CalendarDays, Eye
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
const DAYS = [
  { key: 'sunday', ar: 'الأحد', en: 'Sun', idx: 0 },
  { key: 'monday', ar: 'الاثنين', en: 'Mon', idx: 1 },
  { key: 'tuesday', ar: 'الثلاثاء', en: 'Tue', idx: 2 },
  { key: 'wednesday', ar: 'الأربعاء', en: 'Wed', idx: 3 },
  { key: 'thursday', ar: 'الخميس', en: 'Thu', idx: 4 },
];

const SUBJECT_COLORS = {
  'اللغة العربية': 'bg-blue-100 border-blue-300 text-blue-800 dark:bg-blue-900/40 dark:border-blue-700 dark:text-blue-200',
  'الرياضيات': 'bg-green-100 border-green-300 text-green-800 dark:bg-green-900/40 dark:border-green-700 dark:text-green-200',
  'العلوم': 'bg-purple-100 border-purple-300 text-purple-800 dark:bg-purple-900/40 dark:border-purple-700 dark:text-purple-200',
  'اللغة الإنجليزية': 'bg-red-100 border-red-300 text-red-800 dark:bg-red-900/40 dark:border-red-700 dark:text-red-200',
  'الدراسات الاجتماعية': 'bg-amber-100 border-amber-300 text-amber-800 dark:bg-amber-900/40 dark:border-amber-700 dark:text-amber-200',
  'التربية الإسلامية': 'bg-emerald-100 border-emerald-300 text-emerald-800 dark:bg-emerald-900/40 dark:border-emerald-700 dark:text-emerald-200',
  'الحاسب الآلي': 'bg-cyan-100 border-cyan-300 text-cyan-800 dark:bg-cyan-900/40 dark:border-cyan-700 dark:text-cyan-200',
  'default': 'bg-gray-100 border-gray-300 text-gray-800 dark:bg-gray-800/40 dark:border-gray-600 dark:text-gray-200'
};

const JS_DAY_TO_KEY = { 0: 'sunday', 1: 'monday', 2: 'tuesday', 3: 'wednesday', 4: 'thursday' };

function getTodayDayKey() {
  const jsDay = new Date().getDay();
  return JS_DAY_TO_KEY[jsDay] || null;
}

function dateToDayKey(date) {
  return JS_DAY_TO_KEY[date.getDay()] || null;
}

function parseTime(timeStr) {
  if (!timeStr) return null;
  const parts = timeStr.split(':');
  return parseInt(parts[0]) * 60 + parseInt(parts[1]);
}

function getNowMinutes() {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

function getSessionStatus(session, dayKey) {
  const todayKey = getTodayDayKey();
  if (session.day_of_week !== todayKey || dayKey !== todayKey) return 'upcoming';
  const now = getNowMinutes();
  const start = parseTime(session.start_time);
  const end = parseTime(session.end_time);
  if (start === null || end === null) return 'upcoming';
  if (now > end) return 'completed';
  if (now >= start && now <= end) return 'current';
  return 'upcoming';
}

const STATUS_BADGES = {
  current: { label: 'الحصة الحالية', en: 'Current', className: 'bg-green-500 text-white animate-pulse' },
  upcoming: { label: 'قادمة', en: 'Upcoming', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  completed: { label: 'مكتملة', en: 'Completed', className: 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300' },
};

export default function TeacherSchedulePage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState([]);
  const [timeSlots, setTimeSlots] = useState([]);
  const [view, setView] = useState('weekly');
  const [selectedDay, setSelectedDay] = useState(getTodayDayKey() || 'sunday');
  const [selectedDate, setSelectedDate] = useState('');
  const [showDetail, setShowDetail] = useState(false);
  const [detailSession, setDetailSession] = useState(null);
  const [tick, setTick] = useState(0);
  const [scheduleVersion, setScheduleVersion] = useState(null);
  const [scheduleChanged, setScheduleChanged] = useState(false);
  const [monthDate, setMonthDate] = useState(new Date());
  const prevScheduleRef = useRef(null);

  const { nassaqError } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;
  const todayKey = getTodayDayKey();

  const fetchSchedule = useCallback(async ({ silent = false } = {}) => {
    if (!teacherId) return;
    // Task #145 — when refreshing in the background (WS-triggered or
    // poll-triggered) and we already have data on screen, skip the
    // skeleton/loading flash so the update is truly silent.
    const hasExistingData = (prevScheduleRef.current?.length || 0) > 0;
    if (!silent || !hasExistingData) setLoading(true);
    try {
      const [scheduleRes, slotsRes] = await Promise.all([
        api.get(`/teacher/schedule/${teacherId}`).catch(() => ({ data: [] })),
        api.get('/time-slots').catch(() => ({ data: [] }))
      ]);
      const newSchedule = scheduleRes.data || [];
      const newSlots = (slotsRes.data || []).filter(s => !s.is_break);
      
      if (prevScheduleRef.current !== null) {
        const hashSchedule = (list) => JSON.stringify(
          list.map(s => `${s.id}|${s.day_of_week}|${s.start_time}|${s.end_time}|${s.class_id}|${s.subject_name}|${s.room_name}`).sort()
        );
        if (hashSchedule(prevScheduleRef.current) !== hashSchedule(newSchedule)) {
          setScheduleChanged(true);
        }
      }
      prevScheduleRef.current = newSchedule;
      setSchedule(newSchedule);
      setTimeSlots(newSlots);
      setScheduleVersion(Date.now());
    } catch (error) {
      console.error('Error fetching schedule:', error);
      nassaqError(t('errorLoadingSchedule'));
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, nassaqError, t]);

  useEffect(() => { fetchSchedule(); }, [fetchSchedule]);

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const id = setInterval(() => fetchSchedule({ silent: true }), 300000);
    return () => clearInterval(id);
  }, [fetchSchedule]);

  // Task #145 — listen for the tenant-wide ``schedule_published`` WS event
  // bridged through WebSocketContext and silently refetch. This is what
  // makes a teacher see new periods within seconds of an admin publishing,
  // instead of waiting up to 5 minutes for the polling fallback. We pass
  // ``silent: true`` so the existing schedule stays on screen and we never
  // show a skeleton flash — the diff is computed against the previous
  // payload and surfaced via the existing "schedule changed" badge.
  useEffect(() => {
    const onPublished = () => { fetchSchedule({ silent: true }); };
    window.addEventListener('nassaq:schedule_published', onPublished);
    return () => window.removeEventListener('nassaq:schedule_published', onPublished);
  }, [fetchSchedule]);

  const getSessionsForCell = (day, slotId, slotNumber, slotStartTime) => {
    return schedule.filter(s => {
      if (s.day_of_week !== day) return false;
      if (s.time_slot_id && s.time_slot_id === slotId) return true;
      const sPeriod = s.slot_number || s.period_number;
      if (sPeriod && slotNumber && sPeriod === slotNumber) return true;
      if (s.start_time && slotStartTime && s.start_time.slice(0,5) === slotStartTime.slice(0,5)) return true;
      return false;
    });
  };

  const getSubjectColor = (subjectName) => SUBJECT_COLORS[subjectName] || SUBJECT_COLORS.default;

  const todaySessions = useMemo(() => {
    return schedule.filter(s => s.day_of_week === todayKey)
      .sort((a, b) => (a.slot_number || a.period_number || 0) - (b.slot_number || b.period_number || 0));
  }, [schedule, todayKey]);

  const currentSession = useMemo(() => {
    void tick; // eslint-disable-line react-hooks/exhaustive-deps
    const now = getNowMinutes();
    return todaySessions.find(s => {
      const start = parseTime(s.start_time);
      const end = parseTime(s.end_time);
      return start !== null && end !== null && now >= start && now <= end;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [todaySessions, tick]);

  const nextSession = useMemo(() => {
    void tick; // eslint-disable-line react-hooks/exhaustive-deps
    const now = getNowMinutes();
    return todaySessions.find(s => {
      const start = parseTime(s.start_time);
      return start !== null && start > now;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [todaySessions, tick]);

  const countdown = useMemo(() => {
    void tick; // eslint-disable-line react-hooks/exhaustive-deps
    if (!nextSession) return null;
    const start = parseTime(nextSession.start_time);
    const now = getNowMinutes();
    const diff = start - now;
    if (diff <= 0) return null;
    const h = Math.floor(diff / 60);
    const m = diff % 60;
    if (isRTL) return h > 0 ? `${h} ساعة و ${m} دقيقة` : `${m} دقيقة`;
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextSession, tick]);

  const conflicts = useMemo(() => {
    const found = [];
    for (const day of DAYS) {
      const daySessions = schedule.filter(s => s.day_of_week === day.key);
      for (let i = 0; i < daySessions.length; i++) {
        for (let j = i + 1; j < daySessions.length; j++) {
          const a = daySessions[i], b = daySessions[j];
          const aStart = parseTime(a.start_time), aEnd = parseTime(a.end_time);
          const bStart = parseTime(b.start_time), bEnd = parseTime(b.end_time);
          if (aStart !== null && aEnd !== null && bStart !== null && bEnd !== null) {
            if (aStart < bEnd && bStart < aEnd) {
              found.push({ day: day.key, sessionA: a, sessionB: b });
            }
          }
        }
      }
    }
    return found;
  }, [schedule]);

  const handleStartSession = (session) => {
    const lesson = {
      schedule_session_id: session.schedule_session_id || session.id,
      subject: session.subject_name,
      className: session.class_name,
      classId: session.class_id,
      subjectId: session.subject_id,
      period: session.slot_number || session.period_number,
      time: session.start_time ? `${session.start_time?.slice(0,5)} - ${session.end_time?.slice(0,5)}` : '',
    };
    const lessonData = {
      lesson,
      schedule_session_id: lesson.schedule_session_id,
      class_id: lesson.classId,
      subject_id: lesson.subjectId,
    };
    sessionStorage.setItem('current_lesson', JSON.stringify(lessonData));
    navigate('/teacher/session/start', { state: lessonData });
  };

  const handlePrint = () => {
    const esc = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    const dayName = (key) => DAYS.find(d => d.key === key)?.[isRTL ? 'ar' : 'en'] || key;
    const sortedSchedule = [...schedule].sort((a, b) => {
      const dayOrder = DAYS.map(d => d.key);
      const dayDiff = dayOrder.indexOf(a.day_of_week) - dayOrder.indexOf(b.day_of_week);
      if (dayDiff !== 0) return dayDiff;
      return (a.period_number || a.slot_number || 0) - (b.period_number || b.slot_number || 0);
    });
    const groupedByDay = {};
    sortedSchedule.forEach(s => {
      const day = s.day_of_week;
      if (!groupedByDay[day]) groupedByDay[day] = [];
      groupedByDay[day].push(s);
    });
    const tableRows = sortedSchedule.map(s => `
      <tr>
        <td>${esc(dayName(s.day_of_week))}</td>
        <td>${esc(s.period_number || s.slot_number || '')}</td>
        <td>${esc(s.subject_name || '')}</td>
        <td>${esc(s.class_name || '')}</td>
        <td>${esc(s.room_name || '—')}</td>
        <td>${esc(s.start_time?.slice(0,5) || '')}</td>
        <td>${esc(s.end_time?.slice(0,5) || '')}</td>
      </tr>
    `).join('');
    // SECURITY (audit L-1): use a Blob URL + DOM APIs instead of
    // `printWindow.document.write(...)`. The HTML payload is built with
    // pre-escaped strings, but document.write is on the lint denylist as
    // a high-risk sink class — this version is equivalent and avoids it.
    const html =
      `<!doctype html><html dir="${isRTL ? 'rtl' : 'ltr'}"><head>` +
      `<meta charset="utf-8"><title>${esc(t('mySchedule'))}</title>` +
      `<style>` +
      `body{font-family:'Cairo','Segoe UI',Tahoma,sans-serif;padding:20px;direction:${isRTL ? 'rtl' : 'ltr'};}` +
      `h1{text-align:center;color:#1E3A5F;margin-bottom:5px;}` +
      `p.subtitle{text-align:center;color:#666;margin-bottom:20px;}` +
      `table{width:100%;border-collapse:collapse;}` +
      `th{background:#1E3A5F;color:white;padding:10px 8px;font-size:14px;}` +
      `td{padding:8px;border:1px solid #ddd;text-align:center;font-size:13px;}` +
      `tr:nth-child(even){background:#f8fafc;}` +
      `@media print{body{padding:0;}}` +
      `</style></head><body>` +
      `<h1>${esc(t('mySchedule2'))}</h1>` +
      `<p class="subtitle">${esc(t('nassaq2'))} — ${esc(new Date().toLocaleDateString(isRTL ? 'ar-SA' : 'en-US'))}</p>` +
      `<table><thead><tr>` +
      `<th>${esc(isRTL ? 'اليوم' : 'Day')}</th>` +
      `<th>${esc(isRTL ? 'الحصة' : 'Period')}</th>` +
      `<th>${esc(t('subject'))}</th>` +
      `<th>${esc(t('class'))}</th>` +
      `<th>${esc(t('room2'))}</th>` +
      `<th>${esc(t('start'))}</th>` +
      `<th>${esc(t('end'))}</th>` +
      `</tr></thead><tbody>${tableRows}</tbody></table>` +
      `<script>setTimeout(function(){window.print();},300);</script>` +
      `</body></html>`;
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const printWindow = window.open(url, '_blank');
    if (!printWindow) {
      URL.revokeObjectURL(url);
      toast.success(t('pleaseAllowPopupsToPrint'));
      return;
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  const handleExport = () => {
    const escapeCSV = (val) => {
      const str = String(val ?? '');
      if (str.includes(',') || str.includes('"') || str.includes('\n')) return `"${str.replace(/"/g, '""')}"`;
      return str;
    };
    const dayName = (key) => DAYS.find(d => d.key === key)?.[isRTL ? 'ar' : 'en'] || key;
    const rows = [
      [isRTL ? 'اليوم' : 'Day', isRTL ? 'الحصة' : 'Period', t('subject'), t('class'), t('room2'), t('start'), t('end')],
      ...schedule.map(s => [
        dayName(s.day_of_week),
        s.slot_number || s.period_number || '',
        s.subject_name || '',
        s.class_name || '',
        s.room_name || '—',
        s.start_time?.slice(0,5) || '',
        s.end_time?.slice(0,5) || ''
      ])
    ];
    const csv = '\uFEFF' + rows.map(r => r.map(escapeCSV).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `my-schedule-${new Date().toISOString().slice(0,10)}.csv`;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
    toast.success(t('scheduleExported'));
  };

  const handleDatePick = (e) => {
    const val = e.target.value;
    setSelectedDate(val);
    if (val) {
      const d = new Date(val);
      const dayKey = dateToDayKey(d);
      if (dayKey) {
        setSelectedDay(dayKey);
        setView('daily');
      } else {
        toast.success(t('thisIsAWeekendDay'));
      }
    }
  };

  const monthDays = useMemo(() => {
    const year = monthDate.getFullYear();
    const month = monthDate.getMonth();
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    const days = [];
    const startPad = first.getDay();
    for (let i = 0; i < startPad; i++) days.push(null);
    for (let d = 1; d <= last.getDate(); d++) {
      const date = new Date(year, month, d);
      const jsDay = date.getDay();
      if (jsDay === 5 || jsDay === 6) {
        days.push({ date: d, dayKey: null, sessions: [], isWeekend: true });
      } else {
        const dayKey = DAYS[jsDay === 0 ? 0 : jsDay - 1]?.key;
        const daySessions = schedule.filter(s => s.day_of_week === dayKey);
        days.push({ date: d, dayKey, sessions: daySessions, isWeekend: false });
      }
    }
    return days;
  }, [monthDate, schedule]);

  const isWeekend = todayKey === null;
  const noSessionsToday = todaySessions.length === 0;

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 print:bg-white" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4 print:static print:bg-white">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('mySchedule')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('viewAndManageMyClassSchedule')}
              </p>
            </div>
            <div className="flex items-center gap-2 print:hidden">
              <input
                type="date"
                value={selectedDate}
                onChange={handleDatePick}
                className="h-9 px-3 rounded-md border border-input bg-background text-sm"
              />
              <Button variant="outline" size="sm" onClick={fetchSchedule} disabled={loading}>
                <RefreshCw className={`h-4 w-4 me-1 ${loading ? 'animate-spin' : ''}`} />
                {t('refresh')}
              </Button>
              <Button variant="outline" size="sm" onClick={handlePrint}>
                <Printer className="h-4 w-4 me-1" />
                {t('print')}
              </Button>
              <Button variant="outline" size="sm" onClick={handleExport}>
                <Download className="h-4 w-4 me-1" />
                {t('export')}
              </Button>
            </div>
          </div>
        </div>

        <div className="p-4 space-y-4">
          {scheduleChanged && (
            <div className="bg-amber-50 dark:bg-amber-900/30 border border-amber-300 dark:border-amber-700 rounded-xl p-3 flex items-center justify-between print:hidden">
              <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
                <AlertTriangle className="h-5 w-5" />
                <span className="text-sm font-cairo font-bold">{t('scheduleHasBeenUpdated')}</span>
              </div>
              <Button size="sm" variant="outline" onClick={() => setScheduleChanged(false)}>
                {t('dismiss')}
              </Button>
            </div>
          )}

          {conflicts.length > 0 && (
            <div className="bg-red-50 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-xl p-3 print:hidden">
              <div className="flex items-center gap-2 text-red-700 dark:text-red-300 mb-1">
                <AlertTriangle className="h-5 w-5" />
                <span className="text-sm font-cairo font-bold">
                  {isRTL ? `تعارض في ${conflicts.length} حصة` : `${conflicts.length} schedule conflict(s)`}
                </span>
              </div>
              {conflicts.map((c, i) => (
                <p key={i} className="text-xs text-red-600 dark:text-red-400">
                  {DAYS.find(d => d.key === c.day)?.ar}: {c.sessionA.subject_name} ↔ {c.sessionB.subject_name}
                </p>
              ))}
            </div>
          )}

          {(currentSession || nextSession) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 print:hidden">
              {currentSession && (
                <Card className="border-2 border-green-400 dark:border-green-600 bg-green-50 dark:bg-green-900/20 shadow-lg shadow-green-200/40 dark:shadow-green-900/20">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className="bg-green-500 text-white animate-pulse">{isRTL ? 'الحصة الحالية' : 'Current Session'}</Badge>
                    </div>
                    <h3 className="font-cairo font-bold text-lg text-green-800 dark:text-green-200">{currentSession.subject_name}</h3>
                    <div className="flex items-center gap-4 text-sm text-green-700 dark:text-green-300 mt-1">
                      <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{currentSession.class_name}</span>
                      <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{currentSession.start_time?.slice(0,5)} - {currentSession.end_time?.slice(0,5)}</span>
                      {currentSession.room_name && <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{currentSession.room_name}</span>}
                    </div>
                    <Button size="sm" className="mt-3 bg-green-600 hover:bg-green-700 text-white" onClick={() => handleStartSession(currentSession)}>
                      <Play className="h-4 w-4 me-1" />
                      {isRTL ? 'ابدأ الحصة' : 'Start Session'}
                    </Button>
                  </CardContent>
                </Card>
              )}

              {nextSession && (
                <Card className="border-2 border-blue-300 dark:border-blue-600 bg-blue-50 dark:bg-blue-900/20">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge className="bg-blue-500 text-white">{t('nextSession')}</Badge>
                      {countdown && (
                        <span className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                          <Timer className="h-3.5 w-3.5" />
                          {isRTL ? `بعد ${countdown}` : `in ${countdown}`}
                        </span>
                      )}
                    </div>
                    <h3 className="font-cairo font-bold text-lg text-blue-800 dark:text-blue-200">{nextSession.subject_name}</h3>
                    <div className="flex items-center gap-4 text-sm text-blue-700 dark:text-blue-300 mt-1">
                      <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{nextSession.class_name}</span>
                      <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{nextSession.start_time?.slice(0,5)} - {nextSession.end_time?.slice(0,5)}</span>
                      {nextSession.room_name && <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{nextSession.room_name}</span>}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {(noSessionsToday || isWeekend) && !loading && (
            <Card className="border-dashed border-2 print:hidden">
              <CardContent className="p-6 text-center">
                <Calendar className="h-10 w-10 mx-auto mb-2 text-muted-foreground/40" />
                <p className="text-muted-foreground font-cairo">
                  {isWeekend
                    ? (t('todayIsAWeekend'))
                    : (t('noSessionsToday'))}
                </p>
              </CardContent>
            </Card>
          )}

          <div className="flex items-center justify-between print:hidden">
            <Tabs value={view} onValueChange={setView}>
              <TabsList>
                <TabsTrigger value="weekly">{t('weekly')}</TabsTrigger>
                <TabsTrigger value="daily">{t('daily2')}</TabsTrigger>
                <TabsTrigger value="monthly">{t('monthly')}</TabsTrigger>
              </TabsList>
            </Tabs>

            {view === 'daily' && (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" onClick={() => {
                  const idx = DAYS.findIndex(d => d.key === selectedDay);
                  setSelectedDay(DAYS[(idx - 1 + DAYS.length) % DAYS.length].key);
                }}><ChevronRight className="h-4 w-4" /></Button>
                <span className="font-medium min-w-[80px] text-center font-cairo">
                  {DAYS.find(d => d.key === selectedDay)?.[isRTL ? 'ar' : 'en']}
                </span>
                <Button variant="ghost" size="icon" onClick={() => {
                  const idx = DAYS.findIndex(d => d.key === selectedDay);
                  setSelectedDay(DAYS[(idx + 1) % DAYS.length].key);
                }}><ChevronLeft className="h-4 w-4" /></Button>
              </div>
            )}

            {view === 'monthly' && (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="icon" onClick={() => setMonthDate(d => new Date(d.getFullYear(), d.getMonth() - 1, 1))}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <span className="font-medium min-w-[120px] text-center font-cairo">
                  {monthDate.toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', { month: 'long', year: 'numeric' })}
                </span>
                <Button variant="ghost" size="icon" onClick={() => setMonthDate(d => new Date(d.getFullYear(), d.getMonth() + 1, 1))}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : view === 'monthly' ? (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead className="bg-muted/50">
                    <tr>
                      {[
                        t('sun'),
                        t('mon'),
                        t('tue'),
                        t('wed'),
                        t('thu'),
                        t('fri'),
                        t('sat'),
                      ].map(d => (
                        <th key={d} className="p-2 text-center text-xs font-medium border-b">{d}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: Math.ceil(monthDays.length / 7) }).map((_, weekIdx) => (
                      <tr key={weekIdx}>
                        {Array.from({ length: 7 }).map((_, dayIdx) => {
                          const cell = monthDays[weekIdx * 7 + dayIdx];
                          if (!cell) return <td key={dayIdx} className="p-2 border-b h-20 bg-muted/10" />;
                          const isToday = cell.date === new Date().getDate() && monthDate.getMonth() === new Date().getMonth() && monthDate.getFullYear() === new Date().getFullYear();
                          return (
                            <td key={dayIdx} className={`p-2 border-b h-20 align-top transition-colors ${cell.isWeekend ? 'bg-muted/20' : 'hover:bg-muted/10 cursor-pointer'} ${isToday ? 'bg-brand-turquoise/10' : ''}`}
                              onClick={() => {
                                if (!cell.isWeekend && cell.dayKey) {
                                  setSelectedDay(cell.dayKey);
                                  setView('daily');
                                }
                              }}
                            >
                              <div className="flex flex-col items-center gap-1">
                                <span className={`text-sm font-medium ${isToday ? 'text-brand-turquoise font-bold' : ''}`}>{cell.date}</span>
                                {cell.sessions.length > 0 && (
                                  <Badge variant="outline" className="text-[10px] px-1.5">{cell.sessions.length} {isRTL ? 'حصة' : 'cls'}</Badge>
                                )}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : timeSlots.length === 0 ? (
            <Card>
              <CardContent className="text-center py-16">
                <Calendar className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <p className="text-muted-foreground">{t('noScheduleAvailable2')}</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="overflow-hidden" data-testid="schedule-grid">
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="p-3 text-start border-b min-w-[80px]">
                        <div className="flex items-center gap-2">
                          <Clock className="h-4 w-4" />
                          {isRTL ? 'الحصة' : 'Period'}
                        </div>
                      </th>
                      {(view === 'weekly' ? DAYS : [DAYS.find(d => d.key === selectedDay)]).map(day => (
                        <th
                          key={day.key}
                          className={`p-2 text-center border-b border-s min-w-[100px] sm:min-w-[150px] ${getDayBandClass(day.key)} ${getDayTextOnBand(day.key)} font-cairo font-bold`}
                        >
                          <span>{isRTL ? day.ar : day.en}</span>
                          {day.key === todayKey && (
                            <Badge variant="outline" className="ms-2 text-[10px] bg-white/30 text-white border-white/40">{t('today2')}</Badge>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {timeSlots.map((slot, idx) => (
                      <tr key={slot.id} className={idx % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-muted/20'}>
                        <td className="p-3 border-b">
                          <div className="text-sm font-medium">{isRTL ? `الحصة ${['الأولى','الثانية','الثالثة','الرابعة','الخامسة','السادسة','السابعة','الثامنة','التاسعة','العاشرة'][idx] || (idx + 1)}` : `Period ${idx + 1}`}</div>
                          <div className="text-xs text-muted-foreground">{slot.start_time?.slice(0,5)} - {slot.end_time?.slice(0,5)}</div>
                        </td>
                        {(view === 'weekly' ? DAYS : [DAYS.find(d => d.key === selectedDay)]).map(day => {
                          const sessions = getSessionsForCell(day.key, slot.id, slot.slot_number || slot.period_number, slot.start_time);
                          return (
                            <td key={`${day.key}-${slot.id}`} className={`p-2 border-b border-s min-h-[80px] ${getDayTintClass(day.key)} ${day.key === todayKey ? 'ring-1 ring-inset ring-brand-turquoise/30' : ''}`}>
                              {sessions.length > 0 ? (
                                <div className="space-y-1">
                                  {sessions.map(session => {
                                    const status = getSessionStatus(session, day.key);
                                    const isCurrent = status === 'current';
                                    return (
                                      <div
                                        key={session.id}
                                        onClick={() => { setDetailSession(session); setShowDetail(true); }}
                                        className={`p-2 rounded-lg border-2 cursor-pointer transition-all hover:shadow-md ${getSubjectColor(session.subject_name)} ${isCurrent ? 'ring-2 ring-green-400 shadow-lg shadow-green-200/40' : ''}`}
                                      >
                                        <div className="flex items-center gap-2">
                                          <BookOpen className="h-4 w-4 flex-shrink-0" />
                                          <div className="min-w-0 flex-1">
                                            <p className="font-medium text-sm truncate">{session.subject_name}</p>
                                            <div className="flex items-center gap-1.5 text-xs opacity-70 flex-wrap">
                                              <span className="flex items-center gap-0.5"><Users className="h-3 w-3" />{session.class_name}</span>
                                              {session.room_name && <span className="flex items-center gap-0.5"><MapPin className="h-3 w-3" />{session.room_name}</span>}
                                            </div>
                                          </div>
                                        </div>
                                        {isCurrent && (
                                          <div className="flex items-center gap-2 mt-1.5">
                                            <Badge className="bg-green-500 text-white text-[10px] animate-pulse">{t('now')}</Badge>
                                            <Button size="sm" className="flex-1 h-7 text-xs bg-brand-navy hover:bg-brand-navy/90" onClick={(e) => { e.stopPropagation(); handleStartSession(session); }}>
                                              <Play className="h-3 w-3 me-1" />
                                              {t('start2')}
                                            </Button>
                                          </div>
                                        )}
                                        {status === 'completed' && (
                                          <Badge className="mt-1 bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300 text-[10px]">{isRTL ? 'مكتملة' : 'Done'}</Badge>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <div className="h-16 border-2 border-dashed border-muted-foreground/20 rounded-lg flex items-center justify-center text-muted-foreground/50 text-xs">
                                  {t('empty')}
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 print:hidden">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-brand-navy dark:text-brand-turquoise">{schedule.length}</div>
                <div className="text-sm text-muted-foreground">{t('totalSessions')}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-brand-turquoise">{todaySessions.length}</div>
                <div className="text-sm text-muted-foreground">{t('todaysSessions')}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-green-600">{[...new Set(schedule.map(s => s.class_id))].length}</div>
                <div className="text-sm text-muted-foreground">{t('classes6')}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-bold text-purple-600">{[...new Set(schedule.map(s => s.subject_name))].length}</div>
                <div className="text-sm text-muted-foreground">{t('subjects6')}</div>
              </CardContent>
            </Card>
          </div>
        </div>

        <Dialog open={showDetail} onOpenChange={setShowDetail}>
          <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
            <DialogHeader>
              <DialogTitle className="font-cairo">{t('sessionDetails')}</DialogTitle>
            </DialogHeader>
            {detailSession && (
              <div className="space-y-4">
                <div className={`p-4 rounded-xl border-2 ${getSubjectColor(detailSession.subject_name)}`}>
                  <h3 className="text-lg font-bold font-cairo flex items-center gap-2">
                    <BookOpen className="h-5 w-5" />
                    {detailSession.subject_name}
                  </h3>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-muted/50 rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><Users className="h-3 w-3" />{t('class')}</div>
                    <div className="font-medium text-sm">{detailSession.class_name}</div>
                  </div>
                  <div className="bg-muted/50 rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><Clock className="h-3 w-3" />{t('time2')}</div>
                    <div className="font-medium text-sm">{detailSession.start_time?.slice(0,5)} - {detailSession.end_time?.slice(0,5)}</div>
                  </div>
                  <div className="bg-muted/50 rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><MapPin className="h-3 w-3" />{t('room2')}</div>
                    <div className="font-medium text-sm">{detailSession.room_name || '—'}</div>
                  </div>
                  <div className="bg-muted/50 rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1 flex items-center gap-1"><CalendarDays className="h-3 w-3" />{isRTL ? 'اليوم' : 'Day'}</div>
                    <div className="font-medium text-sm">{DAYS.find(d => d.key === detailSession.day_of_week)?.[isRTL ? 'ar' : 'en']}</div>
                  </div>
                </div>
                <Button className="w-full bg-brand-navy hover:bg-brand-navy/90 text-white" onClick={() => { setShowDetail(false); handleStartSession(detailSession); }}>
                  <Play className="h-4 w-4 me-2" />
                  {isRTL ? 'ابدأ الحصة' : 'Start Session'}
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
