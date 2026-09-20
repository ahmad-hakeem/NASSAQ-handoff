import { fireEvent, render, screen } from '@testing-library/react';
import { DynamicSettingsContent } from './DynamicSettingsContent';

jest.mock('@/shared/components/ui/tabs', () => {
  const React = require('react');
  const TabContext = React.createContext('');
  return {
    Tabs: ({ value, children }) => <TabContext.Provider value={value}>{children}</TabContext.Provider>,
    TabsContent: ({ value, children }) => (
      React.useContext(TabContext) === value ? <div>{children}</div> : null
    ),
    TabsList: ({ children }) => <div>{children}</div>,
    TabsTrigger: ({ children }) => <button type="button">{children}</button>,
  };
});
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, direction: 'rtl' }),
  useTranslation: () => ({ t: key => key }),
}));
jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

function makeHook(classAssignments) {
  return {
    activeTab: 'teacher-assignments',
    setActiveTab: jest.fn(),
    sensors: [],
    schoolInfo: {},
    teachers: [
      { id: 't1', full_name: 'مينا محمد', email: 'mina@example.test' },
      { id: 't2', full_name: 'حكيم أحمد', email: 'hakim@example.test' },
    ],
    classes: [
      { id: 'c1', name: 'الأول أ' },
      { id: 'c2', name: 'الثاني أ' },
    ],
    assignments: [],
    subjects: [],
    editedSchoolInfo: {},
    setEditedSchoolInfo: jest.fn(),
    workDays: {},
    timingSettings: {},
    breakTimes: [],
    teacherUnavailability: [],
    classUnavailability: [],
    hardConstraints: [],
    softConstraints: [],
    customSoftConstraints: [],
    constraintPatterns: [],
    otherDuties: [],
    workloadSummary: [],
    dynamicTabs: [],
    assignmentSubTab: 'classes',
    setAssignmentSubTab: jest.fn(),
    classAssignments,
    classAssignmentsLoaded: true,
    classAssignmentsLoading: false,
    classAssignmentsError: false,
    classAssignmentsBulkLoading: false,
    setDraggingClass: jest.fn(),
    loadClassAssignments: jest.fn(),
    handleCreateClassAssignment: jest.fn(),
    handleDeleteClassAssignment: jest.fn(),
    unassignAllClassesForTeacher: jest.fn().mockResolvedValue(true),
    unassignAllClassAssignments: jest.fn().mockResolvedValue(true),
    handleOpenNoorImport: jest.fn(),
    nassaqWarning: jest.fn(),
    dynamicTabs: [],
  };
}

describe('teacher assignment bulk controls', () => {
  it('disables the global destructive outline action when there are no assignments', () => {
    render(
      <DynamicSettingsContent
        hook={makeHook([])}
        dynamicTabs={[{ id: 'teacher-assignments', label: 'إسناد المعلمين', icon: () => null }]}
      />,
    );

    expect(screen.getByTestId('unassign-all-class-assignments')).toBeDisabled();
    expect(screen.queryByTestId('unassign-all-teacher-t1')).not.toBeInTheDocument();
  });

  it('shows Arabic teacher and global safety confirmations', () => {
    const assignments = [
      { id: 'a1', teacher_id: 't1', class_id: 'c1', class_name: 'الأول أ' },
      { id: 'a2', teacher_id: 't1', class_id: 'c2', class_name: 'الثاني أ' },
    ];
    render(
      <DynamicSettingsContent
        hook={makeHook(assignments)}
        dynamicTabs={[{ id: 'teacher-assignments', label: 'إسناد المعلمين', icon: () => null }]}
      />,
    );

    fireEvent.click(screen.getByTestId('unassign-all-teacher-t1'));
    expect(screen.getByText('هل أنت متأكد من إلغاء إسناد جميع الفصول (2) عن المعلم مينا محمد؟')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));

    fireEvent.click(screen.getByTestId('unassign-all-class-assignments'));
    expect(screen.getByRole('heading', { name: 'إلغاء إسناد كافة الفصول' })).toBeInTheDocument();
    expect(screen.getByText(/لن يتم حذف الفصول أو المعلمين/)).toBeInTheDocument();
  });
});