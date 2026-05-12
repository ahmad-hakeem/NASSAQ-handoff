/**
 * Task #200 §5.8 — AccountSettingsPage IT-only sections smoke test.
 *
 * Verifies that an Independent-Teacher (IT) user sees the three new
 * sections (Workspace, Communication preferences, Data export) in the
 * settings nav, that the workspace identity is loaded from the
 * /independent-teacher/workspace/settings endpoint, and that the
 * coming-soon export action routes through NassaqAlertDialog (nassaqInfo)
 * rather than a native browser alert or toast.error per replit.md.
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

const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();
jest.mock('sonner', () => ({
  toast: {
    success: (...a) => mockToastSuccess(...a),
    error: (...a) => mockToastError(...a),
  },
}));

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApiPost = jest.fn();
const mockApiDelete = jest.fn();
const mockRefreshUser = jest.fn();
const mockLogout = jest.fn();
const mockUpdateToken = jest.fn();

const mockStableItUser = Object.freeze({
  id: 'u-it-1',
  role: 'independent_teacher',
  full_name: 'Test IT',
  email: 'it@example.com',
  phone: '0500000000',
  avatar_url: '',
  title: '',
});
const mockStableApi = Object.freeze({
  get: (...a) => mockApiGet(...a),
  put: (...a) => mockApiPut(...a),
  post: (...a) => mockApiPost(...a),
  delete: (...a) => mockApiDelete(...a),
});
// Mutable holder so individual tests can flip the active role without
// re-mocking the AuthContext module (factory-bound `mock*` symbol).
const mockAuthState = { user: mockStableItUser };
const mockStableAuthCtx = {
  get user() { return mockAuthState.user; },
  api: mockStableApi,
  logout: mockLogout,
  refreshUser: mockRefreshUser,
  updateToken: mockUpdateToken,
};
jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockStableAuthCtx,
}));

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

const mockNassaqError = jest.fn();
const mockNassaqInfo = jest.fn();
const mockNassaqSuccess = jest.fn();
const mockNassaqWarning = jest.fn();
jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqInfo: mockNassaqInfo,
    nassaqSuccess: mockNassaqSuccess,
    nassaqWarning: mockNassaqWarning,
  }),
}));

jest.mock('../../components/GenericNameGuard', () => ({
  isGenericName: () => false,
}));
jest.mock('../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar-shell">{children}</div>,
}));
jest.mock('../../components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => null,
}));
jest.mock('../../components/mfa/MfaSecuritySection', () => () => null);
jest.mock('../../components/ui/ImageCropModal', () => ({
  ImageCropModal: () => null,
}));

jest.mock('lucide-react', () => new Proxy({}, {
  get: () => () => null,
}));

jest.mock('../../components/ui/button', () => ({
  Button: ({ children, asChild: _asChild, ...rest }) => (
    <button {...rest}>{children}</button>
  ),
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
  const Select = ({ value, onValueChange, children }) => {
    // Render a native select wired by inspecting child SelectItem nodes.
    const items = [];
    R.Children.forEach(children, (child) => {
      if (!child) return;
      R.Children.forEach(child.props?.children, (grand) => {
        if (grand?.props?.value !== undefined) {
          items.push({ value: grand.props.value, label: grand.props.children });
        }
      });
    });
    return (
      <select
        value={value || ''}
        onChange={(e) => onValueChange?.(e.target.value)}
        data-testid={`select-${items.map(i => i.value).join('-') || 'empty'}`}
      >
        {items.map(i => (
          <option key={i.value} value={i.value}>{typeof i.label === 'string' ? i.label : i.value}</option>
        ))}
      </select>
    );
  };
  return {
    Select,
    SelectContent: ({ children }) => <>{children}</>,
    SelectItem: () => null,
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

const { AccountSettingsPage } = require('../AccountSettingsPage');

const wireDefaultGetResponses = () => {
  mockApiGet.mockImplementation((path) => {
    if (path === '/users/me/profile') return Promise.resolve({ data: null });
    if (path === '/users/me/notifications') return Promise.resolve({ data: null });
    if (path === '/users/me/preferences') return Promise.resolve({
      data: {
        language: 'ar', theme: 'light', time_format: '12h',
        date_format: 'dd/mm/yyyy', first_day_of_week: 'sunday',
        it_communication: {
          default_channel: 'sms',
          quiet_hours_start: '22:00',
          quiet_hours_end: '06:00',
        },
      },
    });
    if (path === '/users/me/roles') return Promise.resolve({ data: { roles: [] } });
    if (path === '/settings/sessions') return Promise.resolve({ data: [] });
    if (path === '/independent-teacher/workspace/settings') return Promise.resolve({
      data: {
        name_ar: 'مساحة الاختبار',
        name_en: 'Test Workspace',
        logo_url: '',
      },
    });
    return Promise.resolve({ data: null });
  });
};

beforeEach(() => {
  mockNavigate.mockReset();
  mockToastSuccess.mockReset();
  mockToastError.mockReset();
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
  mockAuthState.user = mockStableItUser;
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/account/settings');
  }
  wireDefaultGetResponses();
});

describe('AccountSettingsPage — Task #200 §5.8 IT-only sections', () => {
  test('IT user: workspace identity loads from /independent-teacher/workspace/settings', async () => {
    window.history.replaceState(null, '', '/account/settings#workspace');
    render(<AccountSettingsPage />);

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/independent-teacher/workspace/settings');
    });

    await waitFor(() => {
      expect(screen.getByTestId('it-workspace-section')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByTestId('it-workspace-name-ar')).toHaveValue('مساحة الاختبار');
    });
    expect(screen.getByTestId('it-workspace-name-en')).toHaveValue('Test Workspace');
  });

  test('IT user: data-export uses nassaqInfo (no native alert, no toast.error)', async () => {
    window.history.replaceState(null, '', '/account/settings#export');
    render(<AccountSettingsPage />);

    const btn = await screen.findByTestId('it-export-coming-soon-btn');
    fireEvent.click(btn);

    expect(mockNassaqInfo).toHaveBeenCalledTimes(1);
    expect(mockToastError).not.toHaveBeenCalled();
  });

  test('IT user: communication save PUTs it_communication blob to /users/me/preferences', async () => {
    window.history.replaceState(null, '', '/account/settings#communication');
    mockApiPut.mockResolvedValue({ data: { success: true } });

    render(<AccountSettingsPage />);

    await screen.findByTestId('it-communication-section');
    fireEvent.click(screen.getByTestId('save-communication'));

    await waitFor(() => {
      expect(mockApiPut).toHaveBeenCalledWith(
        '/users/me/preferences',
        expect.objectContaining({
          it_communication: expect.objectContaining({
            default_channel: expect.any(String),
            quiet_hours_start: expect.any(String),
            quiet_hours_end: expect.any(String),
          }),
        }),
      );
    });
  });

  test('IT user: workspace save PUTs to /independent-teacher/workspace/settings (round-trip)', async () => {
    window.history.replaceState(null, '', '/account/settings#workspace');
    mockApiPut.mockResolvedValue({ data: { success: true } });

    render(<AccountSettingsPage />);

    await screen.findByTestId('it-workspace-section');
    await waitFor(() => {
      expect(screen.getByTestId('it-workspace-name-ar')).toHaveValue('مساحة الاختبار');
    });

    // Mutate name_ar then save: PUT must hit the canonical workspace
    // endpoint with the trimmed name, mirroring WorkspaceSettingsPage's
    // contract.
    fireEvent.change(screen.getByTestId('it-workspace-name-ar'), {
      target: { value: 'مساحة محدثة' },
    });
    fireEvent.click(screen.getByTestId('save-workspace'));

    await waitFor(() => {
      expect(mockApiPut).toHaveBeenCalledWith(
        '/independent-teacher/workspace/settings',
        expect.objectContaining({
          name_ar: 'مساحة محدثة',
          name_en: 'Test Workspace',
        }),
      );
    });
    // Success surfaces through NassaqAlertDialog (nassaqSuccess), never
    // through toast.error or a native browser dialog.
    await waitFor(() => {
      expect(mockNassaqSuccess).toHaveBeenCalled();
    });
    expect(mockToastError).not.toHaveBeenCalled();
  });

  test.each([
    ['teacher'],
    ['principal'],
    ['admin'],
  ])('non-IT role %s: the three IT-only sections are not rendered', async (role) => {
    mockAuthState.user = Object.freeze({
      ...mockStableItUser,
      id: `u-${role}-1`,
      role,
      email: `${role}@example.com`,
    });
    render(<AccountSettingsPage />);

    // Wait for the page mount + initial fetch cycle to settle so we're
    // not asserting against a transient render. Any GET against the user
    // endpoints proves the effect has run for the non-IT branch.
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalled();
    });

    expect(screen.queryByTestId('it-workspace-section')).toBeNull();
    expect(screen.queryByTestId('it-communication-section')).toBeNull();
    expect(screen.queryByTestId('it-export-section')).toBeNull();
    expect(screen.queryByTestId('it-export-coming-soon-btn')).toBeNull();

    // Non-IT roles must never trigger the workspace identity fetch.
    expect(mockApiGet).not.toHaveBeenCalledWith('/independent-teacher/workspace/settings');
  });
});
