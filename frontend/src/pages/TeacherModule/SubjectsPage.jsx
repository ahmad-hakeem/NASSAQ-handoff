import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '../../utils/apiError';
import {
  BookOpen, Plus, Pencil, Trash2, Loader2, RefreshCw,
} from 'lucide-react';

// Task #185 — Independent-Teacher subjects CRUD page.
// Backend tenant-scopes every read/write to the caller's `itw_{user_id}`
// workspace; cross-workspace ids return 404. No quota is enforced for
// subjects in v1 (only classes/students/years are capped).

export default function SubjectsPage() {
  const { api, isRTL } = useAuth();
  const { nassaqError, nassaqInfo, nassaqConfirm } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [subjects, setSubjects] = useState([]);
  const [editing, setEditing] = useState(null); // { id?, name, name_en, code, weekly_hours }
  const [saving, setSaving] = useState(false);

  const fetchSubjects = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/subjects');
      const list = Array.isArray(res.data) ? res.data : (res.data?.subjects || []);
      setSubjects(list);
    } catch (err) {
      const detail = getApiErrorMessage(err);
      nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر جلب المواد' : 'Could not load subjects'));
    } finally {
      setLoading(false);
    }
  }, [api, isRTL, nassaqError]);

  useEffect(() => { fetchSubjects(); }, [fetchSubjects]);

  const openAdd = () => setEditing({ name: '', name_en: '', code: '', weekly_hours: 4 });
  const openEdit = (s) => setEditing({
    id: s.id,
    name: s.name || '',
    name_en: s.name_en || '',
    code: s.code || '',
    weekly_hours: s.weekly_hours || s.weekly_periods || 4,
  });

  const save = async () => {
    if (!editing) return;
    const name = (editing.name || '').trim();
    if (!name) {
      nassaqError(isRTL ? 'اسم المادة مطلوب' : 'Subject name is required');
      return;
    }
    setSaving(true);
    try {
      const body = {
        name,
        name_en: (editing.name_en || '').trim() || null,
        code: (editing.code || '').trim() || null,
        weekly_hours: Number(editing.weekly_hours) || 4,
      };
      if (editing.id) {
        await api.put(`/subjects/${editing.id}`, body);
      } else {
        await api.post('/subjects', body);
      }
      setEditing(null);
      await fetchSubjects();
    } catch (err) {
      const detail = getApiErrorMessage(err);
      nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر حفظ المادة' : 'Could not save subject'));
    } finally {
      setSaving(false);
    }
  };

  const remove = (s) => {
    nassaqConfirm(
      isRTL ? `هل تريد حذف المادة "${s.name}"؟` : `Delete subject "${s.name}"?`,
      async () => {
        try {
          await api.delete(`/subjects/${s.id}`);
          nassaqInfo(isRTL ? 'تم حذف المادة' : 'Subject deleted');
          await fetchSubjects();
        } catch (err) {
          const detail = getApiErrorMessage(err);
          nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر حذف المادة' : 'Could not delete subject'));
        }
      }
    );
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {isRTL ? 'موادي الدراسية' : 'My subjects'}
              </h1>
              <p className="text-sm text-muted-foreground">
                {isRTL ? 'أضف وحرّر المواد التي تدرّسها في مساحتك.' : 'Add and edit the subjects you teach in your workspace.'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="icon" onClick={fetchSubjects} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              <Button onClick={openAdd} className="gap-1.5 bg-brand-navy hover:bg-brand-navy/90 text-white" data-testid="subject-add-cta">
                <Plus className="h-4 w-4" />
                {isRTL ? 'إضافة مادة' : 'Add subject'}
              </Button>
            </div>
          </div>
        </div>

        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : subjects.length === 0 ? (
            <Card>
              <CardContent className="text-center py-16">
                <BookOpen className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <h3 className="font-bold mb-2">{isRTL ? 'لا توجد مواد بعد' : 'No subjects yet'}</h3>
                <p className="text-muted-foreground text-sm">
                  {isRTL ? 'اضغط "إضافة مادة" لإنشاء أول مادة في مساحتك.' : 'Click "Add subject" to create your first one.'}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {subjects.map((s) => (
                <Card key={s.id} data-testid={`subject-card-${s.id}`}>
                  <CardHeader className="pb-2">
                    <CardTitle className="font-cairo text-base flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-brand-turquoise" />
                      {s.name}
                    </CardTitle>
                    {s.name_en && <p className="text-xs text-muted-foreground">{s.name_en}</p>}
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center gap-2 flex-wrap text-xs">
                      {s.code && <Badge variant="outline">{s.code}</Badge>}
                      <Badge variant="outline">
                        {(isRTL ? 'حصص/أسبوع: ' : 'Periods/wk: ') + (s.weekly_hours || s.weekly_periods || 0)}
                      </Badge>
                    </div>
                    <div className="flex gap-1.5 pt-1 border-t border-border/50">
                      <Button variant="ghost" size="sm" className="flex-1 h-7 text-xs"
                        onClick={() => openEdit(s)} data-testid={`subject-edit-${s.id}`}>
                        <Pencil className="h-3 w-3 me-1" />
                        {isRTL ? 'تعديل' : 'Edit'}
                      </Button>
                      <Button variant="ghost" size="sm"
                        className="flex-1 h-7 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                        onClick={() => remove(s)} data-testid={`subject-delete-${s.id}`}>
                        <Trash2 className="h-3 w-3 me-1" />
                        {isRTL ? 'حذف' : 'Delete'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
          <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                {editing?.id ? <Pencil className="h-5 w-5 text-brand-turquoise" /> : <Plus className="h-5 w-5 text-brand-turquoise" />}
                {editing?.id
                  ? (isRTL ? 'تعديل المادة' : 'Edit subject')
                  : (isRTL ? 'إضافة مادة' : 'Add subject')}
              </DialogTitle>
            </DialogHeader>
            {editing && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="font-cairo text-sm">{isRTL ? 'اسم المادة' : 'Subject name'}</Label>
                  <Input value={editing.name}
                    onChange={(e) => setEditing((p) => ({ ...p, name: e.target.value }))}
                    placeholder={isRTL ? 'مثال: الرياضيات' : 'e.g. Mathematics'} />
                </div>
                <div className="space-y-2">
                  <Label className="font-cairo text-sm">{isRTL ? 'الاسم بالإنجليزية (اختياري)' : 'English name (optional)'}</Label>
                  <Input value={editing.name_en}
                    onChange={(e) => setEditing((p) => ({ ...p, name_en: e.target.value }))} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label className="font-cairo text-sm">{isRTL ? 'الرمز (اختياري)' : 'Code (optional)'}</Label>
                    <Input value={editing.code}
                      onChange={(e) => setEditing((p) => ({ ...p, code: e.target.value }))} />
                  </div>
                  <div className="space-y-2">
                    <Label className="font-cairo text-sm">{isRTL ? 'حصص/أسبوع' : 'Periods/week'}</Label>
                    <Input type="number" min={1} max={20} value={editing.weekly_hours}
                      onChange={(e) => setEditing((p) => ({ ...p, weekly_hours: e.target.value }))} />
                  </div>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditing(null)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={save} disabled={saving} data-testid="subject-save">
                {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : null}
                {isRTL ? 'حفظ' : 'Save'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
