// Standby (حصص الانتظار) grid-row mapping.
//
// Standby roster entries from GET /standby/roster/me are keyed by the
// timetable's LOGICAL period_number — a contiguous 1..N ordinal over
// teaching periods (the standby engine derives its period universe from
// timetable_sessions.period_number, and the generator numbers sessions
// 1..N with no gaps).
//
// Real-school `time_slots.slot_number`, however, counts break rows too
// (e.g. 1,2,3,[4=break],5,6,7,[8=break],9). The schedule grid filters out
// break rows, so keying grid cells by slot_number makes standby period 4
// point at a row that does not exist and shifts later periods onto wrong
// rows — the "counter says 3, grid shows 1" bug.
//
// The logical period of a rendered grid row is simply its contiguous index
// (idx + 1) over the break-filtered slots — the same ordinal already used
// for the row label ("الحصة الرابعة" = idx 3). We key standby lookups by
// that, with one escape hatch: legacy/manual timetables that numbered
// sessions in slot_number space (periods exceeding the teaching-row count)
// fall back to slot_number keying so their entries still render.

/**
 * True when the roster's period universe can only be explained by
 * slot-number space (a period ordinal larger than the number of teaching
 * rows, but present among the actual slot_numbers).
 * @param {number[]} standbyPeriods - period ordinals of all roster entries
 * @param {Array} timeSlots - break-filtered slot rows shown in the grid
 */
export function standbyUsesSlotNumberSpace(standbyPeriods, timeSlots) {
  if (!standbyPeriods || standbyPeriods.length === 0) return false;
  if (!timeSlots || timeSlots.length === 0) return false;
  const maxP = Math.max(...standbyPeriods);
  if (maxP <= timeSlots.length) return false;
  return timeSlots.some((s) => (s.slot_number || 0) >= maxP);
}

/**
 * Period ordinal a grid row answers to when looking up standby entries.
 * @param {object} slot - the slot row object
 * @param {number} idx - 0-based index of the row among break-filtered slots
 * @param {boolean} useSlotNumberSpace - result of standbyUsesSlotNumberSpace
 */
export function standbyRowPeriod(slot, idx, useSlotNumberSpace) {
  if (useSlotNumberSpace) {
    return slot.slot_number || slot.period_number || idx + 1;
  }
  return idx + 1;
}
