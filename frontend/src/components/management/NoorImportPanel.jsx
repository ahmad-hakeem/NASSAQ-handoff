import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Loader2, Upload, FileSpreadsheet, AlertTriangle, CheckCircle2, Database, Download } from 'lucide-react';

const ROLE_LABELS = {
  insert: { ar: 'إضافة', cls: 'bg-green-50 text-green-700 dark:bg-green-950/40' },
  update: { ar: 'تحديث', cls: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40' },
  skip: { ar: 'تخطي', cls: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40' },
  ambiguous: { ar: 'مطابقة غير مؤكدة', cls: 'bg-orange-50 text-orange-700 dark:bg-orange-950/40' },
  duplicate_in_file: { ar: 'مكرر في الملف', cls: 'bg-red-50 text-red-700 dark:bg-red-950/40' },
};

function csvEscape(v) {
  const s = (v == null ? '' : String(v));
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadCsv(filename, rows) {
  if (!rows || rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const body = [headers.join(','), ...rows.map(r => headers.map(h => csvEscape(r[h])).join(','))].join('\n');
  const blob = new Blob(['\uFEFF' + body], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function NoorImportPanel({ api, nassaqError, nassaqWarning, nassaqConfirm, nassaqInfo, t, onComplete }) {
  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [ambiguousAccept, setAmbiguousAccept] = useState({}); // { row_index: true }

  const ambiguousRowIndexes = useMemo(
    () => (preview?.rows || []).filter(r => r.dedupe === 'ambiguous').map(r => r.row_index),
    [preview],
  );

  const onSelect = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!['.xlsx', '.xls'].some(ext => f.name.toLowerCase().endsWith(ext))) {
      nassaqWarning('نوع الملف غير مدعوم — استخدم Excel (.xlsx أو .xls)');
      return;
    }
    setFile(f);
    setPreview(null);
    setResult(null);
    setAmbiguousAccept({});
  };

  const onParse = async () => {
    if (!file) { nassaqWarning('اختر ملفاً أولاً'); return; }
    setParsing(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/noor-import/parse', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setPreview(res.data);
      setAmbiguousAccept({});
    } catch (err) {
      nassaqError(err?.response?.data?.detail || 'تعذّر تحليل الملف');
    } finally {
      setParsing(false);
    }
  };

  const doCommit = async () => {
      setCommitting(true);
      try {
        const ambiguous_treat_as_new = Object.entries(ambiguousAccept)
          .filter(([, v]) => v)
          .map(([k]) => Number(k));
        const res = await api.post('/noor-import/commit', {
          import_draft_id: preview.import_draft_id,
          confirmations: { ambiguous_treat_as_new },
        });
        const data = res.data;
        setResult(data);
        setPreview(null);
        setFile(null);
        setAmbiguousAccept({});
        const creds = data.credentials_csv || [];
        const dupPart = (data.duplicates || 0) > 0 ? `، مكرر في الملف ${data.duplicates}` : '';
        const unclPart = (data.unclassified || 0) > 0 ? `، بدون فصل ${data.unclassified}` : '';
        const summary = `اكتمل الاستيراد: تمت الإضافة ${data.imported || 0}، تم التحديث ${data.updated || 0}، تم التخطي ${data.skipped || 0}، فشل ${data.failed || 0}${dupPart}${unclPart}.`;
        if (creds.length > 0 && nassaqInfo) {
          nassaqInfo(
            `${summary}\nتم إنشاء ${creds.length} حساب معلّم — يمكنك تنزيل بيانات الدخول الآن، لن يتم عرضها مرة أخرى.`,
            { confirmText: 'تنزيل CSV', onConfirm: () => downloadCsv(`noor_import_credentials_${Date.now()}.csv`, creds) },
          );
        } else if (nassaqInfo) {
          nassaqInfo(summary);
        }
        if (onComplete) onComplete();
      } catch (err) {
        nassaqError(err?.response?.data?.detail || 'تعذّر إتمام عملية الاستيراد');
      } finally {
        setCommitting(false);
      }
  };

  const onCommit = () => {
    if (!preview?.import_draft_id) return;
    const unclassified = preview?.counts?.unclassified || 0;
    if (unclassified > 0) {
      nassaqConfirm(
        `سيتم استيراد ${unclassified} صفاً بدون ربطه بفصل دراسي (تعذّر مطابقة الفصل). يمكنك إنشاء الفصول أولاً ثم إعادة الاستيراد لربط الطلاب تلقائياً، أو المتابعة الآن وربطهم لاحقاً يدوياً.`,
        doCommit,
        { title: 'تأكيد الاستيراد بدون فصل', confirmText: 'أكمل بدون فصل', cancelText: 'إلغاء' },
      );
      return;
    }
    nassaqConfirm('سيتم الآن تنفيذ عملية الاستيراد. هل تريد المتابعة؟', doCommit);
  };

  const detectedLabel = preview?.detected_type === 'teachers' ? 'تقرير المعلمين (نور)' : preview?.detected_type === 'students' ? 'إرشاد الطلاب (نور)' : '';

  return (
    <Card className="mb-2 border-brand-turquoise/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Database className="h-5 w-5 text-brand-turquoise" />استيراد من نظام نور</CardTitle>
        <CardDescription>ارفع تقرير نور كما هو دون تعديل — سيتم اكتشاف نوع التقرير ومعاينته قبل التنفيذ.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Input type="file" accept=".xlsx,.xls" onChange={onSelect} className="max-w-sm" />
          {file && <Badge variant="outline">{file.name}</Badge>}
          <Button onClick={onParse} disabled={parsing || !file} type="button">
            {parsing ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <FileSpreadsheet className="h-4 w-4 me-2" />}
            معاينة
          </Button>
        </div>

        {preview && (
          <div className="space-y-3 border rounded-xl p-4 bg-muted/30">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge className="bg-brand-turquoise/15 text-brand-turquoise">{detectedLabel}</Badge>
              <span className="text-muted-foreground">صف العناوين: {preview.header_row}</span>
              {preview.sheet_name && <span className="text-muted-foreground">| الورقة: {preview.sheet_name}</span>}
            </div>
            <div className="grid grid-cols-4 md:grid-cols-7 gap-2 text-center text-xs">
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold">{preview.counts?.total || 0}</p><p className="text-muted-foreground">الإجمالي</p></div>
              <div className="p-2 rounded bg-green-50 dark:bg-green-950/30" data-testid="bucket-insert"><p className="text-lg font-bold text-green-600">{preview.counts?.insert || 0}</p><p className="text-muted-foreground">جاهز للإضافة</p></div>
              <div className="p-2 rounded bg-blue-50 dark:bg-blue-950/30" data-testid="bucket-update"><p className="text-lg font-bold text-blue-600">{preview.counts?.update || 0}</p><p className="text-muted-foreground">تحديث الموجود</p></div>
              <div className="p-2 rounded bg-red-50 dark:bg-red-950/30" data-testid="bucket-duplicate"><p className="text-lg font-bold text-red-600">{preview.counts?.duplicate_in_file || 0}</p><p className="text-muted-foreground">مكرر في الملف (سيتم تجاهله)</p></div>
              <div className="p-2 rounded bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-300" data-testid="bucket-unclassified"><p className="text-lg font-bold text-yellow-700">{preview.counts?.unclassified || 0}</p><p className="text-muted-foreground">بدون فصل</p></div>
              <div className="p-2 rounded bg-orange-50 dark:bg-orange-950/30"><p className="text-lg font-bold text-orange-600">{preview.counts?.ambiguous || 0}</p><p className="text-muted-foreground">غير مؤكد</p></div>
              <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/30"><p className="text-lg font-bold text-amber-600">{preview.counts?.skip || 0}</p><p className="text-muted-foreground">تخطي</p></div>
            </div>
            {(preview.counts?.unclassified || 0) > 0 && (
              <div
                data-testid="unclassified-banner"
                className="sticky top-0 z-10 text-xs p-3 rounded border border-yellow-400 bg-yellow-50 dark:bg-yellow-950/30 text-yellow-900 dark:text-yellow-100 flex items-start gap-2"
              >
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <div>
                  <p className="font-medium">سيتم استيراد {preview.counts.unclassified} صفاً بدون ربطه بفصل دراسي.</p>
                  <p className="text-yellow-800 dark:text-yellow-200 mt-0.5">
                    تعذّر مطابقة قيم "رقم الصف" / "الفصل" في الملف مع فصول المدرسة الحالية. أنشئ الفصول المناسبة في إدارة الفصول ثم أعد الاستيراد لربط الطلاب تلقائياً.
                  </p>
                </div>
              </div>
            )}
            {ambiguousRowIndexes.length > 0 && (
              <div className="text-xs p-2 rounded bg-orange-50 dark:bg-orange-950/20 text-orange-800 dark:text-orange-200">
                توجد {ambiguousRowIndexes.length} مطابقة غير مؤكدة — فعّل الخانة لكل صف تريد معالجته كصف جديد، وإلا سيتم تخطيه.
              </div>
            )}
            <div className="max-h-[280px] overflow-y-auto border rounded">
              <table className="w-full text-xs">
                <thead className="bg-muted sticky top-0"><tr>
                  <th className="p-2 text-start">#</th>
                  <th className="p-2 text-start">الاسم</th>
                  <th className="p-2 text-start">المعرّف</th>
                  <th className="p-2 text-start">الإجراء</th>
                  <th className="p-2 text-start">ملاحظات</th>
                </tr></thead>
                <tbody>
                  {(preview.rows || []).slice(0, 200).map((r, i) => {
                    const role = ROLE_LABELS[r.dedupe] || ROLE_LABELS.skip;
                    const id = r.data?.national_id || r.data?.student_number || '';
                    const isAmb = r.dedupe === 'ambiguous';
                    return (
                      <tr key={i} className="border-t">
                        <td className="p-2 text-muted-foreground">{r.row_index}</td>
                        <td className="p-2">{r.data?.full_name || '—'}</td>
                        <td className="p-2 font-mono text-[11px]">{id || '—'}</td>
                        <td className="p-2">
                          <span className={`px-2 py-0.5 rounded text-[11px] ${role.cls}`}>{role.ar}</span>
                          {isAmb && (
                            <label className="ms-2 inline-flex items-center gap-1 text-[11px] cursor-pointer">
                              <input
                                type="checkbox"
                                checked={!!ambiguousAccept[r.row_index]}
                                onChange={(e) => setAmbiguousAccept(s => ({ ...s, [r.row_index]: e.target.checked }))}
                              />
                              معالجة كصف جديد
                            </label>
                          )}
                        </td>
                        <td className="p-2 text-amber-700">
                          {(r.issues || []).length > 0 && <AlertTriangle className="inline h-3 w-3 me-1" />}
                          {(r.issues || []).join('، ')}
                          {r.class_unresolved && <span className="ms-1 text-amber-600">(تعذّر مطابقة الفصل)</span>}
                          {r.student_number_generated && <span className="ms-1 text-blue-600">(رقم داخلي مُولّد)</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end">
              <Button onClick={onCommit} disabled={committing} type="button" className="bg-brand-turquoise hover:bg-brand-turquoise/90">
                {committing ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Upload className="h-4 w-4 me-2" />}
                تنفيذ الاستيراد
              </Button>
            </div>
          </div>
        )}

        {result && (
          <div className="border rounded-xl p-4 bg-green-50/40 dark:bg-green-950/10 space-y-2">
            <div className="flex items-center gap-2 font-medium text-green-700"><CheckCircle2 className="h-5 w-5" />اكتمل الاستيراد</div>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-center text-xs">
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-green-600">{result.imported || 0}</p><p className="text-muted-foreground">تمت الإضافة</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-blue-600">{result.updated || 0}</p><p className="text-muted-foreground">تم التحديث</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-red-700">{result.duplicates || 0}</p><p className="text-muted-foreground">مكرر في الملف (تم تجاهله)</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-yellow-700">{result.unclassified || 0}</p><p className="text-muted-foreground">حُفظ بدون فصل</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-amber-600">{result.skipped || 0}</p><p className="text-muted-foreground">تم التخطي</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-red-600">{result.failed || 0}</p><p className="text-muted-foreground">فشل</p></div>
            </div>
            {(result.credentials_csv || []).length > 0 && (
              <div className="flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() => downloadCsv(`noor_import_credentials_${Date.now()}.csv`, result.credentials_csv)}
                >
                  <Download className="h-4 w-4 me-2" />
                  تنزيل بيانات الدخول ({result.credentials_csv.length})
                </Button>
              </div>
            )}
            {(result.errors || []).length > 0 && (
              <div className="max-h-[160px] overflow-y-auto space-y-1">
                {result.errors.slice(0, 50).map((e, i) => (
                  <div key={i} className="text-xs p-2 rounded bg-red-50 dark:bg-red-950/20 text-red-600">صف {e.row}: {e.message}</div>
                ))}
                {result.errors.length > 50 && (
                  <div className="text-[11px] text-muted-foreground p-2">
                    عرض أول 50 خطأ من أصل {result.errors.length}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
