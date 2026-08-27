import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => () => {},
  useLocation: () => ({ pathname: '/school/schedule', search: '', hash: '', state: null }),
  Link: ({ children }) => children,
}), { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: () => {},
    nassaqWarning: () => {},
    nassaqConfirm: () => {},
    nassaqInfo: () => {},
    nassaqSuccess: () => {},
  }),
}));
jest.mock('sonner', () => ({ toast: { success: () => {}, error: () => {} } }));

jest.mock('@/features/schedule/components/schedule/CandidatesSidePanel', () => ({ __esModule: true, default: () => null }));
jest.mock('@/features/schedule/components/schedule/BulkSubstitutionPanel', () => ({ __esModule: true, default: () => null }));
jest.mock('@/features/schedule/components/schedule/ScheduleSettingsTabContent', () => ({ __esModule: true, default: () => null }));
jest.mock('@/features/schedule/components/schedule/MobileScheduleAgenda', () => ({ __esModule: true, default: () => null }));

let capturedDrawerOnSaved = null;
jest.mock('@/features/schedule/components/schedule/SessionEditDrawer', () => ({
  __esModule: true,
  default: ({ open, onSaved }) => {
    capturedDrawerOnSaved = onSaved;
    return open ? <div data-testid="mock-session-drawer">Mock Drawer</div> : null;
  },
}));
jest.mock('@/features/schedule/pages/StandbyRosterPage', () => ({ StandbyRosterContent: () => null }));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockStableApi = {
  get: (...a) => mockApiGet(...a),
  post: (...a) => mockApiPost(...a),
  put: jest.fn(),
  delete: jest.fn(),
};
const mockStableUser = { id: 'u1', role: 'school_admin', tenant_id: 'school-1' };
const mockStableAuth = { user: mockStableUser, api: mockStableApi, isAuthenticated: true };
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockStableAuth,
}));

const mockStableTranslation = { t: (k) => k, language: 'ar', isRTL: true };
const mockStableTheme = { direction: 'rtl', isRTL: true, isDark: false, theme: 'light' };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => mockStableTranslation,
  useTheme: () => mockStableTheme,
}));

const GRID_PAYLOAD = {
  is_empty: false,
  timetable_id: 'tt-1',
  timetable_status: 'draft',
  today: 'sunday',
  days: ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'],
  periods: [1, 2, 3, 4, 5, 6, 7],
  period_times: { 1: { start: '07:00', end: '07:45' } },
  kpis: { fairness_pct: 92, assigned_waiting: 0, absent_teachers_today: 0, vacant_sessions_today: 1 },
  pagination: { total: 2, page: 1, page_size: 200 },
  teachers: [
    {
      id: 't-1',
      full_name: 'أحمد المعلم',
      subject: 'رياضيات',
      rank: 'معلم',
      weekly_quota: 24,
      assigned_periods: 20,
      is_absent_today: false,
    },
  ],
  cells: {
    't-1': {
      sunday: {
        1: {
          session_id: 's-1',
          class_id: 'c-1',
          class_name: '٣ علوم',
          subject_id: 'sb-1',
          subject_name: 'رياضيات',
          is_vacant: false,
        },
      },
    },
  },
};

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe('SchedulePageNew — Scroll Preservation & Silent Refetch', () => {
  beforeEach(() => {
    window.ResizeObserver = ResizeObserverStub;
    global.ResizeObserver = ResizeObserverStub;
    window.localStorage.clear();
    mockApiGet.mockReset();
    mockApiPost.mockReset();
    mockApiGet.mockImplementation((path) => {
      if (path === '/schedule/master-grid') return Promise.resolve({ data: GRID_PAYLOAD });
      if (path === '/smart-scheduling/timetable/versions') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: {} });
    });
    mockApiPost.mockResolvedValue({ data: {} });
  });

  test('keeps MasterMatrix mounted without flashing skeleton when drawer saves a session mutation', async () => {
    const { default: SchedulePageNew } = require('@/features/schedule/pages/SchedulePageNew');
    render(<SchedulePageNew />);

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/schedule/master-grid', expect.anything());
    });

    const matrixContainer = screen.getByTestId('master-matrix-container');
    expect(matrixContainer).toBeInTheDocument();

    // Set arbitrary scroll offset to simulate user scrolled to the bottom
    Object.defineProperty(matrixContainer, 'scrollTop', { value: 650, writable: true });
    Object.defineProperty(matrixContainer, 'scrollLeft', { value: 120, writable: true });

    // Trigger onSaved from drawer
    expect(capturedDrawerOnSaved).toBeDefined();
    await act(async () => {
      capturedDrawerOnSaved?.('created');
    });

    // Skeleton should NOT replace the matrix
    expect(screen.queryByTestId('master-matrix-skeleton')).toBeNull();
    expect(screen.getByTestId('master-matrix-container')).toBeInTheDocument();
  });
});
