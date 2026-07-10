/**
 * School-teacher "التواصل والإشعارات" quick-preview contract.
 *
 * Clicking a notification card must open the full-content preview
 * dialog IN PLACE (parent pattern) — no navigation — while still
 * marking unread notifications as read via the existing endpoint.
 * Read cards must open the dialog too (the old behavior only fired
 * for unread cards).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '' }),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqInfo: jest.fn() }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

// Heavy sibling pages the dispatcher wrapper imports — not under test.
jest.mock('../IndependentTeacherCommunicationPage', () => () => null);
jest.mock('../UnifiedCommunicationsHub', () => () => null);

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApiPost = jest.fn();
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', role: 'teacher', teacher_id: 't1' },
    api: { get: mockApiGet, put: mockApiPut, post: mockApiPost },
    isRTL: true,
  }),
}));

import TeacherCommunicationPage from '../TeacherCommunicationPage';

const LONG_BODY = 'محتوى الإشعار الكامل الذي كان مقصوصًا سابقًا على سطرين فقط.\n'.repeat(6) + 'النهاية.';

const notifs = [
  {
    id: 'n1',
    title: 'تعميم مهم',
    message: LONG_BODY,
    notification_type: 'announcement',
    priority: 'high',
    read_status: false,
    created_at: '2026-07-09T08:00:00Z',
    sender_name: 'الإدارة',
  },
  {
    id: 'n2',
    title: 'إشعار مقروء',
    message: 'نص إشعار سبق قراءته.',
    notification_type: 'system',
    priority: 'medium',
    read_status: true,
    created_at: '2026-07-08T08:00:00Z',
  },
];

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url.startsWith('/teacher/classes/')) return Promise.resolve({ data: [] });
    if (url.startsWith('/notifications')) return Promise.resolve({ data: notifs });
    return Promise.resolve({ data: [] });
  });
  mockApiPut.mockResolvedValue({ data: {} });
});

test('clicking an unread card opens the full-content dialog and marks it read', async () => {
  render(<TeacherCommunicationPage />);

  await waitFor(() => {
    expect(screen.getByTestId('notification-card-n1')).toBeInTheDocument();
  }, { timeout: 4000 });

  fireEvent.click(screen.getByTestId('notification-card-n1'));

  const dialog = await screen.findByTestId('notification-detail-dialog');
  expect(dialog).toHaveAttribute('dir', 'rtl');
  const body = screen.getByTestId('detail-message-body');
  expect(body.textContent).toContain('النهاية.');
  expect(body.textContent.length).toBeGreaterThanOrEqual(LONG_BODY.length);
  expect(mockApiPut).toHaveBeenCalledWith('/notifications/n1/read');
});

test('clicking an already-read card still opens the dialog without re-marking', async () => {
  render(<TeacherCommunicationPage />);

  await waitFor(() => {
    expect(screen.getByTestId('notification-card-n2')).toBeInTheDocument();
  }, { timeout: 4000 });

  fireEvent.click(screen.getByTestId('notification-card-n2'));

  await screen.findByTestId('notification-detail-dialog');
  expect(screen.getByTestId('detail-message-body').textContent).toContain('نص إشعار سبق قراءته.');
  expect(mockApiPut).not.toHaveBeenCalled();
});
