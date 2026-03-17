import React from 'react';
import { useLocation } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
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
  Bell,
  MessageSquare,
  Shield,
  Activity,
  Link2,
  FileText,
  UserCog,
  Network,
  Briefcase,
  School,
  Home,
} from 'lucide-react';

// Map routes to their icons and titles
const PAGE_CONFIG = {
  '/admin': {
    icon: LayoutDashboard,
    title_ar: 'مركز القيادة',
    title_en: 'Control Dashboard',
  },
  '/admin/schools': {
    icon: Building2,
    title_ar: 'إدارة المدارس',
    title_en: 'Schools Management',
  },
  '/admin/users': {
    icon: Users,
    title_ar: 'إدارة المستخدمين',
    title_en: 'Users Management',
  },
  '/admin/teacher-requests': {
    icon: FileText,
    title_ar: 'طلبات المعلمين',
    title_en: 'Teacher Requests',
  },
  '/admin/rules': {
    icon: BookOpen,
    title_ar: 'إدارة القواعد',
    title_en: 'Rules Management',
  },
  '/admin/monitoring': {
    icon: Activity,
    title_ar: 'مراقبة النظام',
    title_en: 'System Monitoring',
  },
  '/admin/reports': {
    icon: BarChart3,
    title_ar: 'التحليلات',
    title_en: 'Analytics',
  },
  '/admin/integrations': {
    icon: Link2,
    title_ar: 'التكاملات',
    title_en: 'Integrations',
  },
  '/admin/security': {
    icon: Shield,
    title_ar: 'مركز الأمان',
    title_en: 'Security Center',
  },
  '/admin/settings': {
    icon: Settings,
    title_ar: 'الإعدادات',
    title_en: 'Settings',
  },
  '/admin/notifications': {
    icon: Bell,
    title_ar: 'الإشعارات',
    title_en: 'Notifications',
  },
  '/school': {
    icon: Home,
    title_ar: 'لوحة التحكم',
    title_en: 'Dashboard',
  },
  '/school/teachers': {
    icon: GraduationCap,
    title_ar: 'المعلمون',
    title_en: 'Teachers',
  },
  '/school/students': {
    icon: Users,
    title_ar: 'الطلاب',
    title_en: 'Students',
  },
  '/school/classes': {
    icon: Briefcase,
    title_ar: 'الفصول',
    title_en: 'Classes',
  },
  '/school/subjects': {
    icon: BookOpen,
    title_ar: 'المواد',
    title_en: 'Subjects',
  },
  '/school/schedule': {
    icon: Calendar,
    title_ar: 'الجدول',
    title_en: 'Schedule',
  },
  '/school/attendance': {
    icon: CalendarCheck,
    title_ar: 'الحضور',
    title_en: 'Attendance',
  },
  '/school/assessments': {
    icon: ClipboardList,
    title_ar: 'التقييمات',
    title_en: 'Assessments',
  },
  '/teacher': {
    icon: LayoutDashboard,
    title_ar: 'لوحة المعلم',
    title_en: 'Teacher Dashboard',
  },
};

// Get page config by path (handles dynamic routes)
const getPageConfig = (pathname) => {
  // Direct match
  if (PAGE_CONFIG[pathname]) {
    return PAGE_CONFIG[pathname];
  }
  
  // Check for partial matches (e.g., /admin/users/123 -> /admin/users)
  const pathParts = pathname.split('/').filter(Boolean);
  while (pathParts.length > 0) {
    const testPath = '/' + pathParts.join('/');
    if (PAGE_CONFIG[testPath]) {
      return PAGE_CONFIG[testPath];
    }
    pathParts.pop();
  }
  
  return null;
};

export const PageHeader = ({ 
  title, 
  subtitle,
  icon: CustomIcon,
  children,
  className = '',
}) => {
  const location = useLocation();
  const { isRTL } = useTheme();
  
  const pageConfig = getPageConfig(location.pathname);
  const Icon = CustomIcon || pageConfig?.icon || LayoutDashboard;
  const displayTitle = title || (isRTL ? pageConfig?.title_ar : pageConfig?.title_en) || '';
  
  return (
    <div className={`flex items-center justify-between mb-6 ${className}`}>
      <div className={`flex items-center gap-3 ${isRTL ? 'flex-row-reverse' : ''}`}>
        <div className="p-2 bg-brand-navy/10 rounded-xl">
          <Icon className="h-6 w-6 text-brand-navy" />
        </div>
        <div className={isRTL ? 'text-right' : 'text-left'}>
          <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
            {displayTitle}
          </h1>
          {subtitle && (
            <p className="text-sm text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
      {children && (
        <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
          {children}
        </div>
      )}
    </div>
  );
};

// Export config for external use
export const getPageIcon = (pathname) => {
  const config = getPageConfig(pathname);
  return config?.icon || LayoutDashboard;
};

export const getPageTitle = (pathname, isRTL = true) => {
  const config = getPageConfig(pathname);
  return isRTL ? config?.title_ar : config?.title_en;
};

export default PageHeader;
