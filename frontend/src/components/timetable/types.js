/**
 * نظام أنواع صفحة الجدول المدرسي
 * Timetable Page Type Definitions
 */

// ============================================
// View Modes
// ============================================
export const ViewModes = {
  ALL: 'all',
  CLASS: 'class',
  TEACHER: 'teacher',
  SUBJECT: 'subject',
  WEEK: 'week',
  DAY: 'day',
  GRADE: 'grade'
};

// ============================================
// Timetable Status
// ============================================
export const TimetableStatus = {
  NONE: 'none',
  DRAFT: 'draft',
  PUBLISHED: 'published',
  GENERATING: 'generating',
  FAILED: 'failed',
  ARCHIVED: 'archived'
};

// ============================================
// Readiness Status
// ============================================
export const ReadinessStatus = {
  NOT_READY: 'NOT_READY',
  PARTIALLY_READY: 'PARTIALLY_READY',
  FULLY_READY: 'FULLY_READY'
};

// ============================================
// Issue Types
// ============================================
export const IssueType = {
  CRITICAL: 'critical',
  WARNING: 'warning',
  INFO: 'info'
};

// ============================================
// Issue Severity
// ============================================
export const IssueSeverity = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical'
};

// ============================================
// Entry Types (Cell Types)
// ============================================
export const EntryType = {
  LECTURE: 'lecture',
  BREAK: 'break',
  PRAYER: 'prayer',
  ASSEMBLY: 'assembly',
  CUSTOM: 'custom',
  EMPTY: 'empty'
};

// ============================================
// Block Types (Row Types)
// ============================================
export const BlockType = {
  PERIOD: 'period',
  BREAK: 'break',
  PRAYER: 'prayer',
  ASSEMBLY: 'assembly',
  CUSTOM: 'custom'
};

// ============================================
// Session Status
// ============================================
export const SessionStatus = {
  SCHEDULED: 'scheduled',
  MODIFIED: 'modified',
  LOCKED: 'locked',
  CANCELLED: 'cancelled'
};

// ============================================
// Generation Mode
// ============================================
export const GenerationMode = {
  FULL: 'full',
  PARTIAL_CLASS: 'class',
  PARTIAL_TEACHER: 'teacher',
  PARTIAL_DAY: 'day',
  PARTIAL_SUBJECT: 'subject'
};

// ============================================
// Days of Week
// ============================================
export const WEEKDAYS = [
  { key: 'sunday', number: 0, ar: 'الأحد', en: 'Sunday', short: 'Sun', color: 'from-blue-500 to-blue-600' },
  { key: 'monday', number: 1, ar: 'الإثنين', en: 'Monday', short: 'Mon', color: 'from-purple-500 to-purple-600' },
  { key: 'tuesday', number: 2, ar: 'الثلاثاء', en: 'Tuesday', short: 'Tue', color: 'from-green-500 to-green-600' },
  { key: 'wednesday', number: 3, ar: 'الأربعاء', en: 'Wednesday', short: 'Wed', color: 'from-amber-500 to-amber-600' },
  { key: 'thursday', number: 4, ar: 'الخميس', en: 'Thursday', short: 'Thu', color: 'from-rose-500 to-rose-600' },
  { key: 'friday', number: 5, ar: 'الجمعة', en: 'Friday', short: 'Fri', color: 'from-emerald-500 to-emerald-600' },
  { key: 'saturday', number: 6, ar: 'السبت', en: 'Saturday', short: 'Sat', color: 'from-slate-500 to-slate-600' },
];

// ============================================
// Subject Colors
// ============================================
export const SUBJECT_COLORS = {
  'لغتي': { bg: 'bg-teal-50', border: 'border-teal-200', text: 'text-teal-800', accent: 'bg-teal-500', badge: 'bg-teal-100' },
  'اللغة العربية': { bg: 'bg-teal-50', border: 'border-teal-200', text: 'text-teal-800', accent: 'bg-teal-500', badge: 'bg-teal-100' },
  'الرياضيات': { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', accent: 'bg-blue-500', badge: 'bg-blue-100' },
  'العلوم': { bg: 'bg-violet-50', border: 'border-violet-200', text: 'text-violet-800', accent: 'bg-violet-500', badge: 'bg-violet-100' },
  'الدراسات الإسلامية': { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-800', accent: 'bg-amber-500', badge: 'bg-amber-100' },
  'القرآن': { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-800', accent: 'bg-yellow-500', badge: 'bg-yellow-100' },
  'اللغة الإنجليزية': { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-800', accent: 'bg-rose-500', badge: 'bg-rose-100' },
  'التربية الفنية': { bg: 'bg-fuchsia-50', border: 'border-fuchsia-200', text: 'text-fuchsia-800', accent: 'bg-fuchsia-500', badge: 'bg-fuchsia-100' },
  'التربية البدنية': { bg: 'bg-cyan-50', border: 'border-cyan-200', text: 'text-cyan-800', accent: 'bg-cyan-500', badge: 'bg-cyan-100' },
  'الدراسات الاجتماعية': { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', accent: 'bg-emerald-500', badge: 'bg-emerald-100' },
  'المهارات الرقمية': { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-700', accent: 'bg-slate-500', badge: 'bg-slate-100' },
  'الحاسب': { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-700', accent: 'bg-slate-500', badge: 'bg-slate-100' },
  default: { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-700', accent: 'bg-gray-400', badge: 'bg-gray-100' }
};

export const NEUTRAL_COLOR = { bg: 'bg-white', border: 'border-gray-200', text: 'text-gray-700', accent: 'bg-gray-300', badge: 'bg-gray-50' };

// ============================================
// Helper Functions
// ============================================
export const getSubjectColor = (subjectName) => {
  if (!subjectName) return SUBJECT_COLORS.default;
  for (const [key, value] of Object.entries(SUBJECT_COLORS)) {
    if (subjectName.includes(key)) return value;
  }
  return SUBJECT_COLORS.default;
};

export const getStatusBadgeStyle = (status) => {
  switch (status) {
    case TimetableStatus.PUBLISHED:
      return 'bg-green-100 text-green-800 border-green-200';
    case TimetableStatus.DRAFT:
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case TimetableStatus.GENERATING:
      return 'bg-violet-100 text-violet-800 border-violet-200';
    case TimetableStatus.FAILED:
      return 'bg-red-100 text-red-800 border-red-200';
    case TimetableStatus.ARCHIVED:
      return 'bg-gray-100 text-gray-800 border-gray-200';
    default:
      return 'bg-gray-100 text-gray-600 border-gray-200';
  }
};

export const getStatusLabel = (status) => {
  switch (status) {
    case TimetableStatus.PUBLISHED:
      return { ar: 'منشور', en: 'Published' };
    case TimetableStatus.DRAFT:
      return { ar: 'مسودة', en: 'Draft' };
    case TimetableStatus.GENERATING:
      return { ar: 'جاري التوليد', en: 'Generating' };
    case TimetableStatus.FAILED:
      return { ar: 'فشل', en: 'Failed' };
    case TimetableStatus.ARCHIVED:
      return { ar: 'مؤرشف', en: 'Archived' };
    case TimetableStatus.NONE:
      return { ar: 'لا يوجد', en: 'None' };
    default:
      return { ar: status, en: status };
  }
};

export const getWeekdayByKey = (key) => {
  return WEEKDAYS.find(d => d.key === key) || WEEKDAYS[0];
};

export const getWorkingDays = (workingDaysArray) => {
  if (!workingDaysArray || !Array.isArray(workingDaysArray)) {
    // Default working days (Sunday - Thursday)
    return WEEKDAYS.filter(d => ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'].includes(d.key));
  }
  return WEEKDAYS.filter(d => workingDaysArray.includes(d.key));
};
