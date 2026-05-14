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
