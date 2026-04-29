import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
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
  
  // Check if user is a school-level user (not platform admin)
  const { nassaqError, nassaqWarning, nassaqConfirm } = useNassaqAlert();
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
      const teachersRes = await api.get('/teachers');
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
      nassaqError(error.response?.data?.detail || (t('failedToAddTeacher')));
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
          setTeachers(prev => prev.filter(t => t.id !== teacherId));
        } catch (error) {
          nassaqError(error.response?.data?.detail || (t('failedToDeleteTeacher')));
        }
      },
      { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') }
    );
  };

  const filteredTeachers = teachers.filter(teacher => {
    const q = (searchTerm || '').toLowerCase();
    const matchesSearch = (teacher.full_name || '').toLowerCase().includes(q) ||
                         (teacher.email || '').toLowerCase().includes(q) ||
                         (teacher.specialization || '').toLowerCase().includes(q);
    const matchesSchool = selectedSchool === 'all' || teacher.school_id === selectedSchool;
    return matchesSearch && matchesSchool;
  }).sort((a, b) => (a.full_name || '').localeCompare(b.full_name || '', 'ar'));

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
        </div>
        
        {/* Add Teacher Wizard */}
        <AddTeacherWizard 
          open={wizardOpen} 
          onClose={() => {
            setWizardOpen(false);
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
      <HakimAssistant />
    </Sidebar>
  );
};
