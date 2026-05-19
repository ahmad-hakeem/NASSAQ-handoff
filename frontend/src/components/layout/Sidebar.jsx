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
  CalendarDays,
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
  Upload,
  Sparkles,
  History,
  Trash2,
  Search,
} from 'lucide-react';
import CommandPalette from '../teacher/CommandPalette';


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
  const { user, logout, isImpersonating, schoolContext, getEffectiveRole, exitSchoolContext, token, updateToken, isSwitchedRole, originalRole, api, fetchPermissions } = useAuth();
  // Phase 0 §4.B-6 backed sidebar permission gate. Items that declare a
  // `permission` field are only shown once the backend confirms the
  // current user actually carries it. Until the lazy fetch resolves we
  // hide gated items (fail-closed) — never the other way round.
  const [perms, setPerms] = useState(null);
  useEffect(() => {
    let cancelled = false;
    if (!token || !fetchPermissions) return undefined;
    (async () => {
      try {
        const data = await fetchPermissions();
        if (cancelled) return;
        const list = Array.isArray(data?.permissions)
          ? data.permissions
          : Array.isArray(data?.effective_permissions)
            ? data.effective_permissions
            : Array.isArray(data) ? data : [];
        setPerms(new Set(list.map((p) => String(p))));
      } catch {
        if (!cancelled) setPerms(new Set());
      }
    })();
    return () => { cancelled = true; };
  }, [token, fetchPermissions]);
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  // 2026-05-18 — IT unread inbox counter for the unified
  // "التواصل والإشعارات" entry (Phase-1 badge migration). Polled
  // from the same IT-scoped endpoint NotificationBell uses so the
  // bell and the sidebar badge never diverge; the global
  // `notifications:refresh` event lets bulk mark-as-read in the
  // hub flush the badge immediately.
  const [unreadInbox, setUnreadInbox] = useState(0);
  const isIndependentTeacher = (user?.role || '').toLowerCase() === 'independent_teacher';
  useEffect(() => {
    if (!isIndependentTeacher || !token) {
      setUnreadInbox(0);
      return undefined;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get('/independent-teacher/notifications/unread-count');
        if (!cancelled) setUnreadInbox(Number(res?.data?.unread_count) || 0);
      } catch {
        if (!cancelled) setUnreadInbox(0);
      }
    };
    load();
    const interval = setInterval(load, 60000);
    const onRefresh = () => load();
    window.addEventListener('notifications:refresh', onRefresh);
    return () => {
      cancelled = true;
      clearInterval(interval);
      window.removeEventListener('notifications:refresh', onRefresh);
    };
  }, [api, token, isIndependentTeacher]);

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
      // Task #225 — IT §6.8 platform-admin hard-delete UI for archived workspaces.
      {
        icon: Trash2,
        label: t('workspacePurgeMenu'),
        href: '/admin/workspace-purge',
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
      // Task #173: first-class entry to the platform admin's personal
      // settings page. Without this, the only way to reach
      // `/account/settings` was a buried MFA deep-link inside Platform
      // Settings. Platform Settings (gear icon) stays where it is.
      {
        icon: UserCog,
        label: t('myAccount'),
        href: '/account/settings',
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
      // 3. Users & Classes Management — direct link (no sub-items),
      // mirrors the structure of Command Center / School Schedule.
      {
        icon: Users,
        label: t('usersClasses'),
        href: '/admin/users-management',
        roles: SCHOOL_ROLES,
      },
      // 4. Attendance Management
      {
        icon: CalendarCheck,
        label: t('staffAttendance'),
        href: '/admin/teacher-attendance',
        roles: SCHOOL_ROLES,
      },
      // 5. Assessments & Grades Management
      // TEMPORARILY HIDDEN — module under maintenance. Restore by uncommenting.
      // {
      //   icon: ClipboardList,
      //   label: t('examsAssessments'),
      //   href: '/admin/assessments',
      //   roles: SCHOOL_ROLES,
      // },
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
    // Task #189 §5.2: shared items also visible to `independent_teacher`;
    // the IT-only workspace-settings entry is added below.
    const teacherItems = [
      {
        icon: Home,
        label: t('dashboard'),
        href: '/teacher',
        roles: ['teacher', 'independent_teacher'],
      },
      {
        icon: BookOpen,
        label: t('myClasses'),
        href: '/teacher/classes',
        roles: ['teacher', 'independent_teacher'],
        dataTour: 'sidebar-my-classes',
      },
      {
        icon: Award,
        label: t('myAchievements'),
        href: '/teacher/achievements',
        roles: ['teacher', 'independent_teacher'],
      },
      {
        icon: MessageSquare,
        label: t('communicationNotifications'),
        href: '/teacher/communication',
        roles: ['teacher', 'independent_teacher'],
        dataTour: 'sidebar-communication',
        // 2026-05-18 — surface the IT unread inbox count next to
        // this single unified entry now that the standalone
        // "الإشعارات" item is gone. The sidebar polls the same
        // IT-scoped /independent-teacher/notifications/unread-count
        // endpoint NotificationBell uses, so the bell and the
        // sidebar badge never disagree.
        showUnreadBadge: true,
      },
      {
        icon: Network,
        label: t('aiInsights'),
        href: '/ai-insights',
        roles: ['teacher', 'independent_teacher'],
      },
      // 2026-05-18 — Unified "الملف الشخصي والإعدادات" entry. The
      // legacy /teacher/settings page has been folded into the
      // canonical /account/settings hub (AccountSettingsPage), and
      // the legacy route now redirects there in appRoutes.js. The
      // bottom-of-sidebar user-card shortcut already points at
      // /account/settings, so both navigation entry points now land
      // on the same surface.
      {
        icon: Settings,
        label: t('profileSettings'),
        href: '/account/settings',
        roles: ['teacher', 'independent_teacher'],
        dataTour: 'sidebar-account-settings',
      },
      // 2026-05-19 — The standalone "إعدادات مساحتي" sidebar entry
      // has been retired. Its two halves now live in their natural
      // homes: identity (name/logo) under Account Settings → My
      // Workspace, and schedule baseline + active year/term under
      // فصولي → "إعدادات الجدول" tab. /teacher/workspace-settings
      // still resolves (it redirects to /teacher/classes?tab=settings)
      // so existing bookmarks and internal links keep working.
      // Task #193 §5.4 — Independent-Teacher manual schedule editor.
      // 2026-05-18 — The standalone "جدولي" sidebar entry has been
      // folded into the "فصولي" page as a fourth tab so IT users
      // get classes / sessions / lesson-planner / schedule under one
      // mounted shell. /teacher/workspace-schedule still resolves
      // (it redirects to /teacher/classes?tab=schedule) so existing
      // bookmarks and internal links keep working.
      // Task #208 §6.3 — Independent-Teacher only: personal calendar.
      // Role-gated AND permission-gated on the new `events.author_own`
      // permission so the link is only shown when the backend RBAC
      // slice actually exposes the route to this user.
      {
        icon: CalendarDays,
        label: 'تقويمي الشخصي',
        href: '/teacher/calendar',
        roles: ['independent_teacher'],
        permission: 'events.author_own',
        dataTour: 'sidebar-calendar',
      },
      // Task #190 §5.3 — IT-only workspace subjects CRUD.
      // 2026-05-18 — The standalone "المواد" sidebar entry has been
      // folded into the "فصولي" page as a fifth tab so IT users
      // get classes / sessions / lesson-planner / schedule / subjects
      // under one mounted shell. /teacher/subjects still resolves
      // (redirects to /teacher/classes?tab=subjects) so old bookmarks
      // and the create-class dialog dropdown keep working.
      // Task #207 §6.1 — IT-only workspace-aware bulk student import.
      // Permission-gated on `students.bulk_import_workspace` so a
      // future RBAC change that grants the permission to additional
      // roles surfaces the link automatically.
      {
        icon: Upload,
        label: 'استيراد الطلاب',
        href: '/teacher/import-students',
        roles: ['independent_teacher'],
        permission: 'students.bulk_import_workspace',
        dataTour: 'sidebar-import-students',
      },
      // Task #278 — IT-only bulk-import hub (students / classes /
      // subjects / duplicate-week). Permission-gated on the new
      // `classes.bulk_import_workspace` slice.
      {
        icon: Upload,
        label: 'الاستيراد الجماعي',
        href: '/teacher/bulk-import',
        roles: ['independent_teacher'],
        permission: 'classes.bulk_import_workspace',
        dataTour: 'sidebar-bulk-import',
      },
      // Task #185 — IT-only subjects CRUD page (workspace-scoped).
      // 2026-05-18 — Duplicate "موادي" sidebar entry removed; the
      // primary entry point is now the "المواد" tab inside
      // /teacher/classes (?tab=subjects). See the redirect in
      // appRoutes.js — old bookmarks land on the new embedded tab.
      // 2026-05-18 — IT "مساعد خطط الدروس" (lesson planner) was
      // relocated into the "فصولي" tabs as `?tab=lesson-planner`
      // (alongside فصولي / إدارة الحصص). The standalone sidebar
      // entry is removed to avoid duplicate nav; deep links to
      // /teacher/lesson-planner redirect to /teacher/classes?tab=
      // lesson-planner in appRoutes.js so historical bookmarks
      // continue to work. Permission gating (ai.lesson_plans) is
      // preserved at both the redirect route and the tab itself.
      // 2026-05-18 — IT "سجل النشاط" was relocated into the unified
      // Account Settings page (tab id `activity`). The sidebar entry
      // is removed to eliminate the duplicate nav item; deep links to
      // /teacher/audit-log redirect to /account/settings#activity in
      // appRoutes.js so historical bookmarks continue to work.
      // 2026-05-19 — Standalone "التحليلات" sidebar entry retired.
      // Its panel is now embedded in /ai-insights as the
      // "التحليلات الرقمية" tab so IT users have a single AI/analytics
      // entry point. /teacher/analytics still redirects there for
      // legacy bookmarks (see appRoutes.js).
      // 2026-05-18 — Standalone IT "الإشعارات" entry removed. The
      // inbox now lives inside the unified "التواصل والإشعارات"
      // hub as its default "البريد الوارد" tab; the unread counter
      // moved onto the kept communication entry above
      // (`showUnreadBadge: true`). Deep links to
      // /teacher/notifications redirect to
      // /teacher/communication?tab=inbox in appRoutes.js so
      // historical bookmarks continue to work.
    ];

    // Parent Menu Items — mirrors the historical Parent Portal navigation so
    // parent users plug into the same shared sidebar registry as everyone else.
    const parentItems = [
      {
        icon: Home,
        label: t('home'),
        href: '/parent',
        roles: ['parent'],
      },
      {
        icon: Users,
        label: t('studentProfile'),
        href: '/parent/children',
        roles: ['parent'],
      },
      {
        icon: MessageSquare,
        label: t('communicationCenter'),
        href: '/parent/communication',
        roles: ['parent'],
      },
      // Absence Excuse, Meeting Request and Notifications are now consolidated
      // inside the Communication Center for parents (tabs). The underlying
      // routes/components remain available for direct deep-links and future
      // reactivation, but they are intentionally hidden from the sidebar to
      // keep the parent IA simple.
      // The standalone Reports page has been merged into the Student Profile
      // (Reports & Statistics tab). The legacy ``/parent/reports`` route
      // still exists but redirects to ``/parent/children`` so the parent
      // can pick a child and open their unified profile.
      {
        icon: Settings,
        label: t('settings'),
        href: '/parent/settings',
        roles: ['parent'],
      },
    ];

    // Combine all items
    const allItems = [...platformAdminItems, ...schoolItems, ...teacherItems, ...parentItems];
    
    // Filter by effective role (supports impersonation)
    // effectiveRole is already defined at the start of this function
    const filteredItems = allItems.filter((item) => {
      if (!item.roles.includes(effectiveRole)) return false;
      if (!item.permission) return true;
      // fail-closed while permissions are still loading
      return !!(perms && perms.has(item.permission));
    });
    
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
      <CommandPalette />
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
            {((getEffectiveRole ? getEffectiveRole() : user?.role) === 'independent_teacher') && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => window.dispatchEvent(new CustomEvent('nassaq:open-command-palette'))}
                className="text-white/70 hover:text-white hover:bg-white/10"
                data-testid="sidebar-cmdk-btn"
                title={t('cmdkOpen')}
              >
                <Search className="h-5 w-5" />
              </Button>
            )}
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
                ? user.role === 'platform_admin' || user.role === 'platform_operations_manager'
                  ? 'مدير المنصة'
                  : user.role === 'school_principal' || user.role === 'school_admin'
                  ? 'مدير المدرسة'
                  : user.role === 'school_sub_admin'
                  ? 'مساعد المدير'
                  : user.role === 'teacher'
                  ? 'معلم'
                  : user.role === 'independent_teacher'
                  ? 'معلم مستقل'
                  : user.role === 'parent'
                  ? 'ولي أمر'
                  : user.role === 'student'
                  ? 'طالب'
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
                data-tour={item.dataTour}
                className={`sidebar-item ${
                  isActive(item.href) ? 'sidebar-item-active' : 'sidebar-item-inactive'
                }`}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                {/* 2026-05-18 — unread badge for sidebar items that
                    opt in via `showUnreadBadge`. Currently used by
                    the IT unified communications entry. Renders in
                    both collapsed and expanded modes so the cue is
                    never hidden behind the rail. */}
                {item.showUnreadBadge && unreadInbox > 0 && (
                  <Badge
                    variant="destructive"
                    className={`h-5 min-w-[1.25rem] px-1.5 text-[10px] font-semibold flex items-center justify-center rounded-full ${collapsed ? 'absolute top-1 end-1' : 'ms-auto'}`}
                    data-testid={`sidebar-badge-${item.href.replace(/\//g, '-')}`}
                  >
                    {unreadInbox > 99 ? '99+' : unreadInbox}
                  </Badge>
                )}
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
            {/* Task #173: footer identity area is now a one-click
                affordance to /account/settings for every authenticated
                role (including platform_admin). The avatar+name block is
                a real button so keyboard and screen-reader users get the
                same shortcut. The trailing logout icon stays as its own
                button. No full reload — react-router navigate(). */}
            <button
              type="button"
              onClick={() => { navigate('/account/settings'); setMobileOpen(false); }}
              className="flex items-center gap-3 flex-1 min-w-0 text-start rounded-xl p-1 -m-1 hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-brand-turquoise/60 transition-colors"
              title={t('accountSettings')}
              aria-label={t('accountSettings')}
              data-testid="sidebar-footer-account"
            >
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
                <div className="flex items-center gap-1.5 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{user.full_name}</p>
                  {/* Task #200 §5.8 — Sub-brand role badge for the
                      Independent-Teacher persona. Uses the workspace-accent
                      design token so it stays consistent with the wizard
                      header, workspace settings header, and IT empty states. */}
                  {((getEffectiveRole ? getEffectiveRole() : user.role) === 'independent_teacher') && (
                    <span
                      className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-workspace-accent-light text-workspace-accent-fg border border-workspace-accent-border flex-shrink-0"
                      data-testid="sidebar-it-role-badge"
                      title={isRTL ? 'معلم مستقل' : 'Independent Teacher'}
                    >
                      {isRTL ? 'معلم مستقل' : 'IT'}
                    </span>
                  )}
                </div>
                <p className="text-xs text-white/50 truncate">
                  {(() => {
                    const effectiveRole = getEffectiveRole ? getEffectiveRole() : user.role;
                    if (isRTL) {
                      return effectiveRole === 'platform_admin' || effectiveRole === 'platform_operations_manager'
                        ? 'مدير المنصة'
                        : effectiveRole === 'school_principal' || effectiveRole === 'school_admin'
                        ? 'مدير المدرسة'
                        : effectiveRole === 'school_sub_admin'
                        ? 'مساعد المدير'
                        : effectiveRole === 'teacher'
                        ? 'معلم'
                        : effectiveRole === 'independent_teacher'
                        ? 'معلم مستقل'
                        : effectiveRole === 'parent'
                        ? 'ولي أمر'
                        : effectiveRole === 'student'
                        ? 'طالب'
                        : effectiveRole;
                    }
                    return effectiveRole?.replace('_', ' ');
                  })()}
                </p>
              </div>
            </button>
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
          {/* Task #173: collapsed-sidebar avatar is also clickable —
              same /account/settings shortcut as the expanded footer. */}
          <button
            type="button"
            onClick={() => { navigate('/account/settings'); setMobileOpen(false); }}
            className="w-full flex justify-center rounded-lg p-1 hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-brand-turquoise/60 transition-colors"
            title={t('accountSettings')}
            aria-label={t('accountSettings')}
            data-testid="sidebar-footer-account-collapsed"
          >
            <div className="w-8 h-8 rounded-lg bg-brand-turquoise flex items-center justify-center overflow-hidden">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name} className="w-full h-full object-cover" />
              ) : (
                <span className="text-white text-xs font-semibold">{user.full_name?.charAt(0)}</span>
              )}
            </div>
          </button>
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
