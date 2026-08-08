// Shared built-in lesson element definitions (تعريفات العناصر).
// Single source of truth for the default behaviours and evaluation items
// rendered by BOTH entry points of the إعدادات الحصة dialog:
//   * the live lesson  (SessionTeachPage → SidebarSettingsDialog)
//   * فصولي → class    (TeacherClassDetailPage → SidebarSettingsDialog)
// Keep ids stable — they key stored behaviour_score_overrides in the
// session_settings template and interaction records.

export const BEHAVIOURS = {
  positive: [
    { id: 'respect', label: 'احترام', labelKey: 'behaviourRespect', points: '+2' },
    { id: 'commitment', label: 'التزام', labelKey: 'behaviourCommitment', points: '+2' },
    { id: 'helping_others', label: 'مساعدة الآخرين', labelKey: 'behaviourHelpingOthers', points: '+2' },
  ],
  negative: [
    { id: 'disruption', label: 'إزعاج', labelKey: 'behaviourDisruption', points: '-2' },
    { id: 'non_compliance', label: 'عدم التزام', labelKey: 'behaviourNonCompliance', points: '-2' },
    { id: 'interruption', label: 'مقاطعة', labelKey: 'behaviourInterruption', points: '-1' },
  ],
};

// The four built-in evaluation items. The live sidebar renders dedicated,
// hard-wired buttons for these (bespoke confetti/scoring/recitation
// behavior); the dialog shows them read-only above user-added items.
export const DEFAULT_EVALUATION_ITEMS = [
  { id: 'eval_default_correct',  name: 'إجابة صحيحة',     color: 'emerald', icon: 'CheckCircle2',    points: 1  },
  { id: 'eval_default_wrong',    name: 'إجابة خاطئة',     color: 'red',     icon: 'XCircle',         points: 0  },
  { id: 'eval_default_homework', name: 'لم يسلّم الواجب',  color: 'amber',   icon: 'ClipboardCheck',  points: -1 },
  { id: 'eval_default_recite',   name: 'تسميع',           color: 'purple',  icon: 'Mic',             points: 2  },
];

export const DEFAULT_EVAL_IDS = new Set(DEFAULT_EVALUATION_ITEMS.map((i) => i.id));
