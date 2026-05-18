// Teacher Module Index - Export all pages

// Main Dashboard (Mobile First)
export { default as TeacherHomePage } from './TeacherHomePage';
export { default as TeacherMainDashboard } from './TeacherMainDashboard';
export { default as TeacherResponsiveDashboard } from './TeacherResponsiveDashboard';

// Session Management (Teacher Session Engine)
export { default as SessionStartPage } from './SessionStartPage';
export { default as SessionTeachPage } from './SessionTeachPage';
// Core Pages
export { default as TeacherTasksPage } from './TeacherTasksPage';
export { default as TeacherSchedulePage } from './TeacherSchedulePage';
export { default as TeacherClassesPage } from './TeacherClassesPage';
export { default as TeacherClassDetailPage } from './TeacherClassDetailPage';
export { default as TeacherAttendanceManagePage } from './TeacherAttendanceManagePage';
export { default as TeacherAssessmentsPage } from './TeacherAssessmentsPage';
export { default as TeacherBehaviorPage } from './TeacherBehaviorPage';
export { default as TeacherStudentsPage } from './TeacherStudentsPage';
export { default as ImportStudentsPage } from './ImportStudentsPage';
// Task #278 — IT bulk-import hub (students / classes / subjects / duplicate-week).
export { default as BulkImportPage } from './BulkImportPage';
export { default as TeacherAchievementsPage } from './TeacherAchievementsPage';
export { default as TeacherCommunicationPage } from './TeacherCommunicationPage';
export { default as TeacherResourcesPage } from './TeacherResourcesPage';
export { default as TeacherSettingsPage } from './TeacherSettingsPage';
// Independent-Teacher only: reduced workspace settings (Task #189 §5.2).
export { default as WorkspaceSettingsPage } from './WorkspaceSettingsPage';
// Independent-Teacher only: manual schedule editor (Task #193 §5.4).
export { default as WorkspaceSchedulePage } from './WorkspaceSchedulePage';
// Independent-Teacher only: personal calendar (Task #208 §6.3).
export { default as TeacherPersonalCalendarPage } from './TeacherPersonalCalendarPage';
// Independent-Teacher only: light AI lesson-planning assistant (Task #209 §6.4).
export { default as LessonPlannerPage, LessonPlannerPanel } from './LessonPlannerPage';
// Independent-Teacher only: workspace subject management (Task #190 §5.3).
export { default as TeacherSubjectsPage } from './TeacherSubjectsPage';
// Independent-Teacher only: workspace audit-log view (Task #248).
// 2026-05-18: also exports the headless `TeacherAuditLogPanel` so the
// Account Settings page can embed the same content inline.
export { default as TeacherAuditLogPage, TeacherAuditLogPanel } from './TeacherAuditLogPage';
// Independent-Teacher only: workspace analytics dashboard (Task #273).
export { default as TeacherAnalyticsPage } from './TeacherAnalyticsPage';
// Independent-Teacher only: notifications inbox (Task #249).
export { default as TeacherNotificationsPage } from './TeacherNotificationsPage';
