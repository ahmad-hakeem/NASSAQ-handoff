/**
 * TeacherScheduleDeepLink.test.jsx
 *
 * Verifies that TeacherSchedulePage correctly parses `day` and `period`
 * query parameters (e.g. from class coverage assignment notifications),
 * selects the assigned day, and visually highlights the target slot.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

let mockSearchParams = new URLSearchParams('day=wednesday&period=2');
const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [mockSearchParams, jest.fn()],
  useLocation: () => ({ search: mockSearchParams.toString(), pathname: '/teacher/schedule' }),
}), { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', role: 'teacher', teacher_id: 'teacher-1' },
    api: { get: (...args) => mockApiGet(...args) },
    isRTL: true,
  }),
}));

import TeacherSchedulePage from '../TeacherSchedulePage';

describe('TeacherSchedulePage — Deep link from coverage notification', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams = new URLSearchParams('day=wednesday&period=2');
    mockApiGet.mockImplementation((url) => {
      if (url.startsWith('/teacher/schedule/')) {
        return Promise.resolve({
          data: [
            {
              id: 'sess-1',
              day_of_week: 'wednesday',
              period_number: 2,
              slot_number: 2,
              time_slot_id: 'slot-2',
              subject_name: 'الرياضيات',
              class_name: 'الصف السابع',
              start_time: '08:45:00',
              end_time: '09:30:00',
            },
          ],
        });
      }
      if (url === '/time-slots') {
        return Promise.resolve({
          data: [
            { id: 'slot-1', slot_number: 1, start_time: '08:00:00', end_time: '08:45:00', is_break: false },
            { id: 'slot-2', slot_number: 2, start_time: '08:45:00', end_time: '09:30:00', is_break: false },
          ],
        });
      }
      if (url === '/standby/roster/me') {
        return Promise.resolve({
          data: {
            days: [
              {
                day: 'wednesday',
                periods: [{ period: 2, status: 'assigned', class_name: 'الصف السابع', subject_name: 'الرياضيات' }],
              },
            ],
            total_slots: 1,
          },
        });
      }
      return Promise.resolve({ data: [] });
    });
  });

  test('parses searchParams and highlights the assigned slot on wednesday period 2', async () => {
    render(<TeacherSchedulePage />);

    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      expect(screen.getByTestId('schedule-grid')).toBeInTheDocument();
    });

    // The cell corresponding to wednesday period 2 is marked as highlighted
    const highlightedCell = document.querySelector('[data-highlighted="true"]');
    expect(highlightedCell).toBeInTheDocument();
    expect(highlightedCell.id).toBe('highlighted-slot-wednesday-2');
    expect(screen.getByText('حصة مكلّفة')).toBeInTheDocument();
  });
});
