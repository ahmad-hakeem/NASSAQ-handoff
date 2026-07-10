// Shared notification display metadata + adapters for the cross-role
// quick-preview dialog (NotificationDetailDialog). The type/priority
// maps and prettifyText are deliberate COPIES of the ones inside
// pages/NotificationsPage.jsx — the parent notifications page is
// stable and must stay untouched (replit.md user preference: no
// changes to stable logic unless strictly necessary).
import {
  Info, CalendarCheck, Calendar, ClipboardList, AlertTriangle,
  MessageSquare, Megaphone, FileText, CheckCheck,
  Users, GraduationCap, Building2, Gauge, Sparkles,
} from 'lucide-react';

export const notificationTypeConfig = {
  system: { icon: Info, label: { ar: 'النظام', en: 'System' }, color: 'bg-gray-500', iconColor: 'text-gray-500' },
  attendance: { icon: CalendarCheck, label: { ar: 'الحضور', en: 'Attendance' }, color: 'bg-blue-500', iconColor: 'text-blue-500' },
  schedule: { icon: Calendar, label: { ar: 'الجدول', en: 'Schedule' }, color: 'bg-purple-500', iconColor: 'text-purple-500' },
  assessment: { icon: ClipboardList, label: { ar: 'التقييمات', en: 'Assessments' }, color: 'bg-green-500', iconColor: 'text-green-500' },
  behaviour: { icon: AlertTriangle, label: { ar: 'السلوك', en: 'Behaviour' }, color: 'bg-yellow-500', iconColor: 'text-yellow-500' },
  communication: { icon: MessageSquare, label: { ar: 'التواصل', en: 'Communication' }, color: 'bg-teal-500', iconColor: 'text-teal-500' },
  announcement: { icon: Megaphone, label: { ar: 'الإعلانات', en: 'Announcements' }, color: 'bg-orange-500', iconColor: 'text-orange-500' },
  circular: { icon: FileText, label: { ar: 'تعميم', en: 'Circular' }, color: 'bg-indigo-500', iconColor: 'text-indigo-500' },
  other: { icon: Info, label: { ar: 'أخرى', en: 'Other' }, color: 'bg-slate-500', iconColor: 'text-slate-500' },
  circular_ack: { icon: CheckCheck, label: { ar: 'تأكيد استلام تعميم', en: 'Circular Ack' }, color: 'bg-green-500', iconColor: 'text-green-600' },
};

export const priorityConfig = {
  low: { label: { ar: 'منخفضة', en: 'Low' }, color: 'bg-gray-400' },
  medium: { label: { ar: 'متوسطة', en: 'Medium' }, color: 'bg-blue-400' },
  high: { label: { ar: 'مرتفعة', en: 'High' }, color: 'bg-orange-500' },
  critical: { label: { ar: 'حرجة', en: 'Critical' }, color: 'bg-red-600' },
};

// IT inbox rows carry `category` (collab_invite, parent_accept, …),
// not `notification_type` — a separate taxonomy mapped here so the
// dialog itself only ever sees resolved display meta.
export const itCategoryConfig = {
  collab_invite: { icon: Users, label: { ar: 'تعاون', en: 'Collaboration' }, color: 'bg-teal-500', iconColor: 'text-teal-500' },
  parent_accept: { icon: GraduationCap, label: { ar: 'أولياء الأمور', en: 'Parents' }, color: 'bg-blue-500', iconColor: 'text-blue-500' },
  workspace_lifecycle: { icon: Building2, label: { ar: 'مساحة العمل', en: 'Workspace' }, color: 'bg-purple-500', iconColor: 'text-purple-500' },
  quota: { icon: Gauge, label: { ar: 'الحصص', en: 'Quota' }, color: 'bg-orange-500', iconColor: 'text-orange-500' },
  lesson_plan: { icon: Sparkles, label: { ar: 'خطط الدروس', en: 'Lesson plans' }, color: 'bg-indigo-500', iconColor: 'text-indigo-500' },
  general: { icon: Info, label: { ar: 'عام', en: 'General' }, color: 'bg-gray-500', iconColor: 'text-gray-500' },
};

const ACCOUNT_TYPE_LABEL_AR = {
  student: 'طالب',
  parent: 'ولي أمر',
  teacher: 'معلم',
  school: 'مدرسة',
  principal: 'مدير مدرسة',
  supervisor: 'مشرف',
  staff: 'موظف',
};
const ACCOUNT_TYPE_LABEL_EN = {
  student: 'Student',
  parent: 'Parent',
  teacher: 'Teacher',
  school: 'School',
  principal: 'Principal',
  supervisor: 'Supervisor',
  staff: 'Staff',
};

// Prettify legacy notification text containing raw "(student)" / "(parent)" codes.
export const prettifyText = (text, isRTL) => {
  if (!text || typeof text !== 'string') return text;
  const map = isRTL ? ACCOUNT_TYPE_LABEL_AR : ACCOUNT_TYPE_LABEL_EN;
  return text.replace(/\(([a-z_]+)\)/gi, (full, code) => {
    const key = code.toLowerCase();
    return map[key] ? `— ${map[key]}` : full;
  });
};

// Adapter: standard notification rows (school/platform/bell shape:
// notification_type, read_status, action_url) → the normalized object
// NotificationDetailDialog consumes.
export function normalizeStandardNotification(n) {
  if (!n) return null;
  return {
    id: n.id,
    title: n.title,
    titleEn: n.title_en,
    message: n.message,
    messageEn: n.message_en,
    typeMeta: notificationTypeConfig[n.notification_type] || notificationTypeConfig.system,
    priority: n.priority,
    createdAt: n.created_at,
    senderName: n.sender_name,
    actionUrl: n.action_url || null,
    student: n.student || null,
    alternativeLocation: n.alternative_location || null,
  };
}

// Adapter: IT inbox rows (category, is_read, cta_url) → normalized.
export function normalizeItNotification(n) {
  if (!n) return null;
  return {
    id: n.id,
    title: n.title,
    titleEn: n.title_en,
    message: n.message,
    messageEn: n.message_en,
    typeMeta: itCategoryConfig[n.category] || itCategoryConfig.general,
    priority: n.priority,
    createdAt: n.created_at,
    senderName: n.sender_name,
    actionUrl: n.cta_url || null,
    student: null,
    alternativeLocation: null,
  };
}
