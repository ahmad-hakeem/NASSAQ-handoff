import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Building2,
  Users,
  GraduationCap,
  UserCheck,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  Bell,
  CheckCircle,
  XCircle,
  RefreshCw,
  Eye,
  Edit,
  MapPin,
  Phone,
  Mail,
  Filter,
  Download,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  LogIn,
  ExternalLink,
  Sparkles,
  PauseCircle,
  PlayCircle,
  LayoutGrid,
  LayoutList,
  Brain,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
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
import { Label } from '../components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

export const PlatformSchoolsPage = () => {
  const navigate = useNavigate();
  const { user, api, enterSchoolContext } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedSchool, setSelectedSchool] = useState(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'table'
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const itemsPerPage = 10;

  const [newSchool, setNewSchool] = useState({
    name: '',
    name_en: '',
    code: '',
    email: '',
    phone: '',
    city: '',
    region: '',
    address: '',
    student_capacity: 500,
  });

  const fetchSchools = async () => {
    try {
      setLoading(true);
      const response = await api.get('/schools');
      setSchools(response.data);
    } catch (error) {
      console.error('Failed to fetch schools:', error);
      nassaqError(isRTL ? 'فشل تحميل المدارس' : 'Failed to load schools');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSchools();
  }, []);

  const handleCreateSchool = async () => {
    try {
      const response = await api.post('/schools', newSchool);
      toast.success(isRTL ? 'تم إنشاء المدرسة بنجاح' : 'School created successfully');
      setCreateDialogOpen(false);
      setNewSchool({
        name: '',
        name_en: '',
        code: '',
        email: '',
        phone: '',
        city: '',
        region: '',
        address: '',
        student_capacity: 500,
      });
      fetchSchools();
    } catch (error) {
      nassaqError(error.response?.data?.detail || (isRTL ? 'فشل إنشاء المدرسة' : 'Failed to create school'));
    }
  };

  const handleStatusChange = async (schoolId, status) => {
    try {
      await api.put(`/schools/${schoolId}/status?status=${status}`);
      toast.success(isRTL ? 'تم تحديث حالة المدرسة' : 'School status updated');
      fetchSchools();
    } catch (error) {
      nassaqError(isRTL ? 'فشل تحديث الحالة' : 'Failed to update status');
    }
  };

  const handleViewSchoolContext = (school) => {
    // Navigate to school context - Platform Admin can view but not edit
    toast.info(isRTL ? 'جاري الدخول لسياق المدرسة...' : 'Entering school context...');
    setSelectedSchool(school);
    setViewDialogOpen(true);
  };
  
  // Enter School Dashboard - Full context switch
  const handleEnterSchoolDashboard = (school) => {
    if (!school || !school.id) {
      nassaqError(isRTL ? 'خطأ: بيانات المدرسة غير صالحة' : 'Error: Invalid school data');
      return;
    }
    
    // Enter school context
    enterSchoolContext(school);
    
    // Show success message
    toast.success(
      isRTL 
        ? `تم الدخول إلى ${school.name} كمدير مدرسة` 
        : `Entered ${school.name_en || school.name} as School Manager`
    );
    
    // Navigate to school principal dashboard
    navigate('/principal');
  };

  const filteredSchools = schools.filter(school => {
    const matchesSearch = 
      school.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      school.name_en?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      school.code?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      school.city?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || school.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  const paginatedSchools = filteredSchools.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPages = Math.ceil(filteredSchools.length / itemsPerPage);

  // Toggle AI feature for a school
  const handleToggleAI = async (schoolId, currentAIStatus) => {
    try {
      await api.patch(`/schools/${schoolId}`, {
        ai_enabled: !currentAIStatus
      });
      toast.success(
        isRTL 
          ? (!currentAIStatus ? 'تم تفعيل الذكاء الاصطناعي' : 'تم إيقاف الذكاء الاصطناعي')
          : (!currentAIStatus ? 'AI enabled successfully' : 'AI disabled successfully')
      );
      fetchSchools();
    } catch (error) {
      console.error('Failed to toggle AI:', error);
      nassaqError(isRTL ? 'فشل تعديل حالة الذكاء الاصطناعي' : 'Failed to toggle AI status');
    }
  };

  // Toggle suspend status for a school
  const handleToggleSuspend = async (schoolId, currentStatus) => {
    const newStatus = currentStatus === 'suspended' ? 'active' : 'suspended';
    try {
      await api.patch(`/schools/${schoolId}`, { status: newStatus });
      toast.success(
        isRTL 
          ? (newStatus === 'suspended' ? 'تم تعليق المدرسة' : 'تم تفعيل المدرسة')
          : (newStatus === 'suspended' ? 'School suspended' : 'School activated')
      );
      fetchSchools();
    } catch (error) {
      console.error('Failed to toggle status:', error);
      nassaqError(isRTL ? 'فشل تعديل حالة المدرسة' : 'Failed to toggle school status');
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">{isRTL ? 'نشطة' : 'Active'}</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">{isRTL ? 'معلقة' : 'Pending'}</Badge>;
      case 'suspended':
        return <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{isRTL ? 'موقوفة' : 'Suspended'}</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const stats = {
    total: schools.length,
    active: schools.filter(s => s.status === 'active').length,
    pending: schools.filter(s => s.status === 'pending').length,
    suspended: schools.filter(s => s.status === 'suspended').length,
    aiEnabled: schools.filter(s => s.ai_enabled).length,
    totalStudents: schools.reduce((sum, s) => sum + (s.current_students || 0), 0),
    totalTeachers: schools.reduce((sum, s) => sum + (s.current_teachers || 0), 0),
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="platform-schools-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'إدارة المدارس' : 'Schools Management'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? 'إدارة جميع المدارس في المنصة' : 'Manage all schools on the platform'}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={fetchSchools} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-brand-navy" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.total}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي المدارس' : 'Total Schools'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.active}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'نشطة' : 'Active'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-yellow-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.pending}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'معلقة' : 'Pending'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <XCircle className="h-5 w-5 text-red-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.suspended}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'موقوفة' : 'Suspended'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center">
                    <GraduationCap className="h-5 w-5 text-brand-turquoise" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.totalStudents.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي الطلاب' : 'Total Students'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-purple/10 flex items-center justify-center">
                    <UserCheck className="h-5 w-5 text-brand-purple" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.totalTeachers.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي المعلمين' : 'Total Teachers'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Schools Table */}
          <Card className="card-nassaq">
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <CardTitle className="font-cairo">{isRTL ? 'قائمة المدارس' : 'Schools List'}</CardTitle>
                  <CardDescription>{isRTL ? `${filteredSchools.length} مدرسة` : `${filteredSchools.length} schools`}</CardDescription>
                </div>
                
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={isRTL ? 'بحث...' : 'Search...'}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-[200px] rounded-xl"
                      data-testid="search-schools-input"
                    />
                  </div>
                  
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[140px] rounded-xl">
                      <Filter className="h-4 w-4 me-2" />
                      <SelectValue placeholder={isRTL ? 'الحالة' : 'Status'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{isRTL ? 'الكل' : 'All'}</SelectItem>
                      <SelectItem value="active">{isRTL ? 'نشطة' : 'Active'}</SelectItem>
                      <SelectItem value="pending">{isRTL ? 'معلقة' : 'Pending'}</SelectItem>
                      <SelectItem value="suspended">{isRTL ? 'موقوفة' : 'Suspended'}</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  {/* View Mode Toggle */}
                  <div className="flex items-center border rounded-xl overflow-hidden">
                    <Button
                      variant={viewMode === 'grid' ? 'default' : 'ghost'}
                      size="sm"
                      onClick={() => setViewMode('grid')}
                      className={`rounded-none ${viewMode === 'grid' ? 'bg-brand-navy' : ''}`}
                    >
                      <LayoutGrid className="h-4 w-4" />
                    </Button>
                    <Button
                      variant={viewMode === 'table' ? 'default' : 'ghost'}
                      size="sm"
                      onClick={() => setViewMode('table')}
                      className={`rounded-none ${viewMode === 'table' ? 'bg-brand-navy' : ''}`}
                    >
                      <LayoutList className="h-4 w-4" />
                    </Button>
                  </div>
                  
                  <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                    <DialogTrigger asChild>
                      <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-school-btn">
                        <Plus className="h-5 w-5 me-2" />
                        {isRTL ? 'إضافة مدرسة' : 'Add School'}
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[600px]">
                      <DialogHeader>
                        <DialogTitle className="font-cairo">{isRTL ? 'إضافة مدرسة جديدة' : 'Add New School'}</DialogTitle>
                        <DialogDescription>{isRTL ? 'أدخل بيانات المدرسة الجديدة' : 'Enter the new school details'}</DialogDescription>
                      </DialogHeader>
                      
                      <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>{isRTL ? 'اسم المدرسة (عربي)' : 'School Name (Arabic)'}</Label>
                            <Input
                              value={newSchool.name}
                              onChange={(e) => setNewSchool({ ...newSchool, name: e.target.value })}
                              placeholder={isRTL ? 'مدرسة...' : 'School...'}
                              className="rounded-xl"
                              data-testid="school-name-input"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{isRTL ? 'اسم المدرسة (إنجليزي)' : 'School Name (English)'}</Label>
                            <Input
                              value={newSchool.name_en}
                              onChange={(e) => setNewSchool({ ...newSchool, name_en: e.target.value })}
                              placeholder="School..."
                              className="rounded-xl"
                            />
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>{isRTL ? 'رمز المدرسة' : 'School Code'}</Label>
                            <Input
                              value={newSchool.code}
                              onChange={(e) => setNewSchool({ ...newSchool, code: e.target.value })}
                              placeholder="SCH001"
                              className="rounded-xl"
                              data-testid="school-code-input"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label>
                            <Input
                              type="email"
                              value={newSchool.email}
                              onChange={(e) => setNewSchool({ ...newSchool, email: e.target.value })}
                              placeholder="school@example.com"
                              className="rounded-xl"
                              data-testid="school-email-input"
                            />
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>{isRTL ? 'الهاتف' : 'Phone'}</Label>
                            <Input
                              value={newSchool.phone}
                              onChange={(e) => setNewSchool({ ...newSchool, phone: e.target.value })}
                              placeholder="+966..."
                              className="rounded-xl"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{isRTL ? 'المدينة' : 'City'}</Label>
                            <Input
                              value={newSchool.city}
                              onChange={(e) => setNewSchool({ ...newSchool, city: e.target.value })}
                              placeholder={isRTL ? 'الرياض' : 'Riyadh'}
                              className="rounded-xl"
                            />
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>{isRTL ? 'المنطقة' : 'Region'}</Label>
                            <Input
                              value={newSchool.region}
                              onChange={(e) => setNewSchool({ ...newSchool, region: e.target.value })}
                              placeholder={isRTL ? 'منطقة الرياض' : 'Riyadh Region'}
                              className="rounded-xl"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{isRTL ? 'سعة الطلاب' : 'Student Capacity'}</Label>
                            <Input
                              type="number"
                              value={newSchool.student_capacity}
                              onChange={(e) => setNewSchool({ ...newSchool, student_capacity: parseInt(e.target.value) })}
                              className="rounded-xl"
                            />
                          </div>
                        </div>
                        
                        <div className="space-y-2">
                          <Label>{isRTL ? 'العنوان' : 'Address'}</Label>
                          <Input
                            value={newSchool.address}
                            onChange={(e) => setNewSchool({ ...newSchool, address: e.target.value })}
                            placeholder={isRTL ? 'العنوان الكامل...' : 'Full address...'}
                            className="rounded-xl"
                          />
                        </div>
                      </div>
                      
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                          {isRTL ? 'إلغاء' : 'Cancel'}
                        </Button>
                        <Button onClick={handleCreateSchool} className="bg-brand-navy rounded-xl" data-testid="create-school-btn">
                          {isRTL ? 'إنشاء المدرسة' : 'Create School'}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            </CardHeader>
            
            <CardContent>
              {/* Grid View - Cards */}
              {viewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {loading ? (
                    <div className="col-span-full text-center py-8 text-muted-foreground">
                      {isRTL ? 'جاري التحميل...' : 'Loading...'}
                    </div>
                  ) : paginatedSchools.length === 0 ? (
                    <div className="col-span-full text-center py-8 text-muted-foreground">
                      {isRTL ? 'لا توجد مدارس' : 'No schools found'}
                    </div>
                  ) : (
                    paginatedSchools.map((school) => (
                      <Card 
                        key={school.id} 
                        className="card-nassaq relative overflow-hidden group"
                        data-testid={`school-card-${school.id}`}
                      >
                        {/* Status indicator */}
                        <div className={`absolute top-0 left-0 right-0 h-1 ${
                          school.status === 'active' ? 'bg-green-500' :
                          school.status === 'suspended' ? 'bg-red-500' : 'bg-yellow-500'
                        }`} />
                        
                        <CardContent className="p-5">
                          {/* Header - School Info */}
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <div className="w-12 h-12 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                                <Building2 className="h-6 w-6 text-brand-navy" />
                              </div>
                              <div>
                                <h3 className="font-bold text-base line-clamp-1">{school.name}</h3>
                                <p className="text-xs text-muted-foreground font-mono">{school.code}</p>
                              </div>
                            </div>
                            {getStatusBadge(school.status)}
                          </div>
                          
                          {/* Stats */}
                          <div className="grid grid-cols-2 gap-3 mb-4">
                            <div className="flex items-center gap-2 text-sm">
                              <GraduationCap className="h-4 w-4 text-brand-turquoise" />
                              <span>{school.current_students || 0} {isRTL ? 'طالب' : 'Students'}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              <UserCheck className="h-4 w-4 text-brand-purple" />
                              <span>{school.current_teachers || 0} {isRTL ? 'معلم' : 'Teachers'}</span>
                            </div>
                            <div className="flex items-center gap-2 text-sm col-span-2">
                              <MapPin className="h-4 w-4 text-muted-foreground" />
                              <span className="text-muted-foreground truncate">{school.city || '-'}, {school.region || '-'}</span>
                            </div>
                          </div>
                          
                          {/* Action Toggles - Suspend & AI - Large and Clear */}
                          <div className="flex items-center gap-2 mb-4 p-3 bg-muted/30 rounded-xl border">
                            {/* Suspend Toggle */}
                            <Button
                              variant={school.status === 'suspended' ? 'destructive' : 'outline'}
                              size="sm"
                              onClick={(e) => { e.stopPropagation(); handleToggleSuspend(school.id, school.status); }}
                              className={`flex-1 rounded-lg h-10 font-bold ${
                                school.status === 'suspended' 
                                  ? 'bg-red-500 hover:bg-red-600 text-white' 
                                  : 'border-red-300 text-red-600 hover:bg-red-50'
                              }`}
                              data-testid={`toggle-suspend-${school.id}`}
                            >
                              {school.status === 'suspended' ? (
                                <>
                                  <PlayCircle className="h-4 w-4 me-2" />
                                  {isRTL ? 'إلغاء التعليق' : 'Activate'}
                                </>
                              ) : (
                                <>
                                  <PauseCircle className="h-4 w-4 me-2" />
                                  {isRTL ? 'تعليق' : 'Suspend'}
                                </>
                              )}
                            </Button>
                            
                            {/* AI Toggle */}
                            <Button
                              variant={school.ai_enabled ? 'default' : 'outline'}
                              size="sm"
                              onClick={(e) => { e.stopPropagation(); handleToggleAI(school.id, school.ai_enabled); }}
                              className={`flex-1 rounded-lg h-10 font-bold ${
                                school.ai_enabled 
                                  ? 'bg-gradient-to-r from-purple-500 to-cyan-500 hover:from-purple-600 hover:to-cyan-600 text-white' 
                                  : 'border-purple-300 text-purple-600 hover:bg-purple-50'
                              }`}
                              data-testid={`toggle-ai-${school.id}`}
                            >
                              <Brain className="h-4 w-4 me-2" />
                              {school.ai_enabled ? (
                                <>{isRTL ? 'AI مفعّل' : 'AI On'}</>
                              ) : (
                                <>{isRTL ? 'تفعيل AI' : 'Enable AI'}</>
                              )}
                            </Button>
                          </div>
                          
                          {/* Primary Action - Open Dashboard */}
                          <Button 
                            className="w-full bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl h-11 font-bold"
                            onClick={() => handleEnterSchoolDashboard(school)}
                            data-testid={`open-dashboard-${school.id}`}
                          >
                            <LogIn className="h-5 w-5 me-2" />
                            {isRTL ? 'فتح لوحة التحكم' : 'Open Dashboard'}
                          </Button>
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              ) : (
                /* Table View */
                <div className="rounded-xl border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{isRTL ? 'المدرسة' : 'School'}</TableHead>
                      <TableHead>{isRTL ? 'الرمز' : 'Code'}</TableHead>
                      <TableHead>{isRTL ? 'المدينة / المنطقة' : 'City / Region'}</TableHead>
                      <TableHead>{isRTL ? 'الحالة' : 'Status'}</TableHead>
                      <TableHead>{isRTL ? 'الطلاب' : 'Students'}</TableHead>
                      <TableHead>{isRTL ? 'المعلمين' : 'Teachers'}</TableHead>
                      <TableHead>{isRTL ? 'الإجراءات' : 'Actions'}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                          {isRTL ? 'جاري التحميل...' : 'Loading...'}
                        </TableCell>
                      </TableRow>
                    ) : paginatedSchools.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                          {isRTL ? 'لا توجد مدارس' : 'No schools found'}
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedSchools.map((school) => (
                        <TableRow key={school.id} data-testid={`school-row-${school.id}`}>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                                <Building2 className="h-5 w-5 text-brand-navy" />
                              </div>
                              <div>
                                <div className="font-medium">{school.name}</div>
                                <div className="text-sm text-muted-foreground">{school.email}</div>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell className="font-mono">{school.code}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <MapPin className="h-4 w-4 text-muted-foreground" />
                              <span>{school.city || '-'}</span>
                              {school.region && <span className="text-muted-foreground">/ {school.region}</span>}
                            </div>
                          </TableCell>
                          <TableCell>{getStatusBadge(school.status)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <GraduationCap className="h-4 w-4 text-brand-turquoise" />
                              <span>{school.current_students || 0}</span>
                              <span className="text-muted-foreground">/ {school.student_capacity}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <UserCheck className="h-4 w-4 text-brand-purple" />
                              <span>{school.current_teachers || 0}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {/* Enter Dashboard Button - Primary Action */}
                              <Button 
                                size="sm" 
                                className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-lg"
                                onClick={() => handleEnterSchoolDashboard(school)}
                                data-testid={`enter-dashboard-${school.id}`}
                              >
                                <LogIn className="h-4 w-4 me-1" />
                                {isRTL ? 'الدخول' : 'Enter'}
                              </Button>
                              
                              {/* More Actions Dropdown */}
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => handleEnterSchoolDashboard(school)}>
                                    <ExternalLink className="h-4 w-4 me-2" />
                                    {isRTL ? 'الدخول للوحة التحكم' : 'Enter Dashboard'}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleViewSchoolContext(school)}>
                                    <Eye className="h-4 w-4 me-2" />
                                    {isRTL ? 'عرض البيانات' : 'View Details'}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => { setSelectedSchool(school); setEditDialogOpen(true); }}>
                                    <Edit className="h-4 w-4 me-2" />
                                    {isRTL ? 'تعديل' : 'Edit'}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem onClick={() => handleStatusChange(school.id, 'active')}>
                                    <CheckCircle className="h-4 w-4 me-2 text-green-600" />
                                    {isRTL ? 'تفعيل' : 'Activate'}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleStatusChange(school.id, 'suspended')}>
                                    <XCircle className="h-4 w-4 me-2 text-red-600" />
                                    {isRTL ? 'إيقاف' : 'Suspend'}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
              )}
              
              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    {isRTL 
                      ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, filteredSchools.length)} من ${filteredSchools.length}`
                      : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, filteredSchools.length)} of ${filteredSchools.length}`
                    }
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                      className="rounded-xl"
                    >
                      {isRTL ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
                    </Button>
                    <span className="text-sm">{currentPage} / {totalPages}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                      className="rounded-xl"
                    >
                      {isRTL ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* View School Context Dialog */}
        <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
          <DialogContent className="sm:max-w-[700px]">
            <DialogHeader>
              <DialogTitle className="font-cairo">{selectedSchool?.name}</DialogTitle>
              <DialogDescription>{isRTL ? 'عرض بيانات المدرسة (للاطلاع فقط)' : 'View school data (read-only)'}</DialogDescription>
            </DialogHeader>
            
            {selectedSchool && (
              <div className="space-y-6 py-4">
                <div className="grid grid-cols-2 gap-4">
                  <Card className="card-nassaq">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <GraduationCap className="h-8 w-8 text-brand-turquoise" />
                        <div>
                          <p className="text-2xl font-bold">{selectedSchool.current_students || 0}</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'طالب' : 'Students'}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="card-nassaq">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <UserCheck className="h-8 w-8 text-brand-purple" />
                        <div>
                          <p className="text-2xl font-bold">{selectedSchool.current_teachers || 0}</p>
                          <p className="text-sm text-muted-foreground">{isRTL ? 'معلم' : 'Teachers'}</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{selectedSchool.email}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{selectedSchool.phone || '-'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    <span>{selectedSchool.city || '-'}, {selectedSchool.region || '-'}</span>
                  </div>
                </div>
                
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl p-4">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    {isRTL 
                      ? 'ملاحظة: كمدير للمنصة، يمكنك الاطلاع على بيانات المدرسة فقط. التعديل متاح لمدير المدرسة.'
                      : 'Note: As Platform Admin, you can only view school data. Editing is available for School Principal.'}
                  </p>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setViewDialogOpen(false)} className="rounded-xl">
                {isRTL ? 'إغلاق' : 'Close'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
