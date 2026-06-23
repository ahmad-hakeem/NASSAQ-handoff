/**
 * Parent schedule grid normalization.
 *
 * The parent timetable endpoint (`/parent-portal/child/{id}/schedule`) returns
 * a canonical `periods` array plus a `schedule` map of day -> entries. Every
 * entry's `period` is the canonical teaching index (1..N). This builds a
 * lookup so grids place each entry on its TRUE period row instead of packing
 * by array index.
 *
 * Backward compatible: if `periods` is absent (e.g. an older cached response),
 * the period list is derived from the distinct `entry.period` values across all
 * days — still placed by true period, never by array index.
 *
 * @param {object} schedule - the raw response: { schedule, days, periods }
 * @returns {{ periods: Array<{period:number,label:string}>, lookup: Object }}
 *          lookup[day][period] => entry
 */
export function buildScheduleGrid(schedule) {
  const scheduleData = (schedule && schedule.schedule) || {};
  const lookup = {};
  const seen = new Set();

  Object.keys(scheduleData).forEach((day) => {
    const cells = {};
    (scheduleData[day] || []).forEach((entry) => {
      const period = entry && entry.period;
      if (period == null) return;
      seen.add(period);
      if (cells[period] === undefined) cells[period] = entry;
    });
    lookup[day] = cells;
  });

  let periods =
    schedule && Array.isArray(schedule.periods) ? schedule.periods : [];

  if (!periods.length) {
    periods = Array.from(seen)
      .sort((a, b) => a - b)
      .map((period) => ({ period, label: String(period) }));
  }

  return { periods, lookup };
}

/** Return the entry for a given day/period, or undefined when empty. */
export function getScheduleCell(lookup, day, period) {
  return (lookup[day] || {})[period];
}
