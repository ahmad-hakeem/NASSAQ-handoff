/**
 * Recitation → Undo activation regression tests.
 *
 * Bug: when recitation (التسميع) is the FIRST action recorded in a lesson,
 * the "تراجع عن آخر إجراء" button stayed disabled. The backend already
 * records recitation as a reversible event (RECITATION_RECORDED is in
 * REVERSIBLE_EVENT_TYPES and /undo/peek counts it), but recordRecitation
 * was the only action handler that did not update the undo state
 * (setCanUndo(true) + peekUndoState()) after a successful save — every
 * sibling handler (answer / participation / behaviour / skill) does.
 *
 * Invariants covered:
 * - After a successful mastered recitation as the first action, the undo
 *   button becomes enabled without any further action.
 * - Same for a not-mastered recitation.
 * - The undo state is re-synced from the server (/undo/peek is fetched
 *   after the POST), keeping the counter accurate from the first event.
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
jest.mock('@/shared/components/SectionErrorBoundary', () => ({
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
jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
  toHijri: () => ({ year: 1446, month: 12, day: 1 }),
}));
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

// ── Timer hook ───────────────────────────────────────────────────────────────
jest.mock('@/shared/hooks/useSessionTimer', () => ({
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
jest.mock('@/shared/contexts/AuthContext', () => ({
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
  teacher_id: 'teacher-1', date: '2026-07-11', start_time: new Date().toISOString(),
  stats: { questions_asked: 0, correct_answers: 0 }, interaction_mode: 'review',
};

const STUDENT = {
  id: 'stu-1', full_name: 'أحمد محمد', class_id: 'cls-1', is_active: true,
  attendance_status: 'present',
  interaction_count: 0, question_count: 0, eval_positive_count: 0, correct_answers: 0,
};

// Server-side reversible-stack simulation: every recorded recitation bumps
// the stack, exactly as the real backend does (RECITATION_RECORDED is a
// REVERSIBLE_EVENT_TYPE and /undo/peek counts it).
let reversibleStack;

function setupDefaultMocks() {
  reversibleStack = 0;
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: [] });
    if (url === '/session/sess-1') return Promise.resolve({ data: SESSION });
    if (url === '/session/sess-1/students') return Promise.resolve({ data: { students: [STUDENT] } });
    if (url.startsWith('/classes/cls-1/students')) return Promise.resolve({ data: { students: [STUDENT] } });
    if (url === '/skills-types') return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/activity')) return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/undo/peek')) {
      const has = reversibleStack > 0;
      return Promise.resolve({
        data: has
          ? { has_reversible: true, stack_depth: reversibleStack, event_type: 'recitation_recorded', student_id: 'stu-1', student_name: 'أحمد محمد' }
          : { has_reversible: false, stack_depth: 0, event_type: null, student_id: null, student_name: null },
      });
    }
    if (url.startsWith('/session/sess-1/settings'))
      return Promise.resolve({ data: { recitation_enabled: true, recitation_max_attempts: 3 } });
    if (url.startsWith('/subjects')) return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/groups')) return Promise.resolve({ data: { groups: [] } });
    if (url.startsWith('/session/sess-1')) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: [] });
  });
  mockApiPost.mockImplementation((url) => {
    if (url === '/session/sess-1/recitation') {
      reversibleStack += 1;
      return Promise.resolve({ data: { success: true } });
    }
    return Promise.resolve({ data: {} });
  });
}

const recitationCalls = () =>
  mockApiPost.mock.calls.filter(([url]) => url === '/session/sess-1/recitation');

const undoButton = () => screen.getByRole('button', { name: 'undoLastAction' });

// Select the one present student (roster row is a <div role="button">), then
// open the recitation popover from the right action sidebar.
async function selectStudentAndOpenRecitation() {
  await waitFor(() => {
    const matches = screen.getAllByRole('button', { name: /أحمد محمد/ });
    expect(matches.some((el) => el.tagName === 'DIV')).toBe(true);
  }, { timeout: 4000 });
  const row = screen
    .getAllByRole('button', { name: /أحمد محمد/ })
    .find((el) => el.tagName === 'DIV');
  await act(async () => { fireEvent.click(row); });

  // The sidebar recitation trigger only renders when recitation_enabled is on.
  // Selecting a student also reveals an inline row action named "recitation",
  // so disambiguate via the popover trigger's aria-haspopup attribute.
  await waitFor(() => {
    const triggers = screen
      .getAllByRole('button', { name: 'recitation' })
      .filter((el) => el.getAttribute('aria-haspopup') === 'dialog');
    expect(triggers).toHaveLength(1);
  }, { timeout: 4000 });
  const trigger = screen
    .getAllByRole('button', { name: 'recitation' })
    .find((el) => el.getAttribute('aria-haspopup') === 'dialog');
  await act(async () => { fireEvent.click(trigger); });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAlert.nassaqError.mockClear();
  try { window.localStorage.clear(); } catch { /* no-op */ }
  mockApi.put.mockResolvedValue({ data: {} });
  mockApi.patch.mockResolvedValue({ data: {} });
  mockApi.delete.mockResolvedValue({ data: {} });
});

test.each([
  ['mastered', 'recitationMastered'],
  ['not mastered', 'recitationNotMastered'],
])('undo activates immediately when the first action is a %s recitation', async (_label, buttonName) => {
  setupDefaultMocks();
  render(<SessionTeachPage />);

  await selectStudentAndOpenRecitation();

  // Sanity: before any action the undo button is disabled.
  expect(undoButton()).toBeDisabled();

  const outcomeBtn = await screen.findByRole('button', { name: buttonName });
  await act(async () => { fireEvent.click(outcomeBtn); });

  // The recitation was recorded…
  expect(recitationCalls()).toHaveLength(1);
  expect(mockAlert.nassaqError).not.toHaveBeenCalled();

  // …so the undo button must become enabled without any further action.
  await waitFor(() => {
    expect(undoButton()).toBeEnabled();
  }, { timeout: 3000 });
});

test('undo state is re-synced from the server after a recitation (peek fetched post-save)', async () => {
  setupDefaultMocks();
  render(<SessionTeachPage />);

  await selectStudentAndOpenRecitation();

  const peeksBefore = mockApiGet.mock.calls.filter(([url]) =>
    typeof url === 'string' && url.startsWith('/session/sess-1/undo/peek')).length;

  const outcomeBtn = await screen.findByRole('button', { name: 'recitationMastered' });
  await act(async () => { fireEvent.click(outcomeBtn); });
  expect(recitationCalls()).toHaveLength(1);

  await waitFor(() => {
    const peeksAfter = mockApiGet.mock.calls.filter(([url]) =>
      typeof url === 'string' && url.startsWith('/session/sess-1/undo/peek')).length;
    expect(peeksAfter).toBeGreaterThan(peeksBefore);
  }, { timeout: 3000 });
});
