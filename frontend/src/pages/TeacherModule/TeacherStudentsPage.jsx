import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Progress } from '../../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Textarea } from '../../components/ui/textarea';
import { DialogFooter } from '../../components/ui/dialog';
import {
  Users, Search, Loader2, RefreshCw, Eye, GraduationCap,
  Phone, Mail, ClipboardCheck, FileText, TrendingUp, Star,
  BookOpen, Calendar, ChevronLeft, BarChart3, Brain, Target,
  CheckCircle, AlertTriangle, Sparkles, ArrowUpCircle, ArrowDownCircle,
  Lightbulb, Activity, MessageSquare, Send
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
export default function TeacherStudentsPage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [studentDetails, setStudentDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [aiInsights, setAiInsights] = useState(null);
  const [loadingAI, setLoadingAI] = useState(false);
  const [showMessageDialog, setShowMessageDialog] = useState(false);
  const [messageTarget, setMessageTarget] = useState(null);
  const [messageSubject, setMessageSubject] = useState('');
  const [messageBody, setMessageBody] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  const fetchClasses = useCallback(async () => {
    if (!teacherId) return;
    
    setLoading(true);
    try {
      const classesRes = await api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] }));
      setClasses(classesRes.data || []);
      
      if (classesRes.data?.length > 0 && !selectedClass) {
        setSelectedClass(classesRes.data[0].id);
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, selectedClass]);

  const fetchStudents = useCallback(async () => {
    if (!selectedClass) return;
    
    setLoading(true);
    try {
      const [studentsRes, statsRes] = await Promise.all([
        api.get(`/classes/${selectedClass}/students`),
        api.get(`/classes/${selectedClass}/student-stats`).catch(() => ({ data: {} }))
      ]);

      const statsMap = statsRes.data || {};
      const enrichedStudents = (studentsRes.data || []).map(student => {
        const s = statsMap[student.id] || {};
        return {
          ...student,
          attendance_rate: s.attendance_rate ?? 0,
          average_grade: s.average_grade ?? 0,
          behavior_points: s.behavior_points ?? 0
        };
      });
      
      setStudents(enrichedStudents);
    } catch (error) {
      console.error('Error:', error);
      nassaqError(t('errorLoadingStudents'));
    } finally {
      setLoading(false);
    }
  }, [api, selectedClass, nassaqError, t]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  useEffect(() => {
    if (selectedClass) {
      fetchStudents();
    }
  }, [selectedClass, fetchStudents]);

  const fetchAIInsights = async (studentId) => {
    setLoadingAI(true);
    try {
      const res = await api.get(`/hakim/student/${studentId}/improvement-plan?days=30`);
      setAiInsights(res.data);
    } catch (e) {
      console.error('Error fetching AI insights:', e);
      setAiInsights(null);
    } finally {
      setLoadingAI(false);
    }
  };

  const viewStudentDetails = async (student) => {
    setSelectedStudent(student);
    setShowDetailsDialog(true);
    setLoadingDetails(true);
    setAiInsights(null);
    
    try {
      const analyticsRes = await api.get(`/students/${student.id}/analytics`).catch(() => ({ data: null }));
      setStudentDetails(analyticsRes.data || {
        attendance: { rate: 0, total: 0, present: 0, absent: 0, late: 0, trend: [], recent: [] },
        grades: { average: 0, count: 0, records: [] },
        participation: { total_interactions: 0, participation_count: 0, recent: [] },
        behavior: { total_points: 0, records: [], session_records: [] },
        skills: []
      });
      fetchAIInsights(student.id);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoadingDetails(false);
    }
  };

  const openMessageParent = (e, student) => {
    e.stopPropagation();
    if (!student.parent_id) {
      nassaqError(t('noParentLinkedToThisStudent'));
      return;
    }
    setMessageTarget(student);
    setMessageSubject('');
    setMessageBody('');
    setShowMessageDialog(true);
  };

  const handleSendParentMessage = async () => {
    if (!messageSubject.trim() || !messageBody.trim()) {
      nassaqError(t('pleaseFillInSubjectAndMessage'));
      return;
    }
    setSendingMessage(true);
    try {
      await api.post('/messages', {
        sender_id: teacherId,
        sender_type: 'teacher',
        recipient_ids: [messageTarget.parent_id],
        type: 'follow_up',
        subject: messageSubject.trim(),
        body: messageBody.trim(),
        student_id: messageTarget.id,
        student_name: messageTarget.full_name,
        class_id: selectedClass
      });
      toast.success(t('messageSentToParentSuccessfully'));
      setShowMessageDialog(false);
    } catch (error) {
      nassaqError(t('errorSendingMessage'));
    } finally {
      setSendingMessage(false);
    }
  };

  const filteredStudents = students.filter(s =>
    s.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.student_id?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getGradeColor = (grade) => {
    if (grade >= 90) return 'text-green-600';
    if (grade >= 75) return 'text-blue-600';
    if (grade >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('myStudents')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('viewAndTrackStudentData')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-full sm:w-[180px]" data-testid="class-select">
                  <SelectValue placeholder={t('selectClass')} />
                </SelectTrigger>
                <SelectContent>
                  {classes.map(cls => (
                    <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('search')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="ps-9 w-full sm:w-[180px]"
                />
              </div>
              <Button variant="outline" size="icon" onClick={fetchStudents} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>

        {/* Stats Summary */}
        <div className="p-4 border-b bg-muted/30">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-brand-navy">{filteredStudents.length}</div>
              <div className="text-xs text-muted-foreground">{isRTL ? 'طالب' : 'Students'}</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-green-600">
                {Math.round(filteredStudents.reduce((s, st) => s + (st.attendance_rate || 0), 0) / filteredStudents.length) || 0}%
              </div>
              <div className="text-xs text-muted-foreground">{t('avgAttendance')}</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-blue-600">
                {Math.round(filteredStudents.reduce((s, st) => s + (st.average_grade || 0), 0) / filteredStudents.length) || 0}
              </div>
              <div className="text-xs text-muted-foreground">{t('avgGrade')}</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-white dark:bg-gray-800">
              <div className="text-2xl font-bold text-purple-600">
                {filteredStudents.filter(s => (s.average_grade || 0) >= 90).length}
              </div>
              <div className="text-xs text-muted-foreground">{t('topStudents3')}</div>
            </div>
          </div>
        </div>

        {/* Students Grid */}
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : filteredStudents.length === 0 ? (
            <Card>
              <CardContent className="text-center py-16">
                <Users className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <h3 className="font-bold mb-2">{t('noStudents')}</h3>
                <p className="text-muted-foreground">
                  {t('selectAClassToViewStudents')}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredStudents.map((student, idx) => (
                <Card 
                  key={student.id}
                  className="hover:shadow-lg transition-all cursor-pointer border-2 hover:border-brand-turquoise"
                  onClick={() => viewStudentDetails(student)}
                  data-testid={`student-card-${student.id}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-4">
                      <Avatar className="h-14 w-14">
                        <AvatarImage src={student.avatar_url} />
                        <AvatarFallback className="bg-gradient-to-br from-brand-navy to-brand-turquoise text-white text-lg">
                          {student.full_name?.charAt(0) || (idx + 1)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold truncate">{student.full_name || `طالب ${idx + 1}`}</p>
                        <p className="text-xs text-muted-foreground">{student.student_id || `#${idx + 1}`}</p>
                      </div>
                      <ChevronLeft className="h-5 w-5 text-muted-foreground" />
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-3 gap-2 text-center mb-3">
                      <div className="p-2 rounded bg-green-50 dark:bg-green-900/20">
                        <ClipboardCheck className="h-4 w-4 mx-auto mb-1 text-green-600" />
                        <div className="text-sm font-bold text-green-700">{student.attendance_rate || 0}%</div>
                        <div className="text-[10px] text-muted-foreground">{isRTL ? 'حضور' : 'Attend'}</div>
                      </div>
                      <div className="p-2 rounded bg-blue-50 dark:bg-blue-900/20">
                        <FileText className="h-4 w-4 mx-auto mb-1 text-blue-600" />
                        <div className={`text-sm font-bold ${getGradeColor(student.average_grade || 0)}`}>
                          {student.average_grade || 0}
                        </div>
                        <div className="text-[10px] text-muted-foreground">{t('grade4')}</div>
                      </div>
                      <div className="p-2 rounded bg-purple-50 dark:bg-purple-900/20">
                        <Star className="h-4 w-4 mx-auto mb-1 text-purple-600" />
                        <div className="text-sm font-bold text-purple-700">{student.behavior_points || 0}</div>
                        <div className="text-[10px] text-muted-foreground">{isRTL ? 'سلوك' : 'Behav'}</div>
                      </div>
                    </div>

                    {/* Progress Bar */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted-foreground">{t('overall')}</span>
                        <span className={`font-medium ${getGradeColor(student.average_grade || 0)}`}>
                          {student.average_grade >= 90 ? (t('excellent')) :
                           student.average_grade >= 75 ? (t('veryGood')) :
                           student.average_grade >= 60 ? (t('good')) : (isRTL ? 'يحتاج تحسين' : 'Needs Improvement')}
                        </span>
                      </div>
                      <Progress value={student.average_grade || 0} className="h-2" />
                    </div>

                    {student.parent_id && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full mt-3 text-xs gap-1.5 border-brand-turquoise/30 text-brand-navy hover:bg-brand-turquoise/10 hover:border-brand-turquoise"
                        onClick={(e) => openMessageParent(e, student)}
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        {t('messageParent')}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Message Parent Dialog */}
        <Dialog open={showMessageDialog} onOpenChange={setShowMessageDialog}>
          <DialogContent className="w-[95vw] max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-brand-turquoise" />
                {t('messageParent2')}
              </DialogTitle>
            </DialogHeader>
            {messageTarget && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <Avatar className="h-10 w-10">
                    <AvatarFallback className="bg-brand-navy text-white">
                      {messageTarget.full_name?.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium text-sm">{messageTarget.full_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t('parent')}: {messageTarget.parent_name || messageTarget.parent_id}
                    </p>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    {t('subject3')}
                  </label>
                  <Input
                    value={messageSubject}
                    onChange={(e) => setMessageSubject(e.target.value)}
                    placeholder={t('enterMessageSubject')}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-1.5 block">
                    {t('message2')}
                  </label>
                  <Textarea
                    value={messageBody}
                    onChange={(e) => setMessageBody(e.target.value)}
                    placeholder={t('typeYourMessageToTheParent')}
                    rows={5}
                  />
                </div>
              </div>
            )}
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setShowMessageDialog(false)}>
                {t('cancel')}
              </Button>
              <Button
                className="bg-brand-turquoise hover:bg-brand-turquoise/90 gap-1.5"
                onClick={handleSendParentMessage}
                disabled={sendingMessage}
              >
                {sendingMessage ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                {t('send')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Student Details Dialog */}
        <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
          <DialogContent className="w-[95vw] max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-3">
                {selectedStudent && (
                  <>
                    <Avatar className="h-10 w-10">
                      <AvatarFallback className="bg-brand-navy text-white">
                        {selectedStudent.full_name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <p>{selectedStudent.full_name}</p>
                      <p className="text-sm text-muted-foreground font-normal">
                        {selectedStudent.student_id}
                      </p>
                    </div>
                    {selectedStudent.parent_id && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs gap-1.5 border-brand-turquoise/30 text-brand-navy hover:bg-brand-turquoise/10"
                        onClick={(e) => { setShowDetailsDialog(false); openMessageParent(e, selectedStudent); }}
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        {t('messageParent')}
                      </Button>
                    )}
                  </>
                )}
              </DialogTitle>
            </DialogHeader>
            
            {loadingDetails ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
              </div>
            ) : studentDetails && (
              <Tabs defaultValue="overview" className="mt-4">
                <TabsList className="grid grid-cols-3 sm:grid-cols-5 w-full">
                  <TabsTrigger value="overview">{t('overview')}</TabsTrigger>
                  <TabsTrigger value="attendance">{t('attendance2')}</TabsTrigger>
                  <TabsTrigger value="grades">{t('grades')}</TabsTrigger>
                  <TabsTrigger value="behavior">{t('behavior')}</TabsTrigger>
                  <TabsTrigger value="ai-insights" className="gap-1">
                    <Brain className="h-3.5 w-3.5" />
                    {isRTL ? 'تحليل ذكي' : 'AI Insights'}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="space-y-4 mt-4">
                  <div className="grid grid-cols-2 gap-3">
                    <Card>
                      <CardContent className="p-4 text-center">
                        <ClipboardCheck className="h-7 w-7 mx-auto mb-1 text-green-600" />
                        <div className="text-2xl font-bold">{studentDetails?.attendance?.rate ?? selectedStudent?.attendance_rate ?? 0}%</div>
                        <div className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <FileText className="h-7 w-7 mx-auto mb-1 text-blue-600" />
                        <div className="text-2xl font-bold">{studentDetails?.grades?.average ?? selectedStudent?.average_grade ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('avgGrade')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <Star className="h-7 w-7 mx-auto mb-1 text-purple-600" />
                        <div className="text-2xl font-bold">{studentDetails?.behavior?.total_points ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('behaviorPts')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <TrendingUp className="h-7 w-7 mx-auto mb-1 text-amber-600" />
                        <div className="text-2xl font-bold">{studentDetails?.participation?.participation_count ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('participations')}</div>
                      </CardContent>
                    </Card>
                  </div>

                  {(studentDetails?.skills || []).length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('recordedSkills')}</CardTitle>
                      </CardHeader>
                      <CardContent className="flex flex-wrap gap-2">
                        {studentDetails.skills.slice(0, 8).map((skill, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {skill.skill_name} {skill.level ? `(${skill.level})` : ''}
                          </Badge>
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  {selectedStudent?.parent_phone && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('contactInfo')}</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <div className="flex items-center gap-2">
                          <Phone className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm">{selectedStudent.parent_phone}</span>
                        </div>
                        {selectedStudent.parent_email && (
                          <div className="flex items-center gap-2">
                            <Mail className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm">{selectedStudent.parent_email}</span>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>

                <TabsContent value="attendance" className="mt-4 space-y-4">
                  <div className="grid grid-cols-3 gap-2">
                    <Card>
                      <CardContent className="p-3 text-center">
                        <div className="text-lg font-bold text-green-600">{studentDetails?.attendance?.present ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('present')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3 text-center">
                        <div className="text-lg font-bold text-red-600">{studentDetails?.attendance?.absent ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('absent')}</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-3 text-center">
                        <div className="text-lg font-bold text-amber-600">{studentDetails?.attendance?.late ?? 0}</div>
                        <div className="text-xs text-muted-foreground">{t('late')}</div>
                      </CardContent>
                    </Card>
                  </div>

                  {(studentDetails?.attendance?.trend || []).length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('monthlyAttendanceTrend')}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {studentDetails.attendance.trend.map((item, idx) => (
                            <div key={idx} className="flex items-center gap-3">
                              <span className="text-xs w-16 text-muted-foreground">{item.month}</span>
                              <div className="flex-1">
                                <Progress value={item.rate} className="h-2" />
                              </div>
                              <span className="text-xs font-medium w-10 text-end">{item.rate}%</span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t('recentRecords')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {(studentDetails?.attendance?.recent || []).length === 0 ? (
                        <p className="text-center text-muted-foreground py-4 text-sm">
                          {t('noAttendanceRecords')}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {studentDetails.attendance.recent.map((record, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                              <span className="text-sm">{new Date(record.date).toLocaleDateString('ar-SA')}</span>
                              <Badge variant={record.status === 'present' ? 'default' : 'destructive'}>
                                {record.status === 'present' ? (t('present')) :
                                 record.status === 'absent' ? (t('absent')) :
                                 (t('late'))}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="grades" className="mt-4 space-y-4">
                  {studentDetails?.grades?.average > 0 && (
                    <Card>
                      <CardContent className="p-4 flex items-center justify-between">
                        <span className="text-sm font-medium">{t('overallAverage')}</span>
                        <div className={`text-2xl font-bold ${getGradeColor(studentDetails.grades.average)}`}>
                          {studentDetails.grades.average}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  <Card>
                    <CardContent className="p-4">
                      {(studentDetails?.grades?.records || []).length === 0 ? (
                        <p className="text-center text-muted-foreground py-4 text-sm">
                          {t('noGrades')}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {studentDetails.grades.records.map((grade, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                              <div>
                                <p className="font-medium text-sm">{grade.assessment_name || grade.subject_name}</p>
                                <p className="text-xs text-muted-foreground">{grade.type || (t('assessment'))}</p>
                              </div>
                              <Badge className={getGradeColor(grade.score || 0)}>
                                {grade.score || 0} / {grade.max_score || 100}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="behavior" className="mt-4 space-y-4">
                  <Card>
                    <CardContent className="p-4 flex items-center justify-between">
                      <span className="text-sm font-medium">{t('totalPoints2')}</span>
                      <div className={`text-2xl font-bold ${(studentDetails?.behavior?.total_points ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(studentDetails?.behavior?.total_points ?? 0) >= 0 ? '+' : ''}{studentDetails?.behavior?.total_points ?? 0}
                      </div>
                    </CardContent>
                  </Card>

                  {(studentDetails?.participation?.recent || []).length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">{t('sessionInteractions')}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {studentDetails.participation.recent.slice(0, 5).map((inter, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                              <div>
                                <p className="text-sm font-medium">{inter.note || inter.type}</p>
                                <p className="text-xs text-muted-foreground">{inter.created_at ? new Date(inter.created_at).toLocaleDateString('ar-SA') : ''}</p>
                              </div>
                              {inter.points != null && (
                                <Badge variant={inter.points > 0 ? 'default' : 'destructive'}>
                                  {inter.points > 0 ? '+' : ''}{inter.points}
                                </Badge>
                              )}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">{t('behaviorRecords2')}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {(studentDetails?.behavior?.records || []).length === 0 && (studentDetails?.behavior?.session_records || []).length === 0 ? (
                        <p className="text-center text-muted-foreground py-4 text-sm">
                          {t('noBehaviorRecords3')}
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {[...(studentDetails?.behavior?.records || []), ...(studentDetails?.behavior?.session_records || [])].slice(0, 10).map((record, idx) => (
                            <div 
                              key={idx} 
                              className={`p-2 rounded ${
                                (record.points || 0) > 0 ? 'bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800'
                              } border`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium text-sm">{record.note || (t('note'))}</span>
                                <Badge variant={(record.points || 0) > 0 ? 'default' : 'destructive'}>
                                  {(record.points || 0) > 0 ? '+' : ''}{record.points || 0}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">
                                {record.date ? new Date(record.date).toLocaleDateString('ar-SA') : 
                                 record.created_at ? new Date(record.created_at).toLocaleDateString('ar-SA') : ''}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="ai-insights" className="mt-4 space-y-4">
                  {loadingAI ? (
                    <div className="flex flex-col items-center justify-center py-10">
                      <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise mb-3" />
                      <p className="text-sm text-muted-foreground">{t('analyzingStudentData')}</p>
                    </div>
                  ) : aiInsights ? (
                    <>
                      <Card className="border-brand-turquoise/30 bg-gradient-to-br from-brand-turquoise/5 to-transparent">
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <Activity className="h-5 w-5 text-brand-turquoise" />
                              <h4 className="font-bold font-cairo">{t('riskAssessment')}</h4>
                            </div>
                            <Badge className={`${
                              aiInsights.risk_assessment?.category === 'low' ? 'bg-green-100 text-green-700' :
                              aiInsights.risk_assessment?.category === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                              aiInsights.risk_assessment?.category === 'high' ? 'bg-orange-100 text-orange-700' :
                              'bg-red-100 text-red-700'
                            }`}>
                              {aiInsights.risk_assessment?.label_ar || aiInsights.risk_assessment?.category}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3">
                            <div className="text-3xl font-bold text-brand-turquoise">{Math.round(aiInsights.risk_assessment?.score || 0)}%</div>
                            <div className="flex-1">
                              <Progress value={aiInsights.risk_assessment?.score || 0} className="h-2" />
                              <p className="text-xs text-muted-foreground mt-1">{t('stabilityIndexHigherBetter')}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <Card className="border-green-200 dark:border-green-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-green-700 dark:text-green-400">
                              <ArrowUpCircle className="h-4 w-4" />
                              {t('strengths')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            {(aiInsights.strengths || []).length > 0 ? (
                              <div className="space-y-2">
                                {aiInsights.strengths.map((s, idx) => (
                                  <div key={idx} className="flex items-center gap-2 p-2 rounded-lg bg-green-50 dark:bg-green-950/30">
                                    <CheckCircle className="h-4 w-4 text-green-600 shrink-0" />
                                    <span className="text-sm font-cairo">{s}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground text-center py-3">
                                {t('notEnoughData')}
                              </p>
                            )}
                          </CardContent>
                        </Card>

                        <Card className="border-red-200 dark:border-red-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-red-700 dark:text-red-400">
                              <ArrowDownCircle className="h-4 w-4" />
                              {t('areasForImprovement')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            {(aiInsights.weaknesses || []).length > 0 ? (
                              <div className="space-y-2">
                                {aiInsights.weaknesses.map((w, idx) => (
                                  <div key={idx} className="flex items-center gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-950/30">
                                    <AlertTriangle className="h-4 w-4 text-red-500 shrink-0" />
                                    <span className="text-sm font-cairo">{w}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-muted-foreground text-center py-3">
                                {t('noConcerns')}
                              </p>
                            )}
                          </CardContent>
                        </Card>
                      </div>

                      {(aiInsights.goals || []).length > 0 && (
                        <Card className="border-blue-200 dark:border-blue-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-blue-700 dark:text-blue-400">
                              <Target className="h-4 w-4" />
                              {t('suggestedGoals')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-2">
                              {aiInsights.goals.map((g, idx) => (
                                <div key={idx} className="flex items-start gap-2 p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                                  <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-xs font-bold text-blue-700 shrink-0 mt-0.5">
                                    {idx + 1}
                                  </div>
                                  <div>
                                    <p className="text-sm font-cairo font-medium">{g.goal_ar}</p>
                                    {g.target != null && (
                                      <p className="text-xs text-muted-foreground mt-0.5">
                                        {isRTL ? `الهدف: ${g.target}${g.metric?.includes('rate') || g.metric?.includes('average') ? '%' : ''}` : `Target: ${g.target}`}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                      )}

                      {aiInsights.action_plan?.actions?.length > 0 && (
                        <Card className="border-purple-200 dark:border-purple-800">
                          <CardHeader className="pb-2">
                            <CardTitle className="text-sm font-cairo flex items-center gap-2 text-purple-700 dark:text-purple-400">
                              <Lightbulb className="h-4 w-4" />
                              {t('improvementEnrichmentPlan')}
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <div className="space-y-3">
                              {aiInsights.action_plan.actions.map((action, idx) => (
                                <div key={idx} className="p-3 rounded-lg border bg-gradient-to-r from-purple-50/50 to-transparent dark:from-purple-950/20">
                                  <div className="flex items-start justify-between mb-1">
                                    <div className="flex items-center gap-2">
                                      <Sparkles className="h-4 w-4 text-purple-600 shrink-0" />
                                      <h5 className="font-medium text-sm font-cairo">{action.title_ar}</h5>
                                    </div>
                                    <Badge variant="outline" className="text-[10px] shrink-0">
                                      {action.deadline_days} {t('days')}
                                    </Badge>
                                  </div>
                                  <p className="text-xs text-muted-foreground font-cairo ps-6">{action.description_ar}</p>
                                  <p className="text-[10px] text-brand-turquoise font-cairo ps-6 mt-1">
                                    {t('responsible')}
                                    {action.responsible === 'class_teacher' ? (isRTL ? 'معلم الفصل' : 'Class Teacher') :
                                     action.responsible === 'subject_teachers' ? (t('subjectTeachers')) :
                                     action.responsible === 'counselor' ? (t('counselor')) :
                                     action.responsible === 'school_principal' ? (t('principal')) :
                                     action.responsible}
                                  </p>
                                </div>
                              ))}
                            </div>
                            {aiInsights.review_date && (
                              <div className="mt-3 p-2 rounded bg-muted/50 text-center">
                                <p className="text-xs text-muted-foreground font-cairo">
                                  {isRTL ? `موعد المراجعة التالية: ${aiInsights.review_date}` : `Next review: ${aiInsights.review_date}`}
                                </p>
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      )}

                      <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                        <span className="font-cairo">
                          {isRTL ? `اتجاه الدرجات: ${
                            aiInsights.grade_trend === 'improving' ? '📈 تحسن' :
                            aiInsights.grade_trend === 'declining' ? '📉 تراجع' : '➡️ مستقر'
                          }` : `Grade trend: ${aiInsights.grade_trend || 'stable'}`}
                        </span>
                        <Button variant="ghost" size="sm" onClick={() => fetchAIInsights(selectedStudent?.id)} className="h-7 text-xs">
                          <RefreshCw className="h-3 w-3 me-1" />
                          {t('refresh')}
                        </Button>
                      </div>
                    </>
                  ) : (
                    <Card className="p-8 text-center">
                      <Brain className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
                      <p className="text-muted-foreground text-sm font-cairo">
                        {t('notEnoughDataAvailableForAnalysisTheSystemNeedsAtt')}
                      </p>
                      <Button variant="outline" size="sm" className="mt-3" onClick={() => fetchAIInsights(selectedStudent?.id)}>
                        <Brain className="h-3.5 w-3.5 me-1" />
                        {isRTL ? 'إعادة المحاولة' : 'Try Again'}
                      </Button>
                    </Card>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
