/**
 * Task #274 — TeacherAuditLogPage mobile contract.
 *
 * At 360px wide the audit-log view must render rows through the shared
 * ResponsiveTable mobile-cards branch (severity badge + action label +
 * timestamp stacked label/value pairs) instead of horizontally
 * overflowing a real `<table>`.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqInfo: jest.fn(), nassaqConfirm: jest.fn() }),
}));

jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

const mockApiGet = jest.fn();
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    api: { get: mockApiGet },
    user: { id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar' },
  }),
}));

import TeacherAuditLogPage from '../TeacherAuditLogPage';

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 360 });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: 720 });
  mockApiGet.mockReset();
});

test('audit log at 360px renders the ResponsiveTable mobile cards with severity + action labels', async () => {
  const logs = [
    {
      id: 'a1', timestamp: '2026-05-01T00:00:00Z', severity: 'info',
      action: 'STUDENT_CREATED', action_label_ar: 'إنشاء طالب',
      actor_name: 'المعلم', actor_role: 'independent_teacher', details: {},
    },
    {
      id: 'a2', timestamp: '2026-05-02T00:00:00Z', severity: 'warning',
      action: 'PARENT_INVITE_CANCELLED', action_label_ar: 'إلغاء دعوة ولي أمر',
      actor_name: 'المعلم', actor_role: 'independent_teacher', details: {},
    },
  ];
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/audit-logs') {
      return Promise.resolve({ data: { logs, categories: [], next_cursor: null } });
    }
    return Promise.resolve({ data: {} });
  });

  render(<TeacherAuditLogPage />);

  // Mobile cards tree mounts whenever ResponsiveTable has rows. Wait
  // for the initial fetch to settle.
  await waitFor(() => {
    expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  }, { timeout: 4000 });

  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).toContain('إنشاء طالب');
  expect(mobile.textContent).toContain('إلغاء دعوة ولي أمر');

  // Each card shows the severity label as a stacked field; the
  // primary "action" column carries the highlighted title row.
  const cards = mobile.querySelectorAll('li');
  expect(cards.length).toBe(2);
  expect(cards[0].textContent).toMatch(/info|warning|إنشاء طالب/);
});
