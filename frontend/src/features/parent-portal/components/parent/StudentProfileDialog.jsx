import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme } from '@/shared/contexts/ThemeContext';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import ProfileEditor from './ProfileEditor';
import {
  Edit3,
  Heart,
  Eye,
  Wind,
  ShieldAlert,
  HeartPulse,
  Brain,
  Home,
} from 'lucide-react';

const healthRose = 'bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300';
const HEALTH_LABELS = {
  asthma: { ar: 'ربو', en: 'Asthma', icon: Wind, color: healthRose },
  weak_vision: { ar: 'ضعف بصر', en: 'Weak Vision', icon: Eye, color: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  weak_hearing: { ar: 'ضعف سمع', en: 'Weak Hearing', icon: null, color: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300' },
  allergy: { ar: 'حساسية', en: 'Allergies', icon: ShieldAlert, color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  food_allergy: { ar: 'حساسية غذائية', en: 'Food Allergy', icon: ShieldAlert, color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  nut_allergy: { ar: 'حساسية من المكسرات', en: 'Nut Allergy', icon: ShieldAlert, color: healthRose },
  dust_allergy: { ar: 'حساسية من الغبار', en: 'Dust Allergy', icon: ShieldAlert, color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  seasonal_allergy: { ar: 'حساسية موسمية', en: 'Seasonal Allergy', icon: ShieldAlert, color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  diabetes: { ar: 'سكري', en: 'Diabetes', icon: null, color: 'bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' },
  epilepsy: { ar: 'صرع', en: 'Epilepsy', icon: null, color: healthRose },
  heart: { ar: 'مشاكل القلب', en: 'Heart Issues', icon: Heart, color: 'bg-pink-50 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300' },
};

const BEHAVIOR_LABELS = {
  shyness: { ar: 'خجل', en: 'Shyness' },
  severe_shyness: { ar: 'خجل شديد', en: 'Severe Shyness' },
  hyperactivity: { ar: 'فرط حركة', en: 'Hyperactivity' },
  motor_anxiety: { ar: 'قلق حركي', en: 'Motor Anxiety' },
  concentration_difficulty: { ar: 'صعوبة التركيز', en: 'Difficulty Concentrating' },
  speech_difficulty: { ar: 'صعوبة نطق', en: 'Speech Difficulty' },
  stuttering: { ar: 'تأتأة', en: 'Stuttering' },
  aggression: { ar: 'عدوانية', en: 'Aggression' },
  anger: { ar: 'غضب', en: 'Anger' },
  sleep_disorder: { ar: 'اضطراب نوم', en: 'Sleep Disorder' },
  eating_difficulty: { ar: 'صعوبة أكل', en: 'Eating Difficulty' },
};

const FAMILY_LABELS = {
  both_parents: { ar: 'مع الوالدين', en: 'Both Parents' },
  father_only: { ar: 'مع الأب فقط', en: 'Father Only' },
  mother_only: { ar: 'مع الأم فقط', en: 'Mother Only' },
  other: { ar: 'أخرى', en: 'Other' },
};

const FAMILY_OTHER_LABELS = {
  parents_separation: { ar: 'انفصال الوالدين', en: 'Parents Separated' },
  parent_traveling: { ar: 'سفر أحد الوالدين', en: 'Parent Traveling' },
  foster_family: { ar: 'أسرة بديلة', en: 'Foster Family' },
  orphan: { ar: 'يتيم', en: 'Orphan' },
  second_marriage: { ar: 'زواج ثانٍ', en: 'Second Marriage' },
  family_problems: { ar: 'مشاكل أسرية', en: 'Family Problems' },
};

const StudentProfileDialog = ({ childId, open, onOpenChange }) => {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);

  const fetchProfile = useCallback(async () => {
    if (!childId) return;
    setLoading(true);
    try {
      const res = await api.get(`/parent-portal/child/${childId}/profile`);
      setProfile(res.data);
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, [api, childId]);

  useEffect(() => {
    if (open) {
      setEditing(false);
      fetchProfile();
    } else {
      setEditing(false);
    }
  }, [open, fetchProfile]);

  const studentName = profile?.name || '';
  const headerHint = isRTL
    ? `تساعد هذه المعلومات المدرسة في تقديم الرعاية الأفضل${studentName ? ` لـ${studentName}` : ''}.`
    : `This information helps the school provide better care${studentName ? ` for ${studentName}` : ''}.`;

  const otherHealth = profile?.other_health_details || '';
  const otherBehavior = profile?.other_behavior_details || '';
  const hasHealth = profile?.health_conditions?.length > 0 || Boolean(otherHealth);
  const hasBehavior = profile?.behavioral_aspects?.length > 0 || Boolean(otherBehavior);
  const hasFamily = profile?.family_situation || profile?.family_other_situations?.length > 0;
  const hasAnyContent = hasHealth || hasBehavior || hasFamily;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg w-[95vw] sm:w-full p-0 overflow-hidden max-h-[90vh] flex flex-col"
        dir={isRTL ? 'rtl' : 'ltr'}
        data-testid="student-profile-dialog"
      >
        {editing ? (
          <div className="overflow-y-auto">
            <DialogHeader className="sr-only">
              <DialogTitle>{isRTL ? 'تعديل ملف الطالب' : 'Edit Student Profile'}</DialogTitle>
              <DialogDescription>{headerHint}</DialogDescription>
            </DialogHeader>
            <ProfileEditor
              profile={profile}
              childId={childId}
              onSave={async () => {
                await fetchProfile();
                setEditing(false);
              }}
              onCancel={() => setEditing(false)}
            />
          </div>
        ) : (
          <>
            <DialogHeader className="px-6 pt-6 pb-3 text-center">
              <DialogTitle className="text-lg font-bold font-cairo">
                {isRTL ? 'ملف الطالب' : 'Student Profile'}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
                {headerHint}
              </DialogDescription>
            </DialogHeader>

            <div className="px-6 pb-4 overflow-y-auto flex-1">
              {loading ? (
                <LoadingState variant="section" />
              ) : !profile ? (
                <p className="text-center text-sm text-muted-foreground py-8">
                  {isRTL ? 'لا يمكن عرض ملف الطالب حالياً' : 'Unable to display student profile'}
                </p>
              ) : !hasAnyContent ? (
                <div className="text-center py-8 space-y-2">
                  <Edit3 className="h-10 w-10 mx-auto text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">
                    {isRTL
                      ? 'لم تتم إضافة أي معلومات بعد. اضغط "تعديل" لإضافة التفاصيل.'
                      : 'No information added yet. Click "Edit" to add details.'}
                  </p>
                </div>
              ) : (
                <div className="space-y-5">
                  {hasHealth && (
                    <div>
                      <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
                        <HeartPulse className="w-3.5 h-3.5 text-rose-500" />
                        {isRTL ? 'المشاكل الصحية' : 'Health Conditions'}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {(profile.health_conditions || []).map((c) => {
                          const cfg = HEALTH_LABELS[c];
                          const Icon = cfg?.icon;
                          return (
                            <span
                              key={c}
                              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${cfg?.color || 'bg-muted/40 text-foreground'}`}
                            >
                              {Icon && <Icon className="w-3 h-3" />}
                              {cfg ? (isRTL ? cfg.ar : cfg.en) : c}
                            </span>
                          );
                        })}
                      </div>
                      {otherHealth && (
                        <p
                          className="mt-2 text-xs text-foreground/80 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-900/40 rounded-lg px-3 py-2 whitespace-pre-wrap break-words"
                          dir={isRTL ? 'rtl' : 'ltr'}
                          data-testid="view-other-health"
                        >
                          <span className="font-semibold">
                            {isRTL ? 'أخرى: ' : 'Other: '}
                          </span>
                          {otherHealth}
                        </p>
                      )}
                    </div>
                  )}

                  {hasBehavior && (
                    <div>
                      <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
                        <Brain className="w-3.5 h-3.5 text-purple-500" />
                        {isRTL ? 'الجوانب السلوكية والتعلم' : 'Behavioral & Learning Aspects'}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {(profile.behavioral_aspects || []).map((b) => {
                          const cfg = BEHAVIOR_LABELS[b];
                          return (
                            <span
                              key={b}
                              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 text-xs font-medium"
                            >
                              {cfg ? (isRTL ? cfg.ar : cfg.en) : b}
                            </span>
                          );
                        })}
                      </div>
                      {otherBehavior && (
                        <p
                          className="mt-2 text-xs text-foreground/80 bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-900/40 rounded-lg px-3 py-2 whitespace-pre-wrap break-words"
                          dir={isRTL ? 'rtl' : 'ltr'}
                          data-testid="view-other-behavior"
                        >
                          <span className="font-semibold">
                            {isRTL ? 'أخرى: ' : 'Other: '}
                          </span>
                          {otherBehavior}
                        </p>
                      )}
                    </div>
                  )}

                  {hasFamily && (
                    <div>
                      <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
                        <Home className="w-3.5 h-3.5 text-blue-500" />
                        {isRTL ? 'الوضع العائلي' : 'Family Situation'}
                      </p>
                      {profile.family_situation && (
                        <p className="text-sm text-foreground/80 mb-2">
                          {FAMILY_LABELS[profile.family_situation]
                            ? (isRTL
                                ? FAMILY_LABELS[profile.family_situation].ar
                                : FAMILY_LABELS[profile.family_situation].en)
                            : profile.family_situation}
                        </p>
                      )}
                      {profile.family_other_situations?.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {profile.family_other_situations.map((f) => {
                            const cfg = FAMILY_OTHER_LABELS[f];
                            return (
                              <span
                                key={f}
                                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300 text-xs font-medium"
                              >
                                {cfg ? (isRTL ? cfg.ar : cfg.en) : f}
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-border bg-muted/30 flex justify-end gap-2 shrink-0">
              <Button
                variant="outline"
                onClick={() => onOpenChange?.(false)}
                className="font-cairo"
              >
                {isRTL ? 'إغلاق' : 'Close'}
              </Button>
              <Button
                onClick={() => setEditing(true)}
                disabled={loading || !profile}
                className="font-cairo gap-2"
                data-testid="btn-edit-student-profile"
              >
                <Edit3 className="w-4 h-4" />
                {isRTL ? 'تعديل' : 'Edit'}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default StudentProfileDialog;
