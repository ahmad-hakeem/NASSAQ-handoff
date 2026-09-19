import React from 'react';
import { render, screen } from '@testing-library/react';
import { SchoolOperationalStatus } from '../DynamicSettingsContent';

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({
    t: (key) => ({
      activeFem: 'نشطة',
      inactiveFem: 'غير نشطة',
    }[key] || key),
  }),
}));

describe('SchoolOperationalStatus', () => {
  it('shows the active treatment only for the canonical active status', () => {
    render(<SchoolOperationalStatus status="active" />);

    expect(screen.getByTestId('school-operational-status')).toHaveTextContent('نشطة');
    expect(screen.getByTestId('school-operational-status-icon')).toHaveClass('text-emerald-500');
    expect(screen.getByTestId('school-operational-status-value')).toHaveClass('text-emerald-600');
  });

  it.each([undefined, null, 'pending', 'setup', 'suspended', 'archived', 'unknown'])(
    'never shows %s as active',
    (status) => {
      render(<SchoolOperationalStatus status={status} />);

      expect(screen.getByTestId('school-operational-status')).toHaveTextContent('غير نشطة');
      expect(screen.getByTestId('school-operational-status-icon')).toHaveClass('text-red-400');
      expect(screen.getByTestId('school-operational-status-value')).toHaveClass('text-red-500');
    },
  );
});