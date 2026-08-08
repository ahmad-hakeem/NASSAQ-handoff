/**
 * QuickAIOperationsPanel — initialStats dedup guard (real component, no stub).
 *
 * The /admin page fetched GET /admin/command-center/stats twice: once in
 * AdminDashboard, once in this embedded panel. The panel now accepts an
 * `initialStats` snapshot from the parent.
 *
 * Two behaviours must hold together:
 *   1. initialStats supplied  -> ZERO stats GETs on the initial load.
 *   2. an explicit refresh    -> ALWAYS re-fetches, so the snapshot can never
 *                                freeze the panel on stale numbers.
 * Without a parent snapshot the panel still fetches its own stats once.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

const mockApiGet = jest.fn();
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockAuthValue = { user: { id: 'admin-1', role: 'platform_admin' }, api: mockApi };
jest.mock('../../../contexts/AuthContext', () => ({ useAuth: () => mockAuthValue }));

const stableT = (k) => k;
jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, isDark: false }),
  useTranslation: () => ({ t: stableT }),
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('../../ui/card', () => ({
  Card: ({ children, ...r }) => <div {...r}>{children}</div>,
  CardContent: ({ children, ...r }) => <div {...r}>{children}</div>,
  CardHeader: ({ children, ...r }) => <div {...r}>{children}</div>,
  CardTitle: ({ children, ...r }) => <div {...r}>{children}</div>,
}));
jest.mock('../../ui/button', () => ({
  Button: ({ children, asChild: _a, variant: _v, size: _s, ...r }) => <button {...r}>{children}</button>,
}));
jest.mock('../../ui/badge', () => ({
  Badge: ({ children, ...r }) => <span {...r}>{children}</span>,
}));
jest.mock('../../ui/progress', () => ({ Progress: () => <div /> }));
jest.mock('../../ui/dialog', () => ({
  Dialog: ({ children }) => <div>{children}</div>,
  DialogContent: ({ children, ...r }) => <div {...r}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogDescription: ({ children }) => <div>{children}</div>,
}));

const QuickAIOperationsPanel = require('../QuickAIOperationsPanel').default;

const STATS_URL = '/admin/command-center/stats';
const PARENT_STATS = { registered_schools: 5, ai_enabled_schools: 3 };
const FRESH_STATS = { registered_schools: 7, ai_enabled_schools: 7 };

const statsCalls = () => mockApiGet.mock.calls.filter(([url]) => url === STATS_URL);

describe('QuickAIOperationsPanel — initialStats reuse is initial-load only', () => {
  beforeEach(() => {
    // CRA resetMocks:true wipes implementations — reinstall per test.
    mockApiGet.mockImplementation((url) => {
      if (url === STATS_URL) return Promise.resolve({ data: FRESH_STATS });
      if (url === '/admin/notifications/stats') return Promise.resolve({ data: {} });
      if (url === '/admin/ai-suggested-actions') return Promise.resolve({ data: { actions: [] } });
      return Promise.resolve({ data: { history: [], operations_today: 0 } });
    });
  });

  test('no stats GET on initial load when the parent supplies initialStats', async () => {
    render(<QuickAIOperationsPanel api={mockApi} initialStats={PARENT_STATS} />);

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/admin/notifications/stats'));
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });

    expect(statsCalls()).toHaveLength(0);
    // The parent snapshot is what the panel renders (5 schools, 3 AI-enabled → partial).
    expect(screen.getByTestId('ai-operations-panel')).toBeInTheDocument();
  });

  test('manual refresh always re-fetches stats even when initialStats was supplied', async () => {
    render(<QuickAIOperationsPanel api={mockApi} initialStats={PARENT_STATS} />);

    await waitFor(() => expect(mockApiGet).toHaveBeenCalledWith('/admin/notifications/stats'));
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    expect(statsCalls()).toHaveLength(0);

    await act(async () => {
      fireEvent.click(screen.getByTestId('ai-refresh-status'));
    });

    await waitFor(() => expect(statsCalls()).toHaveLength(1));
  });

  test('without initialStats the panel fetches its own stats exactly once', async () => {
    render(<QuickAIOperationsPanel api={mockApi} />);

    await waitFor(() => expect(statsCalls()).toHaveLength(1));
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });

    expect(statsCalls()).toHaveLength(1);
  });
});
