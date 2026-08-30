import {
  Building2, Users, GraduationCap, BookOpen, UserCheck,
  Pause, Play, Edit, Trash2, CheckCircle2, XCircle, Shield,
  LogIn, LogOut, AlertTriangle, Key, Download, Upload,
  Sparkles, Lock, Archive, RotateCcw, Send, Calendar, Settings, Activity
} from 'lucide-react';

export const SCHOOL_STATUS = {
  active: {
    label: 'نشطة',
    label_en: 'Active',
    color: 'bg-emerald-500',
    badge: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800',
    dot: 'bg-emerald-500',
  },
  suspended: {
    label: 'موقوفة',
    label_en: 'Suspended',
    color: 'bg-rose-500',
    badge: 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800',
    dot: 'bg-rose-500',
  },
  setup: {
    label: 'مسودة / قيد الإعداد',
    label_en: 'Draft / Setup',
    color: 'bg-amber-500',
    badge: 'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800',
    dot: 'bg-amber-500',
  },
  pending: {
    label: 'معلقة',
    label_en: 'Pending',
    color: 'bg-slate-500',
    badge: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700',
    dot: 'bg-slate-500',
  },
};

export const LOGO_GRADIENTS = [
  'from-[#1C3D74] to-[#2a5096]',
  'from-[#00897B] to-[#46C1BE]',
  'from-[#615090] to-[#7a68a8]',
  'from-[#0284C7] to-[#38BDF8]',
  'from-[#0D9488] to-[#2DD4BF]',
  'from-[#4338CA] to-[#6366F1]',
  'from-[#2563EB] to-[#60A5FA]',
  'from-[#059669] to-[#34D399]',
];

export const getLogoGradient = (id) => {
  const hash = (id || '').split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return LOGO_GRADIENTS[hash % LOGO_GRADIENTS.length];
};

export const COUNTRIES = [
  { code: 'SA', name: 'المملكة العربية السعودية', name_en: 'Saudi Arabia' },
  { code: 'AE', name: 'الإمارات العربية المتحدة', name_en: 'UAE' },
  { code: 'KW', name: 'الكويت', name_en: 'Kuwait' },
  { code: 'QA', name: 'قطر', name_en: 'Qatar' },
  { code: 'BH', name: 'البحرين', name_en: 'Bahrain' },
  { code: 'OM', name: 'عمان', name_en: 'Oman' },
  { code: 'EG', name: 'مصر', name_en: 'Egypt' },
  { code: 'JO', name: 'الأردن', name_en: 'Jordan' },
];

export const SAUDI_REGIONS = {
  central: { name: 'المنطقة الوسطى', cities: ['الرياض', 'القصيم', 'حائل'] },
  western: { name: 'المنطقة الغربية', cities: ['جدة', 'مكة المكرمة', 'المدينة المنورة', 'الطائف', 'ينبع'] },
  eastern: { name: 'المنطقة الشرقية', cities: ['الدمام', 'الخبر', 'الظهران', 'الأحساء', 'الجبيل'] },
  northern: { name: 'المنطقة الشمالية', cities: ['تبوك', 'عرعر', 'سكاكا'] },
  southern: { name: 'المنطقة الجنوبية', cities: ['أبها', 'جازان', 'نجران', 'خميس مشيط'] },
};

export const ALL_SAUDI_CITIES = Object.values(SAUDI_REGIONS).flatMap((r) => r.cities);

export const SCHOOL_TYPES = [
  { value: 'public', label: 'حكومية', label_en: 'Public', desc: 'مدرسة تابعة للتعليم الحكومي العام' },
  { value: 'private', label: 'أهلية', label_en: 'Private', desc: 'مدرسة تابعة لقطاع التعليم الخاص' },
];

export const EDUCATIONAL_STAGES = [
  { value: 'primary', label: 'ابتدائية', label_en: 'Primary', desc: 'الصفوف من الأول إلى السادس' },
  { value: 'intermediate', label: 'متوسطة', label_en: 'Intermediate', desc: 'الصفوف من الأول إلى الثالث متوسط' },
  { value: 'secondary_general', label: 'ثانوية عامة', label_en: 'Secondary General', desc: 'المرحلة الثانوية بنظام المقررات' },
  { value: 'secondary_pathways', label: 'ثانوية مسارات', label_en: 'Secondary Pathways', desc: 'المرحلة الثانوية بنظام المسارات التخصصية' },
  { value: 'school_complex', label: 'مجمع مدارس', label_en: 'School Complex', desc: 'مجمع تعليمي يشمل مراحل متعددة' },
];

export const EDUCATIONAL_PATHWAYS = [
  { value: 'general', label: 'المسار العام', label_en: 'General Pathway' },
  { value: 'cs_engineering', label: 'مسار علوم الحاسب والهندسة', label_en: 'CS & Engineering Pathway' },
  { value: 'health_life', label: 'مسار الصحة والحياة', label_en: 'Health & Life Pathway' },
  { value: 'business', label: 'مسار إدارة الأعمال', label_en: 'Business Administration Pathway' },
  { value: 'sharia', label: 'المسار الشرعي', label_en: 'Sharia Pathway' },
];

export const CALENDAR_SYSTEMS = [
  { value: 'hijri', label: 'هجري', label_en: 'Hijri' },
  { value: 'gregorian', label: 'ميلادي', label_en: 'Gregorian' },
  { value: 'hijri_gregorian', label: 'هجري + ميلادي', label_en: 'Hijri + Gregorian' },
  { value: 'gregorian_hijri', label: 'ميلادي + هجري', label_en: 'Gregorian + Hijri' },
];

export const ASSESSMENT_SYSTEMS = [
  { value: 'standard', label: 'النظام القياسي (100 درجة)', label_en: 'Standard (100 points)' },
  { value: 'gpa', label: 'نظام المعدل التراكمي', label_en: 'GPA System' },
  { value: 'competency', label: 'نظام الكفايات', label_en: 'Competency Based' },
];

export const ROLE_LABELS = {
  school_principal: { ar: 'مدير المدرسة', en: 'Principal', color: 'bg-[#1C3D74]/10 text-[#1C3D74] dark:bg-[#1C3D74]/30 dark:text-blue-300 border border-blue-200 dark:border-blue-800' },
  school_admin:     { ar: 'مشرف', en: 'Supervisor', color: 'bg-[#615090]/10 text-[#615090] dark:bg-[#615090]/30 dark:text-purple-300 border border-purple-200 dark:border-purple-800' },
  teacher:          { ar: 'معلم', en: 'Teacher', color: 'bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300 border border-teal-200 dark:border-teal-800' },
  student:          { ar: 'طالب', en: 'Student', color: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 border border-blue-200 dark:border-blue-800' },
  parent:           { ar: 'ولي أمر', en: 'Parent', color: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800' },
};

export const ACTION_LABELS = {
  'tenant.suspended': { ar: 'تعليق المدرسة', en: 'School suspended', icon: Pause, color: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40' },
  'tenant.activated': { ar: 'تفعيل المدرسة', en: 'School activated', icon: Play, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'tenant.created':   { ar: 'إنشاء المدرسة', en: 'School created', icon: Building2, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'tenant.updated':   { ar: 'تعديل المدرسة', en: 'School updated', icon: Edit, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'user.created':       { ar: 'إنشاء مستخدم', en: 'User created', icon: Users, color: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40' },
  'user.updated':       { ar: 'تعديل مستخدم', en: 'User updated', icon: Edit, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'user.deleted':       { ar: 'حذف مستخدم', en: 'User deleted', icon: Trash2, color: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40' },
  'user.activated':     { ar: 'تفعيل مستخدم', en: 'User activated', icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'user.suspended':     { ar: 'تعليق مستخدم', en: 'User suspended', icon: XCircle, color: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40' },
  'user.role_assigned': { ar: 'إسناد دور', en: 'Role assigned', icon: Shield, color: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40' },
  'user.role_removed':  { ar: 'إزالة دور', en: 'Role removed', icon: Shield, color: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800' },
  'auth.login':            { ar: 'تسجيل دخول', en: 'Login', icon: LogIn, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'auth.logout':           { ar: 'تسجيل خروج', en: 'Logout', icon: LogOut, color: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800' },
  'auth.login_failed':     { ar: 'محاولة دخول فاشلة', en: 'Failed login attempt', icon: AlertTriangle, color: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40' },
  'auth.password_changed': { ar: 'تغيير كلمة المرور', en: 'Password changed', icon: Key, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'auth.password_reset':   { ar: 'إعادة تعيين كلمة المرور', en: 'Password reset', icon: Key, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'academic.grade_recorded':       { ar: 'تسجيل درجة', en: 'Grade recorded', icon: GraduationCap, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'academic.grade_updated':        { ar: 'تعديل درجة', en: 'Grade updated', icon: GraduationCap, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'academic.grades_bulk_recorded': { ar: 'تسجيل درجات بالجملة', en: 'Grades recorded (bulk)', icon: GraduationCap, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'academic.assessment_created':   { ar: 'إنشاء تقييم', en: 'Assessment created', icon: BookOpen, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'academic.assessment_published': { ar: 'نشر تقييم', en: 'Assessment published', icon: BookOpen, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'academic.report_card_generated':{ ar: 'إصدار بطاقة تقرير', en: 'Report card generated', icon: BookOpen, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'attendance.recorded':        { ar: 'تسجيل حضور', en: 'Attendance recorded', icon: UserCheck, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'attendance.bulk_recorded':   { ar: 'تسجيل حضور بالجملة', en: 'Attendance recorded (bulk)', icon: UserCheck, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'attendance.excuse_submitted':{ ar: 'تقديم عذر غياب', en: 'Excuse submitted', icon: UserCheck, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'attendance.excuse_approved': { ar: 'اعتماد عذر غياب', en: 'Excuse approved', icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'behaviour.note_created':   { ar: 'ملاحظة سلوكية', en: 'Behaviour note created', icon: AlertTriangle, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'behaviour.action_created': { ar: 'إجراء انضباطي', en: 'Disciplinary action created', icon: AlertTriangle, color: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40' },
  'behaviour.action_updated': { ar: 'تعديل إجراء انضباطي', en: 'Disciplinary action updated', icon: AlertTriangle, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'behaviour.recorded':       { ar: 'تسجيل سلوك', en: 'Behaviour recorded', icon: AlertTriangle, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'behaviour.reviewed':       { ar: 'مراجعة سلوك', en: 'Behaviour reviewed', icon: CheckCircle2, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'schedule.created':   { ar: 'إنشاء الجدول', en: 'Schedule created', icon: Calendar, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'schedule.published': { ar: 'نشر الجدول', en: 'Schedule published', icon: Calendar, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'schedule.modified':  { ar: 'تعديل الجدول', en: 'Schedule modified', icon: Calendar, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'settings.updated':     { ar: 'تعديل الإعدادات', en: 'Settings updated', icon: Settings, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'system.configuration': { ar: 'إعداد النظام', en: 'System configuration', icon: Settings, color: 'text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800' },
  'data.exported':        { ar: 'تصدير بيانات', en: 'Data exported', icon: Download, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'data.imported':        { ar: 'استيراد بيانات', en: 'Data imported', icon: Upload, color: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/40' },
  'mfa.disabled':        { ar: 'تعطيل التحقق بخطوتين', en: 'Two-factor disabled', icon: Lock, color: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40' },
  'mfa.totp.enroll_success': { ar: 'تسجيل تطبيق المصادقة', en: 'Authenticator app enrolled', icon: Shield, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
  'INDEPENDENT_TEACHER_BOOTSTRAP': { ar: 'تهيئة مساحة العمل', en: 'Workspace initialized', icon: Sparkles, color: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40' },
  'INDEPENDENT_TEACHER_WORKSPACE_ARCHIVE': { ar: 'أرشفة مساحة العمل', en: 'Workspace archived', icon: Archive, color: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40' },
  'INDEPENDENT_TEACHER_WORKSPACE_REACTIVATE': { ar: 'إعادة تنشيط مساحة العمل', en: 'Workspace reactivated', icon: RotateCcw, color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40' },
};

const ACTION_LABELS_LOWER = Object.fromEntries(
  Object.entries(ACTION_LABELS).map(([k, v]) => [k.toLowerCase(), v])
);

export function humaniseActivity(raw) {
  if (!raw || typeof raw !== 'string') return '';
  return raw
    .toLowerCase()
    .split(/[_.\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function resolveActivity(raw, isRTL) {
  const cfg = raw ? ACTION_LABELS_LOWER[String(raw).toLowerCase()] : null;
  if (cfg) {
    return { label: isRTL ? cfg.ar : cfg.en, icon: cfg.icon, color: cfg.color };
  }
  return { label: humaniseActivity(raw), icon: Activity, color: 'text-slate-500 bg-slate-100 dark:bg-slate-800' };
}
