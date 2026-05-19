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
// 2026-05-18 — Unified "التواصل والإشعارات" hub (IT-only) merges
// the inbox + composer under one route. The IT branch in
// TeacherCommunicationPage renders this hub directly.
export { default as UnifiedCommunicationsHub } from './UnifiedCommunicationsHub';
export { IndependentTeacherCommunicationPanel } from './IndependentTeacherCommunicationPage';
export { default as TeacherResourcesPage } from './TeacherResourcesPage';
// 2026-05-18 — TeacherSettingsPage was folded into the canonical
// `/account/settings` hub (AccountSettingsPage). The legacy route
// now redirects there, so we no longer export the page component
// to keep the bundle clean and prevent accidental re-wiring.
// Independent-Teacher only: reduced workspace settings (Task #189 §5.2).
export { default as WorkspaceSettingsPage } from './WorkspaceSettingsPage';
// Independent-Teacher only: manual schedule editor (Task #193 §5.4).
// 2026-05-18 — Also re-exports the headless `WorkspaceSchedulePanel`
// so TeacherClassesPage can embed it as its fourth "جدولي" tab.
export { default as WorkspaceSchedulePage, WorkspaceSchedulePanel } from './WorkspaceSchedulePage';
// 2026-05-18 — IT-only workspace subjects CRUD. Also re-exports the
// headless `TeacherSubjectsPanel` so TeacherClassesPage can embed it
// as a fifth "المواد" tab without rendering a nested Sidebar.
export { default as TeacherSubjectsPage, TeacherSubjectsPanel } from './TeacherSubjectsPage';
// Independent-Teacher only: personal calendar (Task #208 §6.3).
export { default as TeacherPersonalCalendarPage } from './TeacherPersonalCalendarPage';
// Independent-Teacher only: light AI lesson-planning assistant (Task #209 §6.4).
export { default as LessonPlannerPage, LessonPlannerPanel } from './LessonPlannerPage';
// 2026-05-18 — Duplicate `TeacherSubjectsPage` export removed; the
// canonical re-export (with `TeacherSubjectsPanel`) lives above so
// barrel consumers resolve a single named export.
// Independent-Teacher only: workspace audit-log view (Task #248).
// 2026-05-18: also exports the headless `TeacherAuditLogPanel` so the
// Account Settings page can embed the same content inline.
export { default as TeacherAuditLogPage, TeacherAuditLogPanel } from './TeacherAuditLogPage';
// Independent-Teacher only: workspace analytics dashboard (Task #273).
export { default as TeacherAnalyticsPage } from './TeacherAnalyticsPage';
// Independent-Teacher only: notifications inbox (Task #249).
export { default as TeacherNotificationsPage, TeacherNotificationsPanel } from './TeacherNotificationsPage';
