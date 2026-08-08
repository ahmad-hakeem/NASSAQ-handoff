import React, { useRef, useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

import FollowupGradesTable from '../FollowupGradesTable';

const COL = { id: 'c-part', name: 'المشاركة', group: 'coursework', maxGrade: 5 };

function Harness({ initialData }) {
  const [data, setData] = useState(initialData);
  const dirty = useRef(new Set());
  const onGradeChange = (sid, cid, value) => {
    dirty.current.add(`${sid}:${cid}`);
    setData((prev) => ({ ...prev, [sid]: { ...(prev[sid] || {}), [cid]: value } }));
  };
  return (
    <FollowupGradesTable
      students={[
        { id: 's-zero', full_name: 'Zero Student' },
        { id: 's-nonzero', full_name: 'NonZero Student' },
      ]}
      columns={[COL]}
      gradesData={data}
      onGradeChange={onGradeChange}
      t={(k) => k}
    />
  );
}

describe('FollowupGradesTable editing after reopen', () => {
  test('zero-score cell is editable', () => {
    render(<Harness initialData={{ 's-nonzero': { 'c-part': 3 } }} />);
    const inputs = screen.getAllByRole('spinbutton');
    const zeroInput = inputs[0]; // s-zero row
    expect(zeroInput.value).toBe('');
    fireEvent.change(zeroInput, { target: { value: '2' } });
    expect(zeroInput.value).toBe('2');
  });

  test('non-zero-score cell can be increased', () => {
    render(<Harness initialData={{ 's-nonzero': { 'c-part': 3 } }} />);
    const inputs = screen.getAllByRole('spinbutton');
    const nonZeroInput = inputs[1]; // s-nonzero row, value 3
    expect(nonZeroInput.value).toBe('3');
    fireEvent.change(nonZeroInput, { target: { value: '4' } });
    expect(nonZeroInput.value).toBe('4');
  });

  test('non-zero-score cell can be decreased', () => {
    render(<Harness initialData={{ 's-nonzero': { 'c-part': 3 } }} />);
    const inputs = screen.getAllByRole('spinbutton');
    const nonZeroInput = inputs[1];
    expect(nonZeroInput.value).toBe('3');
    fireEvent.change(nonZeroInput, { target: { value: '1' } });
    expect(nonZeroInput.value).toBe('1');
  });
});
