/**
 * Task #929 — frontend coverage for the live-session attendance register.
 *
 * Locks in the #928 fix: when `InlineAttendanceTable` is rendered inside a live
 * class session (a `sessionId` is provided), toggling a student's status must
 *  - persist to the canonical session-attendance store via
 *    PUT /session/:id/attendance/:studentId (NOT POST /attendance/bulk, which is
 *    the school-wide daily table used outside a session), and
 *  - seed/override the displayed status from the session drafts the parent
 *    passes down (server-sourced `attendance_status`).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockGet = jest.fn();
const mockPost = jest.fn(() => Promise.resolve({ data: {} }));
const mockPut = jest.fn(() => Promise.resolve({ data: {} }));
const mockApi = { get: mockGet, post: mockPost, put: mockPut };

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockApi, isRTL: true }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

import InlineAttendanceTable from '@/features/teachers/components/teacher/InlineAttendanceTable';

const STUDENTS = [
  { id: 's1', full_name: 'علي', attendance_status: 'present' },
  { id: 's2', full_name: 'سارة', attendance_status: 'absent' },
];

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockPut.mockReset();
  mockPost.mockResolvedValue({ data: {} });
  mockPut.mockResolvedValue({ data: {} });
  // Daily-table history fetch on mount — irrelevant to the session contract.
  mockGet.mockResolvedValue({ data: [] });
});

test('session mode: toggling status calls PUT /session/:id/attendance/:studentId, not POST /attendance/bulk', async () => {
  render(
    <InlineAttendanceTable
      classId="c1"
      sessionId="sess-1"
      students={STUDENTS}
      showHistory={false}
    />,
  );

  const absentBtn = await screen.findByTestId('attendance-absent-s1');
  fireEvent.click(absentBtn);

  await waitFor(() => {
    expect(mockPut).toHaveBeenCalledWith('/session/sess-1/attendance/s1', {
      status: 'absent',
    });
  });

  // The school-wide daily-table write path must NOT be used inside a session.
  expect(
    mockPost.mock.calls.some(([url]) => url === '/attendance/bulk'),
  ).toBe(false);
});

test('session mode: displayed status seeds from session drafts and overrides after a toggle', async () => {
  render(
    <InlineAttendanceTable
      classId="c1"
      sessionId="sess-1"
      students={STUDENTS}
      showHistory={false}
    />,
  );

  // s2 seeds from its server-sourced draft (absent) — the absent control is active.
  const s2Absent = await screen.findByTestId('attendance-absent-s2');
  expect(s2Absent.className).toContain('bg-red-500');

  // s1 seeds present — flip it to absent and the displayed state must follow.
  const s1Absent = await screen.findByTestId('attendance-absent-s1');
  fireEvent.click(s1Absent);

  await waitFor(() => {
    expect(
      screen.getByTestId('attendance-absent-s1').className,
    ).toContain('bg-red-500');
  });
});

test('non-session mode: toggling status uses the daily-table POST /attendance/bulk path', async () => {
  render(
    <InlineAttendanceTable classId="c1" students={STUDENTS} showHistory={false} />,
  );

  const absentBtn = await screen.findByTestId('attendance-absent-s1');
  fireEvent.click(absentBtn);

  await waitFor(() => {
    const bulk = mockPost.mock.calls.find(([url]) => url === '/attendance/bulk');
    expect(bulk).toBeTruthy();
    expect(bulk[1]).toMatchObject({
      class_id: 'c1',
      records: [{ student_id: 's1', status: 'absent' }],
    });
  });

  // The session-attendance store must NOT be touched outside a live session.
  expect(mockPut).not.toHaveBeenCalled();
});
