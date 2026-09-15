/**
 * TeacherClassDetailPage — attendance tab continuation link.
 *
 * The "الحضور" action on the فصولي class card now opens this in-class tab
 * (?tab=attendance) instead of the standalone /teacher/attendance page. The
 * inline table only records TODAY's present/absent, so the tab must keep an
 * explicit way through to the full workflow (date picker, late/excused,
 * mark-all-present, notes) with the class preselected.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const mockNavigate = jest.fn();
let mockParams = new URLSearchParams('tab=attendance');
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ search: '', pathname: '/teacher/class/c1' }),
  useSearchParams: () => [mockParams, jest.fn()],
  useParams: () => ({ classId: 'c1' }),
}), { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
    nassaqInfo: jest.fn(),
  }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

// Stable module-level objects: `t` is a useCallback dep in the page, so a
// fresh object per render loops the fetch effect.
const mockStableTheme = { isRTL: true };
const mockStableTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => mockStableTheme,
  useTranslation: () => mockStableTranslation,
}));

jest.mock('@/features/hakim/components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => <div />,
}));
jest.mock('@/features/hakim/components/hakim/HakimPresence', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/FollowupGradesTable', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => ({
  __esModule: true,
  default: () => <div data-testid="inline-attendance" />,
}));
jest.mock('@/features/teachers/components/teacher/CollaboratorsTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/shared/models/utils/apiError', () => ({
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
  user: { id: 'u1', role: 'independent_teacher', full_name: 'Test Teacher', tenant_id: 'tenant1' },
  isAuthenticated: true,
};

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const CLASS_DATA = {
  id: 'c1',
  name: 'الصف الأول أ',
  school_id: 'tenant1',
  grade_id: '1',
  grade_name: 'الصف الأول',
  current_students: 5,
  is_active: true,
};

beforeEach(() => {
  jest.clearAllMocks();
  mockParams = new URLSearchParams('tab=attendance');
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
});

// eslint-disable-next-line import/first
import TeacherClassDetailPage from '../TeacherClassDetailPage';

describe.each([
  ['independent teacher', 'independent_teacher'],
  ['school teacher', 'teacher'],
])('attendance tab continuation link — %s', (_label, role) => {
  test('offers the full attendance workflow for this class', async () => {
    mockAuth.user.role = role;
    render(<TeacherClassDetailPage />);
    await waitFor(() => expect(screen.getByText('الصف الأول أ')).toBeInTheDocument());

    // The in-class table is what the card action lands on...
    expect(screen.getByTestId('inline-attendance')).toBeInTheDocument();

    // ...and the date/status/bulk workflow stays one click away, class-scoped.
    fireEvent.click(screen.getByTestId('class-attendance-open-full'));
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/attendance?class=c1');
  });
});
