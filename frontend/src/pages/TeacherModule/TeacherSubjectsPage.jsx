import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Loader2, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';

const EMPTY_FORM = { name: '', name_en: '', code: '', weekly_periods: 4 };

// 2026-05-18 — Reusable subjects panel. The standalone page below
// keeps the legacy /teacher/subjects route working (it renders the
// panel inside the workspace shell); TeacherClassesPage embeds the
// same panel as its fifth "المواد" tab. When `embedded`, the panel
// drops the outer page chrome (sidebar + main wrapper + max-width)
// so it inherits the host tab's spacing. Backend authz is unchanged
// — every CRUD call still hits the IT-scoped /subjects endpoints.
export function TeacherSubjectsPanel({ embedded = false }) {
  const navigate = useNavigate();
  const { api, user, isRTL } = useAuth();
  const { t } = useTranslation();
  const { nassaqError, nassaqConfirm } = useNassaqAlert();

  const isIndependentTeacher = (user?.role || '').toLowerCase() === 'independent_teacher';

  const [loading, setLoading] = useState(true);
  const [subjects, setSubjects] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    // Embedded callers (TeacherClassesPage) already gate the tab on
    // IT role, so the redirect would never fire there. Keep it scoped
    // to the standalone page so we don't yank IT users out of the
    // tabs shell on a transient role-context refresh.
    if (!embedded && !isIndependentTeacher) {
      navigate('/teacher', { replace: true });
    }
  }, [embedded, isIndependentTeacher, navigate]);

  const fetchSubjects = useCallback(async () => {
    if (!api || !isIndependentTeacher) return;
    setLoading(true);
    try {
      const res = await api.get('/subjects');
      const list = Array.isArray(res.data) ? res.data : (res.data?.subjects || []);
      // Backend already excludes soft-deleted rows; keep a defensive
      // client-side filter so a stale cache never surfaces a tombstone.
      setSubjects(list.filter(s => s?.is_active !== false));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      nassaqError(typeof detail === 'string' ? detail : (t('errorLoadingData') || 'تعذّر تحميل المواد.'));
    } finally {
      setLoading(false);
    }
  }, [api, isIndependentTeacher, nassaqError, t]);

  useEffect(() => {
    fetchSubjects();
  }, [fetchSubjects]);

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (subject) => {
    setEditingId(subject.id);
    setForm({
      name: subject.name || subject.name_ar || '',
      name_en: subject.name_en || '',
      code: subject.code || '',
      weekly_periods: subject.weekly_periods || subject.weekly_hours || 4,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    const name = (form.name || '').trim();
    if (!name) {
      nassaqError(t('pleaseFillAllFields') || 'يرجى تعبئة جميع الحقول المطلوبة.');
      return;
    }
    const periods = parseInt(form.weekly_periods, 10);
    const payload = {
      name,
      name_en: (form.name_en || '').trim() || null,
      code: (form.code || '').trim() || null,
      weekly_periods: Number.isFinite(periods) && periods > 0 ? periods : 4,
    };
    setSaving(true);
    try {
      if (editingId) {
        await api.put(`/subjects/${editingId}`, payload);
      } else {
        await api.post('/subjects', payload);
      }
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      fetchSubjects();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      nassaqError(typeof detail === 'string' ? detail : (t('errorSaving') || 'تعذّر حفظ المادة.'));
    } finally {
      setSaving(false);
    }
  };

  const performDelete = async (subjectId, { force = false } = {}) => {
    setDeletingId(subjectId);
    try {
      const res = await api.delete(`/subjects/${subjectId}`, force ? { params: { force: true } } : undefined);
      const data = res?.data;
      if (data && data.requires_confirmation) {
        const deps = data.dependencies || {};
        const classes = deps.classes || 0;
        const assignments = deps.teacher_assignments || 0;
        const sessions = deps.schedule_sessions || 0;
        const lines = [
          data.message || (t('subjectDeleteHasDependencies')
            || 'هذه المادة لا تزال مستخدمة في مساحتك.'),
          `• ${t('classes') || 'الفصول'}: ${classes}`,
          `• ${t('teacherAssignments') || 'إسنادات المعلمين'}: ${assignments}`,
          `• ${t('scheduleSessions') || 'الحصص في الجدول'}: ${sessions}`,
          t('subjectDeleteAnywayHint')
            || 'سيؤدي الحذف إلى إخفاء المادة دون حذف الفصول أو الحصص المرتبطة. هل تريد المتابعة؟',
        ];
        setDeletingId(null);
        nassaqConfirm(lines.join('\n'), async (ok) => {
          if (!ok) return;
          await performDelete(subjectId, { force: true });
        }, {
          confirmText: t('deleteAnyway') || 'حذف على أي حال',
          cancelText: t('cancel') || 'إلغاء',
        });
        return;
      }
      fetchSubjects();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      nassaqError(typeof detail === 'string' ? detail : (t('errorDeleting') || 'تعذّر حذف المادة.'));
    } finally {
      setDeletingId((current) => (current === subjectId ? null : current));
    }
  };

  const handleDelete = (subject) => {
    const label = subject.name || subject.name_ar || subject.name_en || '';
    const message = (t('confirmDelete') || 'هل أنت متأكد من الحذف؟') + (label ? `\n${label}` : '');
    nassaqConfirm(message, async (ok) => {
      if (!ok) return;
      await performDelete(subject.id);
    });
  };

  const sorted = useMemo(() => {
    return [...subjects].sort((a, b) => {
      const an = (a.name || a.name_ar || a.name_en || '').toLowerCase();
      const bn = (b.name || b.name_ar || b.name_en || '').toLowerCase();
      return an.localeCompare(bn);
    });
  }, [subjects]);

  const dir = isRTL ? 'rtl' : 'ltr';
  if (!isIndependentTeacher) return null;

  // When embedded inside the Classes tabs, the host already renders
  // an h1 / icon strip for the page, so the panel shows a tighter
  // h2 header (no duplicate page-level title) and skips the outer
  // sidebar/main shell entirely.
  const HeadingTag = embedded ? 'h2' : 'h1';
  const headingClass = embedded
    ? 'text-xl font-bold font-cairo flex items-center gap-2'
    : 'text-2xl font-bold font-cairo flex items-center gap-2';

  const body = (
    <div className={embedded ? 'space-y-6' : 'max-w-5xl mx-auto space-y-6'} dir={dir}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <HeadingTag className={headingClass}>
            <BookOpen className={embedded ? 'h-5 w-5 text-primary' : 'h-6 w-6 text-primary'} />
            {t('subjects') || 'المواد'}
          </HeadingTag>
          <p className="text-sm text-muted-foreground font-tajawal mt-1">
            {t('workspaceSubjectsHint')
              || 'أضف وعدّل وأحذف المواد الدراسية في مساحتك. تظهر المواد فورًا في نافذة إنشاء الفصل.'}
          </p>
        </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchSubjects}
                disabled={loading}
                className="font-cairo"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              <Button onClick={openCreate} className="font-cairo gap-2">
                <Plus className="h-4 w-4" />
                {t('addSubject') || 'إضافة مادة'}
              </Button>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="font-cairo text-lg">
                {t('subjects') || 'المواد'}
                {!loading && (
                  <span className="text-sm text-muted-foreground font-tajawal ms-2">
                    ({sorted.length})
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : sorted.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground font-tajawal">
                  {t('workspaceClassNoSubjects')
                    || 'لا توجد مواد بعد. يرجى إضافة مادة أولاً.'}
                </div>
              ) : (
                <div className="divide-y">
                  {sorted.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center justify-between py-3 gap-3"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="font-cairo font-medium truncate">
                          {s.name || s.name_ar || s.name_en}
                        </div>
                        <div className="text-xs text-muted-foreground font-tajawal mt-0.5 flex flex-wrap gap-x-3">
                          {s.name_en && s.name_en !== s.name && (
                            <span>{s.name_en}</span>
                          )}
                          {s.code && <span>{s.code}</span>}
                          {(s.weekly_periods || s.weekly_hours) && (
                            <span>
                              {(t('weeklyPeriods') || 'حصص أسبوعيًا') + ': '}
                              {s.weekly_periods || s.weekly_hours}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(s)}
                          className="font-cairo"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(s)}
                          disabled={deletingId === s.id}
                          className="font-cairo text-destructive hover:text-destructive"
                        >
                          {deletingId === s.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
  );

  const dialog = (
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent dir={dir}>
          <DialogHeader>
            <DialogTitle className="font-cairo">
              {editingId
                ? (t('editSubject') || 'تعديل المادة')
                : (t('addSubject') || 'إضافة مادة')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="font-cairo text-sm">
                {t('subjectName') || t('name') || 'اسم المادة'}
              </Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                placeholder={t('subjectName') || 'اسم المادة'}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label className="font-cairo text-sm">
                  {t('nameEn') || 'Name (EN)'}
                </Label>
                <Input
                  value={form.name_en}
                  onChange={(e) => setForm((p) => ({ ...p, name_en: e.target.value }))}
                  placeholder="Math"
                />
              </div>
              <div className="space-y-2">
                <Label className="font-cairo text-sm">
                  {t('subjectCode') || 'الرمز'}
                </Label>
                <Input
                  value={form.code}
                  onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                  placeholder="MATH"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="font-cairo text-sm">
                {t('weeklyPeriods') || 'حصص أسبوعيًا'}
              </Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={form.weekly_periods}
                onChange={(e) =>
                  setForm((p) => ({ ...p, weekly_periods: parseInt(e.target.value, 10) || 1 }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={saving}
              className="font-cairo"
            >
              {t('cancel') || 'إلغاء'}
            </Button>
            <Button onClick={handleSave} disabled={saving} className="font-cairo gap-2">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {t('save') || 'حفظ'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
  );

  if (embedded) {
    return (
      <>
        {body}
        {dialog}
      </>
    );
  }

  return (
    <div className="min-h-screen bg-background flex" dir={dir}>
      <Sidebar />
      <main className="flex-1 p-4 md:p-6 lg:p-8 overflow-x-hidden">
        {body}
      </main>
      {dialog}
    </div>
  );
}

// 2026-05-18 — Standalone page wrapper kept for the legacy
// /teacher/subjects route. The "المواد" sidebar entry was retired
// in favor of a tab inside /teacher/classes (?tab=subjects), and
// the route now redirects there. We keep the default export so any
// historical lazy import resolves without ripple changes.
export default function TeacherSubjectsPage() {
  return <TeacherSubjectsPanel />;
}
