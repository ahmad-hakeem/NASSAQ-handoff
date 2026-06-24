/**
 * CandidatesSidePanel — نافذة اختيار بديل لتغطية حصة شاغرة (غياب معلم).
 * نَسَّق | NASSAQ
 *
 * تستهلك:
 *   GET /api/standby/candidates    — مرشحو جدول الانتظار + الترتيب الذكي
 *   POST /api/substitutions        — إسناد + إشعار
 *   DELETE /api/substitutions/{id} — تراجع
 *
 * الترتيب الذكي:  S = T − (C × 2) + (W × 3)  ·  الأقل = الأفضل
 */
import React, { useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../ui/sheet';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Loader2, User, CheckCircle2, AlertTriangle, Sparkles,
  BellRing, Crown, Layers, TrendingDown, Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { useStandbyCandidates } from '../../hooks/useScheduleCandidates';
import { useCanViewInternalIds } from '../../hooks/useCanViewInternalIds';
import { maskInternalId } from '../../utils/internalId';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import { getApiErrorMessage } from '../../utils/apiError';

const DAY_KEY_MAP = {
  sunday: 'sunday', monday: 'monday', tuesday: 'tuesday',
  wednesday: 'wednesday', thursday: 'thursday', friday: 'friday', saturday: 'saturday',
};

const TAG_META = {
  is_best_match:     { labelKey: 'tagBestMatch',         color: 'bg-emerald-100 text-emerald-700 border-emerald-300', Icon: Crown },
  no_adjacent_classes:{ labelKey: 'tagNoAdjacentClasses', color: 'bg-blue-100 text-blue-700 border-blue-200',         Icon: Layers },
  low_quota:         { labelKey: 'tagLowQuota',          color: 'bg-amber-100 text-amber-700 border-amber-200',       Icon: TrendingDown },
  least_standby:     { labelKey: 'tagLeastStandby',      color: 'bg-violet-100 text-violet-700 border-violet-200',    Icon: Zap },
};

export default function CandidatesSidePanel({
  open,
  onOpenChange,
  slot,
  api,
  onAssigned,
}) {
  const { t, language } = useTranslation();
  const { direction } = useTheme();
  const [assigning, setAssigning] = useState(null);

  const {
    candidates, formula, formula_legend_ar, formula_legend_en, original_session,
    loading, error, refetch,
  } = useStandbyCandidates(api, open ? slot : null, { limit: 3 });

  const handleAssign = async (cand) => {
    if (!slot || !slot.original_session_id) return;
    setAssigning(cand.teacher_id);
    try {
      const params = slot.school_id ? { school_id: slot.school_id } : {};
      const headers = slot.school_id ? { 'X-School-Context': slot.school_id } : undefined;
      const res = await api.post('/substitutions', {
        original_session_id: slot.original_session_id,
        substitute_teacher_id: cand.teacher_id,
        absence_date: slot.absence_date,
      }, { params, headers });
      const doc = res.data?.substitution;
      if (doc && onAssigned) onAssigned(doc, cand);
      onOpenChange(false);
    } catch (err) {
      const msg = getApiErrorMessage(err) || err.message || t('subAssignFailedDefault');
      toast.error(msg);
    } finally {
      setAssigning(null);
    }
  };

  if (!slot) return null;

  const dayLabel = DAY_KEY_MAP[slot.day_of_week] ? t(slot.day_of_week) : slot.day_of_week;
  const className = slot.class_name || original_session?.class_name || '';
  const subjectName = slot.subject_name || original_session?.subject_name || '';
  const absentName = slot.absent_teacher_name || original_session?.teacher_name || '';

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={direction === 'rtl' ? 'left' : 'right'}
        dir={direction}
        className="w-full sm:max-w-md p-0 flex flex-col"
      >
        {/* Header */}
        <SheetHeader className="p-5 bg-gradient-to-l from-[#1C3D74]/10 to-[#2BB5A0]/10 border-b">
          <SheetTitle className="flex items-center gap-2 text-[#1C3D74]">
            <Sparkles className="h-5 w-5" />
            {t('smartCandidatesTitle')}
          </SheetTitle>
          <SheetDescription className="text-slate-700 text-xs leading-relaxed">
            <span className="font-semibold">{className || '—'}</span>
            {' · '} <span>{dayLabel}</span>
            {' · '} <span>{t('periodN', { n: slot.period_number })}</span>
            {subjectName && (
              <> {' · '} <span className="text-emerald-700 font-medium">{subjectName}</span></>
            )}
            {absentName && (
              <div className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-100 text-red-800 text-[10px] border border-red-300">
                <span>{t('absentTeacherColon')}</span>
                <span className="font-bold">{absentName}</span>
              </div>
            )}
          </SheetDescription>
        </SheetHeader>

        {/* Formula banner */}
        <div className="px-4 py-3 bg-slate-900 text-white">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="h-3.5 w-3.5 text-amber-300" />
            <span className="text-[11px] uppercase tracking-wider text-slate-300">{t('smartRankingFormula')}</span>
          </div>
          <p className="font-mono text-base font-bold text-amber-300 text-center tracking-wide">
            {formula || 'S = T − (C × 2) + (W × 3)'} — {t('leastIsBest')}
          </p>
          {(language === 'en' ? (formula_legend_en || t('formulaLegendDefault')) : formula_legend_ar) && (
            <p className="text-[10px] text-slate-400 mt-1.5 text-center leading-relaxed">
              {language === 'en' ? (formula_legend_en || t('formulaLegendDefault')) : formula_legend_ar}
            </p>
          )}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5 bg-slate-50/40">
          {loading && (
            <div className="flex flex-col items-center justify-center py-10 gap-2 text-slate-400">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="text-xs">{t('loadingStandbyRoster')}</span>
            </div>
          )}

          {!loading && error && (
            <div className="flex flex-col items-center justify-center py-10 gap-2 text-red-600">
              <AlertTriangle className="h-6 w-6" />
              <span className="text-xs text-center px-4">{error}</span>
              <Button size="sm" variant="outline" className="text-xs" onClick={refetch}>
                {t('retry')}
              </Button>
            </div>
          )}

          {!loading && !error && candidates.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-slate-500">
              <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center">
                <User className="h-7 w-7 text-slate-300" />
              </div>
              <p className="text-sm font-medium text-slate-600">{t('noTeacherAvailableInSlot')}</p>
              <p className="text-[11px] text-slate-400 text-center px-6">
                {t('tryAnotherSlotHint')}
              </p>
            </div>
          )}

          {!loading && !error && candidates.map((c) => (
            <CandidateCard
              key={c.teacher_id}
              cand={c}
              loading={assigning === c.teacher_id}
              disabled={!!assigning}
              onAssign={() => handleAssign(c)}
            />
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function CandidateCard({ cand, onAssign, loading, disabled }) {
  const { t } = useTranslation();
  const canViewInternalIds = useCanViewInternalIds();
  const isBest = (cand.tags || []).includes('is_best_match');
  const ratio = cand.weekly_quota > 0
    ? Math.min(100, Math.round((cand.weekly_load / cand.weekly_quota) * 100))
    : 0;
  const ratioColor = ratio >= 90 ? 'bg-red-500' : ratio >= 70 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className={`relative border rounded-xl p-3 bg-white shadow-sm hover:shadow-md transition-shadow
                     ${isBest ? 'border-emerald-400 ring-2 ring-emerald-200' : 'border-slate-200'}`}>
      {isBest && (
        <Badge className="absolute -top-2 -end-2 bg-emerald-600 hover:bg-emerald-600 text-white border-0 shadow-md text-[10px] px-2 py-0.5 flex items-center gap-1">
          <Crown className="h-3 w-3" />
          {t('topMatchBadge')}
        </Badge>
      )}

      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-black text-sm shrink-0
                         ${isBest ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-700 border border-slate-200'}`}>
          {cand.rank}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-bold text-sm text-slate-800 truncate">{cand.teacher_name}</h4>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">{maskInternalId(cand.specialty, canViewInternalIds)}</p>

          {/* Tags */}
          <div className="mt-2 flex flex-wrap gap-1">
            {(cand.tags || []).map((tag) => {
              const meta = TAG_META[tag];
              if (!meta) return null;
              const { labelKey, color, Icon } = meta;
              return (
                <span
                  key={tag}
                  className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border ${color}`}
                >
                  <Icon className="h-2.5 w-2.5" />
                  {t(labelKey)}
                </span>
              );
            })}
          </div>

          {/* Stat bar */}
          <div className="mt-2.5 grid grid-cols-3 gap-1.5 text-[10px]">
            <Stat label={t('statTodayLabel')} value={t('todayLoadValue', { n: cand.today_load })} />
            <Stat label={t('statAdjacentLabel')} value={cand.adjacent_count} />
            <Stat label={t('statStandbyLabel')} value={`${cand.standby_used_this_week}`} />
          </div>

          {/* Quota bar */}
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div className={`h-full ${ratioColor} transition-all`} style={{ width: `${ratio}%` }} />
            </div>
            <span className="text-[10px] font-mono text-slate-600 shrink-0 tabular-nums">
              {cand.weekly_load}/{cand.weekly_quota || '—'}
            </span>
          </div>
        </div>

        {/* Score badge */}
        <div className="flex flex-col items-end gap-0.5 shrink-0">
          <span className="text-[10px] text-slate-400">S</span>
          <span className={`text-2xl font-black tabular-nums leading-none ${isBest ? 'text-emerald-600' : 'text-[#1C3D74]'}`}>
            {cand.score}
          </span>
          <span className="text-[9px] text-slate-400 mt-0.5">
            T={cand.score_breakdown?.T} · C={cand.score_breakdown?.C} · W={cand.score_breakdown?.W}
          </span>
        </div>
      </div>

      <Button
        size="sm"
        onClick={onAssign}
        disabled={disabled}
        className={`w-full mt-3 h-9 text-xs font-bold shadow-sm
                    ${isBest
                      ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                      : 'bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] text-white hover:from-[#152d57]'}`}
      >
        {loading
          ? <Loader2 className="h-3.5 w-3.5 animate-spin me-2" />
          : <BellRing className="h-3.5 w-3.5 me-2" />}
        {t('assignAndNotify')}
      </Button>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="bg-slate-50 border border-slate-200 rounded px-1.5 py-1 text-center">
      <div className="text-slate-400 text-[9px]">{label}</div>
      <div className="text-slate-800 font-bold tabular-nums leading-none mt-0.5">{value}</div>
    </div>
  );
}
