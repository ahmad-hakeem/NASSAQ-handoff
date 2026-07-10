/**
 * Cross-role notification quick-preview dialog contract.
 *
 * Pins the parent-pattern guarantees every surface relies on:
 *  1. Closed state renders ZERO DOM (host viewport snapshots stay stable).
 *  2. The full message renders un-clamped (whitespace-pre-wrap, no line-clamp).
 *  3. The deep link is an explicit button — clicking it closes first, then
 *     navigates with the notification's URL.
 *  4. No action button when the notification has no URL or no onNavigate.
 *  5. dir is set explicitly on the portal content (RTL correctness).
 *  6. Adapters normalize both taxonomies (standard action_url/notification_type
 *     vs IT cta_url/category).
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { NotificationDetailDialog } from '../NotificationDetailDialog';
import {
  normalizeStandardNotification,
  normalizeItNotification,
  notificationTypeConfig,
  itCategoryConfig,
} from '../notificationDisplay';

const LONG_MESSAGE = 'سطر أول طويل جدًا في نص الإشعار.\n'.repeat(12) + 'النهاية.';

const standardRow = {
  id: 'n1',
  title: 'تعميم عاجل من الإدارة',
  title_en: 'Urgent circular',
  message: LONG_MESSAGE,
  message_en: 'Long english body',
  notification_type: 'circular',
  priority: 'high',
  read_status: false,
  action_url: '/teacher/schedule',
  sender_name: 'إدارة المدرسة',
  created_at: '2026-07-09T08:30:00Z',
};

const itRow = {
  id: 'it1',
  title: 'دعوة تعاون جديدة',
  message: 'دعاك معلم آخر للتعاون في فصل.',
  category: 'collab_invite',
  is_read: false,
  cta_url: '/teacher/collaboration',
  created_at: '2026-07-09T10:00:00Z',
};

test('renders nothing when notification is null', () => {
  const { container } = render(
    <NotificationDetailDialog notification={null} isRTL onClose={jest.fn()} onNavigate={jest.fn()} />
  );
  expect(container).toBeEmptyDOMElement();
  expect(screen.queryByTestId('notification-detail-dialog')).not.toBeInTheDocument();
});

test('renders the FULL message un-clamped with pre-wrap', () => {
  render(
    <NotificationDetailDialog
      notification={normalizeStandardNotification(standardRow)}
      isRTL
      onClose={jest.fn()}
    />
  );
  const body = screen.getByTestId('detail-message-body');
  expect(body.textContent).toContain('النهاية.');
  expect(body.textContent.length).toBeGreaterThanOrEqual(LONG_MESSAGE.length);
  expect(body.className).toContain('whitespace-pre-wrap');
  expect(body.className).not.toContain('line-clamp');
});

test('action button closes then navigates with the url', () => {
  const onClose = jest.fn();
  const onNavigate = jest.fn();
  render(
    <NotificationDetailDialog
      notification={normalizeStandardNotification(standardRow)}
      isRTL
      onClose={onClose}
      onNavigate={onNavigate}
    />
  );
  fireEvent.click(screen.getByTestId('detail-action-btn'));
  expect(onClose).toHaveBeenCalled();
  expect(onNavigate).toHaveBeenCalledWith('/teacher/schedule');
});

test('no action button without a url, and none without onNavigate', () => {
  const noUrl = normalizeStandardNotification({ ...standardRow, action_url: null });
  const { rerender } = render(
    <NotificationDetailDialog notification={noUrl} isRTL onClose={jest.fn()} onNavigate={jest.fn()} />
  );
  expect(screen.queryByTestId('detail-action-btn')).not.toBeInTheDocument();

  rerender(
    <NotificationDetailDialog
      notification={normalizeStandardNotification(standardRow)}
      isRTL
      onClose={jest.fn()}
    />
  );
  expect(screen.queryByTestId('detail-action-btn')).not.toBeInTheDocument();
});

test('sets dir explicitly for RTL portals', () => {
  render(
    <NotificationDetailDialog
      notification={normalizeStandardNotification(standardRow)}
      isRTL
      onClose={jest.fn()}
    />
  );
  expect(screen.getByTestId('notification-detail-dialog')).toHaveAttribute('dir', 'rtl');
});

test('standard adapter resolves type meta and passes priority/sender through', () => {
  const n = normalizeStandardNotification(standardRow);
  expect(n.typeMeta).toBe(notificationTypeConfig.circular);
  expect(n.priority).toBe('high');
  expect(n.senderName).toBe('إدارة المدرسة');
  expect(n.actionUrl).toBe('/teacher/schedule');
  // unknown type falls back to system
  expect(normalizeStandardNotification({ ...standardRow, notification_type: 'zzz' }).typeMeta)
    .toBe(notificationTypeConfig.system);
});

test('IT adapter maps cta_url and category taxonomy', () => {
  const n = normalizeItNotification(itRow);
  expect(n.actionUrl).toBe('/teacher/collaboration');
  expect(n.typeMeta).toBe(itCategoryConfig.collab_invite);
  expect(normalizeItNotification({ ...itRow, category: 'zzz' }).typeMeta)
    .toBe(itCategoryConfig.general);
  // dialog renders the IT row with its category badge
  render(
    <NotificationDetailDialog notification={n} isRTL onClose={jest.fn()} onNavigate={jest.fn()} />
  );
  expect(screen.getByTestId('notification-detail-dialog')).toBeInTheDocument();
  expect(screen.getByText('تعاون')).toBeInTheDocument();
});
