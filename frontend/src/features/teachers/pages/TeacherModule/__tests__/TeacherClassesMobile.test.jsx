/**
 * Task #303 — TeacherClassesPage mobile contract.
 *
 * At 360px wide the IT classes "list" view must render rows through
 * the shared ResponsiveTable adaptor (mirrors task #280 — notifications
 * + audit log) so we get genuine stacked cards on phones instead of a
 * horizontally overflowing `<table>`. Chips, action buttons, and the
 * row-level click → navigate semantics must stay intact.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('react-router-dom', () => {
  const params = new URLSearchParams('');
  return {
    useNavigate: () => jest.fn(),
    useLocation: () => ({ search: '', pathname: '/teacher/classes' }),
    useSearchParams: () => [params, jest.fn()],
  };
}, { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

const mockTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => mockTranslation,
}));

jest.mock('../SessionsManageTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../StandbyTab', () => ({ __esModule: true, default: () => <div /> }));
jest.mock('../../../components/teacher/SidebarSettingsDialog', () => ({
  __esModule: true, default: () => <div />,
}));

const mockApiGet = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
};
const mockAuth = {
  api: mockApi,
  user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  isRTL: true,
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import TeacherClassesPage from '../TeacherClassesPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiGet.mockReset();
});

test('classes list at 360px renders the ResponsiveTable mobile cards branch', async () => {
  const classes = [
    {
      id: 'c1', name: 'الفصل الأول', grade_name: 'الصف الأول', grade_level: '1',
      subjects: ['رياضيات', 'علوم'], student_count: 12, attendance_rate: 92,
      next_session: { day: 'sunday', start_time: '08:00' },
    },
    {
      id: 'c2', name: 'الفصل الثاني', grade_name: 'الصف الثاني', grade_level: '2',
      subjects: ['لغة عربية'], student_count: 9, attendance_rate: 78,
      next_session: null,
    },
  ];
  mockApiGet.mockImplementation((url) => {
    // IT users load their classes from /classes (workspace classes may
    // have no teacher_assignments rows); keep /teacher/classes/ wired
    // too so the test survives either branch.
    if (typeof url === 'string' && (url === '/classes' || url.startsWith('/teacher/classes/'))) {
      return Promise.resolve({ data: classes });
    }
    if (typeof url === 'string' && url.includes('/class-metrics')) {
      return Promise.resolve({ data: {} });
    }
    if (typeof url === 'string' && url.includes('shared-with-me')) {
      return Promise.resolve({ data: { items: [] } });
    }
    return Promise.resolve({ data: [] });
  });

  render(<TeacherClassesPage />);

  // Wait for the initial fetch to settle, then switch to list view so
  // the ResponsiveTable adaptor is mounted (card mode is the default).
  await waitFor(() => {
    expect(screen.getByText('الفصل الأول')).toBeInTheDocument();
  }, { timeout: 4000 });

  // The view-mode toggle is labelled by the icon and a hidden text;
  // the list-mode button sits next to the card-mode button. We click
  // by class — the list-icon button is the second toggle option.
  const listIconBtn = document.querySelector('button[aria-label="list"]')
    || Array.from(document.querySelectorAll('button')).find(
      (b) => b.querySelector('svg.lucide-list'),
    );
  if (listIconBtn) fireEvent.click(listIconBtn);

  await waitFor(() => {
    expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  }, { timeout: 4000 });

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('الفصل الأول');
  expect(mobile.textContent).toContain('الفصل الثاني');

  // Each row is wired with onRowClick → navigate, so the mobile <li>
  // cards carry the cursor-pointer styling that signals tap intent.
  const cards = mobile.querySelectorAll('li');
  expect(cards.length).toBe(2);
  expect(cards[0].className).toMatch(/cursor-pointer/);
});
