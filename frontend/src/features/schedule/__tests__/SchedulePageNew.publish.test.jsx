/**
 * Publish-flow regression coverage for SchedulePageNew.
 *
 * The publish gate deliberately treats medium hard-constraint findings as
 * warnings: a successful POST must switch the page to the published view and
 * refresh the grid. A structured 409/PUBLISH_BLOCKED response remains a
 * blocking alert and must not switch views.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

const mockNassaqError = jest.fn();
const mockNassaqWarning = jest.fn();
const mockNassaqConfirm = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => () => {},
  useLocation: () => ({ pathname: '/principal/schedule', search: '', hash: '', state: null }),
  Link: ({ children }) => children,
}), { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqWarning: mockNassaqWarning,
    nassaqConfirm: mockNassaqConfirm,
    nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(),
  }),
}));
jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

// Keep this suite focused on the page's publish orchestration rather than its
// substitution/editing children.
jest.mock('@/features/schedule/components/schedule/CandidatesSidePanel', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/features/schedule/components/schedule/BulkSubstitutionPanel', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/features/schedule/components/schedule/ScheduleSettingsTabContent', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/features/schedule/components/schedule/MobileScheduleAgenda', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/features/schedule/components/schedule/SessionEditDrawer', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@/features/schedule/pages/StandbyRosterPage', () => ({
  StandbyRosterContent: () => null,
}));

// Stable refs are important here: api/user/t are effect and useCallback
// dependencies, and fresh objects would cause duplicate grid fetches.
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockStableApi = {
  get: (...args) => mockApiGet(...args),
  post: (...args) => mockApiPost(...args),
  put: jest.fn(),
  delete: jest.fn(),
};
const mockStableUser = { id: 'principal-1', role: 'school_admin', tenant_id: 'school-publish-1' };
const mockStableAuth = { user: mockStableUser, api: mockStableApi, isAuthenticated: true };
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockStableAuth,
}));

const mockStableTranslation = { t: (key) => key, language: 'en', isRTL: false };
const mockStableTheme = { direction: 'ltr', isRTL: false, isDark: false, theme: 'light' };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => mockStableTranslation,
  useTheme: () => mockStableTheme,
}));

const DRAFT_GRID = {
  is_empty: false,
  timetable_id: 'tt-draft',
  timetable_status: 'draft',
  today: 'sunday',
  days: ['sunday'],
  periods: [1],
  period_times: { 1: { start: '07:00', end: '07:45' } },
  kpis: { fairness_pct: 100, assigned_waiting: 0, absent_teachers_today: 0, vacant_sessions_today: 0 },
  pagination: { total: 1, page: 1, page_size: 200 },
  teachers: [{
    id: 'teacher-1',
    full_name: 'Publish Teacher',
    subject: 'Mathematics',
    weekly_quota: 1,
    assigned_periods: 1,
    is_absent_today: false,
  }],
  cells: {
    'teacher-1': {
      sunday: {
        1: {
          session_id: 'session-draft',
          class_id: 'class-draft',
          class_name: 'Draft class',
          subject_id: 'subject-1',
          subject_name: 'Mathematics',
          is_vacant: false,
        },
      },
    },
  },
};

const PUBLISHED_GRID = {
  ...DRAFT_GRID,
  timetable_id: 'tt-published',
  timetable_status: 'published',
  cells: {
    'teacher-1': {
      sunday: {
        1: {
          ...DRAFT_GRID.cells['teacher-1'].sunday[1],
          session_id: 'session-published',
          class_id: 'class-published',
          class_name: 'Published class',
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

let publishResponse;
let gridViews;
let confirmedPublish;

beforeEach(() => {
  window.ResizeObserver = ResizeObserverStub;
  global.ResizeObserver = ResizeObserverStub;
  window.localStorage.clear();
  // Start in the editable draft view so the publish action is available.
  window.localStorage.setItem('nassaq.schedule.view', 'draft');

  mockNassaqError.mockReset();
  mockNassaqWarning.mockReset();
  mockNassaqConfirm.mockReset();
  mockApiGet.mockReset();
  mockApiPost.mockReset();
  gridViews = [];
  confirmedPublish = null;
  publishResponse = {
    data: {
      success: true,
      timetable_id: 'tt-draft',
      // HC-09 is MEDIUM in the backend contract. Its presence must not
      // turn an otherwise successful publish into a blocking dialog.
      warnings: [{
        code: 'HC-09',
        severity: 'MEDIUM',
        message_ar: 'تنبيه أسبوعي غير حاجب',
      }],
    },
  };

  mockNassaqConfirm.mockImplementation((message, onConfirm) => {
    confirmedPublish = onConfirm;
  });
  mockApiGet.mockImplementation((path, config) => {
    if (path === '/schedule/master-grid') {
      const view = config?.params?.view || 'draft';
      gridViews.push(view);
      return Promise.resolve({
        data: view === 'published' ? PUBLISHED_GRID : DRAFT_GRID,
      });
    }
    if (path === '/smart-scheduling/timetable/versions') {
      return Promise.resolve({ data: [] });
    }
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockImplementation((path) => {
    if (path === '/schedule/publish') {
      return publishResponse?.response
        ? Promise.reject(publishResponse)
        : publishResponse;
    }
    return Promise.resolve({ data: {} });
  });
});

function renderSchedulePage() {
  // Require after the module mocks above are installed, matching the stable
  // context-mock convention used by the existing SchedulePageNew suites.
  const { default: SchedulePageNew } = require('@/features/schedule/pages/SchedulePageNew');
  return render(<SchedulePageNew />);
}

async function loadDraftAndConfirmPublish() {
  renderSchedulePage();
  await waitFor(() => {
    expect(screen.getByTestId('publish-schedule-btn')).toBeEnabled();
    expect(screen.getByText('Draft class')).toBeInTheDocument();
  });

  fireEvent.click(screen.getByTestId('publish-schedule-btn'));
  expect(mockNassaqConfirm).toHaveBeenCalledWith(
    'publishScheduleConfirmMessage',
    expect.any(Function),
    expect.objectContaining({
      title: 'publishScheduleConfirmTitle',
      confirmText: 'publishScheduleConfirmAction',
    }),
  );
  expect(confirmedPublish).toEqual(expect.any(Function));

  await act(async () => {
    await confirmedPublish();
  });
}

test('publishes with medium weekly warnings, switches to published grid, and shows no blocker dialog', async () => {
  await loadDraftAndConfirmPublish();

  await waitFor(() => {
    expect(mockApiPost).toHaveBeenCalledWith(
      '/schedule/publish',
      { school_id: 'school-publish-1', timetable_id: 'tt-draft' },
      { headers: { 'X-School-Context': 'school-publish-1' } },
    );
    expect(screen.getByText('Published class')).toBeInTheDocument();
    expect(screen.getByTestId('schedule-view-published')).toHaveAttribute('aria-selected', 'true');
  });

  // The explicit view override in handlePublish prevents a stale draft grid
  // from being left on screen after the successful POST.
  expect(gridViews).toContain('published');
  expect(mockNassaqError).not.toHaveBeenCalled();
  expect(mockNassaqWarning).not.toHaveBeenCalled();
});

test('keeps a real PUBLISH_BLOCKED 409 in the blocking dialog and does not switch views', async () => {
  publishResponse = {
    response: {
      status: 409,
      data: {
        detail: {
          code: 'PUBLISH_BLOCKED',
          message_ar: 'لا يمكن نشر الجدول بسبب تعارض حرج.',
          violations: [{
            code: 'HC-09',
            severity: 'HIGH',
            message_ar: 'يوجد تعارض حرج.',
          }],
        },
      },
    },
  };

  await loadDraftAndConfirmPublish();

  await waitFor(() => {
    expect(mockNassaqError).toHaveBeenCalledWith(
      expect.stringContaining('لا يمكن نشر الجدول بسبب تعارض حرج.'),
      { title: 'publishBlockedTitle' },
    );
  });
  expect(screen.getByText('Draft class')).toBeInTheDocument();
  expect(screen.queryByText('Published class')).toBeNull();
  expect(screen.getByTestId('schedule-view-draft')).toHaveAttribute('aria-selected', 'true');
  expect(gridViews).not.toContain('published');
});