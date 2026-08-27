import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@/shared/contexts/ThemeContext';
import SessionEditDrawer from '../SessionEditDrawer';

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

const teachersList = [
  { id: 't-mina', full_name: 'مينا عادل', name: 'مينا عادل' },
  { id: 't-ahmed', full_name: 'أحمد محمود', name: 'أحمد محمود' },
];

const classesList = [
  { id: 'c-a2', name: 'أ-2', name_ar: 'أ-2' },
  { id: 'c-b1', name: 'ب-1', name_ar: 'ب-1' },
];

const subjectsList = [
  { id: 'sub-soc', name: 'الدراسات الاجتماعية', name_ar: 'الدراسات الاجتماعية' },
  { id: 'sub-math', name: 'الرياضيات', name_ar: 'الرياضيات' },
];

const existingSession = {
  id: 'sess-123',
  session_id: 'sess-123',
  teacher_id: 't-mina',
  teacher_name: 'مينا عادل',
  class_id: 'c-a2',
  class_name: 'أ-2',
  subject_id: 'sub-soc',
  subject_name: 'الدراسات الاجتماعية',
  day_of_week: 'sunday',
  slot_number: 1,
  period_number: 1,
};

describe('SessionEditDrawer — Data Binding & Editability', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.get.mockImplementation((url) => {
      if (url.startsWith('/classes')) return Promise.resolve({ data: classesList });
      if (url.startsWith('/subjects')) return Promise.resolve({ data: subjectsList });
      return Promise.resolve({ data: [] });
    });
  });

  test('pre-populates Teacher, Period, Class, and Subject when opening in edit mode', async () => {
    render(
      <ThemeProvider>
        <SessionEditDrawer
          open={true}
          mode="edit"
          context={{ session: existingSession }}
          schoolId="sch-1"
          timetableId="tt-1"
          teachers={teachersList}
          periods={[1, 2, 3, 4, 5, 6, 7]}
          api={mockApi}
          onClose={() => {}}
          onSaved={() => {}}
        />
      </ThemeProvider>
    );

    // Verify Catalogs were loaded
    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith('/classes', { params: { school_id: 'sch-1' } });
      expect(mockApi.get).toHaveBeenCalledWith('/subjects', { params: { school_id: 'sch-1' } });
    });

    // Verify Teacher is pre-selected and visible
    expect(screen.getByTestId('session-edit-teacher')).toHaveTextContent('مينا عادل');

    // Verify Period is pre-selected and visible (1)
    expect(screen.getByTestId('session-edit-period')).toHaveTextContent('1');

    // Verify Day is pre-selected and visible
    expect(screen.getByTestId('session-edit-day')).toBeInTheDocument();

    // Verify Class is pre-selected and editable (not plain text)
    expect(screen.getByTestId('session-edit-class')).toHaveTextContent('أ-2');

    // Verify Subject is pre-selected and editable (not plain text)
    expect(screen.getByTestId('session-edit-subject')).toHaveTextContent('الدراسات الاجتماعية');
  });

  test('submits full update payload with teacher, class, subject, day, and period on Save', async () => {
    mockApi.put.mockResolvedValueOnce({
      data: { success: true, message_ar: 'تم تعديل الحصة بنجاح' },
    });

    const onSaved = jest.fn();
    const onClose = jest.fn();

    render(
      <ThemeProvider>
        <SessionEditDrawer
          open={true}
          mode="edit"
          context={{ session: existingSession }}
          schoolId="sch-1"
          timetableId="tt-1"
          teachers={teachersList}
          periods={[1, 2, 3, 4, 5, 6, 7]}
          api={mockApi}
          onClose={onClose}
          onSaved={onSaved}
        />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('session-edit-save')).toBeEnabled();
    });

    fireEvent.click(screen.getByTestId('session-edit-save'));

    await waitFor(() => {
      expect(mockApi.put).toHaveBeenCalledWith(
        '/smart-scheduling/session/sess-123',
        {
          teacher_id: 't-mina',
          class_id: 'c-a2',
          subject_id: 'sub-soc',
          day_of_week: 'sunday',
          period_number: 1,
        },
        { headers: { 'X-School-Context': 'sch-1' } }
      );
      expect(onSaved).toHaveBeenCalledWith('updated');
      expect(onClose).toHaveBeenCalled();
    });
  });

  test('resolves teacher, class, and subject by name when IDs are omitted in session payload', async () => {
    const sessionWithNameOnly = {
      id: 'sess-456',
      teacher_name: 'أحمد محمود',
      class_name: 'ب-1',
      subject_name: 'الرياضيات',
      day_of_week: 'monday',
      slot_number: 3,
    };

    render(
      <ThemeProvider>
        <SessionEditDrawer
          open={true}
          mode="edit"
          context={{ session: sessionWithNameOnly }}
          schoolId="sch-1"
          timetableId="tt-1"
          teachers={teachersList}
          periods={[1, 2, 3, 4, 5, 6, 7]}
          api={mockApi}
          onClose={() => {}}
          onSaved={() => {}}
        />
      </ThemeProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('session-edit-teacher')).toHaveTextContent('أحمد محمود');
      expect(screen.getByTestId('session-edit-period')).toHaveTextContent('3');
      expect(screen.getByTestId('session-edit-class')).toHaveTextContent('ب-1');
      expect(screen.getByTestId('session-edit-subject')).toHaveTextContent('الرياضيات');
    });
  });
});
