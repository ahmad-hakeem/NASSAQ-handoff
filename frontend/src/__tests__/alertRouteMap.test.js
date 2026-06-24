/**
 * Task #1072 — guard the role-aware AI Insights "Smart Alerts" route fallback.
 *
 * When an alert payload omits an explicit `route`, AlertsTimeline falls back to
 * `buildAlertRouteMap(isTeacher)`. Teachers / independent teachers must land on
 * their own self-scoping pages (/teacher/attendance, /teacher/behavior); the
 * admin attendance/behaviour pages would 403 their data calls. Admins /
 * principals keep the admin pages (/admin/attendance, /admin/behaviour).
 *
 * If a future change silently re-hardcodes an admin route here, teachers would
 * be sent to a page that 403s its data — this test catches that.
 */
import {
  buildAlertRouteMap,
  withAlertAttendanceContext,
  ALERT_CONTEXT_PARAM,
  ALERT_CONTEXT_VALUE,
} from '../utils/alertRoutes';

describe('buildAlertRouteMap — role-aware AI Insights alert fallback', () => {
  test('teacher scope routes attendance/behaviour to self-scoping pages', () => {
    const map = buildAlertRouteMap(true);
    expect(map.attendance).toBe('/teacher/attendance');
    expect(map.behavior).toBe('/teacher/behavior');
    // Both the US ("behavior") and UK ("behaviour") category keys must map.
    expect(map.behaviour).toBe('/teacher/behavior');
  });

  test('non-teacher (admin/principal) scope routes to admin pages', () => {
    const map = buildAlertRouteMap(false);
    expect(map.attendance).toBe('/admin/attendance');
    expect(map.behavior).toBe('/admin/behaviour');
    expect(map.behaviour).toBe('/admin/behaviour');
  });

  test('defaults to the admin (non-teacher) routes when called with no arg', () => {
    const map = buildAlertRouteMap();
    expect(map.attendance).toBe('/admin/attendance');
    expect(map.behaviour).toBe('/admin/behaviour');
  });

  test('non-role-gated categories are stable across roles', () => {
    const teacherMap = buildAlertRouteMap(true);
    const adminMap = buildAlertRouteMap(false);
    for (const map of [teacherMap, adminMap]) {
      expect(map.academic).toBe('/admin/students');
      expect(map.teacher).toBe('/admin/teacher-attendance');
      expect(map.schedule).toBe('/school/schedule');
      expect(map.performance).toBe('/principal/ai-insights');
    }
  });
});

describe('withAlertAttendanceContext — Smart Alerts attendance marker', () => {
  const marker = `${ALERT_CONTEXT_PARAM}=${ALERT_CONTEXT_VALUE}`;

  test('tags the teacher attendance route for an attendance alert', () => {
    expect(withAlertAttendanceContext('/teacher/attendance', 'attendance', true))
      .toBe(`/teacher/attendance?${marker}`);
  });

  test('preserves existing query params on the route', () => {
    const out = withAlertAttendanceContext('/teacher/attendance?class=7a', 'attendance', true);
    expect(out).toContain('class=7a');
    expect(out).toContain(marker);
  });

  test('leaves non-teacher (admin) attendance routes untouched', () => {
    expect(withAlertAttendanceContext('/admin/attendance', 'attendance', false))
      .toBe('/admin/attendance');
  });

  test('does not tag non-attendance categories', () => {
    expect(withAlertAttendanceContext('/teacher/behavior', 'behavior', true))
      .toBe('/teacher/behavior');
  });

  test('passes through null/empty routes', () => {
    expect(withAlertAttendanceContext(null, 'attendance', true)).toBe(null);
    expect(withAlertAttendanceContext('', 'attendance', true)).toBe('');
  });
});
