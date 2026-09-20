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
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';

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
const mockNassaqWarning = jest.fn();
const mockNassaqConfirm = jest.fn();
const mockNassaqError = jest.fn();
const mockAuthValue = {
  user: mockUser,
  api: mockApi,
  schoolContext: null,
  isImpersonating: false,
};

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuthValue,
}));

const stableT = (k) => k;
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: stableT }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqWarning: mockNassaqWarning,
    nassaqInfo: jest.fn(),
    nassaqConfirm: mockNassaqConfirm,
  }),
}));

jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

jest.mock('@/shared/models/utils/studentNavigation', () => ({
  useSchoolNavigation: () => ({
    rolePrefix: '/principal',
    getStudentDetailPath: () => '/principal/students/1',
  }),
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('@/features/teachers/components/wizards/AddStudentWizard', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('@/features/teachers/components/wizards/AddTeacherWizard', () => ({
  AddTeacherWizard: () => <div />,
}));
jest.mock('@/features/teachers/components/wizards/CreateClassWizard', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('@/features/platform/components/management/TeacherProfileDialog', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('@/features/platform/components/management/ParentProfileDialog', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('@/features/platform/components/management/StudentClassGrid', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('@/features/platform/components/management/NoorImportPanel', () => ({
  __esModule: true,
  default: () => <div />,
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, asChild: _a, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('@/shared/components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardHeader: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardTitle: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardDescription: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('@/shared/components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children, ...rest }) => <span {...rest}>{children}</span>,
}));
jest.mock('@/shared/components/ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('@/shared/components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, ...rest }) => (
    <input
      type="checkbox"
      checked={!!checked}
      onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)}
      {...rest}
    />
  ),
}));
jest.mock('@/shared/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick, disabled }) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  DropdownMenuSeparator: () => <hr />,
}));
jest.mock('@/shared/components/ui/tabs', () => ({
  Tabs: ({ children }) => <div>{children}</div>,
  TabsContent: ({ children }) => <div>{children}</div>,
  TabsList: ({ children }) => <div>{children}</div>,
  TabsTrigger: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
}));
jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));
jest.mock('@/shared/components/ui/select', () => ({
  Select: ({ children }) => <div>{children}</div>,
  SelectTrigger: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
}));

const managementModule = require('@/features/academics/pages/UsersClassesManagement');
const UsersClassesManagement = managementModule.default;
const { getDeleteSuccessMessage } = managementModule;

const DIRECTORY_URLS = ['/students', '/teachers', '/classes', '/reference/grades', '/parents'];

describe('UsersClassesManagement — single fetch per endpoint on mount', () => {
  beforeEach(() => {
    // CRA resetMocks:true wipes implementations — reinstall per test.
    mockAuthValue.user = mockUser;
    mockAuthValue.schoolContext = null;
    mockAuthValue.isImpersonating = false;
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
    // The latest import-batch status is a legitimate secondary read made
    // after the directory settles; it must also remain a single request.
    expect(countsByUrl['/bulk/batches/latest'] || 0).toBe(1);
    expect(mockApiGet.mock.calls.length).toBe(DIRECTORY_URLS.length + 1);
  });

  test('a same-school refresh preserves a list whose individual request fails and warns the user', async () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    mockApiGet.mockImplementation((url) => {
      if (url === '/teachers') return Promise.resolve({ data: [{ id: 'teacher-1', full_name: 'Teacher Kept' }] });
      return Promise.resolve({ data: [] });
    });
    render(<UsersClassesManagement />);
    const teachersStat = screen.getByText('totalTeachers').closest('button');
    await waitFor(() => expect(teachersStat).toHaveTextContent('1'));
    fireEvent.click(teachersStat);
    expect(await screen.findByText('Teacher Kept')).toBeInTheDocument();

    mockApiGet.mockImplementation((url) => {
      if (url === '/teachers') return Promise.reject(new Error('temporary failure'));
      return Promise.resolve({ data: [] });
    });
    fireEvent.click(screen.getByTitle('refresh'));

    await waitFor(() => expect(mockNassaqWarning).toHaveBeenCalled());
    expect(screen.getByText('Teacher Kept')).toBeInTheDocument();
    expect(warnSpy).toHaveBeenCalledWith('Partial data load failure for endpoints:', ['/teachers']);
    warnSpy.mockRestore();
  });

  test('late responses from a prior school scope cannot replace the new school lists', async () => {
    let resolveOldTeachers;
    mockAuthValue.isImpersonating = true;
    mockAuthValue.schoolContext = { school_id: 'old-school' };
    mockApiGet.mockImplementation((url, config = {}) => {
      const scope = config.headers?.['X-School-Context'];
      if (url === '/teachers' && scope === 'old-school') {
        return new Promise((resolve) => { resolveOldTeachers = resolve; });
      }
      if (url === '/teachers' && scope === 'new-school') {
        return Promise.resolve({ data: [{ id: 'teacher-new', full_name: 'New School Teacher' }] });
      }
      return Promise.resolve({ data: [] });
    });

    const view = render(<UsersClassesManagement />);
    await waitFor(() => expect(resolveOldTeachers).toBeDefined());

    mockAuthValue.schoolContext = { school_id: 'new-school' };
    view.rerender(<UsersClassesManagement />);
    fireEvent.click(screen.getByText('totalTeachers').closest('button'));
    expect(await screen.findByText('New School Teacher')).toBeInTheDocument();

    resolveOldTeachers({ data: [{ id: 'teacher-old', full_name: 'Old School Teacher' }] });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByText('Old School Teacher')).not.toBeInTheDocument();
    expect(screen.getByText('New School Teacher')).toBeInTheDocument();
  });

  test('turning impersonation off refetches without the retained school-context header', async () => {
    mockAuthValue.isImpersonating = true;
    mockAuthValue.schoolContext = { school_id: 'preview-school' };
    mockApiGet.mockImplementation((url, config = {}) => {
      if (url === '/teachers' && config.headers?.['X-School-Context'] === 'preview-school') {
        return Promise.resolve({ data: [{ id: 'preview-teacher', full_name: 'Preview Teacher' }] });
      }
      if (url === '/teachers' && !config.headers?.['X-School-Context']) {
        return Promise.resolve({ data: [{ id: 'tenant-teacher', full_name: 'Tenant Teacher' }] });
      }
      return Promise.resolve({ data: [] });
    });

    const view = render(<UsersClassesManagement />);
    await waitFor(() => expect(screen.getByText('totalTeachers').closest('button')).toHaveTextContent('1'));

    mockAuthValue.isImpersonating = false;
    view.rerender(<UsersClassesManagement />);
    fireEvent.click(screen.getByText('totalTeachers').closest('button'));

    expect(await screen.findByText('Tenant Teacher')).toBeInTheDocument();
    expect(screen.queryByText('Preview Teacher')).not.toBeInTheDocument();
    expect(mockApiGet).toHaveBeenCalledWith('/teachers', expect.objectContaining({ headers: {} }));
  });

  test('a tenant change for the same user id refetches and rejects the prior tenant response', async () => {
    let resolveOldTeachers;
    mockAuthValue.user = { ...mockUser, tenant_id: 'tenant-old' };
    mockApiGet.mockImplementation((url) => {
      if (url !== '/teachers') return Promise.resolve({ data: [] });
      if (mockAuthValue.user.tenant_id === 'tenant-old') {
        return new Promise((resolve) => { resolveOldTeachers = resolve; });
      }
      return Promise.resolve({ data: [{ id: 'tenant-new-teacher', full_name: 'New Tenant Teacher' }] });
    });

    const view = render(<UsersClassesManagement />);
    await waitFor(() => expect(resolveOldTeachers).toBeDefined());

    mockAuthValue.user = { ...mockUser, tenant_id: 'tenant-new' };
    view.rerender(<UsersClassesManagement />);
    fireEvent.click(screen.getByText('totalTeachers').closest('button'));
    expect(await screen.findByText('New Tenant Teacher')).toBeInTheDocument();

    resolveOldTeachers({ data: [{ id: 'tenant-old-teacher', full_name: 'Old Tenant Teacher' }] });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByText('Old Tenant Teacher')).not.toBeInTheDocument();
    expect(screen.getByText('New Tenant Teacher')).toBeInTheDocument();
  });
});

describe('UsersClassesManagement — permanent teacher deletion', () => {
  test('uses permanent deletion success copy and never exposes backend cleanup keys', () => {
    const cleanup = { teacher_assignments: 4, timetable_sessions: 9 };
    const englishMessage = getDeleteSuccessMessage('teacher', false, stableT, cleanup);
    const arabicMessage = getDeleteSuccessMessage('teacher', true, stableT, cleanup);

    expect(englishMessage).toBe('teacherDeletedSuccessfully');
    expect(arabicMessage).toBe('teacherDeletedSuccessfully');
    expect(`${englishMessage} ${arabicMessage}`).not.toMatch(/teacher_assignments|timetable_sessions/);
  });

  test('warns about permanence and retention, calls DELETE once, and does not remove before success', async () => {
    let resolveDelete;
    mockApiGet.mockImplementation((url) => (
      url === '/teachers'
        ? Promise.resolve({ data: [{ id: 'teacher-1', full_name: 'Teacher Kept Until Success' }] })
        : Promise.resolve({ data: [] })
    ));
    mockApi.delete.mockReturnValue(new Promise(resolve => { resolveDelete = resolve; }));

    render(<UsersClassesManagement />);
    fireEvent.click(screen.getByText('totalTeachers').closest('button'));
    expect(await screen.findByText('Teacher Kept Until Success')).toBeInTheDocument();
    fireEvent.click(screen.getAllByText('delete')[0]);

    expect(mockNassaqConfirm).toHaveBeenCalledWith(
      'teacherPermanentDeleteWarning\n\nteacherPermanentDeleteRetention',
      expect.any(Function),
      expect.objectContaining({
        title: 'confirmPermanentDelete',
        confirmText: 'yesDeletePermanently',
      })
    );

    const confirmDelete = mockNassaqConfirm.mock.calls[0][1];
    let firstSubmission;
    await act(async () => {
      firstSubmission = confirmDelete();
      await confirmDelete();
    });
    expect(mockApi.delete).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Teacher Kept Until Success')).toBeInTheDocument();

    await act(async () => {
      resolveDelete({ data: { success: true } });
      await firstSubmission;
    });
  });

  test('surfaces a 409 conflict message and leaves the teacher visible', async () => {
    mockApiGet.mockImplementation((url) => (
      url === '/teachers'
        ? Promise.resolve({ data: [{ id: 'shared-teacher', full_name: 'Shared Teacher' }] })
        : Promise.resolve({ data: [] })
    ));
    mockApi.delete.mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: { code: 'TEACHER_DELETE_REVIEW_REQUIRED', message: 'يتطلب هذا الحساب مراجعة مسؤول المنصة' },
        },
      },
    });

    render(<UsersClassesManagement />);
    fireEvent.click(screen.getByText('totalTeachers').closest('button'));
    expect(await screen.findByText('Shared Teacher')).toBeInTheDocument();
    fireEvent.click(screen.getAllByText('delete')[0]);
    await act(async () => {
      await mockNassaqConfirm.mock.calls[0][1]();
    });

    expect(mockNassaqError).toHaveBeenCalledWith('يتطلب هذا الحساب مراجعة مسؤول المنصة');
    expect(screen.getByText('Shared Teacher')).toBeInTheDocument();
  });
});
