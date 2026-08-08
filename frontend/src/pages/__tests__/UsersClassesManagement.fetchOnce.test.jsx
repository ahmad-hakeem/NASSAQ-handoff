/**
 * UsersClassesManagement — duplicate-fetch regression guard.
 *
 * Production trace (إدارة المستخدمين والفصول) showed every directory
 * endpoint (/students, /teachers, /classes, /reference/grades, /parents)
 * requested EXACTLY TWICE on a single page load: two separate mount
 * effects both invoked fetchAllData().
 *
 * Guardrail: one page mount = exactly ONE request per endpoint.
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
  toast: { success: jest.fn(), error: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockUser = { id: 'u1', role: 'school_admin', tenant_id: 'school-1' };
const mockAuthValue = {
  user: mockUser,
  api: mockApi,
  schoolContext: null,
  isImpersonating: false,
};

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => mockAuthValue,
}));

const stableT = (k) => k;
jest.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: stableT }),
}));

jest.mock('../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqWarning: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('../../hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

jest.mock('../../utils/studentNavigation', () => ({
  useSchoolNavigation: () => ({
    rolePrefix: '/principal',
    getStudentDetailPath: () => '/principal/students/1',
  }),
}));

jest.mock('../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('../../components/wizards/AddStudentWizard', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../components/wizards/AddTeacherWizard', () => ({
  AddTeacherWizard: () => <div />,
}));
jest.mock('../../components/wizards/CreateClassWizard', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../components/management/TeacherProfileDialog', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../components/management/ParentProfileDialog', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../components/management/StudentClassGrid', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('../../components/management/NoorImportPanel', () => ({
  __esModule: true,
  default: () => <div />,
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../../components/ui/button', () => ({
  Button: ({ children, asChild: _a, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('../../components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardHeader: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardTitle: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardDescription: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('../../components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('../../components/ui/badge', () => ({
  Badge: ({ children, ...rest }) => <span {...rest}>{children}</span>,
}));
jest.mock('../../components/ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('../../components/ui/progress', () => ({
  Progress: () => <div />,
}));
jest.mock('../../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, ...rest }) => (
    <input
      type="checkbox"
      checked={!!checked}
      onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)}
      {...rest}
    />
  ),
}));
jest.mock('../../components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
  DropdownMenuSeparator: () => <hr />,
}));
jest.mock('../../components/ui/tabs', () => ({
  Tabs: ({ children }) => <div>{children}</div>,
  TabsContent: ({ children }) => <div>{children}</div>,
  TabsList: ({ children }) => <div>{children}</div>,
  TabsTrigger: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
}));
jest.mock('../../components/ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../components/ui/select', () => ({
  Select: ({ children }) => <div>{children}</div>,
  SelectTrigger: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
}));

const UsersClassesManagement = require('../UsersClassesManagement').default;

const DIRECTORY_URLS = ['/students', '/teachers', '/classes', '/reference/grades', '/parents'];

describe('UsersClassesManagement — single fetch per endpoint on mount', () => {
  beforeEach(() => {
    // CRA resetMocks:true wipes implementations — reinstall per test.
    mockApiGet.mockResolvedValue({ data: [] });
  });

  test('each directory endpoint is requested exactly once on initial mount', async () => {
    render(<UsersClassesManagement />);

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalled();
    });
    // Let any second (buggy) effect round flush before counting.
    await new Promise((r) => setTimeout(r, 50));

    const countsByUrl = {};
    for (const [url] of mockApiGet.mock.calls) {
      countsByUrl[url] = (countsByUrl[url] || 0) + 1;
    }

    for (const url of DIRECTORY_URLS) {
      expect(countsByUrl[url] || 0).toBe(1);
    }
    // No other unexpected GET storms from this page's mount.
    expect(mockApiGet.mock.calls.length).toBe(DIRECTORY_URLS.length);
  });
});
