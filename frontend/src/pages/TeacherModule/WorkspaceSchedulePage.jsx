import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, CalendarDays, Trash2, Check, Printer, Plus } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';

const DAY_LABELS = {
  sun: 'الأحد', mon: 'الاثنين', tue: 'الثلاثاء', wed: 'الأربعاء',
  thu: 'الخميس', fri: 'الجمعة', sat: 'السبت',
};

const slotKey = (day, slot) => `${day}__${slot}`;

export default function WorkspaceSchedulePage() {
  const navigate = useNavigate();
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError, nassaqSuccess, nassaqConfirm } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [grid, setGrid] = useState({
    workspace_id: '',
    working_days: [],
    periods_per_day: 7,
    period_minutes: 45,
    sessions: [],
    classes: [],
    subjects: [],
  });
  const [editing, setEditing] = useState(null); // { day, slot, classId, subjectId, version }
  const [saving, setSaving] = useState(false);

  const isIndependent = (user?.role || '').toLowerCase() === 'independent_teacher';

  useEffect(() => {
    if (!isIndependent) navigate('/teacher', { replace: true });
  }, [isIndependent, navigate]);

  const reload = useCallback(async () => {
    if (!api || !isIndependent) return;
    setLoading(true);
    try {
      const { data } = await api.get('/independent-teacher/schedule/grid');
      const slots = Array.isArray(data?.slots)
        ? data.slots
        : (Array.isArray(data?.sessions) ? data.sessions : []);
      setGrid({
        workspace_id: data?.workspace_id || '',
        working_days: Array.isArray(data?.working_days) ? data.working_days : [],
        periods_per_day: Number(data?.periods_per_day) || 7,
        period_minutes: Number(data?.period_minutes) || 45,
        sessions: slots,
        classes: Array.isArray(data?.classes) ? data.classes : [],
        subjects: Array.isArray(data?.subjects) ? data.subjects : [],
      });
    } catch (err) {
      const msg = err?.response?.data?.detail
        || err?.response?.data?.error?.message
        || 'تعذّر تحميل جدولك.';
      nassaqError(typeof msg === 'string' ? msg : (msg?.message || 'تعذّر تحميل جدولك.'));
    } finally {
      setLoading(false);
    }
  }, [api, isIndependent, nassaqError]);

  useEffect(() => { reload(); }, [reload]);

  const sessionsByKey = useMemo(() => {
    const m = new Map();
    for (const s of grid.sessions) m.set(slotKey(s.day_of_week, s.slot_number), s);
    return m;
  }, [grid.sessions]);

  const slots = useMemo(
    () => Array.from({ length: grid.periods_per_day }, (_, i) => i + 1),
    [grid.periods_per_day],
  );

  const openEditor = (day, slot) => {
    const existing = sessionsByKey.get(slotKey(day, slot));
    setEditing({
      day,
      slot,
      classId: existing?.class_id || '',
      subjectId: existing?.subject_id || '',
      version: existing?.version || 0,
      hadContent: Boolean(existing?.class_id || existing?.subject_id),
    });
  };

  const closeEditor = () => setEditing(null);

  const extractConflict = (err) => {
    const detail = err?.response?.data?.detail || err?.response?.data?.error?.message;
    if (detail && typeof detail === 'object' && detail.code === 'schedule_slot_conflict') {
      return detail;
    }
    return null;
  };

  const persistSlot = async () => {
    if (!editing) return;
    const { day, slot, classId, subjectId, version, hadContent } = editing;
    const willClear = !classId && !subjectId;

    const submit = async () => {
      setSaving(true);
      try {
        if (willClear) {
          if (version === 0) {
            closeEditor();
            return;
          }
          await api.request({
            method: 'DELETE',
            url: '/independent-teacher/schedule/slot',
            data: {
              day_of_week: day,
              slot_number: slot,
              expected_version: version,
            },
          });
        } else {
          await api.put('/independent-teacher/schedule/slot', {
            day_of_week: day,
            slot_number: slot,
            expected_version: version,
            class_id: classId || null,
            subject_id: subjectId || null,
          });
        }
        nassaqSuccess('تم حفظ تعديلاتك على الجدول.');
        closeEditor();
        await reload();
      } catch (err) {
        const conflict = extractConflict(err);
        if (conflict) {
          nassaqError(conflict.message || 'تعارض في تحديث الحصة.');
          await reload();
          closeEditor();
        } else {
          const msg = err?.response?.data?.detail
            || err?.response?.data?.error?.message
            || 'تعذّر حفظ تعديلاتك على الجدول.';
          nassaqError(typeof msg === 'string' ? msg : (msg?.message || 'تعذّر حفظ تعديلاتك على الجدول.'));
        }
      } finally {
        setSaving(false);
      }
    };

    if (willClear && hadContent) {
      nassaqConfirm(
        'سيتم مسح محتوى هذه الحصة من جدولك. هل تريد المتابعة؟',
        submit,
        { title: 'مسح الحصة', confirmText: 'مسح', cancelText: 'إلغاء' },
      );
    } else if (hadContent) {
      nassaqConfirm(
        'سيتم استبدال محتوى هذه الحصة الحالي. هل تريد المتابعة؟',
        submit,
        { title: 'استبدال الحصة', confirmText: 'استبدال', cancelText: 'إلغاء' },
      );
    } else {
      await submit();
    }
  };

  const handleExport = async () => {
    try {
      const resp = await api.get('/independent-teacher/schedule/export.pdf', {
        responseType: 'blob',
      });
      const blob = new Blob([resp.data], { type: 'application/pdf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'my-schedule.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      const msg = err?.response?.data?.detail
        || err?.response?.data?.error?.message
        || 'تعذّر تنزيل ملف PDF لجدولك.';
      nassaqError(typeof msg === 'string' ? msg : (msg?.message || 'تعذّر تنزيل ملف PDF لجدولك.'));
    }
  };

  const dir = isRTL ? 'rtl' : 'ltr';
  if (!isIndependent) return null;

  return (
    <div dir={dir} className="min-h-screen bg-slate-50 py-6 px-4">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-emerald-800">جدولي</h1>
            <p className="text-sm text-slate-500 mt-1">
              قم بتعيين الفصول والمواد لكل حصّة في أيام عملك. يمكنك مسح أي حصّة في أي وقت.
            </p>
          </div>
          <Button
            onClick={handleExport}
            variant="outline"
            className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
            data-testid="workspace-schedule-export-btn"
          >
            <Printer className="h-4 w-4 ms-2" />
            تنزيل PDF
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
          </div>
        ) : (grid.sessions.length === 0) ? (
          // Task #200 §5.8 — IT zero-slots empty state for the schedule
          // editor. Trigger condition is "no scheduled sessions" (NOT
          // "no classes") so the surface also covers the case where the
          // IT has classes but the weekly grid is still blank. The CTA
          // routes to the classes page when no classes exist yet,
          // otherwise it scrolls into the existing grid by reloading the
          // editor. Copy is locale-driven for both languages.
          <Card
            className="bg-workspace-accent-light/30 border-workspace-accent-border"
            data-testid="workspace-schedule-empty-state"
          >
            <CardContent className="text-center py-16">
              <CalendarDays className="h-16 w-16 mx-auto mb-4 text-workspace-accent" />
              <h3 className="font-bold text-lg mb-2 font-cairo text-workspace-accent-fg">
                {grid.classes.length === 0
                  ? t('itEmptySlotsNoClassesTitle')
                  : t('itEmptySlotsTitle')}
              </h3>
              <p className="text-muted-foreground text-sm font-tajawal mb-5 max-w-md mx-auto">
                {grid.classes.length === 0
                  ? t('itEmptySlotsNoClassesDescription')
                  : t('itEmptySlotsDescription')}
              </p>
              <Button
                onClick={() => grid.classes.length === 0
                  ? navigate('/teacher/classes')
                  : openEditor(grid.working_days[0] || 'sun', 1)}
                className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 px-5"
                data-testid="workspace-schedule-empty-state-cta"
              >
                <Plus className="h-4 w-4" />
                {grid.classes.length === 0
                  ? t('itEmptySlotsNoClassesCta')
                  : t('itEmptySlotsCta')}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-white shadow-sm border-emerald-100">
            <CardHeader className="pb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                  <CalendarDays className="h-5 w-5 text-white" />
                </div>
                <div>
                  <CardTitle className="text-lg text-emerald-800">الجدول الأسبوعي</CardTitle>
                  <CardDescription>
                    {grid.working_days.length} أيام × {grid.periods_per_day} حصص ({grid.period_minutes} دقيقة لكل حصة)
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm" data-testid="workspace-schedule-grid">
                  <thead>
                    <tr>
                      <th className="bg-slate-50 border border-slate-200 p-2 w-20 text-emerald-800">الحصة</th>
                      {grid.working_days.map(d => (
                        <th key={d} className="bg-slate-50 border border-slate-200 p-2 text-emerald-800">
                          {DAY_LABELS[d] || d}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {slots.map(slot => (
                      <tr key={slot}>
                        <td className="border border-slate-200 p-2 text-center font-semibold text-slate-600 bg-slate-50">
                          {slot}
                        </td>
                        {grid.working_days.map(d => {
                          const cell = sessionsByKey.get(slotKey(d, slot));
                          return (
                            <td key={d} className="border border-slate-200 p-1 align-top">
                              <button
                                type="button"
                                onClick={() => openEditor(d, slot)}
                                data-testid={cell ? `slot-${d}-${slot}` : `workspace-schedule-empty-slot-${d}-${slot}`}
                                className={`w-full min-h-[64px] rounded-lg p-2 text-right transition ${cell
                                  ? 'bg-emerald-50 border border-emerald-300 text-emerald-900 hover:bg-emerald-100'
                                  : 'bg-white border border-dashed border-workspace-accent-border/60 text-workspace-accent/60 hover:border-workspace-accent hover:text-workspace-accent-fg hover:bg-workspace-accent-light/40'
                                }`}
                              >
                                {cell ? (
                                  <>
                                    <div className="font-semibold">{cell.class_name || '—'}</div>
                                    <div className="text-xs opacity-80">{cell.subject_name || '—'}</div>
                                  </>
                                ) : (
                                  <div className="text-xs">إضافة</div>
                                )}
                              </button>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {editing ? (
          <div
            className="fixed inset-0 z-40 bg-black/40 flex items-center justify-center p-4"
            onClick={closeEditor}
          >
            <div
              dir={dir}
              className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-4"
              onClick={(e) => e.stopPropagation()}
              data-testid="slot-editor"
            >
              <h3 className="text-lg font-bold text-emerald-800">
                {DAY_LABELS[editing.day] || editing.day} — حصة {editing.slot}
              </h3>
              <div>
                <label className="block text-sm text-slate-600 mb-1">الفصل</label>
                <select
                  value={editing.classId}
                  onChange={e => setEditing(s => ({ ...s, classId: e.target.value }))}
                  className="w-full h-11 px-3 rounded-md border border-slate-200 focus:border-emerald-600 bg-white text-sm"
                  data-testid="slot-editor-class"
                >
                  <option value="">— بدون فصل —</option>
                  {grid.classes.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-600 mb-1">المادة</label>
                <select
                  value={editing.subjectId}
                  onChange={e => setEditing(s => ({ ...s, subjectId: e.target.value }))}
                  className="w-full h-11 px-3 rounded-md border border-slate-200 focus:border-emerald-600 bg-white text-sm"
                  data-testid="slot-editor-subject"
                >
                  <option value="">— بدون مادة —</option>
                  {grid.subjects.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center justify-between gap-2 pt-2">
                <Button
                  variant="outline"
                  className="border-slate-200"
                  onClick={closeEditor}
                  disabled={saving}
                  data-testid="slot-editor-cancel"
                >
                  إلغاء
                </Button>
                <div className="flex items-center gap-2">
                  {editing.hadContent ? (
                    <Button
                      variant="outline"
                      className="border-rose-300 text-rose-700 hover:bg-rose-50"
                      onClick={() => setEditing(s => ({ ...s, classId: '', subjectId: '' }))}
                      disabled={saving}
                      data-testid="slot-editor-clear"
                    >
                      <Trash2 className="h-4 w-4 ms-2" />
                      مسح المحتوى
                    </Button>
                  ) : null}
                  <Button
                    onClick={persistSlot}
                    disabled={saving}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    data-testid="slot-editor-save"
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin ms-2" /> : <Check className="h-4 w-4 ms-2" />}
                    حفظ
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
