/**
 * Task #254 — End-to-end render test for the Independent-Teacher
 * "إعدادات المساحة" (workspace-hub) hub on AccountSettingsPage.
 *
 * Mirrors the AccountSettingsPage.it.test.jsx mock harness so the page
 * renders inside Jest/jsdom without pulling in routing/sidebar/icons.
 *
 * Covers:
 *   1. Sidebar entry — visible only for Independent-Teacher users.
 *   2. Deep-link `#workspace-hub` activates the section on first mount.
 *   3. All four sub-cards (Quota / Export / Collaborators / Lifecycle)
 *      render once the aggregator hook resolves.
 *   4. Cancel (pending) and Reactivate destructive actions route
 *      through nassaqConfirm and call the canonical endpoints.
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
// nassaqConfirm fires the supplied onConfirm callback synchronously so
// the destructive flows (cancel / revoke / reactivate) run end-to-end
// without a real dialog. Per replit.md, native confirm() / toast.error
// are forbidden — production code routes everything through here.
const mockNassaqConfirm = jest.fn((_message, onConfirm /* , _opts */) => {
  if (typeof onConfirm === 'function') return onConfirm();
  return undefined;
});
jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqInfo: mockNassaqInfo,
    nassaqSuccess: mockNassaqSuccess,
    nassaqWarning: mockNassaqWarning,
    nassaqConfirm: mockNassaqConfirm,
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

// Hub fixture state — individual tests can override before render() to
// flip lifecycle status, change collaborator rows, etc.
let hubFixture;

const _resetHubFixture = () => {
  hubFixture = {
    lifecycle: {
      workspace_id: 'itw_u-it-1',
      last_export_at: '2026-05-12T10:00:00+00:00',
      archived_at: null,
      pending_hard_delete: false,
      reactivation_banner: null,
      quota: {
        max_students: 200,
        current_students: 12,
        max_classes: 5,
        current_classes: 2,
        max_imports_per_day: 5,
        imports_today: 1,
        max_lesson_plans_per_day: 20,
        lesson_plans_today: 3,
      },
    },
    classes: [
      { id: 'c1', name_ar: 'الفصل الأول' },
      { id: 'c2', name_ar: 'الفصل الثاني' },
    ],
    // Per-class collaborator items, keyed by class_id.
    collabByClass: {
      c1: [
        { id: 'co-active', collaborator_email: 'active@x.com', status: 'accepted' },
        { id: 'co-pending', collaborator_email: 'pending@x.com', status: 'pending' },
      ],
      c2: [],
    },
  };
};

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
      return Promise.resolve({ data: hubFixture.lifecycle });
    }
    if (path === '/classes') {
      return Promise.resolve({ data: hubFixture.classes });
    }
    if (path === '/independent-teacher/workspace-collaborators') {
      const cid = opts?.params?.class_id;
      return Promise.resolve({ data: { items: hubFixture.collabByClass[cid] || [] } });
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
  mockNassaqConfirm.mockReset();
  // CRA's react-scripts sets resetMocks:true by default, which wipes the
  // jest.fn(impl) constructor implementation before every test. Re-apply
  // the "fire the supplied callback" behaviour so destructive flows
  // (cancel / revoke / reactivate) actually run end-to-end.
  mockNassaqConfirm.mockImplementation((_message, onConfirm /* , _opts */) => {
    if (typeof onConfirm === 'function') return onConfirm();
    return undefined;
  });
  mockAuthState.user = mockStableItUser;
  if (typeof window !== 'undefined') {
    window.history.replaceState(null, '', '/account/settings');
  }
  _resetHubFixture();
  wireDefaultGetResponses();
});

describe('AccountSettingsPage — Task #254 workspace-hub e2e render', () => {
  test('IT user: sidebar entry "itHubSection" appears in the section nav', async () => {
    render(<AccountSettingsPage />);
    // Wait for the page to mount + initial fetches to settle.
    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());
    // Section labels come from t(key); with the identity-t() mock the
    // label renders as the literal i18n key, which is unique per section.
    expect(screen.getByText('itHubSection')).toBeInTheDocument();
  });

  test.each([
    ['teacher'],
    ['principal'],
    ['parent'],
  ])('non-IT %s: hub sidebar entry is hidden', async (role) => {
    mockAuthState.user = Object.freeze({
      ...mockStableItUser,
      id: `u-${role}-1`,
      role,
      email: `${role}@example.com`,
    });
    render(<AccountSettingsPage />);
    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());
    expect(screen.queryByText('itHubSection')).toBeNull();
    // Non-IT must never trigger the hub aggregator's lifecycle fetch.
    expect(mockApiGet).not.toHaveBeenCalledWith(
      '/independent-teacher/workspace/lifecycle',
    );
  });

  test('deep-link #workspace-hub activates the hub and renders all four sub-cards', async () => {
    window.history.replaceState(null, '', '/account/settings#workspace-hub');
    render(<AccountSettingsPage />);

    // Section container appears => active section was picked up from hash.
    await screen.findByTestId('it-workspace-hub-section');

    // The aggregator hook fans out to lifecycle + classes + per-class
    // collaborators. All three are required for the four-card render.
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith(
        '/independent-teacher/workspace/lifecycle',
      );
    });
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/classes');
    });
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith(
        '/independent-teacher/workspace-collaborators',
        expect.objectContaining({ params: { class_id: 'c1' } }),
      );
    });

    // All four sub-cards present.
    expect(screen.getByTestId('it-hub-quota-card')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-export-card')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-collab-card')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-lifecycle-card')).toBeInTheDocument();

    // Quota bars rendered once data resolved (loading state cleared).
    await waitFor(() => {
      expect(screen.getByTestId('it-hub-quota-students')).toBeInTheDocument();
    });
    expect(screen.getByTestId('it-hub-quota-classes')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-quota-imports')).toBeInTheDocument();
    expect(screen.getByTestId('it-hub-quota-lesson-plans')).toBeInTheDocument();

    // Active workspace → status badge says active, no archived chip.
    await waitFor(() => {
      expect(screen.getByTestId('it-hub-lifecycle-status')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('it-hub-lifecycle-archived-at')).toBeNull();
    expect(screen.queryByTestId('it-hub-reactivate-btn')).toBeNull();
  });

  test('cancel pending collaborator routes through nassaqConfirm and POSTs to /cancel', async () => {
    window.history.replaceState(null, '', '/account/settings#workspace-hub');
    mockApiPost.mockResolvedValue({ data: { ok: true } });

    render(<AccountSettingsPage />);

    // The collab pending row is rendered through ResponsiveTable, which
    // emits BOTH a desktop `<table>` (hidden sm:block) and a mobile
    // stacked card (sm:hidden) variant of every row. jsdom does not
    // apply Tailwind CSS, so both copies stay in the DOM and the
    // `it-hub-collab-cancel-{id}` testid resolves to two elements —
    // which makes `findByTestId` throw "Found multiple elements". Use
    // `findAllByTestId` and click the first match (desktop table row);
    // the mobile copy fires the same handler so picking either is fine.
    const cancelBtns = await screen.findAllByTestId(
      'it-hub-collab-cancel-co-pending',
      {},
      { timeout: 3000 },
    );
    expect(cancelBtns.length).toBeGreaterThan(0);
    const cancelBtn = cancelBtns[0];

    // Wrap the click in act + flush microtasks so the async confirm
    // callback (which awaits api.post) is observed by waitFor.
    await act(async () => {
      fireEvent.click(cancelBtn);
    });

    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalled());
    // The cancel button passes the pending row down through
    // handleHubCollabAction, whose nassaqConfirm callback awaits the
    // /cancel POST. Asserting the URL pins both the dispatch branch
    // (status=pending → cancel, not delete) and the row id wiring.
    await waitFor(() => {
      const cancelCalls = mockApiPost.mock.calls.filter(
        ([url]) => typeof url === 'string' && url.endsWith('/cancel'),
      );
      expect(cancelCalls.length).toBeGreaterThan(0);
      expect(cancelCalls[0][0]).toBe(
        '/independent-teacher/workspace-collaborators/co-pending/cancel',
      );
    });
    // Per replit.md: native confirm()/toast.error are forbidden.
    expect(mockToastError).not.toHaveBeenCalled();
  });

  test('reactivate routes through nassaqConfirm and POSTs to /reactivate', async () => {
    // Flip lifecycle → archived (within window) so the reactivate CTA
    // is rendered.
    hubFixture.lifecycle = {
      ...hubFixture.lifecycle,
      archived_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
      pending_hard_delete: false,
    };
    window.history.replaceState(null, '', '/account/settings#workspace-hub');
    mockApiPost.mockResolvedValue({ data: { ok: true } });

    render(<AccountSettingsPage />);

    const btn = await screen.findByTestId('it-hub-reactivate-btn');
    await act(async () => {
      fireEvent.click(btn);
    });

    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalled());
    await waitFor(() => {
      const reactivateCalls = mockApiPost.mock.calls.filter(
        ([url]) => url === '/independent-teacher/workspace/reactivate',
      );
      expect(reactivateCalls.length).toBeGreaterThan(0);
    });
    expect(mockToastError).not.toHaveBeenCalled();
  });

  // Note on revoke: the hub UI today only renders an inline action
  // button for *pending* invites (cancel). The same handler dispatches
  // accepted rows to DELETE /workspace-collaborators/{id}, but that
  // branch is reachable only from the per-class CollaboratorsTab, not
  // from this hub. The dispatch logic itself is covered by the
  // useWorkspaceHubData hook unit tests + CollaboratorsTab tests.
  //
  // Task #296 — Forward-looking coverage: if/when an inline "revoke"
  // control is added on accepted rows in the hub (data-testid
  // `it-hub-collab-revoke-{id}`), this test pins it to nassaqConfirm
  // + DELETE /workspace-collaborators/{id}. While the control is not
  // rendered yet, the test still passes (no-op assertion + no other
  // surface fired), so a regression to native confirm()/toast.error
  // would be caught the moment the button is wired up.
  test('revoke accepted collaborator (when rendered) routes through nassaqConfirm and DELETEs', async () => {
    window.history.replaceState(null, '', '/account/settings#workspace-hub');
    mockApiDelete.mockResolvedValue({ data: { ok: true } });

    render(<AccountSettingsPage />);

    // Wait for the per-class collab fan-out to resolve so any future
    // accepted-row revoke control would have rendered by now.
    await screen.findByTestId('it-hub-collab-card');
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith(
        '/independent-teacher/workspace-collaborators',
        expect.objectContaining({ params: { class_id: 'c1' } }),
      );
    });

    const revokeBtn = screen.queryByTestId('it-hub-collab-revoke-co-active');
    if (!revokeBtn) {
      // Hub UI does not (yet) expose an inline revoke control on the
      // accepted row. Confirm the current state so the assertion is
      // meaningful, and bail — the rest of this test will activate
      // automatically once the control lands.
      expect(
        screen.queryByTestId('it-hub-collab-revoke-co-active'),
      ).toBeNull();
      // Sanity: no stray DELETE/confirm fired during render.
      expect(mockApiDelete).not.toHaveBeenCalled();
      expect(mockNassaqConfirm).not.toHaveBeenCalled();
      return;
    }

    await act(async () => {
      fireEvent.click(revokeBtn);
    });

    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalled());
    await waitFor(() => {
      const deleteCalls = mockApiDelete.mock.calls.filter(
        ([url]) => url === '/independent-teacher/workspace-collaborators/co-active',
      );
      expect(deleteCalls.length).toBeGreaterThan(0);
    });
    // Per replit.md: native confirm()/toast.error are forbidden for
    // destructive flows — the handler must route everything through
    // nassaqConfirm/nassaqError.
    expect(mockToastError).not.toHaveBeenCalled();
    // And the cancel branch (status=pending → POST /cancel) must NOT
    // have fired for an accepted row.
    const cancelCalls = mockApiPost.mock.calls.filter(
      ([url]) => typeof url === 'string' && url.endsWith('/cancel'),
    );
    expect(cancelCalls.length).toBe(0);
  });
});
