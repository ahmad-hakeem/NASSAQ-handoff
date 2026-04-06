import {
  Shield, Briefcase, Settings, HeadphonesIcon, BarChart3,
  Megaphone, TestTube, School, GraduationCap, Users
} from 'lucide-react';

export const USER_ROLES = [
  { id: 'platform_admin', name: 'مدير المنصة', name_en: 'Platform Admin', color: 'bg-purple-600', icon: Shield },
  { id: 'platform_operations_manager', name: 'مدير العمليات', name_en: 'Operations Manager', color: 'bg-blue-600', icon: Briefcase },
  { id: 'platform_technical_admin', name: 'مسؤول تقني', name_en: 'Technical Admin', color: 'bg-indigo-600', icon: Settings },
  { id: 'platform_support_specialist', name: 'دعم فني', name_en: 'Support Specialist', color: 'bg-green-600', icon: HeadphonesIcon },
  { id: 'platform_data_analyst', name: 'محلل بيانات', name_en: 'Data Analyst', color: 'bg-orange-600', icon: BarChart3 },
  { id: 'platform_security_officer', name: 'مسؤول أمن', name_en: 'Security Officer', color: 'bg-red-600', icon: Shield },
  { id: 'platform_sales', name: 'المبيعات', name_en: 'Sales', color: 'bg-emerald-600', icon: Megaphone },
  { id: 'platform_marketing', name: 'التسويق', name_en: 'Marketing', color: 'bg-pink-600', icon: Megaphone },
  { id: 'platform_quality', name: 'الجودة والاختبار', name_en: 'Quality & Testing', color: 'bg-amber-600', icon: TestTube },
  { id: 'school_principal', name: 'مدير مدرسة', name_en: 'School Principal', color: 'bg-teal-600', icon: School },
  { id: 'teacher', name: 'معلم', name_en: 'Teacher', color: 'bg-cyan-600', icon: GraduationCap },
  { id: 'independent_teacher', name: 'معلم مستقل', name_en: 'Independent Teacher', color: 'bg-violet-600', icon: GraduationCap },
  { id: 'testing_account', name: 'حساب اختبار', name_en: 'Testing Account', color: 'bg-gray-500', icon: TestTube },
];

export const ACCOUNT_TYPES = [
  { id: 'all', name: 'جميع الحسابات', name_en: 'All Accounts' },
  { id: 'platform', name: 'حسابات المنصة', name_en: 'Platform Accounts' },
  { id: 'school', name: 'حسابات المدارس', name_en: 'School Accounts' },
  { id: 'independent', name: 'معلمين مستقلين', name_en: 'Independent Teachers' },
  { id: 'testing', name: 'حسابات اختبار', name_en: 'Testing Accounts' },
];

export const ACCOUNT_STATUSES = [
  { id: 'all', name: 'كل الحالات', name_en: 'All Status', color: '' },
  { id: 'active', name: 'نشط', name_en: 'Active', color: 'bg-green-500' },
  { id: 'suspended', name: 'موقوف', name_en: 'Suspended', color: 'bg-red-500' },
  { id: 'pending', name: 'معلق', name_en: 'Pending', color: 'bg-yellow-500' },
  { id: 'archived', name: 'مؤرشف', name_en: 'Archived', color: 'bg-gray-500' },
];

export const REQUEST_STATUSES = [
  { id: 'all', name: 'جميع الطلبات', name_en: 'All Requests', color: '' },
  { id: 'pending', name: 'قيد الاعتماد', name_en: 'Pending Review', color: 'bg-yellow-500' },
  { id: 'under_review', name: 'تحت المراجعة', name_en: 'Under Review', color: 'bg-orange-500' },
  { id: 'info_required', name: 'بانتظار معلومات', name_en: 'Info Required', color: 'bg-blue-500' },
  { id: 'approved', name: 'المعتمدين', name_en: 'Approved', color: 'bg-green-500' },
  { id: 'rejected', name: 'المرفوضين', name_en: 'Rejected', color: 'bg-red-500' },
  { id: 'archived', name: 'مؤرشف', name_en: 'Archived', color: 'bg-gray-500' },
];

export const PENDING_STATUSES = ['pending', 'pending_review', 'under_review', 'info_required', 'more_info_requested'];

export const getRoleInfo = (roleId) => {
  return USER_ROLES.find(r => r.id === roleId) || { name: roleId, name_en: roleId, color: 'bg-gray-500', icon: Users };
};

export const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('ar-SA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

export const formatTimeAgo = (dateStr) => {
  if (!dateStr) return 'لم يسجل دخول';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `منذ ${diffMins} دقيقة`;
  if (diffHours < 24) return `منذ ${diffHours} ساعة`;
  if (diffDays < 7) return `منذ ${diffDays} يوم`;
  return formatDate(dateStr);
};
