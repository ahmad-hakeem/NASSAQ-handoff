/**
 * BulkSubstitutionPanel — لوحة "تغطية كل حصص المعلم الغائب".
 * نَسَّق | NASSAQ
 *
 * تستهلك:
 *   GET  /api/standby/candidates/bulk   — كل الخانات الشاغرة + المرشحون لكل خانة
 *   POST /api/substitutions/bulk         — إسناد متعدد + إشعار مجمَّع لكل بديل
 *   DELETE /api/substitutions/batch/{id} — تراجع عن كامل الدفعة
 *
 * كل صف يعرض حصة شاغرة مع المرشح الأفضل مُحدَّداً سلفاً، ويُتيح للمدير
 * استبدال البديل من قائمة top-3 لكل خانة. ضغطة واحدة تُسند الكلّ.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '../ui/sheet';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../ui/select';
import {
  Loader2, Sparkles, AlertTriangle, BellRing, Crown, CheckCircle2,
  Layers, UserCheck, XCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { useBulkStandbyCandidates } from '../../hooks/useScheduleCandidates';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';

const RESULT_ERROR_KEY = {
  teacher_busy: 'subErrorTeacherBusy',
  already_substituting: 'subErrorAlreadySubstituting',
  already_assigned: 'subErrorAlreadyAssigned',
  session_not_found: 'subErrorSessionNotFound',
  invalid_teacher: 'subErrorInvalidTeacher',
  invalid_slot: 'subErrorInvalidSlot',
  cross_tenant: 'subErrorCrossTenant',
  race_conflict: 'subErrorRaceConflict',
  missing_fields: 'subErrorMissingFields',
};

export default function BulkSubstitutionPanel({
  open,
  onOpenChange,
  target,
  api,
  onAssignedBatch,
}) {
  const { t, language } = useTranslation();
  const { direction } = useTheme();
  const [selections, setSelections] = useState({});  // { original_session_id: substitute_teacher_id }
  const [submitting, setSubmitting] = useState(false);
  const [perRowResults, setPerRowResults] = useState({}); // { original_session_id: 'success'|errorCode }

  const {
    slots, formula, formula_legend_ar, formula_legend_en,
    absent_teacher_name, day_label_ar, day_of_week,
    loading, error, refetch,
  } = useBulkStandbyCandidates(api, open ? target : null, { limit_per_slot: 3 });

  // Pre-select top candidate (rank 1) for each slot whenever slots refresh.
  useEffect(() => {
    if (!slots || slots.length === 0) {
      setSelections({});
      setPerRowResults({});
      return;
    }
    setSelections((prev) => {
      const next = { ...prev };
      let changed = false;
      slots.forEach((s) => {
        if (!next[s.original_session_id] && s.candidates && s.candidates.length > 0) {
          next[s.original_session_id] = s.candidates[0].teacher_id;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
    setPerRowResults({});
  }, [slots]);

  // Reset state when the panel closes.
  useEffect(() => {
    if (!open) {
      setSelections({});
      setPerRowResults({});
      setSubmitting(false);
    }
  }, [open]);

  const displayName = target?.absent_teacher_name || absent_teacher_name || '—';

  // Validate intra-batch conflicts: same substitute can't cover two slots
  // that share the same period (impossible for one teacher in one period).
  const intraBatchConflicts = useMemo(() => {
    const seen = new Map(); // key: `${tid}__${period}` -> first session_id
    const conflicts = new Set();
    (slots || []).forEach((s) => {
      const tid = selections[s.original_session_id];
      if (!tid) return;
      const key = `${tid}__${s.period_number}`;
      const first = seen.get(key);
      if (first) {
        conflicts.add(first);
        conflicts.add(s.original_session_id);
      } else {
        seen.set(key, s.original_session_id);
      }
    });
    return conflicts;
  }, [slots, selections]);

  const totalSelected = (slots || []).filter(
    (s) => !!selections[s.original_session_id]
  ).length;

  const canSubmit = !submitting && totalSelected > 0 && intraBatchConflicts.size === 0;

  const handleSelect = (sessionId, teacherId) => {
    setSelections((prev) => ({ ...prev, [sessionId]: teacherId }));
    // Clear stale per-row error if user changes the pick.
    setPerRowResults((prev) => {
      if (!prev[sessionId]) return prev;
      const next = { ...prev };
      delete next[sessionId];
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!target?.absent_teacher_id || totalSelected === 0) return;
    if (intraBatchConflicts.size > 0) {
      toast.error(t('intraBatchConflictToast'));
      return;
    }
    setSubmitting(true);
    try {
      const items = (slots || [])
        .filter((s) => !!selections[s.original_session_id])
        .map((s) => ({
          original_session_id: s.original_session_id,
          substitute_teacher_id: selections[s.original_session_id],
        }));

      const params = target.school_id ? { school_id: target.school_id } : {};
      const headers = target.school_id ? { 'X-School-Context': target.school_id } : undefined;

      const res = await api.post('/substitutions/bulk', {
        items,
        absence_date: target.absence_date,
      }, { params, headers });

      const data = res.data || {};
      const succeeded = data.succeeded || 0;
      const failed = data.failed || 0;
      const rowMap = {};
      (data.results || []).forEach((r) => {
        if (!r.original_session_id) return;
        rowMap[r.original_session_id] = r.success ? 'success' : (r.error || 'failed');
      });
      setPerRowResults(rowMap);

      if (succeeded > 0 && failed === 0) {
        if (onAssignedBatch) onAssignedBatch(data);
        onOpenChange(false);
      } else if (succeeded > 0 && failed > 0) {
        toast.warning(t('batchPartialResultTitle', { ok: succeeded, fail: failed }), {
          description: t('batchPartialResultDesc'),
        });
        if (onAssignedBatch) onAssignedBatch(data);
      } else {
        toast.error(t('batchAllFailedDesc'));
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail && typeof detail === 'object' && Array.isArray(detail.results)) {
        const rowMap = {};
        detail.results.forEach((r) => {
          if (!r.original_session_id) return;
          rowMap[r.original_session_id] = r.success ? 'success' : (r.error || 'failed');
        });
        setPerRowResults(rowMap);
        toast.error(t('batchTotalFailureToast'));
      } else {
        const msg = (typeof detail === 'string' && detail) || err.message || t('batchSubmitFailedDefault');
        toast.error(msg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!target) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={direction === 'rtl' ? 'left' : 'right'}
        dir={direction}
        className="w-full sm:max-w-2xl p-0 flex flex-col"
      >
        {/* ── Header ───────────────────────────────────────────────── */}
        <SheetHeader className="p-5 bg-gradient-to-l from-[#1C3D74]/10 to-[#2BB5A0]/10 border-b">
          <SheetTitle className="flex items-center gap-2 text-[#1C3D74]">
            <Layers className="h-5 w-5" />
            {t('bulkCoverTitle')}
          </SheetTitle>
          <SheetDescription className="text-slate-700 text-xs leading-relaxed">
            <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-100 text-red-800 text-[10px] border border-red-300">
              <span>{t('absentTeacherColon')}</span>
              <span className="font-bold">{displayName}</span>
            </div>
            {(day_of_week || day_label_ar) && (
              <span className="ms-2 text-slate-600">• {day_of_week ? t(day_of_week) : day_label_ar}</span>
            )}
            {target.absence_date && (
              <span className="ms-2 text-slate-500">• {target.absence_date}</span>
            )}
          </SheetDescription>
        </SheetHeader>

        {/* ── Formula banner ───────────────────────────────────────── */}
        <div className="px-4 py-2 bg-slate-900 text-white">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-amber-300 shrink-0" />
            <p className="font-mono text-xs font-bold text-amber-300 tracking-wide truncate">
              {formula || 'S = T − (C × 2) + (W × 3)'} — {t('leastIsBest')}
            </p>
          </div>
          {(language === 'en' ? (formula_legend_en || t('formulaLegendDefault')) : formula_legend_ar) && (
            <p className="text-[10px] text-slate-400 mt-1 leading-relaxed">
              {language === 'en' ? (formula_legend_en || t('formulaLegendDefault')) : formula_legend_ar}
            </p>
          )}
        </div>

        {/* ── Body ─────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5 bg-slate-50/40">
          {loading && (
            <div className="flex flex-col items-center justify-center py-10 gap-2 text-slate-400">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="text-xs">{t('loadingVacantSlotsAndCandidates')}</span>
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

          {!loading && !error && slots.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-slate-500">
              <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center">
                <CheckCircle2 className="h-7 w-7 text-emerald-600" />
              </div>
              <p className="text-sm font-medium text-slate-700">
                {t('noVacantSlotsToday')}
              </p>
              <p className="text-[11px] text-slate-400 text-center px-6">
                {t('noSlotsForTeacherTodayHint')}
              </p>
            </div>
          )}

          {!loading && !error && slots.map((slot) => (
            <SlotRow
              key={slot.original_session_id}
              slot={slot}
              selectedTeacherId={selections[slot.original_session_id] || ''}
              onSelect={(tid) => handleSelect(slot.original_session_id, tid)}
              conflictWithinBatch={intraBatchConflicts.has(slot.original_session_id)}
              result={perRowResults[slot.original_session_id]}
              disabled={submitting}
              t={t}
            />
          ))}
        </div>

        {/* ── Footer ───────────────────────────────────────────────── */}
        {!loading && !error && slots.length > 0 && (
          <div className="border-t bg-white p-4 flex items-center justify-between gap-3">
            <div className="text-[11px] text-slate-600">
              <span className="font-bold text-slate-900">{totalSelected}</span>
              <span className="mx-1">/</span>
              <span>{slots.length}</span>
              <span className="ms-1">{t('slotsSelectedSuffix')}</span>
              {intraBatchConflicts.size > 0 && (
                <span className="block text-red-600 mt-1">
                  ⚠ {t('sameSubstituteSamePeriodWarn')}
                </span>
              )}
            </div>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] hover:from-[#152d57] text-white font-bold h-10 px-5 shadow-md"
            >
              {submitting
                ? <Loader2 className="h-4 w-4 animate-spin me-2" />
                : <BellRing className="h-4 w-4 me-2" />}
              {t('assignAllAndNotify')}
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

// ─── Slot row ───────────────────────────────────────────────────────────────
function SlotRow({ slot, selectedTeacherId, onSelect, conflictWithinBatch, result, disabled, t }) {
  const candidates = slot.candidates || [];
  const noCandidates = candidates.length === 0;
  const errorKey = result && result !== 'success' ? RESULT_ERROR_KEY[result] : null;
  const errorMsg = result && result !== 'success' ? (errorKey ? t(errorKey) : result) : null;
  const isSuccess = result === 'success';

  const borderClass = isSuccess
    ? 'border-emerald-400 bg-emerald-50'
    : (errorMsg || conflictWithinBatch)
      ? 'border-red-300 bg-red-50/40'
      : 'border-slate-200 bg-white';

  const selected = candidates.find((c) => c.teacher_id === selectedTeacherId);
  const selectedIsBest = selected && (selected.tags || []).includes('is_best_match');

  return (
    <div className={`border rounded-xl p-3 shadow-sm ${borderClass}`}>
      <div className="flex items-start gap-3">
        {/* Period badge */}
        <div className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-200 flex flex-col items-center justify-center shrink-0">
          <span className="text-[9px] text-slate-500 leading-none">{t('periodAbbrev')}</span>
          <span className="text-base font-black text-slate-800 leading-none mt-0.5">
            {slot.period_number}
          </span>
        </div>

        {/* Slot meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-sm text-slate-800 truncate">
              {slot.class_name || '—'}
            </span>
            {slot.subject_name && (
              <span className="text-[11px] text-emerald-700 font-medium truncate">
                · {slot.subject_name}
              </span>
            )}
          </div>

          {/* Candidate selector */}
          <div className="mt-2">
            {noCandidates ? (
              <div className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded bg-amber-100 text-amber-800 border border-amber-300">
                <AlertTriangle className="h-3 w-3" />
                {t('noTeacherAvailableInSlot')}
              </div>
            ) : (
              <Select
                value={selectedTeacherId}
                onValueChange={onSelect}
                disabled={disabled || isSuccess}
              >
                <SelectTrigger className="w-full h-9 text-xs">
                  <SelectValue placeholder={t('chooseSubstitutePlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {candidates.map((c) => {
                    const tags = c.tags || [];
                    const isBest = tags.includes('is_best_match');
                    return (
                      <SelectItem key={c.teacher_id} value={c.teacher_id}>
                        <span className="flex items-center gap-2">
                          {isBest && <Crown className="h-3 w-3 text-emerald-600" />}
                          <span className="font-semibold">{c.teacher_name}</span>
                          <span className="text-[10px] text-slate-500">
                            S={c.score} · T={c.score_breakdown?.T} · C={c.score_breakdown?.C} · W={c.score_breakdown?.W}
                          </span>
                        </span>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Selected candidate quick badges */}
          {selected && (
            <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
              {selectedIsBest && (
                <Badge className="bg-emerald-100 text-emerald-700 border border-emerald-300 text-[10px]">
                  <Crown className="h-2.5 w-2.5 me-0.5" />
                  {t('topRankedCandidates')}
                </Badge>
              )}
              <span className="text-[10px] text-slate-500">
                {t('candidateScoreSummary', { n: selected.today_load, m: selected.adjacent_count, w: selected.standby_used_this_week })}
              </span>
            </div>
          )}

          {/* Per-row result */}
          {isSuccess && (
            <div className="mt-2 inline-flex items-center gap-1 text-[11px] text-emerald-700 font-semibold">
              <UserCheck className="h-3 w-3" />
              {t('substituteAssignedSuccess')}
            </div>
          )}
          {errorMsg && (
            <div className="mt-2 inline-flex items-center gap-1 text-[11px] text-red-700 font-semibold">
              <XCircle className="h-3 w-3" />
              {errorMsg}
            </div>
          )}
          {conflictWithinBatch && !errorMsg && (
            <div className="mt-2 inline-flex items-center gap-1 text-[11px] text-red-700 font-semibold">
              <AlertTriangle className="h-3 w-3" />
              {t('sameSubstituteAnotherSlot')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
