/**
 * MobileScheduleAgenda — period-first agenda view of the principal
 * master timetable, used on viewports below `md`.
 *
 * Built specifically to replace the compressed desktop matrix on
 * phones (Task #526). The desktop `MasterMatrix` remains the only
 * renderer on tablets/desktops; this component takes the same data
 * shape (`cellsByTeacher[teacherId][dayKey][periodNumber]`) but
 * arranges it as a vertical list of period sections — one card per
 * scheduled session — so each row carries readable subject, class,
 * and teacher labels at phone widths.
 *
 * Daily mode: shows the selected day's periods as sections.
 * Weekly mode: shows each day as a collapsible section (today
 * expanded by default); the dense matrix is never rendered here.
 *
 * Loading / empty / error states all render at full mobile width.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertOctagon,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Clock,
  Coffee,
  Repeat,
  TriangleAlert,
  UserMinus,
  Users,
} from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { SessionDetailModal } from './grid-theme';

const STATUS_DOT = {
  vacant: 'bg-red-500',
  absent: 'bg-amber-500',
  substituted: 'bg-emerald-500',
  substitute: 'bg-violet-500',
  conflict: 'bg-orange-500',
  normal: 'bg-brand-turquoise',
};

function statusOf(cell, teacherAbsent, isToday, hasConflict) {
  if (!cell) return null;
  if (cell.is_vacant) return hasConflict ? 'conflict' : 'vacant';
  if (cell.is_substituted) return 'substituted';
  if (cell.is_substitute) return 'substitute';
  if (teacherAbsent && isToday) return hasConflict ? 'conflict' : 'absent';
  return 'normal';
}

function StatusBadge({ status, t }) {
  if (!status || status === 'normal') return null;
  const map = {
    vacant: {
      cls: 'bg-red-50 text-red-700 border-red-200',
      Icon: AlertOctagon,
      label: t('vacantLabel'),
    },
    absent: {
      cls: 'bg-amber-50 text-amber-700 border-amber-200',
      Icon: UserMinus,
      label: t('absent'),
    },
    substituted: {
      cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      Icon: Users,
      label: t('substituteShortLabel'),
    },
    substitute: {
      cls: 'bg-violet-50 text-violet-700 border-violet-200',
      Icon: Repeat,
      label: t('substituteShortLabel'),
    },
    conflict: {
      cls: 'bg-orange-50 text-orange-700 border-orange-200',
      Icon: TriangleAlert,
      label: t('vacantLabel'),
    },
  };
  const meta = map[status];
  if (!meta) return null;
  const { cls, Icon, label } = meta;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border ${cls} px-2 py-0.5 text-[10px] font-bold shrink-0`}
    >
      <Icon className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
      {label}
    </span>
  );
}

function PeriodSection({
  period,
  startTime,
  endTime,
  isBreak,
  entries,
  onPickEntry,
  t,
}) {
  const timeLabel = startTime && endTime
    ? `${startTime} – ${endTime}`
    : (startTime || endTime || null);
  return (
    <section
      data-testid={`mobile-period-section-${period}`}
      className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden"
    >
      <header className="flex items-center gap-2 bg-slate-50 border-b border-slate-200 px-3 py-2">
        <span className="inline-flex h-7 min-w-7 items-center justify-center rounded-md bg-brand-navy text-white text-xs font-bold tabular-nums px-1.5">
          {period}
        </span>
        <div className="flex flex-col leading-tight min-w-0 flex-1">
          <span className="text-xs font-semibold text-slate-800">
            {t('periodAbbrev')} {period}
          </span>
          {timeLabel && (
            <span className="text-[10px] text-slate-500 inline-flex items-center gap-1">
              <Clock className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
              <span className="tabular-nums" dir="ltr">{timeLabel}</span>
            </span>
          )}
        </div>
        {isBreak && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 text-[10px] font-bold">
            <Coffee className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
            {t('break')}
          </span>
        )}
      </header>

      {entries.length === 0 ? (
        <p className="px-3 py-3 text-xs text-slate-400 text-start">
          {t('noClassesScheduled')}
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {entries.map(({ teacher, cell, status, period: entryPeriod, dayKey: entryDayKey }) => {
            const subject = cell?.subject_name || '—';
            const klass = cell?.class_name || '—';
            const dotCls = STATUS_DOT[status] || STATUS_DOT.normal;
            return (
              <li key={`${teacher.id}-${period}`}>
                <button
                  type="button"
                  onClick={() => onPickEntry({ teacher, cell, status, period: entryPeriod, dayKey: entryDayKey })}
                  className="w-full text-start flex items-stretch gap-3 px-3 py-2.5 hover:bg-slate-50 active:bg-slate-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise"
                  data-testid={`mobile-session-row-${teacher.id}-${period}`}
                >
                  <span
                    aria-hidden="true"
                    className={`w-1 rounded-full ${dotCls}`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 min-w-0">
                      <p className="text-sm font-bold text-brand-navy truncate flex-1 min-w-0">
                        {subject}
                      </p>
                      <StatusBadge status={status} t={t} />
                    </div>
                    <p className="text-xs text-slate-600 mt-0.5 truncate">
                      {klass}
                    </p>
                    <p className="text-[11px] text-slate-500 mt-0.5 truncate">
                      {teacher.full_name}
                      {status === 'substituted' && cell?.substitute_teacher_name && (
                        <span className="text-emerald-700">
                          {' '}· {t('substituteShortLabel')}: {cell.substitute_teacher_name}
                        </span>
                      )}
                      {status === 'substitute' && cell?.original_teacher_name && (
                        <span className="text-violet-700">
                          {' '}· {cell.original_teacher_name}
                        </span>
                      )}
                    </p>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function DayAgenda({
  dayKey,
  teachers,
  cells,
  periods,
  periodTimes,
  today,
  conflictKeys,
  onPickEntry,
  t,
}) {
  const sections = useMemo(() => {
    return periods.map((p) => {
      const pStr = String(p);
      const entries = [];
      for (const teacher of teachers) {
        const rawCell = cells[teacher.id]?.[dayKey]?.[pStr] || null;
        if (!rawCell) continue;
        const isToday = dayKey === today;
        // Mirror the desktop absence→vacant cascade so the mobile
        // agenda surfaces the same red "شاغرة" badges the desktop
        // matrix shows for an absent teacher's still-filled day.
        const cell =
          teacher.is_absent_today &&
          isToday &&
          !rawCell.is_vacant &&
          !rawCell.is_substituted &&
          !rawCell.is_substitute
            ? { ...rawCell, is_vacant: true }
            : rawCell;
        const hasConflict = conflictKeys?.has(`${teacher.id}|${dayKey}|${p}`);
        const status = statusOf(cell, teacher.is_absent_today, isToday, hasConflict);
        entries.push({ teacher, cell, status, period: p, dayKey });
      }
      const meta = periodTimes?.[pStr] || {};
      return {
        period: p,
        startTime: meta.start_time || meta.start || null,
        endTime: meta.end_time || meta.end || null,
        isBreak: !!meta.is_break,
        entries,
      };
    });
  }, [periods, teachers, cells, dayKey, today, periodTimes, conflictKeys]);

  const hasAny = sections.some((s) => s.entries.length > 0);
  if (!hasAny) {
    return (
      <div
        data-testid="mobile-day-empty"
        className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500"
      >
        {t('noSessionsToday')}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {sections.map((s) => (
        <PeriodSection
          key={s.period}
          period={s.period}
          startTime={s.startTime}
          endTime={s.endTime}
          isBreak={s.isBreak}
          entries={s.entries}
          onPickEntry={onPickEntry}
          t={t}
        />
      ))}
    </div>
  );
}

function MobileScheduleSkeleton() {
  return (
    <LoadingState
      variant="section"
      data-testid="mobile-schedule-skeleton"
      className="py-16"
    />
  );
}

export default function MobileScheduleAgenda({
  teachers,
  cells,
  days,
  periods,
  dayLabelMap,
  viewMode,
  selectedDay,
  today,
  periodTimes,
  unresolvedConflicts,
  canEdit,
  onEditSession,
  onVacantClick,
  loading,
  error,
  onRetry,
  enableCoverage = false,
  schoolId = null,
}) {
  // Build a Set of "teacher|day|period" conflict keys so the agenda
  // cards can render the orange conflict badge in parity with the
  // desktop matrix (`conflictsByCell` in `MasterMatrix`). We accept
  // only conflicts that are bound to a teacher — unassigned items
  // surface inside the Hakim insights chip on the control band.
  const conflictKeys = useMemo(() => {
    const s = new Set();
    if (!Array.isArray(unresolvedConflicts)) return s;
    for (const c of unresolvedConflicts) {
      if (!c?.day_of_week || !c?.period_number || !c?.teacher_id) continue;
      s.add(`${c.teacher_id}|${c.day_of_week}|${c.period_number}`);
    }
    return s;
  }, [unresolvedConflicts]);
  const { t } = useTranslation();
  const [expandedDays, setExpandedDays] = useState(() => {
    const initial = {};
    if (today) initial[today] = true;
    return initial;
  });
  // `today` is commonly undefined while the grid is loading and only
  // arrives once the master-grid response is received. Without this
  // sync the "today expanded" default never fires on the first paint
  // because the initial useState ran with `today == null`. We only
  // auto-expand on the *first* time `today` becomes available so we
  // never override a subsequent user collapse.
  const todayAutoExpandedRef = useRef(false);
  useEffect(() => {
    if (!today || todayAutoExpandedRef.current) return;
    todayAutoExpandedRef.current = true;
    setExpandedDays((prev) => (prev[today] ? prev : { ...prev, [today]: true }));
  }, [today]);
  const [detailSession, setDetailSession] = useState(null);

  const safePeriods = periods && periods.length ? periods : [1, 2, 3, 4, 5, 6, 7];

  const handlePickEntry = ({ teacher, cell, status, period, dayKey }) => {
    // The raw `cell` from `cellsByTeacher` is the API session payload
    // and does NOT carry `period_number` / `day_of_week` (those keys
    // are added by the desktop matrix into its `cellData` wrapper, not
    // onto the cell itself). On mobile we already know the period and
    // day from the agenda iteration — use them as the source of truth
    // so downstream consumers (vacant flow, edit drawer, detail modal)
    // never see `undefined` in the "الحصة N" header.
    const effectivePeriod = period ?? cell?.period_number ?? cell?.slot_number;
    const effectiveDay = dayKey ?? cell?.day_of_week;

    if (status === 'vacant') {
      onVacantClick?.({
        teacher_id: teacher.id,
        teacher_name: teacher.full_name,
        day_of_week: effectiveDay,
        period_number: effectivePeriod,
        is_today: effectiveDay === today,
        teacher_absent: teacher.is_absent_today,
        session: cell,
      });
      return;
    }
    if (canEdit && onEditSession && cell?.session_id) {
      onEditSession({
        session: { ...cell, period_number: effectivePeriod, day_of_week: effectiveDay },
        mode: 'edit',
      });
      return;
    }
    // Published / read-only fallback: surface a detail modal so the
    // operator can still inspect the lesson on a phone.
    // SessionDetailModal reads the period number from `slot_number`
    // (matrix vocabulary) and the day from `day_of_week`; map both
    // from the iteration values so the header renders the correct
    // "حصة N" label rather than leaking the literal "undefined".
    const pStr = String(effectivePeriod ?? '');
    const meta = periodTimes?.[pStr] || {};
    setDetailSession({
      ...cell,
      slot_number: effectivePeriod,
      day_of_week: effectiveDay,
      teacher_name: teacher.full_name,
      teacher_specialty: teacher.subject || '',
      teacher_avatar_url: teacher.avatar_url,
      start_time: meta.start_time || meta.start || null,
      end_time: meta.end_time || meta.end || null,
    });
  };

  if (loading) {
    return (
      <div className="px-4 py-3" data-testid="mobile-schedule-loading">
        <MobileScheduleSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="mx-4 my-3 rounded-xl border border-red-200 bg-red-50 p-4 text-center"
        data-testid="mobile-schedule-error"
      >
        <AlertTriangle
          className="h-6 w-6 text-red-500 mx-auto mb-2"
          strokeWidth={1.5}
          aria-hidden="true"
        />
        <p className="text-sm font-semibold text-red-700">
          {t('errorLoadingSchedule')}
        </p>
        <p className="text-xs text-red-600 mt-1">{error}</p>
        {onRetry && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onRetry}
            className="mt-3 border-red-300 text-red-700 hover:bg-red-100 hover:text-red-700"
          >
            {t('retry')}
          </Button>
        )}
      </div>
    );
  }

  if (!teachers || teachers.length === 0) {
    return (
      <div
        className="mx-4 my-3 rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500"
        data-testid="mobile-schedule-empty-teachers"
      >
        {t('noTeachersRegistered')}
      </div>
    );
  }

  if (viewMode === 'weekly') {
    return (
      <div className="px-4 py-3 flex flex-col gap-3" data-testid="mobile-schedule-weekly">
        {days.map((dayKey) => {
          const expanded = !!expandedDays[dayKey];
          const isToday = dayKey === today;
          return (
            <section
              key={dayKey}
              className="rounded-xl border border-slate-200 bg-slate-50 overflow-hidden"
              data-testid={`mobile-day-section-${dayKey}`}
            >
              <button
                type="button"
                onClick={() =>
                  setExpandedDays((prev) => ({ ...prev, [dayKey]: !prev[dayKey] }))
                }
                aria-expanded={expanded}
                className="w-full flex items-center justify-between gap-2 px-3 py-2.5 bg-white border-b border-slate-200 hover:bg-slate-50"
              >
                <span className="flex items-center gap-2 text-sm font-bold text-brand-navy">
                  {dayLabelMap?.[dayKey] || dayKey}
                  {isToday && (
                    <span className="text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200 px-2 py-0.5">
                      {t('todayBadge')}
                    </span>
                  )}
                </span>
                {expanded ? (
                  <ChevronUp className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                )}
              </button>
              {expanded && (
                <div className="p-3">
                  <DayAgenda
                    dayKey={dayKey}
                    teachers={teachers}
                    cells={cells}
                    periods={safePeriods}
                    periodTimes={periodTimes}
                    today={today}
                    conflictKeys={conflictKeys}
                    onPickEntry={handlePickEntry}
                    t={t}
                  />
                </div>
              )}
            </section>
          );
        })}

        <SessionDetailModal
          open={!!detailSession}
          session={detailSession}
          onClose={() => setDetailSession(null)}
          hideActions
          enableCoverage={enableCoverage}
          schoolId={schoolId}
        />
      </div>
    );
  }

  // Daily view
  const dayKey = selectedDay || today || days[0];
  if (!dayKey) {
    return (
      <div
        className="mx-4 my-3 rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500"
        data-testid="mobile-schedule-no-days"
      >
        {t('noSessionsToday')}
      </div>
    );
  }

  return (
    <div className="px-4 py-3" data-testid="mobile-schedule-daily">
      <DayAgenda
        dayKey={dayKey}
        teachers={teachers}
        cells={cells}
        periods={safePeriods}
        periodTimes={periodTimes}
        today={today}
        conflictKeys={conflictKeys}
        onPickEntry={handlePickEntry}
        t={t}
      />

      <SessionDetailModal
        open={!!detailSession}
        session={detailSession}
        onClose={() => setDetailSession(null)}
        hideActions
      />
    </div>
  );
}
