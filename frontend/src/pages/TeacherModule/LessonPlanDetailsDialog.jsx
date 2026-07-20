import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '../../utils/apiError';
import {
  Loader2,
  Pencil,
  Check,
  X,
  Plus,
  Trash2,
  BookOpen,
  School,
  Clock,
  GraduationCap,
  Languages,
} from 'lucide-react';

// Full read-only rendering of the stored plan JSONB. Shared between the
// "الخطة المقترحة" panel (fresh generation) and the saved-plan details
// dialog below. Renders every known section and hides empty ones.
export function PlanPreview({ plan }) {
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

const _linesToList = (text) => String(text || '')
  .split('\n')
  .map((s) => s.trim())
  .filter(Boolean);

const _listToLines = (list) => (Array.isArray(list) ? list : [])
  .map((s) => String(s ?? ''))
  .join('\n');

function _buildDraft(plan) {
  const body = (plan?.plan && typeof plan.plan === 'object') ? plan.plan : {};
  return {
    topic: plan?.topic || '',
    subject: plan?.subject || '',
    grade_level: plan?.grade_level || '',
    duration_minutes: plan?.duration_minutes ?? '',
    language: plan?.language || 'ar',
    class_id: plan?.class_id || '',
    title: body.title || '',
    objectives: _listToLines(body.objectives),
    warmup: body.warmup ? String(body.warmup) : '',
    activities: (Array.isArray(body.activities) ? body.activities : []).map((a) => ({
      name: a?.name ? String(a.name) : '',
      duration_minutes: a?.duration_minutes ?? '',
      description: a?.description ? String(a.description) : '',
    })),
    assessment: body.assessment ? String(body.assessment) : '',
    homework: body.homework ? String(body.homework) : '',
    materials: _listToLines(body.materials),
    summary: body.summary ? String(body.summary) : '',
  };
}

const _fieldLabel = 'text-sm font-medium text-gray-700';
const _textareaCls = 'w-full border rounded-md p-2 text-sm';

/**
 * Full view/edit dialog for one saved lesson plan (spec 2026-07-20).
 *
 * The backend already returns the complete stored plan (`plan` JSONB +
 * `class_id`) and `PUT /independent-teacher/lesson-plans/{id}` accepts a
 * full `plan` object — this dialog closes the FE gap where only 5 scalar
 * fields were exposed. Unknown keys inside the stored `plan` JSONB are
 * preserved verbatim on save (spread-then-override), and the linked class
 * is changed exclusively through the sanctioned `save-to-class` endpoint
 * (own-class checks for school teachers live server-side).
 */
export default function LessonPlanDetailsDialog({
  plan,
  mode = 'view',
  open,
  onOpenChange,
  classes = [],
  onSaved,
}) {
  const { api } = useAuth();
  const { nassaqError, nassaqInfo } = useNassaqAlert();
  const [editing, setEditing] = useState(mode === 'edit');
  const [draft, setDraft] = useState(() => _buildDraft(plan));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setEditing(mode === 'edit');
      setDraft(_buildDraft(plan));
      setBusy(false);
    }
  }, [open, mode, plan]);

  const className = useMemo(() => {
    if (!plan?.class_id) return null;
    const c = classes.find((k) => k.id === plan.class_id);
    return c ? (c.name_ar || c.name || c.id) : null;
  }, [plan, classes]);

  const set = (key) => (e) => {
    const value = e?.target?.value ?? '';
    setDraft((d) => ({ ...d, [key]: value }));
  };

  const setActivity = (idx, key) => (e) => {
    const value = e?.target?.value ?? '';
    setDraft((d) => {
      const activities = d.activities.map((a, i) => (
        i === idx ? { ...a, [key]: value } : a
      ));
      return { ...d, activities };
    });
  };

  const addActivity = () => setDraft((d) => ({
    ...d,
    activities: [...d.activities, { name: '', duration_minutes: '', description: '' }],
  }));

  const removeActivity = (idx) => setDraft((d) => ({
    ...d,
    activities: d.activities.filter((_, i) => i !== idx),
  }));

  const onSave = useCallback(async () => {
    if (!draft.topic?.trim()) {
      nassaqError('موضوع الدرس مطلوب.', { title: 'حقل مطلوب' });
      return;
    }
    setBusy(true);
    try {
      // Spread the ORIGINAL stored plan first so any keys this editor
      // does not know about survive the round-trip untouched.
      const nextPlan = { ...((plan?.plan && typeof plan.plan === 'object') ? plan.plan : {}) };
      const setOrDelete = (key, value) => {
        if (value === '' || value == null || (Array.isArray(value) && !value.length)) {
          delete nextPlan[key];
        } else {
          nextPlan[key] = value;
        }
      };
      setOrDelete('title', draft.title.trim());
      setOrDelete('objectives', _linesToList(draft.objectives));
      setOrDelete('warmup', draft.warmup.trim());
      setOrDelete('activities', draft.activities
        .filter((a) => a.name.trim() || a.description.trim())
        .map((a) => {
          const out = { name: a.name.trim() };
          const dur = Number(a.duration_minutes);
          if (dur > 0) out.duration_minutes = dur;
          if (a.description.trim()) out.description = a.description.trim();
          return out;
        }));
      setOrDelete('assessment', draft.assessment.trim());
      setOrDelete('homework', draft.homework.trim());
      setOrDelete('materials', _linesToList(draft.materials));
      setOrDelete('summary', draft.summary.trim());

      const body = {
        topic: draft.topic.trim(),
        subject: draft.subject?.trim() || null,
        grade_level: draft.grade_level?.trim() || null,
        duration_minutes: draft.duration_minutes ? Number(draft.duration_minutes) : null,
        language: draft.language || 'ar',
        plan: nextPlan,
      };
      await api.put(`/independent-teacher/lesson-plans/${plan.id}`, body);

      // Class re-link goes through the sanctioned endpoint only (it also
      // enforces own-class scoping for school teachers server-side).
      // Failure here must NOT be reported as a total failure — the PUT
      // above already persisted the content edits (retry is safe).
      if (draft.class_id && draft.class_id !== (plan.class_id || '')) {
        try {
          await api.post(
            `/independent-teacher/lesson-plans/${plan.id}/save-to-class`,
            { class_id: draft.class_id },
          );
        } catch (linkErr) {
          const linkMsg = getApiErrorMessage(linkErr)
            || 'تعذّر ربط الخطة بالفصل المحدد.';
          nassaqError(
            `تم حفظ محتوى الخطة، لكن ${String(linkMsg)}`,
            { title: 'لم يكتمل ربط الفصل' },
          );
          onSaved?.();
          return;
        }
      }
      nassaqInfo('تم حفظ التعديلات.', { title: 'تم التحديث' });
      onOpenChange?.(false);
      onSaved?.();
    } catch (err) {
      const msg = getApiErrorMessage(err) || 'تعذّر حفظ التعديلات. حاول مرة أخرى.';
      nassaqError(String(msg), { title: 'فشل التعديل' });
    } finally {
      setBusy(false);
    }
  }, [api, draft, plan, nassaqError, nassaqInfo, onOpenChange, onSaved]);

  if (!plan) return null;

  const metaChips = (
    <div className="flex flex-wrap gap-2">
      {plan.subject && (
        <Badge variant="outline" className="gap-1">
          <BookOpen className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden="true" />
          {plan.subject}
        </Badge>
      )}
      {plan.grade_level && (
        <Badge variant="outline" className="gap-1">
          <GraduationCap className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden="true" />
          {plan.grade_level}
        </Badge>
      )}
      {!!plan.duration_minutes && (
        <Badge variant="outline" className="gap-1">
          <Clock className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden="true" />
          {plan.duration_minutes} د
        </Badge>
      )}
      <Badge variant="outline" className="gap-1">
        <Languages className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden="true" />
        {plan.language === 'en' ? 'الإنجليزية' : 'العربية'}
      </Badge>
      <Badge
        variant={className ? 'secondary' : 'outline'}
        className="gap-1"
        data-testid="plan-detail-class-badge"
      >
        <School className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden="true" />
        {className || 'غير مرتبط بفصل'}
      </Badge>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-3xl max-h-[85vh] overflow-y-auto"
        data-testid="lesson-plan-details-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BookOpen className="w-5 h-5" strokeWidth={1.5} aria-hidden="true" />
            {editing ? 'تعديل خطة الدرس' : 'تفاصيل خطة الدرس'}
          </DialogTitle>
          <DialogDescription className="text-start">
            {plan.topic}
          </DialogDescription>
        </DialogHeader>

        {!editing && (
          <div className="space-y-4" data-testid="plan-detail-view">
            {metaChips}
            <div className="border rounded-lg p-4 bg-gray-50/60">
              <PlanPreview plan={plan.plan} />
              {(!plan.plan || !Object.keys(plan.plan).length) && (
                <p className="text-sm text-gray-500">لا يحتوي هذا السجل على محتوى خطة مفصّل.</p>
              )}
            </div>
          </div>
        )}

        {editing && (
          <div className="space-y-4" data-testid="plan-detail-edit">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className={_fieldLabel}>موضوع الدرس *</label>
                <Input
                  value={draft.topic}
                  onChange={set('topic')}
                  maxLength={500}
                  data-testid="plan-detail-topic-input"
                />
              </div>
              <div>
                <label className={_fieldLabel}>العنوان</label>
                <Input
                  value={draft.title}
                  onChange={set('title')}
                  maxLength={500}
                  data-testid="plan-detail-title-input"
                />
              </div>
              <div>
                <label className={_fieldLabel}>المادة</label>
                <Input
                  value={draft.subject}
                  onChange={set('subject')}
                  maxLength={200}
                  data-testid="plan-detail-subject-input"
                />
              </div>
              <div>
                <label className={_fieldLabel}>الصف</label>
                <Input
                  value={draft.grade_level}
                  onChange={set('grade_level')}
                  maxLength={200}
                  data-testid="plan-detail-grade-input"
                />
              </div>
              <div>
                <label className={_fieldLabel}>المدة (دقيقة)</label>
                <Input
                  type="number"
                  min={5}
                  max={600}
                  value={draft.duration_minutes}
                  onChange={set('duration_minutes')}
                  data-testid="plan-detail-duration-input"
                />
              </div>
              <div>
                <label className={_fieldLabel}>اللغة</label>
                <select
                  className="w-full border rounded-md p-2 text-sm h-10"
                  value={draft.language}
                  onChange={set('language')}
                  data-testid="plan-detail-language-select"
                >
                  <option value="ar">العربية</option>
                  <option value="en">الإنجليزية</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className={_fieldLabel}>الفصل المرتبط</label>
                <select
                  className="w-full border rounded-md p-2 text-sm h-10"
                  value={draft.class_id}
                  onChange={set('class_id')}
                  data-testid="plan-detail-class-select"
                >
                  {!plan.class_id && <option value="">— غير مرتبط بفصل —</option>}
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name_ar || c.name || c.id}
                    </option>
                  ))}
                  {plan.class_id && !classes.some((c) => c.id === plan.class_id) && (
                    <option value={plan.class_id}>فصل غير متاح حاليًا</option>
                  )}
                </select>
              </div>
            </div>

            <div>
              <label className={_fieldLabel}>الأهداف (هدف في كل سطر)</label>
              <textarea
                className={_textareaCls}
                rows={3}
                value={draft.objectives}
                onChange={set('objectives')}
                data-testid="plan-detail-objectives-input"
              />
            </div>

            <div>
              <label className={_fieldLabel}>التهيئة</label>
              <textarea
                className={_textareaCls}
                rows={2}
                value={draft.warmup}
                onChange={set('warmup')}
                data-testid="plan-detail-warmup-input"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className={_fieldLabel}>الأنشطة</label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addActivity}
                  data-testid="plan-detail-add-activity"
                >
                  <Plus className="w-4 h-4 ml-1" strokeWidth={1.5} aria-hidden="true" /> إضافة نشاط
                </Button>
              </div>
              {!draft.activities.length && (
                <p className="text-xs text-gray-500">لا توجد أنشطة — أضف نشاطًا جديدًا.</p>
              )}
              {draft.activities.map((a, i) => (
                <div
                  key={i}
                  className="border rounded-md p-3 space-y-2 bg-gray-50/60"
                  data-testid={`plan-detail-activity-row-${i}`}
                >
                  <div className="flex gap-2 items-start">
                    <div className="flex-1">
                      <label className="text-xs font-medium text-gray-600">اسم النشاط</label>
                      <Input
                        value={a.name}
                        onChange={setActivity(i, 'name')}
                        maxLength={300}
                        data-testid={`plan-detail-activity-name-${i}`}
                      />
                    </div>
                    <div className="w-28">
                      <label className="text-xs font-medium text-gray-600">المدة (د)</label>
                      <Input
                        type="number"
                        min={0}
                        max={600}
                        value={a.duration_minutes}
                        onChange={setActivity(i, 'duration_minutes')}
                        data-testid={`plan-detail-activity-duration-${i}`}
                      />
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="mt-5 shrink-0"
                      onClick={() => removeActivity(i)}
                      aria-label={`حذف النشاط ${i + 1}`}
                      data-testid={`plan-detail-activity-remove-${i}`}
                    >
                      <Trash2 className="w-4 h-4 text-red-600" strokeWidth={1.5} aria-hidden="true" />
                    </Button>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">الوصف</label>
                    <textarea
                      className={_textareaCls}
                      rows={2}
                      value={a.description}
                      onChange={setActivity(i, 'description')}
                      data-testid={`plan-detail-activity-desc-${i}`}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className={_fieldLabel}>التقييم</label>
                <textarea
                  className={_textareaCls}
                  rows={2}
                  value={draft.assessment}
                  onChange={set('assessment')}
                  data-testid="plan-detail-assessment-input"
                />
              </div>
              <div>
                <label className={_fieldLabel}>الواجب</label>
                <textarea
                  className={_textareaCls}
                  rows={2}
                  value={draft.homework}
                  onChange={set('homework')}
                  data-testid="plan-detail-homework-input"
                />
              </div>
            </div>

            <div>
              <label className={_fieldLabel}>المواد (مادة في كل سطر)</label>
              <textarea
                className={_textareaCls}
                rows={2}
                value={draft.materials}
                onChange={set('materials')}
                data-testid="plan-detail-materials-input"
              />
            </div>

            {/* Gate on the ORIGINAL plan having a summary — gating on the
                draft would unmount the field mid-edit the instant the user
                clears it, with no way to restore it. */}
            {!!(plan?.plan && plan.plan.summary) && (
              <div>
                <label className={_fieldLabel}>ملخص</label>
                <textarea
                  className={_textareaCls}
                  rows={3}
                  value={draft.summary}
                  onChange={set('summary')}
                  data-testid="plan-detail-summary-input"
                />
              </div>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          {!editing ? (
            <>
              <Button variant="ghost" onClick={() => onOpenChange?.(false)}>
                إغلاق
              </Button>
              <Button onClick={() => setEditing(true)} data-testid="plan-detail-edit-toggle">
                <Pencil className="w-4 h-4 ml-1" strokeWidth={1.5} aria-hidden="true" /> تعديل
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={() => onOpenChange?.(false)} disabled={busy}>
                <X className="w-4 h-4 ml-1" strokeWidth={1.5} aria-hidden="true" /> إلغاء
              </Button>
              <Button
                onClick={onSave}
                disabled={busy || !draft.topic?.trim()}
                data-testid="plan-detail-save"
              >
                {busy
                  ? <Loader2 className="w-4 h-4 ml-1 animate-spin" strokeWidth={1.5} aria-hidden="true" />
                  : <Check className="w-4 h-4 ml-1" strokeWidth={1.5} aria-hidden="true" />}
                حفظ التغييرات
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
