import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { usePlatformAdminSchoolPreview } from '../hooks/usePlatformAdminSchoolPreview';
import { isIndependentTeacherWorkspaceRow } from '../utils/platformAdminPreview';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, api } = useAuth();
  const { openPrincipalDashboard, canOpenPrincipalDashboard } = usePlatformAdminSchoolPreview();
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
      nassaqError(t('failedToLoadSchools'));
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
      toast.success(t('schoolCreatedSuccessfully2'));
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
      nassaqError(error.response?.data?.detail || (t('failedToCreateSchool')));
    }
  };

  const handleStatusChange = async (schoolId, status) => {
    try {
      await api.put(`/schools/${schoolId}/status?status=${status}`);
      toast.success(t('schoolStatusUpdated'));
      fetchSchools();
    } catch (error) {
      nassaqError(t('failedToUpdateStatus'));
    }
  };

  const handleViewSchoolContext = (school) => {
    // Navigate to school context - Platform Admin can view but not edit
    toast.info(t('enteringSchoolContext'));
    setSelectedSchool(school);
    setViewDialogOpen(true);
  };
  
  const handleEnterSchoolDashboard = (school) => openPrincipalDashboard(school);

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
      nassaqError(t('failedToToggleAiStatus'));
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
      nassaqError(t('failedToToggleSchoolStatus'));
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">{t('active2')}</Badge>;
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">{t('pending2')}</Badge>;
      case 'suspended':
        return <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">{t('suspended')}</Badge>;
      case 'archived':
        return <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">{t('schoolStatusArchived')}</Badge>;
      case 'pending_hard_delete':
        return <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">{t('schoolStatusPendingDelete')}</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const activeCount = schools.filter(s => s.status === 'active').length;
  const suspendedCount = schools.filter(s => s.status === 'suspended').length;
  const stats = {
    total: schools.length,
    active: activeCount,
    // Everything that is neither active nor suspended (pending, setup, or any
    // other onboarding state) is counted as pending so the status cards always
    // reconcile to the total.
    pending: schools.length - activeCount - suspendedCount,
    suspended: suspendedCount,
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
                {t('schoolsManagement')}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('manageAllSchoolsOnThePlatform')}
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
                    <p className="text-xs text-muted-foreground">{t('totalSchools')}</p>
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
                    <p className="text-xs text-muted-foreground">{t('active2')}</p>
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
                    <p className="text-xs text-muted-foreground">{t('pending2')}</p>
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
                    <p className="text-xs text-muted-foreground">{t('suspended')}</p>
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
                    <p className="text-xs text-muted-foreground">{t('totalStudents')}</p>
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
                    <p className="text-xs text-muted-foreground">{t('totalTeachers')}</p>
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
                  <CardTitle className="font-cairo">{t('schoolsList')}</CardTitle>
                  <CardDescription>{isRTL ? `${filteredSchools.length} مدرسة` : `${filteredSchools.length} schools`}</CardDescription>
                </div>
                
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('search')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-[200px] rounded-xl"
                      data-testid="search-schools-input"
                    />
                  </div>
                  
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[140px] rounded-xl">
                      <Filter className="h-4 w-4 me-2" />
                      <SelectValue placeholder={t('status2')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('all')}</SelectItem>
                      <SelectItem value="active">{t('active2')}</SelectItem>
                      <SelectItem value="pending">{t('pending2')}</SelectItem>
                      <SelectItem value="suspended">{t('suspended')}</SelectItem>
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
                        {t('addSchool')}
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[600px]">
                      <DialogHeader>
                        <DialogTitle className="font-cairo">{t('addNewSchool')}</DialogTitle>
                        <DialogDescription>{t('enterTheNewSchoolDetails')}</DialogDescription>
                      </DialogHeader>
                      
                      <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>{t('schoolNameArabic')}</Label>
                            <Input
                              value={newSchool.name}
                              onChange={(e) => setNewSchool({ ...newSchool, name: e.target.value })}
                              placeholder={t('school3')}
                              className="rounded-xl"
                              data-testid="school-name-input"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{t('schoolNameEnglish2')}</Label>
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
                            <Label>{t('schoolCode')}</Label>
                            <Input
                              value={newSchool.code}
                              onChange={(e) => setNewSchool({ ...newSchool, code: e.target.value })}
                              placeholder="SCH001"
                              className="rounded-xl"
                              data-testid="school-code-input"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{t('email2')}</Label>
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
                            <Label>{t('phone2')}</Label>
                            <Input
                              value={newSchool.phone}
                              onChange={(e) => setNewSchool({ ...newSchool, phone: e.target.value })}
                              placeholder="+966..."
                              className="rounded-xl"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{t('city')}</Label>
                            <Input
                              value={newSchool.city}
                              onChange={(e) => setNewSchool({ ...newSchool, city: e.target.value })}
                              placeholder={t('riyadh')}
                              className="rounded-xl"
                            />
                          </div>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label>{t('region2')}</Label>
                            <Input
                              value={newSchool.region}
                              onChange={(e) => setNewSchool({ ...newSchool, region: e.target.value })}
                              placeholder={t('riyadhRegion')}
                              className="rounded-xl"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label>{t('studentCapacity')}</Label>
                            <Input
                              type="number"
                              value={newSchool.student_capacity}
                              onChange={(e) => setNewSchool({ ...newSchool, student_capacity: parseInt(e.target.value) })}
                              className="rounded-xl"
                            />
                          </div>
                        </div>
                        
                        <div className="space-y-2">
                          <Label>{t('address')}</Label>
                          <Input
                            value={newSchool.address}
                            onChange={(e) => setNewSchool({ ...newSchool, address: e.target.value })}
                            placeholder={t('fullAddress')}
                            className="rounded-xl"
                          />
                        </div>
                      </div>
                      
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                          {t('cancel')}
                        </Button>
                        <Button onClick={handleCreateSchool} className="bg-brand-navy rounded-xl" data-testid="create-school-btn">
                          {t('createSchool2')}
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
                      {t('loading')}
                    </div>
                  ) : paginatedSchools.length === 0 ? (
                    <div className="col-span-full text-center py-8 text-muted-foreground">
                      {t('noSchoolsFound')}
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
                                  {t('activate2')}
                                </>
                              ) : (
                                <>
                                  <PauseCircle className="h-4 w-4 me-2" />
                                  {t('suspend')}
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
                                <>{t('aiOn')}</>
                              ) : (
                                <>{t('enableAi')}</>
                              )}
                            </Button>
                          </div>
                          
                          {isIndependentTeacherWorkspaceRow(school) && (
                            <p className="text-xs text-muted-foreground mb-2 text-center">
                              {t('schoolRowIndependentTeacherWorkspace')}
                            </p>
                          )}
                          {/* Primary Action - Open Dashboard */}
                          <Button 
                            className="w-full bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl h-11 font-bold disabled:opacity-50"
                            onClick={() => handleEnterSchoolDashboard(school)}
                            disabled={!canOpenPrincipalDashboard(school)}
                            title={!canOpenPrincipalDashboard(school) ? t('openDashboardBlockedHint') : undefined}
                            data-testid={`open-dashboard-${school.id}`}
                          >
                            <LogIn className="h-5 w-5 me-2" />
                            {t('openDashboard')}
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
                      <TableHead>{t('school')}</TableHead>
                      <TableHead>{t('code')}</TableHead>
                      <TableHead>{t('cityRegion')}</TableHead>
                      <TableHead>{t('status2')}</TableHead>
                      <TableHead>{t('students')}</TableHead>
                      <TableHead>{t('teachers2')}</TableHead>
                      <TableHead>{t('actions2')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                          {t('loading')}
                        </TableCell>
                      </TableRow>
                    ) : paginatedSchools.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                          {t('noSchoolsFound')}
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
                                className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-lg disabled:opacity-50"
                                onClick={() => handleEnterSchoolDashboard(school)}
                                disabled={!canOpenPrincipalDashboard(school)}
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
                                  <DropdownMenuItem
                                    onClick={() => handleEnterSchoolDashboard(school)}
                                    disabled={!canOpenPrincipalDashboard(school)}
                                  >
                                    <ExternalLink className="h-4 w-4 me-2" />
                                    {t('enterDashboard')}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleViewSchoolContext(school)}>
                                    <Eye className="h-4 w-4 me-2" />
                                    {t('viewDetails2')}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => { setSelectedSchool(school); setEditDialogOpen(true); }}>
                                    <Edit className="h-4 w-4 me-2" />
                                    {t('edit')}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem onClick={() => handleStatusChange(school.id, 'active')}>
                                    <CheckCircle className="h-4 w-4 me-2 text-green-600" />
                                    {t('activate')}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleStatusChange(school.id, 'suspended')}>
                                    <XCircle className="h-4 w-4 me-2 text-red-600" />
                                    {t('suspend2')}
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
              <DialogDescription>{t('viewSchoolDataReadonly')}</DialogDescription>
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
                    {t('noteAsPlatformAdminYouCanOnlyViewSchoolDataEditing')}
                  </p>
                </div>
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setViewDialogOpen(false)} className="rounded-xl">
                {t('close')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
