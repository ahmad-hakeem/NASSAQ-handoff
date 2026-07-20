import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { ResponsiveTable } from '../../components/ui/ResponsiveTable';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, Sparkles, BookOpen, Save, Pencil, Trash2, Eye } from 'lucide-react';
import { formatHijriDate } from '../../utils/hijriDate';
import { getApiErrorMessage } from '../../utils/apiError';
import LessonPlanDetailsDialog, { PlanPreview } from './LessonPlanDetailsDialog';

// Phase 2 §6.4 (Task #209) — IT-only light AI lesson-planning assistant.
// Backend pins workspace_school_id == itw_{user_id} + created_by ==
// user.id on every read/write; daily quota lives on workspace_quota.
// No MFA step-up (low-sensitivity content generation per spec).

const DEFAULT_FORM = {
  topic: '',
  subject: '',
  grade_level: '',
  duration_minutes: 45,
  objectives: '',
  language: 'ar',
};

// PlanPreview moved to ./LessonPlanDetailsDialog (spec 2026-07-20) so the
// generate panel and the saved-plan details dialog share one renderer.

// 2026-05-18 — Lesson planner relocated from the main sidebar into a
// tab inside "فصولي" (Teacher Classes Page). The panel below is now
// rendered headless from that tab; the default export keeps the
// standalone shell (Sidebar + main) so the historical
// /teacher/lesson-planner route + any external entry points still
// work without rewriting the entire body. AccountSettings audit-log
// relocation (same day) follows the identical Panel/Page split.
export function LessonPlannerPanel({ embedded = false } = {}) {
  const { api, user } = useAuth();
  const { t } = useTranslation();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  const isIndependentTeacher = (user?.role || '').toLowerCase() === 'independent_teacher';
  const topicInputRef = useRef(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [current, setCurrent] = useState(null);
  const [quota, setQuota] = useState(null);
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState('');
  const [savedPlans, setSavedPlans] = useState([]);
  // Full view/edit dialog (spec 2026-07-20) — replaces the old 5-field
  // inline row editor so the teacher sees/edits the WHOLE stored plan.
  const [detailPlan, setDetailPlan] = useState(null);
  const [detailMode, setDetailMode] = useState('view');
  const [detailOpen, setDetailOpen] = useState(false);
  const [rowBusy, setRowBusy] = useState(null);
  // Task #251 — deep-link via /teacher/lesson-planner?plan_id=… opened
  // from the IT command palette. Tracks scroll-to + brief highlight ring
  // applied to the matching saved-plan row.
  const [highlightedPlanId, setHighlightedPlanId] = useState(null);
  const _location = useLocation();
  const _navigate = useNavigate();
  const _deepLinkConsumedRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [list, cls] = await Promise.all([
        api.get('/independent-teacher/lesson-plans'),
        // Task #1089 — request the assignment-scoped class list so a
        // regular school teacher only sees their OWN classes in the
        // picker. The backend ignores `assigned_only` for Independent
        // Teachers (they own every workspace class), so the IT response
        // is byte-for-byte unchanged.
        api.get('/classes', { params: { assigned_only: true } })
          .catch(() => ({ data: { classes: [] } })),
      ]);
      setSavedPlans(list?.data?.lesson_plans || []);
      if (list?.data?.quota) setQuota(list.data.quota);
      const items = cls?.data?.classes || cls?.data || [];
      setClasses(Array.isArray(items) ? items : []);
    } catch (err) {
      // Silent — list view degrades gracefully if the read fails.
    }
  }, [api]);

  useEffect(() => { refresh(); }, [refresh]);

  // Task #251 — scroll to + briefly highlight the row matching ?plan_id=…
  useEffect(() => {
    if (!savedPlans || !savedPlans.length) return;
    const params = new URLSearchParams(_location.search);
    const pid = params.get('plan_id');
    if (!pid || _deepLinkConsumedRef.current === pid) return;
    if (!savedPlans.some((p) => p.id === pid)) return;
    _deepLinkConsumedRef.current = pid;
    setHighlightedPlanId(pid);
    // ResponsiveTable mounts both desktop table + mobile cards branches
    // simultaneously (CSS-toggled), so look up every wrapper carrying
    // the per-row testid and scroll the one currently visible to the
    // user (offsetParent !== null is the cheapest visibility probe and
    // skips display:none branches). Falls back to the first node if
    // jsdom can't compute layout.
    try {
      const nodes = typeof document !== 'undefined' && document.querySelectorAll
        ? document.querySelectorAll(`[data-testid="saved-plan-row-${pid}"]`)
        : [];
      let target = null;
      for (const n of nodes) {
        if (n && n.offsetParent !== null) { target = n; break; }
      }
      if (!target && nodes.length) target = nodes[0];
      if (target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ block: 'center', behavior: 'smooth' });
      }
    } catch (_e) { /* noop */ }
    const t1 = window.setTimeout(() => setHighlightedPlanId(null), 2400);
    params.delete('plan_id');
    _navigate(
      { pathname: _location.pathname, search: params.toString() ? `?${params.toString()}` : '' },
      { replace: true },
    );
    return () => window.clearTimeout(t1);
  }, [savedPlans, _location.pathname, _location.search, _navigate]);

  const onChange = (key) => (e) => {
    const value = e?.target?.value ?? '';
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const onGenerate = useCallback(async () => {
    if (!form.topic?.trim()) {
      nassaqError('الرجاء إدخال موضوع الدرس.', { title: 'حقل مطلوب' });
      return;
    }
    setGenerating(true);
    setCurrent(null);
    try {
      const body = {
        topic: form.topic.trim(),
        subject: form.subject?.trim() || null,
        grade_level: form.grade_level?.trim() || null,
        duration_minutes: Number(form.duration_minutes) || null,
        objectives: form.objectives?.trim() || null,
        language: form.language || 'ar',
      };
      const res = await api.post('/independent-teacher/lesson-plans/generate', body);
      setCurrent(res?.data?.lesson_plan || null);
      if (res?.data?.quota) setQuota(res.data.quota);
    } catch (err) {
      const msg = getApiErrorMessage(err)
        || err?.response?.data?.message_ar
        || 'تعذّر توليد خطة الدرس. حاول مرة أخرى.';
      nassaqError(String(msg), { title: 'فشل التوليد' });
    } finally {
      setGenerating(false);
    }
  }, [api, form, nassaqError]);

  const onSaveToClass = useCallback(async () => {
    if (!current?.id) return;
    if (!classId) {
      nassaqError('اختر فصلًا قبل الحفظ.', { title: 'حقل مطلوب' });
      return;
    }
    setSaving(true);
    try {
      const res = await api.post(
        `/independent-teacher/lesson-plans/${current.id}/save-to-class`,
        { class_id: classId },
      );
      setCurrent(res?.data?.lesson_plan || current);
      nassaqInfo('تم حفظ خطة الدرس في الفصل.', { title: 'تم الحفظ' });
      refresh();
    } catch (err) {
      const msg = getApiErrorMessage(err)
        || 'تعذّر حفظ خطة الدرس. حاول مرة أخرى.';
      nassaqError(String(msg), { title: 'فشل الحفظ' });
    } finally {
      setSaving(false);
    }
  }, [api, current, classId, nassaqError, nassaqInfo, refresh]);

  const quotaInfo = useMemo(() => {
    const used = Math.max(0, Number(quota?.used_today ?? 0));
    const max = Math.max(0, Number(quota?.max_per_day ?? 0));
    const remaining = Math.max(0, max - used);
    const exhausted = max > 0 && used >= max;
    const percent = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
    let nextResetAr = '';
    try {
      const now = new Date();
      // Build a local-time Date whose y/m/d match the UTC calendar date
      // of the next UTC midnight, so the Hijri formatter (which reads
      // local getters) shows the same Gregorian day as UTC midnight.
      const nextUtcDay = new Date(Date.UTC(
        now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1,
      ));
      const localProxy = new Date(
        nextUtcDay.getUTCFullYear(),
        nextUtcDay.getUTCMonth(),
        nextUtcDay.getUTCDate(),
      );
      nextResetAr = formatHijriDate(localProxy, { includeWeekday: false });
    } catch (_e) { /* graceful */ }
    return { used, max, remaining, exhausted, percent, nextResetAr };
  }, [quota]);

  // Spec 2026-07-20 — opening a saved plan shows the FULL stored plan
  // (objectives/warmup/activities/assessment/homework/materials) plus
  // the linked class; the dialog handles the PUT + save-to-class calls.
  const openDetails = useCallback((p, nextMode) => {
    setDetailPlan(p);
    setDetailMode(nextMode);
    setDetailOpen(true);
  }, []);

  // Resolve a plan's linked class to a display name via the (already
  // assignment-scoped) classes list; null class_id → not linked.
  const classNameById = useMemo(() => {
    const map = {};
    for (const c of classes) map[c.id] = c.name_ar || c.name || c.id;
    return map;
  }, [classes]);

  const askDelete = useCallback((p) => {
    nassaqConfirm(
      `هل تريد حذف الخطة "${p.topic}"؟ لا يمكن التراجع عن هذه العملية.`,
      async () => {
        setRowBusy(p.id);
        try {
          await api.delete(`/independent-teacher/lesson-plans/${p.id}`);
          setDetailOpen(false);
          refresh();
        } catch (err) {
          const msg = getApiErrorMessage(err)
            || 'تعذّر حذف الخطة. حاول مرة أخرى.';
          nassaqError(String(msg), { title: 'فشل الحذف' });
        } finally {
          setRowBusy(null);
        }
      },
      { title: 'تأكيد الحذف', confirmText: 'حذف', cancelText: 'إلغاء' },
    );
  }, [api, refresh, nassaqConfirm, nassaqError]);

  const quotaBadge = useMemo(() => {
    if (!quota) return null;
    return (
      <Badge variant={quotaInfo.exhausted ? 'destructive' : 'outline'}>
        خطط اليوم: {quotaInfo.used} / {quotaInfo.max}
      </Badge>
    );
  }, [quota, quotaInfo]);

  const quotaBarColor = quotaInfo.exhausted
    ? 'bg-red-500'
    : quotaInfo.percent >= 80
      ? 'bg-amber-500'
      : 'bg-emerald-500';

  // When embedded inside the Classes-page tab we drop the page-level
  // chrome (no second Sidebar, no min-h-screen flex shell, no big
  // header — the tab itself already provides title/breadcrumb).
  //
  // Note: we render the body once and wrap it with a conditional JSX
  // tree rather than defining an inline `Shell` component. Inline
  // components recreate their identity on every render and remount
  // the entire subtree (losing focus, form state, AI response panels)
  // on each parent re-render — that's exactly what the spec's
  // "State Preservation" guardrail forbids.
  const body = (
    <>
      {!embedded && (
        <header className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-amber-500" /> مساعد خطط الدروس
          </h1>
          <p className="text-sm text-gray-600">
            وَلِّد مسودة خطة درس قصيرة باستخدام الذكاء الاصطناعي. النتائج لمساعدتك فقط — راجعها قبل الاستخدام.
          </p>
        </header>
      )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              <span className="flex items-center gap-2">
                <BookOpen className="w-5 h-5" /> تفاصيل الدرس
              </span>
              {quotaBadge}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {quota && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-600">
                  <span>
                    استخدمت {quotaInfo.used} من {quotaInfo.max} خطة اليوم
                    {!quotaInfo.exhausted && quotaInfo.max > 0 && (
                      <span className="text-gray-500"> · المتبقي {quotaInfo.remaining}</span>
                    )}
                  </span>
                  {quotaInfo.nextResetAr && (
                    <span className="text-gray-500">
                      تتجدّد عند منتصف الليل بتوقيت UTC ({quotaInfo.nextResetAr})
                    </span>
                  )}
                </div>
                <div
                  className="h-2 w-full rounded-full bg-gray-200 overflow-hidden"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={quotaInfo.max || 0}
                  aria-valuenow={quotaInfo.used}
                  aria-label="استخدام خطط الدروس اليومي"
                >
                  <div
                    className={`h-full transition-all ${quotaBarColor}`}
                    style={{ width: `${quotaInfo.percent}%` }}
                  />
                </div>
                {quotaInfo.exhausted && (
                  <p className="text-xs text-red-600">
                    بلغت الحد اليومي لتوليد خطط الدروس. يمكنك المحاولة مجددًا بعد تجدد الحد عند منتصف الليل بتوقيت UTC.
                  </p>
                )}
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700">موضوع الدرس *</label>
                <Input
                  ref={topicInputRef}
                  value={form.topic}
                  onChange={onChange('topic')}
                  placeholder="مثال: مقدمة في الكسور"
                  maxLength={500}
                  data-testid="lesson-planner-topic-input"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">المادة</label>
                <Input value={form.subject} onChange={onChange('subject')} placeholder="رياضيات" maxLength={200} />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">الصف</label>
                <Input value={form.grade_level} onChange={onChange('grade_level')} placeholder="الرابع الابتدائي" maxLength={200} />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">المدة (دقيقة)</label>
                <Input type="number" min={5} max={600} value={form.duration_minutes} onChange={onChange('duration_minutes')} />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium text-gray-700">أهداف مقترحة (اختياري)</label>
                <textarea
                  className="w-full border rounded-md p-2 text-sm"
                  rows={3}
                  maxLength={2000}
                  value={form.objectives}
                  onChange={onChange('objectives')}
                  placeholder="مثال: يميّز الطالب بين البسط والمقام"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <div className="flex flex-col items-end gap-1">
                <Button
                  onClick={onGenerate}
                  disabled={generating || !form.topic?.trim() || quotaInfo.exhausted}
                  title={quotaInfo.exhausted ? 'بلغت الحد اليومي لتوليد خطط الدروس' : undefined}
                >
                  {generating ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : <Sparkles className="w-4 h-4 ml-2" />}
                  توليد الخطة
                </Button>
                {quotaInfo.exhausted && (
                  <span className="text-xs text-red-600">
                    لا يمكن التوليد حتى تجدد الحد عند منتصف الليل بتوقيت UTC.
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {current && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <BookOpen className="w-5 h-5" /> الخطة المقترحة
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <PlanPreview plan={current.plan} />
              <div className="border-t pt-4 space-y-3">
                <label className="text-sm font-medium text-gray-700">حفظ في فصل (اختياري)</label>
                <div className="flex flex-wrap gap-2 items-center">
                  <select
                    className="border rounded-md p-2 text-sm flex-1 min-w-[200px]"
                    value={classId}
                    onChange={(e) => setClassId(e.target.value)}
                  >
                    <option value="">— اختر فصلًا —</option>
                    {classes.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name_ar || c.name || c.id}
                      </option>
                    ))}
                  </select>
                  <Button onClick={onSaveToClass} disabled={saving || !classId}>
                    {saving ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : <Save className="w-4 h-4 ml-2" />}
                    حفظ
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {!savedPlans.length && !current && isIndependentTeacher && (
          <Card
            className="border-dashed border-workspace-accent-border bg-workspace-accent-light/30"
            data-testid="lesson-planner-empty-state-it"
          >
            <CardContent className="text-center py-16">
              <Sparkles className="h-16 w-16 mx-auto mb-4 text-workspace-accent" />
              <h3 className="font-bold text-lg mb-2 font-cairo text-workspace-accent-fg">
                {t('itEmptyLessonPlansTitle')}
              </h3>
              <p className="text-muted-foreground text-sm font-tajawal mb-5 max-w-md mx-auto">
                {t('itEmptyLessonPlansDescription')}
              </p>
              <Button
                onClick={() => {
                  try { topicInputRef.current?.focus(); } catch (_e) { /* noop */ }
                }}
                className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 px-5"
                data-testid="lesson-planner-empty-state-cta"
              >
                <Sparkles className="h-4 w-4" />
                {t('itEmptyLessonPlansCta')}
              </Button>
            </CardContent>
          </Card>
        )}

        {!!savedPlans.length && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">الخطط المحفوظة</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveTable
                ariaLabel="الخطط المحفوظة"
                rows={savedPlans}
                getRowKey={(p) => p.id}
                columns={[
                  {
                    key: 'topic',
                    header: 'الموضوع',
                    primary: true,
                    render: (p) => (
                      <div
                        data-testid={`saved-plan-row-${p.id}`}
                        className={
                          highlightedPlanId === p.id
                            ? 'ring-2 ring-brand-navy/60 rounded-md p-1 -m-1 transition-shadow'
                            : ''
                        }
                      >
                        <div className="min-w-0">
                          <div className="font-semibold break-words">{p.topic}</div>
                          {p.plan?.title && (
                            <div className="text-xs text-gray-600 font-normal mt-0.5 break-words">
                              {p.plan.title}
                            </div>
                          )}
                        </div>
                      </div>
                    ),
                  },
                  {
                    key: 'subject',
                    header: 'المادة',
                    render: (p) => (p.subject || '—'),
                  },
                  {
                    key: 'grade_level',
                    header: 'الصف',
                    render: (p) => (p.grade_level || '—'),
                  },
                  {
                    key: 'duration_minutes',
                    header: 'المدة (د)',
                    render: (p) => (p.duration_minutes ? `${p.duration_minutes} د` : '—'),
                  },
                  {
                    key: 'class',
                    header: 'الفصل',
                    render: (p) => {
                      if (!p.class_id) {
                        return <span className="text-gray-500">غير مرتبط</span>;
                      }
                      return classNameById[p.class_id] || '—';
                    },
                  },
                  {
                    key: 'actions',
                    header: '',
                    mobileFullWidth: true,
                    cellClassName: 'text-end',
                    render: (p) => {
                      const busy = rowBusy === p.id;
                      return (
                        <div className="flex justify-end gap-2 flex-wrap">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDetails(p, 'view')}
                            disabled={busy}
                            title="عرض"
                          >
                            <Eye className="w-4 h-4 ml-1" strokeWidth={1.5} aria-hidden="true" /> عرض
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDetails(p, 'edit')}
                            disabled={busy}
                            title="تعديل"
                          >
                            <Pencil className="w-4 h-4 ml-1" strokeWidth={1.5} aria-hidden="true" /> تعديل
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => askDelete(p)}
                            disabled={busy}
                            title="حذف"
                          >
                            {busy ? (
                              <Loader2 className="w-4 h-4 ml-1 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4 ml-1 text-red-600" strokeWidth={1.5} aria-hidden="true" />
                            )}
                            حذف
                          </Button>
                        </div>
                      );
                    },
                  },
                ]}
              />
            </CardContent>
          </Card>
        )}

        <LessonPlanDetailsDialog
          plan={detailPlan}
          mode={detailMode}
          open={detailOpen}
          onOpenChange={setDetailOpen}
          classes={classes}
          onSaved={refresh}
        />
    </>
  );

  if (embedded) {
    return (
      <div
        className="w-full space-y-6"
        dir="rtl"
        data-testid="lesson-planner-panel-embedded"
      >
        {body}
      </div>
    );
  }
  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-4 sm:p-6 space-y-6 max-w-5xl mx-auto w-full">
        {body}
      </main>
    </div>
  );
}

// Default export keeps the historical standalone route working
// (Sidebar + main shell). The Classes-page tab uses the named
// LessonPlannerPanel export with embedded=true so we don't render
// a second Sidebar inside the tab.
export default function LessonPlannerPage() {
  return <LessonPlannerPanel embedded={false} />;
}
