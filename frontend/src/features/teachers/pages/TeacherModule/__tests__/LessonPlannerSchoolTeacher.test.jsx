/**
 * Task #1089 — the lesson-plan assistant (مساعد خطط الدروس), previously
 * Independent-Teacher only, is now available to regular school teachers.
 *
 * These tests pin the two FE contracts the widening depends on:
 *   1. The "مساعد خطط الدروس" tab renders in TeacherClassesPage for a
 *      role==='teacher' user (not just 'independent_teacher').
 *   2. The shared LessonPlannerPage panel requests the assignment-scoped
 *      class list (`assigned_only: true`) so a school teacher only sees
 *      their OWN classes in the picker, never the whole school.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => {
  const React2 = require('react');
  const params = new URLSearchParams('');
  return {
    useNavigate: () => jest.fn(),
    useLocation: () => ({ search: '', pathname: '/teacher/classes' }),
    useSearchParams: () => [params, jest.fn()],
    MemoryRouter: ({ children }) => React2.createElement(React2.Fragment, null, children),
  };
}, { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

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

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

jest.mock('../SessionsManageTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../StandbyTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({
  __esModule: true, default: () => <div />,
}));
// TeacherStudentsPanel / ITParentsPanel / BulkImportPanel pull the Hakim
// assistant → react-markdown (ESM) chain that CRA's jest transform does
// not compile, so stub them — this test only cares about the tab bar.
jest.mock('../TeacherStudentsPage', () => ({
  __esModule: true, default: () => <div />, TeacherStudentsPanel: () => <div />,
}));
jest.mock('../ITParentsPage', () => ({
  __esModule: true, default: () => <div />, ITParentsPanel: () => <div />,
}));
jest.mock('../BulkImportPage', () => ({
  __esModule: true, default: () => <div />, BulkImportPanel: () => <div />,
}));

const mockApiGet = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
};
let mockRole = 'teacher';
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    api: mockApi,
    user: { id: 'u-teacher-1', role: mockRole, preferred_language: 'ar' },
    isRTL: true,
  }),
}));

import TeacherClassesPage from '../TeacherClassesPage';
import LessonPlannerPage from '../LessonPlannerPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockRole = 'teacher';
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function () {};
  }
});

test('lesson-planner tab renders for a role=teacher school teacher', async () => {
  mockApiGet.mockImplementation(() => Promise.resolve({ data: [] }));
  render(<TeacherClassesPage />);
  await waitFor(() => {
    expect(
      screen.getByTestId('teacher-classes-lesson-planner-tab'),
    ).toBeInTheDocument();
  }, { timeout: 4000 });
});

test('panel requests the assignment-scoped class list for a school teacher', async () => {
  const ownClass = { id: 'own-1', name: 'صفّي', name_ar: 'صفّي' };
  mockApiGet.mockImplementation((url, config) => {
    if (url === '/independent-teacher/lesson-plans') {
      return Promise.resolve({
        data: { lesson_plans: [], quota: { used_today: 0, max_per_day: 20 } },
      });
    }
    if (url === '/classes') {
      // The panel MUST ask for the assignment-scoped list.
      expect(config && config.params && config.params.assigned_only).toBe(true);
      return Promise.resolve({ data: { classes: [ownClass] } });
    }
    return Promise.resolve({ data: {} });
  });

  render(<LessonPlannerPage />);

  await waitFor(() => {
    const call = mockApiGet.mock.calls.find((c) => c[0] === '/classes');
    expect(call).toBeTruthy();
    expect(call[1]).toEqual(
      expect.objectContaining({ params: { assigned_only: true } }),
    );
  }, { timeout: 4000 });
});
