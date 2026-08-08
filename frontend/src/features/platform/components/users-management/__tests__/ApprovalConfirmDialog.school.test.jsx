/**
 * A queued `teacher` registration request is a SCHOOL teacher joining an
 * existing school. The signup wizard's school field is optional free text, so
 * the reviewing admin picks the real school here — approving without one used
 * to create a teacher attached to no school at all.
 *
 * Pinned contract:
 *   1. Teacher requests render a school picker and keep "تأكيد الموافقة"
 *      disabled until a school is chosen.
 *   2. The chosen school id is handed to onConfirm as the third argument.
 *   3. Independent-Teacher workspaces never appear in the list.
 *   4. School requests are unaffected — no picker, confirm enabled, no school id.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockApiGet = jest.fn();

// Stable `api` object built inside the factory: a fresh object per render would
// loop the schools-fetch effect (it is a useEffect dependency).
jest.mock('@/shared/contexts/AuthContext', () => {
  const api = { get: (...args) => mockApiGet(...args) };
  return { useAuth: () => ({ api }) };
});

// Radix Dialog portals + traps focus; render inline so jsdom can query it.
jest.mock('@/shared/components/ui/dialog', () => {
  const React = require('react');
  const passthrough = ({ children }) => React.createElement(React.Fragment, null, children);
  return {
    Dialog: ({ open, children }) => (open ? React.createElement('div', null, children) : null),
    DialogContent: ({ children }) => React.createElement('div', null, children),
    DialogHeader: passthrough,
    DialogTitle: passthrough,
    DialogDescription: passthrough,
    DialogFooter: passthrough,
  };
});

// Native <select> stand-in: Radix Select needs pointer events jsdom lacks.
jest.mock('@/shared/components/ui/select', () => {
  const React = require('react');
  const SelectItem = () => null;
  const SelectTrigger = () => null;
  const SelectValue = () => null;
  const SelectContent = ({ children }) => children;
  const Select = ({ value, onValueChange, children }) => {
    const options = [];
    const walk = (nodes) => {
      React.Children.forEach(nodes, (child) => {
        if (!React.isValidElement(child)) return;
        if (child.type === SelectItem) {
          options.push({ value: child.props.value, label: child.props.children });
        }
        if (child.props && child.props.children) walk(child.props.children);
      });
    };
    walk(children);
    return React.createElement(
      'select',
      { value: value || '', onChange: (e) => onValueChange(e.target.value) },
      [
        React.createElement('option', { key: '__empty', value: '' }, ''),
        ...options.map((o) => React.createElement('option', { key: o.value, value: o.value }, o.label)),
      ],
    );
  };
  return { Select, SelectContent, SelectTrigger, SelectValue, SelectItem };
});

import { ApprovalConfirmDialog } from '../UsersDialogs';

const SCHOOLS = [
  { id: 'school-a', name: 'مدرسة النور', school_type: 'public', code: 'NUR-100' },
  { id: 'school-b', name: 'مدرسة الفجر', school_type: 'public', code: 'FJR-200' },
  {
    id: 'itw-1',
    name: 'مساحة معلم مستقل',
    school_type: 'independent_teacher',
    tenant_type: 'independent_teacher',
    entity_kind: 'independent_teacher_workspace',
  },
  // Legacy IT workspace: no type markers at all, identified only by the id prefix.
  {
    id: 'itw_legacy-user-1',
    name: 'مساحة معلم مستقل قديمة',
    school_type: 'public',
  },
];

const TEACHER_REQUEST = {
  id: 'req-1',
  full_name: 'أحمد بن سالم',
  email: 'ahmed@example.com',
  phone: '0500000000',
  subject: 'رياضيات',
  school_mentioned: 'مدرسة ذكرها المتقدم',
};

const SCHOOL_REQUEST = {
  id: 'req-2',
  school_name: 'مدرسة جديدة',
  full_name: 'مدير المدرسة',
  school_email: 'principal@example.com',
};

const renderDialog = (requestType, request, onConfirm) =>
  render(
    <ApprovalConfirmDialog
      data={{ request, requestType }}
      onClose={jest.fn()}
      onConfirm={onConfirm}
    />,
  );

const confirmButton = () => screen.getByTestId('approval-confirm-button');

beforeEach(() => {
  mockApiGet.mockResolvedValue({ data: SCHOOLS });
});

describe('ApprovalConfirmDialog — school linking for teacher requests', () => {
  test('blocks confirmation until the reviewer picks a school', async () => {
    const onConfirm = jest.fn();
    renderDialog('teacher', TEACHER_REQUEST, onConfirm);

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));

    expect(confirmButton().disabled).toBe(true);
    fireEvent.click(confirmButton());
    expect(onConfirm).not.toHaveBeenCalled();
  });

  test('passes the chosen school id to onConfirm', async () => {
    const onConfirm = jest.fn();
    renderDialog('teacher', TEACHER_REQUEST, onConfirm);

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'school-b' } });
    expect(confirmButton().disabled).toBe(false);

    fireEvent.click(confirmButton());
    expect(onConfirm).toHaveBeenCalledWith(TEACHER_REQUEST, 'teacher', 'school-b');
  });

  test('never offers an Independent-Teacher workspace as a target school', async () => {
    renderDialog('teacher', TEACHER_REQUEST, jest.fn());

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));

    const labels = Array.from(screen.getByRole('combobox').options).map((o) => o.textContent);
    expect(labels).toEqual(expect.arrayContaining(['مدرسة النور', 'مدرسة الفجر']));
    expect(labels).not.toContain('مساحة معلم مستقل');
  });

  test('never offers a legacy itw_* workspace that carries no type markers', async () => {
    renderDialog('teacher', TEACHER_REQUEST, jest.fn());

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));

    const labels = Array.from(screen.getByRole('combobox').options).map((o) => o.textContent);
    expect(labels).not.toContain('مساحة معلم مستقل قديمة');
  });

  test('surfaces the school the applicant mentioned as a hint', async () => {
    renderDialog('teacher', TEACHER_REQUEST, jest.fn());

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));
    // The applicant's free-text school also shows in the request-details rows,
    // so match the picker's hint line specifically.
    expect(screen.getByText('المدرسة المذكورة في الطلب: مدرسة ذكرها المتقدم')).toBeTruthy();
  });

  test('preselects the school when the applicant entered a matching code', async () => {
    const onConfirm = jest.fn();
    renderDialog(
      'teacher',
      { ...TEACHER_REQUEST, school_mentioned: null, school_code: '  nur-100 ' },
      onConfirm,
    );

    await waitFor(() => expect(screen.getByRole('combobox').value).toBe('school-a'));
    expect(screen.getByTestId('approval-school-hint').textContent)
      .toContain('تم تحديد المدرسة تلقائياً');

    // Reviewer can confirm immediately — the entered code did the work.
    expect(confirmButton().disabled).toBe(false);
    fireEvent.click(confirmButton());
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ id: 'req-1' }), 'teacher', 'school-a');
  });

  test('an unknown school code leaves the picker empty and says so', async () => {
    renderDialog(
      'teacher',
      { ...TEACHER_REQUEST, school_mentioned: null, school_code: 'NO-SUCH-CODE' },
      jest.fn(),
    );

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));
    await waitFor(() => expect(screen.getByTestId('approval-school-hint').textContent)
      .toContain('لا يطابق أي مدرسة'));

    expect(screen.getByRole('combobox').value).toBe('');
    expect(confirmButton().disabled).toBe(true);
  });

  test('a code matching only an IT workspace is treated as unmatched', async () => {
    renderDialog(
      'teacher',
      { ...TEACHER_REQUEST, school_mentioned: null, school_code: 'ITW-9' },
      jest.fn(),
    );

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/schools'));
    await waitFor(() => expect(screen.getByTestId('approval-school-hint').textContent)
      .toContain('لا يطابق أي مدرسة'));
    expect(screen.getByRole('combobox').value).toBe('');
  });

  test('school requests keep the old one-click flow', async () => {
    const onConfirm = jest.fn();
    renderDialog('school', SCHOOL_REQUEST, onConfirm);

    expect(screen.queryByRole('combobox')).toBeNull();
    expect(confirmButton().disabled).toBe(false);

    fireEvent.click(confirmButton());
    expect(onConfirm).toHaveBeenCalledWith(SCHOOL_REQUEST, 'school', undefined);
    expect(mockApiGet).not.toHaveBeenCalled();
  });
});
