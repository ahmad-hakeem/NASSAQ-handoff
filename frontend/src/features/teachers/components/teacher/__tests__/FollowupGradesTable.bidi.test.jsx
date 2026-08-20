import React from 'react';
import { render, screen } from '@testing-library/react';
import FollowupGradesTable from '../FollowupGradesTable';

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, theme: 'light' }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const STUDENTS = [
  { id: 's1', full_name: 'أحمد محمد علي' },
  { id: 's2', full_name: 'John Doe (Class A-2)' },
];

const COLUMNS = [
  { id: 'c1', name: 'واجب 1 (HW1)', group: 'coursework', maxGrade: 10, type: 'grade' },
  { id: 'c2', name: 'Quiz 1 (اختبار قصير)', group: 'exams', maxGrade: 20, type: 'grade' },
];

describe('FollowupGradesTable BiDi & Mixed Script Support', () => {
  test('renders student names inside bdi tags with dir=auto for mixed script support', () => {
    render(
      <FollowupGradesTable
        students={STUDENTS}
        columns={COLUMNS}
        gradesData={{ s1: { c1: 9, c2: 18 }, s2: { c1: 10, c2: 19 } }}
        t={(k) => k}
      />
    );

    // Both Arabic and English names are isolated
    expect(screen.getByText('أحمد محمد علي')).toBeInTheDocument();
    expect(screen.getByText('John Doe (Class A-2)')).toBeInTheDocument();

    const arabicBdi = screen.getByText('أحمد محمد علي').closest('bdi');
    expect(arabicBdi).toHaveAttribute('dir', 'auto');

    const englishBdi = screen.getByText('John Doe (Class A-2)').closest('bdi');
    expect(englishBdi).toHaveAttribute('dir', 'auto');
  });

  test('uses sticky start classes on # and studentName columns', () => {
    const { container } = render(
      <FollowupGradesTable
        students={STUDENTS}
        columns={COLUMNS}
        gradesData={{}}
        t={(k) => k}
      />
    );

    const thElements = container.querySelectorAll('th');
    const firstColHeader = thElements[0];
    const secondColHeader = thElements[1];

    expect(firstColHeader.className).toContain('sticky');
    expect(firstColHeader.className).toContain('start-0');

    expect(secondColHeader.className).toContain('sticky');
    expect(secondColHeader.className).toContain('start-12');
  });

  test('formats max grade indicators with LTR numeric direction', () => {
    render(
      <FollowupGradesTable
        students={STUDENTS}
        columns={COLUMNS}
        gradesData={{}}
        t={(k) => k}
      />
    );

    screen.getAllByText('/10').forEach((el) => {
      expect(el).toHaveAttribute('dir', 'ltr');
    });
    screen.getAllByText('/20').forEach((el) => {
      expect(el).toHaveAttribute('dir', 'ltr');
    });
  });
});
