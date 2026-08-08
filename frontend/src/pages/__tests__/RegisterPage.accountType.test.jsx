/**
 * Account-type routing regression guard for the public /register wizard.
 *
 * BUG: picking "معلم / معلمة" (School Teacher — join an existing school,
 * accountType === 'teacher') at step 3 navigated to /teacher-register.
 * That page posts to /teacher-registration/direct, which hard-codes
 * account_type="independent_teacher" (see the endpoint docstring — it is the
 * Teacher-Experience landing CTA). The signer therefore got an Independent
 * Teacher account with tenant_id = NULL and was pushed into the IT workspace
 * wizard ("مساحتك / السنة والجدول / فصلك الأول") instead of the school-teacher
 * join flow.
 *
 * The wizard already owns a complete school-teacher path: validateStep4's
 * 'teacher' branch, the step-4 teacher fields, and a POST to
 * /registration-requests with account_type 'teacher' (queued for review).
 * These tests pin that each of the three account types stays on its own path.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
}), { virtual: true });

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

// The hook return values are built INSIDE each factory so the identities stay
// stable across renders: RegisterPage has a useCallback keyed on `api` feeding
// a useEffect, and a fresh object per call would loop that effect.
const mockApiPost = jest.fn();
const mockApiGet = jest.fn();
const mockApplyAuthSession = jest.fn();
jest.mock('../../contexts/AuthContext', () => {
  const api = { post: (...a) => mockApiPost(...a), get: (...a) => mockApiGet(...a) };
  const value = { api, applyAuthSession: (...a) => mockApplyAuthSession(...a) };
  return { useAuth: () => value };
});

jest.mock('../../contexts/ThemeContext', () => {
  const theme = { isRTL: true, toggleLanguage: () => {} };
  const translation = { t: (k) => k };
  return { useTheme: () => theme, useTranslation: () => translation };
});

const mockNassaqError = jest.fn();
const mockNassaqWarning = jest.fn();
jest.mock('../../components/ui/NassaqAlertDialog', () => {
  const value = {
    nassaqError: (...a) => mockNassaqError(...a),
    nassaqWarning: (...a) => mockNassaqWarning(...a),
  };
  return { useNassaqAlert: () => value };
});

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../../components/ui/button', () => ({
  Button: ({ children, asChild: _a, variant: _v, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('../../components/ui/input', () => {
  const R = require('react');
  return { Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })) };
});
jest.mock('../../components/ui/label', () => ({
  Label: ({ children, ...rest }) => <label {...rest}>{children}</label>,
}));
jest.mock('../../components/ui/card', () => ({
  Card: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardContent: ({ children, ...rest }) => <div {...rest}>{children}</div>,
  CardHeader: ({ children, ...rest }) => <div {...rest}>{children}</div>,
}));
jest.mock('../../components/ui/checkbox', () => ({
  Checkbox: ({ onCheckedChange, checked, ...rest }) => (
    <input type="checkbox" checked={!!checked} onChange={(e) => onCheckedChange?.(e.target.checked)} {...rest} />
  ),
}));
jest.mock('../../components/ui/radio-group', () => ({
  RadioGroup: ({ children, value: _v, onValueChange: _o, ...rest }) => <div {...rest}>{children}</div>,
  RadioGroupItem: ({ value, ...rest }) => <input type="radio" value={value} readOnly {...rest} />,
}));
jest.mock('../../components/ui/badge', () => ({
  Badge: ({ children, ...rest }) => <span {...rest}>{children}</span>,
}));

// Import after mocks.
const { RegisterPage } = require('../RegisterPage');

const next = () => fireEvent.click(screen.getByTestId('next-step-btn'));

/** Drive steps 1-3 and land on step 4 for the given account type. */
const advanceToStep4 = (accountTypeTestId) => {
  fireEvent.change(screen.getByTestId('full-name-input'), { target: { value: 'أحمد المعلم' } });
  fireEvent.change(screen.getByTestId('phone-input'), { target: { value: '0512345678' } });
  next();

  fireEvent.click(screen.getByTestId('privacy-checkbox'));
  next();

  fireEvent.click(screen.getByTestId(accountTypeTestId));
  next();
};

beforeEach(() => {
  mockNavigate.mockReset();
  mockApiPost.mockReset();
  mockApiGet.mockReset();
  mockApplyAuthSession.mockReset();
  mockNassaqError.mockReset();
  mockNassaqWarning.mockReset();
  mockApiGet.mockResolvedValue({ data: { is_duplicate: false } });
});

describe('RegisterPage — account type must survive to the right onboarding form', () => {
  test('School Teacher stays in the wizard and is NOT sent to the IT signup page', () => {
    render(<RegisterPage />);
    advanceToStep4('account-type-teacher');

    // The regression: this used to navigate away to the Independent-Teacher
    // signup page, which mints role=independent_teacher.
    expect(mockNavigate).not.toHaveBeenCalledWith('/teacher-register', expect.anything());
    expect(mockNavigate).not.toHaveBeenCalled();

    // ...and the school-teacher step-4 form is what renders.
    expect(screen.getByTestId('step-4-content')).toBeInTheDocument();
    expect(screen.getByTestId('teacher-email-input')).toBeInTheDocument();
    expect(screen.getByTestId('specialization-input')).toBeInTheDocument();
    expect(screen.getByTestId('school-code-input')).toBeInTheDocument();

    // Not the Independent-Teacher variant of step 4.
    expect(screen.queryByTestId('it-email-input')).not.toBeInTheDocument();
    expect(screen.queryByTestId('it-password-input')).not.toBeInTheDocument();
  });

  test('School Teacher submits account_type "teacher" to the review queue', async () => {
    mockApiPost.mockResolvedValue({ data: { id: 'req-1' } });

    render(<RegisterPage />);
    advanceToStep4('account-type-teacher');

    fireEvent.change(screen.getByTestId('teacher-email-input'), { target: { value: 'teacher@school.com' } });
    fireEvent.change(screen.getByTestId('specialization-input'), { target: { value: 'رياضيات' } });
    fireEvent.change(screen.getByTestId('school-code-input'), { target: { value: 'SCH001' } });

    await act(async () => { fireEvent.click(screen.getByTestId('submit-btn')); });

    await waitFor(() => expect(mockApiPost).toHaveBeenCalled());
    const [url, payload] = mockApiPost.mock.calls[0];
    expect(url).toBe('/registration-requests');
    expect(payload.account_type).toBe('teacher');
    expect(payload.email).toBe('teacher@school.com');
    expect(payload.school_code).toBe('SCH001');
    // A school teacher joins an existing school — no self-chosen password.
    expect(payload.password).toBeUndefined();

    // Queued for review => confirmation screen, never the IT workspace wizard.
    await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
    const [target, opts] = mockNavigate.mock.calls[mockNavigate.mock.calls.length - 1];
    expect(target).toBe('/registration-confirmation');
    expect(opts.state.accountType).toBe('teacher');
    expect(mockNavigate).not.toHaveBeenCalledWith('/teacher/onboarding', expect.anything());
  });

  test('Independent Teacher still gets the IT step-4 form and posts its own account type', async () => {
    mockApiPost.mockResolvedValue({ data: { id: 'req-2' } });

    render(<RegisterPage />);
    advanceToStep4('account-type-independent-teacher');

    expect(screen.getByTestId('it-email-input')).toBeInTheDocument();
    expect(screen.queryByTestId('teacher-email-input')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('it-email-input'), { target: { value: 'solo@teacher.com' } });
    fireEvent.change(screen.getByTestId('it-password-input'), { target: { value: 'Password123!' } });
    fireEvent.change(screen.getByTestId('it-confirm-password-input'), { target: { value: 'Password123!' } });

    await act(async () => { fireEvent.click(screen.getByTestId('submit-btn')); });

    await waitFor(() => expect(mockApiPost).toHaveBeenCalled());
    expect(mockApiPost.mock.calls[0][1].account_type).toBe('independent_teacher');
  });

  test('stepping back to the chooser and forward again keeps the school-teacher form', () => {
    render(<RegisterPage />);
    advanceToStep4('account-type-teacher');
    expect(screen.getByTestId('teacher-email-input')).toBeInTheDocument();

    // "السابق" returns to the chooser (the old redirect used replace:true, which
    // destroyed the /register history entry and stranded the user).
    fireEvent.click(screen.getByTestId('prev-step-btn'));
    expect(screen.getByTestId('step-3-content')).toBeInTheDocument();

    next();
    expect(screen.getByTestId('teacher-email-input')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();

    // Switching the choice on the way back through must repaint step 4.
    fireEvent.click(screen.getByTestId('prev-step-btn'));
    fireEvent.click(screen.getByTestId('account-type-independent-teacher'));
    next();
    expect(screen.getByTestId('it-email-input')).toBeInTheDocument();
    expect(screen.queryByTestId('teacher-email-input')).not.toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  test('New School still gets the school step-4 form', () => {
    render(<RegisterPage />);
    advanceToStep4('account-type-school');

    expect(screen.getByTestId('school-name-input')).toBeInTheDocument();
    expect(screen.queryByTestId('teacher-email-input')).not.toBeInTheDocument();
    expect(screen.queryByTestId('it-email-input')).not.toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
