/**
 * Regression — AI-Insights "رؤى الذكاء الاصطناعي" → "رادار المخاطر الطلابية"
 * (Student Risk Radar) deep-link.
 *
 * The radar links to `/teacher/students?student_id=<id>`. Its scope is WIDER
 * than this page's loaded roster (teacher_assignments ∪ teacher_class_assignments
 * for school teachers; the whole workspace pool incl. unassigned rows for IT),
 * so the deep-linked student is frequently absent from the loaded list. Before
 * the fix the page stranded the user on a generic roster and never opened the
 * clicked student. The deep-link effect now resolves the EXACT student via
 * `GET /students/{id}` when it is not in the loaded roster and opens that
 * student's detail dialog.
 *
 * Harness note: this is driven through the IT-workspace path (selectedClass
 * defaults to 'all' → a single `GET /students` roster load) because the React-18
 * act environment in this CRA / react-scripts-5 setup reliably drives that
 * single async mount round. The deep-link fallback under test is role-agnostic
 * — the same effect runs for school teachers, where the class-scoped roster is
 * the narrower list that triggers the same fallback.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '?student_id=stu-amir', pathname: '/teacher/students' }),
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

jest.mock('@/shared/models/utils/hijriDate', () => ({ formatHijriDate: () => 'hijri' }));

const mockTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => mockTranslation,
}));

jest.mock('../../../components/hakim/HakimAssistant', () => ({ HakimAssistant: () => <div /> }));
jest.mock('../../../components/wizards/AddStudentWizard', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const mockApiGet = jest.fn();
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockAuth = {
  api: mockApi,
  user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  isRTL: true,
};
jest.mock('@/shared/contexts/AuthContext', () => ({ useAuth: () => mockAuth }));

import TeacherStudentsPage from '../TeacherStudentsPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockAlert.nassaqError.mockReset();
});

test('deep-link opens the exact radar student even when absent from the loaded roster', async () => {
  // The loaded roster deliberately EXCLUDES the deep-linked student so the
  // in-roster fast path misses and the direct-fetch fallback must run.
  const roster = [
    { id: 'stu-ibrahim', full_name: 'إبراهيم الناصر', student_id: 'STU-001', is_active: true },
  ];
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: [] });
    if (url === '/students') return Promise.resolve({ data: roster });
    if (url === '/students/stu-amir') {
      return Promise.resolve({
        data: { id: 'stu-amir', full_name: 'أمير التميمي', student_id: 'STU-099', is_active: true },
      });
    }
    if (url === '/students/stu-amir/analytics') {
      return Promise.resolve({
        data: {
          attendance: { rate: 0 }, grades: { average: 0 },
          participation: {}, behavior: {}, skills: [],
        },
      });
    }
    if (url.startsWith('/teacher/classes/')) return Promise.resolve({ data: [] });
    if (url.startsWith('/independent-teacher/students/')) {
      return Promise.resolve({ data: { invitation: null } });
    }
    return Promise.resolve({ data: [] });
  });

  render(<TeacherStudentsPage />);

  // The fallback resolves the exact student by id…
  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/students/stu-amir');
  }, { timeout: 4000 });

  // …and opens that student's detail dialog (the dialog header renders
  // selectedStudent.full_name).
  await waitFor(() => {
    expect(screen.getByText('أمير التميمي')).toBeInTheDocument();
  }, { timeout: 4000 });

  // It must NOT silently strand the user: the unrelated roster student is not
  // what gets opened, and no error dialog is shown for a resolvable student.
  expect(mockAlert.nassaqError).not.toHaveBeenCalled();
});
