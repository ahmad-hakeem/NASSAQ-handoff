import { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import {
  LayoutDashboard,
  Building2,
  Users,
  UserCog,
  CalendarCheck,
  BookOpen,
  Calendar,
  CalendarDays,
  Settings,
  Menu,
  X,
  Bell,
  MessageSquare,
  Shield,
  Activity,
  Link2,
  FileText,
  Network,
  FileSpreadsheet,
  Home,
  Award,
  Lightbulb,
  Trash2,
} from 'lucide-react';
import SidebarContent from './sidebar/SidebarContent';
import RoleSwitcherDialog from './sidebar/RoleSwitcherDialog';
import PreviewReasonDialog from './sidebar/PreviewReasonDialog';
import PreviewModeBanner from './PreviewModeBanner';
import { getApiErrorMessage } from '../../utils/apiError';

export const Sidebar = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [showRoleSwitcher, setShowRoleSwitcher] = useState(false);
  const [availableRoles, setAvailableRoles] = useState([]);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [switchingRole, setSwitchingRole] = useState(false);
  const [previewReasonRole, setPreviewReasonRole] = useState(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});
  const {
    user, logout, isImpersonating, schoolContext, getEffectiveRole,
    exitSchoolContext, token, updateToken, isSwitchedRole, originalRole,
    api, fetchPermissions, returnToOriginalRole, enterSchoolContext,
  } = useAuth();

  // Phase 0 §4.B-6 backed sidebar permission gate.
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

  const { nassaqError, nassaqWarning } = useNassaqAlert();

  const fetchAvailableRoles = useCallback(async () => {
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
      if (error.response?.status !== 401 && error.response?.status !== 403) {
        setAvailableRoles([]);
      }
    } finally {
      setLoadingRoles(false);
    }
  }, [api, token]);

  // Fetch available roles on mount
  useEffect(() => {
    if (token && user?.id) {
      const timeoutId = setTimeout(() => {
        fetchAvailableRoles();
      }, 100);
      return () => clearTimeout(timeoutId);
    }
  }, [token, user?.id, fetchAvailableRoles]);

  // Fetch available roles when modal opens
  useEffect(() => {
    if (showRoleSwitcher && token && user?.id) {
      fetchAvailableRoles();
    }
  }, [showRoleSwitcher, token, user?.id, fetchAvailableRoles]);

  // Task #498: platform-admin "preview as school principal" rows are minted
  // by /user-roles/my-roles (is_preview=true). The legacy /user-roles/switch
  // endpoint deliberately rejects this case (HTTP 403, see
  // backend/routes/user_roles_routes.py:218) — platform admins must go
  // through the hardened /role-switch/switch flow which requires a typed
  // reason, fresh MFA, and a server-side impersonation_sessions row.
  const isPlatformAdminPreview = useCallback((role) =>
    role?.is_preview === true
    && role?.role === 'school_principal'
    && user?.role === 'platform_admin',
  [user?.role]);

  // Task #525 / Task #528 — hide the Platform Admin's own "self" row
  // from the role-switch popup. The backend still returns it
  // (role='platform_admin', is_primary=true, and either is_current
  // when not previewing or just a stale self-row while impersonating)
  // but it isn't a valid switch target — restoring to the original
  // role is handled by the dedicated "العودة للدور الأصلي" button at
  // the bottom of the dialog and by the persistent PreviewModeBanner
  // in the app shell. Task #528 tightens the filter so the row is
  // dropped for any platform_admin viewer regardless of is_current /
  // is_impersonating state, so it never appears inline next to the
  // previewable schools.
  const displayableRoles = useMemo(() => {
    if (user?.role !== 'platform_admin' && !isImpersonating) return availableRoles;
    return (availableRoles || []).filter((role) => role?.role !== 'platform_admin');
  }, [availableRoles, user?.role, isImpersonating]);

  const _detailString = (error) => {
    const d = getApiErrorMessage(error);
    if (typeof d === 'string' && d.trim()) return d;
    return null;
  };

  const handleSwitchRole = useCallback(async (role) => {
    if (role.is_current) return;

    if (isImpersonating && role?.role === 'platform_admin') return;

    if (isPlatformAdminPreview(role)) {
      setPreviewReasonRole(role);
      return;
    }

    setSwitchingRole(true);
    try {
      const response = await api.post('/user-roles/switch', {
        target_role: role.role,
        target_tenant_id: role.tenant_id,
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
      const detail = _detailString(error);
      nassaqError(detail || t('errorSwitchingRole'));
    } finally {
      setSwitchingRole(false);
    }
  }, [api, isImpersonating, isPlatformAdminPreview, nassaqError, navigate, t, updateToken]);

  // Task #498: hardened impersonation flow for platform admins previewing
  // a specific school as its principal. Posts to /role-switch/switch with
  // the typed reason; the response shape is { token, role, school_id,
  // is_impersonating, original_role } — note `token`, NOT `access_token`.
  // The reason is owned by PreviewReasonDialog and arrives validated.
  // Task #543 — Delegate the impersonation network call + state population
  // to AuthContext.enterSchoolContext so the persistent PreviewModeBanner
  // (which reads `isImpersonating` + `schoolContext` from AuthContext)
  // appears immediately, identical to the "View Dashboard" path. The
  // sidebar only owns local UI concerns: spinner, dialog close, toast,
  // navigation.
  const handleConfirmPreviewSwitch = useCallback(async (reason) => {
    if (!previewReasonRole) return;
    setSwitchingRole(true);
    try {
      await enterSchoolContext(
        {
          id: previewReasonRole.tenant_id,
          name: previewReasonRole.tenant_name,
          name_en: previewReasonRole.tenant_name_en,
          code: previewReasonRole.tenant_code,
        },
        { reason },
      );

      toast.success(t('roleSwitchedSuccessfully'));
      setPreviewReasonRole(null);
      setShowRoleSwitcher(false);
      navigate('/principal');
    } catch (error) {
      console.error('Error switching role (hardened):', error);
      const detail = _detailString(error);
      nassaqError(detail || t('errorSwitchingRole'));
    } finally {
      setSwitchingRole(false);
    }
  }, [enterSchoolContext, nassaqError, navigate, previewReasonRole, t]);

  const handleCancelPreviewSwitch = useCallback(() => {
    if (switchingRole) return;
    setPreviewReasonRole(null);
  }, [switchingRole]);

  // Task #528 — Delegates the network/token swap to AuthContext so the
  // dialog button and the persistent PreviewModeBanner share a single
  // implementation. UI concerns (spinner, dialog close, toast, navigation)
  // still live here at the call site.
  const handleReturnToOriginal = useCallback(async () => {
    setSwitchingRole(true);
    try {
      const result = await returnToOriginalRole();
      if (result?.success) {
        toast.success(result.message || t('returnedToOriginalRole'));
        setShowRoleSwitcher(false);
        navigate(result.redirectTo);
      }
    } catch (error) {
      console.error('Error returning to original role:', error);
      nassaqError(t('errorReturningToOriginalRole'));
    } finally {
      setSwitchingRole(false);
    }
  }, [returnToOriginalRole, nassaqError, navigate, t]);

  const handleLogout = useCallback(() => {
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
      },
    );
  }, [api, logout, nassaqWarning, navigate, t]);

  // Handle exit from school context (impersonation mode)
  // Audit 2026-05-25 (H2): await exitSchoolContext so the server-side
  // /role-switch/restore JTI revocation completes before navigation.
  // eslint-disable-next-line no-unused-vars
  const handleExitSchoolContext = useCallback(async () => {
    try {
      await exitSchoolContext();
    } finally {
      navigate('/admin/tenants');
    }
  }, [exitSchoolContext, navigate]);

  const effectiveRole = getEffectiveRole ? getEffectiveRole() : user?.role;

  const menuItems = useMemo(() => {
    // Platform Admin Menu Items - مدير المنصة
    const platformAdminItems = [
      // Task #940 — platform_sub_admin (read-only deputy) sees the dashboard,
      // schools, and users read pages. All other platform items below stay
      // platform_admin-only (their backend endpoints 403 for the deputy).
      { icon: LayoutDashboard, label: t('controlDashboard'), href: '/admin', roles: ['platform_admin', 'platform_sub_admin'] },
      { icon: Building2, label: t('schoolsManagement'), href: '/admin/schools-table', roles: ['platform_admin', 'platform_sub_admin'] },
      { icon: Users, label: t('usersManagement'), href: '/admin/users', roles: ['platform_admin', 'platform_sub_admin'] },
      { icon: Activity, label: t('systemMonitoring'), href: '/admin/monitoring', roles: ['platform_admin'] },
      // AI Insights intentionally omitted for platform_admin: /principal/ai-insights
      // is a school-scoped page and a platform admin has no school context, so the
      // link only produced errors. Re-add a platform-wide AI page here if one is built.
      { icon: Link2, label: t('integrations'), href: '/admin/integrations', roles: ['platform_admin'] },
      { icon: Shield, label: t('securityCenter'), href: '/admin/security', roles: ['platform_admin'] },
      // Task #225 — IT §6.8 platform-admin hard-delete UI for archived workspaces.
      { icon: Trash2, label: t('workspacePurgeMenu'), href: '/admin/workspace-purge', roles: ['platform_admin'] },
      { icon: FileText, label: t('auditLogs'), href: '/admin/audit', roles: ['platform_admin', 'platform_security_officer', 'platform_data_analyst'] },
      { icon: MessageSquare, label: t('communicationNotifications'), href: '/admin/communication', roles: ['platform_admin'] },
      { icon: Lightbulb, label: t('productHub'), href: '/admin/product-hub', roles: ['platform_admin'] },
      // Task #173: first-class entry to the platform admin's personal settings page.
      { icon: UserCog, label: t('myAccount'), href: '/account/settings', roles: ['platform_admin'] },
    ];

    // School Principal & Sub Admin Menu Items
    const SCHOOL_ROLES = ['school_principal', 'school_admin', 'school_sub_admin'];
    const SCHOOL_PRINCIPAL_ROLES = ['school_principal', 'school_admin'];
    const schoolItems = [
      // Principal route audit 2026-07-28: every school-leadership sidebar
      // entry uses the canonical /principal namespace (the legacy /admin and
      // /school variants are redirect aliases in appRoutes.js).
      { icon: LayoutDashboard, label: t('commandCenter2'), href: '/principal', roles: SCHOOL_ROLES },
      { icon: Calendar, label: t('schoolSchedule'), href: '/principal/schedule', roles: SCHOOL_ROLES },
      { icon: Users, label: t('usersClasses'), href: '/principal/users-management', roles: SCHOOL_ROLES },
      { icon: CalendarCheck, label: t('staffAttendance'), href: '/principal/teacher-attendance', roles: SCHOOL_ROLES },
      // 5. Assessments & Grades Management — TEMPORARILY HIDDEN (module under maintenance).
      { icon: Settings, label: t('schoolSettings'), href: '/principal/settings', roles: SCHOOL_PRINCIPAL_ROLES },
      { icon: Bell, label: t('communicationCenter'), href: '/principal/communication', roles: SCHOOL_ROLES },
      { icon: Network, label: t('aiInsights'), href: '/principal/ai-insights', roles: SCHOOL_ROLES },
      { icon: UserCog, label: t('accountSettings'), href: '/account/settings', roles: SCHOOL_ROLES },
    ];

    // Teacher Menu Items — Task #79
    // Task #189 §5.2: shared items also visible to `independent_teacher`.
    const teacherItems = [
      { icon: Home, label: t('dashboard'), href: '/teacher', roles: ['teacher', 'independent_teacher'] },
      { icon: BookOpen, label: t('myClasses'), href: '/teacher/classes', roles: ['teacher', 'independent_teacher'], dataTour: 'sidebar-my-classes' },
      // IT workspace Parents directory lives as a tab beside Students
      // inside فصولي (TeacherClassesPage, ?tab=parents) — no sidebar entry,
      // mirroring how the IT subjects/students/import surfaces were moved.
      // 2026-05-19 — IT-only "الجدول والتقويم" Time Management Hub.
      { icon: CalendarDays, label: t('timeManagementHub'), href: '/teacher/planning', roles: ['independent_teacher'], dataTour: 'sidebar-time-management' },
      { icon: Award, label: t('myAchievements'), href: '/teacher/achievements', roles: ['teacher', 'independent_teacher'] },
      {
        icon: MessageSquare,
        label: t('communicationNotifications'),
        href: '/teacher/communication',
        roles: ['teacher', 'independent_teacher'],
        dataTour: 'sidebar-communication',
      },
      { icon: Network, label: t('aiInsights'), href: '/ai-insights', roles: ['teacher', 'independent_teacher'] },
      // 2026-05-18 — Unified "الملف الشخصي والإعدادات" entry → /account/settings hub.
      { icon: Settings, label: t('profileSettings'), href: '/account/settings', roles: ['teacher', 'independent_teacher'], dataTour: 'sidebar-account-settings' },
    ];

    // Parent Menu Items
    const parentItems = [
      { icon: Home, label: t('home'), href: '/parent', roles: ['parent'] },
      { icon: Users, label: t('studentProfile'), href: '/parent/children', roles: ['parent'] },
      { icon: MessageSquare, label: t('communicationCenter'), href: '/parent/communication', roles: ['parent'] },
      { icon: Settings, label: t('settings'), href: '/parent/settings', roles: ['parent'] },
    ];

    const allItems = [...platformAdminItems, ...schoolItems, ...teacherItems, ...parentItems];

    const filteredItems = allItems.filter((item) => {
      if (!item.roles.includes(effectiveRole)) return false;
      if (!item.permission) return true;
      // fail-closed while permissions are still loading
      return !!(perms && perms.has(item.permission));
    });

    // Remove duplicates by href
    const uniqueItems = filteredItems.reduce((acc, current) => {
      const exists = acc.find((item) => item.href === current.href);
      if (!exists) acc.push(current);
      return acc;
    }, []);

    return uniqueItems;
  }, [t, effectiveRole, perms]);

  const isActive = useCallback((href) => {
    // Support deep links like "/teacher/communication?tab=bulletin"
    const [hrefPath, hrefQuery] = href.split('?');
    if (location.pathname !== hrefPath) return false;
    if (!hrefQuery) return true;
    const current = new URLSearchParams(location.search);
    const target = new URLSearchParams(hrefQuery);
    for (const [k, v] of target.entries()) {
      if (current.get(k) !== v) return false;
    }
    return true;
  }, [location.pathname, location.search]);

  // Stable callbacks passed into SidebarContent
  const onToggleCollapsed = useCallback(() => setCollapsed((c) => !c), []);
  const onCloseMobile = useCallback(() => setMobileOpen(false), []);
  const onNavigate = useCallback((to) => navigate(to), [navigate]);
  const onToggleGroup = useCallback((href) => {
    setExpandedGroups((prev) => ({ ...prev, [href]: !prev[href] }));
  }, []);
  const onOpenRoleSwitcher = useCallback(() => setShowRoleSwitcher(true), []);

  return (
    <div className="min-h-screen flex">
      {/* Mobile Menu Button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setMobileOpen((v) => !v)}
        className="lg:hidden fixed top-3 start-3 z-[110] bg-brand-navy text-white shadow-lg rounded-xl h-10 w-10"
        data-testid="mobile-sidebar-toggle"
      >
        {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Mobile Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-[100]"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        dir={isRTL ? 'rtl' : 'ltr'}
        className={`
          fixed inset-y-0 z-[100] bg-brand-navy overflow-hidden
          transition-all duration-300 ease-in-out
          ${isRTL ? 'right-0' : 'left-0'}
          ${collapsed ? 'w-20' : 'w-72'}
          ${mobileOpen ? 'translate-x-0' : isRTL ? 'translate-x-full lg:translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        <div className="absolute inset-0 nassaq-pattern opacity-[0.03] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
        <SidebarContent
          isRTL={isRTL}
          t={t}
          user={user}
          effectiveRole={effectiveRole}
          collapsed={collapsed}
          onToggleCollapsed={onToggleCollapsed}
          onCloseMobile={onCloseMobile}
          onNavigate={onNavigate}
          locationPathname={location.pathname}
          menuItems={menuItems}
          isActive={isActive}
          expandedGroups={expandedGroups}
          onToggleGroup={onToggleGroup}
          availableRoles={availableRoles}
          onOpenRoleSwitcher={onOpenRoleSwitcher}
          isSwitchedRole={isSwitchedRole}
          isImpersonating={isImpersonating}
          schoolContext={schoolContext}
          originalRole={originalRole}
          onLogout={handleLogout}
          loggingOut={loggingOut}
        />
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
        {/* Task #528 — Persistent preview banner. Lives in the app shell
            so it stays visible across navigation while a Platform Admin
            is impersonating a school. Renders nothing when not in
            preview mode. */}
        <PreviewModeBanner />
        {children}
      </main>

      {/* Role Switcher Modal */}
      <RoleSwitcherDialog
        open={showRoleSwitcher}
        onOpenChange={setShowRoleSwitcher}
        loadingRoles={loadingRoles}
        availableRoles={displayableRoles}
        switchingRole={switchingRole}
        onSelectRole={handleSwitchRole}
        isSwitchedRole={isSwitchedRole}
        onReturnToOriginal={handleReturnToOriginal}
      />

      {/* Task #498 — Reason dialog for platform-admin → school-principal preview.
          Owns its own draft/error state internally; emits only the validated
          reason on confirm. This is the structural fix for Task #519 — typing
          here no longer re-renders any unrelated sidebar region. */}
      <PreviewReasonDialog
        role={previewReasonRole}
        submitting={switchingRole}
        onConfirm={handleConfirmPreviewSwitch}
        onCancel={handleCancelPreviewSwitch}
      />
    </div>
  );
};
