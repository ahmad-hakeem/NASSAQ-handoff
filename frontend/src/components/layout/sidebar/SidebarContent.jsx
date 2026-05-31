import { Link } from 'react-router-dom';
import {
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ArrowLeftRight,
  Settings,
  Search,
  Shield,
  RefreshCw,
  LogOut,
} from 'lucide-react';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { BetaBadge } from '../../BetaDisclaimer';
import CommandPalette from '../../teacher/CommandPalette';

const LOGO_WHITE = '/nassaq-logo-white.png';

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

const getRoleLabel = (role, isRTL) => {
  if (!isRTL) return role?.replace('_', ' ');
  if (role === 'platform_admin' || role === 'platform_operations_manager') return 'مدير المنصة';
  if (role === 'school_principal' || role === 'school_admin') return 'مدير المدرسة';
  if (role === 'school_sub_admin') return 'مساعد المدير';
  if (role === 'teacher') return 'معلم';
  if (role === 'independent_teacher') return 'معلم مستقل';
  if (role === 'parent') return 'ولي أمر';
  if (role === 'student') return 'طالب';
  return role;
};

export default function SidebarContent({
  isRTL,
  t,
  user,
  effectiveRole,
  collapsed,
  onToggleCollapsed,
  onCloseMobile,
  onNavigate,
  locationPathname,
  menuItems,
  isActive,
  expandedGroups,
  onToggleGroup,
  unreadInbox,
  availableRoles,
  onOpenRoleSwitcher,
  isSwitchedRole,
  isImpersonating,
  schoolContext,
  originalRole,
  onLogout,
  loggingOut,
}) {
  return (
    <div className="flex flex-col h-full">
      <CommandPalette />

      {/* ── Top area ── */}
      {collapsed ? (
        /* Collapsed: clean vertical stack, everything centered */
        <div className="flex flex-col items-center gap-1 py-3 px-2">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center justify-center w-11 h-11 rounded-xl hover:bg-white/10 transition-colors flex-shrink-0"
          >
            <img src={LOGO_WHITE} alt="نَسَّق" className="h-8 w-8 rounded-lg object-contain" />
          </Link>

          {/* Expand toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapsed}
            className="text-white/70 hover:text-white hover:bg-white/10 hidden lg:flex w-11 h-11"
            data-testid="sidebar-collapse-btn"
            title={t('expandSidebar') || 'توسيع الشريط الجانبي'}
          >
            {isRTL ? <ChevronLeft className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
          </Button>

          {/* Settings — platform_admin only */}
          {user?.role === 'platform_admin' && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => { onNavigate('/settings'); onCloseMobile(); }}
              className={`text-white/70 hover:text-white hover:bg-white/10 w-11 h-11 ${
                locationPathname === '/settings' ? 'bg-white/15 text-white' : ''
              }`}
              data-testid="sidebar-settings-btn"
              title={t('systemSettings')}
            >
              <Settings className="h-5 w-5" />
            </Button>
          )}

          {/* Role switcher */}
          {availableRoles.length > 1 && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onOpenRoleSwitcher}
              className="text-white/70 hover:text-white hover:bg-white/10 w-11 h-11"
              data-testid="sidebar-role-switch-btn"
              title={t('switchRole')}
            >
              <ArrowLeftRight className="h-5 w-5" />
            </Button>
          )}

          {/* Command palette — independent_teacher only */}
          {effectiveRole === 'independent_teacher' && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => window.dispatchEvent(new CustomEvent('nassaq:open-command-palette'))}
              className="text-white/70 hover:text-white hover:bg-white/10 w-11 h-11"
              data-testid="sidebar-cmdk-btn"
              title={t('cmdkOpen')}
            >
              <Search className="h-5 w-5" />
            </Button>
          )}
        </div>
      ) : (
        /* Expanded: logo row + inline controls */
        <div className="p-4">
          <div className="flex items-center justify-between w-full">
            <Link to="/" className="flex items-center gap-2">
              <img src={LOGO_WHITE} alt="نَسَّق" className="h-10 w-auto rounded-xl" />
              <BetaBadge />
            </Link>

            <div className="flex items-center gap-1">
              {effectiveRole === 'independent_teacher' && (
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
                  onClick={onOpenRoleSwitcher}
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
                  onClick={() => { onNavigate('/settings'); onCloseMobile(); }}
                  className={`text-white/70 hover:text-white hover:bg-white/10 ${
                    locationPathname === '/settings' ? 'bg-white/15 text-white' : ''
                  }`}
                  data-testid="sidebar-settings-btn"
                  title={t('systemSettings')}
                >
                  <Settings className="h-5 w-5" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleCollapsed}
                className="text-white/70 hover:text-white hover:bg-white/10 hidden lg:flex"
                data-testid="sidebar-collapse-btn"
              >
                {isRTL ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Menu Items */}
      <div
        className={`flex-1 overflow-y-auto px-2 sidebar-scrollbar${collapsed ? ' collapsed' : ''}`}
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        <nav className={`space-y-1 py-2${collapsed ? '' : ' px-1'}`} dir={isRTL ? 'rtl' : 'ltr'}>
          {menuItems.map((item) => {
            const hasSubItems = item.subItems && item.subItems.length > 0;
            const isGroupExpanded = expandedGroups[item.href];
            const isAnySubActive = hasSubItems && item.subItems.some((sub) => isActive(sub.href));

            if (hasSubItems && !collapsed) {
              return (
                <div key={item.href}>
                  <button
                    onClick={() => onToggleGroup(item.href)}
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
                      {item.subItems.map((sub) => (
                        <Link
                          key={sub.href}
                          to={sub.href}
                          onClick={onCloseMobile}
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
                onClick={onCloseMobile}
                data-testid={`sidebar-link-${item.href.replace(/\//g, '-')}`}
                data-tour={item.dataTour}
                className={`sidebar-item relative ${collapsed ? 'justify-center px-0 py-3' : ''} ${
                  isActive(item.href) ? 'sidebar-item-active' : 'sidebar-item-inactive'
                }`}
                title={collapsed ? item.label : undefined}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
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
      </div>

      {/* User Info & Logout */}
      {!collapsed && user && (
        <div className="p-4 border-t border-white/10">
          {isSwitchedRole && (
            <div className="mb-3 p-2 rounded-lg bg-brand-turquoise/20 border border-brand-turquoise/30">
              <div className="flex items-center gap-2 text-brand-turquoise text-xs">
                <ArrowLeftRight className="h-3 w-3" />
                <span className="font-medium">{t('switchedRole')}</span>
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
                <span className="font-medium">{t('previewMode')}</span>
              </div>
              <p className="text-[10px] text-amber-100/80 truncate mt-1">
                {schoolContext.school_name}
              </p>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => { onNavigate('/account/settings'); onCloseMobile(); }}
              className="flex items-center gap-3 flex-1 min-w-0 text-start rounded-xl p-1 -m-1 hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-brand-turquoise/60 transition-colors"
              title={t('accountSettings')}
              aria-label={t('accountSettings')}
              data-testid="sidebar-footer-account"
            >
              <div className="w-10 h-10 rounded-xl bg-brand-turquoise flex items-center justify-center overflow-hidden flex-shrink-0">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.full_name} className="w-full h-full object-cover" />
                ) : (
                  <span className="text-white font-semibold">{user.full_name?.charAt(0)}</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{user.full_name}</p>
                  {effectiveRole === 'independent_teacher' && (
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
                  {getRoleLabel(effectiveRole, isRTL)}
                </p>
              </div>
            </button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onLogout}
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
        <div className="py-3 px-2 border-t border-white/10 flex flex-col items-center gap-1">
          {isSwitchedRole && (
            <div className="w-2 h-2 rounded-full bg-brand-turquoise animate-pulse mb-1" title={t('switchedRole')} />
          )}
          <button
            type="button"
            onClick={() => { onNavigate('/account/settings'); onCloseMobile(); }}
            className="w-11 h-11 flex items-center justify-center rounded-xl hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-brand-turquoise/60 transition-colors"
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
            onClick={onLogout}
            disabled={loggingOut}
            className="w-11 h-11 text-red-300/70 hover:text-red-200 hover:bg-red-500/20 rounded-xl"
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
    </div>
  );
}
