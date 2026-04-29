import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { ScrollArea } from '../ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Badge } from '../ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { BetaBadge } from '../BetaDisclaimer';
import {
  LayoutDashboard,
  Building2,
  Users,
  GraduationCap,
  UserCheck,
  BookOpen,
  Calendar,
  CalendarCheck,
  ClipboardList,
  BarChart3,
  Settings,
  ChevronRight,
  ChevronLeft,
  Menu,
  X,
  Bell,
  MessageSquare,
  LogOut,
  Shield,
  Activity,
  Link2,
  FileText,
  UserCog,
  Network,
  RefreshCw,
  Eye,
  ArrowLeftRight,
  FileSpreadsheet,
  Home,
  FolderOpen,
  Star,
  Play,
  Award,
  Lightbulb,
  ChevronDown,
} from 'lucide-react';


const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';

const getRoleNameAr = (role) => {
  const names = {
    platform_admin: 'مدير المنصة',
    platform_operations_manager: 'مدير العمليات',
    school_principal: 'مدير المدرسة',
    school_admin: 'مسؤول المدرسة',
    school_sub_admin: 'نائب مدير المدرسة',
    teacher: 'معلم',
    student: 'طالب',
    parent: 'ولي أمر',
  };
  return names[role] || role;
};

export const Sidebar = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showRoleSwitcher, setShowRoleSwitcher] = useState(false);
  const [availableRoles, setAvailableRoles] = useState([]);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [switchingRole, setSwitchingRole] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});
  const { user, logout, isImpersonating, schoolContext, getEffectiveRole, exitSchoolContext, token, updateToken, isSwitchedRole, originalRole, api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  // Fetch available roles on mount
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    // Only fetch if we have a valid token and user
    if (token && user?.id) {
      // Small delay to ensure auth context is fully initialized
      const timeoutId = setTimeout(() => {
        fetchAvailableRoles();
      }, 100);
      return () => clearTimeout(timeoutId);
    }
  }, [token, user?.id]);

  // Fetch available roles when modal opens
  useEffect(() => {
    if (showRoleSwitcher && token && user?.id) {
      fetchAvailableRoles();
    }
  }, [showRoleSwitcher, token, user?.id]);

  const fetchAvailableRoles = async () => {
    // Double check token is valid before making request
    if (!token) {
      console.warn('Skipping roles fetch - no token available');
      return;
    }
    
    setLoadingRoles(true);
    try {
      const response = await api.get('/user-roles/my-roles');
      setAvailableRoles(response.data.available_roles || []);
    } catch (error) {
      console.error('Error fetching roles:', error);
      // Only show error if it's not a token/auth issue (those are handled by logout)
      if (error.response?.status !== 401 && error.response?.status !== 403) {
        // Don't show error toast - just log it silently
        setAvailableRoles([]);
      }
    } finally {
      setLoadingRoles(false);
    }
  };

  const handleSwitchRole = async (role) => {
    if (role.is_current) return;
    
    setSwitchingRole(true);
    try {
      const response = await api.post('/user-roles/switch', {
        target_role: role.role,
        target_tenant_id: role.tenant_id
      });
      
      if (response.data.success) {
        await updateToken(response.data.access_token);

        toast.success(response.data.message || (t('roleSwitchedSuccessfully')));
        setShowRoleSwitcher(false);

        const redirectTo = response.data.redirect_to || '/';
        navigate(redirectTo);
      }
    } catch (error) {
      console.error('Error switching role:', error);
      nassaqError(t('errorSwitchingRole'));
    } finally {
      setSwitchingRole(false);
    }
  };

  const handleReturnToOriginal = async () => {
    setSwitchingRole(true);
    try {
      const response = await api.post('/user-roles/return-to-original', {});
      
      if (response.data.success) {
        await updateToken(response.data.access_token);

        toast.success(response.data.message || (t('returnedToOriginalRole')));
        setShowRoleSwitcher(false);

        const redirectTo = response.data.redirect_to || '/admin';
        navigate(redirectTo);
      }
    } catch (error) {
      console.error('Error returning to original role:', error);
      nassaqError(t('errorReturningToOriginalRole'));
    } finally {
      setSwitchingRole(false);
    }
  };

  const handleLogout = () => {
    nassaqWarning(
      t('areYouSureYouWantToLogOut'),
      {
        title: t('confirmLogout'),
        confirmText: t('logout'),
        cancelText: t('cancel'),
        showCancel: true,
        onConfirm: async () => {
          setLoggingOut(true);
          try {
            await api.post('/auth/logout', {}).catch(() => {});
            logout();
            navigate('/login');
          } catch (e) {
            logout();
            navigate('/login');
          } finally {
            setLoggingOut(false);
          }
        },
      }
    );
  };
  
  // Handle exit from school context (impersonation mode)
  const handleExitSchoolContext = () => {
    exitSchoolContext();
    navigate('/admin/tenants');
  };

  const getMenuItems = () => {
    // Get effective role (supports impersonation)
    const effectiveRole = getEffectiveRole ? getEffectiveRole() : user?.role;
    
    // Platform Admin Menu Items - مدير المنصة
    // Based on Platform Admin Role Documentation
    const platformAdminItems = [
      {
        icon: LayoutDashboard,
        label: t('controlDashboard'),
        href: '/admin',
        roles: ['platform_admin'],
      },
      {
        icon: Building2,
        label: t('schoolsManagement'),
        href: '/admin/schools',
        roles: ['platform_admin'],
      },
      {
        icon: Users,
        label: t('usersManagement'),
        href: '/admin/users',
        roles: ['platform_admin'],
      },
      {
        icon: Activity,
        label: t('systemMonitoring'),
        href: '/admin/monitoring',
        roles: ['platform_admin'],
      },
      {
        icon: Network,
        label: t('aiInsights'),
        href: '/principal/ai-insights',
        roles: ['platform_admin'],
      },
      {
        icon: Link2,
        label: t('integrations'),
        href: '/admin/integrations',
        roles: ['platform_admin'],
      },
      {
        icon: Shield,
        label: t('securityCenter'),
        href: '/admin/security',
        roles: ['platform_admin'],
      },
      {
        icon: FileText,
        label: t('auditLogs'),
        href: '/admin/audit',
        roles: ['platform_admin', 'platform_security_officer', 'platform_data_analyst'],
      },
      {
        icon: MessageSquare,
        label: t('communicationNotifications'),
        href: '/admin/communication',
        roles: ['platform_admin'],
      },
      {
        icon: Lightbulb,
        label: t('productHub'),
        href: '/admin/product-hub',
        roles: ['platform_admin'],
      },
    ];

    // School Principal & Sub Admin Menu Items
    // Reorganized according to the required structure
    // school_admin = new schools admins (same access as school_principal)
    const SCHOOL_ROLES = ['school_principal', 'school_admin', 'school_sub_admin'];
    const SCHOOL_PRINCIPAL_ROLES = ['school_principal', 'school_admin'];
    const schoolItems = [
      // 1. Dashboard Overview
      {
        icon: LayoutDashboard,
        label: t('commandCenter2'),
        href: '/principal',
        roles: SCHOOL_ROLES,
      },
      // 2. Schedule Management
      {
        icon: Calendar,
        label: t('schoolSchedule'),
        href: '/school/schedule',
        roles: SCHOOL_ROLES,
      },
      // 3. Users & Classes Management
      {
        icon: Users,
        label: t('usersClasses'),
        href: '/admin/users-management',
        roles: SCHOOL_ROLES,
        subItems: [
          {
            label: t('teachers'),
            href: '/admin/users-management?filter=teachers',
          },
          {
            label: t('students'),
            href: '/admin/users-management?filter=students',
          },
          {
            label: t('classes2'),
            href: '/admin/users-management?filter=classes',
          },
        ],
      },
      // 4. Attendance Management
      {
        icon: CalendarCheck,
        label: t('staffAttendance'),
        href: '/admin/teacher-attendance',
        roles: SCHOOL_ROLES,
      },
      // 5. Assessments & Grades Management
      {
        icon: ClipboardList,
        label: t('examsAssessments'),
        href: '/admin/assessments',
        roles: SCHOOL_ROLES,
      },
      // 6. School Settings
      {
        icon: Settings,
        label: t('schoolSettings'),
        href: '/school/settings',
        roles: SCHOOL_PRINCIPAL_ROLES,
      },
      
      // 7. Communication & Notifications
      {
        icon: Bell,
        label: t('communicationCenter'),
        href: '/principal/communication',
        roles: SCHOOL_ROLES,
      },
      // 8. AI Insights
      {
        icon: Network,
        label: t('aiInsights'),
        href: '/principal/ai-insights',
        roles: SCHOOL_ROLES,
      },
      // 10. Account Settings
      {
        icon: UserCog,
        label: t('accountSettings'),
        href: '/account/settings',
        roles: SCHOOL_ROLES,
      },
    ];

    // Teacher Menu Items — Task #79: schedule, portfolio/achievements, notifications nav
    const teacherItems = [
      {
        icon: Home,
        label: t('dashboard'),
        href: '/teacher',
        roles: ['teacher'],
      },
      {
        icon: BookOpen,
        label: t('myClasses'),
        href: '/teacher/classes',
        roles: ['teacher'],
      },
      {
        icon: Award,
        label: t('myAchievements'),
        href: '/teacher/achievements',
        roles: ['teacher'],
      },
      {
        icon: MessageSquare,
        label: t('communicationNotifications'),
        href: '/teacher/communication',
        roles: ['teacher'],
      },
      {
        icon: Network,
        label: t('aiInsights'),
        href: '/ai-insights',
        roles: ['teacher'],
      },
      {
        icon: Settings,
        label: t('profileSettings'),
        href: '/teacher/settings',
        roles: ['teacher'],
      },
    ];

    // Combine all items
    const allItems = [...platformAdminItems, ...schoolItems, ...teacherItems];
    
    // Filter by effective role (supports impersonation)
    // effectiveRole is already defined at the start of this function
    const filteredItems = allItems.filter((item) => item.roles.includes(effectiveRole));
    
    // Remove duplicates by href
    const uniqueItems = filteredItems.reduce((acc, current) => {
      const exists = acc.find(item => item.href === current.href);
      if (!exists) {
        acc.push(current);
      }
      return acc;
    }, []);

    return uniqueItems;
  };

  const menuItems = getMenuItems();

  const isActive = (href) => {
    // Support deep links like "/teacher/communication?tab=bulletin"
    const [hrefPath, hrefQuery] = href.split('?');
    if (location.pathname !== hrefPath) return false;
    if (!hrefQuery) return true;
    // All query params in href must match current URL
    const current = new URLSearchParams(location.search);
    const target = new URLSearchParams(hrefQuery);
    for (const [k, v] of target.entries()) {
      if (current.get(k) !== v) return false;
    }
    return true;
  };

  const SidebarContent = () => {
    return (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 flex flex-col items-center">
        {/* Logo and collapse button row */}
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between'} w-full`}>
          {!collapsed && (
            <Link to="/" className="flex items-center gap-2">
              <img src={LOGO_WHITE} alt="نَسَّق" className="h-10 w-auto rounded-xl" />
              <BetaBadge />
            </Link>
          )}
          {collapsed && (
            <Link to="/" className="flex-shrink-0">
              <img src={LOGO_WHITE} alt="نَسَّق" className="h-8 w-8 rounded-lg object-contain" />
            </Link>
          )}
          <div className="flex items-center gap-1">
            {availableRoles.length > 1 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowRoleSwitcher(true)}
                className="text-white/70 hover:text-white hover:bg-white/10"
                data-testid="sidebar-role-switch-btn"
                title={t('switchRole')}
              >
                <ArrowLeftRight className="h-5 w-5" />
              </Button>
            )}
            {user?.role === 'platform_admin' && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => { navigate('/settings'); setMobileOpen(false); }}
                className={`text-white/70 hover:text-white hover:bg-white/10 ${
                  location.pathname === '/settings' ? 'bg-white/15 text-white' : ''
                }`}
                data-testid="sidebar-settings-btn"
                title={t('systemSettings')}
              >
                <Settings className="h-5 w-5" />
              </Button>
            )}
            {!collapsed && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCollapsed(!collapsed)}
                className="text-white/70 hover:text-white hover:bg-white/10 hidden lg:flex"
                data-testid="sidebar-collapse-btn"
              >
                {isRTL ? (
                  <ChevronRight className="h-5 w-5" />
                ) : (
                  <ChevronLeft className="h-5 w-5" />
                )}
              </Button>
            )}
          </div>
        </div>
        
        {/* Collapse button when collapsed */}
        {collapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(!collapsed)}
            className="text-white/70 hover:text-white hover:bg-white/10 mt-2 hidden lg:flex"
            data-testid="sidebar-collapse-btn"
          >
            {isRTL ? (
              <ChevronLeft className="h-5 w-5" />
            ) : (
              <ChevronRight className="h-5 w-5" />
            )}
          </Button>
        )}
        
        {/* User info when collapsed */}
        {collapsed && user && (
          <div className="mt-3 text-center">
            <p className="text-xs font-medium text-white truncate max-w-[60px]">
              {user.full_name?.split(' ')[0]}
            </p>
            <p className="text-[10px] text-white/50 truncate max-w-[60px]">
              {isRTL
                ? user.role === 'platform_admin'
                  ? 'مدير المنصة'
                  : user.role === 'school_principal' || user.role === 'school_admin'
                  ? 'مدير المدرسة'
                  : user.role === 'teacher'
                  ? 'معلم'
                  : user.role?.replace('_', ' ')
                : user.role?.replace('_', ' ')}
            </p>
          </div>
        )}
      </div>

      {/* Menu Items */}
      <ScrollArea className="flex-1 px-3" dir={isRTL ? 'rtl' : 'ltr'}>
        <nav className="space-y-1 py-4" dir={isRTL ? 'rtl' : 'ltr'}>
          {menuItems.map((item) => {
            const hasSubItems = item.subItems && item.subItems.length > 0;
            const isGroupExpanded = expandedGroups[item.href];
            const isAnySubActive = hasSubItems && item.subItems.some(sub => isActive(sub.href));

            if (hasSubItems && !collapsed) {
              return (
                <div key={item.href}>
                  <button
                    onClick={() => setExpandedGroups(prev => ({ ...prev, [item.href]: !prev[item.href] }))}
                    data-testid={`sidebar-link-${item.href.replace(/\//g, '-')}`}
                    className={`sidebar-item w-full ${
                      isAnySubActive ? 'sidebar-item-active' : 'sidebar-item-inactive'
                    }`}
                  >
                    <item.icon className="h-5 w-5 flex-shrink-0" />
                    <span className="flex-1 text-start">{item.label}</span>
                    <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${isGroupExpanded ? 'rotate-180' : ''}`} />
                  </button>
                  {isGroupExpanded && (
                    <div className="mt-0.5 space-y-0.5">
                      {item.subItems.map(sub => (
                        <Link
                          key={sub.href}
                          to={sub.href}
                          onClick={() => setMobileOpen(false)}
                          className={`block py-2 rounded-xl text-sm transition-colors duration-150 ${isRTL ? 'pr-12 pl-4 text-right' : 'pl-12 pr-4 text-left'} ${
                            isActive(sub.href)
                              ? 'text-brand-turquoise bg-white/10 font-medium'
                              : 'text-white/60 hover:text-white hover:bg-white/5'
                          }`}
                        >
                          {sub.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            }

            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={() => setMobileOpen(false)}
                data-testid={`sidebar-link-${item.href.replace(/\//g, '-')}`}
                className={`sidebar-item ${
                  isActive(item.href) ? 'sidebar-item-active' : 'sidebar-item-inactive'
                }`}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      {/* User Info & Logout */}
      {!collapsed && user && (
        <div className="p-4 border-t border-white/10">
          {isSwitchedRole && (
            <div className="mb-3 p-2 rounded-lg bg-brand-turquoise/20 border border-brand-turquoise/30">
              <div className="flex items-center gap-2 text-brand-turquoise text-xs">
                <ArrowLeftRight className="h-3 w-3" />
                <span className="font-medium">
                  {t('switchedRole')}
                </span>
              </div>
              <p className="text-[10px] text-white/70 mt-1">
                {isRTL ? `الدور الأصلي: ${getRoleNameAr(originalRole)}` : `Original: ${originalRole?.replace(/_/g, ' ')}`}
              </p>
            </div>
          )}
          {isImpersonating && schoolContext && !isSwitchedRole && (
            <div className="mb-3 p-2 rounded-lg bg-amber-500/20 border border-amber-500/30">
              <div className="flex items-center gap-2 text-amber-200 text-xs">
                <Shield className="h-3 w-3" />
                <span className="font-medium">
                  {t('previewMode')}
                </span>
              </div>
              <p className="text-[10px] text-amber-100/80 truncate mt-1">
                {schoolContext.school_name}
              </p>
            </div>
          )}
          
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-turquoise flex items-center justify-center overflow-hidden flex-shrink-0">
              {user.avatar_url ? (
                <img 
                  src={user.avatar_url} 
                  alt={user.full_name} 
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-white font-semibold">
                  {user.full_name?.charAt(0)}
                </span>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user.full_name}</p>
              <p className="text-xs text-white/50 truncate">
                {(() => {
                  const effectiveRole = getEffectiveRole ? getEffectiveRole() : user.role;
                  if (isRTL) {
                    return effectiveRole === 'platform_admin'
                      ? 'مدير المنصة'
                      : effectiveRole === 'school_principal' || effectiveRole === 'school_admin'
                      ? 'مدير المدرسة'
                      : effectiveRole === 'teacher'
                      ? 'معلم'
                      : effectiveRole;
                  }
                  return effectiveRole?.replace('_', ' ');
                })()}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleLogout}
              disabled={loggingOut}
              className="flex-shrink-0 text-red-300/70 hover:text-red-200 hover:bg-red-500/20 rounded-xl transition-colors"
              data-testid="logout-btn"
              title={t('logout')}
              aria-label={t('logout')}
            >
              {loggingOut ? (
                <RefreshCw className="h-5 w-5 animate-spin" />
              ) : (
                <LogOut className="h-5 w-5" />
              )}
            </Button>
          </div>
        </div>
      )}
      
      {collapsed && user && (
        <div className="p-3 border-t border-white/10 space-y-2">
          {isSwitchedRole && (
            <div className="w-full flex justify-center">
              <div className="w-3 h-3 rounded-full bg-brand-turquoise animate-pulse" title={t('switchedRole')} />
            </div>
          )}
          <div className="w-full flex justify-center">
            <div className="w-8 h-8 rounded-lg bg-brand-turquoise flex items-center justify-center overflow-hidden">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name} className="w-full h-full object-cover" />
              ) : (
                <span className="text-white text-xs font-semibold">{user.full_name?.charAt(0)}</span>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            disabled={loggingOut}
            className="w-full text-red-300/70 hover:text-red-200 hover:bg-red-500/20"
            title={t('logout')}
            aria-label={t('logout')}
            data-testid="logout-btn-collapsed"
          >
            {loggingOut ? (
              <RefreshCw className="h-5 w-5 animate-spin" />
            ) : (
              <LogOut className="h-5 w-5" />
            )}
          </Button>
        </div>
      )}

      {/* Role Switcher Modal */}
      <Dialog open={showRoleSwitcher} onOpenChange={setShowRoleSwitcher}>
        <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowLeftRight className="h-5 w-5 text-brand-turquoise" />
              {t('switchRole2')}
            </DialogTitle>
          </DialogHeader>
          
          {loadingRoles ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {availableRoles.map((role, index) => (
                <button
                  key={`${role.role}-${role.tenant_id || index}`}
                  onClick={() => handleSwitchRole(role)}
                  disabled={role.is_current || switchingRole}
                  className={`w-full p-3 rounded-lg border transition-all text-start ${
                    role.is_current
                      ? 'bg-brand-turquoise/10 border-brand-turquoise'
                      : 'bg-background border-border hover:border-brand-turquoise hover:bg-muted'
                  } ${switchingRole ? 'opacity-50 cursor-not-allowed' : ''}`}
                  data-testid={`switch-role-${role.role}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        role.is_current ? 'bg-brand-turquoise text-white' : 'bg-muted'
                      }`}>
                        {role.is_preview ? (
                          <Eye className="h-5 w-5" />
                        ) : role.role === 'platform_admin' ? (
                          <Shield className="h-5 w-5" />
                        ) : role.role === 'school_principal' || role.role === 'school_admin' || role.role === 'school_sub_admin' ? (
                          <Building2 className="h-5 w-5" />
                        ) : role.role === 'teacher' || role.role === 'independent_teacher' ? (
                          <GraduationCap className="h-5 w-5" />
                        ) : role.role === 'student' ? (
                          <BookOpen className="h-5 w-5" />
                        ) : (
                          <Users className="h-5 w-5" />
                        )}
                      </div>
                      <div>
                        <p className="font-medium text-sm">
                          {isRTL ? (role.descriptive_ar || role.role_name_ar) : (role.descriptive_en || role.role_name_en)}
                        </p>
                        {role.tenant_name && !role.descriptive_ar && (
                          <p className="text-xs text-muted-foreground">
                            {role.tenant_name}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {role.is_current && (
                        <Badge variant="secondary" className="bg-brand-turquoise/20 text-brand-turquoise">
                          {t('current2')}
                        </Badge>
                      )}
                      {role.is_preview && (
                        <Badge variant="outline" className="text-amber-500 border-amber-500">
                          {t('preview')}
                        </Badge>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
          
          {isSwitchedRole && (
            <Button
              variant="outline"
              onClick={handleReturnToOriginal}
              disabled={switchingRole}
              className="w-full mt-4 border-brand-turquoise/50 text-brand-turquoise hover:bg-brand-turquoise/10"
            >
              <RefreshCw className={`h-4 w-4 me-2 ${switchingRole ? 'animate-spin' : ''}`} />
              {t('returnToOriginalRole')}
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </div>
    );
  };

  return (
    <div className="min-h-screen flex">
      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setMobileOpen(!mobileOpen)}
        className="lg:hidden fixed top-3 start-3 z-50 bg-brand-navy text-white shadow-lg rounded-xl h-10 w-10"
        data-testid="mobile-sidebar-toggle"
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        dir={isRTL ? 'rtl' : 'ltr'}
        className={`
          fixed inset-y-0 z-40 bg-brand-navy overflow-hidden
          transition-all duration-300 ease-in-out
          ${isRTL ? 'right-0' : 'left-0'}
          ${collapsed ? 'w-20' : 'w-72'}
          ${mobileOpen ? 'translate-x-0' : isRTL ? 'translate-x-full lg:translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <div className="absolute inset-0 nassaq-pattern opacity-[0.03] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
        <SidebarContent />
      </aside>

      {/* Main Content */}
      <main
        className={`
          flex-1 min-w-0 min-h-screen bg-background w-full overflow-x-hidden
          transition-all duration-300 pt-14 lg:pt-0
          ${isRTL
            ? collapsed ? 'lg:mr-20' : 'lg:mr-72'
            : collapsed ? 'lg:ml-20' : 'lg:ml-72'
          }
        `}
      >
        {children}
      </main>
    </div>
  );
};
