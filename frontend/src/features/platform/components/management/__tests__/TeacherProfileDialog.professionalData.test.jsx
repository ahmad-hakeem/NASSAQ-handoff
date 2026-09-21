import React from 'react';
import { act, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@/shared/contexts/ThemeContext';
import TeacherProfileDialog from '../TeacherProfileDialog';

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const mockNassaqError = jest.fn();
const mockNassaqConfirm = jest.fn();

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: mockNassaqError,
    nassaqConfirm: mockNassaqConfirm,
    nassaqWarning: jest.fn(),
    nassaqInfo: jest.fn(),
  }),
}));

const mockApi = {
  get: jest.fn(),
  put: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
};

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockApi }),
}));

const clickRadixTab = (tabElement) => {
  fireEvent.pointerDown(tabElement, { ctrlKey: false, button: 0 });
  fireEvent.mouseDown(tabElement, { button: 0 });
  fireEvent.focus(tabElement);
  fireEvent.click(tabElement);
  fireEvent.keyDown(tabElement, { key: ' ', code: 'Space' });
};

describe('TeacherProfileDialog — Professional Data Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('accurately fetches and renders Rank, Degree, Contract, and Experience in the Professional tab', async () => {
    const teacherProp = {
      id: 't-ahmed-123',
      full_name: 'احمد المعلم',
      email: 'ahmed@school.com',
      rank: 'teacher',
      qualification: 'bachelor',
      contract_type: 'permanent',
      specialization: 'رياضيات',
      years_of_experience: 3,
    };

    const mockProfileResponse = {
      profile: {
        basic_info: {
          full_name: 'احمد المعلم',
          email: 'ahmed@school.com',
        },
        professional_info: {
          specialization: 'رياضيات',
          academic_degree: 'bachelor',
          teacher_rank: 'teacher',
          years_of_experience: 3,
          contract_type: 'permanent',
          employee_number: 'EMP-9081',
        },
        operational_info: {
          status: 'active',
          max_periods_per_week: 24,
          total_sessions: 0,
        },
        assignments: [],
      },
    };

    mockApi.get.mockResolvedValueOnce({ data: mockProfileResponse });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={teacherProp}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith('/principal/teacher/t-ahmed-123/full-profile');
    });

    const professionalTabBtn = await screen.findByRole('tab', { name: /المهني|career/i });
    clickRadixTab(professionalTabBtn);

    await waitFor(() => {
      // Specialization: رياضيات
      expect(screen.getAllByText('رياضيات').length).toBeGreaterThan(0);
      // Degree: بكالوريوس
      expect(screen.getByText('بكالوريوس')).toBeInTheDocument();
      // Rank: معلم
      expect(screen.getAllByText('معلم').length).toBeGreaterThan(0);
      // Experience: 3 سنة
      expect(screen.getByText(/3/)).toBeInTheDocument();
      // Contract: دائم
      expect(screen.getByText('دائم')).toBeInTheDocument();
      // Employee Number: EMP-9081
      expect(screen.getByText('EMP-9081')).toBeInTheDocument();
    });
  });

  test('falls back gracefully to legacy teacher object properties when profile fields use aliases', async () => {
    const teacherWithLegacyFields = {
      id: 't-legacy-456',
      full_name: 'سارة الفاضل',
      rank: 'معلم ممارس',
      qualification: 'بكالوريوس تربوي',
      contract_type: 'عقد',
      specialization: 'علوم',
      years_of_experience: 5,
    };

    mockApi.get.mockResolvedValueOnce({
      data: {
        profile: {
          basic_info: { full_name: 'سارة الفاضل' },
          professional_info: {},
          operational_info: { status: 'active' },
        },
      },
    });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={teacherWithLegacyFields}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith('/principal/teacher/t-legacy-456/full-profile');
    });

    const professionalTabBtn = await screen.findByRole('tab', { name: /المهني|career/i });
    clickRadixTab(professionalTabBtn);

    await waitFor(() => {
      expect(screen.getByText('بكالوريوس تربوي')).toBeInTheDocument();
      expect(screen.getAllByText('معلم ممارس').length).toBeGreaterThan(0);
      expect(screen.getByText('عقد')).toBeInTheDocument();
      expect(screen.getByText(/5/)).toBeInTheDocument();
    });
  });

  test('preserves an explicit zero years of experience when saving professional data', async () => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        profile: {
          basic_info: { full_name: 'معلم بلا خبرة' },
          professional_info: {
            academic_degree: null,
            teacher_rank: null,
            years_of_experience: 0,
            contract_type: 'permanent',
          },
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValueOnce({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-zero', full_name: 'معلم بلا خبرة' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    const professionalTab = await screen.findByRole('tab', { name: /المهني|career/i });
    clickRadixTab(professionalTab);
    const editButton = await screen.findByTestId('edit-professional');
    fireEvent.click(editButton);
    const experience = await screen.findByRole('spinbutton');
    fireEvent.change(experience, { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));

    await waitFor(() => expect(mockApi.put).toHaveBeenCalledWith(
      '/principal/teacher/t-zero/professional-info',
      expect.objectContaining({ years_of_experience: 0 })
    ));
  });

  test('sends null when degree, rank, and experience are cleared', async () => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        profile: {
          basic_info: { full_name: 'معلم' },
          professional_info: {
            academic_degree: 'bachelor',
            teacher_rank: 'teacher',
            years_of_experience: 4,
            contract_type: 'permanent',
          },
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValueOnce({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-clear', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    const professionalTab = await screen.findByRole('tab', { name: /المهني|career/i });
    clickRadixTab(professionalTab);
    await screen.findByTestId('edit-professional');
    fireEvent.click(screen.getByTestId('edit-professional'));
    fireEvent.click(screen.getByTestId('clear-degree'));
    fireEvent.click(screen.getByTestId('clear-rank'));
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));

    await waitFor(() => expect(mockApi.put).toHaveBeenCalledWith(
      '/principal/teacher/t-clear/professional-info',
      expect.objectContaining({
        academic_degree: null,
        teacher_rank: null,
        years_of_experience: null,
      })
    ));
  });

  test('treats present null professional fields as authoritative over stale teacher props', async () => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        profile: {
          basic_info: { full_name: 'معلم' },
          professional_info: {
            academic_degree: null,
            teacher_rank: null,
            years_of_experience: null,
            contract_type: 'permanent',
          },
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValueOnce({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{
            id: 't-authoritative-null',
            full_name: 'معلم',
            qualification: 'bachelor',
            rank: 'teacher',
            years_of_experience: 9,
          }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    const professionalTab = await screen.findByRole('tab', { name: /المهني|career/i });
    clickRadixTab(professionalTab);
    await waitFor(() => {
      expect(screen.queryByText('بكالوريوس')).not.toBeInTheDocument();
      expect(screen.queryByText(/9/)).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('edit-professional'));
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    await waitFor(() => expect(mockApi.put).toHaveBeenCalledWith(
      '/principal/teacher/t-authoritative-null/professional-info',
      expect.objectContaining({
        academic_degree: null,
        teacher_rank: null,
        years_of_experience: null,
      })
    ));
  });

  test.each(['1.5', '-1'])('rejects invalid experience value %s without PUT', async (value) => {
    mockApi.get.mockResolvedValueOnce({
      data: {
        profile: {
          basic_info: { full_name: 'معلم' },
          professional_info: { years_of_experience: 4, contract_type: 'permanent' },
          operational_info: { status: 'active' },
        },
      },
    });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: `t-invalid-${value}`, full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );
    clickRadixTab(await screen.findByRole('tab', { name: /المهني|career/i }));
    fireEvent.click(await screen.findByTestId('edit-professional'));
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));

    expect(await screen.findByText(/يجب أن تكون الخبرة|Experience must be/)).toBeInTheDocument();
    expect(mockApi.put).not.toHaveBeenCalled();
  });

  test('renders both birth-date calendars and saves only the Gregorian value', async () => {
    const profile = {
      basic_info: {
        full_name: 'معلم',
        date_of_birth: '2024-03-11',
      },
      contact_info: {},
      professional_info: {},
      operational_info: { status: 'active' },
    };
    mockApi.get.mockResolvedValue({ data: { profile } });
    mockApi.put.mockResolvedValue({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-dob', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    expect(await screen.findByText('2024-03-11')).toBeInTheDocument();
    expect(screen.getByText(/١٤٤٥-٠٩-٠١ هـ/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /تعديل|edit/i }));
    fireEvent.change(screen.getByTestId('profile-teacher-dob'), { target: { value: '2000-01-01' } });
    expect(screen.getByTestId('profile-teacher-dob-hijri')).toHaveValue('24/09/1420');
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));

    await waitFor(() => expect(mockApi.put).toHaveBeenCalledWith(
      '/principal/teacher/t-dob/basic-info',
      expect.objectContaining({ date_of_birth: '2000-01-01' })
    ));
    expect(mockApi.put.mock.calls[0][1]).not.toHaveProperty('hijri_date_of_birth');
  });

  test('clears a birth date as null and blocks a future value', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        profile: {
          basic_info: { full_name: 'معلم', date_of_birth: '2024-03-11' },
          contact_info: {},
          professional_info: {},
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValue({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-clear-dob', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );
    await screen.findByText('2024-03-11');
    fireEvent.click(screen.getByRole('button', { name: /تعديل|edit/i }));
    fireEvent.change(screen.getByTestId('profile-teacher-dob'), { target: { value: '2999-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/المستقبل|future/i);
    expect(mockApi.put).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId('profile-teacher-dob'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    await waitFor(() => expect(mockApi.put).toHaveBeenCalledWith(
      '/principal/teacher/t-clear-dob/basic-info',
      expect.objectContaining({ date_of_birth: null })
    ));
  });

  test('allows unrelated edits with a legacy DOB by omitting it until explicitly changed', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        profile: {
          basic_info: { full_name: 'معلم', date_of_birth: 'legacy-date' },
          contact_info: { phone: '0500000000' },
          professional_info: {},
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValue({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-legacy-dob', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );

    expect(await screen.findByText('legacy-date')).toBeInTheDocument();
    expect(screen.getByText(/تاريخ ميلادي مخزن غير صالح|Invalid stored Gregorian date/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /تعديل|edit/i }));
    expect(screen.getByText('legacy-date')).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue('0500000000'), { target: { value: '0511111111' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));

    await waitFor(() => expect(mockApi.put).toHaveBeenCalled());
    expect(mockApi.put.mock.calls[0][1]).toMatchObject({ phone: '0511111111' });
    expect(mockApi.put.mock.calls[0][1]).not.toHaveProperty('date_of_birth');
  });

  test('blocks an explicit invalid DOB replacement after a legacy value', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        profile: {
          basic_info: { full_name: 'معلم', date_of_birth: 'legacy-date' },
          contact_info: {},
          professional_info: {},
          operational_info: { status: 'active' },
        },
      },
    });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-replace-legacy-dob', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );
    await screen.findByText('legacy-date');
    fireEvent.click(screen.getByRole('button', { name: /تعديل|edit/i }));
    fireEvent.change(screen.getByTestId('profile-teacher-dob'), { target: { value: '2999-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/المستقبل|future/i);
    expect(mockApi.put).not.toHaveBeenCalled();
  });

  test('explicitly clears a legacy DOB as null', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        profile: {
          basic_info: { full_name: 'معلم', date_of_birth: 'legacy-date' },
          contact_info: {},
          professional_info: {},
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValue({ data: { success: true } });

    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-clear-legacy-dob', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );
    await screen.findByText('legacy-date');
    fireEvent.click(screen.getByRole('button', { name: /تعديل|edit/i }));
    fireEvent.click(screen.getByTestId('profile-teacher-dob-clear-legacy'));
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    await waitFor(() => expect(mockApi.put).toHaveBeenCalledWith(
      '/principal/teacher/t-clear-legacy-dob/basic-info',
      expect.objectContaining({ date_of_birth: null })
    ));
  });

  test('blocks an incomplete Hijri edit and saves a valid Hijri edit as Gregorian only', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        profile: {
          basic_info: { full_name: 'معلم', date_of_birth: '2024-03-11' },
          contact_info: {},
          professional_info: {},
          operational_info: { status: 'active' },
        },
      },
    });
    mockApi.put.mockResolvedValue({ data: { success: true } });
    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={() => {}}
          teacher={{ id: 't-edit-hijri', full_name: 'معلم' }}
          onRefresh={() => {}}
        />
      </ThemeProvider>
    );
    await screen.findByText('2024-03-11');
    fireEvent.click(screen.getByRole('button', { name: /تعديل|edit/i }));
    fireEvent.change(screen.getByTestId('profile-teacher-dob-hijri'), { target: { value: '31/09/' } });
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    expect(mockApi.put).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(/هجري|Hijri/i);

    fireEvent.change(screen.getByTestId('profile-teacher-dob-hijri'), { target: { value: '01/06/1446' } });
    expect(screen.getByTestId('profile-teacher-dob')).toHaveValue('2024-12-02');
    fireEvent.click(screen.getByRole('button', { name: /حفظ|save/i }));
    await waitFor(() => expect(mockApi.put).toHaveBeenCalled());
    expect(mockApi.put.mock.calls[0][1].date_of_birth).toBe('2024-12-02');
    expect(mockApi.put.mock.calls[0][1]).not.toHaveProperty('birth_date_hijri');
  });
});

describe('TeacherProfileDialog — permanent deletion', () => {
  const profileResponse = {
    data: {
      profile: {
        basic_info: { full_name: 'معلم للحذف', status: 'active' },
        professional_info: {},
        operational_info: {},
        assignments: [],
      },
    },
  };

  const renderDeletionDialog = (props = {}) => {
    const onRefresh = props.onRefresh || jest.fn();
    const onClose = props.onClose || jest.fn();
    render(
      <ThemeProvider>
        <TeacherProfileDialog
          open={true}
          onClose={onClose}
          teacher={{ id: 'delete-teacher-1', full_name: 'معلم للحذف' }}
          onRefresh={onRefresh}
        />
      </ThemeProvider>
    );
    return { onRefresh, onClose };
  };

  const openDeleteConfirmation = async () => {
    clickRadixTab(await screen.findByRole('tab', { name: /إجراءات|actions/i }));
    fireEvent.click(await screen.findByRole('button', { name: /حذف المعلم نهائياً|delete teacher permanently/i }));
    return screen.getAllByRole('button', { name: /حذف المعلم نهائياً/ }).at(-1);
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.get.mockResolvedValue(profileResponse);
  });

  test('confirms permanent deletion, prevents duplicate submission, and refreshes before closing', async () => {
    let resolveDelete;
    const onRefresh = jest.fn().mockResolvedValue(undefined);
    const onClose = jest.fn();
    mockApi.delete.mockReturnValue(new Promise(resolve => { resolveDelete = resolve; }));
    renderDeletionDialog({ onRefresh, onClose });
    const confirm = await openDeleteConfirmation();

    expect(screen.getByText(/تحرير البريد الإلكتروني ورقم الهاتف والهوية/)).toBeInTheDocument();
    expect(screen.getByText(/السجلات التعليمية والتاريخية السابقة محفوظة/)).toBeInTheDocument();
    expect(screen.queryByText(/ارتباطات مشتركة أو غير مؤكدة/)).not.toBeInTheDocument();

    let firstSubmission;
    await act(async () => {
      fireEvent.click(confirm);
      firstSubmission = Promise.resolve();
      fireEvent.click(confirm);
    });
    expect(mockApi.delete).toHaveBeenCalledTimes(1);
    expect(mockApi.delete).toHaveBeenCalledWith('/teachers/delete-teacher-1');
    expect(onRefresh).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveDelete({ data: { success: true } });
      await firstSubmission;
    });
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  test('persists safe structured 409 dependency details and resolution without PII', async () => {
    mockApi.delete.mockRejectedValue({
      response: {
        status: 409,
        data: {
          error: {
            code: 'DELETE_DEPENDENCY_BLOCKED',
            message: 'يجب إزالة التكليف النشط أولاً.',
            detail: {
              dependencies: [{
                reason: 'active_assignment',
                category: 'school_owned',
                table: 'teacher_assignments',
                count: 2,
                resolution: 'أزل التكليف النشط ثم أعد المحاولة.',
                email: 'must-not-render@example.com',
              }],
            },
          },
        },
      },
    });

    const { onRefresh, onClose } = renderDeletionDialog();
    fireEvent.click(await openDeleteConfirmation());

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('تعذر حذف حساب المعلم لوجود ارتباطات مانعة');
    expect(alert).toHaveTextContent('DELETE_DEPENDENCY_BLOCKED');
    expect(alert).toHaveTextContent('active_assignment');
    expect(alert).toHaveTextContent('أزل التكليف النشط ثم أعد المحاولة.');
    expect(alert).not.toHaveTextContent('must-not-render@example.com');
    expect(onRefresh).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  test.each([
    [403, 'لا تملك صلاحية حذف حساب هذا المعلم.'],
    [500, 'تعذر حذف حساب المعلم. لم يُحذف أي شيء؛ حاول مرة أخرى.'],
  ])('persists the safe fallback for an unstructured HTTP %s response', async (status, message) => {
    mockApi.delete.mockRejectedValue({ response: { status, data: {} } });
    renderDeletionDialog();
    fireEvent.click(await openDeleteConfirmation());
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  test('clears a previous deletion failure when confirmation is dismissed and reopened', async () => {
    mockApi.delete.mockRejectedValue({ response: { status: 403, data: {} } });
    renderDeletionDialog();
    fireEvent.click(await openDeleteConfirmation());
    expect(await screen.findByRole('alert')).toHaveTextContent('لا تملك صلاحية');

    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: /حذف المعلم نهائياً|delete teacher permanently/i }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
