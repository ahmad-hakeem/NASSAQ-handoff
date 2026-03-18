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

export const StudentsPage = () => {
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [students, setStudents] = useState([]);
  const [schools, setSchools] = useState([]);
  const [classes, setClasses] = useState([]);
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
      const [studentsRes, classesRes] = await Promise.all([
        api.get('/students'),
        api.get('/classes'),
      ]);
      setStudents(studentsRes.data);
      setClasses(classesRes.data);
      
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
      nassaqError(isRTL ? 'يرجى ملء جميع الحقول المطلوبة' : 'Please fill all required fields');
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/students', { ...newStudent, school_id: schoolId });
      toast.success(isRTL ? 'تم إضافة الطالب بنجاح' : 'Student added successfully');
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
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل إضافة الطالب' : 'Failed to add student'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteStudent = async (studentId) => {
    nassaqConfirm(
      isRTL ? 'هل أنت متأكد من حذف هذا الطالب؟ سيتم حذف جميع البيانات المرتبطة نهائياً.' : 'Are you sure you want to delete this student? All related data will be permanently removed.',
      async () => {
        try {
          const res = await api.delete(`/students/${studentId}`);
          const cleanup = res.data?.cleanup;
          let msg = isRTL ? 'تم حذف الطالب بنجاح' : 'Student deleted successfully';
          if (cleanup) {
            const parts = Object.entries(cleanup).filter(([_, v]) => v > 0).map(([k, v]) => `${k}: ${v}`);
            if (parts.length > 0) msg += ` (${parts.join(', ')})`;
          }
          toast.success(msg);
          setStudents(prev => prev.filter(s => s.id !== studentId));
        } catch (error) {
          nassaqError(error.response?.data?.detail || (isRTL ? 'فشل حذف الطالب' : 'Failed to delete student'));
        }
      },
      { title: isRTL ? 'تأكيد الحذف النهائي' : 'Confirm Permanent Delete', confirmText: isRTL ? 'نعم، احذف نهائياً' : 'Yes, Delete Permanently', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
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
                  {isRTL ? 'إدارة الطلاب' : 'Students Management'}
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
                  placeholder={isRTL ? 'بحث عن طالب...' : 'Search students...'}
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
              
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-[180px] rounded-xl">
                  <SelectValue placeholder={isRTL ? 'الفصل' : 'Class'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{isRTL ? 'جميع الفصول' : 'All Classes'}</SelectItem>
                  {filteredClasses.map(cls => (
                    <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-student-btn">
                  <Plus className="h-5 w-5 me-2" />
                  {isRTL ? 'إضافة طالب' : 'Add Student'}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {isRTL ? 'إضافة طالب جديد' : 'Add New Student'}
                  </DialogTitle>
                  <DialogDescription>
                    {isRTL ? 'أدخل بيانات الطالب الجديد' : 'Enter the new student details'}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'اسم الطالب (عربي) *' : 'Student Name (Arabic) *'}</Label>
                      <Input
                        value={newStudent.full_name}
                        onChange={(e) => setNewStudent({ ...newStudent, full_name: e.target.value })}
                        className="rounded-xl"
                        data-testid="student-name-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'رقم الطالب *' : 'Student Number *'}</Label>
                      <Input
                        value={newStudent.student_number}
                        onChange={(e) => setNewStudent({ ...newStudent, student_number: e.target.value })}
                        placeholder="STU001"
                        className="rounded-xl"
                        data-testid="student-number-input"
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'المدرسة *' : 'School *'}</Label>
                      <Select 
                        value={newStudent.school_id} 
                        onValueChange={(value) => setNewStudent({ ...newStudent, school_id: value, class_id: '' })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="student-school-select">
                          <SelectValue placeholder={isRTL ? 'اختر المدرسة' : 'Select School'} />
                        </SelectTrigger>
                        <SelectContent>
                          {schools.map(school => (
                            <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'الفصل' : 'Class'}</Label>
                      <Select 
                        value={newStudent.class_id} 
                        onValueChange={(value) => setNewStudent({ ...newStudent, class_id: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={isRTL ? 'اختر الفصل' : 'Select Class'} />
                        </SelectTrigger>
                        <SelectContent>
                          {classes.filter(c => c.school_id === newStudent.school_id).map(cls => (
                            <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'تاريخ الميلاد' : 'Date of Birth'}</Label>
                      <Input
                        type="date"
                        value={newStudent.date_of_birth}
                        onChange={(e) => setNewStudent({ ...newStudent, date_of_birth: e.target.value })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'الجنس' : 'Gender'}</Label>
                      <Select 
                        value={newStudent.gender} 
                        onValueChange={(value) => setNewStudent({ ...newStudent, gender: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={isRTL ? 'اختر الجنس' : 'Select Gender'} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="male">{isRTL ? 'ذكر' : 'Male'}</SelectItem>
                          <SelectItem value="female">{isRTL ? 'أنثى' : 'Female'}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{isRTL ? 'اسم ولي الأمر' : 'Parent Name'}</Label>
                      <Input
                        value={newStudent.parent_name}
                        onChange={(e) => setNewStudent({ ...newStudent, parent_name: e.target.value })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{isRTL ? 'هاتف ولي الأمر' : 'Parent Phone'}</Label>
                      <Input
                        value={newStudent.parent_phone}
                        onChange={(e) => setNewStudent({ ...newStudent, parent_phone: e.target.value })}
                        placeholder="+966..."
                        className="rounded-xl"
                      />
                    </div>
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                    {isRTL ? 'إلغاء' : 'Cancel'}
                  </Button>
                  <Button 
                    onClick={handleCreateStudent} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-student-btn"
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
                        <TableHead>{isRTL ? 'الطالب' : 'Student'}</TableHead>
                        <TableHead>{isRTL ? 'رقم الطالب' : 'Student #'}</TableHead>
                        <TableHead>{isRTL ? 'الفصل' : 'Class'}</TableHead>
                        <TableHead>{isRTL ? 'المدرسة' : 'School'}</TableHead>
                        <TableHead>{isRTL ? 'ولي الأمر' : 'Parent'}</TableHead>
                        <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredStudents.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                            <GraduationCap className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{isRTL ? 'لا يوجد طلاب' : 'No students found'}</p>
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
                                    {student.gender === 'male' ? (isRTL ? 'ذكر' : 'Male') : (isRTL ? 'أنثى' : 'Female')}
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
                                {student.is_active ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'غير نشط' : 'Inactive')}
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
                                    onClick={() => handleDeleteStudent(student.id)}
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
