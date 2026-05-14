import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Loader2, Upload, FileSpreadsheet, AlertTriangle, CheckCircle2, Database } from 'lucide-react';

const ROLE_LABELS = {
  insert: { ar: 'إضافة', cls: 'bg-green-50 text-green-700 dark:bg-green-950/40' },
  update: { ar: 'تحديث', cls: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40' },
  skip: { ar: 'تخطي', cls: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40' },
};

export default function NoorImportPanel({ api, nassaqError, nassaqWarning, nassaqConfirm, t, onComplete }) {
  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);

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
    } catch (err) {
      nassaqError(err?.response?.data?.detail || 'تعذّر تحليل الملف');
    } finally {
      setParsing(false);
    }
  };

  const onCommit = async () => {
    if (!preview?.import_draft_id) return;
    nassaqConfirm('سيتم الآن تنفيذ عملية الاستيراد. هل تريد المتابعة؟', async () => {
      setCommitting(true);
      try {
        const res = await api.post('/noor-import/commit', { import_draft_id: preview.import_draft_id, confirmations: {} });
        setResult(res.data);
        setPreview(null);
        setFile(null);
        if (onComplete) onComplete();
      } catch (err) {
        nassaqError(err?.response?.data?.detail || 'تعذّر إتمام عملية الاستيراد');
      } finally {
        setCommitting(false);
      }
    });
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
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold">{preview.counts?.total || 0}</p><p className="text-muted-foreground">الإجمالي</p></div>
              <div className="p-2 rounded bg-green-50 dark:bg-green-950/30"><p className="text-lg font-bold text-green-600">{preview.counts?.insert || 0}</p><p className="text-muted-foreground">إضافة</p></div>
              <div className="p-2 rounded bg-blue-50 dark:bg-blue-950/30"><p className="text-lg font-bold text-blue-600">{preview.counts?.update || 0}</p><p className="text-muted-foreground">تحديث</p></div>
              <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/30"><p className="text-lg font-bold text-amber-600">{preview.counts?.skip || 0}</p><p className="text-muted-foreground">تخطي</p></div>
            </div>
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
                    return (
                      <tr key={i} className="border-t">
                        <td className="p-2 text-muted-foreground">{r.row_index}</td>
                        <td className="p-2">{r.data?.full_name || '—'}</td>
                        <td className="p-2 font-mono text-[11px]">{id || '—'}</td>
                        <td className="p-2"><span className={`px-2 py-0.5 rounded text-[11px] ${role.cls}`}>{role.ar}</span></td>
                        <td className="p-2 text-amber-700">
                          {(r.issues || []).length > 0 && <AlertTriangle className="inline h-3 w-3 me-1" />}
                          {(r.issues || []).join('، ')}
                          {r.class_unresolved && <span className="ms-1 text-amber-600">(تعذّر مطابقة الفصل)</span>}
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
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-green-600">{result.imported || 0}</p><p className="text-muted-foreground">تمت الإضافة</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-blue-600">{result.updated || 0}</p><p className="text-muted-foreground">تم التحديث</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-amber-600">{result.skipped || 0}</p><p className="text-muted-foreground">تم التخطي</p></div>
              <div className="p-2 rounded bg-background border"><p className="text-lg font-bold text-red-600">{result.failed || 0}</p><p className="text-muted-foreground">فشل</p></div>
            </div>
            {(result.errors || []).length > 0 && (
              <div className="max-h-[160px] overflow-y-auto space-y-1">
                {result.errors.map((e, i) => (
                  <div key={i} className="text-xs p-2 rounded bg-red-50 dark:bg-red-950/20 text-red-600">صف {e.row}: {e.message}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
