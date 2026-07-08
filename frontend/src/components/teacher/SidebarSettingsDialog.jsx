import { useState, useMemo } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import {
  Settings, Trash2, Plus, Star, ThumbsUp, ThumbsDown,
  CheckCircle2, XCircle, ClipboardCheck, Mic, Hand, Sparkles,
  BookOpen, FileSpreadsheet, GripVertical, Loader2, Pencil, Check,
} from 'lucide-react';

// Default score weight (وزن الدرجة) awarded for a skill that carries no
// configured value — mirrors the backend `special_skill` rule so the chip
// badge and the live picker show what is actually awarded when recorded.
const DEFAULT_SKILL_POINTS = 3;

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

/**
 * Format a points value with a leading +/- sign. When `signOverride` is
 * 'positive' or 'negative' the sign is forced regardless of `n`'s own
 * sign — this lets the UI present the badge using the *category* a
 * teacher selected (e.g. an item filed under "إيجابي") even if the
 * underlying value happens to be stored unsigned. Falls back to the
 * intrinsic sign of `n` when no override is provided.
 */
const formatPoints = (n, signOverride) => {
  const abs = Math.abs(Number(n) || 0);
  if (signOverride === 'positive') return abs === 0 ? '0' : `${abs}+`;
  if (signOverride === 'negative') return abs === 0 ? '0' : `${abs}-`;
  const v = Number(n) || 0;
  if (v > 0) return `${v}+`;
  if (v < 0) return `${Math.abs(v)}-`;
  return '0';
};

/**
 * Map an evaluation "type" (positive/negative/neutral) to the sign
 * applied to its raw absolute points value. Teachers only ever enter
 * positive numbers in the form — the sign is derived here so the
 * scoring math (add for positive categories, subtract for negative)
 * stays consistent end-to-end.
 */
const signedPointsForType = (rawPoints, type) => {
  const abs = Math.abs(Number(rawPoints) || 0);
  if (type === 'positive') return abs;
  if (type === 'negative') return -abs;
  return 0; // neutral
};

/**
 * Default color paired with each evaluation type. Used when the
 * teacher picks a type but hasn't overridden the color.
 */
const DEFAULT_COLOR_FOR_TYPE = {
  positive: 'emerald',
  negative: 'red',
  neutral: 'gray',
};

/**
 * Internal toggle row used by the "خيارات الحصة" tab. Mirrors the visual
 * shape of the legacy SettingsToggleRow originally inlined in
 * SessionTeachPage so behavior + RTL handling are preserved verbatim.
 */
function SettingsToggleRow({ icon, label, enabled, onToggle, t }) {
  return (
    <div className="flex items-center justify-between gap-2 bg-muted/30 dark:bg-card/50 rounded-lg px-3 py-2">
      <span className="flex items-center gap-2 text-sm font-medium font-cairo">
        <span className={enabled ? 'text-brand-turquoise' : 'text-muted-foreground'}>{icon}</span>
        {label}
      </span>
      <button
        type="button"
        onClick={onToggle}
        role="switch"
        aria-checked={enabled}
        className={`relative inline-flex items-center h-6 w-11 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise/60 ${
          enabled ? 'bg-brand-turquoise' : 'bg-muted-foreground/30'
        }`}
        title={enabled ? (t ? t('enabled') : 'On') : (t ? t('disabled') : 'Off')}
      >
        <span
          className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${
            enabled ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-0.5 rtl:-translate-x-0.5'
          }`}
        />
      </button>
    </div>
  );
}

/**
 * Shared "Sidebar Settings" dialog used in فصولي → تفاصيل الفصل
 * and the live class (الحصة التفاعلية).
 *
 * It groups its tabs into two visual sections:
 *   Group A — تعريفات العناصر:  عناصر التقييم · السلوكيات · المهارات
 *   Group B — تكوين الحصة:       خيارات الحصة · انماط التقييم
 *
 * Group B is rendered only when a `sessionConfig` prop is supplied, which
 * is how SessionTeachPage merges its former "إعدادات الحصة" modal in
 * here. All state is owned by the parent — this component is purely
 * controlled.
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
  // Edit the score weight (وزن الدرجة) of an already-saved skill. Registered
  // skill types persist server-side (durable, school-scoped); custom skills
  // update local session config. Both are optional so callers that haven't
  // wired editing keep the legacy add/remove-only behaviour.
  onUpdateSkillType,
  onUpdateCustomSkill,

  // ── Group B: session configuration (optional) ─────────────────
  // When this object is provided, the dialog renders the second
  // visual group of tabs (خيارات الحصة, انماط التقييم) and a
  // sticky Save button on those tabs.
  sessionConfig = null,
}) {
  const hasSessionConfig = !!sessionConfig;

  // Default to the first tab of the first visible group.
  const [tab, setTab] = useState('evaluation');

  // ── Add-form local state ───────────────────────────────────────
  // Teachers only ever enter the *magnitude* of points; sign is derived
  // from the chosen category/type so the scoring math stays consistent.
  const [evalDraft, setEvalDraft] = useState({ name: '', type: '', color: '', points: 1 });
  const [behaviourDraft, setBehaviourDraft] = useState({ name: '', points: 1 });
  // Skills now carry both a display name and a teacher-defined point
  // magnitude (the same shape as custom behaviours/evaluation items).
  const [skillDraft, setSkillDraft] = useState({ name: '', points: 3 });
  // Inline weight-edit state for an already-saved skill. `key` identifies the
  // chip being edited (`reg-<id>` or `cus-<index>`); `value` is the draft
  // magnitude as a string so the number field can be cleared while typing.
  const [skillEdit, setSkillEdit] = useState(null);

  const startSkillEdit = (key, current) => setSkillEdit({ key, value: String(current ?? '') });
  const cancelSkillEdit = () => setSkillEdit(null);
  const commitSkillEdit = (entry) => {
    const n = Math.abs(Number(skillEdit?.value));
    // Reject empty/zero/non-numeric magnitudes; keep the field open so the
    // teacher can correct it instead of silently discarding the edit.
    if (!Number.isFinite(n) || n <= 0) return;
    if (entry.isCustom) onUpdateCustomSkill?.(entry.customIndex, n);
    else onUpdateSkillType?.(entry.id, n);
    setSkillEdit(null);
  };

  // Coerce a free-form number input to its absolute integer value as a
  // string. Used by the points fields so a teacher cannot type "-" or
  // submit a negative magnitude — sign always comes from the category.
  const sanitizePoints = (raw) => {
    if (raw === '' || raw === null || raw === undefined) return '';
    const n = Math.abs(Number(raw));
    if (!Number.isFinite(n)) return '';
    return String(n);
  };

  const handleAddEvaluation = () => {
    const name = evalDraft.name.trim();
    if (!name) return;
    if (!evalDraft.type) return; // category is required
    const color = evalDraft.color || DEFAULT_COLOR_FOR_TYPE[evalDraft.type] || 'gray';
    onAddEvaluationItem?.({
      id: `eval_${Date.now()}`,
      name,
      type: evalDraft.type,
      color,
      points: signedPointsForType(evalDraft.points, evalDraft.type),
    });
    setEvalDraft({ name: '', type: '', color: '', points: 1 });
  };

  const handleAddBehaviour = (category) => {
    const name = behaviourDraft.name.trim();
    if (!name) return;
    // Force the sign from the button the teacher clicked, ignoring any
    // sign the teacher might have typed.
    const points = signedPointsForType(behaviourDraft.points, category);
    const item = { id: `bhv_${Date.now()}`, name, points };
    if (category === 'positive') onAddPositiveBehaviour?.(item);
    else onAddNegativeBehaviour?.(item);
    setBehaviourDraft({ name: '', points: 1 });
  };

  const handleAddSkill = () => {
    const name = (skillDraft.name || '').trim();
    if (!name) return;
    const rawPts = Math.abs(Number(skillDraft.points));
    const points = Number.isFinite(rawPts) && rawPts > 0 ? rawPts : 3;
    // Pass an object so the parent can store the configured magnitude
    // alongside the name. Parents that haven't migrated yet will simply
    // see the name via the legacy `.name` access path.
    onAddCustomSkill?.({ id: `custom_${Date.now()}`, name, points });
    setSkillDraft({ name: '', points: 3 });
  };

  // ─────────────────────────────────────────────────────────────────
  // Tab group definitions
  // ─────────────────────────────────────────────────────────────────
  const TAB_GROUPS = useMemo(() => {
    const groups = [
      {
        id: 'elements',
        label: t('elementsDefinitions') || 'تعريفات العناصر',
        tabs: [
          { id: 'evaluation', label: t('evaluationElements') || 'عناصر التقييم' },
          { id: 'behaviours', label: t('behaviours') || 'السلوكيات' },
          { id: 'skills',     label: t('skills') || 'المهارات' },
        ],
      },
    ];
    if (hasSessionConfig) {
      groups.push({
        id: 'session',
        label: t('sessionConfiguration') || 'تكوين الحصة',
        tabs: [
          { id: 'sessionOptions',     label: t('sessionOptions') || 'خيارات الحصة' },
          { id: 'evaluationPatterns', label: t('evaluationPatterns') || 'أنماط التقييم' },
        ],
      });
    }
    return groups;
  }, [hasSessionConfig, t]);

  const isSessionTab = tab === 'sessionOptions' || tab === 'evaluationPatterns';

  // ─────────────────────────────────────────────────────────────────
  // Group A renderers
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
            // Derive the visual category: prefer the explicit `type`
            // saved with the item, otherwise fall back to the sign of
            // its stored points (legacy items have no `type`).
            const derivedType = item.type
              || (Number(item.points) > 0 ? 'positive'
                : Number(item.points) < 0 ? 'negative'
                : 'neutral');
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
                  {formatPoints(item.points, derivedType)}
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

      {/* Add new evaluation form ─ teacher enters magnitude only;
          sign is derived from the chosen type (positive/negative/neutral). */}
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
        <div className="grid grid-cols-3 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-cairo text-muted-foreground text-center">
              {t('chooseType') || 'اختر النوع'}
            </span>
            <select
              value={evalDraft.type}
              onChange={(e) => setEvalDraft((d) => ({ ...d, type: e.target.value }))}
              className={`text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center ${evalDraft.type ? '' : 'text-muted-foreground/60'}`}
            >
              <option value="" disabled>{t('chooseType') || 'اختر النوع'}</option>
              <option value="positive">{t('positive') || 'إيجابي'} (+)</option>
              <option value="negative">{t('negative') || 'سلبي'} (−)</option>
              <option value="neutral">{t('neutral') || 'محايد'}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-cairo text-muted-foreground text-center">
              {t('chooseColor') || 'اختر اللون'}
            </span>
            <select
              value={evalDraft.color}
              onChange={(e) => setEvalDraft((d) => ({ ...d, color: e.target.value }))}
              className={`text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center ${evalDraft.color ? '' : 'text-muted-foreground/60'}`}
            >
              <option value="" disabled>{t('chooseColor') || 'اختر اللون'}</option>
              {Object.keys(EVAL_COLORS).map((c) => (
                <option key={c} value={c}>{t(`color_${c}`) || c}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[10px] font-cairo text-muted-foreground text-center">
              {t('pointsMagnitude') || (t('points') || 'النقاط')}
            </span>
            <input
              type="number"
              min="0"
              step="1"
              inputMode="numeric"
              value={evalDraft.points}
              onChange={(e) => setEvalDraft((d) => ({ ...d, points: sanitizePoints(e.target.value) }))}
              onKeyDown={(e) => {
                // Block "-" and "+" so the magnitude stays unsigned.
                if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
                if (e.key === 'Enter') handleAddEvaluation();
              }}
              placeholder={t('pointsMagnitude') || (t('points') || 'النقاط')}
              dir={isRTL ? 'rtl' : 'ltr'}
              className="text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/60"
            />
          </label>
        </div>
        <Button
          type="button"
          onClick={handleAddEvaluation}
          disabled={!evalDraft.name.trim() || !evalDraft.type}
          className="w-full bg-violet-600 hover:bg-violet-700 text-white rounded-full py-3 font-cairo text-sm font-bold shadow-sm disabled:opacity-50"
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
                {/* Force the badge sign to match the category list this
                    item lives in, regardless of how the underlying value
                    was stored. */}
                {formatPoints(item.points, isPositive ? 'positive' : 'negative')}
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
          min="0"
          step="1"
          inputMode="numeric"
          value={behaviourDraft.points}
          onChange={(e) => setBehaviourDraft((d) => ({ ...d, points: sanitizePoints(e.target.value) }))}
          onKeyDown={(e) => {
            // Block sign keys — sign is supplied by the +/- buttons below.
            if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
          }}
          placeholder={t('pointsMagnitude') || (t('points') || 'النقاط')}
          dir={isRTL ? 'rtl' : 'ltr'}
          className="w-full text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/60"
        />
        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => handleAddBehaviour('negative')}
            disabled={!behaviourDraft.name.trim()}
            className="rounded-full border-2 border-red-300 dark:border-red-800/60 text-red-600 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/30 dark:hover:text-red-400 focus-visible:text-red-600 font-cairo text-sm font-bold py-2.5 gap-2"
          >
            <ThumbsDown className="h-4 w-4" />
            {t('negative') || 'سلبي'}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleAddBehaviour('positive')}
            disabled={!behaviourDraft.name.trim()}
            className="rounded-full border-2 border-emerald-300 dark:border-emerald-800/60 text-emerald-600 hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-emerald-950/30 dark:hover:text-emerald-400 focus-visible:text-emerald-600 font-cairo text-sm font-bold py-2.5 gap-2"
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
            role="switch"
            aria-checked={skillEnabled}
            className={`relative inline-flex items-center h-6 w-11 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/60 ${skillEnabled ? 'bg-purple-500' : 'bg-muted-foreground/30'}`}
            title={skillEnabled ? (t ? t('enabled') : 'On') : (t ? t('disabled') : 'Off')}
          >
            <span className={`inline-block h-5 w-5 rounded-full bg-white shadow transform transition-transform ${skillEnabled ? 'translate-x-5 rtl:-translate-x-5' : 'translate-x-0.5 rtl:-translate-x-0.5'}`} />
          </button>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[11px] text-muted-foreground font-cairo">{t('currentSkills') || 'المهارات الحالية'}</p>
        <div className="flex flex-wrap gap-1.5">
          {[
            // Registered skill types surfaced from the backend. Their configured
            // weight (وزن الدرجة) is editable in place — a missing/zero value
            // falls back to the default skill weight so the chip matches what is
            // actually awarded when the skill is recorded.
            ...skillTypes.map((s) => {
              const raw = Number(typeof s === 'string' ? NaN : s?.points);
              return {
                key: `reg-${(typeof s === 'string' ? s : s?.id) ?? ''}`,
                id: typeof s === 'string' ? s : s?.id,
                label: typeof s === 'string' ? s : (s?.name_ar || s?.name_en || s?.name || s?.label || ''),
                weight: Number.isFinite(raw) && raw > 0 ? Math.abs(raw) : DEFAULT_SKILL_POINTS,
                isCustom: false,
              };
            }),
            // Custom skills may be plain strings (legacy state) or
            // `{name, points}` objects produced by the new add form.
            ...customSkills.map((s, ci) => {
              const raw = Number(typeof s === 'string' ? NaN : s?.points);
              return {
                key: `cus-${ci}`,
                customIndex: ci,
                label: typeof s === 'string' ? s : (s?.name || s?.label || ''),
                weight: Number.isFinite(raw) && raw > 0 ? Math.abs(raw) : DEFAULT_SKILL_POINTS,
                isCustom: true,
              };
            }),
          ].map((entry) => {
            if (!entry.label) return null;
            const editing = skillEdit?.key === entry.key;
            const canEdit = entry.isCustom
              ? typeof onUpdateCustomSkill === 'function'
              : (typeof onUpdateSkillType === 'function' && !!entry.id);
            return (
              <span
                key={entry.key}
                className="inline-flex items-center gap-1 bg-purple-50 dark:bg-purple-900/20 px-2 py-1 rounded-lg text-[11px] text-purple-700 dark:text-purple-300"
              >
                <Star className="h-2.5 w-2.5" />
                {entry.label}
                {editing ? (
                  <>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      inputMode="numeric"
                      autoFocus
                      value={skillEdit.value}
                      onChange={(e) => setSkillEdit((s) => ({ ...s, value: sanitizePoints(e.target.value) }))}
                      onKeyDown={(e) => {
                        if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
                        if (e.key === 'Enter') commitSkillEdit(entry);
                        if (e.key === 'Escape') cancelSkillEdit();
                      }}
                      className="w-10 text-[11px] text-center bg-card dark:bg-muted rounded border px-1 py-0.5 outline-none focus:border-purple-500 tabular-nums"
                      aria-label={t('scoreWeight') || 'وزن الدرجة'}
                      dir="ltr"
                    />
                    <button
                      type="button"
                      onClick={() => commitSkillEdit(entry)}
                      className="text-green-600 dark:text-green-400 hover:text-green-500"
                      aria-label={t('save') || 'حفظ'}
                    >
                      <Check className="h-2.5 w-2.5" />
                    </button>
                    <button
                      type="button"
                      onClick={cancelSkillEdit}
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={t('cancel') || 'إلغاء'}
                    >
                      <XCircle className="h-2.5 w-2.5" />
                    </button>
                  </>
                ) : (
                  <>
                    <span className="font-bold tabular-nums">+{entry.weight}</span>
                    {canEdit && (
                      <button
                        type="button"
                        onClick={() => startSkillEdit(entry.key, entry.weight)}
                        className="text-purple-500 dark:text-purple-300 hover:text-purple-700 dark:hover:text-purple-100"
                        aria-label={t('editWeight') || 'تعديل وزن الدرجة'}
                      >
                        <Pencil className="h-2.5 w-2.5" />
                      </button>
                    )}
                    {entry.isCustom && (
                      <button
                        type="button"
                        onClick={() => onRemoveCustomSkill?.(entry.customIndex)}
                        className="text-red-600 dark:text-red-400 hover:text-red-500"
                        aria-label={t('delete') || 'حذف'}
                      >
                        <Trash2 className="h-2.5 w-2.5" />
                      </button>
                    )}
                  </>
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

        {/* Add-skill form: name + points magnitude. Points are added to
            the student's score (like positive behaviours) when the
            teacher records the skill in the live class. */}
        <div className="flex items-center gap-1.5 pt-1">
          <input
            value={skillDraft.name}
            onChange={(e) => setSkillDraft((d) => ({ ...d, name: e.target.value }))}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAddSkill(); }}
            className="flex-1 text-[11px] bg-card dark:bg-muted rounded-lg border px-2 py-1.5 outline-none focus:border-purple-500 font-cairo"
            placeholder={t('addNewSkill') || 'إضافة مهارة جديدة'}
            dir={isRTL ? 'rtl' : 'ltr'}
          />
          <input
            type="number"
            min="0"
            step="1"
            inputMode="numeric"
            value={skillDraft.points}
            onChange={(e) => setSkillDraft((d) => ({ ...d, points: sanitizePoints(e.target.value) }))}
            onKeyDown={(e) => {
              if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
              if (e.key === 'Enter') handleAddSkill();
            }}
            className="w-14 text-[11px] text-center bg-card dark:bg-muted rounded-lg border px-2 py-1.5 outline-none focus:border-purple-500 font-cairo tabular-nums"
            placeholder={t('pointsMagnitude') || (t('points') || 'الدرجات')}
            aria-label={t('pointsMagnitude') || (t('points') || 'الدرجات')}
            dir="ltr"
          />
          <button
            type="button"
            onClick={handleAddSkill}
            disabled={!skillDraft.name.trim()}
            className="p-1.5 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 hover:bg-purple-200 dark:hover:bg-purple-900/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label={t('add') || 'إضافة'}
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );

  // ─────────────────────────────────────────────────────────────────
  // Group B renderers (session configuration)
  // ─────────────────────────────────────────────────────────────────
  const renderSessionOptionsTab = () => {
    const sc = sessionConfig || {};
    // Subject selection and the participation toggle were removed from
    // this tab on purpose:
    //   • Subject is auto-inherited from the active session context, so
    //     forcing the teacher to pick it again was redundant.
    //   • Participation is always on by default and the toggle was
    //     causing confusion. The boolean is still kept in parent state
    //     (defaulted to true) so the API payload shape is unchanged.
    //
    // Callers that DON'T have a session context (e.g. "My Classes" → per-subject
    // template) opt-in to a subject picker by passing `showSubjectPicker: true`
    // along with `subjectsList`, `subjectId`, and `onSubjectIdChange`. This keeps
    // the canonical Interactive Class UX untouched while letting non-session
    // entry points reuse the exact same modal.
    return (
      <div className="space-y-5">
        {sc.showSubjectPicker && (
          <div className="space-y-1.5">
            <label className="text-xs font-cairo text-muted-foreground">
              {t('selectSubject') || 'اختر المادة'}
            </label>
            <select
              value={sc.subjectId || ''}
              onChange={(e) => sc.onSubjectIdChange?.(e.target.value)}
              disabled={!!sc.subjectsLoading}
              dir={isRTL ? 'rtl' : 'ltr'}
              className={`w-full text-sm bg-card dark:bg-muted border border-border rounded-full px-4 py-2.5 outline-none focus:border-brand-turquoise font-cairo disabled:opacity-60 disabled:cursor-not-allowed ${sc.subjectId ? '' : 'text-muted-foreground/60'}`}
            >
              {sc.subjectsLoading ? (
                <option value="" disabled>{'جاري التحميل…'}</option>
              ) : (
                <option value="" disabled>
                  {t('selectSubject') || 'اختر المادة'}
                </option>
              )}
              {(sc.subjectsList || []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {!sc.subjectsLoading && (sc.subjectsList || []).length === 0 && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400 font-cairo">
                {'لم يتم تعيين مواد لك بعد — تواصل مع الإدارة'}
              </p>
            )}
            {!sc.subjectsLoading && (sc.subjectsList || []).length > 0 && !sc.subjectId && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400 font-cairo">
                {t('selectSubjectFirst') || 'اختر المادة أولاً'}
              </p>
            )}
          </div>
        )}
        {/* Correct-answer weight — per-session override */}
        {sc.correctAnswerWeight !== undefined && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-hidden="true" strokeWidth={1.5} />
              <span className="text-sm font-medium font-cairo">{t('correctAnswerWeight') || 'وزن الإجابة الصحيحة'}</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="1000"
                step="1"
                inputMode="numeric"
                value={sc.correctAnswerWeight ?? ''}
                onChange={(e) => {
                  const raw = e.target.value;
                  if (raw === '') {
                    sc.onCorrectAnswerWeightChange?.(null);
                    return;
                  }
                  // Reject floats/non-integers — Number.isInteger ensures no
                  // silent truncation matching the backend's strict 422 rule.
                  const n = Number(raw);
                  if (Number.isFinite(n) && Number.isInteger(n) && n >= 1 && n <= 1000) {
                    sc.onCorrectAnswerWeightChange?.(n);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
                }}
                placeholder="5"
                dir="ltr"
                className="w-20 text-sm bg-card dark:bg-muted border border-border rounded-full px-3 py-2 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/50 tabular-nums"
              />
              <div className="flex items-center gap-1.5 flex-wrap">
                {[1, 2, 5, 10].map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => sc.onCorrectAnswerWeightChange?.(v)}
                    className={`px-2.5 py-1 rounded-full text-xs font-bold font-cairo border transition-colors ${
                      sc.correctAnswerWeight === v
                        ? 'bg-emerald-500 text-white border-emerald-500'
                        : 'bg-card dark:bg-muted border-border text-muted-foreground hover:border-emerald-400 hover:text-emerald-600'
                    }`}
                  >
                    {v}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => sc.onCorrectAnswerWeightChange?.(null)}
                  className="px-2.5 py-1 rounded-full text-xs font-cairo border border-dashed border-border text-muted-foreground hover:text-brand-turquoise hover:border-brand-turquoise transition-colors"
                >
                  {t('restoreDefault') || 'استعادة الافتراضي'}
                </button>
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground font-cairo">
              {sc.correctAnswerWeight == null
                ? `يُستخدم الوزن الافتراضي للحصة (${sc.effectiveCorrectAnswerWeight ?? 5} نقاط)`
                : `كل إجابة صحيحة = ${sc.correctAnswerWeight} ${sc.correctAnswerWeight === 1 ? 'نقطة' : 'نقاط'} في هذه الحصة`}
            </p>
          </div>
        )}

        {/* Excellence (التميز) bonus value — per-session override, mirrors the
            correct-answer weight control but bounded 1–5. Awarded on every 5th
            consecutive correct answer. */}
        {sc.streakBonusValue !== undefined && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-500" aria-hidden="true" strokeWidth={1.5} />
              <span className="text-sm font-medium font-cairo">{t('streakBonusValue') || 'قيمة مكافأة التميز'}</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="5"
                step="1"
                inputMode="numeric"
                value={sc.streakBonusValue ?? ''}
                onChange={(e) => {
                  const raw = e.target.value;
                  if (raw === '') {
                    sc.onStreakBonusValueChange?.(null);
                    return;
                  }
                  // Reject floats/non-integers/out-of-range — matches the backend's
                  // strict 422 rule (integer 1–5) so the FE never sends a value the
                  // API will reject.
                  const n = Number(raw);
                  if (Number.isFinite(n) && Number.isInteger(n) && n >= 1 && n <= 5) {
                    sc.onStreakBonusValueChange?.(n);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
                }}
                placeholder="5"
                dir="ltr"
                className="w-20 text-sm bg-card dark:bg-muted border border-border rounded-full px-3 py-2 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/50 tabular-nums"
              />
              <div className="flex items-center gap-1.5 flex-wrap">
                {[1, 2, 3, 5].map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => sc.onStreakBonusValueChange?.(v)}
                    className={`px-2.5 py-1 rounded-full text-xs font-bold font-cairo border transition-colors ${
                      sc.streakBonusValue === v
                        ? 'bg-amber-500 text-white border-amber-500'
                        : 'bg-card dark:bg-muted border-border text-muted-foreground hover:border-amber-400 hover:text-amber-600'
                    }`}
                  >
                    {v}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => sc.onStreakBonusValueChange?.(null)}
                  className="px-2.5 py-1 rounded-full text-xs font-cairo border border-dashed border-border text-muted-foreground hover:text-brand-turquoise hover:border-brand-turquoise transition-colors"
                >
                  {t('restoreDefault') || 'استعادة الافتراضي'}
                </button>
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground font-cairo">
              {sc.streakBonusValue == null
                ? `يُستخدم المقدار الافتراضي (${sc.effectiveStreakBonusValue ?? 5} نقاط) عند كل 5 إجابات صحيحة متتالية`
                : `كل 5 إجابات صحيحة متتالية = مكافأة ${sc.streakBonusValue} ${sc.streakBonusValue === 1 ? 'نقطة' : 'نقاط'} في هذه الحصة`}
            </p>
          </div>
        )}

        {/* Participation type score overrides */}
        {sc.participationScores !== undefined && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Hand className="h-4 w-4 text-brand-turquoise" />
              <span className="text-sm font-medium font-cairo">{t('participationScores') || 'درجة المشاركة'}</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                { id: 'active',     label: t('participationActive')     || 'مشاركة فعالة' },
                { id: 'initiative', label: t('participationInitiative') || 'مبادرة' },
              ].map(({ id, label }) => (
                <label key={id} className="flex flex-col gap-1">
                  <span className="text-[10px] font-cairo text-muted-foreground text-center">{label}</span>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    step="1"
                    inputMode="numeric"
                    value={(sc.participationScores || {})[id] ?? ''}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const parsed = parseInt(raw, 10);
                      const next = { ...(sc.participationScores || {}) };
                      if (raw === '' || raw === '0') {
                        delete next[id];
                      } else if (Number.isFinite(parsed) && parsed >= 1 && parsed <= 100) {
                        next[id] = parsed;
                      }
                      sc.onParticipationScoresChange?.(next);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === '-' || e.key === '+' || e.key === 'e' || e.key === 'E') e.preventDefault();
                    }}
                    placeholder={t('default') || 'افتراضي'}
                    dir="ltr"
                    className="text-sm bg-card dark:bg-muted border border-border rounded-full px-3 py-2 outline-none focus:border-brand-turquoise font-cairo text-center placeholder:text-muted-foreground/50"
                  />
                </label>
              ))}
            </div>
            <p className="text-[10px] text-muted-foreground font-cairo">
              {t('participationScoresHint') || 'اتركه فارغاً لاستخدام الدرجة الافتراضية'}
            </p>
          </div>
        )}
        {/* Homework toggle + view-mode options */}
        <div className="space-y-2">
              <SettingsToggleRow
                icon={<ClipboardCheck className="h-4 w-4" />}
                label={t('homework')}
                enabled={!!sc.homeworkEnabled}
                onToggle={() => sc.onHomeworkEnabledChange?.(!sc.homeworkEnabled)}
                t={t}
              />
              {sc.homeworkEnabled && (
                <div className="ms-2 grid grid-cols-1 gap-2">
                  <button
                    type="button"
                    onClick={() => sc.onHomeworkViewModeChange?.('not_submitted')}
                    className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg border-2 text-xs font-medium font-cairo transition-colors ${
                      sc.homeworkViewMode === 'not_submitted'
                        ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-turquoise'
                        : 'border-border text-muted-foreground'
                    }`}
                  >
                    <span className="flex items-center gap-2"><XCircle className="h-3.5 w-3.5" /> {t('clickStudentNotSubmitted')}</span>
                    {sc.homeworkViewMode === 'not_submitted' && <CheckCircle2 className="h-3.5 w-3.5" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => sc.onHomeworkViewModeChange?.('submitted')}
                    className={`flex items-center justify-between gap-2 px-3 py-2 rounded-lg border-2 text-xs font-medium font-cairo transition-colors ${
                      sc.homeworkViewMode === 'submitted'
                        ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-turquoise'
                        : 'border-border text-muted-foreground'
                    }`}
                  >
                    <span className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5" /> {t('clickStudentSubmitted')}</span>
                    {sc.homeworkViewMode === 'submitted' && <CheckCircle2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
              )}
            </div>

            {/* Recitation toggle + max attempts */}
            <div className="space-y-2">
              <SettingsToggleRow
                icon={<Mic className="h-4 w-4" />}
                label={t('recitation')}
                enabled={!!sc.recitationEnabled}
                onToggle={() => sc.onRecitationEnabledChange?.(!sc.recitationEnabled)}
                t={t}
              />
              {sc.recitationEnabled && (
                <div className="ms-2 flex items-center gap-2">
                  <label className="text-xs text-muted-foreground font-cairo flex-1">{t('maxAttemptsLabel')}</label>
                  <select
                    value={sc.recitationMaxAttempts || 1}
                    onChange={(e) => sc.onRecitationMaxAttemptsChange?.(parseInt(e.target.value) || 1)}
                    className="bg-card dark:bg-muted border border-border rounded-md px-2 py-1 text-xs font-cairo outline-none focus:border-brand-turquoise"
                  >
                    <option value={1}>{t('oneAttempt')}</option>
                    <option value={2}>{t('twoAttempts')}</option>
                    <option value={3}>{t('threeAttempts')}</option>
                  </select>
                </div>
              )}
            </div>
      </div>
    );
  };

  const renderEvaluationPatternsTab = () => {
    const sc = sessionConfig || {};
    const followupColumns = Array.isArray(sc.followupColumns) ? sc.followupColumns : [];
    const updateColumn = (idx, patch) => {
      const updated = [...followupColumns];
      updated[idx] = { ...updated[idx], ...patch };
      sc.onFollowupColumnsChange?.(updated);
    };
    return (
      <div className="space-y-4">
        {/* The subject-required hint that used to live here was removed
            with the subject dropdown — the subject is now inherited
            from the active session context. */}

        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <label className="text-sm font-medium font-cairo flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4 text-brand-turquoise" />
              {t('addOtherItemsQuestion')}
            </label>
            <button
              type="button"
              onClick={() => sc.onShowAddOtherItemsChange?.(!sc.showAddOtherItems)}
              className={`px-3 py-1 rounded-md text-[11px] font-bold font-cairo transition-colors ${
                sc.showAddOtherItems ? 'bg-brand-turquoise text-white' : 'bg-muted text-muted-foreground'
              }`}
            >
              {sc.showAddOtherItems ? (t('yes') || 'نعم') : (t('no') || 'لا')}
            </button>
          </div>

          {sc.showAddOtherItems && (
            <div className="space-y-2">
              {followupColumns.map((col, ci) => (
                <div key={col.id} className="flex items-center gap-2 bg-muted/40 dark:bg-card rounded-lg p-2">
                  <GripVertical className="h-3.5 w-3.5 text-muted-foreground flex-none" />
                  <input
                    value={col.name}
                    onChange={(e) => updateColumn(ci, { name: e.target.value })}
                    className="flex-1 bg-transparent text-sm font-cairo outline-none"
                  />
                  <select
                    value={col.type || 'grade'}
                    onChange={(e) => updateColumn(ci, { type: e.target.value })}
                    className="text-[10px] bg-card dark:bg-muted rounded border px-1 py-0.5 font-cairo"
                  >
                    <option value="grade">{t('gradeType')}</option>
                    <option value="check">{t('checkType')}</option>
                    <option value="text">{t('textType')}</option>
                  </select>
                  <input
                    type="number"
                    value={col.maxGrade}
                    onChange={(e) => updateColumn(ci, { maxGrade: parseInt(e.target.value) || 0 })}
                    className="w-14 text-center text-xs bg-card dark:bg-muted rounded border px-1 py-0.5 font-cairo"
                    min={0}
                    max={100}
                  />
                  <button
                    type="button"
                    onClick={() => sc.onFollowupColumnsChange?.(followupColumns.filter((_, i) => i !== ci))}
                    className="text-red-600 dark:text-red-400 hover:text-red-500"
                    aria-label={t('delete') || 'حذف'}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => sc.onFollowupColumnsChange?.([
                  ...followupColumns,
                  {
                    id: `col_${Date.now()}`,
                    name: t('newColumn'),
                    maxGrade: 10,
                    type: 'grade',
                    group: 'coursework',
                  },
                ])}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-border text-muted-foreground text-xs font-cairo hover:text-brand-turquoise hover:border-brand-turquoise transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                {t('addColumn')}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────
  const dialogTitle = hasSessionConfig
    ? (t('sessionSettings') || 'إعدادات الحصة')
    : (t('sidebarSettings') || 'إعدادات الشريط الجانبي');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md w-full max-h-[90vh] overflow-y-auto p-0 gap-0 border-0 shadow-2xl rounded-2xl backdrop-blur-sm"
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-border">
          <DialogTitle className="font-cairo flex items-center gap-2 text-base font-bold">
            <Settings className="h-5 w-5 text-brand-turquoise" />
            {dialogTitle}
          </DialogTitle>
        </DialogHeader>

        {/* Grouped tab navigation */}
        <div className="px-5 pt-3 border-b border-border space-y-3 pb-1">
          {TAB_GROUPS.map((grp, gi) => (
            <div key={grp.id} className={gi > 0 ? 'pt-2 border-t border-dashed border-border' : ''}>
              {hasSessionConfig && (
                <div className="text-[10px] font-bold font-cairo text-muted-foreground uppercase tracking-wider mb-1.5 text-end">
                  {grp.label}
                </div>
              )}
              <div className="flex items-center">
                {grp.tabs.map((tDef) => {
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
            </div>
          ))}
        </div>

        <div className="p-5">
          {tab === 'evaluation'         && renderEvaluationTab()}
          {tab === 'behaviours'         && renderBehavioursTab()}
          {tab === 'skills'             && renderSkillsTab()}
          {tab === 'sessionOptions'     && hasSessionConfig && renderSessionOptionsTab()}
          {tab === 'evaluationPatterns' && hasSessionConfig && renderEvaluationPatternsTab()}
        </div>

        {/* Sticky Save bar — only on Group B (session config) tabs */}
        {hasSessionConfig && isSessionTab && (
          <div className="sticky bottom-0 bg-background/95 backdrop-blur border-t border-border px-5 py-3">
            <Button
              type="button"
              onClick={() => sessionConfig.onSave?.()}
              disabled={!!sessionConfig.saving || (!!sessionConfig.showSubjectPicker && !sessionConfig.subjectId)}
              className="w-full bg-violet-600 hover:bg-violet-700 text-white font-cairo font-bold"
            >
              {sessionConfig.saving ? (
                <span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> {t('saving')}</span>
              ) : (
                <span className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4" /> {t('savePattern')}</span>
              )}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
