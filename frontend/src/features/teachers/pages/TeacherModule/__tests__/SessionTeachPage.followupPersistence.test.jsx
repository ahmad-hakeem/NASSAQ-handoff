/**
 * Follow-up sheet (كشف المتابعة) edit-persistence regression tests.
 *
 * Locks in the persistence fix in SessionTeachPage.jsx + followupPersistence.js
 * so the serialized-flush + dirty/revision behavior can't silently regress.
 *
 * Two layers:
 *  - Suite 1 (pure helpers): mergeFollowupData / mergeFollowupAbsences /
 *    isFollowupNoOpFlush / runFollowupClose — the stale-reload guard, the
 *    empty-payload deletion semantics, and the flush-before-dismiss close
 *    orchestration. These underpin every scenario and cover the absence
 *    add/remove and empty-payload deletion paths (the absence-editing UI lives
 *    behind an intentionally-hidden tab, so it isn't DOM-reachable in a full
 *    mount — but absences ride the SAME flush/dirty/revision machinery as
 *    grades, exercised at the component level below).
 *  - Suite 2 (SessionTeachPage integration, mocked api + jest fake timers):
 *    grade edit -> close -> reopen persistence; one /followup-record POST in
 *    flight at a time (last write wins); and a mid-flight edit surviving the
 *    in-flight save's success + the merge poll (revision model).
 *
 * Applies equally to School Teacher and Independent Teacher — the surface is
 * shared and the logic is identical, so no separate IT test path is needed.
 */
import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';

import {
  mergeFollowupData,
  mergeFollowupAbsences,
  isFollowupNoOpFlush,
  runFollowupClose,
  pickManualCells,
  computeManualKeys,
} from '../followupPersistence';

// ───────────────────────────────────────────────────────────────────────────
// Suite 1 — pure persistence helpers
// ───────────────────────────────────────────────────────────────────────────
describe('followupPersistence helpers', () => {
  describe('mergeFollowupData (stale-reload guard)', () => {
    test('syncs non-dirty cells to fresh server values', () => {
      const out = mergeFollowupData(
        { s1: { c1: 5, c2: 8 } },
        { s1: { c1: 1 } },
        new Set(), // nothing dirty
      );
      expect(out).toEqual({ s1: { c1: 5, c2: 8 } });
    });

    test('preserves a dirty (unsaved) cell, ignoring the older server value', () => {
      const out = mergeFollowupData(
        { s1: { c1: 5, c2: 8 } }, // server says c1=5
        { s1: { c1: 9, c2: 8 } }, // teacher just typed c1=9
        new Set(['s1:c1']),       // c1 is dirty
      );
      // c1 keeps the unsaved 9; c2 (not dirty) syncs to the server 8.
      expect(out).toEqual({ s1: { c1: 9, c2: 8 } });
    });

    test('handles empty prev and missing server map', () => {
      expect(mergeFollowupData(undefined, undefined, new Set())).toEqual({});
      expect(mergeFollowupData({ s1: { c1: 2 } }, undefined, new Set())).toEqual({ s1: { c1: 2 } });
    });
  });

  describe('mergeFollowupAbsences (absence stale-reload guard)', () => {
    test('syncs a non-dirty student to the fresh server list', () => {
      const out = mergeFollowupAbsences(
        { s1: ['2026-01-01'] },
        { s1: [] },
        new Set(),
      );
      expect(out).toEqual({ s1: ['2026-01-01'] });
    });

    test('keeps the local list for a student mid-editing (dirty)', () => {
      const out = mergeFollowupAbsences(
        { s1: ['2026-01-01'] },             // server still has the old absence
        { s1: ['2026-01-01', '2026-02-02'] }, // teacher just added one
        new Set(['s1']),
      );
      expect(out).toEqual({ s1: ['2026-01-01', '2026-02-02'] });
    });

    test('deletes the key when a dirty student was locally cleared (last absence removed)', () => {
      const out = mergeFollowupAbsences(
        { s1: ['2026-01-01'] }, // server still lists it
        {},                     // teacher removed the last absence -> prev[s1] undefined
        new Set(['s1']),
      );
      expect(out).toEqual({});
    });
  });

  describe('isFollowupNoOpFlush (deletion vs no-op)', () => {
    test('empty payload with no dirty state is a no-op (skip the POST)', () => {
      expect(isFollowupNoOpFlush({}, {}, new Set(), new Set())).toBe(true);
    });

    test('empty payload WITH a dirty absence is meaningful — must POST {} (deletion)', () => {
      expect(isFollowupNoOpFlush({}, {}, new Set(), new Set(['s1']))).toBe(false);
    });

    test('non-empty data or absences is never a no-op', () => {
      expect(isFollowupNoOpFlush({ s1: { c1: 1 } }, {}, new Set(), new Set())).toBe(false);
      expect(isFollowupNoOpFlush({}, { s1: ['2026-01-01'] }, new Set(), new Set())).toBe(false);
    });
  });

  describe('runFollowupClose (flush-before-dismiss)', () => {
    test('dismisses immediately when nothing is pending (no flush)', async () => {
      const flush = jest.fn();
      const dismiss = jest.fn();
      await runFollowupClose({ needsFlush: false, flush, dismiss });
      expect(flush).not.toHaveBeenCalled();
      expect(dismiss).toHaveBeenCalledTimes(1);
    });

    test('flushes first, then dismisses on success', async () => {
      const order = [];
      const flush = jest.fn(() => { order.push('flush'); return Promise.resolve(); });
      const dismiss = jest.fn(() => order.push('dismiss'));
      await runFollowupClose({ needsFlush: true, flush, dismiss });
      expect(order).toEqual(['flush', 'dismiss']);
    });

    test('keeps the sheet OPEN (no dismiss) when the flush fails', async () => {
      const flush = jest.fn(() => Promise.reject(new Error('save failed')));
      const dismiss = jest.fn();
      await runFollowupClose({ needsFlush: true, flush, dismiss });
      expect(flush).toHaveBeenCalledTimes(1);
      expect(dismiss).not.toHaveBeenCalled();
    });
  });

  describe('pickManualCells (send only the teacher\'s real overrides)', () => {
    test('keeps only cells whose key is in the manual set', () => {
      const grid = { s1: { c1: 5, c2: 8 }, s2: { c1: 3 } };
      // Only s1:c1 is a genuine manual edit; everything else is session-derived.
      const out = pickManualCells(grid, new Set(['s1:c1']));
      expect(out).toEqual({ s1: { c1: 5 } });
    });

    test('drops a derived echo even when it sits next to a manual edit', () => {
      // The sheet shows derived c2=8 and a manual c1=5; only c1 must be sent so
      // c2 keeps tracking the live score and never freezes.
      const grid = { s1: { c1: 5, c2: 8 } };
      expect(pickManualCells(grid, new Set(['s1:c1']))).toEqual({ s1: { c1: 5 } });
    });

    test('omits empty manual cells (cleared = revert to derived)', () => {
      const grid = { s1: { c1: '', c2: null, c3: undefined, c4: 4 } };
      const out = pickManualCells(grid, new Set(['s1:c1', 's1:c2', 's1:c3', 's1:c4']));
      expect(out).toEqual({ s1: { c4: 4 } });
    });

    test('keeps a manual zero (0 is a real score, not empty)', () => {
      expect(pickManualCells({ s1: { c1: 0 } }, new Set(['s1:c1']))).toEqual({ s1: { c1: 0 } });
    });

    test('a row with no surviving manual cells is omitted entirely', () => {
      const grid = { s1: { c1: 5 }, s2: { c1: 9 } };
      // s2:c1 is derived (not manual); s1:c1 is manual.
      expect(pickManualCells(grid, new Set(['s1:c1']))).toEqual({ s1: { c1: 5 } });
    });

    test('handles a null grid / null manual set without throwing', () => {
      expect(pickManualCells(null, new Set(['s1:c1']))).toEqual({});
      expect(pickManualCells({ s1: { c1: 5 } }, null)).toEqual({});
    });
  });

  describe('computeManualKeys (server truth ∪ unsaved-dirty)', () => {
    test('unions the server manual_keys with the local dirty set', () => {
      const out = computeManualKeys(['s1:c1'], new Set(['s2:c1']));
      expect(out).toEqual(new Set(['s1:c1', 's2:c1']));
    });

    test('a cleared cell (absent server-side AND not dirty) is forgotten', () => {
      // The teacher cleared s1:c1: it dropped out of the stored overrides and,
      // after its flush, out of the dirty set too — so it must not linger.
      const out = computeManualKeys(['s1:c2'], new Set());
      expect(out.has('s1:c1')).toBe(false);
      expect(out).toEqual(new Set(['s1:c2']));
    });

    test('an unsaved edit survives a poll that does not yet know about it', () => {
      // Server hasn't seen s1:c9 yet (still in flight), but it is dirty -> keep it.
      const out = computeManualKeys([], new Set(['s1:c9']));
      expect(out).toEqual(new Set(['s1:c9']));
    });

    test('tolerates missing server keys / dirty set', () => {
      expect(computeManualKeys(undefined, undefined)).toEqual(new Set());
    });
  });
});

// ───────────────────────────────────────────────────────────────────────────
// Suite 2 — SessionTeachPage integration (mocked api + fake timers)
// ───────────────────────────────────────────────────────────────────────────

// Router
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ state: { sessionId: 'sess-1' } }),
}), { virtual: true });

// Contexts
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: mockApiPost,
  put: jest.fn().mockResolvedValue({ data: {} }),
  patch: jest.fn().mockResolvedValue({ data: {} }),
  delete: jest.fn().mockResolvedValue({ data: {} }),
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    api: mockApi,
    user: { id: 'teacher-1', teacher_id: 'teacher-1', role: 'teacher', tenant_id: 'school-1' },
    isRTL: true,
  }),
}));
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
  NassaqAlertDialog: () => null,
}));

// Error boundary — passthrough so any thrown error surfaces in the test.
jest.mock('@/shared/components/SectionErrorBoundary', () => ({
  __esModule: true,
  default: ({ children }) => <>{children}</>,
}));

// Stub heavy child components we don't drive.
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({
  __esModule: true,
  default: () => <div data-testid="sidebar-settings" />,
}));
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => ({
  __esModule: true,
  default: () => <div />,
}));

// FollowupGradesTable test double: one editable input per student × visible
// column, wired to onGradeChange and reflecting gradesData so a reopen shows
// the persisted value.
jest.mock('@/features/teachers/components/teacher/FollowupGradesTable', () => ({
  __esModule: true,
  default: ({ students = [], columns = [], gradesData = {}, onGradeChange }) => (
    <div data-testid="followup-grades-table">
      {students.map((s) =>
        columns.filter((c) => !c.hidden).map((c) => (
          <input
            key={`${s.id}-${c.id}`}
            data-testid={`grade-${s.id}-${c.id}`}
            value={(gradesData[s.id] && gradesData[s.id][c.id] != null) ? gradesData[s.id][c.id] : ''}
            onChange={(e) => onGradeChange && onGradeChange(s.id, c.id, e.target.value)}
          />
        )),
      )}
    </div>
  ),
}));

// UI primitives — Dialog GATES its children on `open` (mirrors the real modal)
// so only the open follow-up dialog renders, keeping queries unambiguous.
jest.mock('@/shared/components/ui/card', () => ({
  Card: ({ children, ...p }) => <div {...p}>{children}</div>,
  CardContent: ({ children, ...p }) => <div {...p}>{children}</div>,
}));
jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, onClick, ...p }) => <button onClick={onClick} {...p}>{children}</button>,
}));
jest.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children, ...p }) => <span {...p}>{children}</span>,
}));
jest.mock('@/shared/components/ui/avatar', () => ({
  Avatar: ({ children }) => <div>{children}</div>,
  AvatarFallback: ({ children }) => <div>{children}</div>,
  AvatarImage: () => <img alt="" />,
}));
jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
}));
jest.mock('@/shared/components/ui/textarea', () => ({
  Textarea: (p) => <textarea {...p} />,
}));
jest.mock('canvas-confetti', () => jest.fn());
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

// Import after all mocks are registered.
import SessionTeachPage from '../SessionTeachPage';

const SESSION = {
  id: 'sess-1', status: 'in_progress', class_id: 'cls-1', school_id: 'school-1',
  teacher_id: 'teacher-1', start_time: new Date().toISOString(),
  stats: { questions_asked: 0, correct_answers: 0 }, interaction_mode: 'review',
};
const STUDENTS = [{ id: 'stu-1', full_name: 'أحمد محمد', interaction_count: 0, correct_answers: 0 }];
const COLUMNS = [{ id: 'part', name: 'المشاركة', column_type: 'coursework', max_grade: 10, visible: true, order: 1 }];

// Mutable server-side follow-up record + a POST gate so we can control flush
// resolution timing for the serialization / mid-flight tests.
let serverFollowup;
let postQueue;
let autoResolvePost;
let inFlight;
let maxInFlight;

function postFollowup(body) {
  inFlight += 1;
  if (inFlight > maxInFlight) maxInFlight = inFlight;
  return new Promise((resolve) => {
    const finish = () => {
      serverFollowup = { data: body.data || {}, absences: body.absences || {} };
      inFlight -= 1;
      resolve({ data: serverFollowup });
    };
    if (autoResolvePost) finish();
    else postQueue.push(finish);
  });
}
function releaseOnePost() {
  const f = postQueue.shift();
  if (f) f();
}

function setupApi() {
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: {} });
    if (url === '/session/sess-1') return Promise.resolve({ data: SESSION });
    if (url === '/session/sess-1/students') return Promise.resolve({ data: { students: STUDENTS } });
    if (url === '/session/sess-1/followup-record') return Promise.resolve({ data: serverFollowup });
    if (url === '/class/cls-1/grade-columns') return Promise.resolve({ data: COLUMNS });
    if (url === '/skills-types') return Promise.resolve({ data: [] });
    if (url === '/subjects') return Promise.resolve({ data: [] });
    if (url.endsWith('/groups')) return Promise.resolve({ data: [] });
    if (url.endsWith('/settings')) return Promise.resolve({ data: {} });
    if (url.endsWith('/notes')) return Promise.resolve({ data: [] });
    if (url.endsWith('/undo/peek')) return Promise.resolve({ data: { can_undo: false } });
    if (url.endsWith('/activity')) return Promise.resolve({ data: [] });
    if (url.endsWith('/live-metrics')) return Promise.resolve({ data: {} });
    if (url.endsWith('/homework')) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockImplementation((url, body) => {
    if (url === '/session/sess-1/followup-record') return postFollowup(body);
    return Promise.resolve({ data: {} });
  });
}

const followupPosts = () =>
  mockApiPost.mock.calls.filter(([u]) => u === '/session/sess-1/followup-record');

async function flushMicrotasks() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}
async function advance(ms) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
    // Flush several microtask turns so timer-scheduled GET/POST .then chains
    // (e.g. the 30 s merge poll) settle inside this act() block.
    for (let i = 0; i < 6; i += 1) await Promise.resolve();
  });
}

async function mountPage() {
  await act(async () => {
    render(<SessionTeachPage />);
  });
  await flushMicrotasks();
}

async function openFollowup() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'followupRecord' }));
  });
  await flushMicrotasks();
}

async function closeFollowup() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'close' }));
    await Promise.resolve();
    await Promise.resolve();
  });
  await flushMicrotasks();
}

describe('SessionTeachPage follow-up persistence (integration)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    serverFollowup = { data: {}, absences: {} };
    postQueue = [];
    autoResolvePost = true;
    inFlight = 0;
    maxInFlight = 0;
    setupApi();
  });
  afterEach(() => {
    act(() => { jest.runOnlyPendingTimers(); });
    jest.useRealTimers();
  });

  test('grade edit -> close -> reopen persists the value', async () => {
    await mountPage();
    await openFollowup();

    const input = screen.getByTestId('grade-stu-1-part');
    expect(input.value).toBe('');

    await act(async () => {
      fireEvent.change(input, { target: { value: '7' } });
    });
    expect(screen.getByTestId('grade-stu-1-part').value).toBe('7');

    await closeFollowup();

    // The close fired exactly one POST carrying the edited value.
    const posts = followupPosts();
    expect(posts.length).toBe(1);
    expect(posts[0][1]).toEqual({ data: { 'stu-1': { part: '7' } }, absences: {} });

    // Reopen: awaits the flush chain, then merges the just-saved server value.
    await openFollowup();
    expect(screen.getByTestId('grade-stu-1-part').value).toBe('7');
  });

  test('closing with no edits does not POST (no-op guard)', async () => {
    await mountPage();
    await openFollowup();
    await closeFollowup();
    expect(followupPosts().length).toBe(0);
  });

  test('serializes flushes: one POST in flight at a time, last write wins', async () => {
    autoResolvePost = false;
    await mountPage();
    await openFollowup();

    const input = screen.getByTestId('grade-stu-1-part');

    // First edit -> debounce -> flush #1 (POST gated/in-flight).
    await act(async () => { fireEvent.change(input, { target: { value: '3' } }); });
    await advance(1500);
    expect(inFlight).toBe(1);

    // Second edit while #1 is still in flight -> flush #2 is queued behind the
    // chain; its POST must NOT start until #1 resolves.
    await act(async () => { fireEvent.change(screen.getByTestId('grade-stu-1-part'), { target: { value: '5' } }); });
    await advance(1500);
    expect(inFlight).toBe(1);
    expect(followupPosts().length).toBe(1);

    // Resolve #1 -> #2's POST now starts (still only one in flight).
    await act(async () => { releaseOnePost(); await Promise.resolve(); await Promise.resolve(); });
    expect(inFlight).toBe(1);
    expect(followupPosts().length).toBe(2);

    // Resolve #2.
    await act(async () => { releaseOnePost(); await Promise.resolve(); });

    expect(maxInFlight).toBe(1);
    // Last write wins: the second flush read the latest value from the refs.
    expect(followupPosts()[1][1].data['stu-1'].part).toBe('5');
    expect(serverFollowup.data['stu-1'].part).toBe('5');
  });

  test('a mid-flight edit survives the in-flight save success and the merge poll', async () => {
    autoResolvePost = false;
    await mountPage();
    await openFollowup();

    const input = screen.getByTestId('grade-stu-1-part');

    // Edit -> flush #1 starts (gated).
    await act(async () => { fireEvent.change(input, { target: { value: '3' } }); });
    await advance(1500);
    expect(inFlight).toBe(1);

    // Bump the cell's revision while save #1 is in flight.
    await act(async () => { fireEvent.change(screen.getByTestId('grade-stu-1-part'), { target: { value: '9' } }); });

    // Resolve #1 (it persisted the OLD value 3). Its success must NOT clear the
    // newer dirty edit, because the cell's revision changed mid-flight.
    await act(async () => { releaseOnePost(); await Promise.resolve(); await Promise.resolve(); });
    expect(serverFollowup.data['stu-1'].part).toBe('3');

    // Let flush #2 fire but keep its POST gated, so the server still reads 3
    // when the 30 s merge poll runs.
    await advance(1500); // flush #2 -> POST queued (not released)
    await advance(30000); // 30 s merge poll: GET returns server 3

    // The dirty cell is preserved: the poll did NOT clobber the newer 9.
    expect(screen.getByTestId('grade-stu-1-part').value).toBe('9');
  });

  test('ending the session flushes a pending (debounced) follow-up edit first', async () => {
    await mountPage();
    await openFollowup();

    // Edit a cell but do NOT wait out the 1.5s debounce and do NOT close the
    // dialog — the flush must not depend on either.
    await act(async () => {
      fireEvent.change(screen.getByTestId('grade-stu-1-part'), { target: { value: '6' } });
    });
    expect(followupPosts().length).toBe(0);

    // Open the end-session confirm and start the review — this path must
    // flush the pending edit before fetching the review preview.
    await act(async () => {
      fireEvent.click(screen.getByTitle('endSession'));
    });
    await flushMicrotasks();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'reviewAndEnd' }));
    });
    await flushMicrotasks();

    const posts = followupPosts();
    expect(posts.length).toBe(1);
    expect(posts[0][1].data['stu-1'].part).toBe('6');
    // The review preview was requested (after the flush resolved).
    const previewGets = mockApiGet.mock.calls.filter(([u]) => u === '/session/sess-1/review-preview');
    expect(previewGets.length).toBe(1);
  });

  test('a rejected end-path flush blocks the review (fail closed, edit retained)', async () => {
    await mountPage();
    await openFollowup();

    await act(async () => {
      fireEvent.change(screen.getByTestId('grade-stu-1-part'), { target: { value: '6' } });
    });

    // The flush POST fails (network/server error).
    mockApiPost.mockImplementation((url) => {
      if (url === '/session/sess-1/followup-record') return Promise.reject(new Error('network'));
      return Promise.resolve({ data: {} });
    });

    await act(async () => {
      fireEvent.click(screen.getByTitle('endSession'));
    });
    await flushMicrotasks();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'reviewAndEnd' }));
    });
    await flushMicrotasks();

    // Fail closed: no review preview, no /end — the session cannot end past
    // an unsaved sheet edit; an error was surfaced and the edit stays dirty.
    expect(mockApiGet.mock.calls.filter(([u]) => u === '/session/sess-1/review-preview').length).toBe(0);
    expect(mockApiPost.mock.calls.filter(([u]) => u === '/session/sess-1/end').length).toBe(0);
    expect(mockAlert.nassaqError).toHaveBeenCalled();
    expect(screen.getByTestId('grade-stu-1-part').value).toBe('6');
  });
});
