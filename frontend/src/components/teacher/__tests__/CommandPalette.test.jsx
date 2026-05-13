/**
 * Task #251 — IT command palette.
 *
 * Pins the contract:
 *   - Cmd/Ctrl+K opens the palette (IT only).
 *   - Sub-min-length queries DO NOT hit the network.
 *   - Selecting a result navigates to its href and persists in localStorage
 *     under the per-user recents key.
 *   - Non-IT roles never render the palette even if the open event fires.
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

const _openPalette = async () => {
  await act(async () => {
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  });
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

  await act(async () => {
    fireEvent.change(screen.getByTestId('cmdk-input'), { target: { value: 'ن' } });
  });
  // Wait past the debounce window.
  await act(async () => { await new Promise((r) => setTimeout(r, 220)); });

  expect(mockApiGet).not.toHaveBeenCalled();
});

test('typing 2+ chars hits the search endpoint, renders results, and Enter navigates + persists recents', async () => {
  mockApiGet.mockResolvedValue({ data: _payload() });
  render(<CommandPalette />);
  await _openPalette();

  await act(async () => {
    fireEvent.change(screen.getByTestId('cmdk-input'), { target: { value: 'نور' } });
  });
  await act(async () => { await new Promise((r) => setTimeout(r, 220)); });

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
  await act(async () => {
    fireEvent.change(screen.getByTestId('cmdk-input'), { target: { value: 'نور' } });
  });
  await act(async () => { await new Promise((r) => setTimeout(r, 220)); });
  await waitFor(() => screen.getByTestId('cmdk-result-cl-1'));

  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'ArrowDown' });
  });
  await act(async () => {
    fireEvent.keyDown(screen.getByTestId('cmdk-input'), { key: 'Enter' });
  });

  expect(mockNavigate).toHaveBeenCalledWith('/teacher/class/cl-1');
});

test('non-IT role: Ctrl+K is a no-op and the palette never renders', async () => {
  mockUser = { id: 'u-p-1', role: 'school_principal' };
  render(<CommandPalette />);
  await _openPalette();
  // Even after the open event fires, the early-return on `!isIT` keeps the
  // panel out of the tree and the network silent.
  expect(screen.queryByTestId('cmdk-panel')).toBeNull();
  expect(mockApiGet).not.toHaveBeenCalled();
});
