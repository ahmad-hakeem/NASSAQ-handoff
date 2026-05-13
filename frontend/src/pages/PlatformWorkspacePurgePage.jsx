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
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { RefreshCw, Trash2, AlertTriangle, ShieldAlert, X } from 'lucide-react';

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
};

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

  useEffect(() => {
    load();
  }, [load]);

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
              onClick={load}
              disabled={loading}
              className="rounded-xl gap-2"
              data-testid="refresh-purge-list"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              {ARABIC.refresh}
            </Button>
          </div>

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
        </main>
      </div>
    </div>
  );
};

export default PlatformWorkspacePurgePage;
