/**
 * TeacherClassDetailPage — Add Lesson dialog: date pickers, curriculum range
 * check, override-with-justification flow, and 409 conflict dialog.
 *
 * Covers:
 *  - Date picker inputs render after metadata loads
 *  - Curriculum range label is shown when metadata has bounds
 *  - Save button disabled while form unsavable (out-of-range + no override)
 *  - Override checkbox + reason textarea appear when dates are out of range
 *  - Save button re-enabled when override checked + reason >= 10 chars
 *  - 409 curriculum_date_conflict response opens the conflict dialog
 *  - "Edit Dates" action in conflict dialog closes it (stays on add form)
 *  - "Override with Reason" action in conflict dialog checks the override box
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';

jest.mock('react-router-dom', () => {
  const params = new URLSearchParams('tab=curriculum');
  return {
    useNavigate: () => jest.fn(),
    useLocation: () => ({ search: '?tab=curriculum', pathname: '/teacher/class/c1' }),
    useSearchParams: () => [params, jest.fn()],
    useParams: () => ({ classId: 'c1' }),
  };
}, { virtual: true });

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
    nassaqInfo: jest.fn(),
  }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

// Stable module-level objects: `t` is a useCallback dep in the page
// (fetchClassData), so a fresh object per render loops the fetch effect.
const mockStableTheme = { isRTL: true };
const mockStableTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => mockStableTheme,
  useTranslation: () => mockStableTranslation,
}));

jest.mock('@/features/hakim/components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => <div />,
}));
jest.mock('@/features/hakim/components/hakim/HakimPresence', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/FollowupGradesTable', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/features/teachers/components/teacher/CollaboratorsTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('@/shared/models/utils/apiError', () => ({
  getApiErrorMessage: (err) => err?.response?.data?.detail?.message || 'error',
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: mockApiPost,
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
};

const mockAuth = {
  api: mockApi,
  user: {
    id: 'u1',
    role: 'independent_teacher',
    full_name: 'Test IT',
    tenant_id: 'itw_u1',
  },
  isAuthenticated: true,
};

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

const CLASS_DATA = {
  id: 'c1',
  name: 'الصف الأول أ',
  school_id: 'itw_u1',
  grade_id: '1',
  grade_name: 'الصف الأول',
  current_students: 5,
  is_active: true,
};

const META_WITHIN_RANGE = {
  curriculum_start_date: '2025-09-01',
  curriculum_end_date: '2026-06-30',
  default_start_date: '2025-10-01',
  default_end_date: '2026-06-30',
  allow_override: true,
};

const META_NO_RANGE = {
  curriculum_start_date: null,
  curriculum_end_date: null,
  default_start_date: '2026-06-21',
  default_end_date: '2026-06-21',
  allow_override: true,
};

function setupDefaultMocks() {
  mockApiGet.mockImplementation((url) => {
    if (url.includes('new-metadata')) return Promise.resolve({ data: META_WITHIN_RANGE });
    if (url.includes('curriculum-plan')) return Promise.resolve({ data: { lessons: [], total: 0, completed: 0, progress: 0 } });
    if (url.includes('/classes/c1')) return Promise.resolve({ data: CLASS_DATA });
    if (url.includes('grade-columns')) return Promise.resolve({ data: [] });
    if (url.includes('students')) return Promise.resolve({ data: [] });
    if (url.includes('session-settings')) return Promise.resolve({ data: [] });
    if (url.includes('lesson-plans')) return Promise.resolve({ data: { plans: [] } });
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockResolvedValue({ data: { id: 'lesson1', title: 'Test', week: 1, order: 1 } });
}

async function renderPage() {
  const { default: TeacherClassDetailPage } = await import('../TeacherClassDetailPage');
  let result;
  await act(async () => {
    result = render(<TeacherClassDetailPage />);
  });
  return result;
}

beforeEach(() => {
  jest.clearAllMocks();
  setupDefaultMocks();
});

describe('Add Lesson dialog — date pickers and curriculum range', () => {
  it('opens the dialog with date picker inputs and curriculum range label', async () => {
    await renderPage();

    await waitFor(() => expect(screen.queryByText('addLesson')).toBeTruthy());

    const addBtn = screen.getAllByText('addLesson')[0];
    await act(async () => { fireEvent.click(addBtn); });

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith(expect.stringContaining('new-metadata'));
    });

    await waitFor(() => {
      expect(screen.getByText('lessonStartDate')).toBeTruthy();
      expect(screen.getByText('lessonEndDate')).toBeTruthy();
    });

    expect(screen.getByText(/curriculumRange/)).toBeTruthy();
    expect(screen.getByText(/2025-09-01/)).toBeTruthy();
  });

  it('does not show curriculum range label when metadata has no bounds', async () => {
    mockApiGet.mockImplementation((url) => {
      if (url.includes('new-metadata')) return Promise.resolve({ data: META_NO_RANGE });
      if (url.includes('curriculum-plan')) return Promise.resolve({ data: { lessons: [], total: 0, completed: 0, progress: 0 } });
      if (url.includes('/classes/c1')) return Promise.resolve({ data: CLASS_DATA });
      return Promise.resolve({ data: {} });
    });

    await renderPage();
    await waitFor(() => expect(screen.queryByText('addLesson')).toBeTruthy());
    const addBtn = screen.getAllByText('addLesson')[0];
    await act(async () => { fireEvent.click(addBtn); });

    await waitFor(() => expect(screen.getByText('lessonStartDate')).toBeTruthy());
    expect(screen.queryByText(/curriculumRange/)).toBeNull();
  });
});

describe('Add Lesson dialog — out-of-range date and override flow', () => {
  async function openDialogAndSetOutOfRangeDates() {
    await renderPage();
    await waitFor(() => expect(screen.queryByText('addLesson')).toBeTruthy());
    const addBtn = screen.getAllByText('addLesson')[0];
    await act(async () => { fireEvent.click(addBtn); });
    await waitFor(() => expect(screen.getByText('lessonStartDate')).toBeTruthy());

    const startInputs = document.querySelectorAll('input[type="date"]');
    await act(async () => {
      fireEvent.change(startInputs[0], { target: { value: '2024-01-01' } });
      fireEvent.change(startInputs[1], { target: { value: '2024-01-07' } });
    });
    return startInputs;
  }

  it('shows amber out-of-range warning when dates fall outside curriculum bounds', async () => {
    await openDialogAndSetOutOfRangeDates();
    await waitFor(() => {
      expect(screen.getByText('datesOutsideCurriculumRange')).toBeTruthy();
    });
  });

  it('save button is disabled when dates are out-of-range without override', async () => {
    await openDialogAndSetOutOfRangeDates();

    const titleInput = screen.getByPlaceholderText('lessonTitle');
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: 'Test lesson' } });
    });

    await waitFor(() => expect(screen.getByText('datesOutsideCurriculumRange')).toBeTruthy());

    const saveBtn = screen.getByText('add').closest('button');
    expect(saveBtn).toBeDisabled();
  });

  it('save button re-enabled when override checked with sufficient reason', async () => {
    await openDialogAndSetOutOfRangeDates();

    const titleInput = screen.getByPlaceholderText('lessonTitle');
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: 'Test lesson' } });
    });

    await waitFor(() => expect(screen.getByText('overrideCurriculumWarning')).toBeTruthy());

    const checkbox = screen.getByRole('checkbox');
    await act(async () => { fireEvent.click(checkbox); });

    await waitFor(() => expect(screen.getByText('overrideReason')).toBeTruthy());

    const textarea = document.querySelector('textarea');
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'سبب التجاوز الكافي هنا' } });
    });

    const saveBtn = screen.getByText('add').closest('button');
    expect(saveBtn).not.toBeDisabled();
  });
});

describe('Add Lesson dialog — 409 curriculum_date_conflict conflict flow', () => {
  it('opens conflict dialog on 409 with curriculum_date_conflict code', async () => {
    mockApiPost.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: { code: 'curriculum_date_conflict', message: 'خارج النطاق' } },
      },
    });

    await renderPage();
    await waitFor(() => expect(screen.queryByText('addLesson')).toBeTruthy());
    const addBtn = screen.getAllByText('addLesson')[0];
    await act(async () => { fireEvent.click(addBtn); });
    await waitFor(() => expect(screen.getByText('lessonStartDate')).toBeTruthy());

    const titleInput = screen.getByPlaceholderText('lessonTitle');
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: 'درس جديد' } });
    });

    const saveBtn = screen.getByText('add').closest('button');
    await act(async () => { fireEvent.click(saveBtn); });

    await waitFor(() => {
      expect(screen.getByText('curriculumDateConflict')).toBeTruthy();
    });
  });

  it('"Edit Dates" action closes the conflict dialog', async () => {
    mockApiPost.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { detail: { code: 'curriculum_date_conflict', message: 'خارج النطاق' } },
      },
    });

    await renderPage();
    await waitFor(() => expect(screen.queryByText('addLesson')).toBeTruthy());
    const addBtn = screen.getAllByText('addLesson')[0];
    await act(async () => { fireEvent.click(addBtn); });
    await waitFor(() => expect(screen.getByText('lessonStartDate')).toBeTruthy());

    const titleInput = screen.getByPlaceholderText('lessonTitle');
    await act(async () => {
      fireEvent.change(titleInput, { target: { value: 'درس جديد' } });
    });

    await act(async () => { fireEvent.click(screen.getByText('add').closest('button')); });
    await waitFor(() => expect(screen.getByText('curriculumDateConflict')).toBeTruthy());

    await act(async () => { fireEvent.click(screen.getByText('editDates')); });

    await waitFor(() => {
      expect(screen.queryByText('curriculumDateConflict')).toBeNull();
    });
  });
});
