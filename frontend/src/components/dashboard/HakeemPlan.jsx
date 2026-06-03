import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { toast } from 'sonner';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import {
  Sparkles,
  Plus,
  Pencil,
  Trash2,
  Check,
  Loader2,
  X,
  ListChecks,
} from 'lucide-react';
import { formatFullDate } from '../../utils/hijriDate';
import { getApiErrorMessage } from '../../utils/apiError';

const PRIORITY_META = {
  urgent: { label_ar: 'عاجل',   label_en: 'Urgent', badge: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300', dot: 'bg-rose-500',  weight: 0 },
  medium: { label_ar: 'متوسط',  label_en: 'Medium', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300', dot: 'bg-amber-500', weight: 1 },
  normal: { label_ar: 'عادي',   label_en: 'Normal', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300', dot: 'bg-emerald-500', weight: 2 },
};

const todayStr = () => {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

export const HakeemPlan = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { api } = useAuth();
  const lang = isRTL ? 'ar' : 'en';

  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ title: '', priority: 'normal' });
  const [editingId, setEditingId] = useState(null);
  const [editingText, setEditingText] = useState('');
  const [editingPriority, setEditingPriority] = useState('normal');
  const inputRef = useRef(null);

  const fetchTasks = useCallback(async () => {
    try {
      // Pass the user's local date so we don't drift around midnight UTC.
      const res = await api.get('/v1/hakeem-plan/tasks', { params: { date: todayStr() } });
      const data = Array.isArray(res?.data?.tasks) ? res.data.tasks : [];
      setTasks(data);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[HakeemPlan] fetch error:', err);
      toast.error(isRTL ? 'تعذر تحميل المهام' : 'Failed to load tasks');
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [api, isRTL]);

  useEffect(() => { fetchTasks(); }, [fetchTasks]);

  useEffect(() => {
    if (adding && inputRef.current) inputRef.current.focus();
  }, [adding]);

  const todayLabel = useMemo(() => {
    try { return formatFullDate(new Date(), lang)?.full || ''; } catch { return ''; }
  }, [lang]);

  const activeTasks = useMemo(
    () => tasks
      .filter((tk) => tk.status === 'active')
      .sort((a, b) => (PRIORITY_META[a.priority]?.weight ?? 9) - (PRIORITY_META[b.priority]?.weight ?? 9)),
    [tasks]
  );
  const completedTasks = useMemo(() => tasks.filter((tk) => tk.status === 'completed'), [tasks]);

  const extractError = (err, fallback) => {
    const detail = err?.response?.data?.error?.message || getApiErrorMessage(err);
    return detail || fallback;
  };

  const toggleStatus = async (task) => {
    const nextStatus = task.status === 'active' ? 'completed' : 'active';
    // OPTIMISTIC: flip immediately so the row jumps between sections instantly.
    setTasks((prev) => prev.map((tk) => (tk.id === task.id ? { ...tk, status: nextStatus } : tk)));
    try {
      const res = await api.patch(`/v1/hakeem-plan/tasks/${task.id}`, { status: nextStatus });
      const updated = res?.data?.task;
      if (updated) {
        setTasks((prev) => prev.map((tk) => (tk.id === task.id ? updated : tk)));
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[HakeemPlan] toggle error:', err);
      // Roll back on failure
      setTasks((prev) => prev.map((tk) => (tk.id === task.id ? { ...tk, status: task.status } : tk)));
      toast.error(extractError(err, isRTL ? 'تعذر تحديث المهمة' : 'Failed to update task'));
    }
  };

  const addTask = async () => {
    const title = draft.title.trim();
    if (!title) return;
    const tempId = `tmp-${Date.now()}`;
    const optimistic = {
      id: tempId,
      title,
      details: '',
      priority: draft.priority,
      status: 'active',
      source: 'manual',
      task_date: todayStr(),
    };
    // OPTIMISTIC: show row instantly
    setTasks((prev) => [optimistic, ...prev]);
    setDraft({ title: '', priority: 'normal' });
    setAdding(false);
    try {
      const res = await api.post('/v1/hakeem-plan/tasks', {
        title,
        priority: optimistic.priority,
        task_date: todayStr(),
      });
      const created = res?.data?.task;
      if (created) {
        setTasks((prev) => prev.map((tk) => (tk.id === tempId ? created : tk)));
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[HakeemPlan] add error:', err);
      setTasks((prev) => prev.filter((tk) => tk.id !== tempId));
      toast.error(extractError(err, isRTL ? 'تعذر إضافة المهمة' : 'Failed to add task'));
    }
  };

  const startEdit = (task) => {
    setEditingId(task.id);
    setEditingText(task.title);
    setEditingPriority(task.priority || 'normal');
  };

  const commitEdit = async () => {
    if (!editingId) return;
    const id = editingId;
    const text = editingText.trim();
    const priority = editingPriority;
    const original = tasks.find((tk) => tk.id === id);
    setEditingId(null);
    setEditingText('');
    setEditingPriority('normal');
    if (!text || !original) return;
    const titleChanged = text !== original.title;
    const priorityChanged = priority !== original.priority;
    if (!titleChanged && !priorityChanged) return;
    // OPTIMISTIC: apply all changed fields immediately
    const patch = {};
    if (titleChanged) patch.title = text;
    if (priorityChanged) patch.priority = priority;
    setTasks((prev) => prev.map((tk) => (tk.id === id ? { ...tk, ...patch } : tk)));
    try {
      const res = await api.patch(`/v1/hakeem-plan/tasks/${id}`, patch);
      const updated = res?.data?.task;
      if (updated) {
        setTasks((prev) => prev.map((tk) => (tk.id === id ? updated : tk)));
      }
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[HakeemPlan] edit error:', err);
      // Roll back both fields on error
      setTasks((prev) => prev.map((tk) => (tk.id === id ? original : tk)));
      toast.error(extractError(err, isRTL ? 'تعذر تعديل المهمة' : 'Failed to edit task'));
    }
  };

  const deleteTask = async (id) => {
    const snapshot = tasks;
    // OPTIMISTIC
    setTasks((prev) => prev.filter((tk) => tk.id !== id));
    try {
      await api.delete(`/v1/hakeem-plan/tasks/${id}`);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[HakeemPlan] delete error:', err);
      setTasks(snapshot);
      toast.error(extractError(err, isRTL ? 'تعذر حذف المهمة' : 'Failed to delete task'));
    }
  };

  const renderTaskRow = (task) => {
    const meta = PRIORITY_META[task.priority] || PRIORITY_META.normal;
    const isCompleted = task.status === 'completed';
    const isEditing = editingId === task.id;
    const isAI = task.source === 'ai';
    return (
      <li
        key={task.id}
        className={`group flex items-center gap-3 p-2.5 rounded-xl border transition-all duration-200 ${
          isCompleted
            ? 'bg-muted/20 border-border/30 opacity-70'
            : isAI
              ? 'bg-gradient-to-r from-brand-purple/[0.04] to-brand-turquoise/[0.04] border-brand-purple/30 hover:border-brand-purple/50 hover:shadow-sm'
              : 'bg-background border-border/50 hover:border-brand-turquoise/40 hover:shadow-sm'
        }`}
        data-testid={`task-row-${task.id}`}
      >
        <button
          type="button"
          onClick={() => toggleStatus(task)}
          className={`shrink-0 w-5 h-5 rounded-md border flex items-center justify-center transition-all ${
            isCompleted
              ? 'bg-emerald-500 border-emerald-500 text-white'
              : 'border-muted-foreground/30 hover:border-brand-turquoise hover:bg-brand-turquoise/10'
          }`}
          aria-label={isCompleted ? (isRTL ? 'إعادة كنشط' : 'Mark active') : (isRTL ? 'إكمال' : 'Complete')}
          data-testid={`toggle-task-${task.id}`}
        >
          {isCompleted && <Check className="h-3 w-3" />}
        </button>

        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="flex items-center gap-1.5">
              <input
                autoFocus
                value={editingText}
                onChange={(e) => setEditingText(e.target.value)}
                onBlur={(e) => {
                  // Don't commit if focus moved to the priority select in this row
                  if (e.relatedTarget?.getAttribute('data-edit-priority-select') === String(task.id)) return;
                  commitEdit();
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitEdit();
                  if (e.key === 'Escape') { setEditingId(null); setEditingText(''); setEditingPriority('normal'); }
                }}
                className="flex-1 min-w-0 h-7 rounded-md border border-input bg-background px-2 text-sm font-tajawal"
                data-testid={`edit-title-input-${task.id}`}
              />
              <select
                value={editingPriority}
                onChange={(e) => setEditingPriority(e.target.value)}
                onBlur={commitEdit}
                data-edit-priority-select={String(task.id)}
                className="h-7 rounded-md border border-input bg-background px-1.5 text-xs font-cairo shrink-0"
                data-testid={`edit-priority-select-${task.id}`}
              >
                {Object.entries(PRIORITY_META).map(([key, meta]) => (
                  <option key={key} value={key}>{isRTL ? meta.label_ar : meta.label_en}</option>
                ))}
              </select>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 min-w-0">
              {isAI && !isCompleted && (
                <span
                  title={isRTL ? 'مقترح من حكيم' : 'Suggested by Hakeem'}
                  aria-label={isRTL ? 'مقترح من حكيم' : 'Suggested by Hakeem'}
                  className="shrink-0 inline-flex items-center justify-center w-4.5 h-4.5 rounded-md bg-gradient-to-br from-brand-purple to-brand-turquoise shadow-sm shadow-brand-purple/30"
                  data-testid={`ai-source-badge-${task.id}`}
                >
                  <Sparkles className="h-2.5 w-2.5 text-white" />
                </span>
              )}
              <p className={`text-sm font-tajawal font-semibold truncate ${isCompleted ? 'line-through text-muted-foreground' : ''}`}>
                {task.title}
              </p>
            </div>
          )}
          {task.details && !isEditing && (
            <p className={`text-[11px] font-tajawal truncate ${isCompleted ? 'text-muted-foreground/70' : 'text-muted-foreground'}`}>
              {task.details}
            </p>
          )}
        </div>

        {!isCompleted && !isEditing && (
          <Badge className={`shrink-0 border-0 font-cairo text-[10px] px-2 py-0.5 ${meta.badge}`} data-testid={`priority-badge-${task.id}`}>
            {isRTL ? meta.label_ar : meta.label_en}
          </Badge>
        )}

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <button
            type="button"
            onClick={() => startEdit(task)}
            className="w-7 h-7 rounded-lg hover:bg-brand-turquoise/10 text-brand-turquoise flex items-center justify-center"
            aria-label={t('edit')}
            data-testid={`edit-task-${task.id}`}
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => deleteTask(task.id)}
            className="w-7 h-7 rounded-lg hover:bg-red-500/10 text-red-500 flex items-center justify-center"
            aria-label={t('delete')}
            data-testid={`delete-task-${task.id}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </li>
    );
  };

  return (
    <Card className="card-nassaq h-full" data-testid="hakeem-plan">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="flex items-center gap-2 font-cairo text-lg">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-turquoise to-brand-purple flex items-center justify-center shadow-sm shadow-brand-turquoise/30">
              <Sparkles className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? 'خطة حكيم لليوم' : "Hakeem's Daily Plan"}
          </CardTitle>
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-0 font-cairo text-[11px] px-2 py-0.5" data-testid="hakeem-active-count">
              {activeTasks.length} {isRTL ? 'نشط' : 'active'}
            </Badge>
            <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-0 font-cairo text-[11px] px-2 py-0.5" data-testid="hakeem-completed-count">
              {completedTasks.length} {isRTL ? 'مكتمل' : 'completed'}
            </Badge>
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground font-tajawal mt-1">{todayLabel}</p>
      </CardHeader>

      <CardContent className="space-y-3">
        <Button
          type="button"
          onClick={() => setAdding(true)}
          className="w-full rounded-xl bg-gradient-to-r from-brand-purple to-brand-turquoise hover:opacity-95 text-white font-cairo h-9 shadow-sm shadow-brand-purple/10"
          data-testid="hakeem-quick-add-btn"
        >
          <Plus className="h-3.5 w-3.5 me-1.5" />
          {isRTL ? 'إضافة مهمة' : 'Add Task'}
        </Button>

        {adding && (
          <div className="flex items-center gap-2 p-2 rounded-xl border border-brand-turquoise/30 bg-brand-turquoise/5">
            <input
              ref={inputRef}
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addTask();
                if (e.key === 'Escape') { setAdding(false); setDraft({ title: '', priority: 'normal' }); }
              }}
              placeholder={isRTL ? 'اكتب المهمة...' : 'Type the task...'}
              className="flex-1 h-8 rounded-lg border border-input bg-background px-2.5 text-sm font-tajawal"
              data-testid="hakeem-quick-input"
            />
            <select
              value={draft.priority}
              onChange={(e) => setDraft({ ...draft, priority: e.target.value })}
              className="h-8 rounded-lg border border-input bg-background px-2 text-xs font-cairo"
              data-testid="hakeem-priority-select"
            >
              {Object.entries(PRIORITY_META).map(([key, meta]) => (
                <option key={key} value={key}>{isRTL ? meta.label_ar : meta.label_en}</option>
              ))}
            </select>
            <Button
              size="sm"
              onClick={addTask}
              disabled={!draft.title.trim()}
              className="h-8 rounded-lg bg-brand-turquoise text-white hover:bg-brand-turquoise/90 px-3 text-xs"
            >
              {isRTL ? 'حفظ' : 'Save'}
            </Button>
            <button
              type="button"
              onClick={() => { setAdding(false); setDraft({ title: '', priority: 'normal' }); }}
              className="w-7 h-7 rounded-lg hover:bg-muted flex items-center justify-center text-muted-foreground"
              aria-label={isRTL ? 'إلغاء' : 'Cancel'}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-brand-turquoise" />
          </div>
        ) : (
          <>
            <ul className="space-y-1.5" data-testid="hakeem-active-list">
              {activeTasks.length === 0 ? (
                <li className="text-center py-6">
                  <ListChecks className="h-7 w-7 text-emerald-500/70 mx-auto mb-2" />
                  <p className="text-sm font-tajawal text-muted-foreground">
                    {isRTL ? 'لا توجد مهام نشطة' : 'No active tasks'}
                  </p>
                </li>
              ) : (
                activeTasks.map(renderTaskRow)
              )}
            </ul>

            {completedTasks.length > 0 && (
              <>
                <div className="flex items-center gap-2 pt-1">
                  <div className="h-px flex-1 bg-border" />
                  <span className="text-[10px] font-cairo text-muted-foreground uppercase tracking-wider">
                    {isRTL ? `مكتملة (${completedTasks.length})` : `Completed (${completedTasks.length})`}
                  </span>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <ul className="space-y-1.5" data-testid="hakeem-completed-list">
                  {completedTasks.map(renderTaskRow)}
                </ul>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default HakeemPlan;
