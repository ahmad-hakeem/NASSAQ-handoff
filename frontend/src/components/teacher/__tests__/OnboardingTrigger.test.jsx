/**
 * Task #250 — IT first-login onboarding tour trigger contract.
 *
 * Pins the three behaviours the spec requires from the welcome card +
 * coach-mark trigger that mounts on TeacherMainDashboard / TeacherHomePage:
 *
 *   1. When `/independent-teacher/onboarding/state` returns
 *      `should_show:true`, the welcome card with "ابدأ الجولة" / "تخطي"
 *      renders synchronously after mount.
 *   2. Clicking "تخطي" (or finishing the tour) POSTs to
 *      `/independent-teacher/onboarding/complete` so the server-side
 *      stamp is persisted, and the welcome card unmounts.
 *   3. When the server already reports `should_show:false` (a returning
 *      IT who has finished or skipped) the trigger renders nothing —
 *      no welcome card, no follow-up complete POST.
 *   4. Non-IT callers never trigger any state fetch at all.
 */
import React from 'react';
import { render, screen, act, waitFor, fireEvent } from '@testing-library/react';

jest.mock('react-dom', () => {
  const actual = jest.requireActual('react-dom');
  return { ...actual, createPortal: (node) => node };
});

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
let mockRole = 'independent_teacher';
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: mockRole },
    api: { get: mockApiGet, post: mockApiPost },
    isRTL: true,
  }),
}));

import OnboardingTrigger from '../OnboardingTour/OnboardingTrigger';

const flush = async () => {
  await act(async () => { await Promise.resolve(); });
};

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPost.mockReset();
  mockRole = 'independent_teacher';
});

describe('OnboardingTrigger', () => {
  test('shows welcome card when should_show is true', async () => {
    mockApiGet.mockResolvedValueOnce({ data: { should_show: true, completed_at: null, has_workspace: true } });
    await act(async () => { render(<OnboardingTrigger />); });
    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/independent-teacher/onboarding/state'));
    await waitFor(() => expect(screen.getByTestId('it-onboarding-welcome')).toBeInTheDocument());
    expect(screen.getByTestId('it-onboarding-welcome-start')).toBeInTheDocument();
    expect(screen.getByTestId('it-onboarding-welcome-skip')).toBeInTheDocument();
  });

  test('skip stamps server-side and unmounts the welcome card', async () => {
    mockApiGet.mockResolvedValueOnce({ data: { should_show: true, completed_at: null, has_workspace: true } });
    mockApiPost.mockResolvedValueOnce({ data: { should_show: false, completed_at: '2026-05-13T00:00:00Z' } });
    await act(async () => { render(<OnboardingTrigger />); });
    await waitFor(() => expect(screen.getByTestId('it-onboarding-welcome')).toBeInTheDocument());

    await act(async () => { fireEvent.click(screen.getByTestId('it-onboarding-welcome-skip')); });
    await flush();

    expect(mockApiPost).toHaveBeenCalledWith('/independent-teacher/onboarding/complete');
    await waitFor(() => expect(screen.queryByTestId('it-onboarding-welcome')).not.toBeInTheDocument());
    expect(screen.queryByTestId('it-onboarding-tour')).not.toBeInTheDocument();
  });

  test('renders nothing and does not re-prompt when should_show is false', async () => {
    mockApiGet.mockResolvedValueOnce({ data: { should_show: false, completed_at: '2026-05-13T00:00:00Z', has_workspace: true } });
    await act(async () => { render(<OnboardingTrigger />); });
    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());
    await flush();
    expect(screen.queryByTestId('it-onboarding-welcome')).not.toBeInTheDocument();
    expect(screen.queryByTestId('it-onboarding-tour')).not.toBeInTheDocument();
    expect(mockApiPost).not.toHaveBeenCalled();
  });

  test('non-IT callers never fetch state', async () => {
    mockRole = 'teacher';
    await act(async () => { render(<OnboardingTrigger />); });
    await flush();
    expect(mockApiGet).not.toHaveBeenCalled();
    expect(mockApiPost).not.toHaveBeenCalled();
    expect(screen.queryByTestId('it-onboarding-welcome')).not.toBeInTheDocument();
  });
});
