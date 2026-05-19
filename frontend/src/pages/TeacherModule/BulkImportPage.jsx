import { useCallback, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import { ResponsiveTable } from '../../components/ui/ResponsiveTable';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Loader2, Upload, FileSpreadsheet, CheckCircle, AlertTriangle,
  Users, Layers, BookOpen, Calendar,
} from 'lucide-react';
// 2026-05-19 — IA refactor: import the headless panel directly so the
// students sub-tab no longer renders a nested Sidebar + main shell via
// the old `[&_aside]:hidden` CSS hack. ImportStudentsPage still exports
// a default for back-compat, but we want the clean panel surface here.
import { ImportStudentsPanel } from './ImportStudentsPage';

// Task #278 — IT bulk-import hub with four tabs (students / classes /
// subjects / duplicate-week). Re-uses the existing students importer
// for the first tab; the other three call the §6.1 sibling endpoints
// added in independent_teacher_bulk_extensions_routes.py.
//
// All errors / confirmations go through NassaqAlertDialog; native
// alert/confirm/toast are forbidden by the project's user prefs.

const STUDENT_HEADERS = ['الاسم الكامل', 'رقم الهوية', 'الجنس', 'تاريخ الميلاد', 'الصف'];
const CLASS_HEADERS = ['اسم الفصل', 'المرحلة', 'المادة الافتراضية'];
const SUBJECT_HEADERS = ['اسم المادة', 'الكود'];

function downloadCsv(filename, headers, sampleRows = []) {
  const content = [headers.join(','), ...sampleRows.map((r) => r.join(','))].join('\n');
  const blob = new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function CsvImportPanel({
  api, nassaqError, nassaqInfo, nassaqConfirm,
  parseUrl, commitUrl,
  headers, templateName, sampleRows,
  intro, columnsRender, previewColumns,
  successPrefix, confirmPrefixFn,
  quotaBadgesFn,
  ariaLabel,
}) {
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
      const res = await api.post(parseUrl, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setParseResult(res.data);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.error?.message ||
        'تعذّر قراءة الملف. تحقّق من الصيغة والأعمدة المطلوبة.';
      nassaqError(String(msg), { title: 'فشل التحقق من الملف' });
    } finally {
      setParsing(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }, [api, parseUrl, nassaqError]);

  const validRows = useMemo(
    () => (parseResult?.rows || []).filter((r) => r.is_valid),
    [parseResult],
  );

  const doCommit = useCallback(async () => {
    setCommitting(true);
    try {
      const res = await api.post(commitUrl, { rows: validRows });
      const data = res.data || {};
      nassaqInfo(
        `${successPrefix} ${data.inserted ?? 0} (${data.skipped ?? 0} مُتجاهَل)`,
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
  }, [api, commitUrl, validRows, nassaqInfo, nassaqError, successPrefix]);

  const onCommit = useCallback(() => {
    if (!validRows.length) return;
    nassaqConfirm(
      confirmPrefixFn(validRows.length),
      doCommit,
      { title: 'تأكيد الاستيراد', confirmText: 'تأكيد', cancelText: 'إلغاء' },
    );
  }, [validRows, nassaqConfirm, doCommit, confirmPrefixFn]);

  const quota = parseResult?.quota || {};

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <FileSpreadsheet className="w-5 h-5" /> الخطوة 1 — اختيار الملف
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {intro}
          <p className="text-sm text-gray-600">
            الأعمدة المتوقعة:&nbsp;
            <span className="font-mono">{headers.join(' | ')}</span>
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
            <Button
              variant="ghost"
              onClick={() => downloadCsv(templateName, headers, sampleRows)}
            >
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
              {quotaBadgesFn ? quotaBadgesFn(quota, parseResult) : null}
              {quota?.max_imports_per_day != null && (
                <Badge variant="outline">
                  استيراد اليوم: {quota.imports_today ?? 0} / {quota.max_imports_per_day}
                </Badge>
              )}
            </div>

            <div className="border rounded-md overflow-hidden">
              <ResponsiveTable
                ariaLabel={ariaLabel}
                rows={parseResult.rows || []}
                getRowKey={(r) => r.row_number}
                rowClassName=""
                columns={[
                  ...previewColumns,
                  {
                    key: 'status',
                    header: 'الحالة',
                    render: (r) => (
                      r.is_valid ? (
                        <span className="inline-flex items-center gap-1 text-green-700">
                          <CheckCircle className="w-4 h-4" /> جاهز
                        </span>
                      ) : (
                        <span
                          className="inline-flex items-center gap-1 text-red-700"
                          title={(r.errors || []).join('، ')}
                        >
                          <AlertTriangle className="w-4 h-4" /> {(r.errors || [])[0] || 'غير صالح'}
                        </span>
                      )
                    ),
                  },
                ]}
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => { setParseResult(null); setFileName(''); }}>
                إلغاء
              </Button>
              <Button onClick={onCommit} disabled={committing || !validRows.length}>
                {committing && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
                تأكيد الاستيراد ({validRows.length})
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      {columnsRender}
    </div>
  );
}

function ClassesTab() {
  const { api } = useAuth();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  return (
    <CsvImportPanel
      api={api}
      nassaqError={nassaqError}
      nassaqInfo={nassaqInfo}
      nassaqConfirm={nassaqConfirm}
      parseUrl="/independent-teacher/classes/bulk/parse"
      commitUrl="/independent-teacher/classes/bulk/commit"
      headers={CLASS_HEADERS}
      templateName="nassaq-classes-template.csv"
      sampleRows={[
        ['حلقة القرآن - مستوى أول', 'الصف الأول', 'القرآن الكريم'],
        ['حلقة القرآن - مستوى ثاني', 'الصف الثاني', ''],
      ]}
      intro={(
        <p className="text-sm text-gray-600">
          الحد الأقصى ٥ فصول في حسابك المستقل. عمود «اسم الفصل» مطلوب،
          والباقي اختياري.
        </p>
      )}
      successPrefix="تمت إضافة عدد فصول:"
      confirmPrefixFn={(n) => `سيتم إضافة ${n} فصلًا إلى مساحة عملك. هذه العملية نهائية.`}
      quotaBadgesFn={(quota, parsed) => (
        quota?.max_classes != null && (
          <Badge variant="outline">
            الفصول: {(quota.current_classes ?? 0)} / {quota.max_classes}
            {parsed?.projected_classes != null
              ? ` → ${parsed.projected_classes}` : ''}
          </Badge>
        )
      )}
      ariaLabel="معاينة الفصول المستوردة"
      previewColumns={[
        {
          key: 'name',
          header: 'اسم الفصل',
          primary: true,
          render: (r) => (
            <span className={r.is_valid ? '' : 'text-red-700'}>
              {`#${r.row_number} — ${r.name || '—'}`}
            </span>
          ),
        },
        { key: 'grade_level', header: 'المرحلة', render: (r) => r.grade_level || '—' },
        { key: 'default_subject', header: 'المادة الافتراضية', render: (r) => r.default_subject || '—' },
      ]}
    />
  );
}

function SubjectsTab() {
  const { api } = useAuth();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  return (
    <CsvImportPanel
      api={api}
      nassaqError={nassaqError}
      nassaqInfo={nassaqInfo}
      nassaqConfirm={nassaqConfirm}
      parseUrl="/independent-teacher/subjects/bulk/parse"
      commitUrl="/independent-teacher/subjects/bulk/commit"
      headers={SUBJECT_HEADERS}
      templateName="nassaq-subjects-template.csv"
      sampleRows={[
        ['القرآن الكريم', 'QURAN'],
        ['التجويد', 'TJWD'],
      ]}
      intro={(
        <p className="text-sm text-gray-600">
          الحد الأعلى ٥٠ مادة في كل عملية استيراد. عمود «اسم المادة» مطلوب،
          والكود اختياري.
        </p>
      )}
      successPrefix="تمت إضافة عدد مواد:"
      confirmPrefixFn={(n) => `سيتم إضافة ${n} مادة إلى مساحة عملك. هذه العملية نهائية.`}
      ariaLabel="معاينة المواد المستوردة"
      previewColumns={[
        {
          key: 'name',
          header: 'اسم المادة',
          primary: true,
          render: (r) => (
            <span className={r.is_valid ? '' : 'text-red-700'}>
              {`#${r.row_number} — ${r.name || '—'}`}
            </span>
          ),
        },
        { key: 'code', header: 'الكود', render: (r) => r.code || '—' },
      ]}
    />
  );
}

function isoDate(d) {
  return d.toISOString().slice(0, 10);
}

const DAY_LABELS_AR = {
  sun: 'الأحد', mon: 'الإثنين', tue: 'الثلاثاء',
  wed: 'الأربعاء', thu: 'الخميس', fri: 'الجمعة', sat: 'السبت',
};

function DuplicateWeekTab() {
  const { api } = useAuth();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  const today = useMemo(() => new Date(), []);
  const defaultFrom = useMemo(() => {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - 7);
    return isoDate(d);
  }, [today]);
  const defaultTo = useMemo(() => isoDate(today), [today]);
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(defaultTo);
  const [busy, setBusy] = useState(false);
  // Preview is the dry-run response — until the teacher loads one, the
  // commit button stays disabled. This forces the per-slot conflict
  // report to be acknowledged before any write happens.
  const [preview, setPreview] = useState(null);

  // Invalidate any stale preview when the date inputs change so the
  // teacher can never confirm against an outdated plan.
  const handleFromChange = useCallback((v) => { setFrom(v); setPreview(null); }, []);
  const handleToChange = useCallback((v) => { setTo(v); setPreview(null); }, []);

  const loadPreview = useCallback(async () => {
    setBusy(true);
    try {
      const res = await api.post(
        '/independent-teacher/schedule/duplicate-week',
        { from_week_start: from, to_week_start: to, dry_run: true },
      );
      setPreview(res.data || null);
    } catch (err) {
      setPreview(null);
      const msg = err?.response?.data?.detail || err?.response?.data?.error?.message ||
        'تعذّر تحضير المعاينة. تأكد من التواريخ ثم أعد المحاولة.';
      nassaqError(String(msg), { title: 'فشل المعاينة' });
    } finally {
      setBusy(false);
    }
  }, [api, from, to, nassaqError]);

  const commit = useCallback(async () => {
    setBusy(true);
    try {
      const res = await api.post(
        '/independent-teacher/schedule/duplicate-week',
        { from_week_start: from, to_week_start: to },
      );
      const data = res.data || {};
      setPreview(null);
      nassaqInfo(
        `تم نسخ ${data.created ?? 0} حصة، وتجاهُل ${data.skipped ?? 0}.`,
        { title: 'اكتمل النسخ' },
      );
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.error?.message ||
        'تعذّر نسخ الجدول. تأكد من التواريخ ثم أعد المحاولة.';
      nassaqError(String(msg), { title: 'فشل النسخ' });
    } finally {
      setBusy(false);
    }
  }, [api, from, to, nassaqInfo, nassaqError]);

  const onConfirm = useCallback(() => {
    if (!preview) return;
    nassaqConfirm(
      `سيتم نسخ ${preview.created} حصة من أسبوع ${from} إلى أسبوع ${to}. ` +
      `${preview.skipped} حصة موجودة مسبقًا ولن تُستبدل.`,
      commit,
      { title: 'تأكيد نسخ الأسبوع', confirmText: 'نسخ', cancelText: 'إلغاء' },
    );
  }, [from, to, preview, nassaqConfirm, commit]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Calendar className="w-5 h-5" /> نسخ جدول الأسبوع
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-gray-600">
          انسخ جدول أسبوع كامل من حصصك إلى الأسبوع التالي. يجب أن يكون الفرق
          بين التاريخين سبعة أيام بالضبط، ولن تُستبدل أي حصة موجودة في
          الأسبوع المستهدف. اعرض المعاينة قبل التنفيذ لمراجعة كل حصة.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-gray-700 mb-1">
              بداية الأسبوع المصدر (YYYY-MM-DD)
            </label>
            <Input
              type="date"
              value={from}
              onChange={(e) => handleFromChange(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-700 mb-1">
              بداية الأسبوع المستهدف (YYYY-MM-DD)
            </label>
            <Input
              type="date"
              value={to}
              onChange={(e) => handleToChange(e.target.value)}
            />
          </div>
        </div>

        {preview && Array.isArray(preview.slots) && (
          <div className="rounded-lg border bg-gray-50 p-3 space-y-2">
            <div className="text-sm font-medium text-gray-800">
              معاينة: من {preview.from_week_start} إلى {preview.to_week_start}
              {' — '}
              <span className="text-emerald-700">{preview.created} ستُنشأ</span>
              {' / '}
              <span className="text-amber-700">{preview.skipped} ستُتجاهَل</span>
            </div>
            {preview.slots.length === 0 ? (
              <p className="text-xs text-gray-600">لا توجد حصص للنسخ في هذا الأسبوع.</p>
            ) : (
              <ul className="text-xs text-gray-700 space-y-1 max-h-64 overflow-auto">
                {preview.slots.map((s, idx) => (
                  <li
                    key={`${s.day_of_week}-${s.slot_number}-${idx}`}
                    className="flex items-center justify-between gap-2 border-b last:border-0 pb-1"
                  >
                    <span>
                      {DAY_LABELS_AR[s.day_of_week] || s.day_of_week}
                      {' • الحصة '}{s.slot_number}
                      {s.subject_name ? ` • ${s.subject_name}` : ''}
                      {s.class_name ? ` (${s.class_name})` : ''}
                    </span>
                    {s.will_create ? (
                      <span className="text-emerald-700">ستُنشأ</span>
                    ) : (
                      <span className="text-amber-700">موجودة — تُتجاهل</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="outline"
            onClick={loadPreview}
            disabled={busy || !from || !to}
          >
            {busy && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
            عرض المعاينة
          </Button>
          <Button
            onClick={onConfirm}
            disabled={busy || !preview || (preview?.created ?? 0) === 0}
          >
            {busy && <Loader2 className="w-4 h-4 ml-2 animate-spin" />}
            تنفيذ النسخ
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// 2026-05-19 — IA refactor: extracted the inner Tabs block into a
// headless panel so /teacher/classes can embed it as the "استيراد
// البيانات" tab without rendering a nested page shell. The standalone
// route (/teacher/bulk-import) is now a redirect to ?tab=import; the
// default `BulkImportPage` is preserved as a thin wrapper only for
// back-compat with any lazy import that still references it.
//
// Per-subtab permission gating (mirrors the retired Sidebar entries):
//   - "students"   sub-tab → `students.bulk_import_workspace`
//                            (the old "استيراد الطلاب" sidebar entry)
//   - "classes"  / "subjects" / "duplicate-week" sub-tabs →
//                            `classes.bulk_import_workspace`
//                            (the old "الاستيراد الجماعي" hub entry)
// `permissions` is an optional Set passed from TeacherClassesPage. When
// omitted (e.g. legacy back-compat callers) all sub-tabs render so
// existing screenshots / tests keep working; the backend always remains
// the authoritative enforcement boundary on the /parse and /commit
// endpoints regardless of FE visibility.
export function BulkImportPanel({ permissions = null } = {}) {
  const hasPerm = (key) => (permissions ? permissions.has(key) : true);
  const canStudents = hasPerm('students.bulk_import_workspace');
  const canClasses = hasPerm('classes.bulk_import_workspace');
  // Default to the highest-priority allowed sub-tab so users who only
  // have students-import don't land on a disabled "classes" panel.
  const defaultTab = canStudents
    ? 'students'
    : canClasses ? 'classes' : 'students';
  const [tab, setTab] = useState(defaultTab);
  return (
    <div className="space-y-6" dir="rtl" data-testid="it-bulk-import-panel">
      <p className="text-sm text-gray-600">
        استيراد طلاب وفصول ومواد من ملفات CSV، أو نسخ جدول أسبوع كامل
        إلى الأسبوع التالي. كل العمليات تخضع لحدود حسابك المستقل.
      </p>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex flex-wrap gap-1">
          {canStudents && (
            <TabsTrigger value="students" className="gap-2" data-testid="it-bulk-import-tab-students">
              <Users className="w-4 h-4" /> الطلاب
            </TabsTrigger>
          )}
          {canClasses && (
            <TabsTrigger value="classes" className="gap-2" data-testid="it-bulk-import-tab-classes">
              <Layers className="w-4 h-4" /> الفصول
            </TabsTrigger>
          )}
          {canClasses && (
            <TabsTrigger value="subjects" className="gap-2" data-testid="it-bulk-import-tab-subjects">
              <BookOpen className="w-4 h-4" /> المواد
            </TabsTrigger>
          )}
          {canClasses && (
            <TabsTrigger value="duplicate-week" className="gap-2" data-testid="it-bulk-import-tab-duplicate-week">
              <Calendar className="w-4 h-4" /> نسخ الأسبوع
            </TabsTrigger>
          )}
        </TabsList>

        {canStudents && (
          <TabsContent value="students" className="mt-4">
            <ImportStudentsPanel />
          </TabsContent>
        )}
        {canClasses && (
          <TabsContent value="classes" className="mt-4">
            <ClassesTab />
          </TabsContent>
        )}
        {canClasses && (
          <TabsContent value="subjects" className="mt-4">
            <SubjectsTab />
          </TabsContent>
        )}
        {canClasses && (
          <TabsContent value="duplicate-week" className="mt-4">
            <DuplicateWeekTab />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

export default function BulkImportPage() {
  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6 space-y-6 max-w-5xl mx-auto">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold text-gray-900">الاستيراد الجماعي</h1>
        </header>
        <BulkImportPanel />
      </main>
    </div>
  );
}
