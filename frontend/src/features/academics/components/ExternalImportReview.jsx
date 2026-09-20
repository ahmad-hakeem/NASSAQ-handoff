import { useLayoutEffect, useRef, useState } from 'react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const PAGE_SIZE = 20;
const text = (value) => value == null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const issues = (value) => Array.isArray(value) ? value : value ? [value] : [];

export const hasImportBlockers = (draft) => !draft
  || draft.can_confirm !== true
  || issues(draft.errors).length > 0
  || Number(draft.summary?.blocking_errors || 0) > 0
  || Number(draft.summary?.error_rows || 0) > 0
  || (draft.rows || []).some(row => issues(row.errors).length > 0 || ['error', 'conflict'].includes(row.action));

// JSON (not spreadsheet CSV or HTML) keeps untrusted cell content inert.
export function downloadImportReview(draft) {
  const blob = new Blob([JSON.stringify({
    import_type: draft.import_type,
    errors: draft.errors || [],
    warnings: draft.warnings || [],
    rows: (draft.rows || []).filter(row => issues(row.errors).length || issues(row.warnings).length),
  }, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'external-import-review.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** The parent keys this component by actor, tenant and type: no draft crosses a scope. */
export default function ExternalImportReview({ api, headers, importType, isRTL, onSelectionChange, onComplete }) {
  const [file, setFile] = useState(null);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [warningsAccepted, setWarningsAccepted] = useState(false);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const fileInput = useRef(null);
  const active = useRef(true);
  const generation = useRef(0);
  const pending = useRef(false);
  const controller = useRef(null);
  const draftRef = useRef(null);
  const tr = (ar, en) => isRTL ? ar : en;
  const discard = (value) => {
    if (value?.draft_id) {
      // Best effort cleanup only; the server also expires drafts. Never allow a
      // cleanup failure to turn into an unhandled rejection or a saved import.
      Promise.resolve(api.post(`/bulk/draft/${encodeURIComponent(value.draft_id)}/discard`, {}, { headers })).catch(() => {});
    }
  };
  useLayoutEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      generation.current += 1;
      controller.current?.abort();
      discard(draftRef.current);
    };
    // The parent remounts for every actor/tenant/type change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const invalidate = () => {
    generation.current += 1;
    controller.current?.abort();
    pending.current = false;
    discard(draftRef.current);
    draftRef.current = null;
    setDraft(null);
    setBusy('');
    setError('');
    setAcknowledged(false);
    setWarningsAccepted(false);
    setQuery('');
    setPage(1);
  };
  const selectFile = (event) => {
    const next = event.target.files?.[0];
    invalidate();
    setFile(null);
    onSelectionChange();
    if (!next) return;
    if (!/\.(xlsx|xls|csv)$/i.test(next.name)) {
      setError(tr('صيغة غير مدعومة. اختر ملف Excel أو CSV.', 'Unsupported format. Choose an Excel or CSV file.'));
      event.target.value = '';
      return;
    }
    setFile(next);
  };
  const preview = async () => {
    if (pending.current || !file) return;
    const previous = draftRef.current;
    invalidate();
    pending.current = true;
    setBusy('preview');
    onSelectionChange();
    const version = generation.current;
    const abort = new AbortController();
    controller.current = abort;
    try {
      const form = new FormData();
      form.append('file', file);
      if (previous?.draft_id) form.append('supersedes_draft_id', previous.draft_id);
      const response = await api.post(`/bulk/preview/${importType}`, form, { headers, signal: abort.signal });
      if (!active.current || generation.current !== version) {
        discard(response.data);
        return;
      }
      const result = response.data;
      if (!result?.draft_id || !result.fingerprint || result.preview_version == null || result.import_type !== importType || !Array.isArray(result.rows)) {
        discard(result);
        throw new Error(tr('استجابة معاينة غير صالحة. أعد المحاولة.', 'Invalid preview response. Please try again.'));
      }
      draftRef.current = result;
      setDraft(result);
    } catch (failure) {
      if (active.current && generation.current === version) setError(getApiErrorMessage(failure) || tr('تعذرت المعاينة.', 'Preview failed.'));
    } finally {
      if (active.current && generation.current === version) { pending.current = false; setBusy(''); }
    }
  };

  const warningCount = issues(draft?.warnings).length + (draft?.rows || []).reduce((n, row) => n + issues(row.warnings).length, 0);
  const blocked = hasImportBlockers(draft);
  const confirm = async () => {
    if (pending.current || blocked || !acknowledged || (warningCount > 0 && !warningsAccepted)) return;
    pending.current = true;
    setBusy('confirm');
    setError('');
    const version = generation.current;
    const abort = new AbortController();
    controller.current = abort;
    const current = draftRef.current;
    try {
      const response = await api.post('/bulk/confirm', {
        draft_id: current.draft_id,
        fingerprint: current.fingerprint,
        preview_version: current.preview_version,
        acknowledged: true,
      }, { headers, signal: abort.signal });
      if (!active.current || generation.current !== version) return;
      draftRef.current = null;
      setDraft(null);
      setFile(null);
      if (fileInput.current) fileInput.current.value = '';
      onComplete(response.data || {}, importType);
    } catch (failure) {
      if (active.current && generation.current === version) {
        // A network failure may be ambiguous. Never retry a commit from the
        // same review; require a newly validated preview.
        discard(current);
        draftRef.current = null;
        setDraft(null);
        setAcknowledged(false);
        setError(`${getApiErrorMessage(failure) || tr('تعذر التأكيد.', 'Confirmation failed.')} ${tr('حدّث البيانات وأنشئ معاينة جديدة قبل المحاولة مجدداً.', 'Refresh the data and create a new preview before trying again.')}`);
      }
    } finally {
      if (active.current && generation.current === version) { pending.current = false; setBusy(''); }
    }
  };
  const cancel = () => {
    invalidate();
    setFile(null);
    if (fileInput.current) fileInput.current.value = '';
    onSelectionChange();
  };
  const filtered = (draft?.rows || []).filter(row => text(row).toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const actionLabel = (action) => ({
    create: tr('إنشاء', 'Create'), update: tr('تحديث', 'Update'), restore: tr('استعادة', 'Restore'),
    reuse: tr('إعادة استخدام', 'Reuse'), conflict: tr('تعارض', 'Conflict'), error: tr('خطأ', 'Error'),
    link: tr('ربط', 'Link'), assign: tr('إسناد', 'Assign'), none: tr('بدون تغيير', 'No change'),
  }[action] || text(action));
  const relationshipLabel = (key) => ({
    parent: tr('ولي الأمر', 'Parent'), class: tr('الفصل', 'Class'), grade: tr('الصف', 'Grade'),
    parent_account: tr('حساب ولي الأمر', 'Parent account'), assignment: tr('إسناد الطالب للفصل', 'Class assignment'),
    guardian_link: tr('ربط الطالب بولي الأمر', 'Guardian link'),
  }[key] || key);
  const summaryLabel = (key) => {
    const labels = {
      total_rows: tr('إجمالي الصفوف', 'Total rows'), create: tr('إنشاء سجلات', 'Create records'),
      update: tr('تحديث سجلات', 'Update records'), restore: tr('استعادة سجلات', 'Restore records'),
      errors: tr('أخطاء', 'Errors'), error: tr('صفوف بها أخطاء', 'Error rows'), conflict: tr('تعارضات', 'Conflicts'),
      blocking_errors: tr('أخطاء مانعة', 'Blocking errors'), error_rows: tr('صفوف بها أخطاء', 'Error rows'),
      warnings: tr('تحذيرات', 'Warnings'), error_count: tr('عدد الأخطاء', 'Error count'),
      warning_count: tr('عدد التحذيرات', 'Warning count'), assignments: tr('إسنادات الفصول', 'Class assignments'),
      guardian_links: tr('روابط أولياء الأمور', 'Guardian links'),
    };
    const relationship = key.match(/^(grade|class|parent|parent_account)_(create|reuse)$/);
    return labels[key] || (relationship ? `${relationshipLabel(relationship[1])} — ${actionLabel(relationship[2])}` : key);
  };
  const fieldValue = (row, key) => {
    const value = row[key] ?? row.optional_values?.[key];
    if (key === 'grade' && value && typeof value === 'object') {
      return (isRTL ? value.label_ar : value.label_en) || value.label_ar || value.grade;
    }
    return Array.isArray(value) ? value.join(', ') : value;
  };
  const renderIssues = (values, kind) => issues(values).map((issue, index) => (
    <p key={`${kind}-${index}`} className={kind === 'error' ? 'text-red-700 dark:text-red-400' : 'text-amber-700 dark:text-amber-400'}>
      {typeof issue === 'string' ? issue : issue.message || issue.reason || text(issue)}
    </p>
  ));
  const fields = [
    ['national_id', tr('الهوية', 'National ID')], ['email', tr('البريد الإلكتروني', 'Email')],
    ['phone', tr('الهاتف', 'Phone')], ['grade', tr('الصف', 'Grade')], ['grade_name', tr('الصف', 'Grade')],
    ['class_name', tr('الفصل', 'Class')], ['class', tr('الفصل', 'Class')], ['raw_class_name', tr('الفصل', 'Class')],
    ['section', tr('الشعبة', 'Section')], ['grades', tr('الصفوف', 'Grades')], ['subjects', tr('المواد', 'Subjects')],
    ['parent_name', tr('ولي الأمر', 'Parent')], ['parent_national_id', tr('هوية ولي الأمر', 'Parent ID')],
    ['parent_phone', tr('هاتف ولي الأمر', 'Parent phone')], ['parent_email', tr('بريد ولي الأمر', 'Parent email')],
  ];
  return (
    <section dir={isRTL ? 'rtl' : 'ltr'} className="space-y-4 min-w-0" aria-label={tr('مراجعة الاستيراد الخارجي', 'External import review')}>
      <p className="text-sm text-muted-foreground">{tr('١. اختر الملف  ←  ٢. راجع المعاينة  ←  ٣. أكّد الاستيراد', '1. Select file → 2. Review preview → 3. Confirm import')}</p>
      <label htmlFor="file-upload" className="block text-sm">{tr('ملف Excel أو CSV', 'Excel or CSV file')}</label>
      <Input ref={fileInput} type="file" id="file-upload" accept=".xlsx,.xls,.csv" onChange={selectFile} disabled={busy === 'confirm'} />
      {file && <p className="text-sm break-all">{file.name}</p>}
      <div className="flex gap-2 flex-wrap">
        <Button onClick={preview} disabled={!!busy || !file}>{busy === 'preview' ? tr('جارٍ إعداد المعاينة…', 'Preparing preview…') : tr('معاينة الملف', 'Preview file')}</Button>
        {(file || draft || busy) && <Button variant="outline" onClick={cancel} disabled={busy === 'confirm'}>{tr('إلغاء', 'Cancel')}</Button>}
      </div>
      {error && <p role="alert" className="text-sm text-red-700 dark:text-red-400">{error}</p>}
      {draft && <div className="space-y-4">
        <h3 className="font-semibold">{tr('معاينة فقط — لم تُحفظ أي بيانات بعد', 'Preview only — no data has been saved yet')}</h3>
        <div className="text-sm space-y-1" aria-label={tr('ملخص المعاينة', 'Preview summary')}>
          <p>{tr('إجمالي الصفوف', 'Total rows')}: {draft.rows.length}</p>
          {Object.entries(draft.summary || {}).filter(([key]) => key !== 'total_rows').map(([key, value]) => <p key={key}>{summaryLabel(key)}: {text(value)}</p>)}
        </div>
        {renderIssues(draft.errors, 'error')}
        {renderIssues(draft.warnings, 'warning')}
        {blocked && <p role="alert" className="text-red-700 dark:text-red-400">{tr('لا يمكن التأكيد. أصلح جميع الأخطاء في الملف ثم أعد المعاينة.', 'Confirmation is blocked. Fix all errors in the file and preview again.')}</p>}
        <Button variant="outline" onClick={() => downloadImportReview(draft)}>{tr('تنزيل الأخطاء والتحذيرات (JSON)', 'Download errors and warnings (JSON)')}</Button>
        <Input aria-label={tr('البحث في صفوف المعاينة', 'Search preview rows')} placeholder={tr('ابحث بالاسم أو الهوية أو الفصل…', 'Search name, identity or class…')} value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} />
        <p className="text-sm" aria-live="polite">{tr('نتائج البحث', 'Matching rows')}: {filtered.length}</p>
        <div className="space-y-3">
          {visible.map((row, index) => <article key={`${row.row}-${index}`} className="rounded-lg border p-3 space-y-2 text-sm break-words">
            <h4 className="font-semibold">{tr('صف', 'Row')} {row.row}: {row.name || '—'} — {actionLabel(row.action)}</h4>
            <dl className="grid gap-2 sm:grid-cols-2">{fields.filter(([key]) => fieldValue(row, key) != null && fieldValue(row, key) !== '').map(([key, label]) => <div key={key}><dt className="text-muted-foreground">{label}</dt><dd className="break-all">{text(fieldValue(row, key))}</dd></div>)}</dl>
            <div><strong>{tr('العلاقات والإجراءات المخطط لها', 'Planned relationships and actions')}</strong>
              {Object.entries(row.relationships || {}).map(([key, value]) => <p key={key}>{relationshipLabel(key)}: {actionLabel(typeof value === 'string' ? value : value?.action)}
                {value?.restore && ` — ${tr('استعادة الفصل', 'Restore class')}`}
                {value?.repair_grade_link && ` — ${tr('إصلاح ارتباط الصف', 'Repair grade link')}`}
              </p>)}
            </div>
            {renderIssues(row.errors, 'error')}{renderIssues(row.warnings, 'warning')}
          </article>)}
          {!visible.length && <p>{tr('لا توجد صفوف مطابقة.', 'No matching rows.')}</p>}
        </div>
        <nav className="flex gap-3 items-center" aria-label={tr('صفحات المعاينة', 'Preview pages')}>
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>{tr('السابق', 'Previous')}</Button>
          <span>{page} / {pages}</span>
          <Button variant="outline" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>{tr('التالي', 'Next')}</Button>
        </nav>
        {warningCount > 0 && <label className="flex gap-2 items-start text-sm"><input type="checkbox" checked={warningsAccepted} onChange={event => setWarningsAccepted(event.target.checked)} disabled={!!busy} /><span>{tr('راجعت جميع التحذيرات وأوافق على المتابعة.', 'I reviewed all warnings and agree to proceed.')}</span></label>}
        <label className="flex gap-2 items-start text-sm"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} disabled={!!busy || blocked} /><span>{tr('راجعت المعاينة وأؤكد إنشاء أو تحديث السجلات والعلاقات المعروضة.', 'I reviewed the preview and confirm creating or updating the displayed records and relationships.')}</span></label>
        <Button onClick={confirm} disabled={!!busy || blocked || !acknowledged || (warningCount > 0 && !warningsAccepted)}>{busy === 'confirm' ? tr('جارٍ تأكيد الاستيراد…', 'Confirming import…') : tr('تأكيد الاستيراد', 'Confirm import')}</Button>
      </div>}
    </section>
  );
}