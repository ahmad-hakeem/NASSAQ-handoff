import { fireEvent, render, screen } from '@testing-library/react';
import { DroppableTeacherBox } from './DndComponents';

jest.mock('@dnd-kit/core', () => ({
  useDroppable: () => ({ isOver: false, setNodeRef: jest.fn() }),
  useDraggable: () => ({
    attributes: {}, listeners: {}, setNodeRef: jest.fn(), transform: null, isDragging: false,
  }),
}));
jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

const teacher = { id: 'teacher-1', full_name: 'مينا محمد', email: 'mina@example.test' };

describe('DroppableTeacherBox bulk unassignment action', () => {
  it('shows an accessible clear action only when the teacher has assignments', () => {
    const onUnassignAll = jest.fn();
    const { rerender } = render(
      <DroppableTeacherBox
        teacher={teacher}
        assignments={[{ id: 'a1', class_name: 'الأول أ' }]}
        onRemoveAssignment={jest.fn()}
        onUnassignAll={onUnassignAll}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'إلغاء إسناد جميع الفصول عن المعلم مينا محمد' }));
    expect(onUnassignAll).toHaveBeenCalledWith(teacher);

    rerender(
      <DroppableTeacherBox
        teacher={teacher}
        assignments={[]}
        onRemoveAssignment={jest.fn()}
        onUnassignAll={onUnassignAll}
      />,
    );
    expect(screen.queryByRole('button', { name: /إلغاء إسناد جميع الفصول عن المعلم/ })).not.toBeInTheDocument();
  });

  it('disables bulk and individual delete actions during a bulk request', () => {
    render(
      <DroppableTeacherBox
        teacher={teacher}
        assignments={[{ id: 'a1', class_name: 'الأول أ' }]}
        onRemoveAssignment={jest.fn()}
        onUnassignAll={jest.fn()}
        actionsDisabled
      />,
    );

    expect(screen.getByTestId('unassign-all-teacher-teacher-1')).toBeDisabled();
    expect(screen.getByTitle('إلغاء الإسناد')).toBeDisabled();
  });
});