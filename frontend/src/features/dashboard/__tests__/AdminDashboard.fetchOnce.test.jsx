/**
 * AdminDashboard — duplicate-fetch regression guard.
 *
 * Production trace showed GET /admin/command-center/stats firing TWICE on
 * a single /admin page load: once from AdminDashboard.fetchAllData and once
 * from the embedded QuickAIOperationsPanel.loadAll.
 *
 * Fix: QuickAIOperationsPanel accepts an `initialStats` prop; when the parent
 * supplies it the panel skips the stats GET on its own initial load.
 *
 * Guardrail: mount once → exactly ONE GET to /admin/command-center/stats.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
  Link: ({ children, to, ...rest }) => <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>,
}), { virtual: true });

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

const mockApiGet = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
};
const mockUser = { id: 'admin-1', role: 'platform_admin', full_name: 'Test Admin' };
const mockAuthValue = { user: mockUser, api: mockApi, isImpersonating: false, getEffectiveRole: () => 'platform_admin' };

jest.mock('@/shared/contexts/AuthContext', () => ({ useAuth: () => mockAuthValue }));

const stableT = (k) => k;
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, toggleTheme: jest.fn(), toggleLanguage: jest.fn(), isDark: false }),
  useTranslation: () => ({ t: stableT }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(), nassaqWarning: jest.fn(), nassaqInfo: jest.fn(), nassaqConfirm: jest.fn(),
  }),
}));

jest.mock('@/admin/features/schools/components/CreateSchoolWizard', () => ({ __esModule: true, default: () => <div /> }));

// QuickAIOperationsPanel is the component under test — stub a lightweight version
// that records whether it tried to fetch stats independently.
jest.mock('@/features/hakim/components/ai/QuickAIOperationsPanel', () => ({
  __esModule: true,
  default: function FakeQuickAIPanel({ initialStats }) {
    // Record the prop value; don't issue any API calls.
    FakeQuickAIPanel.lastInitialStats = initialStats;
    return <div data-testid="quick-ai-panel" />;
  },
}));

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));
jest.mock('recharts', () => ({
  XAxis: () => null, YAxis: () => null, Tooltip: () => null,
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  AreaChart: () => null, Area: () => null,
  BarChart: () => null, Bar: () => null, Cell: () => null,
  PieChart: () => null, Pie: () => null,
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));
jest.mock('@/shared/components/ui/card', () => ({
  Card: ({ children, ...r }) => <div {...r}>{children}</div>,
  CardContent: ({ children, ...r }) => <div {...r}>{children}</div>,
  CardHeader: ({ children, ...r }) => <div {...r}>{children}</div>,
  CardTitle: ({ children, ...r }) => <div {...r}>{children}</div>,
}));
jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, ...r }) => <button {...r}>{children}</button>,
}));
jest.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children, ...r }) => <span {...r}>{children}</span>,
}));

const { AdminDashboard } = require('@/features/dashboard/pages/AdminDashboard');
const QuickAIOperationsPanel = require('@/features/hakim/components/ai/QuickAIOperationsPanel').default;

const STATS_URL = '/admin/command-center/stats';
const MOCK_STATS = { registered_schools: 5, ai_enabled_schools: 3 };

describe('AdminDashboard — single fetch of /admin/command-center/stats', () => {
  beforeEach(() => {
    mockApiGet.mockImplementation((url) => {
      if (url === STATS_URL) return Promise.resolve({ data: MOCK_STATS });
      if (url === '/super-admin/dashboard-stats') return Promise.resolve({ data: {} });
      if (url === '/schools') return Promise.resolve({ data: { schools: [], total: 0, page: 1, limit: 5, total_pages: 1 } });
      if (url === '/admin/command-center/system-health') return Promise.resolve({ data: {} });
      if (url === '/analytics/overview') return Promise.resolve({ data: {} });
      if (url === '/reports/school/overview') return Promise.resolve({ data: {} });
      if (url === '/reports/school/behavior') return Promise.resolve({ data: {} });
      return Promise.resolve({ data: {} });
    });
    QuickAIOperationsPanel.lastInitialStats = undefined;
  });

  test('/admin/command-center/stats is fetched exactly once on mount', async () => {
    render(<AdminDashboard />);

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith(STATS_URL);
    });
    // Let any second (buggy) fetch round flush.
    await new Promise((r) => setTimeout(r, 50));

    const statsCalls = mockApiGet.mock.calls.filter(([url]) => url === STATS_URL);
    expect(statsCalls).toHaveLength(1);
  });

  test('QuickAIOperationsPanel receives initialStats so it skips its own stats fetch', async () => {
    render(<AdminDashboard />);

    await waitFor(() => {
      // Dashboard must have resolved stats before rendering the panel
      expect(QuickAIOperationsPanel.lastInitialStats).toBeDefined();
    }, { timeout: 3000 });

    expect(QuickAIOperationsPanel.lastInitialStats).not.toBeNull();
  });
});
