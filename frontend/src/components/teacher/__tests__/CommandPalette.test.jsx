/**
 * Command palette — role-aware contract (sidebar audit follow-up).
 *
 * Pins the contract:
 *   - Cmd/Ctrl+K opens the palette for EVERY role.
 *   - Sub-min-length queries DO NOT hit the network.
 *   - Independent teachers hit /independent-teacher/search (unchanged).
 *   - School staff (teacher + leadership) hit /search/palette.
 *   - Parents / platform admins get navigation-only search: menuItems are
 *     filtered client-side and NO network request is made.
 *   - Selecting a result navigates to its href and persists in localStorage
 *     under the per-user recents key.
 */
import React from 'react';
import { render, screen, act, fireEvent, waitFor } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
let mockUser = { id: 'u-it-1', role: 'independent_teacher' };
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: mockUser, api: { get: mockApiGet } }),
}));

import CommandPalette from '../CommandPalette';

const _payload = () => ({
  students: [
    { id: 'st-1', category: 'students', primary: 'نور الهدى', secondary: 'الصف 5', href: '/teacher/students?student_id=st-1' },
  ],
  classes: [
    { id: 'cl-1', category: 'classes', primary: 'صف نور', secondary: null, href: '/teacher/class/cl-1' },
  ],
  subjects: [],
  lesson_plans: [],
  calendar_events: [],
});

const _palettePayload = () => ({
  q: 'نور',
  students: [
    { id: 'st-9', category: 'students', primary: 'نور المدرسة', secondary: '12345', href: '/principal/students/st-9' },
  ],
  classes: [],
  teachers: [
    { id: 'tc-1', category: 'teachers', primary: 'أ. نورة', secondary: 'n@x.test', href: '/admin/users-management?filter=teachers' },
  ],
});

const NAV_ITEMS = [
  { label: 'الإشعارات', href: '/parent/notifications', icon: null },
  {
    label: 'التواصل',
    icon: null,
    subItems: [{ label: 'الرسائل', href: '/parent/messages' }],
  },
];

const _openPalette = async () => {
  await act(async () => {
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  });
};

const _type = async (value) => {
  await act(async () => {
    fireEvent.change(screen.getByTestId('cmdk-input'), { target: { value } });
  });
  // Wait past the debounce window.
  await act(async () => { await new Promise((r) => setTimeout(r, 220)); });
};

beforeEach(() => {
  mockApiGet.mockReset();
  mockNavigate.mockReset();
  mockUser = { id: 'u-it-1', role: 'independent_teacher' };
  if (typeof window !== 'undefined') localStorage.clear();
});

test('Ctrl+K opens the palette and shows the empty hint when query is short', async () => {
  render(<CommandPalette />);
  expect(screen.queryByTestId('cmdk-panel')).toBeNull();

  await _openPalette();

  expect(screen.getByTestId('cmdk-panel')).toBeInTheDocument();
  expect(screen.getByTestId('cmdk-empty-hint')).toBeInTheDocument();
  // No network hit for an empty query.
  expect(mockApiGet).not.toHaveBeenCalled();
});

test('typing a single character does NOT trigger the search request', async () => {
  render(<CommandPalette />);
  await _openPalette();
  await _type('ن');

  expect(mockApiGet).not.toHaveBeenCalled();
});

test('IT: 2+ chars hits /independent-teacher/search, renders results, Enter navigates + persists recents', async () => {
  mockApiGet.mockResolvedValue({ data: _payload() });
  render(<CommandPalette />);
  await _openPalette();
  await _type('نور');

  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/independent-teacher/search', {
      params: { q: 'نور', limit: 8 },
    });
  });
  expect(screen.getByTestId('cmdk-result-st-1')).toBeInTheDocument();
  expect(screen.getByTestId('cmdk-result-cl-1')).toBeInTheDocument();

  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'Enter' });
  });

  expect(mockNavigate).toHaveBeenCalledWith('/teacher/students?student_id=st-1');
  // Per-user recents are persisted under the namespaced key.
  const stored = JSON.parse(localStorage.getItem('nassaq_cmdk_recents_u-it-1') || '[]');
  expect(stored).toHaveLength(1);
  expect(stored[0].id).toBe('st-1');
  // Palette closed after selection.
  expect(screen.queryByTestId('cmdk-panel')).toBeNull();
});

test('ArrowDown moves the active row before Enter so the second result is opened', async () => {
  mockApiGet.mockResolvedValue({ data: _payload() });
  render(<CommandPalette />);
  await _openPalette();
  await _type('نور');
  await waitFor(() => screen.getByTestId('cmdk-result-cl-1'));

  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'ArrowDown' });
  });
  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'Enter' });
  });

  expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/cl-1');
});

test('school leadership (effectiveRole) hits /search/palette and renders teachers category', async () => {
  mockUser = { id: 'u-p-1', role: 'school_principal' };
  mockApiGet.mockResolvedValue({ data: _palettePayload() });
  render(<CommandPalette effectiveRole="school_principal" menuItems={[]} />);
  await _openPalette();
  await _type('نور');

  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/search/palette', {
      params: { q: 'نور', limit: 8 },
    });
  });
  expect(screen.getByTestId('cmdk-result-st-9')).toBeInTheDocument();
  expect(screen.getByTestId('cmdk-result-tc-1')).toBeInTheDocument();

  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'Enter' });
  });
  expect(mockNavigate).toHaveBeenCalledWith('/principal/students/st-9');
});

test('school teacher hits /search/palette too', async () => {
  mockUser = { id: 'u-t-1', role: 'teacher' };
  mockApiGet.mockResolvedValue({ data: { q: 'نو', students: [], classes: [], teachers: [] } });
  render(<CommandPalette effectiveRole="teacher" menuItems={[]} />);
  await _openPalette();
  await _type('نور');

  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/search/palette', {
      params: { q: 'نور', limit: 8 },
    });
  });
});

test('parent: palette opens, filters menuItems client-side, NO network request', async () => {
  mockUser = { id: 'u-par-1', role: 'parent' };
  render(<CommandPalette effectiveRole="parent" menuItems={NAV_ITEMS} />);
  await _openPalette();

  expect(screen.getByTestId('cmdk-panel')).toBeInTheDocument();

  await _type('الرسائل');

  expect(mockApiGet).not.toHaveBeenCalled();
  expect(screen.getByTestId('cmdk-result-nav-/parent/messages')).toBeInTheDocument();

  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'Enter' });
  });
  expect(mockNavigate).toHaveBeenCalledWith('/parent/messages');
});

test('platform_admin: navigation-only search, no network', async () => {
  mockUser = { id: 'u-pa-1', role: 'platform_admin' };
  render(
    <CommandPalette
      effectiveRole="platform_admin"
      menuItems={[{ label: 'المدارس', href: '/platform/schools', icon: null }]}
    />,
  );
  await _openPalette();
  await _type('المدارس');

  expect(mockApiGet).not.toHaveBeenCalled();
  expect(screen.getByTestId('cmdk-result-nav-/platform/schools')).toBeInTheDocument();
});

test('navigation results merge ABOVE backend results for school staff', async () => {
  mockUser = { id: 'u-p-2', role: 'school_principal' };
  mockApiGet.mockResolvedValue({ data: _palettePayload() });
  render(
    <CommandPalette
      effectiveRole="school_principal"
      menuItems={[{ label: 'نور - صفحة', href: '/admin/nour-page', icon: null }]}
    />,
  );
  await _openPalette();
  await _type('نور');
  await waitFor(() => screen.getByTestId('cmdk-result-st-9'));

  // Navigation category comes first, so plain Enter opens the nav hit.
  expect(screen.getByTestId('cmdk-result-nav-/admin/nour-page')).toBeInTheDocument();
  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'Enter' });
  });
  expect(mockNavigate).toHaveBeenCalledWith('/admin/nour-page');
});
