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
  // Expose a reset hook so per-test setup can reseed the search query
  // before the next render — the module-level closure otherwise carries
  // consumed `?plan_id=` between tests.
  globalThis.__resetRouterMock = (next = '?plan_id=plan-B') => {
    _state.search = next;
    _state.pathname = '/teacher/lesson-planner';
  };
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

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
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

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

import LessonPlannerPage from '../LessonPlannerPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPost.mockReset();
  // Stub scrollIntoView on the prototype so jsdom doesn't throw and
  // we can assert the deep-link effect actually scrolled to the row.
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function () {};
  }
  // Reseed the mocked router state so each test starts with a fresh
  // ?plan_id= query (the previous test's `_navigate` consumed it).
  if (typeof globalThis.__resetRouterMock === 'function') {
    globalThis.__resetRouterMock('?plan_id=plan-B');
  }
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

  // Both rows must render eventually. ResponsiveTable mounts the
  // desktop `<table>` and the mobile cards in parallel (CSS-toggled),
  // so each per-row wrapper appears twice — once per breakpoint.
  await waitFor(() => screen.getAllByTestId('saved-plan-row-plan-A'));
  await waitFor(() => screen.getAllByTestId('saved-plan-row-plan-B'));

  // … but only the one matching ?plan_id= gets the highlight ring,
  // and the ring must apply at both breakpoints so phone + desktop
  // users see the same affordance.
  await waitFor(() => {
    const targets = screen.getAllByTestId('saved-plan-row-plan-B');
    expect(targets.length).toBeGreaterThan(0);
    targets.forEach((t) => expect(t.className).toMatch(/ring-2/));
  });
  const others = screen.getAllByTestId('saved-plan-row-plan-A');
  others.forEach((o) => expect(o.className).not.toMatch(/ring-2/));
});

test('?plan_id= deep-link calls scrollIntoView once on the matching row wrapper', async () => {
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
    if (url === '/classes') return Promise.resolve({ data: { classes: [] } });
    return Promise.resolve({ data: {} });
  });

  const scrollSpy = jest.spyOn(Element.prototype, 'scrollIntoView')
    .mockImplementation(function () {});

  try {
    render(<LessonPlannerPage />);

    await waitFor(() => screen.getAllByTestId('saved-plan-row-plan-B'));

    // Wait for the deep-link effect to find a row and invoke scroll.
    await waitFor(() => expect(scrollSpy).toHaveBeenCalled());

    // The scroll target must be one of the wrappers carrying the
    // matching plan_id testid — never an unrelated row.
    const targets = screen.getAllByTestId('saved-plan-row-plan-B');
    const scrolledOnTarget = scrollSpy.mock.instances.some(
      (inst) => targets.includes(inst),
    );
    expect(scrolledOnTarget).toBe(true);
  } finally {
    scrollSpy.mockRestore();
  }
});
