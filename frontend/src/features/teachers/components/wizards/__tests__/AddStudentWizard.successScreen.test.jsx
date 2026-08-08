/**
 * Regression coverage for the truthful create-student success screen (step 5).
 *
 * The success screen must reflect the REAL guardian-onboarding outcome reported
 * by the backend in `parent_onboarding.mode` — an invitation that was sent, a
 * guardian saved pending a future invite, or a parent linked to a pre-existing
 * account — instead of fabricating a fake/placeholder parent password.
 *
 * For each mode (invite / pending / linked) this drives the wizard end-to-end
 * to step 5 and asserts:
 *   - the correct headline subtitle and onboarding card are shown,
 *   - the parent password row is NEVER rendered (only the student keeps its
 *     real temp password), and
 *   - no literal "undefined" password ever leaks into the DOM.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import AddStudentWizard from '../AddStudentWizard';

const mockApi = { get: jest.fn(), post: jest.fn() };
const mockNassaqError = jest.fn();

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false }),
  useTranslation: () => ({ t: (key, fallback) => fallback || key }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

// Lightweight Dialog: render children only when open.
jest.mock('@/shared/components/ui/dialog', () => {
  const React = require('react');
  const passthrough = ({ children }) => React.createElement(React.Fragment, null, children);
  return {
    Dialog: ({ open, children }) =>
      open ? React.createElement('div', { 'data-testid': 'dialog-root' }, children) : null,
    DialogContent: ({ children }) => React.createElement('div', null, children),
    DialogHeader: passthrough,
    DialogFooter: passthrough,
    DialogTitle: passthrough,
    DialogDescription: passthrough,
  };
});

// Native <select> stand-in: Radix Select relies on pointer events jsdom lacks,
// so render a real <select> whose options mirror the <SelectItem> values.
jest.mock('@/shared/components/ui/select', () => {
  const React = require('react');
  const SelectItem = () => null;
  const SelectTrigger = () => null;
  const SelectValue = () => null;
  const SelectContent = ({ children }) => children;
  const Select = ({ value, onValueChange, disabled, children }) => {
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
      {
        value: value || '',
        disabled,
        onChange: (e) => onValueChange(e.target.value),
      },
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

const GRADES = [
  { id: 'g1', name_en: 'Grade 1', name_ar: 'الصف الأول الابتدائي', grade: 1, stage: 'primary' },
];

const STUDENT = {
  student_id: 'S-100',
  full_name: 'طالب جديد',
  email: 'student@example.com',
  temp_password: 'Stud-1234',
  qr_code: null,
};

const findSelectWithOption = (optionValue) => {
  const selects = Array.from(document.querySelectorAll('select'));
  const target = selects.find((sel) =>
    Array.from(sel.querySelectorAll('option')).some((o) => o.value === optionValue)
  );
  if (!target) throw new Error(`No <select> exposing option "${optionValue}"`);
  return target;
};

// Drive steps 1 -> 4, leaving the wizard on the review step ready to submit.
const fillThroughReview = async () => {
  // Step 1 — student basics (gender defaults to "male").
  fireEvent.change(screen.getByPlaceholderText('enterFullName'), { target: { value: STUDENT.full_name } });
  fireEvent.change(document.querySelector('input[type="date"]'), { target: { value: '2015-01-01' } });
  fireEvent.change(findSelectWithOption('primary'), { target: { value: 'primary' } });
  await waitFor(() => findSelectWithOption('g1'));
  fireEvent.change(findSelectWithOption('g1'), { target: { value: 'g1' } });
  fireEvent.click(screen.getByText('next'));

  // Step 2 — parent (relationship defaults to "father"). First textbox is the
  // parent name; phone is keyed by its placeholder.
  const parentName = document.querySelector('input');
  fireEvent.change(parentName, { target: { value: 'ولي الأمر' } });
  fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0500000000' } });
  await act(async () => {
    fireEvent.click(screen.getByText('next'));
  });

  // Step 3 — health (all optional).
  fireEvent.click(screen.getByText('next'));
};

const renderToSuccess = async (createResponse) => {
  mockApi.get.mockImplementation((url) =>
    url === '/classes/options/grades'
      ? Promise.resolve({ data: { grades: GRADES } })
      : Promise.resolve({ data: {} })
  );
  mockApi.post.mockImplementation((url) => {
    if (url.startsWith('/student-wizard/check-parent')) {
      return Promise.resolve({ data: { found: false } });
    }
    if (url === '/student-wizard/create') {
      return Promise.resolve({ data: createResponse });
    }
    return Promise.resolve({ data: {} });
  });

  const onOpenChange = jest.fn();
  const onSuccess = jest.fn();
  await act(async () => {
    render(
      <AddStudentWizard
        open
        onOpenChange={onOpenChange}
        onSuccess={onSuccess}
        api={mockApi}
        isRTL={false}
        classes={[]}
      />
    );
  });
  await screen.findByPlaceholderText('enterFullName');
  await fillThroughReview();

  await act(async () => {
    fireEvent.click(screen.getByText('confirmSave'));
  });
  await waitFor(() =>
    expect(mockApi.post).toHaveBeenCalledWith('/student-wizard/create', expect.any(Object))
  );
  return { onSuccess };
};

beforeEach(() => {
  jest.clearAllMocks();
});

describe('AddStudentWizard - truthful success screen', () => {
  test('invite mode: shows the parent-invitation card + link, no parent password', async () => {
    const { onSuccess } = await renderToSuccess({
      success: true,
      student: STUDENT,
      // Invited parents activate their own account, so the account exists but
      // carries NO temp password.
      parent: { full_name: 'ولي الأمر', phone: '0500000000', is_new: true },
      parent_onboarding: {
        mode: 'invite',
        email_queued: true,
        parent_email: 'parent@example.com',
        invite_link: 'https://nassaq.test/invite/abc123',
        invite_expires_at: '2026-07-01T00:00:00Z',
      },
      siblings: { list: [] },
    });

    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Student account created and parent invited')).toBeInTheDocument();
    expect(screen.getByText('Parent Invitation')).toBeInTheDocument();
    expect(screen.getByText('https://nassaq.test/invite/abc123')).toBeInTheDocument();

    // Student keeps its real temp password; the parent never gets one.
    expect(screen.getByText('Stud-1234')).toBeInTheDocument();
    expect(screen.getAllByText('password2')).toHaveLength(1);
    expect(screen.queryByText('undefined')).not.toBeInTheDocument();
  });

  test('pending mode: shows the pending-link card, no parent account/password', async () => {
    await renderToSuccess({
      success: true,
      student: STUDENT,
      // Guardian details stored with the student; no parent account created.
      parent: null,
      parent_onboarding: { mode: 'pending' },
      siblings: { list: [] },
    });

    expect(await screen.findByText('Student account created')).toBeInTheDocument();
    expect(screen.getByText('Parent — Pending Link')).toBeInTheDocument();

    expect(screen.getByText('Stud-1234')).toBeInTheDocument();
    expect(screen.getAllByText('password2')).toHaveLength(1);
    expect(screen.queryByText('undefined')).not.toBeInTheDocument();
  });

  test('linked mode: shows self-reset guidance, no fabricated parent password', async () => {
    await renderToSuccess({
      success: true,
      student: STUDENT,
      // Linked to a pre-existing parent account (not new -> no temp password).
      parent: { full_name: 'ولي الأمر', phone: '0500000000', is_new: false },
      parent_onboarding: { mode: 'linked', can_self_reset: true },
      siblings: { list: [] },
    });

    expect(
      await screen.findByText('studentAndParentAccountsCreated')
    ).toBeInTheDocument();
    expect(
      screen.getByText('The parent activates access via "Forgot password" using their registered email.')
    ).toBeInTheDocument();

    expect(screen.getByText('Stud-1234')).toBeInTheDocument();
    expect(screen.getAllByText('password2')).toHaveLength(1);
    expect(screen.queryByText('undefined')).not.toBeInTheDocument();
  });
});
