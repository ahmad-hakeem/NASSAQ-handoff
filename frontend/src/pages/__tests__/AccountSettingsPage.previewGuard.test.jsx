/**
 * Task #496 — Block Account Settings in school preview mode.
 *
 * When a Platform Admin is in school preview mode
 * (`isImpersonating && schoolContext`), AccountSettingsPage must render
 * the preview-mode guard instead of the personal form. The personal
 * profile inputs/fetches must not appear, and clicking the exit CTA
 * must call `exitSchoolContext()` so the page can remount with the
 * Platform Admin's own identity.
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
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApiPost = jest.fn();
const mockApiDelete = jest.fn();
const mockRefreshUser = jest.fn();
const mockLogout = jest.fn();
const mockUpdateToken = jest.fn();
const mockExitSchoolContext = jest.fn();

const platformAdminUser = Object.freeze({
  id: 'u-pa-1',
  role: 'platform_admin',
  full_name: 'Ahmed Hakim',
  email: 'admin@example.com',
  phone: '0500000000',
  avatar_url: '',
  title: '',
});

const mockAuthState = {
  user: platformAdminUser,
  isImpersonating: false,
  schoolContext: null,
};

jest.mock('../../contexts/AuthContext', () => {
  const api = {
    get: (...a) => mockApiGet(...a),
    put: (...a) => mockApiPut(...a),
    post: (...a) => mockApiPost(...a),
    delete: (...a) => mockApiDelete(...a),
  };
  return {
    useAuth: () => ({
      get user() { return mockAuthState.user; },
      get isImpersonating() { return mockAuthState.isImpersonating; },
      get schoolContext() { return mockAuthState.schoolContext; },
      exitSchoolContext: (...a) => mockExitSchoolContext(...a),
      api,
      logout: mockLogout,
      refreshUser: mockRefreshUser,
      updateToken: mockUpdateToken,
    }),
  };
});

jest.mock('../../contexts/ThemeContext', () => ({
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

jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(),
    nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
    showAlert: jest.fn(),
  }),
}));

jest.mock('../../components/GenericNameGuard', () => ({ isGenericName: () => false }));
jest.mock('../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar-shell">{children}</div>,
}));
jest.mock('../../components/hakim/HakimAssistant', () => ({ HakimAssistant: () => null }));
jest.mock('../../components/teacher/TeachingStatsHero', () => () => null);
jest.mock('../../components/mfa/MfaSecuritySection', () => () => null);
jest.mock('../../components/ui/ImageCropModal', () => ({ ImageCropModal: () => null }));
jest.mock('../../components/ui/ResponsiveTable', () => ({ ResponsiveTable: () => null }));
jest.mock('../../hooks/useWorkspaceHubData', () => ({ useWorkspaceHubData: () => ({}) }));
jest.mock('./TeacherModule', () => ({ TeacherAuditLogPanel: () => null }), { virtual: true });
jest.mock('../TeacherModule', () => ({ TeacherAuditLogPanel: () => null }), { virtual: true });

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../../components/ui/button', () => ({
  Button: ({ children, asChild: _asChild, ...rest }) => (
    <button {...rest}>{children}</button>
  ),
}));
jest.mock('../../components/ui/input', () => {
  const R = require('react');
  return {
    Input: R.forwardRef((props, ref) =>
      R.createElement('input', { ref, 'data-testid': props['data-testid'] || `input-${props.name || ''}`, ...props })),
  };
});
jest.mock('../../components/ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('../../components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardHeader: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardTitle: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('../../components/ui/badge', () => ({
  Badge: ({ children, ...rest }) => <span {...rest}>{children}</span>,
}));
jest.mock('../../components/ui/switch', () => ({
  Switch: ({ onCheckedChange, ...rest }) => (
    <input type="checkbox" onChange={(e) => onCheckedChange?.(e.target.checked)} {...rest} />
  ),
}));
jest.mock('../../components/ui/avatar', () => ({
  Avatar: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  AvatarFallback: ({ children }) => <span>{children}</span>,
  AvatarImage: () => null,
}));
jest.mock('../../components/ui/select', () => {
  const R = require('react');
  const Select = ({ value, onValueChange, children }) => (
    <select value={value || ''} onChange={(e) => onValueChange?.(e.target.value)}>
      {R.Children.toArray(children)}
    </select>
  );
  return {
    Select,
    SelectContent: ({ children }) => <>{children}</>,
    SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
    SelectTrigger: ({ children }) => <>{children}</>,
    SelectValue: () => null,
  };
});
jest.mock('../../components/ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }) => <div>{children}</div>,
  AlertDialogContent: ({ children }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <div>{children}</div>,
  AlertDialogDescription: ({ children }) => <div>{children}</div>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, ...rest }) => <button {...rest}>{children}</button>,
  AlertDialogCancel: ({ children, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('recharts', () => ({
  LineChart: () => null,
  Line: () => null,
  ResponsiveContainer: () => null,
  YAxis: () => null,
}));

const { AccountSettingsPage } = require('../AccountSettingsPage');

beforeEach(() => {
  mockNavigate.mockReset();
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockApiDelete.mockReset();
  mockRefreshUser.mockReset();
  mockLogout.mockReset();
  mockExitSchoolContext.mockReset();
  mockAuthState.user = platformAdminUser;
  mockAuthState.isImpersonating = false;
  mockAuthState.schoolContext = null;
  mockApiGet.mockResolvedValue({ data: null });
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/account/settings');
  }
});

describe('AccountSettingsPage — Task #496 preview-mode guard', () => {
  test('renders the guard (not the personal form) while in school preview mode', async () => {
    mockAuthState.isImpersonating = true;
    mockAuthState.schoolContext = {
      school_id: 'school-1',
      school_name: 'مدرسة الاختبار',
      school_name_en: 'Test School',
      school_code: 'TST',
    };

    render(<AccountSettingsPage />);

    // Guard is shown
    expect(screen.getByTestId('account-settings-preview-guard')).toBeInTheDocument();
    expect(screen.getByTestId('account-settings-preview-exit-btn')).toBeInTheDocument();
    expect(screen.getByText(/مدرسة الاختبار/)).toBeInTheDocument();

    // The personal-form page is NOT mounted: no profile/avatar/header,
    // no /users/me/* fetches fired by the inner component's effects.
    expect(screen.queryByTestId('account-settings-page')).toBeNull();
    expect(mockApiGet).not.toHaveBeenCalledWith('/users/me/notifications');
    expect(mockApiGet).not.toHaveBeenCalledWith('/users/me/preferences');
    expect(mockApiGet).not.toHaveBeenCalledWith('/settings/sessions');
  });

  test('exit CTA calls exitSchoolContext and the personal form mounts after exit', async () => {
    // Start in preview mode.
    mockAuthState.isImpersonating = true;
    mockAuthState.schoolContext = {
      school_id: 'school-1',
      school_name: 'مدرسة الاختبار',
      school_name_en: 'Test School',
      school_code: 'TST',
    };

    // Avoid jsdom navigation noise from window.location.assign by stubbing it.
    const originalLocation = window.location;
    delete window.location;
    window.location = { ...originalLocation, assign: jest.fn() };

    const { rerender } = render(<AccountSettingsPage />);

    fireEvent.click(screen.getByTestId('account-settings-preview-exit-btn'));

    expect(mockExitSchoolContext).toHaveBeenCalledTimes(1);

    // Simulate AuthContext clearing preview state (what exitSchoolContext
    // does) and re-render the page in the now-normal Platform Admin shell.
    mockAuthState.isImpersonating = false;
    mockAuthState.schoolContext = null;
    rerender(<AccountSettingsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('account-settings-page')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('account-settings-preview-guard')).toBeNull();

    window.location = originalLocation;
  });

  test('no-op outside preview mode: personal form mounts normally', async () => {
    render(<AccountSettingsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('account-settings-page')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('account-settings-preview-guard')).toBeNull();
  });
});
