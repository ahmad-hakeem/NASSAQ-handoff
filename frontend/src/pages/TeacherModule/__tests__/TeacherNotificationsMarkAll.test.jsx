/**
 * Task #261 — pin the inbox-refresh contract for the IT
 * "تعليم الكل كمقروء" bulk action.
 *
 * After the bulk POST succeeds, the page MUST re-fetch the active
 * tab/filter so the visible list reflects the new server-side state.
 * In particular, on the "Unread" tab the list MUST become empty
 * instead of showing now-read rows.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
  }),
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

// Bypass Radix Tabs (which can be flaky under jsdom + React 19 with
// fireEvent.click) by rendering plain buttons that drive
// ``onValueChange`` synchronously. The behaviour under test is the
// page's refetch contract, not Radix.
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
  mockApiGet.mockReset();
  mockApiPost.mockReset();
});

test('mark-all on the Unread tab clears the visible list via a real refetch', async () => {
  // Mock the API with a tiny hand-rolled router so the page's calls
  // resolve in order:
  //   1. initial list (all tab)         → 2 unread rows
  //   2. unread-count                   → 2
  //   3. unread tab list                → 2 unread rows
  //   4. unread-count                   → 2
  //   5. POST /read-all                 → updated=2
  //   6. unread tab refetch (post-bulk) → 0 rows
  //   7. unread-count                   → 0
  const unreadRows = [
    { id: 'n1', category: 'general', title: 't1', message: 'm1', is_read: false, created_at: '2026-05-01T00:00:00Z' },
    { id: 'n2', category: 'general', title: 't2', message: 'm2', is_read: false, created_at: '2026-05-02T00:00:00Z' },
  ];

  mockApiGet.mockImplementation((url, opts) => {
    if (url === '/independent-teacher/notifications/unread-count') {
      // Return 0 only after read-all has fired.
      const after = mockApiPost.mock.calls.length > 0;
      return Promise.resolve({ data: { unread_count: after ? 0 : 2 } });
    }
    if (url === '/independent-teacher/notifications') {
      const isUnreadOnly = Boolean(opts?.params?.unread_only);
      const after = mockApiPost.mock.calls.length > 0;
      const items = isUnreadOnly && after ? [] : unreadRows;
      return Promise.resolve({
        data: { items, total: items.length, next_cursor: null, has_more: false },
      });
    }
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockResolvedValue({ data: { updated: 2 } });

  render(<TeacherNotificationsPage />);

  // Initial load: 2 rows visible on the All tab. Task #274 — the inbox
  // now mounts ResponsiveTable, which renders both the desktop table
  // and the mobile-cards tree (Tailwind toggles which is visible), so
  // each title appears more than once in the DOM.
  await waitFor(() => {
    expect(screen.getAllByText('t1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('t2').length).toBeGreaterThan(0);
  });

  // Switch to the Unread tab. Radix Tabs uses role=tab buttons; the
  // text node lives inside the trigger so we click the closest button.
  const unreadTab = screen.getByText('غير المقروء').closest('button');
  fireEvent.click(unreadTab);
  await waitFor(() => {
    const calls = mockApiGet.mock.calls.filter(
      ([url]) => url === '/independent-teacher/notifications',
    );
    expect(calls.some(([, opts]) => opts?.params?.unread_only === true)).toBe(true);
  });

  // Wait until the unread-count refresh enables the bulk-action button
  // (it is disabled when ``unread === 0``).
  const button = await screen.findByRole('button', { name: /تعليم الكل كمقروء/ });
  await waitFor(() => expect(button).not.toBeDisabled());

  fireEvent.click(button);

  // The page MUST hit /read-all and then refetch the unread list.
  await waitFor(() => {
    expect(mockApiPost).toHaveBeenCalledWith('/independent-teacher/notifications/read-all');
  });

  // The refetch of the list MUST have honoured the active tab+filter
  // (unread_only=true), not the stale initial values — and it MUST
  // have happened AFTER the POST so the empty server state lands.
  await waitFor(() => {
    const listCalls = mockApiGet.mock.calls.filter(
      ([url]) => url === '/independent-teacher/notifications',
    );
    const lastListCall = listCalls[listCalls.length - 1];
    expect(lastListCall[1]?.params?.unread_only).toBe(true);
    // The last list call must have been issued after POST resolved
    // (mock returns [] only once mockApiPost has been invoked).
    expect(mockApiPost.mock.calls.length).toBeGreaterThan(0);
  });

  // And the visible rows are gone.
  await waitFor(() => {
    expect(screen.queryByText('t1')).toBeNull();
    expect(screen.queryByText('t2')).toBeNull();
  });
});
