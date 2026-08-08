/**
 * Task #1072 — guard the role-aware AI Insights "Smart Alerts" route fallback.
 *
 * When an alert payload omits an explicit `route`, AlertsTimeline falls back to
 * `buildAlertRouteMap(isTeacher)`. Teachers / independent teachers must land on
 * their own self-scoping pages (/teacher/attendance, /teacher/behavior); the
 * admin attendance/behaviour pages would 403 their data calls. Admins /
 * principals use the canonical leadership pages (/principal/attendance;
 * behaviour keeps its legacy key — no leadership behaviour page exists).
 *
 * If a future change silently re-hardcodes an admin route here, teachers would
 * be sent to a page that 403s its data — this test catches that.
 */
import {
  buildAlertRouteMap,
  buildKpiCardRoute,
  withAlertAttendanceContext,
  ALERT_CONTEXT_PARAM,
  ALERT_CONTEXT_VALUE,
} from '@/shared/models/utils/alertRoutes';

describe('buildAlertRouteMap — role-aware AI Insights alert fallback', () => {
  test('teacher scope routes attendance/behaviour to self-scoping pages', () => {
    const map = buildAlertRouteMap(true);
    expect(map.attendance).toBe('/teacher/attendance');
    expect(map.behavior).toBe('/teacher/behavior');
    // Both the US ("behavior") and UK ("behaviour") category keys must map.
    expect(map.behaviour).toBe('/teacher/behavior');
  });

  test('non-teacher (admin/principal) scope routes to canonical principal pages', () => {
    const map = buildAlertRouteMap(false);
    expect(map.attendance).toBe('/principal/attendance');
    // Leadership has no behaviour page — /admin/behaviour was never a
    // registered route (catch-all bounced to the homepage). Conduct is
    // reviewed from the students page.
    expect(map.behavior).toBe('/principal/students');
    expect(map.behaviour).toBe('/principal/students');
  });

  test('defaults to the leadership (non-teacher) routes when called with no arg', () => {
    const map = buildAlertRouteMap();
    expect(map.attendance).toBe('/principal/attendance');
    expect(map.behaviour).toBe('/principal/students');
  });

  test('non-role-gated categories are stable across roles', () => {
    const teacherMap = buildAlertRouteMap(true);
    const adminMap = buildAlertRouteMap(false);
    for (const map of [teacherMap, adminMap]) {
      expect(map.academic).toBe('/principal/students');
      expect(map.teacher).toBe('/principal/teacher-attendance');
      expect(map.schedule).toBe('/principal/schedule');
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

  test('leaves non-teacher (leadership) attendance routes untouched', () => {
    expect(withAlertAttendanceContext('/principal/attendance', 'attendance', false))
      .toBe('/principal/attendance');
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

describe('AI Insights attendance card — composed navigation', () => {
  // The "نسبة الحضور" quick-stat card must reuse the same role-aware logic as
  // the Smart Alerts "انتقل" action instead of hardcoding an admin route.
  // Composition mirrors the card's onClick:
  //   withAlertAttendanceContext(buildAlertRouteMap(isTeacher).attendance, 'attendance', isTeacher)
  const cardRoute = (isTeacher) =>
    withAlertAttendanceContext(buildAlertRouteMap(isTeacher).attendance, 'attendance', isTeacher);

  test('teacher / independent teacher lands on the self-scoped attendance page with the smart-alert marker', () => {
    expect(cardRoute(true)).toBe(`/teacher/attendance?${ALERT_CONTEXT_PARAM}=${ALERT_CONTEXT_VALUE}`);
  });

  test('admin / principal keeps the canonical attendance route untouched', () => {
    expect(cardRoute(false)).toBe('/principal/attendance');
  });
});

describe('buildKpiCardRoute — role-aware AI Insights Quick Stats cards', () => {
  // Regression guard: a genuine platform admin has no school context, so the
  // school-scoped drill-downs (/admin/users-management, /admin/attendance)
  // would fail their route guards and bounce the admin to /admin (Command
  // Center). These cards must be non-clickable (null) for a platform admin.
  test('platform admin gets no destination for any card (non-clickable)', () => {
    for (const key of ['students', 'teachers', 'attendance']) {
      expect(buildKpiCardRoute(key, { isPlatformAdmin: true })).toBeNull();
      // isPlatformAdmin wins even if a stale isTeacher flag is passed too.
      expect(buildKpiCardRoute(key, { isTeacher: true, isPlatformAdmin: true })).toBeNull();
    }
  });

  test('school leadership drills into the users/attendance management pages', () => {
    const opts = { isTeacher: false, isPlatformAdmin: false };
    expect(buildKpiCardRoute('students', opts)).toBe('/principal/users-management');
    expect(buildKpiCardRoute('teachers', opts)).toBe('/principal/users-management?filter=teachers');
    expect(buildKpiCardRoute('attendance', opts)).toBe('/principal/attendance');
  });

  test('teacher self-scopes attendance and has no roster drill-down', () => {
    const opts = { isTeacher: true, isPlatformAdmin: false };
    expect(buildKpiCardRoute('students', opts)).toBeNull();
    expect(buildKpiCardRoute('teachers', opts)).toBeNull();
    expect(buildKpiCardRoute('attendance', opts)).toBe(
      `/teacher/attendance?${ALERT_CONTEXT_PARAM}=${ALERT_CONTEXT_VALUE}`,
    );
  });

  test('unknown card keys and missing options resolve to null', () => {
    expect(buildKpiCardRoute('mystery', { isTeacher: false, isPlatformAdmin: false })).toBeNull();
    expect(buildKpiCardRoute('students')).toBe('/principal/users-management');
  });
});
