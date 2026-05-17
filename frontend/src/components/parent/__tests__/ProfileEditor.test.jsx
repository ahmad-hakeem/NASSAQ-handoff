/**
 * Task #385 — component-level guard for the parent-edited student
 * profile editor.
 *
 * Pins the sibling-switch reset contract: when the parent flips
 * `activeChildId` (or the underlying `profile` prop is refetched),
 * the in-progress local form state in ProfileEditor MUST be reseeded
 * from the new child's `profile` so child A's in-progress chip
 * selections cannot visually bleed into child B's editor.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ api: { put: jest.fn().mockResolvedValue({ data: {} }) } }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false }),
}));

jest.mock('../../ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn() }),
}));

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }), {
  virtual: true,
});

import ProfileEditor from '../ProfileEditor';

const childAProfile = {
  emoji: '⚽',
  health_conditions: ['asthma'],
  behavioral_aspects: ['hyperactivity'],
  family_situation: 'both_parents',
  family_other_situations: ['parent_traveling'],
};

const childBProfile = {
  emoji: '🎨',
  health_conditions: ['weak_vision'],
  behavioral_aspects: [],
  family_situation: 'mother_only',
  family_other_situations: [],
};

describe('ProfileEditor — sibling switch reset', () => {
  test('reseeds local form state from new profile when childId changes', () => {
    const { rerender } = render(
      <ProfileEditor profile={childAProfile} childId="child-a" onSave={() => {}} onCancel={() => {}} />,
    );

    // Child A's selections visible: Asthma + Hyperactivity + Both Parents.
    expect(screen.getByText('Asthma').className).toMatch(/rose/);
    expect(screen.getByText('Hyperactivity').className).toMatch(/amber/);
    expect(screen.getByText('Parent Traveling').className).toMatch(/sky/);
    // Child B-only chip is NOT active.
    expect(screen.getByText('Weak Vision').className).not.toMatch(/rose/);

    // Parent flips to child B — the editor must reseed from B's profile.
    act(() => {
      rerender(
        <ProfileEditor profile={childBProfile} childId="child-b" onSave={() => {}} onCancel={() => {}} />,
      );
    });

    // Child A's selections are gone; Child B's are now the active chips.
    expect(screen.getByText('Asthma').className).not.toMatch(/rose/);
    expect(screen.getByText('Hyperactivity').className).not.toMatch(/amber/);
    expect(screen.getByText('Parent Traveling').className).not.toMatch(/sky/);
    expect(screen.getByText('Weak Vision').className).toMatch(/rose/);
  });

  test('clears in-progress (unsaved) selections when sibling is switched', () => {
    const { rerender } = render(
      <ProfileEditor profile={childAProfile} childId="child-a" onSave={() => {}} onCancel={() => {}} />,
    );

    // Simulate in-progress edit on child A: toggle Diabetes ON locally.
    act(() => {
      screen.getByText('Diabetes').click();
    });
    expect(screen.getByText('Diabetes').className).toMatch(/rose/);

    // Switch to child B — the unsaved Diabetes toggle must NOT carry over.
    act(() => {
      rerender(
        <ProfileEditor profile={childBProfile} childId="child-b" onSave={() => {}} onCancel={() => {}} />,
      );
    });
    expect(screen.getByText('Diabetes').className).not.toMatch(/rose/);
  });
});
