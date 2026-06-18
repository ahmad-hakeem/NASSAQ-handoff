/**
 * GenericNameGuard — name-update modal flow.
 *
 * Confirms the save path uses the app's configured `api` client (not raw
 * axios), wires the input as a controlled component, gates obviously-invalid
 * names client-side, and surfaces a clear backend error inline without
 * freezing the UI (the Save button re-enables on failure).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockNavigate = jest.fn();
let mockPathname = '/admin/product-hub/submit';
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: mockPathname }),
}), { virtual: true });

const mockToastSuccess = jest.fn();
jest.mock('sonner', () => ({
  toast: { success: (...a) => mockToastSuccess(...a), error: jest.fn() },
}));

const mockApiPut = jest.fn();
const mockUpdateUser = jest.fn();
const mockRefreshUser = jest.fn();
const mockAuthState = { user: null };

jest.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    get user() { return mockAuthState.user; },
    api: { put: (...a) => mockApiPut(...a) },
    updateUser: (...a) => mockUpdateUser(...a),
    refreshUser: (...a) => mockRefreshUser(...a),
  }),
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
jest.mock('../ui/button', () => ({
  Button: ({ children, ...rest }) => <button {...rest}>{children}</button>,
}));
jest.mock('../ui/input', () => {
  const R = require('react');
  return {
    Input: R.forwardRef((props, ref) => R.createElement('input', { ref, ...props })),
  };
});

const { GenericNameGuard } = require('../GenericNameGuard');

const openModal = () => {
  // The amber banner button ("تحديث اسمي") opens the modal synchronously,
  // avoiding the 800ms auto-open timer.
  fireEvent.click(screen.getByText('تحديث اسمي'));
};

beforeEach(() => {
  mockNavigate.mockReset();
  mockToastSuccess.mockReset();
  mockApiPut.mockReset();
  mockUpdateUser.mockReset();
  mockRefreshUser.mockReset();
  mockRefreshUser.mockResolvedValue(null);
  mockPathname = '/admin/product-hub/submit';
  mockAuthState.user = { id: 'u1', full_name: 'MJ', has_generic_name: true };
});

describe('GenericNameGuard — name update modal', () => {
  test('valid name saves via the configured api client and clears the flag', async () => {
    mockApiPut.mockResolvedValue({ data: { success: true, user: { full_name: 'احمد زلط' } } });

    render(<GenericNameGuard><div>child</div></GenericNameGuard>);
    openModal();

    const input = screen.getByPlaceholderText(/مثال/);
    fireEvent.change(input, { target: { value: 'احمد زلط' } });
    expect(input.value).toBe('احمد زلط');

    fireEvent.click(screen.getByText('تحديث اسمي الآن'));

    await waitFor(() =>
      expect(mockApiPut).toHaveBeenCalledWith('/users/me/profile', { full_name: 'احمد زلط' }),
    );
    await waitFor(() =>
      expect(mockUpdateUser).toHaveBeenCalledWith({ full_name: 'احمد زلط', has_generic_name: false }),
    );
    expect(mockRefreshUser).toHaveBeenCalled();
    expect(mockToastSuccess).toHaveBeenCalled();
  });

  test('too-short name is blocked client-side (no API call) with an inline error', () => {
    render(<GenericNameGuard><div>child</div></GenericNameGuard>);
    openModal();

    fireEvent.change(screen.getByPlaceholderText(/مثال/), { target: { value: 'a' } });
    fireEvent.click(screen.getByText('تحديث اسمي الآن'));

    expect(mockApiPut).not.toHaveBeenCalled();
    expect(screen.getByText(/الاسم قصير جداً/)).toBeInTheDocument();
  });

  test('leading formula char is blocked client-side, matching the backend rule', () => {
    render(<GenericNameGuard><div>child</div></GenericNameGuard>);
    openModal();

    fireEvent.change(screen.getByPlaceholderText(/مثال/), { target: { value: '-Ali' } });
    fireEvent.click(screen.getByText('تحديث اسمي الآن'));

    expect(mockApiPut).not.toHaveBeenCalled();
    expect(screen.getByText(/رمز غير مسموح به/)).toBeInTheDocument();
  });

  test('backend error envelope is surfaced inline and the UI does not freeze', async () => {
    mockApiPut.mockRejectedValue({
      response: { data: { success: false, error: { code: 'HTTP_400', message: 'رسالة خطأ من الخادم' } } },
    });

    render(<GenericNameGuard><div>child</div></GenericNameGuard>);
    openModal();

    fireEvent.change(screen.getByPlaceholderText(/مثال/), { target: { value: 'احمد زلط' } });
    fireEvent.click(screen.getByText('تحديث اسمي الآن'));

    await waitFor(() => expect(screen.getByText('رسالة خطأ من الخادم')).toBeInTheDocument());
    // Save button is re-enabled (saving=false) — no freeze.
    expect(screen.getByText('تحديث اسمي الآن').closest('button')).not.toBeDisabled();
  });
});
