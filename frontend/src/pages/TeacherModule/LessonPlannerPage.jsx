import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, Sparkles, BookOpen, Save, Pencil, Trash2, X, Check } from 'lucide-react';
import { formatHijriDate } from '../../utils/hijriDate';

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

function PlanPreview({ plan }) {
  if (!plan || typeof plan !== 'object') return null;
  const objectives = Array.isArray(plan.objectives) ? plan.objectives : [];
  const activities = Array.isArray(plan.activities) ? plan.activities : [];
  const materials = Array.isArray(plan.materials) ? plan.materials : [];
  return (
    <div className="space-y-4 text-sm leading-relaxed">
      {plan.title && (
        <h3 className="text-lg font-bold text-gray-900">{plan.title}</h3>
      )}
      {!!objectives.length && (
        <section>
          <h4 className="font-semibold text-gray-700 mb-1">الأهداف</h4>
          <ul className="list-disc pr-5 space-y-1">
            {objectives.map((o, i) => <li key={i}>{String(o)}</li>)}
          </ul>
        </section>
      )}
      {plan.warmup && (
        <section>
          <h4 className="font-semibold text-gray-700 mb-1">التهيئة</h4>
          <p>{String(plan.warmup)}</p>
        </section>
      )}
      {!!activities.length && (
        <section>
          <h4 className="font-semibold text-gray-700 mb-1">الأنشطة</h4>
          <ol className="list-decimal pr-5 space-y-2">
            {activities.map((a, i) => (
              <li key={i}>
                <div className="font-medium">
                  {a?.name || `نشاط ${i + 1}`}
                  {a?.duration_minutes ? ` — ${a.duration_minutes} د` : ''}
                </div>
                {a?.description && (
                  <div className="text-gray-600">{String(a.description)}</div>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}
      {plan.assessment && (
        <section>
          <h4 className="font-semibold text-gray-700 mb-1">التقييم</h4>
          <p>{String(plan.assessment)}</p>
        </section>
      )}
      {plan.homework && (
        <section>
          <h4 className="font-semibold text-gray-700 mb-1">الواجب</h4>
          <p>{String(plan.homework)}</p>
        </section>
      )}
      {!!materials.length && (
        <section>
          <h4 className="font-semibold text-gray-700 mb-1">المواد</h4>
          <ul className="list-disc pr-5 space-y-1">
            {materials.map((m, i) => <li key={i}>{String(m)}</li>)}
          </ul>
        </section>
      )}
      {plan.summary && !plan.title && (
        <p className="whitespace-pre-wrap">{String(plan.summary)}</p>
      )}
    </div>
  );
}

export default function LessonPlannerPage() {
  const { api } = useAuth();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();
  const [form, setForm] = useState(DEFAULT_FORM);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [current, setCurrent] = useState(null);
  const [quota, setQuota] = useState(null);
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState('');
  const [savedPlans, setSavedPlans] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ topic: '', subject: '', grade_level: '', duration_minutes: '', title: '' });
  const [rowBusy, setRowBusy] = useState(null);
  // Task #251 — deep-link via /teacher/lesson-planner?plan_id=… opened
  // from the IT command palette. Tracks scroll-to + brief highlight ring
  // applied to the matching saved-plan row.
  const [highlightedPlanId, setHighlightedPlanId] = useState(null);
  const _location = useLocation();
  const _navigate = useNavigate();
  const _planRefs = useRef({});
  const _deepLinkConsumedRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      const [list, cls] = await Promise.all([
        api.get('/independent-teacher/lesson-plans'),
        api.get('/classes').catch(() => ({ data: { classes: [] } })),
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
    const node = _planRefs.current[pid];
    if (node && typeof node.scrollIntoView === 'function') {
      try { node.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (_e) { /* noop */ }
    }
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
      const msg = err?.response?.data?.detail
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
      const msg = err?.response?.data?.detail
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

  const startEdit = useCallback((p) => {
    setEditingId(p.id);
    setEditDraft({
      topic: p.topic || '',
      subject: p.subject || '',
      grade_level: p.grade_level || '',
      duration_minutes: p.duration_minutes ?? '',
      title: p.plan?.title || '',
    });
  }, []);

  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setEditDraft({ topic: '', subject: '', grade_level: '', duration_minutes: '', title: '' });
  }, []);

  const saveEdit = useCallback(async (p) => {
    if (!editDraft.topic?.trim()) {
      nassaqError('موضوع الدرس مطلوب.', { title: 'حقل مطلوب' });
      return;
    }
    setRowBusy(p.id);
    try {
      const nextPlan = { ...(p.plan || {}) };
      if (editDraft.title?.trim()) {
        nextPlan.title = editDraft.title.trim();
      } else {
        delete nextPlan.title;
      }
      const body = {
        topic: editDraft.topic.trim(),
        subject: editDraft.subject?.trim() || null,
        grade_level: editDraft.grade_level?.trim() || null,
        duration_minutes: editDraft.duration_minutes
          ? Number(editDraft.duration_minutes)
          : null,
        plan: nextPlan,
      };
      await api.put(`/independent-teacher/lesson-plans/${p.id}`, body);
      nassaqInfo('تم حفظ التعديلات.', { title: 'تم التحديث' });
      cancelEdit();
      refresh();
    } catch (err) {
      const msg = err?.response?.data?.detail
        || 'تعذّر حفظ التعديلات. حاول مرة أخرى.';
      nassaqError(String(msg), { title: 'فشل التعديل' });
    } finally {
      setRowBusy(null);
    }
  }, [api, editDraft, cancelEdit, refresh, nassaqError, nassaqInfo]);

  const askDelete = useCallback((p) => {
    nassaqConfirm(
      `هل تريد حذف الخطة "${p.topic}"؟ لا يمكن التراجع عن هذه العملية.`,
      async () => {
        setRowBusy(p.id);
        try {
          await api.delete(`/independent-teacher/lesson-plans/${p.id}`);
          if (editingId === p.id) cancelEdit();
          refresh();
        } catch (err) {
          const msg = err?.response?.data?.detail
            || 'تعذّر حذف الخطة. حاول مرة أخرى.';
          nassaqError(String(msg), { title: 'فشل الحذف' });
        } finally {
          setRowBusy(null);
        }
      },
      { title: 'تأكيد الحذف', confirmText: 'حذف', cancelText: 'إلغاء' },
    );
  }, [api, editingId, cancelEdit, refresh, nassaqConfirm, nassaqError]);

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

  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-4 sm:p-6 space-y-6 max-w-5xl mx-auto w-full">
        <header className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-amber-500" /> مساعد خطط الدروس
          </h1>
          <p className="text-sm text-gray-600">
            وَلِّد مسودة خطة درس قصيرة باستخدام الذكاء الاصطناعي. النتائج لمساعدتك فقط — راجعها قبل الاستخدام.
          </p>
        </header>

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
                  value={form.topic}
                  onChange={onChange('topic')}
                  placeholder="مثال: مقدمة في الكسور"
                  maxLength={500}
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

        {!!savedPlans.length && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">الخطط المحفوظة</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {savedPlans.map((p) => {
                const isEditing = editingId === p.id;
                const busy = rowBusy === p.id;
                return (
                  <div
                    key={p.id}
                    ref={(el) => { _planRefs.current[p.id] = el; }}
                    data-testid={`saved-plan-row-${p.id}`}
                    className={`border rounded-md p-3 text-sm bg-white transition-shadow ${
                      highlightedPlanId === p.id ? 'ring-2 ring-brand-navy/60 shadow-md' : ''
                    }`}
                  >
                    {isEditing ? (
                      <div className="space-y-2">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          <div>
                            <label className="text-xs font-medium text-gray-700">الموضوع</label>
                            <Input
                              value={editDraft.topic}
                              onChange={(e) => setEditDraft((d) => ({ ...d, topic: e.target.value }))}
                              maxLength={500}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-gray-700">العنوان</label>
                            <Input
                              value={editDraft.title}
                              onChange={(e) => setEditDraft((d) => ({ ...d, title: e.target.value }))}
                              maxLength={500}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-gray-700">المادة</label>
                            <Input
                              value={editDraft.subject}
                              onChange={(e) => setEditDraft((d) => ({ ...d, subject: e.target.value }))}
                              maxLength={200}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-gray-700">الصف</label>
                            <Input
                              value={editDraft.grade_level}
                              onChange={(e) => setEditDraft((d) => ({ ...d, grade_level: e.target.value }))}
                              maxLength={200}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-gray-700">المدة (دقيقة)</label>
                            <Input
                              type="number"
                              min={5}
                              max={600}
                              value={editDraft.duration_minutes}
                              onChange={(e) => setEditDraft((d) => ({ ...d, duration_minutes: e.target.value }))}
                            />
                          </div>
                        </div>
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={cancelEdit} disabled={busy}>
                            <X className="w-4 h-4 ml-1" /> إلغاء
                          </Button>
                          <Button size="sm" onClick={() => saveEdit(p)} disabled={busy || !editDraft.topic?.trim()}>
                            {busy ? <Loader2 className="w-4 h-4 ml-1 animate-spin" /> : <Check className="w-4 h-4 ml-1" />}
                            حفظ التغييرات
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="flex flex-wrap justify-between gap-2 items-start">
                          <div className="font-semibold">{p.topic}</div>
                          <div className="flex items-center gap-2">
                            <div className="text-xs text-gray-500">
                              {p.subject || '—'} · {p.grade_level || '—'} · {p.duration_minutes || '—'} د
                            </div>
                            <Button variant="ghost" size="sm" onClick={() => startEdit(p)} disabled={busy} title="تعديل">
                              <Pencil className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => askDelete(p)} disabled={busy} title="حذف">
                              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4 text-red-600" />}
                            </Button>
                          </div>
                        </div>
                        {p.plan?.title && (
                          <div className="text-gray-600 mt-1">{p.plan.title}</div>
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
