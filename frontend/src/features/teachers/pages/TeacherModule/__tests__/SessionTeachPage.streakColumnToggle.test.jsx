/**
 * كشف المتابعة — Excellence Score column (درجات التميز) visibility must track
 * the Excellence Reward (مكافأة التميز) toggle in Lesson Settings.
 *
 * Regression: SessionTeachPage passed a hardcoded `showStreakColumn` (always
 * true) to FollowupGradesTable instead of the live `streakBonusEnabled` state
 * hydrated from GET /session/{id}/settings. The column must be hidden when the
 * saved setting is false and shown when true (or absent — default enabled).
 *
 * Shared page: applies identically to School Teacher and Independent Teacher.
 * Harness mirrors SessionTeachPage.followupPersistence.test.jsx.
 */
import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ state: { sessionId: 'sess-1' } }),
}), { virtual: true });

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
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
  NassaqAlertDialog: () => null,
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

// Test double: surfaces the showStreakColumn prop as a DOM marker.
jest.mock('../../../components/teacher/FollowupGradesTable', () => ({
  __esModule: true,
  default: ({ showStreakColumn }) => (
    <div data-testid="followup-grades-table">
      {showStreakColumn ? <div data-testid="streak-column" /> : null}
    </div>
  ),
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
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../../components/ui/textarea', () => ({
  Textarea: (p) => <textarea {...p} />,
}));
jest.mock('canvas-confetti', () => jest.fn());
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

import SessionTeachPage from '../SessionTeachPage';

const SESSION = {
  id: 'sess-1', status: 'in_progress', class_id: 'cls-1', school_id: 'school-1',
  teacher_id: 'teacher-1', start_time: new Date().toISOString(),
  stats: { questions_asked: 0, correct_answers: 0 }, interaction_mode: 'review',
};
const STUDENTS = [{ id: 'stu-1', full_name: 'أحمد محمد', interaction_count: 0, correct_answers: 0 }];
const COLUMNS = [{ id: 'part', name: 'المشاركة', column_type: 'coursework', max_grade: 10, visible: true, order: 1 }];

// Mutable server-side settings record — flipped between tests / mid-test.
let serverSettings;

function setupApi() {
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: {} });
    if (url === '/session/sess-1') return Promise.resolve({ data: SESSION });
    if (url === '/session/sess-1/students') return Promise.resolve({ data: { students: STUDENTS } });
    if (url === '/session/sess-1/followup-record') return Promise.resolve({ data: { data: {}, absences: {} } });
    if (url === '/class/cls-1/grade-columns') return Promise.resolve({ data: COLUMNS });
    if (url === '/skills-types') return Promise.resolve({ data: [] });
    if (url === '/subjects') return Promise.resolve({ data: [] });
    if (url.endsWith('/groups')) return Promise.resolve({ data: [] });
    if (url.endsWith('/settings')) return Promise.resolve({ data: serverSettings });
    if (url.endsWith('/notes')) return Promise.resolve({ data: [] });
    if (url.endsWith('/undo/peek')) return Promise.resolve({ data: { can_undo: false } });
    if (url.endsWith('/activity')) return Promise.resolve({ data: [] });
    if (url.endsWith('/live-metrics')) return Promise.resolve({ data: {} });
    if (url.endsWith('/homework')) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockImplementation(() => Promise.resolve({ data: {} }));
}

async function flushMicrotasks() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
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

describe('SessionTeachPage — Excellence column tracks streak_bonus_enabled', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupApi();
  });

  test('column is shown when the saved setting is enabled (true)', async () => {
    serverSettings = { streak_bonus_enabled: true };
    await mountPage();
    await openFollowup();
    expect(screen.getByTestId('followup-grades-table')).toBeInTheDocument();
    expect(screen.getByTestId('streak-column')).toBeInTheDocument();
  });

  test('column is shown when the setting is absent (legacy default enabled)', async () => {
    serverSettings = {};
    await mountPage();
    await openFollowup();
    expect(screen.getByTestId('streak-column')).toBeInTheDocument();
  });

  test('column is HIDDEN when the saved setting is disabled (false)', async () => {
    serverSettings = { streak_bonus_enabled: false };
    await mountPage();
    await openFollowup();
    expect(screen.getByTestId('followup-grades-table')).toBeInTheDocument();
    expect(screen.queryByTestId('streak-column')).toBeNull();
  });
});
