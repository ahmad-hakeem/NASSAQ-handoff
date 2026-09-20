import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import {
  TeacherBirthDateDisplay,
  TeacherBirthDateField,
} from '../TeacherBirthDate';
import ar from '@/locales/ar.json';

const messages = {
  gregorianBirthDate: 'Gregorian birth date',
  hijriBirthDate: 'Hijri birth date',
  gregorianDateFormat: 'YYYY-MM-DD (Gregorian)',
  hijriDateFormat: 'YYYY-MM-DD AH (Umm al-Qura)',
  invalidGregorianDate: 'Enter a valid Gregorian date in YYYY-MM-DD format.',
  futureBirthDate: 'Birth date cannot be in the future.',
  hijriConversionUnavailable: 'Hijri conversion is unavailable for this date.',
  invalidStoredGregorianDate: 'Invalid stored Gregorian date',
  notProvided: 'Not provided',
};
const t = (key) => messages[key] || key;

describe('TeacherBirthDate shared field and display', () => {
  test('labels Gregorian input and exposes its calculated Hijri equivalent', () => {
    render(
      <TeacherBirthDateField
        id="dob"
        value="2024-03-11"
        onChange={() => {}}
        t={t}
        today="2026-01-02"
      />
    );

    expect(screen.getByLabelText('Gregorian birth date')).toHaveValue('2024-03-11');
    expect(screen.getByText('1445-09-01 AH')).toBeInTheDocument();
    expect(screen.getByText('YYYY-MM-DD (Gregorian)')).toBeInTheDocument();
  });

  test('announces invalid and future errors and does not render NaN', () => {
    const { rerender } = render(
      <TeacherBirthDateField id="dob" value="2026-01-03" onChange={() => {}} t={t} today="2026-01-02" />
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Birth date cannot be in the future.');
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();

    rerender(<TeacherBirthDateField id="dob" value="2024-02-30" onChange={() => {}} t={t} today="2026-01-02" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid Gregorian date');
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  test('shows an explicit non-blocking message outside the conversion table', () => {
    render(<TeacherBirthDateField id="dob" value="1900-01-01" onChange={() => {}} t={t} today="2026-01-02" />);
    expect(screen.getByText('Hijri conversion is unavailable for this date.')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByLabelText('Gregorian birth date')).toBeValid();
  });

  test('passes only the Gregorian input value and supports clearing', () => {
    const onChange = jest.fn();
    render(<TeacherBirthDateField id="dob" value="2024-03-11" onChange={onChange} t={t} today="2026-01-02" />);
    fireEvent.change(screen.getByLabelText('Gregorian birth date'), { target: { value: '' } });
    expect(onChange).toHaveBeenCalledWith('');
  });

  test('read-only display identifies both calendars and handles blank', () => {
    const { rerender } = render(<TeacherBirthDateDisplay value="2024-03-11" t={t} />);
    expect(screen.getByText('Gregorian birth date')).toBeInTheDocument();
    expect(screen.getByText('2024-03-11')).toBeInTheDocument();
    expect(screen.getByText('Hijri birth date')).toBeInTheDocument();
    expect(screen.getByText('1445-09-01 AH')).toBeInTheDocument();

    rerender(<TeacherBirthDateDisplay value={null} t={t} />);
    expect(screen.getAllByText('Not provided')).toHaveLength(2);
  });

  test('preserves and clearly labels a noncanonical stored Gregorian value', () => {
    render(<TeacherBirthDateDisplay value="legacy-date" t={t} />);
    expect(screen.getByText('legacy-date')).toBeInTheDocument();
    expect(screen.getByText('Invalid stored Gregorian date')).toBeInTheDocument();
    expect(screen.queryByText('Not provided')).not.toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument();
  });

  test('uses the dedicated Arabic clear-birth-date action label', () => {
    render(
      <TeacherBirthDateField
        value="legacy-date"
        onChange={() => {}}
        t={(key) => ar[key] || key}
        locale="ar"
        legacyUnchanged
      />
    );
    expect(screen.getByRole('button', { name: 'مسح تاريخ الميلاد' })).toBeInTheDocument();
    expect(ar.clearTeacherBirthDate).toBe('مسح تاريخ الميلاد');
  });
});