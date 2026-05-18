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

// 2026-05-18 — translate a raw backend event enum (e.g.
// "INDEPENDENT_TEACHER_EXPORT_EXCEL") into a user-friendly Arabic
// string when the backend didn't populate `action_label_ar`. The
// first lookup is the i18n bundle (key: `auditEvent_<lowercase>`);
// the dictionary below is the in-code fallback for the common events;
// finally, an unknown enum is humanised by Title-Casing the snake_case
// token so the table never displays raw ALL_CAPS strings.
const AUDIT_EVENT_FALLBACKS_AR = {
  INDEPENDENT_TEACHER_EXPORT_EXCEL: 'تصدير بيانات المعلم إلى إكسيل',
  INDEPENDENT_TEACHER_EXPORT_CSV: 'تصدير بيانات المعلم إلى CSV',
  INDEPENDENT_TEACHER_EXPORT: 'تصدير بيانات مساحة العمل',
  INDEPENDENT_TEACHER_WORKSPACE_ARCHIVE: 'أرشفة مساحة العمل',
  INDEPENDENT_TEACHER_WORKSPACE_REACTIVATE: 'إعادة تنشيط مساحة العمل',
  INDEPENDENT_TEACHER_INVITE_PARENT: 'دعوة وليّ أمر',
  INDEPENDENT_TEACHER_INVITE_COLLABORATOR: 'دعوة معلم متعاون',
  USER_LOGIN: 'تسجيل دخول',
  USER_LOGOUT: 'تسجيل خروج',
  USER_PASSWORD_CHANGED: 'تغيير كلمة المرور',
  USER_MFA_ENABLED: 'تفعيل التحقق الثنائي',
  USER_MFA_DISABLED: 'إلغاء التحقق الثنائي',
  DATA_UPDATED: 'تعديل بيانات',
  DATA_CREATED: 'إضافة بيانات',
  DATA_DELETED: 'حذف بيانات',
};

function humaniseEnum(raw) {
  if (!raw || typeof raw !== 'string') return raw || '';
  // Lowercase, replace underscores with spaces, then Title-Case each
  // word. Keeps short particles capitalised for readability.
  return raw
    .toLowerCase()
    .split(/[_\s]+/)
    .filter(Boolean)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatAuditEvent(t, raw) {
  if (!raw) return '';
  const i18n = t(`auditEvent_${raw.toLowerCase()}`);
  if (i18n && i18n !== `auditEvent_${raw.toLowerCase()}`) return i18n;
  if (AUDIT_EVENT_FALLBACKS_AR[raw]) return AUDIT_EVENT_FALLBACKS_AR[raw];
  return humaniseEnum(raw);
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

function DetailsBlock({ details }) {
  if (!details || typeof details !== 'object') return null;
  const entries = Object.entries(details);
  if (!entries.length) return null;
  return (
    <pre className="mt-2 text-xs bg-gray-50 border border-gray-200 rounded p-3 overflow-x-auto whitespace-pre-wrap leading-relaxed">
      {JSON.stringify(details, null, 2)}
    </pre>
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
                        return (
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-gray-900">
                                {row.action_label_ar || formatAuditEvent(t, row.action)}
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
                              <button
                                type="button"
                                onClick={() => toggleExpanded(row.id)}
                                className="text-xs text-emerald-700 hover:underline flex items-center gap-1 ms-auto"
                              >
                                {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                {isOpen
                                  ? (t('hideDetails') || 'إخفاء التفاصيل')
                                  : (t('showDetails') || 'عرض التفاصيل')}
                              </button>
                            </div>
                            {isOpen && <DetailsBlock details={row.details} />}
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
