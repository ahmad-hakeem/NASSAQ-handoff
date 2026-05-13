/**
 * Task #319 — IT bulk-import preview mobile contract (classes / subjects).
 *
 * Locks in the second bulk-import surface: the shared CsvImportPanel
 * inside BulkImportPage (used by the classes + subjects tabs) must
 * render its row-by-row preview through the ResponsiveTable mobile
 * cards branch at 360px wide.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';

function activateRadixTab(tab) {
  // Radix Tabs activates on pointerDown (with primary mouse button),
  // not on click — fireEvent.click doesn't switch tabs in jsdom.
  act(() => {
    fireEvent.pointerDown(tab, { button: 0, pointerType: 'mouse' });
    fireEvent.mouseDown(tab, { button: 0 });
    fireEvent.click(tab);
  });
}

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
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    api: { get: jest.fn(), post: mockApiPost, put: jest.fn(), delete: jest.fn() },
    user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  }),
}));

import BulkImportPage from '../BulkImportPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiPost.mockReset();
});

async function uploadCsvAndAwaitMobile(container) {
  // The visible TabsContent's CsvImportPanel mounts a single hidden
  // file input attached to a button labelled "اختيار ملف CSV". Radix
  // Tabs only renders the active tab's content, so picking the file
  // input scoped to that visible panel reliably targets the right one.
  const panels = container.querySelectorAll('[role="tabpanel"]');
  const activePanel = Array.from(panels).find(
    (el) => el.getAttribute('data-state') === 'active' || !el.hidden,
  );
  expect(activePanel).toBeTruthy();
  const fileInput = activePanel.querySelector('input[type="file"]');
  expect(fileInput).toBeTruthy();
  const file = new File(['name'], 'rows.csv', { type: 'text/csv' });
  fireEvent.change(fileInput, { target: { files: [file] } });
  await waitFor(() => {
    expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  }, { timeout: 4000 });
}

test('classes import preview at 360px renders ResponsiveTable mobile cards', async () => {
  mockApiPost.mockResolvedValueOnce({
    data: {
      total_rows: 2,
      valid_count: 1,
      invalid_count: 1,
      quota: { max_classes: 5, current_classes: 1 },
      projected_classes: 2,
      rows: [
        {
          row_number: 1, name: 'حلقة القرآن - مستوى أول',
          grade_level: 'الصف الأول', default_subject: 'القرآن الكريم',
          is_valid: true, errors: [],
        },
        {
          row_number: 2, name: '',
          grade_level: 'الصف الثاني', default_subject: '',
          is_valid: false, errors: ['اسم الفصل مطلوب'],
        },
      ],
    },
  });

  const { container } = render(<BulkImportPage />);
  // Switch to the classes tab and wait for its unique copy to mount.
  const classesTab = screen.getByRole('tab', { name: /الفصول/ });
  activateRadixTab(classesTab);
  await waitFor(() => {
    expect(screen.getByText(/الحد الأقصى ٥ فصول/)).toBeInTheDocument();
  });

  await uploadCsvAndAwaitMobile(container);

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('حلقة القرآن - مستوى أول');
  expect(mobile.textContent).toContain('جاهز');
  expect(mobile.textContent).toContain('اسم الفصل مطلوب');
  expect(mobile.querySelectorAll('li').length).toBe(2);
});

test('subjects import preview at 360px renders ResponsiveTable mobile cards', async () => {
  mockApiPost.mockResolvedValueOnce({
    data: {
      total_rows: 2,
      valid_count: 2,
      invalid_count: 0,
      quota: {},
      rows: [
        { row_number: 1, name: 'القرآن الكريم', code: 'QURAN', is_valid: true, errors: [] },
        { row_number: 2, name: 'التجويد', code: 'TJWD', is_valid: true, errors: [] },
      ],
    },
  });

  const { container } = render(<BulkImportPage />);
  const subjectsTab = screen.getByRole('tab', { name: /المواد/ });
  activateRadixTab(subjectsTab);
  await waitFor(() => {
    expect(screen.getByText(/الحد الأعلى ٥٠ مادة/)).toBeInTheDocument();
  });

  await uploadCsvAndAwaitMobile(container);

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('القرآن الكريم');
  expect(mobile.textContent).toContain('التجويد');
  expect(mobile.textContent).toContain('QURAN');
  expect(mobile.querySelectorAll('li').length).toBe(2);
});
