import {
  normalizeNotificationType,
  normalizeNotificationPriority,
  notificationTypeConfig,
  priorityConfig,
} from '../notificationDisplay';

describe('normalizeNotificationType', () => {
  it('keeps canonical types unchanged', () => {
    ['system', 'attendance', 'schedule', 'assessment', 'behaviour',
      'communication', 'announcement', 'circular', 'other', 'circular_ack']
      .forEach(t => expect(normalizeNotificationType(t)).toBe(t));
  });

  it('maps unknown/legacy types to system (same as the display fallback)', () => {
    ['warning', 'broadcast', 'message', 'info', 'alert', 'success',
      'participation', 'lesson_plan_complete', '', null, undefined]
      .forEach(t => expect(normalizeNotificationType(t)).toBe('system'));
  });

  it('always returns a key that exists in notificationTypeConfig', () => {
    ['communication', 'warning', 'garbage', null].forEach(t => {
      expect(notificationTypeConfig[normalizeNotificationType(t)]).toBeDefined();
    });
  });
});

describe('normalizeNotificationPriority', () => {
  it('keeps canonical priorities unchanged', () => {
    ['low', 'medium', 'high', 'critical']
      .forEach(p => expect(normalizeNotificationPriority(p)).toBe(p));
  });

  it('maps backend aliases: normal→medium, urgent→critical', () => {
    expect(normalizeNotificationPriority('normal')).toBe('medium');
    expect(normalizeNotificationPriority('urgent')).toBe('critical');
  });

  it('maps unknown/empty to medium (same as the display fallback)', () => {
    ['weird', '', null, undefined]
      .forEach(p => expect(normalizeNotificationPriority(p)).toBe('medium'));
  });

  it('always returns a key that exists in priorityConfig', () => {
    ['urgent', 'normal', 'garbage', null].forEach(p => {
      expect(priorityConfig[normalizeNotificationPriority(p)]).toBeDefined();
    });
  });
});
