import React, { useEffect, useState } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { Save, X, HeartPulse, Brain, Home } from 'lucide-react';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';

const EMOJI_OPTIONS = ['👦', '👧', '🧒', '👨‍🎓', '👩‍🎓', '🦸‍♂️', '🦸‍♀️', '🧑‍💻', '🎨', '⚽', '🎵', '📚', '🌟', '🦋', '🚀', '🎯'];

const HEALTH_CONDITIONS = [
  { id: 'seasonal_allergy', label_ar: 'حساسية موسمية', label_en: 'Seasonal Allergy' },
  { id: 'nut_allergy', label_ar: 'حساسية من المكسرات', label_en: 'Nut Allergy' },
  { id: 'dust_allergy', label_ar: 'حساسية من الغبار', label_en: 'Dust Allergy' },
  { id: 'asthma', label_ar: 'ربو', label_en: 'Asthma' },
  { id: 'diabetes', label_ar: 'سكري', label_en: 'Diabetes' },
  { id: 'epilepsy', label_ar: 'صرع', label_en: 'Epilepsy' },
  { id: 'weak_vision', label_ar: 'ضعف بصر', label_en: 'Weak Vision' },
  { id: 'weak_hearing', label_ar: 'ضعف سمع', label_en: 'Weak Hearing' },
  { id: 'food_allergy', label_ar: 'حساسية غذائية', label_en: 'Food Allergy' },
];

const BEHAVIORAL_ASPECTS = [
  { id: 'hyperactivity', label_ar: 'فرط حركة', label_en: 'Hyperactivity' },
  { id: 'motor_anxiety', label_ar: 'قلق حركي', label_en: 'Motor Anxiety' },
  { id: 'speech_difficulty', label_ar: 'صعوبة نطق', label_en: 'Speech Difficulty' },
  { id: 'severe_shyness', label_ar: 'خجل شديد', label_en: 'Severe Shyness' },
  { id: 'aggression', label_ar: 'عدوانية', label_en: 'Aggression' },
  { id: 'stuttering', label_ar: 'تأتأة', label_en: 'Stuttering' },
  { id: 'anger', label_ar: 'غضب', label_en: 'Anger' },
  { id: 'sleep_disorder', label_ar: 'اضطراب نوم', label_en: 'Sleep Disorder' },
  { id: 'eating_difficulty', label_ar: 'صعوبة أكل', label_en: 'Eating Difficulty' },
];

const FAMILY_OPTIONS = [
  { id: 'both_parents', label_ar: 'مع الوالدين', label_en: 'Both Parents' },
  { id: 'mother_only', label_ar: 'الأم فقط', label_en: 'Mother Only' },
  { id: 'father_only', label_ar: 'الأب فقط', label_en: 'Father Only' },
  { id: 'other', label_ar: 'أخرى', label_en: 'Other' },
];

const FAMILY_OTHER_SITUATIONS = [
  { id: 'parents_separation', label_ar: 'انفصال الوالدين', label_en: 'Parents Separated' },
  { id: 'parent_traveling', label_ar: 'سفر أحد الوالدين', label_en: 'Parent Traveling' },
  { id: 'foster_family', label_ar: 'أسرة بديلة', label_en: 'Foster Family' },
  { id: 'orphan', label_ar: 'يتيم', label_en: 'Orphan' },
  { id: 'second_marriage', label_ar: 'زواج ثانٍ', label_en: 'Second Marriage' },
  { id: 'family_problems', label_ar: 'مشاكل أسرية', label_en: 'Family Problems' },
];

const Chip = ({ active, activeClass, onClick, children }) => (
  <button
    type="button"
    onClick={onClick}
    className={`px-3 py-2 rounded-full text-xs sm:text-sm font-medium border transition-all whitespace-nowrap ${
      active
        ? activeClass
        : 'bg-white text-foreground/80 border-border hover:border-foreground/30 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-700'
    }`}
  >
    {children}
  </button>
);

const OTHER_TEXT_MAX = 255;

const ProfileEditor = ({ profile, childId, onSave, onCancel }) => {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();

  // Re-seed local form state from the active student's profile whenever
  // the parent switches between siblings (childId change) or the underlying
  // profile object is refetched. This ensures child A's selections cannot
  // visually carry over to child B when the parent flips children.
  const [emoji, setEmoji] = useState(profile?.emoji || '👦');
  const [healthConditions, setHealthConditions] = useState(profile?.health_conditions || []);
  const [behavioralAspects, setBehavioralAspects] = useState(profile?.behavioral_aspects || []);
  const [familySituation, setFamilySituation] = useState(profile?.family_situation || '');
  const [familyOtherSituations, setFamilyOtherSituations] = useState(
    profile?.family_other_situations || []
  );
  // Free-text "Other" complements for the curated chip catalogues. The
  // boolean flags control whether the textarea is revealed (and the
  // "أخرى" chip is highlighted); the text states hold the actual
  // content. Hydrated from the backend's other_*_details strings so
  // re-opening the modal restores the previously typed text.
  const [otherHealthEnabled, setOtherHealthEnabled] = useState(
    Boolean(profile?.other_health_details)
  );
  const [otherHealthText, setOtherHealthText] = useState(profile?.other_health_details || '');
  const [otherBehaviorEnabled, setOtherBehaviorEnabled] = useState(
    Boolean(profile?.other_behavior_details)
  );
  const [otherBehaviorText, setOtherBehaviorText] = useState(
    profile?.other_behavior_details || ''
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEmoji(profile?.emoji || '👦');
    setHealthConditions(profile?.health_conditions || []);
    setBehavioralAspects(profile?.behavioral_aspects || []);
    setFamilySituation(profile?.family_situation || '');
    setFamilyOtherSituations(profile?.family_other_situations || []);
    setOtherHealthEnabled(Boolean(profile?.other_health_details));
    setOtherHealthText(profile?.other_health_details || '');
    setOtherBehaviorEnabled(Boolean(profile?.other_behavior_details));
    setOtherBehaviorText(profile?.other_behavior_details || '');
  }, [childId, profile]);

  const toggleArrayItem = (arr, setArr, item) => {
    setArr((prev) => (prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item]));
  };

  // Graceful clearing: deselecting the "أخرى" pill drops the typed
  // text so it cannot be silently submitted while hidden from view.
  const toggleOtherHealth = () => {
    setOtherHealthEnabled((prev) => {
      const next = !prev;
      if (!next) setOtherHealthText('');
      return next;
    });
  };
  const toggleOtherBehavior = () => {
    setOtherBehaviorEnabled((prev) => {
      const next = !prev;
      if (!next) setOtherBehaviorText('');
      return next;
    });
  };

  const handleSave = async () => {
    if (!childId) return;
    setSaving(true);
    try {
      // Only persist the free-text fields when the pill is enabled,
      // otherwise send an empty string so the backend clears any
      // previously stored value.
      const otherHealthPayload = otherHealthEnabled ? otherHealthText.trim() : '';
      const otherBehaviorPayload = otherBehaviorEnabled ? otherBehaviorText.trim() : '';
      await api.put(`/parent-portal/child/${childId}/profile`, {
        emoji,
        health_conditions: healthConditions,
        behavioral_aspects: behavioralAspects,
        family_situation: familySituation,
        family_other_situations: familyOtherSituations,
        other_health_details: otherHealthPayload,
        other_behavior_details: otherBehaviorPayload,
      });
      toast.success(isRTL ? 'تم حفظ التعديلات بنجاح' : 'Changes saved successfully');
      onSave?.();
    } catch {
      nassaqError(isRTL ? 'حدث خطأ أثناء الحفظ' : 'Error saving changes');
    } finally {
      setSaving(false);
    }
  };

  const studentName = profile?.name || '';
  const headerHint = isRTL
    ? `تساعد هذه المعلومات المدرسة في تقديم الرعاية الأفضل${studentName ? ` لـ${studentName}` : ''}.`
    : `This information helps the school provide better care${studentName ? ` for ${studentName}` : ''}.`;

  return (
    <div
      className="relative flex flex-col -mx-4 -mb-4 sm:mx-0 sm:mb-0 sm:rounded-2xl bg-white dark:bg-gray-900"
      dir={isRTL ? 'rtl' : 'ltr'}
    >
      <div className="sticky top-0 z-10 bg-white/95 dark:bg-gray-900/95 backdrop-blur px-4 pt-4 pb-3 border-b border-border/60 dark:border-gray-800">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 text-center">
            <h2 className="text-base sm:text-lg font-bold font-cairo text-foreground dark:text-gray-100">
              {isRTL ? 'تعديل ملف الطالب' : 'Edit Student Profile'}
            </h2>
            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{headerHint}</p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label={isRTL ? 'إغلاق' : 'Close'}
            className="p-1.5 rounded-full text-muted-foreground hover:bg-muted/60 dark:hover:bg-gray-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="px-4 py-4 space-y-6 max-h-[70vh] overflow-y-auto">
        <section>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base font-bold font-cairo text-foreground dark:text-gray-100">
              {isRTL ? 'الرمز التعبيري' : 'Emoji Avatar'}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {EMOJI_OPTIONS.map((e) => (
              <button
                key={e}
                type="button"
                onClick={() => setEmoji(e)}
                className={`w-10 h-10 rounded-xl text-xl flex items-center justify-center transition-all ${
                  emoji === e
                    ? 'bg-brand-navy/15 dark:bg-brand-navy-dark/40 ring-2 ring-brand-navy scale-105'
                    : 'bg-muted/50 dark:bg-gray-800 hover:bg-muted dark:hover:bg-gray-700'
                }`}
              >
                {e}
              </button>
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-center gap-2 mb-3">
            <HeartPulse className="w-4 h-4 text-rose-500" />
            <h3 className="text-base font-bold font-cairo text-foreground dark:text-gray-100">
              {isRTL ? 'المشاكل الصحية' : 'Health Conditions'}
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {HEALTH_CONDITIONS.map(({ id, label_ar, label_en }) => (
              <Chip
                key={id}
                active={healthConditions.includes(id)}
                activeClass="bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-700"
                onClick={() => toggleArrayItem(healthConditions, setHealthConditions, id)}
              >
                {isRTL ? label_ar : label_en}
              </Chip>
            ))}
            <Chip
              active={otherHealthEnabled}
              activeClass="bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-700"
              onClick={toggleOtherHealth}
            >
              {isRTL ? 'أخرى' : 'Other'}
            </Chip>
          </div>
          {otherHealthEnabled && (
            <div className="mt-3">
              <textarea
                value={otherHealthText}
                onChange={(e) => setOtherHealthText(e.target.value.slice(0, OTHER_TEXT_MAX))}
                maxLength={OTHER_TEXT_MAX}
                rows={2}
                dir={isRTL ? 'rtl' : 'ltr'}
                placeholder={isRTL ? 'يرجى كتابة التفاصيل...' : 'Please describe...'}
                className={`w-full p-2.5 text-sm rounded-xl border border-border bg-white dark:bg-gray-800 dark:border-gray-700 text-foreground focus:outline-none focus:ring-2 focus:ring-rose-300 ${
                  isRTL ? 'text-right' : 'text-left'
                }`}
                data-testid="textarea-other-health"
              />
              <p className={`mt-1 text-[11px] text-muted-foreground ${isRTL ? 'text-left' : 'text-right'}`}>
                {otherHealthText.length}/{OTHER_TEXT_MAX}
              </p>
            </div>
          )}
        </section>

        <section>
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-4 h-4 text-violet-500" />
            <h3 className="text-base font-bold font-cairo text-foreground dark:text-gray-100">
              {isRTL ? 'الجوانب السلوكية والتعلم' : 'Behavioral & Learning Aspects'}
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {BEHAVIORAL_ASPECTS.map(({ id, label_ar, label_en }) => (
              <Chip
                key={id}
                active={behavioralAspects.includes(id)}
                activeClass="bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700"
                onClick={() => toggleArrayItem(behavioralAspects, setBehavioralAspects, id)}
              >
                {isRTL ? label_ar : label_en}
              </Chip>
            ))}
            <Chip
              active={otherBehaviorEnabled}
              activeClass="bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700"
              onClick={toggleOtherBehavior}
            >
              {isRTL ? 'أخرى' : 'Other'}
            </Chip>
          </div>
          {otherBehaviorEnabled && (
            <div className="mt-3">
              <textarea
                value={otherBehaviorText}
                onChange={(e) => setOtherBehaviorText(e.target.value.slice(0, OTHER_TEXT_MAX))}
                maxLength={OTHER_TEXT_MAX}
                rows={2}
                dir={isRTL ? 'rtl' : 'ltr'}
                placeholder={isRTL ? 'يرجى كتابة التفاصيل...' : 'Please describe...'}
                className={`w-full p-2.5 text-sm rounded-xl border border-border bg-white dark:bg-gray-800 dark:border-gray-700 text-foreground focus:outline-none focus:ring-2 focus:ring-amber-300 ${
                  isRTL ? 'text-right' : 'text-left'
                }`}
                data-testid="textarea-other-behavior"
              />
              <p className={`mt-1 text-[11px] text-muted-foreground ${isRTL ? 'text-left' : 'text-right'}`}>
                {otherBehaviorText.length}/{OTHER_TEXT_MAX}
              </p>
            </div>
          )}
        </section>

        <section className="pt-4 border-t border-border/60 dark:border-gray-800">
          <div className="flex items-center gap-2 mb-3">
            <Home className="w-4 h-4 text-sky-500" />
            <h3 className="text-base font-bold font-cairo text-foreground dark:text-gray-100">
              {isRTL ? 'الوضع العائلي' : 'Family Situation'}
            </h3>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            {isRTL ? 'هل يعيش الطفل مع الوالدين؟' : 'Does the child live with both parents?'}
          </p>
          <div className="grid grid-cols-2 gap-2">
            {FAMILY_OPTIONS.map(({ id, label_ar, label_en }) => {
              const active = familySituation === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setFamilySituation(active ? '' : id)}
                  className={`flex items-center gap-2 px-3 py-2.5 rounded-full text-sm transition-all border ${
                    active
                      ? 'bg-brand-navy/5 text-brand-navy border-brand-navy dark:bg-brand-navy-dark/30 dark:text-brand-navy-light dark:border-brand-navy-dark'
                      : 'bg-white text-foreground/80 border-border hover:border-foreground/30 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-700'
                  }`}
                >
                  <span
                    className={`w-3.5 h-3.5 rounded-full border flex-shrink-0 ${
                      active ? 'bg-brand-navy border-brand-navy' : 'border-muted-foreground/40'
                    }`}
                  />
                  <span>{isRTL ? label_ar : label_en}</span>
                </button>
              );
            })}
          </div>

          <p className="text-xs text-muted-foreground mt-4 mb-2">
            {isRTL ? 'حالات أخرى' : 'Other situations'}
          </p>
          <div className="flex flex-wrap gap-2">
            {FAMILY_OTHER_SITUATIONS.map(({ id, label_ar, label_en }) => (
              <Chip
                key={id}
                active={familyOtherSituations.includes(id)}
                activeClass="bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-900/30 dark:text-sky-300 dark:border-sky-700"
                onClick={() =>
                  toggleArrayItem(familyOtherSituations, setFamilyOtherSituations, id)
                }
              >
                {isRTL ? label_ar : label_en}
              </Chip>
            ))}
          </div>
        </section>
      </div>

      <div className="sticky bottom-0 z-10 bg-white/95 dark:bg-gray-900/95 backdrop-blur border-t border-border/60 dark:border-gray-800 px-4 py-3 flex gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2.5 rounded-xl border border-border dark:border-gray-700 text-foreground/80 dark:text-gray-200 text-sm font-medium hover:bg-muted/50 dark:hover:bg-gray-800 transition-colors"
        >
          {isRTL ? 'إلغاء' : 'Cancel'}
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-brand-navy text-white text-sm font-medium hover:bg-brand-navy-dark disabled:opacity-50 transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving
            ? isRTL
              ? 'جارٍ الحفظ...'
              : 'Saving...'
            : isRTL
              ? 'حفظ التغييرات'
              : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};

export default ProfileEditor;
