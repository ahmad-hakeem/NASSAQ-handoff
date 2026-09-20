import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { SettingsModals } from './SettingsModals';

const mockNavigate = jest.fn();
let mockDirection = 'ltr';
jest.mock('react-router-dom', () => ({ useNavigate: () => mockNavigate }));
jest.mock('@/shared/models/utils/studentNavigation', () => ({
  useSchoolNavigation: () => ({ rolePrefix: '/principal' }),
}));
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ direction: mockDirection }),
  useTranslation: () => ({ t: key => key }),
}));
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn() }),
}));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

const makeHook = type => ({
  showNoorImportModal: true, setShowNoorImportModal: jest.fn(), noorImportType: type,
  teachers: [], classes: [], api: { post: jest.fn().mockResolvedValue({ data: { imported: 1 } }), get: jest.fn() },
  fetchData: jest.fn(),
});

beforeEach(() => { jest.clearAllMocks(); mockDirection = 'ltr'; });

test.each(['students', 'teachers'])('%s directs to mandatory management review without accepting a file or calling legacy import', type => {
  const hook = makeHook(type);
  const { container } = render(<SettingsModals hook={hook} />);
  expect(screen.getByRole('dialog')).toHaveTextContent('No data has been imported here.');
  expect(container.querySelector('input[type="file"]')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Open import review' }));
  expect(mockNavigate).toHaveBeenCalledWith(`/principal/users-management?filter=import-export&import_type=${type}`);
  expect(hook.setShowNoorImportModal).toHaveBeenCalledWith(false);
  expect(hook.api.post).not.toHaveBeenCalled();
});

test('Arabic redirect remains RTL and can cancel without navigation', () => {
  mockDirection = 'rtl';
  const hook = makeHook('students');
  render(<SettingsModals hook={hook} />);
  expect(screen.getByRole('dialog').parentElement).toHaveAttribute('dir', 'rtl');
  fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
  expect(hook.setShowNoorImportModal).toHaveBeenCalledWith(false);
  expect(mockNavigate).not.toHaveBeenCalled();
  expect(hook.api.post).not.toHaveBeenCalled();
});

test.each(['noor_classes', 'noor_assignments'])('%s retains its existing file upload endpoint and success callback', async type => {
  const hook = makeHook(type);
  const { container } = render(<SettingsModals hook={hook} />);
  const file = new File(['data'], 'noor.xlsx');
  fireEvent.change(container.querySelector('input[type="file"]'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: 'startImport' }));
  await waitFor(() => expect(hook.fetchData).toHaveBeenCalledTimes(1));
  expect(hook.api.post).toHaveBeenCalledWith(`/bulk/import/${type}`, expect.any(FormData), {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  expect(hook.api.post.mock.calls[0][1].get('file')).toBe(file);
  expect(mockNavigate).not.toHaveBeenCalled();
});