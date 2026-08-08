/**
 * "فصولي" class-card actions contract.
 *
 * The third card action used to be "تقارير" and navigated to the
 * school-wide /ai-insights page — it carried no class context, so from a
 * class card it was a dead end. It is now "خطة المنهج", deep-linking into
 * the curriculum tab of THAT class. The other two actions must keep their
 * own destinations: طلاب → the class student records, الحضور → the
 * attendance page scoped to the class.
 *
 * Both teacher roles render the same card, so the mapping is asserted for
 * the independent teacher and the school teacher.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => {
  const params = new URLSearchParams('');
  return {
    useNavigate: () => mockNavigate,
    useLocation: () => ({ search: '', pathname: '/teacher/classes' }),
    useSearchParams: () => [params, jest.fn()],
  };
}, { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

// Module-level (stable) alert object: returning a fresh one per call changes
// the identity of `nassaqError`, which is a dep of the fetchClasses
// useCallback — the page would refetch forever and never leave "loading".
const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
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

jest.mock('../SessionsManageTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../StandbyTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({
  __esModule: true, default: () => <div />,
}));

const mockApiGet = jest.fn();
// Stable module-level api/user objects: fresh ones per call re-fire the
// useCallback fetch effects and the page never settles.
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockAuth = {
  api: mockApi,
  user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  isRTL: true,
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import TeacherClassesPage from '../TeacherClassesPage';

const CLASSES = [
  {
    id: 'c1', name: 'الفصل الأول', grade_name: 'الصف الأول', grade_level: '1',
    subjects: ['رياضيات'], student_count: 12, attendance_rate: 92,
    next_session: null,
  },
  // A class with no students / no sessions: the actions must still be wired.
  {
    id: 'c2', name: 'فصل فارغ', grade_name: 'الصف الثاني', grade_level: '2',
    subjects: [], student_count: 0, attendance_rate: 0, next_session: null,
  },
];

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1280 });
  mockNavigate.mockReset();
  mockApiGet.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (typeof url === 'string'
        && (url === '/classes' || url.startsWith('/teacher/classes'))) {
      return Promise.resolve({ data: CLASSES });
    }
    if (typeof url === 'string' && url.includes('/class-metrics')) {
      return Promise.resolve({ data: {} });
    }
    if (typeof url === 'string' && url.includes('shared-with-me')) {
      return Promise.resolve({ data: { items: [] } });
    }
    return Promise.resolve({ data: [] });
  });
});

async function renderClasses(role) {
  mockAuth.user = { id: 'u-1', role, preferred_language: 'ar' };
  render(<TeacherClassesPage />);
  await waitFor(() => {
    expect(screen.getByTestId('class-card-curriculum-c1')).toBeInTheDocument();
  }, { timeout: 4000 });
}

describe.each([
  ['independent teacher', 'independent_teacher'],
  ['school teacher', 'teacher'],
])('class card actions — %s', (_label, role) => {
  test('خطة المنهج replaces تقارير and opens the class curriculum tab', async () => {
    await renderClasses(role);

    // The old reports action is gone from the card...
    expect(screen.queryByText('reports2')).not.toBeInTheDocument();
    // ...and every class exposes the curriculum plan instead.
    expect(screen.getByTestId('class-card-curriculum-c2')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('class-card-curriculum-c1'));
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/c1?tab=curriculum');

    // A class with no plan yet must still route to its own class, not a
    // shared/global page.
    mockNavigate.mockClear();
    fireEvent.click(screen.getByTestId('class-card-curriculum-c2'));
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/c2?tab=curriculum');
  });

  test('طلاب and الحضور open their own tab of the same class', async () => {
    await renderClasses(role);

    fireEvent.click(screen.getByTestId('class-card-students-c1'));
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/c1?tab=records');

    // الحضور must land on the attendance tab INSIDE the class page (class
    // context preserved), not the standalone /teacher/attendance screen.
    mockNavigate.mockClear();
    fireEvent.click(screen.getByTestId('class-card-attendance-c1'));
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/c1?tab=attendance');

    mockNavigate.mockClear();
    fireEvent.click(screen.getByTestId('class-card-attendance-c2'));
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/c2?tab=attendance');
  });

  test('the three actions sit side by side in one equal-width row', async () => {
    await renderClasses(role);

    const row = screen.getByTestId('class-card-students-c1').parentElement;
    expect(row).toHaveClass('grid', 'grid-cols-3');
    // All three actions share the same row element — no stacked/second row.
    expect(row).toContainElement(screen.getByTestId('class-card-attendance-c1'));
    expect(row).toContainElement(screen.getByTestId('class-card-curriculum-c1'));
  });
});
