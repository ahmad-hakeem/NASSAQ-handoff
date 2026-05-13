/**
 * Task #251 — deep-link verification for the lesson-planner page.
 *
 * When the IT command palette navigates the user to
 *   /teacher/lesson-planner?plan_id=<id>
 * the saved-plan row that matches the id MUST receive a brief
 * highlight ring, and the URL must be cleaned of the ?plan_id query
 * after consumption (so a refresh doesn't replay the highlight).
 *
 * This test pins the contract that backend search hrefs actually
 * resolve to a visible affordance — not just a no-op param.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => {
  const React2 = require('react');
  const _state = { search: '?plan_id=plan-B', pathname: '/teacher/lesson-planner' };
  return {
    useLocation: () => _state,
    useNavigate: () => (next) => {
      if (typeof next === 'object' && next) {
        if ('search' in next) _state.search = next.search;
        if ('pathname' in next) _state.pathname = next.pathname;
      }
    },
    MemoryRouter: ({ children }) => React2.createElement(React2.Fragment, null, children),
  };
}, { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div>{children}</div>,
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    api: { get: mockApiGet, post: mockApiPost },
    user: { id: 'u-it-1', role: 'independent_teacher' },
  }),
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

import LessonPlannerPage from '../LessonPlannerPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPost.mockReset();
});

test('?plan_id= deep-link applies the highlight ring to the matching saved-plan row', async () => {
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/lesson-plans') {
      return Promise.resolve({
        data: {
          lesson_plans: [
            { id: 'plan-A', topic: 'الكسور', subject: 'رياضيات', plan: { title: 'الكسور' } },
            { id: 'plan-B', topic: 'الجبر', subject: 'رياضيات', plan: { title: 'الجبر' } },
          ],
          quota: { used_today: 0, max_per_day: 20 },
        },
      });
    }
    if (url === '/classes') {
      return Promise.resolve({ data: { classes: [] } });
    }
    return Promise.resolve({ data: {} });
  });

  render(<LessonPlannerPage />);

  // Both rows must render eventually …
  await waitFor(() => screen.getByTestId('saved-plan-row-plan-A'));
  await waitFor(() => screen.getByTestId('saved-plan-row-plan-B'));

  // … but only the one matching ?plan_id= gets the highlight ring.
  await waitFor(() => {
    const target = screen.getByTestId('saved-plan-row-plan-B');
    expect(target.className).toMatch(/ring-2/);
  });
  const other = screen.getByTestId('saved-plan-row-plan-A');
  expect(other.className).not.toMatch(/ring-2/);
});
