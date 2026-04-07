import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
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
  Users,
  UserCheck,
  UserX,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  RefreshCw,
  Eye,
  Edit,
  Mail,
  Phone,
  Building2,
  Filter,
  ChevronLeft,
  ChevronRight,
  Shield,
  Key,
  UserCog,
  GraduationCap,
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
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';

const roleLabels = {
  platform_admin: { ar: 'مدير المنصة', en: 'Platform Admin', color: 'bg-brand-navy' },
  ministry_rep: { ar: 'ممثل الوزارة', en: 'Ministry Rep', color: 'bg-purple-600' },
  school_principal: { ar: 'مدير المدرسة', en: 'School Principal', color: 'bg-brand-turquoise' },
  school_sub_admin: { ar: 'مسؤول إداري', en: 'School Admin', color: 'bg-blue-500' },
  teacher: { ar: 'معلم', en: 'Teacher', color: 'bg-green-500' },
  student: { ar: 'طالب', en: 'Student', color: 'bg-yellow-500' },
  parent: { ar: 'ولي أمر', en: 'Parent', color: 'bg-orange-500' },
  driver: { ar: 'سائق', en: 'Driver', color: 'bg-gray-500' },
  gatekeeper: { ar: 'مسؤول البوابة', en: 'Gatekeeper', color: 'bg-gray-600' },
};

export const PlatformUsersPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [users, setUsers] = useState([]);
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const itemsPerPage = 15;

  const fetchData = async () => {
    try {
      setLoading(true);
      const [usersRes, schoolsRes] = await Promise.all([
        api.get('/users'),
        api.get('/schools'),
      ]);
      setUsers(usersRes.data);
      setSchools(schoolsRes.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleStatusChange = async (userId, isActive) => {
    try {
      await api.put(`/users/${userId}/status?is_active=${isActive}`);
      toast.success(t('userStatusUpdated'));
      fetchData();
    } catch (error) {
      nassaqError(t('failedToUpdateStatus'));
    }
  };

  const getSchoolName = (tenantId) => {
    const school = schools.find(s => s.id === tenantId);
    return school?.name || '-';
  };

  const filteredUsers = users.filter(u => {
    const matchesSearch = 
      u.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.phone?.includes(searchQuery);
    
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || 
      (statusFilter === 'active' && u.is_active) ||
      (statusFilter === 'inactive' && !u.is_active);
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  const paginatedUsers = filteredUsers.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage);

  const stats = {
    total: users.length,
    active: users.filter(u => u.is_active).length,
    inactive: users.filter(u => !u.is_active).length,
    admins: users.filter(u => u.role === 'platform_admin').length,
    principals: users.filter(u => u.role === 'school_principal').length,
    teachers: users.filter(u => u.role === 'teacher').length,
    students: users.filter(u => u.role === 'student').length,
  };

  const getRoleBadge = (role) => {
    const roleInfo = roleLabels[role] || { ar: role, en: role, color: 'bg-gray-500' };
    return (
      <Badge className={`${roleInfo.color} text-white`}>
        {isRTL ? roleInfo.ar : roleInfo.en}
      </Badge>
    );
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="platform-users-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'إدارة المستخدمين' : 'Users Management'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('manageAllPlatformUsers')}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={fetchData} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                    <Users className="h-5 w-5 text-brand-navy" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.total}</p>
                    <p className="text-xs text-muted-foreground">{t('total2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <UserCheck className="h-5 w-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.active}</p>
                    <p className="text-xs text-muted-foreground">{t('active')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                    <UserX className="h-5 w-5 text-red-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.inactive}</p>
                    <p className="text-xs text-muted-foreground">{t('inactive2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-navy/10 flex items-center justify-center">
                    <Shield className="h-5 w-5 text-brand-navy" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.admins}</p>
                    <p className="text-xs text-muted-foreground">{t('admins2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-brand-turquoise" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.principals}</p>
                    <p className="text-xs text-muted-foreground">{t('principals')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center">
                    <UserCog className="h-5 w-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.teachers}</p>
                    <p className="text-xs text-muted-foreground">{t('teachers3')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-yellow-500/10 flex items-center justify-center">
                    <GraduationCap className="h-5 w-5 text-yellow-500" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats.students}</p>
                    <p className="text-xs text-muted-foreground">{t('students2')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Users Table */}
          <Card className="card-nassaq">
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <CardTitle className="font-cairo">{t('usersList')}</CardTitle>
                  <CardDescription>{isRTL ? `${filteredUsers.length} مستخدم` : `${filteredUsers.length} users`}</CardDescription>
                </div>
                
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('search')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-[200px] rounded-xl"
                      data-testid="search-users-input"
                    />
                  </div>
                  
                  <Select value={roleFilter} onValueChange={setRoleFilter}>
                    <SelectTrigger className="w-[150px] rounded-xl">
                      <SelectValue placeholder={t('role')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('allRoles')}</SelectItem>
                      <SelectItem value="platform_admin">{t('platformAdmin')}</SelectItem>
                      <SelectItem value="school_principal">{isRTL ? 'مدير المدرسة' : 'School Principal'}</SelectItem>
                      <SelectItem value="teacher">{t('teacher')}</SelectItem>
                      <SelectItem value="student">{t('student')}</SelectItem>
                      <SelectItem value="parent">{isRTL ? 'ولي أمر' : 'Parent'}</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[130px] rounded-xl">
                      <SelectValue placeholder={t('status2')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('all')}</SelectItem>
                      <SelectItem value="active">{t('active')}</SelectItem>
                      <SelectItem value="inactive">{t('inactive2')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            
            <CardContent>
              <div className="rounded-xl border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('user')}</TableHead>
                      <TableHead>{t('email2')}</TableHead>
                      <TableHead>{t('role')}</TableHead>
                      <TableHead>{t('school')}</TableHead>
                      <TableHead>{t('status2')}</TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {loading ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          {t('loading')}
                        </TableCell>
                      </TableRow>
                    ) : paginatedUsers.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                          {t('noUsersFound')}
                        </TableCell>
                      </TableRow>
                    ) : (
                      paginatedUsers.map((u) => (
                        <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <Avatar className="h-10 w-10">
                                <AvatarImage src={u.avatar_url} />
                                <AvatarFallback className="bg-brand-navy text-white">
                                  {u.full_name?.charAt(0)}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <div className="font-medium">{u.full_name}</div>
                                {u.phone && (
                                  <div className="text-sm text-muted-foreground flex items-center gap-1">
                                    <Phone className="h-3 w-3" />
                                    {u.phone}
                                  </div>
                                )}
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1 text-sm">
                              <Mail className="h-4 w-4 text-muted-foreground" />
                              {u.email}
                            </div>
                          </TableCell>
                          <TableCell>{getRoleBadge(u.role)}</TableCell>
                          <TableCell>
                            {u.tenant_id ? (
                              <div className="flex items-center gap-1 text-sm">
                                <Building2 className="h-4 w-4 text-muted-foreground" />
                                {getSchoolName(u.tenant_id)}
                              </div>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {u.is_active ? (
                              <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                                {t('active')}
                              </Badge>
                            ) : (
                              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                {t('inactive2')}
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => { setSelectedUser(u); setViewDialogOpen(true); }}>
                                  <Eye className="h-4 w-4 me-2" />
                                  {t('viewDetails')}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {u.is_active ? (
                                  <DropdownMenuItem onClick={() => handleStatusChange(u.id, false)}>
                                    <UserX className="h-4 w-4 me-2 text-red-600" />
                                    {t('deactivate')}
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem onClick={() => handleStatusChange(u.id, true)}>
                                    <UserCheck className="h-4 w-4 me-2 text-green-600" />
                                    {isRTL ? 'تفعيل الحساب' : 'Activate'}
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onClick={() => toast.info(t('comingSoon'))}>
                                  <Key className="h-4 w-4 me-2" />
                                  {t('resetPassword')}
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
              
              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    {isRTL 
                      ? `عرض ${(currentPage - 1) * itemsPerPage + 1} إلى ${Math.min(currentPage * itemsPerPage, filteredUsers.length)} من ${filteredUsers.length}`
                      : `Showing ${(currentPage - 1) * itemsPerPage + 1} to ${Math.min(currentPage * itemsPerPage, filteredUsers.length)} of ${filteredUsers.length}`
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

        {/* View User Dialog */}
        <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="font-cairo">{t('userDetails')}</DialogTitle>
            </DialogHeader>
            
            {selectedUser && (
              <div className="space-y-6 py-4">
                <div className="flex items-center gap-4">
                  <Avatar className="h-16 w-16">
                    <AvatarImage src={selectedUser.avatar_url} />
                    <AvatarFallback className="bg-brand-navy text-white text-xl">
                      {selectedUser.full_name?.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <h3 className="text-lg font-bold">{selectedUser.full_name}</h3>
                    {getRoleBadge(selectedUser.role)}
                  </div>
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <span>{selectedUser.email}</span>
                  </div>
                  {selectedUser.phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone className="h-4 w-4 text-muted-foreground" />
                      <span>{selectedUser.phone}</span>
                    </div>
                  )}
                  {selectedUser.tenant_id && (
                    <div className="flex items-center gap-2 text-sm">
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                      <span>{getSchoolName(selectedUser.tenant_id)}</span>
                    </div>
                  )}
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-muted rounded-xl p-3">
                    <p className="text-sm text-muted-foreground">{t('status2')}</p>
                    <p className="font-medium">
                      {selectedUser.is_active 
                        ? (t('active'))
                        : (t('inactive2'))
                      }
                    </p>
                  </div>
                  <div className="bg-muted rounded-xl p-3">
                    <p className="text-sm text-muted-foreground">{isRTL ? 'تاريخ الإنشاء' : 'Created'}</p>
                    <p className="font-medium">
                      {new Date(selectedUser.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US')}
                    </p>
                  </div>
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
