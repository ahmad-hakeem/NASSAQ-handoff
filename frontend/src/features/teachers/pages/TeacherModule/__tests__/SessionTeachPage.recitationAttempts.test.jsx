/**
 * Recitation attempts must respect the saved Session Settings value.
 *
 * Bug: the recitation (التسميع) popover rendered a hardcoded [1, 2, 3]
 * attempts selector, ignoring the `recitation_max_attempts` value the
 * teacher saved in Session Settings (خيارات الحصة). A teacher who set
 * "1 attempt" or "2 attempts" still saw 3 attempt options.
 *
 * Invariants covered:
 * - max_attempts = 1 → only attempt option "1" is offered.
 * - max_attempts = 2 → options "1" and "2" are offered, never "3".
 * - max_attempts = 3 → all three options are offered (regression guard).
 * - The default selected attempt stays within the allowed range.
 *
 * Both School Teacher and Independent Teacher share SessionTeachPage, so
 * these invariants cover both roles.
 */
import React from 'react';
import { render, screen, waitFor, act, fireEvent, within } from '@testing-library/react';

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

function setupMocks(maxAttempts) {
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: [] });
    if (url === '/session/sess-1') return Promise.resolve({ data: SESSION });
    if (url === '/session/sess-1/students') return Promise.resolve({ data: { students: [STUDENT] } });
    if (url.startsWith('/classes/cls-1/students')) return Promise.resolve({ data: { students: [STUDENT] } });
    if (url === '/skills-types') return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/activity')) return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/undo/peek')) {
      return Promise.resolve({
        data: { has_reversible: false, stack_depth: 0, event_type: null, student_id: null, student_name: null },
      });
    }
    if (url.startsWith('/session/sess-1/settings'))
      return Promise.resolve({ data: { recitation_enabled: true, recitation_max_attempts: maxAttempts } });
    if (url.startsWith('/subjects')) return Promise.resolve({ data: [] });
    if (url.startsWith('/session/sess-1/groups')) return Promise.resolve({ data: { groups: [] } });
    if (url.startsWith('/session/sess-1')) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: [] });
  });
  mockApiPost.mockImplementation(() => Promise.resolve({ data: { success: true } }));
}

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

// The recitation popover is a portal-rendered role="dialog" whose accessible
// name starts with the recitation title ("recitation — <student>", key-echo t()).
async function findRecitationDialog() {
  let dialog;
  await waitFor(() => {
    const dialogs = screen.getAllByRole('dialog');
    dialog = dialogs.find((d) => (d.getAttribute('aria-label') || '').startsWith('recitation'));
    expect(dialog).toBeTruthy();
  }, { timeout: 4000 });
  return dialog;
}

const attemptButtons = (dialog) =>
  within(dialog)
    .getAllByRole('button')
    .filter((b) => /^[0-9]+$/.test(b.textContent.trim()));

beforeEach(() => {
  jest.clearAllMocks();
  mockAlert.nassaqError.mockClear();
  try { window.localStorage.clear(); } catch { /* no-op */ }
  mockApi.put.mockResolvedValue({ data: {} });
  mockApi.patch.mockResolvedValue({ data: {} });
  mockApi.delete.mockResolvedValue({ data: {} });
});

test.each([
  [1, ['1']],
  [2, ['1', '2']],
  [3, ['1', '2', '3']],
])('recitation popover offers exactly the allowed attempts when max_attempts=%i', async (maxAttempts, expected) => {
  setupMocks(maxAttempts);
  render(<SessionTeachPage />);

  await selectStudentAndOpenRecitation();
  const dialog = await findRecitationDialog();

  await waitFor(() => {
    const labels = attemptButtons(dialog).map((b) => b.textContent.trim()).sort();
    expect(labels).toEqual(expected);
  }, { timeout: 3000 });
});

test('default selected attempt stays within the allowed range (max_attempts=1)', async () => {
  setupMocks(1);
  render(<SessionTeachPage />);

  await selectStudentAndOpenRecitation();
  const dialog = await findRecitationDialog();

  const buttons = attemptButtons(dialog);
  expect(buttons).toHaveLength(1);
  // The lone option must be the selected one (selected style is emerald).
  expect(buttons[0].className).toContain('bg-emerald-600');
});

test('recorded recitation sends an attempts value within the allowed range', async () => {
  setupMocks(2);
  render(<SessionTeachPage />);

  await selectStudentAndOpenRecitation();
  const dialog = await findRecitationDialog();

  // Pick attempt 2 (the max) then record a mastered recitation.
  const two = attemptButtons(dialog).find((b) => b.textContent.trim() === '2');
  expect(two).toBeTruthy();
  await act(async () => { fireEvent.click(two); });

  const mastered = within(dialog).getByRole('button', { name: /recitationMastered/ });
  await act(async () => { fireEvent.click(mastered); });

  const call = mockApiPost.mock.calls.find(([url]) => url === '/session/sess-1/recitation');
  expect(call).toBeTruthy();
  expect(call[1].attempts).toBe(2);
});
