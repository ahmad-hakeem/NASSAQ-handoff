import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, History, RefreshCw, ChevronDown, ChevronUp, Search, Download } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import { Checkbox } from '../../components/ui/checkbox';
import { formatHijriDate } from '../../utils/hijriDate';
import { useTranslation } from '../../contexts/ThemeContext';
import { ResponsiveTable } from '../../components/ui/ResponsiveTable';

// Task #248 — IT workspace audit-log view (read-only).
// Backend pins school_id == itw_{user_id} on every read, strips
// sensitive keys from `details`, and returns 404 for cross-workspace
// ids per spec §8 inv. 3. Permission gate: `audit.read_own_workspace`.

const PAGE_LIMIT = 25;

// CSV column presets — keys must mirror backend ``_CSV_FIELDS``.
// "standard" matches the historical default minus the bulky JSON
// ``details`` blob; "minimal" is the share-with-parent slice the
// task brief calls out; "full" is the original fixed column set.
// Order inside each preset matches ``_CSV_FIELDS`` so the FE-side
// equality check against ``CSV_ALL_COLUMNS`` is order-stable.
const CSV_ALL_COLUMNS = [
  'id', 'timestamp', 'category', 'category_label_ar', 'action',
  'action_label_ar', 'severity', 'actor_name', 'actor_role',
  'performed_by', 'entity_type', 'entity_id', 'details',
];
const CSV_COLUMN_PRESETS = {
  minimal: ['timestamp', 'action_label_ar', 'actor_name'],
  standard: [
    'id', 'timestamp', 'category_label_ar', 'action_label_ar',
    'severity', 'actor_name', 'actor_role', 'entity_type', 'entity_id',
  ],
  full: CSV_ALL_COLUMNS,
};

// Per-column Arabic labels for the checklist. Keys mirror
// ``_CSV_FIELDS`` exactly; unknown keys fall back to the raw key.
const CSV_COLUMN_LABELS_AR = {
  id: 'المعرّف',
  timestamp: 'الوقت',
  category: 'التصنيف (مفتاح)',
  category_label_ar: 'التصنيف',
  action: 'الحدث (مفتاح)',
  action_label_ar: 'الحدث',
  severity: 'الخطورة',
  actor_name: 'اسم المنفّذ',
  actor_role: 'دور المنفّذ',
  performed_by: 'معرّف المنفّذ',
  entity_type: 'نوع العنصر',
  entity_id: 'معرّف العنصر',
  details: 'التفاصيل (JSON)',
};

// Order-stable equality between two column lists. Both sides are
// already constrained to the ``_CSV_FIELDS`` order on the FE so a
// shallow comparison is enough.
function sameColumns(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

// Detect which preset (if any) the current selection matches so the
// radio group reflects the live state when the checklist is toggled.
function presetMatching(cols) {
  if (sameColumns(cols, CSV_COLUMN_PRESETS.full)) return 'full';
  if (sameColumns(cols, CSV_COLUMN_PRESETS.standard)) return 'standard';
  if (sameColumns(cols, CSV_COLUMN_PRESETS.minimal)) return 'minimal';
  return 'custom';
}

// Task #269 + #270 — persist the teacher's last-selected CSV columns
// in localStorage so the picker doesn't reset on every page load.
// First-time visitors still see "full" (no behavioural surprise).
// Cross-tab sync is handled via the `storage` event so two open tabs
// don't drift apart. The storage key is scoped to the authenticated
// user id so a shared browser profile (multiple teachers signing in
// turn-by-turn) never leaks one teacher's preference into another
// teacher's session. The stored value is the JSON-encoded ordered
// column array (Task #270 widened the picker from a 3-preset radio to
// a per-column checklist, so a preset name is no longer expressive
// enough to round-trip the user's selection).
const CSV_COLUMNS_STORAGE_PREFIX = 'nassaq.teacherAuditLog.csvColumns';

function csvColumnsStorageKey(userId) {
  if (!userId) return null;
  return `${CSV_COLUMNS_STORAGE_PREFIX}.${userId}`;
}

// Validate a candidate stored payload: must parse to an array of
// known column keys; we re-order against CSV_ALL_COLUMNS so the
// downstream preset detection stays stable. Returns null on any
// problem so callers can fall back to the default "full" set.
function parseStoredCsvColumns(raw) {
  if (!raw || typeof raw !== 'string') return null;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!Array.isArray(parsed)) return null;
  const allowed = new Set(CSV_ALL_COLUMNS);
  const seen = new Set();
  for (const v of parsed) {
    if (typeof v !== 'string' || !allowed.has(v)) return null;
    seen.add(v);
  }
  return CSV_ALL_COLUMNS.filter(k => seen.has(k));
}

function readStoredCsvColumns(userId) {
  if (typeof window === 'undefined') return CSV_COLUMN_PRESETS.full;
  const key = csvColumnsStorageKey(userId);
  if (!key) return CSV_COLUMN_PRESETS.full;
  try {
    const cols = parseStoredCsvColumns(window.localStorage.getItem(key));
    if (cols && cols.length) return cols;
  } catch {
    // localStorage may be unavailable (private mode / quota); fall through.
  }
  return CSV_COLUMN_PRESETS.full;
}

function severityClass(sev) {
  switch ((sev || '').toLowerCase()) {
    case 'critical': return 'bg-red-100 text-red-800 border-red-200';
    case 'high': return 'bg-red-100 text-red-800 border-red-200';
    case 'medium': return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'low': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    default: return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

// 2026-05-18 — translate severity enum to a user-facing Arabic label.
// Backend returns raw enums (low/medium/high/critical) on rows where
// the localised label hasn't been precomputed; we never want to leak
// those raw English keys into the UI.
function severityLabel(t, sev) {
  const key = (sev || '').toLowerCase();
  const fallbacks = {
    low: 'عادي',
    medium: 'متوسط',
    high: 'هام/حرج',
    critical: 'هام/حرج',
  };
  if (!key) return '—';
  const i18n = t(`auditSeverity_${key}`);
  if (i18n && i18n !== `auditSeverity_${key}`) return i18n;
  return fallbacks[key] || sev;
}

// 2026-05-19 — Arabic labels for raw backend audit event enums.
//
// The backend always populates `action_label_ar`, but for enums the
// backend doesn't recognise the value is just a destructive humanise
// of the raw token (e.g. `mfa.disabled` → "mfa · disabled",
// `INDEPENDENT_TEACHER_EXPORT_EXCEL` → "INDEPENDENT TEACHER EXPORT
// EXCEL"). That fallback leaks raw English/snake_case into the IT
// activity log UI, which we never want. The dictionary below is the
// authoritative FE-side translation table — `formatAuditEvent` below
// consults it BEFORE the backend label so a known enum is always
// rendered in Arabic, regardless of what the backend humanised.
//
// Keys mirror the exact strings the backend emits (verify against
// `backend/routes/independent_teacher_audit_routes.py::_ACTION_LABELS_AR`,
// `backend/routes/mfa_routes.py`, `backend/engines/audit_engine.py`).
// Lookups below are case-insensitive so a backend casing tweak
// (`mfa.disabled` vs `MFA.DISABLED`) doesn't silently regress.
const AUDIT_EVENT_FALLBACKS_AR = {
  // -- Independent-Teacher workspace lifecycle / exports -------------
  INDEPENDENT_TEACHER_EXPORT_EXCEL: 'تصدير بيانات المعلم إلى إكسيل',
  INDEPENDENT_TEACHER_EXPORT_CSV: 'تصدير بيانات المعلم إلى CSV',
  INDEPENDENT_TEACHER_EXPORT: 'تصدير بيانات مساحة العمل',
  INDEPENDENT_TEACHER_EXPORT_DOWNLOADED: 'تنزيل ملف التصدير',
  INDEPENDENT_TEACHER_BOOTSTRAP: 'تهيئة مساحة العمل',
  INDEPENDENT_TEACHER_SOFT_DELETE: 'أرشفة مساحة العمل',
  INDEPENDENT_TEACHER_REACTIVATE: 'إعادة تفعيل مساحة العمل',
  INDEPENDENT_TEACHER_PENDING_HARD_DELETE: 'انتهاء مهلة استرجاع المساحة',
  INDEPENDENT_TEACHER_HARD_DELETED: 'حذف نهائي لمساحة العمل',
  INDEPENDENT_TEACHER_WORKSPACE_ARCHIVE: 'أرشفة مساحة العمل',
  INDEPENDENT_TEACHER_WORKSPACE_REACTIVATE: 'إعادة تنشيط مساحة العمل',
  INDEPENDENT_TEACHER_COLLAB_INVITED: 'دعوة معلم متعاون',
  INDEPENDENT_TEACHER_COLLAB_CANCELLED: 'إلغاء دعوة متعاون',
  INDEPENDENT_TEACHER_COLLAB_ACCEPTED: 'قبول دعوة متعاون',
  INDEPENDENT_TEACHER_COLLAB_REVOKED: 'إلغاء وصول متعاون',
  INDEPENDENT_TEACHER_INVITE_PARENT: 'دعوة وليّ أمر',
  INDEPENDENT_TEACHER_INVITE_COLLABORATOR: 'دعوة معلم متعاون',
  INDEPENDENT_TEACHER_BULK_IMPORT_STUDENTS: 'استيراد طلاب بالجملة',
  INDEPENDENT_TEACHER_LESSON_SUMMARY_SENT: 'إرسال ملخص الحصة لأولياء الأمور',
  // -- Auth (engines/audit_engine.py::AuditAction) ------------------
  'auth.login': 'تسجيل دخول',
  'auth.logout': 'تسجيل خروج',
  'auth.login_failed': 'محاولة دخول فاشلة',
  'auth.password_changed': 'تغيير كلمة المرور',
  'auth.password_reset': 'إعادة تعيين كلمة المرور',
  // -- MFA (routes/mfa_routes.py) -----------------------------------
  'mfa.disabled': 'تعطيل التحقق بخطوتين',
  'mfa.disable.denied': 'رفض تعطيل التحقق بخطوتين',
  'mfa.reset.success': 'إعادة ضبط التحقق بخطوتين',
  'mfa.reset.failure': 'فشل إعادة ضبط التحقق بخطوتين',
  'mfa.challenge_issued': 'إصدار تحدّي التحقق بخطوتين',
  'mfa.login.success': 'نجاح تسجيل الدخول عبر التحقق بخطوتين',
  'mfa.login.failure': 'فشل تسجيل الدخول عبر التحقق بخطوتين',
  'mfa.stepup.success': 'نجاح تحقق إضافي (Step-up)',
  'mfa.stepup.failure': 'فشل تحقق إضافي (Step-up)',
  'mfa.stepup.challenge_issued': 'إصدار تحدّي تحقق إضافي',
  'mfa.totp.enroll_begin': 'بدء تسجيل تطبيق المصادقة',
  'mfa.totp.enroll_success': 'تسجيل تطبيق المصادقة',
  'mfa.totp.enroll_failure': 'فشل تسجيل تطبيق المصادقة',
  'mfa.webauthn.register_begin': 'بدء تسجيل مفتاح أمان',
  'mfa.webauthn.register_success': 'تسجيل مفتاح أمان',
  'mfa.webauthn.register_failure': 'فشل تسجيل مفتاح أمان',
  'mfa.email_otp.sent': 'إرسال رمز التحقق بالبريد',
  'mfa.recovery.regenerated': 'إنشاء رموز استرداد جديدة',
  'mfa.recovery.regenerate.denied': 'رفض إنشاء رموز استرداد',
  'mfa.recovery.acknowledged': 'حفظ رموز الاسترداد',
  'mfa.audit.export': 'تصدير سجل التحقق بخطوتين',
  // -- Academic / attendance / behaviour / schedule / data ---------
  'academic.grade_recorded': 'تسجيل درجة',
  'academic.grade_updated': 'تعديل درجة',
  'academic.grades_bulk_recorded': 'تسجيل درجات بالجملة',
  'academic.assessment_created': 'إنشاء تقييم',
  'academic.assessment_published': 'نشر تقييم',
  'attendance.recorded': 'تسجيل حضور',
  'attendance.bulk_recorded': 'تسجيل حضور بالجملة',
  'behaviour.note_created': 'ملاحظة سلوكية',
  'behaviour.recorded': 'تسجيل سلوك',
  'schedule.modified': 'تعديل الجدول',
  'schedule.published': 'نشر الجدول',
  'settings.updated': 'تعديل الإعدادات',
  'data.exported': 'تصدير بيانات',
  'data.imported': 'استيراد بيانات',
  // -- Legacy enums kept for backward-compatibility -----------------
  USER_LOGIN: 'تسجيل دخول',
  USER_LOGOUT: 'تسجيل خروج',
  USER_PASSWORD_CHANGED: 'تغيير كلمة المرور',
  USER_MFA_ENABLED: 'تفعيل التحقق بخطوتين',
  USER_MFA_DISABLED: 'تعطيل التحقق بخطوتين',
  DATA_UPDATED: 'تعديل بيانات',
  DATA_CREATED: 'إضافة بيانات',
  DATA_DELETED: 'حذف بيانات',
};

// Pre-compute a lowercase index so callers can resolve a backend
// enum regardless of casing (`mfa.disabled` vs `MFA.DISABLED`) — the
// dictionary itself keeps the canonical key for readability.
const AUDIT_EVENT_FALLBACKS_AR_LOWER = Object.fromEntries(
  Object.entries(AUDIT_EVENT_FALLBACKS_AR).map(([k, v]) => [k.toLowerCase(), v]),
);

function humaniseEnum(raw) {
  if (!raw || typeof raw !== 'string') return raw || '';
  // Lowercase, replace underscores/dots with spaces, then Title-Case
  // each word. Keeps short particles capitalised for readability.
  return raw
    .toLowerCase()
    .split(/[_.\s]+/)
    .filter(Boolean)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// Translate a raw backend audit action into a user-facing Arabic
// string. Lookup order is:
//   1. i18n bundle (key: `auditEvent_<normalised>`) — lets product
//      override a label without a code change.
//   2. FE dictionary (case-insensitive) — authoritative for known
//      enums, beats the backend's destructive humanise.
//   3. Backend-supplied `action_label_ar`, but only if it actually
//      differs from the raw enum (i.e. the backend recognised it).
//   4. Our own humaniseEnum as a last-resort safety net so the table
//      never prints `mfa.disabled` or `INDEPENDENT_TEACHER_…` raw.
//
// Step 3 deliberately rejects the backend's "humanise" fallback by
// comparing against both the raw token and our own humaniseEnum
// output — if they match, the backend didn't actually know the enum
// and we'd rather show the Title-Cased version than something that
// looks like a translation but isn't.
function formatAuditEvent(t, raw, backendLabel) {
  if (!raw && !backendLabel) return '';
  if (!raw) return backendLabel || '';
  const lower = raw.toLowerCase();
  const i18nKey = `auditEvent_${lower.replace(/[.]/g, '_')}`;
  const i18n = t(i18nKey);
  if (i18n && i18n !== i18nKey) return i18n;
  if (AUDIT_EVENT_FALLBACKS_AR_LOWER[lower]) {
    return AUDIT_EVENT_FALLBACKS_AR_LOWER[lower];
  }
  const humanised = humaniseEnum(raw);
  if (
    backendLabel
    && backendLabel !== raw
    && backendLabel !== humanised
    // backend humanise replaces "." with " · " — strip that out before
    // comparing so we recognise its fallback shape too.
    && backendLabel.replace(/\s*·\s*/g, ' ').toLowerCase() !== humanised.toLowerCase()
  ) {
    return backendLabel;
  }
  return humanised;
}

function formatTimestamp(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const hijri = formatHijriDate(d);
    // Natural Arabic Gregorian date — "الثلاثاء، ١٩ مايو". We pass the
    // plain `ar` locale (Gregorian); the project guardrail forbids
    // `ar-SA-u-ca-islamic`, but the standard `ar` locale formats
    // Gregorian dates correctly with Arabic-Indic digits + weekday.
    const gregorian = d.toLocaleDateString('ar', {
      weekday: 'long', day: 'numeric', month: 'long',
    });
    const time = d.toLocaleTimeString('ar-SA', {
      hour: '2-digit', minute: '2-digit',
    });
    return `${gregorian} • ${hijri} — ${time}`;
  } catch {
    return iso;
  }
}

// Convert YYYY-MM-DD (the Gregorian date input value) to a UTC-day
// boundary ISO string suitable for the backend's `from`/`to` query params.
function dayBoundaryIso(value, { endOfDay = false } = {}) {
  if (!value) return null;
  const [y, m, d] = value.split('-').map(n => parseInt(n, 10));
  if (!y || !m || !d) return null;
  const dt = new Date(Date.UTC(
    y, m - 1, d,
    endOfDay ? 23 : 0,
    endOfDay ? 59 : 0,
    endOfDay ? 59 : 0,
    endOfDay ? 999 : 0,
  ));
  return dt.toISOString();
}

// Show the Hijri equivalent under the Gregorian date input as a
// read-only hint — convention used elsewhere in the app (we never
// render Hijri via Intl.DateTimeFormat).
function hijriHintFor(value) {
  if (!value) return '';
  const [y, m, d] = value.split('-').map(n => parseInt(n, 10));
  if (!y || !m || !d) return '';
  try {
    return formatHijriDate(new Date(Date.UTC(y, m - 1, d, 12)));
  } catch {
    return '';
  }
}

// Localised role label for the row header. Falls back to the raw role
// code when no locale key is registered.
function roleLabel(t, role) {
  if (!role) return '';
  const key = `role_${role}`;
  const localised = t(key);
  return localised && localised !== key ? localised : role;
}

// 2026-05-19 — UX refactor: stop rendering raw JSON in the
// "عرض التفاصيل" panel. Filter internal UUID/identifier keys (they
// mean nothing to a teacher), translate the remaining keys to Arabic,
// and format timestamp-shaped values as human-readable date+time.
//
// `formatAuditDetails` returns an ordered array of {key, label, value}
// triplets — empty when the row has no displayable info. The toggle
// button uses `hasDisplayableDetails` (a thin wrapper) to decide
// whether to render the chevron at all, satisfying the spec's
// "hide the button if there's no useful data" requirement.

// Keys we never expose to the teacher: raw UUIDs and other
// internal plumbing. Suffix-based rules catch the broad family
// (`*_id`, `*_uuid`, `*_token`, `*_hash`) without an explicit
// per-key allowlist; the literal set catches the rest.
const _AUDIT_DETAILS_HIDDEN_LITERAL = new Set([
  'id', 'uuid', 'token', 'hash', 'jti', 'trace_id',
  'request_id', 'session_id', 'csrf', 'csrf_token',
  'ip', 'ip_address', 'user_agent', 'sig', 'signature',
  'workspace_id', 'object_id', 'target_id', 'source_id',
  'parent_id', 'child_id', 'related_id',
]);
function _isHiddenAuditKey(key) {
  if (!key || typeof key !== 'string') return true;
  const lower = key.toLowerCase();
  if (_AUDIT_DETAILS_HIDDEN_LITERAL.has(lower)) return true;
  if (lower.endsWith('_id') || lower.endsWith('_uuid')) return true;
  if (lower.endsWith('_token') || lower.endsWith('_hash')) return true;
  return false;
}

// Arabic labels for known meaningful keys. Unknown keys fall through
// to a destructive humanise so the panel never prints raw snake_case.
const AUDIT_DETAILS_LABELS_AR = {
  ttl_hours: 'مدة الصلاحية (ساعات)',
  ttl_minutes: 'مدة الصلاحية (دقائق)',
  ttl: 'مدة الصلاحية',
  expires_at: 'تاريخ الانتهاء',
  expiry: 'تاريخ الانتهاء',
  issued_at: 'تاريخ الإصدار',
  created_at: 'تاريخ الإنشاء',
  updated_at: 'تاريخ التحديث',
  completed_at: 'تاريخ الإكمال',
  started_at: 'تاريخ البداية',
  ended_at: 'تاريخ الانتهاء',
  status: 'الحالة',
  reason: 'السبب',
  note: 'ملاحظة',
  notes: 'ملاحظات',
  message: 'الرسالة',
  file_name: 'اسم الملف',
  filename: 'اسم الملف',
  format: 'الصيغة',
  file_size: 'حجم الملف',
  count: 'العدد',
  total: 'المجموع',
  rows: 'عدد السجلات',
  records: 'عدد السجلات',
  exported_rows: 'عدد السجلات المُصدَّرة',
  email: 'البريد الإلكتروني',
  phone: 'رقم الجوال',
  name: 'الاسم',
  role: 'الدور',
  category: 'التصنيف',
  action: 'الحدث',
  scope: 'النطاق',
  changes: 'التغييرات',
  before: 'القيمة السابقة',
  after: 'القيمة الجديدة',
};

function _looksLikeIso(value) {
  if (typeof value !== 'string') return false;
  // ISO-8601-ish: 2026-05-19T22:22:42... — be generous so we catch
  // both Z-suffixed and offset-suffixed variants.
  return /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value);
}

function _formatAuditDetailValue(value) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'نعم' : 'لا';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') {
    if (_looksLikeIso(value)) {
      const d = new Date(value);
      if (!isNaN(d.getTime())) return formatTimestamp(value);
    }
    return value;
  }
  if (Array.isArray(value)) {
    if (!value.length) return '—';
    return value.map(v => (
      typeof v === 'object' ? JSON.stringify(v) : String(v)
    )).join('، ');
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function _humaniseAuditKey(key) {
  return key
    .replace(/[_.]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, c => c.toUpperCase());
}

function formatAuditDetails(details) {
  if (!details || typeof details !== 'object' || Array.isArray(details)) {
    return [];
  }
  const out = [];
  for (const [key, value] of Object.entries(details)) {
    if (_isHiddenAuditKey(key)) continue;
    if (value === null || value === undefined || value === '') continue;
    if (Array.isArray(value) && value.length === 0) continue;
    if (
      typeof value === 'object'
      && !Array.isArray(value)
      && Object.keys(value).length === 0
    ) continue;
    const label = AUDIT_DETAILS_LABELS_AR[key.toLowerCase()] || _humaniseAuditKey(key);
    out.push({ key, label, value: _formatAuditDetailValue(value) });
  }
  return out;
}

function hasDisplayableDetails(details) {
  return formatAuditDetails(details).length > 0;
}

function DetailsBlock({ details }) {
  const items = formatAuditDetails(details);
  if (!items.length) return null;
  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4 w-full bg-gray-50 border border-gray-200 rounded-md p-4"
      dir="rtl"
    >
      {items.map(({ key, label, value }) => (
        <div key={key} className="flex flex-col min-w-0">
          <span className="text-xs text-gray-500 whitespace-nowrap">{label}</span>
          <span className="text-sm font-medium text-gray-900 break-words">
            {value}
          </span>
        </div>
      ))}
    </div>
  );
}

// 2026-05-18 — the standalone /teacher/audit-log route has been
// relocated into the Account Settings page (tab id `activity`). The
// inner content (header + filters + table) is exported as
// `TeacherAuditLogPanel` so AccountSettingsPage can embed it without
// double-rendering the Sidebar / app chrome. The default export keeps
// the historical route working as a fallback for deep links and is
// also kept available for the page-level snapshot tests.
export function TeacherAuditLogPanel({ embedded = false }) {
  const { api, user } = useAuth();
  const { nassaqError } = useNassaqAlert();
  const { t } = useTranslation();
  const userId = user?.id || null;
  const [logs, setLogs] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [actorInput, setActorInput] = useState('');
  const [actorQuery, setActorQuery] = useState('');
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [csvColumns, setCsvColumnsState] = useState(() => readStoredCsvColumns(userId));
  const [expanded, setExpanded] = useState({});

  // 2026-05-18 — debounce the actor search input so each keystroke
  // doesn't fire a backend round-trip. The explicit "بحث" button still
  // works (and short-circuits the debounce on submit); typing alone
  // now triggers a server refetch after a 400ms idle window.
  useEffect(() => {
    const trimmed = actorInput.trim();
    if (trimmed === actorQuery) return undefined;
    const handle = setTimeout(() => {
      setCursor(null);
      setActorQuery(trimmed);
    }, 400);
    return () => clearTimeout(handle);
  }, [actorInput, actorQuery]);

  const csvPreset = useMemo(() => presetMatching(csvColumns), [csvColumns]);

  // If the authenticated identity changes (e.g. a different teacher
  // signs into the same browser profile), re-read the per-user
  // preference so we never display the previous teacher's choice.
  useEffect(() => {
    setCsvColumnsState(readStoredCsvColumns(userId));
  }, [userId]);

  // Wrapper around setCsvColumns that also persists the new selection
  // for this user. Empty arrays are intentionally NOT persisted — the
  // export button is disabled in that state and there's no value in
  // resurrecting an empty selection on the next visit.
  const setCsvColumns = useCallback((next) => {
    setCsvColumnsState(prev => {
      const value = typeof next === 'function' ? next(prev) : next;
      if (typeof window !== 'undefined' && Array.isArray(value) && value.length) {
        const key = csvColumnsStorageKey(userId);
        if (key) {
          try {
            window.localStorage.setItem(key, JSON.stringify(value));
          } catch {
            // localStorage may be unavailable or full; preference simply
            // won't persist this session.
          }
        }
      }
      return value;
    });
  }, [userId]);

  // Cross-tab sync — if the teacher edits the column selection in
  // another tab, mirror it here so the two tabs don't show conflicting
  // selections. Scoped to this user's key so a different teacher
  // signed into a sibling tab can't overwrite our state.
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const myKey = csvColumnsStorageKey(userId);
    if (!myKey) return undefined;
    const onStorage = (e) => {
      if (e.key !== myKey) return;
      const cols = parseStoredCsvColumns(e.newValue);
      if (cols && cols.length) setCsvColumnsState(cols);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [userId]);

  const onPickPreset = useCallback((value) => {
    if (value === 'custom') return; // custom is read-only; checkboxes drive it
    const next = CSV_COLUMN_PRESETS[value];
    if (next) setCsvColumns(next);
  }, [setCsvColumns]);

  const onToggleColumn = useCallback((key, checked) => {
    setCsvColumns(prev => {
      const set = new Set(prev);
      if (checked) set.add(key); else set.delete(key);
      // Re-order to match _CSV_FIELDS so the FE-side preset match
      // stays stable regardless of toggle order.
      return CSV_ALL_COLUMNS.filter(f => set.has(f));
    });
  }, [setCsvColumns]);

  const errMsg = useMemo(
    () => t('auditLogLoadFailed') || 'تعذّر تحميل سجل النشاط — حاول لاحقًا.',
    [t],
  );
  const exportErrMsg = useMemo(
    () => t('auditLogExportFailed') || 'تعذّر تصدير سجل النشاط — حاول لاحقًا.',
    [t],
  );

  const onDownloadCsv = useCallback(async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const params = {};
      if (activeCategory) params.category = activeCategory;
      const fromIso = dayBoundaryIso(fromDate);
      const toIso = dayBoundaryIso(toDate, { endOfDay: true });
      if (fromIso) params.from = fromIso;
      if (toIso) params.to = toIso;
      // Only attach `columns` when narrowing the set; omitting the
      // param keeps the legacy default behaviour intact. The backend
      // also falls back to the full set on an empty selection, but
      // the FE blocks the export button in that case.
      if (csvColumns.length && !sameColumns(csvColumns, CSV_COLUMN_PRESETS.full)) {
        params.columns = csvColumns.join(',');
      }
      const res = await api.get('/independent-teacher/audit-logs/export.csv', {
        params,
        responseType: 'blob',
      });
      const blob = res?.data instanceof Blob
        ? res.data
        : new Blob([res?.data ?? ''], { type: 'text/csv;charset=utf-8' });
      const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const filename = `audit-log-${stamp}.csv`;
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(href), 0);
    } catch (e) {
      nassaqError(exportErrMsg);
    } finally {
      setExporting(false);
    }
  }, [api, activeCategory, fromDate, toDate, csvColumns, exporting, nassaqError, exportErrMsg]);

  const fetchPage = useCallback(async (opts = {}) => {
    setLoading(true);
    try {
      const params = { limit: PAGE_LIMIT };
      if (opts.category) params.category = opts.category;
      if (opts.cursor) params.cursor = opts.cursor;
      const fromIso = dayBoundaryIso(opts.from);
      const toIso = dayBoundaryIso(opts.to, { endOfDay: true });
      if (fromIso) params.from = fromIso;
      if (toIso) params.to = toIso;
      const actorTerm = (opts.actor || '').trim();
      if (actorTerm) params.actor = actorTerm;
      const res = await api.get('/independent-teacher/audit-logs', { params });
      const data = res?.data || {};
      const next = Array.isArray(data.logs) ? data.logs : [];
      setLogs(prev => (opts.cursor ? [...prev, ...next] : next));
      if (Array.isArray(data.categories) && data.categories.length) {
        setCategories(data.categories);
      }
      setCursor(data.next_cursor || null);
      setHasMore(Boolean(data.next_cursor));
    } catch (e) {
      nassaqError(errMsg);
    } finally {
      setLoading(false);
    }
  }, [api, errMsg, nassaqError]);

  useEffect(() => {
    fetchPage({
      category: activeCategory, from: fromDate, to: toDate, actor: actorQuery,
    });
  }, [activeCategory, fromDate, toDate, actorQuery, fetchPage]);

  const onPickCategory = (key) => {
    setActiveCategory(prev => (prev === key ? '' : key));
    setCursor(null);
  };

  const onLoadMore = () => {
    if (!hasMore || !cursor || loading) return;
    fetchPage({
      category: activeCategory,
      cursor,
      from: fromDate,
      to: toDate,
      actor: actorQuery,
    });
  };

  const onClearDates = () => {
    setFromDate('');
    setToDate('');
    setCursor(null);
  };

  const onSubmitActor = (e) => {
    e.preventDefault();
    setCursor(null);
    setActorQuery(actorInput.trim());
  };

  const onClearActor = () => {
    setActorInput('');
    setActorQuery('');
    setCursor(null);
  };

  const toggleExpanded = (id) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
  };

  // 2026-05-18 — when embedded inside AccountSettingsPage we render the
  // inner content only (the parent already supplies the page chrome
  // + Sidebar). Standalone route mounts the full page layout below.
  return (
    <AuditLogShell embedded={embedded}>
          <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3">
              <History className="w-6 h-6 text-emerald-700" />
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900">
                {t('teacherAuditLogTitle') || 'سجل النشاط'}
              </h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-md border border-input overflow-hidden">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="rounded-none border-0"
                  onClick={onDownloadCsv}
                  disabled={exporting || loading || !csvColumns.length}
                  title={t('downloadCsv') || 'تنزيل CSV'}
                >
                  {exporting
                    ? <Loader2 className="w-4 h-4 ml-2 animate-spin" />
                    : <Download className="w-4 h-4 ml-2" />}
                  {t('downloadCsv') || 'تنزيل CSV'}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="rounded-none border-0 border-r border-input px-2"
                      disabled={exporting || loading}
                      title={t('csvColumnsPickerTitle') || 'اختيار الأعمدة'}
                      aria-label={t('csvColumnsPickerTitle') || 'اختيار الأعمدة'}
                    >
                      <ChevronDown className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-64">
                    <DropdownMenuLabel>
                      {t('csvColumnsPickerTitle') || 'اختيار الأعمدة'}
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuRadioGroup
                      value={csvPreset}
                      onValueChange={onPickPreset}
                    >
                      <DropdownMenuRadioItem value="minimal" onSelect={(e) => e.preventDefault()}>
                        <div className="flex flex-col">
                          <span className="text-sm">
                            {t('csvColumnsMinimal') || 'مختصر — وقت + الحدث + المنفّذ'}
                          </span>
                          <span className="text-xs text-gray-500">
                            {t('csvColumnsMinimalHint') || 'مناسب للمشاركة مع وليّ الأمر'}
                          </span>
                        </div>
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="standard" onSelect={(e) => e.preventDefault()}>
                        <div className="flex flex-col">
                          <span className="text-sm">
                            {t('csvColumnsStandard') || 'قياسي — بدون تفاصيل JSON'}
                          </span>
                          <span className="text-xs text-gray-500">
                            {t('csvColumnsStandardHint') || 'الأعمدة المعتادة بدون الحقل التفصيلي'}
                          </span>
                        </div>
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="full" onSelect={(e) => e.preventDefault()}>
                        <div className="flex flex-col">
                          <span className="text-sm">
                            {t('csvColumnsFull') || 'كامل — جميع الأعمدة'}
                          </span>
                          <span className="text-xs text-gray-500">
                            {t('csvColumnsFullHint') || 'يتضمن حقل التفاصيل (JSON) للأرشفة'}
                          </span>
                        </div>
                      </DropdownMenuRadioItem>
                      <DropdownMenuRadioItem
                        value="custom"
                        disabled
                        onSelect={(e) => e.preventDefault()}
                        className="data-[disabled]:opacity-100"
                      >
                        <div className="flex flex-col">
                          <span className="text-sm">
                            {t('csvColumnsCustom') || 'مخصّص — اختيار يدوي'}
                          </span>
                          <span className="text-xs text-gray-500">
                            {t('csvColumnsCustomHint') || 'يتفعّل تلقائيًا عند تعديل القائمة أدناه'}
                          </span>
                        </div>
                      </DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                    <DropdownMenuSeparator />
                    <DropdownMenuLabel className="flex items-center justify-between gap-2">
                      <span>{t('csvColumnsListTitle') || 'الأعمدة'}</span>
                      <span className="text-xs font-normal text-gray-500">
                        {csvColumns.length}/{CSV_ALL_COLUMNS.length}
                      </span>
                    </DropdownMenuLabel>
                    <div
                      className="max-h-64 overflow-y-auto px-2 pb-2 space-y-1"
                      role="group"
                      aria-label={t('csvColumnsListTitle') || 'الأعمدة'}
                    >
                      {CSV_ALL_COLUMNS.map((key) => {
                        const checked = csvColumns.includes(key);
                        const id = `csv-col-${key}`;
                        return (
                          <label
                            key={key}
                            htmlFor={id}
                            className="flex items-center gap-2 px-2 py-1.5 rounded text-sm cursor-pointer hover:bg-gray-50"
                          >
                            <Checkbox
                              id={id}
                              checked={checked}
                              onCheckedChange={(v) => onToggleColumn(key, v === true)}
                            />
                            <span className="flex-1">
                              {CSV_COLUMN_LABELS_AR[key] || key}
                            </span>
                            <span className="text-[10px] text-gray-400 font-mono" dir="ltr">
                              {key}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                    {!csvColumns.length && (
                      <div className="px-3 pb-2 text-xs text-amber-700">
                        {t('csvColumnsEmpty') || 'اختر عمودًا واحدًا على الأقل لتفعيل التنزيل.'}
                      </div>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fetchPage({
                  category: activeCategory, from: fromDate, to: toDate, actor: actorQuery,
                })}
                disabled={loading}
              >
                <RefreshCw className={`w-4 h-4 ml-2 ${loading ? 'animate-spin' : ''}`} />
                {t('refresh') || 'تحديث'}
              </Button>
            </div>
          </header>

          <p className="text-sm text-gray-600">
            {t('teacherAuditLogIntro')
              || 'سجلّ مرئي للأحداث المهمة في مساحتك (دخول، تصدير، أرشفة، دعوات، تعديلات بيانات). الحقول الحساسة مُخفاة تلقائيًا.'}
          </p>

          {!!categories.length && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onPickCategory('')}
                className={`px-3 py-1 text-sm rounded-full border transition ${
                  activeCategory === ''
                    ? 'bg-emerald-700 text-white border-emerald-700'
                    : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {t('all') || 'الكل'}
              </button>
              {categories.map(c => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => onPickCategory(c.key)}
                  className={`px-3 py-1 text-sm rounded-full border transition ${
                    activeCategory === c.key
                      ? 'bg-emerald-700 text-white border-emerald-700'
                      : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {c.label_ar}
                </button>
              ))}
            </div>
          )}

          <Card>
            <CardContent className="pt-6 space-y-4">
              <div className="grid gap-3 grid-cols-1 sm:grid-cols-[1fr_1fr_auto] items-end">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t('fromDate') || 'من تاريخ'}
                  </label>
                  <Input
                    type="date"
                    value={fromDate}
                    max={toDate || undefined}
                    onChange={e => { setFromDate(e.target.value); setCursor(null); }}
                  />
                  {!!fromDate && (
                    <div className="text-xs text-gray-500 mt-1">
                      {hijriHintFor(fromDate)}
                    </div>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t('toDate') || 'إلى تاريخ'}
                  </label>
                  <Input
                    type="date"
                    value={toDate}
                    min={fromDate || undefined}
                    onChange={e => { setToDate(e.target.value); setCursor(null); }}
                  />
                  {!!toDate && (
                    <div className="text-xs text-gray-500 mt-1">
                      {hijriHintFor(toDate)}
                    </div>
                  )}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onClearDates}
                  disabled={loading || (!fromDate && !toDate)}
                  className="w-full sm:w-auto"
                >
                  {t('clearDates') || 'مسح التواريخ'}
                </Button>
              </div>
              <form
                onSubmit={onSubmitActor}
                className="grid gap-3 grid-cols-1 sm:grid-cols-[1fr_auto_auto] items-end"
              >
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t('teacherAuditLogActorLabel') || 'بحث باسم المنفّذ'}
                  </label>
                  <div className="relative">
                    <Search className="w-4 h-4 text-gray-400 absolute top-1/2 -translate-y-1/2 right-3 pointer-events-none" />
                    <Input
                      type="search"
                      value={actorInput}
                      maxLength={128}
                      placeholder={t('teacherAuditLogActorPlaceholder') || 'جزء من اسم المستخدم…'}
                      onChange={e => setActorInput(e.target.value)}
                      className="pr-9"
                    />
                  </div>
                </div>
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={loading || actorInput.trim() === actorQuery}
                  className="w-full sm:w-auto"
                >
                  {t('search') || 'بحث'}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onClearActor}
                  disabled={loading || (!actorInput && !actorQuery)}
                  className="w-full sm:w-auto"
                >
                  {t('clearSearch') || 'مسح البحث'}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {t('events') || 'الأحداث'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {loading && !logs.length && (
                <div className="flex items-center justify-center py-12 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin ml-2" />
                  {t('loading') || 'جارٍ التحميل…'}
                </div>
              )}

              {!loading && !logs.length && (
                <div className="text-center text-gray-500 py-12">
                  {t('teacherAuditLogEmpty') || 'لا توجد أحداث بعد.'}
                </div>
              )}

              {/* Task #274 — events render through ResponsiveTable so the
                  list is a real `<table>` at sm+ and stacked label/value
                  cards below 640px. Severity badge, action label, actor
                  metadata, and timestamp keep their look in both modes;
                  the per-row "details" toggle stays inline and the
                  expanded JSON panel renders just under the row in either
                  layout. */}
              {!!logs.length && (
                <ResponsiveTable
                  ariaLabel={t('teacherAuditLogTitle') || 'سجل أنشطة مساحة العمل'}
                  rows={logs}
                  getRowKey={(row) => row.id}
                  rowClassName="align-top"
                  // 2026-05-19 — render the expanded details panel as
                  // a full-width sibling row via ResponsiveTable's
                  // renderExpanded hook (colSpan = columns.length) so
                  // the key/value grid uses the entire table width
                  // instead of being squeezed into the action cell.
                  isRowExpanded={(row) => (
                    !!expanded[row.id] && hasDisplayableDetails(row.details)
                  )}
                  renderExpanded={(row) => (
                    <DetailsBlock details={row.details} />
                  )}
                  columns={[
                    {
                      key: 'severity',
                      header: t('severity') || 'الأهمية',
                      cellClassName: 'whitespace-nowrap',
                      render: (row) => (
                        <Badge
                          variant="outline"
                          className={severityClass(row.severity)}
                        >
                          {severityLabel(t, row.severity)}
                        </Badge>
                      ),
                    },
                    {
                      key: 'action',
                      header: t('events') || 'الحدث',
                      primary: true,
                      render: (row) => {
                        const isOpen = !!expanded[row.id];
                        const role = roleLabel(t, row.actor_role);
                        // 2026-05-19 — Hide the "عرض التفاصيل" toggle
                        // entirely when the row has no displayable
                        // details. A row whose `details` only contains
                        // internal IDs (which we strip in
                        // formatAuditDetails) counts as "empty" too,
                        // so the chevron disappears in that case.
                        const showToggle = hasDisplayableDetails(row.details);
                        return (
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-gray-900">
                                {/* 2026-05-19 — Prefer the FE dictionary
                                   over the backend `action_label_ar`
                                   because backend silently falls back
                                   to a destructive humanise of the raw
                                   enum (e.g. `mfa.disabled` → "mfa ·
                                   disabled") for any action it doesn't
                                   recognise, which leaked raw English
                                   into the IT activity log UI. */}
                                {formatAuditEvent(t, row.action, row.action_label_ar)}
                              </span>
                              {(row.actor_name || role) && (
                                <span className="text-xs text-gray-500">
                                  —
                                  {row.actor_name ? ` ${row.actor_name}` : ''}
                                  {role ? (
                                    <span className="ms-1 inline-flex items-center px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 border border-gray-200">
                                      {role}
                                    </span>
                                  ) : null}
                                </span>
                              )}
                              {showToggle && (
                                <button
                                  type="button"
                                  onClick={() => toggleExpanded(row.id)}
                                  className="text-xs text-emerald-700 hover:underline flex items-center gap-1 ms-auto"
                                  aria-expanded={isOpen}
                                >
                                  {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                  {isOpen
                                    ? (t('hideDetails') || 'إخفاء التفاصيل')
                                    : (t('showDetails') || 'عرض التفاصيل')}
                                </button>
                              )}
                            </div>
                            {/* Expanded details panel is rendered as a
                               full-width sibling row by ResponsiveTable
                               via the `renderExpanded` prop (colSpan =
                               columns.length) so the key/value grid is
                               no longer trapped inside this narrow
                               action cell. */}
                          </div>
                        );
                      },
                    },
                    {
                      key: 'when',
                      header: t('when') || 'الوقت',
                      cellClassName: 'whitespace-nowrap text-xs text-gray-500',
                      render: (row) => formatTimestamp(row.timestamp),
                    },
                  ]}
                />
              )}

              {hasMore && (
                <div className="pt-3 flex justify-center">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onLoadMore}
                    disabled={loading}
                  >
                    {loading
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : (t('loadMore') || 'تحميل المزيد')}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
    </AuditLogShell>
  );
}

// Outer shell: standalone route gets Sidebar + main; embedded mode
// (inside AccountSettingsPage) just yields the content unchanged so
// the parent's section card supplies the visual frame.
function AuditLogShell({ embedded, children }) {
  if (embedded) {
    return <div className="space-y-6" data-testid="teacher-audit-log-panel">{children}</div>;
  }
  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-4 sm:p-6 lg:p-10">
        <div className="max-w-5xl mx-auto space-y-6">
          {children}
        </div>
      </main>
    </div>
  );
}

// Default export: the standalone page used by the (legacy) /teacher/
// audit-log route. The Settings tab imports `TeacherAuditLogPanel`
// directly with `embedded={true}` so it inherits the settings shell
// without rendering a second Sidebar.
export default function TeacherAuditLogPage() {
  return <TeacherAuditLogPanel />;
}
