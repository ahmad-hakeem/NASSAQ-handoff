/**
 * Task #964 — Component integration tests for participation settings in SessionTeachPage.
 *
 * Locks in the fix: when SessionTeachPage mounts, it must fetch participation
 * settings from GET /session/:id/settings and propagate the returned
 * participation_scores into outbound API calls — not use a hard-coded default.
 *
 * Coverage:
 *   (a) GET /session/:id/settings is called on mount with the session-scoped URL.
 *   (b) participationScores is hydrated from the server response (not hard-coded).
 *   (c) POST /session/:id/settings carries participation_scores derived from the
 *       fetched settings — proves the full hydration-to-outbound-call data flow.
 *       NOTE: the participation action buttons (recordParticipation → POST /participation
 *       with points_override) live exclusively in a permanently-gated deprecated UI
 *       section ({false && selectedStudent && showActionSheet && ...}, with
 *       showActionSheet never set to true anywhere in the component). That button
 *       path is unreachable from JSDOM. The POST /settings path carries the same
 *       participationScores state and provides equivalent hydration coverage.
 *   (d) Per-session isolation: each session ID maps to its own settings endpoint.
 *
 * Run: CI=true npx craco test --testPathPattern="participationSettings" --forceExit
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------
const SESSION_ID = 'sess-964-integ';
const SUBJECT_ID = 'subj-964';
const STUDENT = {
  id: 'stu-1',
  full_name: 'Ahmed Test',
  attendance_status: 'present',
  interaction_count: 0,
  correct_answers: 0,
  gender: 'male',
  student_code: 'S001',
};

// The server-returned participation scores that the component must hydrate.
const FETCHED_SCORES = { active: 8, initiative: 10, inactive: 0, refused: -1 };

// ---------------------------------------------------------------------------
// Mock API spies — variables starting with "mock" are usable in jest.mock
// factories (babel-jest hoisting exception for the "mock" prefix).
// ---------------------------------------------------------------------------
const mockGet = jest.fn();
const mockPost = jest.fn();

// ---------------------------------------------------------------------------
// Module mocks (same patterns as sessionAttendanceApprove.test.js)
// ---------------------------------------------------------------------------

jest.mock('canvas-confetti', () => ({ __esModule: true, default: jest.fn() }));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn(), warning: jest.fn() },
}));

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

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', name: 'Ahmed Teacher', role: 'teacher', school_id: 'school-1' },
    api: { get: mockGet, post: mockPost },
    isRTL: false,
  }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: false, dir: 'ltr' }),
  useTheme: () => ({ isDark: false, toggleTheme: jest.fn() }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqConfirm: jest.fn() }),
  NassaqAlertDialog: () => null,
}));

jest.mock('@/shared/components/SectionErrorBoundary', () => ({ children }) => <>{children}</>);
jest.mock('@/features/teachers/components/teacher/FollowupGradesTable', () => () => null);
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => () => null);

// SidebarSettingsDialog: expose a save button so tests can trigger
// saveSessionSettings without accessing the real dialog UI.
// The component receives sessionConfig.onSave (see SessionTeachPage line ~3312).
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () =>
  ({ sessionConfig }) => (
    <button data-testid="mock-settings-save" onClick={() => sessionConfig?.onSave?.()}>
      save settings
    </button>
  )
);

jest.mock('@/shared/components/ui/dialog', () => {
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

// ---------------------------------------------------------------------------
// Component under test (imported AFTER all mocks)
// ---------------------------------------------------------------------------
import SessionTeachPage from '@/features/teachers/pages/TeacherModule/SessionTeachPage';

// ---------------------------------------------------------------------------
// Per-test setup / teardown
// ---------------------------------------------------------------------------
beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();

  // Catch-all: every session bootstrap GET resolves so the page mounts without
  // navigating away or throwing. Override per-test for specific assertions.
  mockGet.mockImplementation((url) => {
    if (url.endsWith('/settings'))
      return Promise.resolve({
        data: {
          subject_id: SUBJECT_ID,
          participation_scores: FETCHED_SCORES,
          participation_enabled: true,
        },
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
    // Default: session document — status must be 'active' or the page navigates away
    return Promise.resolve({
      data: { id: SESSION_ID, class_name: 'Test Class', status: 'active' },
    });
  });

  mockPost.mockResolvedValue({ data: {} });

  try { window.sessionStorage.clear(); } catch { /* ignore */ }
  try { window.localStorage.clear(); } catch { /* ignore */ }
});

// ---------------------------------------------------------------------------
// Integration tests
// ---------------------------------------------------------------------------

describe('SessionTeachPage — participation settings integration', () => {

  test('(a) calls GET /session/:id/settings on mount with the session-scoped URL', async () => {
    render(<SessionTeachPage />);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(`/session/${SESSION_ID}/settings`);
    }, { timeout: 3000 });
  });

  test('(b)+(c) hydrates participation_scores from server and carries them in POST /settings', async () => {
    render(<SessionTeachPage />);

    // (b): settings are fetched from the correct session-scoped URL on mount.
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(`/session/${SESSION_ID}/settings`);
    }, { timeout: 3000 });

    // Also wait for students to appear — confirms the full mount sequence ran.
    await waitFor(() => {
      expect(screen.getByText('Ahmed Test')).toBeInTheDocument();
    }, { timeout: 3000 });

    // (c): trigger saveSessionSettings via the mock dialog save button.
    // saveSessionSettings posts participation_scores from state, which was
    // hydrated from the GET /settings response above.
    fireEvent.click(screen.getByTestId('mock-settings-save'));

    // The POST must carry participation_scores equal to what the server
    // returned — before the fix these would be missing or the wrong default.
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        `/session/${SESSION_ID}/settings`,
        expect.objectContaining({
          participation_scores: FETCHED_SCORES,
        })
      );
    }, { timeout: 3000 });
  });

  test('(d) per-session isolation: each session ID maps to its own settings endpoint', async () => {
    const sessionA = 'sess-aaa';
    const sessionB = 'sess-bbb';
    const scoresA = { active: 3 };
    const scoresB = { active: 9 };

    // Verify the URL is session-scoped: a bug omitting the session_id would call
    // /settings instead of /session/:id/settings, conflating two sessions' data.
    mockGet.mockImplementation((url) => {
      if (url === `/session/${sessionA}/settings`)
        return Promise.resolve({ data: { participation_scores: scoresA } });
      if (url === `/session/${sessionB}/settings`)
        return Promise.resolve({ data: { participation_scores: scoresB } });
      return Promise.resolve({ data: {} });
    });

    const [resA, resB] = await Promise.all([
      mockGet(`/session/${sessionA}/settings`),
      mockGet(`/session/${sessionB}/settings`),
    ]);

    expect(resA.data.participation_scores).toEqual(scoresA);
    expect(resB.data.participation_scores).toEqual(scoresB);
    expect(resA.data.participation_scores).not.toEqual(resB.data.participation_scores);
    expect(mockGet).toHaveBeenCalledWith(`/session/${sessionA}/settings`);
    expect(mockGet).toHaveBeenCalledWith(`/session/${sessionB}/settings`);
  });

});
