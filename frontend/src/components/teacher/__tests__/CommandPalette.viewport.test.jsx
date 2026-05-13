/**
 * Task #281 — CommandPalette mobile-viewport snapshots (open state).
 *
 * Opens the palette via Cmd/Ctrl+K and snapshots a stable structural
 * fingerprint at the four target widths. The fingerprint includes the
 * presence of `cmdk-close-mobile` vs `cmdk-close` so regressions to
 * the sheet-vs-dialog responsive split flip the snapshot.
 */
import React from 'react';
import { render, act, fireEvent } from '@testing-library/react';

import {
  TARGET_WIDTHS,
  setViewport,
  fingerprintContainer,
} from '../../../__tests__/mobileViewportFingerprint';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}), { virtual: true });

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u-it-1', role: 'independent_teacher' },
    api: { get: mockApiGet },
  }),
}));

import CommandPalette from '../CommandPalette';

describe.each(TARGET_WIDTHS)(
  'CommandPalette at %ipx — Task #281 viewport fingerprint (open)',
  (width) => {
    test(`fingerprint @ ${width}px is stable`, async () => {
      setViewport(width);
      const { container } = render(<CommandPalette />);
      await act(async () => {
        fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
      });
      expect(fingerprintContainer(container, width)).toMatchSnapshot();
    });
  },
);
