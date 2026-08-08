/**
 * Task #277 — parent portal polish for IT-invited parents.
 *
 * Pins two FE behaviours surfaced by the spec:
 *
 *   1. The dashboard hero swaps the school chip for a turquoise IT
 *      badge (`hero-it-badge`) — naming the inviting teacher when the
 *      backend returns `is_independent_teacher_workspace=true`.
 *   2. The one-shot welcome card (`parent-invite-welcome-card`)
 *      renders for IT-invited parents when the localStorage flag set
 *      by ParentInvitationAcceptPage is present, and disappears once
 *      the user dismisses it (the flag is cleared, so the card never
 *      reappears on the next render).
 *
 * Heavy upstream subtrees (PortalLayout, ParentActiveStudentContext,
 * AuthContext, hooks, and ESM-only widgets like HakimChatWidget) are
 * mocked at the module boundary so the test stays fast and
 * deterministic — same pattern as LoginPage.test.jsx.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

// --- Router shims -----------------------------------------------------------
jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
  useNavigate: () => jest.fn(),
}), { virtual: true });

// --- Theme + i18n shim ------------------------------------------------------
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, isDark: false, toggleLanguage: () => {} }),
  // Return undefined for every key so the in-component `t('k') || fallback`
  // chain falls through to the inline Arabic copy that the assertions rely on.
  useTranslation: () => ({ t: () => undefined, isRTL: true }),
}));

const ACTIVE_CHILD_ID = 'student-it-1';
const TEACHER_NAME = 'الأستاذة سارة';
const STUDENT_NAME = 'طالب الترحيب';

// --- Hook shim — replace useParentDashboard with a deterministic IT result --
jest.mock('@/shared/hooks/useParentDashboard', () => ({
  __esModule: true,
  default: () => ({
    children: [{ id: 'student-it-1', name: 'طالب الترحيب' }],
    selectedChildIndex: 0,
    selectedChild: {
      id: 'student-it-1',
      name: 'طالب الترحيب',
      school_id: 'itw_owner-1',
      is_independent_teacher_workspace: true,
      teacher_display_name: 'الأستاذة سارة',
    },
    selectedChildId: 'student-it-1',
    liveData: {
      student: {
        name: 'طالب الترحيب',
        school_id: 'itw_owner-1',
        school_name: 'IT-Workspace-owner1',
        is_independent_teacher_workspace: true,
        teacher_display_name: 'الأستاذة سارة',
        class_name: 'الصف الأول',
        grade_level: 'ابتدائي',
      },
      school_day: {
        is_school_day: true, total_periods: 0, completed_periods: 0,
        remaining_periods: 0, all_sessions: [], today: 'sunday', server_time: '08:00',
      },
      current_class: null,
      upcoming_classes: [],
      performance: { level: '', overall_average: 0, trend: 0, trend_direction: 'stable', phrase: '' },
    },
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
jest.mock('../../../components/portal/PortalLayout', () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="portal-layout">{children}</div>,
}));
jest.mock('../../../components/parent/CurrentClassCard', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/parent/UpcomingClasses', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/parent/WeeklyStory', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/parent/HakimChatWidget', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/parent/BackgroundRefreshChip', () => ({
  __esModule: true, default: () => <div />,
}));

// IMPORTANT — import the component AFTER all mocks are registered.
const ParentPortalDashboard = require('../ParentPortalDashboard').default;

describe('ParentPortalDashboard — IT polish (#277)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the IT badge with the teacher name on the hero', async () => {
    await act(async () => {
      render(<ParentPortalDashboard />);
    });
    const badge = await screen.findByTestId('hero-it-badge');
    expect(badge.textContent).toContain(TEACHER_NAME);
  });

  it('renders the one-shot welcome card when the localStorage flag is present, and dismisses', async () => {
    localStorage.setItem(`nassaq_invite_welcome_${ACTIVE_CHILD_ID}`, JSON.stringify({
      inviter_teacher_name: TEACHER_NAME,
      workspace_name: 'مساحة سارة',
      student_name: STUDENT_NAME,
      seeded_at: Date.now(),
    }));

    await act(async () => {
      render(<ParentPortalDashboard />);
    });
    const card = await screen.findByTestId('parent-invite-welcome-card');
    expect(card.textContent).toContain(TEACHER_NAME);
    expect(card.textContent).toContain('مساحة سارة');

    fireEvent.click(screen.getByTestId('invite-welcome-dismiss'));
    await waitFor(() => {
      expect(screen.queryByTestId('parent-invite-welcome-card')).toBeNull();
    });
    expect(localStorage.getItem(`nassaq_invite_welcome_${ACTIVE_CHILD_ID}`)).toBeNull();
  });
});
