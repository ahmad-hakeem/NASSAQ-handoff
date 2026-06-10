import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Loader2, Upload, FileSpreadsheet, AlertTriangle, CheckCircle2, Database, Download, Undo2, History, RefreshCw, Trash2, RotateCcw } from 'lucide-react';
import { getApiErrorMessage } from '../../utils/apiError';

const ROLE_LABELS = {
  insert: { ar: 'إضافة', cls: 'bg-green-50 text-green-700 dark:bg-green-950/40' },
  update: { ar: 'تحديث', cls: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40' },
  skip: { ar: 'تخطي', cls: 'bg-amber-50 text-amber-700 dark:bg-amber-950/40' },
  ambiguous: { ar: 'مطابقة غير مؤكدة', cls: 'bg-orange-50 text-orange-700 dark:bg-orange-950/40' },
  duplicate_in_file: { ar: 'مكرر في الملف', cls: 'bg-red-50 text-red-700 dark:bg-red-950/40' },
};

const TYPE_LABEL = {
  teachers: 'معلمون',
  students: 'طلاب',
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

function formatDate(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString('ar-SA', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return isoStr;
  }
}

function HistoryTab({ api, nassaqError, nassaqConfirm, nassaqInfo }) {
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [history, setHistory] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [restoringId, setRestoringId] = useState(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [actorFilter, setActorFilter] = useState('');
  const [actors, setActors] = useState([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState(null);
  const [nextCursorId, setNextCursorId] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  // The filters actually in effect for the current result set.
  // Editing the controls only stages new values; clicking Apply (or
  // toggling include-deleted) is what swaps them in and triggers a
  // fetch. This keeps a noisy "type-then-pause" flow from spamming
  // the server while filters are mid-edit.
  const [appliedFilters, setAppliedFilters] = useState({
    dateFrom: '', dateTo: '', typeFilter: '', actorFilter: '',
  });
  const PAGE_SIZE = 50;

  const buildParams = useCallback((filters, includeDeleted, cursor, cursorId) => {
    const params = { limit: PAGE_SIZE };
    if (includeDeleted) params.include_deleted = true;
    if (filters.dateFrom) params.date_from = filters.dateFrom;
    // Inclusive "to": cover the entire selected day, including
    // sub-second timestamps (rows committed at HH:MM:59.xxx).
    if (filters.dateTo) params.date_to = `${filters.dateTo}T23:59:59.999999`;
    if (filters.typeFilter) params.detected_type = filters.typeFilter;
    if (filters.actorFilter) params.actor_id = filters.actorFilter;
    if (cursor) {
      params.before = cursor;
      if (cursorId) params.before_id = cursorId;
    }
    return params;
  }, []);

  const fetchHistory = useCallback(async (filters, includeDeleted) => {
    setLoading(true);
    try {
      const res = await api.get('/noor-import/history', { params: buildParams(filters, includeDeleted) });
      setHistory(res.data.history || []);
      setActors(res.data.actors || []);
      setTotal(res.data.total || 0);
      setNextCursor(res.data.next_cursor || null);
      setNextCursorId(res.data.next_cursor_id || null);
      setHasMore(!!res.data.has_more);
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || 'تعذّر تحميل سجل الاستيرادات');
    } finally {
      setLoading(false);
    }
  }, [api, nassaqError, buildParams]);

  const loadMore = useCallback(async () => {
    if (!hasMore || !nextCursor) return;
    setLoadingMore(true);
    try {
      const res = await api.get('/noor-import/history', {
        params: buildParams(appliedFilters, showDeleted, nextCursor, nextCursorId),
      });
      setHistory((prev) => ([...(prev || []), ...(res.data.history || [])]));
      setNextCursor(res.data.next_cursor || null);
      setNextCursorId(res.data.next_cursor_id || null);
      setHasMore(!!res.data.has_more);
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || 'تعذّر تحميل المزيد');
    } finally {
      setLoadingMore(false);
    }
  }, [api, buildParams, appliedFilters, showDeleted, hasMore, nextCursor, nextCursorId, nassaqError]);

  useEffect(() => { fetchHistory(appliedFilters, showDeleted); }, [fetchHistory, appliedFilters, showDeleted]);

  const applyFilters = () => {
    setAppliedFilters({ dateFrom, dateTo, typeFilter, actorFilter });
  };

  const resetFilters = () => {
    setDateFrom('');
    setDateTo('');
    setTypeFilter('');
    setActorFilter('');
    setAppliedFilters({ dateFrom: '', dateTo: '', typeFilter: '', actorFilter: '' });
  };

  const hasActiveFilters = !!(
    appliedFilters.dateFrom || appliedFilters.dateTo
    || appliedFilters.typeFilter || appliedFilters.actorFilter
  );
  const hasStagedChanges = (
    dateFrom !== appliedFilters.dateFrom
    || dateTo !== appliedFilters.dateTo
    || typeFilter !== appliedFilters.typeFilter
    || actorFilter !== appliedFilters.actorFilter
  );

  const onDeleteRow = useCallback((row) => {
    if (!row?.id || !nassaqConfirm) return;
    const typeLabel = TYPE_LABEL[row.detected_type] || row.detected_type;
    nassaqConfirm(
      `سيتم إخفاء سجل استيراد ${typeLabel} بتاريخ ${formatDate(row.committed_at)} من القائمة. لن يؤثر ذلك على الطلاب أو المعلمين الذين تمت إضافتهم سابقاً.`,
      async () => {
        setDeletingId(row.id);
        try {
          await api.delete(`/noor-import/history/${row.id}`);
          setHistory((prev) => {
            if (!prev) return prev;
            if (showDeleted) {
              return prev.map((r) => (
                r.id === row.id ? { ...r, deleted_at: new Date().toISOString() } : r
              ));
            }
            return prev.filter((r) => r.id !== row.id);
          });
          if (!showDeleted) {
            setTotal((t) => Math.max(0, t - 1));
          }
          if (nassaqInfo) nassaqInfo('تم إخفاء سجل الاستيراد.');
        } catch (err) {
          nassaqError(getApiErrorMessage(err) || 'تعذّر حذف سجل الاستيراد');
        } finally {
          setDeletingId(null);
        }
      },
      { title: 'حذف سجل الاستيراد', confirmText: 'حذف السجل', cancelText: 'إلغاء' },
    );
  }, [api, nassaqConfirm, nassaqError, nassaqInfo, showDeleted]);

  const onRestoreRow = useCallback(async (row) => {
    if (!row?.id) return;
    setRestoringId(row.id);
    try {
      await api.post(`/noor-import/history/${row.id}/restore`);
      setHistory((prev) => (
        prev ? prev.map((r) => (r.id === row.id ? { ...r, deleted_at: null } : r)) : prev
      ));
      if (!showDeleted) {
        setTotal((t) => t + 1);
      }
      if (nassaqInfo) nassaqInfo('تمت استعادة سجل الاستيراد.');
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || 'تعذّر استعادة سجل الاستيراد');
    } finally {
      setRestoringId(null);
    }
  }, [api, nassaqError, nassaqInfo, showDeleted]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground text-sm gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        جاري التحميل…
      </div>
    );
  }

  if (!history) return null;

  const toggle = (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
      <input
        type="checkbox"
        checked={showDeleted}
        onChange={(e) => setShowDeleted(e.target.checked)}
        className="h-3.5 w-3.5"
      />
      عرض السجلات المخفية
    </label>
  );

  const filterBar = (
    <div className="rounded-xl border bg-muted/30 p-3 space-y-2">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        <div className="space-y-1">
          <label className="text-[11px] text-muted-foreground">من تاريخ</label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-8 text-xs"
          />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-muted-foreground">إلى تاريخ</label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-8 text-xs"
          />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-muted-foreground">النوع</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value="">الكل</option>
            <option value="teachers">معلمون</option>
            <option value="students">طلاب</option>
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[11px] text-muted-foreground">المنفّذ</label>
          <select
            value={actorFilter}
            onChange={(e) => setActorFilter(e.target.value)}
            className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value="">الكل</option>
            {actors.map((a) => (
              <option key={a.actor_id} value={a.actor_id}>
                {a.actor_name || a.actor_id} ({a.import_count})
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 flex-wrap pt-1">
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            type="button"
            onClick={applyFilters}
            disabled={loading || !hasStagedChanges}
          >
            تطبيق
          </Button>
          {(hasActiveFilters || hasStagedChanges) && (
            <Button size="sm" variant="ghost" type="button" onClick={resetFilters} disabled={loading}>
              مسح
            </Button>
          )}
          {toggle}
        </div>
        <Button size="sm" variant="outline" onClick={() => fetchHistory(appliedFilters, showDeleted)} disabled={loading} type="button">
          <RefreshCw className="h-3.5 w-3.5 me-1.5" />
          تحديث
        </Button>
      </div>
    </div>
  );

  if (history.length === 0) {
    return (
      <div className="space-y-3">
        {filterBar}
        <div className="flex flex-col items-center justify-center py-12 gap-3 text-muted-foreground">
          <History className="h-8 w-8 opacity-40" />
          <p className="text-sm">
            {hasActiveFilters
              ? 'لا توجد سجلات تطابق عوامل التصفية المحددة.'
              : (showDeleted ? 'لا توجد سجلات مخفية.' : 'لا توجد عمليات استيراد مسجّلة بعد.')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {filterBar}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-muted-foreground">
          عرض {history.length} من أصل {total} عملية استيراد — الأحدث أولاً
        </p>
      </div>
      <div className="space-y-2">
        {history.map((row) => {
          const creds = row.credentials_csv || [];
          const classIds = row.created_class_ids || [];
          const createdIds = row.created_ids || [];
          const updatedIds = row.updated_ids || [];
          const typeLabel = TYPE_LABEL[row.detected_type] || row.detected_type;
          const isDeleted = !!row.deleted_at;
          return (
            <div
              key={row.id}
              className={`rounded-xl border p-4 space-y-3 ${
                isDeleted
                  ? 'bg-muted/40 border-dashed opacity-80'
                  : 'bg-background'
              }`}
            >
              <div className="flex flex-wrap items-start gap-2 justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="text-xs">
                      {typeLabel}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{formatDate(row.committed_at)}</span>
                    {isDeleted && (
                      <Badge variant="outline" className="text-xs bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30">
                        مخفي — {formatDate(row.deleted_at)}
                      </Badge>
                    )}
                  </div>
                  {row.actor_name && (
                    <p className="text-xs text-muted-foreground">بواسطة: {row.actor_name}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {creds.length > 0 && !isDeleted && (
                    <Button
                      size="sm"
                      variant="outline"
                      type="button"
                      onClick={() => downloadCsv(`noor_import_credentials_${row.id}.csv`, creds)}
                    >
                      <Download className="h-3.5 w-3.5 me-1.5" />
                      تنزيل بيانات الدخول ({creds.length})
                    </Button>
                  )}
                  {isDeleted ? (
                    <Button
                      size="sm"
                      variant="outline"
                      type="button"
                      onClick={() => onRestoreRow(row)}
                      disabled={restoringId === row.id}
                      className="text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/30"
                      aria-label="استعادة سجل الاستيراد"
                      title="استعادة سجل الاستيراد"
                    >
                      {restoringId === row.id ? (
                        <Loader2 className="h-3.5 w-3.5 me-1.5 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3.5 w-3.5 me-1.5" />
                      )}
                      استعادة
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      type="button"
                      onClick={() => onDeleteRow(row)}
                      disabled={deletingId === row.id}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                      aria-label="حذف سجل الاستيراد"
                      title="حذف سجل الاستيراد"
                    >
                      {deletingId === row.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center text-xs">
                <div className="p-1.5 rounded bg-green-50 dark:bg-green-950/30">
                  <p className="text-base font-bold text-green-600">{row.imported_count}</p>
                  <p className="text-muted-foreground">أُضيف</p>
                </div>
                <div className="p-1.5 rounded bg-blue-50 dark:bg-blue-950/30">
                  <p className="text-base font-bold text-blue-600">{row.updated_count}</p>
                  <p className="text-muted-foreground">حُدِّث</p>
                </div>
                <div className="p-1.5 rounded bg-amber-50 dark:bg-amber-950/30">
                  <p className="text-base font-bold text-amber-600">{row.skipped_count}</p>
                  <p className="text-muted-foreground">تخطّى</p>
                </div>
                <div className="p-1.5 rounded bg-red-50 dark:bg-red-950/30">
                  <p className="text-base font-bold text-red-600">{row.failed_count}</p>
                  <p className="text-muted-foreground">فشل</p>
                </div>
                <div className="p-1.5 rounded bg-red-50 dark:bg-red-950/30">
                  <p className="text-base font-bold text-red-700">{row.duplicates_count}</p>
                  <p className="text-muted-foreground">مكرر</p>
                </div>
                {row.detected_type === 'students' && (
                  <div className="p-1.5 rounded bg-yellow-50 dark:bg-yellow-950/30">
                    <p className="text-base font-bold text-yellow-700">{row.unclassified_count}</p>
                    <p className="text-muted-foreground">بلا فصل</p>
                  </div>
                )}
              </div>

              {(classIds.length > 0 || createdIds.length > 0 || updatedIds.length > 0) && (
                <div className="text-xs text-muted-foreground flex flex-wrap gap-3">
                  {createdIds.length > 0 && (
                    <span>
                      <span className="font-medium text-foreground">{createdIds.length}</span> {row.detected_type === 'teachers' ? 'معلم جديد' : 'طالب جديد'}
                    </span>
                  )}
                  {updatedIds.length > 0 && (
                    <span>
                      <span className="font-medium text-foreground">{updatedIds.length}</span> {row.detected_type === 'teachers' ? 'معلم محدَّث' : 'طالب محدَّث'}
                    </span>
                  )}
                  {classIds.length > 0 && (
                    <span>
                      <span className="font-medium text-foreground">{classIds.length}</span> فصل أُنشئ تلقائياً
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {hasMore && (
        <div className="flex justify-center pt-2">
          <Button
            size="sm"
            variant="outline"
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
          >
            {loadingMore ? (
              <Loader2 className="h-3.5 w-3.5 me-1.5 animate-spin" />
            ) : null}
            تحميل المزيد
          </Button>
        </div>
      )}
    </div>
  );
}

export default function NoorImportPanel({ api, nassaqError, nassaqWarning, nassaqConfirm, nassaqInfo, t, onComplete, onHistoryCountChange }) {
  const [activeTab, setActiveTab] = useState('import');

  const refreshHistoryCount = useCallback(async () => {
    try {
      const res = await api.get('/noor-import/history');
      const n = (res.data?.history || []).length;
      if (typeof onHistoryCountChange === 'function') onHistoryCountChange(n);
    } catch {
      // silent — badge is best-effort
    }
  }, [api, onHistoryCountChange]);

  useEffect(() => { refreshHistoryCount(); }, [refreshHistoryCount]);

  const [file, setFile] = useState(null);
  const [parsing, setParsing] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const fileInputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [ambiguousAccept, setAmbiguousAccept] = useState({}); // { row_index: true }
  const [creatingClasses, setCreatingClasses] = useState(false);
  const [undoingClasses, setUndoingClasses] = useState(false);
  const [undoableClasses, setUndoableClasses] = useState([]);
  const [classOverrides, setClassOverrides] = useState({}); // key: `${grade}||${section}` -> {capacity, homeroom_teacher_id, classroom_id}
  const [teachersList, setTeachersList] = useState([]);
  const [loadingTeachers, setLoadingTeachers] = useState(false);
  const [undoableStudentIds, setUndoableStudentIds] = useState([]);
  const [undoableTeacherIds, setUndoableTeacherIds] = useState([]);
  const [undoToken, setUndoToken] = useState(null);
  const [undoingCommitted, setUndoingCommitted] = useState(false);
  const [classroomsList, setClassroomsList] = useState([]);
  const [loadingClassrooms, setLoadingClassrooms] = useState(false);

  const ambiguousRowIndexes = useMemo(
    () => (preview?.rows || []).filter(r => r.dedupe === 'ambiguous').map(r => r.row_index),
    [preview],
  );

  const missingClassPairs = useMemo(() => {
    const seen = new Map();
    for (const r of (preview?.rows || [])) {
      if (!r.class_unresolved) continue;
      const g = (r.data?.grade_code || '').trim();
      const s = (r.data?.section_code || '').trim();
      const key = `${g}||${s}`;
      const cur = seen.get(key) || { grade_code: g, section_code: s, rows: 0 };
      cur.rows += 1;
      seen.set(key, cur);
    }
    return Array.from(seen.values()).sort((a, b) => b.rows - a.rows);
  }, [preview]);

  // Lazy-load active teachers and classrooms the first time the editor is
  // shown so the dropdowns aren't fetched for imports that don't need it.
  // A ref guards against double-fetch — depending on the state flags in
  // the effect dep array would cancel our own in-flight request when
  // `setLoadingTeachers(true)` triggers a re-render.
  const needsClassEditor = missingClassPairs.length > 0 && preview?.detected_type === 'students';
  const teachersFetchedRef = useRef(false);
  const classroomsFetchedRef = useRef(false);
  useEffect(() => {
    if (!needsClassEditor) return;
    if (!teachersFetchedRef.current) {
      teachersFetchedRef.current = true;
      setLoadingTeachers(true);
      api.get('/teachers', { params: { limit: 100 } })
        .then(res => {
          // `/teachers` has two registered handlers (academics_teacher_routes
          // returns a raw array, teacher_management_routes returns
          // `{teachers, total, ...}`) — accept both shapes, then keep only
          // active rows so the dropdown never lets the principal pick
          // someone the backend will hard-reject (active-only validation).
          const raw = Array.isArray(res?.data)
            ? res.data
            : (Array.isArray(res?.data?.teachers) ? res.data.teachers : []);
          const active = raw.filter(t => t && t.id && t.is_active !== false && t.status !== 'closed');
          setTeachersList(active);
        })
        .catch(() => { setTeachersList([]); })
        .finally(() => { setLoadingTeachers(false); });
    }
    if (!classroomsFetchedRef.current) {
      classroomsFetchedRef.current = true;
      setLoadingClassrooms(true);
      api.get('/academic/classrooms', { params: { available_only: true } })
        .then(res => {
          const raw = Array.isArray(res?.data?.classrooms) ? res.data.classrooms : [];
          setClassroomsList(raw.filter(c => c && c.id));
        })
        .catch(() => { setClassroomsList([]); })
        .finally(() => { setLoadingClassrooms(false); });
    }
  }, [needsClassEditor, api]);
  // Reset the fetched-once guards when the panel is reset to a fresh
  // import (no preview) so a follow-up import re-pulls both lists.
  useEffect(() => {
    if (!preview) {
      teachersFetchedRef.current = false;
      classroomsFetchedRef.current = false;
      setTeachersList([]);
      setClassroomsList([]);
    }
  }, [preview]);

  // Reset overrides whenever the proposed pair set changes (e.g. after
  // re-annotation following a successful create) so stale rows don't
  // leak into the next round.
  useEffect(() => {
    setClassOverrides(prev => {
      const validKeys = new Set(missingClassPairs.map(p => `${p.grade_code}||${p.section_code}`));
      const next = {};
      for (const k of Object.keys(prev)) {
        if (validKeys.has(k)) next[k] = prev[k];
      }
      return next;
    });
  }, [missingClassPairs]);

  const setOverride = (key, patch) => {
    setClassOverrides(prev => ({ ...prev, [key]: { ...(prev[key] || {}), ...patch } }));
  };

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
    setUndoableClasses([]);
    setUndoableStudentIds([]);
    setUndoableTeacherIds([]);
    setUndoToken(null);
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
      setUndoableClasses([]);
      setUndoableStudentIds([]);
      setUndoableTeacherIds([]);
      setUndoToken(null);
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || 'تعذّر تحليل الملف');
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
        setUndoableClasses([]);
        setUndoableStudentIds(data.imported_student_ids || []);
        setUndoableTeacherIds(data.imported_teacher_ids || []);
        setUndoToken(data.undo_token || null);
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
        refreshHistoryCount();
      } catch (err) {
        nassaqError(getApiErrorMessage(err) || 'تعذّر إتمام عملية الاستيراد');
      } finally {
        setCommitting(false);
      }
  };

  const onCreateMissingClasses = async () => {
    if (!preview?.import_draft_id) return;
    if (missingClassPairs.length === 0) return;
    // Build the overrides body from the inline editor state. Only emit
    // an entry when the principal actually changed something — bare
    // pairs fall back to the server's hardcoded defaults (capacity 30,
    // no homeroom).
    const overrides = missingClassPairs
      .map(p => {
        const key = `${p.grade_code}||${p.section_code}`;
        const ov = classOverrides[key] || {};
        const hasCap = ov.capacity !== undefined && ov.capacity !== '' && ov.capacity !== null;
        const hasHr = !!ov.homeroom_teacher_id;
        const hasCr = !!ov.classroom_id;
        // A grade/section override only counts when the principal
        // actually typed something different from the parsed value.
        const gTrim = (ov.grade_override ?? '').trim();
        const sTrim = (ov.section_override ?? '').trim();
        const hasG = gTrim !== '' && gTrim !== (p.grade_code || '');
        const hasS = sTrim !== '' && sTrim !== (p.section_code || '');
        if (!hasCap && !hasHr && !hasCr && !hasG && !hasS) return null;
        const entry = { grade_code: p.grade_code, section_code: p.section_code };
        if (hasCap) entry.capacity = Number(ov.capacity);
        if (hasHr) entry.homeroom_teacher_id = ov.homeroom_teacher_id;
        if (hasCr) entry.classroom_id = ov.classroom_id;
        if (hasG) entry.grade_override = gTrim;
        if (hasS) entry.section_override = sTrim;
        return entry;
      })
      .filter(Boolean);
    // Client-side capacity validation — mirror the backend's 1..500
    // range so the principal sees an Arabic error instead of a 400.
    for (const o of overrides) {
      if (o.capacity !== undefined && (!Number.isInteger(o.capacity) || o.capacity < 1 || o.capacity > 500)) {
        nassaqWarning('السعة يجب أن تكون رقماً صحيحاً بين 1 و 500');
        return;
      }
    }
    const pairsLabel = missingClassPairs
      .map(p => {
        const key = `${p.grade_code}||${p.section_code}`;
        const ov = classOverrides[key] || {};
        const cap = (ov.capacity !== undefined && ov.capacity !== '' && ov.capacity !== null) ? Number(ov.capacity) : 30;
        const teacher = ov.homeroom_teacher_id
          ? (teachersList.find(t => t.id === ov.homeroom_teacher_id)?.full_name || '')
          : '';
        const room = ov.classroom_id
          ? (classroomsList.find(c => c.id === ov.classroom_id)?.name || '')
          : '';
        const hrLabel = teacher ? ` · رائد: ${teacher}` : '';
        const roomLabel = room ? ` · قاعة: ${room}` : '';
        const gTrim = (ov.grade_override ?? '').trim();
        const sTrim = (ov.section_override ?? '').trim();
        const effG = gTrim || p.grade_code || '—';
        const effS = sTrim || p.section_code || '—';
        return `• ${effG} / ${effS}  (${p.rows} صف، سعة ${cap}${hrLabel}${roomLabel})`;
      })
      .join('\n');
    nassaqConfirm(
      `سيتم إنشاء ${missingClassPairs.length} فصلاً جديداً ثم إعادة مطابقة الطلاب تلقائياً.\n\nالفصول المقترحة:\n${pairsLabel}`,
      async () => {
        setCreatingClasses(true);
        try {
          const res = await api.post(
            `/noor-import/draft/${preview.import_draft_id}/create-missing-classes`,
            overrides.length > 0 ? { overrides } : {},
          );
          const data = res.data;
          setPreview(prev => prev ? { ...prev, rows: data.rows, counts: data.counts } : prev);
          const created = data.created_classes || [];
          setUndoableClasses(created);
          const createdN = created.length;
          const rejectedN = (data.rejected_pairs || []).length;
          const skippedN = (data.skipped_existing_classes || []).length;
          let msg = `تم إنشاء ${createdN} فصلاً وإعادة المطابقة.`;
          if (skippedN > 0) msg += ` تم تجاهل ${skippedN} مكرراً مع فصول موجودة.`;
          if (rejectedN > 0) msg += ` تعذّر إنشاء ${rejectedN} لتعذر تحديد الصف/الفصل بشكل قاطع.`;
          if (nassaqInfo) nassaqInfo(msg);
        } catch (err) {
          nassaqError(getApiErrorMessage(err) || 'تعذّر إنشاء الفصول الناقصة');
        } finally {
          setCreatingClasses(false);
        }
      },
      { title: 'إنشاء الفصول الناقصة', confirmText: 'إنشاء وإعادة المطابقة', cancelText: 'إلغاء' },
    );
  };

  const onUndoCreatedClasses = async () => {
    if (!preview?.import_draft_id) return;
    if (undoableClasses.length === 0) return;
    const ids = undoableClasses.map(c => c.class_id).filter(Boolean);
    const pairsLabel = undoableClasses
      .map(c => `• ${c.grade_code || '—'} / ${c.section_code || '—'}`)
      .join('\n');
    nassaqConfirm(
      `سيتم حذف ${ids.length} فصلاً تم إنشاؤه للتو، وإعادة الصفوف المرتبطة بها إلى حالة "بدون فصل". يتم رفض الحذف لأي فصل أصبح يحتوي على طلاب.\n\nالفصول:\n${pairsLabel}`,
      async () => {
        setUndoingClasses(true);
        try {
          const res = await api.post(
            `/noor-import/draft/${preview.import_draft_id}/undo-created-classes`,
            { class_ids: ids },
          );
          const data = res.data;
          setPreview(prev => prev ? { ...prev, rows: data.rows, counts: data.counts } : prev);
          const undoneN = (data.undone_classes || []).length;
          const refused = data.refused_classes || [];
          const refusedHas = refused.filter(c => c.reason === 'has_students');
          let msg = `تم التراجع عن ${undoneN} فصلاً.`;
          if (refusedHas.length > 0) {
            msg += ` تعذّر حذف ${refusedHas.length} فصلاً لاحتوائها على طلاب.`;
          }
          const otherRefused = refused.length - refusedHas.length;
          if (otherRefused > 0) msg += ` تعذّر حذف ${otherRefused} فصلاً.`;
          setUndoableClasses([]);
          if (nassaqInfo) nassaqInfo(msg);
        } catch (err) {
          nassaqError(getApiErrorMessage(err) || 'تعذّر التراجع عن إنشاء الفصول');
        } finally {
          setUndoingClasses(false);
        }
      },
      { title: 'التراجع عن إنشاء الفصول', confirmText: 'تراجع', cancelText: 'إبقاء الفصول' },
    );
  };

  const onUndoImported = async () => {
    const hasStudents = undoableStudentIds.length > 0;
    const hasTeachers = undoableTeacherIds.length > 0;
    if ((!hasStudents && !hasTeachers) || !undoToken) return;

    const parts = [];
    if (hasStudents) parts.push(`${undoableStudentIds.length} طالباً`);
    if (hasTeachers) parts.push(`${undoableTeacherIds.length} معلماً`);
    nassaqConfirm(
      `سيتم حذف ${parts.join(' و')} تم استيرادهم للتو. لن يتم حذف أي سجل له بيانات حضور أو درجات أو روابط أولياء أمور أو مهام — سيتم إبلاغك بالحالات المرفوضة.`,
      async () => {
        setUndoingCommitted(true);
        try {
          const res = await api.post('/noor-import/undo-committed', {
            undo_token: undoToken,
          });
          const data = res.data;
          const undoneS = (data.undone_students || []).length;
          const undoneT = (data.undone_teachers || []).length;
          const refusedS = (data.refused_students || []).filter(r => r.reason !== 'not_found');
          const refusedT = (data.refused_teachers || []).filter(r => r.reason !== 'not_found');
          setUndoableStudentIds([]);
          setUndoableTeacherIds([]);
          setUndoToken(null);
          let msg = '';
          if (undoneS > 0) msg += `تم حذف ${undoneS} طالباً. `;
          if (undoneT > 0) msg += `تم حذف ${undoneT} معلماً. `;
          if (refusedS.length > 0) msg += `تعذّر حذف ${refusedS.length} طالباً (لديهم بيانات مرتبطة). `;
          if (refusedT.length > 0) msg += `تعذّر حذف ${refusedT.length} معلماً (لديهم بيانات مرتبطة). `;
          if (nassaqInfo) nassaqInfo(msg.trim() || 'تم التراجع عن الاستيراد.');
        } catch (err) {
          nassaqError(getApiErrorMessage(err) || 'تعذّر التراجع عن الاستيراد');
        } finally {
          setUndoingCommitted(false);
        }
      },
      { title: 'التراجع عن الاستيراد', confirmText: 'تراجع عن الاستيراد', cancelText: 'إبقاء السجلات' },
    );
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

  // Full reset back to the clean, import-ready state. Clears every piece
  // of preview-stage state (selected file, parsed rows, counts, row-level
  // edits, validation/undo banners) AND the native file input's value so
  // no stale filename, counter, badge, or executable payload lingers.
  const resetImportState = useCallback(() => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setAmbiguousAccept({});
    setClassOverrides({});
    setUndoableClasses([]);
    setUndoableStudentIds([]);
    setUndoableTeacherIds([]);
    setUndoToken(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  // Cancel the in-progress preview/import session. Discards the
  // server-side draft FIRST (so the abandoned preview can never be
  // committed — /commit will 403 on the now-deleted draft) and only then
  // wipes the local state. Even if the discard call fails (e.g. the draft
  // already expired), the UI is still reset because the in-memory
  // import_draft_id is dropped, leaving nothing executable.
  const doCancelImport = useCallback(async () => {
    const draftId = preview?.import_draft_id;
    setCancelling(true);
    try {
      if (draftId) {
        await api.post(`/noor-import/draft/${draftId}/discard`);
      }
      resetImportState();
      if (nassaqInfo) nassaqInfo('تم إلغاء المعاينة. يمكنك رفع ملف جديد للبدء من جديد.');
    } catch (err) {
      // The draft may already be gone/expired — that's still a successful
      // cancel from the user's perspective, so reset the UI regardless and
      // surface the reason only for genuine unexpected failures.
      resetImportState();
      nassaqError(getApiErrorMessage(err) || 'تعذّر إلغاء المعاينة — تم تفريغ الشاشة على أي حال');
    } finally {
      setCancelling(false);
    }
  }, [api, preview, resetImportState, nassaqError, nassaqInfo]);

  const onCancelImport = () => {
    if (!preview) return;
    const hasAmbiguousEdits = Object.values(ambiguousAccept).some(Boolean);
    const hasClassEdits = Object.keys(classOverrides).length > 0;
    const hasCreatedClasses = undoableClasses.length > 0;
    // Only interrupt with a confirmation when the principal would actually
    // lose preview-stage work; a pristine preview cancels immediately.
    if (!hasAmbiguousEdits && !hasClassEdits && !hasCreatedClasses) {
      doCancelImport();
      return;
    }
    let msg = 'سيتم إلغاء المعاينة الحالية دون تنفيذ الاستيراد، وستفقد التعديلات التي أجريتها على هذه المعاينة.';
    if (hasCreatedClasses) {
      msg += `\n\nملاحظة: الفصول التي أنشأتها أثناء المعاينة (${undoableClasses.length}) ستبقى في المدرسة — استخدم زر "تراجع عن إنشاء الفصول" أولاً إن أردت حذفها قبل الإلغاء.`;
    }
    nassaqConfirm(
      msg,
      doCancelImport,
      { title: 'إلغاء الاستيراد', confirmText: 'إلغاء المعاينة', cancelText: 'متابعة المعاينة' },
    );
  };

  const detectedLabel = preview?.detected_type === 'teachers' ? 'تقرير المعلمين (نور)' : preview?.detected_type === 'students' ? 'إرشاد الطلاب (نور)' : '';

  const tabCls = (key) =>
    `px-4 py-1.5 rounded-lg text-xs font-medium transition-colors ${
      activeTab === key
        ? 'bg-brand-turquoise text-white shadow-sm'
        : 'text-muted-foreground hover:text-foreground hover:bg-muted'
    }`;

  return (
    <Card className="mb-2 border-brand-turquoise/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Database className="h-5 w-5 text-brand-turquoise" />استيراد من نظام نور</CardTitle>
        <CardDescription>ارفع تقرير نور كما هو دون تعديل — سيتم اكتشاف نوع التقرير ومعاينته قبل التنفيذ.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-1 p-1 bg-muted/60 rounded-xl w-fit">
          <button type="button" className={tabCls('import')} onClick={() => setActiveTab('import')}>
            <Upload className="inline h-3.5 w-3.5 me-1.5 -mt-0.5" />
            استيراد جديد
          </button>
          <button type="button" className={tabCls('history')} onClick={() => setActiveTab('history')}>
            <History className="inline h-3.5 w-3.5 me-1.5 -mt-0.5" />
            سجل الاستيرادات
          </button>
        </div>

        {activeTab === 'history' && (
          <HistoryTab
            api={api}
            nassaqError={nassaqError}
            nassaqConfirm={nassaqConfirm}
            nassaqInfo={nassaqInfo}
          />
        )}

        {activeTab === 'import' && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <Input ref={fileInputRef} type="file" accept=".xlsx,.xls" onChange={onSelect} className="max-w-sm" />
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
                    <div className="flex-1">
                      <p className="font-medium">سيتم استيراد {preview.counts.unclassified} صفاً بدون ربطه بفصل دراسي.</p>
                      <p className="text-yellow-800 dark:text-yellow-200 mt-0.5">
                        تعذّر مطابقة قيم "رقم الصف" / "الفصل" في الملف مع فصول المدرسة الحالية.
                      </p>
                      {needsClassEditor && (
                        <div className="mt-2 space-y-2">
                          <p className="text-[11px] text-yellow-800 dark:text-yellow-200">
                            راجع الصف والفصل لكل سطر (يمكنك تصحيحهما إن كانت قيم الملف غير صحيحة)، ثم اختر السعة ورائد الفصل والقاعة (السعة الافتراضية 30، يمكنك تركها كما هي).
                          </p>
                          <div className="max-h-[220px] overflow-auto border border-yellow-300 dark:border-yellow-700 rounded">
                            <table className="w-full text-[11px]" data-testid="missing-class-pairs">
                              <thead className="bg-yellow-100 dark:bg-yellow-900/40">
                                <tr>
                                  <th className="p-1.5 text-start">الصف</th>
                                  <th className="p-1.5 text-start">الفصل</th>
                                  <th className="p-1.5 text-start">عدد الطلاب</th>
                                  <th className="p-1.5 text-start">السعة</th>
                                  <th className="p-1.5 text-start">رائد الفصل</th>
                                  <th className="p-1.5 text-start">القاعة</th>
                                </tr>
                              </thead>
                              <tbody>
                                {missingClassPairs.map((p, i) => {
                                  const key = `${p.grade_code}||${p.section_code}`;
                                  const ov = classOverrides[key] || {};
                                  const gVal = ov.grade_override !== undefined ? ov.grade_override : (p.grade_code || '');
                                  const sVal = ov.section_override !== undefined ? ov.section_override : (p.section_code || '');
                                  return (
                                    <tr key={i} className="border-t border-yellow-200 dark:border-yellow-800">
                                      <td className="p-1.5">
                                        <input
                                          type="text"
                                          value={gVal}
                                          onChange={(e) => setOverride(key, { grade_override: e.target.value })}
                                          placeholder={p.grade_code || '—'}
                                          maxLength={32}
                                          data-testid={`grade-input-${i}`}
                                          className="w-16 px-1.5 py-0.5 rounded border border-yellow-300 dark:border-yellow-700 bg-white dark:bg-yellow-950/60 text-[11px]"
                                        />
                                      </td>
                                      <td className="p-1.5">
                                        <input
                                          type="text"
                                          value={sVal}
                                          onChange={(e) => setOverride(key, { section_override: e.target.value })}
                                          placeholder={p.section_code || '—'}
                                          maxLength={32}
                                          data-testid={`section-input-${i}`}
                                          className="w-16 px-1.5 py-0.5 rounded border border-yellow-300 dark:border-yellow-700 bg-white dark:bg-yellow-950/60 text-[11px]"
                                        />
                                      </td>
                                      <td className="p-1.5">{p.rows}</td>
                                      <td className="p-1.5">
                                        <input
                                          type="number"
                                          min={1}
                                          max={500}
                                          placeholder="30"
                                          value={ov.capacity ?? ''}
                                          onChange={(e) => setOverride(key, { capacity: e.target.value })}
                                          data-testid={`capacity-input-${i}`}
                                          className="w-16 px-1.5 py-0.5 rounded border border-yellow-300 dark:border-yellow-700 bg-white dark:bg-yellow-950/60 text-[11px]"
                                        />
                                      </td>
                                      <td className="p-1.5">
                                        <select
                                          value={ov.homeroom_teacher_id || ''}
                                          onChange={(e) => setOverride(key, { homeroom_teacher_id: e.target.value || undefined })}
                                          disabled={loadingTeachers}
                                          data-testid={`homeroom-select-${i}`}
                                          className="max-w-[180px] px-1.5 py-0.5 rounded border border-yellow-300 dark:border-yellow-700 bg-white dark:bg-yellow-950/60 text-[11px]"
                                        >
                                          <option value="">{loadingTeachers ? 'جارٍ التحميل…' : 'بدون'}</option>
                                          {teachersList.map(t => (
                                            <option key={t.id} value={t.id}>{t.full_name}</option>
                                          ))}
                                        </select>
                                      </td>
                                      <td className="p-1.5">
                                        <select
                                          value={ov.classroom_id || ''}
                                          onChange={(e) => setOverride(key, { classroom_id: e.target.value || undefined })}
                                          disabled={loadingClassrooms}
                                          data-testid={`classroom-select-${i}`}
                                          className="max-w-[160px] px-1.5 py-0.5 rounded border border-yellow-300 dark:border-yellow-700 bg-white dark:bg-yellow-950/60 text-[11px]"
                                        >
                                          <option value="">{loadingClassrooms ? 'جارٍ التحميل…' : 'بدون'}</option>
                                          {classroomsList.map(c => (
                                            <option key={c.id} value={c.id}>{c.name}</option>
                                          ))}
                                        </select>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                          <Button
                            size="sm"
                            type="button"
                            variant="outline"
                            disabled={creatingClasses}
                            onClick={onCreateMissingClasses}
                            data-testid="btn-create-missing-classes"
                            className="border-yellow-500 text-yellow-900 hover:bg-yellow-100 hover:text-yellow-900 dark:text-yellow-100 dark:hover:bg-yellow-900/40 dark:hover:text-yellow-100"
                          >
                            {creatingClasses ? <Loader2 className="h-3.5 w-3.5 animate-spin me-2" /> : <Database className="h-3.5 w-3.5 me-2" />}
                            إنشاء الفصول الناقصة وإعادة المطابقة
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {undoableClasses.length > 0 && (
                  <div
                    data-testid="undo-created-classes-banner"
                    className="text-xs p-3 rounded border border-blue-300 bg-blue-50 dark:bg-blue-950/30 text-blue-900 dark:text-blue-100 flex items-start gap-2"
                  >
                    <Undo2 className="h-4 w-4 mt-0.5 shrink-0" />
                    <div className="flex-1 space-y-2">
                      <p className="font-medium">
                        تم إنشاء {undoableClasses.length} فصلاً للتو — يمكنك التراجع قبل المتابعة.
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {undoableClasses.slice(0, 12).map((c, i) => (
                          <span
                            key={c.class_id || i}
                            className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 border border-blue-300 dark:border-blue-700 text-[11px]"
                          >
                            {c.grade_code || '—'} / {c.section_code || '—'}
                          </span>
                        ))}
                        {undoableClasses.length > 12 && (
                          <span className="text-[11px] text-blue-800 dark:text-blue-200">
                            +{undoableClasses.length - 12}
                          </span>
                        )}
                      </div>
                      <Button
                        size="sm"
                        type="button"
                        variant="outline"
                        disabled={undoingClasses}
                        onClick={onUndoCreatedClasses}
                        data-testid="btn-undo-created-classes"
                        className="border-blue-500 text-blue-900 hover:bg-blue-100 hover:text-blue-900 dark:text-blue-100 dark:hover:bg-blue-900/40 dark:hover:text-blue-100"
                      >
                        {undoingClasses ? <Loader2 className="h-3.5 w-3.5 animate-spin me-2" /> : <Undo2 className="h-3.5 w-3.5 me-2" />}
                        تراجع عن إنشاء الفصول
                      </Button>
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
                <div className="flex flex-wrap justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onCancelImport}
                    disabled={cancelling || committing}
                    data-testid="btn-cancel-import"
                  >
                    {cancelling ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : null}
                    إلغاء الاستيراد
                  </Button>
                  <Button
                    onClick={onCommit}
                    disabled={committing || cancelling}
                    type="button"
                    className="bg-brand-turquoise hover:bg-brand-turquoise/90"
                    data-testid="btn-execute-import"
                  >
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
                {undoToken && (undoableStudentIds.length > 0 || undoableTeacherIds.length > 0) && (
                  <div
                    data-testid="undo-committed-banner"
                    className="text-xs p-3 rounded border border-amber-300 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-100 flex items-start gap-2"
                  >
                    <Undo2 className="h-4 w-4 mt-0.5 shrink-0" />
                    <div className="flex-1 space-y-2">
                      <p className="font-medium">
                        {[
                          undoableStudentIds.length > 0 && `${undoableStudentIds.length} طالباً`,
                          undoableTeacherIds.length > 0 && `${undoableTeacherIds.length} معلماً`,
                        ].filter(Boolean).join(' و')}
                        {' '}تم استيرادهم للتو — يمكنك التراجع قبل إغلاق هذا القسم.
                      </p>
                      <p className="text-amber-800 dark:text-amber-200">
                        لن يتم حذف أي سجل له بيانات حضور أو درجات أو مهام — ستظهر حالات الرفض بوضوح.
                      </p>
                      <Button
                        size="sm"
                        type="button"
                        variant="outline"
                        disabled={undoingCommitted}
                        onClick={onUndoImported}
                        data-testid="btn-undo-committed"
                        className="border-amber-500 text-amber-900 hover:bg-amber-100 hover:text-amber-900 dark:text-amber-100 dark:hover:bg-amber-900/40 dark:hover:text-amber-100"
                      >
                        {undoingCommitted ? <Loader2 className="h-3.5 w-3.5 animate-spin me-2" /> : <Undo2 className="h-3.5 w-3.5 me-2" />}
                        تراجع عن استيراد السجلات
                      </Button>
                    </div>
                  </div>
                )}
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
          </>
        )}
      </CardContent>
    </Card>
  );
}
