/**
 * Task #297 — AccountSettingsPage section-by-section smoke render audit.
 *
 * Background: while wiring the workspace-hub render test (Task #254) we
 * found that AccountSettingsPage.jsx referenced an undefined `ToggleRow`
 * inside the auto-export sub-card (~line 1781), which crashed the
 * entire hub on first paint. The patch was a one-line alias
 * (`const ToggleRow = NotificationRow;`); this audit guarantees no
 * other latent "X is not defined" bugs survive in any sub-card.
 *
 * Strategy: deep-link into every section via `#hash`, mount the page,
 * and assert the section's wrapping testid renders. A render-time
 * `ReferenceError` would surface as a thrown error from `render(...)`
 * and fail the test — that is the actual smoke-coverage we need.
 *
 * Each non-IT section already has a `account-section-<id>` testid;
 * IT-only sections reuse their existing `it-*` testids. The IT-only
 * deep-flow assertions (export, soft-delete, hub aggregator, etc.)
 * remain in the dedicated AccountSettingsPage.it.test.jsx and
 * AccountSettingsPage.workspaceHub.test.jsx — this file's job is purely
 * to catch undefined-reference regressions.
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
const mockStableTeacherUser = Object.freeze({
  ...mockStableItUser,
  id: 'u-t-1',
  role: 'teacher',
  email: 'teacher@example.com',
});

const mockStableApi = Object.freeze({
  get: (...a) => mockApiGet(...a),
  put: (...a) => mockApiPut(...a),
  post: (...a) => mockApiPost(...a),
  delete: (...a) => mockApiDelete(...a),
});
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

jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(),
    nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn((_m, cb) => (typeof cb === 'function' ? cb() : undefined)),
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
  mockApiGet.mockImplementation((path, opts) => {
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
    if (path === '/independent-teacher/workspace/lifecycle') {
      return Promise.resolve({
        data: {
          workspace_id: 'itw_u-it-1',
          last_export_at: '2026-05-12T10:00:00+00:00',
          archived_at: null,
          pending_hard_delete: false,
          reactivation_banner: null,
          quota: {
            max_students: 200, current_students: 12,
            max_classes: null, current_classes: 2,
            max_imports_per_day: 5, imports_today: 1,
            max_lesson_plans_per_day: 20, lesson_plans_today: 3,
          },
        },
      });
    }
    if (path === '/classes') {
      return Promise.resolve({ data: [{ id: 'c1', name_ar: 'الفصل الأول' }] });
    }
    if (path === '/independent-teacher/workspace-collaborators') {
      const _cid = opts?.params?.class_id;
      return Promise.resolve({ data: { items: [] } });
    }
    if (path === '/independent-teacher/workspace/auto-export/settings') {
      return Promise.resolve({
        data: {
          enabled: false, day_of_week: 0, hour: 2,
          last_run_at: null, last_status: null, next_run_at: null,
        },
      });
    }
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
  mockAuthState.user = mockStableItUser;
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/account/settings');
  }
  wireDefaultGetResponses();
});

describe('AccountSettingsPage — Task #297 sub-card smoke renders', () => {
  // Non-IT (always-rendered) sections. These are visible to every role,
  // so we exercise them with a non-IT user to keep the IT-only branches
  // off and prove the core sections stand on their own.
  const coreSections = [
    ['profile', 'account-section-profile'],
    ['security', 'account-section-security'],
    ['notifications', 'account-section-notifications'],
    ['preferences', 'account-section-preferences'],
  ];

  test.each(coreSections)(
    'core section "%s" mounts without an undefined-reference crash',
    async (sectionId, testid) => {
      mockAuthState.user = mockStableTeacherUser;
      window.history.replaceState(null, '', `/account/settings#${sectionId}`);

      // render() throws synchronously on a render-time ReferenceError
      // (e.g. `ToggleRow is not defined`), so the mere fact that this
      // call returns is half the smoke check; the testid assertion
      // below pins the section actually rendered.
      render(<AccountSettingsPage />);
      await waitFor(() => expect(mockApiGet).toHaveBeenCalled());
      expect(screen.getByTestId(testid)).toBeInTheDocument();
    },
  );

  // IT-only sections — each owns its own testid scheme. Mounted with an
  // independent_teacher user and a deep-link hash so the corresponding
  // `activeSection === ...` branch fires.
  const itSections = [
    ['workspace', 'it-workspace-section'],
    ['communication', 'it-communication-section'],
    // 2026-05-18: inbox_prefs was merged into the notifications section;
    // the deep link now redirects there (see AccountSettingsPage hash
    // normalization) — assert the redirect target mounts.
    ['inbox_prefs', 'account-section-notifications'],
    ['export', 'it-export-section'],
  ];

  test.each(itSections)(
    'IT-only section "%s" mounts without an undefined-reference crash',
    async (sectionId, testid) => {
      window.history.replaceState(null, '', `/account/settings#${sectionId}`);
      render(<AccountSettingsPage />);
      await waitFor(() => expect(mockApiGet).toHaveBeenCalled());
      expect(await screen.findByTestId(testid)).toBeInTheDocument();
    },
  );

  // Workspace-hub renders four sub-cards; each must mount cleanly.
  // The original ToggleRow regression lived in the auto-export card,
  // so we explicitly assert that one in addition to the canonical four.
  test('workspace-hub mounts all five sub-cards without an undefined-reference crash', async () => {
    window.history.replaceState(null, '', '/account/settings#workspace-hub');
    render(<AccountSettingsPage />);

    expect(await screen.findByTestId('it-workspace-hub-section')).toBeInTheDocument();
    expect(await screen.findByTestId('it-hub-quota-card')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-export-card')).toBeInTheDocument();
    // Auto-export is the sub-card that originally referenced an
    // undefined ToggleRow — explicit smoke coverage prevents regression.
    expect(screen.getByTestId('it-hub-auto-export-card')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-collab-card')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-lifecycle-card')).toBeInTheDocument();
  });
});
