/**
 * Task #236 — pin the post-login banner-paint contract introduced by Task #231.
 *
 * When AuthContext seeds an `initialWorkspaceLifecycle` snapshot via
 * `consumeInitialWorkspaceLifecycle()` (i.e. the embed delivered by the
 * /auth/login or /auth/mfa/verify response), ReactivationBanner must:
 *   1. render the banner synchronously on first paint (no follow-up GET wait), and
 *   2. NOT fire `/independent-teacher/workspace/lifecycle` — the embedded
 *      payload is the freshest data we can possibly have.
 *
 * A regression here would silently bring back the late-pop banner the
 * task was filed to fix.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: (d) => `hijri:${d instanceof Date ? d.toISOString().slice(0, 10) : String(d)}`,
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockConsumeInitial = jest.fn();
let mockUserRole = 'independent_teacher';
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { role: mockUserRole },
    api: { get: mockApiGet, post: mockApiPost },
    consumeInitialWorkspaceLifecycle: mockConsumeInitial,
  }),
}));

import ReactivationBanner from '../ReactivationBanner';

const _bannerSnapshot = () => ({
  reactivation_banner: {
    archived_at: '2026-04-01T00:00:00+00:00',
    reactivated_at: '2026-04-03T00:00:00+00:00',
    would_have_been_deleted_at: '2026-05-01T00:00:00+00:00',
    reactivation_window_days: 30,
    days_remaining_at_reactivation: 28,
  },
});

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPost.mockReset();
  mockConsumeInitial.mockReset();
  mockNavigate.mockReset();
  mockUserRole = 'independent_teacher';
});

test('renders banner synchronously from the seeded post-login snapshot and skips the follow-up GET', async () => {
  mockConsumeInitial.mockReturnValue({ snapshot: _bannerSnapshot(), consumed: true });

  await act(async () => {
    render(<ReactivationBanner />);
  });

  // Banner is present on first paint (no waitFor needed — synchronous from seed).
  expect(screen.getByTestId('it-reactivation-banner')).toBeInTheDocument();
  // The component MUST NOT have hit the lifecycle endpoint — the embed
  // already delivered the freshest snapshot we can have.
  expect(mockApiGet).not.toHaveBeenCalled();
});

test('renders nothing and skips the follow-up GET when the seed says "consumed but no banner"', async () => {
  // The embed surfaced a snapshot but the server resolved
  // reactivation_banner to null (the gate is closed). The follow-up
  // GET must still be skipped — re-fetching would only generate a
  // redundant request.
  mockConsumeInitial.mockReturnValue({ snapshot: { reactivation_banner: null }, consumed: true });

  await act(async () => {
    render(<ReactivationBanner />);
  });

  expect(screen.queryByTestId('it-reactivation-banner')).toBeNull();
  expect(mockApiGet).not.toHaveBeenCalled();
});

test('falls back to the lifecycle GET when no post-login snapshot was delivered (e.g. hard refresh)', async () => {
  mockConsumeInitial.mockReturnValue({ snapshot: null, consumed: false });
  mockApiGet.mockResolvedValue({ data: _bannerSnapshot() });

  await act(async () => {
    render(<ReactivationBanner />);
  });

  expect(mockApiGet).toHaveBeenCalledWith('/independent-teacher/workspace/lifecycle');
});

test('non-IT user never renders the banner and never hits the lifecycle endpoint', async () => {
  mockUserRole = 'school_principal';
  mockConsumeInitial.mockReturnValue({ snapshot: null, consumed: false });

  await act(async () => {
    render(<ReactivationBanner />);
  });

  expect(screen.queryByTestId('it-reactivation-banner')).toBeNull();
  expect(mockApiGet).not.toHaveBeenCalled();
});
