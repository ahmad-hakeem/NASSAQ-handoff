/**
 * UsersManagement — duplicate-fetch regression guard.
 *
 * Production trace showed GET /users/platform-users firing TWICE on a single
 * /admin/users page load. Root cause: the component has three useEffects:
 *
 *   Effect A (empty deps): calls fetchUsers() on mount.
 *   Effect B (filter deps): sets isFirstRender.current = false and returns.
 *   Effect C (filter+page deps): checks isFirstRender.current — but B already
 *     set it false, so C ALSO calls fetchUsers() on the same mount cycle.
 *
 * Fix: each filter effect uses its OWN isFirstRender ref so they cannot
 * interfere with each other (isFirstFetchRender for effect C).
 *
 * Guardrail: one mount = exactly ONE GET to /users/platform-users.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react';

const mockSetSearchParams = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams(), mockSetSearchParams],
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
}), { virtual: true });

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
};
const mockUser = { id: 'admin-1', role: 'platform_admin', full_name: 'Admin' };
const mockAuthValue = { user: mockUser, api: mockApi, isImpersonating: false };

jest.mock('@/shared/contexts/AuthContext', () => ({ useAuth: () => mockAuthValue }));

const stableT = (k) => k;
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: stableT }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(), nassaqWarning: jest.fn(),
    nassaqInfo: jest.fn(), nassaqConfirm: jest.fn(), nassaqSuccess: jest.fn(),
  }),
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('@/features/teachers/components/wizards/CreateUserWizard', () => ({ __esModule: true, default: () => <div /> }));

// Stub every users-management sub-component so they don't mount and issue requests
jest.mock('@/features/platform/components/users-management', () => ({
  UsersStatsCards: () => <div />,
  UserCard: () => <div />,
  UsersFilters: () => <div />,
  SchoolUsersTab: () => <div />,
  TeacherMismatchesTab: () => <div />,
  ApprovalRequestsTab: () => <div />,
  UserDetailsDialog: () => <div />,
  SuspendDialog: () => <div />,
  DeleteDialog: () => <div />,
  NotificationDialog: () => <div />,
  ApprovalConfirmDialog: () => <div />,
  ApprovalSuccessDialog: () => <div />,
  RejectDialog: () => <div />,
  MoreInfoDialog: () => <div />,
  RequestDetailsDialog: () => <div />,
  EditUserSheet: () => <div />,
  APPROVAL_TYPE_CONFIG: {
    teacher: { tabValue: 'requests', tabLabel: 'Teachers', tabIcon: () => null },
  },
  USER_ROLES: [],
  ACCOUNT_TYPES: [{ id: 'all', name: 'All' }],
  ACCOUNT_STATUSES: [{ id: 'all', name: 'All' }],
  PENDING_STATUSES: ['pending'],
  getRoleInfo: () => ({ color: 'bg-gray-500', label: '' }),
}));

// UI stubs
jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, asChild: _a, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('@/shared/components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('@/shared/components/ui/scroll-area', () => ({ ScrollArea: ({ children }) => <div>{children}</div> }));
jest.mock('@/shared/components/ui/tabs', () => ({
  Tabs: ({ children }) => <div>{children}</div>,
  TabsContent: ({ children }) => <div>{children}</div>,
  TabsList: ({ children }) => <div>{children}</div>,
  TabsTrigger: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
}));
jest.mock('@/shared/components/ui/select', () => ({
  Select: ({ children }) => <div>{children}</div>,
  SelectTrigger: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
}));
jest.mock('@/shared/components/ui/sheet', () => ({
  Sheet: ({ children }) => <div>{children}</div>,
  SheetContent: ({ children }) => <div>{children}</div>,
  SheetHeader: ({ children }) => <div>{children}</div>,
  SheetTitle: ({ children }) => <div>{children}</div>,
}));

const UsersManagement = require('@/features/platform/pages/UsersManagement').default;

const PLATFORM_USERS_URL = '/users/platform-users';

describe('UsersManagement — single fetch of /users/platform-users on mount', () => {
  beforeEach(() => {
    mockApiGet.mockImplementation((url) => {
      if (url === PLATFORM_USERS_URL) return Promise.resolve({ data: { users: [], total: 0 } });
      if (url === '/registration-requests') return Promise.resolve({ data: { requests: [] } });
      if (url === '/schools') return Promise.resolve({ data: [] });
      if (url === '/users/by-school') return Promise.resolve({ data: {} });
      if (url === '/users/management-stats') return Promise.resolve({ data: {} });
      if (url === '/users/teacher-school-mismatches') return Promise.resolve({ data: { mismatches: [], total: 0 } });
      return Promise.resolve({ data: {} });
    });
  });

  test('/users/platform-users is fetched exactly once on initial mount', async () => {
    render(<UsersManagement />);

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith(
        PLATFORM_USERS_URL,
        expect.any(Object),
      );
    });
    // Let any second (buggy) effect round flush before counting.
    await new Promise((r) => setTimeout(r, 50));

    const platformUsersCalls = mockApiGet.mock.calls.filter(
      ([url]) => url === PLATFORM_USERS_URL,
    );
    expect(platformUsersCalls).toHaveLength(1);
  });
});
