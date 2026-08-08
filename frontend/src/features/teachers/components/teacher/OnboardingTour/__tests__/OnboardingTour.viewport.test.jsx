/**
 * Task #281 — OnboardingTour mobile-viewport snapshots.
 *
 * Renders the tour open at the four target widths and snapshots a
 * stable structural fingerprint per width. The fingerprint pulls the
 * portal'd tooltip width / left / top out of the inline style so the
 * mobile clamp + spotlight padding logic is part of the contract.
 */
import React from 'react';
import { render, act } from '@testing-library/react';

import {
  TARGET_WIDTHS,
  setViewport,
  fingerprintContainer,
} from '../../../../testUtils/mobileViewportFingerprint';

jest.mock('react-dom', () => {
  const actual = jest.requireActual('react-dom');
  return { ...actual, createPortal: (node) => node };
});

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ isRTL: true }),
}));

jest.mock('../steps', () => ({
  TOUR_STEPS: [
    { id: 'fake-step', target: '#fake-anchor', titleKey: 'tour.title', bodyKey: 'tour.body' },
  ],
}));

import { OnboardingTour } from '../OnboardingTour';

function tooltipFingerprint() {
  const tip = document.querySelector('div[style*="left:"]');
  if (!tip) return null;
  const style = tip.getAttribute('style') || '';
  const pick = (re) => {
    const m = style.match(re);
    return m ? Number(m[1]) : null;
  };
  return {
    width: pick(/width:\s*(\d+)px/),
    left: pick(/left:\s*(-?\d+)px/),
    top: pick(/top:\s*(-?\d+)px/),
  };
}

function spotlightFingerprint() {
  const r = document.querySelector('svg mask rect[fill="black"]');
  if (!r) return null;
  return {
    x: r.getAttribute('x'),
    y: r.getAttribute('y'),
    width: r.getAttribute('width'),
    height: r.getAttribute('height'),
    rx: r.getAttribute('rx'),
  };
}

beforeEach(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  Element.prototype.scrollIntoView = jest.fn();
});

describe.each(TARGET_WIDTHS)(
  'OnboardingTour at %ipx — Task #281 viewport fingerprint',
  (width) => {
    test(`fingerprint @ ${width}px is stable`, async () => {
      setViewport(width, 720);
      const anchor = document.createElement('div');
      anchor.id = 'fake-anchor';
      document.body.appendChild(anchor);
      anchor.getBoundingClientRect = () => ({
        top: 100, left: 80, right: 200, bottom: 140,
        width: 120, height: 40, x: 80, y: 100, toJSON() {},
      });

      const { container } = render(
        <OnboardingTour open onFinish={() => {}} onSkip={() => {}} />,
      );
      await act(async () => { await new Promise((r) => setTimeout(r, 100)); });

      const snap = {
        ...fingerprintContainer(container, width),
        tooltip: tooltipFingerprint(),
        spotlight: spotlightFingerprint(),
      };
      expect(snap).toMatchSnapshot();

      document.body.removeChild(anchor);
    });
  },
);
