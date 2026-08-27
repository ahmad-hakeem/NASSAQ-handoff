import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
});
