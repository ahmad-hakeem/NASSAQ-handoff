/**
 * Task #351 — Change Password handler routes MFA_RESTORE_REQUIRED to the
 * MFA Security section instead of opening the step-up modal or surfacing
 * the raw recovery-code wall-of-text in a generic error dialog.
 *
 * The backend already returns:
 *   HTTP 403
 *   { detail: { code: "MFA_RESTORE_REQUIRED", message: "تم استخدام رمز ..." } }
 *
 * The interceptor (AuthContext.js) is mocked at the api-client level via
 * a rejected POST. We assert that the catch branch:
 *   1. does NOT call the generic nassaqError fallback
 *   2. DOES call showAlert with a re-enrollment-focused dialog
 *   3. The dialog's onConfirm scrolls the MFA section into view
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
}), { virtual: true });

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApiPost = jest.fn();
const mockApiDelete = jest.fn();
const mockRefreshUser = jest.fn();
const mockLogout = jest.fn();
const mockUpdateToken = jest.fn();

const mockPrincipal = Object.freeze({
  id: 'u-prin-1',
  role: 'school_principal',
  full_name: 'Test Principal',
  email: 'p@example.com',
  phone: '0500000000',
  avatar_url: '',
  title: '',
});
const mockApi = Object.freeze({
  get: (...a) => mockApiGet(...a),
  put: (...a) => mockApiPut(...a),
  post: (...a) => mockApiPost(...a),
  delete: (...a) => mockApiDelete(...a),
});
const mockAuthState = { user: mockPrincipal };
const mockAuthCtx = {
  get user() { return mockAuthState.user; },
  api: mockApi,
  logout: mockLogout,
  refreshUser: mockRefreshUser,
  updateToken: mockUpdateToken,
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuthCtx,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({
    isRTL: true,
    toggleTheme: () => {},
    toggleLanguage: () => {},
    isDark: false,
    language: 'ar',
    setLanguage: () => {},
    theme: 'light',
    setTheme: () => {},
  }),
  useTranslation: () => ({ t: (k) => k }),
}));

const mockNassaqError = jest.fn();
const mockNassaqInfo = jest.fn();
const mockNassaqSuccess = jest.fn();
const mockNassaqWarning = jest.fn();
const mockNassaqConfirm = jest.fn();
const mockShowAlert = jest.fn();
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqInfo: mockNassaqInfo,
    nassaqSuccess: mockNassaqSuccess,
    nassaqWarning: mockNassaqWarning,
    nassaqConfirm: mockNassaqConfirm,
    showAlert: mockShowAlert,
  }),
}));

jest.mock('@/shared/components/GenericNameGuard', () => ({ isGenericName: () => false }));
jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar-shell">{children}</div>,
}));
jest.mock('@/features/hakim/components/hakim/HakimAssistant', () => ({ HakimAssistant: () => null }));
jest.mock('@/features/auth/components/mfa/MfaSecuritySection', () => () => (
  <div data-testid="mfa-security-section">mfa-security-section</div>
));
jest.mock('@/shared/components/ui/ImageCropModal', () => ({ ImageCropModal: () => null }));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, asChild: _a, onClick, ...rest }) => (
    <button onClick={onClick} {...rest}>{children}</button>
  ),
}));
jest.mock('@/shared/components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('@/shared/components/ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('@/shared/components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardHeader: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardTitle: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children, ...rest }) => <span {...rest}>{children}</span>,
}));
jest.mock('@/shared/components/ui/switch', () => ({
  Switch: ({ onCheckedChange, ...rest }) => (
    <input type="checkbox" onChange={(e) => onCheckedChange?.(e.target.checked)} {...rest} />
  ),
}));
jest.mock('@/shared/components/ui/avatar', () => ({
  Avatar: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  AvatarFallback: ({ children }) => <span>{children}</span>,
  AvatarImage: () => null,
}));
jest.mock('@/shared/components/ui/select', () => {
  const R = require('react');
  return {
    Select: ({ children }) => <div>{children}</div>,
    SelectContent: ({ children }) => <>{children}</>,
    SelectItem: () => null,
    SelectTrigger: ({ children }) => <>{children}</>,
    SelectValue: () => null,
  };
});
jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));
jest.mock('@/shared/components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }) => <div>{children}</div>,
  AlertDialogContent: ({ children }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <div>{children}</div>,
  AlertDialogDescription: ({ children }) => <div>{children}</div>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, ...rest }) => <button {...rest}>{children}</button>,
  AlertDialogCancel: ({ children, ...rest }) => <button {...rest}>{children}</button>,
}));

const { AccountSettingsPage } = require('../AccountSettingsPage');

const wireDefaultGetResponses = () => {
  mockApiGet.mockImplementation((path) => {
    if (path === '/users/me/profile') return Promise.resolve({ data: null });
    if (path === '/users/me/notifications') return Promise.resolve({ data: null });
    if (path === '/users/me/preferences') return Promise.resolve({ data: null });
    if (path === '/users/me/roles') return Promise.resolve({ data: { roles: [] } });
    if (path === '/settings/sessions') return Promise.resolve({ data: [] });
    return Promise.resolve({ data: null });
  });
};

beforeEach(() => {
  mockNavigate.mockReset();
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockApiDelete.mockReset();
  mockRefreshUser.mockReset();
  mockLogout.mockReset();
  mockNassaqError.mockReset();
  mockNassaqInfo.mockReset();
  mockNassaqSuccess.mockReset();
  mockNassaqWarning.mockReset();
  mockNassaqConfirm.mockReset();
  mockShowAlert.mockReset();
  mockAuthState.user = mockPrincipal;
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/account/settings#security');
  }
  wireDefaultGetResponses();
});

// Build a 403 axios-style error with a configurable response body so we
// can pin BOTH envelope shapes the backend can emit:
//   - Canonical wrapped: { success:false, error:{ code, message } }
//     (produced by backend/server.py http_exception_handler)
//   - Raw FastAPI: { detail: { code, message } }
const make403 = (body) => {
  const err = new Error('Request failed');
  err.response = { status: 403, data: body };
  return err;
};

const CANONICAL_BODY = {
  success: false,
  error: {
    code: 'MFA_RESTORE_REQUIRED',
    message:
      'تم استخدام رمز استرداد. يجب إعادة تسجيل عامل تحقق (مفتاح أمان أو تطبيق مصادقة) قبل المتابعة',
  },
};

const RAW_DETAIL_BODY = {
  detail: {
    code: 'MFA_RESTORE_REQUIRED',
    message:
      'تم استخدام رمز استرداد. يجب إعادة تسجيل عامل تحقق (مفتاح أمان أو تطبيق مصادقة) قبل المتابعة',
  },
};

const fillAndSubmit = async () => {
  const currentPwd = await screen.findByTestId('current-password');
  const newPwd = screen.getByTestId('new-password');
  const confirmPwd = screen.getByTestId('confirm-password');
  fireEvent.change(currentPwd, { target: { value: 'OldPass@123!' } });
  fireEvent.change(newPwd, { target: { value: 'BrandNew@123!' } });
  fireEvent.change(confirmPwd, { target: { value: 'BrandNew@123!' } });
  fireEvent.click(screen.getByTestId('save-password'));
};

const assertRestoreDialog = () => {
  expect(mockNassaqError).not.toHaveBeenCalled();
  const call = mockShowAlert.mock.calls[0][0];
  expect(call.type).toBe('warning');
  expect(call.showCancel).toBe(true);
  expect(typeof call.onConfirm).toBe('function');
  expect(call.message).toMatch(/رمز استرداد/);
  expect(call.message).toMatch(/التحقق بخطوتين|عامل تحقق/);
  const section = document.querySelector('[data-testid="mfa-security-section"]');
  expect(section).toBeTruthy();
  section.scrollIntoView = jest.fn();
  call.onConfirm();
  expect(section.scrollIntoView).toHaveBeenCalled();
};

describe('AccountSettingsPage handleChangePassword — MFA_RESTORE_REQUIRED', () => {
  test('canonical envelope { error: { code } } routes to MFA Security section', async () => {
    // The real backend wraps HTTPException via http_exception_handler so
    // the wire shape is `data.error.code`, NOT `data.detail.code`. This
    // test pins that shape so a future regression in the FE catch path
    // (e.g. only checking `data.detail.code`) is caught immediately.
    mockApiPost.mockImplementation((path) => {
      if (path === '/auth/change-password') return Promise.reject(make403(CANONICAL_BODY));
      return Promise.resolve({ data: null });
    });

    render(<AccountSettingsPage />);
    await fillAndSubmit();

    await waitFor(() => {
      expect(mockShowAlert).toHaveBeenCalledTimes(1);
    });
    assertRestoreDialog();
  });

  test('raw FastAPI envelope { detail: { code } } also routes to MFA Security section', async () => {
    // Defense-in-depth: any router that bypasses the global wrapper and
    // raises HTTPException(detail={...}) directly must still hit the
    // re-enrollment branch instead of the generic error fallback.
    mockApiPost.mockImplementation((path) => {
      if (path === '/auth/change-password') return Promise.reject(make403(RAW_DETAIL_BODY));
      return Promise.resolve({ data: null });
    });

    render(<AccountSettingsPage />);
    await fillAndSubmit();

    await waitFor(() => {
      expect(mockShowAlert).toHaveBeenCalledTimes(1);
    });
    assertRestoreDialog();
  });

  test('canonical envelope with non-restore code falls through to nassaqError using error.message', async () => {
    // Regression guard: a generic 400 in the canonical wrapped shape
    // (e.g. wrong current password) must surface the Arabic
    // `error.message` via nassaqError — NOT the recovery-code dialog
    // and NOT a generic translation key fallback.
    const arabic = 'كلمة المرور الحالية غير صحيحة';
    mockApiPost.mockImplementation((path) => {
      if (path === '/auth/change-password') {
        const err = new Error('Request failed');
        err.response = {
          status: 400,
          data: { success: false, error: { code: 'INVALID_CURRENT_PASSWORD', message: arabic } },
        };
        return Promise.reject(err);
      }
      return Promise.resolve({ data: null });
    });

    render(<AccountSettingsPage />);
    await fillAndSubmit();

    await waitFor(() => {
      expect(mockNassaqError).toHaveBeenCalledTimes(1);
    });
    expect(mockShowAlert).not.toHaveBeenCalled();
    expect(mockNassaqError).toHaveBeenCalledWith(arabic);
  });
});
