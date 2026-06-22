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
import { buildAlertRouteMap } from '../utils/alertRoutes';

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
