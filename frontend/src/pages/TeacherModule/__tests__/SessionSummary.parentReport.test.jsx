/**
 * SessionSummary — end-of-lesson parent-report delivery UX regression tests.
 *
 * Bug context (Task #1057): when an Independent Teacher ended a live lesson the
 * success summary screen ("انتهت الحصة") rendered, then the parent-report POST
 * raised the IT broadcast-deny error and the FE surfaced that RAW backend
 * wording ("لا يمكن للمعلم المستقل البث حسب الدور.") in a popup — a contradictory
 * "success + error" state.
 *
 * Invariants locked here (SessionSummary.sendParentNotifications, fired once on
 * mount):
 *   - On a successful send the summary shows a success toast and NEVER raises an
 *     error dialog.
 *   - On a genuine delivery failure the user sees a SAFE, localized Arabic
 *     message via NassaqAlertDialog — never the raw backend broadcast string,
 *     and never toast.error.
 *
 * Run: CI=true npx craco test --testPathPattern="SessionSummary.parentReport" --watchAll=false --forceExit
 */

import React from 'react';
import { render, waitFor, screen, fireEvent } from '@testing-library/react';

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockNassaqError = jest.fn();

jest.mock('canvas-confetti', () => ({ __esModule: true, default: jest.fn() }));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn(), warning: jest.fn() },
}));
// eslint-disable-next-line global-require
const { toast: mockToast } = require('sonner');

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ state: {}, pathname: '/session/teach' }),
}), { virtual: true });

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'it-1', name: 'IT Teacher', role: 'independent_teacher' },
    api: { get: mockGet, post: mockPost },
    isRTL: true,
  }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: true, dir: 'rtl' }),
  useTheme: () => ({ isDark: false, toggleTheme: jest.fn() }),
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError, nassaqConfirm: jest.fn() }),
  NassaqAlertDialog: () => null,
}));

// The raw IT broadcast-deny wording that MUST never reach the user from the
// summary screen.
const BROADCAST_DENY_AR = 'لا يمكن للمعلم المستقل البث حسب الدور.';

// Component under test (imported AFTER all mocks).
import { SessionSummary } from '../SessionTeachPage';

const SUMMARY = {
  session_record_id: 'sess-it-end',
  duration_minutes: 30,
  present_count: 2,
  absent_count: 0,
  questions_asked: 1,
  correct_answers: 1,
  management_notifications_sent: 0,
};
const SESSION_INFO = {
  subject_name: 'الرياضيات',
  class_name: 'الصف الأول',
  class_id: 'class-1',
};

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockNassaqError.mockReset();
  mockToast.success.mockClear();
  mockToast.error.mockClear();
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
});

describe('SessionSummary — IT parent-report delivery UX', () => {
  test('successful send shows a success toast and NO error dialog', async () => {
    mockPost.mockResolvedValue({ data: { success: true, created_count: 2 } });

    render(<SessionSummary summary={SUMMARY} sessionInfo={SESSION_INFO} onHome={jest.fn()} isRTL />);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/notifications',
        expect.objectContaining({
          recipient_role: 'parent',
          related_entity: 'session',
          related_entity_id: SUMMARY.session_record_id,
        }),
      );
    }, { timeout: 3000 });

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('reportSentToParentsOnly');
    }, { timeout: 3000 });

    // Success must never coincide with an error dialog or an error toast.
    expect(mockNassaqError).not.toHaveBeenCalled();
    expect(mockToast.error).not.toHaveBeenCalled();
  });

  test('failed send shows a safe localized NassaqAlertDialog, never the raw broadcast wording', async () => {
    const err = new Error('denied');
    err.response = { status: 403, data: { detail: BROADCAST_DENY_AR } };
    mockPost.mockRejectedValue(err);

    render(<SessionSummary summary={SUMMARY} sessionInfo={SESSION_INFO} onHome={jest.fn()} isRTL />);

    await waitFor(() => {
      expect(mockNassaqError).toHaveBeenCalledWith('failedToSendNotifications');
    }, { timeout: 3000 });

    // The raw backend broadcast string must never be surfaced to the user.
    expect(mockNassaqError).not.toHaveBeenCalledWith(BROADCAST_DENY_AR);
    expect(mockToast.error).not.toHaveBeenCalledWith(BROADCAST_DENY_AR);
    // A genuine failure must not also claim success.
    expect(mockToast.success).not.toHaveBeenCalled();
  });

  test('after a failed send, the resend button re-runs delivery and shows the success toast', async () => {
    // First (auto) send fails → resend button appears.
    const err = new Error('denied');
    err.response = { status: 500, data: { detail: 'boom' } };
    mockPost.mockRejectedValueOnce(err);

    render(<SessionSummary summary={SUMMARY} sessionInfo={SESSION_INFO} onHome={jest.fn()} isRTL />);

    await waitFor(() => {
      expect(mockNassaqError).toHaveBeenCalledWith('failedToSendNotifications');
    }, { timeout: 3000 });

    // The resend button is only rendered once a delivery failure is recorded.
    const resendBtn = await screen.findByText('resendReport');
    expect(mockPost).toHaveBeenCalledTimes(1);

    // Second attempt (manual resend) succeeds.
    mockPost.mockResolvedValueOnce({ data: { success: true } });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('reportSentToParentsOnly');
    }, { timeout: 3000 });

    // Exactly two POSTs total: the failed auto-send and the successful resend.
    expect(mockPost).toHaveBeenCalledTimes(2);
  });

  test('a successful auto-send never renders the resend button (no accidental duplicate send)', async () => {
    mockPost.mockResolvedValue({ data: { success: true } });

    render(<SessionSummary summary={SUMMARY} sessionInfo={SESSION_INFO} onHome={jest.fn()} isRTL />);

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('reportSentToParentsOnly');
    }, { timeout: 3000 });

    // No failure → no resend affordance, and the send stays one-shot.
    expect(screen.queryByText('resendReport')).toBeNull();
    expect(mockPost).toHaveBeenCalledTimes(1);
  });
});
