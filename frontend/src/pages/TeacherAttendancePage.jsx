import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
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
  BarChart3,
  Download,
  User,
  Briefcase,
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

export const TeacherAttendancePage = () => {
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { nassaqWarning, nassaqError } = useNassaqAlert();
  
  // State
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Filters
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Attendance records
  const [attendanceRecords, setAttendanceRecords] = useState({});
  const [notesDialog, setNotesDialog] = useState({ open: false, teacherId: null });
  const [noteText, setNoteText] = useState('');
  
  // Reports
  const [activeTab, setActiveTab] = useState('record');
  const [summaryReport, setSummaryReport] = useState(null);

  // Fetch teachers on mount and when date changes
  useEffect(() => {
    fetchTeachersWithAttendance();
  }, [selectedDate]);

  const fetchTeachersWithAttendance = async () => {
    try {
      setLoading(true);
      // Fetch teachers
      const teachersRes = await api.get('/teachers');
      setTeachers(teachersRes.data || []);
      
      // Try to fetch existing attendance for today
      try {
        const attendanceRes = await api.get(`/teacher-attendance?date=${selectedDate}`);
        const records = {};
        attendanceRes.data?.forEach(record => {
          records[record.teacher_id] = {
            status: record.status,
            notes: record.notes || '',
            check_in_time: record.check_in_time
          };
        });
        setAttendanceRecords(records);
      } catch (error) {
        // If no attendance records exist, initialize empty
        setAttendanceRecords({});
      }
    } catch (error) {
      console.error('Failed to fetch teachers:', error);
      nassaqError(isRTL ? 'فشل تحميل بيانات المعلمين' : 'Failed to load teachers data');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (teacherId, status) => {
    const now = new Date().toTimeString().slice(0, 5);
    setAttendanceRecords(prev => ({
      ...prev,
      [teacherId]: { 
        ...prev[teacherId], 
        status,
        check_in_time: status === 'present' ? now : null
      }
    }));
  };

  const handleNotesSave = () => {
    if (notesDialog.teacherId) {
      setAttendanceRecords(prev => ({
        ...prev,
        [notesDialog.teacherId]: { 
          ...prev[notesDialog.teacherId], 
          notes: noteText 
        }
      }));
    }
    setNotesDialog({ open: false, teacherId: null });
    setNoteText('');
  };

  const handleSaveAttendance = async () => {
    const records = Object.entries(attendanceRecords)
      .filter(([_, data]) => data.status)
      .map(([teacherId, data]) => ({
        teacher_id: teacherId,
        date: selectedDate,
        status: data.status,
        check_in_time: data.check_in_time || null,
        notes: data.notes || ''
      }));

    if (records.length === 0) {
      nassaqWarning(isRTL ? 'لا يوجد سجلات حضور للحفظ' : 'No attendance records to save');
      return;
    }

    const unrecordedTeachers = teachers.filter(t => !attendanceRecords[t.id]?.status);
    if (unrecordedTeachers.length > 0) {
      nassaqWarning(
        isRTL 
          ? `يوجد ${unrecordedTeachers.length} معلم لم يتم تسجيل حضورهم بعد`
          : `${unrecordedTeachers.length} teachers have not been recorded yet`
      );
    }

    setSaving(true);
    try {
      const BATCH_SIZE = 50;
      let totalSaved = 0;
      let totalUpdated = 0;

      for (let i = 0; i < records.length; i += BATCH_SIZE) {
        const batch = records.slice(i, i + BATCH_SIZE);
        const response = await api.post('/teacher-attendance/bulk', { records: batch });
        totalSaved += response.data?.saved || 0;
        totalUpdated += response.data?.updated || 0;
      }

      toast.success(
        isRTL 
          ? `تم حفظ حضور ${totalSaved + totalUpdated} معلم بنجاح` 
          : `Saved attendance for ${totalSaved + totalUpdated} teachers`
      );
      
      fetchTeachersWithAttendance();
      
    } catch (error) {
      console.error('Failed to save attendance:', error);
      const detail = error.response?.data?.detail;
      nassaqError(detail || (isRTL ? 'فشل حفظ الحضور' : 'Failed to save attendance'));
    } finally {
      setSaving(false);
    }
  };

  const handleMarkAllPresent = () => {
    const now = new Date().toTimeString().slice(0, 5);
    const newRecords = { ...attendanceRecords };
    teachers.forEach(teacher => {
      newRecords[teacher.id] = { 
        status: 'present', 
        notes: newRecords[teacher.id]?.notes || '', 
        check_in_time: newRecords[teacher.id]?.check_in_time || now 
      };
    });
    setAttendanceRecords(newRecords);
    toast.success(isRTL ? `تم تحديد ${teachers.length} معلم حاضر` : `Marked ${teachers.length} teachers as present`);
  };

  const fetchSummaryReport = async () => {
    try {
      const response = await api.get('/teacher-attendance/report/summary');
      setSummaryReport(response.data);
    } catch (error) {
      setSummaryReport({
        overall: { attendance_rate: 0, total_records: 0, present: 0, absent: 0, late: 0 },
        daily: []
      });
    }
  };

  useEffect(() => {
    if (activeTab === 'summary') {
      fetchSummaryReport();
    }
  }, [activeTab]);

  // Calculate current stats
  const stats = {
    total: teachers.length,
    present: Object.values(attendanceRecords).filter(r => r.status === 'present').length,
    absent: Object.values(attendanceRecords).filter(r => r.status === 'absent').length,
    late: Object.values(attendanceRecords).filter(r => r.status === 'late').length,
    excused: Object.values(attendanceRecords).filter(r => r.status === 'excused').length,
  };
  
  const recorded = stats.present + stats.absent + stats.late + stats.excused;
  const attendanceRate = recorded > 0 ? ((stats.present + stats.late) / recorded * 100).toFixed(1) : 0;

  // Filter teachers by search
  const filteredTeachers = teachers.filter(teacher => 
    teacher.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    teacher.specialization?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="teacher-attendance-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
                <CalendarCheck className="h-7 w-7 text-brand-turquoise" />
                {isRTL ? 'إدارة حضور المعلمين والاداريين' : 'Staff Attendance Management'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL 
                  ? 'متابعة وتسجيل حضور المعلمين والاداريين داخل المدرسة' 
                  : 'Track and manage staff attendance in the school'}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={fetchTeachersWithAttendance} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Description Card */}
          <Card className="card-nassaq bg-brand-turquoise/5 border-brand-turquoise/20">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center flex-shrink-0">
                  <Briefcase className="h-5 w-5 text-brand-turquoise" />
                </div>
                <div>
                  <h3 className="font-semibold text-brand-turquoise mb-1">
                    {isRTL ? 'حضور المعلمين والاداريين' : 'Staff Attendance'}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {isRTL 
                      ? 'هذه الصفحة مخصصة لمتابعة وإدارة حضور المعلمين والاداريين داخل المدرسة، وتشمل تسجيل الحضور والغياب والتأخر، ومتابعة التزام الكادر التعليمي والإداري بساعات العمل الرسمية.'
                      : 'This page is dedicated to tracking and managing staff attendance within the school, including recording presence, absence, and tardiness, and monitoring compliance with official working hours.'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full max-w-md grid-cols-2">
              <TabsTrigger value="record" className="rounded-xl">
                <CalendarCheck className="h-4 w-4 me-2" />
                {isRTL ? 'تسجيل الحضور' : 'Record'}
              </TabsTrigger>
              <TabsTrigger value="summary" className="rounded-xl">
                <BarChart3 className="h-4 w-4 me-2" />
                {isRTL ? 'التقارير' : 'Reports'}
              </TabsTrigger>
            </TabsList>

            {/* Record Tab */}
            <TabsContent value="record" className="space-y-6">
              {/* Filters */}
              <Card className="card-nassaq">
                <CardContent className="p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'التاريخ' : 'Date'}</Label>
                      <Input
                        type="date"
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        className="rounded-xl"
                        data-testid="attendance-date-input"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{isRTL ? 'بحث' : 'Search'}</Label>
                      <Input
                        type="text"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder={isRTL ? 'بحث بالاسم أو التخصص...' : 'Search by name or specialization...'}
                        className="rounded-xl"
                        data-testid="search-teachers-input"
                      />
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
                        <p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي المعلمين' : 'Total Teachers'}</p>
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
                        <p className="text-xs text-muted-foreground">{isRTL ? 'حاضر' : 'Present'}</p>
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
                        <p className="text-xs text-muted-foreground">{isRTL ? 'غائب' : 'Absent'}</p>
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
                        <p className="text-xs text-muted-foreground">{isRTL ? 'متأخر' : 'Late'}</p>
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
                        <p className="text-xs text-muted-foreground">{isRTL ? 'بعذر' : 'Excused'}</p>
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
                        {isRTL ? 'نسبة حضور المعلمين' : 'Teacher Attendance Rate'}
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

              {/* Teacher List */}
              <Card className="card-nassaq">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="font-cairo">{isRTL ? 'قائمة المعلمين' : 'Teacher List'}</CardTitle>
                      <CardDescription>
                        {isRTL ? 'اضغط على الحالة لتغييرها' : 'Click status to change it'}
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
                        {isRTL ? 'الكل حاضر' : 'All Present'}
                      </Button>
                      <Button 
                        onClick={handleSaveAttendance}
                        disabled={saving || recorded === 0}
                        className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl"
                        data-testid="save-attendance-btn"
                      >
                        <Save className="h-4 w-4 me-2" />
                        {saving ? (isRTL ? 'جاري الحفظ...' : 'Saving...') : (isRTL ? 'حفظ الحضور' : 'Save Attendance')}
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                
                <CardContent>
                  {loading ? (
                    <div className="text-center py-8 text-muted-foreground">
                      {isRTL ? 'جاري التحميل...' : 'Loading...'}
                    </div>
                  ) : filteredTeachers.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      {isRTL ? 'لا يوجد معلمين' : 'No teachers found'}
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {filteredTeachers.map((teacher) => {
                        const currentStatus = attendanceRecords[teacher.id]?.status;
                        const statusInfo = currentStatus ? statusConfig[currentStatus] : null;
                        const checkInTime = attendanceRecords[teacher.id]?.check_in_time;
                        
                        return (
                          <Card 
                            key={teacher.id} 
                            className={`transition-all ${statusInfo ? statusInfo.bgColor : 'bg-muted/30'}`}
                            data-testid={`teacher-card-${teacher.id}`}
                          >
                            <CardContent className="p-4">
                              <div className="flex items-center gap-3 mb-3">
                                <Avatar className="h-12 w-12">
                                  <AvatarImage src={teacher.avatar_url} />
                                  <AvatarFallback className="bg-brand-navy text-white">
                                    {teacher.full_name?.charAt(0)}
                                  </AvatarFallback>
                                </Avatar>
                                <div className="flex-1 min-w-0">
                                  <h4 className="font-medium truncate">{teacher.full_name}</h4>
                                  <p className="text-xs text-muted-foreground truncate">{teacher.specialization}</p>
                                </div>
                                <div className="text-end">
                                  {statusInfo && (
                                    <Badge className={`${statusInfo.color} text-white`}>
                                      {isRTL ? statusInfo.label.ar : statusInfo.label.en}
                                    </Badge>
                                  )}
                                  {checkInTime && (
                                    <p className="text-xs text-muted-foreground mt-1">{checkInTime}</p>
                                  )}
                                </div>
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
                                      onClick={() => handleStatusChange(teacher.id, status)}
                                      data-testid={`status-btn-${status}-${teacher.id}`}
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
                                  setNoteText(attendanceRecords[teacher.id]?.notes || '');
                                  setNotesDialog({ open: true, teacherId: teacher.id });
                                }}
                              >
                                <FileText className="h-3 w-3 me-1" />
                                {attendanceRecords[teacher.id]?.notes 
                                  ? (isRTL ? 'تعديل الملاحظة' : 'Edit Note')
                                  : (isRTL ? 'إضافة ملاحظة' : 'Add Note')
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

            {/* Summary Tab */}
            <TabsContent value="summary" className="space-y-6">
              {summaryReport ? (
                <>
                  {/* Overall Summary */}
                  <Card className="card-nassaq">
                    <CardHeader>
                      <CardTitle className="font-cairo">{isRTL ? 'ملخص حضور المعلمين' : 'Teacher Attendance Summary'}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="text-center p-4 bg-muted rounded-xl">
                          <p className="text-3xl font-bold text-brand-turquoise">{summaryReport.overall.attendance_rate}%</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'معدل الحضور' : 'Attendance Rate'}</p>
                        </div>
                        <div className="text-center p-4 bg-muted rounded-xl">
                          <p className="text-3xl font-bold">{summaryReport.overall.total_records}</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'إجمالي السجلات' : 'Total Records'}</p>
                        </div>
                        <div className="text-center p-4 bg-green-100 dark:bg-green-900/30 rounded-xl">
                          <p className="text-3xl font-bold text-green-600">{summaryReport.overall.present}</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'حاضر' : 'Present'}</p>
                        </div>
                        <div className="text-center p-4 bg-red-100 dark:bg-red-900/30 rounded-xl">
                          <p className="text-3xl font-bold text-red-600">{summaryReport.overall.absent}</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'غائب' : 'Absent'}</p>
                        </div>
                        <div className="text-center p-4 bg-yellow-100 dark:bg-yellow-900/30 rounded-xl">
                          <p className="text-3xl font-bold text-yellow-600">{summaryReport.overall.late}</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'متأخر' : 'Late'}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  {isRTL ? 'جاري تحميل التقارير...' : 'Loading reports...'}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* Notes Dialog */}
        <Dialog open={notesDialog.open} onOpenChange={(open) => setNotesDialog({ open, teacherId: notesDialog.teacherId })}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-cairo">{isRTL ? 'ملاحظات الحضور' : 'Attendance Notes'}</DialogTitle>
              <DialogDescription>
                {isRTL ? 'أضف ملاحظة حول حضور المعلم' : 'Add a note about teacher attendance'}
              </DialogDescription>
            </DialogHeader>
            <Textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder={isRTL ? 'اكتب ملاحظتك هنا...' : 'Write your note here...'}
              className="min-h-[100px] rounded-xl"
            />
            <DialogFooter>
              <Button variant="outline" onClick={() => setNotesDialog({ open: false, teacherId: null })} className="rounded-xl">
                {isRTL ? 'إلغاء' : 'Cancel'}
              </Button>
              <Button onClick={handleNotesSave} className="bg-brand-navy rounded-xl">
                {isRTL ? 'حفظ' : 'Save'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
