/**
 * Notification quick-preview upgrade — IT inbox contract.
 *
 * Opening a row in the Independent-Teacher notifications inbox must:
 *   - open the in-place NotificationDetailDialog with the FULL
 *     message (rows themselves stay line-clamp-2);
 *   - mark the row read via POST /independent-teacher/notifications/{id}/read;
 *   - NOT navigate (the old behavior pushed cta_url immediately; the
 *     cta now surfaces as an explicit button inside the dialog).
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqInfo: jest.fn() }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
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
jest.mock('@/shared/contexts/AuthContext', () => ({
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
  mockNavigate.mockReset();
});

const FULL_MESSAGE =
  'هذه رسالة إشعار طويلة جدًا يجب أن تظهر كاملة داخل نافذة المعاينة بدلًا من قصّها على سطرين في القائمة.';

test('IT inbox row click opens preview dialog with full message, marks read, no navigation', async () => {
  const rows = [
    {
      id: 'it-n1',
      category: 'collab_invite',
      title: 'دعوة تعاون',
      message: FULL_MESSAGE,
      is_read: false,
      created_at: '2026-07-01T00:00:00Z',
      cta_url: '/teacher/collaboration',
    },
  ];
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/notifications/unread-count') {
      return Promise.resolve({ data: { unread_count: 1 } });
    }
    if (url === '/independent-teacher/notifications') {
      return Promise.resolve({ data: { items: rows, total: 1, next_cursor: null, has_more: false } });
    }
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockResolvedValue({ data: {} });

  render(<TeacherNotificationsPage />);

  await waitFor(() => {
    expect(screen.getByTestId('teacher-notifications-list')).toBeInTheDocument();
  }, { timeout: 4000 });

  // Click the mobile card (same onRowClick path as the desktop row).
  const mobile = screen.getByTestId('responsive-table-mobile');
  const firstCard = mobile.querySelector('li');
  expect(firstCard).not.toBeNull();
  fireEvent.click(firstCard);

  // Dialog opens with the FULL message body.
  await waitFor(() => {
    expect(screen.getByTestId('notification-detail-dialog')).toBeInTheDocument();
  });
  expect(screen.getByTestId('detail-message-body').textContent).toContain(FULL_MESSAGE);

  // Marked read via the IT-scoped endpoint.
  await waitFor(() => {
    expect(mockApiPost).toHaveBeenCalledWith('/independent-teacher/notifications/it-n1/read');
  });

  // No auto-navigation on row open.
  expect(mockNavigate).not.toHaveBeenCalled();

  // cta_url surfaces as the explicit action button; clicking it navigates.
  const actionBtn = screen.getByTestId('detail-action-btn');
  fireEvent.click(actionBtn);
  await waitFor(() => {
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/collaboration');
  });
});
