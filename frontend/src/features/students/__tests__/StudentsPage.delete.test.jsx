/**
 * StudentsPage deletion flow — regression guard.
 *
 * Covers the five cases called out in the task spec:
 *   1. Happy path — DELETE called with exact ID, row removed optimistically.
 *   2. API error — nassaqError shown, both rows remain.
 *   3. nassaqConfirm wiring — confirm dialog opens; DELETE not fired until
 *      the callback is invoked.
 *   4. ID consistency — numeric ID is filtered correctly (type-mismatch guard).
 *   5. No re-fetch — api.get('/students') is NOT called a second time after
 *      a successful delete (optimistic filter is the only update).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { within } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
}), { virtual: true });

const mockToastSuccess = jest.fn();
jest.mock('sonner', () => ({
  toast: { success: (...a) => mockToastSuccess(...a), error: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApiDelete = jest.fn();
const mockApi = { get: mockApiGet, delete: mockApiDelete, post: jest.fn() };
const mockUser = { id: 'u1', role: 'school_admin', tenant_id: 'school-1' };

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser, api: mockApi }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: (k) => k }),
}));

const mockNassaqConfirm = jest.fn();
const mockNassaqError = jest.fn();
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqWarning: jest.fn(),
    nassaqConfirm: mockNassaqConfirm,
  }),
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('@/features/hakim/components/hakim/HakimAssistant', () => ({
  HakimAssistant: () => <div />,
}));

jest.mock('@/features/teachers/components/wizards/AddStudentWizard', () => ({
  __esModule: true,
  default: () => <div />,
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('@/shared/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick, className }) => (
    <button onClick={onClick} className={className || ''}>{children}</button>
  ),
}));

jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, asChild: _a, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('@/shared/components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
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
jest.mock('@/shared/components/ui/select', () => ({
  Select: ({ children }) => <div>{children}</div>,
  SelectTrigger: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
}));
jest.mock('@/shared/components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableRow: ({ children, ...rest }) => <tr {...rest}>{children}</tr>,
  TableHead: ({ children, ...rest }) => <th {...rest}>{children}</th>,
  TableCell: ({ children, ...rest }) => <td {...rest}>{children}</td>,
}));
jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
  DialogTrigger: ({ children }) => <div>{children}</div>,
}));

const { StudentsPage } = require('@/features/students/pages/StudentsPage');

const BASE_STUDENTS = [
  {
    id: 's1', full_name: 'أحمد', student_number: '001',
    is_active: true, gender: 'male', class_name: null,
    school_id: 'school-1', parent_name: null, parent_phone: null, class_id: null,
  },
  {
    id: 's2', full_name: 'سارة', student_number: '002',
    is_active: true, gender: 'female', class_name: null,
    school_id: 'school-1', parent_name: null, parent_phone: null, class_id: null,
  },
];

const seedApiDefaults = (students = BASE_STUDENTS) => {
  mockApiGet.mockImplementation((url) => {
    if (url === '/students') return Promise.resolve({ data: students });
    if (url === '/classes') return Promise.resolve({ data: [] });
    if (url === '/reference/grades') return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });
  mockApiDelete.mockResolvedValue({ data: {} });
};

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiDelete.mockReset();
  mockNassaqConfirm.mockReset();
  mockNassaqError.mockReset();
  mockToastSuccess.mockReset();
  seedApiDefaults();
});

const waitForRows = async () => {
  await waitFor(() => {
    expect(screen.getByTestId('student-row-s1')).toBeInTheDocument();
  }, { timeout: 3000 });
};

const clickDeleteForStudent = (studentId) => {
  const row = screen.getByTestId(`student-row-${studentId}`);
  const deleteBtn = within(row).getByText('delete');
  fireEvent.click(deleteBtn);
};

const invokeConfirmCallback = async () => {
  expect(mockNassaqConfirm).toHaveBeenCalledTimes(1);
  const [, callback] = mockNassaqConfirm.mock.calls[0];
  await callback();
};

describe('StudentsPage — deletion flow', () => {
  test('1. happy path: DELETE called with exact ID and row removed from list', async () => {
    render(<StudentsPage />);
    await waitForRows();

    clickDeleteForStudent('s1');
    await invokeConfirmCallback();

    await waitFor(() => {
      expect(mockApiDelete).toHaveBeenCalledWith('/students/s1');
    });

    await waitFor(() => {
      expect(screen.queryByTestId('student-row-s1')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('student-row-s2')).toBeInTheDocument();
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
    expect(mockNassaqError).not.toHaveBeenCalled();
  });

  test('2. API error: nassaqError shown and both rows remain', async () => {
    mockApiDelete.mockRejectedValue({ response: { data: { detail: 'فشل الحذف' } } });

    render(<StudentsPage />);
    await waitForRows();

    clickDeleteForStudent('s1');
    await invokeConfirmCallback();

    await waitFor(() => {
      expect(mockNassaqError).toHaveBeenCalledTimes(1);
    });

    expect(mockNassaqError.mock.calls[0][0]).toBe('فشل الحذف');
    expect(screen.getByTestId('student-row-s1')).toBeInTheDocument();
    expect(screen.getByTestId('student-row-s2')).toBeInTheDocument();
    expect(mockToastSuccess).not.toHaveBeenCalled();
  });

  test('3. nassaqConfirm wiring: confirm dialog opened on click; DELETE not fired without callback', async () => {
    render(<StudentsPage />);
    await waitForRows();

    expect(mockNassaqConfirm).not.toHaveBeenCalled();
    expect(mockApiDelete).not.toHaveBeenCalled();

    clickDeleteForStudent('s1');

    expect(mockNassaqConfirm).toHaveBeenCalledTimes(1);
    expect(mockApiDelete).not.toHaveBeenCalled();
  });

  test('3b. callback not called on cancel: no DELETE issued', async () => {
    render(<StudentsPage />);
    await waitForRows();

    clickDeleteForStudent('s1');

    expect(mockNassaqConfirm).toHaveBeenCalledTimes(1);

    expect(mockApiDelete).not.toHaveBeenCalled();
    expect(screen.getByTestId('student-row-s1')).toBeInTheDocument();
  });

  test('4. ID consistency: numeric ID is filtered correctly', async () => {
    const numericStudents = [
      {
        id: 42, full_name: 'خالد', student_number: '099',
        is_active: true, gender: 'male', class_name: null,
        school_id: 'school-1', parent_name: null, parent_phone: null, class_id: null,
      },
      {
        id: 43, full_name: 'نورة', student_number: '100',
        is_active: true, gender: 'female', class_name: null,
        school_id: 'school-1', parent_name: null, parent_phone: null, class_id: null,
      },
    ];
    seedApiDefaults(numericStudents);

    render(<StudentsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('student-row-42')).toBeInTheDocument();
    }, { timeout: 3000 });

    const row = screen.getByTestId('student-row-42');
    const deleteBtn = within(row).getByText('delete');
    fireEvent.click(deleteBtn);

    expect(mockNassaqConfirm).toHaveBeenCalledTimes(1);
    const [, callback] = mockNassaqConfirm.mock.calls[0];
    await callback();

    await waitFor(() => {
      expect(screen.queryByTestId('student-row-42')).not.toBeInTheDocument();
    });

    expect(screen.getByTestId('student-row-43')).toBeInTheDocument();
    expect(mockApiDelete).toHaveBeenCalledWith('/students/42');
  });

  test('5. no re-fetch: api.get not called again after successful delete', async () => {
    render(<StudentsPage />);
    await waitForRows();

    const getCallsAfterLoad = mockApiGet.mock.calls.length;

    clickDeleteForStudent('s1');
    await invokeConfirmCallback();

    await waitFor(() => {
      expect(screen.queryByTestId('student-row-s1')).not.toBeInTheDocument();
    });

    expect(mockApiGet.mock.calls.length).toBe(getCallsAfterLoad);
    const getStudentsCalls = mockApiGet.mock.calls.filter(([url]) => url === '/students');
    expect(getStudentsCalls.length).toBe(1);
  });
});
