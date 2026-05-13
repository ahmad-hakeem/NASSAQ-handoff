import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, Sparkles, BookOpen, Save } from 'lucide-react';

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
  const { nassaqError, nassaqInfo } = useNassaqAlert();
  const [form, setForm] = useState(DEFAULT_FORM);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [current, setCurrent] = useState(null);
  const [quota, setQuota] = useState(null);
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState('');
  const [savedPlans, setSavedPlans] = useState([]);

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

  const quotaBadge = useMemo(() => {
    if (!quota) return null;
    return (
      <Badge variant="outline">
        خطط اليوم: {quota.used_today ?? 0} / {quota.max_per_day ?? 0}
      </Badge>
    );
  }, [quota]);

  return (
    <div className="flex min-h-screen bg-gray-50" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6 space-y-6 max-w-5xl mx-auto">
        <header className="space-y-1">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
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
              <Button onClick={onGenerate} disabled={generating || !form.topic?.trim()}>
                {generating ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : <Sparkles className="w-4 h-4 ml-2" />}
                توليد الخطة
              </Button>
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
              {savedPlans.map((p) => (
                <div key={p.id} className="border rounded-md p-3 text-sm bg-white">
                  <div className="flex flex-wrap justify-between gap-2">
                    <div className="font-semibold">{p.topic}</div>
                    <div className="text-xs text-gray-500">
                      {p.subject || '—'} · {p.grade_level || '—'} · {p.duration_minutes || '—'} د
                    </div>
                  </div>
                  {p.plan?.title && (
                    <div className="text-gray-600 mt-1">{p.plan.title}</div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
