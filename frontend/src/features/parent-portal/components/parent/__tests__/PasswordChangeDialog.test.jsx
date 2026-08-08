/**
 * Task #470 — Parent Account Settings → Change Password dialog.
 *
 * Pins the three error/success contracts the bug report fixed:
 *
 *   1. A 200 from /auth/change-password closes the dialog and shows
 *      exactly one success toast — no error dialog fires.
 *   2. A 400 with an Arabic `detail` surfaces exactly one nassaqError
 *      (the dialog's local catch), keeps the dialog mounted, and does
 *      NOT call the global serverErrorWithCode toast.
 *   3. A 500 surfaces exactly one user-visible error (the local
 *      nassaqError); the dialog must not navigate or fire two popups.
 *   4. Submit is disabled while the request is in-flight.
 *
 * The dialog now POSTs `/auth/change-password` (was the broken
 * `PUT /users/{id}/password` route which raised NameError → 500).
 */
import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';

const mockNassaqError = jest.fn();
const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();
const mockPost = jest.fn();
const mockPut = jest.fn();

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'parent-user-id' },
    api: { post: mockPost, put: mockPut },
  }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (key) => key }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

jest.mock('sonner', () => ({
  toast: { success: (...a) => mockToastSuccess(...a), error: (...a) => mockToastError(...a) },
}));

import PasswordChangeDialog from '../PasswordChangeDialog';

function fillAndSubmit() {
  fireEvent.change(screen.getByTestId('parent-password-current-input'), {
    target: { value: 'Old@1234!' },
  });
  fireEvent.change(screen.getByTestId('parent-password-new-input'), {
    target: { value: 'Brand@New4567!' },
  });
  fireEvent.change(screen.getByTestId('parent-password-confirm-input'), {
    target: { value: 'Brand@New4567!' },
  });
  fireEvent.click(screen.getByTestId('parent-password-submit-btn'));
}

describe('PasswordChangeDialog — Task #470', () => {
  beforeEach(() => {
    mockNassaqError.mockClear();
    mockToastSuccess.mockClear();
    mockToastError.mockClear();
    mockPost.mockReset();
    mockPut.mockReset();
  });

  test('calls POST /auth/change-password (not the legacy PUT route) and closes on 200', async () => {
    mockPost.mockResolvedValueOnce({ data: { message: 'تم تغيير كلمة المرور بنجاح' } });
    const onOpenChange = jest.fn();
    render(<PasswordChangeDialog open={true} onOpenChange={onOpenChange} />);

    await act(async () => {
      fillAndSubmit();
    });

    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(mockPost).toHaveBeenCalledWith('/auth/change-password', {
      current_password: 'Old@1234!',
      new_password: 'Brand@New4567!',
    });
    expect(mockPut).not.toHaveBeenCalled();
    expect(mockToastSuccess).toHaveBeenCalledTimes(1);
    expect(mockNassaqError).not.toHaveBeenCalled();
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });

  test('400 with Arabic detail fires exactly one nassaqError (no global toast.error)', async () => {
    const detail = 'كلمة المرور الحالية غير صحيحة';
    mockPost.mockRejectedValueOnce({ response: { status: 400, data: { detail } } });
    const onOpenChange = jest.fn();
    render(<PasswordChangeDialog open={true} onOpenChange={onOpenChange} />);

    await act(async () => {
      fillAndSubmit();
    });

    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledTimes(1));
    expect(mockNassaqError).toHaveBeenCalledWith(detail);
    expect(mockToastError).not.toHaveBeenCalled();
    expect(mockToastSuccess).not.toHaveBeenCalled();
    // Dialog stays mounted (onOpenChange not called with false).
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  test('500 surfaces exactly one local nassaqError with safe Arabic fallback (not raw English)', async () => {
    mockPost.mockRejectedValueOnce({
      response: { status: 500, data: { detail: 'Internal Server Error' } },
    });
    const onOpenChange = jest.fn();
    render(<PasswordChangeDialog open={true} onOpenChange={onOpenChange} />);

    await act(async () => {
      fillAndSubmit();
    });

    await waitFor(() => expect(mockNassaqError).toHaveBeenCalledTimes(1));
    // Raw English "Internal Server Error" MUST NOT leak through. The
    // dialog gates: 4xx → backend safe Arabic `detail`; 5xx → generic
    // Arabic fallback. We mock `t` as the identity function so the
    // fallback key is what appears.
    const surfaced = mockNassaqError.mock.calls[0][0];
    expect(surfaced).not.toBe('Internal Server Error');
    expect(surfaced).toMatch(/errorChangingPassword|كلمة المرور/);
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  test('submit button is disabled while request is in flight', async () => {
    let resolveFn;
    mockPost.mockReturnValueOnce(new Promise((resolve) => { resolveFn = resolve; }));
    render(<PasswordChangeDialog open={true} onOpenChange={jest.fn()} />);

    await act(async () => {
      fillAndSubmit();
    });

    const btn = screen.getByTestId('parent-password-submit-btn');
    expect(btn).toBeDisabled();

    await act(async () => {
      resolveFn({ data: {} });
    });

    await waitFor(() => expect(mockToastSuccess).toHaveBeenCalled());
  });
});
