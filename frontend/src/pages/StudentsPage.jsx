import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  GraduationCap,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  Trash2,
  Edit,
  Phone,
  Loader2,
  ArrowLeft,
  User,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Link } from 'react-router-dom';
import AddStudentWizard from '../components/wizards/AddStudentWizard';
import { getApiErrorMessage } from '../utils/apiError';

export const StudentsPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [students, setStudents] = useState([]);
  const [schools, setSchools] = useState([]);
  const [classes, setClasses] = useState([]);
  // FIX (C12 follow-up): AddStudentWizard requires a populated grades list to
  // enable the "Next" button on step 1. Other pages fetch from `/reference/grades`.
  const [grades, setGrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState('all');
  const [selectedClass, setSelectedClass] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  
  // Check if user is a school-level user (not platform admin)
  const { nassaqError, nassaqWarning, nassaqConfirm } = useNassaqAlert();
  const isSchoolLevel = user?.role && !user.role.startsWith('platform_');
  const userSchoolId = user?.tenant_id;
  
  const [newStudent, setNewStudent] = useState({
    full_name: '',
    full_name_en: '',
    email: '',
    phone: '',
    school_id: userSchoolId || '',
    class_id: '',
    student_number: '',
    date_of_birth: '',
    gender: '',
    parent_phone: '',
    parent_name: '',
  });

  const fetchData = async () => {
    try {
      // For school-level users, only fetch students and classes (tenant-scoped by backend)
      // For platform admins, also fetch schools for filtering
      const [studentsRes, classesRes, gradesRes] = await Promise.all([
        api.get('/students'),
        api.get('/classes'),
        api.get('/reference/grades').catch(() => ({ data: [] })),
      ]);
      // The /students endpoint returns { students: [...], total: N } in its
      // paginated shape, or a plain array in some legacy paths. Extract the
      // array either way so students state is always Array.isArray() === true.
      const studentsRaw = studentsRes.data;
      setStudents(Array.isArray(studentsRaw) ? studentsRaw : (studentsRaw?.students || []));
      setClasses(classesRes.data);
      setGrades(gradesRes.data || []);
      
      // Only fetch schools list for platform admins
      if (!isSchoolLevel) {
        try {
          const schoolsRes = await api.get('/schools');
          setSchools(schoolsRes.data);
        } catch (e) {
          console.error('Error fetching schools list:', e);
          setSchools([]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchData();
      // Set default school_id for new student form
      if (userSchoolId) {
        setNewStudent(prev => ({ ...prev, school_id: userSchoolId }));
      }
    }
  }, [user]);

  const handleCreateStudent = async () => {
    // Use user's school_id for school-level users
    const schoolId = isSchoolLevel ? userSchoolId : newStudent.school_id;
    
    if (!newStudent.full_name || !schoolId || !newStudent.student_number) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      // FIX (C8): The `/students` route on student_management_routes expects
      // `full_name_ar`, but this form historically posted `full_name`. Send
      // both keys so the backend receives the canonical Arabic name.
      const response = await api.post('/students', {
        ...newStudent,
        full_name_ar: newStudent.full_name,
        school_id: schoolId,
      });
      toast.success(t('studentAddedSuccessfully'));
      setCreateDialogOpen(false);
      setNewStudent({
        full_name: '',
        full_name_en: '',
        email: '',
        phone: '',
        school_id: userSchoolId || '',
        class_id: '',
        student_number: '',
        date_of_birth: '',
        gender: '',
        parent_phone: '',
        parent_name: '',
      });
      setStudents(prev => [...prev, response.data]);
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('failedToAddStudent')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteStudent = async (studentId) => {
    nassaqConfirm(
      t('areYouSureYouWantToDeleteThisStudentAllRelatedData'),
      async () => {
        if (process.env.NODE_ENV === 'development') {
          // Step 4 — callback entry: confirms the confirmation dialog invoked the callback.
          // If this never appears in the console the dialog is swallowing the callback.
          console.debug('[handleDeleteStudent] callback entered', {
            studentId,
            studentIdType: typeof studentId,
            selectedSchool,
            selectedClass,
          });
        }

        // Step 1 — pre-call trace: surfaces ID value/type and active filter state.
        if (process.env.NODE_ENV === 'development') {
          console.debug('[handleDeleteStudent] pre-call', {
            studentId,
            studentIdType: typeof studentId,
            selectedSchool,
            selectedClass,
          });
        }

        try {
          const res = await api.delete(`/students/${studentId}`);

          // Step 2 — response trace: surfaces soft-errors (HTTP 200 with error:true)
          // that would silently bail out of the state update.
          if (process.env.NODE_ENV === 'development') {
            console.debug('[handleDeleteStudent] API response', res.data);
          }

          // API integrity: treat an explicit error body as a failure even on
          // HTTP 200, which some proxies emit when the real status is hidden.
          if (res.data?.error) {
            if (process.env.NODE_ENV === 'development') {
              console.debug('[handleDeleteStudent] soft-error bail-out', {
                error: res.data?.error,
                detail: res.data?.detail,
              });
            }
            nassaqError(res.data?.detail || t('failedToDeleteStudent'));
            return;
          }

          const cleanup = res.data?.cleanup;
          let msg = t('studentDeletedSuccessfully');
          if (cleanup) {
            const parts = Object.entries(cleanup).filter(([_, v]) => v > 0).map(([k, v]) => `${k}: ${v}`);
            if (parts.length > 0) msg += ` (${parts.join(', ')})`;
          }
          toast.success(msg);

          // Functional update avoids stale-closure issues.
          // Both sides are explicitly wrapped in String() to reconcile integer
          // IDs from the backend with any string representation at the call
          // site. The `?? s._id` fallback handles object-shape variants without
          // requiring a data migration. Do NOT simplify either String() call.
          setStudents(prev => {
            const safePrev = Array.isArray(prev) ? prev : [];

            // Step 3 — filter trace: confirms whether the functional update
            // actually removed the target record.
            if (process.env.NODE_ENV === 'development') {
              const comparisons = safePrev.map(s => ({
                sid: s.id ?? s._id,
                sidStr: String(s.id ?? s._id),
                studentIdStr: String(studentId),
                willKeep: String(s.id ?? s._id) !== String(studentId),
              }));
              const removed = comparisons.filter(c => !c.willKeep);
              console.debug('[handleDeleteStudent] filter pass', {
                prevCount: safePrev.length,
                removedCount: removed.length,
                removedIds: removed.map(c => c.sid),
                comparisons,
              });
            }

            return safePrev.filter(s => String(s.id ?? s._id) !== String(studentId));
          });
        } catch (error) {
          nassaqError(getApiErrorMessage(error) || t('failedToDeleteStudent'));
        }
      },
      { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') }
    );
  };

  const filteredStudents = students.filter(student => {
    const term = searchTerm.toLowerCase();
    const matchesSearch = !term ||
      (student.full_name || '').toLowerCase().includes(term) ||
      (student.student_number || '').toLowerCase().includes(term) ||
      (student.email || '').toLowerCase().includes(term);
    const matchesSchool = selectedSchool === 'all' || student.school_id === selectedSchool;
    const matchesClass = selectedClass === 'all' || student.class_id === selectedClass;
    return matchesSearch && matchesSchool && matchesClass;
  }).sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'ar'));

  const getSchoolName = (schoolId) => {
    const school = schools.find(s => s.id === schoolId);
    return school?.name || '-';
  };

  const filteredClasses = classes.filter(c => 
    selectedSchool === 'all' || c.school_id === selectedSchool
  );

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="students-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" asChild className="rounded-xl">
                <Link to="/admin">
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  {t('studentsManagement')}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? `${filteredStudents.length} طالب` : `${filteredStudents.length} students`}
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
          <div className="flex flex-col md:flex-row gap-4 justify-between">
            <div className="flex flex-1 gap-4 flex-wrap">
              <div className="relative flex-1 min-w-[200px] max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder={t('searchStudents2')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-students-input"
                />
              </div>
              
              {/* Only show school filter for platform admins */}
              {!isSchoolLevel && schools.length > 0 && (
                <Select value={selectedSchool} onValueChange={(v) => { setSelectedSchool(v); setSelectedClass('all'); }}>
                  <SelectTrigger className="w-[180px] rounded-xl">
                    <SelectValue placeholder={t('school')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('allSchools')}</SelectItem>
                    {schools.map(school => (
                      <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-[180px] rounded-xl">
                  <SelectValue placeholder={t('class')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allClasses')}</SelectItem>
                  {filteredClasses.map(cls => (
                    <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* FIX (C12): The legacy 60vh scrolling modal made it nearly
                impossible to add a student on a phone. Use the existing
                multi-step wizard which handles paging, validation, and
                generated credentials. The old form below is preserved
                temporarily but no longer reachable. */}
            <Button
              className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl"
              data-testid="add-student-btn"
              onClick={() => setCreateDialogOpen(true)}
            >
              <Plus className="h-5 w-5 me-2" />
              {t('addStudent')}
            </Button>
            <AddStudentWizard
              open={createDialogOpen}
              onOpenChange={setCreateDialogOpen}
              onSuccess={() => { setCreateDialogOpen(false); fetchData(); }}
              api={api}
              isRTL={isRTL}
              grades={grades || []}
              classes={classes || []}
            />
          </div>

          <Card className="card-nassaq">
            <CardContent className="p-0">
              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : (
                <div className="rounded-xl overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('student3')}</TableHead>
                        <TableHead>{t('studentNumber')}</TableHead>
                        <TableHead>{t('class')}</TableHead>
                        <TableHead>{t('school')}</TableHead>
                        <TableHead>{t('parent')}</TableHead>
                        <TableHead>{t('status2')}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredStudents.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                            <GraduationCap className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{t('noStudentsFound')}</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredStudents.map((student) => (
                          <TableRow key={student.id} data-testid={`student-row-${student.id}`}>
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-brand-turquoise/10 flex items-center justify-center">
                                  <GraduationCap className="h-5 w-5 text-brand-turquoise" />
                                </div>
                                <div>
                                  <div className="font-medium">{student.full_name}</div>
                                  <div className="text-sm text-muted-foreground">
                                    {student.gender === 'male' ? (t('male')) : (t('female'))}
                                  </div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="font-mono">{student.student_number}</TableCell>
                            <TableCell>
                              <Badge variant="outline" className="rounded-lg">
                                {student.class_name || '-'}
                              </Badge>
                            </TableCell>
                            <TableCell>{getSchoolName(student.school_id)}</TableCell>
                            <TableCell>
                              <div className="text-sm">
                                <div>{student.parent_name || '-'}</div>
                                {student.parent_phone && (
                                  <div className="text-muted-foreground flex items-center gap-1">
                                    <Phone className="h-3 w-3" />
                                    {student.parent_phone}
                                  </div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={student.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                                {student.is_active ? (t('active')) : (t('inactive'))}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem>
                                    <Edit className="h-4 w-4 me-2" />
                                    {t('edit')}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem 
                                    className="text-red-600"
                                    onClick={() => handleDeleteStudent(student.id)}
                                  >
                                    <Trash2 className="h-4 w-4 me-2" />
                                    {t('delete')}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
