/**
 * Task #274 — OnboardingTour mobile viewport contract.
 *
 * At 360px (the tightest target width in this task), the spotlight
 * cutout must use the tightened 3px padding (not the desktop 6px) so
 * the highlight doesn't bleed into the tooltip, and the tooltip must
 * stay clamped within the 8px mobile edge gutter on both axes.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';

jest.mock('react-dom', () => {
  const actual = jest.requireActual('react-dom');
  return { ...actual, createPortal: (node) => node };
});

jest.mock('../../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('../../../../contexts/AuthContext', () => ({
  useAuth: () => ({ isRTL: true }),
}));

jest.mock('../steps', () => ({
  TOUR_STEPS: [
    { id: 'fake-step', target: '#fake-anchor', titleKey: 'tour.title', bodyKey: 'tour.body' },
  ],
}));

import { OnboardingTour } from '../OnboardingTour';

function setViewport(w, h) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: w });
  Object.defineProperty(window, 'innerHeight', { configurable: true, value: h });
}

beforeEach(() => {
  // jsdom doesn't have ResizeObserver — stub a no-op so useTargetRect mounts.
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  // The tour calls scrollIntoView on the anchor; jsdom omits it.
  Element.prototype.scrollIntoView = jest.fn();
});

test('at 360px the spotlight uses tight padding and the tooltip stays inside the gutter', async () => {
  setViewport(360, 720);

  // Mount an anchor element near the bottom-right corner so the clamp
  // logic has to push the tooltip back into the viewport.
  const anchor = document.createElement('div');
  anchor.id = 'fake-anchor';
  document.body.appendChild(anchor);
  anchor.getBoundingClientRect = () => ({
    top: 600, left: 320, right: 360, bottom: 640,
    width: 40, height: 40, x: 320, y: 600, toJSON() {},
  });

  render(<OnboardingTour open onFinish={() => {}} onSkip={() => {}} />);

  // Allow the layout-effect measurement + 80ms scheduled remeasure to flush.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 100));
  });

  // Spotlight rect = anchor.left(320) - spotPad(3) = 317. Width = 40 + 3*2 = 46.
  const svgRect = document.querySelector('svg mask rect[fill="black"]');
  expect(svgRect).not.toBeNull();
  expect(svgRect.getAttribute('x')).toBe('317');
  expect(svgRect.getAttribute('width')).toBe('46');
  // Mobile mode also uses the smaller corner radius.
  expect(svgRect.getAttribute('rx')).toBe('8');

  // Tooltip clamp: width = min(380, 360 - 8*2) = 344. Left clamped to >= 8.
  const tooltip = screen.getByText('tour.title').closest('[style]');
  expect(tooltip).not.toBeNull();
  const style = tooltip.getAttribute('style') || '';
  expect(style).toMatch(/width:\s*344px/);
  // Left must be >= 8px (mobile edge gutter), never negative.
  const leftMatch = style.match(/left:\s*(-?\d+)px/);
  expect(leftMatch).not.toBeNull();
  expect(Number(leftMatch[1])).toBeGreaterThanOrEqual(8);
  // Top must also stay inside the viewport on the bottom edge.
  const topMatch = style.match(/top:\s*(-?\d+)px/);
  expect(topMatch).not.toBeNull();
  const top = Number(topMatch[1]);
  expect(top).toBeGreaterThanOrEqual(8);
  expect(top + 240).toBeLessThanOrEqual(720 - 8 + 1);

  document.body.removeChild(anchor);
});
