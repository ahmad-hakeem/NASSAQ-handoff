import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  ClipboardCheck, Users, Check, X, Clock, FileText,
  Loader2, Save, CheckCircle2, ArrowRight, ArrowLeft
} from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';

// Canonical four-status set, mirrors backend `AttendanceStatusLiteral`
// (`backend/routes/teacher_attendance_routes.py`). Keys MUST stay identical
// to the backend literals — the same string is sent in the bulk payload.
const STATUS_KEYS = ['present', 'absent', 'late', 'excused'];

const ATTENDANCE_STATUS = {
  present: {
    labelKey: 'present',
    labelAr: 'حاضر', labelEn: 'Present',
    badge: 'bg-green-100 text-green-700 border-green-300',
    cardActive: 'border-green-300 bg-green-50/40',
    btnActive: 'bg-green-600 text-white hover:bg-green-700',
    btnIdle: 'text-green-700 hover:bg-green-50',
    icon: Check,
  },
  absent: {
    labelKey: 'absent',
    labelAr: 'غائب', labelEn: 'Absent',
    badge: 'bg-red-100 text-red-700 border-red-300',
    cardActive: 'border-red-300 bg-red-50/40',
    btnActive: 'bg-red-600 text-white hover:bg-red-700',
    btnIdle: 'text-red-700 hover:bg-red-50',
    icon: X,
  },
  late: {
    labelKey: 'late',
    labelAr: 'متأخر', labelEn: 'Late',
    badge: 'bg-amber-100 text-amber-800 border-amber-300',
    cardActive: 'border-amber-300 bg-amber-50/50',
    btnActive: 'bg-amber-500 text-white hover:bg-amber-600',
    btnIdle: 'text-amber-700 hover:bg-amber-50',
    icon: Clock,
  },
  excused: {
    labelKey: 'excused2',
    labelAr: 'بعذر', labelEn: 'Excused',
    badge: 'bg-blue-100 text-blue-700 border-blue-300',
    cardActive: 'border-blue-300 bg-blue-50/40',
    btnActive: 'bg-blue-600 text-white hover:bg-blue-700',
    btnIdle: 'text-blue-700 hover:bg-blue-50',
    icon: FileText,
  },
};

// Coerce any value coming back from the API (including legacy rows that only
// store 'present'/'absent'/'excused', or future unknown values) into one of
// the four canonical statuses, defaulting to 'present'.
const normalizeStatus = (raw) =>
  STATUS_KEYS.includes(raw) ? raw : 'present';

export default function TeacherAttendanceManagePage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const preselectedClass = searchParams.get('class');

  // When opened from the AI Insights → Smart Alerts timeline, the register
  // shows only present/absent per student card. The late/excused statuses stay
  // available through every other entry path (dashboard, My Classes, Tasks,
  // direct URL). Conditional render only — the canonical STATUS_KEYS set and the
  // save payload are untouched.
  const fromSmartAlert = searchParams.get('from') === 'smart-alert';
  const visibleStatusKeys = fromSmartAlert
    ? STATUS_KEYS.filter((k) => k === 'present' || k === 'absent')
    : STATUS_KEYS;

  const handleBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate('/teacher');
  };
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState(preselectedClass || '');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [attendance, setAttendance] = useState({});
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [notes, setNotes] = useState('');

  const teacherId = user?.teacher_id || user?.id;

  const fetchClasses = useCallback(async () => {
    if (!teacherId) return;
    
    try {
      // Fetch teacher's assigned classes
      const response = await api.get(`/teacher/classes/${teacherId}`).catch(() => null);
      if (response?.data) {
        setClasses(response.data);
        if (!selectedClass && response.data.length > 0) {
          setSelectedClass(response.data[0].id);
        }
      } else {
        // Fallback
        const assignmentsRes = await api.get('/teacher-assignments');
        const myAssignments = (assignmentsRes.data || []).filter(a => a.teacher_id === teacherId);
        const classIds = [...new Set(myAssignments.map(a => a.class_id))];
        const classesRes = await api.get('/classes');
        const myClasses = (classesRes.data || []).filter(c => classIds.includes(c.id));
        setClasses(myClasses);
        if (!selectedClass && myClasses.length > 0) {
          setSelectedClass(myClasses[0].id);
        }
      }
    } catch (error) {
      console.error('Error fetching classes:', error);
    }
  }, [api, teacherId, selectedClass]);

  const fetchStudents = useCallback(async () => {
    if (!selectedClass) return;
    
    setLoading(true);
    try {
      // Fetch students for the selected class
      const response = await api.get(`/classes/${selectedClass}/students`).catch(() => null);
      const studentsList = response?.data || [];
      setStudents(studentsList);
      
      const attendanceRes = await api.get(`/attendance/class/${selectedClass}?date=${selectedDate}`).catch(() => null);
      const existingAttendance = {};
      const attData = attendanceRes?.data;
      
      if (Array.isArray(attData)) {
        attData.forEach(record => {
          existingAttendance[record.student_id] = record.status;
        });
      } else if (attData?.records && Array.isArray(attData.records)) {
        attData.records.forEach(record => {
          existingAttendance[record.student_id] = record.status;
        });
      }
      
      // Initialize attendance state — keep the persisted status verbatim
      // when it's one of the four canonical values, otherwise default to
      // 'present' (covers legacy rows and unknown values safely).
      const initialAttendance = {};
      studentsList.forEach(student => {
        initialAttendance[student.id] = normalizeStatus(existingAttendance[student.id]);
      });
      setAttendance(initialAttendance);
      
    } catch (error) {
      console.error('Error fetching students:', error);
      nassaqError(t('errorLoadingStudents'));
    } finally {
      setLoading(false);
    }
  }, [api, selectedClass, selectedDate, nassaqError, t]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  useEffect(() => {
    if (selectedClass) {
      fetchStudents();
    }
  }, [selectedClass, selectedDate, fetchStudents]);

  const handleStatusChange = (studentId, status) => {
    setAttendance(prev => ({ ...prev, [studentId]: status }));
  };

  const markAllPresent = () => {
    const newAttendance = {};
    students.forEach(student => {
      newAttendance[student.id] = 'present';
    });
    setAttendance(newAttendance);
  };

  const saveAttendance = async () => {
    setSaving(true);
    try {
      const records = Object.entries(attendance).map(([studentId, status]) => ({
        student_id: studentId,
        status,
        notes: notes || undefined
      }));

      await api.post('/attendance/bulk', {
        class_id: selectedClass,
        date: selectedDate,
        records
      });
      
      toast.success(t('attendanceSavedSuccessfully'));
      setShowConfirmDialog(false);
      setNotes('');
    } catch (error) {
      console.error('Error saving attendance:', error);
      nassaqError(t('errorSavingAttendance'));
    } finally {
      setSaving(false);
    }
  };

  // Counters: each student is counted in exactly one bucket so the four
  // status totals always sum to `total`. No double-counting (late no longer
  // collapses into present here — that earlier `!== 'absent'` check did).
  const stats = {
    total: students.length,
    present: Object.values(attendance).filter(s => s === 'present').length,
    absent: Object.values(attendance).filter(s => s === 'absent').length,
    late: Object.values(attendance).filter(s => s === 'late').length,
    excused: Object.values(attendance).filter(s => s === 'excused').length,
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0"
                onClick={handleBack}
                aria-label={isRTL ? 'رجوع' : 'Back'}
                data-testid="back-button"
              >
                {isRTL ? <ArrowRight className="h-5 w-5" /> : <ArrowLeft className="h-5 w-5" />}
              </Button>
              <div>
                <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                  {t('attendance3')}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {t('recordStudentAttendance')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={markAllPresent}>
                <CheckCircle2 className="h-4 w-4 me-1" />
                {t('markAllPresent')}
              </Button>
              <Button 
                className="bg-brand-turquoise hover:bg-brand-turquoise/90"
                onClick={() => setShowConfirmDialog(true)}
                disabled={students.length === 0}
              >
                <Save className="h-4 w-4 me-1" />
                {t('saveAttendance2')}
              </Button>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="p-4 border-b bg-muted/30">
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">{t('class3')}</label>
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-full sm:w-[200px]" data-testid="class-select">
                  <SelectValue placeholder={t('selectClass')} />
                </SelectTrigger>
                <SelectContent>
                  {classes.map(cls => (
                    <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">{t('date2')}</label>
              <input 
                type="date" 
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="border rounded-lg px-3 py-2 text-sm"
                data-testid="date-input"
              />
            </div>
          </div>
        </div>

        {/* Stats Summary */}
        <div className="p-4 border-b">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            <div className="p-3 rounded-xl bg-gray-100 text-center" data-testid="stat-total">
              <div className="text-2xl font-bold">{stats.total}</div>
              <div className="text-xs text-muted-foreground">{t('total')}</div>
            </div>
            <div className="p-3 rounded-xl bg-green-100 text-center" data-testid="stat-present">
              <div className="text-2xl font-bold text-green-700">{stats.present}</div>
              <div className="text-xs text-green-600">{t('present')}</div>
            </div>
            <div className="p-3 rounded-xl bg-red-100 text-center" data-testid="stat-absent">
              <div className="text-2xl font-bold text-red-700">{stats.absent}</div>
              <div className="text-xs text-red-600">{t('absent')}</div>
            </div>
            <div className="p-3 rounded-xl bg-amber-100 text-center" data-testid="stat-late">
              <div className="text-2xl font-bold text-amber-700">{stats.late}</div>
              <div className="text-xs text-amber-600">{t('late')}</div>
            </div>
            <div className="p-3 rounded-xl bg-blue-100 text-center" data-testid="stat-excused">
              <div className="text-2xl font-bold text-blue-700">{stats.excused}</div>
              <div className="text-xs text-blue-600">{t('excused2')}</div>
            </div>
          </div>
        </div>

        {/* Students List */}
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : !selectedClass ? (
            <Card>
              <CardContent className="text-center py-16">
                <ClipboardCheck className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <p className="text-muted-foreground">{t('selectAClassToViewStudents')}</p>
              </CardContent>
            </Card>
          ) : students.length === 0 ? (
            <Card>
              <CardContent className="text-center py-16">
                <Users className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <p className="text-muted-foreground">{t('noStudentsInThisClass')}</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
              {students.map((student, idx) => {
                const current = normalizeStatus(attendance[student.id]);
                const statusCfg = ATTENDANCE_STATUS[current];
                const isAbsent = current === 'absent';
                return (
                  <Card
                    key={student.id}
                    className={`transition-all border ${statusCfg.cardActive}`}
                    data-testid={`student-card-${student.id}`}
                    data-status={current}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <Avatar className={`h-12 w-12 ${isAbsent ? 'opacity-50 grayscale' : ''}`}>
                          <AvatarImage src={student.avatar_url} />
                          <AvatarFallback className="bg-brand-navy text-white">
                            {student.full_name?.split(' ').map(n => n[0]).join('').slice(0, 2) || (idx + 1)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className={`font-medium truncate ${isAbsent ? 'line-through opacity-60' : ''}`}>{student.full_name || `طالب ${idx + 1}`}</p>
                          <p className="text-xs text-muted-foreground">{student.student_id || `#${idx + 1}`}</p>
                        </div>
                        <Badge className={statusCfg.badge} data-testid={`student-badge-${student.id}`}>
                          {isRTL ? statusCfg.labelAr : statusCfg.labelEn}
                        </Badge>
                      </div>
                      {/* Mutually-exclusive status row. Selecting one writes
                          a single value to local state — the next save sends
                          exactly that value, no stale active styles. */}
                      <div className={`mt-3 grid ${fromSmartAlert ? 'grid-cols-2' : 'grid-cols-4'} gap-1.5`} role="radiogroup" aria-label={t('attendance3')}>
                        {visibleStatusKeys.map((key) => {
                          const cfg = ATTENDANCE_STATUS[key];
                          const Icon = cfg.icon;
                          const active = current === key;
                          const label = isRTL ? cfg.labelAr : cfg.labelEn;
                          return (
                            <Button
                              key={key}
                              type="button"
                              size="sm"
                              variant="ghost"
                              role="radio"
                              aria-checked={active}
                              aria-label={label}
                              title={label}
                              data-testid={`status-btn-${student.id}-${key}`}
                              data-active={active}
                              className={`h-8 px-2 border ${active ? cfg.btnActive + ' border-transparent' : 'bg-white border-gray-200 ' + cfg.btnIdle}`}
                              onClick={() => handleStatusChange(student.id, key)}
                            >
                              <Icon className="h-3.5 w-3.5 me-1" />
                              <span className="text-[11px]">{label}</span>
                            </Button>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        {/* Confirm Dialog */}
        <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-cairo">
                {isRTL ? 'اعتماد الحضور' : 'Confirm Attendance'}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="p-2 rounded bg-green-100">
                  <div className="font-bold text-green-700">{stats.present}</div>
                  <div className="text-xs">{t('present')}</div>
                </div>
                <div className="p-2 rounded bg-red-100">
                  <div className="font-bold text-red-700">{stats.absent}</div>
                  <div className="text-xs">{t('absent')}</div>
                </div>
                <div className="p-2 rounded bg-amber-100">
                  <div className="font-bold text-amber-700">{stats.late}</div>
                  <div className="text-xs">{t('late')}</div>
                </div>
                <div className="p-2 rounded bg-blue-100">
                  <div className="font-bold text-blue-700">{stats.excused}</div>
                  <div className="text-xs">{t('excused2')}</div>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">
                  {t('notesOptional')}
                </label>
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder={t('addNotes')}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
                {t('cancel')}
              </Button>
              <Button 
                className="bg-brand-turquoise hover:bg-brand-turquoise/90"
                onClick={saveAttendance}
                disabled={saving}
              >
                {saving && <Loader2 className="h-4 w-4 animate-spin me-2" />}
                {t('confirm2')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
