/**
 * Task #274 — CommandPalette mobile sheet contract.
 *
 * At 360px wide the palette must:
 *   - render as a full-screen sheet (overlay has no `pt-` desktop offset
 *     and the panel itself fills the viewport).
 *   - expose an explicit "Done" button (`cmdk-close-mobile`) so the
 *     keyboard-less path off the palette is obvious on phones.
 */
import React from 'react';
import { render, screen, act, fireEvent } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u-it-1', role: 'independent_teacher' },
    api: { get: mockApiGet },
  }),
}));

import CommandPalette from '../CommandPalette';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
});

test('at 360px the palette renders the explicit mobile Done button and the sheet panel', async () => {
  render(<CommandPalette />);
  await act(async () => {
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
  });

  const panel = screen.getByTestId('cmdk-panel');
  // Sheet contract: panel is full-width / full-height on phones and only
  // becomes a centred dialog at sm+. We assert the Tailwind classes that
  // gate that behaviour so a future refactor can't silently revert it.
  expect(panel.className).toMatch(/\bw-full\b/);
  expect(panel.className).toMatch(/\bh-full\b/);
  expect(panel.className).toMatch(/\bsm:max-w-/);
  expect(panel.className).toMatch(/\bsm:rounded/);

  // The mobile Done affordance is rendered and clickable.
  const doneBtn = screen.getByTestId('cmdk-close-mobile');
  expect(doneBtn).toBeInTheDocument();

  await act(async () => {
    fireEvent.click(doneBtn);
  });
  expect(screen.queryByTestId('cmdk-panel')).toBeNull();
});
