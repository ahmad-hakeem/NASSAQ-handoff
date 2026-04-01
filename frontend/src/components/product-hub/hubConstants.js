import {
  Bug, AlertTriangle, Clock, CheckCircle2, XCircle, Eye, Zap, Lightbulb,
  Shield, Target, AlertOctagon, ArrowUpRight, Timer, Settings, Link2,
  HelpCircle, FileText, TrendingUp, Sparkles, RotateCcw, MessageSquare,
  UserPlus, ClipboardCheck, Send, ThumbsUp, ThumbsDown, Edit3
} from 'lucide-react';

export const STATUS_CONFIG = {
  new: { label: 'جديد', labelEn: 'New', color: 'bg-blue-500', textColor: 'text-blue-700', bgLight: 'bg-blue-50', borderColor: 'border-blue-200', icon: Zap, ring: 'ring-blue-400' },
  under_review: { label: 'تحت المراجعة', labelEn: 'Under Review', color: 'bg-amber-500', textColor: 'text-amber-700', bgLight: 'bg-amber-50', borderColor: 'border-amber-200', icon: Eye, ring: 'ring-amber-400' },
  in_progress: { label: 'قيد التنفيذ', labelEn: 'In Progress', color: 'bg-violet-500', textColor: 'text-violet-700', bgLight: 'bg-violet-50', borderColor: 'border-violet-200', icon: Clock, ring: 'ring-violet-400' },
  qa_validation: { label: 'تحقق الجودة', labelEn: 'QA Validation', color: 'bg-cyan-500', textColor: 'text-cyan-700', bgLight: 'bg-cyan-50', borderColor: 'border-cyan-200', icon: Shield, ring: 'ring-cyan-400' },
  done: { label: 'مكتمل', labelEn: 'Done', color: 'bg-emerald-500', textColor: 'text-emerald-700', bgLight: 'bg-emerald-50', borderColor: 'border-emerald-200', icon: CheckCircle2, ring: 'ring-emerald-400' },
  rejected: { label: 'مرفوض', labelEn: 'Rejected', color: 'bg-red-500', textColor: 'text-red-700', bgLight: 'bg-red-50', borderColor: 'border-red-200', icon: XCircle, ring: 'ring-red-400' },
  user_feedback_confirmed: { label: 'أكده المستخدم', labelEn: 'Confirmed', color: 'bg-emerald-600', textColor: 'text-emerald-700', bgLight: 'bg-emerald-50', borderColor: 'border-emerald-300', icon: CheckCircle2, ring: 'ring-emerald-400' },
};

export const PRIORITY_CONFIG = {
  critical: { label: 'حرج', labelEn: 'Critical', color: 'bg-red-600', textColor: 'text-red-700', bgLight: 'bg-red-50', icon: AlertOctagon, dotColor: 'bg-red-500' },
  high: { label: 'عالي', labelEn: 'High', color: 'bg-orange-500', textColor: 'text-orange-700', bgLight: 'bg-orange-50', icon: AlertTriangle, dotColor: 'bg-orange-500' },
  medium: { label: 'متوسط', labelEn: 'Medium', color: 'bg-yellow-500', textColor: 'text-yellow-700', bgLight: 'bg-yellow-50', icon: Target, dotColor: 'bg-yellow-500' },
  low: { label: 'منخفض', labelEn: 'Low', color: 'bg-slate-400', textColor: 'text-slate-600', bgLight: 'bg-slate-50', icon: ArrowUpRight, dotColor: 'bg-slate-400' },
};

export const TYPE_CONFIG = {
  bug: { label: 'خطأ برمجي', icon: Bug, color: 'text-red-600' },
  error: { label: 'خطأ تقني', icon: AlertTriangle, color: 'text-red-500' },
  ui_issue: { label: 'مشكلة واجهة', icon: Eye, color: 'text-blue-600' },
  ux_issue: { label: 'مشكلة تجربة مستخدم', icon: Lightbulb, color: 'text-purple-600' },
  performance_issue: { label: 'مشكلة أداء', icon: Zap, color: 'text-amber-600' },
  content_issue: { label: 'مشكلة محتوى', icon: FileText, color: 'text-teal-600' },
  feature_request: { label: 'طلب ميزة', icon: Lightbulb, color: 'text-green-600' },
  improvement_suggestion: { label: 'اقتراح تحسين', icon: TrendingUp, color: 'text-cyan-600' },
  permission_issue: { label: 'مشكلة صلاحيات', icon: Shield, color: 'text-orange-600' },
  workflow_issue: { label: 'مشكلة سير عمل', icon: Settings, color: 'text-violet-600' },
  integration_issue: { label: 'مشكلة تكامل', icon: Link2, color: 'text-indigo-600' },
  other: { label: 'أخرى', icon: HelpCircle, color: 'text-slate-600' },
};

export const STATUS_PROGRESS = {
  new: 10, under_review: 25, in_progress: 55, qa_validation: 80,
  done: 100, rejected: 100, user_feedback_confirmed: 100,
};

export const KANBAN_COLUMNS = [
  'new', 'under_review', 'in_progress', 'qa_validation', 'done', 'rejected', 'user_feedback_confirmed'
];

export const FINAL_STATUSES = new Set(['done', 'rejected', 'user_feedback_confirmed']);
export const TEAMS = ['Frontend', 'Backend', 'DevOps', 'Design', 'QA', 'Product'];

export const EVENT_LABELS = {
  created: 'تم إنشاء المشكلة',
  issue_created: 'تم إنشاء المشكلة',
  status_changed: 'تم تغيير الحالة',
  assigned: 'تم التعيين',
  issue_assigned: 'تم تعيين الفريق',
  ai_analyzed: 'تحليل حكيم',
  hakim_analysis_started: 'بدأ تحليل حكيم',
  hakim_analysis_completed: 'اكتمل تحليل حكيم',
  duplicate_detected: 'اكتشاف مكرر',
  prompt_generated: 'إنشاء Prompt',
  comment_added: 'تعليق جديد',
  attachment_added: 'مرفق جديد',
  feedback_loop_sent: 'طلب تأكيد من المستخدم',
  user_confirmed_resolution: 'المستخدم أكّد الحل',
  user_rejected_resolution: 'المستخدم رفض الحل',
  issue_reopened: 'إعادة فتح المشكلة',
  issue_updated: 'تحديث المشكلة',
  issue_marked_done: 'تم إكمال المشكلة',
  sla_warning_triggered: 'تحذير SLA',
  updated: 'تحديث',
  closed: 'تم الإغلاق',
  reopened: 'إعادة فتح',
  feedback_confirmed: 'تأكيد الملاحظات',
};

export const COMMENT_TYPE_CONFIG = {
  admin_note: { label: 'ملاحظة إدارية', bgColor: 'bg-blue-50', borderColor: 'border-blue-200', textColor: 'text-blue-700' },
  qa_note: { label: 'ملاحظة QA', bgColor: 'bg-purple-50', borderColor: 'border-purple-200', textColor: 'text-purple-700' },
  general: { label: 'تعليق', bgColor: 'bg-slate-50', borderColor: 'border-slate-200', textColor: 'text-slate-700' },
};

export const IMPACT_LABELS = {
  blocks_process: 'يمنع سير العمل',
  wrong_results: 'نتائج خاطئة',
  slow_performance: 'أداء بطيء',
  user_confusion: 'إرباك المستخدم',
  visual_issue: 'مشكلة بصرية',
  data_loss: 'فقدان بيانات',
  minor_impact: 'تأثير بسيط',
};

export const REPRODUCIBILITY_OPTIONS = [
  { value: 'yes', label: 'نعم، دائماً' },
  { value: 'sometimes', label: 'أحياناً' },
  { value: 'no', label: 'لا' },
];

export const DYNAMIC_FIELD_LABELS = {
  steps_to_reproduce: 'خطوات إعادة الإنتاج',
  reproducibility: 'قابلية التكرار',
  error_message: 'رسالة الخطأ',
  error_code: 'رمز الخطأ',
  screen_area: 'منطقة الشاشة',
  affected_elements: 'العناصر المتأثرة',
  user_journey: 'رحلة المستخدم',
  pain_point: 'نقطة الألم',
  load_time: 'وقت التحميل',
  affected_operation: 'العملية المتأثرة',
  content_location: 'موقع المحتوى',
  content_type: 'نوع المحتوى',
  use_case: 'حالة الاستخدام',
  business_value: 'القيمة التجارية',
  improvement_area: 'مجال التحسين',
  expected_impact: 'الأثر المتوقع',
  affected_role: 'الدور المتأثر',
  expected_access: 'الصلاحية المتوقعة',
  workflow_name: 'اسم سير العمل',
  broken_step: 'الخطوة المعطلة',
  integration_name: 'اسم التكامل',
  api_endpoint: 'نقطة API',
  additional_details: 'تفاصيل إضافية',
};
