import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  CalendarCheck,
  Users,
  UserCheck,
  UserX,
  Clock,
  FileText,
  Sun,
  Moon,
  Globe,
  RefreshCw,
  Save,
  CheckCircle,
  XCircle,
  AlertCircle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  BarChart3,
  Filter,
  Download,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Input } from '../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';

const statusConfig = {
  present: {
    label: { ar: 'حاضر', en: 'Present' },
    icon: CheckCircle,
    color: 'bg-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    textColor: 'text-green-700 dark:text-green-400',
  },
  absent: {
    label: { ar: 'غائب', en: 'Absent' },
    icon: XCircle,
    color: 'bg-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    textColor: 'text-red-700 dark:text-red-400',
  },
  late: {
    label: { ar: 'متأخر', en: 'Late' },
    icon: Clock,
    color: 'bg-yellow-500',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
    textColor: 'text-yellow-700 dark:text-yellow-400',
  },
  excused: {
    label: { ar: 'بعذر', en: 'Excused' },
    icon: FileText,
    color: 'bg-blue-500',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    textColor: 'text-blue-700 dark:text-blue-400',
  },
};

export const AttendancePage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  
  // State
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [timeSlots, setTimeSlots] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Filters
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('');
  const [selectedTimeSlot, setSelectedTimeSlot] = useState('');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  
  // Attendance records
  const [attendanceRecords, setAttendanceRecords] = useState({});
  const [notesDialog, setNotesDialog] = useState({ open: false, studentId: null });
  const [noteText, setNoteText] = useState('');
  
  // Reports
  const [activeTab, setActiveTab] = useState('record');
  const [dailyReport, setDailyReport] = useState(null);
  const [studentHistory, setStudentHistory] = useState(null);
  const [selectedStudentForHistory, setSelectedStudentForHistory] = useState(null);
  const [summaryReport, setSummaryReport] = useState(null);

  // Fetch initial data
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    fetchClasses();
    fetchSubjects();
    fetchTimeSlots();
  }, []);

  // Fetch students when class changes
  useEffect(() => {
    if (selectedClass) {
      fetchStudentsWithAttendance();
    }
  }, [selectedClass, selectedDate]);

  const fetchClasses = async () => {
    try {
      const response = await api.get('/classes');
      setClasses(response.data);
      if (response.data.length > 0) {
        setSelectedClass(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch classes:', error);
    }
  };

  const fetchSubjects = async () => {
    try {
      const response = await api.get('/subjects');
      setSubjects(response.data);
    } catch (error) {
      console.error('Failed to fetch subjects:', error);
    }
  };

  const fetchTimeSlots = async () => {
    try {
      const response = await api.get('/time-slots');
      setTimeSlots(response.data.filter(ts => !ts.is_break));
    } catch (error) {
      console.error('Failed to fetch time slots:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStudentsWithAttendance = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/attendance/students-for-class/${selectedClass}?date=${selectedDate}`);
      setStudents(response.data.students || []);
      
      // Initialize attendance records from existing data
      const records = {};
      response.data.students?.forEach(student => {
        if (student.attendance_status) {
          records[student.id] = {
            status: student.attendance_status,
            notes: student.attendance_notes || ''
          };
        }
      });
      setAttendanceRecords(records);
    } catch (error) {
      console.error('Failed to fetch students:', error);
      nassaqError(t('failedToLoadStudents'));
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (studentId, status) => {
    setAttendanceRecords(prev => ({
      ...prev,
      [studentId]: { ...prev[studentId], status }
    }));
  };

  const handleNotesSave = () => {
    if (notesDialog.studentId) {
      setAttendanceRecords(prev => ({
        ...prev,
        [notesDialog.studentId]: { 
          ...prev[notesDialog.studentId], 
          notes: noteText 
        }
      }));
    }
    setNotesDialog({ open: false, studentId: null });
    setNoteText('');
  };

  const handleSaveAttendance = async () => {
    if (!selectedClass) {
      nassaqError(t('pleaseSelectAClass'));
      return;
    }

    // Check if all students have attendance recorded
    const unrecordedStudents = students.filter(s => !attendanceRecords[s.id]?.status);
    if (unrecordedStudents.length > 0) {
      nassaqWarning(
        isRTL 
          ? `يوجد ${unrecordedStudents.length} طالب لم يتم تسجيل حضورهم`
          : `${unrecordedStudents.length} students have not been recorded`
      );
    }

    try {
      setSaving(true);
      
      const records = Object.entries(attendanceRecords)
        .filter(([_, data]) => data.status)
        .map(([studentId, data]) => ({
          student_id: studentId,
          status: data.status,
          notes: data.notes || null
        }));

      if (records.length === 0) {
        nassaqError(t('noAttendanceRecordsToSave'));
        return;
      }

      const response = await api.post('/attendance/bulk', {
        class_id: selectedClass,
        subject_id: selectedSubject && selectedSubject !== 'none' ? selectedSubject : null,
        time_slot_id: selectedTimeSlot && selectedTimeSlot !== 'none' ? selectedTimeSlot : null,
        date: selectedDate,
        records
      });

      toast.success(t('attendanceSavedSuccessfully'));
      
      // Refresh data
      fetchStudentsWithAttendance();
      
    } catch (error) {
      console.error('Failed to save attendance:', error);
      nassaqError(t('failedToSaveAttendance'));
    } finally {
      setSaving(false);
    }
  };

  const handleMarkAllPresent = () => {
    const newRecords = { ...attendanceRecords };
    students.forEach(student => {
      if (!newRecords[student.id]?.status) {
        newRecords[student.id] = { status: 'present', notes: '' };
      }
    });
    setAttendanceRecords(newRecords);
    toast.success(t('allMarkedAsPresent'));
  };

  const fetchDailyReport = async () => {
    if (!selectedClass) return;
    
    try {
      const response = await api.get(`/attendance/report/daily/${selectedClass}?date=${selectedDate}`);
      setDailyReport(response.data);
    } catch (error) {
      console.error('Failed to fetch daily report:', error);
    }
  };

  const fetchStudentHistory = async (studentId) => {
    try {
      const response = await api.get(`/attendance/student/${studentId}`);
      setStudentHistory(response.data);
      setSelectedStudentForHistory(studentId);
    } catch (error) {
      console.error('Failed to fetch student history:', error);
    }
  };

  const fetchSummaryReport = async () => {
    try {
      const response = await api.get('/attendance/report/summary', {
        params: {
          class_id: selectedClass || undefined
        }
      });
      setSummaryReport(response.data);
    } catch (error) {
      console.error('Failed to fetch summary report:', error);
    }
  };

  useEffect(() => {
    if (activeTab === 'daily' && selectedClass) {
      fetchDailyReport();
    } else if (activeTab === 'summary') {
      fetchSummaryReport();
    }
  }, [activeTab, selectedClass, selectedDate]);

  // Calculate current stats
  const stats = {
    total: students.length,
    present: Object.values(attendanceRecords).filter(r => r.status === 'present').length,
    absent: Object.values(attendanceRecords).filter(r => r.status === 'absent').length,
    late: Object.values(attendanceRecords).filter(r => r.status === 'late').length,
    excused: Object.values(attendanceRecords).filter(r => r.status === 'excused').length,
  };
  
  const recorded = stats.present + stats.absent + stats.late + stats.excused;
  const attendanceRate = recorded > 0 ? ((stats.present + stats.late) / recorded * 100).toFixed(1) : 0;

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="attendance-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
                <CalendarCheck className="h-7 w-7 text-brand-turquoise" />
                {t('attendance3')}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('recordStudentAttendance')}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={fetchStudentsWithAttendance} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-4 sm:p-6 space-y-6">
          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full max-w-md grid-cols-3">
              <TabsTrigger value="record" className="rounded-xl">
                <CalendarCheck className="h-4 w-4 me-2" />
                {t('record')}
              </TabsTrigger>
              <TabsTrigger value="daily" className="rounded-xl">
                <Calendar className="h-4 w-4 me-2" />
                {t('daily')}
              </TabsTrigger>
              <TabsTrigger value="summary" className="rounded-xl">
                <BarChart3 className="h-4 w-4 me-2" />
                {t('summary')}
              </TabsTrigger>
            </TabsList>

            {/* Record Tab */}
            <TabsContent value="record" className="space-y-6">
              {/* Filters */}
              <Card className="card-nassaq">
                <CardContent className="p-4">
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="space-y-2">
                      <Label>{t('date')}</Label>
                      <Input
                        type="date"
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        className="rounded-xl"
                        data-testid="attendance-date-input"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t('class')}</Label>
                      <Select value={selectedClass} onValueChange={setSelectedClass}>
                        <SelectTrigger className="rounded-xl" data-testid="select-class">
                          <SelectValue placeholder={t('selectClass')} />
                        </SelectTrigger>
                        <SelectContent>
                          {classes.map((cls) => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t('subjectOptional')}</Label>
                      <Select value={selectedSubject} onValueChange={setSelectedSubject}>
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectSubject')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">{t('none')}</SelectItem>
                          {subjects.map((subject) => (
                            <SelectItem key={subject.id} value={subject.id}>
                              {subject.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t('periodOptional')}</Label>
                      <Select value={selectedTimeSlot} onValueChange={setSelectedTimeSlot}>
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectPeriod')} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">{t('none')}</SelectItem>
                          {timeSlots.map((slot) => (
                            <SelectItem key={slot.id} value={slot.id}>
                              {slot.name} ({slot.start_time} - {slot.end_time})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Stats */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                        <Users className="h-5 w-5 text-brand-navy" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold">{stats.total}</p>
                        <p className="text-xs text-muted-foreground">{t('total2')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                        <UserCheck className="h-5 w-5 text-green-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold">{stats.present}</p>
                        <p className="text-xs text-muted-foreground">{t('present')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                        <UserX className="h-5 w-5 text-red-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold">{stats.absent}</p>
                        <p className="text-xs text-muted-foreground">{t('absent')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                        <Clock className="h-5 w-5 text-yellow-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold">{stats.late}</p>
                        <p className="text-xs text-muted-foreground">{t('late')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
                        <FileText className="h-5 w-5 text-blue-500" />
                      </div>
                      <div>
                        <p className="text-2xl font-bold">{stats.excused}</p>
                        <p className="text-xs text-muted-foreground">{t('excused2')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Progress Bar */}
              {stats.total > 0 && (
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium">
                        {t('attendanceRate')}
                      </span>
                      <span className="text-sm font-bold text-brand-turquoise">{attendanceRate}%</span>
                    </div>
                    <Progress value={parseFloat(attendanceRate)} className="h-2" />
                    <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                      <span>{isRTL ? `${recorded} من ${stats.total} مسجل` : `${recorded} of ${stats.total} recorded`}</span>
                      <span>{isRTL ? `${stats.total - recorded} متبقي` : `${stats.total - recorded} remaining`}</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Student List */}
              <Card className="card-nassaq">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="font-cairo">{t('studentList')}</CardTitle>
                      <CardDescription>
                        {t('clickStatusToChangeIt')}
                      </CardDescription>
                    </div>
                    <div className="flex gap-2">
                      <Button 
                        variant="outline" 
                        onClick={handleMarkAllPresent}
                        className="rounded-xl"
                        data-testid="mark-all-present-btn"
                      >
                        <CheckCircle className="h-4 w-4 me-2" />
                        {t('allPresent')}
                      </Button>
                      <Button 
                        onClick={handleSaveAttendance}
                        disabled={saving || recorded === 0}
                        className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl"
                        data-testid="save-attendance-btn"
                      >
                        <Save className="h-4 w-4 me-2" />
                        {saving ? (t('saving')) : (t('saveAttendance'))}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent>
                  {loading ? (
                    <div className="text-center py-8 text-muted-foreground">
                      {t('loading')}
                    </div>
                  ) : students.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      {t('noStudentsInThisClass')}
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {students.map((student) => {
                        const currentStatus = attendanceRecords[student.id]?.status;
                        const statusInfo = currentStatus ? statusConfig[currentStatus] : null;
                        
                        return (
                          <Card 
                            key={student.id} 
                            className={`transition-all ${statusInfo ? statusInfo.bgColor : 'bg-muted/30'}`}
                            data-testid={`student-card-${student.id}`}
                          >
                            <CardContent className="p-4">
                              <div className="flex items-center gap-3 mb-3">
                                <Avatar className="h-12 w-12">
                                  <AvatarImage src={student.avatar_url} />
                                  <AvatarFallback className="bg-brand-navy text-white">
                                    {student.full_name?.charAt(0)}
                                  </AvatarFallback>
                                </Avatar>
                                <div className="flex-1">
                                  <h4 className="font-medium">{student.full_name}</h4>
                                  <p className="text-xs text-muted-foreground">{student.student_code}</p>
                                </div>
                                {statusInfo && (
                                  <Badge className={`${statusInfo.color} text-white`}>
                                    {isRTL ? statusInfo.label.ar : statusInfo.label.en}
                                  </Badge>
                                )}
                              </div>
                              
                              {/* Status Buttons */}
                              <div className="grid grid-cols-4 gap-2">
                                {Object.entries(statusConfig).map(([status, config]) => {
                                  const Icon = config.icon;
                                  const isSelected = currentStatus === status;
                                  
                                  return (
                                    <Button
                                      key={status}
                                      variant={isSelected ? 'default' : 'outline'}
                                      size="sm"
                                      className={`rounded-xl ${isSelected ? config.color : ''}`}
                                      onClick={() => handleStatusChange(student.id, status)}
                                      data-testid={`status-btn-${status}-${student.id}`}
                                    >
                                      <Icon className="h-4 w-4" />
                                    </Button>
                                  );
                                })}
                              </div>
                              
                              {/* Notes Button */}
                              <Button
                                variant="ghost"
                                size="sm"
                                className="w-full mt-2 text-xs"
                                onClick={() => {
                                  setNoteText(attendanceRecords[student.id]?.notes || '');
                                  setNotesDialog({ open: true, studentId: student.id });
                                }}
                              >
                                <FileText className="h-3 w-3 me-1" />
                                {attendanceRecords[student.id]?.notes 
                                  ? (t('editNote'))
                                  : (t('addNote'))
                                }
                              </Button>
                            </CardContent>
                          </Card>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Daily Report Tab */}
            <TabsContent value="daily" className="space-y-6">
              {dailyReport && (
                <>
                  {/* Summary Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                    <Card className="card-nassaq col-span-2">
                      <CardContent className="p-4 text-center">
                        <p className="text-4xl font-bold text-brand-turquoise">
                          {dailyReport.summary.attendance_rate}%
                        </p>
                        <p className="text-sm text-muted-foreground">{t('attendanceRate')}</p>
                      </CardContent>
                    </Card>
                    
                    <Card className="card-nassaq">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold">{dailyReport.summary.total_students}</p>
                        <p className="text-xs text-muted-foreground">{t('total2')}</p>
                      </CardContent>
                    </Card>
                    
                    <Card className="card-nassaq">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-green-600">{dailyReport.summary.present}</p>
                        <p className="text-xs text-muted-foreground">{t('present')}</p>
                      </CardContent>
                    </Card>
                    
                    <Card className="card-nassaq">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-red-600">{dailyReport.summary.absent}</p>
                        <p className="text-xs text-muted-foreground">{t('absent')}</p>
                      </CardContent>
                    </Card>
                    
                    <Card className="card-nassaq">
                      <CardContent className="p-4 text-center">
                        <p className="text-2xl font-bold text-yellow-600">{dailyReport.summary.late}</p>
                        <p className="text-xs text-muted-foreground">{t('late')}</p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Records Table */}
                  <Card className="card-nassaq">
                    <CardHeader>
                      <CardTitle className="font-cairo">
                        {isRTL ? `تقرير ${dailyReport.class_name} - ${dailyReport.date}` : `${dailyReport.class_name} Report - ${dailyReport.date}`}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>{t('student3')}</TableHead>
                            <TableHead>{t('status2')}</TableHead>
                            <TableHead>{t('notes')}</TableHead>
                            <TableHead>{t('recordedBy')}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {dailyReport.records.map((record) => {
                            const config = statusConfig[record.status];
                            return (
                              <TableRow key={record.id}>
                                <TableCell className="font-medium">{record.student_name}</TableCell>
                                <TableCell>
                                  <Badge className={`${config.color} text-white`}>
                                    {isRTL ? config.label.ar : config.label.en}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-muted-foreground">{record.notes || '-'}</TableCell>
                                <TableCell className="text-muted-foreground">{record.teacher_name}</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                </>
              )}
            </TabsContent>

            {/* Summary Tab */}
            <TabsContent value="summary" className="space-y-6">
              {summaryReport && (
                <>
                  {/* Overall Summary */}
                  <Card className="card-nassaq">
                    <CardHeader>
                      <CardTitle className="font-cairo">{t('overallSummary')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="text-center p-4 bg-muted rounded-xl">
                          <p className="text-3xl font-bold text-brand-turquoise">{summaryReport.overall.attendance_rate}%</p>
                          <p className="text-sm text-muted-foreground">{t('attendanceRate2')}</p>
                        </div>
                        <div className="text-center p-4 bg-muted rounded-xl">
                          <p className="text-3xl font-bold">{summaryReport.overall.total_records}</p>
                          <p className="text-sm text-muted-foreground">{t('totalRecords')}</p>
                        </div>
                        <div className="text-center p-4 bg-green-100 dark:bg-green-900/30 rounded-xl">
                          <p className="text-3xl font-bold text-green-600">{summaryReport.overall.present}</p>
                          <p className="text-sm text-muted-foreground">{t('present')}</p>
                        </div>
                        <div className="text-center p-4 bg-red-100 dark:bg-red-900/30 rounded-xl">
                          <p className="text-3xl font-bold text-red-600">{summaryReport.overall.absent}</p>
                          <p className="text-sm text-muted-foreground">{t('absent')}</p>
                        </div>
                        <div className="text-center p-4 bg-yellow-100 dark:bg-yellow-900/30 rounded-xl">
                          <p className="text-3xl font-bold text-yellow-600">{summaryReport.overall.late}</p>
                          <p className="text-sm text-muted-foreground">{t('late')}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Daily Trend */}
                  <Card className="card-nassaq">
                    <CardHeader>
                      <CardTitle className="font-cairo">{t('dailyTrend')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>{t('date')}</TableHead>
                            <TableHead>{t('total')}</TableHead>
                            <TableHead>{t('present')}</TableHead>
                            <TableHead>{t('absent')}</TableHead>
                            <TableHead>{t('late')}</TableHead>
                            <TableHead>{t('attendanceRate')}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {summaryReport.daily.map((day) => (
                            <TableRow key={day.date}>
                              <TableCell className="font-medium">{day.date}</TableCell>
                              <TableCell>{day.total}</TableCell>
                              <TableCell className="text-green-600">{day.present}</TableCell>
                              <TableCell className="text-red-600">{day.absent}</TableCell>
                              <TableCell className="text-yellow-600">{day.late}</TableCell>
                              <TableCell>
                                <Badge className={day.attendance_rate >= 90 ? 'bg-green-500' : day.attendance_rate >= 75 ? 'bg-yellow-500' : 'bg-red-500'}>
                                  {day.attendance_rate}%
                                </Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* Notes Dialog */}
        <Dialog open={notesDialog.open} onOpenChange={(open) => setNotesDialog({ open, studentId: notesDialog.studentId })}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-cairo">{t('attendanceNotes')}</DialogTitle>
              <DialogDescription>
                {t('addANoteAboutStudentAttendance')}
              </DialogDescription>
            </DialogHeader>
            <Textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder={t('writeYourNoteHere')}
              className="min-h-[100px] rounded-xl"
            />
            <DialogFooter>
              <Button variant="outline" onClick={() => setNotesDialog({ open: false, studentId: null })} className="rounded-xl">
                {t('cancel')}
              </Button>
              <Button onClick={handleNotesSave} className="bg-brand-navy rounded-xl">
                {t('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
