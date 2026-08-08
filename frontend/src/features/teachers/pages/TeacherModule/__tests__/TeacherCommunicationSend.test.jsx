/**
 * School-teacher "التواصل والإشعارات" send-flow contract.
 *
 * 1. The الإدارة (Management) cohort must post recipient_role: 'admin' —
 *    the backend's canonical alias that resolves the whole management
 *    cohort (school_principal ∪ school_admin ∪ school_sub_admin).
 *    Sending the literal 'school_principal' 404s in tenants whose
 *    leadership rows are provisioned under 'school_admin' (the
 *    "حدث خطأ أثناء الإرسال" bug).
 * 2. The طاقم المدرسة (staff) cohort is removed: its four pseudo-roles
 *    (vice_principal/counselor/activity_leader/gifted_coordinator) never
 *    existed in users.role — they all collapsed to 'school_sub_admin'
 *    and 404'd the same way. The selector must only show cohorts the
 *    backend can actually resolve: parents + admin.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// jsdom has no scrollIntoView; the wizard auto-scrolls between steps.
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ search: '' }),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqInfo: jest.fn() }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), message: jest.fn() },
}));

// Heavy sibling pages the dispatcher wrapper imports — not under test.
jest.mock('../IndependentTeacherCommunicationPage', () => () => null);
jest.mock('../UnifiedCommunicationsHub', () => () => null);

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApiPost = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', role: 'teacher', teacher_id: 't1' },
    api: { get: mockApiGet, put: mockApiPut, post: mockApiPost },
    isRTL: true,
  }),
}));

import TeacherCommunicationPage from '../TeacherCommunicationPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url.startsWith('/teacher/classes/')) return Promise.resolve({ data: [] });
    if (url.startsWith('/notifications')) return Promise.resolve({ data: [] });
    return Promise.resolve({ data: [] });
  });
  mockApiPut.mockResolvedValue({ data: {} });
  mockApiPost.mockResolvedValue({ data: { success: true } });
});

/** Renders the page and walks to the wizard's Step 2 (recipients). */
async function openWizardWithTemplate(templateKey) {
  render(<TeacherCommunicationPage />);
  // Sections view → communication hub.
  const hubBtn = await screen.findByText('communicationCenterSection', {}, { timeout: 4000 });
  fireEvent.click(hubBtn.closest('button'));
  // Hub → wizard.
  const wizardBtn = await screen.findByRole('button', { name: /sendNotificationBtn/ });
  fireEvent.click(wizardBtn);
  // Step 1: pick a template (subject/body are prefilled from its keys).
  const templateBtn = await screen.findByText(templateKey);
  fireEvent.click(templateBtn.closest('button'));
  await screen.findByText('recipientCategories');
}

test('sending to الإدارة posts the canonical admin alias, never a literal principal role', async () => {
  await openWizardWithTemplate('meetingInvitation');

  fireEvent.click(screen.getByText('adminCategory').closest('button'));

  // Step 3 reveals (recipient auto-selected as the general admin notice).
  const sendBtn = await screen.findByRole('button', { name: /send$/ });
  await waitFor(() => expect(sendBtn).not.toBeDisabled());
  fireEvent.click(sendBtn);

  await waitFor(() => expect(mockApiPost).toHaveBeenCalledTimes(1));
  const [url, payload] = mockApiPost.mock.calls[0];
  expect(url).toBe('/notifications');
  expect(payload.recipient_role).toBe('admin');
  expect(payload.template_id).toBe('meeting');
  expect(payload.title).toBeTruthy();
  expect(payload.message).toBeTruthy();
});

test('the unsupported طاقم المدرسة cohort no longer appears in the recipient selector', async () => {
  await openWizardWithTemplate('examNotice');

  // Supported cohorts render…
  expect(screen.getByText('parentsCategory')).toBeInTheDocument();
  expect(screen.getByText('adminCategory')).toBeInTheDocument();
  // …the phantom staff cohort and its pseudo-role sub-options do not.
  expect(screen.queryByText('schoolStaffCategory')).not.toBeInTheDocument();
  expect(screen.queryByText('vicePrincipal')).not.toBeInTheDocument();
  expect(screen.queryByText('studentCounselor')).not.toBeInTheDocument();
  expect(screen.queryByText('activityLeader')).not.toBeInTheDocument();
  expect(screen.queryByText('giftedCoordinator')).not.toBeInTheDocument();
});
