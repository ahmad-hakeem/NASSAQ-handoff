import { Fragment, useCallback, useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { RefreshCw, Trash2, AlertTriangle, ShieldAlert, X, History, ChevronLeft, ChevronRight, Search } from 'lucide-react';

const ARABIC = {
  pageTitle: 'مساحات العمل الجاهزة للحذف النهائي',
  pageSubtitle:
    'مساحات عمل المعلمين المستقلين التي انتهت نافذة الاسترجاع (٣٠ يومًا) وأصبحت جاهزة للحذف النهائي.',
  refresh: 'تحديث',
  empty: 'لا توجد حاليًا أي مساحات عمل جاهزة للحذف النهائي.',
  countLabel: 'عدد المساحات الجاهزة',
  thId: 'معرّف المساحة',
  thName: 'الاسم',
  thArchivedAt: 'تاريخ الأرشفة',
  thLastExport: 'آخر تصدير',
  thAction: 'الإجراء',
  hardDelete: 'حذف نهائي',
  panelTitle: 'تأكيد الحذف النهائي',
  panelIntro:
    'هذا الإجراء لا يمكن التراجع عنه. سيتم حذف جميع بيانات مساحة العمل بشكل نهائي.',
  typeIdHint: 'للتأكيد، اكتب معرّف المساحة كما هو أدناه:',
  inputAriaLabel: 'معرّف التأكيد',
  cancel: 'إلغاء',
  proceed: 'متابعة',
  confirmTitle: 'تأكيد نهائي',
  confirmText: 'حذف نهائي',
  confirmCancel: 'إلغاء',
  confirmBody: (ws) =>
    `سيتم حذف مساحة العمل "${ws.name_ar || ws.name || ws.id}" (${ws.id}) بشكل نهائي ولا يمكن التراجع عن هذه العملية. هل ترغب في المتابعة؟`,
  loadFailed: 'تعذّر تحميل قائمة المساحات الجاهزة للحذف.',
  deleteSuccessTitle: 'تم الحذف بنجاح',
  deleteSuccessBody: (counts, skipped) => {
    const total = Object.values(counts || {}).reduce((s, n) => s + (n || 0), 0);
    const lines = [
      `إجمالي الصفوف المحذوفة: ${total}`,
      '',
      'التفاصيل حسب الجدول:',
      ...Object.entries(counts || {})
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => `• ${k}: ${v}`),
    ];
    if (skipped && skipped.length) {
      lines.push('', 'جداول تم تخطّيها (انجراف في المخطط):');
      skipped.forEach((s) => lines.push(`• ${s}`));
    }
    return lines.join('\n');
  },
  deleteFailed: 'تعذّر تنفيذ الحذف النهائي.',
  pendingBadge: 'بانتظار الحذف',
  notSet: '—',
  tabPending: 'الجاهزة للحذف',
  tabHistory: 'الحذف السابقة',
  historyTitle: 'سجل عمليات الحذف الأخيرة',
  historySubtitle:
    'مساحات العمل التي تم حذفها نهائيًا، مأخوذة من سجل التدقيق.',
  historyEmpty: 'لا توجد عمليات حذف سابقة مسجّلة.',
  historyLoadFailed: 'تعذّر تحميل سجل عمليات الحذف.',
  thPurgedAt: 'تاريخ الحذف',
  thActor: 'المنفّذ',
  thCounts: 'الصفوف المحذوفة',
  totalRows: 'الإجمالي',
  perTable: 'حسب الجدول',
  showDetails: 'عرض التفاصيل',
  hideDetails: 'إخفاء التفاصيل',
  prevPage: 'السابق',
  nextPage: 'التالي',
  page: 'صفحة',
  skippedTablesLabel: 'جداول تم تخطّيها',
  searchPlaceholder: 'ابحث بمعرّف المساحة أو الاسم…',
  searchAria: 'بحث في سجل الحذف',
  fromLabel: 'من تاريخ',
  toLabel: 'إلى تاريخ',
  applyFilters: 'تطبيق',
  clearFilters: 'مسح',
  activeFilters: 'المرشّحات النشطة',
};

const PAGE_SIZE = 25;

const formatDate = (iso) => {
  if (!iso) return ARABIC.notSet;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const yyyy = d.getUTCFullYear();
    const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(d.getUTCDate()).padStart(2, '0');
    const hh = String(d.getUTCHours()).padStart(2, '0');
    const mi = String(d.getUTCMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd} ${hh}:${mi} UTC`;
  } catch (_e) {
    return iso;
  }
};

const safeArabicError = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
};

export const PlatformWorkspacePurgePage = () => {
  const { api } = useAuth();
  useTranslation();
  const { nassaqError, nassaqSuccess, nassaqConfirm } = useNassaqAlert();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [confirmInput, setConfirmInput] = useState('');
  const [submittingId, setSubmittingId] = useState(null);

  const [tab, setTab] = useState('pending');
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyPage, setHistoryPage] = useState(0);
  const [historyExpanded, setHistoryExpanded] = useState(null);
  // Draft values bound to the inputs; "applied" copies are what the
  // request actually uses so typing doesn't re-fire the API on every
  // keystroke.
  const [searchDraft, setSearchDraft] = useState('');
  const [fromDraft, setFromDraft] = useState('');
  const [toDraft, setToDraft] = useState('');
  const [appliedFilters, setAppliedFilters] = useState({ q: '', from: '', to: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get('/platform/workspaces/pending-hard-delete');
      setRows(resp?.data?.workspaces || []);
    } catch (err) {
      nassaqError(safeArabicError(err, ARABIC.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [api, nassaqError]);

  const loadHistory = useCallback(async (page = 0, filters = appliedFilters) => {
    setHistoryLoading(true);
    try {
      const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };
      if (filters.q) params.q = filters.q;
      if (filters.from) params.from = filters.from;
      // Make the "to" date inclusive of the chosen day by advancing one
      // day — the backend uses a strict ``<`` comparison so a raw
      // YYYY-MM-DD would otherwise exclude same-day purges.
      if (filters.to) {
        const d = new Date(`${filters.to}T00:00:00Z`);
        if (!Number.isNaN(d.getTime())) {
          d.setUTCDate(d.getUTCDate() + 1);
          params.to = d.toISOString();
        }
      }
      const resp = await api.get('/platform/workspaces/recent-purges', { params });
      setHistory(resp?.data?.purges || []);
      setHistoryPage(page);
    } catch (err) {
      nassaqError(safeArabicError(err, ARABIC.historyLoadFailed));
    } finally {
      setHistoryLoading(false);
    }
  }, [api, nassaqError, appliedFilters]);

  const applyFilters = useCallback(() => {
    const next = {
      q: searchDraft.trim(),
      from: fromDraft.trim(),
      to: toDraft.trim(),
    };
    setAppliedFilters(next);
    loadHistory(0, next);
  }, [searchDraft, fromDraft, toDraft, loadHistory]);

  const clearFilters = useCallback(() => {
    setSearchDraft('');
    setFromDraft('');
    setToDraft('');
    const next = { q: '', from: '', to: '' };
    setAppliedFilters(next);
    loadHistory(0, next);
  }, [loadHistory]);

  const hasActiveFilters = Boolean(
    appliedFilters.q || appliedFilters.from || appliedFilters.to,
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    // Refetch on every tab activation so a freshly-completed purge
    // shows up without forcing a manual refresh click.
    if (tab === 'history' && !historyLoading) {
      loadHistory(historyPage, appliedFilters);
    }
    // Only fire on tab switch — page changes call loadHistory directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const closePanel = () => {
    if (submittingId) return;
    setExpandedId(null);
    setConfirmInput('');
  };

  const performDelete = useCallback(async (ws) => {
    setSubmittingId(ws.id);
    try {
      const resp = await api.post(
        `/platform/workspaces/${encodeURIComponent(ws.id)}/hard-delete`,
        { confirm_workspace_id: ws.id },
      );
      const data = resp?.data || {};
      setExpandedId(null);
      setConfirmInput('');
      nassaqSuccess(
        ARABIC.deleteSuccessBody(data.deleted_counts || {}, data.skipped_tables || []),
        { title: ARABIC.deleteSuccessTitle },
      );
      load();
    } catch (err) {
      nassaqError(safeArabicError(err, ARABIC.deleteFailed));
    } finally {
      setSubmittingId(null);
    }
  }, [api, nassaqError, nassaqSuccess, load]);

  // The destructive confirm surface is `nassaqConfirm` (NassaqAlertDialog),
  // which is opened only after the admin has typed the workspace id
  // verbatim — that gate lives inline in the row's expanded panel.
  const onProceed = (ws) => {
    if (confirmInput !== ws.id) return;
    nassaqConfirm(
      ARABIC.confirmBody(ws),
      () => performDelete(ws),
      {
        title: ARABIC.confirmTitle,
        confirmText: ARABIC.confirmText,
        cancelText: ARABIC.confirmCancel,
      },
    );
  };

  return (
    <div className="min-h-screen bg-background" data-testid="platform-workspace-purge-page">
      <Sidebar />
      <div className="lg:mr-72 transition-all duration-300">
        <main className="p-4 sm:p-6 lg:p-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-center flex-shrink-0">
                <ShieldAlert className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold font-cairo text-gray-900">
                  {ARABIC.pageTitle}
                </h1>
                <p className="text-sm text-gray-600 font-cairo mt-1 max-w-2xl">
                  {ARABIC.pageSubtitle}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={() => (tab === 'history' ? loadHistory(historyPage, appliedFilters) : load())}
              disabled={tab === 'history' ? historyLoading : loading}
              className="rounded-xl gap-2"
              data-testid="refresh-purge-list"
            >
              <RefreshCw className={`h-4 w-4 ${(tab === 'history' ? historyLoading : loading) ? 'animate-spin' : ''}`} />
              {ARABIC.refresh}
            </Button>
          </div>

          <Tabs value={tab} onValueChange={setTab} className="mb-4">
            <TabsList className="rounded-xl">
              <TabsTrigger value="pending" className="font-cairo gap-2" data-testid="tab-pending-purges">
                <AlertTriangle className="h-4 w-4" />
                {ARABIC.tabPending}
                <Badge variant="secondary" className="ml-1 font-cairo">{rows.length}</Badge>
              </TabsTrigger>
              <TabsTrigger value="history" className="font-cairo gap-2" data-testid="tab-purge-history">
                <History className="h-4 w-4" />
                {ARABIC.tabHistory}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="pending" className="mt-4">

          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="font-cairo text-base flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                {ARABIC.countLabel}
                <Badge variant="secondary" className="ml-2 font-cairo">
                  {rows.length}
                </Badge>
              </CardTitle>
              <CardDescription className="font-cairo">
                {ARABIC.pageSubtitle}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {rows.length === 0 ? (
                <div className="py-10 text-center text-sm text-gray-500 font-cairo">
                  {ARABIC.empty}
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="font-cairo text-right">{ARABIC.thId}</TableHead>
                        <TableHead className="font-cairo text-right">{ARABIC.thName}</TableHead>
                        <TableHead className="font-cairo text-right">{ARABIC.thArchivedAt}</TableHead>
                        <TableHead className="font-cairo text-right">{ARABIC.thLastExport}</TableHead>
                        <TableHead className="font-cairo text-right">{ARABIC.thAction}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((ws) => {
                        const isExpanded = expandedId === ws.id;
                        const matches = isExpanded && confirmInput === ws.id;
                        const submitting = submittingId === ws.id;
                        return (
                          <Fragment key={ws.id}>
                            <TableRow data-testid={`purge-row-${ws.id}`}>
                              <TableCell className="font-mono text-xs">{ws.id}</TableCell>
                              <TableCell className="font-cairo">
                                <div className="flex flex-col">
                                  <span>{ws.name_ar || ws.name || ARABIC.notSet}</span>
                                  {ws.name_en && (
                                    <span className="text-xs text-gray-500">{ws.name_en}</span>
                                  )}
                                </div>
                                <Badge
                                  variant="outline"
                                  className="mt-1 border-red-200 text-red-700 bg-red-50 font-cairo text-[10px]"
                                >
                                  {ARABIC.pendingBadge}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-mono text-xs text-gray-600">
                                {formatDate(ws.archived_at)}
                              </TableCell>
                              <TableCell className="font-mono text-xs text-gray-600">
                                {formatDate(ws.last_export_at)}
                              </TableCell>
                              <TableCell>
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  className="rounded-xl gap-2"
                                  onClick={() => {
                                    setExpandedId(isExpanded ? null : ws.id);
                                    setConfirmInput('');
                                  }}
                                  disabled={submitting}
                                  data-testid={`open-purge-${ws.id}`}
                                >
                                  <Trash2 className="h-4 w-4" />
                                  {ARABIC.hardDelete}
                                </Button>
                              </TableCell>
                            </TableRow>
                            {isExpanded && (
                              <TableRow className="bg-red-50/50">
                                <TableCell colSpan={5} className="p-4">
                                  <div className="rounded-xl border border-red-200 bg-white p-4 space-y-3" dir="rtl">
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="flex items-start gap-2">
                                        <ShieldAlert className="h-5 w-5 text-red-600 mt-0.5" />
                                        <div>
                                          <div className="font-bold font-cairo text-red-700">
                                            {ARABIC.panelTitle}
                                          </div>
                                          <p className="text-sm text-gray-700 font-cairo mt-1">
                                            {ARABIC.panelIntro}
                                          </p>
                                        </div>
                                      </div>
                                      <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={closePanel}
                                        disabled={submitting}
                                        className="rounded-xl"
                                        aria-label={ARABIC.cancel}
                                      >
                                        <X className="h-4 w-4" />
                                      </Button>
                                    </div>
                                    <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-right">
                                      <div className="text-xs text-gray-600 font-cairo mb-1">
                                        {ws.name_ar || ws.name || ARABIC.notSet}
                                      </div>
                                      <div className="font-mono text-sm text-red-700 break-all">
                                        {ws.id}
                                      </div>
                                    </div>
                                    <div>
                                      <Label
                                        htmlFor={`confirm-id-${ws.id}`}
                                        className="font-cairo text-sm"
                                      >
                                        {ARABIC.typeIdHint}
                                      </Label>
                                      <Input
                                        id={`confirm-id-${ws.id}`}
                                        autoFocus
                                        dir="ltr"
                                        className="mt-2 font-mono"
                                        value={confirmInput}
                                        onChange={(e) => setConfirmInput(e.target.value)}
                                        placeholder={ws.id}
                                        disabled={submitting}
                                        data-testid={`confirm-id-input-${ws.id}`}
                                        aria-label={ARABIC.inputAriaLabel}
                                      />
                                    </div>
                                    <div className="flex justify-end gap-2">
                                      <Button
                                        variant="outline"
                                        onClick={closePanel}
                                        disabled={submitting}
                                        className="rounded-xl"
                                      >
                                        {ARABIC.cancel}
                                      </Button>
                                      <Button
                                        variant="destructive"
                                        disabled={!matches || submitting}
                                        onClick={() => onProceed(ws)}
                                        className="rounded-xl gap-2"
                                        data-testid={`proceed-purge-${ws.id}`}
                                      >
                                        {submitting ? (
                                          <RefreshCw className="h-4 w-4 animate-spin" />
                                        ) : (
                                          <>
                                            <Trash2 className="h-4 w-4" />
                                            {ARABIC.proceed}
                                          </>
                                        )}
                                      </Button>
                                    </div>
                                  </div>
                                </TableCell>
                              </TableRow>
                            )}
                          </Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
            </TabsContent>

            <TabsContent value="history" className="mt-4">
              <Card className="rounded-2xl border-0 shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="font-cairo text-base flex items-center gap-2">
                    <History className="h-4 w-4 text-gray-500" />
                    {ARABIC.historyTitle}
                  </CardTitle>
                  <CardDescription className="font-cairo">
                    {ARABIC.historySubtitle}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div
                    className="mb-4 flex flex-col gap-3 rounded-xl border border-gray-200 bg-gray-50/60 p-3 sm:flex-row sm:flex-wrap sm:items-end"
                    dir="rtl"
                  >
                    <div className="flex-1 min-w-[200px]">
                      <Label htmlFor="purge-history-search" className="font-cairo text-xs text-gray-700">
                        {ARABIC.searchAria}
                      </Label>
                      <div className="relative mt-1">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                        <Input
                          id="purge-history-search"
                          dir="rtl"
                          value={searchDraft}
                          onChange={(e) => setSearchDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              applyFilters();
                            }
                          }}
                          placeholder={ARABIC.searchPlaceholder}
                          className="font-cairo pr-9"
                          data-testid="purge-history-search"
                          aria-label={ARABIC.searchAria}
                        />
                      </div>
                    </div>
                    <div className="w-full sm:w-40">
                      <Label htmlFor="purge-history-from" className="font-cairo text-xs text-gray-700">
                        {ARABIC.fromLabel}
                      </Label>
                      <Input
                        id="purge-history-from"
                        type="date"
                        value={fromDraft}
                        onChange={(e) => setFromDraft(e.target.value)}
                        className="mt-1 font-mono"
                        data-testid="purge-history-from"
                      />
                    </div>
                    <div className="w-full sm:w-40">
                      <Label htmlFor="purge-history-to" className="font-cairo text-xs text-gray-700">
                        {ARABIC.toLabel}
                      </Label>
                      <Input
                        id="purge-history-to"
                        type="date"
                        value={toDraft}
                        onChange={(e) => setToDraft(e.target.value)}
                        className="mt-1 font-mono"
                        data-testid="purge-history-to"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        onClick={applyFilters}
                        disabled={historyLoading}
                        className="rounded-xl font-cairo gap-2"
                        data-testid="purge-history-apply"
                      >
                        <Search className="h-4 w-4" />
                        {ARABIC.applyFilters}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={clearFilters}
                        disabled={
                          historyLoading
                          || (!hasActiveFilters && !searchDraft && !fromDraft && !toDraft)
                        }
                        className="rounded-xl font-cairo gap-2"
                        data-testid="purge-history-clear"
                      >
                        <X className="h-4 w-4" />
                        {ARABIC.clearFilters}
                      </Button>
                    </div>
                    {hasActiveFilters && (
                      <div className="flex flex-wrap items-center gap-1 sm:basis-full">
                        <span className="text-xs text-gray-500 font-cairo">{ARABIC.activeFilters}:</span>
                        {appliedFilters.q && (
                          <Badge variant="secondary" className="font-cairo text-[11px]" data-testid="purge-history-active-q">
                            {ARABIC.searchAria}: {appliedFilters.q}
                          </Badge>
                        )}
                        {appliedFilters.from && (
                          <Badge variant="secondary" className="font-cairo text-[11px]">
                            {ARABIC.fromLabel}: {appliedFilters.from}
                          </Badge>
                        )}
                        {appliedFilters.to && (
                          <Badge variant="secondary" className="font-cairo text-[11px]">
                            {ARABIC.toLabel}: {appliedFilters.to}
                          </Badge>
                        )}
                      </div>
                    )}
                  </div>
                  {historyLoading && history.length === 0 ? (
                    <div className="py-10 text-center text-sm text-gray-500 font-cairo">
                      <RefreshCw className="h-5 w-5 animate-spin inline-block ml-2" />
                    </div>
                  ) : history.length === 0 ? (
                    <div className="py-10 text-center text-sm text-gray-500 font-cairo" data-testid="purge-history-empty">
                      {ARABIC.historyEmpty}
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="font-cairo text-right">{ARABIC.thId}</TableHead>
                            <TableHead className="font-cairo text-right">{ARABIC.thName}</TableHead>
                            <TableHead className="font-cairo text-right">{ARABIC.thPurgedAt}</TableHead>
                            <TableHead className="font-cairo text-right">{ARABIC.thActor}</TableHead>
                            <TableHead className="font-cairo text-right">{ARABIC.thCounts}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {history.map((p) => {
                            const totalRows = Object.values(p.deleted_counts || {}).reduce(
                              (s, n) => s + (Number(n) || 0), 0,
                            );
                            const isOpen = historyExpanded === p.id;
                            const snap = p.snapshot || {};
                            return (
                              <Fragment key={p.id}>
                                <TableRow data-testid={`purge-history-row-${p.id}`}>
                                  <TableCell className="font-mono text-xs break-all">
                                    {p.workspace_id || ARABIC.notSet}
                                  </TableCell>
                                  <TableCell className="font-cairo">
                                    <div className="flex flex-col">
                                      <span>{snap.name_ar || snap.name || ARABIC.notSet}</span>
                                      {snap.name_en && (
                                        <span className="text-xs text-gray-500">{snap.name_en}</span>
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell className="font-mono text-xs text-gray-600">
                                    {formatDate(p.purged_at)}
                                  </TableCell>
                                  <TableCell className="font-cairo text-sm">
                                    <div className="flex flex-col">
                                      <span>{p.actor_name || ARABIC.notSet}</span>
                                      {p.actor_email && (
                                        <span className="text-xs text-gray-500 font-mono">{p.actor_email}</span>
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell>
                                    <div className="flex items-center gap-2">
                                      <Badge variant="secondary" className="font-cairo">
                                        {ARABIC.totalRows}: {totalRows}
                                      </Badge>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="rounded-xl font-cairo text-xs"
                                        onClick={() => setHistoryExpanded(isOpen ? null : p.id)}
                                        data-testid={`toggle-purge-details-${p.id}`}
                                      >
                                        {isOpen ? ARABIC.hideDetails : ARABIC.showDetails}
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                                {isOpen && (
                                  <TableRow className="bg-gray-50/70">
                                    <TableCell colSpan={5} className="p-4">
                                      <div className="rounded-xl border border-gray-200 bg-white p-4" dir="rtl">
                                        <div className="font-bold font-cairo text-sm mb-2">
                                          {ARABIC.perTable}
                                        </div>
                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-sm">
                                          {Object.entries(p.deleted_counts || {})
                                            .sort(([a], [b]) => a.localeCompare(b))
                                            .map(([k, v]) => (
                                              <div
                                                key={k}
                                                className="flex justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-1.5 font-mono text-xs"
                                              >
                                                <span className="truncate">{k}</span>
                                                <span className="font-bold text-gray-800">{v}</span>
                                              </div>
                                            ))}
                                        </div>
                                        {p.skipped_tables && p.skipped_tables.length > 0 && (
                                          <div className="mt-3">
                                            <div className="font-bold font-cairo text-xs text-amber-700 mb-1">
                                              {ARABIC.skippedTablesLabel}
                                            </div>
                                            <div className="flex flex-wrap gap-1">
                                              {p.skipped_tables.map((s) => (
                                                <Badge
                                                  key={s}
                                                  variant="outline"
                                                  className="font-mono text-[10px] border-amber-200 text-amber-700 bg-amber-50"
                                                >
                                                  {s}
                                                </Badge>
                                              ))}
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    </TableCell>
                                  </TableRow>
                                )}
                              </Fragment>
                            );
                          })}
                        </TableBody>
                      </Table>

                      <div className="flex items-center justify-between mt-4">
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-xl gap-2 font-cairo"
                          disabled={historyLoading || historyPage === 0}
                          onClick={() => loadHistory(historyPage - 1, appliedFilters)}
                          data-testid="purge-history-prev"
                        >
                          <ChevronRight className="h-4 w-4" />
                          {ARABIC.prevPage}
                        </Button>
                        <div className="font-cairo text-sm text-gray-600">
                          {ARABIC.page} {historyPage + 1}
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-xl gap-2 font-cairo"
                          disabled={historyLoading || history.length < PAGE_SIZE}
                          onClick={() => loadHistory(historyPage + 1, appliedFilters)}
                          data-testid="purge-history-next"
                        >
                          {ARABIC.nextPage}
                          <ChevronLeft className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </main>
      </div>
    </div>
  );
};

export default PlatformWorkspacePurgePage;
