// Role-aware fallback map for AI Insights "Smart Alerts" navigation.
//
// Used by AlertsTimeline when an alert arrives without an explicit `route`
// (e.g. older payloads). Teachers / independent teachers self-scope on
// /teacher/attendance and /teacher/behavior; the admin attendance/behaviour
// pages would 403 their data calls. Admin / principal / school-admin keep the
// admin paths. Kept as a pure function so the role gating is unit-testable
// independent of the (heavy) page component tree.
export const buildAlertRouteMap = (isTeacher = false) => ({
  attendance: isTeacher ? '/teacher/attendance' : '/admin/attendance',
  academic: '/admin/students',
  behavior: isTeacher ? '/teacher/behavior' : '/admin/behaviour',
  behaviour: isTeacher ? '/teacher/behavior' : '/admin/behaviour',
  teacher: '/admin/teacher-attendance',
  schedule: '/school/schedule',
  performance: '/principal/ai-insights',
});

// Context marker carried on the teacher attendance route when the register is
// opened from the Smart Alerts timeline. The teacher attendance page reads this
// to hide the متأخر/بعذر (late/excused) statuses for this entry path only — the
// statuses stay available through every other navigation source.
export const ALERT_CONTEXT_PARAM = 'from';
export const ALERT_CONTEXT_VALUE = 'smart-alert';

// Tag a Smart Alerts navigation target with the context marker, scoped strictly
// to teacher attendance alerts. Every other category, the admin attendance
// route, and non-teacher viewers pass through unchanged. Existing query params
// on the route (e.g. a backend-supplied `?class=`) are preserved.
export const withAlertAttendanceContext = (route, category, isTeacher = false) => {
  if (!route || !isTeacher || category !== 'attendance') return route;
  const [path, query = ''] = route.split('?');
  if (path !== '/teacher/attendance') return route;
  const params = new URLSearchParams(query);
  params.set(ALERT_CONTEXT_PARAM, ALERT_CONTEXT_VALUE);
  return `${path}?${params.toString()}`;
};
