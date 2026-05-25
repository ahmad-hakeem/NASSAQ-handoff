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
  FolderOpen,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  Trash2,
  Edit,
  Users,
  Loader2,
  ArrowLeft,
  UserCheck,
  RotateCcw,
} from 'lucide-react';
import { Switch } from '../components/ui/switch';
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

export const ClassesPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [classes, setClasses] = useState([]);
  const [schools, setSchools] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  
  // Check if user is a school-level user (not platform admin)
  const { nassaqError, nassaqWarning, nassaqConfirm } = useNassaqAlert();
  const isSchoolLevel = user?.role && !user.role.startsWith('platform_');
  const userSchoolId = user?.tenant_id;
  
  const gradeLevels = [
    'الأول الابتدائي', 'الثاني الابتدائي', 'الثالث الابتدائي', 'الرابع الابتدائي', 'الخامس الابتدائي', 'السادس الابتدائي',
    'الأول المتوسط', 'الثاني المتوسط', 'الثالث المتوسط',
    'الأول الثانوي', 'الثاني الثانوي', 'الثالث الثانوي',
  ];
  
  const sections = ['أ', 'ب', 'ج', 'د', 'هـ'];
  
  const [newClass, setNewClass] = useState({
    name: '',
    name_en: '',
    school_id: userSchoolId || '',
    grade_level: '',
    section: '',
    capacity: 30,
    homeroom_teacher_id: '',
  });

  const fetchData = async (opts = {}) => {
    const includeInactive = opts.includeInactive ?? showInactive;
    try {
      // For school-level users, only fetch classes and teachers (tenant-scoped by backend)
      // For platform admins, also fetch schools for filtering
      const [classesRes, teachersRes] = await Promise.all([
        api.get('/classes', { params: includeInactive ? { include_inactive: true } : {} }),
        api.get('/teachers'),
      ]);
      setClasses(classesRes.data);
      setTeachers(teachersRes.data);
      
      // Platform admins get the full schools list; school-level users get only their own school
      if (!isSchoolLevel) {
        try {
          const schoolsRes = await api.get('/schools');
          setSchools(schoolsRes.data);
        } catch (e) {
          console.error('Error fetching schools list:', e);
          setSchools([]);
        }
      } else if (userSchoolId) {
        try {
          const schoolRes = await api.get(`/schools/${userSchoolId}`);
          setSchools([schoolRes.data]);
        } catch (e) {
          console.error('Error fetching own school:', e);
          setSchools([]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Set default school_id for new class form
    if (userSchoolId) {
      setNewClass(prev => ({ ...prev, school_id: userSchoolId }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    fetchData({ includeInactive: showInactive });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showInactive]);

  // Auto-generate class name
  useEffect(() => {
    if (newClass.grade_level && newClass.section) {
      const name = `${newClass.grade_level} - ${newClass.section}`;
      setNewClass(prev => ({ ...prev, name }));
    }
  }, [newClass.grade_level, newClass.section]);

  const handleCreateClass = async () => {
    // Use user's school_id for school-level users
    const schoolId = isSchoolLevel ? userSchoolId : newClass.school_id;
    
    if (!newClass.name || !schoolId || !newClass.grade_level) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/classes', { ...newClass, school_id: schoolId });
      toast.success(t('classAddedSuccessfully'));
      setCreateDialogOpen(false);
      setNewClass({
        name: '',
        name_en: '',
        school_id: userSchoolId || '',
        grade_level: '',
        section: '',
        capacity: 30,
        homeroom_teacher_id: '',
      });
      setClasses(prev => [...prev, response.data]);
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('failedToAddClass')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReactivateClass = async (classId) => {
    try {
      await api.put(`/classes/${classId}`, { is_active: true });
      toast.success(t('classReactivated'));
      setClasses(prev => prev.map(c => c.id === classId ? { ...c, is_active: true } : c));
    } catch (error) {
      nassaqError(error.response?.data?.detail || (t('operationFailed')));
    }
  };

  const handleDeleteClass = async (classId) => {
    nassaqConfirm(
      t('areYouSureYouWantToDeleteThisClassAllRelatedDataWi'),
      async () => {
        try {
          const res = await api.delete(`/classes/${classId}`);
          const cleanup = res.data?.cleanup;
          let msg = t('classDeletedSuccessfully');
          if (cleanup) {
            const parts = Object.entries(cleanup).filter(([_, v]) => v > 0).map(([k, v]) => `${k}: ${v}`);
            if (parts.length > 0) msg += ` (${parts.join(', ')})`;
          }
          toast.success(msg);
          setClasses(prev => prev.filter(c => c.id !== classId));
        } catch (error) {
          nassaqError(error.response?.data?.detail || (t('failedToDeleteClass')));
        }
      },
      { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') }
    );
  };

  const filteredClasses = classes.filter(cls => {
    if (!showInactive && cls.is_active === false) return false;
    const matchesSearch = cls.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         cls.grade_level.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSchool = selectedSchool === 'all' || cls.school_id === selectedSchool;
    return matchesSearch && matchesSchool;
  }).sort((a, b) => a.name.localeCompare(b.name, 'ar'));

  const activeCount = filteredClasses.filter(c => c.is_active !== false).length;

  const getSchoolName = (schoolId) => {
    const school = schools.find(s => s.id === schoolId);
    return school?.name || '-';
  };

  const filteredTeachers = teachers.filter(t => t.school_id === newClass.school_id);

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="classes-page">
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
                  {t('classesManagement')}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? `${activeCount} فصل` : `${activeCount} classes`}
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
            <div className="flex flex-1 gap-4">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder={t('searchClasses')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-classes-input"
                />
              </div>
              
              <div className="flex items-center gap-2 px-3 rounded-xl border border-border bg-background">
                <Switch
                  id="show-inactive-classes"
                  checked={showInactive}
                  onCheckedChange={setShowInactive}
                  data-testid="toggle-show-inactive-classes"
                />
                <Label htmlFor="show-inactive-classes" className="text-sm font-tajawal cursor-pointer whitespace-nowrap">
                  {t('showInactiveClasses')}
                </Label>
              </div>

              {/* Only show school filter for platform admins */}
              {!isSchoolLevel && schools.length > 0 && (
                <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                  <SelectTrigger className="w-[200px] rounded-xl">
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
            </div>

            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-class-btn">
                  <Plus className="h-5 w-5 me-2" />
                  {t('addClass')}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {t('addNewClass')}
                  </DialogTitle>
                  <DialogDescription>
                    {t('enterTheNewClassDetails')}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label>{t('school2')}</Label>
                    <Select 
                      value={newClass.school_id} 
                      onValueChange={(value) => setNewClass({ ...newClass, school_id: value, homeroom_teacher_id: '' })}
                      disabled={isSchoolLevel}
                    >
                      <SelectTrigger
                        className="rounded-xl disabled:opacity-100 disabled:cursor-default"
                        data-testid="class-school-select"
                      >
                        <SelectValue placeholder={t('selectSchool')} />
                      </SelectTrigger>
                      <SelectContent>
                        {schools.map(school => (
                          <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('gradeLevel')}</Label>
                      <Select 
                        value={newClass.grade_level} 
                        onValueChange={(value) => setNewClass({ ...newClass, grade_level: value })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="class-grade-select">
                          <SelectValue placeholder={t('selectGrade')} />
                        </SelectTrigger>
                        <SelectContent>
                          {gradeLevels.map(level => (
                            <SelectItem key={level} value={level}>{level}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('section')}</Label>
                      <Select 
                        value={newClass.section} 
                        onValueChange={(value) => setNewClass({ ...newClass, section: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectSection')} />
                        </SelectTrigger>
                        <SelectContent>
                          {sections.map(sec => (
                            <SelectItem key={sec} value={sec}>{sec}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>{t('className')}</Label>
                    <Input
                      value={newClass.name}
                      onChange={(e) => setNewClass({ ...newClass, name: e.target.value })}
                      className="rounded-xl"
                      placeholder={t('autogenerated')}
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('capacity2')}</Label>
                      <Input
                        type="number"
                        value={newClass.capacity}
                        onChange={(e) => setNewClass({ ...newClass, capacity: parseInt(e.target.value) || 30 })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('homeroomTeacher')}</Label>
                      <Select 
                        value={newClass.homeroom_teacher_id} 
                        onValueChange={(value) => setNewClass({ ...newClass, homeroom_teacher_id: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectTeacher')} />
                        </SelectTrigger>
                        <SelectContent>
                          {filteredTeachers.map(teacher => (
                            <SelectItem key={teacher.id} value={teacher.id}>{teacher.full_name}</SelectItem>
                          ))}
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
                    onClick={handleCreateClass} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-class-btn"
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

          <Card className="card-nassaq">
            <CardContent className="p-0">
              {isLoading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : (
                <div className="rounded-xl overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('class')}</TableHead>
                        <TableHead>{t('gradeLabel')}</TableHead>
                        <TableHead>{t('school')}</TableHead>
                        <TableHead>{t('homeroomLabel')}</TableHead>
                        <TableHead>{t('students')}</TableHead>
                        <TableHead>{t('status2')}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredClasses.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                            <FolderOpen className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{t('noClassesFound')}</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredClasses.map((cls) => (
                          <TableRow
                            key={cls.id}
                            data-testid={`class-row-${cls.id}`}
                            className={cls.is_active === false ? 'opacity-60' : ''}
                          >
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-brand-navy/10 flex items-center justify-center">
                                  <FolderOpen className="h-5 w-5 text-brand-navy" />
                                </div>
                                <div>
                                  <div className="font-medium">{cls.name}</div>
                                  {cls.section && (
                                    <div className="text-sm text-muted-foreground">
                                      {isRTL ? `شعبة ${cls.section}` : `Section ${cls.section}`}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="rounded-lg">
                                {cls.grade_level}
                              </Badge>
                            </TableCell>
                            <TableCell>{getSchoolName(cls.school_id)}</TableCell>
                            <TableCell>
                              {cls.homeroom_teacher_name ? (
                                <div className="flex items-center gap-1">
                                  <UserCheck className="h-4 w-4 text-brand-purple" />
                                  {cls.homeroom_teacher_name}
                                </div>
                              ) : '-'}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <Users className="h-4 w-4 text-brand-turquoise" />
                                {cls.current_students} / {cls.capacity}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={cls.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                                {cls.is_active ? (t('active')) : (t('inactive'))}
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
                                  {cls.is_active === false && (
                                    <DropdownMenuItem
                                      onClick={() => handleReactivateClass(cls.id)}
                                      data-testid={`reactivate-class-${cls.id}`}
                                    >
                                      <RotateCcw className="h-4 w-4 me-2" />
                                      {t('reactivate')}
                                    </DropdownMenuItem>
                                  )}
                                  <DropdownMenuItem 
                                    className="text-red-600"
                                    onClick={() => handleDeleteClass(cls.id)}
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
