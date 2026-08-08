import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  Loader2,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const dateOnly = (d) => (d ? String(d).slice(0, 10) : '');

export default function InlineAttendanceTable({
  classId,
  students = [],
  classData = null,
  onStatusChange,
  showHistory = true,
  sessionId = null,
}) {
  const { t } = useTranslation();
  const { api, isRTL } = useAuth();
  const [attendanceRecords, setAttendanceRecords] = useState([]);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [togglingStudentId, setTogglingStudentId] = useState(null);
  const [historyStudent, setHistoryStudent] = useState(null);
  // When rendered inside a live class session, the persisted truth for today's
  // status is the canonical `session_attendance` store (driven by the session
  // endpoints), not the school-wide daily `attendance` table. We track the
  // session-scoped status locally and seed it from the roster the parent
  // provides (server-sourced `attendance_status`).
  const sessionMode = !!sessionId;
  const [sessionStatus, setSessionStatus] = useState({});

  const todayISO = useMemo(() => new Date().toISOString().split('T')[0], []);

  useEffect(() => {
    if (!sessionMode) return;
    setSessionStatus((prev) => {
      const next = { ...prev };
      students.forEach((s) => {
        if (s?.id != null && next[s.id] === undefined && s.attendance_status) {
          next[s.id] = s.attendance_status;
        }
      });
      return next;
    });
  }, [sessionMode, students]);

  const fetchAttendanceData = useCallback(async () => {
    if (!classId) return;
    setAttendanceLoading(true);
    try {
      const res = await api.get(
        `/attendance/class/${classId}?start_date=2024-01-01&end_date=2030-12-31`,
      );
      const records = Array.isArray(res.data) ? res.data : [];
      setAttendanceRecords(records);
    } catch (err) {
      console.error('Error loading attendance:', err);
    } finally {
      setAttendanceLoading(false);
    }
  }, [api, classId]);

  useEffect(() => {
    fetchAttendanceData();
  }, [fetchAttendanceData]);

  const handleToggleAttendance = async (studentId, newStatus) => {
    if (!studentId) return;
    if (sessionMode) {
      if (!sessionId) return;
    } else if (!classId) {
      return;
    }
    setTogglingStudentId(studentId);
    try {
      if (sessionMode) {
        // Live-session register: persist to the canonical session-attendance
        // store (live roster, live metrics, end-session summary, lesson report).
        // The backend now also writes this status THROUGH to the canonical
        // daily `attendance` table immediately, so the daily page and the
        // class-detail inline table reflect it with no approval step.
        await api.put(`/session/${sessionId}/attendance/${studentId}`, {
          status: newStatus,
        });
        setSessionStatus((prev) => ({ ...prev, [studentId]: newStatus }));
        // Re-read the canonical daily records so the present/absent counters in
        // this register never show stale values after a toggle.
        fetchAttendanceData();
      } else {
        await api.post('/attendance/bulk', {
          class_id: classId,
          date: todayISO,
          records: [{ student_id: studentId, status: newStatus }],
        });
        setAttendanceRecords((prev) => {
          const filtered = prev.filter(
            (r) => !(r.student_id === studentId && dateOnly(r.date) === todayISO),
          );
          return [...filtered, { student_id: studentId, date: todayISO, status: newStatus }];
        });
      }
      toast.success(
        newStatus === 'present' ? t('markedPresent') : t('markedAbsent'),
      );
      if (typeof onStatusChange === 'function') {
        onStatusChange(studentId, newStatus, todayISO);
      }
    } catch (err) {
      console.error('Failed to toggle attendance', err);
      const detail =
        getApiErrorMessage(err) || err?.message || t('saveFailed') || 'فشل الحفظ';
      toast.error(detail);
    } finally {
      setTogglingStudentId(null);
    }
  };

  const attendanceByStudent = useMemo(() => {
    const map = {};
    students.forEach((s) => {
      map[s.id] = {
        student: s,
        presentCount: 0,
        absentCount: 0,
        todayStatus: null,
        records: [],
      };
    });
    attendanceRecords.forEach((r) => {
      const entry = map[r.student_id];
      if (!entry) return;
      entry.records.push(r);
      if (r.status === 'present' || r.status === 'late') entry.presentCount += 1;
      else if (r.status === 'absent') entry.absentCount += 1;
      if (dateOnly(r.date) === todayISO) entry.todayStatus = r.status;
    });
    if (sessionMode) {
      // In a live session, today's toggle reflects the canonical session
      // status, not the daily-table record. Default to present (drafts start
      // present) when nothing is known yet.
      Object.values(map).forEach((entry) => {
        const sid = entry.student?.id;
        entry.todayStatus =
          sessionStatus[sid] ?? entry.student?.attendance_status ?? 'present';
      });
    }
    Object.values(map).forEach((entry) => {
      entry.records.sort((a, b) => dateOnly(b.date).localeCompare(dateOnly(a.date)));
    });
    return Object.values(map);
  }, [students, attendanceRecords, todayISO, sessionMode, sessionStatus]);

  const renderHistoryDialog = () => {
    const records = historyStudent?.records || [];
    const presentCount = records.filter((r) => r.status === 'present').length;
    const absentCount = records.filter((r) => r.status === 'absent').length;
    const lateCount = records.filter((r) => r.status === 'late').length;
    const excusedCount = records.filter((r) => r.status === 'excused').length;
    const attended = presentCount + lateCount;
    const totalRecorded = attended + absentCount + excusedCount;
    const rate = totalRecorded > 0 ? Math.round((attended / totalRecorded) * 100) : 0;

    const classLine = [
      classData?.grade_name,
      classData?.section ? `${classData.section}` : null,
    ]
      .filter(Boolean)
      .join(' - ');

    return (
      <Dialog
        open={!!historyStudent}
        onOpenChange={(open) => {
          if (!open) setHistoryStudent(null);
        }}
      >
        <DialogContent
          className="max-w-md max-h-[85vh] overflow-y-auto p-0 gap-0 border-0 shadow-2xl"
          dir={isRTL ? 'rtl' : 'ltr'}
        >
          <DialogHeader className="px-6 pt-6 pb-4 text-center space-y-1">
            <DialogTitle className="font-cairo text-xl font-bold text-foreground">
              {historyStudent?.student?.full_name || ''}
            </DialogTitle>
            {classLine && (
              <p className="text-xs text-muted-foreground font-cairo">{classLine}</p>
            )}
          </DialogHeader>

          <div className="px-6 pb-2">
            <div className="grid grid-cols-4 gap-2">
              <div className="rounded-xl border border-emerald-200/60 dark:border-emerald-900/40 bg-emerald-50/60 dark:bg-emerald-950/20 p-3 text-center">
                <div className="text-xl font-bold text-emerald-600 tabular-nums font-cairo">
                  {rate}%
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5 font-cairo">
                  {t('attendanceRate') || 'نسبة الحضور'}
                </div>
              </div>
              <div className="rounded-xl border border-amber-200/60 dark:border-amber-900/40 bg-amber-50/60 dark:bg-amber-950/20 p-3 text-center">
                <div className="text-xl font-bold text-amber-600 tabular-nums font-cairo">
                  {lateCount}
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5 font-cairo">
                  {t('late') || 'متأخر'}
                </div>
              </div>
              <div className="rounded-xl border border-red-200/60 dark:border-red-900/40 bg-red-50/60 dark:bg-red-950/20 p-3 text-center">
                <div className="text-xl font-bold text-red-600 tabular-nums font-cairo">
                  {absentCount}
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5 font-cairo">
                  {t('absent') || 'غائب'}
                </div>
              </div>
              <div className="rounded-xl border border-emerald-200/60 dark:border-emerald-900/40 bg-emerald-50/60 dark:bg-emerald-950/20 p-3 text-center">
                <div className="text-xl font-bold text-emerald-600 tabular-nums font-cairo">
                  {attended}
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5 font-cairo">
                  {t('present') || 'حاضر'}
                </div>
              </div>
            </div>
          </div>

          <div className="px-6 py-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-emerald-600 tabular-nums font-cairo">
                {rate}%
              </span>
              <span className="text-xs text-muted-foreground font-cairo">
                {t('attendanceRate2') || 'معدل الحضور'}
              </span>
            </div>
            <Progress value={rate} className="h-2" />
          </div>

          <div className="px-6 pb-6 pt-2 space-y-2">
            {records.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground font-cairo">
                {t('noAttendanceRecords') || 'لا توجد سجلات حضور'}
              </div>
            ) : (
              records.map((r, idx) => {
                const dateLabel = (() => {
                  const ds = dateOnly(r.date);
                  const d = ds ? new Date(ds) : null;
                  if (!d || isNaN(d.getTime())) return ds;
                  return d.toLocaleDateString(isRTL ? 'ar-EG' : 'en-GB', {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric',
                  });
                })();
                const styleByStatus = {
                  absent: {
                    icon: XCircle,
                    iconColor: 'text-red-500',
                    badge:
                      'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400 border-red-200 dark:border-red-900/40',
                    label: t('absent') || 'غائب',
                  },
                  excused: {
                    icon: AlertTriangle,
                    iconColor: 'text-blue-500',
                    badge:
                      'bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400 border-blue-200 dark:border-blue-900/40',
                    label: t('excused2') || 'بعذر',
                  },
                  present: {
                    icon: CheckCircle2,
                    iconColor: 'text-emerald-500',
                    badge:
                      'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/40',
                    label: t('present') || 'حاضر',
                  },
                  late: {
                    icon: CheckCircle2,
                    iconColor: 'text-emerald-500',
                    badge:
                      'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/40',
                    label: t('present') || 'حاضر',
                  },
                };
                const s = styleByStatus[r.status] || styleByStatus.present;
                const Icon = s.icon;
                return (
                  <div
                    key={r.id || `${r.date}-${idx}`}
                    className="flex items-center justify-between gap-3 p-2.5 rounded-lg border border-border/60 bg-card"
                  >
                    <Badge variant="outline" className={`${s.badge} font-cairo border`}>
                      {s.label}
                    </Badge>
                    <span className="text-sm font-cairo text-foreground flex-1 text-center">
                      {dateLabel}
                    </span>
                    <Icon className={`h-5 w-5 ${s.iconColor} shrink-0`} />
                  </div>
                );
              })
            )}
          </div>
        </DialogContent>
      </Dialog>
    );
  };

  return (
    <div className="space-y-4">
      {attendanceLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  <th className="p-3 text-start font-medium font-cairo min-w-[200px]">
                    {t('student3') || 'الطالب'}
                  </th>
                  <th className="p-3 text-center font-medium font-cairo min-w-[220px]">
                    {t('status2') || 'الحالة'}
                  </th>
                  <th className="p-3 text-center font-medium font-cairo text-emerald-600">
                    {t('present') || 'حاضر'}
                  </th>
                  <th className="p-3 text-center font-medium font-cairo text-red-500">
                    {t('absent') || 'غائب'}
                  </th>
                  {showHistory && (
                    <th className="p-3 text-center font-medium font-cairo">
                      {t('history') || 'السجل'}
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {attendanceByStudent.length === 0 ? (
                  <tr>
                    <td
                      colSpan={showHistory ? 5 : 4}
                      className="text-center py-12 text-muted-foreground"
                    >
                      {t('noStudents') || 'لا يوجد طلاب'}
                    </td>
                  </tr>
                ) : (
                  attendanceByStudent.map(
                    ({ student, presentCount, absentCount, todayStatus, records }) => {
                      const isAbsent = todayStatus === 'absent';
                      const isPresent =
                        todayStatus === 'present' || todayStatus === 'late';
                      const isToggling = togglingStudentId === student.id;
                      return (
                        <tr
                          key={student.id}
                          className="border-b border-border/50 hover:bg-muted/20 transition-colors duration-150"
                        >
                          <td className="p-3">
                            <div className="flex items-center gap-2.5">
                              <div className="w-8 h-8 rounded-full bg-brand-navy dark:bg-brand-turquoise flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                                {student.full_name?.charAt(0) || '?'}
                              </div>
                              <p className="font-medium text-sm font-cairo">
                                {student.full_name}
                              </p>
                            </div>
                          </td>
                          <td className="p-3">
                            <div className="inline-flex items-center rounded-full border border-border overflow-hidden bg-background">
                              <button
                                type="button"
                                disabled={isToggling}
                                onClick={() =>
                                  handleToggleAttendance(student.id, 'absent')
                                }
                                className={`px-4 py-1.5 text-xs font-cairo font-semibold transition ${
                                  isAbsent
                                    ? 'bg-red-500 text-white'
                                    : 'text-muted-foreground hover:bg-muted/40'
                                } ${isToggling ? 'opacity-60 cursor-wait' : ''}`}
                                data-testid={`attendance-absent-${student.id}`}
                              >
                                {t('absent') || 'غائب'}
                              </button>
                              <button
                                type="button"
                                disabled={isToggling}
                                onClick={() =>
                                  handleToggleAttendance(student.id, 'present')
                                }
                                className={`px-4 py-1.5 text-xs font-cairo font-semibold transition ${
                                  isPresent
                                    ? 'bg-emerald-500 text-white'
                                    : 'text-muted-foreground hover:bg-muted/40'
                                } ${isToggling ? 'opacity-60 cursor-wait' : ''}`}
                                data-testid={`attendance-present-${student.id}`}
                              >
                                {t('present') || 'حاضر'}
                              </button>
                            </div>
                          </td>
                          <td className="p-3 text-center">
                            <span className="text-sm font-bold font-cairo tabular-nums text-emerald-600">
                              {presentCount}
                            </span>
                          </td>
                          <td className="p-3 text-center">
                            <span className="text-sm font-bold font-cairo tabular-nums text-red-500">
                              {absentCount}
                            </span>
                          </td>
                          {showHistory && (
                            <td className="p-3 text-center">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() =>
                                  setHistoryStudent({ student, records })
                                }
                                aria-label={t('history') || 'السجل'}
                              >
                                <Clock className="h-4 w-4 text-muted-foreground" />
                              </Button>
                            </td>
                          )}
                        </tr>
                      );
                    },
                  )
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {showHistory && renderHistoryDialog()}
    </div>
  );
}
