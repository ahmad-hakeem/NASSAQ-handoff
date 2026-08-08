import { createContext, useContext } from 'react';
import { AuthContext } from '@/shared/contexts/AuthContext';

// Fallback context used only when `AuthContext` is unavailable at the call site
// — e.g. a small leaf component unit-tested without an `AuthProvider`, or a test
// that mocks the AuthContext module and therefore drops its `AuthContext`
// export. Reading it always yields `null`, so the guard fails safe to "hidden".
const NoAuthContext = createContext(null);

/**
 * Single source of truth for "may this viewer see system-generated internal
 * identifiers (auto-generated UUIDs) in the UI?".
 *
 * Platform rule: ONLY the Platform Admin / مدير المنصة. The identifier is an
 * internal technical reference (it stays in the data layer for lookups,
 * selectors and API calls regardless) — this hook only governs whether it is
 * rendered.
 *
 * We key off the *real* account role (`isPlatformAdmin`), not the
 * effective/preview role, so a platform admin keeps full troubleshooting
 * visibility even while previewing a school as its principal — and, in that
 * preview, can still see a leaked id to diagnose bad data. Every other role
 * (teacher, school principal/admin, parent, student, and the platform
 * sub-roles such as نائب مدير منصة) receives `false`.
 *
 * We read `AuthContext` directly with a single, unconditional `useContext`
 * call (the `?? NoAuthContext` only swaps which context object is read, never
 * whether the hook runs). This keeps the rule-of-hooks contract intact while
 * letting the hook be dropped into any presentational component — including
 * prop-driven leaf components rendered in isolation — without forcing an
 * `AuthProvider`. With no provider the value is `null`, so we fail safe to
 * `false` (ids hidden), the correct default for a visibility guard.
 *
 * Centralizing the condition here keeps the rule from drifting across the
 * many components that display ids; callers combine it with the helpers in
 * `utils/internalId.js`.
 *
 * @returns {boolean} true only for the Platform Admin account.
 */
export function useCanViewInternalIds() {
  const auth = useContext(AuthContext ?? NoAuthContext);
  return !!auth?.isPlatformAdmin;
}

export default useCanViewInternalIds;
