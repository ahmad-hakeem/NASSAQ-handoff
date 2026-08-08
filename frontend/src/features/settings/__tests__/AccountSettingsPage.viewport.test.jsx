jest.setTimeout(20000);

/**
 * Task #281 — AccountSettingsPage mobile-viewport snapshots (IT user).
 *
 * Renders the IT-flavoured Account Settings page at the four target
 * widths (360 / 414 / 768 / 1024 px) and snapshots a stable structural
 * fingerprint per width. Mocks mirror AccountSettingsPage.it.test.jsx
 * to keep this fast and deterministic in jest/jsdom.
 */
import React from 'react';
import { render, waitFor, act } from '@testing-library/react';

import {
  TARGET_WIDTHS,
  setViewport,
  fingerprintContainer,
} from '../../testUtils/mobileViewportFingerprint';

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
const mockStableAuthCtx = {
  user: mockStableItUser,
  api: mockStableApi,
  logout: jest.fn(),
  refreshUser: jest.fn(),
  updateToken: jest.fn(),
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockStableAuthCtx,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({
    isRTL: true, toggleTheme: () => {}, toggleLanguage: () => {},
    isDark: false, language: 'ar', setLanguage: () => {},
    theme: 'light', setTheme: () => {},
  }),
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(), nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(), nassaqWarning: jest.fn(),
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

const { AccountSettingsPage } = require('../AccountSettingsPage');

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockApiDelete.mockReset();
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/account/settings');
  }
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
      data: { name_ar: 'مساحة الاختبار', name_en: 'Test Workspace', logo_url: '' },
    });
    return Promise.resolve({ data: null });
  });
});

describe.each(TARGET_WIDTHS)(
  'AccountSettingsPage (IT) at %ipx — Task #281 viewport fingerprint',
  (width) => {
    test(`fingerprint @ ${width}px is stable`, async () => {
      setViewport(width);
      const { container } = render(<AccountSettingsPage />);
      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith('/users/me/preferences');
      });
      await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
      expect(fingerprintContainer(container, width)).toMatchSnapshot();
    });
  },
);
