// Pure persistence helpers for the follow-up sheet (كشف المتابعة).
//
// These are extracted out of SessionTeachPage so the core persistence rules
// (stale-reload guard, no-op-flush guard, and flush-before-dismiss on close)
// can be unit-tested without mounting the full live-session page. SessionTeachPage
// imports and uses these directly, so the tests exercise the real logic.

// Merge fresh server grade values into the local map WITHOUT clobbering any cell
// the teacher has edited but not yet saved (its key is in `dirtyKeys`). This is
// the stale-reload guard: on reopen / poll, a not-yet-persisted edit wins over
// the older server value, while every non-dirty cell syncs to the server.
// `dirtyKeys` is a Set of `${studentId}:${columnId}`.
export function mergeFollowupData(serverData, prevData, dirtyKeys) {
  const fresh = serverData || {};
  const next = { ...(prevData || {}) };
  for (const [sid, cols] of Object.entries(fresh)) {
    for (const [cid, val] of Object.entries(cols || {})) {
      if (!dirtyKeys.has(`${sid}:${cid}`)) {
        next[sid] = { ...(next[sid] || {}), [cid]: val };
      }
    }
  }
  return next;
}

// Absence equivalent of mergeFollowupData. Start from the fresh server map, then
// for each student the teacher is mid-editing (dirty) keep the local list — or
// delete the key entirely if the teacher locally cleared all of that student's
// absences (prev[sid] === undefined) — so the poll/reopen can't clobber an
// unsaved absence edit. `dirtyStudentIds` is a Set of student ids.
export function mergeFollowupAbsences(serverAbsences, prevAbsences, dirtyStudentIds) {
  const next = { ...(serverAbsences || {}) };
  const prev = prevAbsences || {};
  dirtyStudentIds.forEach((sid) => {
    if (prev[sid] !== undefined) next[sid] = prev[sid];
    else delete next[sid];
  });
  return next;
}

// A flush should be skipped only when there is genuinely nothing to persist.
// An empty payload WITH dirty state is meaningful — it's a deletion (e.g. the
// teacher removed the last absence and there are no grades) and must still be
// POSTed so the server record is cleared and the dirty markers released.
export function isFollowupNoOpFlush(data, absences, dirtyCells, dirtyAbsences) {
  return (
    Object.keys(data || {}).length === 0 &&
    Object.keys(absences || {}).length === 0 &&
    dirtyCells.size === 0 &&
    dirtyAbsences.size === 0
  );
}

// Close orchestration: persist FIRST, dismiss only after the save resolves.
// - Nothing unsaved: dismiss immediately.
// - Unsaved edits: flush; on success dismiss; on failure keep the sheet OPEN
//   (the caller's flush already surfaced a safe Arabic message) so the teacher
//   can retry and the edit is never dropped.
export async function runFollowupClose({ needsFlush, flush, dismiss }) {
  if (!needsFlush) {
    dismiss();
    return;
  }
  try {
    await flush();
    dismiss();
  } catch {
    // Save failed: do NOT dismiss — keep the sheet open with the edit intact.
  }
}

// Build the POST payload from the full local grid, keeping ONLY the cells the
// teacher has taken manual ownership of (key in `manualKeys`) AND that hold a
// non-empty value. Every other cell is session-derived and must NOT be sent:
// persisting a derived value as a manual override freezes the cell so later
// sidebar scoring never reaches the sheet or the committed grade. An empty
// manual cell is an explicit "revert to derived" — it is omitted so the
// replace-on-save drops the stored override. `manualKeys` is a Set of
// `${studentId}:${columnId}`.
export function pickManualCells(followupData, manualKeys) {
  const keys = manualKeys || new Set();
  const out = {};
  for (const [sid, cols] of Object.entries(followupData || {})) {
    for (const [cid, val] of Object.entries(cols || {})) {
      if (!keys.has(`${sid}:${cid}`)) continue;
      if (val === null || val === undefined || val === '') continue;
      out[sid] = { ...(out[sid] || {}), [cid]: val };
    }
  }
  return out;
}

// Recompute which cells are manual overrides after a server read. The server is
// authoritative for what is persisted (`serverKeys` = non-empty stored override
// cells); we additionally keep any cell edited locally but not yet saved
// (`dirtyKeys`) so an in-flight edit during the 1.5s debounce / 30s poll isn't
// dropped. A cell the teacher cleared falls out of BOTH sets, so its override is
// correctly forgotten. Both are arrays/Sets of `${studentId}:${columnId}`.
export function computeManualKeys(serverKeys, dirtyKeys) {
  return new Set([...(serverKeys || []), ...(dirtyKeys || [])]);
}
