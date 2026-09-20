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
  toast: { success: jest.fn(), error: jest.fn(), warning: jest.fn() },
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

import UsersClassesManagement, {
  getBulkImportStatus,
} from '../pages/UsersClassesManagement';

async function confirmPreview() {
  fireEvent.click(screen.getByText('معاينة الملف'));
  await screen.findByText('معاينة فقط — لم تُحفظ أي بيانات بعد');
  fireEvent.click(screen.getByLabelText('راجعت المعاينة وأؤكد إنشاء أو تحديث السجلات والعلاقات المعروضة.'));
  fireEvent.click(screen.getByText('تأكيد الاستيراد'));
}

describe('UsersClassesManagement — Bulk Import Error Logs Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams.delete('import_type');
    mockApiPost.mockReset();
    mockApiPost.mockResolvedValueOnce({ data: {
      draft_id: 'review-1', fingerprint: 'file-hash', preview_version: 1,
      import_type: 'students', can_confirm: true, rows: [], errors: [], warnings: [], summary: {},
    } });
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
      expect(screen.getByText('معاينة الملف')).toBeInTheDocument();
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

    // Review and explicitly confirm before actual server results are displayed.
    await confirmPreview();

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

  test('shows distinct student counters and never reports an assignment gap as fully successful', async () => {
    render(<UsersClassesManagement initialTab="import-export" />);

    await waitFor(() => {
      expect(screen.getByText('معاينة الملف')).toBeInTheDocument();
    });

    mockApiPost.mockResolvedValueOnce({
      data: {
        success: true,
        total_rows: 2,
        imported: 2,
        failed: 0,
        created: 1,
        updated: 1,
        restored: 0,
        assigned: 1,
        classes_created: 1,
        parents_created: 2,
        skipped: 0,
        errors: [],
        warnings: [{ row: 4, message: 'الفصل ممتلئ؛ تعذر إسناد الطالب' }],
      },
    });

    const file = new File(['dummy content'], 'students_test.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [file] } });
    await confirmPreview();

    await waitFor(() => {
      expect(screen.getByTestId('import-status-partial')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('import-status-success')).not.toBeInTheDocument();
    expect(screen.getByTestId('import-metric-created')).toHaveTextContent('1');
    expect(screen.getByTestId('import-metric-updated')).toHaveTextContent('1');
    expect(screen.getByTestId('import-metric-assigned')).toHaveTextContent('1');
    expect(screen.getByTestId('import-metric-classes_created')).toHaveTextContent('1');
    expect(screen.getByTestId('import-metric-parents_created')).toHaveTextContent('2');
    expect(screen.getByTestId('import-warning-row-4')).toHaveTextContent('الفصل ممتلئ؛ تعذر إسناد الطالب');
  });

  test('shows reused parents and linked students when no new parents were created', async () => {
    render(<UsersClassesManagement initialTab="import-export" />);

    await waitFor(() => {
      expect(screen.getByText('معاينة الملف')).toBeInTheDocument();
    });

    mockApiPost.mockResolvedValueOnce({
      data: {
        success: true,
        total_rows: 10,
        imported: 10,
        failed: 0,
        created: 10,
        updated: 0,
        restored: 0,
        assigned: 10,
        classes_created: 0,
        classes_reused: 3,
        parents_created: 0,
        parents_reused: 9,
        students_linked_to_parents: 10,
        grades_created: 0,
        grades_reused: 10,
        skipped: 0,
        errors: [],
        warnings: [],
      },
    });

    const file = new File(['workbook'], 'workbook10students.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    fireEvent.change(document.querySelector('input[type="file"]'), { target: { files: [file] } });
    await confirmPreview();

    await waitFor(() => {
      expect(screen.getByTestId('import-status-success')).toBeInTheDocument();
    });
    expect(screen.getByTestId('import-metric-parents_created')).toHaveTextContent('0');
    expect(screen.getByTestId('import-metric-parents_reused')).toHaveTextContent('9');
    expect(screen.getByTestId('import-metric-students_linked_to_parents')).toHaveTextContent('10');
    expect(screen.getByTestId('import-metric-grades_created')).toHaveTextContent('0');
    expect(screen.getByTestId('import-metric-grades_reused')).toHaveTextContent('10');
  });

  test('requires every student parent link when the new link counter is present', () => {
    expect(getBulkImportStatus({
      success: true,
      imported: 10,
      assigned: 10,
      students_linked_to_parents: 9,
    }, 'students')).toBe('partial');
    expect(getBulkImportStatus({
      success: true,
      imported: 10,
      assigned: 10,
    }, 'students')).toBe('success');
  });

  test('settings teacher deep link opens the teacher external review mode', async () => {
    mockSearchParams.set('import_type', 'teachers');
    render(<UsersClassesManagement />);
    await screen.findByText('معاينة الملف');
    expect(screen.getByRole('button', { name: 'المعلمون' })).toHaveClass('border-brand-turquoise');
    fireEvent.change(document.querySelector('input[type="file"]'), {
      target: { files: [new File(['data'], 'teachers.csv')] },
    });
    fireEvent.click(screen.getByText('معاينة الملف'));
    await waitFor(() => expect(mockApiPost).toHaveBeenCalledWith('/bulk/preview/teachers', expect.any(FormData), expect.anything()));
  });

  test('keeps teacher imports on the legacy success semantics', () => {
    expect(getBulkImportStatus({
      success: true,
      total_rows: 2,
      imported: 2,
      failed: 0,
    }, 'teachers')).toBe('success');
  });
});
