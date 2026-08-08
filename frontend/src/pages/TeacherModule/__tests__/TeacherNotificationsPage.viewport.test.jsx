jest.setTimeout(20000);

/**
 * Task #281 — TeacherNotificationsPage mobile-viewport snapshots.
 *
 * Renders the IT notifications inbox at the four target widths (360 /
 * 414 / 768 / 1024 px) and snapshots a stable structural fingerprint
 * per width. Catches regressions in the shared ResponsiveTable mobile
 * cards branch and the responsive Tabs/CTA layout.
 */
import React from 'react';
import { render, act } from '@testing-library/react';

import {
  TARGET_WIDTHS,
  setViewport,
  fingerprintContainer,
} from '../../../testUtils/mobileViewportFingerprint';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));
const mockNassaq = Object.freeze({
  nassaqError: jest.fn(),
  nassaqInfo: jest.fn(),
});
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockNassaq,
}));
const mockTheme = Object.freeze({ isRTL: true, isDark: false, language: 'ar', theme: 'light', toggleTheme: () => {}, toggleLanguage: () => {} });
const mockTranslation = Object.freeze({ t: (k) => k });
jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => mockTheme,
  useTranslation: () => mockTranslation,
}));
jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));
jest.mock('../../../components/ui/tabs', () => {
  const React2 = require('react');
  const Ctx = React2.createContext({ value: undefined, onValueChange: () => {} });
  return {
    Tabs: ({ value, onValueChange, children }) =>
      React2.createElement(Ctx.Provider, { value: { value, onValueChange } }, children),
    TabsList: ({ children }) => React2.createElement('div', null, children),
    TabsTrigger: ({ value, children }) => {
      const ctx = React2.useContext(Ctx);
      return React2.createElement(
        'button',
        { type: 'button', onClick: () => ctx.onValueChange(value) },
        children,
      );
    },
  };
});

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApi = Object.freeze({
  get: (...a) => mockApiGet(...a),
  post: (...a) => mockApiPost(...a),
});
const mockUser = Object.freeze({
  id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar',
});
const mockAuth = Object.freeze({ api: mockApi, user: mockUser });
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import TeacherNotificationsPage from '../TeacherNotificationsPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPost.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/notifications/unread-count') {
      return Promise.resolve({ data: { unread_count: 1 } });
    }
    if (url === '/independent-teacher/notifications') {
      return Promise.resolve({
        data: {
          items: [
            {
              id: 'n1', category: 'general', title: 'دعوة',
              message: 'رسالة', is_read: false,
              created_at: '2026-05-01T00:00:00Z', cta_url: '/teacher/x',
            },
          ],
          total: 1, next_cursor: null, has_more: false,
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
});

describe.each(TARGET_WIDTHS)(
  'TeacherNotificationsPage at %ipx — Task #281 viewport fingerprint',
  (width) => {
    test(`fingerprint @ ${width}px is stable`, async () => {
      setViewport(width);
      let container;
      await act(async () => {
        ({ container } = render(<TeacherNotificationsPage />));
      });
      await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
      expect(mockApiGet).toHaveBeenCalledWith(
        '/independent-teacher/notifications',
        expect.anything(),
      );
      expect(fingerprintContainer(container, width)).toMatchSnapshot();
    });
  },
);
