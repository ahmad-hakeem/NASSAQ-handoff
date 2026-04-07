import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  ClipboardCheck, Users, Check, X,
  Loader2, Save, CheckCircle2
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
const ATTENDANCE_STATUS = {
  present: { label: 'حاضر', labelEn: 'Present', color: 'bg-green-100 text-green-700 border-green-300', icon: Check },
  absent: { label: 'غائب', labelEn: 'Absent', color: 'bg-red-100 text-red-700 border-red-300', icon: X },
};

export default function TeacherAttendanceManagePage() {
  const { user, api, isRTL } = useAuth();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [searchParams] = useSearchParams();
  const preselectedClass = searchParams.get('class');
  
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
      
      // Initialize attendance state
      const initialAttendance = {};
      studentsList.forEach(student => {
        const raw = existingAttendance[student.id];
        initialAttendance[student.id] = raw === 'absent' ? 'absent' : 'present';
      });
      setAttendance(initialAttendance);
      
    } catch (error) {
      console.error('Error fetching students:', error);
      nassaqError(t('errorLoadingStudents'));
    } finally {
      setLoading(false);
    }
  }, [api, selectedClass, selectedDate, isRTL]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  useEffect(() => {
    if (selectedClass) {
      fetchStudents();
    }
  }, [selectedClass, selectedDate, fetchStudents]);

  const handleStatusChange = (studentId, status) => {
  const { t } = useTranslation();
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

  const stats = {
    total: students.length,
    present: Object.values(attendance).filter(s => s !== 'absent').length,
    absent: Object.values(attendance).filter(s => s === 'absent').length,
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('attendance3')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('recordStudentAttendance')}
              </p>
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
          <div className="grid grid-cols-3 gap-2">
            <div className="p-3 rounded-xl bg-gray-100 text-center">
              <div className="text-2xl font-bold">{stats.total}</div>
              <div className="text-xs text-muted-foreground">{t('total')}</div>
            </div>
            <div className="p-3 rounded-xl bg-green-100 text-center">
              <div className="text-2xl font-bold text-green-700">{stats.present}</div>
              <div className="text-xs text-green-600">{t('present')}</div>
            </div>
            <div className="p-3 rounded-xl bg-red-100 text-center">
              <div className="text-2xl font-bold text-red-700">{stats.absent}</div>
              <div className="text-xs text-red-600">{t('absent')}</div>
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
                const isAbsent = attendance[student.id] === 'absent';
                const statusCfg = ATTENDANCE_STATUS[isAbsent ? 'absent' : 'present'];
                return (
                  <Card 
                    key={student.id} 
                    className={`transition-all cursor-pointer active:scale-[0.97] ${statusCfg.color.split(' ')[2]}`}
                    data-testid={`student-card-${student.id}`}
                    onClick={() => handleStatusChange(student.id, isAbsent ? 'present' : 'absent')}
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
                        <Badge className={statusCfg.color}>
                          {isRTL ? statusCfg.label : statusCfg.labelEn}
                        </Badge>
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
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="p-2 rounded bg-green-100">
                  <div className="font-bold text-green-700">{stats.present}</div>
                  <div className="text-xs">{t('present')}</div>
                </div>
                <div className="p-2 rounded bg-red-100">
                  <div className="font-bold text-red-700">{stats.absent}</div>
                  <div className="text-xs">{t('absent')}</div>
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
      <HakimAssistant />
    </Sidebar>
  );
}
