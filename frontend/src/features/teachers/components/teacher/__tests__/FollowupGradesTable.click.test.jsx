import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

import FollowupGradesTable from '../FollowupGradesTable';

const COL = { id: 'c-part', name: 'المشاركة', group: 'coursework', maxGrade: 5 };
const STUDENTS = [
  { id: 's-1', full_name: 'Alpha Student' },
  { id: 's-2', full_name: 'Beta Student' },
];

function renderTable(props = {}) {
  return render(
    <FollowupGradesTable
      students={STUDENTS}
      columns={[COL]}
      gradesData={{ 's-1': { 'c-part': 2 } }}
      t={(k) => k}
      {...props}
    />,
  );
}

describe('FollowupGradesTable onStudentClick', () => {
  test('clicking the student name button opens the profile', () => {
    const onStudentClick = jest.fn();
    renderTable({ onStudentClick, onGradeChange: jest.fn() });

    fireEvent.click(screen.getByRole('button', { name: 'Alpha Student' }));

    expect(onStudentClick).toHaveBeenCalledTimes(1);
    expect(onStudentClick).toHaveBeenCalledWith(expect.objectContaining({ id: 's-1' }));
  });

  test('editing a grade input does NOT open the profile but still records the grade', () => {
    const onStudentClick = jest.fn();
    const onGradeChange = jest.fn();
    renderTable({ onStudentClick, onGradeChange });

    const input = screen.getAllByRole('spinbutton')[0]; // s-1 row
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: '4' } });

    expect(onStudentClick).not.toHaveBeenCalled();
    expect(onGradeChange).toHaveBeenCalledWith('s-1', 'c-part', 4);
  });

  test('without onStudentClick the name renders as plain text (no button)', () => {
    renderTable({ onGradeChange: jest.fn() });

    expect(screen.queryByRole('button', { name: 'Alpha Student' })).toBeNull();
    expect(screen.getByText('Alpha Student')).toBeInTheDocument();
  });
});
