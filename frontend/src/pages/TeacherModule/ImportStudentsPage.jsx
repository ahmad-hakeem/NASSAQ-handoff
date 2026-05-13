import { useCallback, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, Upload, FileSpreadsheet, CheckCircle, AlertTriangle } from 'lucide-react';

// Phase 2 §6.1 (#207) — workspace-aware bulk student import for IT.
// CSV headers (Arabic-only per spec): الاسم الكامل, رقم الهوية, الجنس, تاريخ الميلاد, الصف.
// No classroom column. /commit is gated server-side by require_recent_mfa_403,
// and the global axios interceptor in AuthContext replays after passkey assertion.

const SAMPLE_HEADERS = ['الاسم الكامل', 'رقم الهوية', 'الجنس', 'تاريخ الميلاد', 'الصف'];

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

export default function ImportStudentsPage() {
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
      const msg = err?.response?.data?.detail || err?.response?.data?.error?.message ||
        'تعذّر قراءة الملف. تحقّق من الصيغة والأعمدة المطلوبة.';
      nassaqError(String(msg), { title: 'فشل التحقق من الملف' });
    } finally {
      setParsing(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }, [api, nassaqError]);

  const validRows = useMemo(
    () => (parseResult?.rows || []).filter((r) => r.is_valid),
    [parseResult],
  );

  const doCommit = useCallback(async () => {
    setCommitting(true);
    try {
      const res = await api.post(
        '/independent-teacher/students/bulk/commit',
        { rows: validRows },
      );
      const data = res.data || {};
      nassaqInfo(
        `تمت إضافة ${data.inserted ?? 0} طالبًا. (${data.skipped ?? 0} صف مُتجاهَل)`,
        { title: 'اكتمل الاستيراد' },
      );
      setParseResult(null);
      setFileName('');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.error?.message ||
        'تعذّر إكمال الاستيراد. حاول مرة أخرى لاحقًا.';
      nassaqError(String(msg), { title: 'فشل الاستيراد' });
    } finally {
      setCommitting(false);
    }
  }, [api, validRows, nassaqInfo, nassaqError]);

  const onCommit = useCallback(() => {
    if (!validRows.length) return;
    nassaqConfirm(
      `سيتم إضافة ${validRows.length} طالبًا إلى مساحة عملك. هذه العملية نهائية.`,
      doCommit,
      {
        title: 'تأكيد استيراد الطلاب',
        confirmText: 'تأكيد الاستيراد',
        cancelText: 'إلغاء',
      },
    );
  }, [validRows, nassaqConfirm, doCommit]);

  const quota = parseResult?.quota || {};

  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6 space-y-6 max-w-5xl mx-auto">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold text-gray-900">استيراد الطلاب</h1>
          <p className="text-sm text-gray-600">
            استيراد قائمة طلابك من ملف CSV — الأعمدة باللغة العربية فقط، بدون تعيين فصول.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileSpreadsheet className="w-5 h-5" /> الخطوة 1 — اختيار الملف
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-gray-600">
              الأعمدة المتوقعة:&nbsp;
              <span className="font-mono">{SAMPLE_HEADERS.join(' | ')}</span>
            </p>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={() => fileRef.current?.click()}
                disabled={parsing || committing}
              >
                {parsing ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : <Upload className="w-4 h-4 ml-2" />}
                اختيار ملف CSV
              </Button>
              <Button variant="ghost" onClick={downloadSampleCsv}>
                تنزيل قالب جاهز
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,text/csv"
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
                <Badge className="bg-green-100 text-green-800">صحيحة: {parseResult.valid_count}</Badge>
                <Badge className="bg-red-100 text-red-800">غير صحيحة: {parseResult.invalid_count}</Badge>
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
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 text-gray-700">
                    <tr>
                      <th className="p-2 text-right">#</th>
                      <th className="p-2 text-right">الاسم الكامل</th>
                      <th className="p-2 text-right">رقم الهوية</th>
                      <th className="p-2 text-right">الجنس</th>
                      <th className="p-2 text-right">تاريخ الميلاد</th>
                      <th className="p-2 text-right">الصف</th>
                      <th className="p-2 text-right">الحالة</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(parseResult.rows || []).map((r) => (
                      <tr key={r.row_number} className={r.is_valid ? '' : 'bg-red-50'}>
                        <td className="p-2">{r.row_number}</td>
                        <td className="p-2">{r.full_name || '—'}</td>
                        <td className="p-2">{r.national_id || '—'}</td>
                        <td className="p-2">{r.gender === 'male' ? 'ذكر' : r.gender === 'female' ? 'أنثى' : '—'}</td>
                        <td className="p-2">{r.date_of_birth || '—'}</td>
                        <td className="p-2">{r.grade_level || '—'}</td>
                        <td className="p-2">
                          {r.is_valid ? (
                            <span className="inline-flex items-center gap-1 text-green-700">
                              <CheckCircle className="w-4 h-4" /> جاهز
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-red-700" title={(r.errors || []).join('، ')}>
                              <AlertTriangle className="w-4 h-4" /> {(r.errors || [])[0] || 'غير صالح'}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => { setParseResult(null); setFileName(''); }}>
                  إلغاء
                </Button>
                <Button
                  onClick={onCommit}
                  disabled={committing || !validRows.length}
                >
                  {committing && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
                  تأكيد الاستيراد ({validRows.length})
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
