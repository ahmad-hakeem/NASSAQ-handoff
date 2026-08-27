/**
 * SessionEditDrawer — manual timetable editing for the new master grid.
 *
 * Replaces the old SchedulePage drag-and-drop edit pipeline with an
 * intentional drawer that lives inside the new Grid Matrix. Supports
 * two modes:
 *   - 'edit'   → existing session: change teacher / subject / class / move day&period / delete
 *   - 'create' → empty cell: pick class + subject + teacher to add a lesson
 *
 * Wires to the existing backend mutation endpoints (no duplication):
 *   PUT    /smart-scheduling/session/:id          (edit, conflict-aware)
 *   PUT    /smart-scheduling/session/:id/force    (override conflicts)
 *   DELETE /smart-scheduling/session/:id          (delete)
 *   POST   /smart-scheduling/session/add          (create, JSON body)
 *
 * Editing is gated to draft timetables only — the page suppresses the
 * affordance when scheduleView === 'published'. Published edits are
 * additionally blocked at the backend layer.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/shared/components/ui/sheet';
import { Button } from '@/shared/components/ui/button';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/shared/components/ui/select';
import { Loader2, Save, Trash2, AlertTriangle, Plus, Pencil } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation, useTheme } from '@/shared/contexts/ThemeContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const DAY_KEYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

export default function SessionEditDrawer({
  open,
  mode,                // 'edit' | 'create'
  context,             // { session, day_of_week, period_number, teacher_id, class_id, subject_id }
  schoolId,
  timetableId,
  teachers = [],       // from grid.teachers
  periods = [],        // from grid.periods
  api,
  onClose,
  onSaved,             // (updatedAction) => void   — called after a successful mutation
}) {
  const { t } = useTranslation();
  const { direction } = useTheme();
  const { nassaqError, nassaqConfirm } = useNassaqAlert();

  const isCreate = mode === 'create';

  const [teacherId, setTeacherId] = useState('');
  const [classId, setClassId]     = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [day, setDay]             = useState('');
  const [period, setPeriod]       = useState(0);

  const [classes, setClasses]   = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loadingLookups, setLoadingLookups] = useState(false);

  const [saving, setSaving]     = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [conflicts, setConflicts] = useState([]);

  const session = context?.session || null;
  const sessionId = session?.session_id || session?.id || null;

  // Lookup classes + subjects whenever drawer is open so both create and edit
  // modes have the complete catalog available.
  useEffect(() => {
    if (!open || !schoolId || !api) return;
    let cancelled = false;
    setLoadingLookups(true);
    Promise.all([
      api.get('/classes', { params: { school_id: schoolId } }).catch(() => ({ data: [] })),
      api.get('/subjects', { params: { school_id: schoolId } }).catch(() => ({ data: [] })),
    ]).then(([cs, ss]) => {
      if (cancelled) return;
      setClasses(Array.isArray(cs?.data) ? cs.data : []);
      setSubjects(Array.isArray(ss?.data) ? ss.data : []);
    }).finally(() => { if (!cancelled) setLoadingLookups(false); });
    return () => { cancelled = true; };
  }, [open, schoolId, api]);

  // Hydrate form from context whenever the drawer opens or catalogs resolve.
  useEffect(() => {
    if (!open) return;
    setConflicts([]);

    // 1. Teacher ID resolution
    let resolvedTeacherId = context?.teacher_id || session?.teacher_id || '';
    if (!resolvedTeacherId && (session?.teacher_name || context?.teacher_name)) {
      const targetTeacherName = (session?.teacher_name || context?.teacher_name || '').trim().toLowerCase();
      const matched = teachers.find(t2 =>
        (t2.full_name && t2.full_name.trim().toLowerCase() === targetTeacherName) ||
        (t2.name && t2.name.trim().toLowerCase() === targetTeacherName) ||
        t2.id === targetTeacherName
      );
      if (matched) resolvedTeacherId = matched.id;
    }
    setTeacherId(resolvedTeacherId);

    // 2. Class ID resolution
    let resolvedClassId = context?.class_id || session?.class_id || '';
    if (!resolvedClassId && (session?.class_name || context?.class_name) && classes.length > 0) {
      const targetClassName = (session?.class_name || context?.class_name || '').trim().toLowerCase();
      const matchedClass = classes.find(c =>
        (c.name && c.name.trim().toLowerCase() === targetClassName) ||
        (c.name_ar && c.name_ar.trim().toLowerCase() === targetClassName) ||
        c.id === targetClassName
      );
      if (matchedClass) resolvedClassId = matchedClass.id;
    }
    setClassId(resolvedClassId);

    // 3. Subject ID resolution
    let resolvedSubjectId = context?.subject_id || session?.subject_id || '';
    if (!resolvedSubjectId && (session?.subject_name || context?.subject_name) && subjects.length > 0) {
      const targetSubjectName = (session?.subject_name || context?.subject_name || '').trim().toLowerCase();
      const matchedSubject = subjects.find(s =>
        (s.name_ar && s.name_ar.trim().toLowerCase() === targetSubjectName) ||
        (s.name && s.name.trim().toLowerCase() === targetSubjectName) ||
        s.id === targetSubjectName
      );
      if (matchedSubject) resolvedSubjectId = matchedSubject.id;
    }
    setSubjectId(resolvedSubjectId);

    // 4. Day resolution
    const resolvedDay = context?.day_of_week || session?.day_of_week || '';
    setDay(resolvedDay);

    // 5. Period resolution (support period_number, slot_number, period)
    const rawPeriod = context?.period_number ?? session?.period_number
      ?? context?.slot_number ?? session?.slot_number
      ?? context?.period ?? session?.period ?? 0;
    setPeriod(Number(rawPeriod));
  }, [open, context, session, teachers, classes, subjects]);

  const teacherOptions = useMemo(() => {
    const opts = teachers.map(t2 => ({ value: t2.id, label: t2.full_name || t2.name || t2.id }));
    if (teacherId && !opts.some(o => o.value === teacherId)) {
      opts.unshift({ value: teacherId, label: session?.teacher_name || context?.teacher_name || teacherId });
    }
    return opts;
  }, [teachers, teacherId, session, context]);

  const classOptions = useMemo(() => {
    const opts = classes.map(c => ({ value: c.id, label: c.name || c.name_ar || c.id }));
    if (classId && !opts.some(o => o.value === classId)) {
      opts.unshift({ value: classId, label: session?.class_name || context?.class_name || classId });
    }
    return opts;
  }, [classes, classId, session, context]);

  const subjectOptions = useMemo(() => {
    const opts = subjects.map(s => ({ value: s.id, label: s.name_ar || s.name || s.id }));
    if (subjectId && !opts.some(o => o.value === subjectId)) {
      opts.unshift({ value: subjectId, label: session?.subject_name || context?.subject_name || subjectId });
    }
    return opts;
  }, [subjects, subjectId, session, context]);

  const periodOptions = useMemo(
    () => (periods?.length ? periods : [1,2,3,4,5,6,7]).map(p => ({ value: Number(p), label: String(p) })),
    [periods],
  );

  const canSave = isCreate
    ? Boolean(teacherId && classId && subjectId && day && period)
    : Boolean(teacherId && day && period);

  // ── Mutations ────────────────────────────────────────────────────────
  const callEdit = async (force = false) => {
    if (!sessionId) {
      nassaqError(t('sessionEditMissingId'));
      return null;
    }
    const url = force
      ? `/smart-scheduling/session/${sessionId}/force`
      : `/smart-scheduling/session/${sessionId}`;
    const body = {
      teacher_id: teacherId || undefined,
      class_id: classId || undefined,
      subject_id: subjectId || undefined,
      day_of_week: day || undefined,
      period_number: Number(period),
    };
    const resp = await api.put(url, body, {
      headers: { 'X-School-Context': schoolId },
    });
    return resp?.data;
  };

  const callCreate = async (force = false) => {
    if (!timetableId) {
      nassaqError(t('sessionEditMissingTimetable'));
      return null;
    }
    const resp = await api.post(
      '/smart-scheduling/session/add',
      {
        timetable_id: timetableId,
        class_id: classId,
        subject_id: subjectId,
        teacher_id: teacherId,
        day_of_week: day,
        period_number: Number(period),
        force,
      },
      { headers: { 'X-School-Context': schoolId } },
    );
    return resp?.data;
  };

  const handleSave = async (force = false) => {
    if (!canSave) return;
    setSaving(true);
    setConflicts([]);
    try {
      const data = isCreate ? await callCreate(force) : await callEdit(force);
      if (!data) return;
      // Conflict response (success=false + conflicts[]) — surface inline.
      if (data.success === false && Array.isArray(data.conflicts) && data.conflicts.length) {
        setConflicts(data.conflicts);
        return;
      }
      toast.success(data.message_ar || t('sessionEditSaved'));
      onSaved?.(isCreate ? 'created' : 'updated');
      onClose?.();
    } catch (e) {
      const data = e?.response?.data;
      const detail = data?.detail;
      let msg = t('sessionEditFailed');
      if (typeof detail === 'string' && detail) msg = detail;
      else if (detail?.message_ar) msg = detail.message_ar;
      else if (data?.message_ar) msg = data.message_ar;
      else if (data?.error?.message) msg = data.error.message;
      // Surface field-level validation errors
      const fieldErrors = data?.meta?.validation_errors;
      if (Array.isArray(fieldErrors) && fieldErrors.length) {
        const lines = fieldErrors
          .map((fe) => `• ${fe.field}: ${fe.message}`)
          .join('\n');
        msg = `${msg}\n${lines}`;
      }
      nassaqError(msg, { title: t('sessionEditFailedTitle') });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (!sessionId) return;
    nassaqConfirm(
      t('sessionDeleteConfirmMessage'),
      async () => {
        setDeleting(true);
        try {
          await api.delete(`/smart-scheduling/session/${sessionId}`, {
            headers: { 'X-School-Context': schoolId },
          });
          toast.success(t('sessionDeleted'));
          onSaved?.('deleted');
          onClose?.();
        } catch (e) {
          const detail = getApiErrorMessage(e);
          const msg = (typeof detail === 'string' && detail) || detail?.message_ar
            || e?.response?.data?.message_ar || t('sessionDeleteFailed');
          nassaqError(msg, { title: t('sessionDeleteFailedTitle') });
        } finally {
          setDeleting(false);
        }
      },
      { title: t('sessionDeleteConfirmTitle'), confirmText: t('deleteAction') },
    );
  };

  const titleIcon = isCreate ? <Plus className="h-5 w-5 text-emerald-600" /> : <Pencil className="h-5 w-5 text-brand-turquoise" />;

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose?.(); }}>
      <SheetContent
        side={direction === 'rtl' ? 'left' : 'right'}
        dir={direction}
        className="w-full sm:max-w-md p-0 flex flex-col gap-0"
        data-testid="session-edit-drawer"
      >
        <SheetHeader className="p-5 bg-gradient-to-l from-brand-turquoise/15 to-brand-turquoise/5 border-b border-brand-turquoise/30 text-start">
          <SheetTitle className="flex items-center gap-2 text-brand-navy">
            {titleIcon}
            {isCreate ? t('sessionCreateTitle') : t('sessionEditTitle')}
          </SheetTitle>
          <SheetDescription className="text-brand-navy/70 text-xs leading-relaxed">
            {isCreate ? t('sessionCreateDescription') : t('sessionEditDescription')}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
          {/* ── Class (both create and edit modes) ─────────────────── */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">{t('classLabel')}</Label>
            <Select value={classId} onValueChange={setClassId} disabled={loadingLookups}>
              <SelectTrigger data-testid="session-edit-class">
                <SelectValue placeholder={t('selectClass')} />
              </SelectTrigger>
              <SelectContent dir={direction}>
                {classOptions.map(c => (
                  <SelectItem key={c.value} value={c.value}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* ── Subject (both create and edit modes) ───────────────── */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">{t('subjectLabel')}</Label>
            <Select value={subjectId} onValueChange={setSubjectId} disabled={loadingLookups}>
              <SelectTrigger data-testid="session-edit-subject">
                <SelectValue placeholder={t('selectSubject')} />
              </SelectTrigger>
              <SelectContent dir={direction}>
                {subjectOptions.map(s => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* ── Teacher ────────────────────────────────────────── */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">{t('teacherLabel')}</Label>
            <Select value={teacherId} onValueChange={setTeacherId}>
              <SelectTrigger data-testid="session-edit-teacher">
                <SelectValue placeholder={t('selectTeacher')} />
              </SelectTrigger>
              <SelectContent dir={direction}>
                {teacherOptions.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* ── Day + period ──────────────────────────────────── */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">{t('dayLabel')}</Label>
              <Select value={day} onValueChange={setDay}>
                <SelectTrigger data-testid="session-edit-day">
                  <SelectValue placeholder={t('selectDay')} />
                </SelectTrigger>
                <SelectContent dir={direction}>
                  {DAY_KEYS.map(d => (
                    <SelectItem key={d} value={d}>{t(d)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">{t('periodLabelOnly')}</Label>
              <Select value={String(period || '')} onValueChange={(v) => setPeriod(Number(v))}>
                <SelectTrigger data-testid="session-edit-period">
                  <SelectValue placeholder={t('selectPeriod')} />
                </SelectTrigger>
                <SelectContent dir={direction}>
                  {periodOptions.map(opt => (
                    <SelectItem key={opt.value} value={String(opt.value)}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* ── Conflict warnings (inline, NOT toast.error) ──── */}
          {conflicts.length > 0 && (
            <div
              data-testid="session-edit-conflicts"
              className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm"
            >
              <div className="flex items-center gap-1.5 text-amber-800 font-bold mb-1.5">
                <AlertTriangle className="h-4 w-4" />
                {t('sessionConflictsDetected')}
              </div>
              <ul className="space-y-1 text-xs text-amber-900 list-disc list-inside">
                {conflicts.map((c, i) => (
                  <li key={i}>{c.message_ar || c.message_en || c.type}</li>
                ))}
              </ul>
              <Button
                type="button"
                size="sm"
                onClick={() => handleSave(true)}
                disabled={saving}
                className="mt-2 bg-amber-600 hover:bg-amber-700 text-white h-8"
                data-testid="session-edit-force"
              >
                {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}
                {t('saveAnywayAction')}
              </Button>
            </div>
          )}
        </div>

        {/* ── Footer actions ──────────────────────────────────── */}
        <div className="border-t border-slate-200 bg-white p-3 flex items-center justify-between gap-2">
          <div>
            {!isCreate && sessionId && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleDelete}
                disabled={deleting || saving}
                className="border-red-300 text-red-700 hover:bg-red-50 hover:text-red-700 focus-visible:text-red-700 gap-1.5"
                data-testid="session-edit-delete"
              >
                {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                {t('deleteAction')}
              </Button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={saving || deleting}>
              {t('cancelAction')}
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => handleSave(false)}
              disabled={!canSave || saving || deleting}
              className="bg-brand-turquoise hover:bg-brand-turquoise-dark text-white gap-1.5"
              data-testid="session-edit-save"
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              {isCreate ? t('addAction') : t('saveAction')}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
