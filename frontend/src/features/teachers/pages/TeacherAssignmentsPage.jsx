import { useState, useEffect } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import {
  UserCheck,
  Plus,
  Search,
  Trash2,
  Sun,
  Moon,
  Globe,
  Loader2,
  ArrowLeft,
  BookOpen,
  GraduationCap,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Award,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import { Link } from 'react-router-dom';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

// Teacher rank configuration
const RANK_CONFIG = {
  expert: { 
    label: { ar: 'معلم خبير', en: 'Expert Teacher' }, 
    color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300',
    min: 12, max: 18, dailyMax: 4 
  },
  advanced: { 
    label: { ar: 'معلم متقدم', en: 'Advanced Teacher' }, 
    color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
    min: 16, max: 20, dailyMax: 5 
  },
  practitioner: { 
    label: { ar: 'معلم ممارس', en: 'Practitioner Teacher' }, 
    color: 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300',
    min: 18, max: 24, dailyMax: 6 
  },
  assistant: { 
    label: { ar: 'معلم مساعد', en: 'Assistant Teacher' }, 
    color: 'bg-gray-100 text-gray-700 dark:bg-gray-900/50 dark:text-gray-300',
    min: 20, max: 26, dailyMax: 7 
  },
};

export const TeacherAssignmentsPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [assignments, setAssignments] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [schools, setSchools] = useState([]);
  const [teacherWorkloads, setTeacherWorkloads] = useState({});
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedSchool, setSelectedSchool] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  const { nassaqError, nassaqWarning, nassaqConfirm } = useNassaqAlert();
  const [newAssignment, setNewAssignment] = useState({
    teacher_id: '',
    class_id: '',
    subject_id: '',
    weekly_sessions: 4,
    academic_year: '2026-2027',
    semester: 1,
  });

  const isSchoolLevel = user?.role && !user.role.startsWith('platform_');
  const userSchoolId = user?.tenant_id;

  const fetchSchools = async () => {
    // School-level users (school_admin/principal) can't list /schools
    // (platform-admin only). Use their own tenant_id directly.
    if (isSchoolLevel) {
      if (userSchoolId) {
        const label = user?.tenant_name || user?.school_name || user?.full_name || userSchoolId;
        setSchools([{ id: userSchoolId, name: label }]);
        if (!selectedSchool) setSelectedSchool(userSchoolId);
      }
      return;
    }
    try {
      const res = await api.get('/schools');
      setSchools(res.data);
      if (res.data.length > 0 && !selectedSchool) {
        setSelectedSchool(res.data[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch schools:', error);
    }
  };

  const fetchData = async () => {
    if (!selectedSchool) return;
    
    setLoading(true);
    try {
      const [assignmentsRes, teachersRes, classesRes, subjectsRes] = await Promise.all([
        api.get(`/teacher-assignments?school_id=${selectedSchool}`),
        api.get(`/teachers?school_id=${selectedSchool}`),
        api.get(`/classes?school_id=${selectedSchool}`),
        api.get(`/subjects?school_id=${selectedSchool}`),
      ]);
      
      setAssignments(assignmentsRes.data);
      setTeachers(teachersRes.data);
      setClasses(classesRes.data);
      setSubjects(subjectsRes.data);
      
      // Fetch workloads for each teacher. These are independent of each other,
      // so they go out in parallel — the previous sequential `await` inside a
      // for-loop turned 20 independent calls into a 20-deep request waterfall
      // (each one paying a full round-trip before the next was even issued).
      const shown = teachersRes.data.slice(0, 20); // Limit to first 20 for performance
      const workloadResults = await Promise.all(
        shown.map(teacher =>
          api.get(`/teachers/${teacher.id}/workload`)
            .then(res => [teacher.id, res.data])
            .catch(() => null) // Ignore individual errors
        )
      );
      const workloads = Object.fromEntries(workloadResults.filter(Boolean));
      setTeacherWorkloads(workloads);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchools();
  }, []);

  useEffect(() => {
    if (selectedSchool) {
      fetchData();
    }
  }, [selectedSchool]);

  const handleCreateAssignment = async () => {
    if (!newAssignment.teacher_id || !newAssignment.class_id || !newAssignment.subject_id) {
      nassaqError(t('pleaseSelectTeacherClassAndSubject'));
      return;
    }

    const existingAssignment = assignments.find(
      a => a.teacher_id === newAssignment.teacher_id && a.subject_id === newAssignment.subject_id
    );
    if (existingAssignment) {
      nassaqWarning(t('thisSubjectIsAlreadyAssignedToThisTeacher'));
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/teacher-assignments', {
        ...newAssignment,
        school_id: selectedSchool,
      });
      toast.success(t('assignmentAddedSuccessfully'));
      setCreateDialogOpen(false);
      setNewAssignment({
        teacher_id: '',
        class_id: '',
        subject_id: '',
        weekly_sessions: 4,
        academic_year: '2026-2027',
        semester: 1,
      });
      fetchData();
    } catch (error) {
      const detail = error.response?.data?.detail ?? getApiErrorMessage(error);
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(d => d.msg || JSON.stringify(d)).join(', ') : (t('failedToAddAssignment'));
      nassaqError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteAssignment = async (assignmentId) => {
    nassaqConfirm(
      t('areYouSureYouWantToDeleteThisAssignment'),
      async () => {
        try {
          await api.delete(`/teacher-assignments/${assignmentId}`);
          toast.success(t('assignmentDeleted'));
          setAssignments(prev => prev.filter(a => a.id !== assignmentId));
        } catch (error) {
          nassaqError(t('failedToDeleteAssignment'));
        }
      }
    );
  };

  const handleUpdateRank = async (teacherId, newRank) => {
    try {
      await api.put(`/teachers/${teacherId}/rank?rank=${newRank}`);
      toast.success(t('teacherRankUpdated'));
      fetchData();
    } catch (error) {
      nassaqError(t('failedToUpdateRank'));
    }
  };

  const getWorkloadStatus = (teacherId) => {
    const workload = teacherWorkloads[teacherId];
    if (!workload) return null;
    
    const { total_assigned_sessions, weekly_hours_max, weekly_hours_min, is_overloaded, is_underloaded } = workload;
    const percentage = Math.min((total_assigned_sessions / weekly_hours_max) * 100, 100);
    
    return {
      percentage,
      total: total_assigned_sessions,
      max: weekly_hours_max,
      min: weekly_hours_min,
      isOverloaded: is_overloaded,
      isUnderloaded: is_underloaded,
    };
  };

  const filteredAssignments = assignments.filter(a => {
    const teacherName = a.teacher_name?.toLowerCase() || '';
    const className = a.class_name?.toLowerCase() || '';
    const subjectName = a.subject_name?.toLowerCase() || '';
    const search = searchTerm.toLowerCase();
    return teacherName.includes(search) || className.includes(search) || subjectName.includes(search);
  });

  // Group assignments by teacher
  const assignmentsByTeacher = filteredAssignments.reduce((acc, assignment) => {
    if (!acc[assignment.teacher_id]) {
      acc[assignment.teacher_id] = {
        teacher_name: assignment.teacher_name,
        teacher_id: assignment.teacher_id,
        assignments: [],
      };
    }
    acc[assignment.teacher_id].assignments.push(assignment);
    return acc;
  }, {});

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="teacher-assignments-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" asChild className="rounded-xl">
                <Link to="/principal/schedule">
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  {t('teacherAssignments')}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('assignTeachersToClassesAndSubjects')}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Actions Bar */}
          <div className="flex flex-col md:flex-row gap-4 justify-between">
            <div className="flex gap-4 items-center flex-1">
              <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                <SelectTrigger className="w-[280px] rounded-xl" data-testid="school-select">
                  <SelectValue placeholder={t('selectSchool')} />
                </SelectTrigger>
                <SelectContent>
                  {schools.map(school => (
                    <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder={t('search')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-input"
                />
              </div>
            </div>

            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-assignment-btn">
                  <Plus className="h-5 w-5 me-2" />
                  {t('addAssignment')}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {t('assignTeacherToClassSubject')}
                  </DialogTitle>
                  <DialogDescription>
                    {t('selectTheTeacherClassAndSubject')}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label>{t('teacher5')}</Label>
                    <Select 
                      value={newAssignment.teacher_id} 
                      onValueChange={(value) => setNewAssignment({ ...newAssignment, teacher_id: value })}
                    >
                      <SelectTrigger className="rounded-xl" data-testid="teacher-select">
                        <SelectValue placeholder={t('selectTeacher')} />
                      </SelectTrigger>
                      <SelectContent>
                        {teachers.map(teacher => (
                          <SelectItem key={teacher.id} value={teacher.id}>
                            <div className="flex items-center gap-2">
                              <UserCheck className="h-4 w-4 text-muted-foreground" />
                              {teacher.full_name}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>{t('class2')}</Label>
                    <Select 
                      value={newAssignment.class_id} 
                      onValueChange={(value) => setNewAssignment({ ...newAssignment, class_id: value })}
                    >
                      <SelectTrigger className="rounded-xl" data-testid="class-select">
                        <SelectValue placeholder={t('selectClass')} />
                      </SelectTrigger>
                      <SelectContent>
                        {classes.map(cls => (
                          <SelectItem key={cls.id} value={cls.id}>
                            <div className="flex items-center gap-2">
                              <GraduationCap className="h-4 w-4 text-muted-foreground" />
                              {cls.name}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>{t('subject2')}</Label>
                    <Select 
                      value={newAssignment.subject_id} 
                      onValueChange={(value) => setNewAssignment({ ...newAssignment, subject_id: value })}
                    >
                      <SelectTrigger className="rounded-xl" data-testid="subject-select">
                        <SelectValue placeholder={t('selectSubject')} />
                      </SelectTrigger>
                      <SelectContent>
                        {subjects.map(subject => (
                          <SelectItem key={subject.id} value={subject.id}>
                            <div className="flex items-center gap-2">
                              <BookOpen className="h-4 w-4 text-muted-foreground" />
                              {subject.name || subject.name_ar || subject.name_en || subject.id}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('weeklySessions')}</Label>
                      <Input
                        type="number"
                        min={1}
                        max={10}
                        value={newAssignment.weekly_sessions}
                        onChange={(e) => setNewAssignment({ ...newAssignment, weekly_sessions: parseInt(e.target.value) || 4 })}
                        className="rounded-xl"
                        data-testid="weekly-sessions-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('semester')}</Label>
                      <Select 
                        value={String(newAssignment.semester)} 
                        onValueChange={(value) => setNewAssignment({ ...newAssignment, semester: parseInt(value) })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1">{t('semester1')}</SelectItem>
                          <SelectItem value="2">{t('semester2')}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                    {t('cancel')}
                  </Button>
                  <Button 
                    onClick={handleCreateAssignment} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-assignment-btn"
                  >
                    {submitting ? (
                      <><Loader2 className="h-4 w-4 animate-spin me-2" />{t('adding')}</>
                    ) : (
                      t('add')
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-brand-turquoise/10">
                  <UserCheck className="h-6 w-6 text-brand-turquoise" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{teachers.length}</p>
                  <p className="text-sm text-muted-foreground">{t('teachersLabel')}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-brand-purple/10">
                  <GraduationCap className="h-6 w-6 text-brand-purple" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{classes.length}</p>
                  <p className="text-sm text-muted-foreground">{t('classes4')}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-brand-navy/10">
                  <BookOpen className="h-6 w-6 text-brand-navy dark:text-brand-gold" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{subjects.length}</p>
                  <p className="text-sm text-muted-foreground">{t('subjectsLabel')}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="card-nassaq">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 rounded-xl bg-green-500/10">
                  <CheckCircle2 className="h-6 w-6 text-green-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{assignments.length}</p>
                  <p className="text-sm text-muted-foreground">{t('assignments2')}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Assignments by Teacher */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : Object.keys(assignmentsByTeacher).length === 0 ? (
            <Card className="card-nassaq">
              <CardContent className="text-center py-16">
                <UserCheck className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <p className="text-muted-foreground mb-4">
                  {t('noAssignmentsFound')}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {Object.values(assignmentsByTeacher).map((teacherData) => {
                const workloadStatus = getWorkloadStatus(teacherData.teacher_id);
                const teacher = teachers.find(t => t.id === teacherData.teacher_id);
                const rank = teacher?.rank || 'practitioner';
                const rankConfig = RANK_CONFIG[rank];
                
                return (
                  <Card key={teacherData.teacher_id} className="card-nassaq overflow-hidden" data-testid={`teacher-card-${teacherData.teacher_id}`}>
                    <CardHeader className="pb-3 bg-muted/30">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 rounded-full bg-brand-turquoise/10 flex items-center justify-center">
                            <UserCheck className="h-6 w-6 text-brand-turquoise" />
                          </div>
                          <div>
                            <CardTitle className="font-cairo text-lg">{teacherData.teacher_name}</CardTitle>
                            <div className="flex items-center gap-2 mt-1">
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Select 
                                      value={rank} 
                                      onValueChange={(value) => handleUpdateRank(teacherData.teacher_id, value)}
                                    >
                                      <SelectTrigger className={`h-7 w-auto px-2 text-xs rounded-lg border-0 ${rankConfig.color}`}>
                                        <Award className="h-3 w-3 me-1" />
                                        <SelectValue />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {Object.entries(RANK_CONFIG).map(([key, config]) => (
                                          <SelectItem key={key} value={key}>
                                            {isRTL ? config.label.ar : config.label.en}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    <p>{t('clickToChangeRank')}</p>
                                  </TooltipContent>
                                </Tooltip>
                              </TooltipProvider>
                              
                              <Badge variant="secondary" className="text-xs">
                                {teacherData.assignments.length} {t('assignmentsCount')}
                              </Badge>
                            </div>
                          </div>
                        </div>
                        
                        {/* Workload Progress */}
                        {workloadStatus && (
                          <div className="w-48">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span className="text-muted-foreground">{t('workload')}</span>
                              <span className={`font-medium ${workloadStatus.isOverloaded ? 'text-red-500' : workloadStatus.isUnderloaded ? 'text-amber-500' : 'text-green-500'}`}>
                                {workloadStatus.total} / {workloadStatus.max}
                              </span>
                            </div>
                            <Progress 
                              value={workloadStatus.percentage} 
                              className={`h-2 ${workloadStatus.isOverloaded ? '[&>div]:bg-red-500' : workloadStatus.isUnderloaded ? '[&>div]:bg-amber-500' : '[&>div]:bg-green-500'}`}
                            />
                            {workloadStatus.isOverloaded && (
                              <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3" />
                                {t('overloaded')}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="p-0">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="ps-4">{t('class')}</TableHead>
                            <TableHead>{t('subject')}</TableHead>
                            <TableHead>{t('weeklySessions')}</TableHead>
                            <TableHead>{t('semester')}</TableHead>
                            <TableHead className="w-12"></TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {teacherData.assignments.map((assignment) => (
                            <TableRow key={assignment.id} data-testid={`assignment-row-${assignment.id}`}>
                              <TableCell className="ps-4">
                                <div className="flex items-center gap-2">
                                  <GraduationCap className="h-4 w-4 text-brand-purple" />
                                  {assignment.class_name}
                                </div>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <BookOpen className="h-4 w-4 text-brand-navy dark:text-brand-gold" />
                                  {assignment.subject_name}
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge variant="secondary" className="rounded-lg">
                                  <Clock className="h-3 w-3 me-1" />
                                  {assignment.weekly_sessions} {t('sessionsLabel')}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                {isRTL ? `الفصل ${assignment.semester}` : `Semester ${assignment.semester}`}
                              </TableCell>
                              <TableCell>
                                <Button 
                                  variant="ghost" 
                                  size="icon" 
                                  className="rounded-xl text-red-500 hover:text-red-600 hover:bg-red-50"
                                  onClick={() => handleDeleteAssignment(assignment.id)}
                                  data-testid={`delete-assignment-${assignment.id}`}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Sidebar>
  );
};
