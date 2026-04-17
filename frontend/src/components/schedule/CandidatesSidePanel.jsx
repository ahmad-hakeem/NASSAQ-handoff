/**
 * CandidatesSidePanel — لوحة جانبية لاختيار معلم لحصة فارغة.
 * نَسَّق | NASSAQ
 */
import React, { useMemo, useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../ui/sheet';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Switch } from '../ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Loader2, User, CheckCircle2, AlertTriangle, Sparkles, Clock } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';
import { useScheduleCandidates, buildSlotId } from '../../hooks/useScheduleCandidates';

const DAY_LABEL_AR = {
  sunday: 'الأحد', monday: 'الإثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس', friday: 'الجمعة', saturday: 'السبت',
};

export default function CandidatesSidePanel({
  open,
  onOpenChange,
  slot,           // { timetable_id, class_id, class_name, day_of_week, period_number, subject_id?, subject_name? }
  api,
  teachers = [], // قائمة معلمي المدرسة لاستخراج خيارات التخصص
  subjectsForClass = [], // [{id, name}] قائمة المواد المسموح بها لهذا الفصل (اختياري)
  onAssigned,    // (session, candidate) => void
  onSkipNext,    // () => void  للانتقال للخانة التالية
}) {
  const { t } = useTranslation();
  const [specialty, setSpecialty] = useState('');
  const [onlyAvailable, setOnlyAvailable] = useState(false);
  const [chosenSubjectId, setChosenSubjectId] = useState('');
  const [assigning, setAssigning] = useState(null);

  // إعادة ضبط الفلاتر عند تغيير الخانة
  // eslint-disable-next-line react-hooks/exhaustive-deps
  React.useEffect(() => {
    if (slot) {
      setChosenSubjectId(slot.subject_id || '');
    }
  }, [slot?.class_id, slot?.day_of_week, slot?.period_number]);

  const effectiveSlot = useMemo(() => {
    if (!slot) return null;
    return { ...slot, subject_id: chosenSubjectId || slot.subject_id || undefined };
  }, [slot, chosenSubjectId]);

  const { candidates, loading, error, refetch } = useScheduleCandidates(
    api,
    open ? effectiveSlot : null,
    { specialty, only_available: onlyAvailable }
  );

  const specialtyOptions = useMemo(() => {
    const set = new Set();
    teachers.forEach(t => {
      const s = (t.specialization || t.subject || '').trim();
      if (s) set.add(s);
    });
    return Array.from(set).sort();
  }, [teachers]);

  const handleAssign = async (cand) => {
    if (!effectiveSlot) return;
    setAssigning(cand.teacher_id);
    try {
      const slotId = buildSlotId(effectiveSlot);
      const res = await api.post(`/schedule/slots/${encodeURIComponent(slotId)}/assign`, {
        teacher_id: cand.teacher_id,
        subject_id: effectiveSlot.subject_id || null,
      });
      const sessionDoc = res.data?.session;
      if (sessionDoc && onAssigned) {
        onAssigned(sessionDoc, cand);
      }
      // الانتقال للخانة التالية تلقائياً
      if (onSkipNext) onSkipNext();
    } catch (err) {
      const msg = err.response?.data?.detail || t('candidates_assign_failed');
      alert(msg);
    } finally {
      setAssigning(null);
    }
  };

  if (!slot) return null;

  const dayLabel = DAY_LABEL_AR[slot.day_of_week] || slot.day_of_week;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        dir="rtl"
        className="w-full sm:max-w-md p-0 flex flex-col"
      >
        {/* Header */}
        <SheetHeader className="p-5 bg-gradient-to-l from-[#1C3D74]/10 to-[#2BB5A0]/10 border-b">
          <SheetTitle className="flex items-center gap-2 text-[#1C3D74]">
            <Sparkles className="h-5 w-5" />
            {t('candidates_panel_title')}
          </SheetTitle>
          <SheetDescription className="text-slate-700 text-xs leading-relaxed">
            <span className="font-semibold">{slot.class_name || ''}</span>
            {' · '} <span>{dayLabel}</span>
            {' · '} <span>{t('candidates_period_label')} {slot.period_number}</span>
            {slot.subject_name && (
              <> {' · '} <span className="text-emerald-700 font-medium">{slot.subject_name}</span></>
            )}
          </SheetDescription>
        </SheetHeader>

        {/* Filters */}
        <div className="p-4 space-y-3 border-b bg-slate-50/60">
          {subjectsForClass.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-600 font-medium shrink-0 w-16">{t('candidates_filter_subject')}</label>
              <Select
                value={chosenSubjectId || ''}
                onValueChange={(v) => setChosenSubjectId(v === '__none__' ? '' : v)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder={t('candidates_filter_subject_pick')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__" className="text-xs">{t('candidates_filter_subject_any')}</SelectItem>
                  {subjectsForClass.map(s => (
                    <SelectItem key={s.id} value={s.id} className="text-xs">
                      {s.name || s.name_ar}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-600 font-medium shrink-0 w-16">{t('candidates_filter_specialty')}</label>
            <Select
              value={specialty || '__all__'}
              onValueChange={(v) => setSpecialty(v === '__all__' ? '' : v)}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder={t('candidates_filter_specialty_all')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__" className="text-xs">{t('candidates_filter_specialty_all')}</SelectItem>
                {specialtyOptions.map(s => (
                  <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-slate-200">
            <span className="text-xs text-slate-700 font-medium">{t('candidates_filter_only_available')}</span>
            <Switch checked={onlyAvailable} onCheckedChange={setOnlyAvailable} />
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {loading && (
            <div className="flex flex-col items-center justify-center py-10 gap-2 text-slate-400">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="text-xs">{t('candidates_loading')}</span>
            </div>
          )}

          {!loading && error && (
            <div className="flex flex-col items-center justify-center py-10 gap-2 text-red-600">
              <AlertTriangle className="h-6 w-6" />
              <span className="text-xs text-center px-4">{error}</span>
              <Button size="sm" variant="outline" className="text-xs" onClick={refetch}>{t('candidates_retry')}</Button>
            </div>
          )}

          {!loading && !error && candidates.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-slate-500">
              <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center">
                <User className="h-7 w-7 text-slate-300" />
              </div>
              <p className="text-sm font-medium text-slate-600">{t('candidates_empty_title')}</p>
              <p className="text-[11px] text-slate-400 text-center px-6">{t('candidates_empty_hint')}</p>
            </div>
          )}

          {!loading && !error && candidates.map((c, idx) => (
            <CandidateCard
              key={c.teacher_id}
              cand={c}
              rank={idx + 1}
              t={t}
              loading={assigning === c.teacher_id}
              disabled={!!assigning}
              onSelect={() => handleAssign(c)}
            />
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function CandidateCard({ cand, rank, onSelect, loading, disabled, t }) {
  const ratio = cand.weekly_target > 0
    ? Math.min(100, Math.round((cand.weekly_load / cand.weekly_target) * 100))
    : 0;
  const ratioColor = ratio >= 90 ? 'bg-red-500' : ratio >= 70 ? 'bg-amber-500' : 'bg-emerald-500';
  const rankColors = ['bg-amber-100 text-amber-700 border-amber-300',
                      'bg-slate-100 text-slate-700 border-slate-300',
                      'bg-orange-100 text-orange-700 border-orange-300'];
  const rankColor = rankColors[rank - 1] || 'bg-slate-50 text-slate-600 border-slate-200';

  return (
    <div className="border border-slate-200 rounded-xl p-3 bg-white shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start gap-3">
        <div className={`w-8 h-8 rounded-lg border-2 ${rankColor} flex items-center justify-center font-black text-sm shrink-0`}>
          {rank}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-bold text-sm text-slate-800 truncate">{cand.teacher_name}</h4>
            {cand.specialty_match && (
              <Badge className="text-[9px] px-1.5 py-0 h-4 bg-emerald-100 text-emerald-700 border-emerald-200">
                <CheckCircle2 className="h-2.5 w-2.5 ml-0.5" /> {t('candidates_badge_specialty_match')}
              </Badge>
            )}
            {cand.available ? (
              <Badge className="text-[9px] px-1.5 py-0 h-4 bg-blue-100 text-blue-700 border-blue-200">{t('candidates_badge_available')}</Badge>
            ) : (
              <Badge className="text-[9px] px-1.5 py-0 h-4 bg-red-100 text-red-700 border-red-200">{t('candidates_badge_busy')}</Badge>
            )}
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">{cand.specialty}</p>

          {/* Nisab bar */}
          <div className="mt-2 flex items-center gap-2">
            <Clock className="h-3 w-3 text-slate-400 shrink-0" />
            <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className={`h-full ${ratioColor} transition-all`} style={{ width: `${ratio}%` }} />
            </div>
            <span className="text-[10px] font-mono text-slate-600 shrink-0 tabular-nums">
              {cand.weekly_load}/{cand.weekly_target}
            </span>
          </div>
          <p className="text-[10px] text-slate-400 mt-1">{cand.reason_ar}</p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="text-[10px] text-slate-400">{t('candidates_score_label')}</span>
          <span className="text-base font-bold text-[#1C3D74] tabular-nums">{Math.round(cand.score)}</span>
        </div>
      </div>
      <Button
        size="sm"
        onClick={onSelect}
        disabled={disabled || !cand.available}
        className="w-full mt-3 h-8 text-xs bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] text-white hover:from-[#152d57]"
      >
        {loading
          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
          : <CheckCircle2 className="h-3.5 w-3.5 ml-1" />}
        {loading ? t('candidates_assign_btn_loading') : (cand.available ? t('candidates_assign_btn') : t('candidates_assign_btn_busy'))}
      </Button>
    </div>
  );
}
