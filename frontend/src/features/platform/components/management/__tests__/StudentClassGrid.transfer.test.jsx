/**
 * Task #799 — component-level coverage for the student class-transfer
 * drag-and-drop wiring on the page.
 *
 * The orchestrator (`executeStudentTransfer`) and the pure classifier are
 * already unit-tested. What had NO coverage was the actual on-page wiring that
 * shipped the production regression: the drag-start payload, the column drop
 * handler that calls `onTransfer`, the optimistic state update, the counter
 * refresh, and the failure path surfacing a clear (non-generic) message via the
 * existing NassaqAlertDialog error path.
 *
 * These tests render the real `StudentClassGrid` and, for the end-to-end cases,
 * a small harness that mirrors the page's `handleTransferStudent` /
 * `applyTransferSuccess` (UsersClassesManagement.jsx ~1223-1261) so the whole
 * chain is exercised without booting the heavy management page.
 */
import React, { useState, useCallback } from 'react';
import { render, screen, fireEvent, act, within, waitFor } from '@testing-library/react';
import { NassaqAlertProvider, useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { executeStudentTransfer } from '@/shared/models/utils/studentTransfer';
import StudentClassGrid from '../StudentClassGrid';

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false }),
  useTranslation: () => ({ t: (k) => k, isRTL: false }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

const { toast } = require('sonner');

const CLASSES = [
  { id: 'c1', name: 'Class One', name_ar: 'Class One', grade_level: 1 },
  { id: 'c2', name: 'Class Two', name_ar: 'Class Two', grade_level: 1 },
];

const STUDENTS = [
  { id: 's1', full_name: 'Alice Student', class_id: 'c1', student_number: '1001', is_active: true },
  { id: 's2', full_name: 'Bob Student', class_id: 'c2', student_number: '1002', is_active: true },
];

// A DataTransfer stand-in shared between dragStart and drop so the JSON payload
// set on drag-start is the one the drop handler reads back. jsdom does not
// implement DataTransfer, so fireEvent gets this object via the event init.
function createDataTransfer() {
  const store = {};
  return {
    setData: (type, value) => { store[type] = String(value); },
    getData: (type) => store[type] || '',
    dropEffect: 'move',
    effectAllowed: 'move',
  };
}

// The class column root (the element with the onDrop handler) is the closest
// rounded-2xl/border-2 ancestor of the column header heading. Resolved via text
// rather than the heading role because an open NassaqAlertDialog marks the
// background `aria-hidden`, which would hide role queries.
function columnRootByName(name) {
  const heading = screen.getByText(name, { selector: 'h3' });
  return heading.closest('.rounded-2xl');
}

function chipByName(name) {
  return screen.getByText(name).closest('[draggable="true"]');
}

function dragStudentToClass(studentName, targetClassName) {
  const dataTransfer = createDataTransfer();
  fireEvent.dragStart(chipByName(studentName), { dataTransfer });
  const target = columnRootByName(targetClassName);
  fireEvent.dragOver(target, { dataTransfer });
  fireEvent.drop(target, { dataTransfer });
}

describe('StudentClassGrid drag-and-drop wiring (Task #799)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('dropping a student on another class invokes onTransferStudent with the right ids', () => {
    const onTransferStudent = jest.fn();
    render(
      <StudentClassGrid
        students={STUDENTS}
        classes={CLASSES}
        isRTL={false}
        canDrag
        onView={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onAction={jest.fn()}
        onTransferStudent={onTransferStudent}
      />,
    );

    dragStudentToClass('Alice Student', 'Class Two');

    expect(onTransferStudent).toHaveBeenCalledTimes(1);
    expect(onTransferStudent).toHaveBeenCalledWith('s1', 'c2', 'Alice Student', 'Class Two');
  });

  test('dropping a student on its own class is a no-op (no transfer fired)', () => {
    const onTransferStudent = jest.fn();
    render(
      <StudentClassGrid
        students={STUDENTS}
        classes={CLASSES}
        isRTL={false}
        canDrag
        onView={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onAction={jest.fn()}
        onTransferStudent={onTransferStudent}
      />,
    );

    dragStudentToClass('Alice Student', 'Class One');

    expect(onTransferStudent).not.toHaveBeenCalled();
  });

  test('without canDrag, chips are not draggable and a drop fires no transfer', () => {
    const onTransferStudent = jest.fn();
    render(
      <StudentClassGrid
        students={STUDENTS}
        classes={CLASSES}
        isRTL={false}
        canDrag={false}
        onView={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onAction={jest.fn()}
        onTransferStudent={onTransferStudent}
      />,
    );

    expect(chipByName('Alice Student')).toBeNull();

    const dataTransfer = createDataTransfer();
    dataTransfer.setData('application/nassaq-student', JSON.stringify({ id: 's1', full_name: 'Alice Student', class_id: 'c1' }));
    fireEvent.drop(columnRootByName('Class Two'), { dataTransfer });

    expect(onTransferStudent).not.toHaveBeenCalled();
  });

  test.each([31, 50, 100, 300])('shows the actual Arabic roster count for %i students', (count) => {
    const students = Array.from({ length: count }, (_, index) => ({
      id: `count-${index + 1}`,
      full_name: `Count Student ${index + 1}`,
      class_id: 'count-class',
      student_number: String(index + 1),
      is_active: true,
    }));
    render(
      <StudentClassGrid
        students={students}
        classes={[{ id: 'count-class', name: 'Count Class', name_ar: 'Count Class', grade_level: 1 }]}
        isRTL
        canDrag={false}
        onView={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onAction={jest.fn()}
      />,
    );

    expect(columnRootByName('Count Class')).toHaveTextContent(`${count} طالب`);
  });

  test('bounds large class rosters and reveals every student in 50-student batches', () => {
    const manyStudents = Array.from({ length: 101 }, (_, index) => ({
      id: `large-${index + 1}`,
      full_name: `Student ${String(index + 1).padStart(3, '0')}`,
      class_id: 'large-class',
      student_number: String(index + 1),
      is_active: true,
    }));
    render(
      <StudentClassGrid
        students={manyStudents}
        classes={[{ id: 'large-class', name: 'Large Class', name_ar: 'Large Class', grade_level: 1 }]}
        isRTL={false}
        canDrag={false}
        onView={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onAction={jest.fn()}
      />,
    );

    expect(columnRootByName('Large Class')).toHaveTextContent('101 studentsLower');
    expect(screen.queryByText('Student 101')).toBeNull();
    const showMore = screen.getByTestId('show-more-students-large-class');
    fireEvent.click(showMore);
    expect(screen.queryByText('Student 101')).toBeNull();
    fireEvent.click(screen.getByTestId('show-more-students-large-class'));
    expect(screen.getByText('Student 101')).toBeInTheDocument();
    expect(screen.queryByTestId('show-more-students-large-class')).toBeNull();
  });

  test('bulk assignment remains available for a target whose existing roster is large', async () => {
    const onBulkAssign = jest.fn().mockResolvedValue(true);
    render(
      <StudentClassGrid
        students={STUDENTS}
        classes={[
          { ...CLASSES[0], capacity: 1, student_count: 1 },
          { ...CLASSES[1], capacity: 1, student_count: 1 },
        ]}
        isRTL={false}
        canDrag={false}
        onView={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        onAction={jest.fn()}
        onBulkAssign={onBulkAssign}
      />,
    );

    fireEvent.click(screen.getByTestId('select-student-s1'));
    const target = screen.getByLabelText('Select class');
    expect(within(target).getByRole('option', { name: /Class Two/ })).not.toBeDisabled();
    fireEvent.change(target, { target: { value: 'c2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Assign to class' }));

    await waitFor(() => {
      expect(onBulkAssign).toHaveBeenCalledWith(['s1'], 'c2');
    });
  });
});

// ---- End-to-end wiring: drag -> executeStudentTransfer -> optimistic update ----

// Mirrors UsersClassesManagement's handleTransferStudent / applyTransferSuccess
// so the full page wiring (state move + counter refresh + error surfacing) is
// covered against the real StudentClassGrid and the real orchestrator.
function PageHarness({ api, refetchClasses }) {
  const { nassaqError } = useNassaqAlert();
  const [students, setStudents] = useState(STUDENTS);
  const [classes, setClasses] = useState([
    { ...CLASSES[0], current_students: 1 },
    { ...CLASSES[1], current_students: 1 },
  ]);

  const applyTransferSuccess = useCallback((studentId, targetClassId, studentName, className, outcome) => {
    const movingStudent = students.find((s) => s.id === studentId);
    const oldClassId = outcome.oldClassId || movingStudent?.class_id;
    setStudents((prev) => prev.map((s) => (s.id === studentId ? { ...s, class_id: targetClassId, class_name: className } : s)));
    setClasses((prev) => prev.map((c) => {
      if (c.id === targetClassId && outcome.targetCount != null) {
        return { ...c, current_students: outcome.targetCount };
      }
      if (oldClassId && c.id === oldClassId && outcome.oldCount != null) {
        return { ...c, current_students: outcome.oldCount };
      }
      return c;
    }));
    refetchClasses();
  }, [students, refetchClasses]);

  const handleTransferStudent = useCallback((studentId, targetClassId, studentName, className) => (
    executeStudentTransfer({
      api,
      studentId,
      targetClassId,
      messages: {
        transferred: `moved ${studentName} -> ${className}`,
        serverError: 'TRANSFER_SERVER_ERROR',
        network: 'NETWORK_ERROR_RETRY',
      },
      onToast: (msg) => toast.success(msg),
      onSuccess: (outcome) => applyTransferSuccess(studentId, targetClassId, studentName, className, outcome),
      onError: (msg) => nassaqError(msg),
      sleep: () => Promise.resolve(),
    })
  ), [api, applyTransferSuccess, nassaqError]);

  return (
    <StudentClassGrid
      students={students}
      classes={classes}
      isRTL={false}
      canDrag
      onView={jest.fn()}
      onEdit={jest.fn()}
      onDelete={jest.fn()}
      onAction={jest.fn()}
      onTransferStudent={handleTransferStudent}
    />
  );
}

function countBadgeFor(className) {
  // The column header renders the student count both as a label and a badge;
  // assert on the "N studentsLower" label which is unambiguous per column.
  return columnRootByName(className).textContent;
}

describe('StudentClassGrid + page wiring end-to-end (Task #799)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('successful drop optimistically moves the student and refreshes the counters', async () => {
    const api = {
      post: jest.fn().mockResolvedValue({
        data: { success: true, old_class_id: 'c1', old_class_current_students: 0, target_class_current_students: 2 },
      }),
    };
    const refetchClasses = jest.fn();

    render(
      <NassaqAlertProvider>
        <PageHarness api={api} refetchClasses={refetchClasses} />
      </NassaqAlertProvider>,
    );

    // Before: Alice is under Class One.
    expect(within(columnRootByName('Class One')).getByText('Alice Student')).toBeInTheDocument();
    expect(countBadgeFor('Class One')).toMatch(/1 studentsLower/);
    expect(countBadgeFor('Class Two')).toMatch(/1 studentsLower/);

    await act(async () => {
      dragStudentToClass('Alice Student', 'Class Two');
    });

    // The orchestrator hit the real endpoint with the right payload.
    expect(api.post).toHaveBeenCalledWith(
      '/students/transfer-class',
      { student_id: 's1', target_class_id: 'c2' },
      expect.any(Object),
    );

    // Optimistic move: Alice now lives under Class Two.
    await waitFor(() => {
      expect(within(columnRootByName('Class Two')).getByText('Alice Student')).toBeInTheDocument();
    });
    expect(within(columnRootByName('Class One')).queryByText('Alice Student')).toBeNull();

    // Counters refreshed from the server-provided counts.
    expect(countBadgeFor('Class One')).toMatch(/0 studentsLower/);
    expect(countBadgeFor('Class Two')).toMatch(/2 studentsLower/);

    // Success toast shown; the re-derive refetch fired.
    expect(toast.success).toHaveBeenCalledWith('moved Alice Student -> Class Two');
    expect(refetchClasses).toHaveBeenCalledTimes(1);
  });

  test('a rejected transfer surfaces the backend message and rolls back cleanly (student stays put)', async () => {
    const api = {
      post: jest.fn().mockRejectedValue({
        response: { status: 409, data: { success: false, error: { message: 'الفصل ممتلئ' } } },
      }),
    };
    const refetchClasses = jest.fn();

    render(
      <NassaqAlertProvider>
        <PageHarness api={api} refetchClasses={refetchClasses} />
      </NassaqAlertProvider>,
    );

    await act(async () => {
      dragStudentToClass('Alice Student', 'Class Two');
    });

    // The specific backend cause is shown in the NassaqAlertDialog — never a
    // generic cause-hiding fallback.
    const dialog = await screen.findByTestId('nassaq-alert-dialog');
    expect(within(dialog).getByText('الفصل ممتلئ')).toBeInTheDocument();

    // No optimistic move happened: Alice is still under Class One, counts intact.
    expect(within(columnRootByName('Class One')).getByText('Alice Student')).toBeInTheDocument();
    expect(within(columnRootByName('Class Two')).queryByText('Alice Student')).toBeNull();
    expect(countBadgeFor('Class One')).toMatch(/1 studentsLower/);
    expect(countBadgeFor('Class Two')).toMatch(/1 studentsLower/);

    expect(toast.success).not.toHaveBeenCalled();
    expect(refetchClasses).not.toHaveBeenCalled();
  });
});
