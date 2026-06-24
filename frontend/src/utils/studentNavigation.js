// Canonical role-aware navigation helpers for school-scoped student pages.
//
// School principals must stay inside the `/principal` scope and must never
// fall back to a platform-admin (`/admin`) route. All school-role student
// navigation goes through these helpers so the role->path mapping lives in a
// single place and the principal/admin scope bug cannot reappear per-callsite.
//
// IMPORTANT: routing decisions must use the EFFECTIVE role, not the raw
// `user.role`. When a platform_admin previews/impersonates a school, their
// `user.role` stays `platform_admin` while they act as a principal, so a raw
// `user.role` check would resolve to `/admin` and break the principal scope.
// `RouteGuards` and the route tree both gate on `getEffectiveRole()`, so the
// `useSchoolNavigation` hook below resolves the same way. Prefer the hook over
// the bare functions in components/hooks; the bare functions exist only for
// callers that already hold a resolved effective role.

import { useAuth } from '../contexts/AuthContext';

export function getSchoolRolePrefix(role) {
  return role === 'school_principal' ? '/principal' : '/admin';
}

export function getStudentDetailPath(role, studentId) {
  return `${getSchoolRolePrefix(role)}/students/${studentId}`;
}

// Resolve school-scoped navigation from the effective (preview/impersonation-
// aware) role. Returns the role prefix and a student-detail path builder that
// already has the correct role baked in, so callers cannot accidentally pass
// the raw `user.role`.
export function useSchoolNavigation() {
  const { getEffectiveRole, user } = useAuth();
  const role = (typeof getEffectiveRole === 'function' ? getEffectiveRole() : null) || user?.role;
  return {
    effectiveRole: role,
    rolePrefix: getSchoolRolePrefix(role),
    getStudentDetailPath: (studentId) => getStudentDetailPath(role, studentId),
  };
}
