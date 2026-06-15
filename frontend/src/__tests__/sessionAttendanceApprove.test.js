/**
 * Task #929 — frontend coverage for finalizing the live-session attendance
 * register from SessionTeachPage.
 *
 * Locks in the #928 fix at the page level: closing the in-class attendance modal
 * AFTER a status change must approve the canonical session drafts
 * (POST /session/:id/attendance/approve) — which also syncs the school-wide
 * daily table — and then refresh the roster (GET /session/:id/students) and live
 * metrics (GET /session/:id/live-metrics) so the summary and every live panel
 * read one source of truth. Closing with no change must NOT re-approve (the
 * dirty-ref guard).
 *
 * SessionTeachPage is a very large component; we stub its heavy children and
 * contexts and assert on the API contract used by the finalize loop.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
const mockPut = jest.fn(() => Promise.resolve({ data: {} }));
const mockApi = { get: mockGet, post: mockPost, put: mockPut };

jest.mock('canvas-confetti', () => ({ __esModule: true, default: jest.fn() }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({
    state: { sessionId: 'sess-1', sessionInfo: { class_id: 'c1' } },
  }),
}), { virtual: true });

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', teacher_id: 'teacher-1' },
    api: mockApi,
    isRTL: true,
  }),
}));

jest.mock('../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
  useTheme: () => ({ isDark: false, toggleTheme: jest.fn() }),
}));

jest.mock('../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqConfirm: jest.fn() }),
}));

// Stub heavy child components — irrelevant to the finalize contract.
jest.mock('../components/SectionErrorBoundary', () => ({ children }) => <>{children}</>);
jest.mock('../components/teacher/FollowupGradesTable', () => () => null);
jest.mock('../components/teacher/SidebarSettingsDialog', () => () => null);

// The attendance register itself is unit-tested separately; here we only need it
// to surface a control that fires `onStatusChange` (marking the register dirty).
jest.mock('../components/teacher/InlineAttendanceTable', () => (props) => (
  <button
    data-testid="mock-mark-absent"
    onClick={() => props.onStatusChange && props.onStatusChange('s1', 'absent')}
  >
    mark absent
  </button>
));

// Mock the dialog primitive so the modal renders its children when open and we
// can drive `onOpenChange(false)` (the close path that triggers finalize).
jest.mock('../components/ui/dialog', () => {
  const Passthrough = ({ children }) => <div>{children}</div>;
  return {
    Dialog: ({ open, onOpenChange, children }) =>
      open ? (
        <div>
          <button data-testid="dialog-close" onClick={() => onOpenChange(false)}>
            close
          </button>
          {children}
        </div>
      ) : null,
    DialogPortal: Passthrough,
    DialogOverlay: Passthrough,
    DialogTrigger: Passthrough,
    DialogClose: Passthrough,
    DialogContent: Passthrough,
    DialogHeader: Passthrough,
    DialogFooter: Passthrough,
    DialogTitle: Passthrough,
    DialogDescription: Passthrough,
  };
});

import SessionTeachPage from '../pages/TeacherModule/SessionTeachPage';

const countGetCalls = (suffix) =>
  mockGet.mock.calls.filter(([url]) => typeof url === 'string' && url.endsWith(suffix)).length;
const countApproveCalls = () =>
  mockPost.mock.calls.filter(([url]) => url === '/session/sess-1/attendance/approve').length;

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockPut.mockReset();
  // Catch-all: every session bootstrap GET resolves to an inert payload so the
  // page mounts without navigating away or throwing.
  mockGet.mockImplementation((url) => {
    if (url.endsWith('/students')) return Promise.resolve({ data: { students: [] } });
    if (url.endsWith('/groups')) return Promise.resolve({ data: { groups: [] } });
    if (url.endsWith('/live-metrics')) return Promise.resolve({ data: {} });
    if (url.endsWith('/skills-types') || url.endsWith('/subjects')) return Promise.resolve({ data: [] });
    if (url.endsWith('/activity')) return Promise.resolve({ data: { activity: [] } });
    if (url.endsWith('/notes')) return Promise.resolve({ data: { notes: [] } });
    if (url.endsWith('/followup-record')) return Promise.resolve({ data: { data: {}, absences: {} } });
    if (url.endsWith('/grade-columns')) return Promise.resolve({ data: { columns: [] } });
    if (url.endsWith('/undo/peek')) return Promise.resolve({ data: { has_reversible: false } });
    if (url === '/session/sess-1') return Promise.resolve({ data: { status: 'active' } });
    return Promise.resolve({ data: {} });
  });
  mockPost.mockResolvedValue({ data: {} });
  mockPut.mockResolvedValue({ data: {} });
  try { window.sessionStorage.clear(); } catch { /* ignore */ }
});

test('closing the attendance modal after a change approves the register and refreshes roster/metrics', async () => {
  render(<SessionTeachPage />);

  const openBtn = await screen.findByTestId('open-attendance-modal-btn');
  fireEvent.click(openBtn);

  // Make a change inside the register so the dirty-ref is set.
  const markAbsent = await screen.findByTestId('mock-mark-absent');
  fireEvent.click(markAbsent);

  const studentsBefore = countGetCalls('/students');
  const metricsBefore = countGetCalls('/live-metrics');

  // Close the modal — this is the finalize trigger.
  fireEvent.click(screen.getByTestId('dialog-close'));

  await waitFor(() => {
    expect(countApproveCalls()).toBe(1);
  });

  // Finalize must refresh the roster and the live metrics so the summary agrees
  // with the persisted register.
  await waitFor(() => {
    expect(countGetCalls('/students')).toBeGreaterThan(studentsBefore);
    expect(countGetCalls('/live-metrics')).toBeGreaterThan(metricsBefore);
  });
});

test('closing the attendance modal with no change does not re-approve (dirty-ref guard)', async () => {
  render(<SessionTeachPage />);

  const openBtn = await screen.findByTestId('open-attendance-modal-btn');
  fireEvent.click(openBtn);

  // Ensure the modal is open, then close it without toggling anything.
  await screen.findByTestId('mock-mark-absent');
  fireEvent.click(screen.getByTestId('dialog-close'));

  // Give any (incorrect) finalize call a chance to fire.
  await new Promise((r) => setTimeout(r, 50));
  expect(countApproveCalls()).toBe(0);
});
