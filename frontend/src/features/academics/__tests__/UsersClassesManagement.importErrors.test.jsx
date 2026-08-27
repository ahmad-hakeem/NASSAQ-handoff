import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockSetSearchParams = jest.fn();
const mockSearchParams = new URLSearchParams('filter=import-export');

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
}), { virtual: true });

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApi = { get: mockApiGet, post: mockApiPost, put: jest.fn(), delete: jest.fn() };
const mockUser = { id: 'u1', role: 'school_principal', tenant_id: 'school-1' };
const mockNassaqError = jest.fn();

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser,
    api: mockApi,
    schoolContext: null,
    isImpersonating: false,
  }),
}));

const dict = {
  importexport: 'استيراد/تصدير',
  import: 'استيراد',
  export: 'تصدير',
  importData: 'استيراد البيانات',
  students: 'الطلاب',
  teachers2: 'المعلمون',
  startImport: 'بدء الاستيراد',
  importResult: 'نتيجة الاستيراد',
  total2: 'إجمالي الصفوف',
  done: 'تم استيراده',
  failed: 'فشل',
  selectAFile: 'الرجاء اختيار ملف أولاً',
};

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: (k) => dict[k] || k }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqWarning: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

jest.mock('@/shared/models/utils/studentNavigation', () => ({
  useSchoolNavigation: () => ({
    navigateToStudent: jest.fn(),
  }),
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('@/features/platform/components/management/NoorImportPanel', () => ({
  __esModule: true,
  default: () => <div data-testid="noor-import-panel" />,
}));

import UsersClassesManagement from '../pages/UsersClassesManagement';

describe('UsersClassesManagement — Bulk Import Error Logs Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockImplementation((url) => {
      if (url.startsWith('/students')) return Promise.resolve({ data: [] });
      if (url.startsWith('/teachers')) return Promise.resolve({ data: [] });
      if (url.startsWith('/classes')) return Promise.resolve({ data: [] });
      if (url.startsWith('/parents')) return Promise.resolve({ data: [] });
      if (url.startsWith('/reference/grades')) return Promise.resolve({ data: [] });
      if (url.startsWith('/schools/')) return Promise.resolve({ data: { count: 0 } });
      return Promise.resolve({ data: [] });
    });
  });

  test('renders detailed error grid when import returns validation errors for rows', async () => {
    render(<UsersClassesManagement initialTab="import-export" />);

    await waitFor(() => {
      expect(screen.getByText('بدء الاستيراد')).toBeInTheDocument();
    });

    // Mock API post response for failed import
    mockApiPost.mockResolvedValueOnce({
      data: {
        success: false,
        total_rows: 2,
        imported: 0,
        failed: 1,
        errors: [
          {
            row: 3,
            field: 'اسم العائلة',
            message: 'اسم العائلة: حقل مطلوب ولا يمكن تركه فارغاً',
          },
          {
            row: 3,
            field: 'رقم الهوية',
            message: 'رقم الهوية (123): يجب أن يتكون من 10 أرقام',
          },
        ],
        warnings: [],
      },
    });

    // Simulate selecting a file
    const file = new File(['dummy content'], 'students_test.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    const fileInput = document.querySelector('input[type="file"]');
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Click "Start Import"
    const importBtn = screen.getByText('بدء الاستيراد');
    fireEvent.click(importBtn);

    // Verify error list rendered on screen
    await waitFor(() => {
      expect(screen.getByTestId('import-error-list')).toBeInTheDocument();
    });

    // Verify row 3 errors are displayed (both errors for row 3)
    const row3Errors = screen.getAllByTestId('import-error-row-3');
    expect(row3Errors).toHaveLength(2);
    expect(screen.getByText('اسم العائلة: حقل مطلوب ولا يمكن تركه فارغاً')).toBeInTheDocument();
    expect(screen.getByText('رقم الهوية (123): يجب أن يتكون من 10 أرقام')).toBeInTheDocument();
    expect(screen.getAllByText('الصف 3')).toHaveLength(2);
  });
});
