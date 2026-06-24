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

// School "leadership" roles. In this product a `school_admin` (and the read-only
// `school_sub_admin`) is the account a school actually operates as its principal:
// it is shown as "مدير المدرسة", `AuthContext.isSchoolPrincipal` is true for it,
// and the sidebar gives ALL of these roles the same school menu rooted at
// `/principal` (e.g. the AI-Insights entry is `/principal/ai-insights`, see
// `components/layout/Sidebar.jsx`). The route tree also guards
// `/principal/students/:id` with the same `SCHOOL_ROLES` set. They must therefore
// stay inside the `/principal` scope for student navigation too, and must never
// fall back to the platform `/admin` student route — otherwise clicking a student
// (e.g. from the Risk Radar) jumps a leadership user out of `/principal`.
const SCHOOL_LEADERSHIP_ROLES = ['school_principal', 'school_admin', 'school_sub_admin'];

export function getSchoolRolePrefix(role) {
  return SCHOOL_LEADERSHIP_ROLES.includes(role) ? '/principal' : '/admin';
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
