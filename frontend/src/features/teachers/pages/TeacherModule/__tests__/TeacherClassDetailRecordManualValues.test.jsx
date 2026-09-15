/**
 * TeacherClassDetailPage — Student Record (سجل الطلاب) tab must render
 * check (تحقق) / text (نص) column values entered during the live lesson.
 *
 * Regression: those values are never materialized into the numeric
 * student_grades aggregation (by design — the record AVG casts score::float),
 * so the class page showed the cells permanently empty after the session
 * ended. GET /class/{id}/student-grades now surfaces them raw under
 * `manual_values` (read from the followup_records blob) and the page merges
 * them into the same cell map the sheet renders from.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

const mockNavigate = jest.fn();
let mockParams = new URLSearchParams('tab=records');
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
// Keep the REAL FollowupGradesTable — the assertion is that the merged
// manual values reach its rendered cells.
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => ({ __esModule: true, default: () => <div /> }));
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
  current_students: 1,
  is_active: true,
};

const GRADE_COLUMNS = [
  { id: 'col-grade', name: 'المشاركة', column_type: 'coursework', input_type: 'grade', max_grade: 5, order: 1, visible: true },
  { id: 'col-text', name: 'عمود نص', column_type: 'coursework', input_type: 'text', max_grade: 10, order: 2, visible: true },
  { id: 'col-check', name: 'عمود تحقق', column_type: 'coursework', input_type: 'check', max_grade: 10, order: 3, visible: true },
];

beforeEach(() => {
  jest.clearAllMocks();
  mockParams = new URLSearchParams('tab=records');
  mockApiGet.mockImplementation((url) => {
    if (url.includes('new-metadata')) return Promise.resolve({ data: {} });
    if (url.includes('curriculum-plan')) return Promise.resolve({ data: { lessons: [], total: 0, completed: 0, progress: 0 } });
    if (url.includes('/class/c1/subjects')) {
      return Promise.resolve({ data: { subjects: [{ id: 'sub1', name: 'الفيزياء' }], default_subject_id: 'sub1' } });
    }
    if (url.includes('student-grades')) {
      return Promise.resolve({
        data: {
          class_id: 'c1',
          subject_id: 'sub1',
          grades: [
            { student_id: 's1', column_id: 'col-grade', score: 4, sessions: 1 },
          ],
          manual_values: [
            { student_id: 's1', column_id: 'col-text', value: 'test' },
            { student_id: 's1', column_id: 'col-check', value: 1 },
          ],
        },
      });
    }
    if (url.includes('grade-columns')) return Promise.resolve({ data: GRADE_COLUMNS });
    if (url.includes('/classes/c1/students')) {
      return Promise.resolve({ data: [{ id: 's1', full_name: 'أنس العتيبي', is_active: true }] });
    }
    if (url.includes('/classes/c1')) return Promise.resolve({ data: CLASS_DATA });
    if (url.includes('session-settings')) return Promise.resolve({ data: [] });
    if (url.includes('lesson-plans')) return Promise.resolve({ data: { plans: [] } });
    return Promise.resolve({ data: {} });
  });
});

// eslint-disable-next-line import/first
import TeacherClassDetailPage from '../TeacherClassDetailPage';

test('record tab renders text + check values entered during the lesson', async () => {
  render(<TeacherClassDetailPage />);

  // Sheet loaded (student row present).
  await waitFor(() => {
    expect(screen.getAllByText('أنس العتيبي').length).toBeGreaterThan(0);
  });

  // Text column cell shows the saved string (desktop + mobile branches may
  // both mount — assert at least one carries the value).
  await waitFor(() => {
    const textInputs = screen.getAllByDisplayValue('test');
    expect(textInputs.length).toBeGreaterThan(0);
  });

  // Check column cell renders checked.
  const checkboxes = screen.getAllByRole('checkbox');
  expect(checkboxes.some((c) => c.checked)).toBe(true);

  // Numeric grade still hydrates from the aggregation.
  expect(screen.getAllByDisplayValue('4').length).toBeGreaterThan(0);
});
