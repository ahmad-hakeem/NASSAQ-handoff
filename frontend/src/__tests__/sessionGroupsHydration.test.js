/**
 * Task #862 — frontend coverage for the live-session group refresh-hydration path.
 *
 * On mount/refresh, SessionTeachPage must:
 *  - load groups from the backend (GET /session/:id/groups) as the authoritative
 *    source, not from sessionStorage alone, and
 *  - persist the resulting groups back to the durable session record
 *    (POST /session/:id/groups), so groups survive a full page refresh.
 *
 * The page is a very large component; we stub its heavy children and contexts
 * and assert on the API contract used by the hydration + persistence loop.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react';

const BACKEND_GROUPS = [
  { id: 'g1', name: 'المتقدمون', color: 'bg-green-600', students: ['s1', 's2'] },
  { id: 'g2', name: 'المتوسطون', color: 'bg-blue-600', students: ['s3'] },
];

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
const mockPut = jest.fn(() => Promise.resolve({ data: {} }));
// Stable api reference — the real AuthContext api is referentially stable, so
// effects depending on `api` must not re-run (and clear their debounce timers)
// on every unrelated re-render.
const mockApi = { get: mockGet, post: mockPost, put: mockPut };

jest.mock('canvas-confetti', () => ({ __esModule: true, default: jest.fn() }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ state: { sessionId: 'sess-1', sessionInfo: {} } }),
}), { virtual: true });

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', teacher_id: 'teacher-1' },
    api: mockApi,
    isRTL: true,
  }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
  useTheme: () => ({ isDark: false, toggleTheme: jest.fn() }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqConfirm: jest.fn() }),
}));

// Stub heavy child components — irrelevant to the group hydration contract.
jest.mock('@/shared/components/SectionErrorBoundary', () => ({ children }) => <>{children}</>);
jest.mock('@/features/teachers/components/teacher/FollowupGradesTable', () => () => null);
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => () => null);
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => () => null);

import SessionTeachPage from '@/features/teachers/pages/TeacherModule/SessionTeachPage';

function mockApiGet(groupsResponse) {
  mockGet.mockImplementation((url) => {
    if (url.endsWith('/groups')) return Promise.resolve({ data: { groups: groupsResponse } });
    if (url.endsWith('/students')) return Promise.resolve({ data: { students: [] } });
    if (url.endsWith('/skills-types') || url.endsWith('/subjects')) return Promise.resolve({ data: [] });
    if (url.endsWith('/activity')) return Promise.resolve({ data: { activity: [] } });
    if (url.endsWith('/notes')) return Promise.resolve({ data: { notes: [] } });
    if (url.endsWith('/followup-record')) return Promise.resolve({ data: { data: {}, absences: {} } });
    return Promise.resolve({ data: {} });
  });
}

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockPut.mockReset();
  // Re-establish resolved promises every test (the project's jest config resets
  // mock implementations between tests).
  mockPost.mockResolvedValue({ data: {} });
  mockPut.mockResolvedValue({ data: {} });
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
});

test('loads groups from the backend on mount (refresh-hydration path)', async () => {
  mockApiGet(BACKEND_GROUPS);
  render(<SessionTeachPage />);
  await waitFor(() => {
    expect(mockGet).toHaveBeenCalledWith('/session/sess-1/groups');
  });
});

test('backend groups become authoritative and are persisted back', async () => {
  mockApiGet(BACKEND_GROUPS);
  render(<SessionTeachPage />);

  await waitFor(() => {
    expect(mockGet).toHaveBeenCalledWith('/session/sess-1/groups');
  });

  // The debounced save effect (real 800ms timer) persists the hydrated groups.
  await waitFor(() => {
    const groupPosts = mockPost.mock.calls.filter(([url]) => url === '/session/sess-1/groups');
    expect(groupPosts.length).toBeGreaterThan(0);
    expect(groupPosts[groupPosts.length - 1][1]).toEqual({ groups: BACKEND_GROUPS });
  }, { timeout: 4000 });
});

test('backend wins over a stale sessionStorage cache', async () => {
  // Seed a stale optimistic cache; the backend value must override it.
  window.sessionStorage.setItem(
    'session_state_sess-1',
    JSON.stringify({ groups: [{ id: 'stale', name: 'stale', color: 'bg-red-600', students: [] }] })
  );
  mockApiGet(BACKEND_GROUPS);
  render(<SessionTeachPage />);

  await waitFor(() => {
    expect(mockGet).toHaveBeenCalledWith('/session/sess-1/groups');
  });

  // The persisted value reflects the backend groups, not the stale cache.
  await waitFor(() => {
    const groupPosts = mockPost.mock.calls.filter(([url]) => url === '/session/sess-1/groups');
    expect(groupPosts.length).toBeGreaterThan(0);
    expect(groupPosts[groupPosts.length - 1][1]).toEqual({ groups: BACKEND_GROUPS });
  }, { timeout: 4000 });
});
