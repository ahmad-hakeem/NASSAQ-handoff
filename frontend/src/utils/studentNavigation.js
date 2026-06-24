// Canonical role-aware navigation helpers for school-scoped student pages.
//
// School principals must stay inside the `/principal` scope and must never
// fall back to a platform-admin (`/admin`) route. All school-role student
// navigation goes through these helpers so the role->path mapping lives in a
// single place and the principal/admin scope bug cannot reappear per-callsite.

export function getSchoolRolePrefix(role) {
  return role === 'school_principal' ? '/principal' : '/admin';
}

export function getStudentDetailPath(role, studentId) {
  return `${getSchoolRolePrefix(role)}/students/${studentId}`;
}
