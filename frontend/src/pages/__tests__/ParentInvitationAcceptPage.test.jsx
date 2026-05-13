/**
 * Task #277 — landing snapshot for the parent invitation accept page.
 *
 * Pins three things the polish pass introduced:
 *   1. The page renders the standard NASSAQ portal chrome (logo + date band)
 *      and the centred accept card while the POST is in-flight.
 *   2. On a successful accept, the welcome card surfaces the inviting
 *      teacher's name, the workspace name, and the linked student name
 *      and exposes a "go to portal" CTA.
 *   3. The one-shot localStorage flag (`nassaq_invite_welcome_<sid>`) is
 *      seeded with the response payload so the dashboard's welcome card
 *      can render on first visit even if the parent navigates straight
 *      there.
 */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';

const mockNavigate = jest.fn();

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useSearchParams: () => [new URLSearchParams('token=test-token')],
}), { virtual: true });

jest.mock('axios', () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

// Mirror the real ThemeContext hook contract (#277 fix): `isRTL` lives on
// useTheme; useTranslation returns only `{ t, language, localizedValue }`.
jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, isDark: false, language: 'ar' }),
  useTranslation: () => ({ t: () => undefined, language: 'ar', localizedValue: (v) => v }),
}));

jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ showAlert: jest.fn() }),
}));

jest.mock('../../utils/hijriDate', () => ({
  formatFullDate: () => ({ weekday: 'الأحد', full: '1 محرم 1447 هـ — 1 يونيو 2026' }),
}));

const axios = require('axios').default;
const ParentInvitationAcceptPage = require('../ParentInvitationAcceptPage').default;

describe('ParentInvitationAcceptPage — landing snapshot (#277)', () => {
  beforeEach(() => {
    localStorage.clear();
    axios.post.mockReset();
    mockNavigate.mockReset();
  });

  it('renders portal chrome + welcome card on success and seeds the welcome flag', async () => {
    let resolvePost;
    axios.post.mockReturnValueOnce(new Promise((res) => { resolvePost = res; }));

    await act(async () => {
      render(<ParentInvitationAcceptPage />);
    });

    // Working state — portal chrome is present.
    const root = screen.getByTestId('parent-invitation-accept-page');
    expect(root).toBeTruthy();
    // RTL contract: the page must render dir="rtl" when the theme is
    // Arabic — guards against regressions where `isRTL` is sourced from
    // the wrong hook and the page silently falls back to LTR.
    expect(root.getAttribute('dir')).toBe('rtl');
    expect(screen.getByTestId('invitation-accept-card')).toBeTruthy();
    expect(screen.getByAltText('نَسَّق')).toBeTruthy();
    expect(screen.getByText('الأحد')).toBeTruthy();

    // Resolve the in-flight POST and assert the welcome card renders.
    await act(async () => {
      resolvePost({
        data: {
          access_token: 'parent-bearer',
          student_id: 'stu-it-1',
          inviter_teacher_name: 'الأستاذة سارة',
          workspace_name: 'مساحة سارة',
          student_name: 'طالب الترحيب',
        },
      });
    });

    const welcome = await screen.findByTestId('invitation-welcome-card');
    expect(welcome.textContent).toContain('الأستاذة سارة');
    expect(welcome.textContent).toContain('مساحة سارة');
    expect(welcome.textContent).toContain('طالب الترحيب');
    expect(screen.getByTestId('invitation-go-to-portal')).toBeTruthy();

    // Seeds the one-shot welcome flag the dashboard reads on first visit.
    expect(localStorage.getItem('nassaq_token')).toBe('parent-bearer');
    const flag = JSON.parse(localStorage.getItem('nassaq_invite_welcome_stu-it-1'));
    expect(flag.inviter_teacher_name).toBe('الأستاذة سارة');
    expect(flag.workspace_name).toBe('مساحة سارة');
    expect(flag.student_name).toBe('طالب الترحيب');
  });

  it('shows the error CTA when the public accept POST fails', async () => {
    axios.post.mockRejectedValueOnce({ response: { status: 400 } });

    await act(async () => {
      render(<ParentInvitationAcceptPage />);
    });

    await waitFor(() => {
      expect(screen.getByTestId('parent-invitation-accept-go-login')).toBeTruthy();
    });
    // No token persisted on failure.
    expect(localStorage.getItem('nassaq_token')).toBeNull();
  });
});
