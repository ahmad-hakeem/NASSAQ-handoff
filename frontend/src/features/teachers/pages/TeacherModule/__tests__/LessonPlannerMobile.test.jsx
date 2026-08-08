/**
 * Task #313 — LessonPlannerPage saved-plans mobile contract.
 *
 * At 360px wide the saved-plans list must render rows through the
 * shared ResponsiveTable mobile-cards branch (mirrors task #280 — audit
 * log + #303 — classes/students) instead of overflowing horizontally.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '', pathname: '/teacher/lesson-planner' }),
}), { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

const mockApiGet = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    api: { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() },
    user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  }),
}));

import LessonPlannerPage from '../LessonPlannerPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiGet.mockReset();
});

test('saved plans at 360px render the ResponsiveTable mobile cards with topic + actions', async () => {
  const lesson_plans = [
    {
      id: 'lp1', topic: 'مقدمة في الكسور', subject: 'رياضيات',
      grade_level: 'الرابع', duration_minutes: 45,
      plan: { title: 'درس الكسور البسيطة' },
    },
    {
      id: 'lp2', topic: 'دورة الماء', subject: 'علوم',
      grade_level: 'الخامس', duration_minutes: 30, plan: {},
    },
  ];
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/lesson-plans') {
      return Promise.resolve({ data: { lesson_plans, quota: null } });
    }
    if (url === '/classes') {
      return Promise.resolve({ data: { classes: [] } });
    }
    return Promise.resolve({ data: {} });
  });

  render(<LessonPlannerPage />);

  await waitFor(() => {
    expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  }, { timeout: 4000 });

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('مقدمة في الكسور');
  expect(mobile.textContent).toContain('دورة الماء');
  expect(mobile.textContent).toContain('درس الكسور البسيطة');

  const cards = mobile.querySelectorAll('li');
  expect(cards.length).toBe(2);
  // Action buttons render as a full-width block at the bottom of each
  // mobile card (mobileFullWidth column) — tap targets stay comfortable.
  expect(cards[0].textContent).toMatch(/تعديل/);
  expect(cards[0].textContent).toMatch(/حذف/);
});
