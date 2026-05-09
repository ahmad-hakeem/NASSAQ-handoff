/**
 * Portal Layout Component
 * تخطيط مخصص لبوابة الطالب وولي الأمر
 */

import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '../ui/avatar';
import {
  Home,
  Calendar,
  BookOpen,
  CheckCircle,
  Bell,
  User,
  LogOut,
  Users,
  MessageSquare,
  Settings,
  Menu,
  X,
  GraduationCap,
  BarChart3,
  Trophy,
  FileText,
  CalendarCheck,
} from 'lucide-react';

const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';

export const PortalLayout = ({ children, portalType = 'student', hideHeaderNotifications = false }) => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqWarning } = useNassaqAlert();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isStudent = portalType === 'student';
  const primaryColor = isStudent ? 'emerald' : 'brand-navy';
  const gradientFrom = isStudent ? 'from-emerald-600' : 'from-brand-navy';
  const gradientTo = isStudent ? 'to-teal-500' : 'to-brand-purple';

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

  const studentMenuItems = [
    { icon: Home, label: t('home'), href: '/student' },
    { icon: Calendar, label: t('schedule'), href: '/student/schedule' },
    { icon: BookOpen, label: t('grades'), href: '/student/grades' },
    { icon: CheckCircle, label: t('attendance2'), href: '/student/attendance' },
    { icon: User, label: t('profile2'), href: '/student/profile' },
    { icon: BarChart3, label: t('progress'), href: '/student/progress' },
    { icon: Trophy, label: isRTL ? 'إنجازاتي' : 'Achievements', href: '/student/achievements' },
    { icon: Bell, label: t('notifications'), href: '/notifications' },
  ];

  const parentMenuItems = [
    { icon: Home, label: t('home'), href: '/parent' },
    { icon: Users, label: t('myChildren'), href: '/parent/children' },
    { icon: MessageSquare, label: t('communicationCenter'), href: '/parent/communication' },
    { icon: FileText, label: t('absenceExcuse'), href: '/parent/absence-excuse' },
    { icon: CalendarCheck, label: t('meetingRequest'), href: '/parent/meeting-request' },
    { icon: BarChart3, label: t('reports'), href: '/parent/reports' },
    { icon: Bell, label: t('notifications'), href: '/notifications' },
    { icon: Settings, label: t('settings'), href: '/parent/settings' },
  ];

  const menuItems = isStudent ? studentMenuItems : parentMenuItems;

  const isActive = (href) => {
    if (href === '/student' || href === '/parent') {
      return location.pathname === href;
    }
    return location.pathname.startsWith(href);
  };

  return (
    <div
      className={`min-h-screen bg-gray-50 ${
        portalType === 'parent' ? 'parent-portal-typography' : ''
      }`}
      dir={isRTL ? 'rtl' : 'ltr'}
    >
      {/* Top Header */}
      <header className={`bg-gradient-to-r ${gradientFrom} ${gradientTo} text-white sticky top-0 z-50`}>
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            {/* Logo & Menu Toggle */}
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

            {/* User Info */}
            <div className="flex items-center gap-3">
              {!hideHeaderNotifications && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/10 relative"
                  data-testid="notifications-btn"
                >
                  <Bell className="h-5 w-5" />
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] flex items-center justify-center">
                    3
                  </span>
                </Button>
              )}

              <div className="flex items-center gap-2">
                <Avatar className="h-8 w-8 border-2 border-white/30">
                  <AvatarImage src={user?.avatar_url} />
                  <AvatarFallback className="bg-white/20 text-white text-sm">
                    {user?.full_name?.charAt(0) || (isStudent ? 'ط' : 'و')}
                  </AvatarFallback>
                </Avatar>
                <span className="hidden sm:block text-sm font-medium truncate max-w-[120px]">
                  {user?.full_name}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Desktop Navigation */}
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
              
              {/* Logout */}
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

      {/* Mobile Navigation Overlay */}
      {mobileMenuOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setMobileMenuOpen(false)}>
          <div
            className={`absolute top-0 ${isRTL ? 'right-0' : 'left-0'} w-72 h-full bg-white shadow-xl`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Mobile Menu Header */}
            <div className={`p-4 bg-gradient-to-r ${gradientFrom} ${gradientTo} text-white`}>
              <div className="flex items-center gap-3 mb-4">
                <Avatar className="h-12 w-12 border-2 border-white/30">
                  <AvatarFallback className="bg-white/20 text-white">
                    {user?.full_name?.charAt(0) || (isStudent ? 'ط' : 'و')}
                  </AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-bold">{user?.full_name}</p>
                  <p className="text-sm text-white/70">
                    {isStudent ? (t('student')) : (isRTL ? 'ولي أمر' : 'Parent')}
                  </p>
                </div>
              </div>
            </div>

            {/* Mobile Menu Items */}
            <nav className="p-2">
              {menuItems.map((item) => (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                    isActive(item.href)
                      ? isStudent ? 'bg-emerald-50 text-emerald-600' : 'bg-brand-navy/5 text-brand-navy'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="h-5 w-5" />
                  {item.label}
                </Link>
              ))}
              
              {/* Settings */}
              <Link
                to="/account/settings"
                onClick={() => setMobileMenuOpen(false)}
                className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-50 mt-4 border-t pt-4"
              >
                <Settings className="h-5 w-5" />
                {t('settings')}
              </Link>
              
              {/* Logout */}
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

      {/* Main Content */}
      <main className="pb-24 lg:pb-6">
        {children}
      </main>

      {/* Mobile Bottom Navigation */}
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
                    ? isStudent
                      ? 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30'
                      : 'text-brand-navy bg-brand-navy/5 dark:bg-brand-navy/10'
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

export default PortalLayout;
