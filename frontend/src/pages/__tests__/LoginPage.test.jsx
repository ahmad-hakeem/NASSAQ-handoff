/**
 * Task #195 — login success-and-error race regression guard.
 *
 * These tests pin the new single-state-machine semantics of the login
 * page: every attempt produces exactly one user-visible outcome (success
 * toast OR error surface, never both), the success toast only fires
 * after /auth/me + redirect commit, and a downstream failure leaves the
 * user in a clean signed-out state on /login.
 *
 * The page transitively imports react-router-dom, ThemeContext,
 * AuthContext and NassaqAlertDialog. We mock those at the module
 * boundary so the test stays fast and deterministic.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
}), { virtual: true });

const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();
jest.mock('sonner', () => ({
  toast: {
    success: (...a) => mockToastSuccess(...a),
    error: (...a) => mockToastError(...a),
  },
}));

const mockLogin = jest.fn();
const mockRefreshUser = jest.fn();
const mockClearAuthState = jest.fn();
jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    refreshUser: mockRefreshUser,
    clearAuthState: mockClearAuthState,
  }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleLanguage: () => {} }),
  useTranslation: () => ({ t: (k) => k }),
}));

const mockNassaqError = jest.fn();
jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

// Heavy / unrelated subtree — keep it cheap.
jest.mock('../../components/mfa/MfaLoginChallengePanel', () => ({
  __esModule: true,
  default: ({ onSuccess, onCancel }) => (
    <div data-testid="mfa-panel">
      <button data-testid="mfa-fake-success" onClick={() => onSuccess({ role: 'teacher', tenant_id: 't1', mfa_enrolled_at: '2024-01-01' })}>ok</button>
      <button data-testid="mfa-fake-cancel" onClick={onCancel}>x</button>
    </div>
  ),
}));

// Lucide-react is heavy and pulls many SVGs — stub the icons we use.
jest.mock('lucide-react', () => new Proxy({}, {
  get: () => () => null,
}));

// Our own UI primitives — render minimal native equivalents so we can
// drive the form with fireEvent without needing Radix portals.
jest.mock('../../components/ui/button', () => ({
  Button: ({ children, asChild: _asChild, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('../../components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('../../components/ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('../../components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardHeader: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('../../components/ui/checkbox', () => ({
  Checkbox: ({ onCheckedChange, ...rest }) => (
    <input type="checkbox" onChange={(e) => onCheckedChange?.(e.target.checked)} {...rest} />
  ),
}));

// Import after mocks.
const { LoginPage } = require('../LoginPage');

const fillCredentials = (email = 'a@b.com', password = 'secret123') => {
  fireEvent.change(screen.getByTestId('login-email-input'), { target: { value: email } });
  fireEvent.change(screen.getByTestId('login-password-input'), { target: { value: password } });
};

const submit = () => fireEvent.click(screen.getByTestId('login-submit-btn'));

const flush = () => act(async () => { await Promise.resolve(); });

beforeEach(() => {
  mockNavigate.mockReset();
  mockToastSuccess.mockReset();
  mockToastError.mockReset();
  mockLogin.mockReset();
  mockRefreshUser.mockReset();
  mockClearAuthState.mockReset();
  mockNassaqError.mockReset();
});

describe('LoginPage — Task #195 success-and-error race', () => {
  test('successful teacher login: one toast, redirected to /teacher', async () => {
    mockLogin.mockResolvedValue({ success: true, user: { role: 'teacher' } });
    mockRefreshUser.mockResolvedValue({ role: 'teacher' });

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/teacher'));
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
    expect(mockNassaqError).not.toHaveBeenCalled();
    expect(mockToastError).not.toHaveBeenCalled();
  });

  test('successful principal login: redirected to /principal', async () => {
    mockLogin.mockResolvedValue({ success: true, user: { role: 'school_principal' } });
    mockRefreshUser.mockResolvedValue({ role: 'school_principal' });

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/principal'));
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
    expect(mockNassaqError).not.toHaveBeenCalled();
  });

  test('successful platform-admin login: redirected to /admin', async () => {
    mockLogin.mockResolvedValue({ success: true, user: { role: 'platform_admin' } });
    mockRefreshUser.mockResolvedValue({ role: 'platform_admin' });

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/admin'));
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
    expect(mockNassaqError).not.toHaveBeenCalled();
    expect(mockToastError).not.toHaveBeenCalled();
  });

  test('login OK but /auth/me fails: NO success toast, one error surface, partial state cleared', async () => {
    mockLogin.mockResolvedValue({ success: true, user: { role: 'teacher' } });
    mockRefreshUser.mockResolvedValue(null); // simulate /auth/me failure

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledTimes(1));
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(mockClearAuthState).toHaveBeenCalledTimes(1);
    // Submit button is re-enabled so the user can retry.
    expect(screen.getByTestId('login-submit-btn')).not.toBeDisabled();
  });

  test('login OK but role unresolved: NO success toast, one error surface, no redirect', async () => {
    mockLogin.mockResolvedValue({ success: true, user: { role: 'teacher' } });
    mockRefreshUser.mockResolvedValue({ role: 'martian_overlord' });

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledTimes(1));
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(mockClearAuthState).toHaveBeenCalledTimes(1);
  });

  test('credential failure: branded NassaqAlertDialog only, no toast', async () => {
    // Task #197 — all login failures (credential AND system) now
    // surface through the branded NassaqAlertDialog so the e2e
    // suite can lock a single error contract.
    mockLogin.mockResolvedValue({ success: false, error: 'بيانات الدخول غير صحيحة', kind: 'credentials', httpStatus: 401 });

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockLogin).toHaveBeenCalled());
    await flush();
    expect(mockNassaqError).toHaveBeenCalledTimes(1);
    expect(mockNassaqError.mock.calls[0][0]).toBe('بيانات الدخول غير صحيحة');
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockRefreshUser).not.toHaveBeenCalled();
  });

  test('MFA challenge → verify happy path: success toast fires only after redirect commits', async () => {
    mockLogin.mockResolvedValue({
      success: false,
      mfaChallenge: { challenge_token: 'c', available_factor_kinds: ['email_otp'] },
    });
    mockRefreshUser.mockResolvedValue({ role: 'teacher' });

    render(<LoginPage />);
    fillCredentials();
    submit();

    // Picker shows; no success toast yet.
    await waitFor(() => expect(screen.getByTestId('mfa-panel')).toBeInTheDocument());
    expect(mockToastSuccess).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId('mfa-fake-success'));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/teacher'));
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
    expect(mockNassaqError).not.toHaveBeenCalled();
  });

  test('system failure: only safe Arabic copy is shown, never raw backend detail', async () => {
    // Simulate the result auth.login() returns for a 5xx — login() must
    // map this to a safe Arabic string and tag kind=system; the page must
    // surface that string via nassaqError, never any raw backend payload.
    mockLogin.mockResolvedValue({
      success: false,
      error: 'خطأ في الاتصال بالخادم',
      kind: 'system',
      httpStatus: 500,
    });

    render(<LoginPage />);
    fillCredentials();
    submit();

    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledTimes(1));
    const surfacedMsg = mockNassaqError.mock.calls[0][0];
    // Must be Arabic safe copy — never a backend `detail` like
    // "Database connection refused" or a raw stack trace.
    expect(surfacedMsg).toBe('خطأ في الاتصال بالخادم');
    expect(surfacedMsg).not.toMatch(/Error|Exception|Traceback|refused|TypeError/i);
    expect(mockToastSuccess).not.toHaveBeenCalled();
  });

  test('double-click submit only fires one /auth/login attempt', async () => {
    let resolveLogin;
    mockLogin.mockImplementation(() => new Promise((r) => { resolveLogin = r; }));
    mockRefreshUser.mockResolvedValue({ role: 'teacher' });

    render(<LoginPage />);
    fillCredentials();
    submit();
    submit();
    submit();

    expect(mockLogin).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveLogin({ success: true, user: { role: 'teacher' } });
    });
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/teacher'));
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
  });
});
