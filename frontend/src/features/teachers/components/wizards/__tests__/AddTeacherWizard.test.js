/**
 * Regression coverage for the Add Teacher wizard.
 *
 * Guards the freeze fix (Task #756): after clicking "Confirm & Save" the wizard
 * must reach the success screen, fire onSuccess, and be closable via onOpenChange;
 * a backend rejection must keep the dialog open and re-enable the buttons
 * (submitting cleared); and Escape / backdrop-click must be ignored while a
 * request is in flight.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AddTeacherWizard } from '../AddTeacherWizard';

const mockApi = { get: jest.fn(), post: jest.fn() };
const mockNassaqError = jest.fn();

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }) => <a href={to} {...props}>{children}</a>,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false }),
  useTranslation: () => ({ t: (key) => key }),
}));

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', api: mockApi }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

// Lightweight Dialog: render children when open, and expose a trigger that calls
// onOpenChange(false) to emulate Radix Escape / backdrop-click.
jest.mock('@/shared/components/ui/dialog', () => {
  const React = require('react');
  const Dialog = ({ open, onOpenChange, children }) =>
    open
      ? React.createElement(
          'div',
          { 'data-testid': 'dialog-root' },
          React.createElement('button', {
            type: 'button',
            'data-testid': 'dialog-dismiss',
            onClick: () => onOpenChange && onOpenChange(false),
          }),
          children
        )
      : null;
  const passthrough = ({ children }) => React.createElement(React.Fragment, null, children);
  return {
    Dialog,
    DialogContent: ({ children }) => React.createElement('div', null, children),
    DialogHeader: passthrough,
    DialogFooter: passthrough,
    DialogTitle: passthrough,
    DialogDescription: passthrough,
  };
});

// Native <select> stand-in: collect <SelectItem> values + the trigger testid so
// the multi-step flow can be driven deterministically (Radix Select relies on
// pointer events that jsdom does not implement).
jest.mock('@/shared/components/ui/select', () => {
  const React = require('react');
  const SelectItem = () => null;
  const SelectTrigger = () => null;
  const SelectValue = () => null;
  const SelectContent = ({ children }) => children;
  const Select = ({ value, onValueChange, children }) => {
    let testId;
    const options = [];
    const walk = (nodes) => {
      React.Children.forEach(nodes, (child) => {
        if (!React.isValidElement(child)) return;
        if (child.type === SelectTrigger && child.props['data-testid']) {
          testId = child.props['data-testid'];
        }
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
        'data-testid': testId,
        value: value || '',
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

const OPTIONS = {
  '/teachers/options/subjects': { subjects: [{ id: 'math', name_ar: 'رياضيات', name_en: 'Math' }] },
  '/teachers/options/grades': { grades: [{ id: 'g1', name_ar: 'الأول', name_en: 'Grade 1' }] },
  '/teachers/options/academic-degrees': { degrees: [{ id: 'bachelor', name_ar: 'بكالوريوس', name_en: 'Bachelor' }] },
  '/teachers/options/teacher-ranks': { ranks: [{ id: 'teacher', name_ar: 'معلم', name_en: 'Teacher' }] },
  '/teachers/options/contract-types': { types: [{ id: 'permanent', name_ar: 'دائم', name_en: 'Permanent' }] },
  '/teachers/options/nationalities': { nationalities: [{ id: 'SA', name_ar: 'سعودي', name_en: 'Saudi' }] },
};

const setSelect = (testId, value) =>
  fireEvent.change(screen.getByTestId(testId), { target: { value } });

// Walk steps 1 -> 5 filling every required field, leaving the wizard on the
// review step ready to submit.
const fillThroughReview = async () => {
  // Step 1 - basic info
  fireEvent.change(screen.getByTestId('teacher-name-ar'), { target: { value: 'أحمد المعلم' } });
  fireEvent.change(screen.getByTestId('teacher-national-id'), { target: { value: '1234567890' } });
  fireEvent.click(screen.getByText('Male'));
  fireEvent.change(screen.getByTestId('teacher-phone'), { target: { value: '0500000000' } });
  fireEvent.change(screen.getByTestId('teacher-email'), { target: { value: 'ahmed@example.com' } });
  fireEvent.click(screen.getByText('next'));

  // Step 2 - qualifications
  setSelect('teacher-degree', 'bachelor');
  setSelect('teacher-rank', 'teacher');
  fireEvent.click(screen.getByText('next'));

  // Step 3 - subjects & grades ("Math" also appears as a <select> option, so
  // target the toggle button explicitly).
  fireEvent.click(screen.getByRole('button', { name: 'Math' }));
  fireEvent.click(screen.getByRole('button', { name: 'Grade 1' }));
  setSelect('teacher-primary-subject', 'math');
  fireEvent.click(screen.getByText('next'));

  // Step 4 - schedule (no required fields)
  fireEvent.click(screen.getByText('next'));
};

beforeEach(() => {
  jest.clearAllMocks();
  mockApi.get.mockImplementation((url) => Promise.resolve({ data: OPTIONS[url] || {} }));
});

const renderWizard = async (props = {}) => {
  const onOpenChange = jest.fn();
  const onSuccess = jest.fn();
  await act(async () => {
    render(<AddTeacherWizard open onOpenChange={onOpenChange} onSuccess={onSuccess} {...props} />);
  });
  // Wait for fetchOptions() to resolve so the subjects step is interactive.
  await screen.findByTestId('teacher-name-ar');
  return { onOpenChange, onSuccess };
};

describe('AddTeacherWizard - Confirm & Save', () => {
  test('happy path: creates teacher, shows success, fires onSuccess, and closes via onOpenChange', async () => {
    mockApi.post.mockResolvedValue({
      data: { success: true, teacher_id: 'T-100', user_account: { created: true, email: 'ahmed@example.com' } },
    });

    const { onOpenChange, onSuccess } = await renderWizard();
    await fillThroughReview();

    await act(async () => {
      fireEvent.click(screen.getByText('confirmSave'));
    });

    await waitFor(() => expect(mockApi.post).toHaveBeenCalledWith('/teachers/create', expect.any(Object)));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));

    // Step-6 success screen shows the new teacher id.
    expect(await screen.findByText('T-100')).toBeInTheDocument();
    expect(mockNassaqError).not.toHaveBeenCalled();

    // Closing the success screen propagates through onOpenChange to the parent.
    fireEvent.click(screen.getByText('close'));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  test('error path: backend rejection keeps dialog open, shows Arabic-safe error, and re-enables buttons', async () => {
    mockApi.post.mockRejectedValue({ response: { data: { detail: 'رقم الهوية مسجل مسبقاً' } } });

    const { onOpenChange, onSuccess } = await renderWizard();
    await fillThroughReview();

    const confirmBtn = screen.getByText('confirmSave').closest('button');
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledWith('رقم الهوية مسجل مسبقاً'));
    expect(onSuccess).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalled();

    // Dialog stays open on the review step and the confirm button is usable again.
    expect(screen.getByTestId('dialog-root')).toBeInTheDocument();
    expect(screen.getByText('confirmSave').closest('button')).not.toBeDisabled();
  });

  test('in-flight guard: Escape / backdrop-click does nothing while submitting', async () => {
    let resolvePost;
    mockApi.post.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));

    const { onOpenChange } = await renderWizard();
    await fillThroughReview();

    // Start the request but do not resolve it yet.
    await act(async () => {
      fireEvent.click(screen.getByText('confirmSave'));
    });

    // Simulate Radix Escape / backdrop -> onOpenChange(false) -> handleCloseDialog.
    fireEvent.click(screen.getByTestId('dialog-dismiss'));
    expect(onOpenChange).not.toHaveBeenCalled();

    // Resolve the request; now the wizard behaves normally.
    await act(async () => {
      resolvePost({ data: { success: true, teacher_id: 'T-200', user_account: { created: true } } });
    });
    expect(await screen.findByText('T-200')).toBeInTheDocument();
  });
});
