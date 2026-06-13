/**
 * Task #893 — frontend coverage for the "Generate with Hakim" subject-code
 * button in the SubjectsManager Add-Subject modal.
 *
 * Two behaviours are pinned:
 *  - Clicking generate with no name shows the "needs a name first" prompt and
 *    never calls the suggestion endpoint.
 *  - A successful POST /subjects/hakim-code response fills the editable code
 *    field with the returned (uppercase) code.
 *
 * Contexts and toast are stubbed; the heavy Radix surface is rendered for real
 * but only the create-dialog generate path is exercised.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockGet = jest.fn(() => Promise.resolve({ data: [] }));
const mockPost = jest.fn();
const mockApi = { get: mockGet, post: mockPost };

const mockNassaqError = jest.fn();
const mockNassaqConfirm = jest.fn();
const mockShowAlert = jest.fn();

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'admin-1', role: 'school_admin', tenant_id: 'school-1' },
    api: mockApi,
  }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
  useTheme: () => ({ isRTL: true, isDark: false }),
}));

jest.mock('../../ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError, nassaqConfirm: mockNassaqConfirm, showAlert: mockShowAlert }),
}));

import { SubjectsManager } from '../SubjectsManager';

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockResolvedValue({ data: [] });
  mockPost.mockReset();
  mockNassaqError.mockReset();
});

async function openAddDialog() {
  render(<SubjectsManager embedded />);
  // Wait for the initial /subjects load to settle.
  await waitFor(() => expect(mockGet).toHaveBeenCalled());
  fireEvent.click(screen.getByTestId('add-subject-btn'));
  await screen.findByTestId('generate-subject-code-btn');
}

test('generate with no name shows the prompt and does not call the endpoint', async () => {
  await openAddDialog();

  fireEvent.click(screen.getByTestId('generate-subject-code-btn'));

  await waitFor(() => {
    expect(mockNassaqError).toHaveBeenCalledWith('subjectCodeNeedsNameFirst');
  });
  // The suggestion endpoint must never be hit without a name.
  expect(
    mockPost.mock.calls.filter(([url]) => url === '/subjects/hakim-code')
  ).toHaveLength(0);
});

test('a successful response fills the editable code field', async () => {
  mockPost.mockResolvedValue({ data: { success: true, code: 'MATH101' } });
  await openAddDialog();

  // Provide an Arabic name so the generate handler proceeds.
  fireEvent.change(screen.getByTestId('subject-name-input'), {
    target: { value: 'رياضيات' },
  });

  fireEvent.click(screen.getByTestId('generate-subject-code-btn'));

  await waitFor(() => {
    expect(
      mockPost.mock.calls.some(([url]) => url === '/subjects/hakim-code')
    ).toBe(true);
  });

  const codeInput = screen.getByTestId('subject-code-input');
  await waitFor(() => expect(codeInput.value).toBe('MATH101'));
  // The field stays editable (not disabled/readonly) so the admin can tweak it.
  expect(codeInput).not.toBeDisabled();
  expect(mockNassaqError).not.toHaveBeenCalled();
});
