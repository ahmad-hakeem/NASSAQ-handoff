jest.setTimeout(20000);

/**
 * Task #281 — TeacherAuditLogPage mobile-viewport snapshots.
 *
 * Renders the audit-log view at the four target widths (360 / 414 /
 * 768 / 1024 px) and snapshots a stable structural fingerprint per
 * width. A regression in the shared `ResponsiveTable` (e.g. the mobile
 * cards branch silently disappearing) flips the snapshot for every
 * width below sm:.
 */
import React from 'react';
import { render, act } from '@testing-library/react';

import {
  TARGET_WIDTHS,
  setViewport,
  fingerprintContainer,
} from '../../../testUtils/mobileViewportFingerprint';

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));
const mockNassaq = Object.freeze({
  nassaqError: jest.fn(),
  nassaqInfo: jest.fn(),
  nassaqConfirm: jest.fn(),
});
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockNassaq,
}));
jest.mock('@/shared/models/utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));
const mockT = (k) => k;
const mockTranslation = Object.freeze({ t: mockT });
const mockTheme = Object.freeze({ isRTL: true, isDark: false, language: 'ar', theme: 'light', toggleTheme: () => {}, toggleLanguage: () => {} });
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => mockTheme,
  useTranslation: () => mockTranslation,
}));

const mockApiGet = jest.fn();
const mockApi = Object.freeze({ get: (...a) => mockApiGet(...a) });
const mockUser = Object.freeze({
  id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar',
});
const mockAuth = Object.freeze({ api: mockApi, user: mockUser });
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import TeacherAuditLogPage from '../TeacherAuditLogPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/audit-logs') {
      return Promise.resolve({
        data: {
          logs: [
            {
              id: 'a1',
              timestamp: '2026-05-01T00:00:00Z',
              severity: 'info',
              action: 'STUDENT_CREATED',
              action_label_ar: 'إنشاء طالب',
              actor_name: 'المعلم',
              actor_role: 'independent_teacher',
              details: {},
            },
          ],
          categories: [],
          next_cursor: null,
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
});

describe.each(TARGET_WIDTHS)(
  'TeacherAuditLogPage at %ipx — Task #281 viewport fingerprint',
  (width) => {
    test(`fingerprint @ ${width}px is stable`, async () => {
      setViewport(width);
      let container;
      await act(async () => {
        ({ container } = render(<TeacherAuditLogPage />));
      });
      // Flush the data-fetch microtasks so ResponsiveTable settles into
      // its row-bearing state before we snapshot.
      await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
      expect(mockApiGet).toHaveBeenCalledWith(
        '/independent-teacher/audit-logs',
        expect.anything(),
      );
      expect(fingerprintContainer(container, width)).toMatchSnapshot();
    });
  },
);
