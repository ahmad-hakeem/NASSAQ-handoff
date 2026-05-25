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
  UserMinus,
  Users,
} from 'lucide-react';
import { Button } from '../ui/button';
import { useTranslation } from '../../contexts/ThemeContext';
import { SessionDetailModal } from './grid-theme';

const STATUS_DOT = {
  vacant: 'bg-red-500',
  absent: 'bg-amber-500',
  substituted: 'bg-emerald-500',
  substitute: 'bg-violet-500',
  normal: 'bg-brand-turquoise',
};

function statusOf(cell, teacherAbsent, isToday) {
  if (!cell) return null;
  if (cell.is_vacant) return 'vacant';
  if (cell.is_substituted) return 'substituted';
  if (cell.is_substitute) return 'substitute';
  if (teacherAbsent && isToday) return 'absent';
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
  periodTime,
  isBreak,
  entries,
  onPickEntry,
  t,
}) {
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
          {periodTime && (
            <span className="text-[10px] text-slate-500 inline-flex items-center gap-1">
              <Clock className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
              <span className="tabular-nums">{periodTime}</span>
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
          {entries.map(({ teacher, cell, status }) => {
            const subject = cell?.subject_name || '—';
            const klass = cell?.class_name || '—';
            const dotCls = STATUS_DOT[status] || STATUS_DOT.normal;
            return (
              <li key={`${teacher.id}-${period}`}>
                <button
                  type="button"
                  onClick={() => onPickEntry({ teacher, cell, status })}
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
        const status = statusOf(cell, teacher.is_absent_today, isToday);
        entries.push({ teacher, cell, status });
      }
      const meta = periodTimes?.[pStr] || {};
      return {
        period: p,
        periodTime: meta.start_time || meta.start || null,
        isBreak: !!meta.is_break,
        entries,
      };
    });
  }, [periods, teachers, cells, dayKey, today, periodTimes]);

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
          periodTime={s.periodTime}
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
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-label={t('loading')}
      data-testid="mobile-schedule-skeleton"
      className="flex flex-col gap-2.5"
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-slate-200 bg-white overflow-hidden"
        >
          <div className="flex items-center gap-2 bg-slate-50 border-b border-slate-200 px-3 py-2">
            <div className="h-7 w-7 rounded-md bg-slate-200 animate-pulse" />
            <div className="flex-1 space-y-1">
              <div className="h-3 w-20 bg-slate-200 rounded animate-pulse" />
              <div className="h-2 w-14 bg-slate-100 rounded animate-pulse" />
            </div>
          </div>
          <div className="p-3 space-y-2">
            <div className="h-3 w-3/4 bg-slate-100 rounded animate-pulse" />
            <div className="h-2 w-1/2 bg-slate-100 rounded animate-pulse" />
          </div>
        </div>
      ))}
    </div>
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
  canEdit,
  onEditSession,
  onVacantClick,
  loading,
  error,
  onRetry,
}) {
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

  const handlePickEntry = ({ teacher, cell, status }) => {
    if (status === 'vacant') {
      onVacantClick?.({
        teacher_id: teacher.id,
        teacher_name: teacher.full_name,
        day_of_week: cell?.day_of_week,
        period_number: cell?.period_number,
        is_today: cell?.day_of_week === today,
        teacher_absent: teacher.is_absent_today,
        session: cell,
      });
      return;
    }
    if (canEdit && onEditSession && cell?.session_id) {
      onEditSession({ session: cell, mode: 'edit' });
      return;
    }
    // Published / read-only fallback: surface a detail modal so the
    // operator can still inspect the lesson on a phone.
    // SessionDetailModal reads the period number from `slot_number`
    // (matrix vocabulary), but the master-grid cell uses
    // `period_number`. Map it here so the modal header renders the
    // correct "حصة N" label on mobile parity with the desktop matrix.
    const pStr = String(cell?.period_number ?? '');
    const meta = periodTimes?.[pStr] || {};
    setDetailSession({
      ...cell,
      slot_number: cell?.period_number,
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
