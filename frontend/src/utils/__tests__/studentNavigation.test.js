// AuthContext is only needed by the `useSchoolNavigation` hook (not exercised
// here). Mock it so importing the pure resolvers doesn't drag in the full
// context module chain.
jest.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({}) }));

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

  it('builds a /admin student path for a teacher', () => {
    expect(getStudentDetailPath('teacher', 'abc-123')).toBe('/admin/students/abc-123');
  });
});
