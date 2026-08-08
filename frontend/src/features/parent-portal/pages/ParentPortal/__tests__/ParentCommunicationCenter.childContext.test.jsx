/**
 * Parent Communication Center — required child context (spec 2026-07-10).
 *
 * Pins the frontend contract:
 *   1. With multiple children, no child is preselected: the teacher step shows
 *      the "select the child first" hint and the send button stays disabled
 *      for BOTH recipient types until a child is chosen.
 *   2. The teacher dropdown is child-scoped — only teachers whose `child_ids`
 *      include the selected child are offered, and switching children resets
 *      the previously selected teacher.
 *   3. The quick-message payload always carries `student_id` (teacher AND
 *      admin recipients); a single child is auto-selected.
 *   4. Inbox rows with `student_name` render the "بخصوص: {name}" badge.
 *
 * Radix Select is stubbed with a native <select> so options are queryable in
 * jsdom without pointer-event gymnastics.
 */
import React from 'react';
import { render, screen, act, fireEvent, within } from '@testing-library/react';

// --- Router shim -------------------------------------------------------------
jest.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
}), { virtual: true });

// --- Theme + i18n shim ---------------------------------------------------------
// Stable refs are mandatory: `t` is a dependency of the component's init
// effect, so a fresh function per render would refire the fetch effect forever
// (see .agents/memory/auth-mock-stable-refs.md).
const mockT = (k) => ({ regardingStudent: 'بخصوص: {name}' }[k] || k);
const mockThemeValue = { isRTL: true, isDark: false };
const mockTranslationValue = { t: mockT, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => mockThemeValue,
  useTranslation: () => mockTranslationValue,
}));

// --- Auth shim — stable refs (see .agents/memory/auth-mock-stable-refs.md) ----
// CRA sets `resetMocks: true`, so implementations passed to jest.fn(impl) are
// wiped before every test — they must be (re)installed in beforeEach.
let mockRecipientsPayload = { teachers: [], children: [] };
let mockMessagesPayload = { messages: [] };
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockStableApi = { get: mockApiGet, post: mockApiPost };
const installApiImplementations = () => {
  mockApiGet.mockImplementation((url) => {
    if (url.includes('open-requests-count')) return Promise.resolve({ data: { total_open: 0 } });
    if (url.includes('message-recipients/teachers')) return Promise.resolve({ data: mockRecipientsPayload });
    if (url.includes('/messages')) return Promise.resolve({ data: mockMessagesPayload });
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockImplementation(() => Promise.resolve({ data: { success: true } }));
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockStableApi, user: { id: 'parent-1', role: 'parent' } }),
}));

// --- Alert dialog shim ---------------------------------------------------------
const mockNassaqError = jest.fn();
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

// --- Heavy subtrees — passthrough stubs ---------------------------------------
jest.mock('../../../components/portal/PortalLayout', () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="portal-layout">{children}</div>,
}));
jest.mock('@/features/communication/pages/NotificationsPage', () => ({
  NotificationsPage: () => <div data-testid="notifications-page" />,
}));
jest.mock('../ParentAbsenceExcusePage', () => ({
  __esModule: true,
  default: () => <div data-testid="excuses-page" />,
}));

// --- Radix Select → native <select> shim --------------------------------------
jest.mock('../../../components/ui/select', () => ({
  Select: ({ value, onValueChange, children }) => (
    <select
      data-testid="teacher-select"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    >
      <option value="" />
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }) => <>{children}</>,
  SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
}));

// IMPORTANT — import the component AFTER all mocks are registered.
const ParentCommunicationCenter = require('../ParentCommunicationCenter').default;

const TWO_CHILDREN = {
  children: [
    { student_id: 's1', name: 'أحمد' },
    { student_id: 's2', name: 'سارة' },
  ],
  teachers: [
    { recipient_user_id: 't1', teacher_name: 'المعلم الأول', child_ids: ['s1'] },
    { recipient_user_id: 't2', teacher_name: 'المعلم الثاني', child_ids: ['s2'] },
    { recipient_user_id: 't3', teacher_name: 'المعلم المشترك', child_ids: ['s1', 's2'] },
  ],
};

const getSendButton = () =>
  screen.getAllByText('sendMessage')
    .map((el) => el.closest('button'))
    .find((b) => b && b.className.includes('w-full'));

async function renderPage() {
  await act(async () => {
    render(<ParentCommunicationCenter />);
  });
}

beforeEach(() => {
  installApiImplementations();
  mockRecipientsPayload = TWO_CHILDREN;
  mockMessagesPayload = { messages: [] };
});

describe('ParentCommunicationCenter — required child context', () => {
  it('gates the teacher step and the send button until a child is selected', async () => {
    await renderPage();

    // No auto-select with two children → hint shown, no teacher dropdown yet.
    expect(screen.getByText('selectChildFirstHint')).toBeInTheDocument();
    expect(screen.queryByTestId('teacher-select')).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('writeYourMessageHere'), {
      target: { value: 'رسالة تجريبية' },
    });
    expect(getSendButton()).toBeDisabled();

    // Admin recipient is gated too — child still required.
    fireEvent.click(screen.getByText('recipientAdmin'));
    expect(getSendButton()).toBeDisabled();

    fireEvent.click(screen.getByText('سارة'));
    expect(getSendButton()).not.toBeDisabled();
  });

  it('offers only the selected child teachers and resets the teacher on child change', async () => {
    await renderPage();

    fireEvent.click(screen.getByText('أحمد'));
    let select = screen.getByTestId('teacher-select');
    let options = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(options).toEqual(expect.arrayContaining(['المعلم الأول', 'المعلم المشترك']));
    expect(options.join()).not.toContain('المعلم الثاني');

    fireEvent.change(select, { target: { value: 't1' } });
    expect(select.value).toBe('t1');

    // Switching child invalidates the previous teacher selection.
    fireEvent.click(screen.getByText('سارة'));
    select = screen.getByTestId('teacher-select');
    expect(select.value).toBe('');
    options = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(options).toEqual(expect.arrayContaining(['المعلم الثاني', 'المعلم المشترك']));
    expect(options.join()).not.toContain('المعلم الأول');
  });

  it('sends student_id with a teacher message', async () => {
    await renderPage();

    fireEvent.click(screen.getByText('أحمد'));
    fireEvent.change(screen.getByTestId('teacher-select'), { target: { value: 't3' } });
    fireEvent.change(screen.getByPlaceholderText('writeYourMessageHere'), {
      target: { value: 'استفسار عن الواجب' },
    });
    await act(async () => {
      fireEvent.click(getSendButton());
    });

    expect(mockApiPost).toHaveBeenCalledWith('/parent-portal/quick-message', {
      message_type: 'note',
      recipient_type: 'teacher',
      content: 'استفسار عن الواجب',
      student_id: 's1',
      recipient_user_id: 't3',
    });
  });

  it('auto-selects a single child and sends student_id with an admin message', async () => {
    mockRecipientsPayload = {
      children: [{ student_id: 's9', name: 'خالد' }],
      teachers: [{ recipient_user_id: 't1', teacher_name: 'المعلم الأول', child_ids: ['s9'] }],
    };
    await renderPage();

    fireEvent.click(screen.getByText('recipientAdmin'));
    fireEvent.change(screen.getByPlaceholderText('writeYourMessageHere'), {
      target: { value: 'ملاحظة للإدارة' },
    });
    expect(getSendButton()).not.toBeDisabled();
    await act(async () => {
      fireEvent.click(getSendButton());
    });

    expect(mockApiPost).toHaveBeenCalledWith('/parent-portal/quick-message', {
      message_type: 'note',
      recipient_type: 'admin',
      content: 'ملاحظة للإدارة',
      student_id: 's9',
    });
  });

  it('shows the "بخصوص" student badge on inbox rows that carry student_name', async () => {
    mockMessagesPayload = {
      messages: [
        {
          id: 'm1', content: 'شكراً لتواصلكم', student_name: 'أحمد',
          is_sent: true, read_status: true, status: 'sent',
          created_at: '2026-07-10T08:00:00Z',
        },
      ],
    };
    await renderPage();

    fireEvent.click(screen.getByText('conversationInbox'));
    expect(screen.getByText('بخصوص: أحمد')).toBeInTheDocument();
  });
});
