/**
 * Regression guard — teacher dashboard request fan-out.
 *
 * The Hakim "class health / risk alerts" card was hidden behind `false &&`
 * but its data-fetching effect was left running. On every load of the teacher
 * dashboard it issued, for C classes and S students:
 *
 *   C × GET /hakim/class/{id}/health
 *   C × GET /classes/{id}/students
 *   S × GET /hakim/student/{id}/risk      (S only known AFTER stage 2)
 *
 * — three sequential stages, ~110 requests / 6 MB / 1.7 min on a real teacher
 * account, to populate a card that could never render.
 *
 * These tests pin the invariant: while the card is hidden, the dashboard must
 * not issue ANY per-class or per-student Hakim request. If someone re-enables
 * the card, they must replace the fan-out with a single batched endpoint —
 * flipping the flag alone will fail this suite.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('../../../components/teacher/ReactivationBanner', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/teacher/OnboardingTour/OnboardingTrigger', () => ({
  __esModule: true, default: () => <div />,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatFullDate: () => ({ gregorian: 'g', hijri: 'h', weekday: 'w' }),
  formatHijriDate: () => 'hijri',
}));

jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const mockApiGet = jest.fn();
// Stable module-level identities: a fresh `api`/`user` object on every render
// would retrigger the useCallback-dep fetch effects and mask the very thing
// this test measures.
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockUser = {
  id: 'u-teacher-1',
  teacher_id: 't-1',
  role: 'teacher',
  tenant_id: 'school-1',
  preferred_language: 'ar',
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockApi, user: mockUser, isRTL: true }),
}));

import TeacherMainDashboard from '../TeacherMainDashboard';

const CLASSES = [
  { id: 'c-1', name: 'أول/1', students: 30 },
  { id: 'c-2', name: 'أول/2', students: 30 },
  { id: 'c-3', name: 'ثاني/1', students: 30 },
];

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url.startsWith('/teacher/dashboard/')) {
      return Promise.resolve({
        data: {
          stats: {
            my_classes: CLASSES.length,
            my_students: 90,
            today_lessons: 0,
            pending_attendance: 0,
            weekly_sessions: 0,
            subjects_count: 0,
          },
          classes: CLASSES,
          today_schedule: [],
          recent_activities: [],
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function () {};
  }
});

const urlsCalled = () => mockApiGet.mock.calls.map((c) => String(c[0]));

test('hidden Hakim card issues no per-class or per-student requests', async () => {
  render(<TeacherMainDashboard />);

  // Non-vacuity guard: wait until the dashboard payload has actually been
  // applied to state. `classes` is set in the same batch as these stats, so
  // once they render the Hakim effect has had its chance to run.
  await waitFor(() => {
    expect(
      mockApiGet.mock.calls.some((c) => String(c[0]).startsWith('/teacher/dashboard/')),
    ).toBe(true);
  }, { timeout: 4000 });
  await screen.findByText(String(CLASSES.length), {}, { timeout: 4000 });

  // Let any chained effect round flush before asserting the absence.
  await waitFor(() => new Promise((r) => setTimeout(r, 0)));

  expect(urlsCalled().filter((u) => u.includes('/hakim/'))).toEqual([]);
  expect(urlsCalled().filter((u) => /^\/classes\/[^/]+\/students/.test(u))).toEqual([]);
});

test('dashboard load stays within a small, bounded request budget', async () => {
  render(<TeacherMainDashboard />);

  await waitFor(() => {
    expect(
      mockApiGet.mock.calls.some((c) => String(c[0]).startsWith('/teacher/dashboard/')),
    ).toBe(true);
  }, { timeout: 4000 });
  await screen.findByText(String(CLASSES.length), {}, { timeout: 4000 });
  await waitFor(() => new Promise((r) => setTimeout(r, 0)));

  // Before the fix this was C + C + S (~110) on a real account. The dashboard
  // now issues only its own fixed set of aggregate calls; the budget is
  // deliberately tight so a new per-item fan-out trips it.
  expect(mockApiGet.mock.calls.length).toBeLessThanOrEqual(6);
});
