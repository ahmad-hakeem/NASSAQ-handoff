import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  UserCheck,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  Trash2,
  Edit,
  Mail,
  Phone,
  Award,
  Loader2,
  ArrowLeft,
  Upload,
  UserPlus,
  GraduationCap,
  ChevronDown,
  ChevronUp,
  Undo2,
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
import { AddTeacherWizard } from '../components/wizards/AddTeacherWizard';
import { BulkTeacherImport } from '../components/wizards/BulkTeacherImport';
import AddStudentWizard from '../components/wizards/AddStudentWizard';
import { TeacherSchedulePrefsDialog } from '../components/teacher/TeacherSchedulePrefsDialog';
import { getApiErrorMessage } from '../utils/apiError';

export const TeachersPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [teachers, setTeachers] = useState([]);
  const [schools, setSchools] = useState([]);
  const [grades, setGrades] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [schoolSettings, setSchoolSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [studentWizardOpen, setStudentWizardOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  const [editingTeacher, setEditingTeacher] = useState(null);
  const [deletedExpanded, setDeletedExpanded] = useState(false);
  const [restoringId, setRestoringId] = useState(null);

  // Check if user is a school-level user (not platform admin)
  const { nassaqError, nassaqWarning, nassaqConfirm, nassaqSuccess, showAlert } = useNassaqAlert();
  const isSchoolLevel = user?.role && !user.role.startsWith('platform_');
  const userSchoolId = user?.tenant_id;
  
  const [newTeacher, setNewTeacher] = useState({
    full_name: '',
    full_name_en: '',
    email: '',
    phone: '',
    school_id: userSchoolId || '',
    specialization: '',
    years_of_experience: 0,
    qualification: '',
    gender: '',
  });

  const fetchData = async () => {
    try {
      // For school-level users, only fetch teachers (tenant-scoped by backend)
      // For platform admins, also fetch schools for filtering
      // Task #645 — always request include_deleted=true so the
      // "Recently deleted" section is populated. The backend silently
      // ignores the flag for non-admin callers.
      const teachersRes = await api.get('/teachers', { params: { include_deleted: true } });
      setTeachers(teachersRes.data);
      
      // Fetch grades and classes for student wizard, plus subjects/settings
      // for the schedule preferences dialog.
      try {
        const [gradesRes, classesRes, subjectsRes, settingsRes] = await Promise.all([
          api.get('/reference/grades').catch(() => ({ data: [] })),
          api.get('/classes').catch(() => ({ data: [] })),
          api.get('/subjects').catch(() => ({ data: [] })),
          api.get('/school/settings').catch(() => ({ data: {} })),
        ]);
        setGrades(gradesRes.data || []);
        setClasses(classesRes.data || []);
        setSubjects(Array.isArray(subjectsRes.data) ? subjectsRes.data : []);
        setSchoolSettings(settingsRes.data || {});
      } catch (e) {
        console.error('Error fetching grades/classes:', e);
        setGrades([]);
        setClasses([]);
        setSubjects([]);
        setSchoolSettings({});
      }
      
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
      // Set default school_id for new teacher form
      if (userSchoolId) {
        setNewTeacher(prev => ({ ...prev, school_id: userSchoolId }));
      }
    }
  }, [user]);

  const handleCreateTeacher = async () => {
    // Use user's school_id for school-level users
    const schoolId = isSchoolLevel ? userSchoolId : newTeacher.school_id;
    
    if (!newTeacher.full_name || !newTeacher.email || !schoolId || !newTeacher.specialization) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/teachers', { ...newTeacher, school_id: schoolId });
      toast.success(t('teacherAddedSuccessfully'));
      setCreateDialogOpen(false);
      setNewTeacher({
        full_name: '',
        full_name_en: '',
        email: '',
        phone: '',
        school_id: '',
        specialization: '',
        years_of_experience: 0,
        qualification: '',
        gender: '',
      });
      setTeachers(prev => [...prev, response.data]);
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('failedToAddTeacher')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTeacher = async (teacherId) => {
    nassaqConfirm(
      t('areYouSureYouWantToDeleteThisTeacherAllRelatedData'),
      async () => {
        try {
          const res = await api.delete(`/teachers/${teacherId}`);
          const cleanup = res.data?.cleanup;
          let msg = t('teacherDeletedSuccessfully');
          if (cleanup) {
            const parts = Object.entries(cleanup).filter(([_, v]) => v > 0).map(([k, v]) => `${k}: ${v}`);
            if (parts.length > 0) msg += ` (${parts.join(', ')})`;
          }
          toast.success(msg);
          await fetchData();
        } catch (error) {
          nassaqError(getApiErrorMessage(error) || (t('failedToDeleteTeacher')));
        }
      },
      { title: t('confirmDelete'), confirmText: t('yesDelete') || (isRTL ? 'نعم، حذف' : 'Yes, delete'), cancelText: t('cancel') }
    );
  };

  // Task #645 — restore a soft-deleted teacher. Dependent rows
  // (teacher_assignments, teacher_class_assignments, teacher_subjects,
  // timetable_sessions, class_sessions) stay inactive on purpose so the
  // principal can re-link them deliberately; we surface those counts in
  // a NassaqAlertDialog.
  const handleRestoreTeacher = async (teacher) => {
    const tName = teacher?.full_name || '';
    nassaqConfirm(
      isRTL
        ? `هل تريد استعادة المعلم "${tName}"؟ سيظهر المعلم مرة أخرى في القائمة، لكنك ستحتاج إلى إعادة ربط الفصول والمواد والجدول والحساب يدويًا.`
        : `Restore teacher "${tName}"? They will reappear in the list, but you'll need to re-link their classes, subjects, schedule, and user account manually.`,
      async () => {
        setRestoringId(teacher.id);
        try {
          const res = await api.post(`/teachers/${teacher.id}/restore`);
          const dependents = res?.data?.inactive_dependents || {};
          const labelMap = {
            teacher_assignments: isRTL ? 'إسنادات المعلم' : 'Teacher assignments',
            teacher_class_assignments: isRTL ? 'إسنادات معلم-فصل' : 'Teacher–class links',
            teacher_subjects: isRTL ? 'مواد المعلم' : 'Teacher subjects',
            timetable_sessions: isRTL ? 'حصص الجدول' : 'Timetable sessions',
            class_sessions: isRTL ? 'حصص الفصل' : 'Class sessions',
          };
          const lines = Object.entries(dependents)
            .filter(([, v]) => Number(v) > 0)
            .map(([k, v]) => `• ${labelMap[k] || k}: ${v}`);
          const header = isRTL
            ? `تمت استعادة المعلم "${tName}" بنجاح.`
            : `Teacher "${tName}" was restored successfully.`;
          const followUp = lines.length
            ? (isRTL
                ? `\n\nهذه العناصر المرتبطة لا تزال غير مُفعَّلة وتحتاج إلى إعادة ربط:\n${lines.join('\n')}`
                : `\n\nThe following linked items are still inactive and need to be re-linked:\n${lines.join('\n')}`)
            : (isRTL
                ? '\n\nلا توجد عناصر مرتبطة بحاجة إلى إعادة ربط.'
                : '\n\nNo linked items need re-linking.');
          showAlert({
            type: lines.length ? 'warning' : 'success',
            title: isRTL ? 'تمت استعادة المعلم' : 'Teacher restored',
            message: header + followUp,
            confirmText: isRTL ? 'حسناً' : 'OK',
          });
          await fetchData();
        } catch (error) {
          nassaqError(
            getApiErrorMessage(error)
              || (isRTL ? 'فشل استعادة المعلم' : 'Failed to restore teacher')
          );
        } finally {
          setRestoringId(null);
        }
      },
      {
        title: isRTL ? 'تأكيد الاستعادة' : 'Confirm restore',
        confirmText: isRTL ? 'نعم، استعادة' : 'Yes, restore',
        cancelText: isRTL ? 'إلغاء' : 'Cancel',
      }
    );
  };

  const formatDeletedAt = (iso) => {
    if (!iso) return '-';
    try {
      const d = new Date(iso);
      return d.toLocaleString(isRTL ? 'ar' : 'en', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  // Task #645 — soft-deleted teachers (is_active=false AND deleted_at!=null)
  // live in their own "Recently deleted" section, not the main table.
  const isDeleted = (teacher) => teacher.is_active === false && !!teacher.deleted_at;

  const filteredTeachers = teachers.filter(teacher => {
    if (isDeleted(teacher)) return false;
    const q = (searchTerm || '').toLowerCase();
    const matchesSearch = (teacher.full_name || '').toLowerCase().includes(q) ||
                         (teacher.email || '').toLowerCase().includes(q) ||
                         (teacher.specialization || '').toLowerCase().includes(q);
    const matchesSchool = selectedSchool === 'all' || teacher.school_id === selectedSchool;
    return matchesSearch && matchesSchool;
  }).sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'ar'));

  const deletedTeachers = teachers
    .filter(teacher => isDeleted(teacher))
    .filter(teacher => selectedSchool === 'all' || teacher.school_id === selectedSchool)
    .sort((a, b) => {
      const ad = a.deleted_at || '';
      const bd = b.deleted_at || '';
      return bd.localeCompare(ad);
    });

  const getSchoolName = (schoolId) => {
    const school = schools.find(s => s.id === schoolId);
    return school?.name || '-';
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="teachers-page">
        {/* Header */}
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
                  {isRTL ? 'إدارة المستخدمين والفصول' : 'Users & Classes Management'}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? `${filteredTeachers.length} معلم` : `${filteredTeachers.length} teachers`}
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
            <div className="flex flex-1 gap-4">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder={t('searchTeachers')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-teachers-input"
                />
              </div>
              
              {/* Only show school filter for platform admins */}
              {!isSchoolLevel && schools.length > 0 && (
                <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                  <SelectTrigger className="w-[200px] rounded-xl">
                    <SelectValue placeholder={t('allSchools')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('allSchools')}</SelectItem>
                    {schools.map(school => (
                      <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Add Teacher Buttons */}
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                className="rounded-xl"
                onClick={() => setBulkImportOpen(true)}
                data-testid="bulk-import-btn"
              >
                <Upload className="h-5 w-5 me-2" />
                {t('bulkImport')}
              </Button>
              
              <Button 
                className="bg-brand-navy hover:bg-brand-navy/90 rounded-xl" 
                onClick={() => setStudentWizardOpen(true)}
                data-testid="add-student-btn"
              >
                <GraduationCap className="h-5 w-5 me-2" />
                {t('addStudent')}
              </Button>
              
              <Button 
                className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" 
                onClick={() => setWizardOpen(true)}
                data-testid="add-teacher-btn"
              >
                <UserPlus className="h-5 w-5 me-2" />
                {t('addTeacher')}
              </Button>
            </div>

            {/* Legacy Dialog - keep for backward compatibility */}
            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {t('addNewTeacher')}
                  </DialogTitle>
                  <DialogDescription>
                    {t('enterTheNewTeacherDetails')}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('fullNameArabic2')}</Label>
                      <Input
                        value={newTeacher.full_name}
                        onChange={(e) => setNewTeacher({ ...newTeacher, full_name: e.target.value })}
                        placeholder={t('ahmedMohammed')}
                        className="rounded-xl"
                        data-testid="teacher-name-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('fullNameEnglish')}</Label>
                      <Input
                        value={newTeacher.full_name_en}
                        onChange={(e) => setNewTeacher({ ...newTeacher, full_name_en: e.target.value })}
                        placeholder="Ahmed Mohammed"
                        className="rounded-xl"
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('email4')}</Label>
                      <Input
                        type="email"
                        value={newTeacher.email}
                        onChange={(e) => setNewTeacher({ ...newTeacher, email: e.target.value })}
                        placeholder="teacher@school.com"
                        className="rounded-xl"
                        data-testid="teacher-email-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('phone3')}</Label>
                      <Input
                        value={newTeacher.phone}
                        onChange={(e) => setNewTeacher({ ...newTeacher, phone: e.target.value })}
                        placeholder="+966..."
                        className="rounded-xl"
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('school2')}</Label>
                      <Select 
                        value={newTeacher.school_id} 
                        onValueChange={(value) => setNewTeacher({ ...newTeacher, school_id: value })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="teacher-school-select">
                          <SelectValue placeholder={t('selectSchool')} />
                        </SelectTrigger>
                        <SelectContent>
                          {schools.map(school => (
                            <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('specialization2')}</Label>
                      <Input
                        value={newTeacher.specialization}
                        onChange={(e) => setNewTeacher({ ...newTeacher, specialization: e.target.value })}
                        placeholder={t('mathematics')}
                        className="rounded-xl"
                        data-testid="teacher-specialization-input"
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'سنوات الخبرة' : 'Years of Experience'}</Label>
                      <Input
                        type="number"
                        value={newTeacher.years_of_experience}
                        onChange={(e) => setNewTeacher({ ...newTeacher, years_of_experience: parseInt(e.target.value) || 0 })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'المؤهل العلمي' : 'Qualification'}</Label>
                      <Input
                        value={newTeacher.qualification}
                        onChange={(e) => setNewTeacher({ ...newTeacher, qualification: e.target.value })}
                        placeholder={isRTL ? 'بكالوريوس' : 'Bachelor'}
                        className="rounded-xl"
                      />
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>{t('gender')}</Label>
                    <Select 
                      value={newTeacher.gender} 
                      onValueChange={(value) => setNewTeacher({ ...newTeacher, gender: value })}
                    >
                      <SelectTrigger className="rounded-xl">
                        <SelectValue placeholder={t('selectGender')} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="male">{t('male')}</SelectItem>
                        <SelectItem value="female">{t('female')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                    {t('cancel')}
                  </Button>
                  <Button 
                    onClick={handleCreateTeacher} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-teacher-btn"
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

          {/* Teachers Table */}
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
                        <TableHead>{t('teacher2')}</TableHead>
                        <TableHead>{t('specialization')}</TableHead>
                        <TableHead>{t('school')}</TableHead>
                        <TableHead>{t('experience2')}</TableHead>
                        <TableHead>{t('status2')}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredTeachers.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                            <UserCheck className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{t('noTeachersFound')}</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredTeachers.map((teacher) => (
                          <TableRow key={teacher.id} data-testid={`teacher-row-${teacher.id}`}>
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-brand-purple/10 flex items-center justify-center">
                                  <UserCheck className="h-5 w-5 text-brand-purple" />
                                </div>
                                <div>
                                  <div className="font-medium">{teacher.full_name}</div>
                                  <div className="text-sm text-muted-foreground flex items-center gap-1">
                                    <Mail className="h-3 w-3" />
                                    {teacher.email}
                                  </div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="rounded-lg">
                                {teacher.specialization}
                              </Badge>
                            </TableCell>
                            <TableCell>{getSchoolName(teacher.school_id)}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <Award className="h-4 w-4 text-brand-turquoise" />
                                {teacher.years_of_experience} {isRTL ? 'سنة' : 'years'}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={teacher.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                                {teacher.is_active ? (t('active')) : (t('inactive'))}
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
                                  <DropdownMenuItem
                                    onClick={() => setEditingTeacher(teacher)}
                                    data-testid={`edit-teacher-${teacher.id}`}
                                  >
                                    <Edit className="h-4 w-4 me-2" />
                                    {isRTL ? 'تفضيلات الجدول' : 'Schedule preferences'}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem 
                                    className="text-red-600"
                                    onClick={() => handleDeleteTeacher(teacher.id)}
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

          {/* Task #645 — Recently deleted teachers (soft-deleted rows
              restorable via POST /teachers/{id}/restore). Only rendered
              when there is at least one such row. */}
          {deletedTeachers.length > 0 && (
            <Card className="card-nassaq border-red-200" data-testid="recently-deleted-teachers-card">
              <CardContent className="p-0">
                <button
                  type="button"
                  onClick={() => setDeletedExpanded(v => !v)}
                  className="w-full flex items-center justify-between px-6 py-4 text-start"
                  data-testid="recently-deleted-toggle"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
                      <Trash2 className="h-5 w-5 text-red-600" aria-hidden="true" strokeWidth={1.5} />
                    </div>
                    <div>
                      <div className="font-cairo font-bold text-foreground">
                        {isRTL ? 'المعلمون المحذوفون حديثاً' : 'Recently deleted teachers'}
                      </div>
                      <div className="text-sm text-muted-foreground font-tajawal">
                        {isRTL
                          ? `${deletedTeachers.length} معلم قابل للاستعادة`
                          : `${deletedTeachers.length} teacher${deletedTeachers.length === 1 ? '' : 's'} can be restored`}
                      </div>
                    </div>
                  </div>
                  {deletedExpanded ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
                  )}
                </button>

                {deletedExpanded && (
                  <div className="rounded-b-xl overflow-hidden border-t border-border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('teacher2')}</TableHead>
                          <TableHead>{isRTL ? 'حُذف بواسطة' : 'Deleted by'}</TableHead>
                          <TableHead>{isRTL ? 'تاريخ الحذف' : 'Deleted at'}</TableHead>
                          {!isSchoolLevel && <TableHead>{t('school')}</TableHead>}
                          <TableHead className="w-32"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {deletedTeachers.map((teacher) => (
                          <TableRow
                            key={teacher.id}
                            data-testid={`deleted-teacher-row-${teacher.id}`}
                          >
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-full bg-red-50 flex items-center justify-center">
                                  <UserCheck className="h-4 w-4 text-red-600" aria-hidden="true" strokeWidth={1.5} />
                                </div>
                                <div>
                                  <div className="font-medium">{teacher.full_name}</div>
                                  <div className="text-xs text-muted-foreground">{teacher.specialization || teacher.email}</div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm">
                              {teacher.deleted_by_name
                                || (teacher.deleted_by ? (isRTL ? 'مستخدم محذوف' : 'Unknown user') : '-')}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDeletedAt(teacher.deleted_at)}
                            </TableCell>
                            {!isSchoolLevel && (
                              <TableCell>{getSchoolName(teacher.school_id)}</TableCell>
                            )}
                            <TableCell>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRestoreTeacher(teacher)}
                                disabled={restoringId === teacher.id}
                                className="rounded-xl border-brand-turquoise text-brand-turquoise hover:bg-brand-turquoise/10 hover:text-brand-turquoise"
                                data-testid={`restore-teacher-${teacher.id}`}
                              >
                                {restoringId === teacher.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin me-2" aria-hidden="true" />
                                ) : (
                                  <Undo2 className="h-4 w-4 me-2" aria-hidden="true" strokeWidth={1.5} />
                                )}
                                {isRTL ? 'استعادة' : 'Restore'}
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
        
        {/* Add Teacher Wizard */}
        <AddTeacherWizard 
          open={wizardOpen} 
          onOpenChange={(val) => setWizardOpen(val)}
          onSuccess={() => {
            fetchData();
          }}
        />
        
        {/* Bulk Import Wizard */}
        <BulkTeacherImport 
          open={bulkImportOpen} 
          onClose={() => {
            setBulkImportOpen(false);
            fetchData();
          }} 
        />
        
        {/* Add Student Wizard */}
        <AddStudentWizard 
          open={studentWizardOpen}
          onOpenChange={setStudentWizardOpen}
          isRTL={isRTL}
          api={api}
          grades={grades}
          classes={classes}
          onSuccess={() => {
            toast.success(t('studentAddedSuccessfully'));
            fetchData();
          }}
        />

        {/* Schedule Preferences & Constraints Dialog (Task #95) */}
        <TeacherSchedulePrefsDialog
          open={!!editingTeacher}
          onClose={() => setEditingTeacher(null)}
          teacher={editingTeacher}
          api={api}
          isRTL={isRTL}
          subjects={subjects}
          workingDays={(() => {
            const wd = schoolSettings?.working_days;
            if (Array.isArray(wd)) return wd;
            if (wd && typeof wd === 'object') return Object.entries(wd).filter(([, v]) => v).map(([k]) => k);
            return undefined;
          })()}
          periodsPerDay={schoolSettings?.periods_per_day || 7}
          onSaved={(updated) => {
            setTeachers(prev => prev.map(tr => tr.id === updated.id ? { ...tr, ...updated } : tr));
          }}
        />
      </div>
    </Sidebar>
  );
};
