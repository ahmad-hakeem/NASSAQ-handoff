/**
 * Task #273 — IT analytics dashboard.
 *
 * Pins the FE contract for the analytics page so the four panels keep
 * working as the backend shape evolves. Two scenarios:
 *   1. Empty workspace → every panel shows the empty-state copy
 *      (no placeholder zeros, no chart, no exception).
 *   2. Populated workspace → behavior split renders BOTH the
 *      positive and negative legend labels (not the legacy
 *      `category`-keyed bars), the lesson-plan chart renders
 *      generated AND saved series, and the absence top table
 *      shows `<rate>% (absent/total)` (not the legacy raw count).
 */
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';

// Note: jest.mock factories are hoisted above imports, so JSX inside
// them is parsed without project React-runtime config — use
// React.createElement (matching LessonPlannerDeepLink.test.jsx).
jest.mock('react-router-dom', () => ({
  useLocation: () => ({ search: '', pathname: '/teacher/analytics' }),
  useNavigate: () => () => {},
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => {
  const R = require('react');
  return { Sidebar: ({ children }) => R.createElement('div', null, children) };
});

// Stable hook returns: every fresh object/function returned from a
// hook would re-trigger useCallback/useEffect deps in the page and
// loop the loading spinner forever under jest's fake renders.
const mockTheme = { isRTL: true };
const mockT = (k) => k;
const mockTranslation = { t: mockT, isRTL: true };
jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => mockTheme,
  useTranslation: () => mockTranslation,
}));

const mockApiGet = jest.fn();
// Stable singletons so useEffect deps that close over `api` don't
// retrigger on every render (which would loop the loading spinner).
const mockStableApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockStableAuth = { api: mockStableApi, user: { id: 'u-it-1', role: 'independent_teacher' } };
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => mockStableAuth,
}));

const mockNassaqAlert = {
  nassaqError: jest.fn(),
  nassaqInfo: jest.fn(),
  nassaqConfirm: jest.fn(),
};
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockNassaqAlert,
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

// Recharts pulls heavy DOM deps under jsdom; render simple stand-ins
// so the legend / dataKey contracts can still be asserted.
jest.mock('recharts', () => {
  const R = require('react');
  const wrap = (testid) => ({ children }) =>
    R.createElement('div', { 'data-testid': testid }, children);
  const series = ({ name, dataKey }) =>
    R.createElement('div', { 'data-series': dataKey }, name);
  return {
    ResponsiveContainer: ({ children }) => R.createElement('div', null, children),
    AreaChart: wrap('area-chart'),
    BarChart: wrap('bar-chart'),
    LineChart: wrap('line-chart'),
    Area: series,
    Bar: series,
    Line: series,
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});

import TeacherAnalyticsPage from '../TeacherAnalyticsPage';

beforeEach(() => {
  mockApiGet.mockReset();
});

function emptyEnvelope(extra = {}) {
  return {
    data: {
      range: { from: 'a', to: 'b' },
      class_id: null,
      attendance: [],
      behavior: [],
      lesson_plans: [],
      top_students_absence: [],
      top_students_behavior: [],
      top_classes_attendance: [],
      ...extra,
    },
  };
}

test('empty workspace: every panel renders its empty-state copy', async () => {
  mockApiGet.mockImplementation((url) => {
    if (url === '/classes') return Promise.resolve({ data: { classes: [] } });
    if (url === '/independent-teacher/analytics') return Promise.resolve(emptyEnvelope());
    return Promise.resolve({ data: {} });
  });

  render(<TeacherAnalyticsPage />);

  await waitFor(() => screen.getByTestId('analytics-attendance-empty'));
  expect(screen.getByTestId('analytics-behavior-empty')).toBeTruthy();
  expect(screen.getByTestId('analytics-lp-empty')).toBeTruthy();
  expect(screen.getByTestId('analytics-top-absence')).toBeTruthy();
  expect(screen.getByTestId('analytics-top-behavior')).toBeTruthy();
  expect(screen.getByTestId('analytics-top-classes')).toBeTruthy();
});

test('populated workspace: behavior split + lesson-plan dual series + absence-rate column', async () => {
  mockApiGet.mockImplementation((url) => {
    if (url === '/classes') return Promise.resolve({ data: { classes: [] } });
    if (url === '/independent-teacher/analytics') {
      return Promise.resolve(emptyEnvelope({
        attendance: [{ day: '2026-05-01', present: 3, absent: 1, late: 0, excused: 0, total: 4 }],
        behavior: [{ week: '2026-04-27', positive: 2, negative: 1 }],
        lesson_plans: [{ day: '2026-05-01', generated: 2, saved: 1 }],
        top_students_absence: [
          { student_id: 's1', name: 'Alpha', absent_count: 3, total_count: 4, absence_rate: 0.75 },
        ],
      }));
    }
    return Promise.resolve({ data: {} });
  });

  render(<TeacherAnalyticsPage />);

  // Wait for the populated absence row to land — that proves the api
  // call has resolved and the page has re-rendered with `data`.
  const top = await screen.findByTestId('analytics-top-absence');
  await waitFor(() => within(top).getByText('Alpha'));
  expect(within(top).getByText(/75%\s*\(3\/4\)/)).toBeTruthy();

  // Behavior chart must use the positive/negative split (not the
  // legacy `category`-keyed bars).
  const bar = screen.getByTestId('bar-chart');
  expect(within(bar).getByText('teacherAnalyticsBehaviorPositive')).toBeTruthy();
  expect(within(bar).getByText('teacherAnalyticsBehaviorNegative')).toBeTruthy();

  // Lesson plan chart must render BOTH `generated` and `saved` series.
  const line = screen.getByTestId('line-chart');
  expect(within(line).getByText('teacherAnalyticsLessonPlansGenerated')).toBeTruthy();
  expect(within(line).getByText('teacherAnalyticsLessonPlansSaved')).toBeTruthy();
});
