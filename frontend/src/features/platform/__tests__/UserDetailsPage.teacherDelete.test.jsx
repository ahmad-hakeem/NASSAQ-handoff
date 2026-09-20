import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { toast } from 'sonner';
import UserDetailsPage from '../pages/UserDetailsPage';

const mockNavigate = jest.fn();
const mockApi = {
  get: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
};

jest.mock('react-router-dom', () => ({
  useParams: () => ({ userId: 'teacher-user-1' }),
  useNavigate: () => mockNavigate,
  useLocation: () => ({ state: null }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockApi, isRTL: true }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqWarning: jest.fn() }),
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div>{children}</div>,
}));

jest.mock('@/shared/components/layout/PageHeader', () => ({
  PageHeader: ({ title }) => <h1>{title}</h1>,
}));

jest.mock('@/shared/components/ui/ImageCropModal', () => ({
  ImageCropModal: () => null,
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

const teacher = {
  id: 'teacher-user-1',
  role: 'teacher',
  full_name: 'Teacher One',
  email: 'teacher@example.com',
  is_active: true,
  permissions: [],
};

describe('UserDetailsPage teacher deletion', () => {
  let consoleErrorSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.get.mockResolvedValue({ data: teacher });
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('shows truthful teacher-specific permanent deletion consequences', async () => {
    render(<UserDetailsPage />);

    fireEvent.click(await screen.findByTestId('delete-user-btn'));

    expect(await screen.findByText('حذف حساب المعلم نهائياً')).toBeInTheDocument();
    expect(screen.getByText(/تحرير البريد الإلكتروني ورقم الهاتف والهوية/)).toBeInTheDocument();
    expect(screen.getByText(/السجلات التعليمية والتاريخية السابقة محفوظة/)).toBeInTheDocument();
    expect(screen.getByText(/ارتباطات مشتركة أو غير مؤكدة/)).toBeInTheDocument();
  });

  it('surfaces a structured 409 review message and keeps the dialog open', async () => {
    mockApi.delete.mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: {
            code: 'HTTP_409',
            message: '',
            detail: {
              message: 'يلزم مراجعة مسؤول المنصة بسبب هوية مشتركة',
            },
          },
        },
      },
    });
    render(<UserDetailsPage />);

    fireEvent.click(await screen.findByTestId('delete-user-btn'));
    fireEvent.click(await screen.findByRole('button', { name: /حذف المعلم نهائياً/ }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('يلزم مراجعة مسؤول المنصة بسبب هوية مشتركة');
    });
    expect(screen.getByText('حذف حساب المعلم نهائياً')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalledWith('/admin/users');
  });

  it('prevents a second delete request while the first is pending', async () => {
    let resolveDelete;
    mockApi.delete.mockImplementation(() => new Promise((resolve) => {
      resolveDelete = resolve;
    }));
    render(<UserDetailsPage />);

    fireEvent.click(await screen.findByTestId('delete-user-btn'));
    const confirm = await screen.findByRole('button', { name: /حذف المعلم نهائياً/ });
    fireEvent.click(confirm);
    fireEvent.click(confirm);

    expect(mockApi.delete).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole('button', { name: /جارٍ الحذف/ })).toBeDisabled();

    resolveDelete({ data: { success: true } });
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/admin/users'));
  });
});