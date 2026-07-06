import { useCallback, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { ResponsiveTable } from '../../components/ui/ResponsiveTable';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, Upload, FileSpreadsheet, CheckCircle, AlertTriangle } from 'lucide-react';
import { getApiErrorMessage } from '../../utils/apiError';

// Phase 2 §6.1 (#207) — workspace-aware bulk student import for IT.
// CSV headers (Arabic-only per spec): الاسم الكامل, رقم الهوية, الجنس, تاريخ الميلاد, الصف.
// No classroom column. /commit is gated server-side by require_recent_mfa_403,
// and the global axios interceptor in AuthContext replays after passkey assertion.
//
// 2026-05-19 — IA refactor: the standalone "استيراد الطلاب" page was
// folded into /teacher/classes as a sub-tab inside "استيراد البيانات".
// The page-level shell (Sidebar + main + page header) was removed and
// the form was extracted into the named `ImportStudentsPanel` export
// so it can be embedded as a sub-tab inside BulkImportPanel without
// rendering a nested page shell. The default export is preserved as a
// thin wrapper so any historical lazy import keeps resolving.

const SAMPLE_HEADERS = ['الاسم الكامل', 'رقم الهوية', 'الجنس', 'تاريخ الميلاد', 'الصف'];

// Per-row verdicts — mirror the School-Admin Noor import (NoorImportPanel).
// A repeated identifier is now skipped per-row instead of blocking the file.
const VERDICT_LABELS = {
  insert: { ar: 'إضافة', cls: 'bg-green-50 text-green-700' },
  update: { ar: 'تحديث', cls: 'bg-blue-50 text-blue-700' },
  restore: { ar: 'استعادة', cls: 'bg-teal-50 text-teal-700' },
  duplicate_in_file: { ar: 'مكرر في الملف', cls: 'bg-red-50 text-red-700' },
  skip: { ar: 'تخطي', cls: 'bg-amber-50 text-amber-700' },
};

const IMPORTABLE_VERDICTS = new Set(['insert', 'update', 'restore']);

function downloadSampleCsv() {
  const sample = [
    SAMPLE_HEADERS.join(','),
    'أحمد محمد العتيبي,1098765432,ذكر,2014-03-12,الثالث الابتدائي',
    'سارة عبدالله القحطاني,,أنثى,,الرابع الابتدائي',
  ].join('\n');
  const blob = new Blob(['\ufeff' + sample], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'nassaq-students-template.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function ImportStudentsPanel() {
  const { api } = useAuth();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  const fileRef = useRef(null);
  const [parsing, setParsing] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [parseResult, setParseResult] = useState(null);
  const [fileName, setFileName] = useState('');

  const handleFile = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setParseResult(null);
    setParsing(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post(
        '/independent-teacher/students/bulk/parse',
        fd,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      setParseResult(res.data);
    } catch (err) {
      const msg = getApiErrorMessage(err) || err?.response?.data?.error?.message ||
        'تعذّر قراءة الملف. تحقّق من الصيغة والأعمدة المطلوبة (CSV أو ملف نور .xls/.xlsx).';
      nassaqError(String(msg), { title: 'فشل التحقق من الملف' });
    } finally {
      setParsing(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }, [api, nassaqError]);

  // Send ALL parsed rows to commit — the server re-derives every verdict
  // against a fresh index, so a stale client value cannot be trusted.
  const allRows = useMemo(() => parseResult?.rows || [], [parseResult]);
  // How many rows the server will actually import (insert/update/restore).
  const importableCount = useMemo(() => {
    if (parseResult?.importable_count != null) return parseResult.importable_count;
    return allRows.filter((r) => IMPORTABLE_VERDICTS.has(r.verdict)).length;
  }, [parseResult, allRows]);

  const doCommit = useCallback(async () => {
    setCommitting(true);
    try {
      const res = await api.post(
        '/independent-teacher/students/bulk/commit',
        { rows: allRows },
      );
      const data = res.data || {};
      const parts = [];
      if (data.inserted) parts.push(`${data.inserted} إضافة`);
      if (data.updated) parts.push(`${data.updated} تحديث`);
      if (data.restored) parts.push(`${data.restored} استعادة`);
      if (data.duplicates) parts.push(`${data.duplicates} مكرر`);
      if (data.skipped) parts.push(`${data.skipped} متجاهَل`);
      const summary = parts.length ? parts.join('، ') : 'لا تغييرات';
      nassaqInfo(summary, { title: 'اكتمل الاستيراد' });
      setParseResult(null);
      setFileName('');
    } catch (err) {
      const msg = getApiErrorMessage(err) || err?.response?.data?.error?.message ||
        'تعذّر إكمال الاستيراد. حاول مرة أخرى لاحقًا.';
      nassaqError(String(msg), { title: 'فشل الاستيراد' });
    } finally {
      setCommitting(false);
    }
  }, [api, allRows, nassaqInfo, nassaqError]);

  const onCommit = useCallback(() => {
    if (!importableCount) return;
    nassaqConfirm(
      `سيتم استيراد ${importableCount} طالبًا (إضافة/تحديث/استعادة) إلى مساحة عملك. هذه العملية نهائية.`,
      doCommit,
      {
        title: 'تأكيد استيراد الطلاب',
        confirmText: 'تأكيد الاستيراد',
        cancelText: 'إلغاء',
      },
    );
  }, [importableCount, nassaqConfirm, doCommit]);

  const quota = parseResult?.quota || {};

  return (
    <div className="space-y-6" data-testid="it-import-students-panel">
      <p className="text-sm text-gray-600">
        استيراد قائمة طلابك من ملف CSV أو ملف Excel من نظام نور (.xls/.xlsx) — بدون تعيين فصول.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileSpreadsheet className="w-5 h-5" /> الخطوة 1 — اختيار الملف
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-gray-600">
            أعمدة قالب CSV:&nbsp;
            <span className="font-mono">{SAMPLE_HEADERS.join(' | ')}</span>
          </p>
          <p className="text-xs text-gray-500">
            أو حمّل تقرير «بيانات الطلاب» من نظام نور كما هو — سيُكتشف تلقائيًا (اسم الطالب، رقم الطالب، الصف، الفصل).
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => fileRef.current?.click()}
              disabled={parsing || committing}
            >
              {parsing ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : <Upload className="w-4 h-4 ml-2" />}
              اختيار ملف (CSV أو نور)
            </Button>
            <Button variant="ghost" onClick={downloadSampleCsv}>
              تنزيل قالب جاهز
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv,.xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="hidden"
              onChange={handleFile}
            />
            {fileName && (
              <span className="text-xs text-gray-500 self-center">{fileName}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {parseResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle className="w-5 h-5" /> الخطوة 2 — مراجعة وتأكيد
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">إجمالي الصفوف: {parseResult.total_rows}</Badge>
              <Badge className="bg-green-100 text-green-800">قابلة للاستيراد: {importableCount}</Badge>
              {(parseResult.verdict_counts?.insert ?? 0) > 0 && (
                <Badge className="bg-green-50 text-green-700">إضافة: {parseResult.verdict_counts.insert}</Badge>
              )}
              {(parseResult.verdict_counts?.update ?? 0) > 0 && (
                <Badge className="bg-blue-50 text-blue-700">تحديث: {parseResult.verdict_counts.update}</Badge>
              )}
              {(parseResult.verdict_counts?.restore ?? 0) > 0 && (
                <Badge className="bg-teal-50 text-teal-700">استعادة: {parseResult.verdict_counts.restore}</Badge>
              )}
              {(parseResult.verdict_counts?.duplicate_in_file ?? 0) > 0 && (
                <Badge className="bg-red-50 text-red-700">مكرر في الملف: {parseResult.verdict_counts.duplicate_in_file}</Badge>
              )}
              {parseResult.invalid_count > 0 && (
                <Badge className="bg-amber-100 text-amber-800">غير صحيحة: {parseResult.invalid_count}</Badge>
              )}
              {quota?.max_students != null && (
                <Badge variant="outline">
                  الطلاب الحاليون: {quota.current_students ?? 0} / {quota.max_students}
                </Badge>
              )}
              {quota?.max_imports_per_day != null && (
                <Badge variant="outline">
                  استيراد اليوم: {quota.imports_today ?? 0} / {quota.max_imports_per_day}
                </Badge>
              )}
            </div>

            <div className="border rounded-md overflow-hidden">
              <ResponsiveTable
                ariaLabel="معاينة الطلاب المستوردين"
                rows={parseResult.rows || []}
                getRowKey={(r) => r.row_number}
                rowClassName=""
                columns={[
                  {
                    key: 'full_name',
                    header: 'الاسم الكامل',
                    primary: true,
                    render: (r) => (
                      <span className={r.is_valid ? '' : 'text-red-700'}>
                        {`#${r.row_number} — ${r.full_name || '—'}`}
                      </span>
                    ),
                  },
                  {
                    key: 'identifier',
                    header: 'المعرّف',
                    render: (r) => r.student_number || r.national_id || '—',
                  },
                  {
                    key: 'gender',
                    header: 'الجنس',
                    render: (r) => (r.gender === 'male' ? 'ذكر' : r.gender === 'female' ? 'أنثى' : '—'),
                  },
                  { key: 'date_of_birth', header: 'تاريخ الميلاد', render: (r) => r.date_of_birth || '—' },
                  { key: 'grade_level', header: 'الصف', render: (r) => r.grade_level || '—' },
                  {
                    key: 'status',
                    header: 'الحالة',
                    render: (r) => {
                      if (!r.is_valid) {
                        return (
                          <span
                            className="inline-flex items-center gap-1 text-red-700"
                            title={(r.errors || []).join('، ')}
                          >
                            <AlertTriangle className="w-4 h-4" /> {(r.errors || [])[0] || 'غير صالح'}
                          </span>
                        );
                      }
                      const label = VERDICT_LABELS[r.verdict] || VERDICT_LABELS.insert;
                      return (
                        <Badge className={label.cls}>{label.ar}</Badge>
                      );
                    },
                  },
                ]}
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => { setParseResult(null); setFileName(''); }}>
                إلغاء
              </Button>
              <Button
                onClick={onCommit}
                disabled={committing || !importableCount}
              >
                {committing && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
                تأكيد الاستيراد ({importableCount})
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Back-compat default export. The standalone route has been retired and
// now redirects to /teacher/classes?tab=import, but downstream code that
// still imports the default keeps working by rendering the panel.
export default function ImportStudentsPage() {
  return <ImportStudentsPanel />;
}
