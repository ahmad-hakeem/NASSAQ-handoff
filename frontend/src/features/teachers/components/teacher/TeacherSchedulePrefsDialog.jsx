import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const DAY_KEYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

const DAY_LABELS_AR = {
  sunday: 'الأحد',
  monday: 'الاثنين',
  tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء',
  thursday: 'الخميس',
};

const DAY_LABELS_EN = {
  sunday: 'Sunday',
  monday: 'Monday',
  tuesday: 'Tuesday',
  wednesday: 'Wednesday',
  thursday: 'Thursday',
};

const toggleInArray = (arr, value) => {
  const set = new Set(arr || []);
  if (set.has(value)) set.delete(value);
  else set.add(value);
  return Array.from(set);
};

export const TeacherSchedulePrefsDialog = ({
  open,
  onClose,
  teacher,
  api,
  isRTL,
  subjects = [],
  workingDays = DAY_KEYS,
  periodsPerDay = 7,
  onSaved,
}) => {
  const { t } = useTranslation();
  const dayLabels = isRTL ? DAY_LABELS_AR : DAY_LABELS_EN;

  const [preferredDays, setPreferredDays] = useState([]);
  const [preferredSubjects, setPreferredSubjects] = useState([]);
  const [blockedDays, setBlockedDays] = useState([]);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [maxConsecutive, setMaxConsecutive] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !teacher) return;
    const prefs = teacher.preferences || {};
    const cons = teacher.constraints || {};
    setPreferredDays(Array.isArray(prefs.preferred_days) ? prefs.preferred_days : []);
    setPreferredSubjects(Array.isArray(prefs.preferred_subjects) ? prefs.preferred_subjects : []);
    setBlockedDays(Array.isArray(cons.blocked_days) ? cons.blocked_days : []);
    setBlockedPeriods(Array.isArray(cons.blocked_periods) ? cons.blocked_periods.map(Number).filter(n => !Number.isNaN(n)) : []);
    setMaxConsecutive(
      cons.max_consecutive_periods === undefined || cons.max_consecutive_periods === null
        ? ''
        : String(cons.max_consecutive_periods)
    );
  }, [open, teacher]);

  if (!teacher) return null;

  const days = (workingDays && workingDays.length > 0) ? workingDays : DAY_KEYS;
  const periodNumbers = Array.from({ length: Math.max(1, Number(periodsPerDay) || 7) }, (_, i) => i + 1);

  const handleSave = async () => {
    setSaving(true);
    try {
      const cleanCap = maxConsecutive === '' || maxConsecutive === null
        ? null
        : Math.max(0, parseInt(maxConsecutive, 10) || 0);
      const payload = {
        preferences: {
          preferred_days: preferredDays,
          preferred_subjects: preferredSubjects,
        },
        constraints: {
          blocked_days: blockedDays,
          blocked_periods: blockedPeriods,
          max_consecutive_periods: cleanCap,
        },
      };
      await api.put(`/teachers/${teacher.id}`, payload);
      toast.success(isRTL ? 'تم حفظ تفضيلات الجدول' : 'Schedule preferences saved');
      onSaved?.({ ...teacher, ...payload });
      onClose?.();
    } catch (err) {
      toast.error(getApiErrorMessage(err) || (isRTL ? 'تعذر حفظ التفضيلات' : 'Failed to save preferences'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose?.()}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto" data-testid="teacher-prefs-dialog">
        <DialogHeader>
          <DialogTitle className="font-cairo">
            {isRTL ? 'تفضيلات وقيود الجدول' : 'Schedule Preferences & Constraints'}
          </DialogTitle>
          <DialogDescription>
            {isRTL
              ? `سيستخدمها مولّد الجدول الذكي عند توليد جدول ${teacher.full_name || ''}`
              : `Used by the smart scheduler when generating ${teacher.full_name || ''}'s timetable`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-2">
          <section className="space-y-3">
            <h3 className="font-semibold text-sm text-foreground">
              {isRTL ? 'التفضيلات' : 'Preferences'}
            </h3>

            <div className="space-y-2">
              <Label>{isRTL ? 'الأيام المفضّلة' : 'Preferred days'}</Label>
              <div className="flex flex-wrap gap-2" data-testid="preferred-days">
                {days.map(day => {
                  const active = preferredDays.includes(day);
                  return (
                    <Badge
                      key={`pd-${day}`}
                      variant={active ? 'default' : 'outline'}
                      className="cursor-pointer rounded-lg px-3 py-1"
                      onClick={() => setPreferredDays(toggleInArray(preferredDays, day))}
                      data-testid={`preferred-day-${day}`}
                    >
                      {dayLabels[day] || day}
                    </Badge>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <Label>{isRTL ? 'المواد المفضّلة' : 'Preferred subjects'}</Label>
              {subjects.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  {isRTL ? 'لا توجد مواد متاحة' : 'No subjects available'}
                </p>
              ) : (
                <div className="flex flex-wrap gap-2" data-testid="preferred-subjects">
                  {subjects.map(sub => {
                    const sid = sub.id || sub.subject_id;
                    if (!sid) return null;
                    const label = sub.name_ar || sub.name || sub.name_en || sid;
                    const active = preferredSubjects.includes(sid);
                    return (
                      <Badge
                        key={`ps-${sid}`}
                        variant={active ? 'default' : 'outline'}
                        className="cursor-pointer rounded-lg px-3 py-1"
                        onClick={() => setPreferredSubjects(toggleInArray(preferredSubjects, sid))}
                        data-testid={`preferred-subject-${sid}`}
                      >
                        {label}
                      </Badge>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          <section className="space-y-3 border-t pt-4">
            <h3 className="font-semibold text-sm text-foreground">
              {isRTL ? 'القيود' : 'Constraints'}
            </h3>

            <div className="space-y-2">
              <Label>{isRTL ? 'أيام محجوبة (لن يتم الجدولة فيها)' : 'Blocked days (never schedule)'}</Label>
              <div className="flex flex-wrap gap-2" data-testid="blocked-days">
                {days.map(day => {
                  const active = blockedDays.includes(day);
                  return (
                    <Badge
                      key={`bd-${day}`}
                      variant={active ? 'destructive' : 'outline'}
                      className="cursor-pointer rounded-lg px-3 py-1"
                      onClick={() => setBlockedDays(toggleInArray(blockedDays, day))}
                      data-testid={`blocked-day-${day}`}
                    >
                      {dayLabels[day] || day}
                    </Badge>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <Label>{isRTL ? 'حصص محجوبة' : 'Blocked periods'}</Label>
              <div className="flex flex-wrap gap-2" data-testid="blocked-periods">
                {periodNumbers.map(p => {
                  const active = blockedPeriods.includes(p);
                  return (
                    <Badge
                      key={`bp-${p}`}
                      variant={active ? 'destructive' : 'outline'}
                      className="cursor-pointer rounded-lg px-3 py-1"
                      onClick={() => {
                        setBlockedPeriods(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]);
                      }}
                      data-testid={`blocked-period-${p}`}
                    >
                      {isRTL ? `الحصة ${p}` : `Period ${p}`}
                    </Badge>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2 max-w-xs">
              <Label htmlFor="max-consecutive">
                {isRTL ? 'الحد الأقصى للحصص المتتالية' : 'Max consecutive periods'}
              </Label>
              <Input
                id="max-consecutive"
                type="number"
                min="0"
                placeholder={isRTL ? 'بدون حد' : 'No limit'}
                value={maxConsecutive}
                onChange={(e) => setMaxConsecutive(e.target.value)}
                className="rounded-xl"
                data-testid="max-consecutive-input"
              />
              <p className="text-xs text-muted-foreground">
                {isRTL
                  ? 'اتركه فارغاً لإلغاء الحد. مثال: 3 يعني لا يدرّس المعلم أكثر من 3 حصص متتالية في نفس اليوم.'
                  : 'Leave empty for no cap. e.g. 3 means the teacher will never get more than 3 back-to-back periods on the same day.'}
              </p>
            </div>
          </section>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="rounded-xl" disabled={saving}>
            {t('cancel')}
          </Button>
          <Button
            onClick={handleSave}
            className="bg-brand-navy rounded-xl"
            disabled={saving}
            data-testid="save-teacher-prefs-btn"
          >
            {saving ? (
              <><Loader2 className="h-4 w-4 animate-spin me-2" />{isRTL ? 'جارٍ الحفظ' : 'Saving'}</>
            ) : (
              isRTL ? 'حفظ' : 'Save'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TeacherSchedulePrefsDialog;
