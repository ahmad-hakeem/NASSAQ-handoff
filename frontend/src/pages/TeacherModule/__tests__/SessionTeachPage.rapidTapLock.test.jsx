/**
 * Task #1111 — SessionTeachPage rapid-tap protection regression tests.
 *
 * recordAnswer holds a 600ms lock (answerLockRef) so a burst of accidental
 * double/triple taps can't fire several separate answers and spuriously cross
 * the 3-in-a-row streak threshold. These tests pin the timing contract:
 *
 * - A rapid double-tap on the "correct" evaluation button fires exactly ONE
 *   POST /session/{id}/answer (the burst is swallowed).
 * - A deliberate second tap AFTER the 600ms cooldown still registers, so a
 *   legitimate quick answer is never silently dropped.
 *
 * Entry point under test: the right-action-sidebar evaluation button
 * (the live UI path — the central tabbed action panel is deprecated/`false &&`).
 *
 * Harness note (see .agents/memory/cra-react18-act-harness.md): the page mount
 * sets the roster in one async round (loadStudents → setStudents) before the
 * chained loadSessionInfo, so the student row renders and is clickable without
 * needing a second settled round.
 */
import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';

// ── Router ──────────────────────────────────────────────────────────────────
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '', pathname: '/teacher/session/sess-1', state: { sessionId: 'sess-1' } }),
  useParams: () => ({ sessionId: 'sess-1' }),
}), { virtual: true });

// ── UI primitives ────────────────────────────────────────────────────────────
jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../../components/SectionErrorBoundary', () => ({
  __esModule: true,
  default: ({ children }) => <>{children}</>,
}));
jest.mock('../../../components/teacher/SidebarSettingsDialog', () => ({
  __esModule: true,
  default: () => <div data-testid="sidebar-settings" />,
}));
jest.mock('../../../components/teacher/InlineAttendanceTable', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../../components/teacher/FollowupGradesTable', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../../components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => <div />,
}));
jest.mock('../../../components/ui/card', () => ({
  Card: ({ children, ...p }) => <div {...p}>{children}</div>,
  CardContent: ({ children, ...p }) => <div {...p}>{children}</div>,
}));
jest.mock('../../../components/ui/button', () => ({
  Button: ({ children, onClick, ...p }) => <button onClick={onClick} {...p}>{children}</button>,
}));
jest.mock('../../../components/ui/badge', () => ({
  Badge: ({ children, ...p }) => <span {...p}>{children}</span>,
}));
jest.mock('../../../components/ui/avatar', () => ({
  Avatar: ({ children }) => <div>{children}</div>,
  AvatarFallback: ({ children }) => <div>{children}</div>,
  AvatarImage: () => <img alt="" />,
}));
jest.mock('../../../components/ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../../components/ui/textarea', () => ({
  Textarea: (p) => <textarea {...p} />,
}));
jest.mock('canvas-confetti', () => jest.fn());
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
  NassaqAlertDialog: () => null,
}));
jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
  toHijri: () => ({ year: 1446, month: 12, day: 1 }),
}));
jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

// ── Timer hook ───────────────────────────────────────────────────────────────
jest.mock('../../../hooks/useSessionTimer', () => ({
  __esModule: true,
  default: () => ({ elapsed: 0, formatted: '00:00' }),
}), { virtual: true });

// ── API client ───────────────────────────────────────────────────────────────
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: mockApiPost,
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
};
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    api: mockApi,
    user: { id: 'teacher-1', role: 'teacher', tenant_id: 'school-1', preferred_language: 'ar' },
    isRTL: true,
  }),
}));

// Import after all mocks are registered
import SessionTeachPage from '../SessionTeachPage';

// ── Fixtures ──────────────────────────────────────────────────────────────────
const SESSION = {
  id: 'sess-1', status: 'in_progress', class_id: 'cls-1', school_id: 'school-1',
  teacher_id: 'teacher-1', date: '2026-07-06', start_time: new Date().toISOString(),
  stats: { questions_asked: 0, correct_answers: 0 }, interaction_mode: 'review',
};

const STUDENT = {
  id: 'stu-1', full_name: 'أحمد محمد', class_id: 'cls-1', is_active: true,
  attendance_status: 'present',
  interaction_count: 0, question_count: 0, eval_positive_count: 0, correct_answers: 0,
};

function setupDefaultMocks() {
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: [] });
    if (url === '/session/sess-1') return Promise.resolve({ data: SESSION });
    // loadStudents reads res.data.students (not a bare array)
    if (url === '/session/sess-1/students') return Promise.resolve({ data: { students: [STUDENT] } });
    if (url.startsWith('/classes/cls-1/students')) return Promise.resolve({ data: { students: [STUDENT] } });
    if (url === '/skills-types') return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/activity')) return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/undo')) return Promise.resolve({ data: { can_undo: false } });
    if (url.startsWith('/session/sess-1/settings')) return Promise.resolve({ data: {} });
    if (url.startsWith('/subjects')) return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/groups')) return Promise.resolve({ data: { groups: [] } });
    if (url.startsWith('/session/sess-1')) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: [] });
  });
}

const answerCalls = () =>
  mockApiPost.mock.calls.filter(([url]) => url === '/session/sess-1/answer');

// Select the one present student, then return the live "correct" evaluation
// button from the right action sidebar (re-queried fresh each time so a
// re-render can't leave us holding a stale node).
async function selectStudentAndGetCorrectBtn() {
  // The roster StudentRow is a <div role="button"> whose accessible name also
  // contains the avatar initial + inline action labels; a dialog elsewhere has
  // a plain <button> named exactly "أحمد محمد". Target the roster row (the DIV)
  // so we exercise handleStudentClick, not the dialog button.
  await waitFor(() => {
    const matches = screen.getAllByRole('button', { name: /أحمد محمد/ });
    expect(matches.some((el) => el.tagName === 'DIV')).toBe(true);
  }, { timeout: 4000 });
  const row = screen
    .getAllByRole('button', { name: /أحمد محمد/ })
    .find((el) => el.tagName === 'DIV');
  await act(async () => { fireEvent.click(row); });
  return screen.getByRole('button', { name: 'correct' });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAlert.nassaqError.mockClear();
  try { window.localStorage.clear(); } catch { /* no-op */ }
  // Answer endpoint: backend is the source of truth for the point breakdown.
  mockApiPost.mockImplementation((url) => {
    if (url === '/session/sess-1/answer') {
      return Promise.resolve({ data: { score_change: 5, base_points: 5, streak_bonus: 0 } });
    }
    return Promise.resolve({ data: {} });
  });
  mockApi.put.mockResolvedValue({ data: {} });
  mockApi.patch.mockResolvedValue({ data: {} });
  mockApi.delete.mockResolvedValue({ data: {} });
});


test('a rapid double-tap on "correct" fires exactly one answer submission', async () => {
  setupDefaultMocks();
  render(<SessionTeachPage />);

  const correctBtn = await selectStudentAndGetCorrectBtn();

  // Two taps in the same synchronous batch: the first sets answerLockRef before
  // its awaited POST resolves, so the second must be swallowed.
  await act(async () => {
    fireEvent.click(correctBtn);
    fireEvent.click(correctBtn);
  });

  expect(answerCalls()).toHaveLength(1);
});


test('a deliberate tap after the 600ms cooldown still registers a second submission', async () => {
  setupDefaultMocks();
  render(<SessionTeachPage />);

  const correctBtn = await selectStudentAndGetCorrectBtn();

  // Burst → one submission.
  await act(async () => {
    fireEvent.click(correctBtn);
    fireEvent.click(correctBtn);
  });
  expect(answerCalls()).toHaveLength(1);

  // Wait past the 600ms lock release (real timers), then tap deliberately.
  await act(async () => { await new Promise((r) => setTimeout(r, 700)); });

  const correctBtnAfter = screen.getByRole('button', { name: 'correct' });
  await act(async () => { fireEvent.click(correctBtnAfter); });

  await waitFor(() => {
    expect(answerCalls()).toHaveLength(2);
  }, { timeout: 3000 });
});
