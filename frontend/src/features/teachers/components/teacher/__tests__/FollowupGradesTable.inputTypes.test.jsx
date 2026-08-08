import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

import FollowupGradesTable from '../FollowupGradesTable';

const GRADE_COL = { id: 'c-grade', name: 'نشاط', group: 'coursework', maxGrade: 10, type: 'grade' };
const CHECK_COL = { id: 'c-check', name: 'أحضر الكتاب', group: 'coursework', maxGrade: 10, type: 'check' };
const TEXT_COL = { id: 'c-text', name: 'ملاحظة', group: 'coursework', maxGrade: 10, type: 'text' };

const STUDENT = { id: 's-1', full_name: 'طالب اختبار' };

function Harness({ columns, initialData }) {
  const [data, setData] = useState(initialData || {});
  const onGradeChange = (sid, cid, value) => {
    setData((prev) => ({ ...prev, [sid]: { ...(prev[sid] || {}), [cid]: value } }));
  };
  return (
    <FollowupGradesTable
      students={[STUDENT]}
      columns={columns}
      gradesData={data}
      onGradeChange={onGradeChange}
      t={(k) => k}
    />
  );
}

describe('FollowupGradesTable input types (درجة/تحقق/نص)', () => {
  test('check column renders a checkbox that toggles 1/empty', () => {
    render(<Harness columns={[CHECK_COL]} />);
    const box = screen.getByRole('checkbox');
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    expect(box.checked).toBe(true);
    fireEvent.click(box);
    expect(box.checked).toBe(false);
  });

  test('text column renders a free-text input that keeps strings verbatim', () => {
    render(<Harness columns={[TEXT_COL]} />);
    const input = screen.getByLabelText(`${TEXT_COL.name} — ${STUDENT.full_name}`);
    expect(input).toHaveAttribute('type', 'text');
    fireEvent.change(input, { target: { value: 'ممتاز في القراءة' } });
    expect(input.value).toBe('ممتاز في القراءة');
  });

  test('grade column still renders a clamped numeric input', () => {
    render(<Harness columns={[GRADE_COL]} />);
    const input = screen.getByRole('spinbutton');
    fireEvent.change(input, { target: { value: '99' } });
    expect(input.value).toBe('10'); // clamped to maxGrade
  });

  test('totals count only grade columns — check/text values never inflate the sum', () => {
    render(
      <Harness
        columns={[GRADE_COL, CHECK_COL, TEXT_COL]}
        initialData={{ 's-1': { 'c-grade': 7, 'c-check': 1, 'c-text': 'ملاحظة نصية' } }}
      />,
    );
    // Subtotal + total cells both show 7 (grade only), not 8 or NaN.
    expect(screen.getAllByText('7').length).toBeGreaterThan(0);
    expect(screen.queryByText('8')).not.toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  test('columns without a type behave as grade (legacy rows)', () => {
    const legacy = { id: 'c-legacy', name: 'قديم', group: 'coursework', maxGrade: 5 };
    render(<Harness columns={[legacy]} />);
    expect(screen.getByRole('spinbutton')).toBeInTheDocument();
  });
});
