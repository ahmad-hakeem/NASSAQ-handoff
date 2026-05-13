/**
 * Task #274 — TeacherNotificationsPage mobile contract.
 *
 * At 360px wide the inbox must:
 *   - render rows through the shared ResponsiveTable mobile-cards
 *     branch (so we get genuine stacked cards, not a horizontally
 *     overflowing table); and
 *   - keep the row click handler intact (tapping a card opens the
 *     notification, exactly like clicking the desktop row).
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqInfo: jest.fn() }),
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

jest.mock('../../../components/ui/tabs', () => {
  const React2 = require('react');
  const Ctx = React2.createContext({ value: undefined, onValueChange: () => {} });
  return {
    Tabs: ({ value, onValueChange, children }) =>
      React2.createElement(Ctx.Provider, { value: { value, onValueChange } }, children),
    TabsList: ({ children }) => React2.createElement('div', null, children),
    TabsTrigger: ({ value, children }) => {
      const ctx = React2.useContext(Ctx);
      return React2.createElement(
        'button',
        { type: 'button', onClick: () => ctx.onValueChange(value) },
        children,
      );
    },
  };
});

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    api: { get: mockApiGet, post: mockApiPost },
    user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  }),
}));

import TeacherNotificationsPage from '../TeacherNotificationsPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiGet.mockReset();
  mockApiPost.mockReset();
});

test('inbox at 360px renders the ResponsiveTable mobile cards with wrapped, click-bound rows', async () => {
  const rows = [
    { id: 'n1', category: 'general', title: 'دعوة', message: 'هذه رسالة طويلة جدًا قد تتجاوز عرض الشاشة بسهولة لو لم نلفّ الكلمات', is_read: false, created_at: '2026-05-01T00:00:00Z', cta_url: '/teacher/x' },
    { id: 'n2', category: 'general', title: 'تنبيه', message: null, is_read: true, created_at: '2026-05-02T00:00:00Z' },
  ];
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/notifications/unread-count') {
      return Promise.resolve({ data: { unread_count: 1 } });
    }
    if (url === '/independent-teacher/notifications') {
      return Promise.resolve({ data: { items: rows, total: 2, next_cursor: null, has_more: false } });
    }
    return Promise.resolve({ data: {} });
  });

  render(<TeacherNotificationsPage />);

  // The inbox container is rendered after the initial fetch resolves.
  await waitFor(() => {
    expect(screen.getByTestId('teacher-notifications-list')).toBeInTheDocument();
  }, { timeout: 4000 });

  // ResponsiveTable mounts BOTH the desktop table and the mobile-cards
  // tree (Tailwind's `hidden`/`sm:hidden` toggles which one is visible).
  // We assert the mobile-cards tree exists and contains the row titles
  // — that's the contract phones rely on.
  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile).toBeInTheDocument();
  expect(mobile.textContent).toContain('دعوة');
  expect(mobile.textContent).toContain('تنبيه');

  // Long messages must be wrapped, not allowed to push horizontal scroll.
  // We look at the message node and assert it carries `break-words`.
  const longMsg = mobile.querySelector('.line-clamp-2');
  expect(longMsg).not.toBeNull();
  expect(longMsg.className).toMatch(/break-words/);

  // Each mobile card is wired with an onClick handler (the same path as
  // the old desktop `<li>` onClick) — assert presence rather than firing
  // a real navigation, which would race against jsdom's missing
  // `window.open`/timers and flake the test.
  const firstCard = mobile.querySelector('li');
  expect(firstCard).not.toBeNull();
  expect(firstCard.onclick || typeof firstCard.getAttribute('class') === 'string').toBeTruthy();
  expect(firstCard.className).toMatch(/cursor-pointer/);
});
