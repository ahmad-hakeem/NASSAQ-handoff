/**
 * Task #303 — TeacherStudentsPage mobile contract.
 *
 * At 360px wide the students list must render rows through the shared
 * ResponsiveTable adaptor (mirrors task #280 — notifications + audit
 * log). The rich student card body is preserved as the primary column,
 * so the mobile-cards branch wraps each row as a tappable card with
 * chips, action buttons, and edit/delete CTAs intact.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '', pathname: '/teacher/students' }),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

const mockTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => mockTranslation,
}));

jest.mock('../../../components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => <div />,
}));

jest.mock('../../../components/wizards/AddStudentWizard', () => ({
  __esModule: true, default: () => <div />,
}));

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const mockApiGet = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
};
const mockAuth = {
  api: mockApi,
  user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  isRTL: true,
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import TeacherStudentsPage from '../TeacherStudentsPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiGet.mockReset();
});

test('students list at 360px renders the ResponsiveTable mobile cards branch', async () => {
  const students = [
    {
      id: 's1', full_name: 'فاطمة الزهراء', student_id: 'STU-001',
      attendance_rate: 95, average_grade: 88, behavior_points: 12,
      parent_id: 'p1', parent_name: 'والد فاطمة',
    },
    {
      id: 's2', full_name: 'محمد أحمد', student_id: 'STU-002',
      attendance_rate: 80, average_grade: 72, behavior_points: 5,
      parent_id: null,
    },
  ];
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: [] });
    if (url === '/students') return Promise.resolve({ data: students });
    if (url.startsWith('/teacher/classes/')) {
      return Promise.resolve({ data: [{ id: 'cls-1', name: 'الفصل', grade_name: 'الأول' }] });
    }
    if (url.startsWith('/classes/cls-1/students')) {
      return Promise.resolve({ data: students });
    }
    if (url.startsWith('/classes/cls-1/student-stats')) {
      return Promise.resolve({ data: {} });
    }
    if (url.startsWith('/independent-teacher/students/')) {
      return Promise.resolve({ data: { invitation: null } });
    }
    if (url.startsWith('/grade-levels')) return Promise.resolve({ data: [] });
    if (url.startsWith('/classes')) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });

  render(<TeacherStudentsPage />);

  await waitFor(() => {
    expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  }, { timeout: 4000 });

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('فاطمة الزهراء');
  expect(mobile.textContent).toContain('محمد أحمد');

  // The student card preserves the per-row data-testid so existing
  // selectors keep working through the migration.
  expect(mobile.querySelector('[data-testid="student-card-s1"]')).not.toBeNull();
  expect(mobile.querySelector('[data-testid="student-card-s2"]')).not.toBeNull();
});

const renderWithApi = async () => {
  const students = [
    { id: 's1', full_name: 'فاطمة الزهراء', student_id: 'STU-001',
      attendance_rate: 95, average_grade: 88, behavior_points: 12,
      parent_id: 'p1', parent_name: 'والد فاطمة' },
    { id: 's2', full_name: 'محمد أحمد', student_id: 'STU-002',
      attendance_rate: 80, average_grade: 72, behavior_points: 5,
      parent_id: null },
  ];
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: [] });
    if (url === '/students') return Promise.resolve({ data: students });
    if (url.startsWith('/teacher/classes/')) {
      return Promise.resolve({ data: [{ id: 'cls-1', name: 'الفصل', grade_name: 'الأول' }] });
    }
    if (url.startsWith('/classes/cls-1/students')) return Promise.resolve({ data: students });
    if (url.startsWith('/classes/cls-1/student-stats')) return Promise.resolve({ data: {} });
    if (url.startsWith('/independent-teacher/students/')) return Promise.resolve({ data: { invitation: null } });
    if (url.startsWith('/grade-levels')) return Promise.resolve({ data: [] });
    if (url.startsWith('/classes')) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });
  render(<TeacherStudentsPage />);
  await waitFor(() => {
    expect(screen.getAllByTestId(/^student-card-/).length).toBeGreaterThan(0);
  }, { timeout: 4000 });
};

test('students list at 768px renders the ResponsiveTable desktop grid path', async () => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 768 });
  await renderWithApi();
  // Adaptor's `desktopMode="grid"` branch — single render path, no
  // hand-rolled fallback grid.
  const grid = screen.getByTestId('responsive-table-grid');
  expect(grid.className).toMatch(/md:grid-cols-2/);
  expect(grid.className).toMatch(/lg:grid-cols-3/);
  expect(grid.className).toMatch(/xl:grid-cols-4/);
  expect(grid.querySelector('[data-testid="student-card-s1"]')).not.toBeNull();
});

test('students list at 1024px renders the ResponsiveTable desktop grid path', async () => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
  await renderWithApi();
  const grid = screen.getByTestId('responsive-table-grid');
  expect(grid.className).toMatch(/lg:grid-cols-3/);
  expect(grid.querySelector('[data-testid="student-card-s2"]')).not.toBeNull();
});
