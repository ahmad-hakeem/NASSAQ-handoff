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

// Teacher-scoped roles (regular and independent teachers). Unlike leadership
// roles, teachers have NO `/{scope}/students/:id` detail route — they view a
// student's profile inside their own Teacher Students page, opened via a
// `?student_id=` deep-link (see `TeacherModule/TeacherStudentsPage`). Routing a
// teacher to the school-admin `/admin/students/:id` route fails the role guard
// and bounces them to the home page (the AI-Insights Risk Radar bug). Keep this
// mapping here so every shared surface (Risk Radar, etc.) resolves consistently.
const TEACHER_SCOPED_ROLES = ['teacher', 'independent_teacher'];

export function getSchoolRolePrefix(role) {
  return SCHOOL_LEADERSHIP_ROLES.includes(role) ? '/principal' : '/admin';
}

export function getStudentDetailPath(role, studentId, opts = {}) {
  if (TEACHER_SCOPED_ROLES.includes(role)) {
    // A regular teacher's Students page loads one class at a time, so the
    // caller may pass the student's `classId` to deep-link the right class
    // (the page selects it before resolving the `student_id`). Independent
    // teachers default to the whole-workspace pool, so the class hint is
    // simply ignored there.
    const cls = opts.classId
      ? `&class_id=${encodeURIComponent(opts.classId)}`
      : '';
    return `/teacher/students?student_id=${encodeURIComponent(studentId)}${cls}`;
  }
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
    getStudentDetailPath: (studentId, opts) => getStudentDetailPath(role, studentId, opts),
  };
}
