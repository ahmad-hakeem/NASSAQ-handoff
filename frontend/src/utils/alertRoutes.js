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
