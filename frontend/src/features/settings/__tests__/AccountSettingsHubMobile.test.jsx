/**
 * Task #274 — AccountSettingsPage workspace-hub danger-zone mobile contract.
 *
 * The pending-collaborator list inside the workspace-hub section was
 * migrated to ResponsiveTable so phones get stacked label/value cards
 * (with a full-width cancel CTA) instead of a horizontally overflowing
 * `<table>`. This test loads the hub at 360px wide, seeds one pending
 * collaborator, and asserts the mobile-cards branch mounts and renders
 * the full-width cancel button.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

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

// useAuth / useTranslation mocks MUST return module-level stable objects:
// fresh objects per call loop useCallback/useEffect dependency chains
// ("Maximum update depth exceeded").
const mockStableUser = {
  id: 'u-it-1',
  role: 'independent_teacher',
  full_name: 'Test IT',
  email: 'it@example.com',
  phone: '0500000000',
  avatar_url: '',
  title: '',
};
const mockStableApi = {
  get: (...a) => mockApiGet(...a),
  put: (...a) => mockApiPut(...a),
  post: (...a) => mockApiPost(...a),
  delete: (...a) => mockApiDelete(...a),
};
const mockNoop = () => {};
const mockStableAuth = {
  user: mockStableUser,
  api: mockStableApi,
  logout: mockNoop,
  refreshUser: mockNoop,
  updateToken: mockNoop,
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockStableAuth,
}));

const mockStableTheme = {
  isRTL: true, toggleTheme: mockNoop, toggleLanguage: mockNoop,
  isDark: false, language: 'ar', setLanguage: mockNoop,
  theme: 'light', setTheme: mockNoop,
};
const mockStableTranslation = { t: (k) => k };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => mockStableTheme,
  useTranslation: () => mockStableTranslation,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(), nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(), nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('@/shared/components/GenericNameGuard', () => ({ isGenericName: () => false }));
jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar-shell">{children}</div>,
}));
jest.mock('@/features/hakim/components/hakim/HakimAssistant', () => ({ HakimAssistant: () => null }));
jest.mock('@/features/auth/components/mfa/MfaSecuritySection', () => () => null);
jest.mock('@/shared/components/ui/ImageCropModal', () => ({ ImageCropModal: () => null }));
jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, asChild: _asChild, ...rest }) => (
    <button {...rest}>{children}</button>
  ),
}));
// Radix primitives' compose-refs logic loops setState under jsdom —
// replace them with plain elements (mirrors the workspaceHub suite).
jest.mock('@/shared/components/ui/switch', () => ({
  Switch: ({ onCheckedChange, ...rest }) => (
    <input type="checkbox" onChange={(e) => onCheckedChange?.(e.target.checked)} {...rest} />
  ),
}));
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
jest.mock('@/shared/components/ui/avatar', () => ({
  Avatar: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  AvatarFallback: ({ children }) => <span>{children}</span>,
  AvatarImage: () => null,
}));
jest.mock('@/shared/components/ui/select', () => {
  const R = require('react');
  const Select = ({ value, onValueChange, children }) => {
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
      <select value={value || ''} onChange={(e) => onValueChange?.(e.target.value)}>
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
jest.mock('@/shared/components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});

import AccountSettingsPage from '../AccountSettingsPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockApiDelete.mockReset();
  window.history.replaceState(null, '', '/account/settings#workspace-hub');
});

test('workspace-hub at 360px renders pending-collab cards through ResponsiveTable mobile branch', async () => {
  mockApiGet.mockImplementation((path) => {
    if (path === '/independent-teacher/workspace/lifecycle') {
      return Promise.resolve({ data: { quota: { max_students: 200, students_used: 0 } } });
    }
    if (path === '/classes') {
      return Promise.resolve({ data: [{ id: 'c-1', name: 'الصف الأول' }] });
    }
    if (path === '/independent-teacher/workspace-collaborators') {
      return Promise.resolve({
        data: {
          items: [
            {
              id: 'collab-1',
              status: 'pending',
              collaborator_email: 'invitee@example.com',
              class_id: 'c-1',
              class_name: 'الصف الأول',
            },
          ],
        },
      });
    }
    if (path === '/independent-teacher/workspace/settings') {
      return Promise.resolve({ data: { name_ar: 'م', name_en: 'W', logo_url: '' } });
    }
    return Promise.resolve({ data: null });
  });

  render(<AccountSettingsPage />);

  // The hub section mounts on the deep-link hash; wait for the
  // pending-collab list (data-testid kept stable for the §6.7 E2E suite).
  await waitFor(() => {
    expect(screen.getByTestId('it-hub-collab-pending-list')).toBeInTheDocument();
  }, { timeout: 4000 });

  // ResponsiveTable mounts both branches; the mobile-cards tree is the
  // contract phones rely on at 360px.
  const mobile = await screen.findByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('invitee@example.com');
  expect(mobile.textContent).toContain('الصف الأول');

  // The cancel CTA inside a mobile card must be full-width (the
  // `mobileFullWidth: true` column flag wraps the cell so phones get a
  // tappable affordance instead of a tiny right-aligned button).
  const cancelBtns = mobile.querySelectorAll('[data-testid^="it-hub-collab-cancel-"]');
  expect(cancelBtns.length).toBeGreaterThan(0);
  expect(cancelBtns[0].className).toMatch(/w-full/);
});
