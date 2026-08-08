/**
 * Portal Layout Component
 * تخطيط مخصص لبوابة الطالب وولي الأمر
 *
 * Parent (`portalType="parent"`) renders inside the shared right-side
 * `<Sidebar>` shell used by Admin and Teacher portals — no clone, no
 * second navigation system. Only a thin top utility bar (notifications,
 * theme/lang) is added on top of page content.
 *
 * Student (`portalType="student"`) keeps its existing horizontal+bottom-nav
 * shell (out of scope for this migration).
 */

import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Button } from '@/shared/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/shared/components/ui/avatar';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import ShellStudentSwitcher from '@/features/parent-portal/components/parent/ShellStudentSwitcher';
import {
  Home,
  Calendar,
  BookOpen,
  CheckCircle,
  Bell,
  User,
  LogOut,
  Settings,
  Menu,
  X,
  BarChart3,
  Trophy,
  Sun,
  Moon,
  Globe,
} from 'lucide-react';

const LOGO_WHITE = '/nassaq-logo-white.png';

/* -------------------------------------------------------------------------- */
/*  Parent shell — shared right-side Sidebar + thin top utility bar           */
/* -------------------------------------------------------------------------- */
const ParentShell = ({ children }) => {
  const { t } = useTranslation();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { user } = useAuth();

  return (
    <Sidebar>
      <div className="parent-portal-typography min-h-screen" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Thin sticky top utility bar — no navigation links, just controls.
            All navigation lives in the shared right-side Sidebar. */}
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur border-b border-border/50">
          <div className="flex items-center justify-between gap-3 px-4 sm:px-6 py-2.5">
            <div className="flex items-center gap-2 min-w-0">
              <Avatar className="h-8 w-8 ring-2 ring-brand-turquoise/20">
                <AvatarImage src={user?.avatar_url} />
                <AvatarFallback className="bg-brand-turquoise/15 text-brand-turquoise text-sm font-semibold">
                  {user?.full_name?.charAt(0) || 'و'}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 hidden sm:block">
                <p className="text-sm font-semibold font-cairo truncate text-foreground">
                  {user?.full_name}
                </p>
                <p className="text-[11px] text-muted-foreground font-tajawal truncate">
                  {isRTL ? 'ولي أمر' : 'Parent'}
                </p>
              </div>
            </div>

            {/* Task #146 — global active-student switcher, mounted once for
                the whole parent shell so every page reads the same context. */}
            <div className="flex-1 min-w-0 flex justify-center">
              <ShellStudentSwitcher />
            </div>

            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} title={isRTL ? 'English' : 'العربية'}>
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme}>
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="pb-6">
          {children}
        </main>
      </div>
    </Sidebar>
  );
};

/* -------------------------------------------------------------------------- */
/*  Student shell — preserved unchanged from prior implementation             */
/* -------------------------------------------------------------------------- */
const StudentShell = ({ children, hideHeaderNotifications }) => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqWarning } = useNassaqAlert();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const primaryColor = 'emerald';
  const gradientFrom = 'from-emerald-600';
  const gradientTo = 'to-teal-500';

  const handleLogout = () => {
    nassaqWarning(
      t('areYouSureYouWantToLogOut'),
      {
        title: t('confirmLogout'),
        confirmText: t('logout'),
        cancelText: t('cancel'),
        showCancel: true,
        onConfirm: () => {
          logout();
          navigate('/login');
        },
      }
    );
  };

  const menuItems = [
    { icon: Home, label: t('home'), href: '/student' },
    { icon: Calendar, label: t('schedule'), href: '/student/schedule' },
    { icon: BookOpen, label: t('grades'), href: '/student/grades' },
    { icon: CheckCircle, label: t('attendance2'), href: '/student/attendance' },
    { icon: User, label: t('profile2'), href: '/student/profile' },
    { icon: BarChart3, label: t('progress'), href: '/student/progress' },
    { icon: Trophy, label: isRTL ? 'إنجازاتي' : 'Achievements', href: '/student/achievements' },
    { icon: Bell, label: t('notifications'), href: '/notifications' },
  ];

  const isActive = (href) => {
    if (href === '/student') return location.pathname === href;
    return location.pathname.startsWith(href);
  };

  return (
    <div className="min-h-screen bg-gray-50" dir={isRTL ? 'rtl' : 'ltr'}>
      <header className={`bg-gradient-to-r ${gradientFrom} ${gradientTo} text-white sticky top-0 z-50`}>
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="text-white hover:bg-white/10 lg:hidden"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                data-testid="mobile-menu-toggle"
              >
                {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </Button>
              <Link to="/" className="flex items-center gap-2">
                <img src={LOGO_WHITE} alt="نَسَّق" className="h-8 w-auto rounded-lg" />
              </Link>
            </div>

            <div className="flex items-center gap-3">
              {!hideHeaderNotifications && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/10 relative"
                  data-testid="notifications-btn"
                >
                  <Bell className="h-5 w-5" />
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] flex items-center justify-center">3</span>
                </Button>
              )}

              <div className="flex items-center gap-2">
                <Avatar className="h-8 w-8 border-2 border-white/30">
                  <AvatarImage src={user?.avatar_url} />
                  <AvatarFallback className="bg-white/20 text-white text-sm">
                    {user?.full_name?.charAt(0) || 'ط'}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden sm:block text-sm font-medium truncate max-w-[120px]">
                  {user?.full_name}
                </span>
              </div>
            </div>
          </div>
        </div>

        <nav className="hidden lg:block border-t border-white/10">
          <div className="px-4">
            <div className="flex items-center gap-1">
              {menuItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-all border-b-2 ${
                    isActive(item.href)
                      ? 'border-white text-white'
                      : 'border-transparent text-white/70 hover:text-white hover:border-white/50'
                  }`}
                  data-testid={`nav-${item.href.split('/').pop()}`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-4 py-3 text-sm font-medium text-white/70 hover:text-white transition-all ms-auto"
                data-testid="logout-btn"
              >
                <LogOut className="h-4 w-4" />
                {t('logout2')}
              </button>
            </div>
          </div>
        </nav>
      </header>

      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setMobileMenuOpen(false)}>
          <div
            className={`absolute top-0 ${isRTL ? 'right-0' : 'left-0'} w-72 h-full bg-white shadow-xl`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`p-4 bg-gradient-to-r ${gradientFrom} ${gradientTo} text-white`}>
              <div className="flex items-center gap-3 mb-4">
                <Avatar className="h-12 w-12 border-2 border-white/30">
                  <AvatarFallback className="bg-white/20 text-white">
                    {user?.full_name?.charAt(0) || 'ط'}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-bold">{user?.full_name}</p>
                  <p className="text-sm text-white/70">{t('student')}</p>
                </div>
              </div>
            </div>

            <nav className="p-2">
              {menuItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    isActive(item.href)
                      ? 'bg-emerald-50 text-emerald-600'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  {item.label}
                </Link>
              ))}
              <Link
                to="/account/settings"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50 mt-4 border-t pt-4"
              >
                <Settings className="h-5 w-5" />
                {t('settings')}
              </Link>
              <button
                onClick={handleLogout}
                className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 w-full"
              >
                <LogOut className="h-5 w-5" />
                {t('logout')}
              </button>
            </nav>
          </div>
        </div>
      )}

      <main className="pb-24 lg:pb-6">{children}</main>

      <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-slate-900 border-t border-gray-200 dark:border-slate-700 shadow-[0_-4px_16px_rgba(0,0,0,0.08)] z-50 pb-safe">
        <div className="flex items-center justify-around py-1.5">
          {menuItems.slice(0, 5).map((item) => {
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex flex-col items-center gap-0.5 py-1.5 px-2 min-w-[56px] rounded-xl transition-all duration-200 ${
                  active
                    ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30'
                    : 'text-gray-400 dark:text-gray-500 active:bg-gray-100 dark:active:bg-slate-800'
                }`}
                data-testid={`bottom-nav-${item.href.split('/').pop()}`}
              >
                <item.icon className={`h-5 w-5 ${active ? 'scale-110' : ''} transition-transform`} />
                <span className={`text-[10px] font-medium ${active ? 'font-bold' : ''}`}>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
};

export const PortalLayout = ({ children, portalType = 'student', hideHeaderNotifications = false }) => {
  if (portalType === 'parent') {
    return <ParentShell>{children}</ParentShell>;
  }
  return <StudentShell hideHeaderNotifications={hideHeaderNotifications}>{children}</StudentShell>;
};

export default PortalLayout;
