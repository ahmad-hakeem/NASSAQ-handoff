import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, History, RefreshCw, ChevronDown, ChevronUp, Search, Download } from 'lucide-react';
import { formatHijriDate } from '../../utils/hijriDate';
import { useTranslation } from '../../contexts/ThemeContext';

// Task #248 — IT workspace audit-log view (read-only).
// Backend pins school_id == itw_{user_id} on every read, strips
// sensitive keys from `details`, and returns 404 for cross-workspace
// ids per spec §8 inv. 3. Permission gate: `audit.read_own_workspace`.

const PAGE_LIMIT = 25;

function severityClass(sev) {
  switch ((sev || '').toLowerCase()) {
    case 'critical': return 'bg-red-100 text-red-800 border-red-200';
    case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
    case 'medium': return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'low': return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    default: return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

function formatTimestamp(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const hijri = formatHijriDate(d);
    const time = d.toLocaleTimeString('ar-SA', {
      hour: '2-digit', minute: '2-digit',
    });
    return `${hijri} — ${time}`;
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

export default function TeacherAuditLogPage() {
  const { api } = useAuth();
  const { nassaqError } = useNassaqAlert();
  const { t } = useTranslation();
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
  const [expanded, setExpanded] = useState({});

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
  }, [api, activeCategory, fromDate, toDate, exporting, nassaqError, exportErrMsg]);

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

  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6 lg:p-10">
        <div className="max-w-5xl mx-auto space-y-6">
          <header className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <History className="w-6 h-6 text-emerald-700" />
              <h1 className="text-2xl font-bold text-gray-900">
                {t('teacherAuditLogTitle') || 'سجل النشاط'}
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onDownloadCsv}
                disabled={exporting || loading}
                title={t('downloadCsv') || 'تنزيل CSV'}
              >
                {exporting
                  ? <Loader2 className="w-4 h-4 ml-2 animate-spin" />
                  : <Download className="w-4 h-4 ml-2" />}
                {t('downloadCsv') || 'تنزيل CSV'}
              </Button>
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
              <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] items-end">
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
                >
                  {t('clearDates') || 'مسح التواريخ'}
                </Button>
              </div>
              <form
                onSubmit={onSubmitActor}
                className="grid gap-4 sm:grid-cols-[1fr_auto_auto] items-end"
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
                >
                  {t('search') || 'بحث'}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onClearActor}
                  disabled={loading || (!actorInput && !actorQuery)}
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

              {logs.map(row => {
                const isOpen = !!expanded[row.id];
                const role = roleLabel(t, row.actor_role);
                return (
                  <div
                    key={row.id}
                    className="border border-gray-200 rounded-lg p-3 hover:bg-gray-50 transition"
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <Badge
                        variant="outline"
                        className={severityClass(row.severity)}
                      >
                        {row.severity}
                      </Badge>
                      <span className="font-semibold text-gray-900">
                        {row.action_label_ar || row.action}
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
                      <span className="ms-auto text-xs text-gray-500">
                        {formatTimestamp(row.timestamp)}
                      </span>
                      <button
                        type="button"
                        onClick={() => toggleExpanded(row.id)}
                        className="text-xs text-emerald-700 hover:underline flex items-center gap-1"
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
              })}

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
        </div>
      </main>
    </div>
  );
}
