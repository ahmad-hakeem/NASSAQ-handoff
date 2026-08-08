/**
 * §11 regression guard (CI pipeline plan Task 5): after a generation
 * payload is loaded from GET /schedule/master-grid, the master grid must
 * render session cells — not the empty-grid fallback.
 *
 * The fixture mirrors the real wire contract consumed by SchedulePageNew
 * (grid.teachers / grid.cells / grid.days / grid.periods / grid.kpis /
 * grid.pagination — see loadGrid + the derived consts around line 1439)
 * and the cell shape MasterMatrix renders (same shape as
 * MasterMatrix.test.jsx fixtures).
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => () => {},
  useLocation: () => ({ pathname: '/school/schedule', search: '', hash: '', state: null }),
  Link: ({ children }) => children,
}), { virtual: true });

jest.mock('../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));
jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: () => {},
    nassaqWarning: () => {},
    nassaqConfirm: () => {},
    nassaqInfo: () => {},
    nassaqSuccess: () => {},
  }),
}));
jest.mock('sonner', () => ({ toast: { success: () => {}, error: () => {} } }));

// Heavy siblings not under test — stubbed so the page mounts fast and the
// assertion stays pinned to the master grid itself.
jest.mock('../../components/schedule/CandidatesSidePanel', () => ({ __esModule: true, default: () => null }));
jest.mock('../../components/schedule/BulkSubstitutionPanel', () => ({ __esModule: true, default: () => null }));
jest.mock('../../components/schedule/ScheduleSettingsTabContent', () => ({ __esModule: true, default: () => null }));
jest.mock('../../components/schedule/MobileScheduleAgenda', () => ({ __esModule: true, default: () => null }));
jest.mock('../../components/schedule/SessionEditDrawer', () => ({ __esModule: true, default: () => null }));
jest.mock('../StandbyRosterPage', () => ({ StandbyRosterContent: () => null }));

// Stable module-level context mocks: `t`, `api`, and `user` are effect /
// useCallback deps in the page — fresh objects per call loop the fetch
// effect (see auth-mock-stable-refs / i18n conventions).
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
jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockStableAuth,
}));

const mockStableTranslation = { t: (k) => k, language: 'ar', isRTL: true };
const mockStableTheme = { direction: 'rtl', isRTL: true, isDark: false, theme: 'light' };
jest.mock('../../contexts/ThemeContext', () => ({
  useTranslation: () => mockStableTranslation,
  useTheme: () => mockStableTheme,
}));

// ── Fixture: 2 sessions across 2 classes / 2 teachers ────────────────
const GRID_PAYLOAD = {
  is_empty: false,
  timetable_id: 'tt-1',
  timetable_status: 'published',
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
    {
      id: 't-2',
      full_name: 'سارة الفاضل',
      subject: 'علوم',
      rank: 'معلم',
      weekly_quota: 22,
      assigned_periods: 18,
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
    't-2': {
      monday: {
        2: {
          session_id: 's-2',
          class_id: 'c-2',
          class_name: '١ أدبي',
          subject_id: 'sb-2',
          subject_name: 'علوم',
          is_vacant: false,
        },
      },
    },
  },
};

// jsdom lacks ResizeObserver (the sticky-band density tracker uses it).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// jest resetMocks:true wipes implementations — install in beforeEach.
beforeEach(() => {
  window.ResizeObserver = ResizeObserverStub;
  global.ResizeObserver = ResizeObserverStub;
  window.localStorage.clear();
  mockApiGet.mockImplementation((path) => {
    if (path === '/schedule/master-grid') return Promise.resolve({ data: GRID_PAYLOAD });
    if (path === '/smart-scheduling/timetable/versions') return Promise.resolve({ data: [] });
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockResolvedValue({ data: {} });
});

test('renders session cells from a generation payload (no empty-grid fallback)', async () => {
  const { default: SchedulePageNew } = require('../SchedulePageNew');
  render(<SchedulePageNew />);

  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/schedule/master-grid', expect.anything());
  });

  // Both fixture sessions render their subject text somewhere in the grid
  // (getAllBy* — the teacher meta column also shows the subject, and
  // desktop/mobile branches may both mount).
  await waitFor(() => {
    expect(screen.getAllByText(/رياضيات/).length).toBeGreaterThan(0);
  });
  expect(screen.getAllByText(/علوم/).length).toBeGreaterThan(0);
  // Class names come only from the session cells themselves.
  expect(screen.getAllByText(/٣ علوم/).length).toBeGreaterThan(0);

  // And the explicit empty-state marker must be absent.
  expect(screen.queryByTestId('schedule-empty-state')).toBeNull();
});
