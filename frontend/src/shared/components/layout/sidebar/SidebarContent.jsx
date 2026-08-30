import { useRef, useEffect, useCallback } from 'react';
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
  Globe,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { BetaBadge } from '@/shared/components/BetaDisclaimer';
import CommandPalette from '@/features/teachers/components/teacher/CommandPalette';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { NotificationBell } from '@/features/communication/components/notifications/NotificationBell';

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
  availableRoles,
  onOpenRoleSwitcher,
  isSwitchedRole,
  isImpersonating,
  schoolContext,
  originalRole,
  onLogout,
  loggingOut,
}) {
  const { toggleLanguage } = useTheme();

  const scrollRef = useRef(null);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.classList.add('is-scrolling');
    clearTimeout(el._scrollHideTimer);
    el._scrollHideTimer = setTimeout(() => {
      el.classList.remove('is-scrolling');
    }, 800);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      el.removeEventListener('scroll', handleScroll);
      clearTimeout(el._scrollHideTimer);
    };
  }, [handleScroll]);

  return (
    <div className="flex flex-col h-full font-cairo select-none">
      <CommandPalette effectiveRole={effectiveRole} menuItems={menuItems} />

      {/* ── Top Area (Logo & Controls) ── */}
      {collapsed ? (
        /* Collapsed: clean vertical stack, everything centered */
        <div className="flex flex-col items-center gap-2 py-5 px-2">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center justify-center w-12 h-12 rounded-2xl bg-white/15 hover:bg-white/25 transition-all shadow-md flex-shrink-0 border border-white/20"
          >
            <img src={LOGO_WHITE} alt="نَسَّق" className="h-7 w-7 rounded-lg object-contain" />
          </Link>

          {/* Expand toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapsed}
            className="text-white/80 hover:text-white hover:bg-white/15 hidden lg:flex w-11 h-11 rounded-xl transition-all"
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
              className={`text-white/80 hover:text-white hover:bg-white/15 w-11 h-11 rounded-xl transition-all ${
                locationPathname === '/settings' ? 'bg-white/20 text-[#5DD8D5] border-s-2 border-[#5DD8D5]' : ''
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
              className="text-white/80 hover:text-white hover:bg-white/15 w-11 h-11 rounded-xl transition-all"
              data-testid="sidebar-role-switch-btn"
              title={t('switchRole')}
            >
              <ArrowLeftRight className="h-5 w-5" />
            </Button>
          )}

          {/* Command palette — all roles */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => window.dispatchEvent(new CustomEvent('nassaq:open-command-palette'))}
            className="text-white/80 hover:text-white hover:bg-white/15 w-11 h-11 rounded-xl transition-all"
            data-testid="sidebar-cmdk-btn"
            title={t('cmdkOpen')}
          >
            <Search className="h-5 w-5" />
          </Button>
        </div>
      ) : (
        /* Expanded: Logo row + inline controls */
        <div className="px-4 pt-4 pb-3 border-b border-white/[0.10]">
          <div className="flex items-center justify-between w-full">
            <Link to="/" className="flex items-center gap-3 group">
              <div className="p-2 rounded-2xl bg-white/15 group-hover:bg-white/25 transition-all backdrop-blur-md border border-white/20 shadow-md">
                <img src={LOGO_WHITE} alt="نَسَّق" className="h-8 w-auto rounded-lg" />
              </div>
              <BetaBadge />
            </Link>

            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => window.dispatchEvent(new CustomEvent('nassaq:open-command-palette'))}
                className="text-white/80 hover:text-white hover:bg-white/15 rounded-xl h-9 w-9 transition-all"
                data-testid="sidebar-cmdk-btn"
                title={t('cmdkOpen')}
              >
                <Search className="h-4 w-4" />
              </Button>
              {availableRoles.length > 1 && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onOpenRoleSwitcher}
                  className="text-white/80 hover:text-white hover:bg-white/15 rounded-xl h-9 w-9 transition-all"
                  data-testid="sidebar-role-switch-btn"
                  title={t('switchRole')}
                >
                  <ArrowLeftRight className="h-4 w-4" />
                </Button>
              )}
              {user?.role === 'platform_admin' && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => { onNavigate('/settings'); onCloseMobile(); }}
                  className={`text-white/80 hover:text-white hover:bg-white/15 rounded-xl h-9 w-9 transition-all ${
                    locationPathname === '/settings' ? 'bg-white/20 text-[#5DD8D5]' : ''
                  }`}
                  data-testid="sidebar-settings-btn"
                  title={t('systemSettings')}
                >
                  <Settings className="h-4 w-4" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleCollapsed}
                className="text-white/80 hover:text-white hover:bg-white/15 hidden lg:flex rounded-xl h-9 w-9 transition-all"
                data-testid="sidebar-collapse-btn"
              >
                {isRTL ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Navigation Menu Items ── */}
      <div
        ref={scrollRef}
        className={`flex-1 overflow-y-auto py-3 sidebar-scrollbar${collapsed ? ' collapsed px-2' : ' px-3'}`}
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        <nav className="space-y-0.5" dir={isRTL ? 'rtl' : 'ltr'}>
          {menuItems.map((item, index) => {
            const hasSubItems = item.subItems && item.subItems.length > 0;
            const isGroupExpanded = expandedGroups[item.href];
            const isAnySubActive = hasSubItems && item.subItems.some((sub) => isActive(sub.href));
            const active = isActive(item.href);

            if (hasSubItems && !collapsed) {
              return (
                <div key={item.href} className="space-y-0.5">
                  <button
                    onClick={() => onToggleGroup(item.href)}
                    data-testid={`sidebar-link-${item.href.replace(/\//g, '-')}`}
                    className={`
                      w-full cursor-pointer group flex items-center gap-3 px-3 py-2.5 rounded-xl
                      text-xs font-semibold transition-all duration-200
                      ${isAnySubActive
                        ? 'bg-white/20 text-white shadow-sm ring-1 ring-white/25 border-s-[3px] border-[#5DD8D5]'
                        : 'text-white/90 hover:bg-white/10 hover:text-white'
                      }
                    `}
                  >
                    {/* Icon container */}
                    <span className={`
                      flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0 transition-all
                      ${isAnySubActive
                        ? 'bg-[#5DD8D5]/20 text-[#5DD8D5]'
                        : 'bg-white/10 text-white/80 group-hover:bg-white/15 group-hover:text-white'
                      }
                    `}>
                      <item.icon className="h-4 w-4" />
                    </span>
                    <span className="flex-1 text-start font-bold tracking-wide truncate">{item.label}</span>
                    <ChevronDown className={`h-3.5 w-3.5 flex-shrink-0 transition-transform duration-200 ${
                      isGroupExpanded ? 'rotate-180 text-[#5DD8D5]' : 'text-white/50 group-hover:text-white/80'
                    }`} />
                  </button>

                  {isGroupExpanded && (
                    <div className={`mt-1 space-y-0.5 ${isRTL ? 'pr-4 border-r-2 border-[#5DD8D5]/30' : 'pl-4 border-l-2 border-[#5DD8D5]/30'} ms-2`}>
                      {item.subItems.map((sub) => (
                        <Link
                          key={sub.href}
                          to={sub.href}
                          onClick={onCloseMobile}
                          className={`
                            flex items-center gap-2 py-2 px-3 rounded-lg text-xs transition-all duration-150
                            ${isActive(sub.href)
                              ? 'text-[#5DD8D5] bg-white/15 font-bold'
                              : 'text-white/80 hover:text-white hover:bg-white/10 font-medium'
                            }
                          `}
                        >
                          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${isActive(sub.href) ? 'bg-[#5DD8D5]' : 'bg-white/40'}`} />
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
                title={collapsed ? item.label : undefined}
                className={`
                  group flex items-center transition-all duration-200 rounded-xl
                  ${collapsed
                    ? 'justify-center p-2.5'
                    : 'gap-3 px-3 py-2.5'
                  }
                  ${active
                    ? 'bg-white/20 text-white shadow-sm ring-1 ring-white/25 border-s-[3px] border-[#5DD8D5]'
                    : 'text-white/90 hover:bg-white/10 hover:text-white'
                  }
                `}
              >
                {/* Icon container */}
                <span className={`
                  flex items-center justify-center rounded-lg flex-shrink-0 transition-all
                  ${collapsed ? 'w-9 h-9' : 'w-8 h-8'}
                  ${active
                    ? 'bg-[#5DD8D5]/20 text-[#5DD8D5]'
                    : 'bg-white/10 text-white/80 group-hover:bg-white/15 group-hover:text-[#5DD8D5]'
                  }
                `}>
                  <item.icon className={collapsed ? 'h-4.5 w-4.5' : 'h-4 w-4'} />
                </span>

                {!collapsed && (
                  <span className="flex-1 truncate text-xs font-semibold tracking-wide">
                    {item.label}
                  </span>
                )}

                {/* Active dot indicator for non-collapsed */}
                {!collapsed && active && (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#5DD8D5] flex-shrink-0 shadow-sm shadow-[#5DD8D5]/50" />
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* ── User Footer & Profile Card ── */}
      {!collapsed && user && (
        <div className="p-3 border-t border-white/[0.10]">
          {isSwitchedRole && (
            <div className="mb-2.5 p-2 rounded-xl bg-[#5DD8D5]/15 border border-[#5DD8D5]/30">
              <div className="flex items-center gap-2 text-[#5DD8D5] text-xs font-bold">
                <ArrowLeftRight className="h-3.5 w-3.5" />
                <span>{t('switchedRole')}</span>
              </div>
              <p className="text-[10px] text-white/80 mt-0.5">
                {isRTL ? `الدور الأصلي: ${getRoleNameAr(originalRole)}` : `Original: ${originalRole?.replace(/_/g, ' ')}`}
              </p>
            </div>
          )}
          {isImpersonating && schoolContext && !isSwitchedRole && (
            <div className="mb-2.5 p-2 rounded-xl bg-amber-500/20 border border-amber-500/40">
              <div className="flex items-center gap-2 text-amber-300 text-xs font-bold">
                <Shield className="h-3.5 w-3.5" />
                <span>{t('previewMode')}</span>
              </div>
              <p className="text-[10px] text-amber-100 truncate mt-0.5 font-medium">
                {schoolContext.school_name}
              </p>
            </div>
          )}

          {/* Identity + Actions Card */}
          <div className="flex items-center gap-2 p-2 rounded-2xl bg-white/[0.08] border border-white/15 hover:border-white/25 transition-all">
            <button
              type="button"
              onClick={() => { onNavigate('/account/settings'); onCloseMobile(); }}
              className="flex items-center gap-2.5 flex-1 min-w-0 text-start rounded-xl p-0.5 hover:bg-white/10 focus:outline-none transition-all"
              title={t('accountSettings')}
              aria-label={t('accountSettings')}
              data-testid="sidebar-footer-account"
            >
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#5DD8D5] to-[#615090] ring-2 ring-white/25 flex items-center justify-center overflow-hidden flex-shrink-0 shadow-md">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.full_name} className="w-full h-full object-cover" />
                ) : (
                  <span className="text-white font-black text-sm">{user.full_name?.charAt(0)}</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-white truncate leading-tight">{user.full_name}</p>
                <p className="text-[10px] font-semibold text-[#5DD8D5] truncate leading-tight mt-0.5">
                  {getRoleLabel(effectiveRole, isRTL)}
                </p>
              </div>
            </button>

            <div className="flex items-center flex-shrink-0 gap-0.5">
              <NotificationBell
                triggerClassName="h-8 w-8 text-white/80 hover:text-white hover:bg-white/15 rounded-xl transition-all"
              />
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleLanguage}
                className="h-8 w-8 text-white/80 hover:text-white hover:bg-white/15 rounded-xl transition-all"
                data-testid="sidebar-language-toggle"
                title={isRTL ? 'English' : 'العربية'}
                aria-label={isRTL ? 'Switch to English' : 'التبديل إلى العربية'}
              >
                <Globe className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={onLogout}
                disabled={loggingOut}
                className="h-8 w-8 text-rose-300/90 hover:text-white hover:bg-rose-500/70 rounded-xl transition-all"
                data-testid="logout-btn"
                title={t('logout')}
                aria-label={t('logout')}
              >
                {loggingOut ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <LogOut className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Collapsed Footer ── */}
      {collapsed && user && (
        <div className="py-3 px-2 border-t border-white/[0.10] flex flex-col items-center gap-1.5">
          {isSwitchedRole && (
            <div className="w-2 h-2 rounded-full bg-[#5DD8D5] animate-pulse mb-1" title={t('switchedRole')} />
          )}
          <button
            type="button"
            onClick={() => { onNavigate('/account/settings'); onCloseMobile(); }}
            className="w-11 h-11 flex items-center justify-center rounded-2xl hover:bg-white/15 focus:outline-none transition-all"
            title={t('accountSettings')}
            aria-label={t('accountSettings')}
            data-testid="sidebar-footer-account-collapsed"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#5DD8D5] to-[#615090] flex items-center justify-center overflow-hidden shadow-md ring-2 ring-white/25">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.full_name} className="w-full h-full object-cover" />
              ) : (
                <span className="text-white text-xs font-black">{user.full_name?.charAt(0)}</span>
              )}
            </div>
          </button>
          <NotificationBell
            triggerClassName="w-11 h-11 text-white/80 hover:text-white hover:bg-white/15 rounded-xl transition-all"
          />
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleLanguage}
            className="w-11 h-11 text-white/80 hover:text-white hover:bg-white/15 rounded-xl transition-all"
            data-testid="sidebar-language-toggle-collapsed"
            title={isRTL ? 'English' : 'العربية'}
            aria-label={isRTL ? 'Switch to English' : 'التبديل إلى العربية'}
          >
            <Globe className="h-5 w-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onLogout}
            disabled={loggingOut}
            className="w-11 h-11 text-rose-300/90 hover:text-white hover:bg-rose-500/70 rounded-xl transition-all"
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
