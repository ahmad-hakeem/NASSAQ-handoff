/**
 * Notification quick-preview upgrade — bell contract.
 *
 * Clicking a notification row inside the bell popover must:
 *   - open the in-place NotificationDetailDialog (rendered as a
 *     SIBLING of the Popover, so it survives the popover closing);
 *   - mark the notification read via PUT /notifications/{id}/read;
 *   - NOT navigate anywhere (the old behavior pushed action_url or a
 *     role-based notifications page; navigation now only happens via
 *     the explicit action button inside the dialog).
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k }),
}));

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
// IMPORTANT: user/api must be STABLE object references (like the real
// AuthContext provides). Fresh objects per render would change the
// identity of the bell's useCallback fetchers each render and re-fire
// their effects in an endless loading loop.
const mockStableUser = { id: 'u1', role: 'teacher' };
const mockStableApi = { get: mockApiGet, post: jest.fn(), put: mockApiPut };
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockStableUser, api: mockStableApi }),
}));

import { NotificationBell } from '../NotificationBell';

beforeAll(() => {
  // Radix Popover positioning needs ResizeObserver in jsdom.
  if (!global.ResizeObserver) {
    global.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
  }
});

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockNavigate.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url === '/notifications/unread-count') {
      return Promise.resolve({ data: { unread_count: 1 } });
    }
    if (url.startsWith('/notifications')) {
      return Promise.resolve({ data: [NOTIF] });
    }
    return Promise.resolve({ data: {} });
  });
  mockApiPut.mockResolvedValue({ data: {} });
});

const NOTIF = {
  id: 'bell-n1',
  notification_type: 'announcement',
  title: 'إعلان مهم',
  message: 'هذا نص الإشعار الكامل الذي يجب أن يظهر داخل نافذة المعاينة دون أي انتقال.',
  read_status: false,
  created_at: '2026-07-01T00:00:00Z',
  action_url: '/teacher/schedule',
};

test('bell row click opens preview dialog, marks read, and does not navigate', async () => {
  render(<NotificationBell />);

  fireEvent.click(screen.getByTestId('notification-bell'));

  const row = await screen.findByText('إعلان مهم', {}, { timeout: 4000 });

  fireEvent.click(row);

  // Dialog opens with the FULL message body.
  const dialog = await screen.findByTestId('notification-detail-dialog', {}, { timeout: 4000 });
  expect(dialog).toBeInTheDocument();
  expect(screen.getByTestId('detail-message-body').textContent).toContain(
    'هذا نص الإشعار الكامل الذي يجب أن يظهر داخل نافذة المعاينة دون أي انتقال.',
  );

  // Marked read via the standard endpoint.
  await waitFor(() => {
    expect(mockApiPut).toHaveBeenCalledWith('/notifications/bell-n1/read');
  });

  // No auto-navigation — the row click never routes anymore.
  expect(mockNavigate).not.toHaveBeenCalled();

  // The action button exists (action_url present) and navigates only
  // when explicitly clicked.
  fireEvent.click(screen.getByTestId('detail-action-btn'));
  await waitFor(() => {
    expect(mockNavigate).toHaveBeenCalledWith('/teacher/schedule');
  });
});
