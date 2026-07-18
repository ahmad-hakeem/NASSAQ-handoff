import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, CalendarDays, Trash2, Check, Printer, Plus, BookOpen, Clock } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { LoadingState } from '../../components/ui/LoadingState';
import { getApiErrorMessage } from '../../utils/apiError';
import { getDayBandClass, getDayTintClass, getDayTextOnBand } from '../../components/schedule/grid-theme';

const DAY_LABELS = {
  sun: 'الأحد', mon: 'الاثنين', tue: 'الثلاثاء', wed: 'الأربعاء',
  thu: 'الخميس', fri: 'الجمعة', sat: 'السبت',
};

// Map the IT short day keys (sun/mon/…) to the long keys used by dayPalette.
const SHORT_TO_LONG_DAY = {
  sun: 'sunday', mon: 'monday', tue: 'tuesday',
  wed: 'wednesday', thu: 'thursday', fri: 'friday', sat: 'saturday',
};

// Arabic ordinal labels for period rows (matches school teacher schedule).
const ARABIC_ORDINALS = ['الأولى','الثانية','الثالثة','الرابعة','الخامسة','السادسة','السابعة','الثامنة','التاسعة','العاشرة'];

// Subject-to-color map matching the school teacher schedule palette.
const IT_SUBJECT_COLORS = {
  'اللغة العربية':       'bg-blue-50   border-blue-300   text-blue-800',
  'الرياضيات':           'bg-green-50  border-green-300  text-green-800',
  'العلوم':              'bg-purple-50 border-purple-300 text-purple-800',
  'اللغة الإنجليزية':   'bg-red-50    border-red-300    text-red-800',
  'الدراسات الاجتماعية':'bg-amber-50  border-amber-300  text-amber-800',
  'التربية الإسلامية':  'bg-emerald-50 border-emerald-300 text-emerald-800',
  'الحاسب الآلي':       'bg-cyan-50   border-cyan-300   text-cyan-800',
  'المهارات الرقمية':   'bg-teal-50   border-teal-300   text-teal-800',
  'التربية الفنية':     'bg-pink-50   border-pink-300   text-pink-800',
  'التربية البدنية':    'bg-indigo-50 border-indigo-300 text-indigo-800',
};
const IT_SUBJECT_COLOR_DEFAULT = 'bg-slate-50 border-slate-300 text-slate-700';

const slotKey = (day, slot) => `${day}__${slot}`;

// 2026-05-18 — Reusable "جدولي" panel. The standalone page below
// renders the panel inside the workspace shell for the legacy route;
// TeacherClassesPage embeds the same panel as its fourth tab so the
// IT teacher has classes / sessions / lesson-planner / schedule in
// one surface. When `embedded`, the panel drops its outer page
// chrome (gradient background, max-width, padding) so it fits into
// the host tab's spacing.
//
// Backend authz is unchanged: the panel still talks to
// /independent-teacher/schedule/* exactly as before, and the host
// route ProtectedRoute still gates by role.
//
// `onNavigateToClasses` lets the host customize the
// "create a class first" CTA — when embedded inside TeacherClassesPage
// we switch to the classes tab in-place instead of navigating, which
// avoids a full route remount.
export function WorkspaceSchedulePanel({ embedded = false, onNavigateToClasses }) {
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
    slot_times: [],
    classes: [],
    subjects: [],
  });
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [slotErrors, setSlotErrors] = useState({ classId: false, subjectId: false });

  const isIndependent = (user?.role || '').toLowerCase() === 'independent_teacher';

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
        slot_times: Array.isArray(data?.slot_times) ? data.slot_times : [],
        classes: Array.isArray(data?.classes) ? data.classes : [],
        subjects: Array.isArray(data?.subjects) ? data.subjects : [],
      });
    } catch (err) {
      const msg = getApiErrorMessage(err)
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

  // slot_number → {start_time, end_time} for time-range display in row headers.
  const slotTimesMap = useMemo(() => {
    const m = new Map();
    for (const t of grid.slot_times) m.set(t.slot_number, t);
    return m;
  }, [grid.slot_times]);

  const openEditor = (day, slot) => {
    const existing = sessionsByKey.get(slotKey(day, slot));
    setSlotErrors({ classId: false, subjectId: false });
    setEditing({
      day,
      slot,
      classId: existing?.class_id || '',
      subjectId: existing?.subject_id || '',
      version: existing?.version || 0,
      hadContent: Boolean(existing?.class_id || existing?.subject_id),
    });
  };

  const closeEditor = () => {
    setSlotErrors({ classId: false, subjectId: false });
    setEditing(null);
  };

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

    if (!willClear && (!classId || !subjectId)) {
      setSlotErrors({ classId: !classId, subjectId: !subjectId });
      return;
    }

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
          const msg = getApiErrorMessage(err)
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
      const msg = getApiErrorMessage(err)
        || err?.response?.data?.error?.message
        || 'تعذّر تنزيل ملف PDF لجدولك.';
      nassaqError(typeof msg === 'string' ? msg : (msg?.message || 'تعذّر تنزيل ملف PDF لجدولك.'));
    }
  };

  const dir = isRTL ? 'rtl' : 'ltr';

  // Non-IT users have no schedule grid; render nothing rather than
  // leaking the page chrome. The standalone wrapper below performs
  // the role-redirect; embedded callers (TeacherClassesPage) already
  // gate the tab on `_isITUser`, so this is a defensive no-op.
  if (!isIndependent) return null;

  // CTA when the workspace has no classes yet. In the standalone
  // route we navigate to /teacher/classes; embedded inside that page
  // we just switch tabs in-place via the host-supplied callback to
  // avoid a full route remount and to keep the user's place.
  const handleGoToClasses = () => {
    if (typeof onNavigateToClasses === 'function') {
      onNavigateToClasses();
    } else {
      navigate('/teacher/classes');
    }
  };

  const scheduleBody = (
    <div dir={dir} className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className={`font-bold text-emerald-800 ${embedded ? 'text-xl' : 'text-2xl'}`}>جدولي</h2>
          <p className="text-sm text-slate-500 mt-1">
            قم بتعيين الفصول والمواد لكل حصّة في أيام عملك. يمكنك مسح أي حصّة في أي وقت.
          </p>
        </div>
        <Button
          onClick={handleExport}
          variant="outline"
          className="border-emerald-300 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-700 focus-visible:text-emerald-700"
          data-testid="workspace-schedule-export-btn"
        >
          <Printer className="h-4 w-4 ms-2" />
          تنزيل PDF
        </Button>
      </div>

      {loading ? (
        <LoadingState variant="section" className="py-24" />
      ) : (grid.sessions.length === 0) ? (
        <Card
          className="border-dashed border-workspace-accent-border bg-workspace-accent-light/30"
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
                ? handleGoToClasses()
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
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm" data-testid="workspace-schedule-grid">
                <thead>
                  <tr>
                    {/* Period label column header */}
                    <th className="bg-muted/50 border border-border p-3 w-28 text-start sticky start-0 z-10">
                      <div className="flex items-center gap-1.5 text-foreground/70">
                        <Clock className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                        <span className="text-sm font-medium font-cairo">الحصة</span>
                      </div>
                    </th>
                    {/* One colored band header per working day */}
                    {grid.working_days.map(d => {
                      const longKey = SHORT_TO_LONG_DAY[d] || d;
                      return (
                        <th
                          key={d}
                          className={`border border-border p-3 text-center font-cairo font-bold text-sm min-w-[120px] ${getDayBandClass(longKey)} ${getDayTextOnBand(longKey)}`}
                        >
                          {DAY_LABELS[d] || d}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {slots.map((slot, idx) => (
                    <tr key={slot} className={idx % 2 === 0 ? 'bg-white dark:bg-gray-900' : 'bg-muted/15'}>
                      {/* Period number / ordinal label + time range */}
                      <td className="border border-border p-3 bg-muted/30 sticky start-0 z-10">
                        <div className="text-sm font-medium text-foreground/80 font-cairo whitespace-nowrap">
                          {`الحصة ${ARABIC_ORDINALS[idx] || slot}`}
                        </div>
                        {(() => {
                          const slotTime = slotTimesMap.get(slot);
                          if (!slotTime?.start_time) return null;
                          return (
                            <div className="text-xs text-muted-foreground mt-0.5 whitespace-nowrap font-tajawal">
                              {slotTime.start_time.slice(0, 5)} - {slotTime.end_time?.slice(0, 5)}
                            </div>
                          );
                        })()}
                      </td>
                      {/* Day cells */}
                      {grid.working_days.map(d => {
                        const longKey = SHORT_TO_LONG_DAY[d] || d;
                        const cell = sessionsByKey.get(slotKey(d, slot));
                        const subjectColor = cell
                          ? (IT_SUBJECT_COLORS[cell.subject_name] || IT_SUBJECT_COLOR_DEFAULT)
                          : '';
                        return (
                          <td
                            key={d}
                            className={`border border-border p-2 align-top ${getDayTintClass(longKey)}`}
                          >
                            <button
                              type="button"
                              onClick={() => openEditor(d, slot)}
                              data-testid={cell ? `slot-${d}-${slot}` : `workspace-schedule-empty-slot-${d}-${slot}`}
                              className={`w-full min-h-[76px] rounded-lg p-2 transition-all text-start ${
                                cell
                                  ? `bg-white dark:bg-gray-900 border-2 ${subjectColor} hover:shadow-md hover:-translate-y-0.5`
                                  : 'bg-white/60 border-2 border-dashed border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-white/80'
                              }`}
                            >
                              {cell ? (
                                <div className="flex items-start gap-1.5">
                                  <BookOpen
                                    className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 opacity-60"
                                    strokeWidth={1.5}
                                    aria-hidden="true"
                                  />
                                  <div className="min-w-0 flex-1">
                                    <p className="font-cairo font-semibold text-sm leading-tight truncate">
                                      {cell.subject_name || '—'}
                                    </p>
                                    <p className="text-xs opacity-70 leading-tight mt-0.5 truncate">
                                      {cell.class_name || '—'}
                                    </p>
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-center justify-center h-full min-h-[60px] text-xs text-muted-foreground/50 font-cairo">
                                  فارغ
                                </div>
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
                onChange={e => {
                  setEditing(s => ({ ...s, classId: e.target.value }));
                  if (e.target.value) setSlotErrors(prev => ({ ...prev, classId: false }));
                }}
                className="w-full h-11 px-3 rounded-md border border-slate-200 focus:border-emerald-600 bg-white text-sm"
                data-testid="slot-editor-class"
              >
                <option value="">— بدون فصل —</option>
                {grid.classes.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              {slotErrors.classId && (
                <p className="text-xs text-red-500 mt-1">هذا الحقل مطلوب</p>
              )}
            </div>
            <div>
              <label className="block text-sm text-slate-600 mb-1">المادة</label>
              <select
                value={editing.subjectId}
                onChange={e => {
                  setEditing(s => ({ ...s, subjectId: e.target.value }));
                  if (e.target.value) setSlotErrors(prev => ({ ...prev, subjectId: false }));
                }}
                className="w-full h-11 px-3 rounded-md border border-slate-200 focus:border-emerald-600 bg-white text-sm"
                data-testid="slot-editor-subject"
              >
                <option value="">— بدون مادة —</option>
                {grid.subjects.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
              {slotErrors.subjectId && (
                <p className="text-xs text-red-500 mt-1">هذا الحقل مطلوب</p>
              )}
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
                    className="border-rose-300 text-rose-700 hover:bg-rose-50 hover:text-rose-700 focus-visible:text-rose-700"
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
  );

  if (embedded) return scheduleBody;

  return (
    <div dir={dir} className="min-h-screen bg-slate-50 py-6 px-4">
      <div className="mx-auto max-w-6xl">{scheduleBody}</div>
    </div>
  );
}

// 2026-05-18 — The standalone /teacher/workspace-schedule route is
// now superseded by the "جدولي" tab inside TeacherClassesPage. The
// route in appRoutes.js redirects there, so this page component
// only renders if something else still imports it directly. We
// keep it so the legacy default export contract holds.
export default function WorkspaceSchedulePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isIndependent = (user?.role || '').toLowerCase() === 'independent_teacher';

  useEffect(() => {
    if (!isIndependent) navigate('/teacher', { replace: true });
  }, [isIndependent, navigate]);

  if (!isIndependent) return null;
  return <WorkspaceSchedulePanel />;
}
