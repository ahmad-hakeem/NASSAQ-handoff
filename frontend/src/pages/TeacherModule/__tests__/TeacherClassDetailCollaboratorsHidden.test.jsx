/**
 * TeacherClassDetailPage — "المتعاونون عبر المساحات" (collaborators) tab
 * visibility (product decision 2026-07-29).
 *
 * The tab is temporarily hidden for school teachers (role `teacher`) and
 * independent teachers (role `independent_teacher`) — the only roles that
 * can reach /teacher/class/:classId. UI-only: the CollaboratorsTab
 * component, its endpoints, and data remain intact.
 *
 * Covers:
 *  - Independent teacher (host of class): tab button absent, other tabs render
 *  - School teacher (host of class): tab button absent, other tabs render
 *  - Deep link ?tab=collaborators: panel not rendered, falls back to curriculum
 *  - Role outside the hidden list (host): tab still renders (hide is
 *    role-scoped, not a blanket removal of the host-only feature)
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

let mockParams = new URLSearchParams('tab=curriculum');
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '', pathname: '/teacher/class/c1' }),
  useSearchParams: () => [mockParams, jest.fn()],
  useParams: () => ({ classId: 'c1' }),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
    nassaqInfo: jest.fn(),
  }),
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

// Stable module-level objects: `t` is a useCallback dep in the page
// (fetchClassData), so a fresh object per render loops the fetch effect.
const mockStableTheme = { isRTL: true };
const mockStableTranslation = { t: (k) => k, isRTL: true };
jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => mockStableTheme,
  useTranslation: () => mockStableTranslation,
}));

jest.mock('../../../components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => <div />,
}));
jest.mock('../../../components/hakim/HakimPresence', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../../../components/teacher/FollowupGradesTable', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../../../components/teacher/SidebarSettingsDialog', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../../../components/teacher/InlineAttendanceTable', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../../../components/teacher/CollaboratorsTab', () => ({
  __esModule: true,
  default: () => <div data-testid="collaborators-panel" />,
}));
jest.mock('../../../utils/apiError', () => ({
  getApiErrorMessage: (err) => err?.response?.data?.detail?.message || 'error',
}));

const mockApiGet = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
};

const mockAuth = {
  api: mockApi,
  user: {
    id: 'u1',
    role: 'independent_teacher',
    full_name: 'Test Teacher',
    tenant_id: 'tenant1',
  },
  isAuthenticated: true,
};

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

// school_id === user.tenant_id → the user is host of the class, which is
// the pre-existing condition for the collaborators tab to be eligible.
const CLASS_DATA = {
  id: 'c1',
  name: 'الصف الأول أ',
  school_id: 'tenant1',
  grade_id: '1',
  grade_name: 'الصف الأول',
  capacity: 20,
  current_students: 5,
  is_active: true,
};

function setupDefaultMocks() {
  mockApiGet.mockImplementation((url) => {
    if (url.includes('new-metadata')) return Promise.resolve({ data: {} });
    if (url.includes('curriculum-plan')) return Promise.resolve({ data: { lessons: [], total: 0, completed: 0, progress: 0 } });
    if (url.includes('/classes/c1')) return Promise.resolve({ data: CLASS_DATA });
    if (url.includes('grade-columns')) return Promise.resolve({ data: [] });
    if (url.includes('students')) return Promise.resolve({ data: [] });
    if (url.includes('session-settings')) return Promise.resolve({ data: [] });
    if (url.includes('lesson-plans')) return Promise.resolve({ data: { plans: [] } });
    return Promise.resolve({ data: {} });
  });
}

// eslint-disable-next-line import/first
import TeacherClassDetailPage from '../TeacherClassDetailPage';

async function renderPage() {
  render(<TeacherClassDetailPage />);
  // Wait until class data resolved so isHostOfClass is computed from real data
  await waitFor(() => expect(screen.getByText('الصف الأول أ')).toBeInTheDocument());
}

beforeEach(() => {
  jest.clearAllMocks();
  setupDefaultMocks();
  mockParams = new URLSearchParams('tab=curriculum');
});

describe('Collaborators tab hidden for teacher roles', () => {
  test('independent teacher (host) does not see the collaborators tab', async () => {
    mockAuth.user.role = 'independent_teacher';
    await renderPage();

    expect(screen.queryByText('collabTabTitle')).not.toBeInTheDocument();
    // Other tabs unaffected
    expect(screen.getByText('curriculumPlan')).toBeInTheDocument();
    expect(screen.getByText('studentRecords')).toBeInTheDocument();
    expect(screen.getByText('attendanceLog')).toBeInTheDocument();
  });

  test('school teacher (host) does not see the collaborators tab', async () => {
    mockAuth.user.role = 'teacher';
    await renderPage();

    expect(screen.queryByText('collabTabTitle')).not.toBeInTheDocument();
    expect(screen.getByText('curriculumPlan')).toBeInTheDocument();
    expect(screen.getByText('studentRecords')).toBeInTheDocument();
    expect(screen.getByText('attendanceLog')).toBeInTheDocument();
  });

  test('deep link ?tab=collaborators does not render the panel and falls back to curriculum', async () => {
    mockAuth.user.role = 'independent_teacher';
    mockParams = new URLSearchParams('tab=collaborators');
    await renderPage();

    expect(screen.queryByTestId('collaborators-panel')).not.toBeInTheDocument();
    // Fallback: curriculum tab content is fetched/rendered instead
    await waitFor(() => {
      expect(mockApiGet.mock.calls.some(([url]) => url.includes('curriculum-plan'))).toBe(true);
    });
  });

  test('hide is role-scoped: a host user with a non-hidden role still sees the tab', async () => {
    mockAuth.user.role = 'school_principal';
    await renderPage();

    expect(screen.getByText('collabTabTitle')).toBeInTheDocument();
  });
});
