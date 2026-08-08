// AuthContext is only needed by the `useSchoolNavigation` hook (not exercised
// here). Mock it so importing the pure resolvers doesn't drag in the full
// context module chain.
jest.mock('@/shared/contexts/AuthContext', () => ({ useAuth: () => ({}) }));

import { getSchoolRolePrefix, getStudentDetailPath } from '../studentNavigation';

describe('getSchoolRolePrefix', () => {
  it('routes all school-leadership roles to /principal', () => {
    expect(getSchoolRolePrefix('school_principal')).toBe('/principal');
    expect(getSchoolRolePrefix('school_admin')).toBe('/principal');
    expect(getSchoolRolePrefix('school_sub_admin')).toBe('/principal');
  });

  it('keeps non-school roles on /admin (unchanged behavior)', () => {
    expect(getSchoolRolePrefix('teacher')).toBe('/admin');
    expect(getSchoolRolePrefix('independent_teacher')).toBe('/admin');
    expect(getSchoolRolePrefix('platform_admin')).toBe('/admin');
    expect(getSchoolRolePrefix('parent')).toBe('/admin');
  });

  it('falls back to /admin for unknown/empty roles', () => {
    expect(getSchoolRolePrefix(undefined)).toBe('/admin');
    expect(getSchoolRolePrefix(null)).toBe('/admin');
    expect(getSchoolRolePrefix('')).toBe('/admin');
  });
});

describe('getStudentDetailPath', () => {
  it('builds a /principal student path for a school_admin (the reported bug)', () => {
    expect(getStudentDetailPath('school_admin', 'abc-123')).toBe('/principal/students/abc-123');
  });

  it('routes teachers to their own students page via a student_id deep-link', () => {
    // Teachers have no /{scope}/students/:id route; sending them to
    // /admin/students/:id failed the role guard and bounced them home (the
    // AI-Insights Risk Radar bug). They must land on /teacher/students.
    expect(getStudentDetailPath('teacher', 'abc-123')).toBe('/teacher/students?student_id=abc-123');
    expect(getStudentDetailPath('independent_teacher', 'abc-123')).toBe('/teacher/students?student_id=abc-123');
  });

  it('url-encodes the student id in the teacher deep-link', () => {
    expect(getStudentDetailPath('teacher', 'a/b c')).toBe('/teacher/students?student_id=a%2Fb%20c');
  });

  it('appends class_id to the teacher deep-link when provided', () => {
    expect(getStudentDetailPath('teacher', 'abc-123', { classId: 'cls-9' }))
      .toBe('/teacher/students?student_id=abc-123&class_id=cls-9');
    expect(getStudentDetailPath('independent_teacher', 'abc-123', { classId: 'cls-9' }))
      .toBe('/teacher/students?student_id=abc-123&class_id=cls-9');
  });

  it('ignores classId for non-teacher (leadership/admin) roles', () => {
    expect(getStudentDetailPath('school_admin', 'abc-123', { classId: 'cls-9' }))
      .toBe('/principal/students/abc-123');
    expect(getStudentDetailPath('platform_admin', 'abc-123', { classId: 'cls-9' }))
      .toBe('/admin/students/abc-123');
  });
});
