import {
  mergeFollowupData,
  mergeFollowupAbsences,
  isFollowupNoOpFlush,
  runFollowupClose,
} from '../followupPersistence';

// These tests exercise the real follow-up sheet (كشف المتابعة) persistence
// rules used by SessionTeachPage for both School Teacher and Independent Teacher
// (the logic is shared/tenant-agnostic — the route enforces ownership).

describe('mergeFollowupData — stale-reload guard on reopen / poll', () => {
  test('a dirty (not-yet-saved) cell is NOT clobbered by stale server data', () => {
    // Teacher edited s1/c1 to 7 locally; server still has the old 3.
    const dirty = new Set(['s1:c1']);
    const merged = mergeFollowupData(
      { s1: { c1: 3 } },               // stale server
      { s1: { c1: 7 } },               // local edit
      dirty,
    );
    expect(merged.s1.c1).toBe(7); // close → reopen shows the latest edit
  });

  test('a non-dirty cell DOES sync to the fresh server value', () => {
    const merged = mergeFollowupData(
      { s1: { c1: 5 } },               // fresh server
      { s1: { c1: 2 } },               // older local
      new Set(),                       // nothing dirty
    );
    expect(merged.s1.c1).toBe(5);
  });

  test('mixed: keeps the dirty cell, syncs the rest for the same student', () => {
    const dirty = new Set(['s1:c1']);
    const merged = mergeFollowupData(
      { s1: { c1: 1, c2: 9 } },        // server
      { s1: { c1: 8, c2: 4 } },        // local
      dirty,
    );
    expect(merged.s1.c1).toBe(8); // dirty preserved
    expect(merged.s1.c2).toBe(9); // non-dirty synced
  });

  test.each([
    ['zero→nonzero', 0, 4],
    ['nonzero→another-nonzero', 3, 6],
    ['increment', 2, 3],
    ['decrement', 5, 1],
  ])('persists a dirty %s edit over a stale server value', (_label, serverVal, localVal) => {
    const dirty = new Set(['s1:c1']);
    const merged = mergeFollowupData(
      { s1: { c1: serverVal } },
      { s1: { c1: localVal } },
      dirty,
    );
    expect(merged.s1.c1).toBe(localVal);
  });

  test('handles empty/undefined inputs without throwing', () => {
    expect(mergeFollowupData(undefined, undefined, new Set())).toEqual({});
    expect(mergeFollowupData({}, { s1: { c1: 1 } }, new Set())).toEqual({ s1: { c1: 1 } });
  });
});

describe('mergeFollowupAbsences — stale-reload guard for absences', () => {
  test('keeps a dirty student\'s locally-edited absence list', () => {
    const dirty = new Set(['s1']);
    const merged = mergeFollowupAbsences(
      { s1: ['2026-01-01'] },                       // server (stale)
      { s1: ['2026-01-01', '2026-01-02'] },         // local add not yet saved
      dirty,
    );
    expect(merged.s1).toEqual(['2026-01-01', '2026-01-02']);
  });

  test('removes a dirty student the teacher locally cleared (last absence deleted)', () => {
    const dirty = new Set(['s1']);
    const merged = mergeFollowupAbsences(
      { s1: ['2026-01-01'] },   // server still has the absence
      {},                       // local: teacher removed it (key deleted)
      dirty,
    );
    expect(merged.s1).toBeUndefined();
  });

  test('a non-dirty student syncs to the fresh server list', () => {
    const merged = mergeFollowupAbsences(
      { s1: ['2026-01-03'] },
      { s1: ['2026-01-01'] },
      new Set(),
    );
    expect(merged.s1).toEqual(['2026-01-03']);
  });
});

describe('isFollowupNoOpFlush — empty-payload deletion guard', () => {
  test('skips when payload is empty AND nothing is dirty (fresh session)', () => {
    expect(isFollowupNoOpFlush({}, {}, new Set(), new Set())).toBe(true);
  });

  test('does NOT skip when an absence deletion left an empty payload but dirty state', () => {
    // Teacher removed the last absence and there are no grades: must still POST {}.
    expect(isFollowupNoOpFlush({}, {}, new Set(), new Set(['s1']))).toBe(false);
  });

  test('does NOT skip when there is grade data to persist', () => {
    expect(isFollowupNoOpFlush({ s1: { c1: 4 } }, {}, new Set(), new Set())).toBe(false);
  });
});

describe('runFollowupClose — persist first, dismiss only after save resolves', () => {
  test('dismisses immediately when nothing is unsaved (no flush)', async () => {
    const flush = jest.fn();
    const dismiss = jest.fn();
    await runFollowupClose({ needsFlush: false, flush, dismiss });
    expect(flush).not.toHaveBeenCalled();
    expect(dismiss).toHaveBeenCalledTimes(1);
  });

  test('flushes then dismisses on a successful save', async () => {
    const order = [];
    const flush = jest.fn(() => { order.push('flush'); return Promise.resolve(); });
    const dismiss = jest.fn(() => order.push('dismiss'));
    await runFollowupClose({ needsFlush: true, flush, dismiss });
    expect(flush).toHaveBeenCalledTimes(1);
    expect(dismiss).toHaveBeenCalledTimes(1);
    expect(order).toEqual(['flush', 'dismiss']); // dismiss only AFTER save resolves
  });

  test('keeps the sheet OPEN (no dismiss) when the save fails — edit retained', async () => {
    const flush = jest.fn(() => Promise.reject(new Error('network')));
    const dismiss = jest.fn();
    await runFollowupClose({ needsFlush: true, flush, dismiss });
    expect(flush).toHaveBeenCalledTimes(1);
    expect(dismiss).not.toHaveBeenCalled(); // save-failure UX: stays open, nothing lost
  });
});
