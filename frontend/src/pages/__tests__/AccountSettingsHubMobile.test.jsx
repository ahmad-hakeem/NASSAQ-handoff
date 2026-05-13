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

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'u-it-1',
      role: 'independent_teacher',
      full_name: 'Test IT',
      email: 'it@example.com',
      phone: '0500000000',
      avatar_url: '',
      title: '',
    },
    api: {
      get: (...a) => mockApiGet(...a),
      put: (...a) => mockApiPut(...a),
      post: (...a) => mockApiPost(...a),
      delete: (...a) => mockApiDelete(...a),
    },
    logout: jest.fn(),
    refreshUser: jest.fn(),
    updateToken: jest.fn(),
  }),
}));

jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    isRTL: true, toggleTheme: () => {}, toggleLanguage: () => {},
    isDark: false, language: 'ar', setLanguage: () => {},
    theme: 'light', setTheme: () => {},
  }),
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(), nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(), nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('../../components/GenericNameGuard', () => ({ isGenericName: () => false }));
jest.mock('../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar-shell">{children}</div>,
}));
jest.mock('../../components/hakim/HakimAssistant', () => ({ HakimAssistant: () => null }));
jest.mock('../../components/mfa/MfaSecuritySection', () => () => null);
jest.mock('../../components/ui/ImageCropModal', () => ({ ImageCropModal: () => null }));
jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
jest.mock('../../components/ui/button', () => ({
  Button: ({ children, asChild: _asChild, ...rest }) => (
    <button {...rest}>{children}</button>
  ),
}));
jest.mock('../../components/ui/input', () => {
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
