import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import {
  Settings, Trash2, Plus, Star, ThumbsUp, ThumbsDown,
  CheckCircle2, XCircle, ClipboardCheck, Mic, Hand, Sparkles,
} from 'lucide-react';

/**
 * Color palette for evaluation items. Each entry maps a color key to
 * Tailwind classes for the row background, points text, and icon tint.
 */
const EVAL_COLORS = {
  emerald: { row: 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-200/60 dark:border-emerald-900/40', points: 'text-emerald-600', icon: 'text-emerald-500' },
  red:     { row: 'bg-red-50/60 dark:bg-red-950/20 border-red-200/60 dark:border-red-900/40',                 points: 'text-red-600',     icon: 'text-red-500' },
  amber:   { row: 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-200/60 dark:border-amber-900/40',         points: 'text-amber-600',   icon: 'text-amber-500' },
  sky:     { row: 'bg-sky-50/60 dark:bg-sky-950/20 border-sky-200/60 dark:border-sky-900/40',                 points: 'text-sky-600',     icon: 'text-sky-500' },
  purple:  { row: 'bg-purple-50/60 dark:bg-purple-950/20 border-purple-200/60 dark:border-purple-900/40',     points: 'text-purple-600',  icon: 'text-purple-500' },
  gray:    { row: 'bg-muted/40 dark:bg-card/40 border-border',                                                points: 'text-muted-foreground', icon: 'text-muted-foreground' },
};

const EVAL_ICONS = {
  CheckCircle2, XCircle, ClipboardCheck, Mic, Hand, Star, Sparkles,
};

const formatPoints = (n) => {
  const v = Number(n) || 0;
  if (v > 0) return `${v}+`;
  if (v < 0) return `${Math.abs(v)}-`;
  return '0';
};

/**
 * Shared "Sidebar Settings" dialog used in both فصولي → تفاصيل الفصل
 * and the live class (الحصة التفاعلية). It exposes three tabs:
 *   1) عناصر التقييم – customizable evaluation items list
 *   2) السلوكيات     – grouped positive/negative behaviour lists
 *   3) المهارات      – kept identical to the legacy skills section
 *
 * The dialog is fully controlled. The parent owns all state arrays
 * and persistence; this component only renders + emits add/remove.
 */
export default function SidebarSettingsDialog({
  open,
  onOpenChange,
  isRTL = true,
  t = (k) => k,

  // ── Evaluation Elements tab ───────────────────────────────────
  evaluationItems = [],
  onAddEvaluationItem,
  onRemoveEvaluationItem,

  // ── Behaviors tab ─────────────────────────────────────────────
  positiveBehaviours = [],
  negativeBehaviours = [],
  onAddPositiveBehaviour,
  onAddNegativeBehaviour,
  onRemovePositiveBehaviour,
  onRemoveNegativeBehaviour,

  // ── Skills tab (legacy UI preserved) ──────────────────────────
  skillEnabled = true,
  onToggleSkillEnabled,
  skillTypes = [],
  customSkills = [],
  onAddCustomSkill,
  onRemoveCustomSkill,
}) {
  const [tab, setTab] = useState('evaluation');

  // ── Add-form local state ───────────────────────────────────────
  const [evalDraft, setEvalDraft] = useState({ name: '', color: 'emerald', points: 1 });
  const [behaviourDraft, setBehaviourDraft] = useState({ name: '', points: 1 });
  const [skillDraft, setSkillDraft] = useState('');

  const handleAddEvaluation = () => {
    const name = evalDraft.name.trim();
    if (!name) return;
    onAddEvaluationItem?.({
      id: `eval_${Date.now()}`,
      name,
      color: evalDraft.color,
      points: Number(evalDraft.points) || 0,
    });
    setEvalDraft({ name: '', color: 'emerald', points: 1 });
  };

  const handleAddBehaviour = (category) => {
    const name = behaviourDraft.name.trim();
    if (!name) return;
    const item = {
      id: `bhv_${Date.now()}`,
      name,
      points: Number(behaviourDraft.points) || 0,
    };
    if (category === 'positive') onAddPositiveBehaviour?.(item);
    else onAddNegativeBehaviour?.(item);
    setBehaviourDraft({ name: '', points: 1 });
  };

  const handleAddSkill = () => {
    const name = skillDraft.trim();
    if (!name) return;
    onAddCustomSkill?.(name);
    setSkillDraft('');
  };

  // ─────────────────────────────────────────────────────────────────
  // Tab definitions
  // ─────────────────────────────────────────────────────────────────
  const TABS = [
    { id: 'evaluation', label: t('evaluationElements') || 'عناصر التقييم' },
    { id: 'behaviours', label: t('behaviours') || 'السلوكيات' },
    { id: 'skills',     label: t('skills') || 'المهارات' },
  ];

  // ─────────────────────────────────────────────────────────────────
  // Renderers
  // ─────────────────────────────────────────────────────────────────
  const renderEvaluationTab = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        {evaluationItems.length === 0 ? (
          <p className="text-center py-6 text-xs text-muted-foreground font-cairo">
            {t('noItemsYet') || 'لا توجد عناصر بعد'}
          </p>
        ) : (
          evaluationItems.map((item) => {
            const color = EVAL_COLORS[item.color] || EVAL_COLORS.gray;
            const Icon = EVAL_ICONS[item.icon] || CheckCircle2;
            return (
              <div
                key={item.id}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border ${color.row}`}
              >
                <button
                  type="button"
                  onClick={() => onRemoveEvaluationItem?.(item.id)}
                  className="text-red-500 hover:text-red-600 transition-colors shrink-0"
                  aria-label={t('delete') || 'حذف'}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
                <span className={`text-xs font-bold tabular-nums font-cairo flex-none w-8 text-center ${color.points}`}>
                  {formatPoints(item.points)}
                </span>
                <div className="flex-1 flex items-center justify-end gap-2">
                  <span className="text-sm font-cairo text-foreground">{item.name}</span>
                  <Icon className={`h-4 w-4 shrink-0 ${color.icon}`} />
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add new evaluation form */}
      <div className="space-y-2 pt-2">
        <input
          type="text"
          value={evalDraft.name}
          onChange={(e) => setEvalDraft((d) => ({ ...d, name: e.target.value }))}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAddEvaluation(); }}
          placeholder={t('evaluationName') || 'اسم التقييم'}
          dir={isRTL ? 'rtl' : 'ltr'}
          className="w-full text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo placeholder:text-muted-foreground/60"
        />
        <div className="grid grid-cols-2 gap-2">
          <select
            value={evalDraft.color}
            onChange={(e) => setEvalDraft((d) => ({ ...d, color: e.target.value }))}
            className="text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center"
          >
            {Object.keys(EVAL_COLORS).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <input
            type="number"
            value={evalDraft.points}
            onChange={(e) => setEvalDraft((d) => ({ ...d, points: e.target.value }))}
            placeholder={t('points') || 'النقاط'}
            dir={isRTL ? 'rtl' : 'ltr'}
            className="text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/60"
          />
        </div>
        <Button
          type="button"
          onClick={handleAddEvaluation}
          disabled={!evalDraft.name.trim()}
          className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded-full py-3 font-cairo text-sm font-bold shadow-sm"
        >
          <Plus className="h-4 w-4 me-1" />
          {t('addEvaluation') || 'إضافة تقييم'}
        </Button>
      </div>
    </div>
  );

  // Normalize legacy `string` entries to `{id, name, points}` so the dialog
  // is robust against mixed-shape arrays sent by parents that haven't migrated.
  const normalizeBehaviour = (b, i, defaultPoints) => {
    if (b && typeof b === 'object') return b;
    const name = String(b ?? '');
    return { id: `legacy_${defaultPoints > 0 ? 'p' : 'n'}_${i}_${name}`, name, points: defaultPoints };
  };

  const renderBehaviourGroup = (title, items, color, onRemove) => {
    const isPositive = color === 'green';
    const titleColor = isPositive ? 'text-emerald-600' : 'text-red-600';
    const rowBg = isPositive
      ? 'bg-emerald-50/70 dark:bg-emerald-950/20 border-emerald-200/60 dark:border-emerald-900/40'
      : 'bg-red-50/70 dark:bg-red-950/20 border-red-200/60 dark:border-red-900/40';
    const pointsColor = isPositive ? 'text-emerald-600' : 'text-red-600';
    const Icon = isPositive ? ThumbsUp : ThumbsDown;
    const iconColor = isPositive ? 'text-emerald-500' : 'text-red-500';

    return (
      <div className="space-y-2">
        <div className={`text-xs font-bold font-cairo ${titleColor} text-end`}>
          {title}
        </div>
        {items.length === 0 ? (
          <p className="text-center py-3 text-[11px] text-muted-foreground font-cairo">
            {t('noBehavioursYet') || 'لا توجد سلوكيات بعد'}
          </p>
        ) : (
          items.map((raw, idx) => {
            const item = normalizeBehaviour(raw, idx, isPositive ? 2 : -2);
            return (
            <div
              key={item.id}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border ${rowBg}`}
            >
              <button
                type="button"
                onClick={() => onRemove?.(item.id)}
                className="text-red-500 hover:text-red-600 transition-colors shrink-0"
                aria-label={t('delete') || 'حذف'}
              >
                <Trash2 className="h-4 w-4" />
              </button>
              <span className={`text-xs font-bold tabular-nums font-cairo flex-none w-8 text-center ${pointsColor}`}>
                {formatPoints(item.points)}
              </span>
              <div className="flex-1 flex items-center justify-end gap-2">
                <span className="text-sm font-cairo text-foreground">{item.name}</span>
                <Icon className={`h-4 w-4 shrink-0 ${iconColor}`} />
              </div>
            </div>
            );
          })
        )}
      </div>
    );
  };

  const renderBehavioursTab = () => (
    <div className="space-y-5">
      {renderBehaviourGroup(t('positive') || 'إيجابي', positiveBehaviours, 'green', onRemovePositiveBehaviour)}
      {renderBehaviourGroup(t('negative') || 'سلبي',   negativeBehaviours, 'red',   onRemoveNegativeBehaviour)}

      {/* Add new behaviour form */}
      <div className="space-y-2 pt-2 border-t border-border">
        <input
          type="text"
          value={behaviourDraft.name}
          onChange={(e) => setBehaviourDraft((d) => ({ ...d, name: e.target.value }))}
          placeholder={t('behaviourName') || 'اسم السلوك'}
          dir={isRTL ? 'rtl' : 'ltr'}
          className="w-full text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo placeholder:text-muted-foreground/60"
        />
        <input
          type="number"
          value={behaviourDraft.points}
          onChange={(e) => setBehaviourDraft((d) => ({ ...d, points: e.target.value }))}
          placeholder={t('points') || 'النقاط'}
          dir={isRTL ? 'rtl' : 'ltr'}
          className="w-full text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/60"
        />
        <div className="grid grid-cols-2 gap-2">
          {/* Negative on the left (LTR order); RTL flips visually so this lands on the visual left */}
          <Button
            type="button"
            variant="outline"
            onClick={() => handleAddBehaviour('negative')}
            disabled={!behaviourDraft.name.trim()}
            className="rounded-full border-2 border-red-300 dark:border-red-800/60 text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 font-cairo text-sm font-bold py-2.5 gap-2"
          >
            <ThumbsDown className="h-4 w-4" />
            {t('negative') || 'سلبي'}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleAddBehaviour('positive')}
            disabled={!behaviourDraft.name.trim()}
            className="rounded-full border-2 border-emerald-300 dark:border-emerald-800/60 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 font-cairo text-sm font-bold py-2.5 gap-2"
          >
            <ThumbsUp className="h-4 w-4" />
            {t('positive') || 'إيجابي'}
          </Button>
        </div>
      </div>
    </div>
  );

  // Skills tab — preserves the legacy UI shape (toggle row + chip list + add input)
  const renderSkillsTab = () => (
    <div className="space-y-3">
      {typeof onToggleSkillEnabled === 'function' && (
        <div className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-xl border border-border bg-muted/30 dark:bg-card/40">
          <span className="text-sm font-cairo flex items-center gap-2">
            <Star className="h-4 w-4 text-purple-500" />
            {t('skillItems') || 'المهارات'}
          </span>
          <button
            type="button"
            onClick={() => onToggleSkillEnabled(!skillEnabled)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${skillEnabled ? 'bg-purple-500' : 'bg-muted-foreground/30'}`}
            aria-pressed={skillEnabled}
          >
            <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${skillEnabled ? 'translate-x-0.5' : 'translate-x-[18px]'}`} />
          </button>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[11px] text-muted-foreground font-cairo">{t('currentSkills') || 'المهارات الحالية'}</p>
        <div className="flex flex-wrap gap-1.5">
          {[
            ...skillTypes.map((s) => (typeof s === 'string' ? s : (s?.name_ar || s?.name_en || s?.name || s?.label || ''))),
            ...customSkills,
          ].map((skill, i) => {
            const isCustom = i >= skillTypes.length;
            const label = typeof skill === 'string' ? skill : String(skill ?? '');
            if (!label) return null;
            return (
              <span
                key={`${i}-${label}`}
                className="inline-flex items-center gap-1 bg-purple-50 dark:bg-purple-900/20 px-2 py-1 rounded-lg text-[11px] text-purple-700 dark:text-purple-300"
              >
                <Star className="h-2.5 w-2.5" />
                {label}
                {isCustom && (
                  <button
                    type="button"
                    onClick={() => onRemoveCustomSkill?.(i - skillTypes.length)}
                    className="text-red-600 dark:text-red-400 hover:text-red-500"
                    aria-label={t('delete') || 'حذف'}
                  >
                    <XCircle className="h-2.5 w-2.5" />
                  </button>
                )}
              </span>
            );
          })}
          {skillTypes.length === 0 && customSkills.length === 0 && (
            <span className="text-[11px] text-muted-foreground font-cairo">
              {t('noSkillsYet') || 'لا توجد مهارات بعد'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 pt-1">
          <input
            value={skillDraft}
            onChange={(e) => setSkillDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddSkill(); }}
            className="flex-1 text-[11px] bg-card dark:bg-muted rounded-lg border px-2 py-1.5 outline-none focus:border-purple-500 font-cairo"
            placeholder={t('addNewSkill') || 'إضافة مهارة جديدة'}
            dir={isRTL ? 'rtl' : 'ltr'}
          />
          <button
            type="button"
            onClick={handleAddSkill}
            disabled={!skillDraft.trim()}
            className="p-1.5 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 hover:bg-purple-200 dark:hover:bg-purple-900/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label={t('add') || 'إضافة'}
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md w-full max-h-[90vh] overflow-y-auto p-0 gap-0 border-0 shadow-2xl rounded-2xl"
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-border">
          <DialogTitle className="font-cairo flex items-center gap-2 text-base font-bold">
            <Settings className="h-5 w-5 text-brand-turquoise" />
            {t('sidebarSettings') || 'إعدادات الشريط الجانبي'}
          </DialogTitle>
        </DialogHeader>

        {/* Tab navigation with underline indicator */}
        <div className="flex items-center px-5 pt-3 border-b border-border">
          {TABS.map((tDef) => {
            const active = tab === tDef.id;
            return (
              <button
                key={tDef.id}
                type="button"
                onClick={() => setTab(tDef.id)}
                className={`flex-1 px-3 pb-3 pt-2 text-sm font-cairo font-semibold transition relative ${
                  active ? 'text-brand-turquoise' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {tDef.label}
                {active && (
                  <span className="absolute inset-x-3 -bottom-px h-[2px] bg-brand-turquoise rounded-full" />
                )}
              </button>
            );
          })}
        </div>

        <div className="p-5">
          {tab === 'evaluation' && renderEvaluationTab()}
          {tab === 'behaviours' && renderBehavioursTab()}
          {tab === 'skills' && renderSkillsTab()}
        </div>
      </DialogContent>
    </Dialog>
  );
}
