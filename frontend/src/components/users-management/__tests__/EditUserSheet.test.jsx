/**
 * Task #797 — frontend coverage for the school selector in EditUserSheet.
 *
 * The backend reassign/reconcile path is tested separately; this pins the
 * UI-side contract that produced the original bug:
 *
 *   1. Changing the school sends `tenant_id` (the newly chosen school id)
 *      in the PATCH /users/{id} body.
 *   2. Leaving the school unchanged OMITS `tenant_id` entirely (it is
 *      `undefined`), so an unchanged save never re-triggers a reassign.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

// Sheet is a Radix dialog (portal + focus trap). Render its children inline
// when `open` so the form is queryable without jsdom portal/focus quirks.
jest.mock('../../ui/sheet', () => {
  const React = require('react');
  const Sheet = ({ open, children }) => (open ? React.createElement('div', null, children) : null);
  const passthrough = ({ children }) => React.createElement(React.Fragment, null, children);
  return {
    Sheet,
    SheetContent: ({ children }) => React.createElement('div', null, children),
    SheetHeader: passthrough,
    SheetTitle: passthrough,
  };
});

// Native <select> stand-in: Radix Select relies on pointer events jsdom does
// not implement. Render each SelectItem as an <option> so the school select
// can be driven with fireEvent.change.
jest.mock('../../ui/select', () => {
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
        ...options.map((o) =>
          React.createElement('option', { key: o.value, value: o.value }, o.label)
        ),
      ]
    );
  };
  return { Select, SelectContent, SelectTrigger, SelectValue, SelectItem };
});

import { EditUserSheet } from '../UsersDialogs';

const SCHOOLS = [
  { id: 'school-a', name: 'مدرسة النور' },
  { id: 'school-b', name: 'مدرسة الفجر' },
];

const TEACHER = {
  id: 'user-1',
  full_name: 'أحمد المعلم',
  email: 'ahmed@example.com',
  phone: '0500000000',
  role: 'teacher',
  tenant_id: 'school-a',
};

const makeApi = () => ({ patch: jest.fn().mockResolvedValue({ data: {} }) });

// Find the school <select> by the option labels it renders (the other select
// on the sheet holds roles, not schools).
const getSchoolSelect = () =>
  screen
    .getAllByRole('combobox')
    .find((sel) => Array.from(sel.options).some((o) => o.textContent === 'مدرسة الفجر'));

const renderSheet = (api) => {
  render(
    <EditUserSheet
      user={TEACHER}
      onClose={jest.fn()}
      onSave={jest.fn()}
      api={api}
      fetchUsers={jest.fn()}
      schools={SCHOOLS}
    />,
  );
};

const clickSave = async () => {
  await act(async () => {
    fireEvent.click(screen.getByText('حفظ التغييرات'));
    await Promise.resolve();
  });
};

describe('EditUserSheet — school selector', () => {
  test('sends the new tenant_id when the school is changed', async () => {
    const api = makeApi();
    renderSheet(api);

    fireEvent.change(getSchoolSelect(), { target: { value: 'school-b' } });
    await clickSave();

    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const [path, body] = api.patch.mock.calls[0];
    expect(path).toBe('/users/user-1');
    expect(body.tenant_id).toBe('school-b');
  });

  test('omits tenant_id when the school is left unchanged', async () => {
    const api = makeApi();
    renderSheet(api);

    // No school change — save straight away.
    await clickSave();

    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const [path, body] = api.patch.mock.calls[0];
    expect(path).toBe('/users/user-1');
    expect(body.tenant_id).toBeUndefined();
    expect('tenant_id' in body).toBe(true); // key present, value undefined
  });
});
