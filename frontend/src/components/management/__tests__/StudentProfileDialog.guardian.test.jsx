/**
 * StudentProfileDialog guardian-linking — regression guard.
 *
 * This is the School-Manager "quick edit" dialog (reached from
 * Users & Classes Management). The bug it guards against: its edit mode
 * previously had NO guardian email/relationship inputs and its handleSave
 * never sent any parent_* fields, so a manager could not add or link a
 * guardian to an existing (e.g. Noor-imported, empty-guardian) student.
 *
 * Covers:
 *   1. Edit mode exposes guardian inputs for a student with NO guardian data
 *      (the section is not gated behind an existing parent_name).
 *   2. Saving sends parent_name + parent_phone + parent_email +
 *      parent_relationship to PUT /students/{id}.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockToastSuccess = jest.fn();
jest.mock('sonner', () => ({
  toast: { success: (...a) => mockToastSuccess(...a), error: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApi = { get: mockApiGet, put: mockApiPut, post: jest.fn() };
const mockUser = { id: 'u1', role: 'school_admin', tenant_id: 'school-1' };

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser, api: mockApi }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: (k) => k }),
}));

const mockNassaqError = jest.fn();
const mockNassaqWarning = jest.fn();
jest.mock('../../ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqWarning: mockNassaqWarning,
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('../../../utils/apiError', () => ({
  getFormErrorMessage: () => 'error',
  getApiErrorMessage: () => 'error',
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../../ui/button', () => ({
  Button: ({ children, asChild: _a, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('../../ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('../../ui/badge', () => ({
  Badge: ({ children, ...rest }) => <span {...rest}>{children}</span>,
}));
jest.mock('../../ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('../../ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('../../ui/progress', () => ({
  Progress: () => <div />,
}));
jest.mock('../../ui/radio-group', () => ({
  RadioGroup: ({ children }) => <div>{children}</div>,
  RadioGroupItem: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../ui/tabs', () => ({
  Tabs: ({ children }) => <div>{children}</div>,
  TabsList: ({ children }) => <div>{children}</div>,
  TabsTrigger: ({ children }) => <div>{children}</div>,
  TabsContent: ({ children }) => <div>{children}</div>,
}));
jest.mock('../../ui/select', () => ({
  Select: ({ children, value, onValueChange }) => (
    <select
      data-testid="select"
      value={value || ''}
      onChange={(e) => onValueChange && onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }) => <>{children}</>,
  SelectContent: ({ children }) => <>{children}</>,
  SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
  SelectValue: ({ placeholder }) => <option value="">{placeholder}</option>,
}));
jest.mock('../../ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

const StudentProfileDialog = require('../StudentProfileDialog').default;

const EMPTY_GUARDIAN_STUDENT = {
  id: 's1',
  full_name: 'أحمد',
  student_number: '001',
  is_active: true,
  gender: 'male',
  school_id: 'school-1',
  class_id: null,
  parent_name: null,
  parent_phone: null,
  parent_email: null,
  parent_relationship: null,
};

const inputFor = (labelText) =>
  screen.getByText(labelText).parentElement.querySelector('input');

const selectFor = (labelText) =>
  screen.getByText(labelText).parentElement.querySelector('select');

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockNassaqError.mockReset();
  mockNassaqWarning.mockReset();
  mockToastSuccess.mockReset();
  mockApiGet.mockResolvedValue({ data: {} });
  mockApiPut.mockResolvedValue({ data: {} });
});

describe('StudentProfileDialog — guardian linking (School Manager quick edit)', () => {
  test('1. edit mode exposes guardian inputs for a student with NO guardian data', async () => {
    render(
      <StudentProfileDialog
        open
        onClose={jest.fn()}
        student={EMPTY_GUARDIAN_STUDENT}
        classes={[]}
        onRefresh={jest.fn()}
      />
    );

    fireEvent.click(screen.getByText('edit'));

    await waitFor(() => {
      expect(inputFor('guardianName')).toBeInTheDocument();
      expect(inputFor('guardianPhone')).toBeInTheDocument();
      expect(inputFor('guardianEmail')).toBeInTheDocument();
      expect(selectFor('relationship')).toBeInTheDocument();
    });
  });

  test('2. saving sends all four parent_* fields to PUT /students/{id}', async () => {
    const onRefresh = jest.fn();
    render(
      <StudentProfileDialog
        open
        onClose={jest.fn()}
        student={EMPTY_GUARDIAN_STUDENT}
        classes={[]}
        onRefresh={onRefresh}
      />
    );

    fireEvent.click(screen.getByText('edit'));

    await waitFor(() => expect(inputFor('guardianName')).toBeInTheDocument());

    fireEvent.change(inputFor('guardianName'), { target: { value: 'سعيد الأحمد' } });
    fireEvent.change(inputFor('guardianPhone'), { target: { value: '0500000000' } });
    fireEvent.change(inputFor('guardianEmail'), { target: { value: 'parent@example.com' } });
    fireEvent.change(selectFor('relationship'), { target: { value: 'father' } });

    fireEvent.click(screen.getByText('save'));

    await waitFor(() => expect(mockApiPut).toHaveBeenCalledTimes(1));

    const [url, payload] = mockApiPut.mock.calls[0];
    expect(url).toBe('/students/s1');
    expect(payload).toMatchObject({
      parent_name: 'سعيد الأحمد',
      parent_phone: '0500000000',
      parent_email: 'parent@example.com',
      parent_relationship: 'father',
    });
    expect(onRefresh).toHaveBeenCalled();
    expect(mockNassaqError).not.toHaveBeenCalled();
  });
});
