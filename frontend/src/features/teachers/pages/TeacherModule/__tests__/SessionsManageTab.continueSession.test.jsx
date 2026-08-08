/**
 * Regression — فصولي → إدارة الحصص → "متابعة الحصة" (Continue Session).
 *
 * A teacher who exits an active session with the browser back button (no
 * explicit end) later reopens it from Session Management and clicks
 * Continue Session. The button used to navigate to `/teacher/session/{id}`,
 * a route that does not exist, so the `path="*"` fallback bounced the
 * teacher to the landing page.
 *
 * The contract pinned here:
 *  - teaching-stage sessions (in_progress / teaching_in_progress /
 *    interaction_running / session_review) resume on the live teach page
 *    (`/teacher/session/teach`) with the sessionId in navigation state —
 *    the exact shape SessionTeachPage bootstraps from;
 *  - attendance-stage sessions (session_opened / attendance_in_progress /
 *    attendance_approved) re-enter through `/teacher/session/start` with a
 *    lesson payload, whose POST /session/start resumes the same active
 *    session and lands on the attendance step.
 *
 * The flow is role-agnostic: school teachers and independent teachers both
 * reach this tab through فصولي → إدارة الحصص.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

const mockAlert = { nassaqError: jest.fn(), nassaqInfo: jest.fn(), nassaqConfirm: jest.fn() };
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
}));

const mockTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => mockTranslation,
}));

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

const mockApiGet = jest.fn();
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockAuth = {
  api: mockApi,
  user: { id: 'u-1', teacher_id: 't-1', role: 'teacher', preferred_language: 'ar' },
  isRTL: true,
};
jest.mock('@/shared/contexts/AuthContext', () => ({ useAuth: () => mockAuth }));

import SessionsManageTab from '../SessionsManageTab';

const baseSession = {
  id: 'sess-1',
  schedule_session_id: 'sched-9',
  class_id: 'cls-3',
  subject_id: 'subj-7',
  class_name: 'الصف الثالث/1',
  subject_name: 'رياضيات',
  date: '2026-07-19',
  start_time: '2026-07-19T07:30:00+00:00',
  created_at: '2026-07-19T07:30:00+00:00',
};

function mockHistory(session) {
  mockApiGet.mockImplementation((url) => {
    if (typeof url === 'string' && url.includes('/sessions-history')) {
      return Promise.resolve({ data: { sessions: [session], total: 1, pages: 1 } });
    }
    return Promise.resolve({ data: {} });
  });
}

async function openDetailAndContinue(session) {
  mockHistory(session);
  render(<SessionsManageTab />);
  const card = await screen.findByText(session.subject_name);
  fireEvent.click(card);
  const btn = await screen.findByText('continueSession');
  fireEvent.click(btn);
}

beforeEach(() => {
  mockApiGet.mockReset();
  mockNavigate.mockReset();
});

test('teaching-stage session resumes on the live teach page with sessionId state', async () => {
  await openDetailAndContinue({ ...baseSession, status: 'teaching_in_progress' });

  await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
  const [path, opts] = mockNavigate.mock.calls[0];
  expect(path).toBe('/teacher/session/teach');
  expect(opts?.state?.sessionId).toBe('sess-1');
  expect(opts?.state?.sessionInfo?.class_name).toBe('الصف الثالث/1');
  expect(opts?.state?.sessionInfo?.subject_name).toBe('رياضيات');
});

test('session_review session also resumes on the teach page', async () => {
  await openDetailAndContinue({ ...baseSession, status: 'session_review' });

  await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
  const [path, opts] = mockNavigate.mock.calls[0];
  expect(path).toBe('/teacher/session/teach');
  expect(opts?.state?.sessionId).toBe('sess-1');
});

test('attendance-stage session re-enters through the session start page', async () => {
  await openDetailAndContinue({ ...baseSession, status: 'attendance_in_progress' });

  await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
  const [path, opts] = mockNavigate.mock.calls[0];
  expect(path).toBe('/teacher/session/start');
  expect(opts?.state?.lesson?.schedule_session_id).toBe('sched-9');
  expect(opts?.state?.lesson?.class_id).toBe('cls-3');
  expect(opts?.state?.lesson?.subject_id).toBe('subj-7');
});

test('never navigates to the non-existent /teacher/session/{id} route', async () => {
  await openDetailAndContinue({ ...baseSession, status: 'in_progress' });

  await waitFor(() => expect(mockNavigate).toHaveBeenCalled());
  const [path] = mockNavigate.mock.calls[0];
  expect(path).not.toBe('/teacher/session/sess-1');
  expect(path).toBe('/teacher/session/teach');
});

test('completed session shows no continue button', async () => {
  mockHistory({ ...baseSession, status: 'completed' });
  render(<SessionsManageTab />);
  const card = await screen.findByText('رياضيات');
  fireEvent.click(card);
  await waitFor(() => expect(screen.queryByText('close')).toBeInTheDocument());
  expect(screen.queryByText('continueSession')).not.toBeInTheDocument();
});
