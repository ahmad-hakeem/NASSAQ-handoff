/**
 * SessionTeachPage — live negative-behaviour feedback regression tests.
 *
 * Bug context: recording a negative behaviour (سلبي) in a live class deducts
 * points server-side (it folds into the participation grade / كشف المتابعة),
 * but the LIVE session screen gave no instant sign-aware feedback the way
 * recording an answer / participation does — its toast omitted the points
 * delta and no visible student stat moved.
 *
 * Invariants locked here (recordBehaviour, the single chokepoint shared by the
 * positive/negative quick-behaviour popovers on the right action sidebar):
 *   - Recording a negative behaviour POSTs to /session/:id/behaviour with the
 *     'negative' category and the chosen behaviour_type.
 *   - The teacher gets an instant, sign-aware toast that INCLUDES the deduction
 *     (e.g. "(-2)") via toast.info (not a green success toast).
 *   - The per-student "X/Y" counter is EVALUATION-ONLY, so recording a
 *     behaviour must NOT move it — only question answers (correct/wrong/no
 *     answer), recitation, and evaluation items do. The deduction still lands
 *     server-side and in the sign-aware toast.
 *
 * The live UI path exercised: select a student row -> open the negative
 * behaviour popover (right sidebar TriggerBtn) -> click a negative behaviour.
 *
 * Run: CI=true npx craco test --testPathPattern="behaviourFeedback" --watchAll=false --forceExit
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const SESSION_ID = 'sess-bhv-integ';
const SUBJECT_ID = 'subj-bhv';
// student_code intentionally digit-free so the evaluation-counter badge (a
// bare "1") can be uniquely detected within the row — here we assert it never
// appears for a behaviour, which is not an evaluation event.
const STUDENT = {
  id: 'stu-1',
  full_name: 'Ahmed Test',
  attendance_status: 'present',
  interaction_count: 0,
  correct_answers: 0,
  gender: 'male',
  student_code: 'SX',
};

// ---------------------------------------------------------------------------
// Mock API spies — names prefixed with "mock" for babel-jest hoisting.
// ---------------------------------------------------------------------------
const mockGet = jest.fn();
const mockPost = jest.fn();

jest.mock('canvas-confetti', () => ({ __esModule: true, default: jest.fn() }));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn(), warning: jest.fn() },
}));
// Grab a typed handle to the mocked toast for assertions.
// eslint-disable-next-line global-require
const { toast: mockToast } = require('sonner');

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({
    state: {
      sessionId: SESSION_ID,
      sessionInfo: {
        class_name: 'Test Class',
        subject_name: 'Math',
        subject_id: SUBJECT_ID,
      },
    },
    pathname: '/session/teach',
  }),
}), { virtual: true });

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', name: 'Ahmed Teacher', role: 'teacher', school_id: 'school-1' },
    api: { get: mockGet, post: mockPost },
    isRTL: false,
  }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: false, dir: 'ltr' }),
  useTheme: () => ({ isDark: false, toggleTheme: jest.fn() }),
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqConfirm: jest.fn() }),
  NassaqAlertDialog: () => null,
}));

jest.mock('../../../components/SectionErrorBoundary', () => ({ children }) => <>{children}</>);
jest.mock('../../../components/teacher/FollowupGradesTable', () => () => null);
jest.mock('../../../components/teacher/InlineAttendanceTable', () => () => null);
jest.mock('../../../components/teacher/SidebarSettingsDialog', () => () => null);

jest.mock('../../../components/ui/dialog', () => {
  const Passthrough = ({ children }) => <div>{children}</div>;
  return {
    Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
    DialogPortal: Passthrough,
    DialogOverlay: Passthrough,
    DialogTrigger: Passthrough,
    DialogClose: Passthrough,
    DialogContent: Passthrough,
    DialogHeader: Passthrough,
    DialogFooter: Passthrough,
    DialogTitle: Passthrough,
    DialogDescription: Passthrough,
  };
});

// Component under test (imported AFTER all mocks).
import SessionTeachPage from '../SessionTeachPage';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockToast.success.mockClear();
  mockToast.error.mockClear();
  mockToast.info.mockClear();

  mockGet.mockImplementation((url) => {
    if (url.endsWith('/settings'))
      return Promise.resolve({
        data: { subject_id: SUBJECT_ID, participation_scores: {}, participation_enabled: true },
      });
    if (url.endsWith('/students'))
      return Promise.resolve({ data: { students: [STUDENT] } });
    if (url.endsWith('/groups'))
      return Promise.resolve({ data: { groups: [] } });
    if (url.endsWith('/notes'))
      return Promise.resolve({ data: { notes: [] } });
    if (url.endsWith('/undo/peek'))
      return Promise.resolve({ data: { has_reversible: false } });
    if (url.endsWith('/activity'))
      return Promise.resolve({ data: { activity: [] } });
    if (url.endsWith('/live-metrics'))
      return Promise.resolve({ data: {} });
    if (url.endsWith('/followup-record'))
      return Promise.resolve({ data: { data: {}, absences: {} } });
    if (url.endsWith('/grade-columns'))
      return Promise.resolve({ data: { columns: [] } });
    if (url.endsWith('/skills-types') || url === '/subjects')
      return Promise.resolve({ data: [] });
    // Default: session document — status must be 'active' or the page navigates away.
    return Promise.resolve({ data: { id: SESSION_ID, class_name: 'Test Class', status: 'active' } });
  });

  // Negative behaviour deducts 2 points; everything else is a no-op success.
  mockPost.mockImplementation((url) => {
    if (typeof url === 'string' && url.endsWith('/behaviour'))
      return Promise.resolve({ data: { score_change: -2 } });
    return Promise.resolve({ data: {} });
  });

  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

// ---------------------------------------------------------------------------
// Helper: drive the live UI to record a negative behaviour for STUDENT.
// ---------------------------------------------------------------------------
async function recordNegativeBehaviour() {
  render(<SessionTeachPage />);

  // Student roster has rendered (full mount sequence complete).
  await screen.findByText('Ahmed Test', {}, { timeout: 4000 });

  // Select the student by clicking the StudentRow (role="button" wrapping the
  // name). StudentRow is a stable top-level component, so its node is durable.
  const row = screen
    .getAllByText('Ahmed Test')
    .map(el => el.closest('[role="button"]'))
    .find(Boolean);
  expect(row).toBeTruthy();
  fireEvent.click(row);

  // Open the negative behaviour popover from the right action sidebar.
  // NOTE: TriggerBtn is defined *inline* inside the render, so every re-render
  // gives it a new component identity and React remounts the node. We therefore
  // query it SYNCHRONOUSLY right before clicking — an awaited query can resolve
  // to a node a subsequent re-render has already detached, so the click would
  // never reach React's listener.
  const negativeTrigger = screen.getByRole('button', { name: 'negative' });
  fireEvent.click(negativeTrigger);

  // The popover is rendered by the stable EvalPopover; its behaviour buttons are
  // plain <button>s keyed by id, so awaiting them is safe. Pick "disruption".
  const disruptionBtn = await screen.findByText('behaviourDisruption', {}, { timeout: 3000 });
  fireEvent.click(disruptionBtn);

  return row;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('SessionTeachPage — live negative-behaviour feedback', () => {
  test('POSTs the negative behaviour with the correct category and type', async () => {
    await recordNegativeBehaviour();

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        `/session/${SESSION_ID}/behaviour`,
        expect.objectContaining({
          student_id: STUDENT.id,
          category: 'negative',
          behaviour_type: 'disruption',
        })
      );
    }, { timeout: 3000 });
  });

  test('shows an instant sign-aware toast that includes the deduction', async () => {
    await recordNegativeBehaviour();

    await waitFor(() => {
      expect(mockToast.info).toHaveBeenCalledWith(expect.stringContaining('(-2)'));
    }, { timeout: 3000 });

    // A deduction must NOT read as a green "success".
    expect(mockToast.success).not.toHaveBeenCalledWith(expect.stringContaining('(-2)'));
  });

  test('does NOT move the evaluation-only per-student counter for a behaviour', async () => {
    await recordNegativeBehaviour();

    // Confirm the behaviour flow actually completed (sign-aware deduction toast).
    await waitFor(() => {
      expect(mockToast.info).toHaveBeenCalledWith(expect.stringContaining('(-2)'));
    }, { timeout: 3000 });

    // The per-student "X/Y" counter / badge is EVALUATION-ONLY. A behaviour is
    // not an evaluation event, so no counter badge (a bare "1") may appear in
    // the student's row.
    const row = screen
      .getAllByText('Ahmed Test')
      .map(el => el.closest('[role="button"]'))
      .find(Boolean);
    expect(row).toBeTruthy();
    expect(within(row).queryByText('1')).toBeNull();
  });
});
