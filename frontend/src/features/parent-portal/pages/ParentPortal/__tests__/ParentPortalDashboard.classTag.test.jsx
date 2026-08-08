/**
 * Parent home hero — class/grade identity tag.
 *
 * Regression cover for the malformed tag bug: the hero used to compose
 * `{class_name} — {grade_level}`, and because the `today-live` payload
 * carried an empty `class_name` (the raw students row has no class_name
 * column and the route skipped class-name enrichment), the tag rendered a
 * bare "— N" fragment (e.g. "— 5") instead of the student's real class.
 *
 * These tests pin the render contract:
 *   1. When `class_name` is present, the tag shows the real class name and
 *      never appends a trailing "— grade" fragment.
 *   2. When `class_name` is missing, the tag falls back to a labelled grade
 *      ("الصف N") — a safe, meaningful value, never a bare "— N" fragment.
 *
 * Mocking mirrors ParentPortalDashboard.it.test.jsx (heavy upstream subtrees
 * stubbed at the module boundary). `mockLiveData` is mutable so each test can
 * drive a different payload through the mocked hook.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';

// --- Router shims -----------------------------------------------------------
jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
  useNavigate: () => jest.fn(),
}), { virtual: true });

// --- Theme + i18n shim ------------------------------------------------------
// `t` returns undefined so the in-component `t('k') || fallback` chain falls
// through to the inline Arabic copy the assertions rely on.
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, isDark: false, toggleLanguage: () => {} }),
  useTranslation: () => ({ t: () => undefined, isRTL: true }),
}));

// --- Hook shim — mutable payload so each test drives its own liveData --------
let mockLiveData = null;
jest.mock('@/shared/hooks/useParentDashboard', () => ({
  __esModule: true,
  default: () => ({
    children: [{ id: 'student-1', name: 'الطالب' }],
    selectedChildIndex: 0,
    selectedChild: { id: 'student-1', name: 'الطالب' },
    selectedChildId: 'student-1',
    liveData: mockLiveData,
    weeklyStory: null,
    notifications: [],
    loading: false,
    liveLoading: false,
    weeklyLoading: false,
    liveError: null,
    weeklyError: null,
    childrenError: false,
    refreshing: false,
    selectChild: jest.fn(),
    refreshLiveData: jest.fn(),
    refreshWeeklyStory: jest.fn(),
    refreshChildren: jest.fn(),
  }),
}));

// --- Heavy / ESM subtrees — passthrough stubs -------------------------------
jest.mock('@/features/student-portal/components/portal/PortalLayout', () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="portal-layout">{children}</div>,
}));
jest.mock('@/features/parent-portal/components/parent/CurrentClassCard', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('@/features/parent-portal/components/parent/UpcomingClasses', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('@/features/parent-portal/components/parent/WeeklyStory', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('@/features/parent-portal/components/parent/HakimChatWidget', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('@/features/parent-portal/components/parent/BackgroundRefreshChip', () => ({
  __esModule: true, default: () => <div />,
}));

// IMPORTANT — import the component AFTER all mocks are registered.
const ParentPortalDashboard = require('../ParentPortalDashboard').default;

const baseStudent = {
  name: 'الطالب',
  school_id: 'school-1',
  school_name: 'مدرسة الفارابي',
  is_independent_teacher_workspace: false,
  teacher_display_name: null,
};
const baseSchoolDay = {
  is_school_day: true, total_periods: 0, completed_periods: 0,
  remaining_periods: 0, all_sessions: [], today: 'sunday', server_time: '08:00',
};

function makeLive(studentPatch) {
  return {
    student: { ...baseStudent, ...studentPatch },
    school_day: baseSchoolDay,
    current_class: null,
    upcoming_classes: [],
    performance: { level: '', overall_average: 0, trend: 0, trend_direction: 'stable', phrase: '' },
  };
}

describe('ParentPortalDashboard — hero class/grade tag', () => {
  it('shows the real class name and does not append a "— grade" fragment', async () => {
    mockLiveData = makeLive({ class_name: 'فصل 7 يونيو', grade_level: '5' });
    await act(async () => {
      render(<ParentPortalDashboard />);
    });
    const tag = await screen.findByTestId('hero-class-tag');
    expect(tag.textContent).toContain('فصل 7 يونيو');
    expect(tag.textContent).not.toContain('—');
  });

  it('falls back to a labelled grade (never a bare "— N" fragment) when class_name is missing', async () => {
    mockLiveData = makeLive({ class_name: '', grade_level: '5' });
    await act(async () => {
      render(<ParentPortalDashboard />);
    });
    const tag = await screen.findByTestId('hero-class-tag');
    expect(tag.textContent.replace(/\s+/g, ' ').trim()).toContain('الصف 5');
    expect(tag.textContent).not.toContain('—');
  });
});
