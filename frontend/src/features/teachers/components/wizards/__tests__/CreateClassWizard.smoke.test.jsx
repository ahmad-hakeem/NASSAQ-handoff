/**
 * Smoke regression for the Add → Class flow (Users & Classes Management).
 *
 * A loading-indicator standardization sweep once added `<LoadingState>` to
 * this wizard WITHOUT its import — a runtime-only ReferenceError (webpack
 * treats it as a free variable, so the build stayed green) that crashed the
 * whole app to the global error boundary the moment a principal clicked
 * "فصل" in the add picker. This test mounts the wizard through BOTH render
 * branches — the loading branch (where the crash lived) and the loaded
 * step-1 form — so any missing import/undefined component in either branch
 * fails CI instead of production.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';
import CreateClassWizard from '../CreateClassWizard';

const mockApi = { get: jest.fn(), post: jest.fn() };
const mockNassaqError = jest.fn();

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false, isDark: false }),
  useTranslation: () => ({ t: (key, fallback) => fallback || key }),
}));

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', api: mockApi }),
}));

jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

// Lightweight Dialog: render children only when open.
jest.mock('@/shared/components/ui/dialog', () => {
  const React = require('react');
  const passthrough = ({ children }) => React.createElement(React.Fragment, null, children);
  return {
    Dialog: ({ open, children }) =>
      open ? React.createElement('div', { 'data-testid': 'dialog-root' }, children) : null,
    DialogContent: ({ children, ...props }) =>
      React.createElement('div', { 'data-testid': props['data-testid'] }, children),
    DialogHeader: passthrough,
    DialogFooter: passthrough,
    DialogTitle: passthrough,
    DialogDescription: passthrough,
  };
});

// Radix Select needs pointer events jsdom lacks; a stub is enough for a
// mount smoke test (we never change selection here).
jest.mock('@/shared/components/ui/select', () => {
  const React = require('react');
  const passthrough = ({ children }) => React.createElement(React.Fragment, null, children);
  return {
    Select: passthrough,
    SelectContent: passthrough,
    SelectTrigger: ({ children }) => React.createElement('button', { type: 'button' }, children),
    SelectValue: () => null,
    SelectItem: () => null,
  };
});

beforeEach(() => {
  jest.clearAllMocks();
});

test('mounts through the loading branch, then renders step 1 without crashing', async () => {
  // Keep the options fetch pending so the loading branch actually renders —
  // this is the exact branch whose missing LoadingState import crashed prod.
  let resolveOptions;
  const pending = new Promise((res) => { resolveOptions = res; });
  mockApi.get.mockReturnValue(pending.then(() => ({ data: {} })));

  await act(async () => {
    render(<CreateClassWizard open onOpenChange={jest.fn()} onSuccess={jest.fn()} />);
  });

  // Loading branch: the real LoadingState (role="status") must render.
  expect(screen.getByRole('status')).toBeInTheDocument();

  // Resolve the fetches → step-1 form must appear.
  await act(async () => { resolveOptions(); });
  expect(screen.getByTestId('class-name-ar')).toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
