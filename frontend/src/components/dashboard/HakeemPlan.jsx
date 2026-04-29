import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import {
  Sparkles,
  Plus,
  ChevronDown,
  Pencil,
  Trash2,
  Check,
  Upload,
  Loader2,
  X,
  ListChecks,
} from 'lucide-react';
import { formatFullDate } from '../../utils/hijriDate';

const PRIORITY_META = {
  urgent: { label_ar: 'عاجل',   label_en: 'Urgent', badge: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300', dot: 'bg-rose-500',  weight: 0 },
  medium: { label_ar: 'متوسط',  label_en: 'Medium', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300', dot: 'bg-amber-500', weight: 1 },
  normal: { label_ar: 'عادي',   label_en: 'Normal', badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300', dot: 'bg-emerald-500', weight: 2 },
};

const SEED_TASKS = [
  { id: 't-1', text: 'متابعة لجنة الاختبارات المتأخرين',  details: 'مراجعة مع مرشد الاختبارات', priority: 'urgent', status: 'active' },
  { id: 't-2', text: 'جولة تفقدية – مبنى ب',              details: '09:00 ص في البنية المدرسية', priority: 'urgent', status: 'active' },
  { id: 't-3', text: 'زيارة صفية – الصف الثالث ج',        details: '10:30 ص حصة التعليم والتعلم', priority: 'medium', status: 'active' },
  { id: 't-4', text: 'اجتماع مجلس الإدارة',                details: '08:00 ص الإدارة المدرسية',   priority: 'normal', status: 'completed' },
];

export const HakeemPlan = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const lang = isRTL ? 'ar' : 'en';

  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ text: '', priority: 'normal' });
  const [editingId, setEditingId] = useState(null);
  const [editingText, setEditingText] = useState('');
  const inputRef = useRef(null);

  const fetchTasks = useCallback(async () => {
    await new Promise((r) => setTimeout(r, 250));
    setTasks(SEED_TASKS);
    setLoading(false);
  }, []);

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

  const toggleStatus = async (task) => {
    const nextStatus = task.status === 'active' ? 'completed' : 'active';
    setTasks((prev) => prev.map((tk) => (tk.id === task.id ? { ...tk, status: nextStatus } : tk)));
    await new Promise((r) => setTimeout(r, 150));
  };

  const addTask = async () => {
    if (!draft.text.trim()) return;
    const newTask = {
      id: `t-${Date.now()}`,
      text: draft.text.trim(),
      details: '',
      priority: draft.priority,
      status: 'active',
    };
    setTasks((prev) => [newTask, ...prev]);
    setDraft({ text: '', priority: 'normal' });
    setAdding(false);
    await new Promise((r) => setTimeout(r, 150));
  };

  const importTasks = async () => {
    await new Promise((r) => setTimeout(r, 150));
  };

  const startEdit = (task) => {
    setEditingId(task.id);
    setEditingText(task.text);
  };

  const commitEdit = async () => {
    if (!editingId) return;
    const id = editingId;
    const text = editingText.trim();
    setTasks((prev) => prev.map((tk) => (tk.id === id && text ? { ...tk, text } : tk)));
    setEditingId(null);
    setEditingText('');
    await new Promise((r) => setTimeout(r, 100));
  };

  const deleteTask = async (id) => {
    setTasks((prev) => prev.filter((tk) => tk.id !== id));
    await new Promise((r) => setTimeout(r, 100));
  };

  const renderTaskRow = (task) => {
    const meta = PRIORITY_META[task.priority] || PRIORITY_META.normal;
    const isCompleted = task.status === 'completed';
    const isEditing = editingId === task.id;
    return (
      <li
        key={task.id}
        className={`group flex items-center gap-3 p-2.5 rounded-xl border transition-all duration-200 ${
          isCompleted
            ? 'bg-muted/20 border-border/30 opacity-70'
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
            <input
              autoFocus
              value={editingText}
              onChange={(e) => setEditingText(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit();
                if (e.key === 'Escape') { setEditingId(null); setEditingText(''); }
              }}
              className="w-full h-7 rounded-md border border-input bg-background px-2 text-sm font-tajawal"
            />
          ) : (
            <p className={`text-sm font-tajawal font-semibold truncate ${isCompleted ? 'line-through text-muted-foreground' : ''}`}>
              {task.text}
            </p>
          )}
          {task.details && !isEditing && (
            <p className={`text-[11px] font-tajawal truncate ${isCompleted ? 'text-muted-foreground/70' : 'text-muted-foreground'}`}>
              {task.details}
            </p>
          )}
        </div>

        {!isCompleted && (
          <Badge className={`shrink-0 border-0 font-cairo text-[10px] px-2 py-0.5 ${meta.badge}`}>
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
            <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-0 font-cairo text-[11px] px-2 py-0.5">
              {activeTasks.length} {isRTL ? 'نشط' : 'active'}
            </Badge>
            <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-0 font-cairo text-[11px] px-2 py-0.5">
              {completedTasks.length} {isRTL ? 'مكتمل' : 'completed'}
            </Badge>
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground font-tajawal mt-1">{todayLabel}</p>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Split-action button */}
        <div className="flex items-stretch gap-px rounded-xl overflow-hidden shadow-sm shadow-brand-purple/10">
          <Button
            type="button"
            onClick={() => setAdding((v) => !v)}
            className="flex-1 rounded-none rounded-s-xl bg-gradient-to-r from-brand-purple to-brand-turquoise hover:opacity-95 text-white font-cairo h-9"
            data-testid="hakeem-quick-add-btn"
          >
            <Plus className="h-3.5 w-3.5 me-1.5" />
            {isRTL ? 'إضافة مهمة' : 'Add Task'}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                className="rounded-none rounded-e-xl bg-brand-purple hover:bg-brand-purple/90 text-white px-2.5 h-9"
                aria-label={isRTL ? 'خيارات الإضافة' : 'Add options'}
                data-testid="hakeem-add-options"
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="font-tajawal">
              <DropdownMenuItem onClick={() => { setAdding(true); }} className="gap-2">
                <Plus className="h-3.5 w-3.5 text-brand-turquoise" />
                {isRTL ? 'إضافة يدوية' : 'Manual Add'}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={importTasks} className="gap-2">
                <Upload className="h-3.5 w-3.5 text-brand-purple" />
                {isRTL ? 'استيراد' : 'Import'}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {adding && (
          <div className="flex items-center gap-2 p-2 rounded-xl border border-brand-turquoise/30 bg-brand-turquoise/5">
            <input
              ref={inputRef}
              value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addTask();
                if (e.key === 'Escape') { setAdding(false); setDraft({ text: '', priority: 'normal' }); }
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
              disabled={!draft.text.trim()}
              className="h-8 rounded-lg bg-brand-turquoise text-white hover:bg-brand-turquoise/90 px-3 text-xs"
            >
              {isRTL ? 'حفظ' : 'Save'}
            </Button>
            <button
              type="button"
              onClick={() => { setAdding(false); setDraft({ text: '', priority: 'normal' }); }}
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
