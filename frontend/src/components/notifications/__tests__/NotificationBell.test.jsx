/**
 * Task #261 — pin the bell-refresh contract for the IT
 * "تعليم الكل كمقروء" bulk action.
 *
 * When any surface dispatches the global ``notifications:refresh``
 * CustomEvent, the header bell MUST re-fetch its unread count
 * immediately instead of waiting for the next 30s poll tick.
 *
 * A regression here would silently bring back the "stale red badge
 * after mark-all-read" issue the task was filed to fix.
 */
import React from 'react';
import { render, act, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k }),
}));

const mockApiGet = jest.fn();
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', role: 'independent_teacher' },
    api: { get: mockApiGet, post: jest.fn(), put: jest.fn() },
  }),
}));

import { NotificationBell } from '../NotificationBell';

beforeEach(() => {
  mockApiGet.mockReset();
});

test('refreshes unread count when notifications:refresh is dispatched', async () => {
  mockApiGet
    .mockResolvedValueOnce({ data: { unread_count: 5 } })   // initial mount
    .mockResolvedValueOnce({ data: { unread_count: 0 } });  // after event

  await act(async () => {
    render(<NotificationBell />);
  });

  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/independent-teacher/notifications/unread-count');
  });
  const initialCalls = mockApiGet.mock.calls.length;

  await act(async () => {
    window.dispatchEvent(new CustomEvent('notifications:refresh'));
  });

  await waitFor(() => {
    expect(mockApiGet.mock.calls.length).toBeGreaterThan(initialCalls);
  });
  // The follow-up call hits the IT-scoped unread-count endpoint
  // (not the global /notifications/unread-count) because the user
  // role is independent_teacher.
  const lastCall = mockApiGet.mock.calls[mockApiGet.mock.calls.length - 1];
  expect(lastCall[0]).toBe('/independent-teacher/notifications/unread-count');
});
