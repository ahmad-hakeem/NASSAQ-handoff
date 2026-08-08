/**
 * Task #319 — IT bulk-import preview mobile contract.
 *
 * At 360px wide the CSV row-by-row preview on the IT students importer
 * must render through the shared ResponsiveTable mobile-cards branch
 * (mirrors tasks #280 — audit log, #303 — students/classes, #313 —
 * lesson planner) instead of overflowing horizontally.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
}));

const mockApiPost = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    api: { get: jest.fn(), post: mockApiPost, put: jest.fn(), delete: jest.fn() },
    user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  }),
}));

import ImportStudentsPage from '../ImportStudentsPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiPost.mockReset();
});

test('CSV preview at 360px renders the ResponsiveTable mobile cards with valid + invalid chips', async () => {
  const parseResponse = {
    total_rows: 2,
    valid_count: 1,
    invalid_count: 1,
    quota: { max_students: 200, current_students: 5 },
    rows: [
      {
        row_number: 1,
        full_name: 'أحمد محمد العتيبي',
        national_id: '1098765432',
        gender: 'male',
        date_of_birth: '2014-03-12',
        grade_level: 'الثالث الابتدائي',
        is_valid: true,
        errors: [],
      },
      {
        row_number: 2,
        full_name: 'سارة عبدالله القحطاني',
        national_id: null,
        gender: 'female',
        date_of_birth: null,
        grade_level: 'الرابع الابتدائي',
        is_valid: false,
        errors: ['تاريخ الميلاد مطلوب'],
      },
    ],
  };
  mockApiPost.mockResolvedValueOnce({ data: parseResponse });

  const { container } = render(<ImportStudentsPage />);

  // Trigger the file input change to surface the preview pane.
  const fileInput = container.querySelector('input[type="file"]');
  expect(fileInput).not.toBeNull();
  const file = new File(['name'], 'students.csv', { type: 'text/csv' });
  fireEvent.change(fileInput, { target: { files: [file] } });

  await waitFor(() => {
    expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  }, { timeout: 4000 });

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('أحمد محمد العتيبي');
  expect(mobile.textContent).toContain('سارة عبدالله القحطاني');
  // Per-row status chips (color-coded) must remain visible on phones.
  // Verdict chips (Noor restore semantics): a clean new row is 'إضافة'.
  expect(mobile.textContent).toContain('إضافة');
  expect(mobile.textContent).toContain('تاريخ الميلاد مطلوب');

  const cards = mobile.querySelectorAll('li');
  expect(cards.length).toBe(2);
});
