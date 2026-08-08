/**
 * Unit coverage for `useCanViewInternalIds` — the single source of truth for
 * whether the current viewer may see system-generated internal identifiers.
 *
 * The hook reads `AuthContext` directly and keys off the *real* account role
 * (`isPlatformAdmin`), not the effective/preview role, so a platform admin
 * keeps troubleshooting visibility even while previewing a school. With no
 * provider mounted it must fail safe to `false`.
 */
import React from 'react';
import { renderHook } from '@testing-library/react';
import { AuthContext } from '@/shared/contexts/AuthContext';
import { useCanViewInternalIds } from '../useCanViewInternalIds';

const wrapperWith = (value) =>
  function Wrapper({ children }) {
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
  };

test('returns true only for the real Platform Admin account', () => {
  const { result } = renderHook(() => useCanViewInternalIds(), {
    wrapper: wrapperWith({ isPlatformAdmin: true }),
  });
  expect(result.current).toBe(true);
});

test('returns false for non-admin roles', () => {
  const { result } = renderHook(() => useCanViewInternalIds(), {
    wrapper: wrapperWith({ isPlatformAdmin: false }),
  });
  expect(result.current).toBe(false);
});

test('stays true while a platform admin previews a school (real role wins)', () => {
  // During impersonation `user.role` remains platform_admin, so the context
  // still reports isPlatformAdmin: true even though the effective/preview role
  // is school_principal.
  const { result } = renderHook(() => useCanViewInternalIds(), {
    wrapper: wrapperWith({ isPlatformAdmin: true, isImpersonating: true }),
  });
  expect(result.current).toBe(true);
});

test('coerces a missing/undefined flag to a strict boolean false', () => {
  const { result } = renderHook(() => useCanViewInternalIds(), {
    wrapper: wrapperWith({}),
  });
  expect(result.current).toBe(false);
});

test('fails safe to false when used outside an AuthProvider', () => {
  const { result } = renderHook(() => useCanViewInternalIds());
  expect(result.current).toBe(false);
});
