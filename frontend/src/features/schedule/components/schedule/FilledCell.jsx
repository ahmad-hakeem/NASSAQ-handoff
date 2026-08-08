/**
 * FilledCell — خانة المعلم في مصفوفة الجدول الذكية.
 */
import React from 'react';
import { AlertTriangle, Repeat, CheckCheck, MapPin, Check } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import { Button } from '@/shared/components/ui/button';
import { useTranslation, useTheme } from '@/shared/contexts/ThemeContext';
import SessionCell from './grid-theme/SessionCell';

export default function FilledCell({ cell, onClick, onAcknowledgeRelocation, dayKey, compact = true }) {
  const { t } = useTranslation();
  const { direction } = useTheme();
  const relocated = !!cell?.is_relocated && !!cell?.alternative_location;
  const relocationTip = relocated ? `${t('relocatedToLabel')}: ${cell.alternative_location}` : '';
  const canAck = relocated && !!cell?.unavailability_id && !!cell?.viewer_is_recipient;
  const alreadyAcked = !!cell?.acknowledged_by_viewer;

  if (cell?.is_vacant) {
    const baseTitle = t('tapToPickSubstituteHint');
    return (
      <button
        type="button"
        onClick={onClick}
        title={relocated ? `${baseTitle} • ${relocationTip}` : baseTitle}
        className="w-full h-full flex flex-col items-center justify-center text-xs font-bold leading-tight px-1
                   bg-red-50 hover:bg-red-100 text-red-600 border border-red-200 cursor-pointer transition-colors"
      >
        <span className="font-bold">{t('vacantLabel')}</span>
        <span className="text-[9px] opacity-75 truncate max-w-full">{cell.class_name}</span>
      </button>
    );
  }
  if (cell?.is_substituted) {
    const subTitle = t('substituteWithName', { name: cell.substitute_teacher_name || '' });
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-emerald-50/70 text-emerald-700"
        title={relocated ? `${subTitle} • ${relocationTip}` : subTitle}
      >
        <span className="font-semibold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          {t('substituteShortLabel')}: {cell.substitute_teacher_name || '—'}
        </span>
      </div>
    );
  }
  if (cell?.is_substitute) {
    const subTitle = t('substituteForLabelName', { name: cell.original_teacher_name || '' });
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-violet-50/70 text-violet-700 relative"
        title={relocated ? `${subTitle} • ${relocationTip}` : subTitle}
      >
        <Repeat className="absolute top-0.5 end-0.5 h-2.5 w-2.5 opacity-60" />
        <span className="font-semibold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          {cell.subject_name || ''}
        </span>
      </div>
    );
  }
  if (relocated) {
    const cellBody = (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-orange-50 hover:bg-orange-100 text-orange-700 relative cursor-pointer"
        title={`${cell?.subject_name ? cell.subject_name + ' • ' : ''}${relocationTip}`}
        data-testid="cell-relocated"
      >
        <AlertTriangle className="absolute top-0.5 end-0.5 h-2.5 w-2.5 text-orange-500" />
        {alreadyAcked && (
          <CheckCheck className="absolute top-0.5 start-0.5 h-2.5 w-2.5 text-emerald-600" />
        )}
        <span className="font-semibold truncate max-w-full">{cell?.class_name || '—'}</span>
        <span className="text-[9px] font-semibold truncate max-w-full">
          {t('relocatedToLabel')}: {cell.alternative_location}
        </span>
      </div>
    );
    if (!cell?.unavailability_id) {
      return cellBody;
    }
    return (
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className="w-full h-full p-0 m-0 bg-transparent border-0"
            data-testid="cell-relocated-trigger"
          >
            {cellBody}
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="center"
          side="bottom"
          className="w-64 text-start"
          dir={direction}
          data-testid="cell-relocated-popover"
        >
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-orange-700">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-bold font-cairo">{t('classRelocatedLabel')}</span>
            </div>
            <div className="text-xs text-slate-600">
              <span className="font-semibold">{cell?.class_name || '—'}</span>
              {cell?.subject_name ? <span> • {cell.subject_name}</span> : null}
            </div>
            <div className="flex items-start gap-1.5 text-sm bg-orange-50 border border-orange-200 rounded-md px-2 py-1.5">
              <MapPin className="h-3.5 w-3.5 text-orange-600 mt-0.5 shrink-0" />
              <div>
                <div className="text-[11px] text-orange-600">{t('alternativeLocationLabel')}</div>
                <div className="font-semibold text-orange-800">{cell.alternative_location}</div>
              </div>
            </div>
            {canAck ? (
              <Button
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!alreadyAcked && onAcknowledgeRelocation) {
                    onAcknowledgeRelocation(cell);
                  }
                }}
                disabled={alreadyAcked}
                className={`w-full h-8 gap-1.5 ${alreadyAcked
                  ? 'bg-emerald-600 hover:bg-emerald-600 text-white'
                  : 'bg-orange-600 hover:bg-orange-700 text-white'}`}
                data-testid="cell-relocation-ack"
              >
                {alreadyAcked ? (
                  <>
                    <CheckCheck className="h-3.5 w-3.5" />
                    {t('alreadyAcknowledgedLabel')}
                  </>
                ) : (
                  <>
                    <Check className="h-3.5 w-3.5" />
                    {t('markAsReadLabel')}
                  </>
                )}
              </Button>
            ) : (
              <p className="text-[11px] text-slate-500">
                {alreadyAcked
                  ? t('alreadyAcknowledgedNote')
                  : t('relocationInfoOnlyNote')}
              </p>
            )}
          </div>
        </PopoverContent>
      </Popover>
    );
  }
  if (cell?.needs_review) {
    return (
      <div className="relative w-full h-full" data-testid="cell-needs-review" title={t('needsReviewHint')}>
        <span
          aria-hidden="true"
          className="absolute top-0.5 start-0.5 z-10 h-1.5 w-1.5 rounded-full bg-amber-500 ring-1 ring-amber-200"
        />
        <SessionCell
          session={cell}
          dayKey={dayKey}
          onClick={onClick}
          isLocked={!!cell?.is_locked}
          compact={compact}
        />
      </div>
    );
  }
  return (
    <SessionCell
      session={cell}
      dayKey={dayKey}
      onClick={onClick}
      isLocked={!!cell?.is_locked}
      compact={compact}
    />
  );
}
