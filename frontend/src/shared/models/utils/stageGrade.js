/**
 * Canonical stage / grade hierarchy helpers.
 *
 * The platform uses three educational stages: primary (1–6), middle (7–9),
 * high (10–12). Stage rows on the backend may carry the `stage` token in
 * several historical shapes (English id, Arabic name, fallback compound
 * "متوسط/ثانوي"); this module normalizes them all to one of the three
 * canonical ids so the UI can cascade stage → grade reliably.
 *
 * The backend revalidates the same pair on write — this module is a UX
 * convenience, never the security boundary.
 */

export const EDUCATION_STAGES = [
  { id: 'primary', name_ar: 'المرحلة الابتدائية', name_en: 'Primary',  gradeMin: 1,  gradeMax: 6  },
  { id: 'middle',  name_ar: 'المرحلة المتوسطة',  name_en: 'Middle',   gradeMin: 7,  gradeMax: 9  },
  { id: 'high',    name_ar: 'المرحلة الثانوية',  name_en: 'High',     gradeMin: 10, gradeMax: 12 },
];

/**
 * The twelve product-approved canonical grade levels — the single source of
 * truth for the "المرحلة الدراسية" dropdown. `label_ar` is the canonical
 * value that gets persisted; the backend (`utils/canonical_grades.py`)
 * mirrors this list and revalidates on write, so a tampered payload cannot
 * persist an off-list grade. Keep the two files in sync.
 */
export const CANONICAL_GRADES = [
  { grade: 1,  stage: 'primary', label_ar: 'الصف الأول الابتدائي',  label_en: 'Grade 1'  },
  { grade: 2,  stage: 'primary', label_ar: 'الصف الثاني الابتدائي', label_en: 'Grade 2'  },
  { grade: 3,  stage: 'primary', label_ar: 'الصف الثالث الابتدائي', label_en: 'Grade 3'  },
  { grade: 4,  stage: 'primary', label_ar: 'الصف الرابع الابتدائي', label_en: 'Grade 4'  },
  { grade: 5,  stage: 'primary', label_ar: 'الصف الخامس الابتدائي', label_en: 'Grade 5'  },
  { grade: 6,  stage: 'primary', label_ar: 'الصف السادس الابتدائي', label_en: 'Grade 6'  },
  { grade: 7,  stage: 'middle',  label_ar: 'الصف الأول المتوسط',    label_en: 'Grade 7'  },
  { grade: 8,  stage: 'middle',  label_ar: 'الصف الثاني المتوسط',   label_en: 'Grade 8'  },
  { grade: 9,  stage: 'middle',  label_ar: 'الصف الثالث المتوسط',   label_en: 'Grade 9'  },
  { grade: 10, stage: 'high',    label_ar: 'الصف الأول الثانوي',    label_en: 'Grade 10' },
  { grade: 11, stage: 'high',    label_ar: 'الصف الثاني الثانوي',   label_en: 'Grade 11' },
  { grade: 12, stage: 'high',    label_ar: 'الصف الثالث الثانوي',   label_en: 'Grade 12' },
];

const _collapseWs = (v) => String(v).trim().replace(/\s+/g, ' ');

const CANONICAL_LABEL_INDEX = new Map(
  CANONICAL_GRADES.map((g) => [_collapseWs(g.label_ar), g]),
);

/**
 * Resolve a canonical-grade label (whitespace-insensitive) to its catalogue
 * entry, or `null`. Strict: arbitrary free text returns `null`.
 */
export function canonicalGradeByLabel(label) {
  if (label == null) return null;
  return CANONICAL_LABEL_INDEX.get(_collapseWs(label)) || null;
}

/** True iff `label` is exactly one of the twelve approved canonical labels. */
export function isCanonicalGradeLabel(label) {
  return canonicalGradeByLabel(label) != null;
}

const STAGE_TOKEN_MAP = {
  primary: 'primary', elementary: 'primary', 'pri': 'primary',
  middle: 'middle', intermediate: 'middle', mid: 'middle',
  high: 'high', secondary: 'high', sec: 'high',
  'الابتدائي': 'primary', 'ابتدائي': 'primary',
  'المرحلة الابتدائية': 'primary',
  'المتوسط': 'middle', 'متوسط': 'middle',
  'المرحلة المتوسطة': 'middle',
  'الثانوي': 'high', 'ثانوي': 'high',
  'المرحلة الثانوية': 'high',
};

const fromGradeNumber = (n) => {
  const num = Number(n);
  if (!Number.isFinite(num) || num < 1) return null;
  if (num <= 6) return 'primary';
  if (num <= 9) return 'middle';
  if (num <= 12) return 'high';
  return null;
};

/**
 * Normalize any stage-ish input (object, string id, Arabic name, grade
 * number, raw grade row) to one of `'primary' | 'middle' | 'high' | null`.
 */
export function normalizeStage(input) {
  if (input == null) return null;

  // Grade row → derive from its own stage / stage_id / grade fields.
  if (typeof input === 'object') {
    const g = input;
    return (
      normalizeStage(g.stage) ||
      normalizeStage(g.stage_id) ||
      normalizeStage(g.education_level) ||
      fromGradeNumber(g.grade) ||
      fromGradeNumber(g.grade_number) ||
      fromGradeNumber(g.order) ||
      null
    );
  }

  if (typeof input === 'number') return fromGradeNumber(input);

  const raw = String(input).trim();
  if (!raw) return null;

  // Numeric strings → grade-number bucket.
  if (/^\d+$/.test(raw)) return fromGradeNumber(raw);

  const lower = raw.toLowerCase();
  if (STAGE_TOKEN_MAP[lower]) return STAGE_TOKEN_MAP[lower];
  if (STAGE_TOKEN_MAP[raw]) return STAGE_TOKEN_MAP[raw];

  // Compound/fallback labels like "متوسط/ثانوي" or "high school".
  if (lower.includes('primary') || lower.includes('elementary') || raw.includes('ابتدائ')) return 'primary';
  if (lower.includes('middle') || lower.includes('intermediate') || raw.includes('متوسط')) return 'middle';
  if (lower.includes('high') || lower.includes('secondary') || raw.includes('ثانوي')) return 'high';

  return null;
}

/** True when `grade` belongs to (or cannot be ruled out of) `stage`. */
export function gradeBelongsToStage(grade, stage) {
  const target = normalizeStage(stage);
  if (!target) return true; // no stage filter → accept
  const gs = normalizeStage(grade);
  if (!gs) return false;     // grade has no derivable stage → exclude
  return gs === target;
}

/** Filter a list of grade rows to those that belong to `stage`. */
export function filterGradesByStage(grades, stage) {
  const list = Array.isArray(grades) ? grades : [];
  const target = normalizeStage(stage);
  if (!target) return [];
  return list.filter((g) => gradeBelongsToStage(g, target));
}

/** Stages that have at least one grade row in `grades` — useful for hiding empty options. */
export function availableStagesFromGrades(grades) {
  const list = Array.isArray(grades) ? grades : [];
  const seen = new Set();
  list.forEach((g) => {
    const s = normalizeStage(g);
    if (s) seen.add(s);
  });
  return EDUCATION_STAGES.filter((s) => seen.has(s.id));
}
