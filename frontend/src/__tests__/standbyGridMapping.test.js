import { standbyUsesSlotNumberSpace, standbyRowPeriod } from '../utils/standbyGridMapping';

// Break-filtered rows of a real school whose time_slots count breaks:
// slot_numbers 1,2,3,[4=break],5,6,7,[8=break],9 → 7 teaching rows.
const BREAK_SCHOOL_ROWS = [1, 2, 3, 5, 6, 7, 9].map((n) => ({ id: `s${n}`, slot_number: n }));
// School with contiguous slot numbers (no breaks configured).
const CONTIGUOUS_ROWS = [1, 2, 3, 4, 5, 6].map((n) => ({ id: `s${n}`, slot_number: n }));

describe('standbyUsesSlotNumberSpace', () => {
  it('is false for logical periods within the teaching-row count', () => {
    expect(standbyUsesSlotNumberSpace([4, 5, 6], BREAK_SCHOOL_ROWS)).toBe(false);
    expect(standbyUsesSlotNumberSpace([1, 2], CONTIGUOUS_ROWS)).toBe(false);
  });

  it('is true when a period exceeds the row count but matches a slot_number (legacy slot-space timetable)', () => {
    expect(standbyUsesSlotNumberSpace([9], BREAK_SCHOOL_ROWS)).toBe(true);
  });

  it('is false when a period exceeds the row count and no slot_number reaches it', () => {
    expect(standbyUsesSlotNumberSpace([12], BREAK_SCHOOL_ROWS)).toBe(false);
  });

  it('detects slot-space from the full declared period universe even when assigned periods are small', () => {
    // Legacy slot-space timetable: the roster's declared universe reaches 9
    // (a slot_number), even though this teacher is only assigned period 5.
    // Feeding the full universe (not just assigned entries) flags slot space.
    expect(standbyUsesSlotNumberSpace([1, 2, 3, 5, 6, 7, 9], BREAK_SCHOOL_ROWS)).toBe(true);
  });

  it('handles empty inputs', () => {
    expect(standbyUsesSlotNumberSpace([], BREAK_SCHOOL_ROWS)).toBe(false);
    expect(standbyUsesSlotNumberSpace([3], [])).toBe(false);
  });
});

describe('standbyRowPeriod', () => {
  it('maps rows to contiguous logical ordinals in logical mode', () => {
    // The 4th teaching row (slot_number 5) answers to logical period 4 —
    // this is the bug fix: standby period 4 must land on this row, not
    // disappear into the filtered break slot_number 4.
    const keys = BREAK_SCHOOL_ROWS.map((s, i) => standbyRowPeriod(s, i, false));
    expect(keys).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it('reproduces the pre-fix bug shape: slot_number keys skip 4 and 8', () => {
    const keys = BREAK_SCHOOL_ROWS.map((s, i) => standbyRowPeriod(s, i, true));
    expect(keys).toEqual([1, 2, 3, 5, 6, 7, 9]); // periods 4 & 8 unreachable
  });

  it('logical and slot-number modes agree for contiguous schools', () => {
    CONTIGUOUS_ROWS.forEach((s, i) => {
      expect(standbyRowPeriod(s, i, false)).toBe(standbyRowPeriod(s, i, true));
    });
  });

  it('all assigned periods 4,5,6 resolve to distinct rows after the fix', () => {
    const rowKeys = BREAK_SCHOOL_ROWS.map((s, i) => standbyRowPeriod(s, i, false));
    [4, 5, 6].forEach((p) => expect(rowKeys).toContain(p));
  });
});
