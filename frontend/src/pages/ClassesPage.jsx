import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
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

export const ClassesPage = () => {
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [classes, setClasses] = useState([]);
  const [schools, setSchools] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  
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

  const fetchData = async () => {
    try {
      // For school-level users, only fetch classes and teachers (tenant-scoped by backend)
      // For platform admins, also fetch schools for filtering
      const [classesRes, teachersRes] = await Promise.all([
        api.get('/classes'),
        api.get('/teachers'),
      ]);
      setClasses(classesRes.data);
      setTeachers(teachersRes.data);
      
      // Only fetch schools list for platform admins
      if (!isSchoolLevel) {
        try {
          const schoolsRes = await api.get('/schools');
          setSchools(schoolsRes.data);
        } catch {
          setSchools([]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(isRTL ? 'فشل تحميل البيانات' : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchData();
      // Set default school_id for new class form
      if (userSchoolId) {
        setNewClass(prev => ({ ...prev, school_id: userSchoolId }));
      }
    }
  }, [user]);

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
      nassaqError(isRTL ? 'يرجى ملء جميع الحقول المطلوبة' : 'Please fill all required fields');
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/classes', { ...newClass, school_id: schoolId });
      toast.success(isRTL ? 'تم إضافة الفصل بنجاح' : 'Class added successfully');
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
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل إضافة الفصل' : 'Failed to add class'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteClass = async (classId) => {
    nassaqConfirm(
      isRTL ? 'هل أنت متأكد من حذف هذا الفصل؟ سيتم حذف جميع البيانات المرتبطة نهائياً.' : 'Are you sure you want to delete this class? All related data will be permanently removed.',
      async () => {
        try {
          const res = await api.delete(`/classes/${classId}`);
          const cleanup = res.data?.cleanup;
          let msg = isRTL ? 'تم حذف الفصل بنجاح' : 'Class deleted successfully';
          if (cleanup) {
            const parts = Object.entries(cleanup).filter(([_, v]) => v > 0).map(([k, v]) => `${k}: ${v}`);
            if (parts.length > 0) msg += ` (${parts.join(', ')})`;
          }
          toast.success(msg);
          setClasses(prev => prev.filter(c => c.id !== classId));
        } catch (error) {
          nassaqError(error.response?.data?.detail || (isRTL ? 'فشل حذف الفصل' : 'Failed to delete class'));
        }
      },
      { title: isRTL ? 'تأكيد الحذف النهائي' : 'Confirm Permanent Delete', confirmText: isRTL ? 'نعم، احذف نهائياً' : 'Yes, Delete Permanently', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
    );
  };

  const filteredClasses = classes.filter(cls => {
    const matchesSearch = cls.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         cls.grade_level.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSchool = selectedSchool === 'all' || cls.school_id === selectedSchool;
    return matchesSearch && matchesSchool;
  }).sort((a, b) => a.name.localeCompare(b.name, 'ar'));

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
                  {isRTL ? 'إدارة الفصول' : 'Classes Management'}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? `${filteredClasses.length} فصل` : `${filteredClasses.length} classes`}
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
                  placeholder={isRTL ? 'بحث عن فصل...' : 'Search classes...'}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-classes-input"
                />
              </div>
              
              {/* Only show school filter for platform admins */}
              {!isSchoolLevel && schools.length > 0 && (
                <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                  <SelectTrigger className="w-[200px] rounded-xl">
                    <SelectValue placeholder={isRTL ? 'المدرسة' : 'School'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{isRTL ? 'جميع المدارس' : 'All Schools'}</SelectItem>
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
                  {isRTL ? 'إضافة فصل' : 'Add Class'}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {isRTL ? 'إضافة فصل جديد' : 'Add New Class'}
                  </DialogTitle>
                  <DialogDescription>
                    {isRTL ? 'أدخل بيانات الفصل الجديد' : 'Enter the new class details'}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label>{isRTL ? 'المدرسة *' : 'School *'}</Label>
                    <Select 
                      value={newClass.school_id} 
                      onValueChange={(value) => setNewClass({ ...newClass, school_id: value, homeroom_teacher_id: '' })}
                    >
                      <SelectTrigger className="rounded-xl" data-testid="class-school-select">
                        <SelectValue placeholder={isRTL ? 'اختر المدرسة' : 'Select School'} />
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
                      <Label>{isRTL ? 'المرحلة الدراسية *' : 'Grade Level *'}</Label>
                      <Select 
                        value={newClass.grade_level} 
                        onValueChange={(value) => setNewClass({ ...newClass, grade_level: value })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="class-grade-select">
                          <SelectValue placeholder={isRTL ? 'اختر المرحلة' : 'Select Grade'} />
                        </SelectTrigger>
                        <SelectContent>
                          {gradeLevels.map(level => (
                            <SelectItem key={level} value={level}>{level}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'الشعبة' : 'Section'}</Label>
                      <Select 
                        value={newClass.section} 
                        onValueChange={(value) => setNewClass({ ...newClass, section: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={isRTL ? 'اختر الشعبة' : 'Select Section'} />
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
                    <Label>{isRTL ? 'اسم الفصل' : 'Class Name'}</Label>
                    <Input
                      value={newClass.name}
                      onChange={(e) => setNewClass({ ...newClass, name: e.target.value })}
                      className="rounded-xl"
                      placeholder={isRTL ? 'سيتم توليده تلقائياً' : 'Auto-generated'}
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'السعة' : 'Capacity'}</Label>
                      <Input
                        type="number"
                        value={newClass.capacity}
                        onChange={(e) => setNewClass({ ...newClass, capacity: parseInt(e.target.value) || 30 })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'معلم الفصل' : 'Homeroom Teacher'}</Label>
                      <Select 
                        value={newClass.homeroom_teacher_id} 
                        onValueChange={(value) => setNewClass({ ...newClass, homeroom_teacher_id: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={isRTL ? 'اختر المعلم' : 'Select Teacher'} />
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
                    {isRTL ? 'إلغاء' : 'Cancel'}
                  </Button>
                  <Button 
                    onClick={handleCreateClass} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-class-btn"
                  >
                    {submitting ? (
                      <><Loader2 className="h-4 w-4 animate-spin me-2" />{isRTL ? 'جاري الإضافة...' : 'Adding...'}</>
                    ) : (
                      isRTL ? 'إضافة' : 'Add'
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
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
                        <TableHead>{isRTL ? 'الفصل' : 'Class'}</TableHead>
                        <TableHead>{isRTL ? 'المرحلة' : 'Grade'}</TableHead>
                        <TableHead>{isRTL ? 'المدرسة' : 'School'}</TableHead>
                        <TableHead>{isRTL ? 'معلم الفصل' : 'Homeroom'}</TableHead>
                        <TableHead>{isRTL ? 'الطلاب' : 'Students'}</TableHead>
                        <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredClasses.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                            <FolderOpen className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{isRTL ? 'لا يوجد فصول' : 'No classes found'}</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredClasses.map((cls) => (
                          <TableRow key={cls.id} data-testid={`class-row-${cls.id}`}>
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
                                {cls.is_active ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'غير نشط' : 'Inactive')}
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
                                    {isRTL ? 'تعديل' : 'Edit'}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem 
                                    className="text-red-600"
                                    onClick={() => handleDeleteClass(cls.id)}
                                  >
                                    <Trash2 className="h-4 w-4 me-2" />
                                    {isRTL ? 'حذف' : 'Delete'}
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
