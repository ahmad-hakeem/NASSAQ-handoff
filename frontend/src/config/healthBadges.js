// Shared teacher-facing health/behavior badge vocabulary for the live-session
// surfaces (SessionTeachPage roster, SessionStartPage roster, and the
// in-session StudentHealthDialog).
//
// The keys mirror the REAL stored vocabulary written by the parent-portal
// student profile editor (students.profile_settings.health_conditions /
// .behavioral_aspects) — see StudentProfileDialog.jsx. Legacy keys used by
// older seed data (vision, social_case, special_needs) are kept so historical
// rows still render. Labels are inline ar/en (same pattern as the parent
// dialog) to avoid drifting locale keys.
//
// Privacy: family-situation vocabulary is intentionally ABSENT from this file
// — teachers never see family data.
import {
  Wind, Eye, Ear, ShieldAlert, Heart, Droplets, Zap, Brain,
  MessageSquareWarning, Utensils, MoonStar, Flame, Activity, Accessibility,
} from 'lucide-react';

export const HEALTH_BADGES = {
  asthma: { icon: Wind, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-500/20', ar: 'ربو', en: 'Asthma' },
  weak_vision: { icon: Eye, color: 'text-cyan-600', bg: 'bg-cyan-100 dark:bg-cyan-500/20', ar: 'ضعف بصر', en: 'Weak vision' },
  weak_hearing: { icon: Ear, color: 'text-indigo-500', bg: 'bg-indigo-100 dark:bg-indigo-500/20', ar: 'ضعف سمع', en: 'Weak hearing' },
  allergy: { icon: ShieldAlert, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-500/20', ar: 'حساسية', en: 'Allergy' },
  food_allergy: { icon: Utensils, color: 'text-amber-600', bg: 'bg-amber-100 dark:bg-amber-500/20', ar: 'حساسية غذائية', en: 'Food allergy' },
  nut_allergy: { icon: ShieldAlert, color: 'text-rose-600', bg: 'bg-rose-100 dark:bg-rose-500/20', ar: 'حساسية من المكسرات', en: 'Nut allergy' },
  dust_allergy: { icon: ShieldAlert, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-500/20', ar: 'حساسية من الغبار', en: 'Dust allergy' },
  seasonal_allergy: { icon: ShieldAlert, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-500/20', ar: 'حساسية موسمية', en: 'Seasonal allergy' },
  diabetes: { icon: Droplets, color: 'text-purple-600', bg: 'bg-purple-100 dark:bg-purple-500/20', ar: 'سكري', en: 'Diabetes' },
  epilepsy: { icon: Zap, color: 'text-rose-600', bg: 'bg-rose-100 dark:bg-rose-500/20', ar: 'صرع', en: 'Epilepsy' },
  heart: { icon: Heart, color: 'text-pink-600', bg: 'bg-pink-100 dark:bg-pink-500/20', ar: 'مشاكل القلب', en: 'Heart issues' },
  // Legacy keys from older seed data — keep rendering them.
  vision: { icon: Eye, color: 'text-cyan-600', bg: 'bg-cyan-100 dark:bg-cyan-500/20', ar: 'ضعف بصر', en: 'Vision impairment' },
  social_case: { icon: ShieldAlert, color: 'text-orange-500', bg: 'bg-orange-100 dark:bg-orange-500/20', ar: 'حالة اجتماعية', en: 'Social case' },
  special_needs: { icon: Accessibility, color: 'text-pink-600', bg: 'bg-pink-100 dark:bg-pink-500/20', ar: 'احتياجات خاصة', en: 'Special needs' },
};

export const BEHAVIOR_BADGES = {
  shyness: { icon: MessageSquareWarning, ar: 'خجل', en: 'Shyness' },
  severe_shyness: { icon: MessageSquareWarning, ar: 'خجل شديد', en: 'Severe shyness' },
  hyperactivity: { icon: Activity, ar: 'فرط حركة', en: 'Hyperactivity' },
  motor_anxiety: { icon: Activity, ar: 'قلق حركي', en: 'Motor anxiety' },
  concentration_difficulty: { icon: Brain, ar: 'صعوبة التركيز', en: 'Difficulty concentrating' },
  speech_difficulty: { icon: MessageSquareWarning, ar: 'صعوبة نطق', en: 'Speech difficulty' },
  stuttering: { icon: MessageSquareWarning, ar: 'تأتأة', en: 'Stuttering' },
  aggression: { icon: Flame, ar: 'عدوانية', en: 'Aggression' },
  anger: { icon: Flame, ar: 'غضب', en: 'Anger' },
  sleep_disorder: { icon: MoonStar, ar: 'اضطراب نوم', en: 'Sleep disorder' },
  eating_difficulty: { icon: Utensils, ar: 'صعوبة أكل', en: 'Eating difficulty' },
};

// Label helper: falls back to the raw key so unknown/new vocabulary still
// shows something readable instead of disappearing.
export const badgeLabel = (map, key, language = 'ar') => {
  const def = map[key];
  if (!def) return key;
  return language === 'en' ? def.en : def.ar;
};
