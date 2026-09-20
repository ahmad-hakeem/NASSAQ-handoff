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
import en from '@/locales/en.json';
import ar from '@/locales/ar.json';

const mockApi = { get: jest.fn(), post: jest.fn() };
const mockNassaqError = jest.fn();
const mockNassaqConfirm = jest.fn();

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }) => <a href={to} {...props}>{children}</a>,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false }),
  useTranslation: () => ({
    t: (key) => ({
      invalidExperience: 'Experience must be a non-negative integer',
      qualificationNotProvided: 'Not provided',
    }[key] || key),
  }),
}));

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', api: mockApi }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError, nassaqConfirm: mockNassaqConfirm }),
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
  const SelectTrigger = ({ id, ...props }) => React.createElement('span', { id, ...props });
  const SelectValue = () => null;
  const SelectContent = ({ children }) => children;
  const Select = ({ value, onValueChange, children }) => {
    let testId;
    let triggerId;
    const options = [];
    const walk = (nodes) => {
      React.Children.forEach(nodes, (child) => {
        if (!React.isValidElement(child)) return;
        if (child.type === SelectTrigger && child.props['data-testid']) {
          testId = child.props['data-testid'];
          triggerId = child.props.id;
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
        id: triggerId,
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

const fillBasicToQualifications = () => {
  fireEvent.change(screen.getByTestId('teacher-name-ar'), { target: { value: 'أحمد المعلم' } });
  fireEvent.change(screen.getByTestId('teacher-national-id'), { target: { value: '1234567890' } });
  fireEvent.click(screen.getByText('Male'));
  fireEvent.change(screen.getByTestId('teacher-phone'), { target: { value: '0500000000' } });
  fireEvent.change(screen.getByTestId('teacher-email'), { target: { value: 'ahmed@example.com' } });
  fireEvent.click(screen.getByText('next'));
};

const finishFromQualifications = () => {
  fireEvent.click(screen.getByText('next'));
  fireEvent.click(screen.getByRole('button', { name: 'Math' }));
  fireEvent.click(screen.getByRole('button', { name: 'Grade 1' }));
  setSelect('teacher-primary-subject', 'math');
  fireEvent.click(screen.getByText('next'));
  fireEvent.click(screen.getByText('next'));
};

describe('AddTeacherWizard - optional qualifications', () => {
  test('provides localized qualification validation and missing-value messages', () => {
    expect(en.invalidExperience).toBe('Experience must be a non-negative integer');
    expect(ar.invalidExperience).toBe('يجب أن تكون الخبرة رقمًا صحيحًا غير سالب');
    expect(en.qualificationNotProvided).toBe('Not provided');
    expect(ar.qualificationNotProvided).toBe('غير مضاف');
  });

  test('allows all qualification fields to remain blank and submits null values', async () => {
    mockApi.post.mockResolvedValue({ data: { success: true, teacher_id: 'T-optional' } });
    await renderWizard();
    fillBasicToQualifications();
    expect(screen.getByText('Academic Degree').textContent).not.toContain('*');
    expect(screen.getByText('Years of Experience').textContent).not.toContain('*');
    expect(screen.getByText('teacherRank').textContent).not.toContain('*');
    finishFromQualifications();
    await act(async () => fireEvent.click(screen.getByText('confirmSave')));
    await waitFor(() => expect(mockApi.post).toHaveBeenCalledWith('/teachers/create', expect.objectContaining({
      qualifications: expect.objectContaining({
        academic_degree: null,
        teacher_rank: null,
        years_of_experience: null,
      }),
    })));
  });

  test('preserves explicit zero experience and normalizes partially populated qualifications', async () => {
    mockApi.post.mockResolvedValue({ data: { success: true, teacher_id: 'T-zero' } });
    await renderWizard();
    fillBasicToQualifications();
    fireEvent.change(screen.getByTestId('teacher-experience'), { target: { value: '0' } });
    setSelect('teacher-degree', 'bachelor');
    finishFromQualifications();
    await act(async () => fireEvent.click(screen.getByText('confirmSave')));
    await waitFor(() => expect(mockApi.post).toHaveBeenCalledWith('/teachers/create', expect.objectContaining({
      qualifications: expect.objectContaining({
        academic_degree: 'bachelor',
        teacher_rank: null,
        years_of_experience: 0,
      }),
    })));
  });

  test.each([
    ['degree only', { degree: 'bachelor' }, { academic_degree: 'bachelor', teacher_rank: null, years_of_experience: null }],
    ['rank only', { rank: 'teacher' }, { academic_degree: null, teacher_rank: 'teacher', years_of_experience: null }],
    ['experience only', { experience: '7' }, { academic_degree: null, teacher_rank: null, years_of_experience: 7 }],
    ['all three', { degree: 'bachelor', rank: 'teacher', experience: '7' }, { academic_degree: 'bachelor', teacher_rank: 'teacher', years_of_experience: 7 }],
  ])('submits %s qualification values without changing absent fields', async (_name, values, expected) => {
    mockApi.post.mockResolvedValue({ data: { success: true, teacher_id: 'T-populated' } });
    await renderWizard();
    fillBasicToQualifications();
    if (values.degree) setSelect('teacher-degree', values.degree);
    if (values.rank) setSelect('teacher-rank', values.rank);
    if (values.experience) fireEvent.change(screen.getByTestId('teacher-experience'), { target: { value: values.experience } });
    finishFromQualifications();
    await act(async () => fireEvent.click(screen.getByText('confirmSave')));
    await waitFor(() => expect(mockApi.post).toHaveBeenCalledWith('/teachers/create', expect.objectContaining({
      qualifications: expected,
    })));
  });

  test('resets every qualification field to blank values for another teacher', async () => {
    mockApi.post.mockResolvedValue({ data: { success: true, teacher_id: 'T-reset' } });
    await renderWizard();
    fillBasicToQualifications();
    setSelect('teacher-degree', 'bachelor');
    setSelect('teacher-rank', 'teacher');
    fireEvent.change(screen.getByTestId('teacher-experience'), { target: { value: '7' } });
    finishFromQualifications();
    await act(async () => fireEvent.click(screen.getByText('confirmSave')));
    await screen.findByText('addAnother2');
    fireEvent.click(screen.getByText('addAnother2'));
    fillBasicToQualifications();
    expect(screen.getByTestId('teacher-degree')).toHaveValue('');
    expect(screen.getByTestId('teacher-rank')).toHaveValue('');
    expect(screen.getByTestId('teacher-experience').value).toBe('');
  });

  test('review displays Arabic missing placeholders without an experience suffix', async () => {
    await renderWizard();
    fillBasicToQualifications();
    finishFromQualifications();
    expect(screen.getAllByText('Not provided')).toHaveLength(3);
    const experience = screen.getByText('experience2').parentElement.querySelector('p');
    expect(experience).toHaveTextContent('Not provided');
    expect(experience).not.toHaveTextContent('years');
  });

  test('associates each optional qualification label with its control', async () => {
    await renderWizard();
    fillBasicToQualifications();
    expect(screen.getByLabelText('Academic Degree')).toBe(screen.getByTestId('teacher-degree'));
    expect(screen.getByLabelText('Years of Experience')).toBe(screen.getByTestId('teacher-experience'));
    expect(screen.getByLabelText('teacherRank')).toBe(screen.getByTestId('teacher-rank'));
  });

  test('review appends years only when experience is populated', async () => {
    await renderWizard();
    fillBasicToQualifications();
    fireEvent.change(screen.getByTestId('teacher-experience'), { target: { value: '7' } });
    finishFromQualifications();
    const experience = screen.getByText('experience2').parentElement.querySelector('p');
    expect(experience).toHaveTextContent('7 years');
  });

  test('rejects provided negative or non-integer experience at the field', async () => {
    await renderWizard();
    fillBasicToQualifications();
    fireEvent.change(screen.getByTestId('teacher-experience'), { target: { value: '-1' } });
    fireEvent.click(screen.getByText('next'));
    expect(screen.getByText('Experience must be a non-negative integer')).toBeInTheDocument();
    fireEvent.change(screen.getByTestId('teacher-experience'), { target: { value: '1.5' } });
    fireEvent.click(screen.getByText('next'));
    expect(screen.getByText('Experience must be a non-negative integer')).toBeInTheDocument();
  });
});

describe('AddTeacherWizard - teacher birth date', () => {
  test('shows the calculated Hijri date in basic info and review, then submits Gregorian only', async () => {
    mockApi.post.mockResolvedValue({ data: { success: true, teacher_id: 'T-dob' } });
    await renderWizard();
    fireEvent.change(screen.getByTestId('teacher-dob'), { target: { value: '2024-03-11' } });
    expect(screen.getByText('1445-09-01 AH')).toBeInTheDocument();

    await fillThroughReview();
    expect(screen.getByText('2024-03-11')).toBeInTheDocument();
    expect(screen.getByText('1445-09-01 AH')).toBeInTheDocument();
    await act(async () => fireEvent.click(screen.getByText('confirmSave')));

    await waitFor(() => expect(mockApi.post).toHaveBeenCalledWith(
      '/teachers/create',
      expect.objectContaining({
        basic_info: expect.objectContaining({ date_of_birth: '2024-03-11' }),
      })
    ));
    expect(mockApi.post.mock.calls[0][1].basic_info).not.toHaveProperty('hijri_date_of_birth');
  });

  test('blocks malformed or future values using the Saudi date while allowing an unsupported old date', async () => {
    await renderWizard();
    fillBasicToQualifications();
    fireEvent.click(screen.getByText('back'));
    fireEvent.change(screen.getByTestId('teacher-dob'), { target: { value: '2999-01-01' } });
    fireEvent.click(screen.getByText('next'));
    expect(screen.getByRole('alert')).toHaveTextContent('futureBirthDate');
    expect(screen.getByTestId('teacher-name-ar')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('teacher-dob'), { target: { value: '1900-01-01' } });
    expect(screen.getByText('hijriConversionUnavailable')).toBeInTheDocument();
    fireEvent.click(screen.getByText('next'));
    expect(screen.getByTestId('teacher-degree')).toBeInTheDocument();
  });

  test('normalizes an untouched optional birth date to null', async () => {
    mockApi.post.mockResolvedValue({ data: { success: true, teacher_id: 'T-no-dob' } });
    await renderWizard();
    await fillThroughReview();
    await act(async () => fireEvent.click(screen.getByText('confirmSave')));
    await waitFor(() => expect(mockApi.post).toHaveBeenCalled());
    expect(mockApi.post.mock.calls[0][1].basic_info.date_of_birth).toBeNull();
  });
});

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

  test('restore offer can be cancelled without sending a restore request', async () => {
    mockApi.post.mockRejectedValueOnce({
      response: {
        data: {
          error: {
            code: 'TEACHER_RESTORE_AVAILABLE',
            detail: { message: 'يمكن استعادة الحساب السابق', teacher_id: 'deleted-1' },
          },
        },
      },
    });

    await renderWizard();
    await fillThroughReview();
    fireEvent.click(screen.getByText('confirmSave'));

    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalledTimes(1));
    expect(mockApi.post).toHaveBeenCalledTimes(1);
    const [message, , options] = mockNassaqConfirm.mock.calls[0];
    expect(message).toMatch(/prior account and history/i);
    expect(message).toMatch(/new information.*not.*applied/i);
    expect(message).toMatch(/assignments.*inactive/i);
    options.onCancel?.();
    expect(mockApi.post).toHaveBeenCalledTimes(1);
    expect(screen.getByText('confirmSave').closest('button')).not.toBeDisabled();
  });

  test('confirming restore posts only to restore endpoint and shows restore-specific success without credentials', async () => {
    mockApi.post
      .mockRejectedValueOnce({
        response: {
          data: {
            error: {
              code: 'TEACHER_RESTORE_AVAILABLE',
              detail: { message: 'يمكن استعادة الحساب السابق', teacher_id: 'deleted-2' },
            },
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          success: true,
          teacher_id: 'deleted-2',
          restored_existing: true,
          message: 'تمت الاستعادة',
          inactive_dependents: 3,
          user_account: { created: true, temp_password: 'must-not-render' },
        },
      });

    const { onSuccess } = await renderWizard();
    await fillThroughReview();
    fireEvent.click(screen.getByText('confirmSave'));
    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalled());

    await act(async () => {
      await mockNassaqConfirm.mock.calls[0][1]();
    });

    expect(mockApi.post).toHaveBeenLastCalledWith('/teachers/deleted-2/restore');
    expect(await screen.findByText(/restored/i)).toBeInTheDocument();
    expect(screen.getByText(/existing password/i)).toBeInTheDocument();
    expect(screen.queryByText('must-not-render')).not.toBeInTheDocument();
    expect(screen.queryByText('loginCredentials2')).not.toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ restored_existing: true }));
  });

  test('failed restore stays on review and permits retry', async () => {
    mockApi.post
      .mockRejectedValueOnce({
        response: { data: { error: { code: 'TEACHER_RESTORE_AVAILABLE', detail: { message: 'restore?', teacher_id: 'deleted-3' } } } },
      })
      .mockRejectedValueOnce({
        response: { data: { error: { message: 'تعذر استعادة المعلم' } } },
      });

    await renderWizard();
    await fillThroughReview();
    fireEvent.click(screen.getByText('confirmSave'));
    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalled());
    await act(async () => {
      await mockNassaqConfirm.mock.calls[0][1]();
    });

    expect(mockNassaqError).toHaveBeenCalledWith('تعذر استعادة المعلم');
    expect(screen.getByText('confirmSave')).toBeInTheDocument();
    expect(screen.getByText('confirmSave').closest('button')).not.toBeDisabled();
  });

  test('ordinary active duplicate remains the normal error and does not offer restore', async () => {
    mockApi.post.mockRejectedValue({
      response: { data: { error: { code: 'TEACHER_ALREADY_EXISTS', message: 'المعلم مسجل بالفعل' } } },
    });
    await renderWizard();
    await fillThroughReview();
    fireEvent.click(screen.getByText('confirmSave'));
    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledWith('المعلم مسجل بالفعل'));
    expect(mockNassaqConfirm).not.toHaveBeenCalled();
  });

  test('restore request disables actions, blocks dismissal, and cannot be double-submitted', async () => {
    let resolveRestore;
    mockApi.post
      .mockRejectedValueOnce({
        response: { data: { error: { code: 'TEACHER_RESTORE_AVAILABLE', detail: { message: 'restore?', teacher_id: 'deleted-4' } } } },
      })
      .mockReturnValueOnce(new Promise((resolve) => { resolveRestore = resolve; }));

    const { onOpenChange } = await renderWizard();
    await fillThroughReview();
    fireEvent.click(screen.getByText('confirmSave'));
    await waitFor(() => expect(mockNassaqConfirm).toHaveBeenCalled());
    act(() => {
      mockNassaqConfirm.mock.calls[0][1]();
      mockNassaqConfirm.mock.calls[0][1]();
    });

    await waitFor(() => expect(screen.getByText('confirmSave').closest('button')).toBeDisabled());
    fireEvent.click(screen.getByText('confirmSave'));
    fireEvent.click(screen.getByTestId('dialog-dismiss'));
    expect(mockApi.post).toHaveBeenCalledTimes(2);
    expect(onOpenChange).not.toHaveBeenCalled();

    await act(async () => {
      resolveRestore({ data: { success: true, teacher_id: 'deleted-4', restored_existing: true } });
    });
  });
});
