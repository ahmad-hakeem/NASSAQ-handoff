jest.setTimeout(20000);

/**
 * Task #281 — LessonPlannerPage mobile-viewport snapshots.
 *
 * Renders the IT lesson-planner page at the four target widths and
 * snapshots a stable structural fingerprint per width. Catches
 * regressions in the prompt form's responsive grid + the saved-plans
 * list layout that shared layout primitives provide.
 */
import React from 'react';
import { render, act } from '@testing-library/react';

import {
  TARGET_WIDTHS,
  setViewport,
  fingerprintContainer,
} from '../../../testUtils/mobileViewportFingerprint';

jest.mock('react-router-dom', () => ({
  useLocation: () => ({ pathname: '/teacher/lesson-planner', search: '' }),
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: () => <div data-testid="sidebar" />,
}));
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqConfirm: jest.fn(),
  }),
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

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApiPut = jest.fn();
const mockApiDelete = jest.fn();
const mockApi = Object.freeze({
  get: (...a) => mockApiGet(...a),
  post: (...a) => mockApiPost(...a),
  put: (...a) => mockApiPut(...a),
  delete: (...a) => mockApiDelete(...a),
});
const mockUser = Object.freeze({
  id: 'u-it-1', role: 'independent_teacher', preferred_language: 'ar',
});
const mockAuth = Object.freeze({ api: mockApi, user: mockUser });
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

import LessonPlannerPage from '../LessonPlannerPage';

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPost.mockReset();
  mockApiPut.mockReset();
  mockApiDelete.mockReset();
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/lesson-plans') {
      return Promise.resolve({
        data: {
          lesson_plans: [
            {
              id: 'lp1', topic: 'الكسور', subject: 'رياضيات',
              grade_level: 'الرابع', duration_minutes: 45,
              created_at: '2026-05-01T00:00:00Z',
              plan: { title: 'الكسور البسيطة', objectives: [] },
            },
          ],
          quota: { used_today: 1, max_per_day: 20 },
        },
      });
    }
    if (url === '/classes') return Promise.resolve({ data: { classes: [] } });
    return Promise.resolve({ data: {} });
  });
});

describe.each(TARGET_WIDTHS)(
  'LessonPlannerPage at %ipx — Task #281 viewport fingerprint',
  (width) => {
    test(`fingerprint @ ${width}px is stable`, async () => {
      setViewport(width);
      let container;
      await act(async () => {
        ({ container } = render(<LessonPlannerPage />));
      });
      await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
      expect(mockApiGet).toHaveBeenCalledWith(
        '/independent-teacher/lesson-plans',
      );
      expect(fingerprintContainer(container, width)).toMatchSnapshot();
    });
  },
);
