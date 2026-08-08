// Role-aware fallback map for AI Insights "Smart Alerts" navigation.
//
// Used by AlertsTimeline when an alert arrives without an explicit `route`
// (e.g. older payloads). Teachers / independent teachers self-scope on
// /teacher/attendance and /teacher/behavior; the admin attendance/behaviour
// pages would 403 their data calls. Admin / principal / school-admin use the
// canonical /principal leadership paths. Kept as a pure function so the role
// gating is unit-testable independent of the (heavy) page component tree.
// Principal route audit 2026-07-28: leadership destinations use the canonical
// /principal namespace (the legacy /admin//school variants are now
// redirect-aliases in appRoutes.js, so old payload-supplied routes still work).
export const buildAlertRouteMap = (isTeacher = false) => ({
  attendance: isTeacher ? '/teacher/attendance' : '/principal/attendance',
  academic: '/principal/students',
  // Leadership has no dedicated behaviour page — /admin/behaviour was never
  // a registered route (catch-all bounced to the homepage). Leadership
  // reviews conduct from the students page.
  behavior: isTeacher ? '/teacher/behavior' : '/principal/students',
  behaviour: isTeacher ? '/teacher/behavior' : '/principal/students',
  teacher: '/principal/teacher-attendance',
  schedule: '/principal/schedule',
  performance: '/principal/ai-insights',
});

// Role-aware destination for the AI Insights "Quick Stats" KPI cards
// (إجمالي الطلاب / إجمالي المعلمين / نسبة الحضور). Returns `null` when the card
// has no drill-down for the given viewer, so the card renders as
// non-interactive instead of navigating.
//
// Why this exists: these cards used to hardcode the school-scoped routes
// (/admin/users-management, /admin/attendance). A genuine platform admin is
// not in SCHOOL_ROLES / SCHOOL_TEACHING_ROLES, so ProtectedRoute failed closed
// and bounced them to their role dashboard (/admin = Command Center). A
// platform admin has no single school context, so these KPIs have no
// drill-down for them and the card must not be clickable. Callers pass the
// EFFECTIVE role flags so a platform admin previewing a school (effective role
// = principal) still gets the working school routes.
export const buildKpiCardRoute = (cardKey, { isTeacher = false, isPlatformAdmin = false } = {}) => {
  if (isPlatformAdmin) return null;
  switch (cardKey) {
    case 'students':
      // Teachers see "my students" (their own roster count) with no
      // roster-management page to open; only school leadership drills in.
      return isTeacher ? null : '/principal/users-management';
    case 'teachers':
      return isTeacher ? null : '/principal/users-management?filter=teachers';
    case 'attendance':
      return withAlertAttendanceContext(
        buildAlertRouteMap(isTeacher).attendance,
        'attendance',
        isTeacher,
      );
    default:
      return null;
  }
};

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
